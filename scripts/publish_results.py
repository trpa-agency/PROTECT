"""Publish draft VA results for the web pages: public-jurisdiction culverts with the profile and
exposure fields, the bridges, the classed flood surface, and a summary JSON for the page KPIs.

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

from va_common import REPO, get_logger, load_cfg

CULVERT_COLS = ["culvert_id", "jurisdiction", "road_name", "feature_type", "parent_segment_id", "crossing_id",
                "barrels", "span_in", "d_eq_in", "size_class", "material_class", "contrib_area_ac",
                "basin_slope_pct", "basin_landcover", "basin_precip_in", "q_method", "q_region",
                "q_event_25_cfs", "q_event_100_cfs", "q_cap_crossing_cfs", "load_ratio_25", "load_ratio_100",
                "cond_class", "cond_source", "cond_stale", "blockage_pct", "tailwater_flag", "on_stream",
                "size_suspect", "ratio_review", "profile_completeness", "E_FLC_hist", "E_FLC_pt", "E_FLC_src",
                "E_source"]
BRIDGE_COLS = ["bridge_id", "state", "owner", "facility_carried", "feature_crossed", "year_built",
               "is_culvert_type", "main_spans", "max_span_m", "waterway_eval", "scour_code", "scour_label",
               "channel_cond", "lowest_rating", "bridge_condition_label", "water_crossing", "parent_segment_id",
               "E_FLB_hist", "E_FLB_e1", "E_FLB_e2", "E_source"]
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
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
    cul.to_file(out_dir / "culverts_results.geojson", driver="GeoJSON")
    br.to_file(out_dir / "bridges_results.geojson", driver="GeoJSON")
    flood.to_file(out_dir / "flood_surface.geojson", driver="GeoJSON")
    pd.DataFrame(cul.drop(columns="geometry")).to_csv(out_dir / "culverts_results.csv", index=False)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    for f in sorted(out_dir.glob("*")):
        log.info(f"{f.name}: {f.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
