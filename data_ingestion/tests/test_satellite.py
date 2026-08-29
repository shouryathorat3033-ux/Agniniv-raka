"""
Tests for satellite metadata validator.
Unit tests — no database or real satellite files required.
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from satellite.validator import validate_scene_metadata


VALID_META = {
    "scene_id":        "S2A_MSIL2A_20240615T054651",
    "source":          "SENTINEL_2",
    "acquisition_time": "2024-06-15T05:46:51Z",
    "cloud_cover_pct": 12.5,
    "tile_id":         "43RGP",
}


def test_valid_metadata_no_errors():
    errors = validate_scene_metadata(VALID_META)
    assert errors == []


def test_missing_scene_id():
    meta = {**VALID_META, "scene_id": ""}
    errors = validate_scene_metadata(meta)
    assert any("scene_id" in e for e in errors)


def test_missing_source():
    meta = {**VALID_META, "source": ""}
    errors = validate_scene_metadata(meta)
    assert any("source" in e for e in errors)


def test_missing_acquisition_time():
    meta = {**VALID_META, "acquisition_time": None}
    errors = validate_scene_metadata(meta)
    assert any("acquisition_time" in e for e in errors)


def test_invalid_acquisition_time():
    meta = {**VALID_META, "acquisition_time": "not-a-date"}
    errors = validate_scene_metadata(meta)
    assert any("acquisition_time" in e for e in errors)


def test_cloud_cover_over_100():
    meta = {**VALID_META, "cloud_cover_pct": 105.0}
    errors = validate_scene_metadata(meta)
    assert any("cloud_cover" in e for e in errors)


def test_cloud_cover_zero_valid():
    meta = {**VALID_META, "cloud_cover_pct": 0.0}
    assert validate_scene_metadata(meta) == []


def test_no_cloud_cover_is_ok():
    meta = {k: v for k, v in VALID_META.items() if k != "cloud_cover_pct"}
    assert validate_scene_metadata(meta) == []
