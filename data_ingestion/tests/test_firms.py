"""
Tests for FIRMS pipeline components.
Unit tests using synthetic fixtures — no real FIRMS files required.
No database connection required (marks requiring DB are integration tests).
"""
import io
import pytest
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from firms.validator import validate_firms_dataframe
from firms.normalizer import normalize_firms_row, normalize_firms_dataframe


# ── Synthetic FIRMS data ──────────────────────────────────────

def make_firms_df(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal FIRMS DataFrame from a list of row dicts."""
    return pd.DataFrame(rows)


VALID_ROW = {
    "latitude":  "21.2034",
    "longitude": "72.8765",
    "acq_date":  "2024-06-15",
    "acq_time":  "0830",
    "satellite": "NOAA-20",
    "instrument": "VIIRS",
    "confidence": "nominal",
    "frp":        "45.5",
    "daynight":   "D",
    "brightness": "312.5",
    "brightness_2": "295.0",
}


# ── Validator tests ───────────────────────────────────────────

def test_validate_single_valid_row():
    df = make_firms_df([VALID_ROW])
    valid, rejected = validate_firms_dataframe(df)
    assert len(valid) == 1
    assert len(rejected) == 0


def test_validate_invalid_latitude():
    row = {**VALID_ROW, "latitude": "95.0"}
    df = make_firms_df([row])
    valid, rejected = validate_firms_dataframe(df)
    assert len(valid) == 0
    assert len(rejected) == 1
    assert "Latitude" in rejected.iloc[0]["rejection_reason"]


def test_validate_invalid_longitude():
    row = {**VALID_ROW, "longitude": "-200.0"}
    df = make_firms_df([row])
    valid, rejected = validate_firms_dataframe(df)
    assert len(rejected) == 1


def test_validate_missing_acq_date():
    row = {**VALID_ROW, "acq_date": ""}
    df = make_firms_df([row])
    valid, rejected = validate_firms_dataframe(df)
    assert len(rejected) == 1


def test_validate_invalid_acq_time():
    row = {**VALID_ROW, "acq_time": "9999"}
    df = make_firms_df([row])
    valid, rejected = validate_firms_dataframe(df)
    assert len(rejected) == 1


def test_validate_negative_frp():
    row = {**VALID_ROW, "frp": "-10.0"}
    df = make_firms_df([row])
    valid, rejected = validate_firms_dataframe(df)
    assert len(rejected) == 1


def test_validate_missing_frp_is_ok():
    row = {**VALID_ROW, "frp": ""}
    df = make_firms_df([row])
    valid, rejected = validate_firms_dataframe(df)
    assert len(valid) == 1


def test_validate_empty_dataframe():
    df = pd.DataFrame()
    valid, rejected = validate_firms_dataframe(df)
    assert valid.empty and rejected.empty


def test_validate_mixed_rows():
    rows = [
        VALID_ROW,
        {**VALID_ROW, "latitude": "999"},
        {**VALID_ROW, "acq_time": "bad_time"},
    ]
    df = make_firms_df(rows)
    valid, rejected = validate_firms_dataframe(df)
    assert len(valid) == 1
    assert len(rejected) == 2


# ── Normalizer tests ──────────────────────────────────────────

def test_normalize_row_fields():
    row = pd.Series(VALID_ROW)
    record = normalize_firms_row(row, source_file="test.csv")
    assert record["latitude"] == 21.2034
    assert record["longitude"] == 72.8765
    assert record["source"] == "VIIRS_NOAA20"
    assert record["confidence"] == "nominal"
    assert record["frp"] == 45.5
    assert record["daynight"] == "D"
    assert "POINT" in record["location_wkt"]


def test_normalize_source_mapping():
    row = pd.Series({**VALID_ROW, "satellite": "Terra"})
    record = normalize_firms_row(row, source_file="test.csv")
    assert record["source"] == "MODIS_TERRA"


def test_normalize_unknown_satellite_maps_to_other():
    row = pd.Series({**VALID_ROW, "satellite": "UnknownSat999"})
    record = normalize_firms_row(row, source_file="test.csv")
    assert record["source"] == "OTHER"


def test_normalize_raw_payload_preserved():
    row = pd.Series(VALID_ROW)
    record = normalize_firms_row(row, source_file="test.csv")
    assert record["raw_payload"] is not None
    assert "21.2034" in record["raw_payload"]


def test_normalize_confidence_l():
    row = pd.Series({**VALID_ROW, "confidence": "l"})
    record = normalize_firms_row(row, source_file="test.csv")
    assert record["confidence"] == "low"


def test_normalize_daynight_lowercase():
    row = pd.Series({**VALID_ROW, "daynight": "n"})
    record = normalize_firms_row(row, source_file="test.csv")
    assert record["daynight"] == "N"


def test_normalize_dataframe_batch():
    df = make_firms_df([VALID_ROW, VALID_ROW])
    records = normalize_firms_dataframe(df, source_file="test.csv")
    assert len(records) == 2
