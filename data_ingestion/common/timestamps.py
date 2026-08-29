"""
HEATWATCH Data Ingestion — Timestamp Utilities
==============================================
All timestamps stored in the database must be UTC-aware.
These helpers normalize the variety of datetime formats
found in FIRMS CSVs and other datasets.
"""
from __future__ import annotations

from datetime import datetime, timezone, date, time
from typing import Any

from common.exceptions import InvalidTimestampError


def to_utc(dt: datetime) -> datetime:
    """
    Ensure a datetime is UTC-aware.
    If naive (no tzinfo), assumes UTC.
    If aware, converts to UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_firms_datetime(acq_date_str: str, acq_time_str: str) -> datetime:
    """
    Parse FIRMS acq_date and acq_time into a UTC-aware datetime.

    FIRMS formats:
      acq_date: 'YYYY-MM-DD'
      acq_time: '0000'–'2359' (HHMM, zero-padded, may be int)

    Returns a UTC-aware datetime.
    Raises InvalidTimestampError on parse failure.
    """
    try:
        date_part = datetime.strptime(str(acq_date_str).strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise InvalidTimestampError(
            f"Cannot parse acq_date {acq_date_str!r}: expected YYYY-MM-DD"
        ) from exc

    try:
        time_str = str(int(acq_time_str)).zfill(4)  # ensure zero-padded HHMM
        hh = int(time_str[:2])
        mm = int(time_str[2:])
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError(f"hh={hh}, mm={mm} out of range")
        time_part = time(hh, mm, tzinfo=timezone.utc)
    except (ValueError, TypeError) as exc:
        raise InvalidTimestampError(
            f"Cannot parse acq_time {acq_time_str!r}: expected HHMM (e.g. '0830')"
        ) from exc

    return datetime.combine(date_part, time_part)


def now_utc() -> datetime:
    """Return the current time as UTC-aware datetime."""
    return datetime.now(tz=timezone.utc)


def parse_iso_timestamp(ts_str: str) -> datetime:
    """
    Parse an ISO 8601 timestamp string into a UTC-aware datetime.
    Accepts formats like '2024-06-15T14:30:00Z' or '2024-06-15T14:30:00+00:00'.
    """
    ts_str = ts_str.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(ts_str)
        return to_utc(dt)
    except ValueError as exc:
        raise InvalidTimestampError(
            f"Cannot parse ISO timestamp {ts_str!r}"
        ) from exc


def safe_parse_date(value: Any) -> date | None:
    """
    Try to parse a value as a date. Returns None on failure.
    """
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
