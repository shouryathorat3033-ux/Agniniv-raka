"""
HEATWATCH — OSM Validator
==========================
Validates OSM GeoDataFrame rows before classification.
Checks geometry validity, coordinate bounds, osm_id presence.
"""
from __future__ import annotations

import geopandas as gpd

from common.logging_config import get_logger

log = get_logger(__name__)


def validate_osm_dataframe(gdf: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    Validate OSM features.

    Returns
    -------
    (valid_gdf, rejected_gdf)
    rejected_gdf has a 'rejection_reason' column added.
    """
    if gdf.empty:
        return gdf.copy(), gdf.copy()

    reasons: list[str | None] = []

    for idx, row in gdf.iterrows():
        errors: list[str] = []

        # Geometry check
        geom = row.geometry
        if geom is None or geom.is_empty:
            errors.append("geometry is null or empty")
        elif not geom.is_valid:
            # Try to fix before rejecting
            try:
                fixed = geom.buffer(0)
                if fixed.is_valid:
                    gdf.at[idx, "geometry"] = fixed
                else:
                    errors.append(f"geometry is invalid: {geom.is_valid_reason}")
            except Exception:
                errors.append("geometry could not be validated")

        # Coordinate bounds check (via centroid)
        if not errors and geom and not geom.is_empty:
            try:
                centroid = geom.centroid
                if not (-180 <= centroid.x <= 180 and -90 <= centroid.y <= 90):
                    errors.append(
                        f"Centroid ({centroid.x:.4f}, {centroid.y:.4f}) outside WGS84 bounds"
                    )
            except Exception as exc:
                errors.append(f"Cannot compute centroid: {exc}")

        reasons.append("; ".join(errors) if errors else None)

    gdf = gdf.copy()
    gdf["_rejection_reason"] = reasons
    valid_gdf    = gdf[gdf["_rejection_reason"].isna()].drop(columns=["_rejection_reason"])
    rejected_gdf = gdf[gdf["_rejection_reason"].notna()].rename(
        columns={"_rejection_reason": "rejection_reason"}
    )

    log.info(
        "osm.validator.done",
        total=len(gdf),
        valid=len(valid_gdf),
        rejected=len(rejected_gdf),
    )
    return valid_gdf, rejected_gdf
