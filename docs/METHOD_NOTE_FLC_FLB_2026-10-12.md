# Method note: flood exposure and the culvert profile for FL-C and FL-B

**PROTECT Task 3.2, component 2. Delivery to the consultant, Oct. 12, 2026. Draft for review.**
Source of record for the rubric: `docs/SCORING_RUBRICS.md` v0.3 (sections 1, 2, and 3). Code:
`scripts/culvert_profile.py`, `scripts/score_exposure.py`. Results page: `html/culvert-results.html`.

## What is delivered

| Item | Content |
|---|---|
| `exposure_flood_culverts.csv` | 5,640 scored small culverts: `E_FLC_hist` (watershed sampling), `E_FLC_pt` (25 m point sampling), sampling source, `E_source` |
| `exposure_flood_bridges.csv` | 40 NBI structures: `E_FLB_hist` and its two terms, waterway adequacy and the flood class |
| `culvert_profile.csv` | The hazard-independent profile per culvert: size, material, contributing watershed, event flow, capacity, loading ratio, condition, and the review flags |
| `culvert_review_list.csv` | Records withheld from the loading ratio or flagged for owner confirmation, by jurisdiction |
| `Hazard_Flood_Class` | The classed flood surface, 0 to 3, that every flood pair in both lanes samples |
| `Exposure_flood_roads` | `E_FLR_hist` per street link with the share of length in each class, keyed on the network's link id, for the road, transit, and active-transport lane |

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

- Basins under 1 sq mi (5,514 culverts): rational method, Q = C i A, with C from the majority
  land cover (forest 0.35, shrub and grass 0.40, developed 0.60, barren 0.50) and i the NOAA
  Atlas 14 intensity at the Kirpich time of concentration from the longest flow path and
  relief; 100-yr headline, 25-yr carried.
- Basins of 1 sq mi and over (129 culverts): USGS regional regression for the state on the
  basin's mean annual precipitation. California, Lahontan region of Gotvald and others (2012),
  Q100 = 0.713 A^0.731 P^1.56, standard error of prediction 77 percent. Nevada, region 1 of
  Thomas and others (1997), Q100 = 6.78 A^0.750 P^0.668, standard error 46 percent. On the
  same basin region 1 gives 0.39 of the Lahontan value (median across the 129 basins).
- Capacity: FHWA HDS-5 inlet control solved at headwater equal to the crown (HW/D = 1.0),
  coefficients by shape, material, and inlet type, barrels summed per crossing. Conservative
  by roughly 1.5 to 2 against how culverts are commonly designed to run.
- Loading ratio = Q100 / capacity. Median 1.09; 90th percentile 19.1; 10th percentile 0.02.

## Records withheld or flagged

| Flag | Rule | Count |
|---|---|---|
| `size_suspect` (ratio withheld, S1 default) | Recorded size 24 in. or under on a mapped stream with 100 acres or more; 24 in. or under with 500 acres or more anywhere; or any size under 8 in. | 152 |
| `ratio_review` (scored, listed) | Loading ratio above 20 | 465, of which 303 are legacy provisional points |

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

## Decisions requested with this delivery

1. Watershed versus point sampling for culvert exposure (decision 3). Both values are
   delivered so the choice can be made on the numbers.
2. Lake-stage FEMA zone excluded from the flood pairs pending the high-lake-level pair.
3. Regression equation for the Nevada side: region 1 (the state's own) or Lahontan basin-wide.
4. Capacity at HW/D = 1.0, or a higher headwater criterion.
5. Legacy provisional points out of the rating until a jurisdiction claims them (decision 10).
6. The condition and blockage sensitivity term for FL-C (decision 1), now that condition
   exists for 1,990 of the scored culverts (663 rated, 1,327 blockage only).

## Known limits

The rational method is a screening estimate; slopes, roughness, and inlet conditions are
assumed; inverts are not surveyed; the ratio ranks crossings and is not a design number. The
future-horizon factor scales rainfall intensity only, so rain-on-snow winter peaks are not
captured. Condition exists for about a third of the scored culverts, and none for El Dorado
County. Cross-checks against the documented failures in the literature review (the Incline
Village blocked culvert, the Washoe County flash flood, the SR 89 Meeks Creek culvert) are
reported with the delivery.
