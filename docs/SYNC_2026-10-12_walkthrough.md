# Walkthrough outline: data team sync, Oct. 12, 2026

Twenty minutes, screen by screen, on the live site (trpa-agency.github.io/PROTECT/html/results.html).
Numbers are the Oct. 11 publish with the debris-flow stand-in pairs held out of the combined
class. The longer brief with the same dates is `BRIEF_2026-10-12_results_and_next_steps.md`.

## 1. What changed since you last looked (2 min, landing page)

- One Results page is the front door; the hazard pages and the Phase 1 map are archived.
- Every one of the 15 pairs has an exposure score, and every asset class has a vulnerability score.
- Rubrics v0.4 and the method note went to ICF today. The Oct. 15 meeting settles the open calls.

## 2. Overview tab (6 min)

Show in this order: combined class map, the priority view, the vulnerability-by-criticality chart, the hotspot table.

- Combined class is the highest pair per asset, without debris flow. Roads: 2,161 High and 16,124 Medium, no Low. Culverts: 1,864 High, 1,850 Medium, 1,382 Low. Bridges: 3, 35, 2.
- What sets the road class: wildfire on 14,188 segments, landslide 2,314, flooding 1,762, avalanche 21.
- Hotspots, High vulnerability on the top criticality quarter: 497 segments, 95 miles. Landslide sets 337 of them.
- The priority view sizes segments by criticality class. That class is still the percentile quarters, which is the first ask below.

## 3. One hazard tab, wildfire (4 min)

- Toggle the two "within 300 ft of roads" layers and click a segment to outline its buffer. This is the ground each score came from.
- Say plainly: wildfire likelihood is at least 1 everywhere in the Resource Kit data and the draft's sensitivity floors are 1, so no road can be Low. The map is two colors until sensitivity data exists.

## 4. Workshop notes (2 min)

- Open any popup, Add a workshop note, show the feedback page open at the right station with the asset filled in.
- Notes partners send come back onto the Overview map by concern. Dry run with partners before Nov. 4.

## 5. Asks of the network lane (5 min)

1. **Criticality class rule.** Replace the percentile quarters with the lane's own 0 to 3 class on the road layer. Bridges, culverts, paths, and hubs inherit it. This decides the hotspot list. I can run Jenks and fixed-break options on the current scores for comparison if that helps.
2. **Scenario picks by Oct. 21.** Two scenarios from the hotspot list. The closure set of failing culverts and bridges is ready as the link-failure input once the scenarios are named.
3. **Any sensitivity attribute on the streets.** Pavement, surface, truck route, guardrail, even partial. Anything moves roads off the floor.
4. **Hosted service, yes or no.** The page reads the published GeoJSON today. PROTECT_VA v2 only if the workshop tool or RA2CE needs more.

## 6. What I carry (1 min)

- Oct. 15 decisions with ICF: debris-flow floor and the exclusion, landslide watershed versus point, Nevada regression, span-length direction, legacy points.
- Known-failure check in Pro, the culvert owner review list, the wildcat run if the environment is approved, print maps and layer files Nov. 2 to 4.

## Dates

Oct. 15 ICF meeting. Oct. 21 scenarios picked. Oct. 30 results final. Nov. 4 tool and print maps freeze. Nov. 9 Workshop 1.
