"""Shared I/O helpers for the climate pipeline: config loading, logger factory, manifest."""
import hashlib
import logging
import sys
from pathlib import Path

import yaml


def project_root() -> Path:
    """Return the climate pipeline root (parent of src/)."""
    return Path(__file__).resolve().parent.parent


def load_config(path: str = "config.yaml") -> dict:
    """Load config.yaml from the pipeline root."""
    with open(project_root() / path, "r") as f:
        return yaml.safe_load(f)


def load_secrets() -> None:
    """Load .env into os.environ if python-dotenv is available. All current
    sources are anonymous/public - this exists for convention and future keys."""
    try:
        from dotenv import load_dotenv
        load_dotenv(project_root() / ".env")
    except ImportError:
        pass


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Configured logger writing to console and a timestamped file in
    logs/<name>_<YYYY-MM-DD_HHMMSS>.log. Uses pd.Timestamp to avoid the
    datetime-name shadowing a successful arcpy import causes in notebooks.
    """
    import pandas as pd

    logs_dir = project_root() / "logs"
    logs_dir.mkdir(exist_ok=True)
    ts = pd.Timestamp.now().strftime("%Y-%m-%d_%H%M%S")

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()  # avoid duplicate handlers on notebook re-run

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    for h in (logging.StreamHandler(sys.stdout),
              logging.FileHandler(logs_dir / f"{name}_{ts}.log")):
        h.setFormatter(fmt)
        logger.addHandler(h)

    logger.info(f"Log file: {logs_dir / f'{name}_{ts}.log'}")
    return logger


def sha256_file(path, chunk=1 << 20) -> str:
    """SHA-256 of a local file, streamed."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def append_manifest(row: dict) -> None:
    """
    Append one download record to outputs/manifest.csv, replacing any prior row
    for the same local file. Expected keys: file, source_url, size_bytes,
    sha256, retrieved_date, notebook.
    """
    import pandas as pd

    manifest_path = project_root() / "outputs" / "manifest.csv"
    manifest_path.parent.mkdir(exist_ok=True)
    cols = ["file", "source_url", "size_bytes", "sha256", "retrieved_date", "notebook"]
    new = pd.DataFrame([{c: row.get(c) for c in cols}])
    if manifest_path.exists():
        m = pd.read_csv(manifest_path)
        m = m[m["file"] != row.get("file")]
        m = pd.concat([m, new], ignore_index=True)
    else:
        m = new
    m.to_csv(manifest_path, index=False)
