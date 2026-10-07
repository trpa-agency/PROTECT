# Methods: Tahoe Culvert Layer + Condition Table

**Task:** PROTECT 3.3 - asset layer (culverts) for the Risk Index Tool
**Pipeline:** `notebooks/culvert_layer_engineering.ipynb` | **Config:** `config.yaml`
**Last reviewed:** 2026-10-07 (NDOT integration)

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
| NDOT (restricted) | SAM21 statewide export `NDOT_Culverts.gdb`, read in place from F: by `scripts/ndot_culverts.py` (not by the notebook; see below) | 1,493 basin pipes + 12 reinforced concrete boxes -> 1,475 after status drops, midpoints | 1,307 inspections (2013-2026) on 877 assets: Good/Fair/Poor overall rating (78 rated), blockage percent (701), pavement / end-structure / erosion sub-ratings |
| TRPA Legacy | `F:\...\PROTECT_analysis\Assets.gdb\Tahoe_Culvert` (read-only prior compilation, incl. USFS forest roads) | 2,223 basin points; 1,626 unmatched added as `TRPA Legacy (provisional)` | Good/Fair/Poor text -> 162 provisional records |

## Key decisions

- **Key:** `culvert_id = "<jurisdiction>|<source_id>"`; original IDs preserved, repeats suffixed `-2`, `-3`.
- **CRS:** everything reprojected to EPSG:26910 (NAD83 / UTM 10N).
- **Basin clip:** features outside the TRPA boundary (Boundaries MapServer layer 4) are dropped,
  with their condition records; dropped rows listed in `outputs/clipped_out_of_basin.csv`.
  Current run drops 1,087 records: Douglas County 854 of 858 (their delivery is county-wide;
  the Tahoe-area subset is small, see caveats), Placer County 187 of 660 (28 percent - their
  gdb extends past the basin boundary), El Dorado County 43, Caltrans 3. If a jurisdiction
  asks where their records went, the clip is the answer.
- **Lines to points:** representative point per `run.line_to_point` (default midpoint);
  `geom_source` records the derivation.
- **Ratings stay raw.** Each condition record carries the jurisdiction's own value plus a
  `condition_scheme` note; no cross-jurisdiction normalization until scale semantics are confirmed.
- **Washoe condition:** the delivered `condition` field is uniformly 0; structural/blockage
  subscores and `perc_full` carry the signal.
- **Caltrans:** one culvert per `SYSNO` (segments summed for length, geometry at first inlet).
- **Legacy gap fill:** each point in the prior TRPA compilation is matched to the nearest new
  asset within `run.legacy_match_m` (25 m). For assets ingested from line sources the match
  tests distance to the full original line, not the collapsed representative point (midpoint
  matching under-matches long pipes and inflates provisional adds with duplicates). Unmatched
  points join the layer as jurisdiction `TRPA Legacy (provisional)` with a PROVISIONAL comment;
  condition history on matched points is re-parented onto the surviving asset. Match status per
  legacy point: `outputs/legacy_comparison.csv`. Note the published counts below predate the
  line-geometry match; a rerun will likely reduce the 1,626 provisional adds somewhat.

## NDOT integration (restricted source)

The NDOT export is shared under a sensitive/restricted data sharing agreement (executed
Aug. 12, 2026, term through Dec. 31, 2027, one named Data Steward). It therefore bypasses the
notebook: the notebook writes `data/processed/culverts.gpkg`, which is git-tracked and served
by GitHub Pages. Instead `scripts/load_culverts_gdb.py` calls `scripts/ndot_culverts.py`,
which reads the export in place from TRPA storage, standardizes it in memory, and the loader
appends it on the way into the analysis geodatabase. QA CSVs go to `ndot.work_dir` on F:;
the repo-side snap QA excludes NDOT rows. Nothing NDOT may appear on a page or in a public
service; segment-level aggregates are allowed with NDOT attribution and NDOT review.

- **Scope:** the `Pipe` and `Reinforced_Concrete_Box` layers and their inspection tables.
  Drainage inlets (993), manholes (257), treatment structures (378), channels, and basins
  in the basin are water-quality assets and stay out, consistent with the scope note.
- **Status filter:** `Abandoned`, `Relinquished`, `Removed`, `Replaced`, `Marked for Deletion`
  are dropped (30 basin pipes).
- **feature_type:** the SAM subtype (Storm Drain / Culvert / Down Drain / ...) is blank on
  1,460 of 1,493 basin pipes, so: subtype when present (41 culverts); otherwise a pipe that
  intersects a `Streets_Network_Tahoe` centerline is a culvert (494) unless both ends are
  manholes, a storm-drain trunk run (8); everything else is a stormwater pipe (920). Boxes
  are all culverts (12). The rule applied is written into `comments` (`class <rule>`), so
  the split can be audited and redone if NDOT confirms the Identification prefixes.
- **Key:** `culvert_id = "NDOT|<AssetID>"`, falling back to `Identification` (125 pipes lack
  an AssetID) and then `GlobalID` (55 lack both). The SAM `GlobalID` is kept in `comments`
  for joins to future exports.
- **Dimensions:** `Diameter_in` for circular pipes, `Width_in` x `Height_in` otherwise;
  spans above `ndot.max_diameter_in` (144) are nulled (one 6,300 in. record). Boxes use
  `Width_ft` x `Height_ft` in inches. `Length_ft` from the source, else the projected
  geometry length (flagged in `comments`).
- **Material:** SAM domain values as delivered; `Other (See Notes)` resolves to HDPE or
  cured-in-place lining when the notes say so (165 of 170).
- **Road:** `road_name` carries the NDOT route id and milepost (`57WA MP 8.29`); route ids
  are not yet decoded to highway names (question for NDOT).
- **Condition:** one record per inspection visit. `condition_rating` is the SAM overall
  Good/Fair/Poor (blank on 94 percent of visits), `blockage_pct` the 0/25/50/75/100
  blockage, `structural_cond` a compact string of the pavement, stabilization, end
  structure, joint separation, overtopping, and erosion sub-ratings, `maintenance_need`
  the maintenance / activities flags. Dates before `ndot.min_inspection_year` are nulled
  (one 1899 placeholder).
- **Legacy dedupe:** provisional legacy points within `run.legacy_match_m` (25 m) of an
  NDOT pipe or box line are dropped as superseded (141 points, listed in
  `legacy_superseded_by_ndot.csv` in the work dir).

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
(key nulls/dupes, orphan condition rows, missing-attribute rates, bbox check). Current
notebook run (clipped to the TRPA boundary, incl. legacy gap fill, public sources only):
7,858 assets (6,232 from current deliveries + 1,626 provisional legacy), 2,253 condition
records, 0 orphans, 0 dup keys, 0 null geometries. 1,087 out-of-basin features dropped by the
clip; 597 legacy points matched existing assets within 25 m. Provisional adds are
attribute-sparse (material ~21%, span ~18%); legacy owner field says 99 USFS, 20 NDOT,
~150 Placer, 1,171 unknown.

Analysis geodatabase load (`scripts/load_culverts_gdb.py`, 2026-10-07, with NDOT): 9,192
assets (7,858 public minus 141 legacy points superseded by NDOT, plus 1,475 NDOT) and 3,541
condition records; 2,983 assets have at least one condition record; 8,651 snapped to a road
segment within 50 m (497 of the 541 unsnapped are provisional legacy points on forest roads).
