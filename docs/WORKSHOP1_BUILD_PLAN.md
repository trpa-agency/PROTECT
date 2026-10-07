# Workshop 1 build plan: analysis and website

Plan of record for the Task 3 pieces the data team owes the November 2026 workshop
("Vulnerability Assessment and Baseline Assessment", in person, about 4.5 hours).
Source: the draft detailed agenda and ICF's workshop schedule (both Oct. 2026). Written Oct. 6,
2026, revised the same day for the **Nov. 9 workshop date**.

ICF's checkpoints, which this plan is built around:

| Due | Deliverable |
|---|---|
| Oct. 7 | TRPA finalizes criticality score per asset |
| Oct. 9 | ICF finishes criticality review |
| Oct. 12 week | ICF starts reviewing systemwide VA results, rolling per hazard |
| Oct. 15 | VA meeting: ICF feedback on draft results |
| Oct. 16 | TRPA finalizes methods and results for the systemwide VA |
| Oct. 26 week | TRPA finalizes all results |
| Nov. 2 week | TRPA finalizes the mapping tool, slides, and printed maps |
| Nov. 9 | Workshop |

Baseline assessment, performance measures, and the communication strategy are ICF content and
are out of scope here.

## 0. Ownership

Two lanes inside the data team. Sections 1 to 6 are the whole picture; section 7 is the
detailed plan for the first lane.

| Lane | Owns | VA pairs |
|---|---|---|
| Culverts, bridges, debris flow, avalanche (this plan's author) | Bridge and culvert inventories and sensitivity; exposure of bridges and culverts to every hazard; the debris flow surface and its three pairs; the avalanche method and pair; print maps for debris flow and avalanche; bridge and culvert layers, popups, and hotspots in the tool; the storm events page | FL-B, FL-C, LS-B, LS-C, DF-B, DF-C, DF-R, AV-R (8 of 15) |
| Street network, criticality, OD, wildfire, flood, landslide surfaces | Road, transit center, and active transport inventories; the four criticality components and the combined score; the wildfire, flood, and landslide exposure surfaces; road pairs for those hazards; RA2CE scenarios; the criticality and OD apps | FL-R, FL-AT, FL-TC, LS-R, WF-R, WF-AT, WF-TC (7 of 15) |

Shared: the scoring rubric document, the `PROTECT_VA` v2 schema, the rating script, the
tool's framework, the hub, and the VA slides. The debris flow pairs depend on the wildfire
lane's burn severity proxy; the bridge and culvert flood and landslide pairs depend on that
lane's exposure surfaces. Those two handoffs are the only cross-lane blockers.

---

## 1. What the agenda asks of the data team

| Agenda block | What has to exist | Owner on the day |
|---|---|---|
| VA presentation (15 min) | Slides on criticality (assets, indicators, weights), system-wide screening (assets, hazards, horizons, exposure datasets, sensitivity indicators), and a one-slide scenario overview. Figures pulled from the hub and tool. | TRPA or ICF (undecided) |
| VA results activity (50 min) | One large-format map per hazard with assets scored, posted at stations. On screen: the same hazard with assets hidden first, then revealed. A hotspot list per hazard for the facilitator. | ICF facilitates; we supply maps and the tool |
| Report out (10 min) | A per-hazard list of priority assets and corridors the facilitators can read from. | ICF |
| Black sky exercise (40 min) | Two scenarios at highly critical locations, each with a map and numbers: closed links, detours, service access lost, population isolated, cascading impacts. | ICF facilitates; we build scenarios |
| Tool question in the activity | "What data or features would be most helpful in the interactive mapping tool?" The tool must be demoable and stable so the question is concrete. | us |
| Closing | Next steps text for the VA and tool. | TRPA |

Gating dependency: every item above needs the **Vulnerability Rating** computed for the 15
Include-in-VA pairs. Where things stand (per the Steering Committee status summary and the
repo, Oct. 6):

- Done: all five asset inventories (streets, culverts, bridges, transit centers, active
  transportation); the four criticality components (detour length, traffic volume, equity,
  origin-destination service access); the tool prototype.
- In hand as baseline exposure data: older burn probability (wildfire), FEMA floodplain
  (flood), USGS susceptibility (landslide).
- Not done: combining the four criticality components into one final 0-3 score per asset
  (ICF's Oct. 7 item); exposure scored on a 0-3 rubric for any pair (only road flags exist);
  sensitivity scoring for any class; the rating itself; debris flow analysis; an avalanche
  method; any RA2CE run with a hazard raster.

The Steering Committee's own asks (equity feedback, additional OD destinations and how to
balance them, flood locations, what is missing from the tool) carry straight into the
workshop activity questions, so the tool should surface them as prompts.

---

## 2. Analysis work (Python, arcgispro-py3)

Ordered by dependency. Each item names its output so the website work can build against a
schema before the numbers are final.

### 2.1 Lock the scoring spec (send to ICF by Oct. 9)

- Write `docs/SCORING_RUBRICS.md`: one exposure rubric and one sensitivity rubric per pair,
  0-3, with the dataset, field, and class breaks. Start from Hazard_Asset_Pairs.md section 2 and
  the 6/25 indicator slide. This is the document ICF reviews; nothing else is scored until it is
  agreed.
- Decide and record the three open rules in the same file:
  - Criticality to 0-3: Jenks on the current equal-weight index, or fixed percentile breaks.
  - Asset-level aggregation across pairs: recommend **max pair rating** (a culvert carries
    FL-C, DF-C, LS-C; summing double-counts one physical failure).
  - Horizon: baseline only for the workshop. Contracted flood or fire data that is not in hand
    by Oct. 12 goes to the December release; the public fallback is the workshop dataset.
- Publish fallback decisions per hazard, so purchased-data delivery dates cannot block the
  workshop:

| Hazard | Primary (contracted) | Workshop fallback (public, live today) |
|---|---|---|
| Flooding | Contracted depths, 8 return periods | FEMA zone class (A/AE/X500/X) from Streams_and_Flood_Zone, plus culvert capacity screen from the storm events page |
| Wildfire | Updated burn probability (expected about Nov.), fire pathways, burn severity | Older burn probability already in hand; TRPA Fire/3 high-severity probability as the second indicator |
| Debris flow | Predicted soil burn severity plus wildcat | WRF 1-hr intensity grid x slope x fire severity proxy; wildcat if the environment gets approved in time |
| Landslide | n/a | USGS susceptibility classes (already extracted as mean/max) |
| Avalanche | n/a | TRPA Avalanche_Zones intersect, scored by zone class; method still to be decided (see section 5) |

### 2.2 Consolidate the asset base (Oct. 7 to 9)

- One geodatabase, one road layer. The three notebooks currently write to two geodatabases
  (`PROTECT_analysis.gdb`, `PROTECT_analysis_recovered.gdb`) and two road layers
  (`Streets_Network_Drive`, `Streets_Network_Tahoe`). Pick `Streets_Network_Tahoe` in
  `PROTECT_analysis.gdb` and migrate the hazard flags onto it.
- The status summary says all five inventories are complete, but the published `PROTECT_VA`
  service has one layer (`Streets_Network_Tahoe`) and the repo notebooks only touch roads. So
  the job is to locate the four point and line inventories, bring them into the one
  geodatabase, confirm each has a stable ID, the parent road segment ID (for inherited
  criticality), and the sensitivity fields the rubric needs, and publish them:
  - Bridges: condition, scour criticality, deck rating, year built (National Bridge
    Inventory fields).
  - Culverts: `data/processed/culverts.gpkg` joined to `culvert_condition.parquet`
    (7,858 assets). Re-run the legacy-match fix noted Aug. 1 first; expect the 1,626 provisional
    records to drop. More condition data from jurisdictions is still wanted but not gating.
  - Active transport: paved/unpaved and slope (lidar DTM).
  - Transit centers: site elevation.
- Fix the known defect: `Asset_Criticality.ipynb` cell 9 says 100 m buffer but uses 10.

### 2.3 Score exposure and sensitivity (Oct. 8 to 16, one hazard at a time to ICF)

Order of delivery, easiest surface first so ICF review starts Oct. 12 with something real:
flooding (FEMA, Oct. 9), wildfire (Oct. 12), landslide (Oct. 13), avalanche (Oct. 14),
debris flow (Oct. 16, proxy method). Roads ship with each hazard; the point assets follow
within a day.

- New script `scripts/score_exposure.py`: for each pair, overlay the hazard surface on the asset
  layer and write `E_<pair>` (0-3) using the rubric. Roads use length-weighted max per segment;
  points use the value at the point with a 25 m buffer.
- New script `scripts/score_sensitivity.py`: write `S_<pair>` (0-3) per asset from condition,
  elevation, and material fields. Pavement condition is unavailable, so roads get a default
  S of 1 with a `S_source` flag so the gap is visible on the map rather than hidden.
- Equity (Justice40) multiplier: keep the existing `Equity_Score_Normalized`, applied once at
  the criticality step, not again in sensitivity.

### 2.4 Criticality to 0-3 and extend to all asset classes (due Oct. 7, do this first)

This is the first ICF checkpoint and it is this week. Finalize weights, write the 0-3 class,
and send the road layer with a one-page method note on Oct. 7; the point assets inherit and
can follow by Oct. 9 while ICF reviews.

- The four components exist (detour length, traffic volume, equity, origin-destination
  service access). What is missing is one combined score with agreed weights, written to the
  asset layers as a 0-3 class. Promote `Asset_Scoring.ipynb` into `scripts/score_criticality.py`
  with the weights in `config.yaml`. The criticality app, the OD services app, and the script
  must use the same weights; the script is the source of record and the apps read the result.
- The OD component is the one the Steering Committee asked about (which destinations, how to
  balance them). Ship the current four destination types at equal weight and carry the
  question into the workshop rather than reworking it now.
- Bridges and culverts inherit the parent segment's C. Active transport and transit centers
  score on priority-zone proximity and strategic-asset proximity only (no AADT).

### 2.5 Vulnerability Rating and hotspots (first cut Oct. 16, final Oct. 30)

- `scripts/compute_vulnerability.py`: `V_<pair> = (E x wE) + (S x wS)` with the per-pair weights
  from the Aug. 20 draft VA Methodology (see `docs/SCORING_RUBRICS.md`), bucket High / Medium /
  Low with breaks written to config, `V_max` and `V_max_pair` per asset under the aggregation
  rule. Criticality is not a multiplier: `C_class` is carried as its own field and the hotspot
  lists rank by V within the High criticality class first.
- `scripts/hotspots.py`: per hazard, top 25 assets by V and a corridor roll-up (route name x
  jurisdiction, length-weighted mean V, count High). Output `outputs/hotspots_<hazard>.csv`.
  This is the facilitator report-out sheet and the poster callout list.
- Publish `PROTECT_VA` v2 (hosted feature service, five layers: roads, bridges, culverts,
  active transport, transit centers) with a written schema in `docs/PROTECT_VA_schema.md`.
  All pages read this service; nothing is embedded.

### 2.6 Black sky scenarios in RA2CE (Oct. 19 to 30)

- Choose the two scenarios from the hotspot output, not ahead of it. Scenario 1 is the agenda's
  example: wildfire closure of SR-89 on the West Shore (Emerald Bay to Tahoe City). Scenario 2
  should be the other state, a different hazard, and a different season; candidates are
  US-50 East Shore landslide or rockfall at Cave Rock, or an atmospheric river flood at the
  SR-89 and US-50 junction in South Lake Tahoe.
- Build `hazard.tif` per scenario (the ra2ce notebook's Part 4 has never run because this raster
  is missing) and run: single-link redundancy delta, origin-destination access to the four
  service types (shelters, medical, law enforcement, evacuation exits), isolated hexes and
  population, and the top 10 links that carry the rerouted demand.
- Outputs per scenario: `outputs/scenario_<id>/` with closed links, OD delta per hex, summary
  JSON, and a 1-page fact sheet for the facilitator (what closes, where traffic goes, who loses
  access, which systems it cascades into: emergency services, transit, fuel, schools).
- Promote the ra2ce notebook to `scripts/ra2ce/run_scenario.py` with a scenario YAML, so a
  third scenario in December is a config change.

### 2.7 Print and screen maps (Nov. 2 to 4, print by Nov. 5)

Made by hand in ArcGIS Pro, not scripted. One layout per hazard, two versions each (exposure
only for the screen reveal, assets scored for the posters), plus two scenario maps. The code
side only has to deliver clean scored layers with one shared High / Medium / Low field so the
symbology is the same in every layout.

---

## 3. Website work (html/, TRPA dashboard stack)

### 3.1 risk-index-tool.html: Workshop 1 release (Oct. 19 to Nov. 4)

The page that answers "what data or features would be most helpful". It should mirror the
activity so participants recognize what they just did at the posters.

- Hazard selector (Flooding, Wildfire, Landslide, Debris Flow, Avalanche) driving the exposure
  layer and the per-pair fields.
- Asset class toggles for all five classes, replacing the disabled Bridges and Culverts
  buttons.
- Show-assets switch (exposure only versus assets scored), for the on-screen reveal.
- Score-by control: Exposure, Sensitivity, Criticality, Vulnerability Rating. One High /
  Medium / Low legend shared with the posters.
- Asset popup with the E, S, C, V breakdown, the data source per component, and the
  `S_source` flag so default values are honest.
- Hotspots panel: top assets and corridors for the selected hazard, click to zoom, read from
  the hotspot CSVs published alongside the service.
- Table tab: AG Grid on the selected asset class with the score fields and Export CSV.
- Charts tab: assets by rating per hazard and asset class, and by jurisdiction (Plotly).
- Methods tab: replace the placeholder with the rubrics, weights, aggregation rule, horizon,
  and fallbacks from `docs/SCORING_RUBRICS.md`.
- Status tab: keep, and update each component as it goes live.
- Retire the fixed Arcade criticality expression once `PROTECT_VA` v2 carries the scored
  fields; the page should read scores, not compute them.

### 3.2 Scenario explorer (Oct. 27 to Nov. 4; first thing to cut)

The black sky exercise runs on printed scenario maps and the fact sheets, so the explorer is
nice to have for Nov. 9 and required for December. Build it as a Scenarios tab in the tool
rather than a new page to keep it small.
Baseline versus scenario toggle, closed links in red, OD access change per hex, isolated
population, reroute links, and the fact-sheet text. Two scenario tabs. Reads
`outputs/scenario_<id>/` published as a second hosted service or as GeoJSON in the repo.

### 3.3 Criticality pages (Oct. 8 to 10, alongside the ICF criticality review)

- `criticality-index.html`: adopt the config weights and show the 0-3 class alongside the
  index, so the app and the tool agree.
- `criticality-index-hazards.html`: fold into the tool's score-by control and retire, or keep
  as an internal check. Recommend retire; it duplicates the tool once hazard filters exist
  there.
- `od-services-index-simple.html` and `od-services-index.html`: keep one. The simple page
  was built for the Steering Committee; the scenario explorer supersedes both for the
  workshop.

### 3.4 Reference hub and landing page (Nov. 2 to 4)

- Hub: add a Rubrics tab generated from `docs/SCORING_RUBRICS.md`; update the data and model
  inventory status for every element that went live; record the Steering Committee decision on
  the four proposed pairs (seiche, high lake level) in the pairs grid and
  Hazard_Asset_Pairs.md.
- Landing page: Workshop 1 release banner, card for the scenario explorer, phasing updated
  with the Dec. 2026 finalize milestone.
- Run the `trpa-dashboard-qa` checklist on every page before the freeze.

### 3.5 Feedback capture (Nov. 5 to 6, low effort)

A hosted feature layer `Workshop1_Feedback` (hazard, asset class, location, comment, source:
sticky, poll, or tool) and a Feedback layer toggle in the tool. Digitize the sticky notes and
the Mentimeter asset-of-concern answers the week after the workshop. This becomes the
"missing assets" and "feature requests" backlog for the December tool release.

---

## 4. Schedule

| Week | Analysis | Website | ICF checkpoint |
|---|---|---|---|
| Oct. 6 to 9 | **Criticality final, Oct. 7.** Rubrics doc; consolidate geodatabase; build the four point-asset layers; flooding exposure (roads) Oct. 9 | Criticality page adopts config weights and 0-3 class; schema stub for `PROTECT_VA` v2 | Criticality review done Oct. 9 |
| Oct. 12 to 16 | Wildfire, landslide, avalanche, debris flow exposure, rolling; sensitivity for all classes; Vulnerability Rating v0.1 and hotspots Oct. 16 | Tool UI skeleton against the schema stub | VA review starts; Oct. 15 VA meeting; methods and results due Oct. 16 |
| Oct. 19 to 23 | Apply ICF feedback; pick the two scenarios; build scenario hazard rasters; publish `PROTECT_VA` v2 | Tool reads live scores; hazard and asset controls; hotspots panel | |
| Oct. 26 to 30 | RA2CE scenario runs; fact sheets; **all results final Oct. 30** | Table and charts tabs; methods tab from rubrics; Scenarios tab if time allows | Results final |
| Nov. 2 to 6 | Print layouts Nov. 2 to 4; **posters to print Nov. 5**; slides | Hub and landing updates; QA checklist; **tool freeze Nov. 4**; feedback layer | Tool and materials final |
| Nov. 9 | Workshop | | |

Purchased flood and fire data not in hand by Oct. 12 goes into the December release, not the
workshop. Say so on the Status tab rather than waiting. There is no slack week: a hazard that
slips past Oct. 16 ships to ICF as a proxy method with the gap stated, not late.

---

## 5. Decisions needed this week

1. Who presents the VA block, TRPA or ICF. Determines who builds the slides.
2. Criticality weights, final, by Oct. 7. The equal-weight index is a placeholder; if no
   better weighting is agreed by then, ship equal weights as the method and say so.
3. Aggregation rule across pairs (recommend max).
4. Steering Committee outcome on the four proposed pairs.
5. Scenario 2 location and hazard.
8. Avalanche method. The status summary lists it as undecided. Default: score roads by
   intersect with the TRPA avalanche zone class, no runout modeling, with the initial corridor
   list (US-50, SR-89, SR-28, SR-207, SR-431) as the check against local knowledge.
9. Whether debris flow ships as a proxy (WRF intensity x slope x fire severity) or waits for
   wildcat. Default: proxy for the workshop, wildcat for December.
6. Contracted flood and fire delivery dates, or confirm the public fallback for the workshop.
7. Whether workshop attendees get a URL to the tool. The repo is an internal review draft; the
   Pages URL is public once shared.

---

## 6. Out of scope for the workshop

Earthquake, wind, winter storm, seiche, and high lake level scoring; 2050 and 2100 horizons;
Expected Annual Loss; pavement condition outreach; the two-repo split; the standalone
scenario explorer page; retiring the duplicate OD and criticality-hazards pages. All of these
are December or later.

---

## 7. Lane plan: culverts, bridges, debris flow, avalanche

Eight pairs, two asset inventories, two hazard surfaces, and the pieces of the tool and the
posters that show them. Dated to the ICF checkpoints in the header.

### 7.1 Inputs needed from the other lane, with dates

| Need | By | Used for |
|---|---|---|
| Road segment layer with stable IDs and the combined criticality 0-3 | Oct. 9 | Parent-segment join so bridges and culverts inherit C; AV-R and DF-R scoring |
| Flood exposure surface as FEMA zone classes | Oct. 9 | FL-B, FL-C exposure |
| Landslide exposure surface (USGS susceptibility, classed) | Oct. 12 | LS-B, LS-C exposure |
| Burn severity proxy or older burn probability raster | Oct. 12 | DF-R, DF-B, DF-C exposure conditioning |
| `PROTECT_VA` v2 schema agreed (field names for E, S, C, V per pair) | Oct. 9 | Everything downstream |

If the Oct. 9 items slip, score against the current `PROTECT_VA` streets layer and the live
`Streams_and_Flood_Zone` service and re-run when the final layers land. Do not wait.

### 7.2 Oct. 6 to 9: inventories, rubrics, method calls

- Bridges. Confirm the completed inventory's source and location (expected National Bridge
  Inventory, CA and NV, basin clip). Verify it carries structure number, condition rating,
  scour criticality, deck rating and type, channel and waterway adequacy, year built, and a
  parent road segment ID. Add what is missing. Publish as a layer alongside the streets.
- Culverts. Re-run the legacy-match fix from Aug. 1 on `data/processed/culverts.gpkg` and
  `culvert_condition.parquet`; expect the 1,626 provisional records to drop. Snap each culvert
  to its parent segment and store the ID. Confirm condition, capacity, scour, age, and channel
  condition fields; where condition is null, set `S_source = default` so the map shows the
  gap. Publish. The Douglas County question (4 records typed as culverts) gets a note, not a
  fix.
- Rubrics. Write the eight pair rubrics into `docs/SCORING_RUBRICS.md` (0-3 for E and S each,
  dataset, field, breaks). Bridge and culvert sensitivity rubrics come from NBI condition and
  scour codes and from the culvert condition table; exposure rubrics for flood and landslide
  use the other lane's class breaks so the two lanes stay comparable.
- Avalanche method, decide Oct. 7. Default: roads scored by intersect with the TRPA avalanche
  zone class, length-weighted max per segment, no runout, with the corridor list (US-50,
  SR-89, SR-28, SR-207, SR-431) as the sanity check. Confirm scope with the state DOTs at the
  workshop, not before.
- Debris flow method, decide Oct. 7. Default for the workshop: a proxy surface built from the
  WRF 1-hour intensity grid against the Tahoe intensity threshold, slope and contributing area
  from the lidar DTM, and the burn severity proxy as the conditioning factor. Wildcat stays
  the December method unless the environment is approved this week; if it is, run it in
  parallel and compare, do not swap mid-stream.
- Aggregation rule. Propose max-pair rating to ICF with the rubrics; it matters most for
  culverts (three pairs) and bridges (three pairs), so this lane owns the recommendation.

### 7.3 Oct. 12 to 16: score and ship, rolling

| Date | Ship to ICF |
|---|---|
| Oct. 12 | FL-B and FL-C exposure (FEMA class at the structure, culvert capacity screen from the storm events page as a second indicator; high lake stage as tailwater flagged on shoreline culverts) |
| Oct. 13 | LS-B and LS-C exposure (USGS class at the structure, 25 m buffer) |
| Oct. 14 | AV-R exposure on roads |
| Oct. 15 | Sensitivity for all bridge and culvert pairs (six S fields), with `S_source` |
| Oct. 16 | DF-R, DF-B, DF-C exposure from the proxy surface; method note stating it is a proxy and what wildcat will replace |

Each delivery is a feature class plus a one-page method note and a CSV export, so ICF can
review in a spreadsheet. Promote the code as it stabilizes: `scripts/score_exposure.py`
and `scripts/score_sensitivity.py` take an asset class and pair list from `config.yaml`.

### 7.4 Oct. 19 to 30: feedback, final, scenarios

- Apply ICF feedback from the Oct. 15 meeting and the rolling reviews.
- Bridges and culverts into `PROTECT_VA` v2 as their own layers with E, S, C, V per pair and
  `V_max`, `V_max_pair`.
- Hotspots for bridges, culverts, debris flow, and avalanche: top 25 assets and corridor
  roll-ups per hazard, to the facilitator sheet.
- Scenario support. If either black sky scenario involves a post-fire storm or a shoreline
  flood, this lane supplies the closure set (which culverts and bridges fail at the scenario
  intensity) as the link-failure input for RA2CE. Decide with the scenario pick the week of
  Oct. 19.
- Debris flow: if wildcat ran, document the comparison with the proxy in
  `debris-flow/docs/` and pick one for the final results by Oct. 28.
- All eight pairs final Oct. 30.

### 7.5 Nov. 2 to 5: maps and tool

- Print maps for debris flow and avalanche, made by hand in Pro: exposure-only and
  assets-scored versions each. Bridge and culvert symbology is set once in Pro and shared with
  the other lane as a layer file by Nov. 2 so every hazard poster matches.
- Tool: enable the Bridges and Culverts toggles; popups with E, S, C, V and `S_source`;
  bridge and culvert rows in the hotspots panel and the table tab; the Status tab entries for
  culverts, bridges, debris flow, and avalanche.
- Storm events page: link the culvert screening to the tool's FL-C results so the two agree,
  and match the site header.
- Hub: inventory rows for culverts, bridges, debris flow, and avalanche updated to Live or
  Proxy; rubrics tab rows for the eight pairs.
- Slides: one slide each for the bridge and culvert sensitivity sources and the debris flow
  and avalanche methods, handed to whoever presents.

### 7.6 Lane decisions this week

Avalanche method (Oct. 7), debris flow proxy versus wildcat (Oct. 7), and the aggregation
rule recommendation to ICF (with the rubrics, Oct. 9). Everything else in section 5 belongs
to the other lane or to ICF.

### 7.7 Code to write, in order

Maps, slides, and method notes are by hand. This is the code list, each item small enough to
finish in a sitting, in dependency order.

1. `scripts/build_bridges.py` (done Oct. 7): reads the 40-structure NBI basin clip, keeps
   the condition, scour, channel, waterway, type, and year fields with decoded labels, snaps
   to the parent segment, writes `Bridges` to the analysis geodatabase.
2. `scripts/load_culverts_gdb.py` (done Oct. 7): loads the engineered geopackage and
   condition table into the analysis geodatabase as `Culverts` + `CulvertCondition` with
   the relationship class, parent segment snap, and `has_condition`. The legacy-match
   re-run that would drop provisional records is deferred; the 1,626 provisional records
   stay in, flagged by jurisdiction, until the notebook is re-run.
   Shared helpers live in `scripts/va_common.py`.
3. `scripts/score_exposure.py`: one function per hazard surface (FEMA zone class, USGS
   landslide class, avalanche zone class, debris flow proxy raster) that takes an asset layer
   and writes `E_<pair>` 0-3 from breaks in `config.yaml`. Points sample with a 25 m buffer,
   lines take the length-weighted max.
4. `scripts/debris_flow_proxy.py`: WRF 1-hour intensity grid thresholded at the Tahoe value,
   times a slope and contributing-area factor from the DTM, times the burn severity proxy, to
   one 0-3 raster. Replaced by wildcat output in December without changing step 3.
5. `scripts/score_sensitivity.py`: `S_<pair>` 0-3 for bridges and culverts from condition,
   scour, capacity, age, and elevation, per the rubric table in `config.yaml`.
6. `scripts/compute_vulnerability.py`: `(E x wE) + (S x wS)` per pair, `C_class` carried
   separately, bucket, `V_max` and `V_max_pair`.
   Shared with the other lane; this lane writes it since bridges and culverts are the
   multi-pair case.
7. `scripts/hotspots.py`: top 25 per hazard and corridor roll-up, CSV out.
8. Publish helper: push the bridge and culvert layers to `PROTECT_VA` v2 with the agreed
   schema.
9. Tool: Bridges and Culverts toggles, popups, hotspots rows, table rows, Status tab text.
