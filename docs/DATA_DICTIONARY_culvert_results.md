# Data Dictionary - Culvert profile, flood exposure, and the results files

**Last updated:** 2026-10-09
**Custodian:** TRPA Science and Data team (the vulnerability assessment analyst)
**Source system:** PROTECT analysis file geodatabase on TRPA storage, written by the repo scripts
**Source location:** `F:\GIS\PROJECTS\Transportation\Protect\PROTECT_analysis\PROTECT_analysis.gdb` (assets, profile, exposure), `PROTECT_hazards.gdb` (classed hazard surfaces), `PROTECT_terrain.gdb` (terrain rasters); published subsets in `data/processed/results/`
**Refresh cadence:** On demand. The profile reruns when the inventory, the DEM conditioning, or the hydrology parameters change (`scripts/culvert_profile.py`); exposure reruns when a hazard surface changes (`scripts/score_exposure.py`); the published files follow (`scripts/publish_results.py`)
**Coordinate system:** NAD 1983 UTM Zone 10N (EPSG:26910) in the geodatabases; WGS 84 (EPSG:4326) in the published GeoJSON
**Spatial extent:** Lake Tahoe Basin (TRPA boundary, about 501 sq mi)
**Restricted data:** The state DOT (NDOT) rows exist only in the geodatabase and the restricted QA folder on F:. Every CSV under `outputs/` and every file under `data/processed/results/` excludes them at the row level.

This dictionary covers six datasets that read together:

1. `Culverts` (feature class): one row per culvert or stormwater pipe, with the profile and exposure fields appended
2. `CulvertCrossings` (table) and `CulvertWatersheds_inc` (feature class): one row per crossing and its incremental watershed
3. `Bridges` (feature class): the 40 NBI structures with their flood exposure fields
4. `Exposure_flood_roads` (table): flood exposure per street link, for the road, transit, and active-transport lane
5. `Hazard_Flood_Class` (feature class): the classed flood surface every flood pair samples
6. The published results files

Method: `docs/SCORING_RUBRICS.md` sections 1, 2, and 3, and `docs/METHOD_NOTE_FLC_FLB_2026-10-12.md`.

---

## 1. `Culverts`

**Geometry type:** Point
**Row count (typical):** 9,157 (5,640 scored)
**Primary key:** `culvert_id`

### Description

One point per drainage asset compiled from six jurisdiction deliveries, the state DOT export, and the TRPA legacy compilation. The inventory fields come from the deliveries through `notebooks/culvert_layer_engineering.ipynb` and `scripts/load_culverts_gdb.py`. The profile fields (section 1.2) are written by `scripts/culvert_profile.py` and describe each crossing in the terms the sensitivity indicators use; they are descriptors, not scores. The exposure fields (section 1.3) are written by `scripts/score_exposure.py`. Only rows with `scored = 1` carry a vulnerability rating.

### 1.1 Inventory fields

| Column | Type | Units | Nullable | Description | Domain / Valid values |
|---|---|---|---|---|---|
| `culvert_id` | string | - | No | Jurisdiction and the delivering agency's own id, joined with a bar | `<jurisdiction>|<source_id>`, unique |
| `jurisdiction` | string | - | No | Owning agency as delivered | Caltrans, Placer County, El Dorado County, Douglas County, City of South Lake Tahoe, Washoe County, NDOT, TRPA Legacy (provisional) |
| `source_id` | string | - | No | The agency's asset identifier | - |
| `feature_type` | string | - | No | Asset class after the road-crossing rule | `culvert`, `stormwater pipe` |
| `road_name` | string | - | Yes | Road carried, as delivered; null where the agency gave none | - |
| `material` | string | - | Yes | Pipe material as delivered (raw text or code) | - |
| `xsection_shape` | string | - | Yes | Cross-section shape as delivered | - |
| `span_in` | float | inches | Yes | Opening width (diameter for round pipes), cleaned: the -9999 sentinel and circular spans over 144 in. are nulled | > 0 |
| `rise_in` | float | inches | Yes | Opening height for boxes, arches, and ellipses | > 0 |
| `length_ft` | float | feet | Yes | Pipe length as delivered | > 0 |
| `inlet_type`, `outlet_type` | string | - | Yes | End treatments as delivered | - |
| `install_year` | int | year | Yes | Year built; exists for El Dorado County and the city only | 1900 to 2026 |
| `comments` | string | - | Yes | Delivery notes; `crossing-rule` is appended where the road-crossing rule retyped a pipe | - |
| `geom_source` | string | - | No | How the point was derived from the delivery | `point`, `line-midpoint`, `line-start` |
| `data_source` | string | - | No | Delivered file or service | - |
| `load_date` | date | - | No | Date the loader wrote the row | ISO 8601 |
| `parent_segment_id` | string | - | Yes | Link id of the nearest street within 50 m (`src_objectid` on the clean street network); null for assets with no street within 50 m | matches `Streets_Network_Tahoe_Clean.src_objectid` |
| `parent_dist_m` | float | meters | Yes | Distance from the point to its parent link | 0 to 50 |
| `has_condition` | int | - | No | 1 where at least one inspection record exists | 0, 1 |
| `SHAPE` | geometry(Point) | - | No | Asset location | NAD 1983 UTM Zone 10N |

### 1.2 Profile fields (hazard-independent)

| Column | Type | Units | Nullable | Description | Domain / Valid values |
|---|---|---|---|---|---|
| `scored` | int | - | No | 1 where the asset is a typed culvert on a street link and not within 25 m of an NBI culvert-type structure | 0, 1 |
| `large_culvert_id` | string | - | Yes | NBI structure number when the asset is within 25 m of an NBI culvert-type structure; the asset then scores with the bridges | `Bridges.bridge_id` |
| `d_eq_in` | float | inches | Yes | Equivalent diameter: `span_in` for round pipes, square root of (4 x span x rise / pi) otherwise; null when size is missing | > 0 |
| `size_class` | string | - | Yes | Size band on `d_eq_in` | `small` (18 in. or under), `medium` (over 18 to 36), `large` (over 36 to 72), `major` (over 72) |
| `material_class` | string | - | No | Material harmonized across agencies | `corrodible_metal`, `plastic`, `concrete`, `unknown` |
| `crossing_id` | string | - | Yes | Crossing the culvert belongs to (culverts within 10 m on one link are one crossing); null where the pour point could not be found | `CulvertCrossings.crossing_id` |
| `barrels` | int | - | Yes | Number of culverts in the crossing | 1 and over |
| `snap_dist_m` | float | meters | Yes | Distance from the point to its pour cell | 0 to 4 |
| `contrib_area_ac` | float | acres | Yes | Full contributing watershed at the crossing, including everything upstream of upstream crossings; null where no watershed was delineated | > 0 |
| `basin_slope_pct` | float | percent | Yes | Area-weighted mean slope of the contributing watershed | 0 to 100 |
| `basin_elev_mean_ft` | float | feet | Yes | Area-weighted mean elevation of the contributing watershed | 6,200 to 10,900 |
| `basin_precip_in` | float | inches per year | Yes | Area-weighted mean annual precipitation of the watershed, PRISM 1991 to 2020 normals (800 m) | 15 to 90 |
| `basin_landcover` | string | - | Yes | Majority NLCD 2021 group over the watershed | `forest`, `shrub`, `grass`, `developed`, `barren`, `water`, `wetland` |
| `runoff_c` | float | - | No | Rational-method runoff coefficient; the land-cover value, or 0.35 where no watershed | 0.30 to 1.00 |
| `tc_min` | float | minutes | Yes | Kirpich time of concentration from the longest flow path and relief, bounded 5 to 1,440 | 5 to 1,440 |
| `ddf_point` | string | - | Yes | Nearest NOAA Atlas 14 point used for intensity | one of the eight basin points |
| `q_method` | string | - | No | How the event flow was estimated | `rational` (under 1 sq mi), `regression_CA`, `regression_NV`, `regression_needed` (no precipitation or state), `none` (no watershed) |
| `q_region` | string | - | Yes | The regression equation applied | `CA Lahontan (Gotvald 2012)`, `NV region 1 (Thomas 1997)` |
| `q_event_25_cfs`, `q_event_100_cfs` | float | cubic feet per second | Yes | 25-yr and 100-yr event peak flow at the crossing | > 0 |
| `q_cap_cfs` | float | cubic feet per second | Yes | This barrel's capacity, FHWA HDS-5 inlet control at headwater equal to the crown | > 0 |
| `q_full_cfs` | float | cubic feet per second | Yes | Manning full-flow capacity, carried as a cross-check | > 0 |
| `q_cap_crossing_cfs` | float | cubic feet per second | Yes | Capacity summed over the barrels of the crossing | > 0 |
| `load_ratio_25`, `load_ratio_100` | float | - | Yes | Event flow over crossing capacity; above 1 means the event exceeds the crossing at the crown. Null where size, watershed, or flow is missing, and withheld where `size_suspect = 1` | 0 and over |
| `cond_class` | int | - | No | Harmonized latest-inspection condition | 0 good, 1, 2, 3 poor; 1 is the default where no rating exists |
| `cond_source` | string | - | No | Where `cond_class` came from | `rated`, `blockage_only`, `default` |
| `cond_date` | date | - | Yes | Latest inspection date | ISO 8601 |
| `cond_stale` | int | - | No | 1 where the latest inspection predates 2015 | 0, 1 |
| `blockage_pct` | float | percent | Yes | Latest recorded blockage | 0 to 100 |
| `pp_elev_ft` | float | feet | Yes | Elevation of the pour cell | 6,200 to 9,000 |
| `tailwater_flag` | int | - | No | 1 where the pour cell is below 6,230 ft (the legal maximum lake level is 6,229.1 ft), so high lake stage can reduce outlet capacity | 0, 1 |
| `dem_vintage_flag` | int | - | No | 1 where `install_year` is 2011 or later, so the crossing postdates the 2010 lidar | 0, 1 |
| `on_stream` | int | - | No | 1 where the point is within 10 m of the lidar-derived streams and lakes layer | 0, 1 |
| `size_suspect` | int | - | No | 1 where the recorded size cannot be the crossing for the basin that arrives: 24 in. or under on a mapped stream with 100 acres or more, 24 in. or under with 500 acres or more anywhere, or any size under 8 in. The loading ratio is withheld | 0, 1 |
| `ratio_review` | int | - | No | 1 where `load_ratio_100` is above 20; scored as is and listed for the owner to confirm | 0, 1 |
| `profile_completeness` | string | - | No | Whether size, hydrology, and condition were all observed | `full`, `partial`, `default` |
| `profile_date` | date | - | No | Date the profile was written | ISO 8601 |

### 1.3 Exposure fields

| Column | Type | Units | Nullable | Description | Domain / Valid values |
|---|---|---|---|---|---|
| `E_FLC_hist` | float | score | Yes | FL-C flood exposure, historical horizon: the maximum flood class over the contributing watershed (or within 25 m where none), plus 1 where `tailwater_flag = 1`, capped at 3 | 0, 1, 2, 3 |
| `E_FLC_pt` | float | score | Yes | The same indicator sampled as the maximum within 25 m of the point, carried for comparison with the watershed rule | 0, 2, 3 |
| `E_FLC_src` | string | - | Yes | Which sampling produced `E_FLC_hist` | `watershed`, `buffer` |
| `E_source` | string | - | Yes | Exposure data completeness | `full` (watershed), `partial` (buffer fallback) |

Future fields follow the same pattern: `E_LSC_hist`, `E_DFC_hist`, the sensitivity scores `S_<pair>`, and `V_<pair>_hist`, `V_max`, `V_max_pair`, `V_class` per rubric section 2.6.

### Joins and relationships

- **Joins to:** `CulvertCondition` on `culvert_id` (one-to-many; relationship class `Culvert_has_Condition`). That table holds one row per inspection: `inspection_date`, `condition_rating` as delivered, `condition_scheme` (how the agency rates condition, recorded because schemes differ), `structural_cond`, `blockage_pct`, `maintenance_need`, `notes`, `data_source`, `load_date`. The profile's `cond_class` is the harmonized latest row (rubric 2.5)
- **Joins to:** `CulvertCrossings` on `crossing_id` (many-to-one)
- **Joins to:** `Streets_Network_Tahoe_Clean` on `parent_segment_id = src_objectid` (many-to-one), which is how criticality is inherited
- **Referenced by:** `Bridges.bridge_id` through `large_culvert_id`

### Known caveats

- `segment_id` on the street network is the Overture id and is shared by split links; `parent_segment_id` therefore stores `src_objectid`, the unique link id. Older rows snapped to `segment_id` were re-snapped on Oct. 9, 2026.
- Condition exists for about a third of scored culverts. El Dorado County delivered none; Placer's 1 to 5 direction and Washoe's structural codes are unconfirmed (`docs/jurisdiction_data_questions.md`).
- The El Dorado and Washoe crossing rule has no manhole-run exception, so a short storm-drain pipe that crosses a side street can be typed as a culvert.
- TRPA legacy provisional points carry sizes that were never verified; 303 of the 465 `ratio_review` flags are legacy points.
- 221 typed culverts had no flow cell within 4 m and have no watershed; they take the 25 m exposure fallback and a null loading ratio.
- The runoff coefficient is the land-cover default per group, not calibrated to Tahoe snow-affected runoff.
- Rows for the restricted jurisdiction exist here and nowhere under the repo.

---

## 2. `CulvertCrossings` and `CulvertWatersheds_inc`

**Geometry type:** none (table) and Polygon
**Row count (typical):** 5,321 crossings
**Primary key:** `crossing_id`

### Description

One row per crossing: the group of culverts within 10 m of each other on one street link, represented by the member with the largest flow accumulation. `CulvertWatersheds_inc` holds each crossing's incremental watershed, the cells that reach this crossing without passing through another crossing; the table's `full_cells` and `contrib_area_ac` are the sum up the drainage tree.

| Column | Type | Units | Nullable | Description | Domain / Valid values |
|---|---|---|---|---|---|
| `crossing_id` | string | - | No | Crossing identifier | `X` plus five digits |
| `crossing_pp` | int | - | No | Internal pour-point id; equals `gridcode` on the watershed polygons | > 0 |
| `downstream_crossing_id` | string | - | Yes | The next crossing downstream on the drainage tree; null at an outlet or where the link was cut | `crossing_id` |
| `barrels` | int | - | No | Member culverts | 1 and over |
| `member_ids` | string | - | No | Member `culvert_id` values, semicolon-separated | - |
| `jurisdiction` | string | - | No | Jurisdiction of the first member | as in `Culverts` |
| `restricted` | int | - | No | 1 where any member is from the restricted jurisdiction | 0, 1 |
| `pp_x`, `pp_y` | float | meters | No | Pour cell center | UTM 10N |
| `snap_dist_m` | float | meters | No | Distance from the representative culvert to its pour cell | 0 to 4 |
| `pp_elev_ft` | float | feet | No | Pour cell elevation | - |
| `basin_elev_max_m` | float | meters | Yes | Highest cell in the full watershed | - |
| `basin_elev_mean_ft` | float | feet | Yes | Area-weighted mean elevation of the full watershed | - |
| `basin_precip_in` | float | inches per year | Yes | Area-weighted mean annual precipitation of the full watershed (PRISM) | - |
| `relief_ft` | float | feet | Yes | `basin_elev_max_m` minus pour elevation, in feet | 0 and over |
| `flow_len_ft` | float | feet | Yes | Longest upstream flow path | > 0 |
| `inc_cells` | float | cells | Yes | Cells in the incremental zone (2 m cells, 4 sq m each) | > 0 |
| `full_cells` | float | cells | No | Cells in the full watershed | > 0 |
| `contrib_area_ac` | float | acres | No | `full_cells` x 4 sq m, in acres | > 0 |
| `facc_area_ac` | float | acres | No | Flow accumulation at the pour cell plus the cell itself, in acres; the cross-check on the tree | > 0 |
| `area_check_pct` | float | percent | No | `contrib_area_ac` against `facc_area_ac`; a disagreement over 5 percent and 2 cells is logged | about 0 |
| `basin_slope_pct` | float | percent | Yes | Area-weighted mean slope | 0 to 100 |
| `basin_landcover` | string | - | Yes | Majority NLCD group | as in `Culverts` |
| `runoff_c` | float | - | Yes | Area-weighted runoff coefficient from the land-cover shares | 0.30 to 1.00 |
| `delineated` | date | - | No | Run date | ISO 8601 |

`CulvertWatersheds_inc` carries `gridcode` (= `crossing_pp`), `crossing_id`, and `downstream_crossing_id` on each polygon.

### Known caveats

- The terrain the watersheds come from is the 2010 lidar DEM breached through the inventory and filled to 3 m. Crossings rebuilt after 2010 and drainages re-routed since are not in it.
- Breach lines within 10 m of mapped streams are not cut; those crossings rely on the DEM's own enforcement.
- The incremental zones are exact; the full watershed depends on the downstream links, which are computed from one D8 step below the pour cell and can be cut where a loop or an uphill link is detected. The log reports both counts for each run.

---

## 3. `Bridges`

**Geometry type:** Point
**Row count (typical):** 40
**Primary key:** `bridge_id`

### Description

The National Bridge Inventory structures inside the TRPA boundary (California and Nevada), built by `scripts/build_bridges.py`. Five are NBI culvert-type structures. The inventory fields decode the NBI items the rubric uses; the exposure fields are written by `scripts/score_exposure.py`. Only the exposure fields are listed here; the NBI fields follow the NBI coding guide, with the item number in the script's field list.

| Column | Type | Units | Nullable | Description | Domain / Valid values |
|---|---|---|---|---|---|
| `bridge_id` | string | - | No | NBI structure number, unique within the state | - |
| `state` | string | - | No | State | `CA`, `NV` |
| `is_culvert_type` | int | - | No | 1 where NBI item 43B is 19 (culvert over 20 ft) | 0, 1 |
| `water_crossing` | int | - | No | 1 where the structure is over a waterway (scour item 113 not N) | 0, 1 |
| `waterway_eval` | string | - | Yes | NBI item 71, waterway adequacy | 0 to 9, N |
| `scour_code` | string | - | Yes | NBI item 113, scour criticality | 0 to 9, N, U |
| `lowest_rating` | int | - | Yes | Lowest of deck, superstructure, and substructure (or culvert) ratings | 0 to 9 |
| `main_spans`, `max_span_m` | int, float | -, meters | Yes | NBI items 45 and 48 | - |
| `parent_segment_id` | string | - | Yes | Street link id (`src_objectid`) within 50 m | - |
| `E_FLB_e1` | float | score | No | Waterway adequacy scored on the FL-B E1 scale; 1 where blank, 0 where N | 0 to 3 |
| `E_FLB_e2` | float | score | No | Flood class, maximum within 25 m | 0, 2, 3 |
| `E_FLB_hist` | float | score | No | (0.20 x E1 + 0.10 x E2) / 0.30, the weight-normalized exposure | 0 to 3 |
| `E_source` | string | - | No | `partial` where item 71 was blank | `full`, `partial` |

---

## 4. `Exposure_flood_roads`

**Row count (typical):** 18,285
**Primary key:** `src_objectid`

### Description

Flood exposure per street link of `Streets_Network_Tahoe_Clean`, written as a standalone table so the street layer itself, which the road, transit, and active-transport lane owns, is not edited. The same classed surface the culverts and bridges use.

| Column | Type | Units | Nullable | Description | Domain / Valid values |
|---|---|---|---|---|---|
| `src_objectid` | string | - | No | Street link id, unique per link | matches the street layer |
| `E_FLR_hist` | float | score | No | Maximum flood class touching the link | 0, 1, 2, 3 |
| `len_pct_c1`, `len_pct_c2`, `len_pct_c3` | float | percent | No | Share of the link's length inside class 1, 2, and 3 | 0 to 100 |
| `seg_len_m` | float | meters | No | Link length | > 0 |

---

## 5. `Hazard_Flood_Class`

**Geometry type:** Polygon
**Row count (typical):** 1,307
**Primary key:** none (dissolved by class)

### Description

The flood exposure surface on the FL-C E1 values, so every flood pair in both lanes samples one surface. Built by `scripts/score_exposure.py --hazard flood --build` from the TRPA `Streams_and_Flood_Zone` service: layer 0 (FEMA zones) and layer 1 (lidar-derived streams and lakes). Where classes overlap, the higher class wins.

| Column | Type | Units | Nullable | Description | Domain / Valid values |
|---|---|---|---|---|---|
| `hz_class` | int | score | No | Flood class | 3 (FEMA 1 percent zone), 2 (0.2 percent zone, or within 10 m of a mapped stream), 1 (NHD flowline outside a zone; unused until a flowline layer is configured) |
| `hazard` | string | - | No | Hazard the surface belongs to | `flood` |
| `label` | string | - | No | Plain-language class label | - |
| `SHAPE` | geometry(Polygon) | - | No | Class extent | NAD 1983 UTM Zone 10N |

### Known caveats

- The FEMA polygons more than half on a water body over 1 km2 (the lake's 1 percent stillwater zone, 13 polygons, 467 km2) are excluded; lake-stage flooding is the high-lake-level pair. `exposure.flood.include_lake_zone` restores them.
- Water bodies over 1 km2 are excluded from the stream buffer; small lakes and ponds are not, so a culvert beside a pond scores 2.
- Class 1 does not occur: no NHD flowline layer is configured. A culvert at 1 got there through the tailwater modifier.

---

## 6. Published results files (`data/processed/results/`)

**Source location:** `data/processed/results/` in the repo, served by GitHub Pages and read by `html/culvert-results.html`
**Written by:** `scripts/publish_results.py`
**Coordinate system:** WGS 84 (EPSG:4326)

| File | Content | Rows |
|---|---|---|
| `culverts_results.geojson` | Scored culverts in the public jurisdictions, with the inventory, profile, and exposure fields listed in sections 1.1 to 1.3 (subset: the columns in `CULVERT_COLS` of the script), floats rounded | 5,096 |
| `culverts_results.csv` | The same rows without geometry | 5,096 |
| `bridges_results.geojson` | The bridges with the section 3 fields plus facility, feature crossed, owner, year built, and condition labels | 40 |
| `flood_surface.geojson` | `Hazard_Flood_Class` simplified to 5 m, with `hz_class` and `label` | 1,307 |
| `summary.json` | Counts and quantiles the page's KPI cards show: scored, full profile, with ratio, ratio median and 90th percentile, suspect and review counts, tailwater count, regression count, exposure distribution, counts by jurisdiction, bridge counts, surface area by class, generation date, and notes | - |

### Known caveats

- Public rows only; counts here are lower than the full-set counts in the run logs and the method note (for example, ratio median 0.90 here against 1.09 for the full set).
- Values are a snapshot of the last publish; the generation date is in `summary.json`.

---

## Change Log

| Date | Change | Author |
|---|---|---|
| 2026-10-09 | Initial dictionary: inventory, profile, exposure, crossings, bridges, road table, flood surface, published files | the analyst |
