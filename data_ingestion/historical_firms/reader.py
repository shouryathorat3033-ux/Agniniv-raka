"""
HEATWATCH — Historical FIRMS Reader
=====================================
Reads historical NASA FIRMS CSV files (may be large — multi-year archives).
Yields chunks of rows instead of loading the full file into memory.

Historical FIRMS uses the same CSV format as current FIRMS.
The only difference is that acquisition_time will be older.

Loads into: hotspots (same table as current FIRMS).
There is NO separate historical table.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pandas as pd

from common.exceptions import DatasetNotFoundError, DatasetReadError, MissingRequiredColumnsError
from common.logging_config import get_logger
from config.datasets import FIRMS_COLUMN_ALIASES, FIRMS_REQUIRED_COLUMNS

log = get_logger(__name__)


def read_historical_firms_chunks(
    path: Path,
    chunk_size: int = 50_000,
) -> Iterator[pd.DataFrame]:
    """
    Yield successive DataFrame chunks from a historical FIRMS CSV.
    Avoids loading multi-GB files into memory all at once.

    Parameters
    ----------
    path       : Path to one historical FIRMS CSV file.
    chunk_size : Number of rows per chunk.

    Yields
    ------
    pd.DataFrame chunks with normalized column names.
    """
    if not path.exists():
        raise DatasetNotFoundError(f"Historical FIRMS file not found: {path}")

    log.info(
        "historical_firms.reader.start",
        path=str(path),
        size_bytes=path.stat().st_size,
        chunk_size=chunk_size,
    )

    try:
        reader = pd.read_csv(
            path,
            dtype=str,
            low_memory=False,
            chunksize=chunk_size,
            encoding="utf-8",
        )
    except Exception as exc:
        raise DatasetReadError(f"Cannot open historical FIRMS CSV {path}: {exc}") from exc

    chunk_num = 0
    required_norm = {FIRMS_COLUMN_ALIASES.get(c, c) for c in FIRMS_REQUIRED_COLUMNS}

    for chunk in reader:
        chunk_num += 1
        # Normalize column names
        chunk.columns = [c.strip().lower() for c in chunk.columns]
        rename_map = {
            col: FIRMS_COLUMN_ALIASES[col]
            for col in chunk.columns
            if col in FIRMS_COLUMN_ALIASES
        }
        chunk = chunk.rename(columns=rename_map)

        # Check required columns on first chunk only
        if chunk_num == 1:
            actual = set(chunk.columns)
            missing = required_norm - actual
            if missing:
                raise MissingRequiredColumnsError(
                    f"Historical FIRMS file {path.name} missing required columns: "
                    f"{sorted(missing)}"
                )

        log.debug(
            "historical_firms.reader.chunk",
            chunk=chunk_num,
            rows=len(chunk),
        )
        yield chunk

    log.info("historical_firms.reader.done", chunks=chunk_num, path=str(path.name))


def list_historical_files(directory: Path, pattern: str = "*.csv") -> list[Path]:
    """Return all historical FIRMS CSV files sorted by name (chronological)."""
    if not directory.exists():
        raise DatasetNotFoundError(
            f"Historical FIRMS directory not found: {directory}"
        )
    files = sorted(directory.glob(pattern))
    log.info(
        "historical_firms.reader.listed",
        directory=str(directory),
        count=len(files),
    )
    return files
