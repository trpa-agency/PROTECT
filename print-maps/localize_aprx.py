"""Point a copy of the PROTECT Pro project at local data so the maps draw without F: or the SDE server.

PROTECT_Maps.aprx was saved from F:\\...\\PROTECT_analysis\\PROTECT_analysis.aprx into the repo's data folder
with relative paths, so Pro rewrote every F: geodatabase next to the project as <repo>\\data\\<name>.gdb (most of
them broken) and left the SDE layers on sql12. This script:

  1. rewrites every file geodatabase, folder, and raster path by the PATH_MAP table below (local copies under
     LOCAL first, the F: original where nothing was copied),
  2. exports every SDE feature class and table the project uses into LOCAL\\PROTECT_reference.gdb once and
     repoints the layers at the export (--skip-sde leaves them on the server),
  3. saves the result as a new .aprx (the source project is never written) with LOCAL as its home folder, then
     reopens it and reports what is still broken, by source.

Run from the arcgispro-py3 environment:
  python print-maps/localize_aprx.py                       # data\\PROTECT_Maps.aprx -> C:\\GIS\\PROTECT_local\\PROTECT_Maps.aprx
  python print-maps/localize_aprx.py --report-only         # list sources and what they would map to; write nothing
  python print-maps/localize_aprx.py --skip-sde            # path rewrite only

The NDOT SAM21 export never moves: the analysis geodatabase holds NDOT culvert rows, so it (and this project)
lives in LOCAL, outside the repo, never under data/ (CLAUDE.md, config.yaml ndot:).
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import logging
import sys
import time
from pathlib import Path

import arcpy

REPO = Path(__file__).resolve().parents[1]
LOCAL = Path(r"C:\GIS\PROTECT_local")
F_ANALYSIS = r"F:\GIS\PROJECTS\Transportation\Protect\PROTECT_analysis"
F_DATA = r"F:\GIS\PROJECTS\Transportation\Protect\Data"
REPO_DATA = str(REPO / "data")

# Longest prefixes first: each layer's database / folder path takes the first entry that matches.
# (what the copied project holds, what it becomes). A right side under LOCAL must exist (copied by hand or by
# robocopy); one on F: is the slow-but-working original, listed in the report as "still on F:".
PATH_MAP = [
    (REPO_DATA + r"\PROTECT_curated.gdb", str(LOCAL / "PROTECT_curated.gdb")),
    (REPO_DATA + r"\PROTECT_hazards.gdb", str(LOCAL / "PROTECT_hazards.gdb")),
    (REPO_DATA + r"\PROTECT_analysis.gdb", str(LOCAL / "PROTECT_analysis.gdb")),
    (REPO_DATA + r"\PROTECT_data.gdb", str(LOCAL / "PROTECT_data.gdb")),
    (REPO_DATA + r"\Assets.gdb", str(LOCAL / "Assets.gdb")),
    (REPO_DATA + r"\Hazards.gdb", str(LOCAL / "Hazards.gdb")),
    (REPO_DATA + r"\Streetlight_AADT", str(LOCAL / "Streetlight_AADT")),
    (REPO_DATA + r"\Tahoe District Sample Data", str(LOCAL / "Tahoe District Sample Data")),
    (REPO_DATA + r"\usgs_landslide_risk.tif", F_ANALYSIS + r"\usgs_landslide_risk.tif"),   # 9.2 GB: stays on F:
    (str(REPO / "Data" / "Culvert"), F_DATA + r"\Culvert"),    # jurisdiction deliveries (50 GB, NDOT inside): F: only;
                                                               # before the catch-all, which matches "Data" case-insensitively
    (REPO_DATA, F_ANALYSIS),                                   # anything else that sat beside the project on F:
    (r"C:\Users\mbindl\Documents\TRPA_Maps\Cartography.gdb", str(LOCAL / "Cartography.gdb")),  # labels; copy when found
]

SDE_GDB = LOCAL / "PROTECT_reference.gdb"
FGDB = "File Geodatabase"

# SDE dataset -> the same layer published on maps.trpa.org (checked against the REST catalog, Nov. 3, 2026).
# --sde-mode services repoints these at the service and exports only what is not listed here.
TRPA = "https://maps.trpa.org/server/rest/services"
SERVICE_MAP = {
    "SDE.bike_ped_counter_spatial": f"{TRPA}/LTInfo_Monitoring/MapServer/5",
    "SDE.Traffic_Volumes": f"{TRPA}/DataDownloader_Transportation/MapServer/18",
    "SDE.Existing_Active_Transportation_Facilities": f"{TRPA}/Transportation/MapServer/3",
    "SDE.High_Injury_Network_OSM": f"{TRPA}/Transportation_Planning/MapServer/8",
    "SDE.Streets": f"{TRPA}/DataDownloader_Transportation/MapServer/2",
    "SDE.Tahoe_BlockGroup_2022_TDC_Values": f"{TRPA}/Demographics/MapServer/1",
    "SDE.Tahoe_BlockGroup_TDC_Values": f"{TRPA}/Demographics/MapServer/0",
    "SDE.Demographics_Tessellation": f"{TRPA}/Demographics/MapServer/2",
    "SDE.Major_Highways": f"{TRPA}/DataDownloader_Transportation/MapServer/0",
    "SDE.Tahoe_Census_County": f"{TRPA}/Boundaries/FeatureServer/3",
    "SDE.Watershed": f"{TRPA}/DataDownloader_SoilsandHydro/MapServer/5",
    "SDE.Hydrography_StreamNetwork_2010_Tahoe": f"{TRPA}/Streams_and_Flood_Zone/MapServer/1",
    "SDE.NHDFlowline": f"{TRPA}/DataDownloader_SoilsandHydro/MapServer/30",
    "SDE.CA_NV_Census_State_Boundary": f"{TRPA}/Boundaries/FeatureServer/16",
    "SDE.UrbanAreas": f"{TRPA}/Boundaries/FeatureServer/14",
    # not published: bike_ped_counter_tabular, Network_Drive, StreamEnvironmentZone_LakeTahoeBasin, subwatersheds
}


def service_cp(url: str) -> dict:
    """Layer connection properties for one sublayer of a map or feature service."""
    base, _, layer_id = url.rpartition("/")
    return {"dataset": layer_id, "workspace_factory": "FeatureService", "connection_info": {"url": base}}


def set_connection(lyr, conn_str: str, factory: str, dataset: str, is_table: bool) -> None:
    """Replace a layer's or standalone table's data connection outright through its CIM definition.
    updateConnectionProperties merges dictionaries, so moving a layer off SDE left the sql12 keys beside the
    new database path (a broken connection); the CIM swap writes a whole new CIMStandardDataConnection."""
    cim = lyr.getDefinition("V3")
    dc = arcpy.cim.CreateCIMObjectFromClassName("CIMStandardDataConnection", "V3")
    dc.workspaceConnectionString = conn_str
    dc.workspaceFactory = factory
    dc.dataset = dataset
    dc.datasetType = "esriDTTable" if is_table else "esriDTFeatureClass"
    if hasattr(cim, "featureTable") and cim.featureTable is not None:
        cim.featureTable.dataConnection = dc
    else:
        cim.dataConnection = dc
    lyr.setDefinition(cim)


def get_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("localize_aprx")
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    for h in (logging.StreamHandler(sys.stdout),
              logging.FileHandler(log_dir / f"localize_aprx_{dt.datetime.now():%Y%m%d_%H%M%S}.log", encoding="utf-8")):
        h.setFormatter(fmt)
        log.addHandler(h)
    return log


def conn(layer):
    """connectionProperties, or None for layers that have none (map image sublayers, basemaps)."""
    try:
        return layer.connectionProperties
    except Exception:
        return None


def iter_members(aprx):
    """Every layer and standalone table in every map, with its map."""
    for m in aprx.listMaps():
        for lyr in m.listLayers():
            yield m, lyr
        for tbl in m.listTables():
            yield m, tbl


def database_of(cp: dict) -> str | None:
    """The file path a connection points at (database for geodatabases, shapefile and raster folders alike)."""
    if not isinstance(cp, dict) or "connection_info" not in cp:
        return None
    return cp["connection_info"].get("database")


def map_path(path: str) -> str | None:
    """The PATH_MAP replacement for a path, or None when no entry matches."""
    for old, new in PATH_MAP:
        if path.lower() == old.lower() or path.lower().startswith(old.lower() + "\\"):
            return new + path[len(old):]
    return None


def status(path: str) -> str:
    if path.lower().startswith(str(LOCAL).lower()):
        return "local" if Path(path).exists() else "LOCAL COPY MISSING"
    if path.upper().startswith("F:"):
        return "still on F:" if Path(path).exists() else "F: path missing"
    return "unresolved"


def _rewrite_cp(c: dict, found: dict) -> bool:
    """Rewrite one connection dict's database path in place by PATH_MAP; True when it changed."""
    db = database_of(c)
    if not db or c.get("workspace_factory") == "SDE":
        return False
    new = map_path(db)
    if new is None:
        found.setdefault(db, (db, "unresolved" if not Path(db).exists() else "ok"))
        return False
    found.setdefault(db, (new, status(new)))
    if new != db:
        c["connection_info"]["database"] = new
        return True
    return False


def rewrite_paths(aprx, log, dry: bool) -> dict:
    """Rewrite file-based connections by PATH_MAP, one call per layer (a project-wide replacement is a full
    pass over every map per path, minutes each). Returns {old_path: (new_path, status)}."""
    found: dict[str, tuple[str, str]] = {}
    n = 0
    for m, lyr in iter_members(aprx):
        cp = conn(lyr)
        if not isinstance(cp, dict):
            continue
        new_cp = copy.deepcopy(cp)
        if "source" in new_cp:      # joined layer: cp = {source: {...}, destination: [{...}, ...]}
            changed = _rewrite_cp(new_cp["source"], found)
            for d in new_cp.get("destination", []):
                if isinstance(d, dict):
                    changed = _rewrite_cp(d, found) or changed
        else:
            changed = _rewrite_cp(new_cp, found)
        if changed and not dry:
            try:
                lyr.updateConnectionProperties(cp, new_cp, validate=False)
                n += 1
            except Exception as e:
                log.warning(f"path  could not repoint {m.name}\\{getattr(lyr, 'longName', lyr.name)}: {e}")
    log.info(f"path  {n} layers repointed")
    return found


def export_sde(aprx, log, dry: bool, services: bool = True) -> dict:
    """Repoint every SDE layer: at its maps.trpa.org service when SERVICE_MAP lists it (and services is on),
    otherwise at a copy exported once into SDE_GDB."""
    done: dict[str, str] = {}
    if not dry and not SDE_GDB.exists():
        arcpy.management.CreateFileGDB(str(SDE_GDB.parent), SDE_GDB.name)
    for m, lyr in iter_members(aprx):
        cp = conn(lyr)
        if not isinstance(cp, dict) or "source" in cp:
            continue
        db = database_of(cp) or ""
        is_sde = cp.get("workspace_factory") == "SDE"
        # a layer an earlier run merged onto the export (the reference gdb path with the sql12 keys still beside it)
        is_ref = db.rstrip("\\").lower().endswith(SDE_GDB.name.lower())
        if not (is_sde or is_ref):
            continue
        if getattr(lyr, "isRasterLayer", False):   # never export SDE rasters (the DEMs run to gigabytes); they stay on the server
            log.info(f"sde   raster left on the server: {m.name}\\{lyr.longName}")
            continue
        name = cp["dataset"].split(".")[-1]      # SDE.Watershed -> Watershed
        ds = "SDE." + name
        if services and ds in SERVICE_MAP:
            url = SERVICE_MAP[ds]
            if ds not in done:
                log.info(f"sde   {ds} -> {url}")
                done[ds] = url
            if not dry:
                base, _, layer_id = url.rpartition("/")
                try:
                    set_connection(lyr, f"URL={base}", "FeatureService", layer_id,
                                   is_table=not getattr(lyr, "isFeatureLayer", False))
                except Exception as e:
                    log.warning(f"sde   could not repoint {m.name}\\{getattr(lyr, 'longName', lyr.name)} to {url}: {e}")
            continue
        out = str(SDE_GDB / name)
        if ds not in done:
            if dry:
                done[ds] = out
                log.info(f"sde   would export {ds} -> {out}")
                continue
            if arcpy.Exists(out):
                log.info(f"sde   {name}: already in {SDE_GDB.name}")
            else:
                t0 = time.time()
                try:
                    dq = getattr(lyr, "definitionQuery", "")
                    if dq:
                        lyr.definitionQuery = ""
                    if getattr(lyr, "isFeatureLayer", False):
                        arcpy.conversion.ExportFeatures(lyr, out)
                    else:
                        arcpy.conversion.ExportTable(lyr, out)
                    if dq:
                        lyr.definitionQuery = dq
                    n = int(arcpy.management.GetCount(out)[0])
                    log.info(f"sde   exported {ds} -> {out}  ({n} rows, {time.time() - t0:.0f} s)")
                except Exception as e:
                    log.warning(f"sde   FAILED {ds} on {m.name}\\{lyr.longName}: {e}")
                    continue
            done[ds] = out
        if not dry:
            try:
                set_connection(lyr, f"DATABASE={SDE_GDB}", "FileGDB", name,
                               is_table=not getattr(lyr, "isFeatureLayer", False))
            except Exception as e:
                log.warning(f"sde   could not repoint {m.name}\\{getattr(lyr, 'longName', lyr.name)}: {e}")
    return done


def report_broken(aprx, log) -> int:
    """List every file-based layer whose dataset does not exist, by source (services are not checked:
    isBroken on 700 layers is a network round trip each)."""
    broken: dict[str, list[str]] = {}
    for m, lyr in iter_members(aprx):
        cp = conn(lyr)
        if not isinstance(cp, dict) or "source" in cp:
            continue
        db = database_of(cp)
        if not db or cp.get("workspace_factory") in ("SDE", "FeatureService"):
            continue
        try:
            if arcpy.Exists(lyr.dataSource):
                continue
        except Exception:
            pass
        broken.setdefault(db, []).append(f"{m.name}\\{getattr(lyr, 'longName', lyr.name)}")
    n = sum(len(v) for v in broken.values())
    log.info(f"--- {n} file-based layers still missing their data, across {len(broken)} sources")
    for src, layers in sorted(broken.items(), key=lambda kv: -len(kv[1])):
        log.info(f"  {len(layers):3d} x {src}")
        for l in layers[:3]:
            log.info(f"        {l}")
        if len(layers) > 3:
            log.info(f"        ... and {len(layers) - 3} more")
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=str(REPO / "data" / "PROTECT_Maps.aprx"))
    ap.add_argument("--out", default=str(LOCAL / "PROTECT_Maps.aprx"))
    ap.add_argument("--report-only", action="store_true", help="list sources and targets; write nothing")
    ap.add_argument("--skip-sde", action="store_true", help="leave the SDE layers on the server")
    ap.add_argument("--sde-mode", choices=["services", "export"], default="services",
                    help="services: maps.trpa.org where SERVICE_MAP has the layer, local export otherwise (default); "
                         "export: local copies for every SDE layer")
    ap.add_argument("--force", action="store_true", help="overwrite --out if it exists")
    a = ap.parse_args()
    log = get_logger(Path(__file__).parent / "logs")
    if Path(a.out).exists() and not a.report_only and not a.force:
        sys.exit(f"{a.out} exists; pass --force to overwrite it")
    LOCAL.mkdir(parents=True, exist_ok=True)

    log.info(f"open {a.src}")
    aprx = arcpy.mp.ArcGISProject(a.src)
    log.info(f"maps: {[m.name for m in aprx.listMaps()]}")

    found = rewrite_paths(aprx, log, dry=a.report_only)
    log.info("--- file sources")
    for old, (new, st) in sorted(found.items(), key=lambda kv: kv[1][1]):
        log.info(f"  {st:20s} {old}" + (f"  ->  {new}" if new != old else ""))

    if not a.skip_sde:
        done = export_sde(aprx, log, dry=a.report_only, services=a.sde_mode == "services")
        n_svc = sum(v.startswith("http") for v in done.values())
        log.info(f"--- {len(done)} SDE datasets: {n_svc} on maps.trpa.org, {len(done) - n_svc} in {SDE_GDB}")
    if a.report_only:
        return

    aprx.homeFolder = str(LOCAL)
    local_analysis = LOCAL / "PROTECT_analysis.gdb"
    if local_analysis.exists():
        aprx.defaultGeodatabase = str(local_analysis)
    aprx.saveACopy(a.out)
    log.info(f"saved {a.out}")
    report_broken(aprx, log)


if __name__ == "__main__":
    main()
