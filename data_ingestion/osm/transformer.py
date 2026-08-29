"""
HEATWATCH — OSM Transformer
==============================
Post-classification filtering before database load.
Removes records with missing coordinates or invalid facility_type.
Writes rejected records to rejected/ directory.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from common.logging_config import get_logger
from config.datasets import FACILITY_TYPES

log = get_logger(__name__)


def filter_industrial_records(
    records: list[dict[str, Any]],
    rejected_dir: Path,
) -> tuple[list[dict[str, Any]], int]:
    """
    Filter industrial facility records before DB load.
    Rejects records with missing coordinates or invalid facility_type.
    """
    valid: list[dict[str, Any]] = []
    rejected_count = 0

    for r in records:
        errors: list[str] = []
        if r.get("_lat") is None or r.get("_lon") is None:
            errors.append("missing centroid coordinates")
        if r.get("facility_type") not in FACILITY_TYPES:
            errors.append(f"invalid facility_type={r.get('facility_type')!r}")

        if errors:
            r["_rejection_reason"] = "; ".join(errors)
            rejected_count += 1
            _write_rejected(r, rejected_dir, "industrial")
        else:
            valid.append(r)

    return valid, rejected_count


def _write_rejected(record: dict, rejected_dir: Path, prefix: str) -> None:
    rejected_dir.mkdir(parents=True, exist_ok=True)
    out_file = rejected_dir / f"{prefix}_rejected.jsonl"
    with out_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")
