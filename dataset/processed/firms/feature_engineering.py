"""
HeatWatch — FIRMS Feature Engineering Pipeline
================================================
Project  : Urban/Industrial Heat & Thermal Anomaly Detection
Dataset  : FIRMS India 2022-2024
Input    : dataset/processed/firms_india_2022_2024.csv
Output   : dataset/processed/firms/firms_india_2022_2024_features.csv
           dataset/processed/firms/feature_engineering_report.txt

Design rules
------------
* Never modify the original input file.
* Row count must be identical after feature engineering.
* All original columns are preserved verbatim.
* No ML model training.
* No fake target labels.
* Pandas only -- no PostGIS, no external network calls.
* Script is safe to re-run (output files are overwritten).
"""

import os
import sys
import textwrap
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent          # .../firms/
REPO_ROOT  = SCRIPT_DIR.parent.parent.parent          # C:\SIH_Hackthon

INPUT_FILE  = REPO_ROOT / "dataset" / "processed" / "firms_india_2022_2024.csv"
OUTPUT_DIR  = SCRIPT_DIR                               # dataset/processed/firms/
OUTPUT_CSV  = OUTPUT_DIR / "firms_india_2022_2024_features.csv"
REPORT_FILE = OUTPUT_DIR / "feature_engineering_report.txt"

# ---------------------------------------------------------------------------
# Expected raw columns (fail fast if any are missing)
# ---------------------------------------------------------------------------
REQUIRED_COLUMNS = [
    "latitude", "longitude",
    "bright_ti4", "scan", "track",
    "acq_date", "acq_time",
    "satellite", "instrument",
    "confidence", "version",
    "bright_ti5", "frp",
    "daynight", "type", "year",
]

# ---------------------------------------------------------------------------
# Confidence encoding mapping (documented values only)
# ---------------------------------------------------------------------------
CONFIDENCE_MAP = {"h": 2, "n": 1, "l": 0}

# ---------------------------------------------------------------------------
# Spatial grid resolution (degrees)
# ---------------------------------------------------------------------------
GRID_RESOLUTION = 0.01   # 2 decimal places -> ~1 km grid cells

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def validate_columns(df):
    """Raise a descriptive error if any expected column is missing."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            "Input file is missing expected column(s): {}\n"
            "Available columns: {}".format(missing, df.columns.tolist())
        )


def parse_acq_time(series):
    """
    Convert FIRMS acq_time (integer HHMM, e.g. 1345 -> 13:45) into
    acquisition_hour and acquisition_minute.

    The original acq_time column is NOT modified.

    FIRMS acq_time is stored as an integer (or float if the CSV has decimals).
    Values range from 0 (midnight) to 2359 (23:59).
    Any value that cannot be parsed safely is kept as NaN for that sub-field.
    """
    # Coerce to numeric; fill NaN with 0 for safe decomposition
    time_int = pd.to_numeric(series, errors="coerce").fillna(0).astype(int)

    # HHMM decomposition
    hours   = time_int // 100
    minutes = time_int %  100

    # Clamp to valid ranges (defensive -- real FIRMS data should already be valid)
    hours   = hours.clip(0, 23)
    minutes = minutes.clip(0, 59)

    return pd.DataFrame({"acquisition_hour": hours, "acquisition_minute": minutes})


def build_observation_id(df):
    """
    Create a zero-padded string identifier for each row.
    The ID is row-order based (stable within a single run).
    Format: FIRMS_<zero-padded index>, e.g. FIRMS_0000001
    """
    width = len(str(len(df)))
    return pd.Series(
        ["FIRMS_{}".format(str(i).zfill(width)) for i in range(len(df))],
        index=df.index,
        name="observation_id",
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("HeatWatch -- FIRMS Feature Engineering Pipeline")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. Validate paths
    # ------------------------------------------------------------------
    if not INPUT_FILE.exists():
        sys.exit(
            "\n[ERROR] Input file not found:\n  {}\n"
            "Please ensure the processed dataset is present before running.".format(INPUT_FILE)
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 2. Load raw data
    # ------------------------------------------------------------------
    print("\n[1/8] Loading input file ...\n      {}".format(INPUT_FILE))
    df_raw = pd.read_csv(INPUT_FILE, low_memory=False)
    n_input = len(df_raw)
    print("      Loaded {:,} rows, {} columns.".format(n_input, len(df_raw.columns)))

    # ------------------------------------------------------------------
    # 3. Validate columns
    # ------------------------------------------------------------------
    print("\n[2/8] Validating required columns ...")
    validate_columns(df_raw)
    print("      All required columns present.")

    # Work on a copy -- the original DataFrame is never modified
    df = df_raw.copy()
    original_columns = df_raw.columns.tolist()

    # ------------------------------------------------------------------
    # 4. Temporal features from acq_date
    # ------------------------------------------------------------------
    print("\n[3/8] Parsing acq_date and extracting temporal features ...")

    # Convert to datetime (ISO 8601 format: YYYY-MM-DD)
    df["acq_date"] = pd.to_datetime(df["acq_date"], format="%Y-%m-%d", errors="coerce")

    # Temporal decomposition
    # Note: 'year' already exists as a raw column (preserved verbatim).
    df["month"]       = df["acq_date"].dt.month
    df["day"]         = df["acq_date"].dt.day
    df["day_of_year"] = df["acq_date"].dt.day_of_year
    df["day_of_week"] = df["acq_date"].dt.day_of_week   # Monday=0, Sunday=6

    print("      acq_date range: {} -> {}".format(
        df["acq_date"].min().date(), df["acq_date"].max().date()))

    # ------------------------------------------------------------------
    # 5. Temporal features from acq_time
    # ------------------------------------------------------------------
    print("\n[4/8] Parsing acq_time into acquisition_hour / acquisition_minute ...")
    time_df = parse_acq_time(df["acq_time"])
    df["acquisition_hour"]   = time_df["acquisition_hour"]
    df["acquisition_minute"] = time_df["acquisition_minute"]
    print("      acq_time conversion complete (original acq_time preserved).")

    # ------------------------------------------------------------------
    # 6. Thermal features
    # ------------------------------------------------------------------
    print("\n[5/8] Computing thermal features ...")

    # brightness_difference:
    #   bright_ti4 ~ 3.75 um (mid-infrared, fire-sensitive)
    #   bright_ti5 ~ 11   um (long-wave infrared, ambient thermal)
    #   A large positive difference indicates an active thermal anomaly.
    df["brightness_difference"] = df["bright_ti4"] - df["bright_ti5"]

    print("      brightness_difference: min={:.2f}, max={:.2f}, mean={:.2f}".format(
        df["brightness_difference"].min(),
        df["brightness_difference"].max(),
        df["brightness_difference"].mean()))

    # ------------------------------------------------------------------
    # 7. Encoded confidence score
    # ------------------------------------------------------------------
    print("\n[6/8] Encoding confidence column ...")

    # Map documented values; anything not in the map becomes NaN
    df["confidence_score"] = df["confidence"].map(CONFIDENCE_MAP)

    unmapped = df["confidence_score"].isna().sum()
    if unmapped > 0:
        print("      [WARNING] {:,} confidence values could not be mapped "
              "(not in {{h, n, l}}) -- confidence_score set to NaN.".format(unmapped))
    else:
        print("      All confidence values mapped successfully.")

    # ------------------------------------------------------------------
    # 8. FRP handling
    # ------------------------------------------------------------------
    print("\n[7/8] Handling FRP (Fire Radiative Power) ...")

    # Flag: True if frp is a physically valid (non-negative) measurement
    df["frp_valid"] = df["frp"] >= 0

    # Modeling-safe column: negative values clipped to 0 (NOT deleted)
    df["frp_model"] = df["frp"].clip(lower=0)

    n_frp_neg   = (~df["frp_valid"]).sum()
    n_frp_valid = df["frp_valid"].sum()
    print("      FRP negative observations : {:,}".format(n_frp_neg))
    print("      FRP valid   observations  : {:,}".format(n_frp_valid))

    # ------------------------------------------------------------------
    # 9. Spatial grid features
    # ------------------------------------------------------------------
    print("\n[8/8] Creating spatial grid features ...")

    # Simple reproducible geographic grid at 0.01-degree resolution (~1 km).
    # These are NOT official administrative boundaries.
    df["latitude_grid"]  = df["latitude"].round(2)
    df["longitude_grid"] = df["longitude"].round(2)

    n_grid_cells = df[["latitude_grid", "longitude_grid"]].drop_duplicates().shape[0]
    print("      Unique spatial grid cells (0.01deg x 0.01deg): {:,}".format(n_grid_cells))

    # ------------------------------------------------------------------
    # 10. Observation identifier
    # ------------------------------------------------------------------
    df["observation_id"] = build_observation_id(df)

    # ------------------------------------------------------------------
    # 11. Verify row count integrity
    # ------------------------------------------------------------------
    n_output = len(df)
    if n_output != n_input:
        sys.exit(
            "[CRITICAL] Row count mismatch! Input: {:,}, Output: {:,}. "
            "The pipeline must not alter the number of observations.".format(n_input, n_output)
        )
    print("\n[OK] Row count verified: {:,} in -> {:,} out (unchanged).".format(n_input, n_output))

    # ------------------------------------------------------------------
    # 12. Save output CSV
    # ------------------------------------------------------------------
    print("\n[Saving] Writing feature CSV ...\n         {}".format(OUTPUT_CSV))
    df.to_csv(OUTPUT_CSV, index=False)
    print("         Done.")

    # ------------------------------------------------------------------
    # 13. Build and save the feature engineering report
    # ------------------------------------------------------------------
    print("\n[Saving] Writing report ...\n         {}".format(REPORT_FILE))

    engineered_columns = [c for c in df.columns if c not in original_columns]

    # Missing value summary
    missing_lines = []
    for col in df.columns:
        n_miss = df[col].isna().sum()
        if n_miss > 0:
            missing_lines.append("  {:<32s}: {:>10,} missing".format(col, n_miss))
    if not missing_lines:
        missing_lines = ["  (none -- no missing values detected)"]

    sep = "=" * 80
    report_parts = [
        sep,
        "HeatWatch -- FIRMS Feature Engineering Report",
        sep,
        "Generated at   : {}".format(pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")),
        "Script         : {}".format(Path(__file__).resolve()),
        "",
        "INPUT",
        "-----",
        "File           : {}".format(INPUT_FILE),
        "Rows (input)   : {:,}".format(n_input),
        "Columns        : {}".format(len(original_columns)),
        "Original cols  : {}".format(original_columns),
        "",
        "OUTPUT",
        "------",
        "File           : {}".format(OUTPUT_CSV),
        "Rows (output)  : {:,}".format(n_output),
        "Row delta      : {:+,}  (must be 0)".format(n_output - n_input),
        "",
        "ENGINEERED COLUMNS ADDED ({})".format(len(engineered_columns)),
        "-" * 55,
    ]
    for c in engineered_columns:
        report_parts.append("  {}".format(c))

    report_parts += [
        "",
        "DATE RANGE",
        "----------",
        "Min acq_date   : {}".format(df["acq_date"].min().date()),
        "Max acq_date   : {}".format(df["acq_date"].max().date()),
        "",
        "CONFIDENCE DISTRIBUTION (original column)",
        "-" * 43,
        df["confidence"].value_counts(dropna=False).to_string(),
        "",
        "CONFIDENCE SCORE DISTRIBUTION (engineered)",
        "-" * 44,
        df["confidence_score"].value_counts(dropna=False).to_string(),
        "",
        "TYPE DISTRIBUTION",
        "-" * 18,
        df["type"].value_counts(dropna=False).to_string(),
        "",
        "DAY / NIGHT DISTRIBUTION",
        "-" * 25,
        df["daynight"].value_counts(dropna=False).to_string(),
        "",
        "FRP SUMMARY",
        "-" * 12,
        "Negative FRP count : {:,}".format(n_frp_neg),
        "Valid FRP count    : {:,}".format(n_frp_valid),
        "FRP original min   : {:.4f}".format(df["frp"].min()),
        "FRP original max   : {:.4f}".format(df["frp"].max()),
        "FRP model    min   : {:.4f}".format(df["frp_model"].min()),
        "FRP model    max   : {:.4f}".format(df["frp_model"].max()),
        "",
        "SPATIAL GRID (0.01deg x 0.01deg)",
        "-" * 34,
        "Unique grid cells  : {:,}".format(n_grid_cells),
        "",
        "MISSING VALUE SUMMARY",
        "-" * 22,
    ] + missing_lines + ["", sep, ""]

    report_text = "\n".join(report_parts)

    with open(REPORT_FILE, "w", encoding="utf-8") as fh:
        fh.write(report_text)

    print("         Done.\n")
    print("=" * 70)
    print("Feature engineering complete.")
    print("  Output CSV : {}".format(OUTPUT_CSV))
    print("  Report     : {}".format(REPORT_FILE))
    print("=" * 70)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
