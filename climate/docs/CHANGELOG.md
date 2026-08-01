# Changelog

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
