"""Rebuild the PROTECT Pro project at another page size: a new .aprx with every map and layout imported from
map (.mapx) and layout (.pagx) files written from the source project, and every layout resized.

  python print-maps/resize_aprx.py export          # source .aprx -> <files>/maps/*.mapx + <files>/layouts/*.pagx + metrics
  python print-maps/resize_aprx.py build           # new .aprx from the files, layouts at --width x --height, then a reopen report
  python print-maps/resize_aprx.py report <aprx>   # page sizes, elements, and map frame scales of any project

Defaults (override with --src, --out, --files, --width, --height): C:\\GIS\\PROTECT_local\\PROTECT_Maps.aprx ->
C:\\GIS\\PROTECT_local\\PROTECT_Maps_24x36.aprx at 24 x 36 in. The source project is never written. The new project
starts as a copy of the source (home folder, default geodatabase, connections, toolboxes, every map and layout) and
its layouts are resized in place (build --mode copy, the default, a few minutes). --mode import instead strips the
copy and brings every map back from the .mapx files and every layout from the .pagx files (reuse_existing_maps, so a
layout frames the imported map of the same name); it takes about 75 s per 238-layer map, so use it only when the
files are the point. export is still useful on its own: the .mapx and .pagx files are reusable in any project.

Resize (uniform): every element scales by the one factor that fits the old page inside the new one about the
bottom-left corner (sizes, positions, text sizes). The map frame and its background then grow to the new page's
top margin, and the frame keeps the geography it showed across its width (recentered), so the map scale changes by
the width ratio and symbols drawn in points read larger relative to the map. See resize_layout().
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import re
import sys
import time
from pathlib import Path

LOCAL = Path(r"C:\GIS\PROTECT_local")
HERE = Path(__file__).resolve().parent


def get_logger(name: str) -> logging.Logger:
    log_dir = HERE / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("resize_aprx")
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    for h in (logging.StreamHandler(sys.stdout),
              logging.FileHandler(log_dir / f"resize_aprx_{name}_{dt.datetime.now():%Y%m%d_%H%M%S}.log", encoding="utf-8")):
        h.setFormatter(fmt)
        log.addHandler(h)
    sys.stdout.reconfigure(line_buffering=True)
    return log


def safe_name(name: str) -> str:
    return re.sub(r"[^\w\- ]+", "_", name).strip()


def metrics(aprx) -> dict:
    """Page size, every element's box and text size, and each map frame's scale and extent, per layout."""
    out = {}
    for lyt in aprx.listLayouts():
        els = []
        for e in lyt.listElements():
            d = {"type": e.type, "name": e.name,
                 "x": round(e.elementPositionX, 3), "y": round(e.elementPositionY, 3),
                 "w": round(e.elementWidth, 3), "h": round(e.elementHeight, 3)}
            if e.type == "TEXT_ELEMENT":
                d["textSize"] = round(e.textSize, 2)
            if e.type == "MAPFRAME_ELEMENT":
                ext = e.camera.getExtent()
                d.update(map=e.map.name if e.map else None, scale=round(e.camera.scale),
                         extent=[round(v) for v in (ext.XMin, ext.YMin, ext.XMax, ext.YMax)])
            els.append(d)
        out[lyt.name] = {"page": [lyt.pageWidth, lyt.pageHeight, lyt.pageUnits], "elements": els}
    return out


def print_report(aprx, log, before: dict | None = None) -> None:
    log.info(f"maps ({len(aprx.listMaps())}): {[m.name for m in aprx.listMaps()]}")
    log.info(f"layouts ({len(aprx.listLayouts())}):")
    for name, lay in metrics(aprx).items():
        w, h, u = lay["page"]
        mfs = [e for e in lay["elements"] if e["type"] == "MAPFRAME_ELEMENT"]
        frame = ", ".join(f"{e['name']} -> {e['map']} 1:{e['scale']:,} box {e['w']}x{e['h']} at ({e['x']},{e['y']})" for e in mfs)
        log.info(f"  {name!r}: {w:g} x {h:g} {u}; {frame}")
        if before and name in before:
            b = {e["name"]: e for e in before[name]["elements"]}
            for e in lay["elements"]:
                o = b.get(e["name"])
                if o and e["type"] == "TEXT_ELEMENT" and o.get("textSize") != e.get("textSize"):
                    log.info(f"      text {e['name']!r}: {o['textSize']} -> {e['textSize']} pt")


# ---------------------------------------------------------------- export
def cmd_export(a, log) -> None:
    import arcpy
    files = Path(a.files)
    (files / "maps").mkdir(parents=True, exist_ok=True)
    (files / "layouts").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log.info(f"opening {a.src}")
    aprx = arcpy.mp.ArcGISProject(a.src)
    log.info(f"opened in {time.time() - t0:.0f} s")
    print_report(aprx, log)
    (files / "metrics_source.json").write_text(json.dumps(metrics(aprx), indent=1), encoding="utf-8")
    manifest = {"source": a.src, "maps": [], "layouts": []}
    for m in aprx.listMaps():
        p = files / "maps" / f"{safe_name(m.name)}.mapx"
        t = time.time()
        m.exportToMAPX(str(p))
        manifest["maps"].append({"name": m.name, "file": p.name})
        log.info(f"map {m.name!r} -> {p.name} ({p.stat().st_size / 1e6:.1f} MB, {time.time() - t:.0f} s)")
    for lyt in aprx.listLayouts():
        p = files / "layouts" / f"{safe_name(lyt.name)}.pagx"
        t = time.time()
        lyt.exportToPAGX(str(p))
        manifest["layouts"].append({"name": lyt.name, "file": p.name,
                                    "maps": [mf.map.name for mf in lyt.listElements("MAPFRAME_ELEMENT") if mf.map]})
        log.info(f"layout {lyt.name!r} -> {p.name} ({p.stat().st_size / 1e6:.1f} MB, {time.time() - t:.0f} s)")
    (files / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    log.info(f"export done in {time.time() - t0:.0f} s: {len(manifest['maps'])} maps, {len(manifest['layouts'])} layouts -> {files}")


# ---------------------------------------------------------------- resize
def resize_layout(lyt, width: float, height: float, log) -> dict:
    """Resize one layout to width x height (page units) with a uniform scale; see the module docstring."""
    import arcpy
    old_w, old_h = lyt.pageWidth, lyt.pageHeight
    s = min(width / old_w, height / old_h)
    frames = lyt.listElements("MAPFRAME_ELEMENT")
    main = max(frames, key=lambda e: e.elementWidth * e.elementHeight) if frames else None
    # what the main frame shows now, so it keeps the same geography across its width afterwards
    old_ext = main.camera.getExtent() if main else None
    old_margins = None
    if main:
        old_margins = {"left": main.elementPositionX, "bottom": main.elementPositionY,
                       "right": old_w - main.elementPositionX - main.elementWidth,
                       "top": old_h - main.elementPositionY - main.elementHeight}
    backgrounds = [e for e in lyt.listElements("GRAPHIC_ELEMENT")
                   if main and abs(e.elementWidth - main.elementWidth) < 0.05 and abs(e.elementHeight - main.elementHeight) < 0.05
                   and abs(e.elementPositionX - main.elementPositionX) < 0.05 and abs(e.elementPositionY - main.elementPositionY) < 0.05]

    lyt.pageWidth, lyt.pageHeight = width, height
    notes = []
    for e in lyt.listElements():
        try:
            x, y, w, h = e.elementPositionX, e.elementPositionY, e.elementWidth, e.elementHeight
            if e.type == "TEXT_ELEMENT":
                e.textSize = e.textSize * s          # point text: size follows the font, not the box
                e.elementPositionX, e.elementPositionY = x * s, y * s
            else:
                e.elementWidth, e.elementHeight = w * s, h * s
                e.elementPositionX, e.elementPositionY = x * s, y * s
        except Exception as ex:                       # noqa: BLE001 - keep going, report what did not scale
            notes.append(f"{e.type} {e.name!r}: {ex}")
    extra = 0.0
    if main:
        # grow the main frame (and its background) up to the new page's top margin, keeping the scaled margins
        new_h = height - old_margins["bottom"] * s - old_margins["top"] * s
        extra = new_h - main.elementHeight
        for e in [main] + backgrounds:
            e.elementHeight = new_h
        # same geography across the width, recentered: the frame is taller in proportion, so it shows more north-south
        cx, cy = (old_ext.XMin + old_ext.XMax) / 2, (old_ext.YMin + old_ext.YMax) / 2
        half_w = (old_ext.XMax - old_ext.XMin) / 2
        half_h = half_w * main.elementHeight / main.elementWidth
        main.camera.setExtent(arcpy.Extent(cx - half_w, cy - half_h, cx + half_w, cy + half_h))
        # elements sitting on the map body (not the bottom block) move up with the recentered geography
        for e in lyt.listElements():
            if e is main or any(e.name == b.name and e.type == b.type for b in backgrounds) or e.type == "MAPFRAME_ELEMENT":
                continue
            if e.elementPositionY > 0.3 * height:
                e.elementPositionY += extra / 2
    log.info(f"  {lyt.name!r}: {old_w:g}x{old_h:g} -> {width:g}x{height:g}, scale {s:.4f}, frame +{extra:.2f} in tall"
             + (f", map 1:{round(main.camera.scale):,}" if main else ""))
    for n in notes:
        log.warning(f"    not scaled: {n}")
    return {"scale": s, "extra": extra, "notes": notes}


# ---------------------------------------------------------------- build
def cmd_build(a, log) -> None:
    import arcpy
    files = Path(a.files)
    manifest = json.loads((files / "manifest.json").read_text(encoding="utf-8")) if a.mode == "import" else None
    out = Path(a.out)
    if out.exists() and not a.overwrite:
        sys.exit(f"{out} exists; pass --overwrite to replace it")
    t0 = time.time()
    log.info(f"opening {a.src}; the new project starts as a copy of it ({a.mode} mode)")
    src = arcpy.mp.ArcGISProject(a.src)
    want_maps = {m.name for m in src.listMaps()}
    want_lyts = {l.name for l in src.listLayouts()}
    log.info(f"opened in {time.time() - t0:.0f} s ({len(want_maps)} maps, {len(want_lyts)} layouts); saving a copy to {out}")
    src.saveACopy(str(out))
    del src
    aprx = arcpy.mp.ArcGISProject(str(out))
    if a.mode == "import":
        # strip the copy and bring every map and layout back from the files written by `export`
        for lyt in aprx.listLayouts():
            aprx.deleteItem(lyt)
        for m in aprx.listMaps():
            aprx.deleteItem(m)
        log.info(f"stripped: {len(aprx.listMaps())} maps, {len(aprx.listLayouts())} layouts left")
        for item in manifest["maps"]:
            t = time.time()
            aprx.importDocument(str(files / "maps" / item["file"]))
            log.info(f"imported map {item['name']!r} ({time.time() - t:.0f} s)")
        names = [m.name for m in aprx.listMaps()]
        for item in manifest["maps"]:
            if item["name"] not in names:
                log.warning(f"map {item['name']!r} did not come back under its name; maps now: {names}")
        for item in manifest["layouts"]:
            t = time.time()
            aprx.importDocument(str(files / "layouts" / item["file"]), reuse_existing_maps=True)
            log.info(f"imported layout {item['name']!r} ({time.time() - t:.0f} s)")
        dupes = [m.name for m in aprx.listMaps() if m.name not in names]
        if dupes:
            log.warning(f"layout import added maps instead of reusing: {dupes}")
        want_maps, want_lyts = {m["name"] for m in manifest["maps"]}, {l["name"] for l in manifest["layouts"]}
    log.info(f"resizing {len(aprx.listLayouts())} layouts to {a.width:g} x {a.height:g}")
    for lyt in aprx.listLayouts():
        resize_layout(lyt, a.width, a.height, log)
    aprx.save()
    log.info(f"saved {out} in {time.time() - t0:.0f} s; reopening to verify")
    del aprx
    chk = arcpy.mp.ArcGISProject(str(out))
    src_metrics = files / "metrics_source.json"
    before = json.loads(src_metrics.read_text(encoding="utf-8")) if src_metrics.exists() else None
    print_report(chk, log, before)
    files.mkdir(parents=True, exist_ok=True)
    (files / "metrics_new.json").write_text(json.dumps(metrics(chk), indent=1), encoding="utf-8")
    have_maps, have_lyts = {m.name for m in chk.listMaps()}, {l.name for l in chk.listLayouts()}
    bad = [l.name for l in chk.listLayouts() if (round(l.pageWidth, 2), round(l.pageHeight, 2)) != (round(a.width, 2), round(a.height, 2))]
    log.info(f"check: maps missing {sorted(want_maps - have_maps)}, extra {sorted(have_maps - want_maps)}; "
             f"layouts missing {sorted(want_lyts - have_lyts)}, extra {sorted(have_lyts - want_lyts)}; not {a.width:g}x{a.height:g}: {bad}")
    log.info(f"done in {time.time() - t0:.0f} s")


def cmd_report(a, log) -> None:
    import arcpy
    print_report(arcpy.mp.ArcGISProject(a.aprx), log)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=str(LOCAL / "PROTECT_Maps.aprx"))
    ap.add_argument("--out", default=str(LOCAL / "PROTECT_Maps_24x36.aprx"))
    ap.add_argument("--files", default=str(LOCAL / "PROTECT_Maps_files"), help="where the .mapx and .pagx files go")
    ap.add_argument("--width", type=float, default=24.0)
    ap.add_argument("--height", type=float, default=36.0)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("export")
    b = sub.add_parser("build")
    b.add_argument("--overwrite", action="store_true", help="replace --out when it exists")
    b.add_argument("--mode", choices=["copy", "import"], default="copy",
                   help="copy: resize the layouts in a copy of the source (default, minutes); "
                        "import: strip the copy and re-import every map and layout from the files written by export (slow)")
    r = sub.add_parser("report")
    r.add_argument("aprx")
    a = ap.parse_args()
    log = get_logger(a.cmd)
    {"export": cmd_export, "build": cmd_build, "report": cmd_report}[a.cmd](a, log)


if __name__ == "__main__":
    main()
