"""
HEATWATCH — OSM Reader
========================
Reads local/regional OSM extracts in GeoJSON, GeoPackage,
or CSV format. Does NOT download from OSM — reads local files only.

Supported formats:
  .geojson  — GeoJSON FeatureCollection
  .gpkg     — GeoPackage layer
  .json     — GeoJSON (same as .geojson)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

from common.exceptions import DatasetNotFoundError, DatasetReadError, UnsupportedFormatError
from common.logging_config import get_logger

log = get_logger(__name__)

SUPPORTED_EXTENSIONS = {".geojson", ".json", ".gpkg"}


def read_osm_file(path: Path, layer: str | None = None) -> gpd.GeoDataFrame:
    """
    Read a local OSM extract into a GeoDataFrame.

    Parameters
    ----------
    path  : Path to GeoJSON or GeoPackage file.
    layer : Optional layer name for GeoPackage files.

    Returns
    -------
    GeoDataFrame in EPSG:4326.

    Raises
    ------
    DatasetNotFoundError  : File does not exist.
    UnsupportedFormatError: File format not in SUPPORTED_EXTENSIONS.
    DatasetReadError      : File cannot be parsed.
    """
    if not path.exists():
        raise DatasetNotFoundError(f"OSM file not found: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(
            f"OSM file {path.name} has unsupported extension {ext!r}. "
            f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    log.info("osm.reader.reading", path=str(path), format=ext)

    try:
        kwargs: dict[str, Any] = {}
        if ext == ".gpkg" and layer:
            kwargs["layer"] = layer
        gdf = gpd.read_file(path, **kwargs)
    except Exception as exc:
        raise DatasetReadError(f"Cannot read OSM file {path}: {exc}") from exc

    # Reproject to WGS84 if needed
    if gdf.crs is None:
        log.warning("osm.reader.no_crs", path=str(path), action="assuming EPSG:4326")
        gdf = gdf.set_crs("EPSG:4326")
    elif gdf.crs.to_epsg() != 4326:
        log.info("osm.reader.reprojecting", from_crs=str(gdf.crs), to_crs="EPSG:4326")
        gdf = gdf.to_crs("EPSG:4326")

    log.info("osm.reader.done", path=str(path.name), rows=len(gdf))
    return gdf


def list_osm_files(directory: Path) -> list[Path]:
    """Return all supported OSM extract files in a directory."""
    if not directory.exists():
        raise DatasetNotFoundError(f"OSM directory not found: {directory}")
    files = [
        p for p in sorted(directory.iterdir())
        if p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    log.info("osm.reader.listed", directory=str(directory), count=len(files))
    return files
