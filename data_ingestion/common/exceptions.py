"""
HEATWATCH Data Ingestion — Custom Exceptions
=============================================
All pipelines raise these typed exceptions so callers can
distinguish recoverable warnings from pipeline-stopping failures.
"""
from __future__ import annotations


class IngestionError(Exception):
    """Base class for all HEATWATCH ingestion errors."""


# ── Configuration ─────────────────────────────────────────────
class ConfigurationError(IngestionError):
    """Missing or invalid environment variable / configuration."""


# ── Database ──────────────────────────────────────────────────
class DatabaseConnectionError(IngestionError):
    """Cannot connect to PostgreSQL / PostGIS is unavailable."""


class DatabaseTransactionError(IngestionError):
    """A database transaction failed and was rolled back."""


# ── File / Dataset reading ────────────────────────────────────
class DatasetReadError(IngestionError):
    """Source file cannot be opened or parsed (unrecoverable)."""


class DatasetNotFoundError(DatasetReadError):
    """Source file or directory does not exist."""


class UnsupportedFormatError(DatasetReadError):
    """File format is not supported by this reader."""


# ── Validation ───────────────────────────────────────────────
class ValidationError(IngestionError):
    """
    One or more rows failed validation.
    Not raised per-row — raised when the dataset as a whole
    cannot proceed (e.g. required structural columns are missing).
    """


class MissingRequiredColumnsError(ValidationError):
    """Required columns are completely absent from the source file."""


class InvalidCoordinatesError(ValidationError):
    """Coordinate values are outside valid WGS84 range."""


class InvalidCRSError(ValidationError):
    """CRS is unknown or unsupported for spatial conversion."""


class InvalidTimestampError(ValidationError):
    """Acquisition date/time cannot be parsed."""


# ── Geometry ─────────────────────────────────────────────────
class GeometryError(IngestionError):
    """Geometry creation or transformation failed."""


# ── Deduplication ─────────────────────────────────────────────
class DuplicateRecordError(IngestionError):
    """Record already exists and DEDUP_STRATEGY does not allow updates."""
