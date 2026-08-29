"""
HEATWATCH Data Ingestion — Provenance Tracking
===============================================
Standardized ingestion run result record.
Every pipeline returns an IngestionResult that is logged
and optionally written to a manifest file.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from common.timestamps import now_utc


@dataclass
class IngestionResult:
    """
    Structured result for one ingestion run.
    All fields are serializable to JSON for manifest output.
    """
    dataset_name:       str
    source_reference:   str          # file path or API URL
    pipeline_version:   str = "v1"

    started_at:         str = field(default_factory=lambda: now_utc().isoformat())
    finished_at:        str = ""

    records_read:       int = 0
    records_valid:      int = 0
    records_rejected:   int = 0
    records_inserted:   int = 0
    records_skipped:    int = 0      # duplicates skipped
    records_updated:    int = 0      # safe metadata updates

    validation_errors:  list[str] = field(default_factory=list)
    warnings:           list[str] = field(default_factory=list)
    metadata:           dict[str, Any] = field(default_factory=dict)

    success:            bool = False

    def finish(self, success: bool = True) -> "IngestionResult":
        self.finished_at = now_utc().isoformat()
        self.success = success
        return self

    def add_error(self, msg: str) -> None:
        self.validation_errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def write_manifest(self, output_dir: Path) -> Path:
        """Write the ingestion result as a JSON manifest file."""
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = now_utc().strftime("%Y%m%dT%H%M%SZ")
        fname = output_dir / f"ingestion_{self.dataset_name}_{ts}.json"
        fname.write_text(self.to_json(), encoding="utf-8")
        return fname

    def summary_line(self) -> str:
        return (
            f"[{self.dataset_name}] "
            f"read={self.records_read} "
            f"valid={self.records_valid} "
            f"rejected={self.records_rejected} "
            f"inserted={self.records_inserted} "
            f"skipped={self.records_skipped} "
            f"success={self.success}"
        )
