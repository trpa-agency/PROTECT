"""Smoke-test the graph-reuse linchpin before committing to hours of routing.

stage_route passes reuse_network_output=True so the repaired base_graph
survives, having first deleted the OD artefacts so Network.create() rebuilds
them for the current destination set. Both halves of that have to hold:

  * reuse=True must NOT rmtree static/output_graph  (base_graph.p unchanged)
  * the OD graph must be rebuilt, and carry THIS destination set

This exercises the same RA2CE code path run_od_analysis triggers, but stops
before the Dijkstra routing, so it takes minutes rather than hours.
"""
import hashlib
import pickle
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import nb_helpers as nb  # noqa: E402  (sets PROJ, imports RA2CE)
import geopandas as gpd  # noqa: E402
from pyproj import CRS  # noqa: E402
from ra2ce.network.network_config_data.network_config_data import (  # noqa: E402
    NetworkSection, NetworkConfigData, OriginsDestinationsSection,
)
from ra2ce.network.network_config_data.enums.source_enum import SourceEnum  # noqa: E402
from ra2ce.network.network_config_wrapper import NetworkConfigWrapper  # noqa: E402

from pipeline import OUTPUT_GRAPH, SPLIT_NETWORK, _clear_od_graph  # noqa: E402


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def main():
    bg = OUTPUT_GRAPH / "base_graph.p"
    before = sha(bg)
    g_before = pickle.load(open(bg, "rb"))
    print("base_graph.p sha={} edges={:,}".format(before, g_before.number_of_edges()))

    # count how many edges carry repaired (multi-vertex) geometry, as a
    # fingerprint that the repair is still in the graph afterwards
    def rich(g):
        return sum(1 for e in g.edges(data=True, keys=True)
                   if e[-1].get("geometry") is not None and len(e[-1]["geometry"].coords) > 8)
    rich_before = rich(g_before)
    print("edges with >8 vertices (repair fingerprint): {:,}".format(rich_before))

    dests = HERE / "static" / "network" / "Destinations.shp"
    n_dest = len(gpd.read_file(dests, read_geometry=False))
    print("destination set: {} ({} features)".format(dests.name, n_dest))

    _clear_od_graph()
    assert not (OUTPUT_GRAPH / "origins_destinations_graph.p").exists()
    print("cleared OD artefacts")

    cfg = NetworkConfigData(
        root_path=HERE, static_path=HERE / "static", crs=CRS.from_epsg(4326),
        network=NetworkSection(source=SourceEnum.SHAPEFILE, primary_file=SPLIT_NETWORK,
                               save_gpkg=True, reuse_network_output=True),
        origins_destinations=OriginsDestinationsSection(
            origins=HERE / "static" / "network" / "Origins.shp",
            destinations=dests, origin_count="POPULATION",
        ),
    )
    t = time.time()
    wrapper = NetworkConfigWrapper.from_data(HERE / "network.ini", cfg)
    wrapper.configure()
    print("configure() took {:.1f}s".format(time.time() - t))

    after = sha(bg)
    g_after = pickle.load(open(bg, "rb"))
    print("\nRESULTS")
    print("  base_graph.p unchanged : {}  ({} -> {})".format(before == after, before, after))
    print("  repair fingerprint kept: {}  ({:,} -> {:,} edges >8 vertices)".format(
        rich(g_after) == rich_before, rich_before, rich(g_after)))
    odp = OUTPUT_GRAPH / "origins_destinations_graph.p"
    print("  OD graph rebuilt       : {}".format(odp.exists()))
    odt = OUTPUT_GRAPH / "origin_destination_table.feather"
    if odt.exists():
        import pandas as pd
        t_ = pd.read_feather(odt)
        nd = t_["d_id"].nunique() if "d_id" in t_.columns else "?"
        print("  OD table rows          : {:,}".format(len(t_)))
        print("  distinct destinations  : {} (expected {})".format(nd, n_dest))
    ok = (before == after) and odp.exists() and rich(g_after) == rich_before
    print("\n{}".format("PASS - safe to run the full route stage" if ok else "FAIL - do not run routing"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
