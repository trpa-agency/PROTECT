"""Corrected RA2CE OD criticality pipeline.

Two defects in RA2CE 1.2.2 corrupt the Tahoe network. Both are fixed here,
before any routing happens.

1. Parallel-link collapse. VectorNetworkWrapper builds a plain nx.DiGraph and
   then calls to_undirected(), producing a plain nx.Graph. Two source links
   sharing a pair of endpoint coordinates therefore collapse into one edge and
   the loser geometry is overwritten with no warning. 2,529 of 95,285 Tahoe
   features were lost this way, which is exactly the 95,285 -> 92,756 row drop
   in base_network.feather, and it is why 388 in-basin streets read NULL rather
   than 0 in PROTECT_VA. Stage `prepare` splits one member of each colliding
   pair at its midpoint so every link gets a distinct node pair.

2. Simplified geometry is never concatenated. Every multi-segment edge in the
   simplified routing graph is drawn as a polyline through the chain NODE
   positions - 100% of them have n_vert == n_complex + 1. Where the source
   segments are straight this is identical to the real road, which is why it
   hides; where a constituent curves, the curve is discarded and the routing
   weight is understated. Stage `repair` rebuilds each edge from its rfid_c
   constituents with shapely.ops.linemerge.

Ordering matters: the repair rewrites geometry, length and time on the routing
graph, so it has to land before Dijkstra runs, not after.

Stages (run all, or a subset with --stages):
  prepare    split colliding links  -> static/network/overture_split.shp
  basegraph  RA2CE network build    -> static/output_graph/base_graph.p
                                       static/output_graph/base_network.feather
  repair     linemerge repair of base_graph.p (original kept as .orig)
  route      per-analysis OD routing + criticality, reusing the repaired graph
  slr        single link redundancy (detour length) on the repaired graph
  verify     post-run checks

Usage:
  python pipeline.py                      # everything
  python pipeline.py --stages prepare basegraph repair
  python pipeline.py --stages route --analyses medicalfacilities
"""
import argparse
import json
import logging
import pickle
import shutil
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SOURCE_NETWORK = HERE.parent / "ra2ce" / "static" / "network" / "overture_drive_routable.shp"
SPLIT_NETWORK = HERE / "static" / "network" / "overture_split.shp"
OUTPUT_GRAPH = HERE / "static" / "output_graph"
LOGS = HERE / "logs"

_GDB = r"F:\GIS\PROJECTS\Transportation\Protect\PROTECT_analysis\PROTECT_analysis.gdb"

DESTINATIONS = {
    "locallawenforcement": _GDB + chr(92) + "LocalLawEnforcement",
    "medicalfacilities":   _GDB + chr(92) + "MedicalFacilities",
    "evacuationshelters":  _GDB + chr(92) + "EvacuationShelters",
    "evacuation":          None,   # Destinations.shp - the 7 basin exit points
}

_t0 = time.time()


def log(msg):
    line = "[{:8.1f}s] {}".format(time.time() - _t0, msg)
    print(line, flush=True)
    LOGS.mkdir(exist_ok=True)
    with open(LOGS / "pipeline.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ----------------------------------------------------------------------------
def stage_prepare(force=False):
    import geopandas as gpd
    from preprocess import split_colliding_links, find_collisions

    if SPLIT_NETWORK.exists() and not force:
        log("prepare: {} exists, skipping (use --force)".format(SPLIT_NETWORK.name))
        return
    log("prepare: reading {}".format(SOURCE_NETWORK))
    net = gpd.read_file(SOURCE_NETWORK)
    _, counts = find_collisions(net)
    n_groups = sum(1 for v in counts.values() if v > 1)
    log("prepare: {:,} features, {:,} colliding endpoint pairs, "
        "{:,} would be silently overwritten".format(len(net), n_groups, len(net) - len(counts)))
    out, n_split = split_colliding_links(net, verbose=False)
    _, counts2 = find_collisions(out)
    remaining = sum(1 for v in counts2.values() if v > 1)
    before = net.to_crs(3310).length.sum()
    after = out.to_crs(3310).length.sum()
    assert remaining == 0, "still {} colliding groups after split".format(remaining)
    assert abs(after - before) < 1.0, "length changed by {:.3f} m".format(after - before)
    out.to_file(SPLIT_NETWORK)
    log("prepare: split {:,} features -> {:,} total, 0 collisions left, "
        "length {:,.1f} m preserved".format(n_split, len(out), before))


# ----------------------------------------------------------------------------
def stage_basegraph(force=False):
    import nb_helpers as nb  # noqa: F401  (sets PROJ, imports RA2CE)
    import geopandas as gpd
    from ra2ce.network.networks import Network
    from ra2ce.network.graph_files.graph_files_collection import GraphFilesCollection
    from ra2ce.network.network_config_data.network_config_data import (
        NetworkSection, NetworkConfigData,
    )
    from ra2ce.network.network_config_data.enums.source_enum import SourceEnum
    from pyproj import CRS

    bg = OUTPUT_GRAPH / "base_graph.p"
    if bg.exists() and not force:
        log("basegraph: {} exists, skipping (use --force)".format(bg.name))
        return
    if OUTPUT_GRAPH.exists():
        shutil.rmtree(OUTPUT_GRAPH)
    OUTPUT_GRAPH.mkdir(parents=True, exist_ok=True)

    cfg = NetworkConfigData(
        root_path=HERE, static_path=HERE / "static", crs=CRS.from_epsg(4326),
        network=NetworkSection(source=SourceEnum.SHAPEFILE,
                               primary_file=SPLIT_NETWORK, save_gpkg=True),
    )
    log("basegraph: building network (complex -> simple -> segment) ...")
    net = Network(cfg, GraphFilesCollection())
    net._get_new_network_and_graph(["pickle", "gpkg"])

    bn = gpd.read_feather(OUTPUT_GRAPH / "base_network.feather")
    n_in = len(gpd.read_file(SPLIT_NETWORK, columns=["segment_id"], read_geometry=False))
    log("basegraph: input {:,} features -> complex rows {:,} (lost {:,})".format(
        n_in, len(bn), n_in - len(bn)))
    if n_in != len(bn):
        log("basegraph: WARNING {:,} rows still lost - expected 0".format(n_in - len(bn)))


# ----------------------------------------------------------------------------
def stage_repair(force=False):
    import geopandas as gpd
    import networkx as nx
    from repair_simple_geometry import repair_simple_geometry

    bg = OUTPUT_GRAPH / "base_graph.p"
    orig = OUTPUT_GRAPH / "base_graph.p.orig"
    if orig.exists() and not force:
        log("repair: already applied (base_graph.p.orig present), skipping")
        return
    shutil.copy2(bg, orig)
    bn = gpd.read_feather(OUTPUT_GRAPH / "base_network.feather")
    g = pickle.load(open(bg, "rb"))
    log("repair: loaded simple graph, {:,} edges".format(g.number_of_edges()))
    n0, e0 = g.number_of_nodes(), g.number_of_edges()
    c0 = nx.number_connected_components(g) if not g.is_directed() else None
    g, st = repair_simple_geometry(g, bn, verbose=False)
    c1 = nx.number_connected_components(g) if not g.is_directed() else None
    assert (g.number_of_nodes(), g.number_of_edges()) == (n0, e0), "topology changed"
    assert c0 == c1, "connected components changed {} -> {}".format(c0, c1)
    with open(bg, "wb") as f:
        pickle.dump(g, f, protocol=4)
    log("repair: repaired {:,} of {:,} multi-segment edges; {:,} rejected by the "
        "endpoint guard; {:,} unmergeable".format(
            st["repaired"], st["multi"], st["endpoint_reject"], st["unmergeable"]))
    log("repair: length of repaired edges {:,.0f} m -> {:,.0f} m".format(
        st["len_before"], st["len_after"]))
    log("repair: topology unchanged ({:,} nodes / {:,} edges / {} components)".format(
        n0, e0, c0))


# ----------------------------------------------------------------------------
def _clear_od_graph():
    """Drop only the OD artefacts so Network.create() rebuilds them from the
    repaired base_graph, while _get_stored_network_and_graph keeps the base."""
    for name in ("origins_destinations_graph.p", "origins_destinations_graph.gpkg",
                 "origins_destinations_graph_edges.gpkg",
                 "origins_destinations_graph_nodes.gpkg",
                 "origin_destination_table.feather", "origin_destination_table.gpkg"):
        p = OUTPUT_GRAPH / name
        if p.exists():
            p.unlink()


def stage_route(analyses=None, force=False):
    import nb_helpers as nb
    import ra2ce_patches
    ra2ce_patches.apply_all()

    names = analyses or list(DESTINATIONS)
    results = {}
    for name in names:
        analysis_name = "tahoe_od_" + name
        marker = HERE / "output" / "optimal_route_origin_destination" / (analysis_name + ".gpkg")
        if marker.exists() and not force:
            log("route[{}]: {} exists, skipping (use --force)".format(name, marker.name))
            continue
        dest = DESTINATIONS[name] or (HERE / "static" / "network" / "Destinations.shp")
        log("route[{}]: clearing OD graph, reusing repaired base graph".format(name))
        _clear_od_graph()
        assert (OUTPUT_GRAPH / "base_graph.p").exists(), "base_graph.p missing"
        t = time.time()
        try:
            res = nb.run_od_analysis(
                origins_fc_path=HERE / "static" / "network" / "Origins.shp",
                destinations_fc_path=dest,
                analysis_name=analysis_name,
                origin_count_field="POPULATION",
                run_criticality=True,
                # True so the repaired base_graph survives; the OD graph was
                # just deleted above, so Network.create() rebuilds it for THIS
                # destination set rather than carrying over the previous one.
                reuse_network_output=True,
            )
            nb.archive_graph_files(
                HERE / "output" / "optimal_route_origin_destination" / (analysis_name + "_graph"),
                root_dir=HERE,
            )
            crit = res.get("criticality")
            msg = "route[{}]: done in {:.1f} min, {:,} routes".format(
                name, (time.time() - t) / 60, len(res["od_gdf"]))
            if crit:
                msg += ", {:,} edges carry traffic".format(crit["edges_with_traffic"])
            log(msg)
            results[name] = "ok"
        except Exception as e:
            log("route[{}]: FAILED after {:.1f} min: {}".format(name, (time.time() - t) / 60, e))
            log(traceback.format_exc())
            results[name] = "failed: {}".format(e)
    (LOGS / "route_results.json").write_text(json.dumps(results, indent=2))
    return results


# ----------------------------------------------------------------------------
SLR_NAME = "tahoe_slr_v2"


def stage_slr(force=False):
    """Single link redundancy on the repaired base graph.

    RA2CE runs SLR on graph_files.base_graph, the simplified graph that both
    defects corrupt, so the July run (scripts/ra2ce, tahoe_slr) inherited them:
    collapsed parallel links were missing from the graph, and straight-line
    geometry understated edge lengths and therefore detour lengths. This runs the
    same analysis (LENGTH weighing) on the split + repaired graph instead.

    reuse_network_output=True keeps static/output_graph/ (no rmtree), and with no
    origins/destinations section Network.create() builds nothing new. The base
    graph's hash is checked before and after so a silent rebuild cannot slip by.
    """
    import hashlib
    import nb_helpers as nb  # noqa: F401  (sets PROJ, imports RA2CE)
    from ra2ce.ra2ce_handler import Ra2ceHandler
    from ra2ce.network.network_config_data.network_config_data import (
        NetworkSection, NetworkConfigData,
    )
    from ra2ce.network.network_config_data.enums.source_enum import SourceEnum
    from ra2ce.analysis.analysis_config_data.analysis_config_data import (
        AnalysisSectionLosses, AnalysisConfigData,
    )
    from ra2ce.analysis.analysis_config_data.enums.analysis_losses_enum import AnalysisLossesEnum
    from ra2ce.analysis.analysis_config_data.enums.weighing_enum import WeighingEnum
    from pyproj import CRS

    out_dir = HERE / "output"
    marker = out_dir / "single_link_redundancy" / (SLR_NAME + ".gpkg")
    if marker.exists() and not force:
        log("slr: {} exists, skipping (use --force)".format(marker.name))
        return
    bg = OUTPUT_GRAPH / "base_graph.p"
    assert (OUTPUT_GRAPH / "base_graph.p.orig").exists(), "run the repair stage first"

    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]

    before = sha(bg)
    cfg = NetworkConfigData(
        root_path=HERE, static_path=HERE / "static", crs=CRS.from_epsg(4326),
        network=NetworkSection(source=SourceEnum.SHAPEFILE, primary_file=SPLIT_NETWORK,
                               save_gpkg=True, reuse_network_output=True),
    )
    analysis = AnalysisConfigData(
        root_path=HERE, output_path=out_dir, static_path=HERE / "static",
        analyses=[AnalysisSectionLosses(
            name=SLR_NAME, analysis=AnalysisLossesEnum.SINGLE_LINK_REDUNDANCY,
            weighing=WeighingEnum.LENGTH, save_csv=True, save_gpkg=True)],
    )
    t = time.time()
    log("slr: running single link redundancy on the repaired base graph ...")
    handler = Ra2ceHandler.from_config(network=cfg, analysis=analysis)
    handler.configure()
    handler.run_analysis()
    after = sha(bg)
    assert before == after, "base_graph.p changed during the SLR run ({} -> {})".format(before, after)
    log("slr: done in {:.1f} min -> {}; base_graph.p unchanged ({})".format(
        (time.time() - t) / 60, marker.relative_to(HERE), after))


# ----------------------------------------------------------------------------
def stage_verify():
    """Check the OD graph that was actually routed.

    Comparing one OD edge against the full length of the complex segments it
    names is misleading: adding origins and destinations SPLITS base edges at
    the snap points, and each piece still carries the whole rfid_c list. A half
    edge then scores 0.5 and looks straightened when it is not. 80% of the edges
    flagged that way are split pieces whose lengths sum back to 1.000. So group
    edges by their rfid_c signature first and score the group.
    """
    import geopandas as gpd
    import numpy as np
    from collections import Counter
    from repair_simple_geometry import _ids

    bn = gpd.read_feather(OUTPUT_GRAPH / "base_network.feather")
    n_in = len(gpd.read_file(SPLIT_NETWORK, columns=["segment_id"], read_geometry=False))
    log("verify: complex rows {:,} vs input {:,} -> lost {:,} (want 0)".format(
        len(bn), n_in, n_in - len(bn)))

    for name in DESTINATIONS:
        d = HERE / "output" / "optimal_route_origin_destination" / ("tahoe_od_" + name + "_graph")
        if not (d / "base_network.feather").exists():
            log("verify[{}]: no archived graph, skipped".format(name))
            continue
        g = gpd.read_file(d / "origins_destinations_graph_edges.gpkg")
        b = gpd.read_feather(d / "base_network.feather").set_crs(4326, allow_override=True)
        sl = dict(zip(b.rfid_c, b.to_crs(3310).geometry.length))
        L = g.set_crs(4326, allow_override=True).to_crs(3310).length

        sig = [tuple(sorted(_ids(rc))) for rc in g.rfid_c]
        counts = Counter(s for s in sig if s)
        grouped, rich = {}, 0
        for li, s, gm in zip(L, sig, g.geometry):
            if gm is not None and len(gm.coords) > 8:
                rich += 1
            if not s or not li:
                continue
            grouped.setdefault(s, 0.0)
            grouped[s] += li
        r, n_split = [], 0
        for s, total in grouped.items():
            denom = sum(sl.get(i, np.nan) for i in s)
            if np.isnan(denom) or denom <= 0:
                continue
            if counts[s] > 1:
                n_split += 1
            r.append(total / denom)
        r = np.array(r)
        log("verify[{}]: {:,} OD edges in {:,} rfid_c groups ({:,} split by snapping); "
            "short(<0.95) {:,} ({:.1f}%), min {:.3f}; repaired-geometry edges {:,}".format(
                name, len(g), len(r), n_split, int((r < 0.95).sum()),
                100 * (r < 0.95).mean(), r.min(), rich))


STAGES = {"prepare": stage_prepare, "basegraph": stage_basegraph,
          "repair": stage_repair, "route": stage_route, "slr": stage_slr,
          "verify": stage_verify}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", nargs="+", default=list(STAGES), choices=list(STAGES))
    ap.add_argument("--analyses", nargs="+", default=None, choices=list(DESTINATIONS))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    log("=== pipeline start: stages={} analyses={} force={}".format(
        a.stages, a.analyses or "all", a.force))
    for s in a.stages:
        if s == "route":
            STAGES[s](analyses=a.analyses, force=a.force)
        elif s == "verify":
            STAGES[s]()
        else:
            STAGES[s](force=a.force)
    log("=== pipeline done")
