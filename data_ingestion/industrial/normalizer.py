"""
HEATWATCH — Industrial Facility Normalizer
===========================================
Maps external dataset columns to industrial_facilities table columns.

Target table (migration 003):
  name, facility_type (ENUM), source, source_reference,
  location GEOMETRY(Point,4326), boundary GEOMETRY nullable,
  confidence NUMERIC(5,4), metadata JSONB
"""
from __future__ import annotations

import json
from typing import Any

import geopandas as gpd

from common.logging_config import get_logger
from config.datasets import (
    FACILITY_TYPE_KEYWORDS,
    FACILITY_TYPES,
    DATASET_SOURCE_INDUSTRIAL,
)

log = get_logger(__name__)

# Common column name aliases for facility type
_TYPE_ALIASES = {
    "type": "facility_type",
    "plant_type": "facility_type",
    "category": "facility_type",
    "sector": "facility_type",
    "kind": "facility_type",
}

_NAME_ALIASES = {"name", "plant_name", "facility_name", "site_name", "operator"}
_REF_ALIASES  = {"source_reference", "source_ref", "id", "gid", "uid", "identifier"}


def _map_facility_type(raw: Any) -> str:
    """Map raw facility type string to allowed ENUM value."""
    if not raw or str(raw).strip() in ("", "nan", "None"):
        return "OTHER"
    s = str(raw).strip().upper().replace(" ", "_").replace("-", "_")
    if s in FACILITY_TYPES:
        return s
    # Keyword search
    s_lower = s.lower()
    for keywords, ftype in FACILITY_TYPE_KEYWORDS:
        if any(kw in s_lower for kw in keywords):
            return ftype
    return "OTHER"


def _find_col(columns: list[str], aliases: set[str]) -> str | None:
    for c in columns:
        if c.lower() in aliases:
            return c
    return None


def normalize_industrial_dataframe(
    gdf: gpd.GeoDataFrame,
    source_name: str = DATASET_SOURCE_INDUSTRIAL,
    dataset_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Normalize industrial GeoDataFrame into DB-ready dicts.
    """
    cols_lower = {c: c.lower() for c in gdf.columns}
    name_col = _find_col(list(gdf.columns), _NAME_ALIASES)
    ref_col  = _find_col(list(gdf.columns), _REF_ALIASES)
    type_col = None
    for c in gdf.columns:
        if c.lower() in _TYPE_ALIASES or c.lower() == "facility_type":
            type_col = c
            break

    records: list[dict[str, Any]] = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom and not geom.is_empty:
            centroid = geom.centroid
            lat, lon = centroid.y, centroid.x
        else:
            continue  # skip rows without geometry

        name    = str(row[name_col]).strip() if name_col and row.get(name_col) else f"Facility @ ({lat:.4f},{lon:.4f})"
        raw_type = row.get(type_col) if type_col else None
        ftype   = _map_facility_type(raw_type)
        src_ref = str(row[ref_col]).strip() if ref_col and row.get(ref_col) else None

        # Build metadata from all remaining columns
        meta: dict[str, Any] = {}
        for col in gdf.columns:
            if col == "geometry":
                continue
            val = row.get(col)
            if val is not None and str(val) not in ("", "nan", "None"):
                meta[col] = str(val)
        if dataset_id:
            meta["dataset_id"] = dataset_id
        meta["original_type"] = str(raw_type) if raw_type else None

        # Boundary: non-Point geometry
        boundary_wkt = None
        if geom and not geom.is_empty and geom.geom_type != "Point":
            boundary_wkt = geom.wkt

        records.append({
            "name":             name,
            "facility_type":    ftype,
            "source":           source_name,
            "source_reference": src_ref,
            "_lat":             lat,
            "_lon":             lon,
            "boundary_wkt":     boundary_wkt,
            "confidence":       0.8,
            "metadata":         json.dumps(meta),
        })

    log.info("industrial.normalizer.done", records=len(records))
    return records
