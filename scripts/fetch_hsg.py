"""Download the SSURGO map units with their hydrologic soil group for the runoff coefficient
surface of culvert_profile.py (profile.runoff_c_method: table).

    python scripts/fetch_hsg.py                    # writes profile.hsg (shapefile) from Soil Data Access
    python scripts/fetch_hsg.py --force            # overwrite
    python scripts/fetch_hsg.py --out C:\\tmp\\hsg.shp   # elsewhere (a test, or while F: is down)

One survey, CA693 (Tahoe Basin Area, California and Nevada), covers the whole basin in both
states. Polygons come from USDA NRCS Soil Data Access (https://sdmdataaccess.sc.egov.usda.gov,
Tabular REST service, WKT geometry in pages) with each map unit's dominant-condition group
(muaggatt.hydgrpdcd). Dual groups A/D, B/D, and C/D take the undrained letter
(profile.hsg_dual_as), as the CULVERT tool does. The Water map unit (the lake) carries group D
in SSURGO; it is written with no group (hsg_n 0) so the C surface falls back there instead of
scoring open water as the tightest soil. A JSON sidecar records the survey version
(sacatalog.saverest), the download date, and acres by group. Runs anywhere; about 17 MB.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely import wkt

from va_common import get_logger, load_cfg

SDA = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"
PAGE = 400
HSG_N = {"A": 1, "B": 2, "C": 3, "D": 4}
SQM_PER_ACRE = 4046.8564


def sda_query(sql: str) -> pd.DataFrame:
    r = requests.post(SDA, json={"query": sql, "format": "JSON+COLUMNNAME"}, timeout=300)
    r.raise_for_status()
    t = r.json().get("Table", [])
    return pd.DataFrame(t[1:], columns=t[0]) if t else pd.DataFrame()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--out", help="shapefile path instead of profile.hsg")
    args = ap.parse_args()
    log = get_logger("fetch_hsg")
    cfg = load_cfg()
    p = cfg["profile"]
    area = p.get("hsg_survey", "CA693")
    out = Path(args.out or p["hsg"])
    if out.exists() and not args.force:
        raise SystemExit(f"{out} exists; --force to overwrite")

    meta = sda_query(f"SELECT areaname, saverest FROM sacatalog WHERE areasymbol = '{area}'")
    if meta.empty:
        raise SystemExit(f"Survey area {area} not in Soil Data Access")
    n = int(sda_query(f"SELECT COUNT(*) AS n FROM mupolygon WHERE areasymbol = '{area}'").iloc[0, 0])
    log.info(f"{area} ({meta.at[0, 'areaname']}), version {meta.at[0, 'saverest']}: {n} polygons")

    frames = []
    for off in range(0, n, PAGE):
        sql = (f"SELECT mp.mupolygonkey AS mupolykey, mp.mukey, mp.musym, m.muname, ma.hydgrpdcd, "
               f"mp.mupolygongeo.STAsText() AS wkt FROM mupolygon mp "
               f"JOIN mapunit m ON m.mukey = mp.mukey LEFT JOIN muaggatt ma ON ma.mukey = mp.mukey "
               f"WHERE mp.areasymbol = '{area}' ORDER BY mp.mupolygonkey "
               f"OFFSET {off} ROWS FETCH NEXT {PAGE} ROWS ONLY")
        df = sda_query(sql)
        frames.append(df)
        log.info(f"  {off + len(df)} / {n}")
    df = pd.concat(frames, ignore_index=True)
    if len(df) != n:
        raise SystemExit(f"Expected {n} polygons, received {len(df)}")

    gdf = gpd.GeoDataFrame(df.drop(columns="wkt"), geometry=df["wkt"].map(wkt.loads), crs="EPSG:4326")
    gdf = gdf.to_crs(epsg=cfg["output"]["target_epsg"])
    grp = gdf["hydgrpdcd"].astype("string").str.strip()
    gdf["hsg"] = grp.where(~grp.str.contains("/", na=False), p.get("hsg_dual_as", "D")).fillna("")
    water = gdf["musym"].eq("W") | gdf["muname"].str.strip().str.lower().eq("water")
    gdf.loc[water, "hsg"] = ""
    gdf["hsg_n"] = gdf["hsg"].map(HSG_N).fillna(0).astype(int)
    gdf["area_ac"] = (gdf.area / SQM_PER_ACRE).round(2)
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = ["mupolykey", "mukey", "musym", "muname", "hydgrpdcd", "hsg", "hsg_n", "area_ac", "geometry"]
    gdf[cols].to_file(out)
    by = gdf.groupby(gdf["hsg"].replace("", "none"))["area_ac"].sum().round(0)
    log.info(f"Wrote {out} ({len(gdf)} polygons). Acres by group (Water map unit and no data = none):\n"
             + by.to_string())
    side = {"survey": area, "areaname": meta.at[0, "areaname"], "saverest": meta.at[0, "saverest"],
            "downloaded": date.today().isoformat(), "source": SDA, "polygons": len(gdf),
            "dual_groups_as": p.get("hsg_dual_as", "D"), "water_map_unit": "no group (hsg_n 0)",
            "acres_by_group": {k: float(v) for k, v in by.items()}}
    out.with_suffix(".json").write_text(json.dumps(side, indent=2))


if __name__ == "__main__":
    main()
