# protect-climate-data

Climate projection inputs for the PROTECT Task 3 Risk Index (Lake Tahoe Basin, CA/NV).
Downloads bbox subsets of LOCA2 6 km, Cal-Adapt 3 km / WRF wind, gridMET, and NOAA
Atlas 14; clips to the buffered TRPA boundary; and produces per-scenario, per-horizon
summary grids (EPSG:26910) and CSV tables for the vulnerability assessment.

Run the numbered notebooks in `notebooks/` in order with the `arcgispro-py3` interpreter
(see `environment.md` for two extra packages). Configuration in `config.yaml`; methods
and caveats in `docs/METHODS.md`. Downloaded data is never committed.

Lives inside the `PROTECT` repo for now; structured to lift out as a standalone
`protect-climate-data` repo when the two-repo split happens.
