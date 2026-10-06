# Environment

**Do NOT use `arcgispro-py3` for this pipeline.** wildcat depends on `rasterio` and
`fiona`, which must never be installed into the Pro environment (they carry their own
GDAL and break arcpy's; see the climate pipeline's environment.md for the user-site
numpy incident). wildcat's own docs also strongly recommend a clean environment.

wildcat requires Python >= 3.11, < 4 (verified 2026-07-29, wildcat 1.1.1).

## Create the dedicated environment (not yet done)

Using the conda that ships with ArcGIS Pro, created in the user profile so no admin
rights are needed:

```
"C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\conda.exe" create -y -p %USERPROFILE%\.conda\envs\wildcat -c conda-forge python=3.12 pip
```

Then install wildcat from the **USGS GitLab package registry** (the package named
`wildcat` on pypi.org is an unrelated quantum-annealing SDK):

```
%USERPROFILE%\.conda\envs\wildcat\python.exe -m pip install wildcat jupyterlab ipykernel pyyaml geopandas -i https://code.usgs.gov/api/v4/groups/859/-/packages/pypi/simple
```

(The GitLab registry forwards requests for packages it does not host to pypi.org, so
dependencies resolve normally. If that ever fails, rerun with
`--extra-index-url https://pypi.org/simple`.)

Register the kernel so the notebooks in `notebooks/` can select it:

```
%USERPROFILE%\.conda\envs\wildcat\python.exe -m ipykernel install --user --name wildcat --display-name "Python (wildcat)"
```

## What lands in the env

- `wildcat` 1.1.x (CLI `wildcat` + Python API `from wildcat import initialize, preprocess, assess, export`)
- `pfdf` >= 3.0 (assessment engine; also provides data acquisition helpers)
- `numpy`, `rasterio`, `fiona` (wildcat deps)
- `geopandas` (post-processing: intersect results with the road network)
- `jupyterlab`, `ipykernel`, `pyyaml` (notebook workflow + config loading)

## Verify

First cell of every notebook prints `sys.executable`; it must point at
`...\.conda\envs\wildcat\python.exe`, not the Pro env.
