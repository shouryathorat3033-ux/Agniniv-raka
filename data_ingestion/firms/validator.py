"""
HEATWATCH — FIRMS Validator
============================
Row-level validation for FIRMS observations.
Returns (valid_rows, rejected_rows) DataFrames.
Rejected rows include a 'rejection_reason' column.

Validation rules:
  ✓ latitude in [-90, 90]
  ✓ longitude in [-180, 180]
  ✓ acq_date parseable as YYYY-MM-DD
  ✓ acq_time parseable as HHMM integer (0–2359)
  ✓ frp is numeric or missing (optional field)
  ✓ Row is not fully null (all key fields missing)
"""
from __future__ import annotations

import pandas as pd

from common.logging_config import get_logger
from common.validators import validate_coordinates, validate_positive_float

log = get_logger(__name__)


def validate_firms_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Validate each row in a FIRMS DataFrame.

    Returns
    -------
    (valid_df, rejected_df)
        valid_df    — rows that pass all checks
        rejected_df — rows that failed, with 'rejection_reason' column added
    """
    if df.empty:
        return df.copy(), df.copy()

    rejection_reasons: list[str | None] = []

    for _, row in df.iterrows():
        errors: list[str] = []

        # Coordinates
        lat_val = row.get("latitude")
        lon_val = row.get("longitude")
        errors += validate_coordinates(lat_val, lon_val)

        # acq_date
        acq_date = row.get("acq_date", "")
        if not acq_date or str(acq_date).strip() == "":
            errors.append("acq_date is missing")
        else:
            try:
                pd.to_datetime(str(acq_date).strip(), format="%Y-%m-%d")
            except Exception:
                errors.append(f"acq_date {acq_date!r} is not YYYY-MM-DD")

        # acq_time
        acq_time = row.get("acq_time", "")
        if acq_time is None or str(acq_time).strip() == "":
            errors.append("acq_time is missing")
        else:
            try:
                t = int(float(str(acq_time).strip()))
                if not (0 <= t <= 2359):
                    errors.append(f"acq_time {acq_time!r} is outside 0000–2359")
            except (ValueError, TypeError):
                errors.append(f"acq_time {acq_time!r} is not a valid integer HHMM")

        # FRP (optional)
        frp_val = row.get("frp")
        if frp_val is not None and str(frp_val).strip() not in ("", "nan"):
            errors += validate_positive_float(frp_val, "frp")

        rejection_reasons.append("; ".join(errors) if errors else None)

    df = df.copy()
    df["_rejection_reason"] = rejection_reasons

    valid_df    = df[df["_rejection_reason"].isna()].drop(columns=["_rejection_reason"])
    rejected_df = df[df["_rejection_reason"].notna()].rename(
        columns={"_rejection_reason": "rejection_reason"}
    )

    log.info(
        "firms.validator.done",
        total=len(df),
        valid=len(valid_df),
        rejected=len(rejected_df),
    )
    return valid_df, rejected_df
