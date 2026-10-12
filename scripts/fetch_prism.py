"""Download the PRISM 1991-2020 annual precipitation normal (800 m, mm) for the regression
step of culvert_profile.py.

    python scripts/fetch_prism.py            # downloads profile.prism_url, unzips next to profile.prism_ppt
    python scripts/fetch_prism.py --force    # re-download

The zip holds a Cloud Optimized GeoTIFF plus ancillary files; the .tif is renamed to the
config path if PRISM's own file name differs. CONUS-wide, about 60 MB; clipped on the fly by
the zonal statistics, so no basin subset is made. Source: PRISM Climate Group, Oregon State
University, https://prism.oregonstate.edu (terms of use on that site; attribution required).
"""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

import requests

from va_common import get_logger, load_cfg


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    log = get_logger("fetch_prism")
    cfg = load_cfg()
    p = cfg["profile"]
    target = Path(p["prism_ppt"])
    url = p["prism_url"]
    if target.exists() and not args.force:
        log.info(f"Already present: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    zpath = target.parent / url.rsplit("/", 1)[-1]
    log.info(f"Downloading {url} -> {zpath}")
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(zpath, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    log.info(f"{zpath.stat().st_size / 1e6:.1f} MB; unzipping")
    with zipfile.ZipFile(zpath) as z:
        z.extractall(target.parent)
        names = z.namelist()
    tifs = [target.parent / n for n in names if n.lower().endswith(".tif")]
    if not tifs:
        raise SystemExit(f"No .tif in {zpath}: {names}")
    if tifs[0] != target:
        shutil.move(tifs[0], target)
        # keep sidecars (.xml, .prj, .stx) with the same stem
        for n in names:
            src = target.parent / n
            if src.exists() and src.suffix.lower() != ".tif" and src.stem == tifs[0].stem:
                shutil.move(src, target.with_suffix(src.suffix))
    log.info(f"PRISM annual precipitation normal ready: {target}")


if __name__ == "__main__":
    main()
