# Walkthrough outline: data team sync, Oct. 12, 2026

Lunch agenda, screen by screen, on the live site (trpa-agency.github.io/PROTECT/html/results.html).
The pre-read sent in the morning is `BRIEF_2026-10-12_results_and_next_steps.md`; this is the
talk track for it. Numbers are the Oct. 11 publish with the debris-flow stand-in pairs held out
of the combined class. Nothing has gone to ICF yet.

## 1. What changed since you last looked (2 min, landing page)

- One Results page is the front door; the hazard pages and the Phase 1 map are archived.
- Every one of the 15 pairs has an exposure score, and every asset class has a vulnerability score.
- Rubrics v0.4 and the method note are ready for ICF. They go out after we agree on the open calls today.

## 2. Overview tab (6 min)

Show in this order: combined class map, the priority view, the vulnerability-by-criticality chart, the hotspot table.

- Combined class is the highest pair per asset, without debris flow. Roads: 3,937 High, 2,075 Medium, 12,273 Low (wildfire pairs classed Low under 2, Medium 2 to 2.5, High over 2.5; fire severity by 25 percent area share). Culverts: 1,864 High, 1,850 Medium, 1,382 Low. Bridges: 3, 35, 2.
- What sets the road class: wildfire on 14,476 segments, flooding 1,982, landslide 1,808, avalanche 19.
- Hotspots, High vulnerability on the top criticality quarter: 1,032 segments, 142 miles. Flooding sets 629 of them, landslide 310, wildfire 92, avalanche 1.
- The priority view sizes segments by criticality class. That class is still the percentile quarters, which is the first ask below.

## 3. One hazard tab, wildfire (4 min)

- Toggle the two "within 300 ft of roads" layers and click a segment to outline its buffer. This is the ground each score came from.
- Say plainly: roads carry no sensitivity, so a road's score is its exposure. Wildfire likelihood is at least 1 everywhere in the Resource Kit data, so no road can be Low.

## 4. Workshop notes (2 min)

- Open any popup, Add a workshop note, show the feedback page open at the right station with the asset filled in.
- Notes partners send come back onto the Overview map by concern. Dry run with partners before Nov. 4.

## 5. Asks of the network lane (5 min)

1. **Criticality class rule.** Replace the percentile quarters with the lane's own 0 to 3 class on the road layer. Bridges, culverts, paths, and hubs inherit it. This decides the hotspot list. I can run Jenks and fixed-break options on the current scores for comparison if that helps.
2. **Scenario picks by Oct. 21.** Two scenarios from the hotspot list. The closure set of failing culverts and bridges is ready as the link-failure input once the scenarios are named.
3. **Hosted service, yes or no.** The page reads the published GeoJSON today. PROTECT_VA v2 only if the workshop tool or RA2CE needs more.

## 6. What I carry (1 min)

- ICF package and the consultant meeting: debris-flow floor and the exclusion, landslide watershed versus point, Nevada regression, span-length direction, legacy points. Agree today which of these TRPA recommends before they go out.
- Known-failure check in Pro, the culvert owner review list, the wildcat run if the environment is approved, print maps and layer files Nov. 2 to 4.

## Dates

ICF package this week, consultant meeting to schedule. Oct. 21 scenarios picked. Oct. 30 results final. Nov. 4 tool and print maps freeze. Nov. 9 Workshop 1.
