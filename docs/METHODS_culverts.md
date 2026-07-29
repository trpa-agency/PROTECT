# Methods: Tahoe Culvert Layer + Condition Table

**Task:** PROTECT 3.3 - asset layer (culverts) for the Risk Index Tool
**Pipeline:** `notebooks/culvert_layer_engineering.ipynb` | **Config:** `config.yaml`
**Last reviewed:** 2026-07-29

## Purpose

Engineer one basin-wide culvert point layer and a related 1:many condition/inspection table
from heterogeneous jurisdiction deliveries, so the PROTECT vulnerability assessment can score
road-drainage assets against hazards. Output: `outputs/culverts.gdb` (feature class `Culverts`,
table `CulvertCondition`, relationship class on `culvert_id`), with
`data/processed/culverts.gpkg` + CSVs as license-free fallbacks.

## Scope

Culverts (road-crossing drainage) are the PROTECT asset. Basins, inlets, manholes, and other
water-quality features are excluded. Sources that do not distinguish culverts from buried
conveyance keep all pipes, tagged `feature_type` = `culvert` or `stormwater pipe`; the risk
tool filters to `culvert`.

## Data sources (delivered July 2026, in `C:\GIS\Culvert`)

| Jurisdiction | Source | Geometry | Condition |
|---|---|---|---|
| Placer County | `Tahoe Culverts.gdb/Tahoe_Culverts_7_17_2026` | 660 points | 1-5 rating + date, same row |
| Douglas County | `Stormwater.gdb/Stormwater_Inspections_Rev_3`, filtered `DrainFeature = '1 - Culvert'` | 858 visits -> 858 assets (`GID_Join`, AreaID fallback) | maintenance score 1-5, repeat visits |
| El Dorado County | `SW_PIPE.gdb/SW_PIPE`, active only (`STOP_DATE_CODE <> 1`) | 2,658 lines -> midpoints | none delivered |
| Washoe County | `ConveyancePipe.shp` + `Condition.dbf` (join `asset_guid` -> `GlobalID`) | 2,413 lines -> midpoints | 806 records, structural/blockage codes |
| Caltrans D3 | 5 xlsx drainage inventories, segments grouped by `SYSNO` | 698 inlet lat-lon points | last-inspection date only |
| CSLT | AGOL Stormwater FeatureServer layer 415006, live query, domains decoded | 32 lines -> midpoints (retired statuses dropped) | none (no culvert inspection table) |
| NDOT | pending data sharing agreement | - | - |
| TRPA Legacy | `F:\...\PROTECT_analysis\Assets.gdb\Tahoe_Culvert` (read-only prior compilation, incl. USFS forest roads) | 2,223 basin points; 1,626 unmatched added as `TRPA Legacy (provisional)` | Good/Fair/Poor text -> 162 provisional records |

## Key decisions

- **Key:** `culvert_id = "<jurisdiction>|<source_id>"`; original IDs preserved, repeats suffixed `-2`, `-3`.
- **CRS:** everything reprojected to EPSG:26910 (NAD83 / UTM 10N).
- **Basin clip:** features outside the TRPA boundary (Boundaries MapServer layer 4) are dropped,
  with their condition records; dropped rows listed in `outputs/clipped_out_of_basin.csv`.
- **Lines to points:** representative point per `run.line_to_point` (default midpoint);
  `geom_source` records the derivation.
- **Ratings stay raw.** Each condition record carries the jurisdiction's own value plus a
  `condition_scheme` note; no cross-jurisdiction normalization until scale semantics are confirmed.
- **Washoe condition:** the delivered `condition` field is uniformly 0; structural/blockage
  subscores and `perc_full` carry the signal.
- **Caltrans:** one culvert per `SYSNO` (segments summed for length, geometry at first inlet).
- **Legacy gap fill:** each point in the prior TRPA compilation is matched to the nearest new
  asset within `run.legacy_match_m` (25 m); unmatched points join the layer as jurisdiction
  `TRPA Legacy (provisional)` with a PROVISIONAL comment. Match status per legacy point:
  `outputs/legacy_comparison.csv`.

## Known caveats

- **Douglas coverage gap**: the county-wide delivery has 286 Tahoe-area records, but only 4
  are typed `1 - Culvert` (the rest are drop inlets, manholes, basins, Vortechs units). Either
  basin cross-drains are typed as drop inlets, or Tahoe-side culverts belong to the GIDs/NDOT;
  follow-up in `docs/jurisdiction_data_questions.md`.
- El Dorado attribute domains (`MATL_CODE` etc.) are undocumented - raw codes carried as `code N`.
- Placer material is ~99% null in the source; Placer 1-5 rating direction unconfirmed.
- 471 condition records lack an inspection date.
- Older jurisdiction + USFS culvert data exists for a coverage comparison (not yet integrated).

The full per-jurisdiction follow-up list is `docs/jurisdiction_data_questions.md`.

## Outputs and QA

Run log in `logs/`. QA report: `outputs/qa_culverts.csv` + `outputs/qa_by_jurisdiction.csv`
(key nulls/dupes, orphan condition rows, missing-attribute rates, bbox check). Current run
(clipped to the TRPA boundary, incl. legacy gap fill): 7,858 assets (6,232 from current
deliveries + 1,626 provisional legacy), 2,253 condition records, 0 orphans, 0 dup keys,
0 null geometries. 1,087 out-of-basin features dropped by the clip; 597 legacy points matched
existing assets within 25 m. Provisional adds are attribute-sparse (material ~21%, span ~18%);
legacy owner field says 99 USFS, 20 NDOT, ~150 Placer, 1,171 unknown.
