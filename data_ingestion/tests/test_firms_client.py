"""
Tests for FIRMS API client (firms/client.py).
No real API calls — uses mocked responses.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from firms.client import (
    FIRMSAuthError,
    FIRMSAPIError,
    FIRMSRateLimitError,
    make_country_csv_url,
    make_area_csv_url,
    fetch_firms_csv,
    _mask_key_in_url,
    _check_response_body,
)


# ── URL construction ─────────────────────────────────────────────

def test_make_country_csv_url_format():
    url = make_country_csv_url(
        base_url="https://firms.modaps.eosdis.nasa.gov/api",
        api_key="TESTKEY123",
        source="VIIRS_NOAA20_NRT",
        country="IND",
        days=1,
    )
    assert "TESTKEY123" in url
    assert "VIIRS_NOAA20_NRT" in url
    assert "IND" in url
    assert "/csv/" in url


def test_make_country_csv_url_trailing_slash_stripped():
    url = make_country_csv_url(
        base_url="https://firms.example.com/api/",
        api_key="KEY",
        source="MODIS_NRT",
        country="IND",
        days=3,
    )
    assert not url.startswith("https://firms.example.com/api//")


def test_make_area_csv_url_format():
    bbox = {"min_lon": 68.0, "min_lat": 6.0, "max_lon": 98.0, "max_lat": 37.5}
    url = make_area_csv_url(
        base_url="https://firms.example.com/api",
        api_key="KEY",
        source="VIIRS_NOAA20_NRT",
        bbox=bbox,
        days=1,
    )
    assert "68.0" in url
    assert "37.5" in url
    assert "/area/csv/" in url


# ── Key masking ──────────────────────────────────────────────────

def test_mask_key_in_url_hides_key():
    url = "https://firms.modaps.eosdis.nasa.gov/api/country/csv/SECRETKEY123/VIIRS_NOAA20_NRT/IND/1"
    masked = _mask_key_in_url(url)
    assert "SECRETKEY123" not in masked
    assert "***" in masked
    assert "VIIRS_NOAA20_NRT" in masked


def test_mask_key_in_url_no_csv_segment_unchanged():
    url = "https://example.com/no-csv-here"
    masked = _mask_key_in_url(url)
    # Should not crash
    assert isinstance(masked, str)


# ── Embedded error detection ──────────────────────────────────────

def test_check_response_body_invalid_key_raises():
    with pytest.raises(FIRMSAPIError):
        _check_response_body("Invalid Key", "https://example.com/url")


def test_check_response_body_valid_csv_does_not_raise():
    csv_body = "latitude,longitude,acq_date,acq_time\n21.2,72.8,2024-06-15,0830\n" * 100
    _check_response_body(csv_body, "https://example.com")  # Should not raise


def test_check_response_body_empty_does_not_raise():
    _check_response_body("", "https://example.com")


# ── HTTP error handling ───────────────────────────────────────────

@patch("firms.client.requests.get")
def test_fetch_firms_csv_auth_error_401(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_get.return_value = mock_resp

    with pytest.raises(FIRMSAuthError) as exc_info:
        fetch_firms_csv("https://example.com/api/country/csv/KEY/SRC/IND/1")
    assert "401" in str(exc_info.value) or "authentication" in str(exc_info.value).lower()


@patch("firms.client.requests.get")
def test_fetch_firms_csv_auth_error_403(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_get.return_value = mock_resp

    with pytest.raises(FIRMSAuthError):
        fetch_firms_csv("https://example.com/api/country/csv/KEY/SRC/IND/1")


@patch("firms.client.requests.get")
def test_fetch_firms_csv_404_raises_api_error(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_get.return_value = mock_resp

    with pytest.raises(FIRMSAPIError):
        fetch_firms_csv("https://example.com/api/country/csv/KEY/SRC/IND/1")


@patch("firms.client.requests.get")
def test_fetch_firms_csv_success(mock_get):
    csv_body = (
        "latitude,longitude,acq_date,acq_time,satellite\n"
        "21.2034,72.8765,2024-06-15,0830,NOAA-20\n" * 50
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = csv_body
    mock_get.return_value = mock_resp

    result = fetch_firms_csv(
        "https://example.com/api/country/csv/KEY/VIIRS_NOAA20_NRT/IND/1",
        max_retries=1,
    )
    assert "latitude" in result
    assert "NOAA-20" in result


@patch("firms.client.requests.get")
@patch("firms.client.time.sleep")
def test_fetch_firms_csv_retries_on_500(mock_sleep, mock_get):
    """Server error should be retried."""
    fail_resp = MagicMock()
    fail_resp.status_code = 503

    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.text = "latitude,longitude,acq_date,acq_time\n21.2,72.8,2024-06-15,0830\n" * 20

    mock_get.side_effect = [fail_resp, ok_resp]

    result = fetch_firms_csv(
        "https://example.com/api/country/csv/KEY/SRC/IND/1",
        max_retries=3,
    )
    assert mock_get.call_count == 2
    assert "latitude" in result


# ── India filtering ───────────────────────────────────────────────

def test_india_bbox_values():
    from firms.config import INDIA_BBOX
    assert INDIA_BBOX["min_lat"] < 10.0
    assert INDIA_BBOX["max_lat"] > 35.0
    assert INDIA_BBOX["min_lon"] < 70.0
    assert INDIA_BBOX["max_lon"] > 95.0
