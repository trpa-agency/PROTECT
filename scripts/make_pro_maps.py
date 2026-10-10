"""Write ArcGIS Pro map files (.mapx) for the PROTECT culvert and bridge work, from the data in
the analysis and terrain geodatabases. Import in Pro: Insert > Import Map.

    python scripts/make_pro_maps.py                 # writes pro/*.mapx
    python scripts/make_pro_maps.py --host <aprx>   # use a specific project as the build host

A map has to be built inside a project, so the script opens a copy of an existing .aprx (any
project; the copy is discarded), creates the maps, sets symbology, and exports each to .mapx.
Nothing is saved to the host project. The .mapx files reference the geodatabases by the paths
in config.yaml, so they open on any machine that sees F:.

Maps:
  PROTECT Culvert Profile   Culverts classed by the 100-yr loading ratio (rubric S1 breaks),
                            unscored culverts, crossing watersheds, bridges by lowest NBI
                            rating, streets, flow accumulation; the profile and crossing tables.
  PROTECT Terrain QA        Filled vs raw DEM, flow direction, flow accumulation, flow length,
                            crossing watersheds and culverts for checking pour points.

Restricted data: the Culverts layer in the analysis geodatabase includes NDOT rows. These maps
are for internal review in Pro on TRPA infrastructure; nothing from them goes to a page or a
public service without NDOT review.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from va_common import REPO, get_logger, load_cfg

# TRPA palette
ICE, BLUE, NAVY, ORANGE, BRICK, FOREST, EARTH = (
    [180, 203, 232], [0, 114, 206], [0, 59, 113], [232, 119, 34], [156, 62, 39], [74, 97, 24], [180, 126, 0])
GREY = [130, 130, 130]


def rgb(c, a=100):
    return {"RGB": [c[0], c[1], c[2], a]}


def find_host(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    home = Path.home() / "Documents" / "ArcGIS" / "Projects"
    hits = sorted(home.rglob("*.aprx"), key=lambda p: p.stat().st_mtime, reverse=True) if home.exists() else []
    if not hits:
        raise SystemExit("No .aprx found under Documents\\ArcGIS\\Projects; pass --host <path to any .aprx>")
    return hits[0]


def graduated(lyr, field: str, breaks: list[float], labels: list[str], colors: list, size: float | None = None):
    sym = lyr.symbology
    sym.updateRenderer("GraduatedColorsRenderer")
    r = sym.renderer
    r.classificationField = field
    r.breakCount = len(breaks)
    for brk, ub, label, col in zip(r.classBreaks, breaks, labels, colors):
        brk.upperBound = ub
        brk.label = label
        brk.symbol.color = rgb(col)
        if size:
            brk.symbol.size = size
        try:
            brk.symbol.outlineColor = rgb([255, 255, 255])
            brk.symbol.outlineWidth = 0.4
        except Exception:
            pass
    lyr.symbology = sym


def simple(lyr, color, size: float | None = None, width: float | None = None, outline=None, hollow: bool = False):
    sym = lyr.symbology
    sym.updateRenderer("SimpleRenderer")
    s = sym.renderer.symbol
    if hollow:
        s.color = rgb([0, 0, 0], 0)
    else:
        s.color = rgb(color)
    if size:
        s.size = size
    if width is not None:
        try:
            s.outlineWidth = width
        except Exception:
            s.size = width
    if outline is not None:
        try:
            s.outlineColor = rgb(outline)
        except Exception:
            pass
    lyr.symbology = sym


def stretch(lyr, ramp_name: str, aprx, stretch_type: str = "PercentClip", gamma: float | None = None):
    sym = lyr.symbology
    try:
        sym.updateColorizer("RasterStretchColorizer")
        sym.colorizer.stretchType = stretch_type
        ramps = aprx.listColorRamps(ramp_name)
        if ramps:
            sym.colorizer.colorRamp = ramps[0]
        if gamma is not None:
            sym.colorizer.gamma = gamma
        lyr.symbology = sym
    except Exception as e:  # raster colorizers vary by raster type; keep the default rather than fail
        return str(e)
    return None


def build_profile_map(aprx, cfg, log):
    import arcpy
    gdb, work = cfg["paths"]["analysis_gdb"], cfg["profile"]["work_gdb"]
    a = cfg["assets"]
    br = cfg["profile"].get("load_ratio_breaks", [0.5, 1.0, 2.0])
    m = aprx.createMap("PROTECT Culvert Profile", "MAP")
    m.spatialReference = arcpy.SpatialReference(int(cfg["output"]["target_epsg"]))

    # bottom to top: each addDataFromPath goes on top
    facc = m.addDataFromPath(f"{work}\\facc")
    facc.name = "Flow accumulation (cells, filled DEM)"
    facc.transparency = 40
    err = stretch(facc, "Blues (Continuous)", aprx, "StandardDeviation")
    facc.visible = False

    ws = m.addDataFromPath(f"{gdb}\\CulvertWatersheds_inc")
    ws.name = "Crossing watersheds (incremental)"
    simple(ws, GREY, hollow=True, width=0.6, outline=NAVY)
    ws.transparency = 30

    st = m.addDataFromPath(f"{a.get('streets_gdb') or gdb}\\{a['streets_fc']}")
    st.name = f"Streets ({a['streets_fc']})"
    simple(st, GREY, width=0.7)

    br_l = m.addDataFromPath(f"{gdb}\\{a['bridges_fc']}")
    br_l.name = "Bridges (NBI, lowest rating)"
    graduated(br_l, "lowest_rating", [4, 5, 6, 9],
              ["Poor: 4 and under", "Fair: 5", "Fair: 6", "Good: 7 to 9"], [BRICK, ORANGE, BLUE, FOREST], size=9)

    un = m.addDataFromPath(f"{gdb}\\{a['culverts_fc']}")
    un.name = "Culverts, not scored (pipes, inlets, no segment, large-culvert twins)"
    un.definitionQuery = "scored <> 1 OR scored IS NULL"
    simple(un, [200, 200, 200], size=3, outline=GREY)
    un.visible = False

    nc = m.addDataFromPath(f"{gdb}\\{a['culverts_fc']}")
    nc.name = "Culverts, scored, no loading ratio (no watershed or no size)"
    nc.definitionQuery = "scored = 1 AND load_ratio_100 IS NULL"
    simple(nc, [255, 255, 255], size=4, outline=NAVY)

    sc = m.addDataFromPath(f"{gdb}\\{a['culverts_fc']}")
    sc.name = "Culverts, 100-yr loading ratio (Qevent / Qcap)"
    sc.definitionQuery = "scored = 1 AND load_ratio_100 IS NOT NULL"
    graduated(sc, "load_ratio_100", [br[0], br[1], br[2], 10_000],
              [f"S1 = 0: under {br[0]}", f"S1 = 1: {br[0]} to under {br[1]}",
               f"S1 = 2: {br[1]} to under {br[2]}", f"S1 = 3: {br[2]} and over"],
              [ICE, BLUE, ORANGE, BRICK], size=6)

    for t in ("CulvertProfile", "CulvertCrossings", a["condition_table"]):
        try:
            m.addDataFromPath(f"{gdb}\\{t}")
        except Exception as e:
            log.warning(f"table {t} not added: {e}")
    if err:
        log.warning(f"facc colorizer left at default: {err}")
    return m


def build_terrain_map(aprx, cfg, log):
    import arcpy
    gdb, work = cfg["paths"]["analysis_gdb"], cfg["profile"]["work_gdb"]
    a = cfg["assets"]
    m = aprx.createMap("PROTECT Terrain QA", "MAP")
    m.spatialReference = arcpy.SpatialReference(int(cfg["output"]["target_epsg"]))

    dem = m.addDataFromPath(f"{work}\\dem")
    dem.name = "DEM, raw (hydro-enforced lidar 2010)"
    stretch(dem, "Elevation #1", aprx, "PercentClip")
    dem.visible = False
    if arcpy.Exists(f"{work}\\dem_fill"):
        df = m.addDataFromPath(f"{work}\\dem_fill")
        df.name = f"DEM, filled (sinks under {cfg['profile'].get('fill_z_limit_m')} m)"
        stretch(df, "Elevation #1", aprx, "PercentClip")
        df.visible = False
    fd = m.addDataFromPath(f"{work}\\fdir")
    fd.name = "Flow direction (D8)"
    fd.visible = False
    fl = m.addDataFromPath(f"{work}\\flen_up") if arcpy.Exists(f"{work}\\flen_up") else None
    if fl:
        fl.name = "Flow length, upstream (m)"
        stretch(fl, "Yellow-Green-Blue (Continuous)", aprx, "StandardDeviation")
        fl.visible = False
    facc = m.addDataFromPath(f"{work}\\facc")
    facc.name = "Flow accumulation (cells)"
    stretch(facc, "Blues (Continuous)", aprx, "StandardDeviation")
    facc.transparency = 30

    ws = m.addDataFromPath(f"{gdb}\\CulvertWatersheds_inc")
    ws.name = "Crossing watersheds (incremental)"
    simple(ws, GREY, hollow=True, width=0.8, outline=ORANGE)
    st = m.addDataFromPath(f"{a.get('streets_gdb') or gdb}\\{a['streets_fc']}")
    st.name = "Streets"
    simple(st, NAVY, width=0.6)
    cu = m.addDataFromPath(f"{gdb}\\{a['culverts_fc']}")
    cu.name = "Culverts, scored (crossing_id, snap_dist_m in popup)"
    cu.definitionQuery = "scored = 1"
    simple(cu, BRICK, size=5, outline=[255, 255, 255])
    return m


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", help="an existing .aprx to build in (a copy is used and discarded)")
    ap.add_argument("--out", default="pro", help="output folder, relative to the repo (default: pro)")
    args = ap.parse_args()
    log = get_logger("make_pro_maps")
    cfg = load_cfg()
    import arcpy

    host = find_host(args.host)
    scratch = Path(arcpy.env.scratchFolder) / "protect_mapx_host.aprx"
    shutil.copyfile(host, scratch)
    log.info(f"Build host: copy of {host}")
    aprx = arcpy.mp.ArcGISProject(str(scratch))

    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)
    for builder, fname in ((build_profile_map, "PROTECT_culvert_profile.mapx"),
                           (build_terrain_map, "PROTECT_terrain_qa.mapx")):
        m = builder(aprx, cfg, log)
        path = out / fname
        m.exportToMAPX(str(path))
        log.info(f"{m.name}: {len(m.listLayers())} layers, {len(m.listTables())} tables -> {path}")
    del aprx
    try:
        scratch.unlink()
    except OSError:
        pass


if __name__ == "__main__":
    main()
