# Methods: protect-climate-data

**Task:** PROTECT Task 3 - climate projection inputs for the Risk Index / vulnerability assessment
**Pipeline root:** `PROTECT/climate/` | **Config:** `climate/config.yaml`
**Last reviewed:** 2026-07-29

## Purpose

Acquire and prepare downscaled climate projection data for the Lake Tahoe Basin (bi-state
CA/NV) plus a 10 km buffer covering adjacent highway corridors. Outputs are per-scenario,
per-horizon summary grids and tables that feed the Task 3 Risk Index exposure scoring.
**ICF consumes the processed summaries in `data/processed/` and `outputs/`, not the raw
downloads** - raw subsets exist only for reproducibility and are never committed or shared.

## Study area

TRPA boundary (Boundaries MapServer layer 4) buffered 10 km outward, in EPSG:26910.
Server-side subsetting uses bbox lon -120.5..-119.5, lat 38.5..39.5; local clip to the
buffered boundary follows. Final grids in EPSG:26910; gridded intermediates also kept in
native lat/lon.

## Data sources

| # | Source | Resolution | Variables | Period | Access | Notebook |
|---|---|---|---|---|---|---|
| 1 | LOCA2 North America (CMIP6, Scripps) | ~6 km (1/16 deg) | pr, tasmax, tasmin (daily) | 1950-2014 hist + SSP2-4.5 / SSP3-7.0 to 2100 | HTTPS/OPeNDAP subset, bbox only | `01_extract_loca2` |
| 2 | Cal-Adapt Analytics Engine (`s3://cadcat`, anonymous) | LOCA2-Hybrid 3 km; WRF 9 km (wind) | pr, tasmax, tasmin; u10/v10 | same | xarray + s3fs + zarr, bbox subset | `02_extract_caladapt` |
| 3 | gridMET (climatologylab.org) | 4 km | pr, tmmx, tmmn, vs (daily) | 1979-present | THREDDS/OPeNDAP subset | `03_extract_gridmet` |
| 4 | NOAA Atlas 14 (NWS PFDS) | point DDF | precip depth-duration-frequency | stationary | point CSV API | `04_extract_atlas14` |

Ensemble: Cal-Adapt **General Use Projections** 5-GCM starter set (ACCESS-CM2, EC-Earth3,
FGOALS-g3, MIROC6, MPI-ESM1-2-HR r3i1p1f1), scalable in config to the full 15-model
LOCA2-Hybrid ensemble selected for performance over California.

**LOCA2 access, verified 2026-07-29**: region-split daily NetCDFs on
`cirrus.ucsd.edu/~pierce/LOCA2/CONUS_regions_split/<GCM>/west/0p0625deg/<member>/<scenario>/<var>/`,
version `v20240915`; historical is one 1950-2014 file, each SSP is three chunks
(2015-2044 / 2045-2074 / 2075-2100). Full plan = 105 files, ~60 GB remote; HTTP
byte-range subsetting (fsspec + h5netcdf) pulls only the bbox window. Member note:
MPI-ESM1-2-HR's General Use run r3i1p1f1 covers historical + ssp370 only - ssp245 falls
back to r1i1p1f1 (notebook 01 logs the fallback; QA reports members used).

## The 6 km vs 3 km bi-state decision

LOCA2-Hybrid 3 km (Cal-Adapt) is the finer product but **covers California only** - the NV
side of the basin (Incline Village, east shore, Kingsbury, Mt Rose corridor) falls outside
it. LOCA2 North America 6 km covers the full bi-state study area. Decision: **6 km is the
primary analysis grid** so every asset scores from one consistent product; 3 km is pulled
for the CA side as a sensitivity/verification layer, and the NV gap is the documented
reason it cannot be primary. Revisit if a bi-state 3 km product publishes.

## Processing (notebook 05_transform)

1. Clip all grids to the 10 km buffered boundary.
2. Per scenario x horizon (2020-2049, 2040-2069, 2070-2099 vs 1981-2010 baseline):
   total annual precip; extreme precip (99th percentile daily, max 1-day, max 3-day);
   mean/max tasmax; mean tasmin.
3. Ensemble median + 10th/90th percentile across configured GCMs.
4. Write GeoTIFF (EPSG:26910, via osgeo.gdal) + NetCDF (lat/lon) to `data/processed/`;
   small CSV summary to `outputs/` for human review.

## QA (notebook 06_qa)

- Grid coverage check: no clipped-off NV cells inside the buffered boundary.
- Unit sanity: precip in mm/day (LOCA2 native kg m-2 s-1 x 86400 conversion asserted),
  temperatures in degC (K conversion asserted).
- Completeness matrix: every configured GCM x scenario x variable present.
- Download manifest (file, source URL, size, checksum, retrieved date) to
  `outputs/manifest.csv`.

## Known caveats

- **FGOALS-g3 publishes no wind variables** on the cadcat LOCA2 mirror - the daily wind
  (`wspeed`) ensemble is 4 models, not 5. Precip/temp remain 5-model.

- LOCA2-Hybrid 3 km has no Nevada coverage (see decision above).
- WRF wind is dynamically downscaled from a smaller GCM subset than LOCA2 - ensemble
  stats for wind are not directly comparable to the precip/temp ensemble.
- NOAA Atlas 14 is stationary (no climate-change adjustment); Atlas 15 (non-stationary)
  is pilot-only as of mid-2026 - stub in `04_extract_atlas14` with the status URL.
- gridMET is a gridded interpolation of stations; sparse high-elevation coverage in the
  basin means mountain precip/wind carry extra uncertainty.

## Changelog

See `CHANGELOG.md`.
