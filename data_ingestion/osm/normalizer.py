"""
HEATWATCH — OSM Classifier / Normalizer
=========================================
Routes OSM features to one of two destinations:

  A. industrial_facilities — features that are likely industrial sites
  B. osm_context          — general geographic context features

Classification is based on OSM tag analysis using rules defined
in config/datasets.py (OSM_INDUSTRIAL_TAGS).

Also normalizes:
  - osm_id (extracted from feature ID or properties)
  - osm_type (node / way / relation)
  - name (from 'name' property)
  - tags (full properties dict → JSONB)
  - geometry → WKT
"""
from __future__ import annotations

import json
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping

from common.logging_config import get_logger
from config.datasets import (
    OSM_INDUSTRIAL_TAGS,
    FACILITY_TYPE_KEYWORDS,
    FACILITY_TYPES,
    DATASET_SOURCE_OSM,
)

log = get_logger(__name__)


def _is_industrial(tags: dict[str, str]) -> bool:
    """Return True if OSM tags suggest an industrial facility."""
    for tag_key, allowed_values in OSM_INDUSTRIAL_TAGS.items():
        tag_val = tags.get(tag_key, "").lower()
        if any(tag_val == av.lower() for av in allowed_values):
            return True
    return False


def _classify_facility_type(tags: dict[str, str], name: str) -> str:
    """
    Map OSM tags/name to a facility_type ENUM value.
    Falls back to 'OTHER' if no keyword match.
    """
    combined = " ".join([
        tags.get("industrial", ""),
        tags.get("man_made", ""),
        tags.get("landuse", ""),
        tags.get("power", ""),
        name or "",
    ]).lower()

    for keywords, ftype in FACILITY_TYPE_KEYWORDS:
        if any(kw in combined for kw in keywords):
            return ftype
    return "OTHER"


def _extract_osm_type_id(feature: "gpd.GeoSeries") -> tuple[str, int | None]:
    """
    Extract osm_type and osm_id from a GeoDataFrame row.
    FIRMS-style OSM extracts often encode ID in the '@id' property.
    """
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    # Try standard OSM columns first
    osm_id_raw  = feature.get("osm_id") or props.get("@id") or props.get("id")
    osm_type_raw = feature.get("osm_type") or props.get("type") or "way"

    # '@id' format: "way/123456789" or "node/123456789"
    if osm_id_raw and "/" in str(osm_id_raw):
        parts = str(osm_id_raw).split("/")
        osm_type_raw = parts[0].lower()
        osm_id_raw   = parts[1]

    try:
        osm_id = int(float(str(osm_id_raw)))
    except (TypeError, ValueError):
        osm_id = None

    osm_type = str(osm_type_raw).lower()
    if osm_type not in ("node", "way", "relation"):
        osm_type = "way"

    return osm_type, osm_id


def classify_osm_features(gdf: gpd.GeoDataFrame) -> tuple[list[dict], list[dict]]:
    """
    Split a GeoDataFrame of OSM features into:
      - industrial_records  → for industrial_facilities table
      - context_records     → for osm_context table

    Returns
    -------
    (industrial_records, context_records)
    Each record is a dict ready for database insertion.
    """
    industrial_records: list[dict] = []
    context_records:    list[dict] = []

    for idx, row in gdf.iterrows():
        # Build tags dict from all non-geometry columns
        skip = {"geometry", "osm_id", "osm_type", "name", "@id", "id"}
        tags: dict[str, str] = {}
        for col in gdf.columns:
            if col not in skip and col != "geometry":
                val = row.get(col)
                if val is not None and str(val) not in ("", "nan", "None"):
                    tags[col] = str(val)

        # Also parse a 'tags' column if it's already a JSON object
        if "tags" in row and isinstance(row["tags"], dict):
            tags.update(row["tags"])

        name = str(row.get("name", "") or "").strip()
        osm_type, osm_id = _extract_osm_type_id(row)

        # Geometry → WKT
        geom = row.geometry
        geom_wkt = geom.wkt if geom and not geom.is_empty else None

        # Centroid for point-based location
        if geom and not geom.is_empty:
            centroid = geom.centroid
            lat = centroid.y
            lon = centroid.x
        else:
            lat = lon = None

        if _is_industrial(tags):
            ftype = _classify_facility_type(tags, name)
            industrial_records.append({
                "name":             name or f"OSM {osm_type} {osm_id}",
                "facility_type":    ftype,
                "source":           DATASET_SOURCE_OSM,
                "source_reference": f"{osm_type}/{osm_id}" if osm_id else None,
                "location_wkt":     f"POINT({lon} {lat})" if lon is not None else None,
                "boundary_wkt":     geom_wkt if geom and geom.geom_type != "Point" else None,
                "confidence":       0.6,  # OSM data is approximate
                "metadata":         json.dumps({
                    "osm_type": osm_type,
                    "osm_id":   osm_id,
                    "tags":     tags,
                }),
                "_osm_type":        osm_type,
                "_osm_id":          osm_id,
                "_lat":             lat,
                "_lon":             lon,
            })
        else:
            # General context feature
            context_records.append({
                "osm_type":        osm_type,
                "osm_id":          osm_id,
                "name":            name or None,
                "tags":            json.dumps(tags),
                "geometry_wkt":    geom_wkt,
                "_lat":            lat,
                "_lon":            lon,
            })

    log.info(
        "osm.classifier.done",
        total=len(gdf),
        industrial=len(industrial_records),
        context=len(context_records),
    )
    return industrial_records, context_records
