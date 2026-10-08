"""Runtime patches applied to RA2CE 1.2.2 before any analysis runs.

1. find_route_ods quadratic union  (performance, mandatory here)
   OptimalRouteOriginDestination.find_route_ods builds each route's geometry
   with an accumulating pairwise union:
       combined_pref_edges = MultiLineString([])
       for geometry in pref_edges:
           combined_pref_edges = combined_pref_edges.union(geometry)
   Every call re-processes the whole accumulated geometry, so cost is O(n^2)
   in edges per route, for every OD pair. unary_union produces identical
   geometry in one pass.

   This matters far more after repair_simple_geometry: repaired edges carry
   real road geometry, so the longest highway edge goes from ~30 vertices to
   1,152, and union cost scales with vertex count. Unpatched, the repair
   would make routing dramatically slower rather than faster.

2. closest_node coordinate rounding  (correctness)
   Applied by nb_helpers (notebook cell 3), which rounds node coordinates to
   7 decimals and breaks the inverse_vertices_dict / inverse_nodes_dict
   lookups during OD snapping.
"""
import logging


def patch_find_route_ods():
    """Replace the accumulating union with a single unary_union."""
    import numpy as np
    import pandas as pd
    import geopandas as gpd
    import networkx as nx
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    from ra2ce.analysis.losses.optimal_route_origin_destination import (
        OptimalRouteOriginDestination,
    )

    original = OptimalRouteOriginDestination.find_route_ods
    src = original.__doc__ or ""

    def find_route_ods(graph, od_nodes, weighing):
        o_node_list, d_node_list, origin_list, destination_list = [], [], [], []
        opt_path_list, weighing_list, match_ids_list, geometries_list = [], [], [], []

        for o, d in od_nodes:
            if nx.has_path(graph, o[0], d[0]):
                pref_route = nx.dijkstra_path_length(
                    graph, o[0], d[0], weight=weighing.config_value
                )
                pref_nodes = nx.dijkstra_path(
                    graph, o[0], d[0], weight=weighing.config_value
                )
                edgesinpath = list(zip(pref_nodes[0:], pref_nodes[1:]))

                pref_edges, match_list = [], []
                for u, v in edgesinpath:
                    _uv_graph = graph[u][v]
                    edge_key = sorted(
                        _uv_graph,
                        key=lambda x, _fgraph=_uv_graph: _fgraph[x][weighing.config_value],
                    )[0]
                    _uv_graph_edge = _uv_graph[edge_key]
                    if "geometry" in _uv_graph_edge:
                        pref_edges.append(_uv_graph_edge["geometry"])
                    else:
                        pref_edges.append(
                            LineString(
                                [graph.nodes[u]["geometry"], graph.nodes[v]["geometry"]]
                            )
                        )
                    if "rfid" in _uv_graph_edge:
                        match_list.append(_uv_graph_edge["rfid"])

                # THE PATCH: one pass instead of an accumulating pairwise union.
                combined_pref_edges = unary_union(pref_edges)

                o_node_list.append(o[0])
                d_node_list.append(d[0])
                origin_list.append(o[1])
                destination_list.append(d[1])
                opt_path_list.append(pref_nodes)
                weighing_list.append(pref_route)
                match_ids_list.append(match_list)
                geometries_list.append(combined_pref_edges)

        pref_routes = gpd.GeoDataFrame(
            {
                "o_node": o_node_list,
                "d_node": d_node_list,
                "origin": origin_list,
                "destination": destination_list,
                "opt_path": opt_path_list,
                weighing.config_value: weighing_list,
                "match_ids": match_ids_list,
                "geometry": geometries_list,
            },
            geometry="geometry",
            crs=graph.graph["crs"],
        )
        return pref_routes

    find_route_ods.__doc__ = src
    OptimalRouteOriginDestination.find_route_ods = staticmethod(find_route_ods)
    logging.info("patched OptimalRouteOriginDestination.find_route_ods -> unary_union")
    return True


def apply_all():
    patch_find_route_ods()
