"""Debris-flow and avalanche surfaces for score_exposure.py (docs/SCORING_RUBRICS.md 4 and 5).

Debris flow, option 1 as revised by decision 33 (config exposure.debris_flow): from the 2 m
terrain rasters of the culvert delineation (profile.work_gdb: fdir, facc, slope_pct),
    E1  mean slope of the upslope contributing area at each cell (slope-weighted flow
        accumulation over flow accumulation), aggregated to 30 m by mean, on the draft's
        half-point breaks (over 30 percent = 3 ... 0 to 5 = 0); cells draining more than
        area_gate_sqmi score 0 when e1_mask_over_gate is set (decision 34), so a road crossing
        a large river reads the hillslope beside it, not the river's basin-wide mean
    E3  TRPA most-likely fire severity (the wildfire E2 surface) standing in for the contracted
        predicted soil burn severity: High 3, Moderate 2, Low 1, outside 0
Weights 0.40 / 0.60. The draft's E2, contributing area (flow accumulation, 30 m by maximum, on
its breaks: under 0.25 sq mi = 3 ... over 5 sq mi = 0), is still built as Hazard_DebrisFlow_Area
but is a gate, not a score: culverts and bridges over exposure.debris_flow.area_gate_sqmi score
exposure 0. Culverts read E1 from their own profile (basin_slope_pct) and E3 as the highest
severity class covering e3_min_share of the watershed; roads read E1 touching the segment and E3
by share within 300 ft; bridges read E1 within 25 m and E3 by share within 300 ft.

Avalanche x roads (config exposure.avalanche): one lookup of the dominant slope tier on the
uphill side within 1,000 ft of the segment (10 m DEM, 20 m elevation bands; decision 17) and a
record within 1,000 ft, where the record is a TRPA Avalanche_Zones polygon (decision 18; the
accident databases are not used). Tiers: under 25 degrees 0; 25 to under 30 or over 50 1; 30
to under 35 or over 45 to 50 2; 35 to 45 3. Scores: no record 0 / 1 / 1.5 / 2, record 1 / 2 /
2.5 / 3 (the draft's table plus decision 20 for record and under 25 degrees).
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from va_common import fetch_basin, fetch_rest_features, target_crs

SQM_PER_SQMI = 2_589_988.11
FT = 0.3048


# ----------------------------------------------------------------------------------------
# pure helpers

def df_slope_score(pct) -> float | None:
    """DF E1 (option 1): mean basin slope in percent on the draft's breaks."""
    if pct is None or (isinstance(pct, float) and np.isnan(pct)):
        return None
    s = float(pct)
    for hi, v in ((5, 0.0), (10, 0.5), (15, 1.0), (20, 1.5), (25, 2.0), (30, 2.5)):
        if s <= hi:
            return v
    return 3.0


def df_area_score(sqmi) -> float | None:
    """The draft's DF E2 classes for contributing area in square miles, smaller scores higher.
    Map only since decision 33: it classes Hazard_DebrisFlow_Area; the area is a gate, not a score."""
    if sqmi is None or (isinstance(sqmi, float) and np.isnan(sqmi)):
        return None
    a = float(sqmi)
    if a < 0.25:
        return 3.0
    if a <= 0.5:
        return 2.5
    if a <= 1:
        return 2.0
    if a <= 2:
        return 1.5
    if a <= 3:
        return 1.0
    if a <= 5:
        return 0.5
    return 0.0


def av_tier(slope_deg) -> int | None:
    if slope_deg is None or (isinstance(slope_deg, float) and np.isnan(slope_deg)):
        return None
    s = float(slope_deg)
    if s < 25:
        return 0
    if s < 30 or s > 50:
        return 1
    if s < 35 or s > 45:
        return 2
    return 3


AV_SCORE = {False: {0: 0.0, 1: 1.0, 2: 1.5, 3: 2.0}, True: {0: 1.0, 1: 2.0, 2: 2.5, 3: 3.0}}


def av_score(tier: int | None, record: bool) -> float:
    return AV_SCORE[bool(record)][0 if tier is None else int(tier)]


def dominant_tier(areas: dict) -> int | None:
    """Tier covering the largest area (ties to the higher tier); None when nothing uphill."""
    if not areas or sum(areas.values()) <= 0:
        return None
    best = max(areas.values())
    return max(t for t, a in areas.items() if a == best)


# ----------------------------------------------------------------------------------------
# raster helpers (arcpy)

def _poly_from_int_raster(raster, scratch_gdb: str, name: str, crs, log, field: str = "gridcode") -> gpd.GeoDataFrame:
    import arcpy
    import pyogrio
    poly = f"{scratch_gdb}\\{name}"
    arcpy.conversion.RasterToPolygon(raster, poly, "NO_SIMPLIFY", "VALUE")
    g = pyogrio.read_dataframe(scratch_gdb, layer=name).to_crs(crs)
    return g.rename(columns={"gridcode": field})


def max_area_sqmi_near(cfg: dict, pts: gpd.GeoDataFrame, buffer_m: float) -> pd.Series:
    """Largest contributing area (sq mi) within buffer_m of each point, from the 2 m flow
    accumulation of the culvert delineation (profile.work_gdb facc), one small windowed read per
    point. The bridge gate (decision 33): culverts carry their own contrib_area_ac, bridges do
    not, and Hazard_DebrisFlow_Area drops ground over 5 sq mi, so it cannot see a big river.
    NaN where no cell has data. Index = pts.index."""
    import arcpy
    R = arcpy.Raster(f"{cfg['profile']['work_gdb']}\\facc")
    cs, ext, sr = float(R.meanCellWidth), R.extent, R.spatialReference
    pts = pts.to_crs(sr.factoryCode or sr.exportToString())
    n = int(np.ceil(2 * buffer_m / cs)) + 2
    out = []
    for x, y in zip(pts.geometry.x, pts.geometry.y):
        c0 = int(np.floor((x - buffer_m - ext.XMin) / cs))
        r0 = int(np.floor((ext.YMax - (y + buffer_m)) / cs))
        a = arcpy.RasterToNumPyArray(R, arcpy.Point(ext.XMin + c0 * cs, ext.YMax - (r0 + n) * cs), n, n, nodata_to_value=-1)
        xs = ext.XMin + (c0 + np.arange(a.shape[1]) + 0.5) * cs
        ys = ext.YMax - (r0 + np.arange(a.shape[0]) + 0.5) * cs
        m = (np.hypot(xs[None, :] - x, ys[:, None] - y) <= buffer_m) & (a >= 0)
        out.append(float((a[m].max() + 1) * cs * cs / SQM_PER_SQMI) if m.any() else np.nan)
    return pd.Series(out, index=pts.index)


def build_debris_flow_surface(cfg: dict, log, overwrite: bool) -> dict:
    """The slope and drainage-area surfaces in the hazards geodatabase (Hazard_DebrisFlow_Slope,
    _Area), with the wildfire severity fc reused as E3. Returns the scored indicators (E1, E3)
    with sampling hints; the area surface is map context for the gate, not an indicator."""
    import arcpy
    import pyogrio
    from arcpy import sa
    from score_exposure import dissolve_classes, ensure_gdb, write_class_fc
    ex = cfg["exposure"]
    df = ex["debris_flow"]
    crs = target_crs(cfg)
    gdb = ex["hazards_gdb"]
    ensure_gdb(gdb, log)
    w = df["weights"]
    sev_fc = ex["wildfire"]["e2_fc"]
    if not arcpy.Exists(f"{gdb}\\{sev_fc}"):
        raise SystemExit(f"{sev_fc} (the wildfire E2 surface) is the burn-severity stand-in; build wildfire first")
    hints = {"e1": "profile:slope", "e3": "watershed"}
    if arcpy.Exists(f"{gdb}\\{df['slope_fc']}") and arcpy.Exists(f"{gdb}\\{df['area_fc']}") and not overwrite:
        log.info(f"{df['slope_fc']} and {df['area_fc']} exist; reading them (use --build to rebuild)")
        return {"e1": (float(w["e1"]), pyogrio.read_dataframe(gdb, layer=df["slope_fc"]).to_crs(crs), hints["e1"]),
                "e3": (float(w["e3"]), pyogrio.read_dataframe(gdb, layer=sev_fc).to_crs(crs), hints["e3"])}

    work = cfg["profile"]["work_gdb"]
    for r in ("fdir", "facc", "slope_pct"):
        if not arcpy.Exists(f"{work}\\{r}"):
            raise SystemExit(f"{work}\\{r} missing: run culvert_profile.py --stage terrain first")
    arcpy.CheckOutExtension("Spatial")
    arcpy.env.overwriteOutput = True
    arcpy.env.parallelProcessingFactor = cfg["profile"].get("parallel", "75%")
    fdir = sa.Raster(f"{work}\\fdir")
    facc = sa.Raster(f"{work}\\facc")
    slope = sa.Raster(f"{work}\\slope_pct")
    cell = float(arcpy.Describe(facc).meanCellWidth)
    arcpy.env.snapRaster = facc
    arcpy.env.extent = facc
    arcpy.env.cellSize = facc
    agg = int(round(float(df.get("cell_m", 30)) / cell))
    out_cell = cell * agg

    # E1: mean slope of the upslope area = (slope-weighted accumulation + own slope) / (facc + 1)
    p_wacc = f"{work}\\slope_wacc"
    if not arcpy.Exists(p_wacc):
        log.info("Slope-weighted flow accumulation (2 m) ...")
        sa.FlowAccumulation(fdir, slope, "FLOAT", "D8").save(p_wacc)
    else:
        log.info(f"Reusing {p_wacc} (the 2 m terrain has not changed; delete it to recompute after a terrain rerun)")
    wacc = sa.Raster(p_wacc)
    mean_up = (wacc + slope) / (facc + 1)
    log.info(f"Aggregating to {out_cell:g} m (mean upslope slope by MEAN, accumulation by MAXIMUM) ...")
    mean_up30 = sa.Aggregate(mean_up, agg, "MEAN", "EXPAND", "DATA")
    facc30 = sa.Aggregate(facc, agg, "MAXIMUM", "EXPAND", "DATA")
    area_sqmi = (facc30 + 1) * cell * cell / SQM_PER_SQMI
    # half-point scores x 10 as integers
    s = mean_up30
    a = area_sqmi
    e1 = sa.Con(s > 30, 30, sa.Con(s > 25, 25, sa.Con(s > 20, 20, sa.Con(s > 15, 15, sa.Con(s > 10, 10, sa.Con(s > 5, 5, 0))))))
    gate_sqmi = float(df.get("area_gate_sqmi", 0) or 0)
    if df.get("e1_mask_over_gate") and gate_sqmi > 0:
        # decision 34: on a channel cell the mean upslope slope is the whole basin's mean, so a road crossing a
        # large river read E1 from the river; cells draining more than the gate score 0 and the road reads the
        # hillslope cells beside it
        e1 = sa.Con(a > gate_sqmi, 0, e1)
        log.info(f"E1 masked to 0 where the 30 m contributing area is over {gate_sqmi:g} sq mi (e1_mask_over_gate)")
    e2 = sa.Con(a < 0.25, 30, sa.Con(a <= 0.5, 25, sa.Con(a <= 1, 20, sa.Con(a <= 2, 15, sa.Con(a <= 3, 10, sa.Con(a <= 5, 5, 0))))))
    e1_path, e2_path = f"{gdb}\\df_e1_cls", f"{gdb}\\df_e2_cls"
    sa.Int(e1).save(e1_path)
    sa.Int(e2).save(e2_path)
    out = {}
    for key, path, fc, label in (("e1", e1_path, df["slope_fc"], "mean upslope slope"), ("e2", e2_path, df["area_fc"], "contributing area")):
        g = _poly_from_int_raster(path, gdb, f"df_{key}_poly", crs, log)
        g["hz_class"] = g["gridcode"].astype(float) / 10.0
        g = dissolve_classes(g[["hz_class", "geometry"]], crs)
        log.info(f"DF {key} ({label}), area by score (km2):\n"
                 + (g.groupby("hz_class").geometry.apply(lambda x: x.area.sum() / 1e6)).round(1).to_string())
        write_class_fc(g, gdb, fc, "debris_flow", {}, cfg, log)
        if key in w:
            out[key] = (float(w[key]), g, hints[key])
    sev = pyogrio.read_dataframe(gdb, layer=sev_fc).to_crs(crs)
    out["e3"] = (float(w["e3"]), sev, hints["e3"])
    log.info("E3 is the TRPA most-likely fire severity surface standing in for predicted soil burn severity (DF_option stand-in)")
    arcpy.CheckInExtension("Spatial")
    return out


def build_avalanche_products(cfg: dict, log, overwrite: bool) -> dict:
    """Hazard_Avalanche_Cells (10 m slope tier x 20 m elevation band polygons) and the TRPA
    avalanche zones. Returns {"cells": gdf(tier, band), "zones": gdf}."""
    import arcpy
    import pyogrio
    from arcpy import sa
    from score_exposure import ensure_gdb
    ex = cfg["exposure"]
    av = ex["avalanche"]
    crs = target_crs(cfg)
    gdb = ex["hazards_gdb"]
    ensure_gdb(gdb, log)
    fc = av["cells_fc"]
    zones = fetch_rest_features(av["zones_layer"], crs, log)
    if arcpy.Exists(f"{gdb}\\{fc}") and not overwrite:
        log.info(f"{fc} exists; reading it (use --build to rebuild)")
        return {"cells": pyogrio.read_dataframe(gdb, layer=fc).to_crs(crs), "zones": zones}
    dem_src = cfg["paths"]["dem"]
    arcpy.CheckOutExtension("Spatial")
    arcpy.env.overwriteOutput = True
    arcpy.env.parallelProcessingFactor = cfg["profile"].get("parallel", "75%")
    dem = sa.Raster(dem_src)
    cell = float(arcpy.Describe(dem_src).meanCellWidth)
    agg = int(round(float(av.get("cell_m", 10)) / cell))
    log.info(f"Aggregating the DEM to {cell * agg:g} m by MEAN ...")
    dem10 = sa.Aggregate(dem, agg, "MEAN", "EXPAND", "DATA") if agg > 1 else dem
    slope_deg = sa.Slope(dem10, "DEGREE")
    s = slope_deg
    tier = sa.Con(s < 25, 0, sa.Con((s < 30) | (s > 50), 1, sa.Con((s < 35) | (s > 45), 2, 3)))
    band_m = float(av.get("band_m", 20))
    band = sa.Int(dem10 / band_m)
    code = sa.Int(tier * 1000 + band)
    code_path = f"{gdb}\\av_code"
    code.save(code_path)
    g = _poly_from_int_raster(code_path, gdb, "av_code_poly", crs, log)
    g["tier"] = (g["gridcode"] // 1000).astype(int)
    g["band_m"] = (g["gridcode"] % 1000).astype(int) * band_m
    g = g[["tier", "band_m", "geometry"]]
    log.info(f"{len(g)} slope-tier x elevation-band polygons; tier area (km2):\n"
             + (g.groupby("tier").geometry.apply(lambda x: x.area.sum() / 1e6)).round(1).to_string())
    sr = arcpy.SpatialReference(int(cfg["output"]["target_epsg"]))
    out_fc = f"{gdb}\\{fc}"
    if arcpy.Exists(out_fc):
        arcpy.management.Delete(out_fc)
    arcpy.management.CreateFeatureclass(gdb, fc, "POLYGON", spatial_reference=sr)
    arcpy.management.AddFields(out_fc, [["tier", "SHORT", "tier", ""], ["band_m", "DOUBLE", "band_m", ""]])
    with arcpy.da.InsertCursor(out_fc, ["SHAPE@", "tier", "band_m"]) as cur:
        for r in g.itertuples():
            cur.insertRow([arcpy.FromWKB(r.geometry.wkb), int(r.tier), float(r.band_m)])
    log.info(f"-> {out_fc}")
    arcpy.CheckInExtension("Spatial")
    return {"cells": g, "zones": zones}


def score_avalanche_lines(lines: gpd.GeoDataFrame, key: str, products: dict, cfg: dict, log) -> pd.DataFrame:
    """AV-R per segment: dominant uphill slope tier within 1,000 ft (cells whose elevation
    band is above the band at the segment midpoint) and a zone record within 1,000 ft."""
    av = cfg["exposure"]["avalanche"]
    dist = float(av.get("buffer_ft", 1000)) * FT
    cells, zones = products["cells"], products["zones"]
    mid = gpd.GeoDataFrame({key: lines[key].values}, geometry=lines.geometry.interpolate(0.5, normalized=True).values, crs=lines.crs)
    road_band = gpd.sjoin(mid, cells[["band_m", "geometry"]], how="left", predicate="within").groupby(key)["band_m"].min()
    buf = gpd.GeoDataFrame({key: lines[key].values}, geometry=lines.geometry.buffer(dist).values, crs=lines.crs)
    buf["road_band"] = buf[key].map(road_band)
    log.info(f"Overlaying {len(buf)} buffers ({dist:.0f} m) with {len(cells)} tier x band cells ...")
    cut = gpd.overlay(buf, cells[["tier", "band_m", "geometry"]], how="intersection", keep_geom_type=True)
    cut = cut[cut["band_m"] > cut["road_band"]]  # uphill side: at least one band above the road
    cut["a"] = cut.geometry.area
    areas = cut.groupby([key, "tier"])["a"].sum().unstack(fill_value=0.0)
    rec = gpd.sjoin(buf[[key, "geometry"]], zones[["geometry"]], how="inner", predicate="intersects")[key].unique()
    record = pd.Series(False, index=lines[key].values)
    record.loc[record.index.isin(rec)] = True
    tiers, scores, up_ha = [], [], []
    for k in lines[key].values:
        a = areas.loc[k].to_dict() if k in areas.index else {}
        t = dominant_tier({int(t): float(v) for t, v in a.items()})
        tiers.append(t)
        scores.append(av_score(t, bool(record.loc[k])))
        up_ha.append(round(sum(a.values()) / 1e4, 1))
    out = pd.DataFrame({key: lines[key].values, "E_hist": scores, "av_tier": tiers, "av_record": record.values.astype(int),
                        "uphill_ha": up_ha, "seg_len_m": lines.geometry.length.round(1).values})
    log.info(f"AV E_hist on {len(out)} segments; records within {dist:.0f} m: {int(record.sum())}:\n"
             + out["E_hist"].value_counts().sort_index().to_string())
    return out
