"""
HEATWATCH — Industrial Facility Reader
=======================================
Reads external industrial facility databases.

Supported formats:
  .csv     — CSV with latitude/longitude columns
  .geojson — GeoJSON FeatureCollection
  .gpkg    — GeoPackage
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from common.exceptions import DatasetNotFoundError, DatasetReadError, UnsupportedFormatError
from common.logging_config import get_logger

log = get_logger(__name__)

SUPPORTED = {".csv", ".geojson", ".json", ".gpkg"}


def read_industrial_file(path: Path) -> gpd.GeoDataFrame:
    """
    Read an industrial facility file into a GeoDataFrame (EPSG:4326).
    For CSV files, expects 'latitude'/'lat' and 'longitude'/'lon'/'long' columns.
    """
    if not path.exists():
        raise DatasetNotFoundError(f"Industrial facility file not found: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED:
        raise UnsupportedFormatError(
            f"Unsupported format {ext!r}. Supported: {sorted(SUPPORTED)}"
        )

    log.info("industrial.reader.reading", path=str(path))

    try:
        if ext == ".csv":
            df = pd.read_csv(path, dtype=str, low_memory=False, encoding="utf-8")
            # Flexible coordinate column detection
            df.columns = [c.strip().lower() for c in df.columns]
            lat_col = next((c for c in df.columns if c in ("latitude", "lat")), None)
            lon_col = next((c for c in df.columns if c in ("longitude", "lon", "long")), None)
            if not lat_col or not lon_col:
                raise DatasetReadError(
                    f"CSV {path.name} has no latitude/longitude columns. "
                    f"Found: {list(df.columns)}"
                )
            df = df.dropna(subset=[lat_col, lon_col])
            df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
            df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
            df = df.dropna(subset=[lat_col, lon_col])
            gdf = gpd.GeoDataFrame(
                df,
                geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
                crs="EPSG:4326",
            )
            # Standardize column names
            if lat_col != "latitude":
                gdf = gdf.rename(columns={lat_col: "latitude"})
            if lon_col != "longitude":
                gdf = gdf.rename(columns={lon_col: "longitude"})
        else:
            gdf = gpd.read_file(path)
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            elif gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs("EPSG:4326")

    except (DatasetReadError, UnsupportedFormatError):
        raise
    except Exception as exc:
        raise DatasetReadError(f"Cannot read industrial file {path}: {exc}") from exc

    log.info("industrial.reader.done", rows=len(gdf), columns=list(gdf.columns))
    return gdf
