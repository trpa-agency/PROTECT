"""Map the v2 single link redundancy results onto the PROTECT_VA streets.

RA2CE reports SLR per edge of the simplified graph (output/single_link_redundancy/
tahoe_slr_v2.gpkg). Those edges are chains of Overture links, so their result is
first pushed down to every complex segment they cover, using RA2CE's own mapping
(base_network.feather: rfid_c -> rfid), which carries the true segment geometry.
The complex segments are then joined to the 18,285 published streets with the same
two-sided, endpoint-trimmed rule export_protect_va.py uses for the OD fields, so a
street only takes values from segments that run along it.

Per street:
  slr_diff_length   max extra detour distance (m) over contributing segments,
                    the conservative choice where a street spans a junction
  slr_detour        min: 0 if any contributing segment has no detour at all
  slr_alt_length    alternative route length (m) for the segment that set slr_diff_length

Self-loops (u == v, mostly cul-de-sac loops) are neutralized: RA2CE reports
diff_length = -length for them because the "alternative" from a node to itself
is 0 m. Removing a loop never disconnects anything, so they get detour = 1 and
diff_length = 0.

Other negative detours are clipped to 0. On the 2026-10-07 run there were 3,633:
2,139 are the longer member of a parallel pair (the alternative is the shorter
parallel edge), the other 1,489 are winding links whose endpoints are also joined
by a shorter route (median 16% shorter). Removing either kind adds no distance,
so 0 is the right value. The raw value is kept on the complex layer.

Writes to output/:
  tahoe_slr_v2_complex.gpkg                    complex segments with SLR attributes
  protect_va_update/protect_va_slr_update.csv  OBJECTID + SLR fields + QA columns
  protect_va_update/protect_va_slr_update_qa.txt
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.strtree import STRtree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from export_protect_va import (  # noqa: E402
    BUFFER_M, MIN_ROW_COVER, METRIC_CRS, OUT, _interior, fetch_published,
)

SLR = HERE / "output" / "single_link_redundancy" / "tahoe_slr_v2.gpkg"
BASE_NETWORK = HERE / "static" / "output_graph" / "base_network.feather"
COMPLEX_OUT = HERE / "output" / "tahoe_slr_v2_complex.gpkg"
OLD_SLR = HERE.parent / "ra2ce" / "output" / "single_link_redundancy" / "tahoe_slr.gpkg"


def complex_slr():
    """SLR attributes on every complex segment, via rfid_c -> rfid."""
    s = gpd.read_file(SLR, ignore_geometry=True)
    s = s[["u", "v", "rfid", "length", "alt_length", "diff_length", "detour"]].copy()
    loop = (s.u == s.v).to_numpy()
    raw_neg = int(((s.diff_length < 0) & ~loop).sum())
    s["selfloop"] = loop.astype("int16")
    s.loc[loop, ["diff_length", "detour"]] = [0.0, 1]
    s.loc[loop, "alt_length"] = np.nan
    s["diff_length_raw"] = s["diff_length"]
    s["diff_length"] = s["diff_length"].clip(lower=0)
    s = s.rename(columns={"length": "edge_length"}).drop(columns=["u", "v"])
    if s.rfid.duplicated().any():
        raise ValueError("rfid is not unique in the SLR output")

    bn = gpd.read_feather(BASE_NETWORK)[["rfid_c", "rfid", "geometry"]]
    bn = bn.set_crs(4326, allow_override=True)
    c = bn.merge(s, on="rfid", how="left")
    stats = dict(simple_edges=len(s), selfloops=int(loop.sum()), negative_non_loop=raw_neg,
                 complex_rows=len(c), complex_without_slr=int(c.detour.isna().sum()))
    return c, stats


def join_to_streets(pub, crit):
    """Two-sided, endpoint-trimmed join (export_protect_va rules), vectorized."""
    pub_m = pub.to_crs(METRIC_CRS).reset_index(drop=True)
    crit_m = crit[crit.detour.notna()].to_crs(METRIC_CRS).reset_index(drop=True)
    sg = pub_m.geometry.values
    cg = crit_m.geometry.values
    clen = shapely.length(cg)
    cbuf = shapely.buffer(cg, BUFFER_M)
    ibuf = shapely.buffer(np.array([_interior(g) for g in sg], dtype=object), BUFFER_M)

    si, ci = STRtree(cg).query(shapely.buffer(sg, BUFFER_M))
    ok = clen[ci] > 0
    si, ci = si[ok], ci[ok]
    along = shapely.length(shapely.intersection(cg[ci], ibuf[si])) / clen[ci]
    ok = along >= MIN_ROW_COVER
    si, ci = si[ok], ci[ok]
    cov = shapely.length(shapely.intersection(sg[si], cbuf[ci])) / shapely.length(sg[si])
    ok = cov > 0
    m = pd.DataFrame({"s": si[ok], "c": ci[ok], "w": cov[ok]})
    m["diff"] = crit_m.diff_length.to_numpy()[m.c]
    m["alt"] = crit_m.alt_length.to_numpy()[m.c]
    m["detour"] = crit_m.detour.to_numpy()[m.c]
    m["loop"] = crit_m.selfloop.to_numpy()[m.c]

    g = m.groupby("s")
    top = m.sort_values(["s", "diff"], ascending=[True, False], na_position="last").drop_duplicates("s")
    upd = pd.DataFrame({"OBJECTID": pub_m["OBJECTID"].to_numpy()})
    upd["slr_diff_length"] = g["diff"].max().reindex(upd.index)
    upd["slr_alt_length"] = top.set_index("s")["alt"].reindex(upd.index)
    upd["slr_detour"] = g["detour"].min().reindex(upd.index)
    upd["slr_selfloop_only"] = (g["loop"].min().reindex(upd.index) == 1).astype("int16")
    upd["slr_coverage_pct"] = (100 * g["w"].sum().clip(upper=1).reindex(upd.index)).fillna(0).round(1)
    upd["slr_source_rows"] = g.size().reindex(upd.index).fillna(0).astype(int)
    return upd


def report(upd, pub, stats):
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    say("PROTECT_VA SLR update - QA (ra2ce_v2 repaired graph)")
    say("=" * 60)
    say("simple edges analysed        : {:,}".format(stats["simple_edges"]))
    say("  self-loops neutralized     : {:,}".format(stats["selfloops"]))
    say("  negative detours, non-loop : {:,} (clipped to 0)".format(stats["negative_non_loop"]))
    say("complex segments             : {:,}  ({:,} with no simple edge)".format(
        stats["complex_rows"], stats["complex_without_slr"]))
    say("")
    d = upd.slr_detour
    say("streets: {:,}".format(len(upd)))
    say("  matched                    : {:,}".format(int(d.notna().sum())))
    say("  unmatched (NULL)           : {:,}".format(int(d.isna().sum())))
    say("  detour exists (1)          : {:,}".format(int((d == 1).sum())))
    say("  no detour (0)              : {:,}".format(int((d == 0).sum())))
    say("  coverage >=95%             : {:,}".format(int((upd.slr_coverage_pct >= 95).sum())))
    say("")
    if "class" in pub.columns:
        say("no detour, by class (published -> v2):")
        old = pub.get("slr_detour_max")
        for cls in ["trunk", "primary", "secondary", "tertiary", "residential", "service"]:
            sel = (pub["class"] == cls).to_numpy()
            o = int((old[sel] == 0).sum()) if old is not None else -1
            say("  {:<12} {:>6,} -> {:>6,}".format(cls, o, int((d[sel] == 0).sum())))
        say("")
    q = upd.slr_diff_length.dropna()
    say("slr_diff_length (m): median {:,.0f}, p90 {:,.0f}, max {:,.0f}".format(
        q.median(), q.quantile(0.9), q.max()))
    return "\n".join(lines)


def main():
    if not SLR.exists():
        raise SystemExit("run `pipeline.py --stages slr` first - {} missing".format(SLR))
    crit, stats = complex_slr()
    crit.to_file(COMPLEX_OUT, driver="GPKG")
    print("wrote {} ({:,} rows)".format(COMPLEX_OUT.name, len(crit)))

    pub = fetch_published()
    upd = join_to_streets(pub, crit)
    OUT.mkdir(parents=True, exist_ok=True)
    upd.to_csv(OUT / "protect_va_slr_update.csv", index=False)
    print("wrote protect_va_slr_update.csv ({:,} rows)".format(len(upd)))

    # published SLR fields for the comparison, read from the local layer
    try:
        import pyogrio
        gdb = r"F:\GIS\PROJECTS\Transportation\Protect\PROTECT_analysis\PROTECT_analysis.gdb"
        old = pyogrio.read_dataframe(gdb, layer="Streets_Network_Tahoe",
                                     columns=["class", "slr_detour_max"], read_geometry=False,
                                     fid_as_index=True).reindex(upd.OBJECTID.to_numpy())
        old = old.reset_index(drop=True)
    except Exception as e:  # comparison is optional
        print("published SLR fields unavailable ({}); report without comparison".format(e))
        old = pub[["class"]].reset_index(drop=True)
    txt = report(upd, old, stats)
    (OUT / "protect_va_slr_update_qa.txt").write_text(txt, encoding="utf-8")
    print("wrote protect_va_slr_update_qa.txt")


if __name__ == "__main__":
    sys.exit(main())
