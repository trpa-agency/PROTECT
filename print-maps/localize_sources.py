"""Local copies of the network layers the print maps draw, and a project repointed at them, so a poster export
does not wait on services. Driven by the local_sources: block of print-maps/config.yaml (what, where, the clip extent).

  python print-maps/localize_sources.py export [--replace]        # services -> vectors: geodatabase + rasters: folder
  python print-maps/localize_sources.py apply --aprx <path> [--preview "<layout name>" ...] [--dry-run]

apply edits the maps the project's layouts use and saves the project in place after copying it to .backups/.
--preview renders the named layouts to PNG (20 dpi) before and after, into <files>/previews/, for a look.
Run from the arcgispro-py3 environment, signed in to ArcGIS Online in Pro (the Terrain image service needs it).
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import shutil
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
LOCAL = Path(r"C:\GIS\PROTECT_local")
PREVIEWS = LOCAL / "PROTECT_Maps_files" / "previews"


def load_cfg() -> dict:
    cfg = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
    if "local_sources" not in cfg:
        sys.exit("print-maps/config.yaml has no local_sources: block")
    return cfg["local_sources"]


def get_logger(name: str) -> logging.Logger:
    log_dir = HERE / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("localize_sources")
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    for h in (logging.StreamHandler(sys.stdout),
              logging.FileHandler(log_dir / f"localize_sources_{name}_{dt.datetime.now():%Y%m%d_%H%M%S}.log", encoding="utf-8")):
        h.setFormatter(fmt)
        log.addHandler(h)
    sys.stdout.reconfigure(line_buffering=True)
    return log


def clip_box(cfg: dict) -> dict:
    e, m = cfg["extent"], float(cfg.get("margin_km", 0)) * 1000
    return {"xmin": e["xmin"] - m, "ymin": e["ymin"] - m, "xmax": e["xmax"] + m, "ymax": e["ymax"] + m,
            "spatialReference": {"wkid": e["wkid"]}}


def features_by_url(cfg: dict) -> dict:
    return {f["url"].rstrip("/"): f["name"] for f in cfg["features"]}


# ---------------------------------------------------------------- export
def export_features(cfg: dict, log, replace: bool) -> None:
    """Each service layer -> a feature class in vectors:, only the rows that touch the print box. arcpy's own
    feature-layer tools page the service and retry (the arcgis API's chunked query died on one bad page)."""
    import arcpy
    arcpy.env.overwriteOutput = True
    gdb = Path(cfg["vectors"])
    if not arcpy.Exists(str(gdb)):
        arcpy.management.CreateFileGDB(str(gdb.parent), gdb.name)
    box = clip_box(cfg)
    sr = arcpy.SpatialReference(box["spatialReference"]["wkid"])
    poly = arcpy.Extent(box["xmin"], box["ymin"], box["xmax"], box["ymax"], spatial_reference=sr).polygon
    done = set()
    for f in cfg["features"]:
        name, out = f["name"], f"{gdb}\\{f['name']}"
        if name in done:
            continue
        done.add(name)
        if arcpy.Exists(out) and not replace:
            log.info(f"{name}: exists ({arcpy.management.GetCount(out)[0]} rows), kept; --replace to pull again")
            continue
        t = time.time()
        try:
            arcpy.management.MakeFeatureLayer(f["url"], "svc_tmp", f.get("where", "1=1"))
            arcpy.management.SelectLayerByLocation("svc_tmp", "INTERSECT", poly)
            n_sel = int(arcpy.management.GetCount("svc_tmp")[0])
            if n_sel == 0:
                log.warning(f"{name}: no rows in the print extent from {f['url']}; nothing written")
                continue
            arcpy.conversion.ExportFeatures("svc_tmp", out)
            log.info(f"{name}: {arcpy.management.GetCount(out)[0]} of {n_sel} selected rows from {f['url']} ({time.time() - t:.0f} s)")
        except Exception as ex:  # noqa: BLE001 - one bad service must not stop the rest
            log.error(f"{name}: failed from {f['url']}: {str(ex)[:300]}")
        finally:
            try:
                arcpy.management.Delete("svc_tmp")
            except Exception:  # noqa: BLE001
                pass


TILE_PX = 4800   # the Terrain service serves at most 5,000 x 5,000 px per request


def export_rasters(cfg: dict, log, replace: bool) -> None:
    """Each image service -> one 8-bit TIFF in rasters: at cell_size over the print box, pulled in tiles the service
    accepts and mosaicked, with pyramids."""
    import math
    import arcpy
    arcpy.env.overwriteOutput = True
    out_dir = Path(cfg["rasters"])
    out_dir.mkdir(parents=True, exist_ok=True)
    box = clip_box(cfg)
    sr = arcpy.SpatialReference(box["spatialReference"]["wkid"])
    for svc, r in (cfg.get("image_services") or {}).items():
        out = out_dir / r["name"]
        if out.exists() and not replace:
            log.info(f"{out.name}: exists, kept; --replace to pull again")
            continue
        t = time.time()
        cell = float(r["cell_size"])
        tile_m = TILE_PX * cell
        nx, ny = math.ceil((box["xmax"] - box["xmin"]) / tile_m), math.ceil((box["ymax"] - box["ymin"]) / tile_m)
        tiles_dir = out_dir / f"_tiles_{out.stem}"
        tiles_dir.mkdir(exist_ok=True)
        arcpy.management.MakeImageServerLayer(r["url"], "isl_tmp", processing_template=r.get("template"))
        tiles = []
        log.info(f"{out.name}: {nx} x {ny} tiles of {TILE_PX} px at {cell:g} from {svc} ({r.get('template')})")
        for i in range(ny):
            for j in range(nx):
                tile = tiles_dir / f"t_{i}_{j}.tif"
                xmin, ymin = box["xmin"] + j * tile_m, box["ymin"] + i * tile_m
                ext = arcpy.Extent(xmin, ymin, min(xmin + tile_m, box["xmax"]), min(ymin + tile_m, box["ymax"]), spatial_reference=sr)
                for attempt in range(3):
                    try:
                        with arcpy.EnvManager(extent=ext, cellSize=cell, outputCoordinateSystem=sr, snapRaster=None, compression="LZW", pyramid="NONE"):
                            arcpy.management.CopyRaster("isl_tmp", str(tile), pixel_type="8_BIT_UNSIGNED", format="TIFF")
                        tiles.append(str(tile))
                        break
                    except Exception as ex:  # noqa: BLE001
                        log.warning(f"  tile {i},{j} attempt {attempt + 1}: {str(ex).strip()[:200]}")
                        time.sleep(5)
                else:
                    log.error(f"  tile {i},{j} failed three times; the mosaic will have a hole there")
            log.info(f"  row {i + 1} of {ny} done ({time.time() - t:.0f} s)")
        arcpy.management.Delete("isl_tmp")
        if not tiles:
            log.error(f"{out.name}: no tiles; nothing written")
            continue
        if out.exists():
            arcpy.management.Delete(str(out))
        with arcpy.EnvManager(compression="LZW", pyramid="PYRAMIDS -1 BILINEAR LZ77"):
            arcpy.management.MosaicToNewRaster(tiles, str(out_dir), out.name, sr, "8_BIT_UNSIGNED", cell, 1, "FIRST", "FIRST")
        for p in tiles:
            arcpy.management.Delete(p)
        tiles_dir.rmdir()
        d = arcpy.Describe(str(out))
        log.info(f"{out.name}: {d.width} x {d.height} px at {cell:g}, {out.stat().st_size / 1e6:.0f} MB ({time.time() - t:.0f} s)")


def cmd_export(a, log) -> None:
    cfg = load_cfg()
    log.info(f"print extent + {cfg.get('margin_km', 0)} km: {clip_box(cfg)}")
    export_features(cfg, log, a.replace)
    export_rasters(cfg, log, a.replace)


# ---------------------------------------------------------------- apply
def url_of(lyr) -> str | None:
    """Service URL + layer id behind a feature layer's connection, or None. Reads the URL= token so the merged
    SDE-plus-URL strings an earlier repoint left behind still match."""
    cim = lyr.getDefinition("V3")
    ft = getattr(cim, "featureTable", None)
    dc = ft.dataConnection if ft is not None else getattr(cim, "dataConnection", None)
    if dc is None or getattr(dc, "workspaceFactory", "") != "FeatureService":
        return None
    ws = dc.workspaceConnectionString or ""
    url = next((p[4:] for p in ws.split(";") if p.upper().startswith("URL=")), None)
    return f"{url.rstrip('/')}/{dc.dataset}" if url else None


def print_maps_of(aprx) -> list:
    names = {mf.map.name for l in aprx.listLayouts() for mf in l.listElements("MAPFRAME_ELEMENT") if mf.map}
    return [m for m in aprx.listMaps() if m.name in names]


def render(aprx, names: list[str], tag: str, log) -> None:
    from resize_aprx import safe_name
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    for lyt in aprx.listLayouts():
        if lyt.name in names:
            t = time.time()
            p = PREVIEWS / f"{safe_name(lyt.name)}_{tag}.png"
            if tag == "before" and p.exists():
                log.info(f"preview {p.name} exists from an earlier run, kept")
                continue
            lyt.exportToPNG(str(p), resolution=20)
            log.info(f"preview {p.name} ({time.time() - t:.0f} s)")


def localize_map(m, cfg: dict, log, dry: bool) -> dict:
    import arcpy
    from localize_aprx import set_connection

    by_url = features_by_url(cfg)
    where_of = {f["url"].rstrip("/"): f.get("where") for f in cfg["features"]}
    conn = f"DATABASE={cfg['vectors']}"
    n = {"repointed": 0, "converted": 0, "off": 0, "raster": 0, "kept": []}
    seen, changed, passes = set(), True, 0
    while changed and passes < 10:        # re-list after a layer is added or removed: the old list goes stale
        changed, passes = False, passes + 1
        for lyr in list(m.listLayers()):
            if lyr.isGroupLayer:
                continue
            try:
                cim = lyr.getDefinition("V3")
            except Exception:  # noqa: BLE001 - a sublayer object of a layer removed in this pass
                continue
            key = getattr(cim, "uRI", None) or lyr.longName   # Layer.URI is not supported on every layer type
            if key in seen:
                continue
            seen.add(key)
            kind = type(cim).__name__
            if kind == "CIMFeatureLayer":
                url = url_of(lyr)
                if url and url in by_url:
                    note = ""
                    want = where_of.get(url)
                    have = getattr(cim.featureTable, "definitionExpression", None) if getattr(cim, "featureTable", None) else None
                    if want and (have or "").replace(" ", "").lower() != want.replace(" ", "").lower():
                        note = f" (local copy holds only {want}; this layer's query is {have!r})"
                    log.info(f"    repoint {lyr.longName!r} -> {by_url[url]}{note}")
                    if not dry:
                        set_connection(lyr, conn, "FileGDB", by_url[url], False)
                    n["repointed"] += 1
                elif url:
                    n["kept"].append(f"{lyr.longName} ({url})")
                continue
            done = _localize_service_layer(m, lyr, cim, kind, cfg, by_url, conn, log, dry, n)
            if done and not dry:
                changed = True
                break                     # the list is stale now; start a new pass
    return n


def _localize_service_layer(m, lyr, cim, kind: str, cfg: dict, by_url: dict, conn: str, log, dry: bool, n: dict) -> bool:
    """Map image and image service layers. Returns True when the map's layer list changed."""
    from localize_aprx import set_connection
    if kind == "CIMMapImageLayer":
        base = cim.serviceConnection.url.rstrip("/")
        action = (cfg.get("map_image") or {}).get(base)
        if action == "off":
            log.info(f"    off     {lyr.longName!r} ({base})")
            if not dry:
                lyr.visible = False
            n["off"] += 1
            return False
        if action == "convert":
            subs = [s for s in (cim.subLayers or []) if s.visibility]
            missing = [s.name for s in subs if f"{base}/{s.subLayerID}" not in by_url]
            if missing:
                n["kept"].append(f"{lyr.longName}: no local copy for sublayers {missing}; left on the service")
                return False
            new_layers = []
            for s in subs:
                url = f"{base}/{s.subLayerID}"
                log.info(f"    convert {lyr.longName!r} / {s.name!r} -> {by_url[url]} (scales {s.minScale or 0}-{s.maxScale or 0})")
                if dry:
                    continue
                new = m.addDataFromPath(url)           # a feature layer carrying the service's renderer
                set_connection(new, conn, "FileGDB", by_url[url], False)
                new.name = s.name
                new.minThreshold, new.maxThreshold = s.minScale or 0, s.maxScale or 0
                new.visible = True
                new_layers.append(new)
            if not dry:
                for new in reversed(new_layers):       # keep the sublayer order, just above the old layer
                    m.moveLayer(lyr, new, "BEFORE")
                m.removeLayer(lyr)
            n["converted"] += len(subs)
            return True
        n["kept"].append(f"{lyr.longName} ({base}, map image)")
        return False
    if kind == "CIMImageServiceLayer":
        svc = cim.dataConnection.objectName
        r = (cfg.get("image_services") or {}).get(svc)
        if not r:
            n["kept"].append(f"{lyr.longName} ({svc}, image service)")
            return False
        tif = Path(cfg["rasters"]) / r["name"]
        if not tif.exists():
            n["kept"].append(f"{lyr.longName}: {tif} not exported yet")
            return False
        log.info(f"    raster  {lyr.longName!r} -> {tif.name} (transparency {cim.transparency}, blend {cim.blendingMode})")
        if not dry:
            new = m.addDataFromPath(str(tif))
            ncim = new.getDefinition("V3")
            ncim.colorizer, ncim.transparency, ncim.blendingMode, ncim.name = cim.colorizer, cim.transparency, cim.blendingMode, cim.name
            new.setDefinition(ncim)
            m.moveLayer(lyr, new, "BEFORE")
            m.removeLayer(lyr)
        n["raster"] += 1
        return True
    if getattr(cim, "visibility", True) and kind not in ("CIMVectorTileLayer",):
        n["kept"].append(f"{lyr.longName} ({kind})")
    return False


def cmd_apply(a, log) -> None:
    import arcpy
    cfg = load_cfg()
    path = Path(a.aprx)
    if not path.exists():
        sys.exit(f"{path} not found")
    t0 = time.time()
    out = Path(a.out) if a.out else path
    if not a.dry_run and out == path:
        bdir = path.parent / ".backups"
        bdir.mkdir(exist_ok=True)
        b = bdir / f"{path.stem}_before_localize_{dt.datetime.now():%Y%m%d_%H%M%S}.aprx"
        shutil.copy2(path, b)
        log.info(f"backup {b}")
    log.info(f"opening {path}" + (f" (result goes to {out}; {path.name} is not written)" if out != path else ""))
    aprx = arcpy.mp.ArcGISProject(str(path))
    maps = print_maps_of(aprx)
    log.info(f"opened in {time.time() - t0:.0f} s; {len(maps)} maps behind layouts: {[m.name for m in maps]}")
    if a.preview:
        render(aprx, a.preview, "before", log)
    totals = {}
    for m in maps:
        log.info(f"  map {m.name!r}")
        n = localize_map(m, cfg, log, a.dry_run)
        for k in ("repointed", "converted", "off", "raster"):
            totals[k] = totals.get(k, 0) + n[k]
        for k in n["kept"]:
            log.info(f"    still on the network: {k}")
    log.info(f"totals: {totals}" + (" (dry run, nothing written)" if a.dry_run else ""))
    if not a.dry_run:
        if out == path:
            aprx.save()
        else:
            aprx.saveACopy(str(out))
        log.info(f"saved {out} ({time.time() - t0:.0f} s)")
        if a.preview:
            render(aprx, a.preview, "after", log)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--replace", action="store_true", help="pull again what is already local")
    p = sub.add_parser("apply")
    p.add_argument("--aprx", default=str(LOCAL / "PROTECT_Maps_24x36.aprx"))
    p.add_argument("--out", default="", help="write the result here instead of saving --aprx in place (no backup needed; "
                                             "use it while --aprx is open in Pro)")
    p.add_argument("--preview", nargs="*", default=[], help="layout names to render before and after")
    p.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    log = get_logger(a.cmd)
    {"export": cmd_export, "apply": cmd_apply}[a.cmd](a, log)


if __name__ == "__main__":
    main()
