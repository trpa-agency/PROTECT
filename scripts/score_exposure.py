"""Exposure scores (E_<pair>_hist, 0 to 3) from classed hazard surfaces, per docs/SCORING_RUBRICS.md.

Two jobs, both config-driven (config.yaml `exposure:`):

  1. Build the classed hazard surface in the hazards geodatabase (exposure.hazards_gdb), so
     every pair in both lanes samples the same classes. Flood today: the FEMA flood zones and
     the mapped streams classed on the FL-C E1 values (1 percent zone 3, 0.2 percent zone or a
     mapped stream 2, NHD flowline outside a zone 1 when a flowline layer is configured,
     otherwise 0). Landslide, wildfire, debris flow, and avalanche plug in the same way.
  2. Sample it per asset on the rubric's sampling rule (section 1.7) and write the scores:
       culverts   maximum over the contributing watershed (CulvertWatersheds_inc aggregated up
                  the drainage tree from CulvertCrossings), 25 m buffer where no watershed;
                  FL-C tailwater modifier +1 (cap 3) where tailwater_flag is set
       bridges    maximum within 25 m; FL-B combines E1 waterway adequacy (NBI item 71) at
                  0.20 with E2 the flood class at 0.10, weight-normalized to 0 to 3
       roads      maximum class touching the segment, plus the share of length in each class
       transit, active transport   maximum within 25 m / along the line (when those layers exist)

Usage (arcgispro-py3; runs on the server):
    python scripts/score_exposure.py --hazard flood --build                 # classed surface only
    python scripts/score_exposure.py --hazard flood --assets culverts bridges roads
    python scripts/score_exposure.py --hazard flood --assets culverts --dry-run   # CSV only
    python scripts/score_exposure.py --hazard flood --assets culverts bridges roads --overwrite

Outputs: fields on Culverts and Bridges (E_FLC_hist, E_FLC_pt, E_FLC_src, E_FLB_hist, E_FLB_e1,
E_FLB_e2, E_source), a table Exposure_<hazard>_roads in the analysis geodatabase (segment_id,
E_FLR_hist, length shares), and CSVs under outputs/ (NDOT rows go to the restricted QA folder).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from va_common import (REPO, fetch_rest_features, field_types, get_logger, load_cfg, read_streets, target_crs,
                       text_lengths, write_table)

HAZARD_CODE = {"flood": "FL", "landslide": "LS", "wildfire": "WF", "debris_flow": "DF", "avalanche": "AV"}

# ----------------------------------------------------------------------------------------
# pure scoring helpers (tested without arcpy)

def flood_class(zone, year) -> int:
    """FL-C E1 value for one FEMA polygon from its FLOOD_ZONE / FLOOD_YEAR attributes:
    3 for the 1 percent (100-yr) zones, 2 for the 0.2 percent (500-yr) zone, else 0."""
    z = (str(zone) if zone is not None else "").strip().upper()
    y = (str(year) if year is not None else "").strip().upper()
    if "100" in y or z in ("A", "AE", "AH", "AO", "A99", "V", "VE") or z.startswith("AE") or z.startswith("AO"):
        return 3
    if "500" in y or z in ("X500", "X 500", "B", "SHADED X") or "0.2" in z or "500" in z:
        return 2
    return 0


def waterway_score(code) -> float:
    """FL-B E1 from NBI item 71 (waterway adequacy). N = not over a waterway = 0; blank = 1."""
    if code is None or (isinstance(code, float) and np.isnan(code)):
        return 1.0
    c = str(code).strip().upper()
    if c == "":
        return 1.0
    if c == "N":
        return 0.0
    if not c.isdigit():
        return 1.0
    v = int(c)
    if v <= 1:
        return 3.0
    if v <= 3:
        return 2.5
    if v <= 5:
        return 2.0
    if v == 6:
        return 1.5
    if v <= 8:
        return 1.0
    return 0.5


def tree_max(values: dict[int, float], down_map: dict[int, int]) -> dict[int, float]:
    """Maximum of a per-zone value over each crossing's full upstream set. `down_map` is
    pp_id -> downstream pp_id. Cycles are cut the way culvert_profile does (walk downstream,
    drop the edge that returns to the walk). Leaves-first, no recursion."""
    down = dict(down_map)
    state: dict[int, int] = {}
    for start in list(values):
        n, path = start, []
        while state.get(n, 0) == 0:
            state[n] = 1
            path.append(n)
            nxt = down.get(n)
            if nxt is None:
                break
            if state.get(nxt) == 1:
                del down[n]
                break
            n = nxt
        for m in path:
            state[m] = 2
    children: dict[int, list[int]] = {}
    for c, par in down.items():
        if par in values:
            children.setdefault(par, []).append(c)
    full: dict[int, float] = {}
    pending = {pid: len(children.get(pid, [])) for pid in values}
    ready = [pid for pid, k in pending.items() if k == 0]
    while ready:
        pid = ready.pop()
        v = values.get(pid, 0.0)
        v = 0.0 if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)
        for ch in children.get(pid, []):
            v = max(v, full[ch])
        full[pid] = v
        par = down.get(pid)
        if par is not None and par in pending:
            pending[par] -= 1
            if pending[par] == 0:
                ready.append(par)
    return full


# ----------------------------------------------------------------------------------------
# classed surfaces

def build_flood_surface(cfg: dict, log, overwrite: bool) -> gpd.GeoDataFrame:
    """FEMA zones and mapped streams classed 0 to 3, dissolved by class, written to the hazards
    geodatabase as exposure.flood.class_fc with field `hz_class`. Returns the classed polygons."""
    import arcpy
    ex = cfg["exposure"]
    fl = ex["flood"]
    crs = target_crs(cfg)
    gdb = ex["hazards_gdb"]
    if not arcpy.Exists(gdb):
        arcpy.management.CreateFileGDB(str(Path(gdb).parent), Path(gdb).name)
        log.info(f"Created {gdb}")
    out_fc = f"{gdb}\\{fl['class_fc']}"
    if arcpy.Exists(out_fc) and not overwrite:
        log.info(f"{fl['class_fc']} exists; reading it (use --overwrite to rebuild)")
        import pyogrio
        return pyogrio.read_dataframe(gdb, layer=fl["class_fc"]).to_crs(crs)

    # FEMA zones with their attributes (fetch_rest_features keeps OBJECTID only, so query here)
    import requests
    frames, offset = [], 0
    url = fl["zones_layer"]
    while True:
        r = requests.get(f"{url}/query", params={"where": "1=1", "outFields": f"{fl['zone_field']},{fl['year_field']}",
                                                 "returnGeometry": "true", "f": "geojson",
                                                 "resultOffset": offset, "resultRecordCount": 1000}, timeout=300)
        r.raise_for_status()
        feats = r.json().get("features", [])
        if not feats:
            break
        frames.append(gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326"))
        offset += len(feats)
        if len(feats) < 1000:
            break
    zones = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs="EPSG:4326").to_crs(crs)
    zones["hz_class"] = [flood_class(z, y) for z, y in zip(zones[fl["zone_field"]], zones[fl["year_field"]])]
    # Lake Tahoe's own 1 percent stillwater zone (AE over the lake) is lake-stage flooding, the
    # high-lake-level pair the Steering Committee has not adopted; keep it out of the flood pairs
    # unless exposure.flood.include_lake_zone is true.
    if not fl.get("include_lake_zone", False):
        lake_cap = float(fl.get("exclude_water_over_km2", 1.0)) * 1e6
        big = zones.area > lake_cap
        if big.any():
            log.info(f"{int(big.sum())} FEMA polygon(s) over {lake_cap / 1e6:g} km2 dropped as lake-stage zones "
                     f"({zones.loc[big].area.sum() / 1e6:.0f} km2); set exposure.flood.include_lake_zone to keep them")
            zones = zones[~big]
    log.info(f"{len(zones)} FEMA polygons; class counts:\n" + zones["hz_class"].value_counts().to_string())
    unclassed = zones[zones["hz_class"] == 0]
    if len(unclassed):
        log.warning(f"{len(unclassed)} FEMA polygons scored 0; zone / year values: "
                    f"{unclassed[[fl['zone_field'], fl['year_field']]].drop_duplicates().head(10).to_dict('records')}")

    # mapped streams (lidar-derived polygons; the lake and large water bodies excluded) -> class 2
    streams = fetch_rest_features(fl["streams_layer"], crs, log)
    cap = float(fl.get("exclude_water_over_km2", 1.0)) * 1e6
    streams = streams[streams.area <= cap]
    sb = gpd.GeoDataFrame({"hz_class": [2] * len(streams)}, geometry=streams.buffer(float(fl["stream_buffer_m"])).values, crs=crs)
    log.info(f"{len(streams)} stream polygons (water bodies over {fl.get('exclude_water_over_km2', 1.0)} km2 excluded) "
             f"buffered {fl['stream_buffer_m']} m as class 2")

    parts = [zones[["hz_class", "geometry"]], sb]
    if fl.get("nhd_flowlines"):
        nhd = fetch_rest_features(fl["nhd_flowlines"], crs, log)
        parts.append(gpd.GeoDataFrame({"hz_class": [1] * len(nhd)}, geometry=nhd.buffer(float(fl["stream_buffer_m"])).values, crs=crs))
    allp = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs=crs)
    allp = allp[allp["hz_class"] > 0]
    dissolved = allp.dissolve(by="hz_class", as_index=False)[["hz_class", "geometry"]]
    # higher class wins where they overlap: subtract the higher classes from the lower
    geoms = {int(r.hz_class): r.geometry for r in dissolved.itertuples()}
    for c in sorted(geoms):
        for higher in [h for h in geoms if h > c]:
            geoms[c] = geoms[c].difference(geoms[higher])
    surf = gpd.GeoDataFrame({"hz_class": list(geoms)}, geometry=[geoms[c] for c in geoms], crs=crs)
    surf = surf[~surf.geometry.is_empty].explode(index_parts=False).reset_index(drop=True)
    log.info("Classed flood surface, area by class (km2):\n"
             + (surf.groupby("hz_class").geometry.apply(lambda g: g.area.sum() / 1e6)).round(2).to_string())

    # write
    sr = arcpy.SpatialReference(int(cfg["output"]["target_epsg"]))
    if arcpy.Exists(out_fc):
        arcpy.management.Delete(out_fc)
    arcpy.management.CreateFeatureclass(gdb, fl["class_fc"], "POLYGON", spatial_reference=sr)
    arcpy.management.AddFields(out_fc, [["hz_class", "SHORT", "hz_class", ""], ["hazard", "TEXT", "hazard", 20],
                                        ["label", "TEXT", "label", 80]])
    labels = {3: "1 percent (100-yr) flood zone", 2: "0.2 percent (500-yr) zone or mapped stream",
              1: "NHD flowline outside a zone"}
    with arcpy.da.InsertCursor(out_fc, ["SHAPE@", "hz_class", "hazard", "label"]) as cur:
        for r in surf.itertuples():
            cur.insertRow([arcpy.FromWKB(r.geometry.wkb), int(r.hz_class), "flood", labels.get(int(r.hz_class), "")])
    log.info(f"{len(surf)} polygons -> {out_fc}")
    return surf


SURFACE_BUILDERS = {"flood": build_flood_surface}


# ----------------------------------------------------------------------------------------
# sampling

def sample_points(pts: gpd.GeoDataFrame, surf: gpd.GeoDataFrame, buffer_m: float) -> pd.Series:
    """Maximum hz_class within buffer_m of each point (0 where none). Index = pts.index."""
    buf = gpd.GeoDataFrame(geometry=pts.geometry.buffer(buffer_m), crs=pts.crs)
    sj = gpd.sjoin(buf, surf[["hz_class", "geometry"]], how="left", predicate="intersects")
    return sj.groupby(level=0)["hz_class"].max().reindex(pts.index).fillna(0)


def sample_lines(lines: gpd.GeoDataFrame, surf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Maximum hz_class touching each line and the share of its length inside each class."""
    sj = gpd.sjoin(lines[["geometry"]], surf[["hz_class", "geometry"]], how="left", predicate="intersects")
    out = pd.DataFrame({"hz_max": sj.groupby(level=0)["hz_class"].max().reindex(lines.index).fillna(0)})
    total = lines.geometry.length.replace(0, np.nan)
    for c in sorted(surf["hz_class"].unique()):
        geom = surf.loc[surf["hz_class"] == c].geometry.union_all() if hasattr(surf.geometry, "union_all") \
            else surf.loc[surf["hz_class"] == c].geometry.unary_union
        inter = lines.geometry.intersection(geom)
        out[f"len_pct_c{int(c)}"] = (inter.length / total * 100).fillna(0).round(1)
    return out


def sample_watersheds(cfg: dict, surf: gpd.GeoDataFrame, log) -> pd.DataFrame:
    """Per crossing: maximum hz_class over its full contributing watershed (incremental zones
    aggregated up the drainage tree). Returns crossing_id -> hz_ws."""
    import pyogrio
    gdb = cfg["paths"]["analysis_gdb"]
    crs = target_crs(cfg)
    ws = pyogrio.read_dataframe(gdb, layer="CulvertWatersheds_inc").to_crs(crs)
    xt = pyogrio.read_dataframe(gdb, layer="CulvertCrossings", read_geometry=False)
    sj = gpd.sjoin(ws[["gridcode", "geometry"]], surf[["hz_class", "geometry"]], how="left", predicate="intersects")
    per_zone = sj.groupby("gridcode")["hz_class"].max().fillna(0)
    values = {int(pp): float(per_zone.get(int(pp), 0.0)) for pp in xt["crossing_pp"]}
    dn = xt.set_index("crossing_pp")["downstream_crossing_id"]
    id_to_pp = {f"X{int(pp):05d}": int(pp) for pp in xt["crossing_pp"]}
    down_map = {int(pp): id_to_pp[d] for pp, d in dn.items() if isinstance(d, str) and d in id_to_pp}
    full = tree_max(values, down_map)
    out = pd.DataFrame({"crossing_id": [f"X{int(pp):05d}" for pp in xt["crossing_pp"]],
                        "hz_ws": [full[int(pp)] for pp in xt["crossing_pp"]],
                        "hz_zone": [values[int(pp)] for pp in xt["crossing_pp"]]})
    log.info(f"Watershed sampling on {len(out)} crossings; class counts (full watershed):\n"
             + out["hz_ws"].value_counts().sort_index().to_string())
    return out


# ----------------------------------------------------------------------------------------
# per-asset scoring

def score_culverts(cfg: dict, hazard: str, surf: gpd.GeoDataFrame, log, dry_run: bool, overwrite: bool) -> pd.DataFrame:
    from culvert_profile import apply_by_key, ensure_fields, read_culverts, restricted_jurisdictions, write_split_csv
    ex = cfg["exposure"]
    code = HAZARD_CODE[hazard]
    pair = f"{code}C"
    h = ex["horizon"]
    cul = read_culverts(cfg, log)
    cul = cul[cul["scored"] == 1].copy() if "scored" in cul.columns else cul
    log.info(f"{len(cul)} scored culverts")
    pt = sample_points(cul, surf, float(ex["point_buffer_m"]))
    wsx = sample_watersheds(cfg, surf, log).set_index("crossing_id")["hz_ws"]
    cul["hz_pt"] = pt.values
    cul["hz_ws"] = cul["crossing_id"].map(wsx) if "crossing_id" in cul.columns else np.nan
    e = cul["hz_ws"].where(cul["hz_ws"].notna(), cul["hz_pt"])
    src = np.where(cul["hz_ws"].notna(), "watershed", "buffer")
    if hazard == "flood" and "tailwater_flag" in cul.columns:
        tw = cul["tailwater_flag"].fillna(0).astype(int) == 1
        e = (e + tw.astype(int)).clip(upper=3)
        log.info(f"Tailwater modifier applied on {int(tw.sum())} culverts")
    cul[f"E_{pair}_{h}"] = e.round(2)
    cul[f"E_{pair}_pt"] = cul["hz_pt"].round(2)
    cul[f"E_{pair}_src"] = src
    cul["E_source"] = np.where(src == "watershed", "full", "partial")
    log.info(f"E_{pair}_{h} distribution:\n" + cul[f"E_{pair}_{h}"].value_counts().sort_index().to_string())
    fields = [(f"E_{pair}_{h}", "DOUBLE", None), (f"E_{pair}_pt", "DOUBLE", None), (f"E_{pair}_src", "TEXT", 12),
              ("E_source", "TEXT", 10)]
    out = cul[["culvert_id", "jurisdiction", "crossing_id"] + [f[0] for f in fields]].copy()
    write_split_csv(out, f"exposure_{hazard}_culverts", cfg, log)
    if not dry_run:
        fc = f"{cfg['paths']['analysis_gdb']}\\{cfg['assets']['culverts_fc']}"
        ensure_fields(fc, fields, log)
        apply_by_key(fc, out, "culvert_id", fields, log)
    return out


def score_bridges(cfg: dict, hazard: str, surf: gpd.GeoDataFrame, log, dry_run: bool, overwrite: bool) -> pd.DataFrame:
    import pyogrio
    from culvert_profile import apply_by_key, ensure_fields
    ex = cfg["exposure"]
    code = HAZARD_CODE[hazard]
    pair = f"{code}B"
    h = ex["horizon"]
    gdb = cfg["paths"]["analysis_gdb"]
    br = pyogrio.read_dataframe(gdb, layer=cfg["assets"]["bridges_fc"]).to_crs(target_crs(cfg))
    hz = sample_points(br, surf, float(ex["point_buffer_m"]))
    br["hz_pt"] = hz.values
    fields = []
    if hazard == "flood":
        w = ex["flood"]["bridge_weights"]  # e1 waterway adequacy, e2 flood class
        e1 = br["waterway_eval"].map(waterway_score)
        e2 = br["hz_pt"].astype(float)
        br[f"E_{pair}_e1"], br[f"E_{pair}_e2"] = e1.round(2), e2.round(2)
        br[f"E_{pair}_{h}"] = ((w["e1"] * e1 + w["e2"] * e2) / (w["e1"] + w["e2"])).round(2)
        br["E_source"] = np.where(br["waterway_eval"].isna() | (br["waterway_eval"].astype(str).str.strip() == ""),
                                  "partial", "full")
        fields = [(f"E_{pair}_{h}", "DOUBLE", None), (f"E_{pair}_e1", "DOUBLE", None), (f"E_{pair}_e2", "DOUBLE", None),
                  ("E_source", "TEXT", 10)]
    else:
        br[f"E_{pair}_{h}"] = br["hz_pt"].round(2)
        br["E_source"] = "full"
        fields = [(f"E_{pair}_{h}", "DOUBLE", None), ("E_source", "TEXT", 10)]
    log.info(f"E_{pair}_{h} on {len(br)} structures:\n" + br[f"E_{pair}_{h}"].round(1).value_counts().sort_index().to_string())
    out = br[["bridge_id", "facility_carried", "feature_crossed"] + [f[0] for f in fields]].copy()
    p = REPO / cfg["paths"]["outputs"] / f"exposure_{hazard}_bridges.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(p, index=False)
    log.info(f"-> {p}")
    if not dry_run:
        fc = f"{gdb}\\{cfg['assets']['bridges_fc']}"
        ensure_fields(fc, fields, log)
        apply_by_key(fc, out, "bridge_id", fields, log)
    return out


def score_roads(cfg: dict, hazard: str, surf: gpd.GeoDataFrame, log, dry_run: bool, overwrite: bool) -> pd.DataFrame:
    """Road segments: the classed surface sampled along the segment, written to a standalone
    table (not onto the street layer, which the other lane owns) and a CSV for that lane."""
    import arcpy
    ex = cfg["exposure"]
    code = HAZARD_CODE[hazard]
    pair = f"{code}R"
    h = ex["horizon"]
    key = cfg["assets"]["streets_key"]
    st = read_streets(cfg, log)
    st = st.drop_duplicates(key).reset_index(drop=True)
    res = sample_lines(st, surf)
    out = pd.DataFrame({key: st[key].values, f"E_{pair}_{h}": res["hz_max"].values})
    for c in [c for c in res.columns if c.startswith("len_pct_")]:
        out[c] = res[c].values
    out["seg_len_m"] = st.geometry.length.round(1).values
    log.info(f"E_{pair}_{h} on {len(out)} segments:\n" + out[f"E_{pair}_{h}"].value_counts().sort_index().to_string())
    p = REPO / cfg["paths"]["outputs"] / f"exposure_{hazard}_roads.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(p, index=False)
    log.info(f"-> {p}")
    if not dry_run:
        name = f"Exposure_{hazard}_roads"
        tbl = f"{cfg['paths']['analysis_gdb']}\\{name}"
        if arcpy.Exists(tbl):
            if not overwrite:
                raise SystemExit(f"{tbl} exists; re-run with --overwrite")
            arcpy.management.Delete(tbl)
        fields = [(key, "TEXT", 64), (f"E_{pair}_{h}", "DOUBLE", None)] \
            + [(c, "DOUBLE", None) for c in out.columns if c.startswith("len_pct_")] + [("seg_len_m", "DOUBLE", None)]
        write_table(out, fields, cfg["paths"]["analysis_gdb"], name, log)
    return out


SCORERS = {"culverts": score_culverts, "bridges": score_bridges, "roads": score_roads}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hazard", default="flood", choices=list(HAZARD_CODE))
    ap.add_argument("--assets", nargs="*", default=[], choices=list(SCORERS), help="asset classes to score")
    ap.add_argument("--build", action="store_true", help="(re)build the classed surface")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="CSV only; no geodatabase writes")
    args = ap.parse_args()
    log = get_logger(f"score_exposure_{args.hazard}")
    cfg = load_cfg()
    builder = SURFACE_BUILDERS.get(args.hazard)
    if builder is None:
        raise SystemExit(f"No surface builder for {args.hazard} yet (flood is implemented)")
    surf = builder(cfg, log, overwrite=args.build or args.overwrite)
    if not args.assets:
        log.info("No --assets given; surface built only")
        return
    for a in args.assets:
        SCORERS[a](cfg, args.hazard, surf, log, args.dry_run, args.overwrite)
    log.info("Done")


if __name__ == "__main__":
    main()
