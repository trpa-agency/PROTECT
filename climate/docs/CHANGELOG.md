# Changelog

## 2026-08-17
- New notebook 07_wrf_hourly_intensity: max_1hr_precip metric from the WRF hourly
  subsets (d02 9 km, 3 models - ACCESS-CM2, EC-Earth3, MIROC6 - ssp370 only).
  Mean water-year (Sep-Aug) max 1-hr rate for the baseline + 3 horizons; change
  factors computed per model against its own baseline, then ensembled (median/
  p10/p90). Outputs: 21 NetCDFs + GeoTIFFs (nearest-resampled regular grid) in
  data/processed/, outputs/summary_wrf_i1h.csv, outputs/wrf_i1h_grid.geojson
  (54 cell polygons).
- Basin-mean change factors: x1.12 (2020-2049), x1.16 (2040-2069), x1.33
  (2070-2099) - consistent with the d03 2-model +37 percent late-century figure
  on the storm events page.
- wrf_i1h_grid.geojson embedded in html/tahoe-precip-events.html as the map tab's
  "Future 1-hr intensity (WRF)" layer (change-factor symbology, horizon selector,
  per-cell popup with mm/hr, CSV export). DRAFT pending human review of the
  numbers - same review gate as the projections payload.
- climate-data.html metrics table: sub-daily intensity row updated (1-hr computed;
  3-hr/6-hr still pending).

## 2026-07-29 (later)
- LOCA2 source switched to the cadcat S3 Zarr mirror (western-US domain, covers NV);
  cirrus HTTP demoted to fallback. wspeed added to the variable list.
- WRF extract rebuilt for the real store layout: hourly precip (RAINC+RAINNC diff),
  daily SWE, daily wind; ssp370-only asymmetry documented.
- html/climate-data.html v0.2: added Use in Task 3 narrative tab and Projections tab
  (Plotly; pending until reviewed pipeline output is pasted). 05_transform now emits
  outputs/projections_inline.json for that manual publish step.

## 2026-07-29
- Initial scaffold: config.yaml, src/io.py, environment.md, METHODS.md.
- Ensemble set to Cal-Adapt General Use Projections (5 GCMs), full 15-model list in config.
- Decision recorded: LOCA2 6 km is the primary bi-state grid; 3 km CA-only as sensitivity.
