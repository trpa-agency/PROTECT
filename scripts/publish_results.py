"""Publish draft VA results for the web pages: public-jurisdiction culverts with the profile and
exposure fields, the bridges, the classed flood surface, the wildfire scores on roads, paths, and
transit hubs with the two wildfire surfaces, and a summary JSON for the page KPIs.

    python scripts/publish_results.py            # writes data/processed/results/*
    python scripts/publish_results.py --dry-run  # counts only

Everything written here is served by GitHub Pages, so the restricted jurisdiction (NDOT) is
excluded at the row level, never aggregated in, and the file names carry no restricted name.
The flood surface is simplified to 5 m for size. Run on the server (reads the geodatabases).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from va_common import REPO, get_logger, load_cfg, read_streets, target_crs

CULVERT_COLS = ["culvert_id", "jurisdiction", "road_name", "feature_type", "parent_segment_id", "crossing_id",
                "barrels", "span_in", "d_eq_in", "size_class", "material_class", "contrib_area_ac",
                "basin_slope_pct", "basin_landcover", "basin_precip_in", "q_method", "q_region",
                "q_event_25_cfs", "q_event_100_cfs", "q_cap_crossing_cfs", "load_ratio_25", "load_ratio_100",
                "cond_class", "cond_source", "cond_stale", "blockage_pct", "tailwater_flag", "on_stream",
                "size_suspect", "ratio_review", "profile_completeness", "E_FLC_hist", "E_FLC_pt", "E_FLC_src",
                "E_LSC_hist", "E_LSC_e1", "E_LSC_pt", "E_source",
                "S_FLC", "V_FLC_hist", "S_LSC", "V_LSC_hist", "V_max", "V_max_pair", "V_class", "S_source"]
BRIDGE_COLS = ["bridge_id", "state", "owner", "facility_carried", "feature_crossed", "year_built",
               "is_culvert_type", "main_spans", "max_span_m", "waterway_eval", "scour_code", "scour_label",
               "channel_cond", "lowest_rating", "bridge_condition_label", "water_crossing", "parent_segment_id",
               "E_FLB_hist", "E_FLB_e1", "E_FLB_e2", "E_LSB_hist", "E_LSB_e1", "E_source"]
ROAD_COLS = ["src_objectid", "name", "class", "E_{p}_hist", "E_{p}_e1", "E_{p}_e2", "len_pct_c1", "len_pct_c2",
             "len_pct_c3", "seg_len_m"]
WF_ROAD_COLS = [c.format(p="WFR") for c in ROAD_COLS]
ROUND = {"contrib_area_ac": 1, "basin_slope_pct": 1, "basin_precip_in": 1, "q_event_25_cfs": 1, "q_event_100_cfs": 1,
         "q_cap_crossing_cfs": 1, "load_ratio_25": 2, "load_ratio_100": 2, "max_span_m": 1, "span_in": 1, "d_eq_in": 1}


def public_only(df: pd.DataFrame, cfg: dict, log) -> pd.DataFrame:
    from culvert_profile import restricted_jurisdictions
    restricted = restricted_jurisdictions(cfg) | {"NDOT"}
    keep = ~df["jurisdiction"].isin(restricted)
    log.info(f"{int((~keep).sum())} restricted rows excluded; {int(keep.sum())} public rows")
    return df[keep]


def tidy(gdf: gpd.GeoDataFrame, cols: list[str]) -> gpd.GeoDataFrame:
    cols = [c for c in cols if c in gdf.columns]
    out = gdf[cols + ["geometry"]].copy()
    for c, n in ROUND.items():
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").round(n)
    for c in out.columns:
        if c != "geometry" and str(out[c].dtype).startswith(("Int", "int")):
            out[c] = out[c].astype("float").where(out[c].notna())
    return out.to_crs("EPSG:4326")


def write_watersheds(cfg: dict, out_dir: Path, log, simplify_m: float = 5.0) -> int:
    """One GeoJSON per public crossing under out_dir/watersheds/<crossing_id>.geojson with two
    features: part = direct (the crossing's own incremental zone) and part = upstream (every
    zone that reaches it through upstream crossings, dissolved). The page draws them on click.
    Restricted crossings get no file; an upstream union may cover ground drained through a
    restricted culvert, which is area, not an asset record."""
    import pyogrio
    from shapely.ops import unary_union
    gdb = cfg["paths"]["analysis_gdb"]
    ws = pyogrio.read_dataframe(gdb, layer="CulvertWatersheds_inc")
    xt = pyogrio.read_dataframe(gdb, layer="CulvertCrossings", read_geometry=False)
    inc = {int(r.gridcode): r.geometry.simplify(simplify_m, preserve_topology=True) for r in ws.itertuples()}
    pp_of = {r.crossing_id: int(r.crossing_pp) for r in xt.itertuples()}
    down = {int(r.crossing_pp): pp_of.get(r.downstream_crossing_id) for r in xt.itertuples()}
    children: dict[int, list[int]] = {}
    for c, par in down.items():
        if par is not None and par in down:
            children.setdefault(par, []).append(c)
    # leaves first, as in culvert_profile.aggregate_upstream (links were already cycle-cut there)
    pending = {pid: len(children.get(pid, [])) for pid in down}
    ready = [pid for pid, k in pending.items() if k == 0]
    up: dict[int, object] = {}
    n_up: dict[int, int] = {}
    while ready:
        pid = ready.pop()
        parts, count = [], 0
        for ch in children.get(pid, []):
            if ch in inc:
                parts.append(inc[ch])
            if up.get(ch) is not None:
                parts.append(up[ch])
            count += 1 + n_up.get(ch, 0)
        up[pid] = unary_union(parts) if parts else None
        n_up[pid] = count
        par = down.get(pid)
        if par is not None and par in pending:
            pending[par] -= 1
            if pending[par] == 0:
                ready.append(par)
    wdir = out_dir / "watersheds"
    wdir.mkdir(parents=True, exist_ok=True)
    for f in wdir.glob("*.geojson"):
        f.unlink()
    crs = ws.crs
    n = 0
    for r in xt.itertuples():
        pid = int(r.crossing_pp)
        if int(r.restricted) == 1 or pid not in inc:
            continue
        feats = [{"part": "direct", "crossing_id": r.crossing_id, "area_ac": round(inc[pid].area / 4046.8564, 1),
                  "geometry": inc[pid]}]
        if up.get(pid) is not None:
            feats.append({"part": "upstream", "crossing_id": r.crossing_id,
                          "area_ac": round(up[pid].area / 4046.8564, 1), "n_upstream": n_up.get(pid, 0),
                          "geometry": up[pid]})
        g = gpd.GeoDataFrame(feats, geometry="geometry", crs=crs).to_crs("EPSG:4326")
        g.to_file(wdir / f"{r.crossing_id}.geojson", driver="GeoJSON")
        n += 1
    log.info(f"{n} drainage files -> {wdir} ({sum(f.stat().st_size for f in wdir.glob('*.geojson')) / 1e6:.1f} MB)")
    return n


def _table(gdb: str, name: str, log):
    """Analysis-geodatabase table as a DataFrame, or None when it has not been written yet."""
    import arcpy
    import pyogrio
    if not arcpy.Exists(f"{gdb}\\{name}"):
        log.warning(f"{name} not in {gdb}; skipped")
        return None
    return pyogrio.read_dataframe(gdb, layer=name, read_geometry=False)


def _geojson(gdf: gpd.GeoDataFrame, path: Path, log, precision: int = 5) -> None:
    gdf.to_crs("EPSG:4326").to_file(path, driver="GeoJSON", COORDINATE_PRECISION=precision)
    log.info(f"{len(gdf)} features -> {path.name} ({path.stat().st_size / 1e6:.2f} MB)")


def slim_surface(surf: gpd.GeoDataFrame, crs, log, stem: str, simplify_m: float = 20.0,
                 many: int = 20000, min_ha: float = 0.5) -> gpd.GeoDataFrame:
    """Web-size a classed surface: simplify, and when it has more than `many` parts drop the
    parts under min_ha (the severity surface has 58,896 parts and 25 MB otherwise). The
    dropped area is logged; the summary areas are computed before this."""
    surf = surf.copy()
    surf["geometry"] = surf.geometry.simplify(simplify_m, preserve_topology=True)
    if len(surf) > many:
        a = surf.to_crs(crs).area / 1e4
        keep = a >= min_ha
        log.info(f"{stem}: {int((~keep).sum())} of {len(surf)} parts under {min_ha:g} ha dropped for the web layer "
                 f"({a[~keep].sum() / 100:.1f} of {a.sum() / 100:.1f} km2)")
        surf = surf[keep]
    return surf


def _e_counts(series: pd.Series) -> dict:
    return {str(k): int(v) for k, v in series.round(1).value_counts().sort_index().items()}


def write_hazard_roads(cfg: dict, out_dir: Path, log, hazard: str, pair: str):
    """Road scores for one hazard joined to the street geometry -> roads_<hazard>.geojson and
    .csv, plus the summary block. Returns (frame, summary) or (None, None) when the table is
    not there yet."""
    import pyogrio
    gdb = cfg["paths"]["analysis_gdb"]
    crs = target_crs(cfg)
    key = cfg["assets"]["streets_key"]
    roads = _table(gdb, f"Exposure_{hazard}_roads", log)
    if roads is None:
        return None, None
    info = pyogrio.read_info(cfg["assets"]["streets_gdb"], layer=cfg["assets"]["streets_fc"])
    extra = [c for c in ("name", "class") if c in list(info["fields"])]
    st = read_streets(cfg, log, columns=extra).drop_duplicates(key)
    roads[key] = roads[key].astype(str)
    r = st.merge(roads, on=key, how="inner")
    r["geometry"] = r.geometry.simplify(5, preserve_topology=True)
    for c in ("name", "class"):
        if c not in r.columns:
            r[c] = None
    cols = [c.format(p=pair) for c in ROAD_COLS]
    r = r[[c for c in cols if c in r.columns] + ["geometry"]]
    ecols = [c for c in (f"E_{pair}_hist", f"E_{pair}_e1", f"E_{pair}_e2") if c in r.columns]
    for c in ecols:
        r[c] = pd.to_numeric(r[c], errors="coerce").round(2)
    r["seg_len_m"] = pd.to_numeric(r["seg_len_m"], errors="coerce").round(1)
    _geojson(gpd.GeoDataFrame(r, geometry="geometry", crs=crs), out_dir / f"roads_{hazard}.geojson", log)
    pd.DataFrame(r.drop(columns="geometry")).to_csv(out_dir / f"roads_{hazard}.csv", index=False)
    mi = r["seg_len_m"] / 1609.344
    e = r[f"E_{pair}_hist"]
    summ = {"segments": int(len(r)), "miles": round(float(mi.sum()), 1), "E": _e_counts(e),
            "miles_by_E": {str(k): round(float(v), 1) for k, v in mi.groupby(e.round(1)).sum().items()},
            "zero_segments": int((e == 0).sum())}
    for name in ("e1", "e2"):
        c = f"E_{pair}_{name}"
        if c in r.columns:
            summ[name.upper()] = _e_counts(r[c])
            summ[f"miles_by_{name.upper()}"] = {str(k): round(float(v), 1) for k, v in mi.groupby(r[c].round(1)).sum().items()}
    if "class" in r.columns and r["class"].notna().any():
        summ["miles_by_class_E"] = {str(c): {str(k): round(float(v), 1) for k, v in
                                             mi[r["class"] == c].groupby(e[r["class"] == c].round(1)).sum().items()}
                                    for c in sorted(r["class"].dropna().unique())}
    return r, summ


def write_landslide(cfg: dict, out_dir: Path, log, cul: gpd.GeoDataFrame, br: gpd.GeoDataFrame) -> dict | None:
    """Landslide exposure (LS-R, LS-C, LS-B): roads joined to the street geometry, the classed
    susceptibility surface, and the summary block; the culvert and bridge columns ride on the
    flood exports (E_LSC_*, E_LSB_*)."""
    import pyogrio
    ls = cfg["exposure"]["landslide"]
    r, summ = write_hazard_roads(cfg, out_dir, log, "landslide", "LSR")
    if r is None:
        return None
    summary = {"roads": summ}
    mi = r["seg_len_m"] / 1609.344
    summary["roads"]["miles_e1_class3"] = round(float(mi[r["E_LSR_e1"] >= 3].sum()), 1) if "E_LSR_e1" in r.columns else None
    if "E_LSC_hist" in cul.columns:
        summary["culverts"] = {"scored": int(cul["E_LSC_hist"].notna().sum()), "E": _e_counts(cul["E_LSC_hist"].dropna()),
                               "E1": _e_counts(cul["E_LSC_e1"].dropna()) if "E_LSC_e1" in cul.columns else {},
                               "n_e1_class3": int((cul.get("E_LSC_e1", pd.Series(dtype=float)) >= 3).sum()),
                               "by_jurisdiction_e1_class3": {j: int(n) for j, n in
                                                             cul.loc[cul.get("E_LSC_e1", pd.Series(dtype=float)) >= 3, "jurisdiction"].value_counts().items()}}
    if "E_LSB_hist" in br.columns:
        summary["bridges"] = {"count": int(br["E_LSB_hist"].notna().sum()), "E": _e_counts(br["E_LSB_hist"].dropna()),
                              "n_e1_class3": int((br.get("E_LSB_e1", pd.Series(dtype=float)) >= 3).sum())}
    surf = pyogrio.read_dataframe(cfg["exposure"]["hazards_gdb"], layer=ls["class_fc"])
    summary["surface_km2"] = {str(int(k)): round(float(v), 1) for k, v in
                              surf.to_crs(target_crs(cfg)).groupby("hz_class").geometry.apply(lambda g: g.area.sum() / 1e6).items()}
    surf = slim_surface(surf, target_crs(cfg), log, "landslide_surface", simplify_m=10)
    _geojson(surf[["hz_class", "label", "geometry"]], out_dir / "landslide_surface.geojson", log)
    summary["inputs"] = {"e1": "USGS 2024 landslide susceptibility, share of the 90 m cell that is prone (over 80 = 3, over 60 = 2, over 40 = 1) or a recorded landslide (USGS inventory; polygons under "
                               f"{ls.get('recorded_max_area_km2', 10)} km2, points within {ls.get('recorded_point_buffer_m', 50)} m) = 3",
                         "e2": "Cal-Adapt precipitation change, 0 at the historical horizon by definition",
                         "weights": ls["weights"], "sampling": "culverts: maximum over the watershed; bridges: 25 m; roads: along the segment"}
    return summary


def write_wildfire(cfg: dict, out_dir: Path, log) -> dict | None:
    """Wildfire exposure (WF-R, WF-AT, WF-TC) for the results page: roads with their scores
    joined to the street geometry, the paths and transit hubs, the burn probability and E2
    (severity or flame length) surfaces, and the summary block. Skips cleanly when the tables are not there yet."""
    import pyogrio
    from score_exposure import fetch_with_fields
    gdb = cfg["paths"]["analysis_gdb"]
    hz_gdb = cfg["exposure"]["hazards_gdb"]
    wf = cfg["exposure"]["wildfire"]
    crs = target_crs(cfg)
    key = cfg["assets"]["streets_key"]
    r, summ = write_hazard_roads(cfg, out_dir, log, "wildfire", "WFR")
    if r is None:
        return None
    summary: dict = {"roads": summ}
    mi = r["seg_len_m"] / 1609.344
    summary["roads"]["miles_e2_class3"] = round(float(mi[r["E_WFR_e2"] >= 3].sum()), 1)
    summary["roads"]["miles_e_ge_1_6"] = round(float(mi[r["E_WFR_hist"] >= 1.6].sum()), 1)

    # paths (existing active transportation facilities) and transit hubs, geometry from the services
    at = _table(gdb, "Exposure_wildfire_active_transport", log)
    if at is not None:
        ex = cfg["exposure"]
        g = fetch_with_fields(ex["active_transport_layer"], [ex.get("active_transport_key", "OBJECTID"), "NAME", "CLASS"], crs, log)
        g["at_id"] = g[ex.get("active_transport_key", "OBJECTID")].astype(str)
        at["at_id"] = at["at_id"].astype(str)
        a = g.merge(at.drop(columns=[c for c in ("name",) if c in at.columns]), on="at_id", how="inner")
        a = a.rename(columns={"NAME": "name", "CLASS": "class"})
        a = a[["at_id", "name", "class", "E_WFAT_hist", "E_WFAT_e1", "E_WFAT_e2", "seg_len_m", "geometry"]]
        a["geometry"] = a.geometry.simplify(5, preserve_topology=True)
        _geojson(gpd.GeoDataFrame(a, geometry="geometry", crs=crs), out_dir / "paths_wildfire.geojson", log)
        summary["paths"] = {"count": int(len(a)), "miles": round(float(a["seg_len_m"].sum() / 1609.344), 1),
                            "E": _e_counts(a["E_WFAT_hist"]),
                            "miles_e_ge_1_6": round(float(a.loc[a["E_WFAT_hist"] >= 1.6, "seg_len_m"].sum() / 1609.344), 1)}
    tc = _table(gdb, "Exposure_wildfire_transit_centers", log)
    if tc is not None:
        ex = cfg["exposure"]
        k = ex.get("transit_centers_key", "OBJECTID")
        g = fetch_with_fields(ex["transit_centers_layer"], [k], crs, log)
        g["tc_id"] = g[k].astype(str)
        tc["tc_id"] = tc["tc_id"].astype(str)
        t = g.merge(tc, on="tc_id", how="inner")[["tc_id", "E_WFTC_hist", "E_WFTC_e1", "E_WFTC_e2", "geometry"]]
        _geojson(gpd.GeoDataFrame(t, geometry="geometry", crs=crs), out_dir / "transit_wildfire.geojson", log)
        summary["transit"] = {"count": int(len(t)), "E": _e_counts(t["E_WFTC_hist"]),
                              "n_e_ge_1_6": int((t["E_WFTC_hist"] >= 1.6).sum())}

    # the two surfaces (180 m cells; 20 m simplify keeps the shapes)
    areas = {}
    for name, stem in ((wf["bp_fc"], "wildfire_burnprob"), (wf["e2_fc"], "wildfire_e2")):
        surf = pyogrio.read_dataframe(hz_gdb, layer=name)
        areas[stem] = {str(int(k)): round(float(v), 1) for k, v in
                       surf.to_crs(crs).groupby("hz_class").geometry.apply(lambda g: g.area.sum() / 1e6).items()}
        surf = slim_surface(surf, crs, log, stem)
        _geojson(surf[["hz_class", "label", "geometry"]], out_dir / f"{stem}.geojson", log)
    summary["surfaces_km2"] = areas
    summary["inputs"] = {"e1": "Regional Resource Kit annual burn probability (Pyrologix 2022, 30 m), breaks 0.5 and 1 percent",
                         "e2": "contracted flame length, breaks 4 and 8 ft" if wf.get("flame_length_raster")
                               else "TRPA most-likely fire severity (RRK severity probabilities stacked; Low 1, Moderate 2, High 3)",
                         "sampling": f"maximum within {wf['buffer_ft']} ft", "weights": wf["weights"]}
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-watersheds", action="store_true", help="skip the per-crossing drainage files")
    ap.add_argument("--no-wildfire", action="store_true", help="skip the wildfire roads, paths, hubs, and surfaces")
    ap.add_argument("--no-landslide", action="store_true", help="skip the landslide roads and surface")
    args = ap.parse_args()
    log = get_logger("publish_results")
    cfg = load_cfg()
    import pyogrio
    gdb = cfg["paths"]["analysis_gdb"]
    a = cfg["assets"]
    out_dir = REPO / cfg["paths"]["processed"] / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    cul = pyogrio.read_dataframe(gdb, layer=a["culverts_fc"])
    cul = cul[cul["scored"] == 1] if "scored" in cul.columns else cul
    cul = public_only(cul, cfg, log)
    cul = tidy(cul, CULVERT_COLS)
    br = tidy(pyogrio.read_dataframe(gdb, layer=a["bridges_fc"]), BRIDGE_COLS)

    hz_gdb = cfg["exposure"]["hazards_gdb"]
    fl_fc = cfg["exposure"]["flood"]["class_fc"]
    flood = pyogrio.read_dataframe(hz_gdb, layer=fl_fc)
    flood["geometry"] = flood.geometry.simplify(5, preserve_topology=True)
    flood = flood[["hz_class", "label", "geometry"]].to_crs("EPSG:4326")

    lr = cul["load_ratio_100"]
    summary = {
        "generated": pd.Timestamp.today().strftime("%Y-%m-%d"),
        "culverts": {
            "scored_public": int(len(cul)),
            "full_profile": int((cul["profile_completeness"] == "full").sum()),
            "with_ratio": int(lr.notna().sum()),
            "ratio_over_1": int((lr >= 1).sum()),
            "ratio_median": float(lr.median()) if lr.notna().any() else None,
            "ratio_p90": float(lr.quantile(0.9)) if lr.notna().any() else None,
            "size_suspect": int((cul["size_suspect"] == 1).sum()) if "size_suspect" in cul else 0,
            "ratio_review": int((cul["ratio_review"] == 1).sum()) if "ratio_review" in cul else 0,
            "tailwater": int((cul["tailwater_flag"] == 1).sum()) if "tailwater_flag" in cul else 0,
            "regression": int(cul["q_method"].astype(str).str.startswith("regression").sum()),
            "E_FLC": {str(k): int(v) for k, v in cul["E_FLC_hist"].value_counts().sort_index().items()}
            if "E_FLC_hist" in cul else {},
            "by_jurisdiction": {j: int(n) for j, n in cul["jurisdiction"].value_counts().items()},
            "vulnerability": ({
                "V_FLC_median": float(cul["V_FLC_hist"].median()),
                "V_FLC_class": {str(k): int(v) for k, v in cul["V_FLC_hist"].map(
                    lambda v: None if pd.isna(v) else ("Low" if v < 1 else "Medium" if v < 2 else "High")).value_counts().items()},
                "V_class": {str(k): int(v) for k, v in cul["V_class"].value_counts().items()} if "V_class" in cul else {},
                "V_max_pair": {str(k): int(v) for k, v in cul["V_max_pair"].value_counts().items()} if "V_max_pair" in cul else {},
                "S_source": {str(k): int(v) for k, v in cul["S_source"].value_counts().items()} if "S_source" in cul else {},
                "high_by_jurisdiction": {j: int(n) for j, n in cul.loc[cul["V_FLC_hist"] >= 2, "jurisdiction"].value_counts().items()},
            } if "V_FLC_hist" in cul.columns and cul["V_FLC_hist"].notna().any() else None),
        },
        "bridges": {
            "count": int(len(br)),
            "water_crossings": int((br["water_crossing"] == 1).sum()) if "water_crossing" in br else None,
            "E_FLB": {str(k): int(v) for k, v in br["E_FLB_hist"].round(1).value_counts().sort_index().items()}
            if "E_FLB_hist" in br else {},
        },
        "flood_surface": {"polygons": int(len(flood)),
                          "area_km2_by_class": {str(int(k)): round(float(v), 1) for k, v in
                                                flood.to_crs(cfg["output"]["target_epsg"]).groupby("hz_class").geometry
                                                .apply(lambda g: g.area.sum() / 1e6).items()}},
        "notes": ["Public jurisdictions only; the restricted state DOT export is excluded at the row level.",
                  "Draft screening values for workshop review; the loading ratio ranks crossings and is not a design number."],
    }
    log.info(json.dumps(summary["culverts"], indent=1)[:800])
    if args.dry_run:
        log.info("Dry run; nothing written")
        return
    if not args.no_wildfire:
        wf_summary = write_wildfire(cfg, out_dir, log)
        if wf_summary:
            summary["wildfire"] = wf_summary
    if not args.no_landslide:
        ls_summary = write_landslide(cfg, out_dir, log, cul, br)
        if ls_summary:
            summary["landslide"] = ls_summary
    cul.to_file(out_dir / "culverts_results.geojson", driver="GeoJSON")
    br.to_file(out_dir / "bridges_results.geojson", driver="GeoJSON")
    flood.to_file(out_dir / "flood_surface.geojson", driver="GeoJSON")
    pd.DataFrame(cul.drop(columns="geometry")).to_csv(out_dir / "culverts_results.csv", index=False)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    for f in sorted(out_dir.glob("*.*")):
        log.info(f"{f.name}: {f.stat().st_size / 1e6:.2f} MB")
    if not args.no_watersheds:
        write_watersheds(cfg, out_dir, log)


if __name__ == "__main__":
    main()
