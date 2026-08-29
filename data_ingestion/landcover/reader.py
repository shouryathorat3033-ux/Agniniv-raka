"""
HEATWATCH — Land Cover Reader / Validator
==========================================
Reads and validates a land-cover raster (GeoTIFF).
Does NOT load raster pixels into PostgreSQL.

Supported datasets:
  ESA WorldCover 10m 2021 (v200)
  MODIS MCD12Q1 (500m)
  Any single-band integer GeoTIFF

Key functions:
  open_raster()         — open raster, validate CRS and band count
  validate_raster()     — full validation report
  read_raster_metadata()— return metadata dict for manifests
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import rasterio
from rasterio.crs import CRS

from common.exceptions import DatasetNotFoundError, DatasetReadError, InvalidCRSError
from common.logging_config import get_logger

log = get_logger(__name__)


def open_raster(path: Path) -> rasterio.DatasetReader:
    """
    Open a GeoTIFF land-cover raster.
    Caller must close the returned dataset.
    """
    if not path.exists():
        raise DatasetNotFoundError(f"Land-cover raster not found: {path}")
    if path.suffix.lower() not in (".tif", ".tiff"):
        raise DatasetReadError(f"Expected a GeoTIFF (.tif), got: {path.suffix}")

    try:
        ds = rasterio.open(path)
    except Exception as exc:
        raise DatasetReadError(f"Cannot open raster {path}: {exc}") from exc

    log.info("landcover.reader.opened", path=str(path), crs=str(ds.crs), shape=(ds.height, ds.width))
    return ds


def read_raster_metadata(path: Path) -> dict[str, Any]:
    """
    Read metadata from a land-cover raster without loading pixel data.
    Returns a dict suitable for provenance manifests.
    """
    with open_raster(path) as ds:
        meta: dict[str, Any] = {
            "path":         str(path),
            "driver":       ds.driver,
            "width":        ds.width,
            "height":       ds.height,
            "band_count":   ds.count,
            "crs":          str(ds.crs),
            "crs_epsg":     ds.crs.to_epsg() if ds.crs else None,
            "transform":    list(ds.transform),
            "bounds": {
                "left":     ds.bounds.left,
                "bottom":   ds.bounds.bottom,
                "right":    ds.bounds.right,
                "top":      ds.bounds.top,
            },
            "dtype":        ds.dtypes[0],
            "nodata":       ds.nodata,
            "res_x":        abs(ds.transform.a),
            "res_y":        abs(ds.transform.e),
        }
    return meta


def validate_raster(path: Path) -> list[str]:
    """
    Validate a land-cover raster.
    Returns list of error/warning strings. Empty = valid.
    """
    errors: list[str] = []

    try:
        with open_raster(path) as ds:
            if ds.crs is None:
                errors.append("Raster has no CRS defined")
            elif ds.crs.to_epsg() not in (4326, 32632, 32643):
                # Allow WGS84 and common UTM zones; reprojection is supported
                epsg = ds.crs.to_epsg()
                errors.append(
                    f"CRS EPSG:{epsg} — confirm this is correct and that reprojection "
                    "to EPSG:4326 is possible before computing lookups."
                )
            if ds.count < 1:
                errors.append("Raster has zero bands")
            if ds.width == 0 or ds.height == 0:
                errors.append(f"Raster has zero dimensions: {ds.width}x{ds.height}")
    except (DatasetNotFoundError, DatasetReadError) as exc:
        errors.append(str(exc))
    except Exception as exc:
        errors.append(f"Raster validation error: {exc}")

    return errors
