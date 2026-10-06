"""The headline check: does 4th Street's 55.4 m middle piece now carry traffic?

In scripts/ra2ce/ this link had NO row in base_network at all - it collided with a
parallel 156.84 m service road, lost, and its traffic was painted on the service
road instead. It is OBJECTID 15271 in PROTECT_VA, NULL on every OD field.
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "ra2ce" / "output_rerun" / "optimal_route_origin_destination"
NEW = HERE / "output" / "optimal_route_origin_destination"
SRC = HERE.parent / "ra2ce" / "static" / "network" / "overture_drive_routable.shp"

FOURTH = "5945adb5-300e-4542-b160-6202145e7820"
SVC = "e162d010-94eb-4405-8d47-c34a18faf3a2"


def cover(crit, geom, tol_m=5):
    """How much of `geom` is represented by rows of `crit`, as a percentage."""
    from shapely.ops import unary_union
    g = gpd.GeoSeries([geom], crs=4326).to_crs(3310).iloc[0]
    c = crit.set_crs(4326, allow_override=True).to_crs(3310)
    hits = c[c.geometry.intersects(g.buffer(tol_m))]
    if hits.empty:
        return 0.0, None
    u = unary_union(hits.geometry.tolist()).buffer(tol_m)
    pct = 100 * g.intersection(u).length / g.length
    exact = [i for i, x in zip(hits.index, hits.geometry)
             if x.hausdorff_distance(g) < 1e-6]
    return pct, (hits.loc[exact[0]] if exact else None)


def main():
    net = gpd.read_file(SRC, where="segment_id='{}'".format(FOURTH))
    piece = net[net.length_m.between(55, 56)].iloc[0].geometry
    svc = gpd.read_file(SRC, where="segment_id='{}'".format(SVC)).iloc[0].geometry
    print("4th St 55.4 m link and the parallel 156.84 m service road\n")

    for label, d in (("OLD  scripts/ra2ce", OLD), ("NEW  scripts/ra2ce_v2", NEW)):
        p = d / "tahoe_od_medicalfacilities_criticality.gpkg"
        if not p.exists():
            print("{}: missing".format(label))
            continue
        bb = gpd.GeoSeries([piece, svc], crs=4326).total_bounds
        pad = 0.004
        crit = gpd.read_file(p, bbox=(bb[0]-pad, bb[1]-pad, bb[2]+pad, bb[3]+pad))
        pct4, row4 = cover(crit, piece)
        pcts, rows = cover(crit, svc)
        print(label)
        print("   4th St 55.4 m link : {:5.1f}% represented".format(pct4), end="")
        if row4 is not None:
            print("  | own row: traffic={:.1f} routed={} par_alt={}".format(
                row4.traffic, row4.routed, row4.par_alt))
        else:
            print("  | NO exact row of its own")
        print("   service road       : {:5.1f}% represented".format(pcts), end="")
        if rows is not None:
            print("  | own row: traffic={:.1f} routed={} par_alt={}".format(
                rows.traffic, rows.routed, rows.par_alt))
        else:
            print("  | no exact row (it was split by preprocessing)")
        print()


if __name__ == "__main__":
    sys.exit(main())
