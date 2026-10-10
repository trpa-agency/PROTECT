"""Exposure scores (E_<pair>_hist, 0 to 3) from classed hazard surfaces, per docs/SCORING_RUBRICS.md.

Two jobs, both config-driven (config.yaml `exposure:`):

  1. Build the classed hazard surface in the hazards geodatabase (exposure.hazards_gdb), so
     every pair in both lanes samples the same classes. Flood today: the FEMA flood zones and
     the mapped streams classed on the FL-C E1 values (1 percent zone 3, 0.2 percent zone or a
     mapped stream 2, NHD flowline outside a zone 1 when a flowline layer is configured,
     otherwise 0). Wildfire (decision 22): two indicator surfaces, E1 the burn probability
     raster classed on the draft's breaks (over 1 percent 3, over 0.5 to 1 percent 2, over 0 to
     0.5 percent 1) and E2 the TRPA most-likely fire severity polygons (Low 1, Moderate 2,
     High 3; the contracted flame-length raster replaces it on 4 and 8 ft breaks when set),
     combined per asset as 0.70 E1 + 0.30 E2 after each is sampled as the maximum within
     300 ft. Landslide, debris flow, and avalanche plug in the same way.
  2. Sample it per asset on the rubric's sampling rule (section 1.7) and write the scores:
       culverts   maximum over the contributing watershed (CulvertWatersheds_inc aggregated up
                  the drainage tree from CulvertCrossings), 25 m buffer where no watershed;
                  FL-C tailwater modifier +1 (cap 3) where tailwater_flag is set
       bridges    maximum within 25 m; FL-B combines E1 waterway adequacy (NBI item 71) at
                  0.20 with E2 the flood class at 0.10, weight-normalized to 0 to 3
       roads      maximum class touching the segment, plus the share of length in each class
       active transport   maximum within the hazard's sampling distance of the line (Transportation
                          service, existing facilities), plus length shares; table Exposure_<hazard>_active_transport
       transit centers    maximum within the sampling distance (exposure.transit_centers_layer; blank = skipped)

Usage (arcgispro-py3; runs on the server):
    python scripts/score_exposure.py --hazard flood --build                 # classed surface only
    python scripts/score_exposure.py --hazard flood --assets culverts bridges roads
    python scripts/score_exposure.py --hazard flood --assets culverts --dry-run   # CSV only
    python scripts/score_exposure.py --hazard flood --assets culverts bridges roads --overwrite
    python scripts/score_exposure.py --hazard wildfire --build
    python scripts/score_exposure.py --hazard wildfire --assets roads active_transport --overwrite

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

from va_common import (REPO, fetch_basin, fetch_rest_features, field_types, get_logger, load_cfg, read_streets, target_crs,
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


def burn_prob_class(value_pct, breaks=(0.5, 1.0)) -> int:
    """WF E1 class from annual burn probability in percent, the draft's breaks: over breaks[1]
    = 3, over breaks[0] = 2, over 0 = 1, 0 or no data = 0."""
    if value_pct is None or (isinstance(value_pct, float) and np.isnan(value_pct)) or value_pct <= 0:
        return 0
    if value_pct > breaks[1]:
        return 3
    if value_pct > breaks[0]:
        return 2
    return 1


def weighted_exposure(parts: dict, weights: dict) -> float:
    """Indicator scores combined by their weights and normalized by the weights present, so a
    missing indicator does not pull the score down (0 to 3)."""
    w = sum(float(weights[k]) for k in parts)
    return sum(float(weights[k]) * float(parts[k]) for k in parts) / w if w else 0.0


def indicators(surf) -> list:
    """A builder returns one classed surface (single indicator at weight 1) or a dict of
    indicator name -> (weight, surface). Normalize to [(name, weight, surface), ...]."""
    if isinstance(surf, dict):
        return [(k, float(w), g) for k, (w, g) in surf.items()]
    return [("e1", 1.0, surf)]


def fetch_with_fields(url: str, fields: list, crs, log, where: str = "1=1", page: int = 1000) -> gpd.GeoDataFrame:
    """Paged REST query keeping the named attribute fields (va_common.fetch_rest_features keeps
    OBJECTID only)."""
    import requests
    frames, offset = [], 0
    while True:
        r = requests.get(f"{url}/query", params={"where": where, "outFields": ",".join(fields), "returnGeometry": "true",
                                                 "f": "geojson", "resultOffset": offset, "resultRecordCount": page},
                         timeout=300)
        r.raise_for_status()
        feats = r.json().get("features", [])
        if not feats:
            break
        frames.append(gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326"))
        offset += len(feats)
        if len(feats) < page:
            break
    out = pd.concat(frames, ignore_index=True) if frames else gpd.GeoDataFrame(columns=fields, geometry=[], crs="EPSG:4326")
    out = gpd.GeoDataFrame(out, geometry="geometry", crs="EPSG:4326").to_crs(crs)
    log.info(f"{len(out)} features from {url}")
    return out


# ----------------------------------------------------------------------------------------
# classed surfaces

def ensure_gdb(gdb: str, log) -> None:
    import arcpy
    if not arcpy.Exists(gdb):
        arcpy.management.CreateFileGDB(str(Path(gdb).parent), Path(gdb).name)
        log.info(f"Created {gdb}")


def write_class_fc(surf: gpd.GeoDataFrame, gdb: str, name: str, hazard: str, labels: dict, cfg: dict, log) -> None:
    """Write a classed polygon surface (hz_class, hazard, label) to the hazards geodatabase."""
    import arcpy
    out_fc = f"{gdb}\\{name}"
    sr = arcpy.SpatialReference(int(cfg["output"]["target_epsg"]))
    if arcpy.Exists(out_fc):
        arcpy.management.Delete(out_fc)
    arcpy.management.CreateFeatureclass(gdb, name, "POLYGON", spatial_reference=sr)
    arcpy.management.AddFields(out_fc, [["hz_class", "SHORT", "hz_class", ""], ["hazard", "TEXT", "hazard", 20],
                                        ["label", "TEXT", "label", 80]])
    with arcpy.da.InsertCursor(out_fc, ["SHAPE@", "hz_class", "hazard", "label"]) as cur:
        for r in surf.itertuples():
            cur.insertRow([arcpy.FromWKB(r.geometry.wkb), int(r.hz_class), hazard, labels.get(int(r.hz_class), "")])
    log.info(f"{len(surf)} polygons -> {out_fc}")


def dissolve_classes(allp: gpd.GeoDataFrame, crs) -> gpd.GeoDataFrame:
    """Dissolve by hz_class, higher class winning where classes overlap, exploded to parts."""
    allp = allp[allp["hz_class"] > 0]
    dissolved = allp.dissolve(by="hz_class", as_index=False)[["hz_class", "geometry"]]
    geoms = {int(r.hz_class): r.geometry for r in dissolved.itertuples()}
    for c in sorted(geoms):
        for higher in [h for h in geoms if h > c]:
            geoms[c] = geoms[c].difference(geoms[higher])
    surf = gpd.GeoDataFrame({"hz_class": list(geoms)}, geometry=[geoms[c] for c in geoms], crs=crs)
    return surf[~surf.geometry.is_empty].explode(index_parts=False).reset_index(drop=True)


def raster_to_classes(raster: str, breaks: list, units: str, cfg: dict, log, scratch_gdb: str, name: str) -> gpd.GeoDataFrame:
    """Reclassify a continuous raster to 0 to 3 on two upper breaks (class 1 over 0, class 2
    over breaks[0], class 3 over breaks[1]) inside the basin's bounding box, and return the
    class polygons (hz_class) in the target CRS."""
    import arcpy
    import pyogrio
    from arcpy.sa import Con, Raster
    arcpy.CheckOutExtension("Spatial")
    arcpy.env.overwriteOutput = True
    crs = target_crs(cfg)
    basin = fetch_basin(cfg, log)
    sr = arcpy.Describe(raster).spatialReference
    b = basin.to_crs(f"EPSG:{sr.factoryCode}" if sr.factoryCode else sr.exportToString()).total_bounds
    pad = 500.0
    clip = f"{scratch_gdb}\\{name}_clip"
    arcpy.management.Clip(raster, f"{b[0] - pad} {b[1] - pad} {b[2] + pad} {b[3] + pad}", clip,
                          clipping_geometry="NONE", maintain_clipping_extent="NO_MAINTAIN_EXTENT")
    r = Raster(clip)
    vmax = float(arcpy.management.GetRasterProperties(clip, "MAXIMUM").getOutput(0))
    scale = 1.0
    if units == "auto":
        units = "fraction" if vmax <= 1.0 else "percent"
        log.info(f"{Path(raster).name}: maximum {vmax:g} inside the basin box; read as {units}")
    if units == "fraction":
        scale = 100.0
    b1, b2 = float(breaks[0]) / scale, float(breaks[1]) / scale
    cls = Con(r > b2, 3, Con(r > b1, 2, Con(r > 0, 1, 0)))
    cls_path = f"{scratch_gdb}\\{name}_cls"
    cls.save(cls_path)
    poly = f"{scratch_gdb}\\{name}_poly"
    arcpy.conversion.RasterToPolygon(cls_path, poly, "NO_SIMPLIFY", "VALUE")
    g = pyogrio.read_dataframe(scratch_gdb, layer=f"{name}_poly").to_crs(crs)
    g = g.rename(columns={"gridcode": "hz_class"})[["hz_class", "geometry"]]
    g["hz_class"] = g["hz_class"].astype(int)
    log.info(f"{Path(raster).name} classed on breaks {breaks} {units}: cells by class (polygons)\n"
             + g["hz_class"].value_counts().sort_index().to_string())
    return g


def build_wildfire_surface(cfg: dict, log, overwrite: bool) -> dict:
    """Two classed surfaces for WF-R, WF-AT, and WF-TC (rubric 6.4, decision 22): E1 the annual
    burn probability raster on the draft's breaks and E2 the TRPA most-likely fire severity
    polygons (or the contracted flame-length raster when exposure.wildfire.flame_length_raster is
    set). Written to the hazards geodatabase as exposure.wildfire.bp_fc and e2_fc. Returns
    {"e1": (weight, surface), "e2": (weight, surface)}."""
    import arcpy
    import pyogrio
    ex = cfg["exposure"]
    wf = ex["wildfire"]
    crs = target_crs(cfg)
    gdb = ex["hazards_gdb"]
    ensure_gdb(gdb, log)
    w = wf["weights"]
    bp_fc, e2_fc = wf["bp_fc"], wf["e2_fc"]
    if arcpy.Exists(f"{gdb}\\{bp_fc}") and arcpy.Exists(f"{gdb}\\{e2_fc}") and not overwrite:
        log.info(f"{bp_fc} and {e2_fc} exist; reading them (use --overwrite to rebuild)")
        return {"e1": (float(w["e1"]), pyogrio.read_dataframe(gdb, layer=bp_fc).to_crs(crs)),
                "e2": (float(w["e2"]), pyogrio.read_dataframe(gdb, layer=e2_fc).to_crs(crs))}

    # E1: burn probability
    bp_raster = str(wf["bp_raster"])
    if not bp_raster or "<" in bp_raster or not arcpy.Exists(bp_raster):
        raise SystemExit(f"exposure.wildfire.bp_raster is not set or not found: {bp_raster}")
    bp = raster_to_classes(bp_raster, wf["bp_breaks_pct"], str(wf.get("bp_units", "auto")), cfg, log, gdb, "wf_bp")
    bp = dissolve_classes(bp, crs)
    log.info("Burn probability surface, area by class (km2):\n"
             + (bp.groupby("hz_class").geometry.apply(lambda g: g.area.sum() / 1e6)).round(1).to_string())
    bk = wf["bp_breaks_pct"]
    write_class_fc(bp, gdb, bp_fc, "wildfire", {3: f"burn probability over {bk[1]:g} percent",
                                                2: f"burn probability over {bk[0]:g} to {bk[1]:g} percent",
                                                1: f"burn probability over 0 to {bk[0]:g} percent"}, cfg, log)

    # E2: flame length when the contracted raster is set, else the TRPA severity polygons
    fl_raster = str(wf.get("flame_length_raster") or "")
    if fl_raster:
        fb = wf["flame_breaks_ft"]
        e2 = dissolve_classes(raster_to_classes(fl_raster, fb, "percent", cfg, log, gdb, "wf_fl"), crs)
        labels = {3: f"flame length over {fb[1]:g} ft", 2: f"flame length over {fb[0]:g} to {fb[1]:g} ft",
                  1: f"flame length over 0 to {fb[0]:g} ft"}
        log.info("E2 is flame length (contracted package)")
    else:
        fld = wf["severity_field"]
        sev = fetch_with_fields(wf["severity_layer"], [fld], crs, log)
        classes = {str(k).strip().lower(): int(v) for k, v in wf["severity_classes"].items()}
        sev["hz_class"] = sev[fld].astype(str).str.strip().str.lower().map(classes).fillna(0).astype(int)
        unknown = sev.loc[sev["hz_class"] == 0, fld].dropna().unique()
        if len(unknown):
            log.warning(f"severity values not in exposure.wildfire.severity_classes scored 0: {list(unknown)[:10]}")
        e2 = dissolve_classes(sev[["hz_class", "geometry"]], crs)
        inv = {v: k for k, v in wf["severity_classes"].items()}
        labels = {c: f"most likely fire severity: {inv.get(c, c)}" for c in (1, 2, 3)}
        log.info("E2 is TRPA most-likely fire severity (decision 22); set exposure.wildfire.flame_length_raster "
                 "to switch to the contracted flame length")
    log.info("E2 surface, area by class (km2):\n"
             + (e2.groupby("hz_class").geometry.apply(lambda g: g.area.sum() / 1e6)).round(1).to_string())
    write_class_fc(e2, gdb, e2_fc, "wildfire", labels, cfg, log)
    return {"e1": (float(w["e1"]), bp), "e2": (float(w["e2"]), e2)}

def build_flood_surface(cfg: dict, log, overwrite: bool) -> gpd.GeoDataFrame:
    """FEMA zones and mapped streams classed 0 to 3, dissolved by class, written to the hazards
    geodatabase as exposure.flood.class_fc with field `hz_class`. Returns the classed polygons."""
    import arcpy
    ex = cfg["exposure"]
    fl = ex["flood"]
    crs = target_crs(cfg)
    gdb = ex["hazards_gdb"]
    ensure_gdb(gdb, log)
    out_fc = f"{gdb}\\{fl['class_fc']}"
    if arcpy.Exists(out_fc) and not overwrite:
        log.info(f"{fl['class_fc']} exists; reading it (use --overwrite to rebuild)")
        import pyogrio
        return pyogrio.read_dataframe(gdb, layer=fl["class_fc"]).to_crs(crs)

    # FEMA zones with their attributes
    zones = fetch_with_fields(fl["zones_layer"], [fl["zone_field"], fl["year_field"]], crs, log)
    zones["hz_class"] = [flood_class(z, y) for z, y in zip(zones[fl["zone_field"]], zones[fl["year_field"]])]
    # Lake Tahoe's own 1 percent stillwater zone (AE over the lake) is lake-stage flooding, the
    # high-lake-level pair the Steering Committee has not adopted; keep it out of the flood pairs
    # unless exposure.flood.include_lake_zone is true.
    log.info(f"{len(zones)} FEMA polygons; class counts:\n" + zones["hz_class"].value_counts().to_string())
    unclassed = zones[zones["hz_class"] == 0]
    if len(unclassed):
        log.warning(f"{len(unclassed)} FEMA polygons scored 0; zone / year values: "
                    f"{unclassed[[fl['zone_field'], fl['year_field']]].drop_duplicates().head(10).to_dict('records')}")

    # mapped streams (lidar-derived polygons); water bodies over the cap are the lake and the
    # large lakes, used below to recognize lake-stage FEMA zones and excluded from "a stream"
    water = fetch_rest_features(fl["streams_layer"], crs, log)
    cap = float(fl.get("exclude_water_over_km2", 1.0)) * 1e6
    lakes = water[water.area > cap]
    streams = water[water.area <= cap]
    if not fl.get("include_lake_zone", False) and len(lakes):
        lake_geom = lakes.geometry.union_all() if hasattr(lakes.geometry, "union_all") else lakes.geometry.unary_union
        frac = zones.geometry.intersection(lake_geom).area / zones.area.replace(0, np.nan)
        on_lake = frac.fillna(0) > 0.5
        if on_lake.any():
            log.info(f"{int(on_lake.sum())} FEMA polygon(s) dropped as lake-stage zones (more than half on a water body "
                     f"over {cap / 1e6:g} km2; {zones.loc[on_lake].area.sum() / 1e6:.0f} km2); "
                     f"set exposure.flood.include_lake_zone to keep them")
            zones = zones[~on_lake]
        kept_big = zones[zones.area > cap]
        if len(kept_big):
            log.info(f"{len(kept_big)} FEMA floodplain polygon(s) over {cap / 1e6:g} km2 kept (not on the lake): "
                     f"{[round(a / 1e6, 1) for a in kept_big.area]} km2")
    sb = gpd.GeoDataFrame({"hz_class": [2] * len(streams)}, geometry=streams.buffer(float(fl["stream_buffer_m"])).values, crs=crs)
    log.info(f"{len(streams)} stream polygons (water bodies over {fl.get('exclude_water_over_km2', 1.0)} km2 excluded) "
             f"buffered {fl['stream_buffer_m']} m as class 2")

    parts = [zones[["hz_class", "geometry"]], sb]
    if fl.get("nhd_flowlines"):
        nhd = fetch_rest_features(fl["nhd_flowlines"], crs, log)
        parts.append(gpd.GeoDataFrame({"hz_class": [1] * len(nhd)}, geometry=nhd.buffer(float(fl["stream_buffer_m"])).values, crs=crs))
    allp = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs=crs)
    surf = dissolve_classes(allp, crs)
    log.info("Classed flood surface, area by class (km2):\n"
             + (surf.groupby("hz_class").geometry.apply(lambda g: g.area.sum() / 1e6)).round(2).to_string())

    write_class_fc(surf, gdb, fl["class_fc"], "flood", {3: "1 percent (100-yr) flood zone",
                                                        2: "0.2 percent (500-yr) zone or mapped stream",
                                                        1: "NHD flowline outside a zone"}, cfg, log)
    return surf


SURFACE_BUILDERS = {"flood": build_flood_surface, "wildfire": build_wildfire_surface}
# asset classes that are a scored pair under each hazard (Hazard_Asset_Pairs.md)
PAIRS = {"flood": {"culverts", "bridges", "roads", "active_transport", "transit_centers"},
         "wildfire": {"roads", "active_transport", "transit_centers"}}


def sample_distance_m(cfg: dict, hazard: str) -> float:
    """Line sampling distance per hazard: wildfire pairs sample within 300 ft (exposure.wildfire
    .buffer_ft); flood samples the line itself."""
    hz = cfg["exposure"].get(hazard, {}) or {}
    return float(hz.get("buffer_ft", 0)) * 0.3048 if "buffer_ft" in hz else float(hz.get("line_buffer_m", 0) or 0)


# ----------------------------------------------------------------------------------------
# sampling

def sample_points(pts: gpd.GeoDataFrame, surf: gpd.GeoDataFrame, buffer_m: float) -> pd.Series:
    """Maximum hz_class within buffer_m of each point (0 where none). Index = pts.index."""
    buf = gpd.GeoDataFrame(geometry=pts.geometry.buffer(buffer_m), crs=pts.crs)
    sj = gpd.sjoin(buf, surf[["hz_class", "geometry"]], how="left", predicate="intersects")
    return sj.groupby(level=0)["hz_class"].max().reindex(pts.index).fillna(0)


def sample_lines(lines: gpd.GeoDataFrame, surf: gpd.GeoDataFrame, buffer_m: float = 0.0) -> pd.DataFrame:
    """Maximum hz_class within buffer_m of each line (touching it when 0) and the share of the
    line's own length inside each class."""
    probe = lines[["geometry"]] if buffer_m <= 0 else gpd.GeoDataFrame(geometry=lines.geometry.buffer(buffer_m), crs=lines.crs)
    sj = gpd.sjoin(probe, surf[["hz_class", "geometry"]], how="left", predicate="intersects")
    out = pd.DataFrame({"hz_max": sj.groupby(level=0)["hz_class"].max().reindex(lines.index).fillna(0)})
    total = lines.geometry.length.replace(0, np.nan)
    # length in each class through the spatial index: overlay against the (many, small) class
    # polygons rather than intersecting every line with one basin-wide union
    L = gpd.GeoDataFrame({"_lid": lines.index}, geometry=lines.geometry.values, crs=lines.crs)
    cut = gpd.overlay(L, surf[["hz_class", "geometry"]].explode(index_parts=False).reset_index(drop=True),
                      how="intersection", keep_geom_type=True)
    cut["_len"] = cut.geometry.length
    share = cut.groupby(["_lid", "hz_class"])["_len"].sum().unstack(fill_value=0.0)
    for c in sorted(surf["hz_class"].unique()):
        col = share[c] if c in share.columns else pd.Series(0.0, index=share.index)
        out[f"len_pct_c{int(c)}"] = (col.reindex(lines.index).fillna(0) / total * 100).fillna(0).clip(upper=100).round(1)
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
    out = score_line_assets(st, key, cfg, hazard, surf, log)
    write_line_scores(out, key, f"{hazard}_roads", pair, cfg, log, dry_run, overwrite)
    return out


def score_line_assets(lines: gpd.GeoDataFrame, key: str, cfg: dict, hazard: str, surf, log) -> pd.DataFrame:
    """Line assets against every indicator surface of the hazard: each indicator is the maximum
    within the hazard's sampling distance, combined by the rubric weights; length shares come
    from the first (E1) surface."""
    ex = cfg["exposure"]
    code = HAZARD_CODE[hazard]
    h = ex["horizon"]
    dist = sample_distance_m(cfg, hazard)
    inds = indicators(surf)
    out = pd.DataFrame({key: lines[key].values})
    parts = {}
    for i, (name, w, g) in enumerate(inds):
        res = sample_lines(lines, g, dist)
        parts[name] = res["hz_max"].values
        if len(inds) > 1:
            out[f"E_{name}"] = res["hz_max"].values
        if i == 0:
            for c in [c for c in res.columns if c.startswith("len_pct_")]:
                out[c] = res[c].values
    weights = {name: w for name, w, _ in inds}
    out[f"E_{h}"] = [round(weighted_exposure({k: v[j] for k, v in parts.items()}, weights), 2) for j in range(len(lines))]
    out["seg_len_m"] = lines.geometry.length.round(1).values
    log.info(f"{code} E_{h} on {len(out)} lines (sampled within {dist:.0f} m):\n"
             + out[f"E_{h}"].value_counts().sort_index().to_string())
    return out


def write_line_scores(out: pd.DataFrame, key: str, stem: str, pair: str, cfg: dict, log, dry_run: bool, overwrite: bool) -> None:
    """Rename the generic E_ columns to the pair, write the CSV, and the analysis-geodatabase table."""
    import arcpy
    h = cfg["exposure"]["horizon"]
    out.rename(columns={f"E_{h}": f"E_{pair}_{h}", "E_e1": f"E_{pair}_e1", "E_e2": f"E_{pair}_e2"}, inplace=True)
    p = REPO / cfg["paths"]["outputs"] / f"exposure_{stem}.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(p, index=False)
    log.info(f"-> {p}")
    if dry_run:
        return
    name = f"Exposure_{stem}"
    tbl = f"{cfg['paths']['analysis_gdb']}\\{name}"
    if arcpy.Exists(tbl):
        if not overwrite:
            raise SystemExit(f"{tbl} exists; re-run with --overwrite")
        arcpy.management.Delete(tbl)
    fields = [(key, "TEXT", 64)] + [(c, "DOUBLE", None) for c in out.columns if c != key and c != "name"]
    if "name" in out.columns:
        fields.insert(1, ("name", "TEXT", 120))
    write_table(out, fields, cfg["paths"]["analysis_gdb"], name, log)


def score_active_transport(cfg: dict, hazard: str, surf, log, dry_run: bool, overwrite: bool) -> pd.DataFrame:
    """Existing active transportation facilities (exposure.active_transport_layer) sampled like roads."""
    ex = cfg["exposure"]
    pair = f"{HAZARD_CODE[hazard]}AT"
    url = ex.get("active_transport_layer") or ""
    if not url:
        log.warning("exposure.active_transport_layer is blank; active transport skipped")
        return pd.DataFrame()
    key = ex.get("active_transport_key", "OBJECTID")
    at = fetch_with_fields(url, [key, "NAME", "CLASS"], target_crs(cfg), log)
    at = at[at.geometry.notna() & ~at.geometry.is_empty].reset_index(drop=True)
    at[key] = at[key].astype(str)
    out = score_line_assets(at, key, cfg, hazard, surf, log)
    out.insert(1, "name", at["NAME"].fillna("").astype(str).str.slice(0, 120).values)
    write_line_scores(out, key, f"{hazard}_active_transport", pair, cfg, log, dry_run, overwrite)
    return out


def score_transit_centers(cfg: dict, hazard: str, surf, log, dry_run: bool, overwrite: bool) -> pd.DataFrame:
    """Transit centers (exposure.transit_centers_layer, points): maximum within the hazard's
    sampling distance (or exposure.point_buffer_m when the hazard sets none), weighted across
    indicators. Blank layer = skipped."""
    ex = cfg["exposure"]
    pair = f"{HAZARD_CODE[hazard]}TC"
    h = ex["horizon"]
    url = ex.get("transit_centers_layer") or ""
    if not url:
        log.warning("exposure.transit_centers_layer is blank; transit centers skipped (which layer holds them is an open item)")
        return pd.DataFrame()
    key = ex.get("transit_centers_key", "OBJECTID")
    tc = fetch_with_fields(url, [key], target_crs(cfg), log)
    tc[key] = tc[key].astype(str)
    dist = sample_distance_m(cfg, hazard) or float(ex["point_buffer_m"])
    inds = indicators(surf)
    parts = {name: sample_points(tc, g, dist).values for name, _, g in inds}
    weights = {name: w for name, w, _ in inds}
    out = pd.DataFrame({key: tc[key].values})
    for name in parts:
        if len(inds) > 1:
            out[f"E_{name}"] = parts[name]
    out[f"E_{h}"] = [round(weighted_exposure({k: v[j] for k, v in parts.items()}, weights), 2) for j in range(len(tc))]
    log.info(f"E_{pair}_{h} on {len(out)} transit centers (within {dist:.0f} m):\n"
             + out[f"E_{h}"].value_counts().sort_index().to_string())
    write_line_scores(out, key, f"{hazard}_transit_centers", pair, cfg, log, dry_run, overwrite)
    return out


SCORERS = {"culverts": score_culverts, "bridges": score_bridges, "roads": score_roads,
           "active_transport": score_active_transport, "transit_centers": score_transit_centers}


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
        raise SystemExit(f"No surface builder for {args.hazard} yet ({', '.join(SURFACE_BUILDERS)} implemented)")
    bad = [a for a in args.assets if a not in PAIRS.get(args.hazard, set())]
    if bad:
        raise SystemExit(f"{args.hazard} x {', '.join(bad)} is not a scored pair (Hazard_Asset_Pairs.md)")
    surf = builder(cfg, log, overwrite=args.build or args.overwrite)
    if not args.assets:
        log.info("No --assets given; surface built only")
        return
    for a in args.assets:
        SCORERS[a](cfg, args.hazard, surf, log, args.dry_run, args.overwrite)
    log.info("Done")


if __name__ == "__main__":
    main()
