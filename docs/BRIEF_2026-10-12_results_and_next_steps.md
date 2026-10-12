# Brief: where the vulnerability assessment stands (Oct. 12, 2026)

Talking points for the data team sync. Numbers are from the published results of Oct. 11
(trpa-agency.github.io/PROTECT/html/results.html). Internal draft.

## 1. What landed this week

- **Every hazard-asset pair has an exposure score on the historical horizon.** Flooding (FEMA
  zones and stream crossings), wildfire (Regional Resource Kit burn probability plus TRPA fire
  severity), landslide (USGS 2024 susceptibility), debris flow (option 1 with a severity stand-in
  for soil burn severity), avalanche (uphill slope tiers plus the TRPA zones).
- **Vulnerability is scored on every asset class:** culverts (5,096 public), bridges (40), roads
  (18,285 segments), paths (216), transit hubs (8). Sensitivity comes from the culvert profile,
  the National Bridge Inventory, and the draft's defaults for roads.
- **One Results page** replaced the hazard pages and the Phase 1 map: an Overview tab (combined
  class, vulnerability by criticality, hotspots) and a tab per hazard. Five-group navigation on
  every page; the landing page is grouped the same way.
- **Rubrics v0.4** with 24 numbered decisions; the method note for the consultant is refreshed.
  Both go to ICF today.

## 2. Headline numbers

Combined class with the debris-flow stand-in pairs held out (decision carried to ICF; one config
line puts them back).

| Asset | High | Medium | Low | Set mostly by |
|---|---|---|---|---|
| Roads (18,285) | 2,161 | 16,124 | 0 | wildfire (14,188), landslide (2,314), flooding (1,762) |
| Culverts (5,096) | 1,864 | 1,850 | 1,382 | landslide (2,970), flooding (2,126) |
| Bridges (40) | 3 | 35 | 2 | flooding (30), landslide (10) |
| Paths (216) | 115 | 101 | 0 | wildfire (121), flooding (95) |
| Transit hubs (8) | 2 | 6 | 0 | wildfire |

Hotspots: 497 road segments (95 miles) are High vulnerability on the top criticality quarter,
337 of them set by landslide. Flooding alone: 594 High culverts, 1,896 culverts cannot pass the
100-year storm, 93 records withheld for owner confirmation. With debris flow back in, the
stand-in pair would set 2,745 culverts and 2,408 road segments to High on its own.

## 3. Two things the numbers say that we have to decide

- **Debris flow dominates the combined class.** The draft's drainage-size indicator scores 3 for
  anything under a quarter square mile, which is nearly every culvert basin and hillslope cell.
  With the severity stand-in and the sensitivity floors, the pair starts near 1.4 and most
  assets clear 2.0 on it. Options: keep the arithmetic and show pairs separately (the Overview
  does), or keep the stand-in pair out of the combined class until the contracted burn severity
  arrives (one config line). The drainage-size breaks go on the ICF list either way.
- **Roads are never Low.** Wildfire likelihood is at least 1 everywhere in the Resource Kit data
  and the draft's sensitivity floors are 1, so every segment is Medium or High. The map reads as
  two colors until sensitivity data exists or the floors change.

## 4. What the network lane owns next

- **Criticality class.** The Results page cuts the criticality percentile into quarters as a
  stand-in. The lane's own 0 to 3 class on the road layer replaces it and is inherited by
  bridges, culverts, paths, and hubs. This decides the hotspot list.
- **Scenarios.** Two scenarios picked from the hotspots (Oct. 21); scenario hazard rasters and
  the closure set of failing culverts and bridges as the RA2CE link-failure input (Oct. 23);
  RA2CE runs and fact sheets (Oct. 30).
- **Hosted service.** PROTECT_VA v2 with E, S, C, V per pair only if the workshop tool needs more
  than the published GeoJSON; the Results page reads the GeoJSON today.
- **Sensitivity attributes on the street layer.** Pavement condition, surface, truck traffic, and
  guardrails are all defaults. Any source the lane has, even partial, moves roads off the floor.

## 5. What the surfaces lane owns next

- ICF package today; the Oct. 15 meeting settles the debris-flow question, the Nevada regression
  choice, the span-length direction, and legacy culvert points in the rating.
- Known-failure check in Pro (Northwood Blvd, the Washoe flash flood, Meeks Creek) and the
  culvert owner review list to the jurisdictions.
- Wildcat debris-flow run if the environment is approved; compare with the stand-in.
- Visualization pass on the Results page, then the print maps and layer files (Nov. 2 to 4).
- Workshop feedback app: dry run with partners before Nov. 4.

## 6. Dates

Oct. 12 ICF package. Oct. 15 consultant VA meeting. Oct. 21 scenarios picked. Oct. 30 all
results final. Nov. 4 tool and print maps freeze. Nov. 9 Workshop 1.
