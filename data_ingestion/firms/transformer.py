"""
HEATWATCH — FIRMS Transformer
==============================
Post-normalization transformations applied before database load.
Currently responsible for:
  - Rejecting records whose source is not in HOTSPOT_SOURCES
  - Writing rejected records to the rejected/ directory
  - Computing any derived fields before insert
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from common.logging_config import get_logger
from config.datasets import HOTSPOT_SOURCES

log = get_logger(__name__)


def filter_invalid_sources(
    records: list[dict[str, Any]],
    rejected_dir: Path,
    source_file_name: str,
) -> tuple[list[dict[str, Any]], int]:
    """
    Remove records whose normalized source is not in HOTSPOT_SOURCES.
    Writes rejected records to rejected_dir as JSON Lines.

    Returns
    -------
    (valid_records, rejected_count)
    """
    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for rec in records:
        if rec["source"] in HOTSPOT_SOURCES:
            valid.append(rec)
        else:
            rec["_rejection_reason"] = (
                f"source={rec['source']!r} not in HOTSPOT_SOURCES; "
                f"original satellite={rec.get('satellite')!r}"
            )
            rejected.append(rec)

    if rejected:
        rejected_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        out_path = rejected_dir / f"firms_invalid_source_{source_file_name}_{ts}.jsonl"
        with out_path.open("w", encoding="utf-8") as fh:
            for r in rejected:
                fh.write(json.dumps(r, default=str) + "\n")
        log.warning(
            "firms.transformer.rejected_source",
            count=len(rejected),
            path=str(out_path),
        )

    return valid, len(rejected)
