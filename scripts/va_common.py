"""Shared helpers for the PROTECT vulnerability assessment asset scripts.

Used by load_culverts_gdb.py and build_bridges.py (and the scoring scripts that follow).
Keeps the repo conventions in one place: config.yaml, timestamped logs, the analysis
geodatabase, and the parent-road-segment snap that lets point assets inherit criticality.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]


def load_cfg() -> dict:
    with open(REPO / "config.yaml") as f:
        return yaml.safe_load(f)


def get_logger(name: str) -> logging.Logger:
    logs = REPO / "logs"
    logs.mkdir(exist_ok=True)
    # pd.Timestamp, not datetime: a successful arcpy import shadows the datetime name
    ts = pd.Timestamp.now().strftime("%Y-%m-%d_%H%M%S")
    log = logging.getLogger(name)
    log.setLevel(logging.INFO)
    log.handlers.clear()
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(logs / f"{name}_{ts}.log")):
        h.setFormatter(fmt)
        log.addHandler(h)
    return log


def target_crs(cfg: dict) -> str:
    return f"EPSG:{cfg['output']['target_epsg']}"


def fetch_basin(cfg: dict, log: logging.Logger) -> gpd.GeoDataFrame:
    """TRPA boundary polygon(s) from sources.trpa_boundary_layer, in the target CRS."""
    import requests
    url = cfg["sources"]["trpa_boundary_layer"]
    bj = requests.get(f"{url}/query", params={"where": "1=1", "outFields": "OBJECTID", "f": "geojson"},
                      timeout=120).json()
    basin = gpd.GeoDataFrame.from_features(bj["features"], crs="EPSG:4326").to_crs(target_crs(cfg))
    log.info(f"TRPA boundary: {len(basin)} feature(s) from {url}")
    return basin


def dedupe_ids(s: pd.Series) -> pd.Series:
    """Make IDs unique by suffixing -2, -3... on repeats (same rule as the culvert notebook)."""
    s = s.astype(str)
    counts = s.groupby(s).cumcount()
    return s.where(counts == 0, s + "-" + (counts + 1).astype(str))


def line_rep_point(geom, how: str = "midpoint"):
    """Collapse a (Multi)LineString to a representative Point (same rule as the culvert notebook)."""
    from shapely.geometry import MultiLineString, Point
    from shapely.ops import linemerge
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, MultiLineString):
        merged = linemerge(geom)
        if isinstance(merged, MultiLineString):  # disjoint parts: take the longest
            merged = max(merged.geoms, key=lambda g: g.length)
        geom = merged
    if how == "start":
        return Point(geom.coords[0])
    if how == "end":
        return Point(geom.coords[-1])
    return geom.interpolate(0.5, normalized=True)


def read_streets(cfg: dict, log: logging.Logger, columns: list[str] | None = None) -> gpd.GeoDataFrame:
    """Road segments from the analysis geodatabase, in the target CRS."""
    a = cfg["assets"]
    cols = sorted(set([a["streets_key"]] + (columns or [])))
    log.info(f"Reading {a['streets_fc']} from the analysis geodatabase (slow on F:)")
    streets = gpd.read_file(cfg["paths"]["analysis_gdb"], layer=a["streets_fc"], columns=cols)
    streets = streets.to_crs(target_crs(cfg))
    log.info(f"{len(streets)} segments read")
    return streets


def snap_to_segments(points: gpd.GeoDataFrame, id_col: str, cfg: dict, log: logging.Logger,
                     streets: gpd.GeoDataFrame | None = None) -> gpd.GeoDataFrame:
    """Add parent_segment_id and parent_dist_m: nearest road segment within assets.segment_snap_m."""
    a = cfg["assets"]
    key = a["streets_key"]
    if streets is None:
        streets = read_streets(cfg, log)
    streets = streets[[key, "geometry"]]
    pts = points.to_crs(streets.crs)
    joined = gpd.sjoin_nearest(
        pts[[id_col, "geometry"]], streets,
        how="left", max_distance=a["segment_snap_m"], distance_col="parent_dist_m",
    )
    joined = joined[~joined.index.duplicated(keep="first")]  # sjoin_nearest can return ties
    out = pts.copy()
    out["parent_segment_id"] = joined[key].astype("string")
    out["parent_dist_m"] = joined["parent_dist_m"].round(2)
    n_un = int(out["parent_segment_id"].isna().sum())
    log.info(f"Snapped {len(out) - n_un}; {n_un} have no segment within {a['segment_snap_m']} m")
    return out


# ---- arcpy write helpers (arcpy imported lazily inside write_* so the rest runs licence-free)

def fields_spec(fields):
    """[(name, type, length)] -> AddFields spec [[name, type, alias, length], ...]."""
    return [[n, t, n, ln if ln else ""] for n, t, ln in fields]


def text_lengths(fields) -> dict[str, int]:
    return {n: ln for n, t, ln in fields if t == "TEXT"}


def to_dt(v):
    return None if v is None or pd.isna(v) else pd.Timestamp(v).to_pydatetime()


def field_types(fields) -> dict[str, str]:
    return {n: t for n, t, ln in fields}


def clean(v, col=None, text_len: dict | None = None, ftype: str | None = None):
    """Python value for an arcpy cursor: None for any null, numpy scalars unboxed, integers for
    SHORT / LONG (a float 2005.0 from a geopackage or pandas 3 is rejected by arcpy otherwise),
    floats for DOUBLE / FLOAT, strings for TEXT truncated to the field length."""
    try:
        if v is None or v is pd.NA or pd.isna(v):
            return None
    except (TypeError, ValueError):  # arrays and other non-scalars: leave as is
        pass
    if hasattr(v, "item") and not isinstance(v, str):  # numpy / pandas scalar -> python
        v = v.item()
    if ftype in ("SHORT", "LONG"):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
        try:
            return int(round(float(v)))
        except (TypeError, ValueError):
            return None
    if ftype in ("DOUBLE", "FLOAT"):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    if ftype == "TEXT" and not isinstance(v, str):
        v = str(v)
    if isinstance(v, str) and text_len and col in text_len and len(v) > text_len[col]:
        return v[: text_len[col]]
    return v


def guard_exists(paths: list[str], overwrite: bool, log: logging.Logger) -> None:
    import arcpy
    for p in paths:
        if arcpy.Exists(p):
            if not overwrite:
                raise SystemExit(f"{p} exists. Re-run with --overwrite to replace it.")
            log.warning(f"Deleting existing {p}")
            arcpy.management.Delete(p)
    arcpy.management.ClearWorkspaceCache()


def write_point_fc(gdf: gpd.GeoDataFrame, fields, gdb: str, name: str, epsg: int,
                   log: logging.Logger, date_cols: set[str] = frozenset()) -> str:
    """Write a point GeoDataFrame to <gdb>/<name> with the given field spec. Returns the path."""
    import arcpy
    cols = [f[0] for f in fields]
    tl, ft = text_lengths(fields), field_types(fields)
    fc = arcpy.management.CreateFeatureclass(
        gdb, name, "POINT", spatial_reference=arcpy.SpatialReference(epsg)).getOutput(0)
    arcpy.management.AddFields(fc, fields_spec(fields))
    gdf = gdf.to_crs(f"EPSG:{epsg}")
    with arcpy.da.InsertCursor(fc, ["SHAPE@XY"] + cols) as cur:
        for _, r in gdf.iterrows():
            xy = (float(r.geometry.x), float(r.geometry.y)) if r.geometry is not None else None
            cur.insertRow([xy] + [to_dt(r[c]) if c in date_cols else clean(r[c], c, tl, ft.get(c)) for c in cols])
    log.info(f"Wrote {int(arcpy.management.GetCount(fc)[0])} rows -> {name}")
    return fc


def write_table(df: pd.DataFrame, fields, gdb: str, name: str, log: logging.Logger,
                date_cols: set[str] = frozenset()) -> str:
    import arcpy
    cols = [f[0] for f in fields]
    tl, ft = text_lengths(fields), field_types(fields)
    tbl = arcpy.management.CreateTable(gdb, name).getOutput(0)
    arcpy.management.AddFields(tbl, fields_spec(fields))
    with arcpy.da.InsertCursor(tbl, cols) as cur:
        for _, r in df.iterrows():
            cur.insertRow([to_dt(r[c]) if c in date_cols else clean(r[c], c, tl, ft.get(c)) for c in cols])
    log.info(f"Wrote {int(arcpy.management.GetCount(tbl)[0])} rows -> {name}")
    return tbl
