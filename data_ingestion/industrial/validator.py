"""Industrial validator — delegates to common validators."""
from __future__ import annotations

import geopandas as gpd

from common.logging_config import get_logger
from common.validators import validate_coordinates

log = get_logger(__name__)


def validate_industrial_dataframe(
    gdf: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Validate industrial facility rows. Returns (valid, rejected)."""
    if gdf.empty:
        return gdf.copy(), gdf.copy()

    reasons: list[str | None] = []
    for _, row in gdf.iterrows():
        errors: list[str] = []
        geom = row.geometry
        if geom is None or geom.is_empty:
            errors.append("geometry is null or empty")
        else:
            try:
                c = geom.centroid
                errors += validate_coordinates(c.y, c.x)
            except Exception as exc:
                errors.append(f"centroid error: {exc}")
        reasons.append("; ".join(errors) if errors else None)

    gdf = gdf.copy()
    gdf["_rejection_reason"] = reasons
    valid = gdf[gdf["_rejection_reason"].isna()].drop(columns=["_rejection_reason"])
    rejected = gdf[gdf["_rejection_reason"].notna()].rename(
        columns={"_rejection_reason": "rejection_reason"}
    )
    log.info("industrial.validator.done", valid=len(valid), rejected=len(rejected))
    return valid, rejected
