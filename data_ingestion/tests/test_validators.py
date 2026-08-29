"""
Tests for common/validators.py
All unit tests — no database required.
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.validators import (
    validate_latitude,
    validate_longitude,
    validate_coordinates,
    validate_positive_float,
    validate_confidence_range,
    validate_not_empty,
    check_required_columns,
)


# ── Latitude ──────────────────────────────────────────────────
@pytest.mark.parametrize("lat,expected_errors", [
    (0.0,    []),
    (90.0,   []),
    (-90.0,  []),
    (45.5,   []),
    (90.001, ["Latitude 90.001 is outside"]),
    (-91.0,  ["Latitude -91.0 is outside"]),
    ("abc",  ["not a valid number"]),
    (None,   ["not a valid number"]),
])
def test_validate_latitude(lat, expected_errors):
    errors = validate_latitude(lat)
    if expected_errors:
        assert errors, f"Expected errors for lat={lat!r}, got none"
        for exp in expected_errors:
            assert any(exp in e for e in errors), f"Expected '{exp}' in {errors}"
    else:
        assert errors == [], f"Unexpected errors for lat={lat!r}: {errors}"


# ── Longitude ─────────────────────────────────────────────────
@pytest.mark.parametrize("lon,expected_errors", [
    (0.0,     []),
    (180.0,   []),
    (-180.0,  []),
    (77.5,    []),
    (180.001, ["Longitude 180.001 is outside"]),
    (-181.0,  ["Longitude -181.0 is outside"]),
    ("xyz",   ["not a valid number"]),
])
def test_validate_longitude(lon, expected_errors):
    errors = validate_longitude(lon)
    if expected_errors:
        assert errors
    else:
        assert errors == []


# ── Coordinate pairs ──────────────────────────────────────────
def test_validate_coordinates_valid():
    assert validate_coordinates(21.2, 72.8) == []


def test_validate_coordinates_both_invalid():
    errors = validate_coordinates(95.0, -200.0)
    assert len(errors) == 2


# ── Positive float ────────────────────────────────────────────
def test_validate_positive_float_valid():
    assert validate_positive_float(100.5, "frp") == []


def test_validate_positive_float_zero():
    assert validate_positive_float(0.0, "frp") == []


def test_validate_positive_float_negative():
    errors = validate_positive_float(-5.0, "frp")
    assert errors


def test_validate_positive_float_none():
    assert validate_positive_float(None, "frp") == []  # optional


def test_validate_positive_float_empty_string():
    assert validate_positive_float("", "frp") == []  # optional


# ── Confidence range ──────────────────────────────────────────
def test_validate_confidence_valid():
    assert validate_confidence_range(0.85) == []


def test_validate_confidence_zero():
    assert validate_confidence_range(0.0) == []


def test_validate_confidence_one():
    assert validate_confidence_range(1.0) == []


def test_validate_confidence_over_one():
    errors = validate_confidence_range(1.1)
    assert errors


def test_validate_confidence_none():
    assert validate_confidence_range(None) == []


# ── Required columns ──────────────────────────────────────────
def test_check_required_columns_all_present():
    errors = check_required_columns(
        {"latitude", "longitude", "acq_date", "acq_time"},
        frozenset({"latitude", "longitude", "acq_date", "acq_time"}),
        "firms"
    )
    assert errors == []


def test_check_required_columns_missing():
    errors = check_required_columns(
        {"latitude", "longitude"},
        frozenset({"latitude", "longitude", "acq_date", "acq_time"}),
        "firms"
    )
    assert errors
    assert "acq_date" in errors[0] or "acq_time" in errors[0]
