"""Write the cleaned Workshop Feedback geodatabase to one JSON file for html/workshop-feedback-explorer.html.

Reads outputs/PROTECT_workshop_feedback.gdb (extract_workshop_feedback.py, then reviewed by hand: duplicate
notes and areas carried forward between sends on one browser, and test records, removed Nov. 10, 2026) and
writes outputs/PROTECT_workshop_feedback_explorer.json: the sends, notes, station answers, and flooded areas,
with geometry in WGS84.

The file holds participant names, so it stays in outputs/ (gitignored, never served by GitHub Pages). The
explorer reads it through the repo-root preview server (.claude/launch.json protect-root, port 8012), or from
the page's Open data file button anywhere else.

Run from arcgispro-py3:

    python scripts/export_feedback_explorer.py               # fails if the JSON exists
    python scripts/export_feedback_explorer.py --overwrite
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import datetime as dt   # a module alias: a successful arcpy import shadows the name datetime
from pathlib import Path

import yaml

# va_common is not imported: it needs geopandas, which plain arcgispro-py3 lacks, and this needs only the config
REPO = Path(__file__).resolve().parents[1]


def load_cfg() -> dict:
    with open(REPO / "config.yaml") as f:
        return yaml.safe_load(f)


def get_logger(name: str) -> logging.Logger:
    log = logging.getLogger(name)
    log.setLevel(logging.INFO)
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.handlers[:] = [h]
    return log


def guard_exists(paths: list[str], overwrite: bool, log: logging.Logger) -> None:
    for p in map(Path, paths):
        if p.exists() and not overwrite:
            raise SystemExit(f"{p} exists. Re-run with --overwrite to replace it.")


def rows(arcpy, path: str, fields: list[str], sr=None) -> list[dict]:
    with arcpy.da.SearchCursor(path, fields, spatial_reference=sr) as cur:
        return [dict(zip(fields, r)) for r in cur]


def iso(v):
    return v.isoformat(timespec="seconds") if isinstance(v, dt.datetime) else v


def main() -> int:
    ap = argparse.ArgumentParser(description="Cleaned feedback geodatabase -> explorer JSON.")
    ap.add_argument("--overwrite", action="store_true", help="replace the JSON if it exists")
    args = ap.parse_args()
    fc = load_cfg()["feedback"]
    log = get_logger("export_feedback_explorer")
    gdb = Path(fc["gdb"]); gdb = gdb if gdb.is_absolute() else REPO / gdb
    out = Path(fc.get("explorer_json") or gdb.with_name(f"{gdb.stem}_explorer.json"))
    out = out if out.is_absolute() else REPO / out
    guard_exists([str(out)], args.overwrite, log)

    import arcpy
    wgs = arcpy.SpatialReference(4326)
    sends = rows(arcpy, f"{gdb}/FeedbackSends", ["src_objectid", "reviewer_name", "reviewer_key", "round", "sent_local", "latest_send"])
    notes = rows(arcpy, f"{gdb}/FeedbackNotes",
                 ["OBJECTID", "src_objectid", "note_seq", "note_key", "asset_type", "asset_type_label", "asset_id", "asset_name",
                  "asset_detail", "hazards", "concern", "issue", "missing_asset", "noted_local", "lon", "lat"])
    stations = rows(arcpy, f"{gdb}/FeedbackStationAnswers", ["OBJECTID", "src_objectid", "station", "station_label", "expected", "tool"])
    areas = rows(arcpy, f"{gdb}/FeedbackFloodAreas",
                 ["OBJECTID", "src_objectid", "reviewer_name", "send_id", "area_id", "observed_when", "notes", "area_acres",
                  "reporter_name", "SHAPE@JSON"], sr=wgs)
    by_send = {s["src_objectid"]: s for s in sends}
    # areas carry send_id, not the notes row: match it through the sends table's send id
    sid_to_send = {r[0]: r[1] for r in arcpy.da.SearchCursor(f"{gdb}/FeedbackSends", ["send_id", "src_objectid"])}

    doc = {
        "built": dt.datetime.now().isoformat(timespec="seconds"),
        "source": gdb.name,
        "sends": [{"send": s["src_objectid"], "name": s["reviewer_name"], "round": s["round"],
                   "sent": iso(s["sent_local"])} for s in sends],
        "notes": [{"id": n["OBJECTID"], "send": n["src_objectid"], "name": by_send.get(n["src_objectid"], {}).get("reviewer_name"),
                   "key": n["note_key"], "type": n["asset_type"], "type_label": n["asset_type_label"], "asset_id": n["asset_id"],
                   "asset": n["asset_name"], "detail": n["asset_detail"],
                   "hazards": [h for h in (n["hazards"] or "").split(",") if h],
                   "concern": n["concern"], "issue": n["issue"], "missing": n["missing_asset"],
                   "noted": iso(n["noted_local"]), "lon": n["lon"], "lat": n["lat"]} for n in notes],
        "stations": [{"id": s["OBJECTID"], "send": s["src_objectid"], "name": by_send.get(s["src_objectid"], {}).get("reviewer_name"),
                      "station": s["station"], "label": s["station_label"], "expected": s["expected"], "tool": s["tool"]}
                     for s in stations],
        "areas": [{"id": a["OBJECTID"], "send": sid_to_send.get(a["send_id"]), "name": a["reviewer_name"], "area_id": a["area_id"],
                   "when": a["observed_when"], "notes": a["notes"], "acres": a["area_acres"], "reporter": a["reporter_name"],
                   "rings": (json.loads(a["SHAPE@JSON"]) or {}).get("rings") if a["SHAPE@JSON"] else None} for a in areas],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info(f"{len(doc['sends'])} sends, {len(doc['notes'])} notes, {len(doc['stations'])} station answers, "
             f"{len(doc['areas'])} flooded areas -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
