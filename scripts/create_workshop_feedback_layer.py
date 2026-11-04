"""Create (or check) the ArcGIS Online services that html/workshop-feedback.html sends to.

Layout, following the EIP Funding Priorities picks survey (maps repo, eip/funding-priorities.html),
for each of two services:

* a private parent, one record per send (notes) or per drawn area (flood areas);
* a public view with Create only ("... submit"), which the page posts to with applyEdits;
* a public view with Query only ("... public view"), which the page reads to show everyone's.

The services:

* "PROTECT Workshop Feedback notes", a hosted table, one row per send;
* "PROTECT Workshop Feedback flood areas v2" (Nov. 4, 2026), a hosted polygon layer, one
  feature per area a participant drew where they have seen flooding: when, what happened, acres,
  and the name at the top of the page. Each area carries the send_id of its send, and the notes
  row of the same send carries it as sid in notes_json; the page shows a participant's areas only
  from their latest send. It replaces the Oct. 30, 2026 "PROTECT Workshop Feedback flood areas"
  service (owner amcclary_TRPA, left in place, empty): that service's submit view was made with a
  hand-rolled create_service that never set isUpdatableView, so ArcGIS Online marked the view
  non-updatable and refused every add with "This operation is not supported." Views are now made
  with FeatureLayerCollection.manager.create_view(updateable=True), the supported way.

The page no longer asks for an email or agency (Nov. 4, 2026), so the flood area contacts table
built Oct. 30 is not created or used any more.

Built Oct. 10, 2026 (owner mbindl, TRPA ArcGIS Online). What did not work in this org, so the
page is designed around it: hiding a field on a view of a hosted *table* (sourceLayerFields at
creation or by updateDefinition reports success and changes nothing), and editor tracking
(editFieldsInfo stays unset, CreationDate is never filled). Therefore the page never sends the
email address, only its hash as reviewer_key, and it orders sends by OBJECTID and timestamps
them itself inside notes_json (and send_id on the areas).

Run from arcgispro-py3 while ArcGIS Pro is signed in to ArcGIS Online (GIS("home") reuses that
sign-in; no password in this file). Safe to run again: it finds the items by title and only
creates what is missing. --smoke-test posts one anonymous row to the notes submit view, reads it
back from the public view, confirms the submit view refuses queries, and deletes the row; then
the same with one polygon on the flood areas service. The smoke test needs the signed-in user to
own the parent (it deletes its rows there); someone else's service is reported and skipped.

    python scripts/create_workshop_feedback_layer.py [--smoke-test]
"""
import json
import logging
import sys
import time
import urllib.parse
import urllib.request

from arcgis.features import FeatureLayerCollection, Table
from arcgis.gis import GIS

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

TAGS = ["PROTECT", "TRIP", "workshop", "feedback"]
LONG = 50000
FIELDS = [
    {"name": "reviewer_name", "type": "esriFieldTypeString", "alias": "Name", "length": 255, "nullable": True, "editable": True},
    {"name": "reviewer_email", "type": "esriFieldTypeString", "alias": "Not used: the page sends a hash of the email as reviewer_key", "length": 255, "nullable": True, "editable": True},
    {"name": "agency", "type": "esriFieldTypeString", "alias": "Agency", "length": 255, "nullable": True, "editable": True},
    {"name": "reviewer_key", "type": "esriFieldTypeString", "alias": "Reviewer key (hash of the email)", "length": 32, "nullable": True, "editable": True},
    {"name": "round", "type": "esriFieldTypeString", "alias": "Round (Workshop 1, Workshop 2)", "length": 64, "nullable": True, "editable": True},
    {"name": "notes_text", "type": "esriFieldTypeString", "alias": "Notes (one per line: hazards, concern, asset, key, missing, why)", "length": LONG, "nullable": True, "editable": True},
    {"name": "notes_json", "type": "esriFieldTypeString", "alias": "Notes (JSON, read by the page; carries the sent time)", "length": LONG, "nullable": True, "editable": True},
    {"name": "station_text", "type": "esriFieldTypeString", "alias": "Station answers (one hazard per line)", "length": LONG, "nullable": True, "editable": True},
]
TABLE_DEF = {
    "name": "notes", "type": "Table", "displayField": "reviewer_name", "objectIdField": "OBJECTID",
    "description": "One row per send from html/workshop-feedback.html",
    "fields": [{"name": "OBJECTID", "type": "esriFieldTypeOID", "alias": "OBJECTID", "nullable": False, "editable": False}] + FIELDS,
    "capabilities": "Create,Query,Update,Delete,Editing", "hasAttachments": False,
    "indexes": [{"name": "key_idx", "fields": "reviewer_key", "isAscending": True, "isUnique": False}],
}


def text(name, alias, length=255):
    return {"name": name, "type": "esriFieldTypeString", "alias": alias, "length": length, "nullable": True, "editable": True}


AREA_FIELDS = [
    text("reviewer_name", "Name"),
    text("agency", "Agency"),
    text("reviewer_key", "Reviewer key (hash of the email)", 32),
    text("round", "Round (Workshop 1, Workshop 2)", 64),
    {"name": "send_id", "type": "esriFieldTypeDouble", "alias": "Send (ms since 1970; sid in the notes row of the same send)", "nullable": True, "editable": True},
    text("area_id", "Area id (made by the page)", 64),
    text("observed_when", "When it happened"),
    text("notes", "What happened", 4000),
    {"name": "area_acres", "type": "esriFieldTypeDouble", "alias": "Area (acres)", "nullable": True, "editable": True},
    text("reporter_name", "Who saw it: the name at the top of the page when the area was saved"),
]
TAHOE_EXTENT = {"xmin": -13392000, "ymin": 4688000, "xmax": -13331000, "ymax": 4770000, "spatialReference": {"wkid": 102100, "latestWkid": 3857}}
AREA_DEF = {
    "name": "flood_areas", "type": "Feature Layer", "geometryType": "esriGeometryPolygon", "displayField": "observed_when", "objectIdField": "OBJECTID",
    "description": "Areas participants drew on html/workshop-feedback.html where they have seen flooding",
    "fields": [{"name": "OBJECTID", "type": "esriFieldTypeOID", "alias": "OBJECTID", "nullable": False, "editable": False}] + AREA_FIELDS,
    "capabilities": "Create,Query,Update,Delete,Editing", "hasAttachments": False, "extent": TAHOE_EXTENT,
    "indexes": [{"name": "key_idx", "fields": "reviewer_key", "isAscending": True, "isUnique": False}],
}

# kind: the key the sublayer goes under in addToDefinition ("tables" or "layers")
NOTES = {"parent": "PROTECT Workshop Feedback notes", "submit": "PROTECT Workshop Feedback notes submit",
         "public": "PROTECT Workshop Feedback notes public view", "service": "PROTECT_Workshop_Feedback_notes",
         "kind": "tables", "definition": TABLE_DEF, "what": "Feedback sent from the PROTECT Workshop Feedback page (data.trpa.gov/PROTECT)."}
AREAS = {"parent": "PROTECT Workshop Feedback flood areas v2", "submit": "PROTECT Workshop Feedback flood areas v2 submit",
         "public": "PROTECT Workshop Feedback flood areas v2 public view", "service": "PROTECT_Workshop_Feedback_flood_areas_v2",
         "kind": "layers", "definition": AREA_DEF, "what": "Areas of observed flooding drawn on the PROTECT Workshop Feedback page (data.trpa.gov/PROTECT)."}



def find(gis, title):
    # anywhere in the org, preferring the signed-in user's own: the notes service was made by another account,
    # and a second create_service under the same service name fails ("Service name ... already exists")
    hits = [i for i in gis.content.search(f'title:"{title}"', item_type="Feature Service", max_items=50) if i.title == title]
    hits.sort(key=lambda i: i.owner != gis.users.me.username)
    return hits[0] if hits else None


def mine(gis, item):
    return item.owner == gis.users.me.username


def sublayer_of(gis, item, kind):
    for _ in range(12):                              # a new service can take a moment to list its table or layer
        flc = FeatureLayerCollection.fromitem(gis.content.get(item.id))
        subs = flc.tables if kind == "tables" else flc.layers
        if subs:
            return Table(subs[0].url, gis) if kind == "tables" else subs[0]
        time.sleep(5)
    raise RuntimeError(f"{item.title}: no {kind[:-1]} after a minute; check it in ArcGIS Online")


def share_public(gis, item):
    try:
        from arcgis.gis import SharingLevel
        item.sharing.sharing_level = SharingLevel.EVERYONE
    except Exception:
        item.share(everyone=True, org=True)
    log.info("shared with everyone: %s (%s)", item.title, gis.content.get(item.id).access)


def ensure_parent(gis, spec):
    item = find(gis, spec["parent"])
    if item:
        log.info("parent exists: %s (%s, owner %s)", item.title, item.id, item.owner)
        return item
    log.info("creating hosted %s %s", spec["kind"][:-1], spec["parent"])
    item = gis.content.create_service(name=spec["service"], service_type="featureService", has_static_data=False,   # Web Mercator by default
                                      capabilities="Create,Query,Update,Delete,Editing", tags=TAGS, snippet=spec["what"])
    item.update({"title": spec["parent"]})
    log.info("addToDefinition: %s", FeatureLayerCollection.fromitem(item).manager.add_to_definition({spec["kind"]: [spec["definition"]]}))
    sublayer_of(gis, item, spec["kind"])
    return gis.content.get(item.id)


def ensure_view(gis, spec, parent, which, name, capabilities):
    title = spec[which]
    item = find(gis, title)
    if item:
        log.info("view exists: %s (%s)", title, item.id)
    else:
        log.info("creating view %s (%s)", title, capabilities)
        # manager.create_view is the supported way: it sets isUpdatableView, which a hand-rolled create_service +
        # addToDefinition left unset on the Oct. 30 flood areas view (ArcGIS Online then refused every add)
        sublayer_of(gis, parent, spec["kind"])             # waits until the parent lists its layer or table
        item = FeatureLayerCollection.fromitem(parent).manager.create_view(
            name=name, capabilities=capabilities, updateable=True, allow_schema_changes=True, tags=",".join(TAGS),
            snippet=f"{capabilities} view of {spec['parent']} for the Workshop Feedback page.")
        item.update({"title": title})
        item = gis.content.get(item.id)
        log.info("view %s: isUpdatableView %s", title, sublayer_of(gis, item, spec["kind"]).properties.get("isUpdatableView"))
    tbl = sublayer_of(gis, item, spec["kind"])
    if not mine(gis, item):                          # someone else's view: report it, change nothing
        log.info("view %s is owned by %s; left as is (%s, %s)", title, item.owner, tbl.properties.get("capabilities"), item.access)
        return item, tbl.url
    have = set((tbl.properties.get("capabilities") or "").split(","))
    bad = ("Query" in have) if capabilities == "Create" else bool({"Create", "Update", "Delete"} & have)
    if capabilities not in have or bad:
        log.info("%s capabilities %s -> %s: %s", title, ",".join(sorted(have)), capabilities, tbl.manager.update_definition({"capabilities": capabilities}))
    if gis.content.get(item.id).access != "public":
        share_public(gis, item)
    return item, tbl.url


def post(url, data):
    body = urllib.parse.urlencode(data).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=60) as r:
        return json.loads(r.read().decode())


def smoke_test(gis, parent, submit_url, public_url):
    row = {"reviewer_name": "Smoke Test", "agency": "TRPA", "reviewer_key": "deadbeef", "round": "smoke",
           "notes_text": "Flooding - Concern 1 - Road segment - Test road - road:test", "notes_json": json.dumps({"v": 1, "sent": int(time.time() * 1000), "notes": [], "station": {}})}
    r = post(f"{submit_url}/applyEdits", {"f": "json", "adds": json.dumps([{"attributes": row}]), "rollbackOnFailure": "true"})
    log.info("anonymous add: %s", r.get("addResults") or r)
    ok = bool(r.get("addResults", [{}])[0].get("success"))
    q = post(f"{public_url}/query", {"f": "json", "where": "round='smoke'", "outFields": "*", "orderByFields": "OBJECTID DESC"})
    log.info("anonymous read back: %s rows (error: %s)", len(q.get("features", [])), q.get("error"))
    ok = ok and len(q.get("features", [])) >= 1
    blocked = bool(post(f"{submit_url}/query", {"f": "json", "where": "1=1"}).get("error"))
    log.info("submit view refuses queries: %s", blocked)
    ok = ok and blocked
    log.info("delete test rows: %s", sublayer_of(gis, parent, "tables").delete_features(where="round='smoke'").get("deleteResults"))
    return ok


def smoke_test_areas(gis, parent, submit_url, public_url):
    x, y = -13358000, 4732000                        # a small square near Tahoe City, in Web Mercator like the page sends
    geom = {"rings": [[[x, y], [x, y + 200], [x + 200, y + 200], [x + 200, y], [x, y]]], "spatialReference": {"wkid": 102100}}
    row = {"reviewer_name": "Smoke Test", "agency": None, "reviewer_key": "deadbeef", "round": "smoke", "send_id": int(time.time() * 1000),
           "area_id": "smoke", "observed_when": "Jan. 2017 storm", "notes": "Test area", "area_acres": 9.9, "reporter_name": "Smoke Test"}
    r = post(f"{submit_url}/applyEdits", {"f": "json", "adds": json.dumps([{"geometry": geom, "attributes": row}]), "rollbackOnFailure": "true"})
    log.info("anonymous area add: %s", r.get("addResults") or r)
    ok = bool(r.get("addResults", [{}])[0].get("success"))
    q = post(f"{public_url}/query", {"f": "json", "where": "round='smoke'", "outFields": "*", "returnGeometry": "true", "outSR": "4326"})
    feats = q.get("features", [])
    log.info("anonymous area read back: %s features (error: %s)", len(feats), q.get("error"))
    ok = ok and len(feats) >= 1 and bool((feats[0].get("geometry") or {}).get("rings"))
    blocked = bool(post(f"{submit_url}/query", {"f": "json", "where": "1=1"}).get("error"))
    log.info("area submit view refuses queries: %s", blocked)
    ok = ok and blocked
    log.info("delete test areas: %s", sublayer_of(gis, parent, "layers").delete_features(where="round='smoke'").get("deleteResults"))
    return ok


def main():
    gis = GIS("home")
    log.info("signed in as %s at %s", gis.users.me.username, gis.url)
    found = {}
    for spec, keys in ((NOTES, ("submitUrl", "viewUrl")), (AREAS, ("areasSubmitUrl", "areasViewUrl"))):
        parent = ensure_parent(gis, spec)
        submit_item, submit_url = ensure_view(gis, spec, parent, "submit", f"{spec['service']}_submit", "Create")
        public_item, public_url = ensure_view(gis, spec, parent, "public", f"{spec['service']}_read", "Query") if spec["public"] else (None, None)
        log.info("parent (private): %s", sublayer_of(gis, parent, spec["kind"]).url)
        print(f"\nSURVEY.{keys[0]} = \"{submit_url}\"" + (f"\nSURVEY.{keys[1]} = \"{public_url}\"" if keys[1] else "")
              + f"\nparent item {parent.id}; submit view {submit_item.id}" + (f"; public view {public_item.id}" if public_item else "; no public view") + "\n")
        found[spec["service"]] = (parent, submit_url, public_url)
    if "--smoke-test" in sys.argv:
        # the test deletes its rows from the parent, which takes owning it; someone else's service is skipped
        results = {}
        for spec, test in ((NOTES, smoke_test), (AREAS, smoke_test_areas)):
            parent = found[spec["service"]][0]
            if mine(gis, parent):
                results[spec["parent"]] = "passed" if test(gis, *found[spec["service"]]) else "FAILED"
            else:
                results[spec["parent"]] = f"skipped (owned by {parent.owner})"
        log.info("smoke test: %s", "; ".join(f"{k} {v}" for k, v in results.items()))
        return 1 if "FAILED" in results.values() else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
