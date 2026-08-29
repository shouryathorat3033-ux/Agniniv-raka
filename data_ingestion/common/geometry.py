"""
HEATWATCH Data Ingestion — Geometry Utilities
=============================================
PostGIS-compatible geometry helpers using Shapely.
All geometries are WGS84 (EPSG:4326).

RULE: X = longitude, Y = latitude. Always.
Never swap coordinates.
"""
from __future__ import annotations

from typing import Any

import pyproj
from shapely import wkb, wkt
from shapely.geometry import Point, mapping, shape
from shapely.ops import transform

from common.exceptions import GeometryError, InvalidCoordinatesError

# ── Coordinate validation bounds ──────────────────────────────
LAT_MIN, LAT_MAX = -90.0, 90.0
LON_MIN, LON_MAX = -180.0, 180.0


def validate_coordinates(lat: float, lon: float) -> None:
    """
    Raise InvalidCoordinatesError if lat/lon are out of WGS84 range.
    Always: lat = Y axis, lon = X axis.
    """
    if not (LAT_MIN <= lat <= LAT_MAX):
        raise InvalidCoordinatesError(
            f"Latitude {lat!r} is outside valid range [{LAT_MIN}, {LAT_MAX}]"
        )
    if not (LON_MIN <= lon <= LON_MAX):
        raise InvalidCoordinatesError(
            f"Longitude {lon!r} is outside valid range [{LON_MIN}, {LON_MAX}]"
        )


def make_point_wkt(lon: float, lat: float) -> str:
    """
    Return a WKT POINT string for PostGIS insertion.
    X = longitude, Y = latitude.

    Example result: 'POINT(77.5 28.3)'
    """
    validate_coordinates(lat, lon)
    return f"POINT({lon} {lat})"


def make_point(lon: float, lat: float) -> Point:
    """Return a Shapely Point(lon, lat) — X first."""
    validate_coordinates(lat, lon)
    return Point(lon, lat)


def geojson_to_wkt(geojson_geometry: dict[str, Any]) -> str:
    """
    Convert a GeoJSON geometry dict to WKT string for PostgreSQL.
    Validates geometry is not empty before conversion.
    """
    try:
        geom = shape(geojson_geometry)
        if geom.is_empty:
            raise GeometryError("GeoJSON geometry is empty")
        return geom.wkt
    except Exception as exc:
        raise GeometryError(f"Failed to convert GeoJSON to WKT: {exc}") from exc


def reproject_wkt(wkt_str: str, from_crs: str, to_crs: str = "EPSG:4326") -> str:
    """
    Reproject a WKT geometry from from_crs to to_crs.
    Returns WKT in the target CRS.
    """
    try:
        transformer = pyproj.Transformer.from_crs(
            from_crs, to_crs, always_xy=True
        )
        geom = wkt.loads(wkt_str)
        reprojected = transform(transformer.transform, geom)
        return reprojected.wkt
    except Exception as exc:
        raise GeometryError(
            f"Failed to reproject geometry from {from_crs} to {to_crs}: {exc}"
        ) from exc


def is_valid_wkt(wkt_str: str) -> bool:
    """Return True if the WKT string parses to a valid, non-empty geometry."""
    try:
        geom = wkt.loads(wkt_str)
        return not geom.is_empty and geom.is_valid
    except Exception:
        return False


def shapely_to_geojson(geom: Any) -> dict[str, Any]:
    """Convert a Shapely geometry to a GeoJSON geometry dict."""
    return mapping(geom)
