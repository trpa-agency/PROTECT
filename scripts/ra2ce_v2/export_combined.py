"""Combine the four v2 criticality layers into one network layer.

All four are the same 97,814-row complex network with identical rfid_c indexing,
so this is a column-wise merge on rfid_c rather than a spatial join. Mirrors the
schema of scripts/ra2ce/output_rerun/tahoe_od_criticality_combined.* so anything
built against that keeps working.

Writes:
  output/tahoe_od_criticality_combined_v2.gpkg
  output/tahoe_od_criticality_combined_v2.shp        (10-char field names)
  output/tahoe_od_criticality_combined_v2_fields.csv (field dictionary)
"""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

HERE = Path(__file__).resolve().parent
CRIT = HERE / "output" / "optimal_route_origin_destination"
OUT = HERE / "output"

# published field suffix -> (analysis name on disk, routing mode, destination description)
ANALYSES = [
    ("evacuation",         "tahoe_od_evacuation",          "nearest",
     "7 basin highway exit points (Destinations.shp)"),
    ("law_enforcement",    "tahoe_od_locallawenforcement", "nearest",
     "police/sheriff/CHP facilities"),
    ("medical_facilities", "tahoe_od_medicalfacilities",   "gravity",
     "hospitals / urgent care"),
    ("emergency_shelters", "tahoe_od_evacuationshelters",  "gravity",
     "community centres / schools"),
]

METRICS = [
    ("traffic",      "traffic",              "trf",
     "population routed over this segment (utilitarian)"),
    ("egalitarian",  "traffic_egalitarian",  "egl",
     "number of trips over this segment, unweighted by population"),
    ("prioritarian", "traffic_prioritarian", "pri",
     "population x equity weight (1.0-2.0, poverty rate)"),
    ("routed",       "routed",               "rtd",
     "1 = on at least one optimal route"),
    ("par_alt",      "par_alt",              "alt",
     "1 = lies only on a parallel alternative edge; never carries routed traffic"),
]

SHORT = {"evacuation": "evac", "law_enforcement": "law",
         "medical_facilities": "med", "emergency_shelters": "shel"}


def main():
    base = None
    rows = []
    for suffix, disk, mode, dest in ANALYSES:
        p = CRIT / (disk + "_criticality.gpkg")
        if not p.exists():
            raise FileNotFoundError(p)
        g = gpd.read_file(p)
        n_dest = _dest_count(disk)
        print("{:<22} {:,} rows  mode={:<8} destinations={}".format(
            disk, len(g), mode, n_dest))
        if base is None:
            keep = ["rfid_c", "rfid", "node_A", "node_B", "edge_fid",
                    "highway", "avgspeed", "length", "time", "geometry"]
            base = g[[c for c in keep if c in g.columns]].copy()
            base = base.sort_values("rfid_c").reset_index(drop=True)
        g = g.sort_values("rfid_c").reset_index(drop=True)
        assert (g.rfid_c.values == base.rfid_c.values).all(), \
            "rfid_c indexing differs between analyses - cannot merge column-wise"
        for metric, src_col, short_metric, meaning in METRICS:
            out_col = "{}_{}".format(metric, suffix)
            base[out_col] = g[src_col].values
            rows.append({
                "gpkg_field": out_col,
                "shapefile_field": "{}_{}".format(short_metric, SHORT[suffix]),
                "analysis": suffix,
                "metric": metric,
                "routing_mode": mode,
                "destinations": "{} {}".format(n_dest, dest) if n_dest else dest,
                "meaning": meaning,
            })

    OUT.mkdir(parents=True, exist_ok=True)
    gpkg = OUT / "tahoe_od_criticality_combined_v2.gpkg"
    base.to_file(gpkg, driver="GPKG")
    print("\nwrote {}  ({:,} rows, {} fields)".format(gpkg.name, len(base), len(base.columns) - 1))

    fields = pd.DataFrame(rows)
    fields.to_csv(OUT / "tahoe_od_criticality_combined_v2_fields.csv", index=False)
    print("wrote {}".format((OUT / 'tahoe_od_criticality_combined_v2_fields.csv').name))

    # shapefile copy with 10-char names, for ArcGIS Pro
    ren = dict(zip(fields.gpkg_field, fields.shapefile_field))
    shp = base.rename(columns=ren)
    shp.to_file(OUT / "tahoe_od_criticality_combined_v2.shp")
    print("wrote {} (fields renamed to <=10 chars)".format(
        (OUT / 'tahoe_od_criticality_combined_v2.shp').name))

    nz = {c: int((base[c] > 0).sum()) for c in base.columns if c.startswith("traffic_")}
    print("\nsegments carrying traffic > 0:")
    for k, v in nz.items():
        print("  {:<34} {:>7,}".format(k, v))


def _dest_count(disk):
    p = HERE / "static" / "network" / (disk + "_destinations.shp")
    if not p.exists():
        return None
    return len(gpd.read_file(p, read_geometry=False))


if __name__ == "__main__":
    sys.exit(main())
