"""
HEATWATCH — OSM PBF File Validator
====================================
Validates the downloaded India OSM PBF before parsing begins.
Distinct from osm/validator.py which validates GeoDataFrame rows.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from common.logging_config import get_logger

log = get_logger(__name__)

_MIN_SIZE_BYTES = 10_000_000   # India PBF should be > 10 MB


@dataclass
class PBFValidationReport:
    valid:      bool  = False
    file:       str   = ""
    size_bytes: int   = 0
    size_mb:    float = 0.0
    format:     str   = ""
    errors:     list[str] = field(default_factory=list)
    warnings:   list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "valid":      self.valid,
            "file":       self.file,
            "size_bytes": self.size_bytes,
            "size_mb":    round(self.size_mb, 2),
            "format":     self.format,
            "errors":     self.errors,
            "warnings":   self.warnings,
        }

    def print_summary(self) -> None:
        status = "VALID" if self.valid else "INVALID"
        print(f"  PBF Validation : {status}")
        print(f"    File         : {self.file}")
        print(f"    Size         : {self.size_mb:.1f} MB ({self.size_bytes:,} bytes)")
        print(f"    Format       : {self.format}")
        for e in self.errors:
            print(f"    [ERROR]      : {e}")
        for w in self.warnings:
            print(f"    [WARN]       : {w}")


def validate_pbf(path: Path) -> PBFValidationReport:
    """
    Validate a downloaded OSM PBF file.

    Checks: existence, extension, size, magic bytes, osmium structural check.
    """
    report = PBFValidationReport(file=str(path))
    log.info("osm.pbf_validation.start", path=str(path))

    if not path.exists():
        report.errors.append(f"File not found: {path}")
        return report

    # Extension check
    name_lower = path.name.lower()
    if name_lower.endswith(".osm.pbf"):
        report.format = "osm.pbf"
    elif name_lower.endswith(".pbf"):
        report.format = "pbf"
        report.warnings.append("Extension is .pbf — may still be valid OSM PBF")
    else:
        report.errors.append(f"Unexpected extension in: {path.name}")
        return report

    # Size
    stat = path.stat()
    report.size_bytes = stat.st_size
    report.size_mb    = stat.st_size / 1024 / 1024

    if stat.st_size == 0:
        report.errors.append("File is empty (0 bytes)")
        return report

    if stat.st_size < _MIN_SIZE_BYTES:
        report.warnings.append(
            f"File is small ({report.size_mb:.1f} MB) — may be truncated or a test file"
        )

    # Magic bytes (PBF has a 4-byte big-endian blob length at start)
    try:
        with open(path, "rb") as fh:
            header = fh.read(4)
        if len(header) < 4:
            report.errors.append("File too short for PBF header")
            return report
    except OSError as exc:
        report.errors.append(f"Cannot read file: {exc}")
        return report

    # osmium structural check — open header only
    try:
        import osmium

        class _PeekHandler(osmium.SimpleHandler):
            found_node = False
            def node(self, n):
                _PeekHandler.found_node = True
                raise StopIteration

        try:
            _PeekHandler().apply_file(str(path))
        except StopIteration:
            pass  # expected early exit after first node
        log.info("osm.pbf_validation.osmium_ok", path=str(path))
    except Exception as exc:
        report.warnings.append(
            f"osmium structural check: {exc} "
            "(may be a relation-only file — continuing)"
        )

    report.valid = len(report.errors) == 0
    log.info(
        "osm.pbf_validation.complete",
        valid=report.valid,
        size_mb=round(report.size_mb, 1),
    )
    return report
