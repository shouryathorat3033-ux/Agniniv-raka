"""
HEATWATCH — Land Cover Lookup
================================
Provides point-based and buffer/window-based land-cover class lookup.
Used by the analytics pipeline when thermal_object coordinates are known.

These functions are reusable utilities — they do NOT insert into the database.
Callers (who have valid thermal_object_ids) pass results to the loader.

ESA WorldCover class codes → land_context column mapping:
  10  Tree cover      → tree_cover_score
  20  Shrubland       → shrubland_score
  30  Grassland       → grassland_score
  40  Cropland        → cropland_score
  50  Built-up        → built_up_score
  60  Bare/sparse veg → bare_land_score
  80  Permanent water → water_score
  90  Wetland         → grassland_score
  95  Mangroves       → tree_cover_score
 100  Moss/lichen     → bare_land_score
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.transform import rowcol

from common.exceptions import GeometryError, InvalidCRSError
from common.logging_config import get_logger
from config.datasets import ESA_WORLDCOVER_CLASSES, ESA_WORLDCOVER_CLASS_NAMES

log = get_logger(__name__)

# Default buffer radius for window sampling (metres converted to degrees approx)
DEFAULT_BUFFER_DEGREES = 0.01  # ~1 km at equator


def lookup_point(
    raster_path: Path,
    lon: float,
    lat: float,
) -> dict[str, Any]:
    """
    Read the land-cover class at a single point.

    Returns
    -------
    dict with keys:
      class_code   : int pixel value
      class_name   : str human-readable class name
      score_field  : str field name in land_context table (or None)
    """
    with rasterio.open(raster_path) as ds:
        _assert_geographic_crs(ds)
        try:
            row, col = rowcol(ds.transform, lon, lat)
            data = ds.read(1, window=rasterio.windows.Window(col, row, 1, 1))
            code = int(data[0, 0])
        except Exception as exc:
            raise GeometryError(f"Failed to lookup point ({lon},{lat}): {exc}") from exc

    class_info = ESA_WORLDCOVER_CLASSES.get(code, {"name": f"Unknown({code})", "score_field": None})
    return {
        "class_code":  code,
        "class_name":  class_info["name"],
        "score_field": class_info["score_field"],
    }


def lookup_buffer_window(
    raster_path: Path,
    lon: float,
    lat: float,
    buffer_degrees: float = DEFAULT_BUFFER_DEGREES,
) -> dict[str, Any]:
    """
    Sample land-cover pixels within a buffer around a point.
    Returns fractional scores for each land-cover class.

    This is the main function used to populate land_context columns.

    Returns
    -------
    dict with fractional scores matching land_context column names.
    Also includes dominant class info and pixel count.
    """
    with rasterio.open(raster_path) as ds:
        _assert_geographic_crs(ds)

        # Define bounding box of the buffer window
        left   = lon - buffer_degrees
        bottom = lat - buffer_degrees
        right  = lon + buffer_degrees
        top    = lat + buffer_degrees

        try:
            window = from_bounds(left, bottom, right, top, ds.transform)
            data   = ds.read(1, window=window)
        except Exception as exc:
            raise GeometryError(
                f"Failed to read buffer window around ({lon},{lat}): {exc}"
            ) from exc

    # Filter nodata / zero
    valid_pixels = data[data > 0]
    total        = len(valid_pixels)

    if total == 0:
        log.warning("landcover.lookup.no_valid_pixels", lon=lon, lat=lat)
        return _empty_scores()

    # Accumulate fractional scores per land_context field
    scores: dict[str, float] = {
        "tree_cover_score": 0.0,
        "shrubland_score":  0.0,
        "grassland_score":  0.0,
        "cropland_score":   0.0,
        "built_up_score":   0.0,
        "bare_land_score":  0.0,
        "water_score":      0.0,
    }

    unique, counts = np.unique(valid_pixels, return_counts=True)
    for code, cnt in zip(unique.tolist(), counts.tolist()):
        info = ESA_WORLDCOVER_CLASSES.get(code)
        if info and info["score_field"] and info["score_field"] in scores:
            scores[info["score_field"]] += cnt / total

    # Dominant class
    dominant_code = int(unique[counts.argmax()])
    dominant_name = ESA_WORLDCOVER_CLASS_NAMES.get(dominant_code, f"Unknown({dominant_code})")

    return {
        **scores,
        "land_cover_class": dominant_name,
        "pixel_count":      total,
        "buffer_degrees":   buffer_degrees,
    }


def _assert_geographic_crs(ds: rasterio.DatasetReader) -> None:
    if ds.crs is None:
        raise InvalidCRSError("Raster has no CRS — cannot perform geographic lookup")
    if not ds.crs.is_geographic:
        raise InvalidCRSError(
            f"Raster CRS {ds.crs} is not geographic. Reproject to EPSG:4326 before lookup."
        )


def _empty_scores() -> dict[str, Any]:
    return {
        "land_cover_class": None,
        "tree_cover_score": None,
        "shrubland_score":  None,
        "grassland_score":  None,
        "cropland_score":   None,
        "built_up_score":   None,
        "bare_land_score":  None,
        "water_score":      None,
        "pixel_count":      0,
    }
