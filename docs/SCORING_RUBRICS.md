# PROTECT scoring rubrics

**Version 0.7, Oct. 21, 2026.** TRPA working document for the
vulnerability assessment.

**What this document is.** TRPA's scoring rules, built on the draft Vulnerability
Assessment Methodology (Aug. 20, 2026). We made a few new calls and the numbered notes at the end of each section say where TRPA departed from the draft and why. Anything TRPA added or changed is marked **TRPA
proposal**. The interactive page is `html/scoring-rubrics.html`;
pair definitions doc is `Hazard_Asset_Pairs.md`.

## 1. Shared framework

### 1.1 Equation and scale

Every indicator scores 0 to 3 and carries a weight. Most score in half-point steps; a few score
whole points. Weights sum to 1.0 within a pair, so the pair score is on the same 0 to 3 scale:

    V_<pair> = sum over indicators of (weight x score)

wE is the sum of the exposure weights and wS the sum of the sensitivity weights, so this is the
draft's "Vulnerability = (Exposure Score x wE) + (Sensitivity Score x wS)" written per
component. `E_<pair>` and `S_<pair>` are the weight-normalized component scores (0 to 3) so
the tool can show them separately. Weights are written as decimals here, percentages in the
draft.

Several draft sensitivity rubrics floor at 1 rather than 0 (bridge condition, culvert
condition, scour codes 5 to 9), so a sensitivity component is rarely 0. That is the draft's
design and is kept. Roads carry no sensitivity (decision 25).

Per-pair weights, from the draft:

| Hazard | Roads | Bridges and large culverts | Small culverts | Active transport | Transit centers |
|---|---|---|---|---|---|
| Flooding | E 1.0 (decision 25) | E 0.3 / S 0.7 | E 0.3 / S 0.7 | E 0.7 / S 0.3 | E 1.0 |
| Landslide | E 1.0 (decision 25) | E 0.7 / S 0.3 | E 0.7 / S 0.3 | not scored | not scored |
| Wildfire | E 1.0 (decision 25) | not scored | not scored | E 1.0 | E 1.0 |
| Debris flow | E 1.0 (decision 25) | E 0.7 / S 0.3 | E 0.7 / S 0.3 | not scored | not scored |
| Avalanche | E 1.0 | not scored | not scored | not scored | not scored |

### 1.2 Buckets

`V_<pair>` is kept to two decimals and classed for the map and posters. **TRPA proposal
(decision 9):** Low under 1.0, Medium 1.0 to under 2.0, High 2.0 and over, set in `config.yaml`
(`scoring.v_breaks`). **Wildfire pairs (decision 26):** Low under 2.0, Medium 2.0 to 2.5, High
over 2.5 (`scoring.v_breaks_wildfire`).

### 1.3 Criticality

Road segments carry a 0 to 3 class (`C_class`); bridges and culverts inherit it through `parent_segment_id`. Full methods can be found [here](CRITICALITY_OVERVIEW.md)

### 1.4 Aggregation across pairs

An asset in several pairs (a culvert carries FL-C, LS-C, and DF-C) needs one rating for the
map and a way to sort the list. **TRPA proposal (decision 9):** the rating is the highest pair
score, `V_max`, with `V_max_pair` naming the hazard; `V_class` is the highest per-pair class,
since wildfire has its own breaks (section 1.2). The maximum flags an asset vulnerable to any
hazard, but it cannot tell an asset High on one hazard from one High on three, and that is the
sort prioritization needs. **TRPA proposal (decision 30):** carry two sort fields beside it,
the number of pairs classed High and the sum of the pair scores. The sum counts one failure at
one location more than once, so it ranks and never classes.

### 1.5 Horizons

Historical, 2050, and 2080. The Nov. 9 workshop uses historical only. Fields carry a horizon
suffix from the start (`E_FLC_hist`, `E_FLC_2050`, `E_FLC_2080`), so December adds columns. Sensitivity does not vary by horizon. FEMA zones have no future horizon; the flood
pairs carry the future through the culvert loading ratio (section 2.4), whose design flows take
2050 and 2080 factors from the climate pipeline. Whether the FEMA term also takes a
precipitation modifier is decision 29.

### 1.6 Missing data

Where the draft states one (bridge condition none scores 1, scour other scores 1) it is used; the rest are **TRPA proposals** (decision 8, section 2.8). An asset scored on any default carries `S_source` (or `E_source`) = `partial`; one with every sensitivity indicator defaulted carries `default`. Defaults are labeled on the map and in popups.

### 1.7 Sampling rule

Line assets (roads, trails) take the maximum of the hazard surface touching the segment, and
carry the share of their length in each class beside it (`len_pct_c0` to `len_pct_c3`). Point
assets (bridges, transit centers) take the maximum within 25 m. **Small culverts are the exception (decision 3):** surfaces that describe what arrives at the crossing (flood, debris flow, landslide) are sampled over the culvert's contributing watershed, with the 25 m buffer as the fallback where no watershed could be delineated.

---

## 2. Culverts (small culverts): FL-C, LS-C, DF-C

### 2.1 Asset set

**Large culverts** are the five National Bridge Inventory structures coded as culverts (NBI
item 43B = 19, spans over 20 ft); they sit in the `Bridges` layer (`is_culvert_type` = 1) and
score under section 3. **Small culverts** are everything in the `Culverts` layer that meets
this filter:

| Rule | Effect |
|---|---|
| `feature_type` = `culvert` | Scores. Stormwater pipes, inlets, and basins are inventory only |
| Road-crossing rule applied to El Dorado County and Washoe County pipes | El Dorado delivered no feature type, so all 2,615 of its pipes are typed stormwater pipe today and its roads would carry zero culverts. Apply the rule already used for NDOT: a pipe that crosses a `Streets_Network_Tahoe` centerline is a culvert unless both ends are manholes |
| Within 25 m of an NBI culvert-type structure | Excluded from scoring; `large_culvert_id` points at the bridge record |
| No `parent_segment_id` (not within 50 m of a road segment) | Inventory only; no criticality, no rating. Mostly provisional legacy points on forest roads (decision 10) |
| Jurisdiction = NDOT | Scored in the analysis geodatabase only. Nothing NDOT-derived at the asset level goes to a page, a public service, or a printed map without NDOT review; segment-level aggregates with NDOT attribution are allowed |

Expected scored set: about 5,000 culverts including NDOT.

### 2.2 Culvert profile (descriptive, hazard-independent)

The profile describes size and condition in the assessment's terms. It is written to the
`Culverts` feature class, shown in the popup and table, and feeds every sensitivity indicator.
It is not a score.

| Field | Definition | Source |
|---|---|---|
| `span_in`, `rise_in` | Cleaned opening dimensions. The -9999 sentinel and spans over 144 in. on circular pipes are nulled | Jurisdiction deliveries |
| `d_eq_in` | Equivalent diameter: `span_in` for circular pipes; `sqrt(4 x span x rise / pi)` for boxes, arches, ellipses | Derived |
| `size_class` | The draft's opening classes on `d_eq_in`: under 2 ft, 2 to under 3, 3 to under 5, 5 to under 7, 7 ft and over | Derived |
| `material_class` | Corrodible metal (CMP, CSP, squash, annular, corrugated metal), plastic (HDPE, PVC), concrete (RCP, concrete, box), unknown. El Dorado's undecoded `code N` values map to unknown until the county supplies the domain | `material` |
| `contrib_area_ac` | Contributing drainage area at the crossing | Flow accumulation on the conditioned lidar DEM (section 2.4) |
| `basin_slope_pct` | Mean slope of the contributing watershed | Same DEM, zonal mean |
| `basin_landcover` | Majority NLCD class in the watershed, grouped to the draft's four classes: water and snow (NLCD 11, 12), urban (21 to 24), trees (41, 42, 43, 90), shrubs (all other classes) | NLCD 2021 |
| `q_event_cfs` (hist, 2050, 2080) | Event peak flow at the crossing, 100-yr headline, 25-yr carried as a second column | Section 2.4 |
| `q_cap_cfs` | Hydraulic capacity with headwater at the crown | Section 2.4 |
| `load_ratio` | `q_event_cfs / q_cap_cfs` (the draft's Qevent/Qdesign) | Derived |
| `cond_class` | Harmonized latest-inspection condition on the draft's scale: 1 good, 2 fair, 3 poor | Section 2.5 |
| `cond_date`, `cond_stale` | Latest inspection date; stale when before 2015 | `CulvertCondition` |
| `blockage_pct` | Latest recorded blockage | Washoe `perc_full`, NDOT `PercentBlockage`, legacy text |
| `tailwater_flag` | Outlet within 50 m of the shoreline and below 6,230 ft (the legal maximum lake level is 6,229.1 ft) | DEM, high-water shoreline layer |
| `on_stream`, `size_suspect` | On a mapped stream (within 10 m of the lidar-derived streams and lakes). Flagged when the recorded size cannot be the crossing for the basin that arrives: 24 in. or under on a mapped stream with 100 acres or more, 24 in. or under with 500 acres or more anywhere, or any size under 8 in. (a wrong size field, a ditch pipe beside the real structure, or an underdrain). `load_ratio` is withheld and S1 takes its default | Derived (`profile.size_suspect`) |
| `ratio_review` | `load_ratio` above 20: scored as is but listed for the owner to confirm; `outputs/culvert_review_list.csv` | Derived |
| `profile_completeness` | `full`, `partial`, `default`: whether size, hydrology, and condition were observed or defaulted | Derived |

Notes on the profile:
- Pipe size is not scored on its own. A 24 in. pipe is fine on a small ditch and undersized
  on a creek, so the score uses `load_ratio` (event flow over capacity) and keeps `size_class`
  for display.
- Condition enters through `cond_class` only, in LS-C and DF-C (section 2.3). FL-C has no
  condition term (decision 1).
- Blockage is not scored. It is one inspection date on Washoe and NDOT crossings only (436 of
  5,096 scored culverts), so it stays in the popup.
- Age is not used. Only El Dorado County and the city record an install year, so
  `material_class` is the proxy.

### 2.3 Indicator rubrics

Weights and scores came from the draft unless marked **TRPA proposal**. The pair score is the
weighted sum.

**FL-C, flooding x small culverts** (E 0.3 / S 0.7)

The draft gives two sensitivity options: option 1 (StreamStats) takes debris potential from
basin slope and landcover and Qdesign from asset data; option 2 (CULVERT tool) takes both from
the tool. TRPA computes the option 1 matrix locally from its own watersheds and estimates Qcap
with HDS-5 (decisions 2 and 6). The option 2 scale is listed for reference.

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 | **TRPA proposal** (decision 19): FEMA flood zone and stream crossing, in place of the draft's flood depth indicator. The lake's own 1 percent stillwater zone (AE over Lake Tahoe) is excluded: lake-stage flooding is the high-lake-level pair, not adopted (`exposure.flood.include_lake_zone`) | 0.30 | 1 percent zone (A, AE) | 3 | 0 | Maximum within 25 m of the crossing on the road |
| | | | 0.2 percent zone (X500) | 2 | | |
| | | | on a mapped TRPA stream (10 m band) or an NHD flowline, outside a zone (decision 32) | 1 | | |
| | | | no zone, no flowline | 0 | | |
| E1 (draft, not applicable) | 100-yr flood depth over the road from a flood depth model, maximum of fluvial and pluvial. Listed for the record; no such dataset is being acquired | 0.30 | over 20 ft | 3 | | |
| | | | over 12 to 20 ft | 2.5 | | |
| | | | over 6 to 12 ft | 2 | | |
| | | | over 3 to 6 ft | 1.5 | | |
| | | | over 2 to 3 ft | 1 | | |
| | | | over 0 to 2 ft | 0.5 | | |
| | | | none | 0 | | |
| E1 modifier | **TRPA proposal** (decision 4): tailwater. Add 1 (maximum 3) when `tailwater_flag` is set, because high lake stage reduces outlet capacity independent of rainfall | in E1 | | | no change | |
| S1 | Debris potential of the basin: mean basin slope by majority landcover (draft option 1 matrix). Rows are slope, columns are landcover | 0.35 | 0 to 8 percent: water and snow 0, urban 0.5, shrubs 1, trees 1 | | 1 when no watershed, `S_source` partial | Watershed |
| | | | over 8 to 16 percent: water and snow 0, urban 1, shrubs 2.5, trees 2.5 | | | |
| | | | over 16 percent: water and snow 0, urban 2.5, shrubs 2.5, trees 3 | | | |
| S1 (option 2, not used) | CULVERT tool WDBFM debris-flow score, 0 to 5 | 0.35 | 5 | 3 | | |
| | | | 4 | 2.5 | | |
| | | | 3 | 2 | | |
| | | | 2 | 1.5 | | |
| | | | 1 | 1 | | |
| | | | 0 | 0.5 | | |
| S2 | 100-yr capacity loading ratio, `load_ratio` = Qevent / Qdesign; the 25-yr ratio is scored on the same bands as an alternate reading (decision 5) | 0.35 | 4 and over | 3 | 1 when `span_in` is null, `S_source` partial | Per crossing; multi-barrel crossings grouped (section 2.4) |
| | | | 3 to under 4 | 2.5 | | |
| | | | 2.5 to under 3 | 2 | | |
| | | | 2 to under 2.5 | 1.5 | | |
| | | | 1.5 to under 2 | 1 | | |
| | | | 1 to under 1.5 | 0.5 | | |
| | | | under 1 | 0 | | |

No condition term (decision 1): condition is observed on about one in five scored culverts, so
a third term would default to fair almost everywhere. `cond_class` stays in the popup.

**LS-C, landslide x small culverts** (E 0.7 / S 0.3)

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 | USGS landslide susceptibility, or a recorded landslide. **TRPA proposal** (decision 24): the USGS 2024 release holds the share of each 90 m cell that is landslide-prone, not five classes, so the draft's classes 5, 4, and 3 are read as over 80, 60, and 40 percent of the cell | 0.50 | over 80 percent of the cell prone (the draft's class 5), or any recorded landslide | 3 | 0 | **TRPA proposal:** maximum over the watershed; 25 m buffer where none |
| | | | over 60 to 80 percent (class 4) | 2 | | |
| | | | over 40 to 60 percent (class 3) | 1 | | |
| | | | 40 percent and under (classes 1 and 2) | 0 | | |
| E2 | Cal-Adapt annual precipitation change versus historical | 0.20 | over 40 percent | 3 | 0; the historical horizon scores 0 by definition | Watershed mean |
| | | | over 20 to 40 percent | 2 | | |
| | | | over 0 to 20 percent | 1 | | |
| | | | no change or decrease | 0 | | |
| S1 | Culvert size, opening width (`d_eq_in`) | 0.15 | under 2 ft | 3 | 2, `S_source` partial | Per asset |
| | | | 2 to under 3 ft | 2.5 | | |
| | | | 3 to under 5 ft | 2 | | |
| | | | 5 to under 7 ft | 1.5 | | |
| | | | 7 to 8 ft, and **TRPA interpretation** over 8 ft (the draft's lowest band; decision 20) | 1 | | |
| S2 | Culvert condition where available (`cond_class`) | 0.15 | poor | 3 | 2 (fair), `S_source` partial | Latest inspection |
| | | | fair | 2 | | |
| | | | good | 1 | | |

**DF-C, debris flow x small culverts** (E 0.7 / S 0.3)

Exposure is the shared debris-flow surface of section 4.2, option 1 (decision 15), sampled as
the watershed maximum. Under option 1 basin slope already sits in exposure, so the draft's
debris-potential sensitivity would count it twice. **TRPA decision (decision 7):** sensitivity
is opening size and condition on the LS-C scales.

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 to E3 | Section 4.2, option 1 | 0.70 total | | | | Watershed maximum |
| S1 | Opening size (`d_eq_in`), the LS-C S1 scale | 0.15 | as LS-C S1 | | 2, `S_source` partial | Per asset |
| S2 | Condition (`cond_class`), the LS-C S2 scale | 0.15 | as LS-C S2 | | 2 (fair), `S_source` partial | Latest inspection |
| S1 (draft, not used) | Debris potential of the basin, the FL-C S1 matrix | 0.30 | as FL-C S1 | | | Watershed |

### 2.4 Hydrology and hydraulics for the loading ratio

The draft's Qdesign is missing for nearly every culvert, so capacity is estimated from
geometry. Parameters live in `config.yaml`; the method is `scripts/culvert_profile.py` (stage
`attributes`). The local computation replaces the draft's StreamStats API call so NDOT crossings
are never sent to a third-party service.

- **Watershed.** Flow direction and accumulation on the TRPA hydro-enforced bare-earth lidar
  DEM (`SDE.DEM_BareEarth_LiDAR_2010`, 2 m, EPSG 26910), run at native resolution on the server.
  The enforcement carries mapped streams through their crossings but not every culvert, and
  the Oct. 8 QA found sinks behind unbreached fills that split accumulation or, once filled,
  spilled creeks along roadside ditches (292 pipes of 24 in. or less inherited basins over 100
  acres). The DEM is therefore conditioned with the culvert inventory itself: a 40 m breach
  line through every typed culvert, perpendicular to its road segment, lowered to the lower
  end minus 0.3 m (`profile.breach`), except within 10 m of the lidar-derived streams and lakes
  that the enforcement already carries; then sinks shallower than 3 m are filled
  (`profile.fill_z_limit_m`) and deeper sinks (lakes, real basins) kept. Pour point is the
  maximum-accumulation cell within 4 m of the culvert (`profile.pour_snap_m`). Culverts within
  10 m of each other on the same segment are one crossing: one watershed, capacities summed.
  Watershed polygons are kept and serve the sampling in section 2.3. Crossings rebuilt after
  the 2010 lidar are flagged where `install_year` is 2011 or later.
- **Event flow, Qevent.** Basins under 1 sq mi: rational method, Q = C i A. C is the
  area-weighted watershed mean of a cell surface on the Rawls, Wong, and McCuen (1981) table
  (NLCD class x hydrologic soil group x slope class, the 25-year-and-over column for both
  events; **decision 28**). Soil groups are SSURGO CA693, which covers both states (dual
  groups take the undrained letter); slope class is the 2 m slope averaged to 30 m (under 2, 2
  to 6, 6 and over percent); NLCD developed classes map to the table's residential and
  commercial rows by impervious share. Cells with no soil group, water, and barren take the
  land-cover values (forest 0.35, shrub and grass 0.40, developed 0.60, barren 0.50, water
  1.0), which remain available as a whole method (`profile.runoff_c_method: landcover`); both
  coefficients travel with every crossing (`runoff_c_lc`, `runoff_c_tab`, `runoff_c_method`).
  i is the Atlas 14 intensity at the basin's time of concentration (Kirpich), 100-yr headline
  and 25-yr carried; 2050 and 2080 apply the climate pipeline's DDF change factors to i. No
  frequency factor is applied on top of the table.
  Why the table: on the 58 California basins inside both methods' ranges (0.45 to 1 sq mi) the
  land-cover C gave flows about twice the Lahontan regression; with the table the regression is
  0.82 of the rational flow (Oct. 20, 2026 run; median basin C 0.20 on forest and 0.34 on
  developed basins, against 0.38 and 0.60 before). The attributes stage logs that ratio on
  every run.
  Basins of 1 sq mi and over (about 230 crossings): USGS regional regression for the state,
  Q_T = a A^b P^c, A in sq mi, P the PRISM 1991 to 2020 mean annual precipitation in inches.
  California, Lahontan region of Gotvald and others (2012, SIR 2012-5113, table 5): Q100 =
  0.713 A^0.731 P^1.56, Q25 = 0.394 A^0.733 P^1.58, standard error 76 to 77 percent. Nevada,
  region 1 of Thomas and others (1997, WSP 2433): Q100 = 6.78 A^0.750 P^0.668, Q25 = 3.08
  A^0.768 P^0.811, standard error 46 percent. On the same basin region 1 gives roughly one
  third of the Lahontan value (0.16 of the rational flow on its 31 basins); `q_region` records
  which applied, and `regression.nv_uses` can apply Lahontan basin-wide (**TRPA decision
  pending**).
- **Capacity, Qcap.** FHWA HDS-5 inlet-control submerged-inlet equation solved for Q at HW/D =
  1.0 (`profile.hw_d`), coefficients by shape, material, and inlet type (projecting end
  default), culvert slope assumed (`profile.culvert_slope`). At HW/D = 1.0 the form sits just
  below its strict validity range and underestimates capacity by roughly 10 to 20 percent
  against the nomographs, conservative for a screen; `q_full_cfs` (Manning full flow) is the
  cross-check. Barrels at one crossing are summed (`q_cap_crossing_cfs`) before the ratio.
- **Known limits.** The rational method is a screening estimate; slopes and roughness are
  assumed and inverts are not surveyed. Capacity is taken at HW/D = 1.0 while culverts are
  commonly designed for 1.5 or more, so the ratio is conservative by roughly that factor where
  ponding is tolerable. The ratio ranks; it does not design. The future factor scales rainfall
  intensity only and misses rain-on-snow winter peaks, so 2050 and 2080 ratios are a lower
  bound for mid-elevation basins. State all of this on the method slide.

### 2.5 Condition harmonization

`cond_class` is the draft's 1 (good) to 3 (poor) from the latest inspection per culvert.
Undated rows sort oldest. Recorded in `condition_scheme`; two are
unconfirmed and on the jurisdiction question list.

| Source | Rule | Caveat |
|---|---|---|
| Placer County 1 to 5 | 5 and 4 to good (1), 3 to fair (2), 1 and 2 to poor (3) | Direction unconfirmed; the distribution (mostly 4 and 5) supports 5 = good |
| Douglas County maintenance 1 to 5 (1 = replacement) | Same mapping | 4 culverts |
| NDOT overall Good/Fair/Poor plus blockage | G 1, F 2, P 3; blockage under 25 percent 1, 25 to under 50 percent 2, 50 percent and over 3; take the maximum | Overall rating is blank on 94 percent of visits, so blockage carries most of the signal |
| TRPA legacy text | First token Good/Fair/Poor to 1, 2, 3; Moderate to 2 | Provisional, often undated |
| Washoe County | Structural subscore is 2 on 793 of 806 rows and is treated as no signal; `perc_full` feeds `blockage_pct`; `cond_class` is partial | Code semantics unconfirmed |
| Caltrans, City of South Lake Tahoe, El Dorado County | No rating delivered. `cond_class` default 2 (fair), `S_source` partial; `cond_stale` set where the last Caltrans inspection predates 2015 | Caltrans has dates only |

Condition is observed on about one in five scored culverts (544 rated and 436 with a blockage
figure only, of 5,096). Say so on the slide.

### 2.6 Criticality and output fields

`C_class` is inherited from `parent_segment_id` on `Streets_Network_Tahoe`. Fields written to
the `Culverts` feature class beyond the profile:

| Field | Content |
|---|---|
| `E_FLC_hist`, `S_FLC`, `V_FLC_hist` | Component and pair scores, two decimals; `_2050` and `_2080` added in December |
| `E_LSC_hist`, `S_LSC`, `V_LSC_hist` | Same |
| `E_DFC_hist`, `S_DFC`, `V_DFC_hist` | Same; `DF_option` records 1, 2, or `proxy` |
| `S_FLC_q25`, `V_FLC_hist_q25` | FL-C on the 25-yr ratio (decision 5); not in `V_max` |
| `E_source`, `S_source` | `full`, `partial`, `default` per section 1.6 |
| `C_class` | Inherited criticality 0 to 3 |
| `V_max`, `V_max_pair`, `V_class` | Sections 1.4 and 1.2 |
| `large_culvert_id`, `scored` | Section 2.1 |

### 2.7 Validation and QA

- Distribution checks on `contrib_area_ac` and `load_ratio` by jurisdiction.
- Known-failure check. Three documented sites from the Task 3.1 literature review.
  High: the Aug. 2025 Incline Village flood from a blocked culvert on Northwood Blvd (a
  blockage, which the screen does not score, so this tests E1 and the loading ratio);
  the June 2026 Washoe County flash flood, 2 to 3 in. in under an hour and over 4 million
  dollars in road repairs (loading ratio at the 1-hr intensity); and the SR 89 culvert at Meeks
  Creek from the Caltrans District 3 Adaptation Priorities report, which is an NBI culvert-type
  structure and scores under section 3, so it cross-checks the two paths. Any crossing the
  DOTs or counties name as a repeat overtopping site is added. A screen with no known failures
  in its top class is not credible at the workshop.
- Prior-assessment counts: the City of South Lake Tahoe hazard mitigation plan counts seven
  transportation assets in the 1 percent floodplain and two in the 0.2 percent; compare before
  shipping FL-C.
- Design-event sensitivity: `score_vulnerability.py` logs the 25-yr versus 100-yr class
  crosstab on every run (decision 5).
- Row counts reconcile across the profile, the scored set, and the published layer, NDOT rows
  counted separately.

### 2.8 Notes

29. Flood horizons. The FEMA term has no 2050 or 2080 version. The loading ratio carries the
    future through the climate pipeline's change factors on the 25-yr and 100-yr intensities.
    Is that enough for the flood pairs, or should a precipitation-change modifier also be
    applied to the FEMA term? TRPA's working position is the loading ratio alone.

1. **TRPA decision (Oct. 21, 2026): no condition or blockage term in FL-C.** The draft's S1
   0.35 and S2 0.35 stand. Condition is recorded on 544 of 5,096 scored culverts and blockage
   on 436 more, so a third term would default to fair on four of five assets and separate
   nothing. `cond_class` stays in the popup and scores in LS-C and DF-C.
2. Debris potential computed locally with the option 1 matrix for every culvert, not the
   CULVERT tool score (option 2). NDOT data cannot go to a third-party tool, so option 2 would
   score Nevada highways differently from everything else.
3. Watershed sampling for culvert exposure (section 1.7) instead of a point buffer.
4. Tailwater modifier on FL-C E1 for shoreline outlets.
5. 100-yr as the loading-ratio event, 25-yr carried for comparison (the draft names the 100-yr
   as likely appropriate). The 25-yr reading is scored alongside (`S_FLC_q25`, `V_FLC_hist_q25`,
   config `scoring.flc.alt_rps`) and shown through the Design storm toggle on the Results page
   Flooding tab; it stays out of `V_max` and `V_class`. On the public culverts it moves about
   230 down one FL-C class (about 80 High to Medium, 150 Medium to Low) and never raises one.
6. Capacity from HDS-5 inlet control as the default Qdesign where asset records have none.
7. **TRPA decision (Oct. 21, 2026): DF-C sensitivity is opening size and condition** on the
   LS-C scales, 0.15 each, since basin slope already sits in option 1 exposure.
8. Missing-data defaults as stated per row in section 2.3.
9. Bucket breaks (section 1.2) and the max-pair aggregation rule (section 1.4).
10. Whether unsnapped forest-road culverts stay out of the rating.
19. **TRPA decision (Oct. 21, 2026): flood exposure is FEMA flood zones and stream crossings
    on every flood pair** (the FL-C E1 values: 1 percent zone 3, 0.2 percent zone 2, TRPA
    stream or NHD flowline 1, none 0; the stream value was 2 until decision 32), at the full exposure weight for roads, active transport,
    and transit centers, with the culvert loading ratio carrying the hydraulic signal. No depth
    model is being acquired, so the draft's depth indicators have no dataset. Absorbs decision
    21; the horizon question is decision 29.
20. Two gaps in the draft's tables, scored by TRPA interpretation until confirmed: culvert
    openings over 8 ft score 1 (the lowest band), and an avalanche record with no slope over
    25 degrees within 1,000 ft scores 1 (section 5.2).
28. **TRPA decision (Oct. 20, 2026): runoff coefficient from land cover, soil group, and
    slope.** C is the area-weighted mean of a cell surface on the Rawls, Wong, and McCuen (1981)
    table (the CULVERT tool's lookup), SSURGO CA693 soil groups, in place of one value per
    majority land cover, which gave flows about twice the Lahontan regression on comparable
    basins. The land-cover values stay as the fallback and are carried beside the table value.
    No frequency factor on top of the table (section 2.4).
30. Cumulative sort fields beside `V_max` (section 1.4): the number of pairs classed High and
    the sum of the pair scores. Not yet in the published layer.
31. **Withdrawn (Oct. 28, 2026): the 20 m band around the FEMA zones.** Adopted Oct. 27 from
    the consultant's Oct. 26 review (10 to 30 m around the 500-year floodplain as exposure 1)
    and never run. Withdrawn with decision 32: the review of the Results page showed that the
    flood signal on roads was already too broad, and a band around every zone would widen it
    again. `exposure.flood.near_zone_buffer_m` stays in the config at 0. The same review
    concurred with the FEMA-zone and stream-crossing approach and with an NHD flowline at 1.
32. **TRPA decision (Oct. 28, 2026): a stream crossing scores 1, not 2, on every flood pair**
    (`exposure.flood.stream_class`). At 2 a crossing read High on every road pair, since roads
    carry no sensitivity: 264 of the 287 High road miles (2,288 of 2,668 segments) were High only
    because the segment touched the 10 m band around a mapped stream somewhere along its
    length, so a 4.5-mile mountain road turned High end to end for one creek. The 500-year zone
    accounted for 1.8 miles and the 100-year zone for 22. Scored at 1, a crossing reads Medium,
    the FEMA zones keep 2 and 3, and the scale matches the consultant's reading of a stream
    crossing (an NHD flowline) as exposure 1. Previewed on the Oct. 20 tables: High road miles
    across all hazards drop from 41 to 26 percent and Medium rises from 9 to 25 percent; flood
    alone leaves 23 High miles. Culverts and bridges take the new value too (E_FLC is the
    highest class in the drainage area); takes effect at the next flood run.

---

## 3. Bridges and large culverts: FL-B, LS-B, DF-B

### 3.1 Asset set

The `Bridges` layer has the 40 National Bridge Inventory structures inside the TRPA boundary,
built by `scripts/build_bridges.py`. Five are NBI culvert-type structures (item 43B = 19) and
score here, not in section 2. Every structure inherits `C_class` from `parent_segment_id`.
Structures not over a waterway (scour item 113 = N) stay in the set; their water-dependent
sensitivity indicators score low.

NBI condition items run 0 (failed) to 9 (excellent), N for not applicable. The draft's bands are
0 to 2 (3), 3 to 4 (2.5), 5 (2), 6 (1.5), and 7 to 9, N, or none (1); the draft's "2 to 4" is
read as 3 to 4 so the bands do not overlap. Item 45 (main spans) and item 48 (maximum span
length, meters in the layer, feet in the draft) are carried as `main_spans` and `max_span_m`.

### 3.2 Indicator rubrics

**FL-B, flooding x bridges** (E 0.3 / S 0.7)

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 | Waterway adequacy, NBI item 71 (`waterway_eval`) | 0.20 | 0 to 1 (severe overtopping or closure from waterway capacity) | 3 | **TRPA proposal:** 1 when blank (the draft says TBD) | Per structure |
| | | | 2 to 3 (frequent overtopping) | 2.5 | | |
| | | | 4 to 5 (occasional overtopping with significant delays) | 2 | | |
| | | | 6 (occasional overtopping with insignificant delays) | 1.5 | | |
| | | | 7 to 8 (slight chance of overtopping) | 1 | | |
| | | | 9 (remote chance of overtopping) | 0.5 | | |
| | | | N (not over a waterway) | 0 | | |
| E2 | **TRPA proposal** (decision 19): FEMA flood zone at the structure, the FL-C E1 values, in place of the draft's change-in-depth indicator | 0.10 | as FL-C E1 | | 0 | Maximum within 25 m |
| E2 (draft, not applicable) | Change in 100-yr flood depth at the structure relative to historical from a flood depth model. Listed for the record | 0.10 | over 5 ft | 3 | | |
| | | | over 4 to 5 ft | 2.5 | | |
| | | | over 3 to 4 ft | 2 | | |
| | | | over 2 to 3 ft | 1.5 | | |
| | | | over 1 to 2 ft | 1 | | |
| | | | over 0 to 1 ft | 0.5 | | |
| | | | 0 or less | 0 | | |
| S1 | Channel and channel protection, NBI item 61 (`channel_cond`) | 0.10 | 0 to 2 (near or full channel failure) | 3 | **TRPA proposal:** 1 when blank | Per structure |
| | | | 3 (bank protection failure) | 2.5 | | |
| | | | 4 (bank protection severely undermined) | 2 | | |
| | | | 5 (bank protection eroded) | 1.5 | | |
| | | | 6 to 7 (minor damage) | 1 | | |
| | | | 8 to 9 (no noteworthy deficiencies) or N (not over a waterway) | 0.5 | | |
| S2 | Scour criticality, NBI item 113 (`scour_code`) | 0.40 | 1 (imminent failure) | 3 | 1 (the draft's "other" band covers blanks and U) | Per structure |
| | | | 2 (critical condition) | 2.5 | | |
| | | | 3 (serious condition) | 2 | | |
| | | | 4 (poor condition) | 1.5 | | |
| | | | 5 to 9, U, N, or other | 1 | | |
| S3 | Span type, NBI item 45 (`main_spans`) | 0.10 | single span (item 45 = 1) | 3 | **TRPA proposal:** 1 when blank | Per structure |
| | | | continuous span (item 45 over 1) | 1 | | |
| S4 | Bridge condition, lowest of NBI items 58, 59, 60 (62 for culvert-type structures), `lowest_rating` | 0.10 | 0 to 2 (poor) | 3 | 1 (the draft scores N or none as 1) | Per structure |
| | | | 3 to 4 (poor) | 2.5 | | |
| | | | 5 (fair) | 2 | | |
| | | | 6 (fair) | 1.5 | | |
| | | | 7 to 9 (good), N, or none | 1 | | |

E1 is an inventory attribute, not a hazard surface: item 71 encodes observed overtopping
frequency, in effect a recorded exposure history.

**LS-B, landslide x bridges** (E 0.7 / S 0.3)

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 | USGS Landslide Susceptibility Index class, or a recorded landslide (California Landslides Database) | 0.50 | as LS-C E1 | | 0 | Maximum within 25 m, plus the parent segment's value where the abutment slopes extend past the buffer |
| E2 | Cal-Adapt annual precipitation change versus historical | 0.20 | as LS-C E2 | | 0; historical horizon scores 0 | At the structure |
| S1 | Span type, NBI item 45 | 0.10 | as FL-B S3 | | 1 | Per structure |
| S2 | Bridge condition, `lowest_rating` | 0.10 | as FL-B S4 | | 1 | Per structure |
| S3 | Span length, NBI item 48 (`max_span_m`, converted to feet) | 0.10 | over 500 ft (major bridge) | 3 | **TRPA proposal:** 1 when blank | Per structure |
| | | | over 350 to 500 ft | 2.5 | | |
| | | | over 200 to 350 ft | 2 | | |
| | | | over 100 to 200 ft | 1.5 | | |
| | | | over 50 to 100 ft | 1 | | |
| | | | over 20 to 50 ft | 0.5 | | |
| | | | 0 to 20 ft (short-span bridge) | 0 | | |

The draft scores longer spans higher. **TRPA proposal** (decision 12): reverse it. Item 48 is
the maximum span, which is the pier spacing, and FHWA's debris guidance holds that longer spans
are less prone to debris blockage and that piers should stay out of the main channel where
possible (HEC-9, FHWA-IF-04-016, 2005, section 6.26). Bridges with piers were more vulnerable
than bridges without in a fragility study of 15 lahar-hit bridges (Dagá and others, 2018, Nat.
Hazards Earth Syst. Sci. 18, 2111 to 2125). If the draft's direction reflects replacement cost,
that is consequence, which the framework carries in criticality, not sensitivity.

**DF-B, debris flow x bridges** (E 0.7 / S 0.3)

Exposure is the shared debris-flow surface of section 4.2, sampled over the crossing's
watershed where the structure is over a waterway and within 25 m otherwise. Sensitivity is the
LS-B set (span type 0.10, condition 0.10, span length 0.10), same values, same direction
question.

### 3.3 Output fields

`E_FLB_hist`, `S_FLB`, `V_FLB_hist`, and the LS-B and DF-B equivalents; `C_class`; `V_max`,
`V_max_pair`, `V_class`; `E_source`, `S_source`; `DF_option`. Horizon columns are added in
December.

### 3.4 Validation

- Meeks Creek (structure 25 0019; culvert condition 5, scour code 4) is the Caltrans
  Adaptation Priorities cross-check and should land High or Medium on FL-B.
- The Placer County vulnerability assessment flags I-80 bridges for flooding; none are in the
  basin, so this is a method check, not a result check.
- With 40 structures, review every row by hand against the NBI record before publication.

### 3.5 Notes

11. Whether "NBI 45 span type" in the draft means item 45 (number of main spans) or item 43
    (structure type). The rubric assumes item 45.
12. The direction of the span-length indicator. The draft scores longer spans higher; TRPA
    proposes the reverse (sources in section 3.2).

**Resolved by the draft.**

13. Resolved by the draft's table: scour codes 5 to 9, U, and blanks score 1. No action.
14. Resolved by decision 19: E2 is the FEMA zone at the structure under every horizon. No action.

Consultant review of the results (Oct. 26, 2026): the bridge and large-culvert approach is consistent with the original recommendation for landslide; no additional comments.

---

## 4. Debris flow x roads: DF-R

### 4.1 Asset set and sampling

`Streets_Network_Tahoe` segments, scored as the maximum along the segment. Segment IDs
and `C_class` come from the criticality assessment. The debris-flow surface is built once so
DF-R, DF-B, and DF-C share one surface and one set of breaks.

### 4.2 Indicator rubrics (E 1.0, exposure only; decision 25)

Exposure is option 1 (decision 15); option 2 and the TRPA proxy are listed for the record. All
are rasters so roads (maximum along the segment), bridges (25 m or watershed), and culverts
(watershed) sample the same surfaces. The weights below are the draft's; on roads they scale
to the full weight in the same proportions (option 1: 0.29, 0.29, 0.43; option 2: 0.50, 0.25,
0.25; proxy: 1.00). The S rows are the draft's and are not scored for roads.

| Code | Indicator | Weight | Indicator value | Score | Default | Build |
|---|---|---|---|---|---|---|
| E1 (option 1) | Mean basin slope. Raster: mean slope of the upslope contributing area at each cell, from the hydro-enforced DEM | 0.20 | over 30 percent | 3 | 1 | DEM |
| | | | over 25 to 30 percent | 2.5 | | |
| | | | over 20 to 25 percent | 2 | | |
| | | | over 15 to 20 percent | 1.5 | | |
| | | | over 10 to 15 percent | 1 | | |
| | | | over 5 to 10 percent | 0.5 | | |
| | | | 0 to 5 percent | 0 | | |
| E2 (option 1) | Drainage area. Raster: contributing area at each cell; smaller areas lead to higher debris-flow intensities | 0.20 | under 0.25 sq mi | 3 | 1 | DEM flow accumulation |
| | | | 0.25 to 0.5 sq mi | 2.5 | | |
| | | | over 0.5 to 1 sq mi | 2 | | |
| | | | over 1 to 2 sq mi | 1.5 | | |
| | | | over 2 to 3 sq mi | 1 | | |
| | | | over 3 to 5 sq mi | 0.5 | | |
| | | | over 5 sq mi | 0 | | |
| E3 (option 1) | Contracted predicted soil burn severity | 0.30 | high | 3 | 0 | As delivered |
| | | | moderate | 2 | | |
| | | | low | 1 | | |
| | | | unburned or very low | 0 | | |
| E1 (option 2) | Wildcat debris-flow likelihood, stream-segment results rasterized to the contributing area of each modeled segment | 0.30 | over 75 percent | 3 | 0 | `debris-flow/` pipeline |
| | | | over 60 to 75 percent | 2.5 | | |
| | | | over 50 to 60 percent | 2 | | |
| | | | over 40 to 50 percent | 1.5 | | |
| | | | over 25 to 40 percent | 1 | | |
| | | | over 0 to 25 percent | 0.5 | | |
| | | | 0 | 0 | | |
| E2 (option 2) | Wildcat combined hazard classification | 0.15 | high (3) | 3 | 0 | Same |
| | | | moderate (2) | 2 | | |
| | | | low (1) | 1 | | |
| | | | none or no assessment | 0 | | |
| E3 (option 2) | Contracted predicted soil burn severity | 0.15 | as E3 (option 1) | | 0 | As delivered |
| E1 (proxy, not used) | TRPA proxy raster (WRF 1-hr intensity against the Tahoe threshold, slope and contributing area from the DEM, burn severity proxy), classed 0 to 3 in whole points. Listed for the record | 0.70 | class 3 | 3 | 0 | `tahoe-precip-events.html` |
| | | | class 2 | 2 | | |
| | | | class 1 | 1 | | |
| | | | class 0 | 0 | | |
| S1 (draft; not scored for roads (decision 25)) | Pavement condition | 0.15 | poor | 3 | | |
| | | | fair | 2 | | |
| | | | good or none | 1 | | |
| S2 (draft; not scored for roads (decision 25)) | Paved versus unpaved | 0.15 | unpaved | 3 | | |
| | | | paved | 1 | | |

`DF_option` records which exposure applied.

### 4.3 Notes

- Option 1 reuses the flow-accumulation and slope rasters from the culvert delineation; burn
  severity is the only new input, and the TRPA most-likely fire severity surface (the decision
  22 input) stands in for predicted soil burn severity until the contracted package arrives.
- The draft's drainage-area direction (smaller scores higher) describes the concentrated runoff
  of small steep basins. A road crossing a large river scores low on this term; a road below a
  small burned ravine scores high. Intended.
- The segment maximum catches both the crossing and the toe of slope; a segment with one High
  culvert reads High. Intended.
- Roads carry no sensitivity (decision 25), so pavement condition is not a gap for roads.

### 4.4 Notes

15. **TRPA decision (Oct. 21, 2026): option 1 for the Nov. 9 workshop.** Option 2 (Wildcat) is
    reviewed for December; the proxy is not used.
16. Resolved: the draft's drainage-area breaks and direction are adopted. No action.

Consultant review of the results (Oct. 26, 2026): option 1 is consistent with the original recommendation; debris flow to be reviewed in more detail as data becomes available. The review also noted that most of the network scores Medium or High and that some overlap with landslide is expected; the stand-in pairs stay out of the combined class, and the question is revisited with the Wildcat run.

---

## 5. Avalanche x roads: AV-R

### 5.1 Asset set and sampling

`Streets_Network_Tahoe` segments, maximum along the segment, exposure only (E 1.0), current
terrain, no climate horizon. The corridor list (US-50, SR-89, SR-28, SR-207, SR-431) is the check, not the scope: every segment is scored, and a High segment off those corridors is
a finding to review with the state DOTs.

### 5.2 Indicator rubric

The draft scores one combined lookup of avalanche record and dominant slope angle within 1,000
ft (its header shows two 35 percent weights, but one score is read per row, so it is a single
indicator at 1.00). The draft does not define dominant slope; the definitions are **TRPA
proposals** (decisions 17 and 18).

- **Dominant slope:** the slope class covering the largest area uphill of the road within
  1,000 ft, from the lidar DEM aggregated to 10 m. Slopes under 25 degrees rarely release and
  slopes over 50 shed snow before it accumulates, which is why the bands step down both sides
  of 35 to 45.
- **Record:** a Sierra Avalanche Center accident-map point, a National Avalanche Accident
  Database entry, or (**TRPA proposal**, decision 18) a mapped TRPA `Avalanche_Zones` polygon
  or a documented closure in the Task 3.1 event catalog (SR 431 Jan. 2017 and Mar. 2023; US 50
  Echo Summit Apr. 2019), within 1,000 ft.

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 | Historical avalanche record within 1,000 ft combined with the dominant slope angle within 1,000 ft | 1.00 | record, and 35 to 45 degrees | 3 | 0 | Length-weighted maximum per segment |
| | | | record, and 30 to under 35 or over 45 to 50 degrees | 2.5 | | |
| | | | record, and 25 to under 30 or over 50 degrees | 2 | | |
| | | | no record, and 35 to 45 degrees | 2 | | |
| | | | no record, and 30 to under 35 or over 45 to 50 degrees | 1.5 | | |
| | | | no record, and 25 to under 30 or over 50 degrees | 1 | | |
| | | | record, and under 25 degrees (**TRPA interpretation**, decision 20: the draft has no row for this case) | 1 | | |
| | | | no record, and under 25 degrees | 0 | | |

### 5.3 Validation

- The five corridors should carry nearly all High segments; list any High segment off them for
  the DOTs.
- Avalanches rarely damage infrastructure (literature review), which is why AV-B left the VA.
  The score describes closure likelihood, not damage.

### 5.4 Notes

17. The definition of dominant slope (largest-area class on the uphill side within 1,000 ft).
    The classes and scores are the draft's.
18. Whether the TRPA avalanche zone layer and documented closures count as records alongside
    the two accident databases. TRPA default: yes; the accident databases alone are not used.

Consultant review of the results (Oct. 26, 2026): the avalanche approach appears generally consistent with the original recommendation.

---

## 6. Roads, active transport, and transit centers: FL-R, FL-AT, FL-TC, LS-R, WF-R, WF-AT, WF-TC

### 6.1 Asset sets and sampling

Roads are `Streets_Network_Tahoe` segments, maximum along the segment. Active transport is the
Class 1 and Class 2 trail inventory (paved or unpaved, slope from the DTM), maximum along the
trail. Transit centers are points, maximum within 25 m (300 ft for wildfire, per the draft).
Segment IDs, the inventories, and `C_class` come from the criticality assessment.

### 6.2 Flooding: FL-R, FL-AT, FL-TC

The draft scores two exposure indicators at 0.35 each: floodplain extent (10-yr scoring 3 down
to 1,000-yr scoring 0.5) and 100-yr depth. There is no depth model, and FEMA maps only the 100-
and 500-year floodplains, which would score 2 and 1 on the draft's scale with the top bands
unused. **TRPA proposal** (decisions 19 and 21): one exposure indicator, the FEMA flood zone and
stream crossing on the FL-C E1 values, at the full exposure weight, so every flood pair samples
the same surface.

**FL-R, flooding x roads** (E 1.0, exposure only; decision 25)

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 | **TRPA proposal:** FEMA flood zone and stream crossing, the FL-C E1 values, in place of the draft's extent and depth indicators | 1.00 (draft 0.70; decision 25) | as FL-C E1 | | 0 | Maximum along the segment |
| E1 (draft, not applicable) | Floodplain extent, lowest intersecting floodplain: 10-yr 3, 50-yr 2.5, 100-yr 2, 200-yr 1.5, 500-yr 1, 1,000-yr 0.5, none 0; and 100-yr flood depth on the FL-C depth scale (over 20 ft scores 3) | 0.35 each | | | | |
| S1 (draft; not scored for roads (decision 25)) | Pavement condition | 0.10 | poor | 3 | | |
| | | | fair | 2 | | |
| | | | good or none | 1 | | |
| S2 (draft; not scored for roads (decision 25)) | Paved versus unpaved | 0.10 | unpaved | 3 | | |
| | | | paved | 1 | | |
| S3 (draft; not scored for roads (decision 25)) | Truck AADT | 0.10 | over 1,000 | 3 | | |
| | | | over 500 to 1,000 | 2.5 | | |
| | | | over 250 to 500 | 2 | | |
| | | | over 100 to 250 | 1.5 | | |
| | | | under 100 | 1 | | |

**FL-AT, flooding x active transport** (E 0.7 / S 0.3)

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 | **TRPA proposal:** FEMA flood zone and stream crossing, the FL-C E1 values | 0.70 | as FL-C E1 | | 0 | Maximum along the trail |
| S1 | Paved versus unpaved trail | 0.15 | unpaved | 3 | 3 (unpaved, per the draft) | Trail inventory |
| | | | paved | 1 | | |
| S2 | Trail slope | 0.15 | 15 percent and over | 3 | **TRPA proposal:** 1 when unknown (the draft says TBD), `S_source` partial | Mean slope from the DTM |
| | | | 10 to under 15 percent | 2 | | |
| | | | 5 to under 10 percent | 1 | | |
| | | | under 5 percent | 0 | | |

**FL-TC, flooding x transit centers** (E 1.0)

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 | **TRPA proposal:** FEMA flood zone and stream crossing, the FL-C E1 values, in place of the draft's extent and depth indicators (the draft's transit center depth thresholds, 3 at over 8 ft, have no dataset) | 1.00 | as FL-C E1 | | 0 | Maximum within 25 m |

### 6.3 Landslide: LS-R

**LS-R, landslide x roads** (E 1.0, exposure only; decision 25; E1 and E2 scaled to 0.71 and 0.29)

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 | USGS Landslide Susceptibility Index class, or a recorded landslide | 0.50 | as LS-C E1 | | 0 | Maximum along the segment |
| E2 | Cal-Adapt annual precipitation change versus historical | 0.20 | as LS-C E2 | | 0; historical horizon scores 0 | Segment mean |
| S1 (draft; not scored for roads (decision 25)) | Pavement condition. The draft prefers embankment condition or stabilization measures where available; pavement condition is the stand-in | 0.30 | poor | 3 | | |
| | | | fair | 2 | | |
| | | | good or none | 1 | | |

### 6.4 Wildfire: WF-R, WF-AT, WF-TC

The draft scores annual burn probability and flame length, maximum within 300 ft, current
conditions, from the contracted fire-behavior package. TRPA holds current data for both from
the Sierra Nevada Regional Resource Kit (Pyrologix 2022, 30 m): annual burn probability on the
draft's breaks, and the three fire severity probabilities stacked as the TRPA most-likely fire
severity layer (`Fire` service, layer 3), classed Low 1, Moderate 2, High 3 in place of flame
length. **TRPA proposal** (decision 22): these are the workshop inputs; the contracted package
replaces them for December on the same breaks if delivered and reviewed in time. The 2018 FSim
set mixes vintages and predates the 2021 Caldor Fire, so it is not used.

**WF-R, wildfire x roads** (E 1.0, exposure only; decision 25)

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 | Annual burn probability (RRK Pyrologix 2022; contracted fire-behavior modeling when delivered) | 0.70 | over 1 percent | 3 | 0 | Maximum within a 300 ft buffer along the segment |
| | | | over 0.5 to 1 percent | 2 | | |
| | | | over 0 to 0.5 percent | 1 | | |
| | | | 0 percent | 0 | | |
| E2 | **TRPA proposal** (decision 22): TRPA most-likely fire severity (RRK 2023 severity probabilities, stacked) in place of flame length | 0.30 | High | 3 | 0 | Highest class covering at least 25 percent of the 300 ft buffer (decision 27) |
| | | | Moderate | 2 | | |
| | | | Low | 1 | | |
| | | | outside the layer (non-burnable) | 0 | | |
| E2 (draft, when the contracted package is delivered) | Flame length | 0.30 | over 8 ft | 3 | 0 | Maximum within a 300 ft buffer |
| | | | over 4 to 8 ft | 2 | | |
| | | | over 0 to 4 ft | 1 | | |
| | | | 0 ft | 0 | | |
| S1 (draft; not scored for roads (decision 25)) | Wooden guardrails present | 0.30 | present | 3 | | |
| | | | not present | 1 | | |

**WF-AT, wildfire x active transport, and WF-TC, wildfire x transit centers** (E 1.0)

The WF-R exposure set, E1 0.70 and E2 0.30, no sensitivity. Both sample E1 as the maximum
within 300 ft. E2 is the
highest severity class covering at least 25 percent of the 300 ft buffer on both (decision 27).

### 6.5 Notes

**For the record.** TRPA's choice is in use; flag anything you disagree with.

21. Folded into decision 19 (FEMA flood zones as the one flood exposure indicator for roads,
    active transport, and transit centers).
22. Wildfire exposure from the data in hand: RRK annual burn probability (Pyrologix 2022, 30 m)
    on the draft's breaks, and TRPA most-likely fire severity classed Low 1, Moderate 2, High 3
    in place of flame length. The contracted package replaces them for December if delivered
    and reviewed in time, on the same breaks.
23. Missing-data defaults the draft leaves TBD: truck AADT 1 (under 100; no longer used,
    decision 25) and trail slope 1 (5 to under 10 percent), both flagged `S_source` partial.
24. Landslide susceptibility from the USGS 2024 release (Mirus and others, doi
    10.5066/P13KAGU3), which gives the share of each 90 m cell that is landslide-prone: over 80
    percent scores 3, over 60 scores 2, over 40 scores 1, standing in for the draft's classes
    5, 4, and 3. Recorded landslides come from the USGS inventory (CGS and NBMG in the basin);
    polygons over 10 km2 are mapping units and are dropped; a point counts within 50 m. The
    precipitation-change term scores 0 at the historical horizon and keeps its weight, so
    landslide exposure tops out at 2.14 until the 2050 and 2080 columns are added.
25. **TRPA decision (Oct. 12, 2026): roads carry no sensitivity.** FL-R, LS-R, WF-R, and DF-R
    are scored on exposure alone, V = E, as AV-R already is. The street network carries none of
    the draft's road sensitivity attributes (pavement condition, paved surface, truck AADT,
    wooden guardrails), and scoring every road on one default added a constant that moved
    roads between classes without telling them apart. Exposure keeps the draft's proportions
    scaled to the full weight. Roads are read alongside criticality, never multiplied by it
    (section 1.3).
26. **TRPA decision (Oct. 12, 2026): wildfire class breaks.** WF-R, WF-AT, and WF-TC are
    classed Low under 2.0, Medium 2.0 to 2.5, High over 2.5 (`scoring.v_breaks_wildfire`);
    every other pair keeps the section 1.2 breaks. Wildfire scores run 1.0 to 3.0, so the
    shared breaks put nearly every road in Medium or High on wildfire alone. `V_class` is the
    highest per-pair class (section 1.4). Effect on roads: High 6,191 to 4,031 segments;
    hotspots (High on top-quarter criticality) 1,323 to 1,060.
27. **TRPA decision (Oct. 12, 2026): wildfire severity sampled by area share.** E2 on WF-R,
    WF-AT, and WF-TC is the highest most-likely severity class covering at least 25 percent of
    the 300 ft buffer (`exposure.wildfire.e2_min_share`), 0 when none reaches it. The severity
    layer is a 30 m raster turned into polygons, and the maximum-touching rule let single
    isolated High cells set E2 = 3 on roads wholly inside Low severity (El Dorado Avenue,
    segment 17899, had six one-cell High patches 30 to 80 m away). E1 keeps the maximum within
    300 ft. Effect on roads: 7,549 of 9,813 segments at E2 = 3 drop to 1; High vulnerability
    4,031 to 3,937; hotspots 1,060 to 1,032.

Consultant review of the results (Oct. 26, 2026): the landslide approach for roads is consistent with the original recommendation. If the state DOTs can supply embankment condition or the locations of stabilization measures, either could serve as an LS-R sensitivity indicator (not required); it would be the first road sensitivity term and would revisit decision 25 for that pair only.
