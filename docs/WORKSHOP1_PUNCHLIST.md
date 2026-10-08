# Workshop 1 punch list: Oct. 8 to Nov. 9, 2026

Combined data-team list for both lanes, dated to the ICF checkpoints. Check items off here;
the detailed reasoning and method notes stay in `WORKSHOP1_BUILD_PLAN.md`. Updated Oct. 8, 2026.

Lanes:

- **Hazards and structures (HS):** all hazard exposure surfaces classed 0-3 (wildfire, flood,
  landslide, debris flow, avalanche); bridges and culverts (inventory, sensitivity, exposure to
  every hazard); debris flow and avalanche pairs and print maps; bridge and culvert pieces of
  the tool; the storm events page. Pairs FL-B, FL-C, LS-B, LS-C, DF-B, DF-C, DF-R, AV-R.
- **Network and criticality (NC):** street network, the four criticality components and the
  combined 0-3 class; transit center and active transport inventories; the road, transit, and
  active-transport pairs (sampling the classed surfaces); RA2CE scenarios; the criticality and
  OD apps. Pairs FL-R, FL-AT, FL-TC, LS-R, WF-R, WF-AT, WF-TC.
- **Shared:** rubrics, `PROTECT_VA` v2 schema, the rating and hotspot scripts, the tool
  framework, the hub and landing page, slides.

ICF checkpoints: criticality final Oct. 7; VA methods and results Oct. 16 (rolling per hazard
from Oct. 9); Oct. 15 VA meeting; all results final Oct. 30; tool and materials final Nov. 6;
Workshop Nov. 9.

---

## Week of Oct. 5 to 9: rubrics, asset base, first surface

| Done | Due | Lane | Item |
|---|---|---|---|
| [ ] | Oct. 7 | NC | Criticality weights final; combined 0-3 class written to the road layer; promote `Asset_Scoring.ipynb` to `scripts/score_criticality.py` with weights in `config.yaml`; road layer plus one-page method note to ICF |
| [x] | Oct. 8 | HS | Lane defaults confirmed Oct. 8: debris flow proxy for the workshop, Wildcat for December; road-crossing rule applied to both El Dorado and Washoe pipes; max-pair aggregation; avalanche by dominant slope plus record flag as in rubric section 5, zone layer as a record source, no runout |
| [ ] | Oct. 8 | HS | Send NDOT the workshop-display sign-off request (segment-level aggregates only; NDOT reviews before anything is shown) |
| [ ] | Oct. 8 | HS | Inventory the three baseline surfaces (FEMA zones in `Streams_and_Flood_Zone`, USGS landslide raster on F:, high-severity fire layer): paths, CRS, resolution, vintage, NV-side gaps |
| [ ] | Oct. 9 | Shared | `docs/SCORING_RUBRICS.md` v0.2 to ICF as PDF or Word, with the max-pair recommendation; HS closes the flood, landslide, and wildfire class breaks before sending |
| [ ] | Oct. 9 | NC | One geodatabase, one road layer: `Streets_Network_Tahoe` in `PROTECT_analysis.gdb`; migrate the hazard flags; retire `PROTECT_analysis_recovered.gdb` and `Streets_Network_Drive` |
| [ ] | Oct. 9 | NC | Segment layer with stable IDs and `C_class` handed to HS; bridges and culverts inherit C through `parent_segment_id` |
| [ ] | Oct. 9 | NC | Active transport (paved or unpaved, slope from the DTM) and transit center (site elevation) inventories in the analysis geodatabase with stable IDs and C from priority-zone and strategic-asset proximity |
| [ ] | Oct. 9 | NC | Fix `Asset_Criticality.ipynb` cell 9 (says 100 m buffer, uses 10) |
| [ ] | Oct. 9 | Shared | `PROTECT_VA` v2 schema agreed: field names for E, S, C, V per pair, `V_max`, `V_max_pair`, `S_source`; stub `docs/PROTECT_VA_schema.md` |
| [ ] | Oct. 9 | HS | Flood surface classed 0-3 (FEMA A/AE, X500, X) in the analysis geodatabase, breaks in `config.yaml`; handed to NC |
| [ ] | Oct. 9 | HS | `scripts/score_exposure.py` started: flood function, breaks from config, 25 m buffer for points, length-weighted max for lines |
| [ ] | Oct. 9 | HS | Culvert rerun: road-crossing rule for El Dorado and Washoe in the notebook; regenerate `culverts.gpkg`; reload with `load_culverts_gdb.py` (NDOT rows in memory only) |
| [ ] | Oct. 12 | HS | NLCD 2021 clip requested from the MRLC viewer Oct. 8; when it lands, save to F:, set `profile.nlcd`, rerun `--stage delineate --overwrite` then `--stage attributes`. Until then the profile uses the default runoff coefficient; say so in the FL-C method note |
| [x] | Oct. 8 | HS | `build_bridges.py --overwrite` to add NBI items 45 and 48 (ran on the server) |
| [x] | Oct. 8 | HS | Server clone: 10 m smoke test of `culvert_profile.py`, all three stages. Fixes on the `server-run` branch: outputs folder, drainage-tree cycles, area cross-check, DDF table tracked |
| [ ] | Oct. 9 | HS | 2 m run started Oct. 8 (`--stage all --overwrite`, no land cover); check the log in the morning: zero cut links expected, snap count up from 3,653, area mismatches down from 592 |
| [ ] | Oct. 10 | NC | `criticality-index.html` adopts the config weights and shows the 0-3 class next to the index |

## Week of Oct. 12 to 16: score and ship, rolling to ICF

| Done | Due | Lane | Item |
|---|---|---|---|
| [ ] | Oct. 12 | HS | Wildfire surface classed 0-3 (older burn probability; TRPA Fire/3 high-severity probability as the second indicator); handed to NC |
| [ ] | Oct. 12 | HS | FL-B and FL-C exposure to ICF: FEMA class at the structure, culvert capacity screen as the second indicator, high lake stage tailwater flag on shoreline culverts; feature class, method note, CSV |
| [ ] | Oct. 12 | NC | FL-R, FL-AT, FL-TC exposure to ICF from the classed flood surface |
| [ ] | Oct. 12 | Shared | Contracted flood and fire data cutoff: anything not in hand goes to December; say so on the tool Status tab |
| [ ] | Oct. 13 | HS | Landslide surface classed 0-3 (USGS susceptibility, mean or max in the 25 m buffer decided and recorded); LS-B and LS-C exposure to ICF |
| [ ] | Oct. 13 | NC | WF-R, WF-AT, WF-TC exposure to ICF |
| [ ] | Oct. 14 | HS | Avalanche surface (TRPA `Avalanche_Zones` class, length-weighted max per segment); AV-R exposure to ICF; corridor list (US-50, SR-89, SR-28, SR-207, SR-431) as the sanity check |
| [ ] | Oct. 14 | NC | LS-R exposure to ICF |
| [ ] | Oct. 15 | HS | `scripts/score_sensitivity.py`: six S fields for bridges and culverts (condition, scour, capacity, age, elevation) with `S_source`; to ICF |
| [ ] | Oct. 15 | NC | Sensitivity for roads (default S = 1 with `S_source`), active transport, transit centers; equity applied once at criticality, not again here |
| [ ] | Oct. 15 | Shared | ICF VA meeting |
| [ ] | Oct. 16 | HS | `scripts/debris_flow_proxy.py`: WRF 1-hr intensity vs the Tahoe threshold, slope and contributing area from the DTM, burn severity proxy, to one 0-3 raster; DF-R, DF-B, DF-C exposure to ICF with the proxy method note |
| [ ] | Oct. 16 | Shared | `scripts/compute_vulnerability.py`: (E x wE) + (S x wS) per pair, buckets with breaks in config, `C_class` carried separately, `V_max` and `V_max_pair`; Vulnerability Rating v0.1 and hotspots v0.1 to ICF (HS writes, both lanes run) |
| [ ] | Oct. 16 | Shared | Tool UI skeleton built against the v2 schema stub (hazard selector, five asset toggles, score-by control, show-assets switch) |

## Week of Oct. 19 to 23: feedback, scenarios, publish

| Done | Due | Lane | Item |
|---|---|---|---|
| [ ] | Oct. 21 | Both | Apply ICF feedback from the Oct. 15 meeting and the rolling reviews |
| [ ] | Oct. 21 | Shared | Pick the two black sky scenarios from the hotspot output (Scenario 1: SR-89 West Shore wildfire closure; Scenario 2: other state, other hazard, other season) |
| [ ] | Oct. 23 | NC | Scenario `hazard.tif` per scenario; `scripts/ra2ce/run_scenario.py` with a scenario YAML |
| [ ] | Oct. 23 | HS | If a scenario is a post-fire storm or shoreline flood: closure set (which culverts and bridges fail at the scenario intensity) as the RA2CE link-failure input |
| [ ] | Oct. 23 | Shared | Publish `PROTECT_VA` v2: five layers (NC publishes roads, active transport, transit centers; HS supplies bridges and culverts with E, S, C, V per pair); `docs/PROTECT_VA_schema.md` final |
| [ ] | Oct. 23 | Shared | Tool reads live scores from v2; hazard and asset controls; hotspots panel from the CSVs; retire the Arcade criticality expression |

## Week of Oct. 26 to 30: results final

| Done | Due | Lane | Item |
|---|---|---|---|
| [ ] | Oct. 28 | HS | If Wildcat ran: comparison with the proxy in `debris-flow/docs/`, pick one for the final results |
| [ ] | Oct. 30 | NC | RA2CE scenario runs: single-link redundancy delta, OD access to the four service types, isolated hexes and population, top 10 reroute links; one-page fact sheet per scenario |
| [ ] | Oct. 30 | Both | All 15 pairs final; `scripts/hotspots.py` final (top 25 per hazard, corridor roll-up) to the facilitator sheet |
| [ ] | Oct. 30 | Shared | Tool: table tab (AG Grid, Export CSV), charts tab (Plotly), methods tab from the rubrics; Scenarios tab only if time allows (first thing to cut) |

## Week of Nov. 2 to 6: maps, tool freeze, materials

| Done | Due | Lane | Item |
|---|---|---|---|
| [ ] | Nov. 2 | Mason | Symbology set once in Pro and saved as layer files (`.lyrx`) for every scored layer so all posters match: one shared High / Medium / Low field, bridge and culvert point symbols, road line widths by class |
| [ ] | Nov. 2 | NC | Scored layers for the maps delivered clean to `PROTECT_VA` v2 (roads, active transport, transit centers) and the two scenario outputs (closed links, OD delta per hex, isolated hexes) in `outputs/scenario_<id>/` |
| [ ] | Nov. 4 | Mason | Print maps, see the list below: 10 hazard layouts plus 2 scenario layouts, made by hand in Pro from one template |
| [ ] | Nov. 4 | Mason | Screen versions of the same 12 layouts exported as PDF for the on-screen reveal (exposure first, assets revealed) |
| [ ] | Nov. 4 | Shared | Tool freeze: popups with E, S, C, V and `S_source`; bridges and culverts in hotspots and table; Status tab current for every component; `trpa-dashboard-qa` checklist on every page |
| [ ] | Nov. 4 | HS | Storm events page: culvert screening linked to the tool's FL-C results; header matched to the site |
| [ ] | Nov. 4 | Shared | Hub: Rubrics tab from `SCORING_RUBRICS.md`; inventory rows to Live or Proxy; Steering Committee decision on the four proposed pairs recorded. Landing page: Workshop 1 banner, phasing with the December milestone |
| [ ] | Nov. 5 | Both | Posters to print |
| [ ] | Nov. 5 | Both | Slides to the presenter: criticality (NC); bridge and culvert sensitivity sources, debris flow and avalanche methods (HS); one scenario overview slide (NC) |
| [ ] | Nov. 6 | NC | `Workshop1_Feedback` hosted layer (hazard, asset class, location, comment, source) and the Feedback toggle in the tool |
| [ ] | Nov. 9 | Both | Workshop 1 |
| [ ] | Nov. 13 | Both | Digitize sticky notes and Mentimeter answers into `Workshop1_Feedback`; December backlog started |

---

## Decisions still open

| Need by | Decision | Who |
|---|---|---|
| Oct. 9 | Who presents the VA block, TRPA or ICF (decides who builds the slides) | TRPA project lead with ICF |
| Oct. 9 | Max-pair aggregation across pairs | HS recommends, ICF confirms |
| Oct. 12 | Contracted flood and fire delivery dates, or confirm the public fallback for the workshop | ICF |
| Oct. 12 | Wildcat environment approval (if yes, run in parallel with the proxy; do not swap mid-stream) | TRPA IT |
| Oct. 16 | Steering Committee outcome on the four proposed pairs (seiche, high lake level) | Steering Committee via ICF |
| Oct. 21 | Scenario 2 location and hazard | Shared |
| Nov. 2 | Whether attendees get the tool URL (the Pages site is public once shared) | TRPA project lead |

## Out of scope for the workshop

Earthquake, wind, winter storm, seiche, and high lake level scoring; 2050 and 2100 horizons;
Expected Annual Loss; pavement condition outreach; the two-repo split; the standalone scenario
explorer page; retiring the duplicate OD and criticality-hazards pages. December or later.

---

## Print maps (Mason, Nov. 2 to 4, to the printer Nov. 5)

One Pro template, basin extent, TRPA brand, the same High / Medium / Low legend on every sheet.
Each hazard gets two sheets: exposure only (for the on-screen reveal and the station poster
before assets are added) and assets scored (the poster the facilitators work from). Large
format for the stations, PDF for the screen.

| Done | Map | Exposure layer | Assets shown on the scored version |
|---|---|---|---|
| [ ] | 1. Flooding, exposure | FEMA zone class 0-3 | - |
| [ ] | 2. Flooding, assets scored | FEMA zone class 0-3 | Roads (FL-R), bridges (FL-B), culverts (FL-C), active transport (FL-AT), transit centers (FL-TC) by V |
| [ ] | 3. Wildfire, exposure | Burn probability class 0-3, high-severity probability inset | - |
| [ ] | 4. Wildfire, assets scored | same | Roads (WF-R), active transport (WF-AT), transit centers (WF-TC) by V |
| [ ] | 5. Landslide, exposure | USGS susceptibility class 0-3 | - |
| [ ] | 6. Landslide, assets scored | same | Roads (LS-R), bridges (LS-B), culverts (LS-C) by V |
| [ ] | 7. Debris flow, exposure | Proxy raster 0-3 (or Wildcat if it ran) | - |
| [ ] | 8. Debris flow, assets scored | same | Roads (DF-R), bridges (DF-B), culverts (DF-C) by V |
| [ ] | 9. Avalanche, exposure | TRPA avalanche zone class 0-3, corridor labels | - |
| [ ] | 10. Avalanche, assets scored | same | Roads (AV-R) by V |
| [ ] | 11. Scenario 1: SR-89 West Shore wildfire closure | Scenario hazard raster | Closed links, reroute links, OD access change per hex, isolated population |
| [ ] | 12. Scenario 2 (location and hazard decided Oct. 21) | Scenario hazard raster | same |

Also: a criticality-only map (C_class on roads, bridges, culverts) as the context sheet at the
entrance, if time allows. Hotspot callouts (top 25 per hazard from `outputs/hotspots_<hazard>.csv`)
labeled on the scored sheets.

---

## Resources and notes

### Scripts and notebooks: what does what

| File | What it does | Status |
|---|---|---|
| [`scripts/va_common.py`](../scripts/va_common.py) | Shared helpers for the VA asset scripts: config load, timestamped logs, analysis geodatabase, parent-segment snap (50 m) so points inherit criticality | Live |
| [`scripts/build_bridges.py`](../scripts/build_bridges.py) | NBI basin clip (40 structures) to the `Bridges` feature class: condition, scour, channel, waterway, age, type with decoded labels; snapped to the parent segment | Live; rerun `--overwrite` for items 45 and 48 |
| [`scripts/load_culverts_gdb.py`](../scripts/load_culverts_gdb.py) | Loads `data/processed/culverts.gpkg` and `culvert_condition.parquet` into the analysis geodatabase as `Culverts` + `CulvertCondition` with the relationship class; appends the NDOT rows in memory | Live |
| [`scripts/ndot_culverts.py`](../scripts/ndot_culverts.py) | Reads the NDOT SAM21 export in place on F: into the culvert schema (road-crossing rule splits culverts from pipes). RESTRICTED: never written under the repo | Live |
| [`scripts/culvert_profile.py`](../scripts/culvert_profile.py) | Rubrics 2.2, 2.4, 2.5: `terrain` and `delineate` stages (flow direction, accumulation, watershed per culvert on the 2 m DEM, server job) and `attributes` (contributing area, capacity, loading ratio, condition harmonization) | Attributes stage run once offline; terrain and delineate never run |
| [`notebooks/culvert_layer_engineering.ipynb`](../notebooks/culvert_layer_engineering.ipynb) | Builds the culvert layer from six jurisdiction deliveries plus the legacy TRPA compilation; writes the geopackage and condition parquet. Methods in [`docs/METHODS_culverts.md`](METHODS_culverts.md) | Live; needs the El Dorado and Washoe crossing rule and the legacy-match rerun |
| [`scripts/Asset_Criticality.ipynb`](../scripts/Asset_Criticality.ipynb) | The four criticality components on `Streets_Network_Tahoe` (detour length, traffic volume, equity, OD service access) | Working; cell 9 buffer defect |
| [`scripts/Asset_Scoring.ipynb`](../scripts/Asset_Scoring.ipynb) | Combines the components into the criticality index; the hazard flags from the next notebook ride along | Working; promote to `scripts/score_criticality.py` |
| [`scripts/Hazard_Vulnerability.ipynb`](../scripts/Hazard_Vulnerability.ipynb) | Per-segment hazard extracts: `in_flood_zone`, `in_flood_zone_100`, `landslide_mean`, `landslide_max`, `high_sev_fire`. Still points at the recovered geodatabase and `Streets_Network_Drive` | Working; migrate to the one geodatabase |
| [`scripts/ra2ce/ra2ce_tahoe.ipynb`](../scripts/ra2ce/ra2ce_tahoe.ipynb) | RA2CE network setup on the Overture streets, single-link redundancy, OD access. Part 4 (hazard overlay) has never run: no `hazard.tif` yet | Working through Part 3 |
| [`scripts/Wildcat/Wildcat.ipynb`](../scripts/Wildcat/Wildcat.ipynb) and [`debris-flow/notebooks/01_wildcat_scoping.ipynb`](../debris-flow/notebooks/01_wildcat_scoping.ipynb) | USGS Wildcat debris-flow scoping; environment not yet created (see [`debris-flow/environment.md`](../debris-flow/environment.md)) | Scoped |
| [`notebooks/wepp_debris_flow_hindcast.ipynb`](../notebooks/wepp_debris_flow_hindcast.ipynb) | WEPP sediment runs and the July 14 debris-flow hindcast feeding the storm events page | Built |
| [`climate/notebooks/`](../climate/notebooks/) 01 to 07 | LOCA2, Cal-Adapt, gridMET, Atlas 14 extraction; transform; QA; WRF 1-hr intensity grid (notebook 07) used by the debris-flow proxy. Methods in [`climate/docs/METHODS.md`](../climate/docs/METHODS.md) | Validated run |
| `scripts/score_exposure.py` | E_<pair> 0-3 per hazard surface, breaks from config, 25 m buffer for points, length-weighted max for lines | To write (Oct. 9) |
| `scripts/debris_flow_proxy.py` | WRF intensity x slope and contributing area x burn severity proxy to one 0-3 raster | To write (Oct. 16) |
| `scripts/score_sensitivity.py` | S_<pair> 0-3 for bridges and culverts from condition, scour, capacity, age, elevation; `S_source` | To write (Oct. 15) |
| `scripts/compute_vulnerability.py` | (E x wE) + (S x wS), buckets, `V_max`, `V_max_pair`, `C_class` carried | To write (Oct. 16) |
| `scripts/hotspots.py` | Top 25 per hazard and corridor roll-up to `outputs/hotspots_<hazard>.csv` | To write (Oct. 16 first cut) |
| `scripts/score_criticality.py` | Promoted from `Asset_Scoring.ipynb`, weights in `config.yaml` | To write (NC, Oct. 7) |
| `scripts/ra2ce/run_scenario.py` | Promoted from the RA2CE notebook, scenario YAML in | To write (NC, Oct. 23) |

### Data paths

All paths resolve through [`config.yaml`](../config.yaml); change them there, not in scripts.

| What | Path | Notes |
|---|---|---|
| Analysis geodatabase (the one geodatabase) | `F:\GIS\PROJECTS\Transportation\Protect\PROTECT_analysis\PROTECT_analysis.gdb` | `config.yaml` `paths.analysis_gdb`. Holds `Streets_Network_Tahoe`, `Bridges`, `Culverts`, `CulvertCondition`, and the scored layers to come. `Tahoe_Culvert_merge` in here is the legacy compilation, not the VA layer |
| Terrain work geodatabase (server job) | `F:\GIS\PROJECTS\Transportation\Protect\PROTECT_analysis\PROTECT_terrain.gdb` | `profile.work_gdb`; flow direction, accumulation, watersheds from `culvert_profile.py` |
| Recovered geodatabase (retire) | `F:\GIS\PROJECTS\Transportation\Protect\PROTECT_analysis\PROTECT_analysis_recovered.gdb` | Still referenced by `Hazard_Vulnerability.ipynb`; migrate and stop using |
| Legacy TRPA culverts (read only) | `F:\GIS\PROJECTS\Transportation\Protect\PROTECT_analysis\Assets.gdb\Tahoe_Culvert` | `paths.legacy_culverts`; gap fill only |
| Landslide surface | `F:\GIS\PROJECTS\Transportation\Protect\PROTECT_analysis\usgs_landslide_risk.tif` | USGS susceptibility; to be classed 0-3 |
| Flood surface | `https://maps.trpa.org/server/rest/services/Streams_and_Flood_Zone/MapServer` | FEMA zone classes; confirm the layer index |
| Wildfire surface | `https://maps.trpa.org/server/rest/services/Fire/MapServer` (high-severity probability, layer 3) plus the older burn probability raster | Confirm where the burn probability raster lives on F: |
| Avalanche surface | `https://maps.trpa.org/server/rest/services/Avalanche_Zones/MapServer` | Zone class |
| DEM of record (hydro-enforced) | `F:\GIS\DB_CONNECT\Raster.sde\SDE.DEM_BareEarth_LiDAR_2010` | `paths.dem`; 2 m, EPSG 26910; no Fill step. Not usable for blue-spot work |
| Engineered culvert layer (public) | `data/processed/culverts.gpkg` and `data/processed/culvert_condition.parquet` | Git-tracked, served by Pages; never put NDOT rows here |
| NDOT SAM21 export (RESTRICTED) | `F:\GIS\PROJECTS\Transportation\Protect\Data\Culvert\NDOT\SAM21_Export_260707-1551\NDOT_Culverts.gdb` | `ndot.gdb`; read in place only; NDOT reviews derivatives before publication |
| Raw jurisdiction culvert deliveries | `C:\GIS\Culvert\<jurisdiction>` | Outside the repo, one folder per jurisdiction |
| Published VA service (v1, roads only) | `https://services5.arcgis.com/fXXSUzHD5JjcOt1v/arcgis/rest/services/PROTECT_VA/FeatureServer/0` | v2 adds bridges, culverts, active transport, transit centers |
| Climate outputs | `climate/outputs/` (projections, `wrf_i1h_grid.geojson`) | WRF 1-hr grid feeds the debris-flow proxy |

### Reference documents

- [`WORKSHOP1_BUILD_PLAN.md`](WORKSHOP1_BUILD_PLAN.md): the reasoning behind every item here; section 7 is the HS lane in detail.
- [`SCORING_RUBRICS.md`](SCORING_RUBRICS.md): the 0-3 rubrics per pair, 18 decisions for ICF.
- [`METHODS_culverts.md`](METHODS_culverts.md) and [`jurisdiction_data_questions.md`](jurisdiction_data_questions.md): culvert layer methods and the open questions per jurisdiction.
- [`../Hazard_Asset_Pairs.md`](../Hazard_Asset_Pairs.md): source of record for the 15 pairs.
- [`SESSION_NOTES.md`](SESSION_NOTES.md): shared working notes and hard-won process rules.
- [`risk_index_tool_scoping.md`](risk_index_tool_scoping.md): the tool vision and phasing.
- Live pages: [index](../html/index.html), [reference hub](../html/reference-hub.html), [risk index tool](../html/risk-index-tool.html), [criticality index](../html/criticality-index.html), [climate data](../html/climate-data.html), [storm events](../html/tahoe-precip-events.html).
