"""
HEATWATCH — Satellite Scene Reader
=====================================
Reads satellite scene metadata from:
  - Sentinel-2 SAFE directory MTD_MSIL2A.xml
  - JSON scene manifests (custom format)
  - GeoJSON scene footprint files

Does NOT read or store raw image pixels in PostgreSQL.
Does NOT download from Copernicus/USGS.

Supports locally available scene files only.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from common.exceptions import DatasetNotFoundError, DatasetReadError, UnsupportedFormatError
from common.logging_config import get_logger

log = get_logger(__name__)


def read_sentinel2_metadata(safe_dir: Path) -> dict[str, Any]:
    """
    Read Sentinel-2 SAFE directory metadata from MTD_MSIL2A.xml.
    Returns a metadata dict suitable for provenance manifests.
    """
    if not safe_dir.exists():
        raise DatasetNotFoundError(f"Sentinel-2 SAFE directory not found: {safe_dir}")

    # Find the product metadata XML
    xml_candidates = list(safe_dir.glob("MTD_MSIL*.xml"))
    if not xml_candidates:
        raise DatasetReadError(
            f"No MTD_MSIL*.xml found in {safe_dir}. "
            "Confirm this is a valid Sentinel-2 SAFE directory."
        )

    xml_path = xml_candidates[0]
    log.info("satellite.reader.xml", path=str(xml_path))

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as exc:
        raise DatasetReadError(f"Cannot parse Sentinel-2 XML {xml_path}: {exc}") from exc

    def _find(tag: str) -> str | None:
        el = root.find(f".//{tag}")
        return el.text.strip() if el is not None and el.text else None

    return {
        "scene_id":         safe_dir.name,
        "source":           "SENTINEL_2",
        "satellite":        _find("SPACECRAFT_NAME"),
        "product_type":     _find("PRODUCT_TYPE"),
        "processing_level": _find("PROCESSING_LEVEL"),
        "acquisition_time": _find("DATATAKE_SENSING_START"),
        "cloud_cover_pct":  _safe_float(_find("Cloud_Coverage_Assessment")),
        "sensing_orbit":    _find("SENSING_ORBIT_NUMBER"),
        "tile_id":          _find("TILE_ID"),
        "crs":              _find("HORIZONTAL_CS_NAME"),
        "safe_path":        str(safe_dir),
    }


def read_scene_json(json_path: Path) -> dict[str, Any]:
    """
    Read a scene metadata JSON manifest (custom format).
    """
    if not json_path.exists():
        raise DatasetNotFoundError(f"Scene JSON not found: {json_path}")
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise DatasetReadError(f"Cannot parse scene JSON {json_path}: {exc}") from exc
    return data


def list_scene_sources(directory: Path) -> list[Path]:
    """
    Discover satellite scene sources in a directory.
    Returns SAFE directories and JSON manifest files.
    """
    if not directory.exists():
        raise DatasetNotFoundError(f"Satellite directory not found: {directory}")

    sources: list[Path] = []
    # SAFE directories
    sources.extend(p for p in directory.iterdir() if p.is_dir() and p.suffix == ".SAFE")
    # JSON manifests
    sources.extend(sorted(directory.glob("*.json")))
    log.info("satellite.reader.listed", directory=str(directory), count=len(sources))
    return sources


def _safe_float(val: str | None) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
