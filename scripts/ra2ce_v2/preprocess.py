"""Resolve endpoint-pair collisions before handing a network to RA2CE.

RA2CE's VectorNetworkWrapper builds a plain nx.DiGraph and then calls
to_undirected(), so two links sharing the same unordered pair of endpoint
coordinates collapse into one edge and the loser's geometry is overwritten.
Splitting all but one member of each colliding group at its midpoint gives
each link a distinct node pair, so nothing is overwritten.
"""
import numpy as np, pandas as pd, geopandas as gpd
from collections import Counter
from shapely.ops import substring


def _pair_key(geom, ndigits=12):
    a = tuple(np.round(geom.coords[0], ndigits))
    b = tuple(np.round(geom.coords[-1], ndigits))
    return (a, b) if a <= b else (b, a)


def find_collisions(gdf):
    keys = [_pair_key(g) for g in gdf.geometry]
    counts = Counter(keys)
    return pd.Series(keys, index=gdf.index), counts


def split_colliding_links(gdf, length_col="length_m", scale_cols=("length_m", "Shape_Leng", "DriveTime"),
                          max_passes=5, verbose=True):
    gdf = gdf.reset_index(drop=True).copy()
    total_split = 0
    for p in range(1, max_passes + 1):
        keys, counts = find_collisions(gdf)
        groups = {k: idx for k, idx in keys.groupby(keys).groups.items() if counts[k] > 1}
        if not groups:
            if verbose:
                print(f"  pass {p}: no collisions left")
            break
        # keep the shortest member of each group intact, split the rest
        to_split = []
        for k, idx in groups.items():
            members = list(idx)
            members.sort(key=lambda i: gdf.at[i, length_col] if length_col in gdf.columns
                         else gdf.geometry[i].length)
            to_split.extend(members[1:])
        if verbose:
            print(f"  pass {p}: {len(groups):,} colliding groups, splitting {len(to_split):,} features")
        new_rows, drop = [], []
        for i in to_split:
            line = gdf.geometry[i]
            half = line.length / 2.0
            a, b = substring(line, 0, half), substring(line, half, line.length)
            if a.is_empty or b.is_empty or a.length == 0 or b.length == 0:
                continue          # degenerate, leave it alone
            base = gdf.loc[i].to_dict()
            for part, frac in ((a, a.length / line.length), (b, b.length / line.length)):
                row = dict(base)
                row["geometry"] = part
                for c in scale_cols:
                    if c in row and pd.notna(row[c]):
                        row[c] = row[c] * frac
                new_rows.append(row)
            drop.append(i)
        if not drop:
            break
        total_split += len(drop)
        gdf = pd.concat(
            [gdf.drop(index=drop), gpd.GeoDataFrame(new_rows, crs=gdf.crs)],
            ignore_index=True,
        )
        gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=gdf.crs)
    return gdf, total_split


if __name__ == "__main__":
    SRC = r"C:/Users/amcclary/Documents/GitHub/PROTECT/scripts/ra2ce/static/network/overture_drive_routable.shp"
    net = gpd.read_file(SRC)
    print(f"source features: {len(net):,}")
    keys, counts = find_collisions(net)
    n_groups = sum(1 for v in counts.values() if v > 1)
    print(f"colliding groups: {n_groups:,}  features involved: {sum(v for v in counts.values() if v>1):,}")
    print(f"features RA2CE would silently overwrite: {len(net) - len(counts):,}\n")

    out, n_split = split_colliding_links(net)
    keys2, counts2 = find_collisions(out)
    print(f"\nafter preprocessing: {len(out):,} features ({len(out)-len(net):+,})")
    print(f"  features split: {n_split:,}")
    print(f"  remaining colliding groups: {sum(1 for v in counts2.values() if v>1):,}")
    print(f"  features that would still be overwritten: {len(out) - len(counts2):,}")
    tot_before = net.to_crs(3310).length.sum()
    tot_after = out.to_crs(3310).length.sum()
    print(f"\ntotal network length preserved: {tot_before:,.1f} m -> {tot_after:,.1f} m "
          f"(delta {tot_after-tot_before:+.3f} m)")
    OUT = r"C:/Users/amcclary/AppData/Local/Temp/claude/c--Users-amcclary-Documents-GitHub-PROTECT/48254e3f-075d-43a4-8182-7ccb66c11a02/scratchpad/netrepro/static/network/overture_split.shp"
    out.to_file(OUT)
    print(f"written -> {OUT}")
