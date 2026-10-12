# Pre-read: where the vulnerability assessment stands (Oct. 12, 2026)

Five-minute read before the lunch sync. Numbers are from the published results of Oct. 11.
If you open one thing first, make it the Overview tab of the Results page
(trpa-agency.github.io/PROTECT/html/results.html). Nothing has gone to ICF yet; the package
goes out after we align on the asks in section 4. Internal draft.

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
- **Rubrics v0.4** with 24 numbered decisions and a refreshed method note are ready for ICF.
  They go out after lunch once we agree on the open calls.

## 2. Headline numbers

Combined class with the debris-flow stand-in pairs held out (decision carried to ICF; one config
line puts them back).

| Asset | High | Medium | Low | Set mostly by |
|---|---|---|---|---|
| Roads (18,285) | 3,937 | 2,075 | 12,273 | wildfire (14,476), flooding (1,982), landslide (1,808) |
| Culverts (5,096) | 1,864 | 1,850 | 1,382 | landslide (2,970), flooding (2,126) |
| Bridges (40) | 3 | 35 | 2 | flooding (30), landslide (10) |
| Paths (216) | 108 | 2 | 106 | wildfire (111), flooding (105) |
| Transit hubs (8) | 0 | 1 | 7 | wildfire |

Hotspots: 1,032 road segments (142 miles) are High vulnerability on the top criticality quarter,
629 of them set by flooding, 310 by landslide, 92 by wildfire, and 1 by avalanche. Wildfire pairs are classed on their own breaks (Low under 2, Medium 2 to 2.5, High over 2.5), and fire severity is the highest class covering at least 25 percent of the 300 ft buffer. Flooding alone: 594 High culverts, 1,896 culverts cannot pass the
100-year storm, 93 records withheld for owner confirmation. With debris flow back in, the
stand-in pair would set 2,745 culverts and 4,149 road segments to High on its own.

## 3. Two things the numbers say that we have to decide

- **Debris flow dominates the combined class.** The draft's drainage-size indicator scores 3 for
  anything under a quarter square mile, which is nearly every culvert basin and hillslope cell.
  With the severity stand-in and the sensitivity floors, the pair starts near 1.4 and most
  assets clear 2.0 on it. Options: keep the arithmetic and show pairs separately (the Overview
  does), or keep the stand-in pair out of the combined class until the contracted burn severity
  arrives (one config line). The drainage-size breaks go on the ICF list either way.
- **Roads are never Low.** Roads carry no sensitivity (decision 25), so a road pair's score is its
  exposure. Wildfire likelihood is at least 1 everywhere in the Resource Kit data, so every segment's
  wildfire score, and with it its highest pair, is at least 1: every segment is Medium or High.

## 4. What the network lane owns next

- **Criticality class.** The Results page cuts the criticality percentile into quarters as a
  stand-in. The lane's own 0 to 3 class on the road layer replaces it and is inherited by
  bridges, culverts, paths, and hubs. This decides the hotspot list.
- **Scenarios.** Two scenarios picked from the hotspots (Oct. 21); scenario hazard rasters and
  the closure set of failing culverts and bridges as the RA2CE link-failure input (Oct. 23);
  RA2CE runs and fact sheets (Oct. 30).
- **Hosted service.** PROTECT_VA v2 with E, S, C, V per pair only if the workshop tool needs more
  than the published GeoJSON; the Results page reads the GeoJSON today.

## 5. What the surfaces lane owns next

- ICF package after lunch, then a consultant meeting to settle the debris-flow question, the
  landslide sampling choice, the Nevada regression, the span-length direction, and legacy
  culvert points in the rating.
- Known-failure check in Pro (Northwood Blvd, the Washoe flash flood, Meeks Creek) and the
  culvert owner review list to the jurisdictions.
- Wildcat debris-flow run if the environment is approved; compare with the stand-in.
- Visualization pass on the Results page, then the print maps and layer files (Nov. 2 to 4).
- Workshop feedback app: dry run with partners before Nov. 4.

## 6. Dates

ICF package this week, consultant meeting to schedule. Oct. 21 scenarios picked. Oct. 30 all
results final. Nov. 4 tool and print maps freeze. Nov. 9 Workshop 1.
