"""Build a PROTECT_VA update table from the ra2ce_v2 criticality results.

The published layer (Streets_Network_Tahoe, 18,285 in-basin features) carries 60
fields, only 20 of which come from RA2CE. The other 40 are hazard, equity, SLR,
AADT and Jenks work that has nothing to do with this rebuild. So this does NOT
rebuild the layer - it emits an update table keyed on OBJECTID carrying just the
20 OD fields, to be joined and field-calculated into the existing layer. Geometry,
OBJECTIDs and the other 40 fields stay exactly as they are.

Keying on OBJECTID means pulling the published geometry rather than assuming the
local source shapefile is in the same order. segment_id is not unique (51,933 ids
over 95,285 features), so it cannot be the key.

The join is two-sided on purpose. A one-sided "how much of this street does the
criticality row cover?" test is what produced the 388 NULLs in the first place:
preprocessing splits a colliding link in half, so each half covers only ~50% of
the street and a 50% threshold rejects both. Here a criticality row is accepted
when most of THAT ROW runs along the street (so a crossing street at a junction is
rejected), and it then contributes in proportion to how much of the street it
covers. Values are length-weighted means; routed / par_alt are maxima.

Writes to output/protect_va_update/:
  protect_va_od_update.csv     OBJECTID + 20 OD fields + QA columns
  protect_va_od_update.gpkg    same, with geometry, for a visual check
  protect_va_od_update_qa.txt  coverage report and old-vs-new comparison
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import shape
from shapely.strtree import STRtree

HERE = Path(__file__).resolve().parent
OUT = HERE / "output" / "protect_va_update"
CACHE = OUT / "protect_va_published.gpkg"
COMBINED = HERE / "output" / "tahoe_od_criticality_combined_v2.gpkg"

SERVICE = ("https://services5.arcgis.com/fXXSUzHD5JjcOt1v/arcgis/rest/services/"
           "PROTECT_VA/FeatureServer/0")

OD_FIELDS = [
    "traffic_evacuation", "egalitarian_evacuation", "prioritarian_evacuation",
    "routed_evacuation", "par_alt_evacuation",
    "traffic_law_enforcement", "egalitarian_law_enforcement",
    "prioritarian_law_enforcement", "routed_law_enforcement", "par_alt_law_enforcement",
    "traffic_medical_facilities", "egalitarian_medical_facilities",
    "prioritarian_medical_facilities", "routed_medical_facilities",
    "par_alt_medical_facilities",
    "traffic_emergency_shelters", "egalitarian_emergency_shelters",
    "prioritarian_emergency_shelters", "routed_emergency_shelters",
    "par_alt_emergency_shelters",
]
MAX_FIELDS = [f for f in OD_FIELDS if f.startswith(("routed_", "par_alt_"))]
MEAN_FIELDS = [f for f in OD_FIELDS if f not in MAX_FIELDS]

BUFFER_M = 5.0        # tolerance for "runs along"
MIN_ROW_COVER = 0.5   # a criticality row must lie >=50% along the street's interior
TRIM_M = 5.0          # endpoint trim used for the "runs along" test only
METRIC_CRS = 3310


def _interior(line, trim=TRIM_M):
    """The street minus `trim` metres at each end.

    The "runs along" test is applied against this, not the whole street. A short
    segment meeting this street end-on is collinear with it, so several metres of
    it fall inside a buffer of the full street - an 8 m neighbour scores 5/8 and
    passes a 50% test on geometry that belongs to the next street along. Trimming
    the ends removes that without affecting genuine covering rows, which overlap
    the interior. Streets too short to trim are used whole.
    """
    from shapely.geometry import MultiLineString
    from shapely.ops import substring
    if isinstance(line, MultiLineString):
        # the published layer holds a handful of multi-part streets; trim each
        # part independently and keep the parts too short to trim
        parts = [_interior(p, trim) for p in line.geoms]
        return MultiLineString([p for p in parts if not p.is_empty])
    if line.length <= 2.5 * trim:
        return line
    return substring(line, trim, line.length - trim)


def fetch_published(force=False):
    """Page the published layer down to a local GeoPackage."""
    if CACHE.exists() and not force:
        g = gpd.read_file(CACHE)
        print("published layer: {:,} features (cached)".format(len(g)))
        return g
    OUT.mkdir(parents=True, exist_ok=True)
    fields = ["OBJECTID", "segment_id", "name", "class", "length_m", "In_Basin"] + OD_FIELDS
    feats, offset, page = [], 0, 1000
    while True:
        url = (SERVICE + "/query?where=1%3D1&outFields=" + ",".join(fields) +
               "&returnGeometry=true&outSR=4326&f=geojson"
               "&resultOffset={}&resultRecordCount={}".format(offset, page))
        with urllib.request.urlopen(url, timeout=180) as r:
            d = json.load(r)
        got = d.get("features", [])
        if not got:
            break
        feats.extend(got)
        offset += len(got)
        print("  fetched {:,}".format(offset), end="\r", flush=True)
        if not d.get("properties", {}).get("exceededTransferLimit") and len(got) < page:
            break
        time.sleep(0.2)
    print("  fetched {:,} features      ".format(len(feats)))
    g = gpd.GeoDataFrame(
        [f["properties"] for f in feats],
        geometry=[shape(f["geometry"]) for f in feats],
        crs=4326,
    )
    g.to_file(CACHE, driver="GPKG")
    print("published layer: {:,} features -> {}".format(len(g), CACHE.name))
    return g


def build_update(pub):
    crit = gpd.read_file(COMBINED)
    print("criticality network: {:,} rows".format(len(crit)))

    pub_m = pub.to_crs(METRIC_CRS)
    crit_m = crit.to_crs(METRIC_CRS)
    crit_geom = list(crit_m.geometry)
    crit_len = np.array([g.length for g in crit_geom])
    tree = STRtree(crit_geom)
    vals = {f: crit_m[f].to_numpy() for f in OD_FIELDS}

    out = {f: np.full(len(pub_m), np.nan) for f in OD_FIELDS}
    coverage = np.zeros(len(pub_m))
    n_rows = np.zeros(len(pub_m), dtype=int)
    # how much the contributing rows disagree, as a share of the largest value.
    # 0 means every row on this street carried the same traffic, which is the
    # normal case for pieces of one road in series. A high value means the street
    # spans a junction where traffic genuinely changes, and the length-weighted
    # mean is a summary rather than a single true value.
    spread = np.zeros(len(pub_m))
    traffic_cols = [f for f in MEAN_FIELDS if f.startswith("traffic_")]

    t0 = time.time()
    for i, sgeom in enumerate(pub_m.geometry):
        if i % 2000 == 0:
            print("  joined {:,}/{:,}  ({:.0f}s)".format(i, len(pub_m), time.time() - t0),
                  end="\r", flush=True)
        if sgeom is None or sgeom.length == 0:
            continue
        sbuf = sgeom.buffer(BUFFER_M)
        ibuf = _interior(sgeom).buffer(BUFFER_M)
        cand = tree.query(sbuf)
        if len(cand) == 0:
            continue
        w, idx = [], []
        for j in cand:
            cg = crit_geom[j]
            if crit_len[j] <= 0:
                continue
            # two-sided: the row must run ALONG this street's interior, not just
            # touch its endpoint
            along = cg.intersection(ibuf).length / crit_len[j]
            if along < MIN_ROW_COVER:
                continue
            cov = sgeom.intersection(cg.buffer(BUFFER_M)).length / sgeom.length
            if cov <= 0:
                continue
            w.append(cov)
            idx.append(j)
        if not w:
            continue
        w = np.array(w)
        n_rows[i] = len(w)
        coverage[i] = min(float(w.sum()), 1.0)
        for f in MEAN_FIELDS:
            out[f][i] = float(np.dot(w, vals[f][idx]) / w.sum())
        for f in MAX_FIELDS:
            out[f][i] = float(np.max(vals[f][idx]))
        if len(w) > 1:
            worst = 0.0
            for f in traffic_cols:
                v = vals[f][idx]
                hi = float(np.max(v))
                if hi > 0:
                    worst = max(worst, float(np.ptp(v)) / hi)
            spread[i] = worst
    print("  joined {:,}/{:,}  ({:.0f}s)      ".format(len(pub_m), len(pub_m), time.time() - t0))

    upd = pd.DataFrame({"OBJECTID": pub["OBJECTID"].values})
    for f in OD_FIELDS:
        upd[f] = out[f]
    upd["od_coverage_pct"] = (100 * coverage).round(1)
    upd["od_source_rows"] = n_rows
    upd["od_row_spread_pct"] = (100 * spread).round(1)
    return upd, pub


def report(upd, pub):
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    n = len(upd)
    old_null = int(pub["traffic_medical_facilities"].isna().sum())
    new_null = int(upd["traffic_medical_facilities"].isna().sum())
    say("PROTECT_VA OD update - QA")
    say("=" * 60)
    say("features: {:,}".format(n))
    say("")
    say("NULL traffic_medical_facilities:")
    say("  published (scripts/ra2ce)  : {:,}".format(old_null))
    say("  this update (ra2ce_v2)     : {:,}".format(new_null))
    say("  recovered                  : {:,}".format(old_null - new_null))
    say("")
    cov = upd["od_coverage_pct"]
    say("coverage of each street by criticality rows:")
    say("  >=95%      : {:,} ({:.1f}%)".format(int((cov >= 95).sum()), 100 * (cov >= 95).mean()))
    say("  50-95%     : {:,}".format(int(((cov >= 50) & (cov < 95)).sum())))
    say("  1-50%      : {:,}".format(int(((cov > 0) & (cov < 50)).sum())))
    say("  0% (NULL)  : {:,}".format(int((cov == 0).sum())))
    say("")
    multi = upd["od_source_rows"] > 1
    sp = upd["od_row_spread_pct"]
    say("streets built from more than one criticality row: {:,}".format(int(multi.sum())))
    say("  contributing rows agree exactly on traffic : {:,}".format(int((multi & (sp == 0)).sum())))
    say("  disagree by >5% of the largest value       : {:,}".format(int((sp > 5).sum())))
    say("  disagree by >20%                           : {:,}".format(int((sp > 20).sum())))
    say("  (values are length-weighted means; check od_row_spread_pct before")
    say("   quoting a single figure for one of these streets)")
    say("")
    say("traffic > 0 counts, published -> update:")
    for f in ("traffic_evacuation", "traffic_law_enforcement",
              "traffic_medical_facilities", "traffic_emergency_shelters"):
        o = int((pub[f].fillna(0) > 0).sum())
        nn = int((upd[f].fillna(0) > 0).sum())
        say("  {:<34} {:>7,} -> {:>7,}  ({:+,})".format(f, o, nn, nn - o))
    say("")
    say("total routed population, published -> update:")
    for f in ("traffic_evacuation", "traffic_law_enforcement",
              "traffic_medical_facilities", "traffic_emergency_shelters"):
        o = float(pub[f].fillna(0).sum())
        nn = float(upd[f].fillna(0).sum())
        say("  {:<34} {:>14,.0f} -> {:>14,.0f}".format(f, o, nn))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download the published layer")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    if not COMBINED.exists():
        raise SystemExit("run export_combined.py first - {} missing".format(COMBINED))
    pub = fetch_published(force=a.refresh)
    upd, pub = build_update(pub)

    csv = OUT / "protect_va_od_update.csv"
    upd.to_csv(csv, index=False)
    print("\nwrote {}  ({:,} rows, {} columns)".format(csv.name, len(upd), len(upd.columns)))

    g = gpd.GeoDataFrame(upd.merge(pub[["OBJECTID", "segment_id", "name", "class", "geometry"]],
                                   on="OBJECTID", how="left"),
                         geometry="geometry", crs=pub.crs)
    g.to_file(OUT / "protect_va_od_update.gpkg", driver="GPKG")
    print("wrote protect_va_od_update.gpkg (with geometry, for a visual check)")

    txt = report(upd, pub)
    (OUT / "protect_va_od_update_qa.txt").write_text(txt, encoding="utf-8")
    print("\nwrote protect_va_od_update_qa.txt")


if __name__ == "__main__":
    sys.exit(main())
