# protect-climate-data

Climate projection inputs for the PROTECT Task 3 Risk Index (Lake Tahoe Basin, CA/NV).
Downloads bbox subsets of LOCA2 6 km (five-GCM General Use ensemble), UCLA WRF
(wind, SWE, hourly precip; historical + SSP3-7.0), gridMET, and NOAA Atlas 14 point
DDF; clips to the buffered TRPA boundary; and produces per-scenario, per-horizon
summary grids (EPSG:26910) and CSV tables for the vulnerability assessment.
LOCA2-Hybrid is the same 1/16 deg grid CA-only (not 3 km) and is disabled as redundant.

Run the numbered notebooks in `notebooks/` in order with the `arcgispro-py3` interpreter
(see `environment.md` for extra packages). Configuration in `config.yaml`; the extraction
spec (scenarios, ensemble, metrics) is a placeholder pending consultant review - edits
land in `config.yaml` and the pipeline reruns. Methods and caveats in `docs/METHODS.md`;
validation status in `docs/CHANGELOG.md`. Downloaded data is never committed, and the
web page publish step is gated on human review of `outputs/projections_inline.json`.

Lives inside the `PROTECT` repo for now; structured to lift out as a standalone
`protect-climate-data` repo when the two-repo split happens.
