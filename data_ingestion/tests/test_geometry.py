"""
Tests for common/geometry.py
Unit tests — no database or PostGIS required.
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.geometry import (
    validate_coordinates,
    make_point_wkt,
    make_point,
    is_valid_wkt,
)
from common.exceptions import InvalidCoordinatesError, GeometryError


def test_make_point_wkt_valid():
    wkt = make_point_wkt(72.8, 21.2)
    assert wkt == "POINT(72.8 21.2)"


def test_make_point_wkt_swapped():
    # X=lon, Y=lat — ensure correct ordering
    wkt = make_point_wkt(lon=77.5, lat=28.6)
    assert "POINT(77.5 28.6)" == wkt


def test_make_point_wkt_invalid_lat():
    with pytest.raises(InvalidCoordinatesError):
        make_point_wkt(72.8, 95.0)  # lat out of range


def test_make_point_wkt_invalid_lon():
    with pytest.raises(InvalidCoordinatesError):
        make_point_wkt(200.0, 21.2)  # lon out of range


def test_make_point():
    pt = make_point(77.5, 28.6)
    assert abs(pt.x - 77.5) < 1e-9
    assert abs(pt.y - 28.6) < 1e-9


def test_make_point_origin():
    pt = make_point(0.0, 0.0)
    assert pt.x == 0.0
    assert pt.y == 0.0


def test_validate_coordinates_valid():
    # Should not raise
    validate_coordinates(21.2, 72.8)


def test_validate_coordinates_invalid_lat():
    with pytest.raises(InvalidCoordinatesError):
        validate_coordinates(91.0, 72.8)


def test_validate_coordinates_invalid_lon():
    with pytest.raises(InvalidCoordinatesError):
        validate_coordinates(21.2, 181.0)


def test_is_valid_wkt_point():
    assert is_valid_wkt("POINT(77.5 28.6)") is True


def test_is_valid_wkt_polygon():
    assert is_valid_wkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))") is True


def test_is_valid_wkt_invalid():
    assert is_valid_wkt("NOT A WKT") is False


def test_is_valid_wkt_empty():
    assert is_valid_wkt("") is False


def test_is_valid_wkt_none():
    assert is_valid_wkt(None) is False  # type: ignore
