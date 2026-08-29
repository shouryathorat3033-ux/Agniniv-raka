"""
Tests for land-cover and deduplication utilities.
Unit tests — no database or raster files required.
"""
import pytest
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.deduplication import firms_fingerprint, osm_dedup_key, industrial_dedup_key


# ── Deduplication tests ───────────────────────────────────────

def test_firms_fingerprint_deterministic():
    dt = datetime(2024, 6, 15, 8, 30, tzinfo=timezone.utc)
    fp1 = firms_fingerprint("VIIRS_NOAA20", 21.2034, 72.8765, dt)
    fp2 = firms_fingerprint("VIIRS_NOAA20", 21.2034, 72.8765, dt)
    assert fp1 == fp2


def test_firms_fingerprint_different_source():
    dt = datetime(2024, 6, 15, 8, 30, tzinfo=timezone.utc)
    fp1 = firms_fingerprint("VIIRS_NOAA20", 21.2034, 72.8765, dt)
    fp2 = firms_fingerprint("MODIS_TERRA", 21.2034, 72.8765, dt)
    assert fp1 != fp2


def test_firms_fingerprint_coordinate_rounding():
    dt = datetime(2024, 6, 15, 8, 30, tzinfo=timezone.utc)
    # Difference beyond 4 decimal places should still match
    fp1 = firms_fingerprint("VIIRS_NOAA20", 21.20341, 72.87651, dt)
    fp2 = firms_fingerprint("VIIRS_NOAA20", 21.20349, 72.87659, dt)
    assert fp1 == fp2  # both round to 21.2034 / 72.8766


def test_firms_fingerprint_different_time():
    dt1 = datetime(2024, 6, 15, 8, 30, tzinfo=timezone.utc)
    dt2 = datetime(2024, 6, 15, 9, 30, tzinfo=timezone.utc)
    fp1 = firms_fingerprint("VIIRS_NOAA20", 21.2034, 72.8765, dt1)
    fp2 = firms_fingerprint("VIIRS_NOAA20", 21.2034, 72.8765, dt2)
    assert fp1 != fp2


def test_osm_dedup_key():
    key = osm_dedup_key("way", 123456789)
    assert key == "way:123456789"


def test_osm_dedup_key_node():
    key = osm_dedup_key("node", 987)
    assert key == "node:987"


def test_industrial_dedup_key_with_ref():
    key = industrial_dedup_key("GEM_2024", "GEM-IND-12345")
    assert key == "GEM_2024::GEM-IND-12345"


def test_industrial_dedup_key_no_ref():
    key = industrial_dedup_key("GEM_2024", None)
    assert key is None


# ── Landcover transformer tests ───────────────────────────────
from landcover.transformer import transform_landcover_result

def test_transform_landcover_clamps_over_one():
    raw = {
        "land_cover_class": "Built-up",
        "built_up_score":   1.5,  # > 1.0 — should be clamped
        "pixel_count":      100,
    }
    record = transform_landcover_result(
        raw,
        thermal_object_id="test-uuid",
        land_cover_source="ESA_WorldCover_2021",
        resolution_meters=10,
    )
    assert record["built_up_score"] == 1.0


def test_transform_landcover_clamps_negative():
    raw = {
        "land_cover_class": "Grassland",
        "grassland_score":  -0.1,  # < 0 — should be clamped
    }
    record = transform_landcover_result(
        raw,
        thermal_object_id="test-uuid",
        land_cover_source="ESA_WorldCover_2021",
        resolution_meters=10,
    )
    assert record["grassland_score"] == 0.0


def test_transform_landcover_missing_scores_become_none():
    raw = {"land_cover_class": "Water"}
    record = transform_landcover_result(
        raw,
        thermal_object_id="test-uuid",
        land_cover_source="ESA_WorldCover_2021",
        resolution_meters=10,
    )
    assert record["built_up_score"] is None
    assert record["water_score"] is None
