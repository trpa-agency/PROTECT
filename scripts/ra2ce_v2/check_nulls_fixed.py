"""Two checks on the completed run.

A. The 388 in-basin features that read NULL in PROTECT_VA were all collision
   losers. Are they now represented by a criticality row of their own?

B. verify reported short edges rising from 1,368 (base graph, post-repair) to
   3,398 in the OD graph. OD snapping splits edges at snap points, so some
   repaired geometry may not survive into the graph that was actually routed.
   Measure how much of the repair reached the router.
"""
import ast
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import linemerge

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from preprocess import find_collisions  # noqa: E402

SRC = HERE.parent / "ra2ce" / "static" / "network" / "overture_drive_routable.shp"
NEW = HERE / "output" / "optimal_route_origin_destination"


def _ids(v):
    if isinstance(v, (list, tuple, np.ndarray)):
        return list(v)
    if isinstance(v, str):
        try:
            x = ast.literal_eval(v)
            return list(x) if isinstance(x, (list, tuple)) else [x]
        except Exception:
            return []
    if v is None:
        return []
    try:
        return [] if pd.isna(v) else [v]
    except Exception:
        return [v]


def check_a():
    print("=" * 70)
    print("A. Were the collision losers recovered?")
    print("=" * 70)
    net = gpd.read_file(SRC)
    keys, counts = find_collisions(net)
    net["k"] = keys.values
    coll = net[(net.k.map(counts) > 1) & (net.In_Basin == 1)].copy()
    print("in-basin features involved in a collision: {:,}".format(len(coll)))

    crit = gpd.read_file(NEW / "tahoe_od_medicalfacilities_criticality.gpkg")
    crit = crit.set_crs(4326, allow_override=True).to_crs(3310)
    sidx = crit.sindex
    c3 = coll.to_crs(3310)

    represented = 0
    with_traffic = 0
    for geom in c3.geometry:
        buf = geom.buffer(5)
        cand = list(sidx.query(buf))
        if not cand:
            continue
        hits = crit.iloc[cand]
        hits = hits[hits.geometry.intersects(buf)]
        if hits.empty:
            continue
        ov = hits.geometry.intersection(buf).length
        best = ov.max()
        if best >= 0.5 * geom.length:
            represented += 1
            if (hits.loc[ov.idxmax(), "traffic"] or 0) > 0:
                with_traffic += 1
    print("  represented by a criticality row (>=50% overlap): {:,} / {:,} ({:.1f}%)".format(
        represented, len(c3), 100 * represented / len(c3)))
    print("  of those, carrying traffic > 0                  : {:,}".format(with_traffic))
    print("  (in scripts/ra2ce, 388 of these had NO row at all)")


def check_b():
    print()
    print("=" * 70)
    print("B. How much of the geometry repair survived OD snapping?")
    print("=" * 70)
    gd = HERE / "output" / "optimal_route_origin_destination" / "tahoe_od_medicalfacilities_graph"
    bn = gpd.read_feather(gd / "base_network.feather").set_crs(4326, allow_override=True)
    od = gpd.read_file(gd / "origins_destinations_graph_edges.gpkg")
    geom_by_id = dict(zip(bn.rfid_c, bn.geometry))
    len_by_id = dict(zip(bn.rfid_c, bn.to_crs(3310).geometry.length))

    L = od.set_crs(4326, allow_override=True).to_crs(3310).length
    rows = []
    for li, rc, gm in zip(L, od.rfid_c, od.geometry):
        ids = _ids(rc)
        if not ids or not li or li <= 0:
            continue
        s = sum(len_by_id.get(i, np.nan) for i in ids)
        if np.isnan(s) or s <= 0:
            continue
        node_poly = (len(gm.coords) == len(ids) + 1)
        rows.append((li / s, len(ids), node_poly))
    d = pd.DataFrame(rows, columns=["ratio", "n_complex", "node_poly"])
    short = d[d.ratio < 0.95]
    print("OD-graph edges compared: {:,}".format(len(d)))
    print("  short (<0.95): {:,} ({:.1f}%)   min ratio {:.3f}".format(
        len(short), 100 * len(short) / len(d), d.ratio.min()))
    print("  of the short ones, still a pure node polyline: {:,} ({:.0f}%)".format(
        int(short.node_poly.sum()), 100 * short.node_poly.mean()))
    print()
    print("  single-segment edges short: {:,} of {:,}".format(
        int((d[d.n_complex == 1].ratio < 0.95).sum()), int((d.n_complex == 1).sum())))
    print("  multi-segment  edges short: {:,} of {:,}".format(
        int((d[d.n_complex > 1].ratio < 0.95).sum()), int((d.n_complex > 1).sum())))

    # does the OD graph carry repaired (rich) geometry at all?
    rich = sum(1 for g in od.geometry if g is not None and len(g.coords) > 8)
    print()
    print("  OD-graph edges with >8 vertices (repair fingerprint): {:,}".format(rich))
    print("  (the repaired base graph had 12,630)")


if __name__ == "__main__":
    check_a()
    check_b()
