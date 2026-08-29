"""
HeatWatch -- FIRMS Feature Dataset Verification Script
======================================================
Project  : Urban/Industrial Heat & Thermal Anomaly Detection
Target   : dataset/processed/firms/firms_india_2022_2024_features.csv

Purpose
-------
Independently verify the integrity of the engineered feature dataset
produced by feature_engineering.py.

Rules
-----
* Read-only -- this script never modifies any file.
* No new datasets are created.
* No packages are installed or downloaded.
* Pandas only.
"""

import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths (resolved relative to this script's location)
# ---------------------------------------------------------------------------
SCRIPT_DIR  = Path(__file__).resolve().parent
FEATURE_CSV = SCRIPT_DIR / "firms_india_2022_2024_features.csv"

# ---------------------------------------------------------------------------
# Expected values (from the master prompt and pipeline run)
# ---------------------------------------------------------------------------
EXPECTED_ROW_COUNT = 1_723_639

EXPECTED_ORIGINAL_COLUMNS = [
    "latitude", "longitude",
    "bright_ti4", "scan", "track",
    "acq_date", "acq_time",
    "satellite", "instrument",
    "confidence", "version",
    "bright_ti5", "frp",
    "daynight", "type", "year",
]

EXPECTED_ENGINEERED_COLUMNS = [
    "month",
    "day",
    "day_of_year",
    "day_of_week",
    "acquisition_hour",
    "acquisition_minute",
    "brightness_difference",
    "confidence_score",
    "frp_valid",
    "frp_model",
    "latitude_grid",
    "longitude_grid",
    "observation_id",
]

# Columns that must have zero missing values
NO_MISSING_REQUIRED = [
    "latitude", "longitude",
    "bright_ti4", "bright_ti5",
    "frp", "frp_model", "frp_valid",
    "scan", "track",
    "acq_time",
    "satellite", "instrument",
    "confidence", "type", "daynight",
    "month", "day", "day_of_year", "day_of_week",
    "acquisition_hour", "acquisition_minute",
    "brightness_difference",
    "latitude_grid", "longitude_grid",
    "observation_id",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def banner(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def result(label, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    line   = "[{}] {}".format(status, label)
    if detail:
        line += "  |  {}".format(detail)
    print(line)
    return passed


# ---------------------------------------------------------------------------
# Main verification
# ---------------------------------------------------------------------------

def main():
    failures = []

    # -----------------------------------------------------------------------
    # Load
    # -----------------------------------------------------------------------
    banner("HeatWatch -- FIRMS Feature Dataset Verification")

    if not FEATURE_CSV.exists():
        print("[FAIL] Feature CSV not found: {}".format(FEATURE_CSV))
        sys.exit(1)

    print("\nLoading: {}".format(FEATURE_CSV))
    df = pd.read_csv(FEATURE_CSV, low_memory=False)

    # Parse acq_date for date checks
    df["acq_date"] = pd.to_datetime(df["acq_date"], errors="coerce")

    # -----------------------------------------------------------------------
    # 1. Total row count
    # -----------------------------------------------------------------------
    banner("1. ROW COUNT")
    n_rows = len(df)
    print("   Observed : {:,}".format(n_rows))
    print("   Expected : {:,}".format(EXPECTED_ROW_COUNT))
    ok = result("Row count matches expected", n_rows == EXPECTED_ROW_COUNT,
                "{:,} rows".format(n_rows))
    if not ok:
        failures.append("Row count: expected {:,}, got {:,}".format(EXPECTED_ROW_COUNT, n_rows))

    # -----------------------------------------------------------------------
    # 2. Total column count
    # -----------------------------------------------------------------------
    banner("2. COLUMN COUNT")
    n_cols = len(df.columns)
    print("   Total columns : {}".format(n_cols))

    # -----------------------------------------------------------------------
    # 3. Complete column list
    # -----------------------------------------------------------------------
    banner("3. COLUMN LIST")
    for c in df.columns:
        print("   {}".format(c))

    # -----------------------------------------------------------------------
    # 4. Missing values for every column
    # -----------------------------------------------------------------------
    banner("4. MISSING VALUES (all columns)")
    any_unexpected_missing = False
    for col in df.columns:
        n_miss = df[col].isna().sum()
        pct    = 100.0 * n_miss / n_rows if n_rows else 0
        flag   = "<-- !!!" if (col in NO_MISSING_REQUIRED and n_miss > 0) else ""
        print("   {:<32s}: {:>10,} missing  ({:.4f}%)  {}".format(col, n_miss, pct, flag))
        if col in NO_MISSING_REQUIRED and n_miss > 0:
            any_unexpected_missing = True
            failures.append("Unexpected missing values in '{}': {:,}".format(col, n_miss))

    ok = result("No unexpected missing values in required columns",
                not any_unexpected_missing)
    if not ok and any_unexpected_missing:
        pass  # already appended to failures above

    # -----------------------------------------------------------------------
    # 5. Duplicate observation_id
    # -----------------------------------------------------------------------
    banner("5. OBSERVATION_ID UNIQUENESS")
    if "observation_id" not in df.columns:
        print("   [FAIL] observation_id column is missing.")
        failures.append("observation_id column missing")
    else:
        n_dupes = df["observation_id"].duplicated().sum()
        print("   Duplicate observation_id count : {:,}".format(n_dupes))
        ok = result("observation_id is unique", n_dupes == 0,
                    "{:,} duplicates".format(n_dupes))
        if not ok:
            failures.append("observation_id has {:,} duplicates".format(n_dupes))

    # -----------------------------------------------------------------------
    # 6. Date minimum and maximum
    # -----------------------------------------------------------------------
    banner("6. DATE RANGE")
    if "acq_date" in df.columns:
        n_invalid_dates = df["acq_date"].isna().sum()
        print("   Min acq_date     : {}".format(df["acq_date"].min()))
        print("   Max acq_date     : {}".format(df["acq_date"].max()))
        print("   Invalid/null     : {:,}".format(n_invalid_dates))
        ok = result("acq_date has no invalid values", n_invalid_dates == 0,
                    "{:,} null dates".format(n_invalid_dates))
        if not ok:
            failures.append("acq_date has {:,} invalid/null values".format(n_invalid_dates))
    else:
        print("   [FAIL] acq_date column not found.")
        failures.append("acq_date column missing")

    # -----------------------------------------------------------------------
    # 7. Year distribution
    # -----------------------------------------------------------------------
    banner("7. YEAR DISTRIBUTION")
    if "year" in df.columns:
        print(df["year"].value_counts(dropna=False).sort_index().to_string())

    # -----------------------------------------------------------------------
    # 8. Confidence distribution (original)
    # -----------------------------------------------------------------------
    banner("8. CONFIDENCE DISTRIBUTION (original)")
    if "confidence" in df.columns:
        print(df["confidence"].value_counts(dropna=False).to_string())

    # -----------------------------------------------------------------------
    # 9. confidence_score distribution (engineered)
    # -----------------------------------------------------------------------
    banner("9. CONFIDENCE_SCORE DISTRIBUTION (engineered)")
    if "confidence_score" in df.columns:
        print(df["confidence_score"].value_counts(dropna=False).to_string())

    # -----------------------------------------------------------------------
    # 10. Day / Night distribution
    # -----------------------------------------------------------------------
    banner("10. DAY / NIGHT DISTRIBUTION")
    if "daynight" in df.columns:
        print(df["daynight"].value_counts(dropna=False).to_string())

    # -----------------------------------------------------------------------
    # 11. frp_valid distribution
    # -----------------------------------------------------------------------
    banner("11. FRP_VALID DISTRIBUTION")
    if "frp_valid" in df.columns:
        print(df["frp_valid"].value_counts(dropna=False).to_string())

    # -----------------------------------------------------------------------
    # 12. Negative original FRP values
    # -----------------------------------------------------------------------
    banner("12. NEGATIVE FRP (original column)")
    if "frp" in df.columns:
        n_neg_frp = (df["frp"] < 0).sum()
        print("   Negative FRP count : {:,}".format(n_neg_frp))
        print("   FRP min            : {:.4f}".format(df["frp"].min()))
        print("   FRP max            : {:.4f}".format(df["frp"].max()))

    # -----------------------------------------------------------------------
    # 13. frp_model min / max
    # -----------------------------------------------------------------------
    banner("13. FRP_MODEL (clipped, min >= 0)")
    if "frp_model" in df.columns:
        frp_model_min = df["frp_model"].min()
        frp_model_max = df["frp_model"].max()
        print("   frp_model min : {:.4f}".format(frp_model_min))
        print("   frp_model max : {:.4f}".format(frp_model_max))
        ok = result("frp_model min >= 0", frp_model_min >= 0,
                    "min = {:.4f}".format(frp_model_min))
        if not ok:
            failures.append("frp_model has values below 0 (min = {:.4f})".format(frp_model_min))

    # -----------------------------------------------------------------------
    # 14. brightness_difference min / max
    # -----------------------------------------------------------------------
    banner("14. BRIGHTNESS_DIFFERENCE")
    if "brightness_difference" in df.columns:
        print("   Min : {:.4f}".format(df["brightness_difference"].min()))
        print("   Max : {:.4f}".format(df["brightness_difference"].max()))
        print("   Mean: {:.4f}".format(df["brightness_difference"].mean()))
        print("   Std : {:.4f}".format(df["brightness_difference"].std()))

    # -----------------------------------------------------------------------
    # 15. Unique latitude_grid values
    # -----------------------------------------------------------------------
    banner("15. UNIQUE LATITUDE_GRID VALUES")
    if "latitude_grid" in df.columns:
        n_lat = df["latitude_grid"].nunique()
        print("   Unique latitude_grid  : {:,}".format(n_lat))

    # -----------------------------------------------------------------------
    # 16. Unique longitude_grid values
    # -----------------------------------------------------------------------
    banner("16. UNIQUE LONGITUDE_GRID VALUES")
    if "longitude_grid" in df.columns:
        n_lon = df["longitude_grid"].nunique()
        print("   Unique longitude_grid : {:,}".format(n_lon))

    # -----------------------------------------------------------------------
    # 17. Unique spatial grid cells (lat + lon combined)
    # -----------------------------------------------------------------------
    banner("17. UNIQUE SPATIAL GRID CELLS")
    if "latitude_grid" in df.columns and "longitude_grid" in df.columns:
        n_cells = df[["latitude_grid", "longitude_grid"]].drop_duplicates().shape[0]
        print("   Unique grid cells (0.01deg x 0.01deg) : {:,}".format(n_cells))

    # -----------------------------------------------------------------------
    # 18. observation_id uniqueness (summary re-check)
    # -----------------------------------------------------------------------
    banner("18. OBSERVATION_ID UNIQUENESS SUMMARY")
    if "observation_id" in df.columns:
        n_unique_ids = df["observation_id"].nunique()
        print("   Total rows        : {:,}".format(n_rows))
        print("   Unique obs IDs    : {:,}".format(n_unique_ids))
        print("   IDs == rows       : {}".format(n_unique_ids == n_rows))

    # -----------------------------------------------------------------------
    # 19. latitude / longitude missing values
    # -----------------------------------------------------------------------
    banner("19. LATITUDE / LONGITUDE MISSING VALUES")
    for col in ["latitude", "longitude"]:
        if col in df.columns:
            n_miss = df[col].isna().sum()
            print("   {} missing : {:,}".format(col, n_miss))
            ok = result("{} has no missing values".format(col), n_miss == 0)
            if not ok:
                failures.append("{} has {:,} missing values".format(col, n_miss))

    # -----------------------------------------------------------------------
    # 20. All engineered columns exist
    # -----------------------------------------------------------------------
    banner("20. ENGINEERED COLUMNS PRESENCE CHECK")
    missing_eng_cols = [c for c in EXPECTED_ENGINEERED_COLUMNS if c not in df.columns]
    if missing_eng_cols:
        for c in missing_eng_cols:
            print("   [MISSING] {}".format(c))
        failures.append("Missing engineered columns: {}".format(missing_eng_cols))
    else:
        print("   All {} expected engineered columns are present.".format(
            len(EXPECTED_ENGINEERED_COLUMNS)))
        for c in EXPECTED_ENGINEERED_COLUMNS:
            print("   [OK] {}".format(c))
    ok = result("All engineered columns present", len(missing_eng_cols) == 0)

    # -----------------------------------------------------------------------
    # FINAL SUMMARY
    # -----------------------------------------------------------------------
    print("\n")
    print("=" * 40)
    print("FINAL VERIFICATION")
    print("=" * 40)

    final_checks = [
        ("Row count = {:,}".format(EXPECTED_ROW_COUNT),           n_rows == EXPECTED_ROW_COUNT),
        ("observation_id has no duplicates",
         "observation_id" in df.columns and df["observation_id"].duplicated().sum() == 0),
        ("All engineered columns present",                         len(missing_eng_cols) == 0),
        ("latitude has no missing values",
         "latitude" in df.columns and df["latitude"].isna().sum() == 0),
        ("longitude has no missing values",
         "longitude" in df.columns and df["longitude"].isna().sum() == 0),
        ("acq_date has no invalid values",
         "acq_date" in df.columns and df["acq_date"].isna().sum() == 0),
        ("No unexpected missing values in required columns",       not any_unexpected_missing),
        ("frp_model min >= 0",
         "frp_model" in df.columns and df["frp_model"].min() >= 0),
    ]

    all_passed = True
    for label, passed in final_checks:
        status = "PASS" if passed else "FAIL"
        print("[{}] {}".format(status, label))
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("RESULT: PASS -- All validation checks passed.")
    else:
        print("RESULT: FAIL -- The following issues were detected:")
        for f in failures:
            print("  - {}".format(f))

    print("=" * 40)
    sys.exit(0 if all_passed else 1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
