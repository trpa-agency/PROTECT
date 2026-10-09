"""Watershed delineation and the culvert profile for the PROTECT vulnerability assessment.

Implements docs/SCORING_RUBRICS.md sections 2.2 (profile fields), 2.4 (hydrology and
hydraulics), and 2.5 (condition harmonization). Three stages, run in order; each one is
resumable and skips work that already exists unless --overwrite is given.

    terrain     Flow direction, flow accumulation, slope, and longest upstream flow length
                from the hydro-enforced bare-earth lidar DEM (paths.dem), written to
                profile.work_gdb. Two conditioning steps first: (1) BREACH the road fill
                through every inventoried culvert (profile.breach: a short line through
                the point, perpendicular to its parent segment, lowered to the lower of its
                two ends), because the enforcement did not breach every crossing and the
                Fill otherwise spills creeks along roadside ditches; (2) FILL sinks
                shallower than profile.fill_z_limit_m (unfilled sinks make two-cell
                flow-direction loops that split accumulation and stop flow). SERVER JOB.
    delineate   Snap every culvert to its pour point (max accumulation within
                profile.pour_snap_m, a few metres: the breach runs through the culvert's
                own cell), group multi-barrel crossings, delineate incremental watersheds,
                record each crossing's downstream crossing, zonal statistics (slope, max
                and mean elevation, PRISM mean annual precipitation, NLCD), and aggregate
                up the drainage tree so every crossing carries its FULL contributing area.
                Writes CulvertCrossings and CulvertWatersheds_inc. SERVER JOB.
    attributes  Equivalent diameter, size and material classes, condition harmonization,
                event flow (rational method on Atlas 14 under profile.rational_max_sqmi,
                USGS regional regression above it: Gotvald 2012 Lahontan region in
                California, Thomas 1997 region 1 in Nevada), inlet-control capacity,
                loading ratio, tailwater and vintage flags. Writes CulvertProfile and
                applies the fields onto Culverts. Runs anywhere; without the delineate
                outputs the hydrology fields are null and profile_completeness says so.

    PRISM 1991-2020 annual precipitation normals (800 m) feed the regression:
    python scripts/fetch_prism.py downloads them to profile.prism_ppt.

Usage (arcgispro-py3, Spatial Analyst):
    python scripts/culvert_profile.py --stage terrain
    python scripts/culvert_profile.py --stage delineate
    python scripts/culvert_profile.py --stage attributes [--dry-run] [--no-apply]
    python scripts/culvert_profile.py --stage all --overwrite

Restricted data: NDOT rows are processed with everything else inside the analysis
geodatabase, but every CSV written under the repo excludes them; the full CSVs go to
ndot.work_dir on F:.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from va_common import (REPO, clean, fields_spec, get_logger, load_cfg, target_crs, text_lengths,
                       to_dt, write_table)

# D8 flow-direction codes -> (dx, dy) in cells
D8 = {1: (1, 0), 2: (1, -1), 4: (0, -1), 8: (-1, -1), 16: (-1, 0), 32: (-1, 1), 64: (0, 1), 128: (1, 1)}
SQM_PER_ACRE = 4046.8564
SQM_PER_SQMI = 2_589_988.1
FT_PER_M = 3.280839895
LEGACY_JURISDICTION = "TRPA Legacy (provisional)"

CROSSING_TABLE = "CulvertCrossings"
WATERSHED_FC = "CulvertWatersheds_inc"
PROFILE_TABLE = "CulvertProfile"


# ----------------------------------------------------------------------------------------
# small helpers

def restricted_jurisdictions(cfg: dict) -> set[str]:
    nd = cfg.get("ndot", {})
    return {nd["jurisdiction"]} if nd.get("enabled") else set()


def write_split_csv(df: pd.DataFrame, name: str, cfg: dict, log, jur_col: str = "jurisdiction") -> None:
    """Public rows under outputs/, the full table to ndot.work_dir (restricted)."""
    restricted = restricted_jurisdictions(cfg)
    out = REPO / cfg["paths"]["outputs"] / f"{name}.csv"
    out.parent.mkdir(exist_ok=True)
    public = df if not restricted else df[~df[jur_col].isin(restricted)]
    public.to_csv(out, index=False)
    log.info(f"{name}: {len(public)} public rows -> {out}")
    if restricted:
        full = Path(cfg["ndot"]["work_dir"]) / f"{name}_all.csv"
        full.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(full, index=False)
        log.info(f"{name}: {len(df)} rows incl. restricted -> {full}")


def read_layer(gdb: str, layer: str, geometry: bool = True, columns=None) -> gpd.GeoDataFrame | pd.DataFrame:
    import pyogrio
    df = pyogrio.read_dataframe(gdb, layer=layer, read_geometry=geometry, columns=columns)
    return df


def read_culverts(cfg: dict, log) -> gpd.GeoDataFrame:
    a = cfg["assets"]
    g = read_layer(cfg["paths"]["analysis_gdb"], a["culverts_fc"]).to_crs(target_crs(cfg))
    log.info(f"Read {len(g)} culvert rows from {a['culverts_fc']}")
    return g


def ensure_fields(target: str, fields, log) -> None:
    import arcpy
    have = {f.name for f in arcpy.ListFields(target)}
    missing = [f for f in fields if f[0] not in have]
    if missing:
        arcpy.management.AddFields(target, fields_spec(missing))
        log.info(f"Added {len(missing)} field(s) to {Path(target).name}: {[f[0] for f in missing]}")


def apply_by_key(target: str, df: pd.DataFrame, key: str, fields, log, date_cols=frozenset()) -> None:
    """Write df columns onto target rows matched on key (UpdateCursor)."""
    import arcpy
    cols = [f[0] for f in fields]
    tl, ft = text_lengths(fields), {n: t for n, t, ln in fields}
    lookup = df.set_index(key)[cols].to_dict("index")
    n = 0
    with arcpy.da.UpdateCursor(target, [key] + cols) as cur:
        for row in cur:
            rec = lookup.get(row[0])
            if rec is None:
                continue
            cur.updateRow([row[0]] + [to_dt(rec[c]) if c in date_cols else clean(rec[c], c, tl, ft.get(c)) for c in cols])
            n += 1
    log.info(f"Updated {n} rows in {Path(target).name}")


# ----------------------------------------------------------------------------------------
# stage 1: terrain (server)

def breach_lines(cfg: dict, log) -> gpd.GeoDataFrame:
    """One breach line per typed culvert on a road segment, and per NBI water-crossing bridge
    or large culvert: through the point, perpendicular to the parent segment at its nearest
    point. Culvert lines are profile.breach.length_m long; bridge lines are stretched to the
    maximum span plus 20 m and sampled beyond the deck, because a lidar surface that kept the
    deck otherwise walls the creek off and sends it to the nearest breached ditch pipe."""
    from shapely.geometry import LineString
    from va_common import read_streets
    a_cfg = cfg["assets"]
    b = cfg["profile"]["breach"]
    base_len, base_from = float(b["length_m"]), float(b["sample_from_m"])
    cul = read_culverts(cfg, log)
    cand = cul[(cul["feature_type"] == "culvert") & cul["parent_segment_id"].notna()].copy()
    cand["asset"] = "culvert"
    cand["len_m"], cand["from_m"] = base_len, base_from
    cand = cand[["culvert_id", "parent_segment_id", "asset", "len_m", "from_m", "geometry"]]
    try:
        if not b.get("bridges", False):
            raise ValueError("profile.breach.bridges is false (bridges sit on enforced channels)")
        br = read_layer(cfg["paths"]["analysis_gdb"], a_cfg["bridges_fc"]).to_crs(cand.crs)
        br = br[(br["water_crossing"] == 1) & br["parent_segment_id"].notna()].copy()
        span = pd.to_numeric(br["max_span_m"], errors="coerce").fillna(0)
        br["asset"] = "bridge"
        br["len_m"] = np.maximum(base_len, span + 20)
        br["from_m"] = np.maximum(base_from, span / 2 + 2)
        br = br.rename(columns={"bridge_id": "culvert_id"})[["culvert_id", "parent_segment_id", "asset", "len_m",
                                                             "from_m", "geometry"]]
        log.info(f"{len(br)} water-crossing bridges and large culverts added to the breach set")
        cand = gpd.GeoDataFrame(pd.concat([cand, br], ignore_index=True), geometry="geometry", crs=cul.crs)
    except Exception as e:
        log.info(f"Bridges not in the breach set: {e}")
    key = a_cfg["streets_key"]
    st = read_streets(cfg, log)
    dup = int(st[key].duplicated().sum())
    if dup:
        log.warning(f"{dup} duplicate {key} values in the street layer; first geometry kept per id")
    streets = st.drop_duplicates(key).set_index(key)["geometry"]
    rows = []
    for _, r in cand.iterrows():
        seg = streets.get(r.parent_segment_id)
        if seg is None or getattr(seg, "is_empty", True):
            continue
        d = seg.project(r.geometry)
        a, c = seg.interpolate(max(d - 0.5, 0)), seg.interpolate(min(d + 0.5, seg.length))
        tx, ty = c.x - a.x, c.y - a.y
        n = math.hypot(tx, ty)
        if n == 0:
            continue
        px, py = -ty / n, tx / n  # unit normal to the road
        x, y = r.geometry.x, r.geometry.y
        half = float(r.len_m) / 2
        rows.append(dict(culvert_id=r.culvert_id, asset=r.asset, len_m=float(r.len_m), from_m=float(r.from_m),
                         geometry=LineString([(x - px * half, y - py * half), (x + px * half, y + py * half)])))
    out = gpd.GeoDataFrame(rows, geometry="geometry", crs=cand.crs)
    log.info(f"{len(out)} breach lines ({len(cand) - len(out)} assets without a usable segment); "
             f"{int((out['asset'] == 'bridge').sum())} are bridges")

    # Keep the breach off the enforced channels. The DEM already carries every mapped stream
    # through its crossing; a breach line that reaches a stream sets its floor from the stream
    # bed and pulls the creek out of its channel into a ditch pipe (Oct. 8: the Upper Truckee
    # through an 18 in pipe, a 1,200 ac creek handed down a chain of Washoe pipes).
    ex = float(b.get("stream_exclude_m", 0) or 0)
    if ex and b.get("streams_layer"):
        from va_common import fetch_rest_features
        streams = fetch_rest_features(b["streams_layer"], out.crs, log)
        if len(streams):
            zone = gpd.GeoDataFrame(geometry=streams.buffer(ex), crs=out.crs)
            hit = gpd.sjoin(out[["geometry"]], zone, how="inner", predicate="intersects").index.unique()
            log.info(f"{len(hit)} breach lines dropped within {ex:.0f} m of a mapped stream or lake "
                     f"(those crossings are enforced in the DEM); {len(out) - len(hit)} remain")
            out = out.drop(index=hit)
    return out


def breach_dem(dem, cfg: dict, log):
    """DEM lowered along the breach lines to min(ground at both ends) - drop_m. Returns a Raster."""
    import arcpy
    from arcpy import sa
    p = cfg["profile"]
    b = p["breach"]
    epsg = cfg["output"]["target_epsg"]
    cell = float(dem.meanCellWidth)
    lines = breach_lines(cfg, log)
    # ground elevation sampled along the outer part of each line, both sides, beyond the fill
    # (or the deck, for bridges)
    spts = "in_memory\\breach_samples"
    arcpy.management.CreateFeatureclass("in_memory", "breach_samples", "POINT",
                                        spatial_reference=arcpy.SpatialReference(epsg))
    arcpy.management.AddField(spts, "lid", "LONG")
    with arcpy.da.InsertCursor(spts, ["SHAPE@XY", "lid"]) as cur:
        for i, (geom, len_m, from_m) in enumerate(zip(lines.geometry, lines["len_m"], lines["from_m"])):
            half = float(len_m) / 2
            (x0, y0), (x1, y1) = geom.coords[0], geom.coords[-1]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            ux, uy = (x1 - x0) / (2 * half), (y1 - y0) / (2 * half)
            for t in [float(s * v) for s in (-1, 1) for v in np.linspace(float(from_m), half, 4)]:
                cur.insertRow([(float(cx + ux * t), float(cy + uy * t)), int(i)])
    sa.ExtractMultiValuesToPoints(spts, [[dem, "z"]], "NONE")
    z = pd.DataFrame([r for r in arcpy.da.SearchCursor(spts, ["lid", "z"])], columns=["lid", "z"])
    zmin = z.groupby("lid")["z"].min()
    lines = lines.reset_index(drop=True)
    lines["z_breach"] = zmin.reindex(range(len(lines))).values - float(b["drop_m"])
    lines = lines[lines["z_breach"].notna()]
    log.info(f"Breach elevations set on {len(lines)} lines (drop {b['drop_m']} m below the lower end)")
    # rasterize and lower the DEM where the breach is below it
    lfc = "in_memory\\breach_lines"
    arcpy.management.CreateFeatureclass("in_memory", "breach_lines", "POLYLINE",
                                        spatial_reference=arcpy.SpatialReference(epsg))
    arcpy.management.AddField(lfc, "z_breach", "DOUBLE")
    sr = arcpy.SpatialReference(epsg)
    with arcpy.da.InsertCursor(lfc, ["SHAPE@", "z_breach"]) as cur:
        for geom, zb in zip(lines.geometry, lines["z_breach"]):
            cur.insertRow([arcpy.Polyline(arcpy.Array([arcpy.Point(*c) for c in geom.coords]), sr), float(zb)])
    arcpy.env.snapRaster = dem
    arcpy.env.extent = dem
    arcpy.env.cellSize = dem
    breach = f"{p['work_gdb']}\\breach_z"
    arcpy.conversion.PolylineToRaster(lfc, "z_breach", breach, "MAXIMUM_LENGTH", "NONE", cell)
    bz = sa.Raster(breach)
    return sa.Con(sa.IsNull(bz), dem, sa.Con(bz < dem, bz, dem))


def stage_terrain(cfg: dict, log, overwrite: bool) -> None:
    import arcpy
    from arcpy import sa
    p = cfg["profile"]
    work = p["work_gdb"]
    if not arcpy.Exists(work):
        arcpy.management.CreateFileGDB(str(Path(work).parent), Path(work).name)
        log.info(f"Created {work}")
    arcpy.CheckOutExtension("Spatial")
    arcpy.env.overwriteOutput = True
    arcpy.env.parallelProcessingFactor = p.get("parallel", "75%")

    dem_src = cfg["paths"]["dem"]
    d = arcpy.Describe(dem_src)
    native = float(d.meanCellWidth)
    log.info(f"DEM {dem_src}: {native} m cells, {d.width} x {d.height}")
    dem = sa.Raster(dem_src)
    cell = float(p["cell_m"])
    if cell > native:
        factor = int(round(cell / native))
        log.warning(f"TEST MODE: aggregating the DEM by {factor} with MINIMUM to {native * factor} m")
        dem_path = f"{work}\\dem_{int(native * factor)}m"
        if overwrite or not arcpy.Exists(dem_path):
            sa.Aggregate(dem, factor, "MINIMUM", "EXPAND", "DATA").save(dem_path)
        dem = sa.Raster(dem_path)
    arcpy.env.snapRaster = dem
    arcpy.env.extent = dem
    arcpy.env.cellSize = dem

    def build(name, fn):
        path = f"{work}\\{name}"
        if arcpy.Exists(path) and not overwrite:
            log.info(f"{name} exists, skipping")
            return
        log.info(f"Building {name} ...")
        fn().save(path)
        log.info(f"{name} -> {path}")

    # Breach the road fill through every inventoried culvert. The enforcement breached the
    # mapped drainage lines, not every crossing; where a creek meets an unbreached fill the
    # Fill below spills it along the roadside ditch to the next low point, and every ditch
    # pipe downstream inherits the creek. A short line through each culvert, perpendicular
    # to its parent road segment, lowered to the lower of its two ends minus a small drop,
    # lets the creek pass where its culvert actually is.
    flow_dem = dem
    b = p.get("breach") or {}
    if b.get("enabled", True):
        build("dem_breach", lambda: breach_dem(dem, cfg, log))
        flow_dem = sa.Raster(f"{work}\\dem_breach")
    else:
        log.warning("No breach (profile.breach.enabled false): creeks at unbreached crossings spill along ditches")

    # Depth-limited Fill. The enforced DEM still holds sinks (ditch ponds behind unbreached
    # road fills, pits); FlowDirection without Fill turns each into a two-cell loop that
    # splits accumulation between the loop cells and ends the flow path at the fill. Sinks
    # deeper than the limit (lakes, real basins) are left alone. Slope and zonal elevation
    # keep using the unfilled surface.
    z_limit = p.get("fill_z_limit_m")
    if z_limit:
        src = flow_dem
        build("dem_fill", lambda: sa.Fill(src, float(z_limit)))
        flow_dem = sa.Raster(f"{work}\\dem_fill")
        log.info(f"Flow direction from the breached, filled DEM (sinks under {z_limit} m filled)")
    else:
        log.warning("No Fill (profile.fill_z_limit_m unset): unbreached sinks will loop and truncate flow")

    build("fdir", lambda: sa.FlowDirection(flow_dem, "NORMAL", None, "D8"))
    fdir = sa.Raster(f"{work}\\fdir")
    build("facc", lambda: sa.FlowAccumulation(fdir, None, "FLOAT", "D8"))
    build("slope_pct", lambda: sa.Slope(dem, "PERCENT_RISE"))
    if p.get("flow_length", True):
        build("flen_up", lambda: sa.FlowLength(fdir, "UPSTREAM"))
    if cell <= native and (overwrite or not arcpy.Exists(f"{work}\\dem")):
        log.info("Copying the DEM into the work geodatabase (zonal statistics source)")
        arcpy.management.CopyRaster(dem_src, f"{work}\\dem")
    arcpy.CheckInExtension("Spatial")
    log.info("Terrain stage complete")


# ----------------------------------------------------------------------------------------
# stage 2: delineate (server)

def _group_crossings(pts: gpd.GeoDataFrame, dist_m: float) -> pd.Series:
    """Union-find on culverts within dist_m of each other on the same parent segment."""
    parent = {i: i for i in pts.index}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for _, grp in pts.groupby("parent_segment_id"):
        if len(grp) < 2:
            continue
        buf = grp[["geometry"]].copy()
        buf["geometry"] = buf.geometry.buffer(dist_m / 2)
        pairs = gpd.sjoin(buf, grp[["geometry"]], how="inner", predicate="intersects")
        for i, j in zip(pairs.index, pairs["index_right"]):
            if i != j:
                parent[find(i)] = find(j)
    roots = pd.Series({i: find(i) for i in pts.index})
    return roots


def aggregate_upstream(tree: pd.DataFrame, lc_cols: list, log, mean_cols: list[str] = ()) -> dict[int, tuple]:
    """Sum each crossing's incremental zone with everything upstream of it.

    `tree` is indexed by pp_id with `dn_zone` (the next crossing downstream, NaN at an
    outlet), `inc_cells`, `inc_slope_mean`, `inc_elev_max`, one column per NLCD code in
    `lc_cols`, and any per-zone means named in `mean_cols` (area-weighted up the tree).
    Returns {pp_id: (cells, slope_sum, elev_max, {code: cells}, {mean_col: weighted_sum})}.

    Cycles are cut first. D8 flow direction can loop inside flat sinks (the aggregated test
    DEM has them; the hydro-enforced 2 m DEM should not), and a looped downstream chain
    would otherwise never resolve. Walking downstream from every crossing, an edge that
    lands on a crossing already on the current walk is dropped and that crossing becomes
    an outlet; `dn_zone` is set to NaN for it in place. Aggregation then runs leaves-first
    (Kahn's order) with no recursion, so the depth of the drainage tree does not matter.
    """
    ids = [int(i) for i in tree.index]
    down_map = {int(pid): int(dz) for pid, dz in tree["dn_zone"].items()
                if pd.notna(dz) and int(dz) in tree.index}

    state: dict[int, int] = {}  # 1 = on the current walk, 2 = finished
    cut: list[tuple[int, int]] = []
    for start in ids:
        n, path = start, []
        while state.get(n, 0) == 0:
            state[n] = 1
            path.append(n)
            nxt = down_map.get(n)
            if nxt is None:
                break
            if state.get(nxt) == 1:
                cut.append((n, nxt))
                del down_map[n]
                break
            n = nxt
        for m in path:
            state[m] = 2
    if cut:
        log.warning(f"{len(cut)} downstream links cut to break drainage-tree cycles (flat sinks in the "
                    f"flow direction raster); those crossings are treated as outlets: "
                    f"{', '.join(f'X{a:05d}->X{b:05d}' for a, b in cut[:20])}{' ...' if len(cut) > 20 else ''}")
        tree.loc[[a for a, _ in cut], "dn_zone"] = np.nan

    children: dict[int, list[int]] = {}
    for c, par in down_map.items():
        children.setdefault(par, []).append(c)

    full: dict[int, tuple] = {}
    pending = {pid: len(children.get(pid, [])) for pid in ids}
    ready = [pid for pid, k in pending.items() if k == 0]
    while ready:
        pid = ready.pop()
        own = tree.loc[pid]
        cells = float(own["inc_cells"]) if pd.notna(own["inc_cells"]) else 0.0
        slope_sum = (float(own["inc_slope_mean"]) * cells) if cells and pd.notna(own["inc_slope_mean"]) else 0.0
        elev = float(own["inc_elev_max"]) if pd.notna(own["inc_elev_max"]) else -np.inf
        lcs = {c: (float(own[c]) if pd.notna(own[c]) else 0.0) for c in lc_cols}
        own_cells = float(own["inc_cells"]) if pd.notna(own["inc_cells"]) else 0.0
        wsum = {c: (float(own[c]) * own_cells if own_cells and pd.notna(own[c]) else 0.0) for c in mean_cols}
        for ch in children.get(pid, []):
            c_cells, c_slope_sum, c_elev, c_lcs, c_wsum = full[ch]
            cells += c_cells
            slope_sum += c_slope_sum
            elev = max(elev, c_elev)
            for k in lc_cols:
                lcs[k] += c_lcs[k]
            for k in mean_cols:
                wsum[k] += c_wsum[k]
        full[pid] = (cells, slope_sum, elev, lcs, wsum)
        par = down_map.get(pid)
        if par is not None:
            pending[par] -= 1
            if pending[par] == 0:
                ready.append(par)
    if len(full) != len(ids):
        raise RuntimeError(f"drainage-tree aggregation left {len(ids) - len(full)} crossings unresolved")
    return full


def stage_delineate(cfg: dict, log, overwrite: bool) -> None:
    import arcpy
    from arcpy import sa
    p = cfg["profile"]
    work = p["work_gdb"]
    gdb = cfg["paths"]["analysis_gdb"]
    epsg = cfg["output"]["target_epsg"]
    for r in ("fdir", "facc", "slope_pct"):
        if not arcpy.Exists(f"{work}\\{r}"):
            raise SystemExit(f"{work}\\{r} missing: run --stage terrain first")
    out_tbl, out_fc = f"{gdb}\\{CROSSING_TABLE}", f"{gdb}\\{WATERSHED_FC}"
    if (arcpy.Exists(out_tbl) or arcpy.Exists(out_fc)) and not overwrite:
        raise SystemExit(f"{CROSSING_TABLE} / {WATERSHED_FC} exist. Re-run with --overwrite.")

    arcpy.CheckOutExtension("Spatial")
    arcpy.env.overwriteOutput = True
    arcpy.env.parallelProcessingFactor = p.get("parallel", "75%")
    fdir, facc = sa.Raster(f"{work}\\fdir"), sa.Raster(f"{work}\\facc")
    slope = sa.Raster(f"{work}\\slope_pct")
    dem_name = "dem" if float(p["cell_m"]) <= float(arcpy.Describe(cfg["paths"]["dem"]).meanCellWidth) \
        else f"dem_{int(p['cell_m'])}m"
    dem = sa.Raster(f"{work}\\{dem_name}")
    flen = sa.Raster(f"{work}\\flen_up") if arcpy.Exists(f"{work}\\flen_up") else None
    cell = float(facc.meanCellWidth)
    arcpy.env.snapRaster = facc
    arcpy.env.extent = facc
    arcpy.env.cellSize = facc
    scratch = "in_memory"

    # 1. candidate culverts: typed culvert, on a road segment
    cul = read_culverts(cfg, log)
    cand = cul[(cul["feature_type"] == "culvert") & cul["parent_segment_id"].notna()].copy()
    cand = cand.reset_index(drop=True)
    cand["pp_id"] = np.arange(1, len(cand) + 1, dtype=np.int64)
    log.info(f"{len(cand)} culverts to delineate (typed culvert, snapped to a segment)")

    # 2. snap every culvert to its pour point (max accumulation within pour_snap_m)
    pts = f"{scratch}\\culvert_pts"
    arcpy.management.CreateFeatureclass(scratch, "culvert_pts", "POINT", spatial_reference=arcpy.SpatialReference(epsg))
    arcpy.management.AddField(pts, "pp_id", "LONG")
    with arcpy.da.InsertCursor(pts, ["SHAPE@XY", "pp_id"]) as cur:
        for _, r in cand.iterrows():
            cur.insertRow([(r.geometry.x, r.geometry.y), int(r.pp_id)])
    snapped = sa.SnapPourPoint(pts, facc, p["pour_snap_m"], "pp_id")
    snap_pts = f"{scratch}\\snap_pts"
    arcpy.conversion.RasterToPoint(snapped, snap_pts, "VALUE")
    sa.ExtractMultiValuesToPoints(snap_pts, [[facc, "facc"], [fdir, "fdir"], [dem, "elev_m"]]
                                  + ([[flen, "flen_m"]] if flen is not None else []), "NONE")
    rows = [r for r in arcpy.da.SearchCursor(snap_pts, ["grid_code", "SHAPE@X", "SHAPE@Y", "facc", "fdir", "elev_m"]
                                             + (["flen_m"] if flen is not None else []))]
    cols = ["pp_id", "pp_x", "pp_y", "facc", "fdir", "elev_m"] + (["flen_m"] if flen is not None else [])
    snap = pd.DataFrame(rows, columns=cols)
    cand = cand.merge(snap, on="pp_id", how="left")
    cand["snap_dist_m"] = np.hypot(cand.geometry.x - cand["pp_x"], cand.geometry.y - cand["pp_y"]).round(1)
    n_un = int(cand["pp_x"].isna().sum())
    log.info(f"Snapped {len(cand) - n_un} culverts; {n_un} had no flow cell within {p['pour_snap_m']} m")

    # 3. group multi-barrel crossings; representative = member with the largest accumulation
    snap_geom = gpd.GeoDataFrame(cand[["parent_segment_id"]],
                                 geometry=gpd.points_from_xy(cand["pp_x"].fillna(cand.geometry.x),
                                                             cand["pp_y"].fillna(cand.geometry.y)), crs=cand.crs)
    roots = _group_crossings(snap_geom, p["crossing_group_m"])
    cand["crossing_root"] = roots.reindex(cand.index).values
    rep = cand.sort_values("facc", ascending=False).groupby("crossing_root").head(1)
    rep_id = rep.set_index("crossing_root")["pp_id"]
    cand["crossing_pp"] = cand["crossing_root"].map(rep_id)
    cand["crossing_id"] = "X" + cand["crossing_pp"].astype(int).astype(str).str.zfill(5)
    cand["barrels"] = cand.groupby("crossing_pp")["pp_id"].transform("size")
    log.info(f"{cand['crossing_id'].nunique()} crossings ({int((cand['barrels'] > 1).sum())} culverts in multi-barrel groups)")

    # 4. incremental watersheds from the crossing pour cells
    xpts = f"{scratch}\\xing_pts"
    arcpy.management.CreateFeatureclass(scratch, "xing_pts", "POINT", spatial_reference=arcpy.SpatialReference(epsg))
    arcpy.management.AddField(xpts, "xid", "LONG")
    reps = cand[cand["pp_id"] == cand["crossing_pp"]].dropna(subset=["pp_x"])
    with arcpy.da.InsertCursor(xpts, ["SHAPE@XY", "xid"]) as cur:
        for _, r in reps.iterrows():
            cur.insertRow([(r.pp_x, r.pp_y), int(r.pp_id)])
    xcells = sa.SnapPourPoint(xpts, facc, 0.0, "xid")
    log.info("Delineating incremental watersheds ...")
    wshed = sa.Watershed(fdir, xcells, "VALUE")
    wshed_path = f"{work}\\wshed_inc"
    wshed.save(wshed_path)

    # 5. downstream crossing: the zone one D8 step below each pour cell
    dn = reps[["pp_id", "pp_x", "pp_y", "fdir"]].copy()
    dxdy = dn["fdir"].map(lambda c: D8.get(int(c), (0, 0)) if pd.notna(c) else (0, 0))
    dn["dn_x"] = dn["pp_x"] + dxdy.map(lambda t: t[0]) * cell
    dn["dn_y"] = dn["pp_y"] + dxdy.map(lambda t: t[1]) * cell
    dpts = f"{scratch}\\down_pts"
    arcpy.management.CreateFeatureclass(scratch, "down_pts", "POINT", spatial_reference=arcpy.SpatialReference(epsg))
    arcpy.management.AddField(dpts, "xid", "LONG")
    with arcpy.da.InsertCursor(dpts, ["SHAPE@XY", "xid"]) as cur:
        for _, r in dn.iterrows():
            cur.insertRow([(r.dn_x, r.dn_y), int(r.pp_id)])
    sa.ExtractMultiValuesToPoints(dpts, [[wshed, "dn_zone"]], "NONE")
    down = pd.DataFrame([r for r in arcpy.da.SearchCursor(dpts, ["xid", "dn_zone"])], columns=["pp_id", "dn_zone"])
    down["dn_zone"] = pd.to_numeric(down["dn_zone"], errors="coerce")
    down.loc[down["dn_zone"] == down["pp_id"], "dn_zone"] = np.nan  # a cell cannot drain to itself
    # A downstream crossing must carry at least the upstream one's accumulation. A link that
    # fails this comes from a flow-direction loop (two sink cells pointing at each other) or a
    # pour cell on a neighboring channel; drop it rather than let the tree sum the wrong way.
    facc_by_pp = reps.set_index("pp_id")["facc"]
    up_f = down["pp_id"].map(facc_by_pp)
    dn_f = down["dn_zone"].map(facc_by_pp)
    bad_link = down["dn_zone"].notna() & dn_f.notna() & (dn_f < up_f)
    if bad_link.any():
        log.warning(f"{int(bad_link.sum())} downstream links dropped: the downstream crossing has less flow "
                    f"accumulation than the upstream one (flow-direction loops at unfilled sinks)")
        down.loc[bad_link, "dn_zone"] = np.nan

    # 6. zonal statistics on the incremental zones
    log.info("Zonal statistics (count, mean slope, max and mean elevation, PRISM precipitation) ...")
    zs_slope = f"{scratch}\\zs_slope"
    sa.ZonalStatisticsAsTable(wshed, "Value", slope, zs_slope, "DATA", "MEAN")
    zs_elev = f"{scratch}\\zs_elev"
    sa.ZonalStatisticsAsTable(wshed, "Value", dem, zs_elev, "DATA", "MIN_MAX_MEAN")
    zsl = pd.DataFrame([r for r in arcpy.da.SearchCursor(zs_slope, ["VALUE", "COUNT", "MEAN"])],
                       columns=["pp_id", "inc_cells", "inc_slope_mean"])
    zel = pd.DataFrame([r for r in arcpy.da.SearchCursor(zs_elev, ["VALUE", "MAX", "MEAN"])],
                       columns=["pp_id", "inc_elev_max", "inc_elev_mean"])
    zones = zsl.merge(zel, on="pp_id", how="left")
    mean_cols = ["inc_elev_mean"]
    prism = p.get("prism_ppt")
    if prism and arcpy.Exists(prism):
        zs_ppt = f"{scratch}\\zs_ppt"
        # 800 m normals resampled to the zone grid on the fly through the cell-size environment
        sa.ZonalStatisticsAsTable(wshed, "Value", sa.Raster(prism), zs_ppt, "DATA", "MEAN")
        zpp = pd.DataFrame([r for r in arcpy.da.SearchCursor(zs_ppt, ["VALUE", "MEAN"])],
                           columns=["pp_id", "inc_ppt_mm"])
        zones = zones.merge(zpp, on="pp_id", how="left")
        mean_cols.append("inc_ppt_mm")
    else:
        log.warning(f"PRISM normals not found at profile.prism_ppt ({prism}); basin precipitation will be null "
                    f"and the regression cannot run. python scripts/fetch_prism.py downloads them.")
        zones["inc_ppt_mm"] = np.nan
        mean_cols.append("inc_ppt_mm")
    lc = None
    if p.get("nlcd"):
        log.info("Tabulating NLCD area per zone ...")
        ta = f"{scratch}\\ta_nlcd"
        sa.TabulateArea(wshed, "Value", sa.Raster(p["nlcd"]), "Value", ta, cell)
        fld = [f.name for f in arcpy.ListFields(ta) if f.name.upper().startswith("VALUE_")]
        lc = pd.DataFrame([r for r in arcpy.da.SearchCursor(ta, ["VALUE"] + fld)], columns=["pp_id"] + fld)
        lc.columns = ["pp_id"] + [int(c.split("_")[1]) for c in fld]

    # 7. aggregate up the drainage tree: full contributing area, area-weighted slope, max elev, landcover
    tree = reps[["pp_id"]].merge(down, on="pp_id", how="left").merge(zones, on="pp_id", how="left")
    if lc is not None:
        tree = tree.merge(lc, on="pp_id", how="left")
    tree = tree.set_index("pp_id")
    lc_cols = [c for c in tree.columns if isinstance(c, (int, np.integer))]
    full = aggregate_upstream(tree, lc_cols, log, mean_cols=mean_cols)
    tree["full_cells"] = [full[int(i)][0] for i in tree.index]
    tree["basin_slope_pct"] = [full[int(i)][1] / full[int(i)][0] if full[int(i)][0] else np.nan for i in tree.index]
    tree["basin_elev_max_m"] = [full[int(i)][2] if np.isfinite(full[int(i)][2]) else np.nan for i in tree.index]
    tree["basin_elev_mean_ft"] = [full[int(i)][4]["inc_elev_mean"] / full[int(i)][0] * FT_PER_M
                                  if full[int(i)][0] else np.nan for i in tree.index]
    tree["basin_precip_in"] = [full[int(i)][4]["inc_ppt_mm"] / full[int(i)][0] / 25.4
                               if full[int(i)][0] else np.nan for i in tree.index]
    tree["contrib_area_ac"] = tree["full_cells"] * cell * cell / SQM_PER_ACRE
    # FlowAccumulation counts upstream cells only; add the pour cell so this is comparable to
    # full_cells, which comes from watershed zones that include it.
    tree["facc_area_ac"] = (reps.set_index("pp_id")["facc"].reindex(tree.index) + 1) * cell * cell / SQM_PER_ACRE
    if lc_cols:
        groups = {int(code): grp for grp, codes in p["nlcd_groups"].items() for code in codes}
        gsum = pd.DataFrame({g: 0.0 for g in p["nlcd_groups"]}, index=tree.index)
        for i in tree.index:
            for code in lc_cols:
                g = groups.get(int(code))
                if g:
                    gsum.loc[i, g] += full[int(i)][3][code]
        tree["basin_landcover"] = gsum.idxmax(axis=1).where(gsum.sum(axis=1) > 0)
        tot = gsum.sum(axis=1).replace(0, np.nan)
        tree["runoff_c"] = sum(gsum[g] * p["runoff_c"].get(g, p["runoff_c"]["default"]) for g in gsum.columns) / tot
    else:
        tree["basin_landcover"] = None
        tree["runoff_c"] = np.nan

    # 8. assemble the crossing table
    rep_attrs = reps.set_index("pp_id")[["pp_x", "pp_y", "elev_m", "snap_dist_m"] + (["flen_m"] if flen is not None else [])]
    xt = tree.join(rep_attrs)
    xt = xt.reset_index().rename(columns={"pp_id": "crossing_pp", "dn_zone": "downstream_pp"})
    xt["crossing_id"] = "X" + xt["crossing_pp"].astype(int).astype(str).str.zfill(5)
    xt["downstream_crossing_id"] = xt["downstream_pp"].map(
        lambda v: f"X{int(v):05d}" if pd.notna(v) else None)
    xt["pp_elev_ft"] = xt["elev_m"] * FT_PER_M
    xt["relief_ft"] = (xt["basin_elev_max_m"] - xt["elev_m"]).clip(lower=0) * FT_PER_M
    if flen is None:
        xt["flen_m"] = np.nan
    xt["flow_len_ft"] = xt["flen_m"] * FT_PER_M
    members = cand.groupby("crossing_pp").agg(barrels=("pp_id", "size"),
                                              member_ids=("culvert_id", lambda s: ";".join(s)),
                                              jurisdiction=("jurisdiction", "first"),
                                              restricted=("jurisdiction", lambda s: int(s.isin(restricted_jurisdictions(cfg)).any())))
    xt = xt.merge(members, left_on="crossing_pp", right_index=True, how="left")
    xt["area_check_pct"] = ((xt["contrib_area_ac"] - xt["facc_area_ac"]) / xt["facc_area_ac"].replace(0, np.nan) * 100).round(1)
    xt["delineated"] = pd.Timestamp.today().normalize()
    xt = xt[["crossing_id", "crossing_pp", "downstream_crossing_id", "barrels", "member_ids", "jurisdiction",
             "restricted", "pp_x", "pp_y", "snap_dist_m", "pp_elev_ft", "basin_elev_max_m", "basin_elev_mean_ft",
             "basin_precip_in", "relief_ft", "flow_len_ft", "inc_cells", "full_cells", "contrib_area_ac",
             "facc_area_ac", "area_check_pct", "basin_slope_pct", "basin_landcover", "runoff_c", "delineated"]]
    log.info("Basin mean annual precipitation (in) quantiles:\n"
             + xt["basin_precip_in"].quantile([.1, .5, .9]).round(1).to_string())
    log.info("Contributing area (ac) quantiles:\n" + xt["contrib_area_ac"].quantile([.1, .5, .9, .99]).round(1).to_string())
    # Flag only when the disagreement is both relative (> 5 pct) and more than two cells, so
    # tiny basins do not trip on rounding.
    cell_diff = (xt["contrib_area_ac"] - xt["facc_area_ac"]).abs() * SQM_PER_ACRE / (cell * cell)
    bad = xt[(xt["area_check_pct"].abs() > 5) & (cell_diff > 2)]
    if len(bad):
        log.warning(f"{len(bad)} crossings where the tree-aggregated area differs from flow accumulation by > 5 pct "
                    f"and > 2 cells (largest: {bad['area_check_pct'].abs().max():.0f} pct). Shared pour cells, "
                    f"cut cycles, and unsnapped upstream culverts are the usual causes.")

    # 9. write outputs
    xfields = [("crossing_id", "TEXT", 12), ("crossing_pp", "LONG", None), ("downstream_crossing_id", "TEXT", 12),
               ("barrels", "SHORT", None), ("member_ids", "TEXT", 2000), ("jurisdiction", "TEXT", 60),
               ("restricted", "SHORT", None), ("pp_x", "DOUBLE", None), ("pp_y", "DOUBLE", None),
               ("snap_dist_m", "DOUBLE", None), ("pp_elev_ft", "DOUBLE", None), ("basin_elev_max_m", "DOUBLE", None),
               ("basin_elev_mean_ft", "DOUBLE", None), ("basin_precip_in", "DOUBLE", None),
               ("relief_ft", "DOUBLE", None), ("flow_len_ft", "DOUBLE", None), ("inc_cells", "DOUBLE", None),
               ("full_cells", "DOUBLE", None), ("contrib_area_ac", "DOUBLE", None), ("facc_area_ac", "DOUBLE", None),
               ("area_check_pct", "DOUBLE", None), ("basin_slope_pct", "DOUBLE", None),
               ("basin_landcover", "TEXT", 20), ("runoff_c", "DOUBLE", None), ("delineated", "DATE", None)]
    for pth in (out_tbl, out_fc):
        if arcpy.Exists(pth):
            arcpy.management.Delete(pth)
    write_table(xt, xfields, gdb, CROSSING_TABLE, log, date_cols={"delineated"})
    arcpy.management.AddIndex(out_tbl, ["crossing_id"], "xing_id_idx", "UNIQUE")
    log.info("Incremental watershed polygons ...")
    arcpy.conversion.RasterToPolygon(wshed, out_fc, "NO_SIMPLIFY", "VALUE", "MULTIPLE_OUTER_PART")
    arcpy.management.AddField(out_fc, "crossing_id", "TEXT", field_length=12)
    arcpy.management.AddField(out_fc, "downstream_crossing_id", "TEXT", field_length=12)
    dn_map = xt.set_index("crossing_pp")["downstream_crossing_id"].to_dict()
    with arcpy.da.UpdateCursor(out_fc, ["gridcode", "crossing_id", "downstream_crossing_id"]) as cur:
        for row in cur:
            row[1] = f"X{int(row[0]):05d}"
            row[2] = dn_map.get(int(row[0]))
            cur.updateRow(row)
    # per-culvert crossing membership + snap QA
    link = cand[["culvert_id", "jurisdiction", "crossing_id", "barrels", "snap_dist_m", "facc"]].copy()
    write_split_csv(link, "culvert_crossing_link", cfg, log)
    write_split_csv(xt, "culvert_crossings", cfg, log)
    arcpy.CheckInExtension("Spatial")
    log.info("Delineate stage complete")


# ----------------------------------------------------------------------------------------
# stage 3: attributes (anywhere)

def _material_class(m) -> str:
    if m is None or (isinstance(m, float) and pd.isna(m)):
        return "unknown"
    s = str(m).strip().lower()
    if any(k in s for k in ("cmp", "csp", "corrugated", "annular", "squash", "steel", "metal", "aluminum")):
        return "corrodible_metal"
    if any(k in s for k in ("hdpe", "pvc", "plastic", "poly", "cipp", "cured")):
        return "plastic"
    if any(k in s for k in ("rcp", "concrete", "rcb", "box", "masonry", "cip")):
        return "concrete"
    return "unknown"


def _size_class(d, breaks) -> str | None:
    if d is None or pd.isna(d):
        return None
    labels = ["small", "medium", "large", "major"]
    for lab, b in zip(labels, breaks):
        if d <= b:
            return lab
    return labels[-1]


def _inlet_key(material_class: str, shape, inlet) -> str:
    sh = str(shape or "").lower()
    inl = str(inlet or "").lower()
    if any(k in sh for k in ("box", "rect")):
        return "box_concrete"
    if "arch" in sh:
        return "arch_metal"
    if material_class in ("concrete", "plastic"):
        return "circular_concrete"
    if any(k in inl for k in ("headwall", "wingwall", "flared", "fes", "end section")):
        return "circular_metal_headwall"
    return "circular_metal_projecting"


def capacity(row, p: dict) -> tuple[float | None, float | None]:
    """(inlet-control Q at hw_d, Manning full-flow Q) in cfs for one barrel."""
    span, rise = row["span_in"], row["rise_in"]
    if pd.isna(span) or span <= 0:
        return None, None
    rise = span if pd.isna(rise) or rise <= 0 else rise
    key = _inlet_key(row["material_class"], row.get("xsection_shape"), row.get("inlet_type"))
    w_ft, h_ft = span / 12.0, rise / 12.0
    if key == "box_concrete":
        area, perim = w_ft * h_ft, 2 * (w_ft + h_ft)
    elif key == "arch_metal":
        area, perim = math.pi * w_ft * h_ft / 4.0, math.pi * (w_ft + h_ft) / 2.0
    else:
        area, perim = math.pi * (w_ft / 2.0) ** 2, math.pi * w_ft
        h_ft = w_ft
    coef = p["inlet_control"][key]
    s = p["culvert_slope"]
    term = p["hw_d"] - coef["Y"] + 0.5 * s
    q_inlet = area * math.sqrt(h_ft) * math.sqrt(term / coef["c"]) if term > 0 else 0.0
    n = p["manning_n"].get(row["material_class"], p["manning_n"]["unknown"])
    q_full = 1.486 / n * area * (area / perim) ** (2.0 / 3.0) * math.sqrt(s)
    return round(q_inlet, 1), round(q_full, 1)


_DUR_MIN = {"min": 1, "hr": 60, "day": 1440}


def load_ddf(cfg: dict, log) -> tuple[pd.DataFrame, gpd.GeoDataFrame]:
    """Atlas 14 depths (in) by point, duration (min), ARI; plus the PFDS points in the target CRS."""
    ddf = pd.read_csv(REPO / cfg["profile"]["ddf_csv"])
    parts = ddf["duration"].str.extract(r"(\d+)-(\w+)")
    ddf["dur_min"] = parts[0].astype(int) * parts[1].map(_DUR_MIN)
    ddf = ddf[ddf["dur_min"] <= 1440]
    pts = ddf.groupby("point")[["lat", "lon"]].first().reset_index()
    pts = gpd.GeoDataFrame(pts, geometry=gpd.points_from_xy(pts["lon"], pts["lat"]), crs="EPSG:4326").to_crs(target_crs(cfg))
    log.info(f"Atlas 14 DDF: {len(pts)} points, durations {sorted(ddf['dur_min'].unique())} min")
    return ddf, pts


def intensity_in_hr(ddf: pd.DataFrame, point: str, ari: int, tc_min: float) -> float | None:
    sub = ddf[(ddf["point"] == point) & (ddf["ari_years"] == ari)].sort_values("dur_min")
    if sub.empty:
        return None
    x, y = np.log(sub["dur_min"].values), np.log(sub["depth_in"].values)
    depth = float(np.exp(np.interp(np.log(tc_min), x, y)))
    return depth / (tc_min / 60.0)


COND_MAP_1TO5 = {5: 0, 4: 1, 3: 2, 2: 3, 1: 3}
COND_MAP_GFP = {"good": 0, "fair": 2, "poor": 3, "moderate": 2}


def _blockage_class(b) -> float | None:
    if b is None or pd.isna(b):
        return None
    return 0 if b < 25 else 1 if b < 50 else 2 if b < 75 else 3


def harmonize_condition(cond: pd.DataFrame, cfg: dict, log) -> pd.DataFrame:
    """Latest inspection per culvert -> cond_class (0 good to 3 poor), cond_source, cond_date, blockage."""
    c = cond.copy()
    c["inspection_date"] = pd.to_datetime(c["inspection_date"], errors="coerce")
    c = c.sort_values(["culvert_id", "inspection_date"], na_position="first")
    latest = c.groupby("culvert_id").tail(1).set_index("culvert_id")

    def rate(r):
        j, txt = str(r["jurisdiction"]), r["condition_rating"]
        s = None if txt is None or pd.isna(txt) else str(txt).strip()
        if j in ("Placer County", "Douglas County"):
            try:
                return COND_MAP_1TO5.get(int(float(s)), None) if s else None
            except ValueError:
                return None
        if j.startswith("NDOT"):
            return COND_MAP_GFP.get(s.lower(), None) if s else None
        if j == LEGACY_JURISDICTION:
            if not s:
                return None
            low = s.lower()
            first = low.replace("-", " ").replace("/", " ").replace(",", " ").split()[0] if low.split() else ""
            if first in COND_MAP_GFP:
                v = COND_MAP_GFP[first]
                if "fair" in low and "good" in low:
                    return 1
                if "fair" in low and "poor" in low:
                    return 3
                return v
            return None
        return None  # Washoe (near-constant structural code), Caltrans, CSLT, El Dorado: no rating

    latest["cond_rated"] = latest.apply(rate, axis=1)
    latest["blk_class"] = latest["blockage_pct"].map(_blockage_class)
    latest["cond_class"] = latest[["cond_rated", "blk_class"]].max(axis=1)
    latest["cond_source"] = np.where(latest["cond_rated"].notna(), "rated",
                                     np.where(latest["blk_class"].notna(), "blockage_only", "default"))
    latest.loc[latest["cond_class"].isna(), "cond_class"] = 1
    stale_year = cfg["profile"]["cond_stale_year"]
    latest["cond_stale"] = ((latest["cond_source"] != "default") &
                            (latest["inspection_date"].isna() | (latest["inspection_date"].dt.year < stale_year))).astype(int)
    out = latest[["cond_class", "cond_source", "inspection_date", "cond_stale", "blockage_pct"]].rename(
        columns={"inspection_date": "cond_date"})
    log.info("Condition source counts:\n" + out["cond_source"].value_counts().to_string())
    return out


def culvert_state(cul: gpd.GeoDataFrame, reg: dict) -> pd.Series:
    """CA or NV per culvert: by jurisdiction where the agency implies the state, otherwise by
    position against the state line (the 120 W meridian north of 39 N, the diagonal south of it)."""
    nv = set(reg.get("nv_jurisdictions", [])); ca = set(reg.get("ca_jurisdictions", []))
    state = pd.Series(np.where(cul["jurisdiction"].isin(nv), "NV", np.where(cul["jurisdiction"].isin(ca), "CA", None)),
                      index=cul.index, dtype="object")
    need = state.isna() & cul.geometry.notna()
    if need.any():
        ll = cul.loc[need].to_crs("EPSG:4326")
        lon, lat = ll.geometry.x, ll.geometry.y
        boundary = np.where(lat >= 39.0, -120.0, -120.0 + (39.0 - lat) * 1.35)  # diagonal runs SE from 39 N 120 W
        state.loc[need] = np.where(lon > boundary, "NV", "CA")
    return state


# Regional regression coefficients: Q_T = a * AREA^b * PRECIP^c, AREA in square miles, PRECIP
# mean annual precipitation in inches. CA: Gotvald and others (2012, SIR 2012-5113) table 5,
# Lahontan region (4- and 1-percent AEP rows). NV: Thomas and others (1997, WSP 2433) region 1
# as reproduced in USGS Fact Sheet 123-98 table 1.
REGRESSION = {
    "CA": {25: (0.394, 0.733, 1.58), 100: (0.713, 0.731, 1.56)},
    "NV": {25: (3.08, 0.768, 0.811), 100: (6.78, 0.750, 0.668)},
}


def regression_q(area_sqmi: pd.Series, precip_in: pd.Series, state: pd.Series, rp: int) -> pd.Series:
    """Regional-regression peak flow (cfs) for the return period, per culvert, by state."""
    out = pd.Series(np.nan, index=area_sqmi.index, dtype="float")
    for st, coefs in REGRESSION.items():
        if rp not in coefs:
            continue
        a, b, c = coefs[rp]
        m = (state == st) & area_sqmi.gt(0) & precip_in.gt(0)
        out[m] = a * area_sqmi[m] ** b * precip_in[m] ** c
    return out


def profile_fields(cfg: dict):
    rps = cfg["profile"]["return_periods"]
    f = [("d_eq_in", "DOUBLE", None), ("size_class", "TEXT", 10), ("material_class", "TEXT", 20),
         ("crossing_id", "TEXT", 12), ("barrels", "SHORT", None), ("large_culvert_id", "TEXT", 20),
         ("scored", "SHORT", None), ("contrib_area_ac", "DOUBLE", None), ("basin_slope_pct", "DOUBLE", None),
         ("basin_elev_mean_ft", "DOUBLE", None), ("basin_precip_in", "DOUBLE", None),
         ("basin_landcover", "TEXT", 20), ("runoff_c", "DOUBLE", None), ("tc_min", "DOUBLE", None),
         ("ddf_point", "TEXT", 30), ("q_method", "TEXT", 20), ("q_region", "TEXT", 30)]
    f += [(f"q_event_{rp}_cfs", "DOUBLE", None) for rp in rps]
    f += [("q_cap_cfs", "DOUBLE", None), ("q_full_cfs", "DOUBLE", None), ("q_cap_crossing_cfs", "DOUBLE", None)]
    f += [(f"load_ratio_{rp}", "DOUBLE", None) for rp in rps]
    f += [("cond_class", "SHORT", None), ("cond_source", "TEXT", 20), ("cond_date", "DATE", None),
          ("cond_stale", "SHORT", None), ("blockage_pct", "DOUBLE", None), ("pp_elev_ft", "DOUBLE", None),
          ("tailwater_flag", "SHORT", None), ("dem_vintage_flag", "SHORT", None), ("snap_dist_m", "DOUBLE", None),
          ("profile_completeness", "TEXT", 10), ("profile_date", "DATE", None)]
    return f


def stage_attributes(cfg: dict, log, dry_run: bool, apply: bool) -> pd.DataFrame:
    p = cfg["profile"]
    a = cfg["assets"]
    gdb = cfg["paths"]["analysis_gdb"]
    rps = p["return_periods"]
    cul = read_culverts(cfg, log)
    # On a rerun the layer already carries the profile fields from the last apply. Drop them so
    # the stage recomputes from the raw inventory and the merges below do not collide
    # (pandas would suffix cond_class, crossing_id, ... with _x / _y).
    stale = [f[0] for f in profile_fields(cfg) if f[0] in cul.columns]
    if stale:
        cul = cul.drop(columns=stale)
        log.info(f"Dropped {len(stale)} profile field(s) already on the layer; recomputing")
    cond = read_layer(gdb, a["condition_table"], geometry=False)
    log.info(f"Read {len(cond)} condition records")

    # geometry-derived descriptors
    span = pd.to_numeric(cul["span_in"], errors="coerce")
    rise = pd.to_numeric(cul["rise_in"], errors="coerce")
    span = span.where((span > 0) & (span <= p["max_span_in"] * 4))
    rise = rise.where(rise > 0)
    circ = cul["xsection_shape"].isna() | cul["xsection_shape"].astype(str).str.lower().str.contains("circ|pipe|round|code 1|none", regex=True)
    span = span.where(~(circ & (span > p["max_span_in"])))
    cul["span_in"], cul["rise_in"] = span, rise
    cul["d_eq_in"] = np.where(rise.notna() & (rise != span), np.sqrt(4 * span * rise / math.pi), span).round(1)
    cul["size_class"] = cul["d_eq_in"].map(lambda d: _size_class(d, p["size_breaks_in"]))
    cul["material_class"] = cul["material"].map(_material_class)
    cul["dem_vintage_flag"] = (pd.to_numeric(cul["install_year"], errors="coerce") >= p["dem_vintage_year"]).astype(int)

    # large culverts (NBI culvert-type structures) within large_culvert_m
    try:
        br = read_layer(gdb, a["bridges_fc"]).to_crs(cul.crs)
        big = br[br["is_culvert_type"] == 1][["bridge_id", "geometry"]]
        near = gpd.sjoin_nearest(cul[["culvert_id", "geometry"]], big, how="left",
                                 max_distance=p["large_culvert_m"], distance_col="d")
        near = near[~near.index.duplicated(keep="first")]
        cul["large_culvert_id"] = near["bridge_id"].values
        log.info(f"{int(cul['large_culvert_id'].notna().sum())} culverts within {p['large_culvert_m']} m of an NBI culvert-type structure")
    except Exception as e:  # bridges layer not built yet
        log.warning(f"Bridges layer not read ({e}); large_culvert_id left null")
        cul["large_culvert_id"] = None

    # condition
    cc = harmonize_condition(cond, cfg, log)
    cul = cul.merge(cc, left_on="culvert_id", right_index=True, how="left")
    cul["cond_class"] = cul["cond_class"].fillna(1).astype(int)
    cul["cond_source"] = cul["cond_source"].fillna("default")
    cul["cond_stale"] = cul["cond_stale"].fillna(0).astype(int)

    # crossings (from the delineate stage) and hydrology
    have_xing = False
    try:
        xt = read_layer(gdb, CROSSING_TABLE, geometry=False)
        link = pd.concat([pd.read_csv(f) for f in [
            REPO / cfg["paths"]["outputs"] / "culvert_crossing_link.csv",
            Path(cfg["ndot"]["work_dir"]) / "culvert_crossing_link_all.csv"] if f.exists()]).drop_duplicates("culvert_id")
        have_xing = True
        log.info(f"Read {len(xt)} crossings and {len(link)} culvert links")
    except Exception as e:
        log.warning(f"Crossing table not available ({e}); hydrology fields will be null")
    xcols = ["contrib_area_ac", "basin_slope_pct", "basin_landcover", "runoff_c", "pp_elev_ft", "relief_ft",
             "flow_len_ft", "basin_elev_mean_ft", "basin_precip_in"]
    if have_xing:
        for c in ("basin_elev_mean_ft", "basin_precip_in"):  # crossing tables from before Oct. 9 lack these
            if c not in xt.columns:
                xt[c] = np.nan
        cul = cul.merge(link[["culvert_id", "crossing_id", "barrels", "snap_dist_m"]], on="culvert_id", how="left")
        cul = cul.merge(xt[["crossing_id"] + xcols], on="crossing_id", how="left")
    else:
        for c in ["crossing_id", "barrels", "snap_dist_m"] + xcols:
            cul[c] = np.nan
    cul["runoff_c"] = cul["runoff_c"].fillna(p["runoff_c"]["default"])
    cul["tailwater_flag"] = (cul["pp_elev_ft"] < p["tailwater_ft"]).astype(int)

    # capacity per barrel, summed per crossing
    caps = cul.apply(lambda r: capacity(r, p), axis=1, result_type="expand")
    cul["q_cap_cfs"], cul["q_full_cfs"] = caps[0], caps[1]
    cul["q_cap_crossing_cfs"] = cul.groupby("crossing_id")["q_cap_cfs"].transform("sum").where(cul["crossing_id"].notna(), cul["q_cap_cfs"])
    cul.loc[cul["q_cap_cfs"].isna() & (cul["barrels"].fillna(1) == 1), "q_cap_crossing_cfs"] = np.nan

    # event flow: rational method on Atlas 14 at Kirpich tc, nearest PFDS point
    ddf, ddf_pts = load_ddf(cfg, log)
    nearest = gpd.sjoin_nearest(cul[["culvert_id", "geometry"]], ddf_pts[["point", "geometry"]], how="left")
    nearest = nearest[~nearest.index.duplicated(keep="first")]
    cul["ddf_point"] = nearest["point"].values
    L, H = cul["flow_len_ft"], cul["relief_ft"]
    s_basin = (H / L).where(L > 0)
    tc = (0.0078 * L ** 0.77 * s_basin.clip(lower=0.005) ** -0.385).clip(p["tc_min_minutes"], p["tc_max_minutes"])
    cul["tc_min"] = tc.round(1)
    sqmi = cul["contrib_area_ac"] * SQM_PER_ACRE / SQM_PER_SQMI
    # Basins over rational_max_sqmi use the USGS regional regression for their state: the
    # California side of the basin is in the Lahontan region of Gotvald and others (2012),
    # the Nevada side in region 1 of Thomas and others (1997). Both need mean annual
    # precipitation; without PRISM those rows stay "regression_needed".
    state = culvert_state(cul, p["regression"])
    # regression.nv_uses = "CA" applies the Lahontan equation basin-wide (one hydrologic unit
    # on the Sierra east slope); "NV" keeps Thomas 1997 region 1 for Nevada-side culverts.
    eq_state = state.replace({"NV": p["regression"].get("nv_uses", "NV")})
    big = cul["contrib_area_ac"].notna() & (sqmi > p["rational_max_sqmi"])
    can_reg = big & cul["basin_precip_in"].notna() & state.notna()
    cul["q_method"] = np.where(cul["contrib_area_ac"].isna(), "none",
                               np.where(~big, "rational",
                                        np.where(can_reg, "regression_" + eq_state.fillna("").astype(str), "regression_needed")))
    cul["q_region"] = np.where(can_reg, eq_state.map({"CA": "CA Lahontan (Gotvald 2012)", "NV": "NV region 1 (Thomas 1997)"}), None)
    for rp in rps:
        i = [intensity_in_hr(ddf, pt, rp, t) if (pd.notna(t) and isinstance(pt, str)) else None
             for pt, t in zip(cul["ddf_point"], cul["tc_min"])]
        q_rat = cul["runoff_c"] * pd.Series(i, index=cul.index, dtype="float") * cul["contrib_area_ac"]
        q_reg = regression_q(sqmi, cul["basin_precip_in"], eq_state, rp)
        q = q_rat.where(cul["q_method"] == "rational", q_reg.where(can_reg))
        cul[f"q_event_{rp}_cfs"] = q.round(1)
        cul[f"load_ratio_{rp}"] = (cul[f"q_event_{rp}_cfs"] / cul["q_cap_crossing_cfs"]).round(2)
    n_reg = int(can_reg.sum())
    log.info(f"Event flow: rational on {int((cul['q_method'] == 'rational').sum())} culverts; regression on {n_reg} "
             f"(CA {int((state[can_reg] == 'CA').sum())}, NV {int((state[can_reg] == 'NV').sum())}); "
             f"regression_needed (no precipitation or state): {int((cul['q_method'] == 'regression_needed').sum())}")
    if n_reg:
        # The two state equations come from different regionalizations (Sierra east slope vs
        # the arid Southwest); log how far apart they sit on the same basins so the method
        # note can say so.
        hl = p["headline_rp"]
        both = can_reg & (sqmi > 0)
        q_ca = regression_q(sqmi, cul["basin_precip_in"], pd.Series("CA", index=cul.index), hl)
        q_nv = regression_q(sqmi, cul["basin_precip_in"], pd.Series("NV", index=cul.index), hl)
        ratio = (q_nv / q_ca)[both]
        log.info(f"Cross-check on the {int(both.sum())} regression basins: NV region 1 / CA Lahontan Q{hl} "
                 f"median {ratio.median():.2f} (10th {ratio.quantile(.1):.2f}, 90th {ratio.quantile(.9):.2f})")
        rng = p["regression"]["applicability"]
        out_a = can_reg & ((sqmi < rng["area_sqmi"][0]) | (sqmi > rng["area_sqmi"][1]))
        out_p = can_reg & ((cul["basin_precip_in"] < rng["precip_in"][0]) | (cul["basin_precip_in"] > rng["precip_in"][1]))
        if out_a.any() or out_p.any():
            log.warning(f"Regression applied outside the published ranges: area {int(out_a.sum())}, "
                        f"precipitation {int(out_p.sum())} culverts (table 9 / table 3 of the source reports)")

    # scoring set and completeness
    cul["scored"] = ((cul["feature_type"] == "culvert") & cul["parent_segment_id"].notna()
                     & cul["large_culvert_id"].isna()).astype(int)
    size_ok, hyd_ok, cond_ok = cul["d_eq_in"].notna(), cul["contrib_area_ac"].notna(), cul["cond_source"] != "default"
    cul["profile_completeness"] = np.where(size_ok & hyd_ok & cond_ok, "full",
                                           np.where(size_ok | hyd_ok | cond_ok, "partial", "default"))
    cul["profile_date"] = pd.Timestamp.today().normalize()
    hl = p["headline_rp"]
    log.info(f"Scored set: {int(cul['scored'].sum())} of {len(cul)}; completeness:\n"
             + cul.loc[cul["scored"] == 1, "profile_completeness"].value_counts().to_string())
    if have_xing:
        log.info(f"Loading ratio ({hl}-yr) quantiles, scored culverts:\n"
                 + cul.loc[cul["scored"] == 1, f"load_ratio_{hl}"].quantile([.1, .5, .9]).round(2).to_string())

    fields = profile_fields(cfg)
    cols = ["culvert_id", "jurisdiction"] + [f[0] for f in fields]
    prof = pd.DataFrame(cul.drop(columns="geometry"))[cols]
    write_split_csv(prof, "culvert_profile", cfg, log)
    if dry_run:
        log.info("Dry run: geodatabase not written")
        return prof

    import arcpy
    tbl = f"{gdb}\\{PROFILE_TABLE}"
    if arcpy.Exists(tbl):
        arcpy.management.Delete(tbl)
    write_table(prof, [("culvert_id", "TEXT", 160), ("jurisdiction", "TEXT", 60)] + fields, gdb, PROFILE_TABLE, log,
                date_cols={"cond_date", "profile_date"})
    arcpy.management.AddIndex(tbl, ["culvert_id"], "prof_culvert_id_idx", "UNIQUE")
    if apply:
        fc = f"{gdb}\\{a['culverts_fc']}"
        ensure_fields(fc, fields, log)
        apply_by_key(fc, prof, "culvert_id", fields, log, date_cols={"cond_date", "profile_date"})
    return prof


# ----------------------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=["terrain", "delineate", "attributes", "all"], default="attributes")
    ap.add_argument("--overwrite", action="store_true", help="rebuild terrain rasters / crossing outputs")
    ap.add_argument("--dry-run", action="store_true", help="attributes: CSV only, no geodatabase write")
    ap.add_argument("--no-apply", action="store_true", help="attributes: write CulvertProfile but do not update Culverts")
    args = ap.parse_args()

    log = get_logger("culvert_profile")
    cfg = load_cfg()
    if args.stage in ("terrain", "all"):
        stage_terrain(cfg, log, args.overwrite)
    if args.stage in ("delineate", "all"):
        stage_delineate(cfg, log, args.overwrite)
    if args.stage in ("attributes", "all"):
        stage_attributes(cfg, log, args.dry_run, apply=not args.no_apply)


if __name__ == "__main__":
    main()
