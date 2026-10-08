"""Build the Bridges asset layer for the PROTECT vulnerability assessment.

Reads the National Bridge Inventory points already clipped to the TRPA boundary
(assets.nbi_basin_fc in the analysis geodatabase), keeps the fields the sensitivity rubric
needs (condition, scour, channel, waterway, age, type), decodes the NBI codes that matter,
snaps each bridge to its parent road segment, and writes:

    <analysis_gdb>/Bridges   point feature class, one row per structure

Raw NBI codes are kept as text (they include "N" for not applicable); decoded labels sit
beside them. Scoring happens later in score_sensitivity.py, not here.

Usage (arcgispro-py3):
    python scripts/build_bridges.py              # fails if Bridges already exists
    python scripts/build_bridges.py --overwrite
    python scripts/build_bridges.py --dry-run    # QA CSV only, no geodatabase write
"""

from __future__ import annotations

import argparse

import geopandas as gpd
import pandas as pd

from va_common import (REPO, get_logger, guard_exists, load_cfg, snap_to_segments,
                       target_crs, write_point_fc)

# NBI coding guide (FHWA Recording and Coding Guide for the Structure Inventory and
# Appraisal of the Nation's Bridges, 1995, with the 2018 condition definitions)
OWNER = {"01": "State highway agency", "02": "County", "03": "Town or township", "04": "City",
         "11": "State park or forest", "21": "Other state agency", "25": "Other local agency",
         "26": "Private (other than railroad)", "27": "Railroad", "31": "State toll authority",
         "32": "Local toll authority", "60": "Other federal", "62": "Bureau of Indian Affairs",
         "64": "U.S. Forest Service", "66": "National Park Service", "70": "Corps of Engineers"}
STRUCTURE_KIND = {"1": "Concrete", "2": "Concrete continuous", "3": "Steel", "4": "Steel continuous",
                  "5": "Prestressed concrete", "6": "Prestressed concrete continuous",
                  "7": "Wood or timber", "8": "Masonry", "9": "Aluminum, wrought iron, or cast iron",
                  "0": "Other"}
SCOUR = {"N": "Not over waterway", "U": "Unknown foundation, not evaluated", "T": "Tidal, not evaluated",
         "9": "Dry land or well above flood", "8": "Stable, footing above streambed",
         "7": "Countermeasures installed", "6": "Not evaluated", "5": "Stable, within footing limits",
         "4": "Stable, action required", "3": "Scour critical", "2": "Scour critical, extensive",
         "1": "Scour critical, failure imminent", "0": "Failed or closed"}
CONDITION = {"G": "Good", "F": "Fair", "P": "Poor"}
CULVERT_TYPE_CODE = "19"  # 043B: structure type "culvert"

# (field, arcpy type, length). Order = column order in the GDB.
BRIDGE_FIELDS = [
    ("bridge_id", "TEXT", 20),          # NBI structure number (008), unique within state
    ("state", "TEXT", 2),               # CA / NV
    ("owner_code", "TEXT", 2),
    ("owner", "TEXT", 60),
    ("facility_carried", "TEXT", 40),
    ("feature_crossed", "TEXT", 40),
    ("location", "TEXT", 40),
    ("year_built", "SHORT", None),
    ("year_reconstructed", "SHORT", None),
    ("structure_kind_code", "TEXT", 1),
    ("structure_kind", "TEXT", 40),
    ("structure_type_code", "TEXT", 2),
    ("is_culvert_type", "SHORT", None),  # 1 if NBI type 19 (culvert > 20 ft)
    ("length_m", "DOUBLE", None),
    ("deck_width_m", "DOUBLE", None),
    ("adt", "LONG", None),
    ("adt_year", "SHORT", None),
    ("detour_km", "SHORT", None),
    ("deck_cond", "TEXT", 1),           # 058, 0-9 or N
    ("super_cond", "TEXT", 1),          # 059
    ("sub_cond", "TEXT", 1),            # 060
    ("channel_cond", "TEXT", 1),        # 061
    ("culvert_cond", "TEXT", 1),        # 062
    ("waterway_eval", "TEXT", 1),       # 071
    ("scour_code", "TEXT", 1),          # 113
    ("scour_label", "TEXT", 50),
    ("bridge_condition", "TEXT", 1),    # G / F / P
    ("bridge_condition_label", "TEXT", 10),
    ("lowest_rating", "SHORT", None),   # min of deck, super, sub (or culvert)
    ("water_crossing", "SHORT", None),  # 1 if the structure is over a waterway (scour != N)
    ("inspect_date", "TEXT", 4),        # NBI MMYY
    ("parent_segment_id", "TEXT", 64),
    ("parent_dist_m", "DOUBLE", None),
    ("data_source", "TEXT", 160),
    ("load_date", "DATE", None),
]
BRIDGE_COLS = [f[0] for f in BRIDGE_FIELDS]


def _code(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip()


def _num(s: pd.Series, zero_is_null: bool = True) -> pd.Series:
    v = pd.to_numeric(s, errors="coerce")
    return v.where(v != 0) if zero_is_null else v


def build(cfg: dict, log) -> gpd.GeoDataFrame:
    a = cfg["assets"]
    src = f"{cfg['paths']['analysis_gdb']}\\{a['nbi_basin_fc']}"
    nbi = gpd.read_file(cfg["paths"]["analysis_gdb"], layer=a["nbi_basin_fc"]).to_crs(target_crs(cfg))
    log.info(f"Read {len(nbi)} NBI structures from {a['nbi_basin_fc']}")

    b = gpd.GeoDataFrame(geometry=nbi.geometry, crs=nbi.crs)
    b["bridge_id"] = _code(nbi["STRUCTURE_NUMBER_008"])
    b["state"] = _code(nbi["STATE_CODE_001"]).map({"06": "CA", "32": "NV"})
    b["owner_code"] = _code(nbi["OWNER_022"])
    b["owner"] = b["owner_code"].map(OWNER).fillna("Other (" + b["owner_code"] + ")")
    b["facility_carried"] = _code(nbi["FACILITY_CARRIED_007"])
    b["feature_crossed"] = _code(nbi["FEATURES_DESC_006A"])
    b["location"] = _code(nbi["LOCATION_009"])
    b["year_built"] = _num(nbi["YEAR_BUILT_027"])
    b["year_reconstructed"] = _num(nbi["YEAR_RECONSTRUCTED_106"])
    b["structure_kind_code"] = _code(nbi["STRUCTURE_KIND_043A"])
    b["structure_kind"] = b["structure_kind_code"].map(STRUCTURE_KIND)
    b["structure_type_code"] = _code(nbi["STRUCTURE_TYPE_043B"])
    b["is_culvert_type"] = (b["structure_type_code"] == CULVERT_TYPE_CODE).astype(int)
    b["length_m"] = _num(nbi["STRUCTURE_LEN_MT_049"])
    b["deck_width_m"] = _num(nbi["DECK_WIDTH_MT_052"])
    b["adt"] = _num(nbi["ADT_029"])
    b["adt_year"] = _num(nbi["YEAR_ADT_030"])
    b["detour_km"] = _num(nbi["DETOUR_KILOS_019"], zero_is_null=False)
    for col, src_col in [("deck_cond", "DECK_COND_058"), ("super_cond", "SUPERSTRUCTURE_COND_059"),
                         ("sub_cond", "SUBSTRUCTURE_COND_060"), ("channel_cond", "CHANNEL_COND_061"),
                         ("culvert_cond", "CULVERT_COND_062"), ("waterway_eval", "WATERWAY_EVAL_071"),
                         ("scour_code", "SCOUR_CRITICAL_113")]:
        b[col] = _code(nbi[src_col])
    b["scour_label"] = b["scour_code"].map(SCOUR)
    b["bridge_condition"] = _code(nbi["BRIDGE_CONDITION"])
    b["bridge_condition_label"] = b["bridge_condition"].map(CONDITION)
    b["lowest_rating"] = _num(nbi["LOWEST_RATING"], zero_is_null=False)
    b["water_crossing"] = (b["scour_code"] != "N").astype(int)
    b["inspect_date"] = _code(nbi["DATE_OF_INSPECT_090"])
    b["data_source"] = f"FHWA National Bridge Inventory via {a['nbi_basin_fc']} (analysis gdb)"
    b["load_date"] = pd.Timestamp.today().normalize()

    dup = b["bridge_id"].duplicated().sum()
    if dup:
        raise ValueError(f"{dup} duplicate structure numbers; fix upstream before loading")

    b = snap_to_segments(b, "bridge_id", cfg, log)
    log.info("Condition: " + b["bridge_condition_label"].value_counts(dropna=False).to_dict().__repr__())
    log.info("Scour: " + b["scour_label"].value_counts(dropna=False).to_dict().__repr__())
    log.info(f"Water crossings: {int(b['water_crossing'].sum())} of {len(b)}; "
             f"NBI culvert-type structures: {int(b['is_culvert_type'].sum())}")
    far = b.loc[b["parent_dist_m"].isna() | (b["parent_dist_m"] > 25), ["bridge_id", "facility_carried", "parent_dist_m"]]
    if len(far):
        log.warning(f"{len(far)} bridges more than 25 m from a segment or unsnapped:\n{far.to_string(index=False)}")
    return b[BRIDGE_COLS + ["geometry"]]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    log = get_logger("build_bridges")
    cfg = load_cfg()
    bridges = build(cfg, log)

    qa = REPO / cfg["paths"]["outputs"] / "bridges_attributes.csv"
    bridges.drop(columns="geometry").to_csv(qa, index=False)
    log.info(f"Attributes -> {qa}")
    if args.dry_run:
        log.info("Dry run: geodatabase not written")
        return

    a = cfg["assets"]
    gdb = cfg["paths"]["analysis_gdb"]
    guard_exists([f"{gdb}\\{a['bridges_fc']}"], args.overwrite, log)
    fc = write_point_fc(bridges, BRIDGE_FIELDS, gdb, a["bridges_fc"], cfg["output"]["target_epsg"],
                        log, date_cols={"load_date"})
    import arcpy
    arcpy.management.AddIndex(fc, ["bridge_id"], "bridge_id_idx", "UNIQUE")
    arcpy.management.AddIndex(fc, ["parent_segment_id"], "parent_seg_idx")
    log.info(f"Bridges layer ready: {fc}")


if __name__ == "__main__":
    main()
