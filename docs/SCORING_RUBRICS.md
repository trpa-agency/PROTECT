# PROTECT scoring rubrics

**Version 0.3, Oct. 8, 2026.** Draft for consultant review (ICF checkpoint Oct. 9).
**Scope of this version:** the shared framework (section 1) and all 15 pairs: FL-C, LS-C, DF-C
(section 2), FL-B, LS-B, DF-B (section 3), DF-R (section 4), AV-R (section 5), and FL-R, FL-AT,
FL-TC, LS-R, WF-R, WF-AT, and WF-TC (section 6). Sections 2 to 5 were drafted first; section 6
was added Oct. 8 so that every pair samples the same classed hazard surfaces on one scale.
Nothing is scored until the rubric for that pair is agreed.

**What changed in v0.3.** Every indicator value and score now matches the rubric tables in the
consultant's draft Vulnerability Assessment Methodology (Aug. 20, 2026): the half-point score
scale, the draft's class breaks, and the draft's direction for span type, span length, and
drainage area. Version 0.2 had used an integer scale with placeholder breaks. TRPA additions
(workshop fallbacks, the tailwater modifier, the condition and blockage term, missing-data
defaults, sampling rules, and two interpretations where the draft's tables leave a gap) are
marked **TRPA proposal** and are listed in the decision sections. **TRPA is not acquiring a
flood depth model.** The draft's depth-based flood exposure rows (FL-C E1, FL-B E2) are listed
for the record but do not apply; flood exposure is scored from FEMA flood zones and stream
crossings (decision 19).

Source of record for the equation, weights, and indicators: the consultant's draft Vulnerability
Assessment Methodology (Aug. 20, 2026, internal draft, not committed). Pair definitions mirror
`Hazard_Asset_Pairs.md` (v0.8). The interactive mirror of this file is
`html/scoring-rubrics.html`.

---

## 1. Shared framework

### 1.1 Equation and scale

Every indicator is scored 0 to 3 and carries a weight. The draft's tables score most indicators
in half-point steps (0, 0.5, 1, 1.5, 2, 2.5, 3); a few score whole points only. Indicator
weights sum to 1.0 within a pair, so the pair score is on the same 0 to 3 scale:

    V_<pair> = sum over indicators of (weight x score)

The exposure weight wE is the sum of the exposure indicator weights and wS the sum of the
sensitivity indicator weights, so the draft's "Vulnerability = (Exposure Score x wE) +
(Sensitivity Score x wS)" is the same thing written per component. `E_<pair>` and `S_<pair>` are
written as the weight-normalized component scores (each 0 to 3) so the tool can show them
separately. The draft writes weights as percentages; this document writes them as decimals.

Several of the draft's sensitivity rubrics have a floor of 1 rather than 0 (bridge condition,
pavement condition, culvert condition, paved surface, scour codes 5 to 9). A sensitivity
component is therefore rarely 0. This is the draft's design and is kept.

Per-pair weights, from the draft:

| Hazard | Roads | Bridges and large culverts | Small culverts | Active transport | Transit centers |
|---|---|---|---|---|---|
| Flooding | E 0.7 / S 0.3 | E 0.3 / S 0.7 | E 0.3 / S 0.7 | E 0.7 / S 0.3 | E 1.0 |
| Landslide | E 0.7 / S 0.3 | E 0.7 / S 0.3 | E 0.7 / S 0.3 | not scored | not scored |
| Wildfire | E 0.7 / S 0.3 | not scored | not scored | E 1.0 | E 1.0 |
| Debris flow | E 0.7 / S 0.3 | E 0.7 / S 0.3 | E 0.7 / S 0.3 | not scored | not scored |
| Avalanche | E 1.0 | not scored | not scored | not scored | not scored |

### 1.2 Buckets

`V_<pair>` is kept to two decimals and bucketed for the map and posters. **TRPA proposal:**
Low under 1.0, Medium 1.0 to under 2.0, High 2.0 and above. Breaks live in `config.yaml`
(`scoring.v_breaks`) so one change moves every page and layout.

### 1.3 Criticality

Criticality is component 1 of the assessment, scored separately, and is not a multiplier in
the vulnerability score. Road segments carry a 0 to 3 criticality class (`C_class`); bridges and
culverts inherit it through `parent_segment_id`. Priority for scenario selection and the TRIP is
read on two axes, vulnerability class by criticality class, and the hotspot lists rank assets by
`V` within the High criticality class first.

### 1.4 Aggregation across pairs

One asset appears in several pairs (a culvert carries FL-C, LS-C, DF-C). **TRPA proposal:** the
asset-level rating is the maximum pair score, written as `V_max` with `V_max_pair` recording
which hazard set it. Summing would double-count one physical failure at one location.

### 1.5 Horizons

The draft scores historical, mid-century (2050), and late-century (2080). The Nov. 9 workshop
uses the historical horizon only. Field names carry a horizon suffix from the start
(`E_FLC_hist`, `E_FLC_2050`, `E_FLC_2080`) so December adds columns, not a schema change.
Sensitivity does not vary by horizon. The FEMA flood zones have no future horizon; the flood
pairs carry the future through the culvert loading ratio, whose design flows (section 2.4)
take their 2050 and 2080 factors from the climate pipeline's DDF extract. A precipitation
change modifier on FEMA exposure for the 2050 and 2080 columns is a December question
(decision 19).

### 1.6 Missing data

The draft leaves most defaults TBD. Every indicator below carries a default (stated in its
rubric row); where the draft states one (pavement condition fair, surface paved, bridge
condition none scores 1, scour other scores 1) that value is used, and the rest are **TRPA
proposals** listed in section 2.8. An asset scored on any default carries `S_source` (or
`E_source`) = `partial`; an asset with every sensitivity indicator defaulted carries `default`.
Defaults are shown on the map and in popups as such.

### 1.7 Sampling rule

Line assets take the length-weighted maximum of the hazard surface along the segment. Point
assets (bridges, transit centers) take the maximum within a 25 m buffer. **Small culverts are the
exception** (section 2.3): hazard surfaces that describe what arrives at the crossing (flood,
debris flow, landslide) are sampled over the culvert's contributing watershed, with the 25 m
buffer as the fallback where no watershed could be delineated.

---

## 2. Culverts (small culverts): FL-C, LS-C, DF-C

### 2.1 Asset set

The draft splits culverts into large and small. **Large culverts** are the National Bridge
Inventory structures coded as culverts (NBI item 43B = 19, spans over 20 ft). There are five in
the basin, carried in the `Bridges` layer with `is_culvert_type` = 1, and they score with the
bridge rubrics. **Small culverts** are everything in the `Culverts` layer that passes the
following filter, and they are the subject of this section.

| Rule | Effect |
|---|---|
| `feature_type` = `culvert` | Scores. Stormwater pipes, inlets, and basins are inventory only |
| Road-crossing rule applied to El Dorado County and Washoe County pipes | El Dorado delivered no feature type, so all 2,615 of its pipes are typed stormwater pipe today and its roads would carry zero culverts. Apply the rule already used for NDOT: a pipe that crosses a `Streets_Network_Tahoe` centerline is a culvert unless both ends are manholes |
| Within 25 m of an NBI culvert-type structure | Excluded from scoring; `large_culvert_id` points at the bridge record |
| No `parent_segment_id` (not within 50 m of a road segment) | Inventory only; no criticality, no rating. These are mostly provisional legacy points on forest roads |
| Jurisdiction = NDOT | Scored in the analysis geodatabase only. Nothing NDOT-derived at the asset level goes to a page, a public service, or a printed map without NDOT review; segment-level aggregates with NDOT attribution are allowed |

Expected scored set after the crossing rule: about 5,000 culverts including NDOT.

### 2.2 Culvert profile (descriptive, hazard-independent)

The profile describes size and condition in the terms the assessment uses. It is written to the
`Culverts` feature class, shown in the tool popup and table, and is the input to every
sensitivity indicator below. It is not itself a score.

| Field | Definition | Source |
|---|---|---|
| `span_in`, `rise_in` | Cleaned opening dimensions. The -9999 sentinel and spans over 144 in. on circular pipes are nulled | Jurisdiction deliveries |
| `d_eq_in` | Equivalent diameter: `span_in` for circular pipes; `sqrt(4 x span x rise / pi)` for boxes, arches, ellipses | Derived |
| `size_class` | The draft's opening classes on `d_eq_in`: under 2 ft, 2 to under 3, 3 to under 5, 5 to under 7, 7 ft and over | Derived |
| `material_class` | Corrodible metal (CMP, CSP, squash, annular, corrugated metal), plastic (HDPE, PVC), concrete (RCP, concrete, box), unknown. El Dorado's undecoded `code N` values map to unknown until the county supplies the domain | `material` |
| `contrib_area_ac` | Contributing drainage area at the crossing | Flow accumulation on the TRPA hydro-enforced bare-earth lidar DEM (`SDE.DEM_BareEarth_LiDAR_2010`, 2 m, EPSG 26910); pour point is the maximum-accumulation cell within 20 m of the culvert, on the upstream side of the road |
| `basin_slope_pct` | Mean slope of the contributing watershed | Same DEM, zonal mean |
| `basin_landcover` | Majority NLCD class in the watershed, grouped to the draft's four classes: water and snow (NLCD 11, 12), urban (21 to 24), trees (41, 42, 43, 90), shrubs (all other classes) | NLCD 2021 |
| `q_event_cfs` (hist, 2050, 2080) | Event peak flow at the crossing, 100-yr headline, 25-yr carried as a second column | Section 2.4 |
| `q_cap_cfs` | Hydraulic capacity with headwater at the crown | Section 2.4 |
| `load_ratio` | `q_event_cfs / q_cap_cfs` (the draft's Qevent/Qdesign) | Derived |
| `cond_class` | Harmonized latest-inspection condition on the draft's scale: 1 good, 2 fair, 3 poor | Section 2.5 |
| `cond_date`, `cond_stale` | Latest inspection date; stale when before 2015 | `CulvertCondition` |
| `blockage_pct` | Latest recorded blockage | Washoe `perc_full`, NDOT `PercentBlockage`, legacy text |
| `tailwater_flag` | Outlet within 50 m of the shoreline and below 6,230 ft (the legal maximum lake level is 6,229.1 ft) | DEM, high-water shoreline layer |
| `profile_completeness` | `full`, `partial`, `default`: whether size, hydrology, and condition were observed or defaulted | Derived |

**Why size and condition are framed this way.** Size matters only relative to demand: an
18-inch pipe under a five-acre swale is adequate and the same pipe under a 200-acre burned
watershed is not, so absolute size is a descriptor and the loading ratio is the indicator.
Condition enters three ways that line up with the three pairs: structural condition (crushing,
corrosion, joint separation) reduces capacity and risks collapse under the road; blockage reduces
the effective opening and is the debris-flow failure mode; outlet scour and fill erosion are the
embankment-loss mode shared with landslide. Age is not an indicator because install year exists
only for El Dorado County and the city; `material_class` stands in for durability.

### 2.3 Indicator rubrics

Weights and scores are the draft's unless marked **TRPA proposal**. Each indicator lists its
values and scores as the draft's tables do; the pair score is the weighted sum.

**FL-C, flooding x small culverts** (E 0.3 / S 0.7)

The draft gives two sensitivity options. Option 1 (StreamStats) estimates debris potential from
mean basin slope and majority landcover and takes Qdesign from asset data. Option 2 (CULVERT
tool) takes debris potential from the tool's WDBFM score and Qdesign from the tool. TRPA computes
the option 1 matrix locally from its own watershed delineation and estimates Qcap with HDS-5
(decisions 2 and 6); the option 2 scale is listed for reference.

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 | **TRPA proposal** (decision 19): FEMA flood zone and stream crossing, in place of the draft's flood depth indicator, because no flood depth model is being acquired | 0.30 | 1 percent zone (A, AE) | 3 | 0 | Maximum within 25 m of the crossing on the road |
| | | | 0.2 percent zone (X500) or on a mapped TRPA stream | 2 | | |
| | | | on an NHD flowline outside a zone | 1 | | |
| | | | no zone, no flowline | 0 | | |
| E1 (draft, not applicable) | 100-yr flood depth over the road from a flood depth model, maximum of fluvial and pluvial. Listed for the record; no such dataset is being acquired | 0.30 | over 20 ft | 3 | | |
| | | | over 12 to 20 ft | 2.5 | | |
| | | | over 6 to 12 ft | 2 | | |
| | | | over 3 to 6 ft | 1.5 | | |
| | | | over 2 to 3 ft | 1 | | |
| | | | over 0 to 2 ft | 0.5 | | |
| | | | none | 0 | | |
| E1 modifier | **TRPA proposal:** tailwater. Add 1 (maximum 3) when `tailwater_flag` is set, because high lake stage reduces outlet capacity independent of rainfall | in E1 | | | no change | |
| S1 | Debris potential of the basin: mean basin slope by majority landcover (draft option 1 matrix). Rows are slope, columns are landcover | 0.35 (draft); 0.25 under the S3 proposal | 0 to 8 percent: water and snow 0, urban 0.5, shrubs 1, trees 1 | | 1 when no watershed, `S_source` partial | Watershed |
| | | | over 8 to 16 percent: water and snow 0, urban 1, shrubs 2.5, trees 2.5 | | | |
| | | | over 16 percent: water and snow 0, urban 2.5, shrubs 2.5, trees 3 | | | |
| S1 (option 2, not used) | CULVERT tool WDBFM debris-flow score, 0 to 5 | 0.35 | 5 | 3 | | |
| | | | 4 | 2.5 | | |
| | | | 3 | 2 | | |
| | | | 2 | 1.5 | | |
| | | | 1 | 1 | | |
| | | | 0 | 0.5 | | |
| S2 | 100-yr capacity loading ratio, `load_ratio` = Qevent / Qdesign | 0.35 (draft); 0.30 under the S3 proposal | 4 and over | 3 | 1 when `span_in` is null, `S_source` partial | Per crossing; multi-barrel crossings grouped (section 2.4) |
| | | | 3 to under 4 | 2.5 | | |
| | | | 2.5 to under 3 | 2 | | |
| | | | 2 to under 2.5 | 1.5 | | |
| | | | 1.5 to under 2 | 1 | | |
| | | | 1 to under 1.5 | 0.5 | | |
| | | | under 1 | 0 | | |
| S3 | **TRPA proposal:** condition and blockage, the maximum of `cond_class` (good 1, fair 2, poor 3, the draft's condition scale) and the blockage class | 0.15 | poor, or blockage 50 percent and over | 3 | 2 (fair), `S_source` partial | Latest inspection |
| | | | fair, or blockage 25 to under 50 percent | 2 | | |
| | | | good, blockage under 25 percent | 1 | | |

Note on S3. The draft has no condition term for small culverts. TRPA proposes re-splitting the
0.7 sensitivity weight as S1 0.25, S2 0.30, S3 0.15. If the consultant declines, the draft's S1
0.35 and S2 0.35 stand and `cond_class` stays a profile field shown in the popup.

**LS-C, landslide x small culverts** (E 0.7 / S 0.3)

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 | USGS Landslide Susceptibility Index class, or a recorded landslide (California Landslides Database) | 0.50 | class 5 (very high), or any recorded landslide | 3 | 0 | **TRPA proposal:** maximum over the watershed; 25 m buffer where none |
| | | | class 4 (high) | 2 | | |
| | | | class 3 (moderate) | 1 | | |
| | | | class 1 or 2 (very low or low) | 0 | | |
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

Exposure is the shared debris-flow surface of section 4.2 (option 1, option 2, or the workshop
proxy), sampled as the watershed maximum. Sensitivity in the draft is debris potential at 0.30
(the option 1 matrix, or the option 2 WDBFM scale, both as in FL-C S1).

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 to E3 | Section 4.2, option 1, option 2, or proxy | 0.70 total | | | | Watershed maximum; pour point for Wildcat likelihood |
| S1 (draft) | Debris potential of the basin, the FL-C S1 matrix | 0.30 | as FL-C S1 | | 1, `S_source` partial | Watershed |
| S1 and S2 (**TRPA proposal**, decision 7) | Under option 1, basin slope already sits in exposure, so debris potential in sensitivity counts it twice. Proposal: S1 opening size (the LS-C S1 scale; small pipes plug regardless of ratio) at 0.15 and S2 condition and blockage (the FL-C S3 scale) at 0.15. Under option 2 or the proxy the draft's S1 stands | 0.30 total | | | 2 each, `S_source` partial | Per asset; latest inspection |

### 2.4 Hydrology and hydraulics for the loading ratio

The draft's Qdesign is missing for nearly every culvert, so capacity is estimated from geometry.
Parameters live in `config.yaml` (`hydraulics:` block, to be added with the profile script).

- **Watershed.** Flow direction and accumulation on the TRPA hydro-enforced bare-earth lidar
  DEM (`SDE.DEM_BareEarth_LiDAR_2010`, 2 m, EPSG 26910, about 600 million cells basin-wide).
  The hydro-enforcement breaches road fills along the mapped drainage lines, but not at every
  crossing: the Oct. 8 QA found sinks behind unbreached fills that turn into two-cell flow
  loops, splitting accumulation and ending the flow path at the road, and once those sinks
  were filled the creeks spilled along roadside ditches and 292 pipes of 24 in. or less
  inherited basins over 100 acres. The DEM is therefore conditioned with the VA culvert
  inventory itself: a 40 m breach line through every typed culvert, perpendicular to its
  parent road segment, lowered to the lower of its two ends minus 0.3 m
  (`profile.breach`), except within 10 m of the lidar-derived streams and lakes, whose
  crossings the enforcement already carries (a breach floor set from a creek bed would pull
  the creek into the ditch pipe); then sinks shallower than 3 m (`profile.fill_z_limit_m`)
  are filled;
  deeper sinks (lakes, real basins) are kept. The delineation runs at the native 2 m on the
  server machine rather than a resampled surface, because aggregating to 10 m would average
  away the breach channels. Pour point is the maximum-accumulation cell within 4 m of the
  culvert (`profile.pour_snap_m`): the breach runs through the culvert's own cell, so a
  wider search only captures neighboring creeks. Watershed polygons are kept as a feature
  class; they also serve the watershed sampling in section 2.3. Culverts within 10 m of each
  other on the same segment are one crossing: one watershed, capacities summed. The DEM is 2010
  lidar; crossings rebuilt since then are flagged where `install_year` is 2011 or later.
- **Event flow, Qevent.** Rational method, Q = C i A, for basins under 1 sq mi, with C by
  majority landcover (forest 0.35, shrub 0.40, developed 0.60, barren 0.50) and i the Atlas 14
  intensity at the basin's time of concentration (Kirpich), 100-yr headline and 25-yr carried.
  Basins of 1 sq mi and over (about 230 crossings) use the USGS regional regression
  equations for their state, Q_T = a A^b P^c with A in sq mi and P the basin mean annual
  precipitation in inches from the PRISM 1991-2020 normals (800 m): California, Lahontan
  region of Gotvald and others (2012, SIR 2012-5113, table 5), Q100 = 0.713 A^0.731 P^1.56
  and Q25 = 0.394 A^0.733 P^1.58, average standard error of prediction 76 to 77 percent;
  Nevada, region 1 of Thomas and others (1997, WSP 2433; USGS Fact Sheet 123-98, table 1),
  Q100 = 6.78 A^0.750 P^0.668 and Q25 = 3.08 A^0.768 P^0.811, standard error 46 percent.
  The two regionalizations differ: on the same basin region 1 gives roughly one third of the
  Lahontan value, so `q_region` records which applied and the run log prints the ratio;
  `regression.nv_uses` can apply the Lahontan equation basin-wide instead (**TRPA decision
  pending**). 2050 and 2080 flows apply the climate pipeline's DDF change factors to i. The
  draft takes Qevent from the StreamStats API; the local computation replaces it so that
  NDOT crossings are not sent to a third-party service.
- **Capacity, Qcap.** FHWA HDS-5 inlet-control submerged-inlet equation solved for Q at a
  headwater criterion of HW/D = 1.0 (`profile.hw_d`), coefficients by shape, material, and
  inlet type (`inlet_type` where delivered; projecting end default), culvert slope assumed
  (`profile.culvert_slope`). At HW/D = 1.0 the submerged form sits just below its strict
  validity range and underestimates capacity by roughly 10 to 20 percent against the HDS-5
  nomographs, which is conservative for a screen; `q_full_cfs` (Manning full flow) is carried
  as the cross-check. Barrels at one crossing are summed (`q_cap_crossing_cfs`) before the
  ratio. A culvert that overtops its headwater at the design flow has `load_ratio` over 1.0.
  Implemented in `scripts/culvert_profile.py` (stage `attributes`).
- **Known limits.** Rational method is a screening estimate, slopes and roughness are assumed,
  and culvert inverts are not surveyed. The ratio is for ranking, not design. State this on the
  method slide. The future-horizon factor scales rainfall intensity only; the literature review
  cites a shift of the runoff peak toward January under warming, which means rain-on-snow
  winter peaks that a rainfall change factor does not capture. Treat 2050 and 2080 ratios as a
  lower bound for mid-elevation basins and say so.

### 2.5 Condition harmonization

`cond_class` is on the draft's condition scale, 1 (good) to 3 (poor), from the latest inspection
per culvert. Undated rows sort oldest. Scheme semantics are recorded in `condition_scheme`; two
of them are unconfirmed and are on the jurisdiction question list.

| Source | Rule | Caveat |
|---|---|---|
| Placer County 1 to 5 | 5 and 4 to good (1), 3 to fair (2), 1 and 2 to poor (3) | Direction unconfirmed; the distribution (mostly 4 and 5) supports 5 = good |
| Douglas County maintenance 1 to 5 (1 = replacement) | Same mapping | 4 culverts |
| NDOT overall Good/Fair/Poor plus blockage | G 1, F 2, P 3; blockage under 25 percent 1, 25 to under 50 percent 2, 50 percent and over 3; take the maximum | Overall rating is blank on 94 percent of visits, so blockage carries most of the signal |
| TRPA legacy text | First token Good/Fair/Poor to 1, 2, 3; Moderate to 2 | Provisional, often undated |
| Washoe County | Structural subscore is 2 on 793 of 806 rows and is treated as no signal; `perc_full` feeds `blockage_pct`; `cond_class` is partial | Code semantics unconfirmed |
| Caltrans, City of South Lake Tahoe, El Dorado County | No rating delivered. `cond_class` default 2 (fair), `S_source` partial; `cond_stale` set where the last Caltrans inspection predates 2015 | Caltrans has dates only |

Condition will exist for roughly a third of scored culverts. Say so on the slide.

### 2.6 Criticality and output fields

`C_class` is inherited from `parent_segment_id` on `Streets_Network_Tahoe`. Fields written to
the `Culverts` feature class, in addition to the profile:

| Field | Content |
|---|---|
| `E_FLC_hist`, `S_FLC`, `V_FLC_hist` | Component and pair scores, two decimals; `_2050` and `_2080` added in December |
| `E_LSC_hist`, `S_LSC`, `V_LSC_hist` | Same |
| `E_DFC_hist`, `S_DFC`, `V_DFC_hist` | Same; `DF_option` records 1, 2, or `proxy` |
| `E_source`, `S_source` | `full`, `partial`, `default` per section 1.6 |
| `C_class` | Inherited criticality 0 to 3 |
| `V_max`, `V_max_pair`, `V_class` | Section 1.4 and 1.2 |
| `large_culvert_id`, `scored` | Section 2.1 |

Each delivery to the consultant is the feature class plus a CSV export and a one-page method
note.

### 2.7 Validation and QA

- Distribution checks on `contrib_area_ac` and `load_ratio` by jurisdiction before scoring;
  spot-check 20 watersheds by eye against the DEM hillshade.
- Known-failure check: the July 14 event hindcast on the storm events page and any crossing the
  state DOTs or counties can name as a repeat overtopping or plugging site should land in the
  High class for FL-C or DF-C. A screening with no known failures in its top class is not
  credible at the workshop. The Task 3.1 literature review supplies three documented sites to
  start with: the Aug. 2025 Incline Village flooding caused by a blocked culvert on Northwood
  Blvd (a blockage failure, FL-C S3); the June 2026 Washoe County flash flood, 2 to 3 in. in
  under an hour with over 4 million dollars in road repairs (a short-duration pluvial event;
  crossings in that area should score high on the loading ratio at the 1-hr intensity); and the
  SR 89 culvert at Meeks Creek, listed as a high priority in the Caltrans District 3 Adaptation
  Priorities report. Meeks Creek is one of the five NBI culvert-type structures and scores under
  the bridge rubric, so it is the cross-check between the two culvert paths.
- Prior-assessment counts: the City of South Lake Tahoe hazard mitigation plan counts seven
  transportation assets in the 1 percent floodplain and two in the 0.2 percent. Compare with the
  FEMA fallback counts for city culverts and roads before shipping FL-C.
- Sensitivity to the design event: report how many culverts change class between the 25-yr and
  100-yr ratio.
- Row counts reconcile across the profile, the scored set, and the published layer, with the
  NDOT rows accounted for separately.

### 2.8 Decisions requested from the consultant

1. Condition and blockage as a third FL-C sensitivity term (S3) with weights S1 0.25, S2 0.30,
   S3 0.15, versus the draft's 0.35 / 0.35 with no condition term. The one culvert failure in
   the literature review's event catalog (Incline Village, Aug. 2025) was a blockage, which
   neither draft term captures.
2. Debris potential computed locally with the option 1 matrix for every culvert, rather than
   the CULVERT tool score (option 2). NDOT data cannot be uploaded to a third-party tool, so
   option 2 would score Nevada highways differently from everything else.
3. Watershed sampling for culvert exposure (section 1.7) instead of a point buffer.
4. Tailwater modifier on FL-C E1 for shoreline outlets.
5. 100-yr as the loading-ratio event, with 25-yr carried for comparison (the draft names the
   100-yr as likely appropriate).
6. Capacity from HDS-5 inlet control as the default Qdesign where asset records have none.
7. Under debris-flow option 1, replace the sensitivity debris-potential term with opening size
   and condition to avoid counting basin slope twice.
8. Missing-data defaults as stated per row in section 2.3.
9. Bucket breaks (section 1.2) and the max-pair aggregation rule (section 1.4).
10. Whether unsnapped forest-road culverts stay out of the rating.
19. Flood exposure without a depth model. TRPA is not acquiring a commercial flood depth
    model, so the draft's depth-based indicators (FL-C E1, FL-B E2, and the depth half of the
    road, active transport, and transit center rubrics) have no dataset. TRPA scores flood
    exposure from FEMA flood zones and stream crossings on the values in FL-C E1, with the
    culvert loading ratio carrying the hydraulic signal. Two consequences for the consultant to
    confirm: the flood pairs have no exposure horizon beyond historical unless a precipitation
    change modifier is applied to the FEMA term in December, and the public alternatives for
    depth (USGS StreamStats peak flows, HEC-RAS at selected crossings) stay available if a
    depth indicator is still wanted.
20. Two gaps in the draft's tables, scored by TRPA interpretation until confirmed: culvert
    openings over 8 ft score 1 (the draft's lowest band), and an avalanche record with no slope
    over 25 degrees within 1,000 ft scores 1 (section 5.2).

---

## 3. Bridges and large culverts: FL-B, LS-B, DF-B

### 3.1 Asset set

The `Bridges` layer holds the 40 National Bridge Inventory structures inside the TRPA boundary
(California and Nevada), built by `scripts/build_bridges.py` from the basin clip. Five are NBI
culvert-type structures (item 43B = 19) and score here, not in section 2. Every structure
inherits `C_class` from `parent_segment_id`. Structures not over a waterway (scour item 113 = N,
such as grade separations) stay in the set: their flood and debris-flow sensitivity indicators
that depend on water score at the draft's lowest band, and the exposure indicators still apply.

NBI condition items are integers 0 (failed) to 9 (excellent) with N for not applicable. The
draft's condition breaks are 0 to 2 (3), 3 to 4 (2.5), 5 (2), 6 (1.5), and 7 to 9, N, or none
(1); the draft writes the second band as "2 to 4", read here as 3 to 4 so the bands do not
overlap.

Two NBI items the draft uses, item 45 (number of spans in the main unit) and item 48 (length
of the maximum span), are carried as `main_spans` and `max_span_m`; `build_bridges.py` was
re-run with `--overwrite` on Oct. 8 to add them to the layer. Item 48 is in meters in the
layer; the draft's breaks are in feet and are converted at scoring time.

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
| E2 | **TRPA proposal** (decision 19): FEMA flood zone at the structure, the FL-C E1 values, in place of the draft's change-in-depth indicator, because no flood depth model is being acquired | 0.10 | as FL-C E1 | | 0 | Maximum within 25 m |
| E2 (draft, not applicable) | Change in 100-yr flood depth at the structure relative to historical from a flood depth model. Listed for the record; no such dataset is being acquired | 0.10 | over 5 ft | 3 | | |
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

The draft's E1 is an inventory attribute rather than a hazard surface, which is why the pair is
exposure-light. Item 71 encodes observed overtopping frequency, so it is in effect a recorded
exposure history.

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

The draft scores longer spans higher. **TRPA proposal** (decision 12): the direction should be
reversed, because a longer maximum span means more clearance and fewer in-channel piers. The
draft's direction is used until the consultant decides.

**DF-B, debris flow x bridges** (E 0.7 / S 0.3)

Exposure is the shared debris-flow surface of section 4.2, sampled over the contributing
watershed of the crossing where the structure is over a waterway and within 25 m otherwise. The
five culvert-type structures and the stream bridges get a watershed from the same delineation as
the small culverts. Sensitivity is the LS-B set: span type 0.10, bridge condition 0.10, span
length 0.10, with the same values and the same direction question on span length.

### 3.3 Output fields

`E_FLB_hist`, `S_FLB`, `V_FLB_hist`, and the LS-B and DF-B equivalents; `C_class`; `V_max`,
`V_max_pair`, `V_class`; `E_source`, `S_source`; `DF_option`. Horizon columns are added in
December as for culverts.

### 3.4 Validation

- The SR 89 culvert at Meeks Creek (structure 25 0019; culvert condition 5, scour code 4) is the
  Caltrans Adaptation Priorities cross-check and should land High or Medium on FL-B.
- The Placer County vulnerability assessment flags I-80 bridges for flooding; none are in the
  basin, so this is a method check against their rubric rather than a result check.
- With 40 structures, review every row by hand against the NBI record before delivery.

### 3.5 Decisions requested from the consultant

11. Whether "NBI 45 span type" in the draft means item 45 (number of main spans) or item 43
    (structure type). The rubric assumes item 45.
12. The direction of the span-length indicator. The draft scores longer spans higher; TRPA
    proposes the reverse. The draft's direction is used until decided.
13. Resolved by the draft's table: scour codes 5 to 9, U, and blanks score 1, so an unevaluated
    foundation is not read as safe. No decision needed.
14. Resolved by decision 19: with no depth model, E2 is the FEMA zone at the structure under
    every horizon. No separate decision needed.

---

## 4. Debris flow x roads: DF-R

### 4.1 Asset set and sampling

`Streets_Network_Tahoe` segments, scored length-weighted maximum along the segment on the hazard
rasters below. The segment set, IDs, and `C_class` come from the criticality assessment; the
debris-flow surface is built once so that DF-R, DF-B, and DF-C share one surface and one set of
class breaks.

### 4.2 Indicator rubrics (E 0.7 / S 0.3)

Exposure is option 1 or option 2, undecided in the draft. Both are built as rasters so that
roads (length-weighted maximum), bridges (25 m or watershed), and culverts (watershed) sample the
same surfaces. The draft's tables apply to roads, bridges, and culverts alike.

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
| E1 (proxy) | **TRPA proposal**, workshop fallback: the proxy raster (WRF 1-hr intensity against the Tahoe threshold, slope and contributing area from the DEM, burn severity proxy), classed 0 to 3 in whole points | 0.70 | class 3 | 3 | 0 | Section 4.3 |
| | | | class 2 | 2 | | |
| | | | class 1 | 1 | | |
| | | | class 0 | 0 | | |
| S1 | Pavement condition | 0.15 | poor | 3 | 2 (fair, per the draft), `S_source` partial | Jurisdiction outreach; unavailable today |
| | | | fair | 2 | | |
| | | | good or none | 1 | | |
| S2 | Paved versus unpaved | 0.15 | unpaved | 3 | 1 (paved, per the draft) | Street network surface attribute where present |
| | | | paved | 1 | | |

Workshop fallback (either option not ready by Oct. 16): the proxy raster, same sampling, with
`DF_option` = `proxy` and the method note stating what replaces it.

### 4.3 Notes

- Option 1 and the proxy both reuse the flow-accumulation and slope rasters from the culvert
  delineation; the burn severity surface is the only new input.
- The draft's drainage-area direction (smaller area scores higher) describes the concentrated,
  rapid runoff of small steep basins. Road cells take the contributing area of the maximum
  accumulation cell they intersect, so a road crossing a large river scores low on this term
  and a road below a small burned ravine scores high, which is the intended behavior.
- Roads are hit by debris flows at the crossing (the culvert or bridge) and along the toe of
  slope. Length-weighted maximum catches both; a segment with a High culvert and a Low roadway
  score will read High on the segment, which is the intended behavior.
- Pavement condition is the open sensitivity gap for every road pair. The default of fair with
  `S_source` partial makes the gap visible on the map rather than hiding it.

### 4.4 Decisions requested from the consultant

15. Option 1 or option 2 for debris-flow exposure, and whether the proxy is acceptable for the
    Nov. 9 workshop if neither is ready by Oct. 16.
16. Resolved: the draft's drainage-area breaks and direction are adopted. No decision needed.

---

## 5. Avalanche x roads: AV-R

### 5.1 Asset set and sampling

`Streets_Network_Tahoe` segments, scored length-weighted maximum. Exposure only (E 1.0); the
draft sets no sensitivity for this pair. Current terrain conditions only, no climate horizon. The
initial corridor list (US-50, SR-89, SR-28, SR-207, SR-431) is the sanity check, not the scope:
every segment is scored, and a High score off those corridors is a finding to review with the
state DOTs at the workshop.

### 5.2 Indicator rubric

The draft scores one combined lookup of the historical avalanche record within 1,000 ft and the
dominant slope angle within 1,000 ft (its table header shows two 35 percent weights, but the
equation is Exposure x 1.0 and one score is read per row, so the lookup is used as a single
indicator at 1.00). The draft does not define dominant slope; the definition below is a
**TRPA proposal** (decision 17).

- **Dominant slope** is the slope class covering the largest area of terrain above the road
  (uphill side only) within 1,000 ft of the segment, from the hydro-enforced lidar DEM
  aggregated to 10 m. Slopes below 25 degrees rarely release and slopes above 50 degrees shed
  snow before it accumulates, which is why the draft's bands step down on both sides of 35 to
  45 degrees.
- **Record** is any of: a Sierra Avalanche Center accident-map point, a National Avalanche
  Accident Database entry, and (**TRPA proposal**, decision 18) a mapped TRPA `Avalanche_Zones`
  polygon or a documented closure in the Task 3.1 event catalog (SR 431 Jan. 2017 and Mar.
  2023; US 50 Echo Summit Apr. 2019), within 1,000 ft of the segment.

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

- The five corridors should carry nearly all High segments; list any High segment off those
  corridors for the DOTs.
- The literature review notes avalanches rarely damage infrastructure, which is why the pair is
  operational and why AV-B left the VA. The score describes closure likelihood, not damage.

### 5.4 Decisions requested from the consultant

17. The definition of dominant slope (largest-area class on the uphill side within 1,000 ft).
    The classes and scores are the draft's.
18. Whether the TRPA avalanche zone layer and documented closures count as records alongside
    the two accident databases.

---

## 6. Roads, active transport, and transit centers: FL-R, FL-AT, FL-TC, LS-R, WF-R, WF-AT, WF-TC

### 6.1 Asset sets and sampling

Roads are `Streets_Network_Tahoe` segments, scored length-weighted maximum along the segment.
Active transport is the Class 1 and Class 2 trail inventory (paved or unpaved, slope from the
DTM), scored length-weighted maximum. Transit centers are point assets, scored as the maximum
within a 25 m buffer (300 ft for wildfire, as the draft specifies). Segment IDs, the active
transport and transit center inventories, and `C_class` come from the criticality assessment.

### 6.2 Flooding: FL-R, FL-AT, FL-TC

The draft scores flood exposure for these assets as two indicators at 0.35 each: floodplain
extent (the lowest intersecting floodplain, 10-yr scoring 3 down to 1,000-yr scoring 0.5) and
the 100-yr flood depth. Neither dataset is being acquired as the draft assumed: there is no flood
depth model, and FEMA maps only the 1 percent (100-yr) and 0.2 percent (500-yr) floodplains, on
which the draft's extent scale would score 2 and 1 with the top two bands unused. **TRPA
proposal** (decisions 19 and 21): one exposure indicator, the FEMA flood zone and stream
crossing on the FL-C E1 values, at the full exposure weight, so every flood pair samples the
same classed surface.

**FL-R, flooding x roads** (E 0.7 / S 0.3)

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 | **TRPA proposal:** FEMA flood zone and stream crossing, the FL-C E1 values, in place of the draft's extent and depth indicators | 0.70 | as FL-C E1 | | 0 | Length-weighted maximum along the segment |
| E1 (draft, not applicable) | Floodplain extent, lowest intersecting floodplain: 10-yr 3, 50-yr 2.5, 100-yr 2, 200-yr 1.5, 500-yr 1, 1,000-yr 0.5, none 0; and 100-yr flood depth on the FL-C depth scale (over 20 ft scores 3) | 0.35 each | | | | |
| S1 | Pavement condition | 0.10 | poor | 3 | 2 (fair, per the draft), `S_source` partial | Jurisdiction outreach; unavailable today |
| | | | fair | 2 | | |
| | | | good or none | 1 | | |
| S2 | Paved versus unpaved | 0.10 | unpaved | 3 | 1 (paved, per the draft) | Street network surface attribute where present |
| | | | paved | 1 | | |
| S3 | Truck AADT | 0.10 | over 1,000 | 3 | **TRPA proposal:** 1 when unknown (the draft says TBD), `S_source` partial | Street network traffic attribute where present |
| | | | over 500 to 1,000 | 2.5 | | |
| | | | over 250 to 500 | 2 | | |
| | | | over 100 to 250 | 1.5 | | |
| | | | under 100 | 1 | | |

**FL-AT, flooding x active transport** (E 0.7 / S 0.3)

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 | **TRPA proposal:** FEMA flood zone and stream crossing, the FL-C E1 values | 0.70 | as FL-C E1 | | 0 | Length-weighted maximum along the trail |
| S1 | Paved versus unpaved trail | 0.15 | unpaved | 3 | 3 (unpaved, per the draft) | Trail inventory |
| | | | paved | 1 | | |
| S2 | Trail slope | 0.15 | 15 percent and over | 3 | **TRPA proposal:** 1 when unknown (the draft says TBD), `S_source` partial | Mean slope from the DTM |
| | | | 10 to under 15 percent | 2 | | |
| | | | 5 to under 10 percent | 1 | | |
| | | | under 5 percent | 0 | | |

**FL-TC, flooding x transit centers** (E 1.0)

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 | **TRPA proposal:** FEMA flood zone and stream crossing, the FL-C E1 values, in place of the draft's extent and depth indicators (the draft's lower depth thresholds for transit centers, 3 at over 8 ft, have no dataset) | 1.00 | as FL-C E1 | | 0 | Maximum within 25 m |

### 6.3 Landslide: LS-R

**LS-R, landslide x roads** (E 0.7 / S 0.3)

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 | USGS Landslide Susceptibility Index class, or a recorded landslide | 0.50 | as LS-C E1 | | 0 | Length-weighted maximum along the segment |
| E2 | Cal-Adapt annual precipitation change versus historical | 0.20 | as LS-C E2 | | 0; historical horizon scores 0 | Segment mean |
| S1 | Pavement condition. The draft prefers embankment condition or stabilization measures where available; pavement condition is the stand-in | 0.30 | poor | 3 | 2 (fair, per the draft), `S_source` partial | Jurisdiction outreach; unavailable today |
| | | | fair | 2 | | |
| | | | good or none | 1 | | |

### 6.4 Wildfire: WF-R, WF-AT, WF-TC

The draft scores wildfire exposure as annual burn probability and flame length, the maximum
within a 300 ft buffer, current conditions only, and names the contracted fire-behavior package
as the source. TRPA holds wildfire data that serves both indicators today: the basin burn
probability raster, scored on the draft's breaks, and the TRPA high-severity fire probability
layer (`Fire` service, layer 3), classed 0 to 3 in place of flame length. **TRPA proposal**
(decision 22): these are the wildfire exposure inputs for the workshop; the contracted package
replaces them for the December release if it is delivered and reviewed in time, on the same
breaks, so the scores change in value but not in form.

**WF-R, wildfire x roads** (E 0.7 / S 0.3)

| Code | Indicator | Weight | Indicator value | Score | Default | Sampling |
|---|---|---|---|---|---|---|
| E1 | Annual burn probability (TRPA burn probability raster; contracted fire-behavior modeling when delivered) | 0.70 | over 1 percent | 3 | 0 | Maximum within a 300 ft buffer, length-weighted along the segment |
| | | | over 0.5 to 1 percent | 2 | | |
| | | | over 0 to 0.5 percent | 1 | | |
| | | | 0 percent | 0 | | |
| E2 | **TRPA proposal** (decision 22): TRPA high-severity fire probability classed 0 to 3, in place of flame length | 0.30 | class 3 (highest) | 3 | 0 | Maximum within a 300 ft buffer |
| | | | class 2 | 2 | | |
| | | | class 1 | 1 | | |
| | | | class 0 | 0 | | |
| E2 (draft, when the contracted package is delivered) | Flame length | 0.30 | over 8 ft | 3 | 0 | Maximum within a 300 ft buffer |
| | | | over 4 to 8 ft | 2 | | |
| | | | over 0 to 4 ft | 1 | | |
| | | | 0 ft | 0 | | |
| S1 | Wooden guardrails present | 0.30 | present | 3 | 1 (the draft's default) | Street network or jurisdiction attribute where present |
| | | | not present | 1 | | |

**WF-AT, wildfire x active transport, and WF-TC, wildfire x transit centers** (E 1.0)

Exposure is the WF-R set at E1 0.70 and E2 0.30 (the same TRPA inputs); there is no sensitivity
indicator. Active transport samples the length-weighted maximum within a 300 ft
buffer; transit centers the maximum within 300 ft.

### 6.5 Decisions requested from the consultant

21. FEMA flood zones as the flood exposure indicator for roads, active transport, and transit
    centers, with the 1 percent zone scoring 3 and the extent and depth indicators collapsed
    into one at the full exposure weight. The draft's extent scale would score the 100-year
    floodplain 2 and the 500-year 1, with 3 and 2.5 reserved for the 10- and 50-year
    floodplains that FEMA does not map.
22. Wildfire exposure from the TRPA data in hand: the burn probability raster on the draft's
    breaks, and TRPA high-severity fire probability classed 0 to 3 in place of flame length.
    The contracted fire-behavior package replaces them for December if delivered and reviewed
    in time, on the same breaks.
23. Missing-data defaults the draft leaves TBD: truck AADT 1 (under 100) and trail slope 1
    (5 to under 10 percent), both flagged `S_source` partial.
