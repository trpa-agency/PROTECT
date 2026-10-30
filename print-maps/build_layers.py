"""Build the Results page's layers, maps, and layouts into the print-map Pro project, from PROTECT_curated.gdb.

    python print-maps/build_layers.py --dry-run   # check layers.yaml, the sources, and the template; nothing saved
    python print-maps/build_layers.py             # back up the project, rebuild what layers.yaml owns, save
    python print-maps/build_layers.py --lyrx      # also save each layer as print-maps/layers/<name>.lyrx

Run with ArcGIS Pro's Python on the server, with the project closed in Pro (the save needs it).
The project is project.aprx in print-maps/config.yaml. layers.yaml mirrors html/results.html: the
datasets, fields, class breaks, colors, and legend labels of each view it carries. Renderers are
written as CIM, with the exact breaks and a gray default symbol for nulls ("not scored", as the
page draws them), because the class-break API reclassifies fields that hold only a few values.

What layers.yaml owns is rebuilt on every run, so symbology belongs in layers.yaml, not in hand
edits in Pro:
  group:    one group layer in the map named by map: (the Results group in TRPA Standard Layers)
  maps:     whole maps, made when missing with their basemap; their owned group is rebuilt
  layouts:  copies of a template layout pointed at one of those maps, with an extent and text
The rest of the project is left as it is, except the layers in hide_after_build, which are turned
off. A layer or layout that fails is reported and the rest still build, so one run lists every
problem; the project is saved only when there are none, after it is copied beside itself as
<name>_backup_<timestamp>.aprx.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import time
from pathlib import Path

import yaml

from print_maps import HERE, get_logger, load_cfg, open_project

PX_TO_PT = 0.75   # the page's sizes are CSS pixels
FRAME = {"xmin": -5, "ymin": -5, "xmax": 5, "ymax": 5}
CIRCLE = {"curveRings": [[[0, 5], {"a": [[0, 5], [0, 0], 0, 1]}]]}   # Pro's own circle marker in that frame
SQUARE = {"rings": [[[-5, -5], [-5, 5], [5, 5], [5, -5], [-5, -5]]]}
KINDS = ("line", "point", "polygon")


def load_spec(cfg: dict) -> dict:
    spec = yaml.safe_load((HERE / "layers.yaml").read_text(encoding="utf-8"))
    spec["source_gdb"] = spec.get("source_gdb") or (cfg["_root"].get("curated") or {}).get("gdb", "")
    return spec


def groups(spec: dict) -> list[dict]:
    """Every owned group: the one in an existing map, then one per owned map."""
    out = [{"map": spec["map"], "group": spec["group"], "layers": spec.get("layers") or [],
            "place_before": spec.get("place_before"), "show_group": spec.get("show_group"),
            "hide_after_build": spec.get("hide_after_build") or []}] if spec.get("group") else []
    for m in spec.get("maps") or []:
        out.append({"map": m["name"], "group": m.get("group") or m["name"], "layers": m.get("layers") or [],
                    "owned_map": m})
    return out


def class_spec(spec: dict, lyr: dict) -> dict:
    c = lyr.get("classes")
    return (spec.get("class_sets") or {}).get(c) if isinstance(c, str) else c


def per_class(v, n: int) -> list:
    return list(v) if isinstance(v, (list, tuple)) else [v] * n


def validate(spec: dict) -> list[str]:
    errs = []
    if not spec.get("source_gdb"):
        errs.append("no source_gdb in layers.yaml and no curated.gdb in the root config.yaml")
    hexes = spec.get("colors") or {}

    def bad_color(c) -> bool:
        return c not in hexes and not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(c))

    errs += [f"color '{k}' is not #rrggbb" for k, v in hexes.items() if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(v))]
    for g in groups(spec):
        names = []
        for i, lyr in enumerate(g["layers"], 1):
            tag = f"{g['map']}, layer {i} ({lyr.get('name')})"
            names.append(lyr.get("name"))
            if not lyr.get("name"):
                errs.append(f"{tag}: needs name")
            if not (lyr.get("dataset") or lyr.get("source")):
                errs.append(f"{tag}: needs dataset (in source_gdb) or source (a path or URL)")
            if g.get("owned_map") is None and not lyr.get("group"):
                errs.append(f"{tag}: needs group (its hazard group)")
            if lyr.get("kind") not in KINDS:
                errs.append(f"{tag}: kind must be line, point, or polygon")
                continue
            if "simple" in lyr:
                if bad_color(lyr["simple"]):
                    errs.append(f"{tag}: unknown color '{lyr['simple']}'")
                continue
            if not lyr.get("field"):
                errs.append(f"{tag}: needs field, or simple: <color>")
            cs = class_spec(spec, lyr)
            if not cs or not cs.get("classes"):
                errs.append(f"{tag}: classes must name a class set or hold {{min, classes}}")
                continue
            rows = cs["classes"]
            if any(not isinstance(r, list) or len(r) != 3 for r in rows):
                errs.append(f"{tag}: each class is [upper bound, color, label]")
                continue
            ubs = [r[0] for r in rows]
            if any(not isinstance(u, (int, float)) for u in ubs) or ubs != sorted(set(ubs)):
                errs.append(f"{tag}: class upper bounds must be numbers that increase")
            elif cs.get("min") is not None and cs["min"] >= ubs[0]:
                errs.append(f"{tag}: min must be below the first upper bound")
            errs += [f"{tag}: unknown color '{r[1]}'" for r in rows if bad_color(r[1])]
            n = len(rows)
            for key, default in (("widths", spec.get("line_widths") if lyr["kind"] == "line" else None),
                                 ("sizes", None), ("alpha", None)):
                v = lyr.get(key, default)
                if isinstance(v, list) and len(v) != n:
                    errs.append(f"{tag}: {key} needs one value per class ({n})")
            if lyr["kind"] == "point" and lyr.get("sizes") is None:
                errs.append(f"{tag}: points need sizes")
        errs += [f"{g['map']}: layer name '{n}' is used twice" for n in sorted({n for n in names if n and names.count(n) > 1})]
    maps = {g["map"] for g in groups(spec)}
    for i, lay in enumerate(spec.get("layouts") or [], 1):
        tag = f"layout {i} ({lay.get('name')})"
        errs += [f"{tag}: needs {k}" for k in ("name", "from", "map") if not lay.get(k)]
        if lay.get("map") and lay["map"] not in maps:
            errs.append(f"{tag}: map '{lay['map']}' is not a map layers.yaml builds")
        ext = lay.get("extent") or {}
        if ext and not any(k in ext for k in ("layer", "bookmark", "xy")):
            errs.append(f"{tag}: extent needs layer, bookmark, or xy")
    return errs


# ---------- CIM ----------

def new(cls: str, **kw):
    """A CIM object with every attribute checked, so a misspelling fails here and not inside Pro."""
    import arcpy
    obj = arcpy.cim.CreateCIMObjectFromClassName(cls, "V3")
    for k, v in kw.items():
        if not hasattr(obj, k):
            raise AttributeError(f"{cls} has no attribute '{k}'")
        setattr(obj, k, v)
    return obj


def rgb(spec: dict, color: str, alpha: float = 1.0):
    h = (spec["colors"].get(color) or color).lstrip("#")
    return new("CIMRGBColor", values=[int(h[i:i + 2], 16) for i in (0, 2, 4)] + [round(100 * alpha)])


def symbol(spec: dict, lyr: dict, color: str, k: int, n: int):
    """CIM symbol reference for class k of n, sized for print."""
    import arcpy
    scale = PX_TO_PT * float(spec.get("print_scale", 1))
    if lyr["kind"] == "line":
        width = per_class(lyr.get("widths", spec.get("line_widths", 1)), n)[k] * scale
        stroke = new("CIMSolidStroke", color=rgb(spec, color), width=width)
        if lyr.get("dashed"):   # the page's short-dash paths
            stroke.effects = [new("CIMGeometricEffectDashes", dashTemplate=[4, 3])]
        sym = new("CIMLineSymbol", symbolLayers=[stroke])
    elif lyr["kind"] == "point":
        px = per_class(lyr["sizes"], n)[k]
        square = lyr.get("marker") == "square"
        ring = new("CIMSolidStroke", color=rgb(spec, "#ffffff", 0.95 if square else 0.9),
                   width=(1.0 if square and px >= 9 else 0.6) * scale)
        face = new("CIMPolygonSymbol", symbolLayers=[ring, new("CIMSolidFill", color=rgb(spec, color))],
                   angleAlignment=arcpy.cim.AngleAlignment.Map)
        marker = new("CIMVectorMarker", size=px * scale, frame=dict(FRAME), respectFrame=True,
                     scaleSymbolsProportionally=False, dominantSizeAxis3D=arcpy.cim.DominantSizeAxis.Y,
                     markerGraphics=[new("CIMMarkerGraphic", geometry=SQUARE if square else CIRCLE, symbol=face)])
        sym = new("CIMPointSymbol", symbolLayers=[marker], haloSize=1, scaleX=1)
    else:
        a = per_class(lyr.get("alpha", 1.0), n)[k]
        edge = lyr.get("outline_alpha", min(1.0, a + 0.1))
        sym = new("CIMPolygonSymbol", symbolLayers=[
            new("CIMSolidStroke", color=rgb(spec, color, edge), width=float(lyr.get("outline_width", 0.3)) * scale),
            new("CIMSolidFill", color=rgb(spec, color, a))])
    return new("CIMSymbolReference", symbol=sym)


def renderer(spec: dict, lyr: dict):
    """The page's renderer for one layer, as a CIM class-breaks (or simple) renderer."""
    import arcpy
    if "simple" in lyr:
        return new("CIMSimpleRenderer", symbol=symbol(spec, lyr, lyr["simple"], 0, 1),
                   label=lyr.get("label", lyr["name"]))
    cs = class_spec(spec, lyr)
    rows = cs["classes"]
    n = len(rows)
    breaks = [new("CIMClassBreak", upperBound=float(ub), label=str(label), symbol=symbol(spec, lyr, color, k, n))
              for k, (ub, color, label) in enumerate(rows)]
    # nulls and anything outside the classes draw gray, the page's "not scored"
    gray = dict(lyr, alpha=0.35) if lyr["kind"] == "polygon" else lyr
    return new("CIMClassBreaksRenderer", field=lyr["field"], breaks=breaks,
               minimumBreak=float(cs.get("min", -1)), classBreakType=arcpy.cim.ClassBreakType.GraduatedColor,
               classificationMethod=arcpy.cim.ClassificationMethod.Manual,
               showInAscendingOrder=not lyr.get("legend_descending", False),
               useDefaultSymbol=True, defaultLabel="not scored",
               defaultSymbol=symbol(spec, gray, "gray", 0, n))


def style_layer(spec: dict, out, lyr: dict) -> None:
    """Renderer, opacity, and draw order on a built layer, through its CIM definition."""
    import arcpy
    cim = out.getDefinition("V3")
    cim.renderer = renderer(spec, lyr)
    cim.transparency = round(100 * (1 - float(lyr.get("opacity", 1))))
    if lyr.get("sort"):   # ascending: the highest value draws last, on top (the bright top quarter)
        cim.featureSortInfos = [new("CIMFeatureSortInfo", fieldName=lyr["sort"],
                                    sortDirection=arcpy.cim.SortOrderType.Ascending)]
    out.setDefinition(cim)
    out.visible = lyr.get("visible", True)


# ---------- project ----------

def source_path(spec: dict, lyr: dict) -> str:
    return lyr.get("source") or f"{spec['source_gdb'].rstrip(chr(92))}\\{lyr['dataset']}"


def missing_sources(spec: dict) -> list[str]:
    import arcpy
    paths = {source_path(spec, lyr) for g in groups(spec) for lyr in g["layers"]}
    return sorted(p for p in paths if not p.lower().startswith("http") and not arcpy.Exists(p))


def find_layer(m, long_name: str):
    return next((x for x in m.listLayers() if x.longName == long_name), None)


def owned_map(aprx, g: dict, log):
    """The map an owned group goes in: an existing map, or an owned map made when missing."""
    import arcpy
    m = next((x for x in aprx.listMaps() if x.name == g["map"]), None)
    om = g.get("owned_map")
    if m is None and om:
        m = aprx.createMap(g["map"], "MAP")
        if om.get("spatial_reference"):
            m.spatialReference = arcpy.SpatialReference(int(om["spatial_reference"]))
        log.info(f"Created map '{g['map']}'")
    if m is not None and om and om.get("basemap") and not any(x.isBasemapLayer for x in m.listLayers()):
        try:
            m.addBasemap(om["basemap"])
            log.info(f"{g['map']}: basemap {om['basemap']}")
        except Exception as e:   # the gallery needs the portal; the map still builds
            log.warning(f"{g['map']}: basemap '{om['basemap']}' not added ({e}); add it from the Basemap gallery in Pro")
    return m


def build_group(m, spec: dict, g: dict, log) -> list:
    """Remove and rebuild one owned group in map m. Returns the built (layer, spec) pairs, top to bottom,
    and the problems; a layer that fails is reported and the rest still build, so one run lists them all."""
    name = g["group"]
    old = find_layer(m, name)
    if old is not None:
        m.removeLayer(old)
        log.info(f"{m.name}: removed the previous '{name}' group")
    top = m.createGroupLayer(name)
    ref = find_layer(m, g.get("place_before") or "")
    if ref is not None:
        m.moveLayer(ref, top, "BEFORE")
    order = list(dict.fromkeys(lyr["group"] for lyr in g["layers"] if lyr.get("group")))
    # moveLayer refuses to reorder nested groups (ValueError, Oct. 30), so they are made last-first:
    # a new nested group lands on top of its parent, which leaves them in layers.yaml order
    for sub in reversed(order):
        m.createGroupLayer(sub, find_layer(m, name))
    top = find_layer(m, name)
    subs = {sub: find_layer(m, f"{name}\\{sub}") for sub in order}
    made = [x.longName.split("\\")[1] for x in m.listLayers() if x.isGroupLayer and x.longName.count("\\") == 1
            and x.longName.startswith(name + "\\")]
    if made != order:
        log.warning(f"{m.name}: hazard groups came out as {made}, not {order} (draw order only)")
    built, probs = [], []
    for lyr in g["layers"]:
        parent = f"{name}\\{lyr['group']}" if lyr.get("group") else name
        step = "add"
        try:
            added = m.addDataFromPath(source_path(spec, lyr))
            added.name = lyr["name"]
            step = "group"
            m.addLayerToGroup(subs.get(lyr.get("group")) or top, added, "BOTTOM")
            m.removeLayer(added)
            out = find_layer(m, f"{parent}\\{lyr['name']}")
            step = "symbology"
            style_layer(spec, out, lyr)
        except Exception as e:
            probs.append(f"{m.name}: {parent}\\{lyr['name']}: {step} failed: {type(e).__name__}: {e}")
            continue
        built.append((out, lyr))
        log.info(f"{m.name}: {parent}\\{lyr['name']}: {lyr.get('dataset') or lyr.get('source')}"
                 + (f" by {lyr['field']}" if lyr.get("field") else ""))
    if g.get("show_group"):
        for sub, lyr in subs.items():
            lyr.visible = sub == g["show_group"]
    for hide in g.get("hide_after_build") or []:
        hit = [x for x in m.listLayers() if x.longName == hide]
        for x in hit:
            x.visible = False
        if not hit:
            log.warning(f"hide_after_build: no layer '{hide}' in map '{m.name}'")
    return built, probs


def build_layout(aprx, spec: dict, lay: dict, built: dict, log) -> list[str]:
    """Replace one owned layout: a copy of its template, framed on its map. Returns the problems."""
    import arcpy
    tpl = next((x for x in aprx.listLayouts() if x.name == lay["from"]), None)
    m = next((x for x in aprx.listMaps() if x.name == lay["map"]), None)
    if tpl is None or m is None:
        return [f"layout '{lay['name']}': no " + ("template layout '" + lay["from"] if tpl is None else "map '" + lay["map"]) + "'"]
    for old in [x for x in aprx.listLayouts() if x.name == lay["name"]]:
        aprx.deleteItem(old)
    lyt = aprx.copyItem(tpl, lay["name"])
    fname = lay.get("frame", "Map Frame")
    mf = next((e for e in lyt.listElements("MAPFRAME_ELEMENT") if e.name == fname), None)
    if mf is None:
        return [f"layout '{lay['name']}': no map frame '{fname}'"]
    mf.map = m
    probs = []
    ext = lay.get("extent") or {}
    if "layer" in ext:
        lyr = next((x for x in m.listLayers() if x.name == ext["layer"] or x.longName == ext["layer"]), None)
        if lyr is None:
            probs.append(f"layout '{lay['name']}': no layer '{ext['layer']}' in map '{m.name}' to zoom to")
        else:
            e = mf.getLayerExtent(lyr, False, True)
            pad = float(ext.get("margin_pct", 0)) / 100
            dx, dy = (e.XMax - e.XMin) * pad, (e.YMax - e.YMin) * pad
            mf.camera.setExtent(arcpy.Extent(e.XMin - dx, e.YMin - dy, e.XMax + dx, e.YMax + dy))
    elif "bookmark" in ext:
        bk = [b for b in m.listBookmarks() if b.name == ext["bookmark"]]
        if bk:
            mf.zoomToBookmark(bk[0])
        else:
            probs.append(f"layout '{lay['name']}': no bookmark '{ext['bookmark']}' in map '{m.name}'")
    elif "xy" in ext:
        mf.camera.setExtent(arcpy.Extent(*ext["xy"]))
    for name, value in (lay.get("text") or {}).items():
        hits = [e for e in lyt.listElements("TEXT_ELEMENT") if e.name == name]
        for e in hits:
            e.text = value or " "
        if not hits:
            probs.append(f"layout '{lay['name']}': no text element '{name}'")
    for name, vis in (lay.get("elements") or {}).items():
        hits = [e for e in lyt.listElements() if e.name == name]
        for e in hits:
            e.visible = bool(vis)
        if not hits:
            probs.append(f"layout '{lay['name']}': no element '{name}'")
    # the template's legend lists the old map's layers: clear it, then list the owned layers marked for it
    for lg in lyt.listElements("LEGEND_ELEMENT"):
        if lg.mapFrame and lg.mapFrame.name == fname:
            for item in list(lg.items):
                lg.removeItem(item)
            for out, lyr in built.get(lay["map"], []):
                if lyr.get("legend", True):
                    lg.addItem(out, "BOTTOM")
            lg.syncLayerVisibility = True
    log.info(f"Layout '{lay['name']}' from '{lay['from']}' on map '{m.name}'" + (f", zoomed to {ext}" if ext else ""))
    return probs


def build(aprx, spec: dict, log, lyrx_dir: Path | None) -> list[str]:
    """Rebuild everything layers.yaml owns. Returns the problems; the caller saves only when there are none."""
    import arcpy
    missing = missing_sources(spec)
    if missing:
        return [f"source dataset not found: {p}" for p in missing]
    built: dict[str, list] = {}
    probs = []
    for g in groups(spec):
        m = owned_map(aprx, g, log)
        if m is None:
            return [f"no map '{g['map']}' in the project"]
        built[g["map"]], p = build_group(m, spec, g, log)
        probs += p
    for lay in spec.get("layouts") or []:
        try:
            probs += build_layout(aprx, spec, lay, built, log)
        except Exception as e:
            probs.append(f"layout '{lay['name']}': {type(e).__name__}: {e}")
    if lyrx_dir:
        lyrx_dir.mkdir(parents=True, exist_ok=True)
        outs = [out for pairs in built.values() for out, _ in pairs]
        for out in outs:
            path = lyrx_dir / (re.sub(r"[^A-Za-z0-9]+", "_", out.name).strip("_") + ".lyrx")
            arcpy.management.SaveToLayerFile(out, str(path), "ABSOLUTE")
        log.info(f"{len(outs)} layer files -> {lyrx_dir}")
    return probs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aprx", help="the Pro project (overrides project.aprx in config.yaml)")
    ap.add_argument("--dry-run", action="store_true", help="check layers.yaml, the sources, and the templates; save nothing")
    ap.add_argument("--lyrx", action="store_true", help="also save each built layer to print-maps/layers/")
    args = ap.parse_args()

    cfg = load_cfg()
    log = get_logger(cfg, "build_layers")
    spec = load_spec(cfg)
    errs = validate(spec)
    if errs:
        for e in errs:
            log.error(f"layers.yaml: {e}")
        raise SystemExit(1)
    aprx = open_project(cfg, args.aprx, log)
    for g in groups(spec):
        for lyr in g["layers"]:
            renderer(spec, lyr)   # every CIM attribute checked before anything changes
    if args.dry_run:
        probs = [f"source dataset not found: {p}" for p in missing_sources(spec)]
        names = [x.name for x in aprx.listLayouts()]
        probs += [f"layout '{lay['name']}': no template layout '{lay['from']}'"
                  for lay in spec.get("layouts") or [] if lay["from"] not in names]
        for p in probs:
            log.error(p)
        n = sum(len(g["layers"]) for g in groups(spec))
        log.info(f"{n} layers and {len(spec.get('layouts') or [])} layouts checked; {len(probs)} problems; nothing saved")
        raise SystemExit(1 if probs else 0)

    probs = build(aprx, spec, log, HERE / "layers" if args.lyrx else None)
    if probs:
        for p in probs:
            log.error(p)
        log.error(f"{len(probs)} problems; nothing saved, the project is as it was")
        raise SystemExit(1)
    # the file on disk is still the project as it was until save(), so the backup is a plain copy of it
    path = Path(aprx.filePath)
    backup = path.with_name(f"{path.stem}_backup_{time.strftime('%Y-%m-%d_%H%M%S')}.aprx")
    shutil.copy2(path, backup)
    log.info(f"Backup: {backup}")
    try:
        aprx.save()
    except OSError as e:
        raise SystemExit(f"Save failed ({e}); close the project in Pro and rerun. The backup is {backup}")
    log.info(f"Saved {path}")
    del aprx


if __name__ == "__main__":
    sys.exit(main())
