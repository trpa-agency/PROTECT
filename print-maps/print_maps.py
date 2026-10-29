"""Print maps for the PROTECT workshops, exported from one template layout in an ArcGIS Pro project.

    python print-maps/print_maps.py inspect        # maps, layers, layouts, elements, bookmarks in the project
    python print-maps/print_maps.py check          # resolve every sheet against the project; nothing is exported
    python print-maps/print_maps.py export         # every enabled sheet, every export it names
    python print-maps/print_maps.py export --only sr28 --exports screen   # one corridor, screen PDFs only
    python print-maps/print_maps.py build          # a copy of the project with a layout per sheet, to finish by hand

Run with ArcGIS Pro's Python (arcgispro-py3) while signed in to Pro, so arcpy has a license. The
project, the template, the exports, and the sheet list are in print-maps/config.yaml.

For each sheet the script restores the template as authored, points each map frame at its map,
turns on exactly the layers the sheet lists (parent groups and the contents of a listed group
included; basemaps left alone), sets the extent, fills the text elements, shows or hides elements,
checks the visible layers, and exports. The project is never saved. `build` instead writes
<project>_sheets.aprx beside the project: a layout per sheet, and a copy of each map whose layers
the sheet sets, so a sheet can be finished by hand in Pro.

Restricted data: NDOT culvert rows need NDOT sign-off before any display. A sheet does not export
when a visible layer reads a restricted source, shows a row that matches restricted.row_checks, or
reads one of the analysis geodatabase's culvert datasets without a field to check (config.yaml
restricted:). --allow-restricted, after sign-off, writes only to
paths.restricted_outputs, which must be outside the repo.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from datetime import date
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TODAY = date.today()
MONTHS = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]
EXT = {"PDF": ".pdf", "PNG": ".png", "JPEG": ".jpg", "TIFF": ".tif", "SVG": ".svg", "EPS": ".eps", "AIX": ".aix"}


def house_date(d: date) -> str:
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def here_path(p: str) -> Path:
    return Path(p) if Path(p).is_absolute() else HERE / p


def load_cfg() -> dict:
    cfg = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
    root = REPO / "config.yaml"
    cfg["_root"] = yaml.safe_load(root.read_text(encoding="utf-8")) if root.exists() else {}
    made, cfg["_matrix_errors"] = expand_matrix(cfg)
    cfg["sheets"] = made + list(cfg.get("sheets") or [])
    return cfg


def expand_matrix(cfg: dict) -> tuple[list[dict], list[str]]:
    """Sheets for every corridor x hazard x version in each sheet_matrix entry, ids <corridor>_<hazard>_<version>."""
    cors, hzs, vers = cfg.get("corridors") or {}, cfg.get("hazards") or {}, cfg.get("versions") or {}
    out, errs = [], []
    for i, mx in enumerate(cfg.get("sheet_matrix") or [], 1):
        cs, hs, vs = mx.get("corridors") or list(cors), mx.get("hazards") or list(hzs), mx.get("versions") or list(vers)
        missing = [f"{kind} '{k}'" for kind, keys, tbl in (("corridor", cs, cors), ("hazard", hs, hzs), ("version", vs, vers))
                   for k in keys if k not in tbl]
        if missing:
            errs.append(f"sheet_matrix entry {i}: no {', '.join(missing)}")
            continue
        for c in cs:
            for h in hs:
                for v in vs:
                    cor, hz, ver = cors[c], hzs[h], vers[v]
                    names = {"corridor": cor.get("label", c), "hazard": hz.get("label", h)}
                    s = {"id": f"{c}_{h}_{v}", **names,
                         **{k: val for k, val in ver.items() if k not in ("legend", "assets")},
                         "legend": fill(ver.get("legend", "{hazard}"), names),
                         "layers": list(hz.get("exposure") or []) + (list(hz.get("assets") or []) if ver.get("assets") else [])}
                    if cor.get("title"):
                        s["text"] = {"Title": cor["title"]}
                    if cor.get("bookmark"):
                        s["extent"] = {"bookmark": cor["bookmark"]}
                    out.append(s)
    return out, errs


def get_logger(cfg: dict) -> logging.Logger:
    logs = here_path(cfg["paths"].get("logs", "logs"))
    logs.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("print_maps")
    log.setLevel(logging.INFO)
    log.handlers.clear()
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    for h in (logging.StreamHandler(sys.stdout),
              logging.FileHandler(logs / f"print_maps_{time.strftime('%Y-%m-%d_%H%M%S')}.log", encoding="utf-8")):
        h.setFormatter(fmt)
        log.addHandler(h)
    return log


# ---------- config ----------

def validate(cfg: dict, only: list[str] | None, export_names: list[str] | None) -> list[str]:
    """Config errors that need no project open."""
    errs, ids = list(cfg.get("_matrix_errors") or []), [s.get("id") for s in cfg.get("sheets", [])]
    exdefs = cfg.get("exports", {})
    if any(not i for i in ids):
        errs.append("every sheet needs an id")
    errs += [f"sheet id '{i}' is used twice" for i in sorted({i for i in ids if i and ids.count(i) > 1})]
    for name, ex in exdefs.items():
        if str(ex.get("format", "")).upper() not in EXT:
            errs.append(f"export '{name}': format must be one of {', '.join(EXT)}")
        if ex.get("combine") and str(ex.get("format", "")).upper() != "PDF":
            errs.append(f"export '{name}': combine works for PDF only")
    for s in cfg.get("sheets", []):
        for n in sheet_spec(cfg, s).get("exports") or []:
            if n not in exdefs:
                errs.append(f"sheet '{s.get('id')}': no export named '{n}'")
    errs += [f"--exports: no export named '{n}'" for n in export_names or [] if n not in exdefs]
    errs += [f"--only: no sheet matches '{o}'" for o in only or [] if not any(matches(i or "", o) for i in ids)]
    return errs


def matches(sheet_id: str, key: str) -> bool:
    return sheet_id == key or sheet_id.startswith(f"{key}_")


def pick_sheets(cfg: dict, only: list[str] | None) -> list[dict]:
    if only:
        return [s for s in cfg["sheets"] if any(matches(s["id"], o) for o in only)]
    return [s for s in cfg["sheets"] if s.get("enabled", True)]


def sheet_spec(cfg: dict, sheet: dict) -> dict:
    d = cfg.get("defaults", {})
    spec = {**d, **sheet}
    for k in ("text", "elements", "frames"):
        spec[k] = {**(d.get(k) or {}), **(sheet.get(k) or {})}
    return spec


def tokens_for(cfg: dict, spec: dict) -> dict:
    plain = {k: v for k, v in spec.items() if isinstance(v, (str, int, float)) and not isinstance(v, bool)}
    return {"date": house_date(TODAY), **(cfg.get("tokens") or {}), **plain}


def fill(template: str, tokens: dict) -> str:
    """{name} from tokens; unknown names are left as written (dynamic text tags pass through)."""
    return re.sub(r"\{(\w+)\}", lambda m: str(tokens.get(m.group(1), m.group(0))), str(template))


# ---------- project ----------

def open_project(cfg: dict, override: str | None, log: logging.Logger):
    p = override or cfg["project"].get("aprx")
    if not p:
        raise SystemExit("Set project.aprx in print-maps/config.yaml, or pass --aprx")
    if p != "CURRENT" and not Path(p).exists():
        raise SystemExit(f"Project not found: {p} (is F: connected?)")
    try:
        import arcpy
    except RuntimeError as e:   # "The Product License has not been initialized"
        raise SystemExit(f"arcpy did not start ({e}); open ArcGIS Pro, sign in, and rerun")
    aprx = arcpy.mp.ArcGISProject(p)
    log.info(f"Project: {aprx.filePath}")
    if cfg["project"].get("pagx"):
        pagx = here_path(cfg["project"]["pagx"])
        aprx.importDocument(str(pagx), reuse_existing_maps=True)
        log.info(f"Template imported from {pagx}")
    return aprx


def template_name(cfg: dict) -> str:
    if not cfg["project"].get("layout"):
        raise SystemExit("Set project.layout in print-maps/config.yaml (inspect lists the layouts)")
    return cfg["project"]["layout"]


def find_layout(aprx, name: str):
    hits = [lyt for lyt in aprx.listLayouts() if lyt.name == name]
    if not hits:
        raise SystemExit(f"No layout '{name}' in the project; layouts: {', '.join(l.name for l in aprx.listLayouts())}")
    return hits[0]


def snapshot(aprx, layouts) -> dict:
    """The template as authored, so every sheet starts from the same state whatever ran before it."""
    st = {"layers": [(lyr, lyr.visible) for m in aprx.listMaps() for lyr in m.listLayers()],
          "text": [], "elements": [], "frames": []}
    for lyt in layouts:
        st["text"] += [(e, e.text) for e in lyt.listElements("TEXT_ELEMENT")]
        st["elements"] += [(e, e.visible) for e in lyt.listElements()]
        st["frames"] += [(mf, mf.map, mf.camera.getExtent()) for mf in lyt.listElements("MAPFRAME_ELEMENT") if mf.map]
    return st


def restore(st: dict) -> None:
    for lyr, vis in st["layers"]:
        lyr.visible = vis
    for e, txt in st["text"]:
        e.text = txt
    for e, vis in st["elements"]:
        e.visible = vis
    for mf, m, ext in st["frames"]:
        mf.map = m
        mf.camera.setExtent(ext)


def resolve_layers(m, names: list[str]) -> tuple[list, list[str]]:
    """Layers by full name (Group\\Layer) or by a name used once in the map."""
    lyrs = m.listLayers()
    by_long = {lyr.longName: lyr for lyr in lyrs}
    by_name: dict[str, list] = {}
    for lyr in lyrs:
        by_name.setdefault(lyr.name, []).append(lyr)
    found, probs = [], []
    for n in names:
        if n in by_long:
            found.append(by_long[n])
        elif len(by_name.get(n, [])) == 1:
            found.append(by_name[n][0])
        elif n in by_name:
            probs.append(f"'{n}' is {len(by_name[n])} layers in map '{m.name}'; use the full name: "
                         + ", ".join(lyr.longName for lyr in by_name[n]))
        else:
            probs.append(f"no layer '{n}' in map '{m.name}'")
    return found, probs


def under(long_name: str, parents) -> bool:
    return any(long_name == p or long_name.startswith(p + "\\") for p in parents)


def set_visibility(m, on: list, managed: list | None = None) -> None:
    """Listed layers on with their parents and contents. Without `managed`, every other layer turns off
    (basemaps excepted); with it, only the other layers inside `managed` do and the rest stay as authored."""
    lyrs = m.listLayers()
    basemaps = [lyr.longName for lyr in lyrs if lyr.isBasemapLayer]
    scope = [lyr.longName for lyr in managed] if managed is not None else None
    keep = set()
    for lyr in on:
        parts = lyr.longName.split("\\")
        keep.update("\\".join(parts[:i]) for i in range(1, len(parts) + 1))
    groups = [lyr.longName for lyr in on if lyr.isGroupLayer]
    for lyr in lyrs:
        show = lyr.longName in keep or under(lyr.longName, groups)
        if show:
            lyr.visible = True
        elif not under(lyr.longName, basemaps) and (scope is None or under(lyr.longName, scope)):
            lyr.visible = False


def visible_layers(m) -> list:
    lyrs = m.listLayers()
    off = [lyr.longName for lyr in lyrs if not lyr.visible]
    return [lyr for lyr in lyrs if not under(lyr.longName, off)]


def set_extent(mf, m, ext: dict | None, probs: list[str]) -> None:
    import arcpy
    if not ext:
        return
    if "bookmark" in ext:
        bk = [b for b in m.listBookmarks() if b.name == ext["bookmark"]]
        if not bk:
            probs.append(f"no bookmark '{ext['bookmark']}' in map '{m.name}'")
            return
        mf.zoomToBookmark(bk[0])
    elif "layer" in ext:
        lyr, p = resolve_layers(m, [ext["layer"]])
        if p:
            probs += p
            return
        mf.camera.setExtent(mf.getLayerExtent(lyr[0], False, True))
    elif "xy" in ext:
        mf.camera.setExtent(arcpy.Extent(*ext["xy"]))
    if ext.get("scale"):
        mf.camera.scale = ext["scale"]


def apply_sheet(aprx, lyt, cfg: dict, spec: dict, copy_maps: bool = False) -> list[str]:
    """Set up the layout for one sheet. Returns the problems; an empty list means it is ready."""
    probs: list[str] = []
    main = {k: spec[k] for k in ("map", "extent", "managed") if spec.get(k)}
    if spec.get("layers") is not None:
        main["layers"] = list(spec.get("always_on") or []) + list(spec["layers"])
    for fname, fs in {cfg["project"]["frame"]: main, **spec["frames"]}.items():
        mf = [e for e in lyt.listElements("MAPFRAME_ELEMENT") if e.name == fname]
        if not mf:
            probs.append(f"no map frame '{fname}' on layout '{lyt.name}'")
            continue
        mf = mf[0]
        m = mf.map
        if fs.get("map"):
            hits = [x for x in aprx.listMaps() if x.name == fs["map"]]
            if not hits:
                probs.append(f"no map '{fs['map']}' in the project")
                continue
            m = hits[0]
        if m is None:
            probs.append(f"map frame '{fname}' shows no map")
            continue
        if copy_maps and fs.get("layers") is not None:
            m = aprx.copyItem(m, f"{spec['id']} {m.name}")
        if fs.get("map") or copy_maps:
            ext = mf.camera.getExtent()
            mf.map = m
            mf.camera.setExtent(ext)
        if fs.get("layers") is not None:
            on, p = resolve_layers(m, fs["layers"])
            managed, pm = resolve_layers(m, fs["managed"]) if fs.get("managed") else (None, [])
            probs += p + pm
            if not (p or pm):
                set_visibility(m, on, managed)
        set_extent(mf, m, fs.get("extent"), probs)

    tokens = tokens_for(cfg, spec)
    texts = lyt.listElements("TEXT_ELEMENT")
    for name, value in spec["text"].items():
        hits = [e for e in texts if e.name == name]
        if not hits:
            probs.append(f"no text element '{name}' on layout '{lyt.name}'")
        for e in hits:
            e.text = fill(value, tokens) or " "   # an empty string is refused
    elements = lyt.listElements()
    for name, vis in spec["elements"].items():
        hits = [e for e in elements if e.name == name]
        if not hits:
            probs.append(f"no element '{name}' on layout '{lyt.name}'")
        for e in hits:
            e.visible = bool(vis)
    return probs


def layer_problems(lyt) -> list[str]:
    probs = []
    for mf in lyt.listElements("MAPFRAME_ELEMENT"):
        if mf.visible and mf.map:
            probs += [f"'{lyr.longName}' in map '{mf.map.name}' has a broken data source"
                      for lyr in visible_layers(mf.map) if lyr.isBroken]
    return probs


def restricted_problems(lyt, cfg: dict) -> list[str]:
    import arcpy
    r, root = cfg.get("restricted") or {}, cfg["_root"]

    def norm(p) -> str:
        return str(p).replace("/", "\\").rstrip("\\").lower()

    blocked = [norm(p) for p in (root.get("ndot", {}).get("gdb"), root.get("ndot", {}).get("work_dir"),
                                 root.get("curated", {}).get("restricted_gdb"), *r.get("blocked_sources", [])) if p]
    agdb = root.get("paths", {}).get("analysis_gdb")
    need = [norm(f"{agdb}\\{d}") for d in r.get("check_required_datasets", []) if agdb]
    need += [norm(p) for p in r.get("check_required_sources", [])]
    checks = r.get("row_checks") or []
    probs = []
    for mf in lyt.listElements("MAPFRAME_ELEMENT"):
        if not (mf.visible and mf.map):
            continue
        for lyr in visible_layers(mf.map):
            if not lyr.isFeatureLayer or lyr.isBroken:
                continue
            tag = f"'{lyr.longName}' in map '{mf.map.name}'"
            src = norm(lyr.dataSource) if lyr.supports("DATASOURCE") else ""
            if any(src.startswith(b) for b in blocked):
                probs.append(f"{tag} reads a restricted source ({lyr.dataSource})")
                continue
            fields = {f.name.lower(): f.name for f in arcpy.ListFields(lyr)}
            mine = [c for c in checks if c["field"].lower() in fields]
            if not mine:
                if any(src.startswith(p) for p in need):
                    probs.append(f"{tag} reads a culvert dataset that holds NDOT rows and has no "
                                 f"{' or '.join(c['field'] for c in checks)} field to check; use PROTECT_curated.gdb")
                continue
            for c in mine:
                fld = fields[c["field"].lower()]
                vals = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in c["values"])
                with arcpy.da.SearchCursor(lyr, ["OID@"], where_clause=f"{fld} IN ({vals})") as cur:
                    if next(cur, None) is not None:
                        probs.append(f"{tag} shows rows with {fld} in ({vals})")
    return probs


def export_layout(lyt, path: Path, ex: dict) -> None:
    import arcpy
    fmt = arcpy.mp.CreateExportFormat(str(ex["format"]).upper(), str(path))
    fmt.resolution = int(ex.get("dpi", 300))
    for k, v in (ex.get("options") or {}).items():
        if not hasattr(fmt, k):
            raise SystemExit(f"export option '{k}' is not a {ex['format']} setting")
        setattr(fmt, k, v)
    lyt.export(fmt)


def combine_pdfs(paths: list[Path], out: Path) -> None:
    import arcpy
    out.unlink(missing_ok=True)
    pdf = arcpy.mp.PDFDocumentCreate(str(out))
    for p in paths:
        pdf.appendPages(str(p))
    pdf.saveAndClose()


# ---------- commands ----------

def cmd_inspect(aprx, cfg: dict, log: logging.Logger) -> None:
    inv = {"project": aprx.filePath, "maps": [], "layouts": []}
    for m in aprx.listMaps():
        sr = getattr(m.spatialReference, "name", "")
        bks = [b.name for b in m.listBookmarks()]
        log.info(f"MAP '{m.name}' ({m.mapType}, {sr}); bookmarks: {', '.join(bks) or 'none'}")
        rows = []
        for lyr in m.listLayers():
            row = {"longName": lyr.longName, "visible": lyr.visible, "group": lyr.isGroupLayer,
                   "basemap": lyr.isBasemapLayer, "broken": lyr.isBroken,
                   "source": lyr.dataSource if lyr.supports("DATASOURCE") else "",
                   "query": lyr.definitionQuery if lyr.supports("DEFINITIONQUERY") else ""}
            rows.append(row)
            flags = "".join(f" [{k}]" for k in ("group", "basemap", "broken") if row[k])
            log.info(f"  {'on ' if row['visible'] else 'off'} {row['longName']}{flags}"
                     + (f"  where {row['query']}" if row["query"] else ""))
        inv["maps"].append({"name": m.name, "spatialReference": sr, "bookmarks": bks, "layers": rows})
    for lyt in aprx.listLayouts():
        log.info(f"LAYOUT '{lyt.name}' {lyt.pageWidth} x {lyt.pageHeight} {lyt.pageUnits}")
        rows = []
        for e in lyt.listElements():
            detail = (e.text if e.type == "TEXT_ELEMENT" else
                      (e.map.name if e.map else "no map") if e.type == "MAPFRAME_ELEMENT" else "")
            rows.append({"name": e.name, "type": e.type, "visible": e.visible, "detail": detail})
            log.info(f"  {e.type:<20} '{e.name}'" + (f"  {detail[:70]!r}" if detail else ""))
        inv["layouts"].append({"name": lyt.name, "width": lyt.pageWidth, "height": lyt.pageHeight,
                               "units": lyt.pageUnits, "elements": rows})
    out = here_path(cfg["paths"]["outputs"]) / f"inspect_{Path(aprx.filePath).stem}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(inv, indent=2), encoding="utf-8")
    log.info(f"Inventory -> {out}")


def cmd_export(aprx, cfg: dict, sheets: list[dict], args, log: logging.Logger, out_root: Path, dry_run: bool) -> int:
    exdefs = cfg["exports"]
    tpl = template_name(cfg)
    in_use = [n for n in exdefs if not args.exports or n in args.exports]
    lyts = {n: find_layout(aprx, n) for n in {exdefs[x].get("layout") or tpl for x in in_use}}
    state = snapshot(aprx, lyts.values())
    if cfg["project"].get("legend_sync_visibility"):
        for lyt in lyts.values():
            for lg in lyt.listElements("LEGEND_ELEMENT"):
                lg.syncLayerVisibility = True
    prefix = cfg["paths"].get("file_prefix", "")
    written: dict[str, list[Path]] = {n: [] for n in exdefs}
    failed = []
    for s in sheets:
        spec = sheet_spec(cfg, s)
        wanted = [n for n in spec.get("exports") or list(exdefs) if not args.exports or n in args.exports]
        groups: dict[str, list[str]] = {}
        for n in wanted:
            groups.setdefault(exdefs[n].get("layout") or tpl, []).append(n)
        for lname, names in groups.items():
            lyt = lyts[lname]
            restore(state)
            probs = apply_sheet(aprx, lyt, cfg, spec)
            probs += layer_problems(lyt)
            rprobs = restricted_problems(lyt, cfg) if not probs else []
            if rprobs and args.allow_restricted:
                for p in rprobs:
                    log.warning(f"{s['id']}: restricted, allowed: {p}")
                rprobs = []
            if probs or rprobs:
                for p in probs + rprobs:
                    log.error(f"{s['id']} ({lname}): {p}")
                failed.append(s["id"])
                break
            for lg in lyt.listElements("LEGEND_ELEMENT"):
                if lg.isOverflowing:
                    log.warning(f"{s['id']} ({lname}): legend '{lg.name}' overflows its frame")
            if dry_run:
                log.info(f"{s['id']} ({lname}): ready for {', '.join(names)}")
                continue
            for n in names:
                ex = exdefs[n]
                path = out_root / n / f"{prefix}{s['id']}{EXT[str(ex['format']).upper()]}"
                path.parent.mkdir(parents=True, exist_ok=True)
                t0 = time.time()
                export_layout(lyt, path, ex)
                written[n].append(path)
                log.info(f"{s['id']} {n}: {path} ({time.time() - t0:.0f} s)")
    restore(state)
    for n, paths in written.items():
        if exdefs[n].get("combine") and paths:
            if args.only:
                log.info(f"{n}: combined PDF skipped (--only)")
                continue
            out = out_root / n / f"{prefix}all.pdf"
            combine_pdfs(paths, out)
            log.info(f"{n}: {len(paths)} sheets combined -> {out}")
    if failed:
        log.error(f"{len(failed)} of {len(sheets)} sheets not ready: {', '.join(failed)}")
        return 1
    log.info(f"{len(sheets)} sheets {'ready' if dry_run else 'exported'}")
    return 0


def cmd_build(aprx, cfg: dict, sheets: list[dict], args, log: logging.Logger) -> int:
    tpl = find_layout(aprx, template_name(cfg))
    failed = []
    for s in sheets:
        spec = sheet_spec(cfg, s)
        lyt = aprx.copyItem(tpl, s["id"])
        probs = apply_sheet(aprx, lyt, cfg, spec, copy_maps=True)
        probs += layer_problems(lyt) + restricted_problems(lyt, cfg)
        for p in probs:
            log.error(f"{s['id']}: {p}")
        if probs:
            failed.append(s["id"])
        else:
            log.info(f"{s['id']}: layout built")
    out = Path(args.out) if args.out else Path(aprx.filePath).with_name(f"{Path(aprx.filePath).stem}_sheets.aprx")
    if out.resolve().is_relative_to(REPO):
        raise SystemExit(f"Refusing to write a project under the repo: {out}")
    aprx.saveACopy(str(out))
    log.info(f"{len(sheets) - len(failed)} sheet layouts -> {out}"
             + (f"; check before using: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["inspect", "check", "export", "build"])
    ap.add_argument("--aprx", help="the Pro project (overrides project.aprx; CURRENT inside Pro)")
    ap.add_argument("--only", nargs="+", metavar="ID", help="sheets by id or prefix (sr28, sr28_wildfire)")
    ap.add_argument("--exports", nargs="+", metavar="NAME", help="only these exports (names in config exports:)")
    ap.add_argument("--allow-restricted", action="store_true",
                    help="after NDOT sign-off: export restricted rows, to paths.restricted_outputs only")
    ap.add_argument("--out", help="build: where to write the sheet project (default: beside the project)")
    args = ap.parse_args()

    cfg = load_cfg()
    log = get_logger(cfg)
    errs = validate(cfg, args.only, args.exports)
    if errs:
        for e in errs:
            log.error(f"config: {e}")
        raise SystemExit(1)

    out_root = here_path(cfg["paths"]["outputs"])
    if args.allow_restricted:
        ro = cfg["paths"].get("restricted_outputs")
        if not ro or Path(ro).resolve().is_relative_to(REPO):
            raise SystemExit("--allow-restricted needs paths.restricted_outputs set to a folder on F:, outside the repo")
        out_root = Path(ro)

    aprx = open_project(cfg, args.aprx, log)
    sheets = pick_sheets(cfg, args.only)
    if args.command == "inspect":
        cmd_inspect(aprx, cfg, log)
        rc = 0
    elif args.command == "build":
        rc = cmd_build(aprx, cfg, sheets, args, log)
    else:
        rc = cmd_export(aprx, cfg, sheets, args, log, out_root, dry_run=args.command == "check")
    del aprx
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
