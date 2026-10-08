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
    ap.add_argument("--grid", action="store_true",
                    help="print the origin / cell size / extent of every terrain raster and a 5x5 "
                         "neighborhood of facc, fdir, and zone around the first 3 sampled pour cells")
    ap.add_argument("--conserve", action="store_true",
                    help="numpy test on a box around the first 3 sampled pour cells: D8 conservation of facc, "
                         "the true upstream count of the pour cell walked on fdir, and facc along the downstream path")
    ap.add_argument("--box-m", type=float, default=1000.0, help="box size for --conserve (m)")
    args = ap.parse_args()
    log = get_logger("qa_crossings")
    cfg = load_cfg()
    import arcpy
    import pyogrio

    gdb, work = cfg["paths"]["analysis_gdb"], cfg["profile"]["work_gdb"]
    wfc = WATERSHED_FC
    cell = float(arcpy.Describe(f"{work}\\facc").meanCellWidth)

    if args.grid:
        arcpy.env.workspace = work
        rows = []
        for r in arcpy.ListRasters():
            d = arcpy.Describe(r)
            e = d.extent
            rows.append(dict(raster=r, cell_w=d.meanCellWidth, cell_h=d.meanCellHeight, xmin=e.XMin, ymin=e.YMin,
                             xmax=e.XMax, ymax=e.YMax, cols=d.width, rows=d.height, epsg=d.spatialReference.factoryCode))
        src = arcpy.Describe(cfg["paths"]["dem"])
        e = src.extent
        rows.append(dict(raster="SDE DEM (source)", cell_w=src.meanCellWidth, cell_h=src.meanCellHeight, xmin=e.XMin,
                         ymin=e.YMin, xmax=e.XMax, ymax=e.YMax, cols=src.width, rows=src.height,
                         epsg=src.spatialReference.factoryCode))
        pd.set_option("display.width", 250)
        pd.set_option("display.float_format", lambda v: f"{v:.3f}")
        log.info("raster grids (any difference in xmin/ymin modulo the cell size is a misalignment):\n"
                 + pd.DataFrame(rows).to_string(index=False))
        pd.reset_option("display.float_format")

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

    if args.grid:
        def window(raster: str, x: float, y: float, n: int = 5):
            half = n // 2
            grid = []
            for j in range(half, -half - 1, -1):          # north row first
                grid.append([cellval(raster, x + i * cell, y + j * cell) for i in range(-half, half + 1)])
            df = pd.DataFrame(grid, index=[f"y{j:+d}" for j in range(half, -half - 1, -1)],
                              columns=[f"x{i:+d}" for i in range(-half, half + 1)])
            return df
        for _, r in pick.head(3).iterrows():
            x, y = float(r.pp_x), float(r.pp_y)
            log.info(f"{r.crossing_id} neighborhood at ({x:.1f}, {y:.1f}); center is the pour cell, north is up\n"
                     f"facc:\n{window('facc', x, y).to_string()}\n"
                     f"fdir:\n{window('fdir', x, y).to_string()}\n"
                     f"zone:\n{window('wshed_inc', x, y).to_string()}")

    if args.conserve:
        n = int(round(args.box_m / cell))
        half = n // 2
        for _, r in pick.head(3).iterrows():
            x, y = float(r.pp_x), float(r.pp_y)
            ll = arcpy.Point(x - half * cell - cell / 2, y - half * cell - cell / 2)
            fd = arcpy.RasterToNumPyArray(f"{work}\\fdir", ll, n, n, nodata_to_value=0).astype(np.int64)
            fa = arcpy.RasterToNumPyArray(f"{work}\\facc", ll, n, n, nodata_to_value=-1).astype(np.float64)
            ws = arcpy.RasterToNumPyArray(f"{work}\\wshed_inc", ll, n, n, nodata_to_value=0).astype(np.int64)
            if fd.shape != (n, n):
                log.warning(f"{r.crossing_id}: box clipped to {fd.shape}; skipping")
                continue
            c = d8_checks(fd, fa, ws, half, half, int(r.crossing_pp))
            log.info(f"{r.crossing_id}: D8 conservation in a {n}x{n} box: {c['violations']} of {c['n_inside']} cells "
                     f"({100 * c['violations'] / max(c['n_inside'], 1):.2f} pct) drain to a cell with LESS accumulation "
                     f"than themselves + 1. Should be 0 for a D8 accumulation of this fdir."
                     + (f" Violations on cells with facc >= 100: {c['violations_big']}; largest facc lost: {c['lost_max']:.0f}"
                        if c["violations"] else ""))
            log.info(f"{r.crossing_id}: walked upstream on fdir from the pour cell: {c['upstream_walk']} cells incl. the "
                     f"pour cell{' (reached the box edge, so a lower bound)' if c['touched_edge'] else ''}; "
                     f"facc at pour cell + 1 = {c['facc_plus1']:.0f}; Watershed zone cells in box = {c['zone_cells']}; "
                     f"table inc_cells = {r.inc_cells:.0f}")
            log.info(f"{r.crossing_id}: facc downstream of the pour cell ({c['facc_plus1'] - 1:.0f}), step by step: "
                     + " > ".join(f"{v:.0f}" for v in c["path"]) + "   (must never decrease under D8)")


# numpy D8 offsets as (drow, dcol); row 0 is the north edge of the array
D8_RC = {1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1), 64: (-1, 0), 128: (-1, 1)}


def d8_checks(fd: np.ndarray, fa: np.ndarray, ws: np.ndarray, pr: int, pc: int, zone_id: int) -> dict:
    """Pure-numpy checks on a window: fd (D8 codes, 0 = nodata), fa (accumulation, < 0 = nodata),
    ws (zone ids), pour cell at (pr, pc). Returns conservation violations, the upstream cell count
    walked on fd from the pour cell, the zone size, and facc along the downstream path."""
    n_r, n_c = fd.shape
    rows_i, cols_i = np.indices(fd.shape)
    drow, dcol = np.zeros_like(fd), np.zeros_like(fd)
    valid = np.zeros(fd.shape, bool)
    for code, (dr, dc) in D8_RC.items():
        m = fd == code
        drow[m], dcol[m] = dr, dc
        valid |= m
    tr, tc = rows_i + drow, cols_i + dcol
    inside = valid & (tr >= 0) & (tr < n_r) & (tc >= 0) & (tc < n_c) & (fa >= 0)
    trc, tcc = tr.clip(0, n_r - 1), tc.clip(0, n_c - 1)
    viol = inside & (fa[trc, tcc] < fa + 1)

    # upstream walk: children lists via a sort on the downstream index
    target = np.where(inside, trc * n_c + tcc, -1).ravel()
    order = np.argsort(target, kind="stable")
    tsorted = target[order]
    cells = np.arange(n_r * n_c)
    starts = np.searchsorted(tsorted, cells, side="left")
    ends = np.searchsorted(tsorted, cells, side="right")
    seen = np.zeros(n_r * n_c, bool)
    start = pr * n_c + pc
    seen[start] = True
    stack, touched_edge = [start], False
    while stack:
        cur = stack.pop()
        cr, cc = divmod(cur, n_c)
        if cr in (0, n_r - 1) or cc in (0, n_c - 1):
            touched_edge = True
        for k in order[starts[cur]:ends[cur]]:
            if not seen[k]:
                seen[k] = True
                stack.append(int(k))

    path, cr, cc = [], pr, pc
    for _ in range(25):
        if not inside[cr, cc]:
            break
        cr, cc = int(trc[cr, cc]), int(tcc[cr, cc])
        path.append(float(fa[cr, cc]))
    return dict(n_inside=int(inside.sum()), violations=int(viol.sum()),
                violations_big=int((viol & (fa >= 100)).sum()), lost_max=float(fa[viol].max()) if viol.any() else 0.0,
                upstream_walk=int(seen.sum()), touched_edge=touched_edge, facc_plus1=float(fa[pr, pc] + 1),
                zone_cells=int((ws == zone_id).sum()), path=path)
    log.info("Read: zone_is_pp False = the Watershed pour cell is not the sampled cell. "
             "facc_pp + 1 != inc_cells with zone_is_pp True = zone/accumulation disagree at the same cell. "
             "facc_dn < facc_pp = the D8 step-down cell is not downstream (wrong link).")


if __name__ == "__main__":
    main()
