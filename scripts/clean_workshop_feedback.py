"""Add new Workshop Feedback sends to the reviewed geodatabase and apply the review rules.

The reviewed geodatabase (config feedback.gdb, outputs/PROTECT_workshop_feedback.gdb) was cleaned by hand on
Nov. 10, 2026. A fresh extract (extract_workshop_feedback.py --overwrite) would bring back every record removed
then, so new sends go through this script instead:

1. Back up the reviewed gdb (outputs/<name>_backup_<timestamp>.gdb).
2. Append the sends in --new (an extract written with extract_workshop_feedback.py --gdb) that the reviewed
   gdb does not have yet, with their notes, station answers, and flooded areas.
3. Remove copies. When two sends come from one browser, the later send repeats the earlier notes. A note that
   matches a note in an earlier send on asset, issue, and the time it was saved is a copy; so is a station
   answer that matches an earlier one from the same reviewer key, and a flooded area with an earlier area's id.
   The earliest copy is kept (the person who wrote it). A concern level set only on a later copy moves to the
   kept note.
4. Remove test records: notes and flooded areas whose text has the word "test" (--keep-tests to skip).
5. Reset latest_send to the newest send per reviewer key, as the extract does.
6. Rewrite the CSV copies beside the gdb.

Every removal is logged. Then run export_feedback_explorer.py --overwrite and commit the JSON.

Run from arcgispro-py3:

    python scripts/extract_workshop_feedback.py --gdb C:/temp/fb_new.gdb
    python scripts/clean_workshop_feedback.py --new C:/temp/fb_new.gdb --dry-run
    python scripts/clean_workshop_feedback.py --new C:/temp/fb_new.gdb
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import shutil
import sys
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
TABLES = ["FeedbackSends", "FeedbackNotes", "FeedbackStationAnswers", "FeedbackFloodAreas"]
TEST = re.compile(r"\btest\b", re.I)


def get_logger() -> logging.Logger:
    log = logging.getLogger("clean_workshop_feedback")
    log.setLevel(logging.INFO)
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.handlers[:] = [h]
    return log


def rows(arcpy, path, fields, where=None):
    with arcpy.da.SearchCursor(path, fields, where_clause=where) as cur:
        return [dict(zip(fields, r)) for r in cur]


def delete_oids(arcpy, path, oids):
    if not oids:
        return
    with arcpy.da.UpdateCursor(path, ["OBJECTID"]) as cur:
        for r in cur:
            if r[0] in oids:
                cur.deleteRow()


def main() -> int:
    ap = argparse.ArgumentParser(description="Append new feedback sends to the reviewed gdb and remove copies and tests.")
    ap.add_argument("--new", required=True, help="a fresh extract (extract_workshop_feedback.py --gdb)")
    ap.add_argument("--keep-tests", action="store_true", help="do not remove records that say 'test'")
    ap.add_argument("--dry-run", action="store_true", help="report what would change; write nothing")
    args = ap.parse_args()
    log = get_logger()
    cfg = yaml.safe_load(open(REPO / "config.yaml"))["feedback"]
    gdb = Path(cfg["gdb"]); gdb = gdb if gdb.is_absolute() else REPO / gdb
    new = Path(args.new)

    import arcpy
    for g in (gdb, new):
        for t in TABLES:
            if not arcpy.Exists(f"{g}/{t}"):
                raise SystemExit(f"{g}/{t} is missing")
    T = {t: f"{gdb}/{t}" for t in TABLES}
    N = {t: f"{new}/{t}" for t in TABLES}

    # ---------------------------------------------------------------- 1-2: back up, append new sends
    have = {r["src_objectid"] for r in rows(arcpy, T["FeedbackSends"], ["src_objectid"])}
    incoming = rows(arcpy, N["FeedbackSends"], ["src_objectid", "send_id", "reviewer_name"])
    add = [s for s in incoming if s["src_objectid"] not in have]
    gone = sorted(have - {s["src_objectid"] for s in incoming})
    if gone:
        log.warning(f"Sends in the reviewed gdb but no longer in the service (kept): {gone}")
    log.info(f"New sends: {[(s['src_objectid'], s['reviewer_name']) for s in add] or 'none'}")
    if not args.dry_run:
        bak = gdb.with_name(f"{gdb.stem}_backup_{time.strftime('%Y%m%d_%H%M%S')}.gdb")
        shutil.copytree(gdb, bak, ignore=shutil.ignore_patterns("*.lock"))
        log.info(f"Backup: {bak}")
    if add:
        src = ",".join(str(s["src_objectid"]) for s in add)
        sids = ",".join(repr(float(s["send_id"])) for s in add if s["send_id"] is not None) or "-1"
        where = {"FeedbackSends": f"src_objectid IN ({src})", "FeedbackNotes": f"src_objectid IN ({src})",
                 "FeedbackStationAnswers": f"src_objectid IN ({src})", "FeedbackFloodAreas": f"send_id IN ({sids})"}
        for t in TABLES:
            n = len(rows(arcpy, N[t], ["OBJECTID"], where[t]))
            log.info(f"{t}: {n} rows to append")
            if n and not args.dry_run:
                lyr = f"fb_new_{t}"
                (arcpy.management.MakeFeatureLayer if t in ("FeedbackNotes", "FeedbackFloodAreas")
                 else arcpy.management.MakeTableView)(N[t], lyr, where[t])
                arcpy.management.Append(lyr, T[t], "TEST")
                arcpy.management.Delete(lyr)
    # in a dry run the checks below read the reviewed gdb plus the new extract's rows for the new sends
    def read(t, fields):
        out = rows(arcpy, T[t], fields)
        if args.dry_run and add:
            out += [dict(r, OBJECTID=-r["OBJECTID"]) for r in rows(arcpy, N[t], fields, where[t])]
        return out

    # ---------------------------------------------------------------- 3: copies
    order = {r["src_objectid"]: (r["send_id"] or 0) for r in read("FeedbackSends", ["OBJECTID", "src_objectid", "send_id"])}
    notes = read("FeedbackNotes", ["OBJECTID", "src_objectid", "note_key", "issue", "noted_local", "concern", "concern_label", "reviewer_name"])
    notes.sort(key=lambda r: (order.get(r["src_objectid"], 0), r["OBJECTID"]))
    first, drop_notes, fill = {}, {}, {}
    for r in notes:
        k = (r["note_key"], r["issue"] or "", str(r["noted_local"]))
        if k in first:
            keep = first[k]
            drop_notes[r["OBJECTID"]] = keep["OBJECTID"]
            if keep["concern"] is None and r["concern"] is not None and keep["OBJECTID"] not in fill:
                fill[keep["OBJECTID"]] = (r["concern"], r["concern_label"])
        else:
            first[k] = r
    for d, k in drop_notes.items():
        r = next(x for x in notes if x["OBJECTID"] == d)
        log.info(f"Note copy: OID {d} (send {r['src_objectid']}, {r['reviewer_name']}) = OID {k}: {(r['issue'] or '')[:60]!r}")
    for k, v in fill.items():
        log.info(f"Concern from a later copy: OID {k} -> {v[0]} {v[1]}")

    sts = read("FeedbackStationAnswers", ["OBJECTID", "src_objectid", "reviewer_key", "station", "expected", "tool", "reviewer_name"])
    sts.sort(key=lambda r: (order.get(r["src_objectid"], 0), r["OBJECTID"]))
    seen, drop_st = set(), set()
    for r in sts:
        k = (r["reviewer_key"], r["station"], r["expected"] or "", r["tool"] or "")
        if k in seen:
            drop_st.add(r["OBJECTID"])
            log.info(f"Station answer copy: OID {r['OBJECTID']} (send {r['src_objectid']}, {r['reviewer_name']}, {r['station']})")
        seen.add(k)

    areas = read("FeedbackFloodAreas", ["OBJECTID", "send_id", "area_id", "notes", "reviewer_name"])
    areas.sort(key=lambda r: (r["send_id"] or 0, r["OBJECTID"]))
    seen, drop_areas = set(), set()
    for r in areas:
        if r["area_id"] in seen:
            drop_areas.add(r["OBJECTID"])
            log.info(f"Flooded area copy: OID {r['OBJECTID']} ({r['reviewer_name']}, {r['area_id']})")
        seen.add(r["area_id"])

    # ---------------------------------------------------------------- 4: tests
    if not args.keep_tests:
        for r in notes:
            if r["OBJECTID"] not in drop_notes and TEST.search(r["issue"] or ""):
                drop_notes[r["OBJECTID"]] = None
                log.info(f"Test note: OID {r['OBJECTID']} ({r['reviewer_name']}): {r['issue']!r}")
        for r in areas:
            if r["OBJECTID"] not in drop_areas and TEST.search(r["notes"] or ""):
                drop_areas.add(r["OBJECTID"])
                log.info(f"Test flooded area: OID {r['OBJECTID']} ({r['reviewer_name']}): {r['notes']!r}")

    log.info(f"To remove: {len(drop_notes)} notes, {len(drop_st)} station answers, {len(drop_areas)} flooded areas")
    if args.dry_run:
        log.info("Dry run: nothing written")
        return 0

    with arcpy.da.Editor(str(gdb)):
        with arcpy.da.UpdateCursor(T["FeedbackNotes"], ["OBJECTID", "concern", "concern_label"]) as cur:
            for r in cur:
                if r[0] in fill:
                    cur.updateRow([r[0], *fill[r[0]]])
        delete_oids(arcpy, T["FeedbackNotes"], set(drop_notes))
        delete_oids(arcpy, T["FeedbackStationAnswers"], drop_st)
        delete_oids(arcpy, T["FeedbackFloodAreas"], drop_areas)

        # ------------------------------------------------------------ 5: latest_send per reviewer key
        sends = rows(arcpy, T["FeedbackSends"], ["src_objectid", "reviewer_key", "reviewer_name", "send_id"])
        person = lambda s: s["reviewer_key"] or f"name:{s['reviewer_name'] or ''}"
        last = {}
        for s in sends:
            last[person(s)] = max(last.get(person(s), -1), s["src_objectid"])
        latest = {s["src_objectid"]: int(last[person(s)] == s["src_objectid"]) for s in sends}
        latest_sid = {s["send_id"]: latest[s["src_objectid"]] for s in sends}
        for t in ("FeedbackSends", "FeedbackNotes", "FeedbackStationAnswers"):
            with arcpy.da.UpdateCursor(T[t], ["src_objectid", "latest_send"]) as cur:
                for r in cur:
                    cur.updateRow([r[0], latest.get(r[0], r[1])])
        with arcpy.da.UpdateCursor(T["FeedbackFloodAreas"], ["send_id", "latest_send"]) as cur:
            for r in cur:
                cur.updateRow([r[0], latest_sid.get(r[0], r[1])])

    # ---------------------------------------------------------------- 6: CSV copies
    for t in TABLES:
        fields = [f.name for f in arcpy.ListFields(T[t]) if f.type not in ("Geometry", "OID") and not f.name.startswith("Shape_")]
        out = gdb.with_name(f"{gdb.stem}_{t}.csv")
        with open(out, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(fields)
            with arcpy.da.SearchCursor(T[t], fields) as cur:
                w.writerows(cur)
        log.info(f"{t}: {int(arcpy.management.GetCount(T[t])[0])} rows; wrote {out.name}")
    log.info("Done. Next: python scripts/export_feedback_explorer.py --overwrite, then commit the JSON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
