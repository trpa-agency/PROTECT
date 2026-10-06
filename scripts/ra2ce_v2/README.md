# ra2ce_v2 - corrected RA2CE OD criticality pipeline

Rebuild of the `scripts/ra2ce/` OD criticality work with two RA2CE 1.2.2 network
defects fixed before any routing happens. The analysis definitions, routing modes,
equity weighting and exports are unchanged - they are lifted verbatim from
`ra2ce_tahoe.ipynb` so the only differences in the output are the ones the fixes
cause.

## Why

### 1. Parallel links silently collapse

`VectorNetworkWrapper._create_graph_from_gdf` builds a plain `nx.DiGraph`, and
`_get_undirected_graph_from_vector` then calls `digraph.to_undirected()`, giving a
plain `nx.Graph`. Neither is a multigraph, so two source links sharing a pair of
endpoint coordinates merge into one edge and `add_edge` overwrites the loser's
geometry, length and attributes.

The arithmetic closes exactly:

```
source features                                      95,285
exact-duplicate geometries dropped by clean_vector        1
features silently overwritten by to_undirected()      2,529
                                                     ------
                                                     92,756   = base_network.feather rows
```

5,047 features sit in 2,518 colliding pairs (plus 9 triples and 1 quad); 774 are
in-basin; mostly `service` and `residential` but also 19 `primary`, 12 `trunk` and
1 `motorway`. The median length ratio within a colliding pair is 2.9x, the worst
275x.

This is why 388 in-basin streets read NULL rather than 0 in `PROTECT_VA` - all 388
were verified to be collision members. Worked example: 4th Street, South Lake
Tahoe (`segment_id 5945adb5-300e-4542-b160-6202145e7820`) shares both endpoints
with an unnamed 156.84 m service road that loops the block. The service road won,
took 4th Street's `traffic_medical_facilities = 771.727`, and 4th Street's own
55.4 m piece was left with no row at all.

**Fix:** `preprocess.split_colliding_links` splits all but the shortest member of
each colliding group at its midpoint, so every link gets a distinct node pair.
One pass clears all 2,518 groups; total network length is preserved exactly.

### 2. Simplified geometry is never concatenated

Every multi-segment edge in RA2CE's simplified (routing) graph is drawn as a
polyline through the chain's **node positions** - 100% of them have
`n_vert == n_complex + 1`, at every stage from `NetworkGraphSimplificator` onward.
It is not an intermittent failure.

It hides because ~37% of Overture complex edges are already straight 2-point
links, so for a chain of straight segments the node polyline *is* the correct
answer. It only bites when a constituent carries interior vertices: the curve is
discarded and the routing weight is understated. 6,253 of 80,785 simple edges
(7.7%) were shorter than the sum of their parts; none were longer; the worst was
0.078 of true length.

**Fix:** `repair_simple_geometry` rebuilds each edge from its `rfid_c`
constituents with `shapely.ops.linemerge`, which succeeds on 100% of a 1,500-edge
sample and is length-exact. The longest highway edge goes from ~30 vertices to
1,152.

**The endpoint guard is mandatory.** Without it the repair breaks 1,378 edges
whose merged line no longer terminates on the edge's own two nodes (RA2CE ships
zero such edges). An `rfid_c` list can name a segment that is not on that edge's
path - 3,342 complex segments are referenced by two different simple edges. Those
1,378 keep RA2CE's node polyline and remain the only short edges left. Treat
RA2CE's `rfid_c` mapping as unreliable for them.

Ordering matters: the repair rewrites `geometry`, `length` and `time` on the
routing graph, so it lands **before** Dijkstra, not after.

## Layout

```
ra2ce_v2/
|- pipeline.py               orchestrator (prepare / basegraph / repair / route / verify)
|- preprocess.py             split_colliding_links
|- repair_simple_geometry.py linemerge repair with the endpoint guard
|- ra2ce_patches.py          find_route_ods unary_union patch
|- build_helpers.py          regenerates nb_helpers.py from the notebook
|- nb_helpers.py             GENERATED - notebook cells 3, 4, 55, verbatim
|- smoke_test_reuse.py       verifies graph reuse before a long run
|- static/network/           inputs (Origins, Destinations, blockgroup, split network)
|- static/output_graph/      base_graph.p (repaired), base_network.feather
|- output/                   RA2CE outputs + criticality exports
|- logs/                     pipeline.log, route.log
```

## Running

```powershell
$py = "C:\Users\amcclary\AppData\Local\ESRI\conda\envs\arcgispro-py3-plotly\python.exe"
& $py pipeline.py                                      # everything
& $py pipeline.py --stages prepare basegraph repair     # fast stages only (~4 min)
& $py smoke_test_reuse.py                               # verify reuse, ~1 min
& $py pipeline.py --stages route --analyses medicalfacilities
```

Stages are idempotent and skip completed work; pass `--force` to redo one.

**Close ArcGIS Pro before running the route stage.** RA2CE deletes then rewrites
its GeoPackages, so an open layer causes `PermissionError: WinError 32` after the
expensive routing has already finished.

## How the repaired graph reaches the router

RA2CE decides in `Network.create()`:

```python
if not (graph_files.base_graph.file or graph_files.base_network.file):
    self._get_new_network_and_graph(to_save)   # rebuild
else:
    self._get_stored_network_and_graph()       # reuse

if origins and destinations and not graph_files.origins_destinations_graph.file:
    ...build the OD graph from base_graph
```

So `stage_route` passes `reuse_network_output=True` (which keeps
`static/output_graph/` rather than `rmtree`-ing it) **and** deletes only the OD
artefacts first. The repaired `base_graph.p` survives; the OD graph is rebuilt for
each destination set rather than carried over from the previous one. That carry-over
is a real hazard - it once produced a "baseline" of 19,251 routes to 9 evacuation
shelters instead of 7,371 to the 7 basin exit points - so `smoke_test_reuse.py`
checks both halves before a long run.

## The unary_union patch is not optional here

`OptimalRouteOriginDestination.find_route_ods` builds each route's geometry with an
accumulating pairwise union, which is O(n^2) in edges per route, for every OD pair.
`ra2ce_patches` replaces it with a single `unary_union` - identical geometry
(length delta 4e-16, Hausdorff 7e-18, `equals_exact(1e-9)` True) and ~300x faster
on a 400-edge route.

This matters more after the repair, not less: repaired edges carry real road
geometry, so union cost per route rises with vertex count. Unpatched, the repair
would make routing dramatically slower rather than faster.

## Known remaining issues

- **12 complex edges have no simple ID.** RA2CE logs `Could not find the simple ID
  belonging to complex ID ...` for 12 of 97,814 edges during the build. They are
  excluded from criticality scoring.
- **1,378 simple edges keep the straight-line geometry**, rejected by the endpoint
  guard because their `rfid_c` list names a segment off their own path.
- **Do not enable a cleanup option to work around any of this.** That switches the
  factory to `ShpNetworkWrapper`, whose `cut_lines` appends the same mutated
  `properties_dict` object once per cut piece and then calls
  `pd.concat([lines_gdf] + to_add)` on a list of dicts, raising
  `TypeError: cannot concatenate object of type '<class 'dict'>'` under pandas
  2.3.3. It only survives today because no node falls mid-line in the Overture
  input, so `cut_lines` is a no-op.

## Results of the completed run (2026-09-16)

All four analyses completed in 4 h 33 m: law enforcement 48.9 min (15,365 routes),
medical 42.7 min (10,975), shelters 94.4 min (19,755), evacuation 86.2 min (15,365).

| | ra2ce | ra2ce_v2 |
|---|---|---|
| input features | 95,285 | 97,814 (2,529 split) |
| complex rows (`base_network`) | 92,756 (2,529 lost) | **97,814 (0 lost)** |
| network length | 8,627,609 m (-2.54%) | **8,852,786 m (exact)** |
| short edges in the routed graph | 8.6% | **0.9%** (684, min ratio 0.090) |
| in-basin collision features with their own row | 386 of 774 | **773 of 774 (99.9%)** |

Worked example: 4th Street's 55.4 m middle link went from 18% represented with no
row of its own, to 100% represented with `traffic = 417.0, routed = 1`. Its traffic
is no longer painted on the parallel service road.

### Reading the verify output

`stage_verify` groups OD edges by their `rfid_c` signature before scoring them.
Adding origins and destinations **splits** base edges at the snap points, and each
piece still carries the whole `rfid_c` list, so a half edge scores 0.5 against the
full complex length and looks straightened when it is not. Ungrouped, that inflated
the count to 3,393 (4.2%); 80% of those were split pieces whose lengths sum back to
1.000 (99% within 2%). The real figure is 684.

12,248 edges carrying repaired multi-vertex geometry survive into the graph that was
actually routed, out of 12,630 in the repaired base graph.

`rfid` and `rfid_c` numbering differs completely from `scripts/ra2ce/`, so the two
sets of outputs cannot be joined to each other - `ra2ce_v2` outputs stand alone, and
PROTECT_VA needs republishing from these rather than patching.

## Publishing to PROTECT_VA

```powershell
& $py export_combined.py      # 4 criticality layers -> one network layer
& $py export_protect_va.py    # -> update table keyed on OBJECTID
```

`export_combined.py` merges the four criticality layers column-wise on `rfid_c`
(they are the same 97,814-row network, so no spatial join is needed) and writes
`output/tahoe_od_criticality_combined_v2.{gpkg,shp}` plus a field dictionary,
mirroring the old `tahoe_od_criticality_combined.*` schema.

`export_protect_va.py` does **not** rebuild the published layer. `Streets_Network_Tahoe`
carries 60 fields and only 20 come from RA2CE; the other 40 are hazard, equity, SLR,
AADT and Jenks work unrelated to this rebuild. So it emits an update table keyed on
`OBJECTID` carrying just the 20 OD fields, to be joined and field-calculated into the
existing layer. Geometry, OBJECTIDs and the other 40 fields are untouched.

It pulls the published geometry rather than assuming the local shapefile is in the
same order - `segment_id` is not unique, so it cannot be the key.

### The join is two-sided on purpose

A one-sided "how much of this street does the criticality row cover?" test with a 50%
threshold is what produced the 388 NULLs. Preprocessing splits a colliding link in
half, so each half covers ~50% of the street and both get rejected.

Here a row is accepted when most of **that row** runs along the street's **interior**,
then contributes in proportion to how much of the street it covers. The interior
matters: a short segment meeting the street end-on is collinear with it, so several
metres of it fall inside a buffer of the whole street - an 8 m neighbour scores 5/8
and passes. Trimming 5 m off each end before the test cut spurious multi-row matches
from 4,562 streets to 1,759, whose second contributing row now has a median weight of
0.533, i.e. genuine half-coverage.

Values are length-weighted means; `routed` / `par_alt` are maxima.

### Results

```
NULL traffic_medical_facilities:  published 388  ->  update 0   (388 recovered)
coverage >=95%:                   18,285 of 18,285 (100.0%)
0 null cells across 20 fields x 18,285 rows

traffic > 0, published -> update
  traffic_evacuation           7,084 -> 7,364   (+280)
  traffic_law_enforcement      7,094 -> 7,365   (+271)
  traffic_medical_facilities   8,198 -> 8,503   (+305)
  traffic_emergency_shelters   8,605 -> 8,884   (+279)
```

4th Street's OBJECTID 15271 (the 55.4 m piece) goes from NULL to
`traffic_medical_facilities = 416.96, routed = 1`, at 100% coverage from a single row.

Three QA columns ride along: `od_coverage_pct`, `od_source_rows` and
`od_row_spread_pct`. The last is how much the contributing rows disagreed, as a share
of the largest value - 0 for pieces of one road in series (1,200 of the 1,759
multi-row streets), high where a street spans a junction and traffic genuinely
changes (540 streets above 20%). **Check `od_row_spread_pct` before quoting a single
figure for a multi-row street**; the length-weighted mean is a summary there, not a
single true value.

### Applying it

1. `output/protect_va_update/protect_va_od_update.csv` - join to
   `Streets_Network_Tahoe` on `OBJECTID`, then field-calculate the 20 OD fields.
2. `protect_va_od_update.gpkg` carries the same values with geometry, for a visual
   check before committing.
3. `protect_va_od_update_qa.txt` is the report above, to keep with the change.

Re-download the published layer with `--refresh`; it is otherwise cached in
`output/protect_va_update/protect_va_published.gpkg`.
