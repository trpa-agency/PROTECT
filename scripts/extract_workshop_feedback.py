"""Unpack the Workshop Feedback sends into a review geodatabase: one row per note, station answer,
and flooded area, with the participant and the send on every row.

html/workshop-feedback.html stores each send as one row of the hosted table "PROTECT Workshop
Feedback notes". The notes and the station answers sit inside that row's notes_json as text. This
script reads that table and the "PROTECT Workshop Feedback flood areas v2" polygon layer and writes:

* FeedbackSends (table): one row per send, the source row as stored plus counts and flags;
* FeedbackNotes (points): one row per note in notes_json, at the asset or pin it was made on;
* FeedbackStationAnswers (table): one row per hazard station answer in notes_json;
* FeedbackFloodAreas (polygons): one row per drawn area, as stored, with the same send flags;

and a CSV copy of each beside the geodatabase, for review in Excel.

Read only. The script only queries the services. It never adds, updates, or deletes a row there.
Answers are copied as sent: no trimming, case changes, or truncation. Text fields are as long as
the 50,000-character source fields, and the run stops if any value would not fit. Labels for
concern levels, hazards, and asset types go in their own fields beside the stored codes.

Every send is kept. latest_send = 1 marks the send the page counts: the last send for a
reviewer_key (a hash of the name and the browser), as the page's loadRemote does. A later send
repeats the person's earlier notes, so filter on latest_send = 1 to review each person once. Two
people who sent with the same name (or no name) from the same browser share a key. The log lists
those keys; check their superseded sends before dropping them.

Run from arcgispro-py3. The config points at the public read views, so no sign-in is needed; for a
private service, sign in to ArcGIS Online in ArcGIS Pro first (GIS("home") reuses that sign-in; no
password in this file). Settings are in the config.yaml feedback: block.

    python scripts/extract_workshop_feedback.py               # fails if the geodatabase exists
    python scripts/extract_workshop_feedback.py --overwrite   # rebuild from the services
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from va_common import REPO, clean, get_logger, guard_exists, load_cfg, to_dt

# Labels as the page shows them (workshop-feedback.html CONCERN, HAZARDS, ASSET_TYPES). Keep in step with the page.
CONCERN = {1: "Greatest Concern", 2: "Somewhat Concerned", 3: "Just Adding a Note"}
HAZARD = {"flood": "Flooding", "fire": "Wildfire", "slide": "Landslide", "debris": "Debris flow", "avy": "Avalanche", "any": "Any hazard"}
SCORED = ["flood", "fire", "slide", "debris", "avy"]
ASSET_TYPE = {"road": "Road segment", "bridge": "Bridge", "culvert": "Culvert", "transit": "Transit route",
              "trail": "Bike or pedestrian path", "pin": "Place (pin)"}
LONG = 50000   # the source text fields' length (create_workshop_feedback_layer.py LONG)


def fld(name, ftype, alias, length=None):
    return (name, ftype, length, alias)


SEND_COLS = [
    fld("src_objectid", "LONG", "OBJECTID of the notes row in ArcGIS Online"),
    fld("reviewer_name", "TEXT", "Name", 255),
    fld("reviewer_key", "TEXT", "Reviewer key (hash of name and browser)", 32),
    fld("round", "TEXT", "Round", 64),
    fld("send_id", "DOUBLE", "Send id (ms since 1970; send_id on the flooded areas)"),
    fld("sent_local", "DATE", "Sent (local time)"),
    fld("latest_send", "SHORT", "Latest send for this reviewer key (1 = the send the page counts)"),
]
SENDS = SEND_COLS + [
    fld("n_notes", "LONG", "Notes in this send"),
    fld("n_station", "LONG", "Station answers in this send"),
    fld("n_areas_sent", "LONG", "Flooded areas the send reported"),
    fld("n_areas_found", "LONG", "Flooded areas found with this send id"),
    fld("json_ok", "SHORT", "notes_json read (1 = yes)"),
    fld("json_error", "TEXT", "notes_json read error", 255),
    fld("notes_text", "TEXT", "Notes as sent (one per line)", LONG),
    fld("station_text", "TEXT", "Station answers as sent (one per line)", LONG),
    fld("notes_json", "TEXT", "notes_json as sent", LONG),
]
NOTES = SEND_COLS + [
    fld("note_seq", "SHORT", "Note number within the send"),
    fld("note_key", "TEXT", "Note key (asset type:asset id)", 255),
    fld("asset_type", "TEXT", "Asset type code", 32),
    fld("asset_type_label", "TEXT", "Asset type", 64),
    fld("asset_id", "TEXT", "Asset id", 255),
    fld("asset_name", "TEXT", "Asset name", 1000),
    fld("asset_detail", "TEXT", "Asset details (as shown on the card)", 4000),
    fld("hazards", "TEXT", "Hazard codes (blank = any hazard)", 255),
    fld("hazard_labels", "TEXT", "Hazards", 255),
] + [fld(f"haz_{h}", "SHORT", f"{HAZARD[h]} (1 = tagged)") for h in SCORED] + [
    fld("concern", "SHORT", "Concern level (1 greatest to 3)"),
    fld("concern_label", "TEXT", "Concern", 64),
    fld("issue", "TEXT", "Issue description", LONG),
    fld("missing_asset", "SHORT", "Flagged as missing from the map (1 = yes)"),
    fld("noted_local", "DATE", "Note saved (local time)"),
    fld("lon", "DOUBLE", "Longitude (WGS84, as sent)"),
    fld("lat", "DOUBLE", "Latitude (WGS84, as sent)"),
    fld("has_location", "SHORT", "Has a map location (1 = yes)"),
]
STATIONS = SEND_COLS + [
    fld("station", "TEXT", "Station code", 32),
    fld("station_label", "TEXT", "Station", 64),
    fld("expected", "TEXT", "Do the results match what you expected?", LONG),
    fld("tool", "TEXT", "What should the tool show?", LONG),
]
AREAS = [
    fld("src_objectid", "LONG", "OBJECTID of the area in ArcGIS Online"),
    fld("reviewer_name", "TEXT", "Name", 255),
    fld("agency", "TEXT", "Agency", 255),
    fld("reviewer_key", "TEXT", "Reviewer key (hash of name and browser)", 32),
    fld("round", "TEXT", "Round", 64),
    fld("send_id", "DOUBLE", "Send id (ms since 1970; send_id on FeedbackSends)"),
    fld("sent_local", "DATE", "Sent (local time)"),
    fld("latest_send", "SHORT", "From the send the page counts for this person (1 = yes)"),
    fld("notes_row_found", "SHORT", "A notes row carries this send id (1 = yes)"),
    fld("area_id", "TEXT", "Area id (made by the page)", 64),
    fld("observed_when", "TEXT", "When it happened", 255),
    fld("notes", "TEXT", "What happened", 4000),
    fld("area_acres", "DOUBLE", "Area (acres, as the page measured it)"),
    fld("reporter_name", "TEXT", "Who saw it", 255),
]
AREA_SRC = ["reviewer_name", "agency", "reviewer_key", "round", "send_id", "area_id", "observed_when", "notes", "area_acres", "reporter_name"]


# ---------------------------------------------------------------- read (query only)

def read_service(gis, url: str, geometry: bool, log):
    """All rows of the service's first table or layer (or the one the URL names), oldest first."""
    from arcgis.features import FeatureLayer, FeatureLayerCollection, Table
    m = re.match(r"^(.*?/FeatureServer)(?:/(\d+))?/?$", url.strip(), re.I)
    if not m:
        raise SystemExit(f"Not a FeatureServer URL: {url}")
    if m.group(2) is not None:
        lyr = (FeatureLayer if geometry else Table)(f"{m.group(1)}/{m.group(2)}", gis)
    else:
        flc = FeatureLayerCollection(m.group(1), gis)
        subs = (flc.layers or []) if geometry else (flc.tables or []) + (flc.layers or [])
        if not subs:
            raise SystemExit(f"{url}: no {'layer' if geometry else 'table'} found")
        lyr = subs[0]
    oid = lyr.properties.objectIdField
    fs = lyr.query(where="1=1", out_fields="*", return_geometry=geometry, out_sr=4326 if geometry else None,
                   order_by_fields=f"{oid} ASC", return_all_records=True)
    rows = [f.as_dict for f in fs.features]
    log.info(f"Read {len(rows)} rows from {lyr.url}")
    return rows, oid


# ---------------------------------------------------------------- unpack

def ms_to_local(ms, tz: str):
    if ms is None:
        return None
    try:                                                                                                                                                                                                                        
        return pd.to_datetime(float(ms), unit="ms", utc=True).tz_convert(tz).tz_localize(None)
    except (TypeError, ValueError, OverflowError):
        return None


def person_key(a: dict) -> str:
    # as the page's loadRemote: reviewer_key, else the name and agency
    return a.get("reviewer_key") or f"name:{a.get('reviewer_name') or ''}|{a.get('agency') or ''}"


def type_label(t, sub) -> str | None:
    # as the page's typeLabel: a transit note on a transit center is a hub
    if t == "transit" and re.search(r"transit center", str(sub or ""), re.I):
        return "Transit hub"
    return ASSET_TYPE.get(t, t)


def as_int(v):
    try:
        return None if v is None or v == "" else int(v)
    except (TypeError, ValueError):
        return None


def as_float(v):
    try:
        return None if v is None or v == "" else float(v)
    except (TypeError, ValueError):
        return None


def unpack(rows: list[dict], oid: str, tz: str, log):
    """Notes table rows -> (sends, notes, station answers). Values are copied as sent."""
    latest = {}
    for r in rows:
        a = r["attributes"]
        latest[person_key(a)] = max(latest.get(person_key(a), -1), a[oid])
    sends, notes, stations = [], [], []
    for r in sorted(rows, key=lambda r: r["attributes"][oid]):
        a = r["attributes"]
        raw = a.get("notes_json")
        doc, ok, err = {}, 1, None
        if raw:
            try:
                doc = json.loads(raw)
                if not isinstance(doc, dict):
                    raise ValueError("notes_json is not a JSON object")
            except (ValueError, TypeError) as e:
                doc, ok, err = {}, 0, str(e)[:255]
                log.warning(f"OBJECTID {a[oid]}: notes_json not read ({err}); the row is kept with its notes_text")
        sid = doc.get("sid")                          # sends before sid existed carry only sent
        send_id = sid if sid is not None else doc.get("sent")
        base = {"src_objectid": a[oid], "reviewer_name": a.get("reviewer_name"), "reviewer_key": a.get("reviewer_key"),
                "round": a.get("round"), "send_id": send_id, "sent_local": ms_to_local(send_id, tz),
                "latest_send": int(latest[person_key(a)] == a[oid])}
        note_list = doc.get("notes") or []
        station = doc.get("station") or {}
        sends.append({**base, "n_notes": len(note_list), "n_station": len(station), "n_areas_sent": as_int(doc.get("areas")),
                      "json_ok": ok, "json_error": err, "notes_text": a.get("notes_text"),
                      "station_text": a.get("station_text"), "notes_json": raw,
                      "_person": person_key(a), "_sid": sid})
        for i, n in enumerate(note_list, 1):
            key = n.get("key")
            haz = n.get("hazards") or []
            haz = [haz] if isinstance(haz, str) else list(haz)
            concern = as_int(n.get("concern"))
            lon, lat = as_float(n.get("lon")), as_float(n.get("lat"))
            missing = n.get("missing")
            notes.append({**base, "note_seq": i, "note_key": key, "asset_type": n.get("type"),
                          "asset_type_label": type_label(n.get("type"), n.get("sub")),
                          "asset_id": str(key).split(":", 1)[1] if key and ":" in str(key) else None,
                          "asset_name": n.get("name"), "asset_detail": n.get("sub"),
                          "hazards": ",".join(map(str, haz)) or None,
                          "hazard_labels": ", ".join(HAZARD.get(h, str(h)) for h in haz) or "Any hazard",
                          **{f"haz_{h}": int(h in haz) for h in SCORED},
                          "concern": concern, "concern_label": CONCERN.get(concern),
                          "issue": n.get("why"), "missing_asset": None if missing is None else int(bool(missing)),
                          "noted_local": ms_to_local(n.get("when"), tz), "lon": lon, "lat": lat,
                          "has_location": int(lon is not None and lat is not None)})
        for k, sq in station.items():
            sq = sq or {}
            stations.append({**base, "station": k, "station_label": HAZARD.get(k, k),
                             "expected": sq.get("expect"), "tool": sq.get("tool")})
    return sends, notes, stations


def flag_areas(area_rows: list[dict], oid: str, sends: list[dict], tz: str):
    """Area features -> rows with the page's latest-send rule: the areas whose send_id matches the sid on the
    person's latest notes row, or, for a person whose latest row has no sid, their highest send_id."""
    latest_sid = {s["_person"]: s["_sid"] for s in sends if s["latest_send"]}
    sids = {s["_sid"] for s in sends if s["_sid"] is not None}
    top = {}
    for f in area_rows:
        a = f["attributes"]
        k = a.get("reviewer_key") or ""
        top[k] = max(top.get(k, 0), a.get("send_id") or 0)
    out, geoms = [], []
    for f in sorted(area_rows, key=lambda f: f["attributes"][oid]):
        a = f["attributes"]
        k = a.get("reviewer_key") or ""
        want = latest_sid.get(k) if latest_sid.get(k) is not None else top.get(k)
        sid = a.get("send_id")
        out.append({"src_objectid": a[oid], **{c: a.get(c) for c in AREA_SRC}, "sent_local": ms_to_local(sid, tz),
                    "latest_send": int((sid or 0) == want), "notes_row_found": int(sid in sids)})
        geoms.append((f.get("geometry") or {}).get("rings"))
    found = {}
    for r in out:
        found[r["send_id"]] = found.get(r["send_id"], 0) + 1
    for s in sends:
        s["n_areas_found"] = found.get(s["_sid"], 0) if s["_sid"] is not None else None
    return out, geoms


# ---------------------------------------------------------------- write

def check_lengths(name: str, fields, rows: list[dict]) -> None:
    lens = {n: ln for n, t, ln, al in fields if t == "TEXT"}
    for r in rows:
        for c, ln in lens.items():
            v = r.get(c)
            if isinstance(v, str) and len(v) > ln:
                raise SystemExit(f"{name}: {c} on source row {r.get('src_objectid')} is {len(v):,} characters; "
                                 f"the field holds {ln:,}. Raise the length in this script rather than cut the answer.")


def write(arcpy, gdb: str, name: str, geom: str | None, fields, rows: list[dict], shapes, sr, log) -> str:
    check_lengths(name, fields, rows)
    if geom:
        path = arcpy.management.CreateFeatureclass(gdb, name, geom, spatial_reference=sr).getOutput(0)
    else:
        path = arcpy.management.CreateTable(gdb, name).getOutput(0)
    arcpy.management.AddFields(path, [[n, t, al, ln or ""] for n, t, ln, al in fields])
    cols = [f[0] for f in fields]
    ft = {n: t for n, t, ln, al in fields}
    tl = {n: ln for n, t, ln, al in fields if t == "TEXT"}
    with arcpy.da.InsertCursor(path, (["SHAPE@"] if geom else []) + cols) as cur:
        for i, r in enumerate(rows):
            vals = [to_dt(r.get(c)) if ft[c] == "DATE" else clean(r.get(c), c, tl, ft[c]) for c in cols]
            cur.insertRow(([shapes[i]] if geom else []) + vals)
    for idx in ("send_id", "reviewer_key"):
        arcpy.management.AddIndex(path, [idx], f"{idx}_idx")
    log.info(f"Wrote {int(arcpy.management.GetCount(path)[0])} rows -> {name}")
    return path


def write_csv(gdb: Path, name: str, fields, rows: list[dict], log) -> None:
    out = gdb.with_name(f"{gdb.stem}_{name}.csv")
    pd.DataFrame(rows, columns=[f[0] for f in fields]).to_csv(out, index=False, encoding="utf-8-sig")
    log.info(f"Wrote {out}")


def summarize(sends, notes, stations, areas, log) -> None:
    people = {s["_person"] for s in sends}
    log.info(f"Sends: {len(sends)} from {len(people)} reviewer keys; latest sends: {sum(s['latest_send'] for s in sends)}")
    log.info(f"Notes: {len(notes)} in all sends, {sum(n['latest_send'] for n in notes)} in latest sends; "
             f"{sum(1 - n['has_location'] for n in notes)} without a location")
    log.info(f"Station answers: {len(stations)} in all sends, {sum(s['latest_send'] for s in stations)} in latest sends")
    log.info(f"Flooded areas: {len(areas)} in all sends, {sum(a['latest_send'] for a in areas)} in latest sends")
    bad = [s["src_objectid"] for s in sends if not s["json_ok"]]
    if bad:
        log.warning(f"notes_json not read on OBJECTID {bad}; their answers are only in notes_text and station_text")
    orphans = [a["src_objectid"] for a in areas if not a["notes_row_found"]]
    if orphans:
        log.warning(f"Flooded areas with no notes row for their send (the notes row failed after the areas were "
                    f"added, or the send predates sid): OBJECTID {orphans}")
    mism = [s["src_objectid"] for s in sends if s["n_areas_sent"] is not None and s["n_areas_found"] is not None
            and s["n_areas_sent"] != s["n_areas_found"]]
    if mism:
        log.warning(f"Sends whose area count does not match the areas found: OBJECTID {mism}")
    shared = sorted({s["_person"] for s in sends if not (s["reviewer_name"] or "").strip()}
                    & {s["_person"] for s in sends if not s["latest_send"]})
    if shared:
        log.warning(f"Unnamed reviewer keys with superseded sends (possibly more than one person on one browser): {shared}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Unpack Workshop Feedback sends into a review geodatabase (read only).")
    ap.add_argument("--overwrite", action="store_true", help="replace the geodatabase and CSVs if they exist")
    args = ap.parse_args()
    cfg = load_cfg()
    fc = cfg["feedback"]
    log = get_logger("extract_workshop_feedback")
    tz = fc.get("timezone", "America/Los_Angeles")
    gdb = Path(fc["gdb"])
    gdb = gdb if gdb.is_absolute() else REPO / gdb

    from arcgis.gis import GIS
    try:
        gis = GIS("home")                             # the Pro sign-in, for private services
    except Exception as e:                            # the read views are public: read them anonymously
        log.info(f"No ArcGIS Pro sign-in ({e}); reading anonymously")
        gis = GIS()
    log.info(f"Signed in as {gis.users.me.username if gis.users.me else 'anonymous'} at {gis.url}")
    rows, oid = read_service(gis, fc["notes_service"], False, log)
    sends, notes, stations = unpack(rows, oid, tz, log)
    areas, rings = [], []
    if fc.get("areas_service"):
        area_rows, aoid = read_service(gis, fc["areas_service"], True, log)
        areas, rings = flag_areas(area_rows, aoid, sends, tz)
    else:
        log.info("feedback.areas_service is blank: flooded areas skipped")
    summarize(sends, notes, stations, areas, log)

    import arcpy                                      # after the reads: a successful arcpy import shadows datetime
    gdb.parent.mkdir(parents=True, exist_ok=True)
    guard_exists([str(gdb)], args.overwrite, log)
    arcpy.management.CreateFileGDB(str(gdb.parent), gdb.name)
    sr = arcpy.SpatialReference(int(cfg["output"]["target_epsg"]))
    wgs = arcpy.SpatialReference(4326)
    xf = fc.get("wgs84_to_target") or ""

    def project(g):
        return g.projectAs(sr, xf) if xf else g.projectAs(sr)

    pts = [project(arcpy.PointGeometry(arcpy.Point(n["lon"], n["lat"]), wgs)) if n["has_location"] else None for n in notes]
    polys = [project(arcpy.AsShape({"rings": r, "spatialReference": {"wkid": 4326}}, True)) if r else None for r in rings]
    write(arcpy, str(gdb), "FeedbackSends", None, SENDS, sends, None, sr, log)
    write(arcpy, str(gdb), "FeedbackNotes", "POINT", NOTES, notes, pts, sr, log)
    write(arcpy, str(gdb), "FeedbackStationAnswers", None, STATIONS, stations, None, sr, log)
    if fc.get("areas_service"):
        write(arcpy, str(gdb), "FeedbackFloodAreas", "POLYGON", AREAS, areas, polys, sr, log)
    for name, fields, data in (("FeedbackSends", SENDS, sends), ("FeedbackNotes", NOTES, notes),
                               ("FeedbackStationAnswers", STATIONS, stations), ("FeedbackFloodAreas", AREAS, areas)):
        if name != "FeedbackFloodAreas" or fc.get("areas_service"):
            write_csv(gdb, name, fields, data, log)
    log.info(f"Done: {gdb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
