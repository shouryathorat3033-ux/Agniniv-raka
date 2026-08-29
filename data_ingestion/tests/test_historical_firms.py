"""
Tests for timestamp utilities.
Unit tests — no database required.
"""
import pytest
from datetime import timezone
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.timestamps import parse_firms_datetime, to_utc, parse_iso_timestamp
from common.exceptions import InvalidTimestampError


def test_parse_firms_datetime_basic():
    dt = parse_firms_datetime("2024-06-15", "0830")
    assert dt.year == 2024
    assert dt.month == 6
    assert dt.day == 15
    assert dt.hour == 8
    assert dt.minute == 30
    assert dt.tzinfo == timezone.utc


def test_parse_firms_datetime_midnight():
    dt = parse_firms_datetime("2024-01-01", "0")
    assert dt.hour == 0 and dt.minute == 0


def test_parse_firms_datetime_end_of_day():
    dt = parse_firms_datetime("2024-12-31", "2359")
    assert dt.hour == 23 and dt.minute == 59


def test_parse_firms_datetime_int_time():
    dt = parse_firms_datetime("2024-06-15", 1245)
    assert dt.hour == 12 and dt.minute == 45


def test_parse_firms_datetime_invalid_date():
    with pytest.raises(InvalidTimestampError):
        parse_firms_datetime("not-a-date", "0830")


def test_parse_firms_datetime_invalid_time():
    with pytest.raises(InvalidTimestampError):
        parse_firms_datetime("2024-06-15", "2500")  # HH=25 invalid


def test_to_utc_naive():
    from datetime import datetime
    naive = datetime(2024, 1, 1, 12, 0, 0)
    result = to_utc(naive)
    assert result.tzinfo == timezone.utc


def test_to_utc_already_utc():
    from datetime import datetime
    aware = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    result = to_utc(aware)
    assert result == aware


def test_parse_iso_timestamp_z():
    dt = parse_iso_timestamp("2024-06-15T14:30:00Z")
    assert dt.tzinfo == timezone.utc
    assert dt.hour == 14


def test_parse_iso_timestamp_offset():
    dt = parse_iso_timestamp("2024-06-15T14:30:00+05:30")
    assert dt.tzinfo == timezone.utc
    assert dt.hour == 9  # 14:30 IST = 09:00 UTC
