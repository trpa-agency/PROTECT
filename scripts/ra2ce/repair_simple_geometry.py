"""Rebuild each simplified edge's geometry from its complex constituents.

RA2CE's simplified graph always draws an edge as a polyline through the chain's
NODE positions; it never concatenates the constituent geometries. Where every
constituent is a straight 2-point segment that is identical to the real road.
Where any constituent carries interior vertices, the curve is thrown away and
the routing weight is understated.

Every edge records the complex segments it covers in `rfid_c`, and those
geometries are all present in base_network.feather, so the true line is just
shapely.ops.linemerge of them.
"""
import ast, numpy as np, pandas as pd, geopandas as gpd
from shapely.ops import linemerge
from shapely.geometry import LineString, Point


def _ids(v):
    if isinstance(v, (list, tuple, np.ndarray)): return list(v)
    if isinstance(v, str):
        try:
            x = ast.literal_eval(v)
            return list(x) if isinstance(x, (list, tuple)) else [x]
        except Exception: return []
    if v is None: return []
    try: return [] if pd.isna(v) else [v]
    except Exception: return [v]


def repair_simple_geometry(graph_simple, base_network, crs_m=3310, verbose=True, tol=1e-7):
    """Only accepts a merged line that still terminates on the edge's own two
    nodes (either orientation). An `rfid_c` list can include a segment that is
    not on this edge's path - 3,342 segments are referenced by two simple edges -
    and linemerge then yields a line that starts or ends somewhere else. Those
    keep RA2CE's node polyline."""
    bn = base_network.set_crs(4326, allow_override=True)
    geom_by_id = dict(zip(bn.rfid_c, bn.geometry))
    len_by_id = dict(zip(bn.rfid_c, bn.to_crs(crs_m).geometry.length))

    node_geom = {n: d.get("geometry") for n, d in graph_simple.nodes(data=True)}
    stats = dict(edges=0, multi=0, repaired=0, unmergeable=0, missing=0,
                 endpoint_reject=0, len_before=0.0, len_after=0.0)
    it = (graph_simple.edges(data=True, keys=True) if graph_simple.is_multigraph()
          else graph_simple.edges(data=True))
    fixes = []
    for e in it:
        d = e[-1]; stats["edges"] += 1
        ids = _ids(d.get("rfid_c")); geom = d.get("geometry")
        if geom is None or len(ids) < 2: continue
        stats["multi"] += 1
        if not all(i in geom_by_id for i in ids):
            stats["missing"] += 1; continue
        merged = linemerge([geom_by_id[i] for i in ids])
        if not isinstance(merged, LineString):
            stats["unmergeable"] += 1; continue
        if len(merged.coords) == len(geom.coords): continue   # already correct
        nu, nv = node_geom.get(e[0]), node_geom.get(e[1])
        if nu is not None and nv is not None:
            a, b = Point(merged.coords[0]), Point(merged.coords[-1])
            fwd = a.distance(nu) < tol and b.distance(nv) < tol
            rev = a.distance(nv) < tol and b.distance(nu) < tol
            if not (fwd or rev):
                stats["endpoint_reject"] += 1
                continue
        fixes.append((e, merged, sum(len_by_id[i] for i in ids)))

    if fixes:
        old = gpd.GeoSeries([f[0][-1]["geometry"] for f in fixes], crs=4326).to_crs(crs_m).length
        new = gpd.GeoSeries([f[1] for f in fixes], crs=4326).to_crs(crs_m).length
        stats["len_before"] = float(old.sum()); stats["len_after"] = float(new.sum())
        for (e, merged, csum), nl in zip(fixes, new):
            d = e[-1]
            d["geometry"] = merged
            d["length"] = float(nl)
            if d.get("avgspeed"):
                d["time"] = float(nl) / 1000.0 / d["avgspeed"]
            stats["repaired"] += 1
    if verbose:
        print(f"  simple edges                 : {stats['edges']:,}")
        print(f"  multi-segment edges          : {stats['multi']:,}")
        print(f"  repaired                     : {stats['repaired']:,}")
        print(f"  unmergeable (MultiLineString): {stats['unmergeable']:,}")
        print(f"  rejected: merged line misses the edge's own nodes: {stats['endpoint_reject']:,}")
        print(f"  rfid_c not in base_network   : {stats['missing']:,}")
        print(f"  length of repaired edges     : {stats['len_before']:,.0f} m -> {stats['len_after']:,.0f} m "
              f"({stats['len_after']-stats['len_before']:+,.0f} m)")
    return graph_simple, stats


if __name__ == "__main__":
    import pickle
    S = r"C:/Users/amcclary/AppData/Local/Temp/claude/c--Users-amcclary-Documents-GitHub-PROTECT/48254e3f-075d-43a4-8182-7ccb66c11a02/scratchpad/netrepro/static/output_graph"
    bn = gpd.read_feather(S + "/base_network_FIXED.feather")
    g = pickle.load(open(S + "/graph_simple_FIXED.p", "rb"))

    def ratios(g, bn):
        bnm = bn.set_crs(4326, allow_override=True).to_crs(3310)
        sl = dict(zip(bn.rfid_c, bnm.geometry.length))
        it = (g.edges(data=True, keys=True) if g.is_multigraph() else g.edges(data=True))
        geoms, sums = [], []
        for e in it:
            d = e[-1]; ids = _ids(d.get("rfid_c"))
            if d.get("geometry") is None or not ids: continue
            s = sum(sl.get(i, np.nan) for i in ids)
            if np.isnan(s) or s <= 0: continue
            geoms.append(d["geometry"]); sums.append(s)
        L = gpd.GeoSeries(geoms, crs=4326).to_crs(3310).length
        return np.asarray(L) / np.array(sums), np.asarray(L).sum()

    r0, tot0 = ratios(g, bn)
    print("BEFORE repair")
    print(f"  short (<0.95): {(r0<0.95).sum():,} / {len(r0):,} ({100*(r0<0.95).mean():.1f}%)   min ratio {r0.min():.3f}")
    print(f"  total simple-graph length: {tot0:,.0f} m\n")
    print("REPAIR")
    g, st = repair_simple_geometry(g, bn)
    r1, tot1 = ratios(g, bn)
    print("\nAFTER repair")
    print(f"  short (<0.95): {(r1<0.95).sum():,} / {len(r1):,} ({100*(r1<0.95).mean():.1f}%)   min ratio {r1.min():.3f}")
    print(f"  total simple-graph length: {tot1:,.0f} m   ({tot1-tot0:+,.0f} m, {100*(tot1-tot0)/tot0:+.2f}%)")
    print(f"  source network length     : 8,852,786 m")
