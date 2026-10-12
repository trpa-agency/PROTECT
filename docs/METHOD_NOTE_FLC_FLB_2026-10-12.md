# Method note: flood exposure, the culvert profile, and the first vulnerability scores for FL-C and FL-B

**PROTECT Task 3.2, component 2. Delivery to the consultant, Oct. 12, 2026. Draft for review;
refreshed Oct. 11 with the sensitivity and vulnerability scores and the other hazards now on the
same assets.** Source of record for the rubric: `docs/SCORING_RUBRICS.md` v0.4 (sections 1, 2,
and 3). Code: `scripts/culvert_profile.py`, `scripts/score_exposure.py`,
`scripts/score_vulnerability.py`. Results: the Flooding tab of `html/results.html`
(trpa-agency.github.io/PROTECT/html/results.html#flood).

## What is delivered

| Item | Content |
|---|---|
| `exposure_flood_culverts.csv` | 5,640 scored small culverts: `E_FLC_hist` (watershed sampling), `E_FLC_pt` (25 m point sampling), sampling source, `E_source` |
| `exposure_flood_bridges.csv` | 40 NBI structures: `E_FLB_hist` and its two terms, waterway adequacy and the flood class |
| `vulnerability_culverts.csv` | Per culvert: FL-C sensitivity terms (`S_FLC_s1` debris potential, `S_FLC_s2` loading ratio, `S_FLC_s3` condition and blockage), `S_FLC`, `V_FLC_hist`; the same for LS-C and DF-C; `V_max`, `V_max_pair`, `V_class`, `S_source` |
| `vulnerability_bridges.csv` | Per structure: FL-B sensitivity terms (channel, scour, span type, condition), `S_FLB`, `V_FLB_hist`; the same for LS-B and DF-B; `V_max`, `V_max_pair`, `V_class`, `S_source` |
| `culvert_profile.csv` | The hazard-independent profile per culvert: size, material, contributing watershed, event flow, capacity, loading ratio, condition, and the review flags |
| `culvert_review_list.csv` | Records withheld from the loading ratio or flagged for owner confirmation, by jurisdiction |
| `Hazard_Flood_Class` | The classed flood surface, 0 to 3, that every flood pair in both lanes samples |
| `Exposure_flood_roads`, `Vulnerability_roads` | `E_FLR_hist` per street link with the share of length in each class, and every pair's V with `V_max` and the provisional criticality class, keyed on the network's link id |

Public jurisdictions appear as records. The state DOT export shared under the restricted data
agreement appears only as counts; its records stay in the TRPA analysis geodatabase.

## Culvert inventory

Six jurisdiction deliveries plus the TRPA legacy compilation, compiled to one layer with a
one-to-many condition table. Pipes delivered without a culvert type (El Dorado County, and
Washoe County alignments other than cross and driveway) are typed as culverts where the pipe
line crosses a street centerline and is 60 m or shorter, the rule already applied to the state
DOT export. The scored set is typed culverts on a road link: 5,640 of 9,157 features. Culverts
within 25 m of an NBI culvert-type structure score with the bridges.

## Contributing watershed

Flow direction and accumulation on the TRPA hydro-enforced bare-earth lidar DEM (2 m, 2010) at
native resolution. The enforcement carries the mapped streams through their crossings but not
every culvert, so the DEM is conditioned with the inventory before flow direction: a 40 m line
through every typed culvert, perpendicular to its road link, is lowered to the lower of its two
ends minus 0.3 m, except within 10 m of the mapped streams and lakes, whose crossings are
already cut. Sinks shallower than 3 m are then filled; deeper sinks are kept. The pour point is
the culvert's own cell on the breach (maximum accumulation within 4 m). Culverts within 10 m of
each other on one link are one crossing with one watershed and summed capacity. Watersheds are
delineated incrementally between crossings and aggregated up the drainage tree, so every
crossing carries its full contributing area, mean slope, mean elevation, majority NLCD 2021
land cover, and PRISM 1991 to 2020 mean annual precipitation.

Why the conditioning matters: without the breach, creeks at unbreached crossings spilled along
roadside ditches into successive small pipes; without the stream exclusion, a breach beside a
creek pulled the creek out of its channel. Both were found and removed in the Oct. 8 to 9 runs.

## Event flow and capacity

- Basins under 1 sq mi (5,511 culverts): rational method, Q = C i A, with C from the majority
  NLCD land cover (forest 0.35, shrub and grass 0.40, developed 0.60, barren 0.50) and i the
  NOAA Atlas 14 intensity at the Kirpich time of concentration from the longest flow path and
  relief; 100-yr headline, 25-yr carried.
- Basins of 1 sq mi and over (129 culverts): USGS regional regression for the state on the
  basin's mean annual precipitation. California, Lahontan region of Gotvald and others (2012),
  Q100 = 0.713 A^0.731 P^1.56, standard error of prediction 77 percent. Nevada, region 1 of
  Thomas and others (1997), Q100 = 6.78 A^0.750 P^0.668, standard error 46 percent. On the
  same basin region 1 gives 0.39 of the Lahontan value (median across the 129 basins).
- Capacity: FHWA HDS-5 inlet control solved at headwater equal to the crown (HW/D = 1.0),
  coefficients by shape, material, and inlet type, barrels summed per crossing. Conservative
  by roughly 1.5 to 2 against how culverts are commonly designed to run.
- Loading ratio = Q100 / capacity. Median 1.07; 90th percentile 18.5 (public jurisdictions:
  median 0.90, 90th percentile 8.75).

## Records withheld or flagged

| Flag | Rule | Count |
|---|---|---|
| `size_suspect` (ratio withheld, S2 default) | Recorded size 24 in. or under on a mapped stream with 100 acres or more; 24 in. or under with 500 acres or more anywhere; or any size under 8 in. | 150 |
| `ratio_review` (scored, listed) | Loading ratio above 20 | 457, of which 302 are legacy provisional points |

A suspect record is a wrong size field, a ditch pipe beside the real structure, or an
underdrain; the basin arriving at it is real, the pipe is not its crossing. The review list goes
to each owner for confirmation.

## Flood exposure

The classed surface follows the FL-C E1 values of rubric decision 19: the FEMA 1 percent zone
scores 3, the 0.2 percent zone and a 10 m buffer on the lidar-derived streams score 2, and an
NHD flowline outside a zone would score 1 (no flowline layer is configured, so 1 occurs only
through the tailwater modifier). The lake's own 1 percent stillwater zone (13 FEMA polygons,
467 km2, more than half on the lake) is excluded as lake-stage flooding, the high-lake-level
pair the Steering Committee has not adopted. The surface covers 12.0 km2 at class 3 and 97.6
km2 at class 2.

Sampling follows rubric 1.7 and decision 3: small culverts take the maximum over the full
contributing watershed, with the 25 m point value as the fallback where no watershed exists
and carried alongside for every culvert; bridges take the maximum within 25 m; road links take
the maximum class touching the link, with the share of length in each class. The tailwater
modifier adds 1 (maximum 3) where the outlet is below 6,230 ft (128 culverts).

| E value | Culverts, watershed sampling | Road links |
|---|---|---|
| 0 | 3,350 | 15,617 |
| 1 | 88 | 0 |
| 2 | 1,959 | 2,307 |
| 3 | 243 | 361 |

The point-sampled value for every culvert is the `E_FLC_pt` column of the delivered CSV; its
distribution sits well below the watershed values, which is the comparison decision 3 turns on.

FL-B combines waterway adequacy (NBI item 71) at 0.20 with the flood class at 0.10,
normalized to 0 to 3: five structures at 0, 13 at 1.7, three above 2.

## Sensitivity and vulnerability (added Oct. 11)

FL-C sensitivity follows rubric 2.3 with the TRPA proposal for S3 (decision 1): S1 debris
potential of the basin from the draft's slope by land cover matrix at 0.25, S2 the 100-yr
loading ratio on the draft's bands at 0.30, S3 condition and blockage at 0.15, so that
V_FLC = 0.30 E + 0.25 S1 + 0.30 S2 + 0.15 S3 on the 0 to 3 scale. The profile's land cover
groups map onto the matrix columns as trees (forest), shrubs (shrub, grass, barren), urban
(developed), and water and snow (water, wetland); the three middle assignments are TRPA
choices the draft does not make. Defaults (rubric 1.6): S1 is 1 where no watershed exists, S2
is 1 where the ratio is withheld or the size is missing, S3 is 2 (fair) where no inspection
carries a rating or a blockage figure; `S_source` is full, partial, or default per culvert.

FL-B sensitivity is the draft's four NBI terms: channel condition (item 61) at 0.10, scour
criticality (item 113) at 0.40, span type (item 45) at 0.10, and the lowest of the condition
ratings (items 58 to 60, or 62 for culvert-type structures) at 0.10, with blanks scored as the
draft's lowest band and span type 1 when blank (TRPA proposal). All 40 structures carry every
term.

| Pair | Low (under 1) | Medium (1 to under 2) | High (2 and over) | Median V |
|---|---|---|---|---|
| FL-C, all 5,640 scored culverts | 2,115 | 2,866 | 659 | 1.15 |
| FL-C, public jurisdictions (5,096) | 1,947 | 2,555 | 594 | 1.15 |
| FL-B, 40 structures | 7 | 32 | 1 | 1.2 |

Class breaks are the TRPA proposal of rubric 1.2 (1.0 and 2.0). Condition exists for 1,990 of
the scored culverts (663 rated, 1,327 blockage only); the rest carry the fair default, so
`S_source` is partial on 4,543 culverts, full on 1,066, and default on 31.

## The same assets under the other hazards

Landslide (LS-C, LS-B) and debris flow (DF-C, DF-B) are scored on the same culverts and
bridges, and the asset-level rating is the maximum pair (rubric 1.4). Landslide exposure reads
the USGS 2024 susceptibility release as the share of each 90 m cell that is landslide-prone
(decision 24), with the precipitation-change term at 0 for the historical horizon, so it tops
out at 2.14. Debris flow is the draft's option 1 with the TRPA most-likely fire severity surface
standing in for the contracted predicted soil burn severity (`DF_option` records this), and
the sensitivity set of decision 7 (opening size, condition and blockage).

One result needs the consultant's attention. Debris flow sets `V_max` on 4,451 of the 5,096
public culverts and 27 of the 40 bridges, and 59 percent of culverts class High on it, because
the draft's drainage-size indicator scores 3 for any contributing area under 0.25 sq mi, which
nearly every culvert basin is. With the severity stand-in and the sensitivity floors, the pair
carries a floor near 1.4 before slope says anything. Flooding alone gives 594 High culverts.
The Results page shows each pair separately; the question is whether the stand-in pair should
set the combined class for the workshop, and whether the drainage-size breaks hold.

## Decisions requested with this delivery

1. Watershed versus point sampling for culvert exposure (decision 3). Both values are
   delivered so the choice can be made on the numbers.
2. Lake-stage FEMA zone excluded from the flood pairs pending the high-lake-level pair.
3. Regression equation for the Nevada side: region 1 (the state's own) or Lahontan basin-wide.
4. Capacity at HW/D = 1.0, or a higher headwater criterion.
5. Legacy provisional points out of the rating until a jurisdiction claims them (decision 10).
6. The condition and blockage sensitivity term for FL-C (decision 1), applied here as the TRPA
   proposal; the draft's S1 0.35 and S2 0.35 without S3 is a configuration switch.
7. Whether the debris-flow stand-in stays in `V_max` for the workshop, and the drainage-size
   breaks (decisions 7 and 15).
8. The landslide susceptibility reading (decision 24) and the wildfire inputs (decision 22),
   both taken from data in hand.
9. Span-length direction for LS-B and DF-B (decision 12): the draft's direction is applied.

## Known limits

The rational method is a screening estimate; slopes, roughness, and inlet conditions are
assumed; inverts are not surveyed; the ratio ranks crossings and is not a design number. The
future-horizon factor scales rainfall intensity only, so rain-on-snow winter peaks are not
captured. Condition exists for about a third of the scored culverts, and none for El Dorado
County. Roads carry no sensitivity (decision 25): each road pair's vulnerability is its
exposure. The 2050 and 2080 columns are December work. Cross-checks
against the documented failures in the literature review (the Incline Village blocked culvert,
the Washoe County flash flood, the SR 89 Meeks Creek culvert) are reported with the delivery.
