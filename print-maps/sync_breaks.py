"""sync_breaks.py - put the page's class breaks on the print layers already built in the Pro project.

build_layers.py builds the Results layers once from layers.yaml and keeps what is there, so a break or a
legend label changed on vulnerability-assessment.html after a build (the Oct. 30 wildfire breaks; the Nov. 2 debris flow
breaks, decision 34) never reaches the project. This rewrites, in place, the class bounds, labels, and
minimum break of every class-breaks layer whose field layers.yaml classes, in every map (the template
map and each copied print map), and keeps the symbols as finished by hand. Unique-value layers (V_class)
and layers whose class count differs from layers.yaml are reported, not changed.

  python sync_breaks.py --aprx C:\\GIS\\PROTECT_local\\PROTECT_Maps_24x36_local.aprx
      [--dry-run] [--out OTHER.aprx] [--maps NAME ...] [--all-layers]
      [--check-export LAYOUT ... --check-dir DIR --dpi 40]

Saving in place copies the project to .backups/ first. --check-export writes a PNG of each named layout
after the save, for a look at the legend and the classes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sys
import time
from pathlib import Path

from build_layers import class_spec, groups, load_spec
from print_maps import HERE, get_logger, load_cfg


def wanted_breaks(spec: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    """Every classed layer in layers.yaml as {name, field, min, bounds: [(upper bound, label, color)]}:
    by its long name (group\\subgroup\\layer, the same in every copied map), and by field for the
    fields only one layer classes (the fallback when a layer was renamed by hand). hz_class is shared
    by the hazard surfaces with different labels, so it is matched by name only."""
    by_name: dict[str, dict] = {}
    by_field: dict[str, list[dict]] = {}
    for g in groups(spec):
        for lyr in g["layers"]:
            if "classes" not in lyr or "field" not in lyr:
                continue
            cs = class_spec(spec, lyr)
            name = "\\".join(x for x in (g["group"], lyr.get("group"), lyr["name"]) if x)
            w = {"name": name, "field": lyr["field"], "min": float(cs.get("min", -1)),
                 "bounds": [(float(ub), str(label), str(color)) for ub, color, label in cs["classes"]]}
            by_name[name] = w
            by_field.setdefault(lyr["field"], []).append(w)
    return by_name, {f: ws[0] for f, ws in by_field.items() if len(ws) == 1}


def owned_prefixes(spec: dict) -> list[str]:
    names = [spec.get("group", "Results")] + [m.get("group") for m in spec.get("maps") or [] if m.get("group")]
    return [n + "\\" for n in names]


def current_breaks(r) -> tuple[float, list[tuple[float, str]]]:
    return float(r.minimumBreak), [(float(b.upperBound), str(b.label or "")) for b in (r.breaks or [])]


def sync_map(m, by_name: dict, by_field: dict, prefixes: list[str], all_layers: bool, log, dry_run: bool) -> dict:
    n = {"changed": 0, "current": 0, "skipped": 0}
    for lyr in m.listLayers():
        if lyr.isGroupLayer or lyr.isBasemapLayer or not lyr.isFeatureLayer:
            continue
        if not all_layers and not any(lyr.longName.startswith(p) for p in prefixes):
            continue
        cim = lyr.getDefinition("V3")
        r = getattr(cim, "renderer", None)
        if r is None or type(r).__name__ != "CIMClassBreaksRenderer":
            continue
        w = by_name.get(lyr.longName) or by_field.get(r.field)
        if not w:
            continue
        if w["field"] != r.field:
            log.warning(f"    {lyr.longName}: draws {r.field}, layers.yaml has {w['field']}; left as is")
            n["skipped"] += 1
            continue
        cur_min, cur = current_breaks(r)
        want = [(ub, label) for ub, label, _ in w["bounds"]]
        if len(cur) != len(want):
            log.warning(f"    {lyr.longName}: {len(cur)} classes in the project, {len(want)} in layers.yaml; left as is")
            n["skipped"] += 1
            continue
        if cur == want and cur_min == w["min"]:
            n["current"] += 1
            continue
        log.info(f"    {lyr.longName} ({r.field}): {cur_min} {cur} -> {w['min']} {want}")
        if not dry_run:
            r.minimumBreak = w["min"]
            for b, (ub, label) in zip(r.breaks, want):
                b.upperBound = ub
                b.label = label
            lyr.setDefinition(cim)
        n["changed"] += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aprx", required=True, help="the Pro project to update")
    ap.add_argument("--out", default="", help="write the result here instead of saving --aprx in place")
    ap.add_argument("--dry-run", action="store_true", help="report what would change; save nothing")
    ap.add_argument("--maps", nargs="*", metavar="NAME", help="only these maps (default: every map in the project)")
    ap.add_argument("--all-layers", action="store_true", help="look at every feature layer, not only the owned groups")
    ap.add_argument("--check-export", nargs="*", metavar="LAYOUT", default=[], help="after saving, export these layouts to PNG")
    ap.add_argument("--check-dir", default=str(HERE / "logs"), help="where the check PNGs go (default: print-maps/logs)")
    ap.add_argument("--dpi", type=int, default=40, help="check export resolution")
    a = ap.parse_args()

    cfg = load_cfg()
    log = get_logger(cfg, "sync_breaks")
    spec = load_spec(cfg)
    by_name, by_field = wanted_breaks(spec)
    for w in by_name.values():
        log.info(f"layers.yaml {w['name']} ({w['field']}): min {w['min']} {[(ub, label) for ub, label, _ in w['bounds']]}")
    path = Path(a.aprx)
    if not path.exists():
        sys.exit(f"{path} not found")
    out = Path(a.out) if a.out else path
    if not a.dry_run and out == path:
        bdir = path.parent / ".backups"
        bdir.mkdir(exist_ok=True)
        b = bdir / f"{path.stem}_before_sync_breaks_{dt.datetime.now():%Y%m%d_%H%M%S}.aprx"
        shutil.copy2(path, b)
        log.info(f"backup {b}")
    import arcpy
    t0 = time.time()
    log.info(f"opening {path}" + (f" (result goes to {out})" if out != path else ""))
    aprx = arcpy.mp.ArcGISProject(str(path))
    maps = aprx.listMaps()
    if a.maps:
        maps = [m for m in maps if m.name in a.maps]
        missing = set(a.maps) - {m.name for m in maps}
        if missing:
            log.warning(f"maps not in the project: {sorted(missing)}")
    log.info(f"opened in {time.time() - t0:.0f} s; {len(maps)} maps")
    prefixes = owned_prefixes(spec)
    totals = {"changed": 0, "current": 0, "skipped": 0}
    for m in maps:
        log.info(f"  map {m.name!r}")
        n = sync_map(m, by_name, by_field, prefixes, a.all_layers, log, a.dry_run)
        for k in totals:
            totals[k] += n[k]
        log.info(f"    {n['changed']} changed, {n['current']} already current, {n['skipped']} skipped")
    log.info(f"totals: {totals}" + (" (dry run, nothing written)" if a.dry_run else ""))
    if a.dry_run:
        pass
    elif totals["changed"]:
        if out == path:
            aprx.save()
        else:
            aprx.saveACopy(str(out))
        log.info(f"saved {out} ({time.time() - t0:.0f} s)")
    else:
        log.info("nothing to change; not saved")
    for name in a.check_export:
        lay = next((x for x in aprx.listLayouts() if x.name == name), None)
        if lay is None:
            log.warning(f"check export: no layout {name!r}")
            continue
        stem = "".join(c if c.isalnum() else "_" for c in name).strip("_")
        png = Path(a.check_dir) / f"sync_breaks_{stem}_{dt.datetime.now():%Y%m%d_%H%M%S}.png"
        t1 = time.time()
        lay.exportToPNG(str(png), resolution=a.dpi)
        log.info(f"check export {png} ({time.time() - t1:.0f} s)")


if __name__ == "__main__":
    main()
