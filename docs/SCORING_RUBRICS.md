# PROTECT scoring rubrics

**Version 0.1, Oct. 8, 2026.** Draft for consultant review (ICF checkpoint Oct. 9).
**Scope of this version:** the shared framework (section 1) and the three culvert pairs FL-C,
LS-C, and DF-C (section 2). Bridge, debris flow on roads, and avalanche sections follow from the
same lane; road, active transport, and transit center sections belong to the other lane. Nothing
is scored until the rubric for that pair is agreed.

Source of record for the equation, weights, and indicators: the consultant's draft VA
Methodology (Aug. 20, 2026, internal draft, not committed). Where this document goes beyond the
draft, the item is marked **TRPA proposal** and listed in section 2.8 for a decision. Pair
definitions mirror `Hazard_Asset_Pairs.md` (v0.8).

---

## 1. Shared framework

### 1.1 Equation and scale

Every indicator is scored as an integer 0 (none) to 3 (highest) and carries a weight. Indicator
weights sum to 1.0 within a pair, so the pair score is on the same 0 to 3 scale:

    V_<pair> = sum over indicators of (weight x score)

The exposure weight wE is the sum of the exposure indicator weights and wS the sum of the
sensitivity indicator weights, so the draft's "Vulnerability = (Exposure x wE) + (Sensitivity x
wS)" is the same thing written per component. `E_<pair>` and `S_<pair>` are written as the
weight-normalized component scores (each 0 to 3) so the tool can show them separately.

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
Sensitivity does not vary by horizon. Contracted flood depths are already climate-adjusted; do
not apply a second change factor to them. Locally computed design flows (section 2.4) take their
2050 and 2080 factors from the climate pipeline's DDF extract.

### 1.6 Missing data

Every indicator has a default (stated in its rubric row). An asset scored on any default carries
`S_source` (or `E_source`) = `partial`; an asset with every sensitivity indicator defaulted
carries `default`. Defaults are shown on the map and in popups as such. The draft leaves most
defaults "TBD"; the values in this document are TRPA proposals and are listed in section 2.8.

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
| `size_class` | Small (18 in. or under), medium (over 18 to 36), large (over 36 to 72), major (over 72) on `d_eq_in` | Derived |
| `material_class` | Corrodible metal (CMP, CSP, squash, annular, corrugated metal), plastic (HDPE, PVC), concrete (RCP, concrete, box), unknown. El Dorado's undecoded `code N` values map to unknown until the county supplies the domain | `material` |
| `contrib_area_ac` | Contributing drainage area at the crossing | Flow accumulation on the 2022 lidar DTM; pour point is the maximum-accumulation cell within 20 m of the culvert, on the upstream side of the road |
| `basin_slope_pct` | Mean slope of the contributing watershed | DTM, zonal mean |
| `basin_landcover` | Majority NLCD class in the watershed | NLCD 2021 |
| `q_event_cfs` (hist, 2050, 2080) | Event peak flow at the crossing, 100-yr headline, 25-yr carried as a second column | Section 2.4 |
| `q_cap_cfs` | Hydraulic capacity with headwater at the crown | Section 2.4 |
| `load_ratio` | `q_event_cfs / q_cap_cfs` (the draft's Qevent/Qdesign) | Derived |
| `cond_class` | Harmonized latest-inspection condition, 0 good to 3 poor | Section 2.5 |
| `cond_date`, `cond_stale` | Latest inspection date; stale when before 2015 | `CulvertCondition` |
| `blockage_pct` | Latest recorded blockage | Washoe `perc_full`, NDOT `PercentBlockage`, legacy text |
| `tailwater_flag` | Outlet within 50 m of the shoreline and below 6,230 ft (the legal maximum lake level is 6,229.1 ft) | DTM, high-water shoreline layer |
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

Weights are the draft's unless marked. Each row is one indicator; the pair score is the weighted
sum. Class breaks marked "match FL-R" (and so on) must equal the breaks the roads lane uses for
the same surface, so the two lanes stay comparable; the values shown are placeholders until that
lane's breaks are set.

**FL-C, flooding x small culverts** (E 0.3 / S 0.7)

| Code | Indicator | Weight | 0 | 1 | 2 | 3 | Default | Sampling |
|---|---|---|---|---|---|---|---|---|
| E1 | 100-yr flood depth over the road, contracted flood model, max of fluvial and pluvial | 0.30 | under 0.5 ft | 0.5 to under 1 ft | 1 to under 3 ft | 3 ft and over (match FL-R) | 0 where the model has no cell | Max within 25 m of the crossing on the road |
| E1 workshop fallback | FEMA flood zone and stream crossing (public, live today) | 0.30 | no zone, no flowline | on an NHD flowline outside a zone | 0.2 percent zone (X500) or on a mapped TRPA stream | 1 percent zone (A, AE) | 0 | Max within 25 m |
| E1 modifier | **TRPA proposal:** tailwater. Add 1 (cap 3) when `tailwater_flag` is set, because high lake stage reduces outlet capacity independent of rainfall | in E1 | | | | | no change | |
| S1 | Capacity loading ratio `load_ratio` (Qevent/Qdesign) | 0.35 | under 0.5 | 0.5 to under 1.0 | 1.0 to under 2.0 | 2.0 and over | 1 when `span_in` is null | Per crossing; multi-barrel crossings grouped (section 2.4) |
| S2 | Debris potential of the basin, draft option 1: mean basin slope by majority landcover | 0.35 | slope under 10 percent | 10 to under 20 | 20 to under 35 | 35 and over; subtract 1 (floor 0) when majority landcover is developed, barren, or water (little wood or sediment supply) | 1 when no watershed | Watershed |
| S3 | **TRPA proposal:** condition and blockage, max of `cond_class` and the blockage class (0 to 24 percent = 0, 25 to 49 = 1, 50 to 74 = 2, 75 and over = 3) | see note | | | | | 1, `S_source` partial | Latest inspection |

Note on S3. The draft has no condition term for small culverts and leaves "culvert condition"
TBD. TRPA proposes re-splitting the 0.7 sensitivity weight as S1 0.30, S2 0.25, S3 0.15. If the
consultant declines, the draft's S1 0.35 and S2 0.35 stand and `cond_class` stays a profile
field shown in the popup.

**LS-C, landslide x small culverts** (E 0.7 / S 0.3)

| Code | Indicator | Weight | 0 | 1 | 2 | 3 | Default | Sampling |
|---|---|---|---|---|---|---|---|---|
| E1 | USGS Landslide Susceptibility Index class, or a recorded landslide (California Landslides Database) | 0.50 | class 1 and 2 | class 3 | class 4 | class 5, or any recorded landslide (match LS-R) | 0 | **TRPA proposal:** max over the watershed; 25 m buffer where none |
| E2 | Cal-Adapt annual precipitation change versus historical | 0.20 | 0 percent or less | over 0 to 5 | over 5 to 10 | over 10 (match LS-R) | 0; the historical horizon scores 0 by definition | Watershed mean |
| S1 | Culvert size, opening width (`d_eq_in`) | 0.15 | over 72 in. | over 36 to 72 | over 18 to 36 | 18 in. and under | 2 when null | Per asset |
| S2 | Culvert condition where available (`cond_class`) | 0.15 | good | fair-good | fair | poor | 1, `S_source` partial | Latest inspection |

**DF-C, debris flow x small culverts** (E 0.7 / S 0.3)

Exposure follows whichever debris-flow option is chosen for roads (DF-R); the rows below give
both so the choice does not change the culvert schema. Option 2 is the path the `debris-flow/`
Wildcat pipeline supports; option 1 can be computed locally for every culvert from the same
watershed delineation.

| Code | Indicator | Weight | 0 | 1 | 2 | 3 | Default | Sampling |
|---|---|---|---|---|---|---|---|---|
| E1 (opt. 1) | Mean basin slope (`basin_slope_pct`) | 0.20 | under 10 percent | 10 to under 20 | 20 to under 35 | 35 and over (match DF-R) | 1 | Watershed |
| E2 (opt. 1) | Drainage area (`contrib_area_ac`) | 0.20 | under 10 ac | 10 to under 50 | 50 to under 250 | 250 and over (placeholder; set from the basin distribution with DF-R) | 1 | Watershed |
| E3 (opt. 1) | Contracted predicted soil burn severity | 0.30 | unburned or unburnable | low | moderate | high | 0 | Watershed max |
| E1 (opt. 2) | Wildcat debris-flow likelihood at the pour point | 0.30 | under 0.2 | 0.2 to under 0.4 | 0.4 to under 0.6 | 0.6 and over (USGS classes) | 0 | Pour point |
| E2 (opt. 2) | Wildcat combined hazard class | 0.15 | 1 | 2 | 3 | 4 and over | 0 | Pour point |
| E3 (opt. 2) | Contracted predicted soil burn severity | 0.15 | unburned | low | moderate | high | 0 | Watershed max |
| S1 (draft) | Debris potential of the basin (same rubric as FL-C S2) | 0.30 | | | | | 1 | Watershed |
| S1 and S2 (**TRPA proposal**) | Under option 1, basin slope already sits in exposure, so debris potential in sensitivity counts it twice. Proposal: S1 opening size (`d_eq_in`, same bins as LS-C S1, small pipes plug regardless of ratio) 0.15 and S2 condition and blockage (same as FL-C S3) 0.15. Under option 2 the draft's S1 stands | 0.30 | | | | | 1 | |

Workshop fallback for DF exposure (either option not ready by Oct. 16): the proxy surface from
the lane plan (WRF 1-hr intensity against the Tahoe threshold, slope, and the burn severity
proxy), classed 0 to 3 and sampled as watershed max, with the method note stating it is a proxy.

### 2.4 Hydrology and hydraulics for the loading ratio

The draft's Qdesign is missing for nearly every culvert, so capacity is estimated from geometry.
Parameters live in `config.yaml` (`hydraulics:` block, to be added with the profile script).

- **Watershed.** Flow direction and accumulation on the 2022 lidar DTM resampled to 10 m, Fill
  applied once. Pour point is the maximum-accumulation cell within 20 m of the culvert on the
  upstream side of the road (lidar road fills act as dams, so the culvert point itself often sits
  off the flow path). Watershed polygons are kept as a feature class; they also serve the
  watershed sampling in section 2.3. Culverts within 10 m of each other on the same segment are
  one crossing: one watershed, capacities summed.
- **Event flow, Qevent.** Rational method, Q = C i A, for basins under 1 sq mi, with C by
  majority landcover (forest 0.35, shrub 0.40, developed 0.60, barren 0.50) and i the Atlas 14
  intensity at the basin's time of concentration (Kirpich), 100-yr headline and 25-yr carried.
  Basins of 1 sq mi and over (expected: a few dozen) use the USGS regional regression equations
  for the Sierra Nevada and northern Nevada. 2050 and 2080 flows apply the climate pipeline's
  DDF change factors to i.
- **Capacity, Qcap.** FHWA HDS-5 inlet-control equations with headwater at the crown
  (HW/D = 1.0), coefficients by shape, material, and inlet type (`inlet_type` where delivered;
  projecting end default). A culvert that overtops its headwater at the design flow has
  `load_ratio` over 1.0.
- **Known limits.** Rational method is a screening estimate, slopes and roughness are assumed,
  and culvert inverts are not surveyed. The ratio is for ranking, not design. State this on the
  method slide. The future-horizon factor scales rainfall intensity only; the literature review
  cites a shift of the runoff peak toward January under warming, which means rain-on-snow
  winter peaks that a rainfall change factor does not capture. Treat 2050 and 2080 ratios as a
  lower bound for mid-elevation basins and say so.

### 2.5 Condition harmonization

`cond_class` is 0 (good) to 3 (poor), from the latest inspection per culvert. Undated rows sort
oldest. Scheme semantics are recorded in `condition_scheme`; two of them are unconfirmed and are
on the jurisdiction question list.

| Source | Rule | Caveat |
|---|---|---|
| Placer County 1 to 5 | 5 to 0, 4 to 1, 3 to 2, 1 and 2 to 3 | Direction unconfirmed; the distribution (mostly 4 and 5) supports 5 = good |
| Douglas County maintenance 1 to 5 (1 = replacement) | Same mapping | 4 culverts |
| NDOT overall Good/Fair/Poor plus blockage | G 0, F 2, P 3; blockage 0, 25, 50, 75 and over to 0, 1, 2, 3; take the max | Overall rating is blank on 94 percent of visits, so blockage carries most of the signal |
| TRPA legacy text | First token Good/Fair/Poor to 0, 2, 3; Moderate to 2 | Provisional, often undated |
| Washoe County | Structural subscore is 2 on 793 of 806 rows and is treated as no signal; `perc_full` feeds `blockage_pct`; `cond_class` is partial | Code semantics unconfirmed |
| Caltrans, City of South Lake Tahoe, El Dorado County | No rating delivered. `cond_class` default 1, `S_source` partial; `cond_stale` set where the last Caltrans inspection predates 2015 | Caltrans has dates only |

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
  spot-check 20 watersheds by eye against the DTM hillshade.
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

1. Condition and blockage as a third FL-C sensitivity term (S3) with weights 0.30 / 0.25 / 0.15,
   versus the draft's 0.35 / 0.35 with no condition term. The one culvert failure in the
   literature review's event catalog (Incline Village, Aug. 2025) was a blockage, which neither
   draft term captures.
2. Debris potential computed locally (option 1 matrix in section 2.3) for every culvert, rather
   than the CULVERT tool score (option 2). NDOT data cannot be uploaded to a third-party tool,
   so option 2 would score Nevada highways differently from everything else.
3. Watershed sampling for culvert exposure (section 1.7) instead of a point buffer.
4. Tailwater modifier on FL-C E1 for shoreline outlets.
5. 100-yr as the loading-ratio event, with 25-yr carried for comparison.
6. Capacity from HDS-5 inlet control as the default Qdesign where asset records have none.
7. Under debris-flow option 1, replace the sensitivity debris-potential term with opening size
   and condition to avoid counting basin slope twice.
8. Missing-data defaults as stated per row in section 2.3.
9. Bucket breaks (section 1.2) and the max-pair aggregation rule (section 1.4).
10. Whether unsnapped forest-road culverts stay out of the rating.
