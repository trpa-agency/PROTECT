"""Load the engineered culvert layer into the PROTECT analysis geodatabase.

Reads data/processed/culverts.gpkg (one point per culvert) and
data/processed/culvert_condition.parquet (1:many inspections), snaps each culvert to its
parent road segment in the analysis geodatabase, and writes:

    <analysis_gdb>/Culverts              point feature class
    <analysis_gdb>/CulvertCondition      standalone table
    <analysis_gdb>/Culvert_has_Condition relationship class on culvert_id (1:M)

Promoted from the "Build the File GDB" cell of notebooks/culvert_layer_engineering.ipynb,
re-pointed at the shared analysis geodatabase instead of a standalone culverts.gdb.

NDOT (restricted). When config `ndot.enabled` is true the NDOT SAM21 export is read in place
from TRPA storage by scripts/ndot_culverts.py and appended here, in memory, on the way into
the geodatabase. NDOT rows never touch data/processed (git-tracked) and are filtered out of
the repo-side QA CSV; the full QA goes to `ndot.work_dir` on F:. Provisional legacy points
within run.legacy_match_m of an NDOT pipe are dropped as superseded.

Usage (arcgispro-py3):
    python scripts/load_culverts_gdb.py            # fails if Culverts already exists
    python scripts/load_culverts_gdb.py --overwrite
    python scripts/load_culverts_gdb.py --dry-run  # snap + QA only, no geodatabase write
    python scripts/load_culverts_gdb.py --no-ndot  # public-source layer only
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd

from va_common import (REPO, get_logger, guard_exists, load_cfg, read_streets, snap_to_segments,
                       target_crs, write_point_fc, write_table)

LEGACY_JURISDICTION = "TRPA Legacy (provisional)"

# Target schema. (field_name, arcpy_type, length_or_None). Order = column order in the GDB.
# Mirrors the notebook; parent_segment_id, parent_dist_m, and has_condition are new.
CULVERT_FIELDS = [
    ("jurisdiction", "TEXT", 60),
    ("source_id", "TEXT", 100),
    ("culvert_id", "TEXT", 160),  # "<jurisdiction>|<source_id>" - stable key
    ("feature_type", "TEXT", 40),
    ("road_name", "TEXT", 254),
    ("material", "TEXT", 60),
    ("xsection_shape", "TEXT", 80),
    ("span_in", "DOUBLE", None),
    ("rise_in", "DOUBLE", None),
    ("length_ft", "DOUBLE", None),
    ("inlet_type", "TEXT", 60),
    ("outlet_type", "TEXT", 60),
    ("install_year", "SHORT", None),
    ("comments", "TEXT", 500),
    ("geom_source", "TEXT", 40),
    ("data_source", "TEXT", 160),
    ("load_date", "DATE", None),
    ("parent_segment_id", "TEXT", 64),  # nearest road segment within assets.segment_snap_m
    ("parent_dist_m", "DOUBLE", None),
    ("has_condition", "SHORT", None),  # 1 if any row in CulvertCondition
]

CONDITION_FIELDS = [
    ("culvert_id", "TEXT", 160),
    ("jurisdiction", "TEXT", 60),
    ("inspection_date", "DATE", None),
    ("condition_rating", "TEXT", 30),
    ("condition_scheme", "TEXT", 120),
    ("structural_cond", "TEXT", 60),
    ("blockage_pct", "DOUBLE", None),
    ("maintenance_need", "TEXT", 60),
    ("inspector", "TEXT", 120),
    ("notes", "TEXT", 500),
    ("data_source", "TEXT", 160),
    ("load_date", "DATE", None),
]

CULVERT_COLS = [f[0] for f in CULVERT_FIELDS]
CONDITION_COLS = [f[0] for f in CONDITION_FIELDS]


def load_inputs(cfg: dict, log) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    processed = REPO / cfg["paths"]["processed"]
    culverts = gpd.read_file(processed / "culverts.gpkg", layer="culverts").to_crs(target_crs(cfg))
    condition = pd.read_parquet(processed / "culvert_condition.parquet")
    log.info(f"Read {len(culverts)} culverts, {len(condition)} condition records")

    dup = culverts["culvert_id"].duplicated().sum()
    if dup:
        raise ValueError(f"{dup} duplicate culvert_id values in culverts.gpkg; fix upstream")
    orphan = ~condition["culvert_id"].isin(culverts["culvert_id"])
    if orphan.any():
        log.warning(f"{orphan.sum()} condition rows have no matching culvert; dropping them")
        condition = condition[~orphan]
    return culverts, condition


def add_ndot(culverts: gpd.GeoDataFrame, condition: pd.DataFrame, cfg: dict, log,
             streets: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """Append the restricted NDOT subset and retire legacy points it supersedes."""
    from ndot_culverts import read_ndot, write_qa

    nd_culv, nd_cond, nd_lines = read_ndot(cfg, log, streets)
    work = write_qa(nd_culv, nd_cond, cfg, log)

    clash = nd_culv["culvert_id"].isin(culverts["culvert_id"])
    if clash.any():
        raise ValueError(f"{int(clash.sum())} NDOT culvert_id values collide with existing keys")

    # Legacy gap-fill points (the prior TRPA compilation) within the match radius of an NDOT
    # pipe or box are the same asset seen twice: drop the provisional copy and its condition rows.
    radius = cfg["run"]["legacy_match_m"]
    prov = culverts[culverts["jurisdiction"] == LEGACY_JURISDICTION]
    lines_gdf = gpd.GeoDataFrame({"ndot_id": nd_lines.index}, geometry=nd_lines.values, crs=nd_lines.crs)
    near = gpd.sjoin_nearest(prov[["culvert_id", "geometry"]], lines_gdf, how="inner",
                             max_distance=radius, distance_col="dist_m")
    near = near[~near.index.duplicated(keep="first")]
    superseded = set(near["culvert_id"])
    log.info(f"{len(superseded)} provisional legacy points within {radius} m of an NDOT asset: dropped as superseded")
    if superseded:
        near.drop(columns="geometry").to_csv(work / "legacy_superseded_by_ndot.csv", index=False)
        culverts = culverts[~culverts["culvert_id"].isin(superseded)]
        condition = condition[~condition["culvert_id"].isin(superseded)]

    nd_culv = nd_culv.drop(columns=["_globalid", "_rule"])
    culverts = gpd.GeoDataFrame(pd.concat([culverts, nd_culv], ignore_index=True), geometry="geometry",
                                crs=culverts.crs)
    condition = pd.concat([condition, nd_cond], ignore_index=True)
    log.info(f"With NDOT: {len(culverts)} culverts, {len(condition)} condition records")
    return culverts, condition


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--overwrite", action="store_true", help="replace existing Culverts / CulvertCondition")
    ap.add_argument("--dry-run", action="store_true", help="snap and QA only; do not write the geodatabase")
    ap.add_argument("--no-ndot", action="store_true", help="skip the restricted NDOT source even if enabled")
    args = ap.parse_args()

    log = get_logger("load_culverts_gdb")
    cfg = load_cfg()
    culverts, condition = load_inputs(cfg, log)
    streets = read_streets(cfg, log)

    with_ndot = cfg.get("ndot", {}).get("enabled", False) and not args.no_ndot
    restricted = {cfg["ndot"]["jurisdiction"]} if with_ndot else set()
    if with_ndot:
        culverts, condition = add_ndot(culverts, condition, cfg, log, streets)
    else:
        log.info("NDOT source skipped")

    culverts = snap_to_segments(culverts, "culvert_id", cfg, log, streets=streets)
    log.info("Unsnapped by jurisdiction:\n" +
             culverts.loc[culverts["parent_segment_id"].isna(), "jurisdiction"].value_counts().to_string())
    culverts["has_condition"] = culverts["culvert_id"].isin(condition["culvert_id"]).astype(int)
    log.info(f"{int(culverts['has_condition'].sum())} culverts have at least one condition record")
    for c in CULVERT_COLS:
        if c not in culverts.columns:
            culverts[c] = None
    for c in CONDITION_COLS:
        if c not in condition.columns:
            condition[c] = None

    # Repo-side QA excludes restricted jurisdictions; the full version lives in ndot.work_dir.
    snap_cols = ["culvert_id", "jurisdiction", "parent_segment_id", "parent_dist_m", "has_condition"]
    snap_qa = culverts.drop(columns="geometry")[snap_cols]
    qa = REPO / cfg["paths"]["outputs"] / "culverts_segment_snap.csv"
    qa.parent.mkdir(parents=True, exist_ok=True)  # outputs/ is gitignored; absent on a fresh clone
    snap_qa[~snap_qa["jurisdiction"].isin(restricted)].to_csv(qa, index=False)
    log.info(f"Snap QA (public sources) -> {qa}")
    if restricted:
        full = Path(cfg["ndot"]["work_dir"]) / "culverts_segment_snap_all.csv"
        snap_qa.to_csv(full, index=False)
        log.info(f"Snap QA (all sources, restricted) -> {full}")
    if args.dry_run:
        log.info("Dry run: geodatabase not written")
        return

    import arcpy
    a = cfg["assets"]
    gdb = cfg["paths"]["analysis_gdb"]
    rc_path = f"{gdb}\\{a['relationship_class']}"
    guard_exists([f"{gdb}\\{a['culverts_fc']}", f"{gdb}\\{a['condition_table']}", rc_path],
                 args.overwrite, log)
    fc = write_point_fc(culverts, CULVERT_FIELDS, gdb, a["culverts_fc"], cfg["output"]["target_epsg"],
                        log, date_cols={"load_date"})
    tbl = write_table(condition, CONDITION_FIELDS, gdb, a["condition_table"], log,
                      date_cols={"inspection_date", "load_date"})
    arcpy.management.CreateRelationshipClass(
        origin_table=fc, destination_table=tbl, out_relationship_class=rc_path,
        relationship_type="SIMPLE", forward_label="Condition", backward_label="Culvert",
        message_direction="NONE", cardinality="ONE_TO_MANY", attributed="NONE",
        origin_primary_key="culvert_id", origin_foreign_key="culvert_id")
    arcpy.management.AddIndex(fc, ["culvert_id"], "culvert_id_idx", "UNIQUE")
    arcpy.management.AddIndex(fc, ["parent_segment_id"], "parent_seg_idx")
    arcpy.management.AddIndex(tbl, ["culvert_id"], "cond_culvert_id_idx")
    log.info(f"Relationship class {a['relationship_class']} created in {gdb}")


if __name__ == "__main__":
    main()
