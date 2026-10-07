"""NDOT SAM21 stormwater export -> the PROTECT culvert schema. RESTRICTED DATA.

The source is NDOT's statewide Stormwater Asset Management (SAM21) export, shared under a
sensitive / restricted data sharing agreement (config.yaml `ndot:` block). This module reads
it in place from TRPA-managed storage, keeps the basin subset of the Pipe and Reinforced
Concrete Box layers plus their inspection tables, and returns frames in the Culverts /
CulvertCondition schema used by load_culverts_gdb.py. It never writes under the repo: the
only outputs are QA CSVs in `ndot.work_dir` (also on F:) and, through the loader, rows in
the analysis geodatabase.

What the basin subset looks like (export of 2026-07-07, profiled 2026-10-07):
    Pipe                      1,493 features, 1,463 Active; SAM subtype blank on 1,460
    Reinforced_Concrete_Box      12 features, all Active
    Pipe_Inspection           1,314 visits on 884 pipes (2013-2026; 775 of them 2025-26)
    RCB_Inspection               21 visits on 12 boxes
The other SAM layers (drainage inlets, manholes, treatment structures, channels, basins)
are water-quality assets and stay out of the culvert layer, per the scope note in
docs/METHODS_culverts.md.

feature_type rule (the SAM subtype is blank on 98 percent of basin pipes):
    1. SAM subtype Culvert or Driveway/Approach           -> culvert          (rule "sam-subtype")
    2. SAM subtype Storm Drain / Down Drain / Subsurface  -> stormwater pipe  (rule "sam-subtype")
    3. otherwise, crosses a Streets_Network_Tahoe segment -> culvert          (rule "road-crossing")
       unless both ends are manholes (a storm-drain run)  -> stormwater pipe  (rule "manhole-run")
    4. otherwise                                          -> stormwater pipe  (rule "no-crossing")
Every box culvert is a culvert. The rule applied is recorded in `comments`.

Usage (arcgispro-py3), standalone QA only:
    python scripts/ndot_culverts.py        # reads, classifies, writes QA CSVs to ndot.work_dir
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from va_common import (dedupe_ids, fetch_basin, get_logger, line_rep_point, load_cfg,
                       read_streets, target_crs)

FT_PER_M = 3.280839895


def _s(v, n: int) -> str | None:
    """Trim a text value to n characters; None stays None."""
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA:
        return None
    v = str(v).strip()
    return v[:n] if v else None


def _join(parts: list[str | None], sep: str = " | ") -> str | None:
    parts = [p for p in parts if p]
    return sep.join(parts) if parts else None


def _dates(s: pd.Series, min_year: int) -> pd.Series:
    d = pd.to_datetime(s, errors="coerce", utc=True).dt.tz_localize(None)
    return d.where(d.dt.year >= min_year)


def _read_basin_layer(gdb: str, layer: str, basin: gpd.GeoDataFrame, crs: str, log) -> gpd.GeoDataFrame:
    """Read one SAM layer, bbox-filtered at the source then clipped to the TRPA boundary."""
    native_bbox = tuple(basin.to_crs("EPSG:3857").total_bounds)  # SAM export is Web Mercator
    g = gpd.read_file(gdb, layer=layer, bbox=native_bbox).to_crs(crs)
    inside = g.geometry.intersects(basin.geometry.union_all())
    log.info(f"[NDOT] {layer}: {len(g)} in bbox, {int(inside.sum())} intersect the TRPA boundary")
    return g[inside].reset_index(drop=True)


def _crosses_road(lines: gpd.GeoDataFrame, streets: gpd.GeoDataFrame, key: str) -> pd.Series:
    """True where a line intersects at least one street centerline."""
    sj = gpd.sjoin(lines[["geometry"]], streets[[key, "geometry"]], how="left", predicate="intersects")
    n = sj.groupby(level=0)[key].apply(lambda s: int(s.notna().sum()))
    return n.reindex(lines.index).fillna(0).astype(int) > 0


def _road_label(route: pd.Series, milepost: pd.Series) -> pd.Series:
    """'<RouteID> MP <mp>' from NDOT's route id and milepost; None when both are blank."""
    mp = pd.to_numeric(milepost, errors="coerce")
    label = route.fillna("").astype(str).str.strip() + mp.map(lambda v: "" if pd.isna(v) else f" MP {v:.2f}")
    return label.str.strip().replace("", None)


def _pipes(cfg: dict, raw: gpd.GeoDataFrame, streets: gpd.GeoDataFrame, log) -> tuple[pd.DataFrame, pd.Series]:
    nd = cfg["ndot"]
    j = nd["jurisdiction"]
    p = raw.copy()

    drop = p["FacilityStatus_PIP"].isin(nd["drop_status"])
    if drop.any():
        log.info("[NDOT] dropping pipes by status:\n" + p.loc[drop, "FacilityStatus_PIP"].value_counts().to_string())
    p = p[~drop].reset_index(drop=True)

    # --- feature_type ---
    sub = pd.to_numeric(p["F_Subtype"], errors="coerce")
    src_culv = (p["Display"] == "Culvert") | sub.isin(nd["culvert_subtypes"])
    src_pipe = sub.isin(nd["pipe_subtypes"]) & ~src_culv
    crosses = _crosses_road(p, streets, cfg["assets"]["streets_key"])
    # Manhole to manhole is a storm-drain trunk run even where it passes under a side street.
    manhole_run = p["EndConfigurationUpstream"].eq("Manhole") & p["EndConfigurationDownstream"].eq("Manhole")
    p["feature_type"] = "stormwater pipe"
    p["class_rule"] = "no-crossing"
    p.loc[crosses, ["feature_type", "class_rule"]] = ["culvert", "road-crossing"]
    p.loc[crosses & manhole_run, ["feature_type", "class_rule"]] = ["stormwater pipe", "manhole-run"]
    p.loc[src_pipe, ["feature_type", "class_rule"]] = ["stormwater pipe", "sam-subtype"]
    p.loc[src_culv, ["feature_type", "class_rule"]] = ["culvert", "sam-subtype"]
    log.info("[NDOT] pipe feature_type x rule:\n" + pd.crosstab(p["feature_type"], p["class_rule"]).to_string())

    # --- dimensions: Diameter_in for circular, Width x Height for the rest ---
    config = p["PipeConfiguration"].fillna("Circular")
    circular = config.eq("Circular")
    dia = pd.to_numeric(p["Diameter_in"], errors="coerce")
    width = pd.to_numeric(p["Width_in"], errors="coerce")
    height = pd.to_numeric(p["Height_in"], errors="coerce")
    span = dia.where(circular, width.fillna(dia))
    rise = height.where(~circular)
    bad = span > nd["max_diameter_in"]
    if bad.any():
        log.warning(f"[NDOT] {int(bad.sum())} pipe span values exceed {nd['max_diameter_in']} in; nulled")
    span = span.where(~bad)
    rise = rise.where(rise.gt(0))
    span = span.where(span.gt(0))

    length_src = pd.to_numeric(p["Length_ft"], errors="coerce")
    length = length_src.fillna((p.geometry.length * FT_PER_M).round(1))

    # --- key: AssetID, then Identification, then GlobalID ---
    key = p["AssetID"].where(p["AssetID"].notna(), p["Identification"]).where(
        lambda s: s.notna(), p["GlobalID"])
    p["source_id"] = dedupe_ids(key)

    install = pd.to_datetime(p["AssetInstallDate"], errors="coerce", utc=True).dt.year
    road = _road_label(p["RouteID1"], p["Milepost1"])

    material = p["PipeMaterial"].copy()
    notes_u = p["Notes"].fillna("").str.upper()
    other = material.eq("Other (See Notes)")
    material = material.mask(other & notes_u.str.contains("HDPE|POLYETHYLENE"), "HDPE (from notes)")
    material = material.mask(other & notes_u.str.contains("CIPP|CURED IN PLACE"), "Lined, cured in place (from notes)")

    comments = [
        _join([
            f"NDOT SAM {_s(r.Identification, 30) or '-'} / {_s(r.AssetID, 20) or '-'} / {r.GlobalID}",
            f"class {r.class_rule}",
            f"owner {_s(r.AssetOwner_PIP, 20)}" if _s(r.AssetOwner_PIP, 20) else None,
            f"status {_s(r.FacilityStatus_PIP, 25)}",
            f"maint {_s(r.MaintenanceStatus, 25)}" if _s(r.MaintenanceStatus, 25) else None,
            f"src {_s(r.FeatureSource_PIP, 30)}" if _s(r.FeatureSource_PIP, 30) else None,
            "length from geometry" if pd.isna(r.Length_ft) else None,
            f"desc: {_s(r.Description, 120)}" if _s(r.Description, 120) else None,
            f"notes: {_s(r.Notes, 120)}" if _s(r.Notes, 120) else None,
        ])
        for r in p.itertuples()
    ]

    out = pd.DataFrame({
        "jurisdiction": j,
        "source_id": p["source_id"],
        "culvert_id": f"{j}|" + p["source_id"],
        "feature_type": p["feature_type"],
        "road_name": road,
        "material": material,
        "xsection_shape": p["PipeConfiguration"].replace({"Eliptical": "Elliptical"}),
        "span_in": span,
        "rise_in": rise,
        "length_ft": length.round(1),
        "inlet_type": p["EndConfigurationUpstream"],
        "outlet_type": p["EndConfigurationDownstream"],
        "install_year": install.astype("Int64"),
        "comments": [_s(c, 500) for c in comments],
        "geom_source": f"line-{cfg['run']['line_to_point']}",
        "data_source": f"NDOT SAM21 {nd['layers']['pipes']} (export 2026-07-07)",
        "_globalid": p["GlobalID"].str.upper(),
        "_rule": p["class_rule"],
    })
    out = gpd.GeoDataFrame(out, geometry=p.geometry.apply(lambda g: line_rep_point(g, cfg["run"]["line_to_point"])),
                           crs=p.crs)
    lines = gpd.GeoSeries(p.geometry.values, index=out["culvert_id"].values, crs=p.crs)
    return out, lines


def _boxes(cfg: dict, raw: gpd.GeoDataFrame, log) -> tuple[pd.DataFrame, pd.Series]:
    nd = cfg["ndot"]
    j = nd["jurisdiction"]
    b = raw.copy()
    drop = b["FacilityStatus_RCB"].isin(nd["drop_status"])
    if drop.any():
        log.info(f"[NDOT] dropping {int(drop.sum())} boxes by status")
    b = b[~drop].reset_index(drop=True)

    key = b["AssetID"].where(b["AssetID"].notna(), b["Identification"]).where(lambda s: s.notna(), b["GlobalID"])
    b["source_id"] = dedupe_ids(key)
    width_ft = pd.to_numeric(b["Width_ft"], errors="coerce")
    height_ft = pd.to_numeric(b["Height_ft"], errors="coerce")
    length = pd.to_numeric(b["Length_ft"], errors="coerce").fillna((b.geometry.length * FT_PER_M).round(1))
    nboxes = pd.to_numeric(b["NumberOfBoxes"], errors="coerce")
    road = _road_label(b["RouteID1"], b["Milepost1"])

    comments = [
        _join([
            f"NDOT SAM {_s(r.Identification, 30) or '-'} / {_s(r.AssetID, 20) or '-'} / {r.GlobalID}",
            "class box-culvert",
            f"status {_s(r.FacilityStatus_RCB, 25)}",
            f"boxes {int(n)}" if pd.notna(n) and n > 1 else None,
            f"headwall up {_s(r.HeadwallTypeUpstream, 20)}" if _s(r.HeadwallTypeUpstream, 20) else None,
            f"outlet {_s(r.OutletConfiguration, 25)}" if _s(r.OutletConfiguration, 25) else None,
            f"src {_s(r.FeatureSource_RCB, 30)}" if _s(r.FeatureSource_RCB, 30) else None,
            f"desc: {_s(r.Description, 120)}" if _s(r.Description, 120) else None,
            f"notes: {_s(r.Notes, 120)}" if _s(r.Notes, 120) else None,
        ])
        for r, n in zip(b.itertuples(), nboxes)
    ]
    out = pd.DataFrame({
        "jurisdiction": j,
        "source_id": b["source_id"],
        "culvert_id": f"{j}|" + b["source_id"],
        "feature_type": "culvert",
        "road_name": road,
        "material": "Reinforced concrete",
        "xsection_shape": "Box",
        "span_in": (width_ft * 12).round(1),
        "rise_in": (height_ft * 12).round(1),
        "length_ft": length.round(1),
        "inlet_type": b["HeadwallTypeUpstream"],
        "outlet_type": b["OutletConfiguration"].where(b["OutletConfiguration"].notna(), b["HeadwallTypeDownstream"]),
        "install_year": pd.to_datetime(b["AssetInstallDate"], errors="coerce", utc=True).dt.year.astype("Int64"),
        "comments": [_s(c, 500) for c in comments],
        "geom_source": f"line-{cfg['run']['line_to_point']}",
        "data_source": f"NDOT SAM21 {nd['layers']['boxes']} (export 2026-07-07)",
        "_globalid": b["GlobalID"].str.upper(),
        "_rule": "box-culvert",
    })
    out = gpd.GeoDataFrame(out, geometry=b.geometry.apply(lambda g: line_rep_point(g, cfg["run"]["line_to_point"])),
                           crs=b.crs)
    lines = gpd.GeoSeries(b.geometry.values, index=out["culvert_id"].values, crs=b.crs)
    return out, lines


def _gfp(v) -> str | None:
    """Good/Fair/Poor domain values arrive as the code (Good/Fair/Poor), keep as-is."""
    return _s(v, 10)


def _pipe_inspections(cfg: dict, assets: pd.DataFrame, log) -> pd.DataFrame:
    nd = cfg["ndot"]
    t = pd.DataFrame(gpd.read_file(nd["gdb"], layer=nd["layers"]["pipe_inspection"]).drop(columns="geometry", errors="ignore"))
    t["_pg"] = t["ParentGlobal"].astype(str).str.upper()
    gid_to_id = dict(zip(assets["_globalid"], assets["culvert_id"]))
    t = t[t["_pg"].isin(gid_to_id)].copy()
    log.info(f"[NDOT] {len(t)} pipe inspections link to {t['_pg'].nunique()} basin pipes")

    def structural(r):
        return _s(_join([
            f"pav {r.Pipepavement}" if pd.notna(r.Pipepavement) else None,
            f"stab {r.Stabilization}" if pd.notna(r.Stabilization) else None,
            f"end {r.EndStructCond}" if pd.notna(r.EndStructCond) else None,
            f"joint sep {r.JointSeparation}" if pd.notna(r.JointSeparation) else None,
            f"overtop {r.RoadOvertop}" if pd.notna(r.RoadOvertop) else None,
            f"inlet eros {r.InletErosion}" if pd.notna(r.InletErosion) else None,
            f"outlet eros {r.OutletErosion}" if pd.notna(r.OutletErosion) else None,
        ], "; "), 60)

    def maint(r):
        return _s(_join([f"maintenance {r.Maintenance}" if pd.notna(r.Maintenance) else None,
                         f"activities {r.MaintActivities}" if pd.notna(r.MaintActivities) else None], "; "), 60)

    def notes(r):
        return _s(_join([_s(r.Comments, 200), _s(r.DescribePipe, 150),
                         f"inlet erosion: {_s(r.DescribeInletErosion, 80)}" if _s(r.DescribeInletErosion, 80) else None,
                         f"outlet erosion: {_s(r.DescribeOutletErosion, 80)}" if _s(r.DescribeOutletErosion, 80) else None]), 500)

    return pd.DataFrame({
        "culvert_id": t["_pg"].map(gid_to_id),
        "jurisdiction": nd["jurisdiction"],
        "inspection_date": _dates(t["InspectionDate"], nd["min_inspection_year"]),
        "condition_rating": t["OverallPipeCond"].map(_gfp),
        "condition_scheme": "NDOT SAM Good/Fair/Poor overall pipe condition (blank = not rated that visit); blockage 0-100 pct",
        "structural_cond": [structural(r) for r in t.itertuples()],
        "blockage_pct": pd.to_numeric(t["PercentBlockage"], errors="coerce"),
        "maintenance_need": [maint(r) for r in t.itertuples()],
        "inspector": t["InspectorName"].map(lambda v: _s(v, 120)),
        "notes": [notes(r) for r in t.itertuples()],
        "data_source": f"NDOT SAM21 {nd['layers']['pipe_inspection']}",
    })


def _box_inspections(cfg: dict, assets: pd.DataFrame, log) -> pd.DataFrame:
    nd = cfg["ndot"]
    t = pd.DataFrame(gpd.read_file(nd["gdb"], layer=nd["layers"]["box_inspection"]).drop(columns="geometry", errors="ignore"))
    t["_pg"] = t["ParentGlobal"].astype(str).str.upper()
    gid_to_id = dict(zip(assets["_globalid"], assets["culvert_id"]))
    t = t[t["_pg"].isin(gid_to_id)].copy()
    log.info(f"[NDOT] {len(t)} box inspections link to {t['_pg'].nunique()} basin boxes")

    def structural(r):
        return _s(_join([
            f"pav {r.RCBpavement}" if pd.notna(r.RCBpavement) else None,
            f"embank {r.EmbankErosion}" if pd.notna(r.EmbankErosion) else None,
            f"box eros {r.RCBErosion}" if pd.notna(r.RCBErosion) else None,
            f"end {r.EndStructCond}" if pd.notna(r.EndStructCond) else None,
            f"joint sep {r.JointSeparation}" if pd.notna(r.JointSeparation) else None,
            f"overtop {r.RoadwayOvertop}" if pd.notna(r.RoadwayOvertop) else None,
        ], "; "), 60)

    def maint(r):
        return _s(_join([f"maintenance {r.Maintenance}" if pd.notna(r.Maintenance) else None,
                         f"activities {r.MaintActivities}" if pd.notna(r.MaintActivities) else None], "; "), 60)

    def notes(r):
        return _s(_join([_s(r.Comments, 200), _s(r.OverallRCBCondition, 150), _s(r.DescribeRCBCond, 120)]), 500)

    return pd.DataFrame({
        "culvert_id": t["_pg"].map(gid_to_id),
        "jurisdiction": nd["jurisdiction"],
        "inspection_date": _dates(t["InspectionDate"], nd["min_inspection_year"]),
        "condition_rating": t["GeneralCondition"].map(_gfp),
        "condition_scheme": "NDOT SAM Good/Fair/Poor general box condition (blank = not rated that visit); blockage 0-100 pct",
        "structural_cond": [structural(r) for r in t.itertuples()],
        "blockage_pct": pd.to_numeric(t["RCBBlockage"], errors="coerce"),
        "maintenance_need": [maint(r) for r in t.itertuples()],
        "inspector": t["InspectorName"].map(lambda v: _s(v, 120)),
        "notes": [notes(r) for r in t.itertuples()],
        "data_source": f"NDOT SAM21 {nd['layers']['box_inspection']}",
    })


def read_ndot(cfg: dict, log, streets: gpd.GeoDataFrame, basin: gpd.GeoDataFrame | None = None,
              ) -> tuple[gpd.GeoDataFrame, pd.DataFrame, gpd.GeoSeries]:
    """Basin subset of the NDOT export in the culvert schema.

    Returns (culverts, condition, lines): culverts is a point GeoDataFrame in the target CRS
    with the Culverts columns plus `_globalid` and `_rule`; condition is a CulvertCondition
    frame; lines holds the original pipe/box geometries indexed by culvert_id, for the
    legacy-point match in the loader (distance to the whole line, not the midpoint).
    """
    nd = cfg["ndot"]
    crs = target_crs(cfg)
    if basin is None:
        basin = fetch_basin(cfg, log)
    streets = streets.to_crs(crs)
    log.warning("[NDOT] RESTRICTED source: %s - derived rows go to the analysis geodatabase only", nd["gdb"])

    raw_p = _read_basin_layer(nd["gdb"], nd["layers"]["pipes"], basin, crs, log)
    raw_b = _read_basin_layer(nd["gdb"], nd["layers"]["boxes"], basin, crs, log)
    pipes, p_lines = _pipes(cfg, raw_p, streets, log)
    boxes, b_lines = _boxes(cfg, raw_b, log)
    culverts = gpd.GeoDataFrame(pd.concat([pipes, boxes], ignore_index=True), geometry="geometry", crs=crs)
    lines = pd.concat([p_lines, b_lines])
    dup = culverts["culvert_id"].duplicated().sum()
    if dup:
        raise ValueError(f"[NDOT] {dup} duplicate culvert_id after keying; inspect AssetID / Identification")

    condition = pd.concat([_pipe_inspections(cfg, culverts, log), _box_inspections(cfg, culverts, log)],
                          ignore_index=True)
    log.info(f"[NDOT] {len(culverts)} assets ({(culverts['feature_type'] == 'culvert').sum()} culverts, "
             f"{(culverts['feature_type'] == 'stormwater pipe').sum()} stormwater pipes), "
             f"{len(condition)} condition records on {condition['culvert_id'].nunique()} assets")
    return culverts, condition, lines


def write_qa(culverts: gpd.GeoDataFrame, condition: pd.DataFrame, cfg: dict, log) -> Path:
    """QA CSVs into ndot.work_dir (restricted; on F:, never under the repo)."""
    work = Path(cfg["ndot"]["work_dir"])
    if work.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise RuntimeError("ndot.work_dir must not be inside the repo (restricted data)")
    work.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(culverts.drop(columns="geometry")).to_csv(work / "ndot_culverts_std.csv", index=False)
    condition.to_csv(work / "ndot_condition_std.csv", index=False)
    pd.crosstab(culverts["feature_type"], culverts["_rule"]).to_csv(work / "ndot_feature_type_by_rule.csv")
    summary = {
        "assets": len(culverts),
        "culverts": int((culverts["feature_type"] == "culvert").sum()),
        "stormwater_pipes": int((culverts["feature_type"] == "stormwater pipe").sum()),
        "span_in_null_pct": round(100 * culverts["span_in"].isna().mean(), 1),
        "material_null_pct": round(100 * culverts["material"].isna().mean(), 1),
        "condition_records": len(condition),
        "assets_with_condition": int(condition["culvert_id"].nunique()),
        "condition_rated_gfp": int(condition["condition_rating"].notna().sum()),
        "condition_with_blockage": int(condition["blockage_pct"].notna().sum()),
        "latest_inspection": str(condition["inspection_date"].max()),
    }
    pd.Series(summary).to_csv(work / "ndot_summary.csv", header=False)
    log.info("[NDOT] QA -> %s\n%s", work, pd.Series(summary).to_string())
    return work


if __name__ == "__main__":
    log = get_logger("ndot_culverts")
    cfg = load_cfg()
    streets = read_streets(cfg, log)
    culverts, condition, _ = read_ndot(cfg, log, streets)
    write_qa(culverts, condition, cfg, log)
