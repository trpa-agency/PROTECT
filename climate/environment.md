# Environment

Uses the default ArcGIS Pro Python environment:
`C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe`

Already present (verified 2026-07-29): `xarray` 2024.11, `netCDF4` 1.6.4, `fsspec`,
`pandas`, `geopandas`, `pyyaml`, `requests`, GDAL Python bindings (`osgeo`, 3.10).

## Extra packages needed in arcgispro-py3

- `s3fs` - anonymous S3 reads of the Cal-Adapt `cadcat` bucket
- `zarr` - Zarr store access for cadcat holdings
- `h5netcdf` - HTTP byte-range subsetting of LOCA2 NetCDF4 files (h5py 3.10 already
  present); this is what keeps LOCA2 pulls at ~tens of MB instead of 306 MB/file
- `intake` + `intake-esm` (optional) - catalog browsing of cadcat; plain s3fs paths work without it

Installed 2026-07-29 via **pip --user** (conda cannot write to the Program Files env
without admin: `EnvironmentNotWritableError`):

```
"C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" -m pip install --user s3fs "zarr<3" h5netcdf
```

Packages land in `%APPDATA%\Python\Python311\site-packages` and are picked up by
arcgispro-py3 automatically. **Pin `zarr<3`**: zarr 3 drags in numpy >= 2.x to the user
site, which shadows the env's numpy 1.26 and breaks h5py/scipy/arcpy binary compat
(observed, then rolled back). If numpy ever appears in the user site, remove it:
`python -m pip uninstall -y numpy`.

## Do NOT install

- `rasterio` / `rioxarray` - conflicts with the GDAL that arcpy ships. GeoTIFF export
  uses the bundled `osgeo.gdal` bindings instead.
- `dask` extras - bundled dask is present but the pipeline stays single-threaded
  xarray per TRPA conventions (no distributed/Dask clusters).

## Notes

- OPeNDAP subsetting (gridMET THREDDS) works through the bundled `netCDF4`.
- arcpy is not required by this pipeline; nothing here touches an ArcGIS license.
