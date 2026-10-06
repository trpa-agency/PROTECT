# Changelog

## 2026-07-30
- html/debris-flow.html v0.1 published: reference page (Calcite + AG Grid + Plotly,
  TRPA brand) covering the analysis plan, wildcat workflow, input mapping, scenarios,
  Atlas 14 design-storm chart, and open decisions. Cross-linked from index.html and
  climate-data.html.
- Finding recorded: basin 2-yr 15-min intensity (31.6 mm/hr) exceeds three of the four
  USGS default I15 values; Tahoe-specific design storms are required.

## 2026-07-29
- Initial scaffold: config.yaml, src/io.py, environment.md, notebooks/01_wildcat_scoping.ipynb.
- Tool verified: USGS wildcat 1.1.1 (Python >= 3.11; pfdf >= 3.0; installs from the
  USGS GitLab package registry, not pypi.org). Dedicated conda env planned - wildcat
  needs rasterio/fiona, which are prohibited in arcgispro-py3.
- Scenario framing recorded: (1) validation run on a real fire (Caldor 2021 or
  Angora 2007), (2) pre-fire planning run with constant burn severity following USGS
  pre-fire assessment practice, (3) design storms from the climate pipeline's
  Atlas 14 15-minute DDF extract, climate-adjusted later.
