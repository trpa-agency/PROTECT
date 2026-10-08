"""QA for the culvert crossing table: why does the tree-aggregated area exceed flow accumulation?

Run on the server (rasters are local there):

    python scripts/qa_crossings.py              # summary of the mismatches + pour-cell check on the worst 12
    python scripts/qa_crossings.py --n 40       # check more crossings
    python scripts/qa_crossings.py --ids X01999 X01197 X01185

Reads CulvertCrossings and the watershed polygons from the analysis geodatabase and the terrain
rasters from profile.work_gdb. For each checked crossing it samples flow accumulation, flow
direction, and the watershed zone at the pour cell and at the D8 step-down cell, so a pour cell
that does not match the zone, or a downstream link that lands in the wrong zone, shows up
directly. Prints aggregates and crossing ids only; nothing is written.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from va_common import get_logger, load_cfg

SQM_PER_ACRE = 4046.8564
D8 = {1: (1, 0), 2: (1, -1), 4: (0, -1), 8: (-1, -1), 16: (-1, 0), 32: (-1, 1), 64: (0, 1), 128: (1, 1)}
CROSSING_TABLE, WATERSHED_FC = "CulvertCrossings", "CulvertWatersheds_inc"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=12, help="number of worst crossings to sample")
    ap.add_argument("--ids", nargs="*", help="specific crossing ids to sample instead")
    args = ap.parse_args()
    log = get_logger("qa_crossings")
    cfg = load_cfg()
    import arcpy
    import pyogrio

    gdb, work = cfg["paths"]["analysis_gdb"], cfg["profile"]["work_gdb"]
    wfc = WATERSHED_FC
    cell = float(arcpy.Describe(f"{work}\\facc").meanCellWidth)

    xt = pyogrio.read_dataframe(gdb, layer=CROSSING_TABLE, read_geometry=False)
    xt["cells_diff"] = (xt["contrib_area_ac"] - xt["facc_area_ac"]) * SQM_PER_ACRE / (cell * cell)
    bad = xt[(xt["area_check_pct"].abs() > 5) & (xt["cells_diff"].abs() > 2)].copy()
    up_counts = xt["downstream_crossing_id"].value_counts()
    bad["n_upstream"] = bad["crossing_id"].map(up_counts).fillna(0).astype(int)

    log.info(f"{len(xt)} crossings; {len(bad)} mismatches (> 5 pct and > 2 cells); "
             f"tree > facc on {int((bad['cells_diff'] > 0).sum())}, tree < facc on {int((bad['cells_diff'] < 0).sum())}")
    log.info(f"mismatches with no upstream crossing: {int((bad['n_upstream'] == 0).sum())}; "
             f"with upstream: {int((bad['n_upstream'] > 0).sum())}")
    log.info("area_check_pct quantiles (mismatches):\n" + bad["area_check_pct"].quantile([.05, .5, .95]).round(1).to_string())
    log.info("crossings sharing a pour cell: " + str(int(xt.duplicated(subset=["pp_x", "pp_y"], keep=False).sum())))
    log.info("by jurisdiction (mismatch / total):\n" + pd.concat(
        [bad["jurisdiction"].value_counts().rename("mismatch"), xt["jurisdiction"].value_counts().rename("total")],
        axis=1).fillna(0).astype(int).to_string())

    if args.ids:
        pick = xt[xt["crossing_id"].isin(args.ids)]
    else:
        pick = bad[bad["restricted"] == 0].sort_values("area_check_pct", key=abs, ascending=False).head(args.n)

    def cellval(raster: str, x: float, y: float):
        v = arcpy.management.GetCellValue(f"{work}\\{raster}", f"{x} {y}").getOutput(0)
        return None if v == "NoData" else float(v)

    out = []
    for _, r in pick.iterrows():
        x, y, pp = float(r.pp_x), float(r.pp_y), int(r.crossing_pp)
        facc_pp, fdir_pp, z_pp = cellval("facc", x, y), cellval("fdir", x, y), cellval("wshed_inc", x, y)
        dx, dy = D8.get(int(fdir_pp), (0, 0)) if fdir_pp is not None else (0, 0)
        xd, yd = x + dx * cell, y + dy * cell
        with arcpy.da.SearchCursor(f"{gdb}\\{wfc}", ["SHAPE@AREA"], where_clause=f"gridcode = {pp}") as cur:
            poly_cells = sum(a for (a,) in cur) / (cell * cell)
        out.append(dict(crossing=r.crossing_id, pp=pp, dn=r.downstream_crossing_id, snap_m=round(r.snap_dist_m, 1),
                        facc_pp=facc_pp, zone_pp=z_pp, zone_is_pp=(z_pp == pp), fdir=fdir_pp,
                        facc_dn=cellval("facc", xd, yd), zone_dn=cellval("wshed_inc", xd, yd),
                        inc_cells=r.inc_cells, poly_cells=round(poly_cells), full_cells=r.full_cells,
                        facc_cells=round(r.facc_area_ac * SQM_PER_ACRE / (cell * cell)), pct=r.area_check_pct))
    pd.set_option("display.width", 250)
    log.info("pour-cell check:\n" + pd.DataFrame(out).to_string(index=False))
    log.info("Read: zone_is_pp False = the Watershed pour cell is not the sampled cell. "
             "facc_pp + 1 != inc_cells with zone_is_pp True = zone/accumulation disagree at the same cell. "
             "facc_dn < facc_pp = the D8 step-down cell is not downstream (wrong link).")


if __name__ == "__main__":
    main()
