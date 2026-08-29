"""
HEATWATCH — FIRMS Reader
========================
Reads NASA FIRMS CSV files into a pandas DataFrame.
Applies column alias normalization from config/datasets.py.
Does NOT validate or transform — only reads and renames columns.

Supported products:
  MODIS (Terra/Aqua)       — fire_archive_M-C61_*.csv
  VIIRS SNPP               — fire_archive_V1*.csv
  VIIRS NOAA-20 (J1)       — fire_archive_J1V*.csv
  Any FIRMS-format CSV with at least latitude, longitude,
  acq_date, acq_time columns.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from common.exceptions import DatasetNotFoundError, DatasetReadError, MissingRequiredColumnsError
from common.logging_config import get_logger
from config.datasets import FIRMS_COLUMN_ALIASES, FIRMS_REQUIRED_COLUMNS

log = get_logger(__name__)


def read_firms_csv(path: Path) -> pd.DataFrame:
    """
    Read a FIRMS CSV file and normalize column names.

    Parameters
    ----------
    path : Path
        Path to a single FIRMS CSV file.

    Returns
    -------
    pd.DataFrame
        DataFrame with normalized column names.
        All original columns preserved; aliases renamed.

    Raises
    ------
    DatasetNotFoundError    : File does not exist.
    DatasetReadError        : File cannot be parsed.
    MissingRequiredColumnsError : Required columns absent after alias mapping.
    """
    if not path.exists():
        raise DatasetNotFoundError(f"FIRMS file not found: {path}")

    log.info("firms.reader.reading", path=str(path), size_bytes=path.stat().st_size)

    try:
        df = pd.read_csv(
            path,
            dtype=str,          # read all as str; type conversion in normalizer
            low_memory=False,
            encoding="utf-8",
        )
    except Exception as exc:
        raise DatasetReadError(f"Cannot read FIRMS CSV {path}: {exc}") from exc

    if df.empty:
        log.warning("firms.reader.empty_file", path=str(path))
        return df

    # Normalize column names: strip whitespace + lowercase
    df.columns = [c.strip().lower() for c in df.columns]

    # Apply alias mapping
    rename_map = {
        col: FIRMS_COLUMN_ALIASES[col]
        for col in df.columns
        if col in FIRMS_COLUMN_ALIASES
    }
    df = df.rename(columns=rename_map)

    # Check required columns exist
    actual = set(df.columns)
    # Use normalized names for required check
    required_norm = {FIRMS_COLUMN_ALIASES.get(c, c) for c in FIRMS_REQUIRED_COLUMNS}
    missing = required_norm - actual
    if missing:
        raise MissingRequiredColumnsError(
            f"FIRMS file {path.name} is missing required columns: {sorted(missing)}. "
            f"Available columns: {sorted(actual)}"
        )

    log.info(
        "firms.reader.done",
        path=str(path.name),
        rows=len(df),
        columns=list(df.columns),
    )
    return df


def list_firms_files(directory: Path, pattern: str = "*.csv") -> list[Path]:
    """
    Return all CSV files in a directory (non-recursive).
    """
    if not directory.exists():
        raise DatasetNotFoundError(f"FIRMS directory not found: {directory}")
    files = sorted(directory.glob(pattern))
    log.info("firms.reader.listed_files", directory=str(directory), count=len(files))
    return files
