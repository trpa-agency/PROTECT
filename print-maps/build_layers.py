"""Rebuild the Results page's map layers in the print-map Pro project, from PROTECT_curated.gdb.

    python print-maps/build_layers.py --dry-run   # check layers.yaml and every source dataset; nothing saved
    python print-maps/build_layers.py             # back up the project, rebuild the Results group, save
    python print-maps/build_layers.py --lyrx      # also save each layer as print-maps/layers/<name>.lyrx

Run with ArcGIS Pro's Python on the server, with the project closed in Pro (the save needs it).
The project is project.aprx in print-maps/config.yaml. layers.yaml mirrors html/results.html: the
datasets, fields, class breaks, colors, and legend labels of each hazard tab's default view and
its surface. Renderers are written as CIM, with the exact breaks and a gray default symbol for
nulls ("not scored", as the page draws them), because the class-break API reclassifies fields
that hold only a few values.

The script owns one group layer (layers.yaml group:). Each run removes it and builds it again,
so symbology belongs in layers.yaml, not in hand edits in Pro. The rest of the map is left as it
is, except the layers in hide_after_build, which are turned off. Before saving, the project is
copied beside itself as <name>_backup_<timestamp>.aprx.
"""

from __future__ import annotations

import argparse
import re
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


def class_spec(spec: dict, lyr: dict) -> dict:
    c = lyr.get("classes")
    return (spec.get("class_sets") or {}).get(c) if isinstance(c, str) else c


def per_class(v, n: int) -> list:
    return list(v) if isinstance(v, (list, tuple)) else [v] * n


def validate(spec: dict) -> list[str]:
    errs, names = [], []
    if not spec.get("source_gdb"):
        errs.append("no source_gdb in layers.yaml and no curated.gdb in the root config.yaml")
    hexes = spec.get("colors") or {}

    def bad_color(c) -> bool:
        return c not in hexes and not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(c))

    errs += [f"color '{k}' is not #rrggbb" for k, v in hexes.items() if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(v))]
    for i, lyr in enumerate(spec.get("layers") or [], 1):
        tag = f"layer {i} ({lyr.get('name')})"
        names.append(lyr.get("name"))
        errs += [f"{tag}: needs {k}" for k in ("name", "group", "dataset") if not lyr.get(k)]
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
    errs += [f"layer name '{n}' is used twice" for n in sorted({n for n in names if n and names.count(n) > 1})]
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
        sym = new("CIMPolygonSymbol", symbolLayers=[
            new("CIMSolidStroke", color=rgb(spec, color, min(1.0, a + 0.1)), width=0.3 * scale),
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
               classificationMethod=arcpy.cim.ClassificationMethod.Manual, showInAscendingOrder=True,
               useDefaultSymbol=True, defaultLabel="not scored",
               defaultSymbol=symbol(spec, gray, "gray", 0, n))


# ---------- project ----------

def source_path(spec: dict, lyr: dict) -> str:
    return f"{spec['source_gdb'].rstrip(chr(92))}\\{lyr['dataset']}"


def missing_sources(spec: dict) -> list[str]:
    import arcpy
    return sorted({source_path(spec, lyr) for lyr in spec["layers"] if not arcpy.Exists(source_path(spec, lyr))})


def find_layer(m, long_name: str):
    return next((x for x in m.listLayers() if x.longName == long_name), None)


def build(aprx, spec: dict, log, lyrx_dir: Path | None) -> list[str]:
    """Remove and rebuild the owned group. Returns the problems; the caller saves only when there are none."""
    import arcpy
    m = next((x for x in aprx.listMaps() if x.name == spec["map"]), None)
    if m is None:
        return [f"no map '{spec['map']}' in the project"]
    missing = missing_sources(spec)
    if missing:
        return [f"source dataset not found: {p}" for p in missing]

    old = find_layer(m, spec["group"])
    if old is not None:
        m.removeLayer(old)
        log.info(f"Removed the previous '{spec['group']}' group")
    top = m.createGroupLayer(spec["group"])
    ref = find_layer(m, spec.get("place_before") or "")
    if ref is not None:
        m.moveLayer(ref, top, "BEFORE")
    top = find_layer(m, spec["group"])
    order = list(dict.fromkeys(lyr["group"] for lyr in spec["layers"]))
    for g in order:
        m.createGroupLayer(g, top)
    for prev, g in zip(order, order[1:]):   # nested groups land on top of their parent; put them in layers.yaml order
        m.moveLayer(find_layer(m, f"{spec['group']}\\{prev}"), find_layer(m, f"{spec['group']}\\{g}"), "AFTER")
    subs = {g: find_layer(m, f"{spec['group']}\\{g}") for g in order}
    built = []
    for lyr in spec["layers"]:
        g = lyr["group"]
        added = m.addDataFromPath(source_path(spec, lyr))
        added.name = lyr["name"]
        m.addLayerToGroup(subs[g], added, "BOTTOM")
        m.removeLayer(added)
        out = find_layer(m, f"{spec['group']}\\{g}\\{lyr['name']}")
        cim = out.getDefinition("V3")
        cim.renderer = renderer(spec, lyr)
        cim.transparency = round(100 * (1 - float(lyr.get("opacity", 1))))
        out.setDefinition(cim)
        out.visible = lyr.get("visible", True)
        built.append(out)
        log.info(f"{spec['group']}\\{g}\\{lyr['name']}: {lyr['dataset']}"
                 + (f" by {lyr['field']}" if lyr.get("field") else ""))
    for g, sub in subs.items():
        sub.visible = g == spec.get("show_group", g)
    for name in spec.get("hide_after_build") or []:
        hit = [x for x in m.listLayers() if x.longName == name]
        for x in hit:
            x.visible = False
        if not hit:
            log.warning(f"hide_after_build: no layer '{name}' in map '{m.name}'")
    if lyrx_dir:
        lyrx_dir.mkdir(parents=True, exist_ok=True)
        for out in built:
            path = lyrx_dir / (re.sub(r"[^A-Za-z0-9]+", "_", out.name).strip("_") + ".lyrx")
            arcpy.management.SaveToLayerFile(out, str(path), "ABSOLUTE")
        log.info(f"{len(built)} layer files -> {lyrx_dir}")
    return []


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aprx", help="the Pro project (overrides project.aprx in config.yaml)")
    ap.add_argument("--dry-run", action="store_true", help="check layers.yaml and the source datasets; save nothing")
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
    for lyr in spec["layers"]:
        renderer(spec, lyr)   # every CIM attribute checked before anything changes
    if args.dry_run:
        missing = missing_sources(spec)
        for p in missing:
            log.error(f"source dataset not found: {p}")
        log.info(f"{len(spec['layers'])} layers checked; {len(missing)} source datasets missing; nothing saved")
        raise SystemExit(1 if missing else 0)

    path = Path(aprx.filePath)
    backup = path.with_name(f"{path.stem}_backup_{time.strftime('%Y-%m-%d_%H%M%S')}.aprx")
    aprx.saveACopy(str(backup))
    log.info(f"Backup: {backup}")
    probs = build(aprx, spec, log, HERE / "layers" if args.lyrx else None)
    if probs:
        for p in probs:
            log.error(p)
        log.error("Nothing saved")
        raise SystemExit(1)
    try:
        aprx.save()
    except OSError as e:
        raise SystemExit(f"Save failed ({e}); close the project in Pro and rerun. The backup is {backup}")
    log.info(f"Saved {path}: '{spec['group']}' group with {len(spec['layers'])} layers")
    del aprx


if __name__ == "__main__":
    sys.exit(main())
