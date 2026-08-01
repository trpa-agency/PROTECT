# Assistant Session Notes - shared knowledge base

Cross-assistant handoff notes: durable, empirically-discovered facts from working sessions
in this repo. Deeper detail lives in the canonical docs listed per section - read those
before extending a pipeline. No secrets, no staff names, no commercial vendor names
(repo is served by GitHub Pages).

Last updated: 2026-07-31

## Culvert layer (canonical: docs/METHODS_culverts.md, docs/jurisdiction_data_questions.md)

- Basin-wide culvert layer + 1:many condition table built from 6 jurisdiction deliveries
  (raw data in C:\GIS\Culvert, not committed). Output: outputs/culverts.gdb (Culverts FC,
  CulvertCondition table, relationship class on culvert_id = "<jurisdiction>|<source_id>").
- 7,858 assets after clipping to the TRPA boundary + legacy gap fill; 2,253 condition
  records; QA clean. 1,626 assets are jurisdiction "TRPA Legacy (provisional)" from the
  prior compilation (F:\GIS\PROJECTS\Transportation\Protect\PROTECT_analysis\Assets.gdb,
  READ-ONLY) - largely USFS forest-road culverts; 25 m spatial match radius.
- Douglas County finding: their delivery is county-wide; the Tahoe area has exactly 286
  records but only 4 typed as culverts (rest are drop inlets/manholes/basins). Open
  question whether cross-drains hide under other types or belong to the GIDs/NDOT.
- Per-jurisdiction follow-up questions: docs/jurisdiction_data_questions.md.
- CSLT is a live AGOL FeatureServer (Stormwater layer 415006); it has at least one bogus
  installdate that overflows epoch-ms conversion - bound-check before pd.to_datetime.

## Climate pipeline (canonical: climate/docs/METHODS.md, CHANGELOG.md, environment.md)

- Working data source is the Cal-Adapt cadcat S3 bucket (anonymous):
  LOCA2 6 km daily at s3://cadcat/loca2/ucsd/<model>/<scen>/<member>/day/<var>/d03
  (western-US domain, covers NV-side Tahoe). Do not bulk-pull from cirrus.ucsd.edu
  (3.3 MB/s); it is fallback only.
- WRF (cadcat/wrf/ucla) has two layouts: access-cm2 + fgoals-g3 = raw hourly "1hr/all"
  stores; ec-earth3/miroc6/mpi-esm1-2-hr = per-variable stores incl. a day frequency
  (wspd10mean/max, snow=SWE, prec). Notebook 02 auto-detects. WRF = historical + ssp370
  only. Domain d02 = 9 km.
- Data gaps: FGOALS-g3 publishes no wind anywhere (wind ensemble = 4 models; precip/temp
  = 5). MPI-ESM1-2-HR ssp245 lacks the r3i1p1f1 General Use member (falls back r1i1p1f1).
  LOCA2-Hybrid is 6 km CA-only (not 3 km) - disabled as redundant.
- Environment (arcgispro-py3): s3fs + zarr<3 + h5netcdf installed via pip --user (conda
  cannot write the Program Files env). Never let pip put numpy in the user site (breaks
  h5py/arcpy binary compat); never install rasterio/rioxarray (GDAL conflict) - GeoTIFF
  export uses bundled osgeo.gdal.
- First full validation run complete (2026-07-31): 57 LOCA2 stores + 26 WRF files +
  gridMET + Atlas 14 (8 basin DDF points); 5-GCM ensemble metrics over 3 horizons vs
  1981-2010; results in climate/outputs/summary_climate_metrics.csv. Headline: annual
  precip roughly flat, max 1-day precip +9-15% (SSP3-7.0), basin-mean tasmin crosses
  0 degC by mid-century.
- The extraction spec (scenarios/ensemble/metrics) is a PLACEHOLDER pending consultant
  review; consultant edits land in climate/config.yaml and the pipeline reruns (~1-2 h).
  Consultant consumes processed summaries, never raw downloads; raw NDOT data stays
  TRPA-side per the data agreement.
- Publish gate: notebook 05 emits outputs/projections_inline.json; a human reviews, then
  pastes into html/climate-data.html at the /*__PROJECTIONS__*/ marker. Never auto-publish.

## Process rules for notebook pipelines (hard-won)

1. Never edit a .ipynb while nbconvert --execute runs on it - the final write clobbers
   concurrent edits silently.
2. Notebook cell ids are not stable across executions - re-read before targeted edits.
3. A successful arcpy import shadows the datetime name in the kernel - use pd.Timestamp
   in shared helpers.
4. Extract notebooks share outputs/manifest.csv (read-modify-write) - never run two
   extract notebooks concurrently; thread-lock manifest writes within one.
5. Temp/scratch dirs get wiped mid-session by cleaners - the repo is the only durable
   location for anything worth keeping.
