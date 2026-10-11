"""Create (or check) the ArcGIS Online table that html/workshop-feedback.html sends notes to.

Layout, following the EIP Funding Priorities picks survey (maps repo, eip/funding-priorities.html):

* a private hosted table, "PROTECT Workshop Feedback notes", one row per send;
* a public view with Create only ("... notes submit"), which the page posts to with applyEdits;
* a public view with Query only ("... notes public view"), which the page reads to show
  everyone's notes.

Built Oct. 10, 2026 (owner mbindl, TRPA ArcGIS Online). What did not work in this org, so the
page is designed around it: hiding a field on a view of a hosted *table* (sourceLayerFields at
creation or by updateDefinition reports success and changes nothing), and editor tracking
(editFieldsInfo stays unset, CreationDate is never filled). Therefore the page never sends the
email address, only its hash as reviewer_key, and it orders sends by OBJECTID and timestamps
them itself inside notes_json.

Run from arcgispro-py3 while ArcGIS Pro is signed in to ArcGIS Online (GIS("home") reuses that
sign-in; no password in this file). Safe to run again: it finds the items by title and only
creates what is missing. --smoke-test posts one anonymous row to the submit view, reads it back
from the public view, confirms the submit view refuses queries, and deletes the row.

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

PARENT_TITLE = "PROTECT Workshop Feedback notes"
SUBMIT_TITLE = "PROTECT Workshop Feedback notes submit"
PUBLIC_TITLE = "PROTECT Workshop Feedback notes public view"
SERVICE_NAME = "PROTECT_Workshop_Feedback_notes"
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


def find(gis, title):
    hits = [i for i in gis.content.search(f'title:"{title}" owner:{gis.users.me.username}', item_type="Feature Service", max_items=20) if i.title == title]
    return hits[0] if hits else None


def table_of(gis, item):
    for _ in range(12):                              # a new service can take a moment to list its table
        tables = FeatureLayerCollection.fromitem(gis.content.get(item.id)).tables
        if tables:
            return Table(tables[0].url, gis)
        time.sleep(5)
    raise RuntimeError(f"{item.title}: no table after a minute; check it in ArcGIS Online")


def share_public(gis, item):
    try:
        from arcgis.gis import SharingLevel
        item.sharing.sharing_level = SharingLevel.EVERYONE
    except Exception:
        item.share(everyone=True, org=True)
    log.info("shared with everyone: %s (%s)", item.title, gis.content.get(item.id).access)


def ensure_parent(gis):
    item = find(gis, PARENT_TITLE)
    if item:
        log.info("parent exists: %s (%s)", item.title, item.id)
        return item
    log.info("creating hosted table %s", PARENT_TITLE)
    item = gis.content.create_service(name=SERVICE_NAME, service_type="featureService", has_static_data=False,
                                      capabilities="Create,Query,Update,Delete,Editing", tags=TAGS,
                                      snippet="Feedback sent from the PROTECT Workshop Feedback page (data.trpa.gov/PROTECT).")
    item.update({"title": PARENT_TITLE})
    log.info("addToDefinition: %s", FeatureLayerCollection.fromitem(item).manager.add_to_definition({"tables": [TABLE_DEF]}))
    table_of(gis, item)
    return gis.content.get(item.id)


def ensure_view(gis, parent, title, name, capabilities):
    item = find(gis, title)
    if item:
        log.info("view exists: %s (%s)", title, item.id)
    else:
        log.info("creating view %s (%s)", title, capabilities)
        src = table_of(gis, parent).properties
        item = gis.content.create_service(name=name, is_view=True, service_type="featureService", capabilities=capabilities, tags=TAGS,
                                          snippet=f"{capabilities} view of {PARENT_TITLE} for the Workshop Feedback page.")
        item.update({"title": title})
        tdef = {"adminLayerInfo": {"viewLayerDefinition": {"sourceServiceName": SERVICE_NAME, "sourceLayerId": 0, "sourceLayerFields": "*"}},
                "name": "notes", "type": "Table", "displayField": "reviewer_name", "objectIdField": "OBJECTID",
                "fields": [dict(f) for f in src["fields"]], "capabilities": capabilities, "hasAttachments": False}
        log.info("addToDefinition: %s", FeatureLayerCollection.fromitem(item).manager.add_to_definition({"tables": [tdef]}))
        item = gis.content.get(item.id)
    tbl = table_of(gis, item)
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
    log.info("delete test rows: %s", table_of(gis, parent).delete_features(where="round='smoke'").get("deleteResults"))
    return ok


def main():
    gis = GIS("home")
    log.info("signed in as %s at %s", gis.users.me.username, gis.url)
    parent = ensure_parent(gis)
    submit_item, submit_url = ensure_view(gis, parent, SUBMIT_TITLE, f"{SERVICE_NAME}_submit", "Create")
    public_item, public_url = ensure_view(gis, parent, PUBLIC_TITLE, f"{SERVICE_NAME}_read", "Query")
    log.info("parent table (private): %s", table_of(gis, parent).url)
    print(f"\nSURVEY.submitUrl = \"{submit_url}\"\nSURVEY.viewUrl   = \"{public_url}\"\nparent item {parent.id}; submit view {submit_item.id}; public view {public_item.id}\n")
    if "--smoke-test" in sys.argv:
        ok = smoke_test(gis, parent, submit_url, public_url)
        log.info("smoke test %s", "passed" if ok else "FAILED")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
