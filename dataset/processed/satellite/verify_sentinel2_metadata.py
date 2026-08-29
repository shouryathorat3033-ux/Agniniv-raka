"""
HeatWatch -- Sentinel-2 India Metadata Verification Script
==========================================================
Project  : Urban/Industrial Heat & Thermal Anomaly Detection
Purpose  : Verify the integrity of the Sentinel-2 India metadata CSV
           produced by discover_india_sentinel2.py.

Exit codes:
  0 = PASS -- all checks passed
  1 = FAIL -- one or more checks failed
"""

import sys
import csv
from pathlib import Path
from datetime import date

# ---------------------------------------------------------------------------
# Dependency guards
# ---------------------------------------------------------------------------
try:
    import pandas as pd
except ImportError:
    print("[ERROR] pandas not installed.  pip install pandas")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR    = Path(__file__).resolve().parent
CSV_FILE      = SCRIPT_DIR / "sentinel2_india_2022_2024_metadata.csv"
REPORT_FILE   = SCRIPT_DIR / "sentinel2_india_2022_2024_metadata_report.txt"

# ---------------------------------------------------------------------------
# Expected schema
# ---------------------------------------------------------------------------
REQUIRED_COLUMNS = [
    "item_id",
    "collection",
    "acquisition_datetime",
    "acquisition_date",
    "cloud_cover",
    "platform",
    "constellation",
    "mgrs_tile",
    "bbox_min_lon",
    "bbox_min_lat",
    "bbox_max_lon",
    "bbox_max_lat",
    "geometry_available",
    "india_intersection",
    "stac_url",
    "s3_product_path",
    "imagery_downloaded",
]

EXPECTED_COLLECTION = "sentinel-2-l2a"
EXPECTED_PLATFORMS  = {"sentinel-2a", "sentinel-2b", "sentinel-2c"}
DATE_MIN = date(2022, 1, 1)
DATE_MAX = date(2024, 12, 31)
MAX_CLOUD_COVER = 20

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sep(w=62):
    print("=" * w)

def hdr(n, title):
    print()
    sep()
    print("[{}] {}".format(n, title))
    sep()

failures = []

def check(label, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    msg = "  [{}] {}".format(status, label)
    if detail:
        msg += " -- {}".format(detail)
    print(msg)
    if not passed:
        failures.append("{}: {}".format(label, detail) if detail else label)
    return passed

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    sep()
    print("HeatWatch -- Sentinel-2 Metadata Verification")
    sep()

    # -----------------------------------------------------------------------
    # [0] File existence
    # -----------------------------------------------------------------------
    hdr(0, "File Existence")
    if not check("CSV file exists", CSV_FILE.exists(),
                 str(CSV_FILE)):
        print("\n[FAIL] CSV not found -- run discover_india_sentinel2.py first.")
        sys.exit(1)

    check("Report file exists", REPORT_FILE.exists(), str(REPORT_FILE))

    # -----------------------------------------------------------------------
    # [1] Load CSV
    # -----------------------------------------------------------------------
    hdr(1, "Load CSV")
    try:
        df = pd.read_csv(CSV_FILE, dtype=str)
        check("CSV loads without error", True,
              "{:,} rows x {} cols".format(len(df), len(df.columns)))
    except Exception as exc:
        check("CSV loads without error", False, str(exc))
        sys.exit(1)

    # -----------------------------------------------------------------------
    # [2] Row count
    # -----------------------------------------------------------------------
    hdr(2, "Row Count")
    check("Row count > 0", len(df) > 0,
          "{:,} rows".format(len(df)))
    print("  Total rows : {:,}".format(len(df)))

    # -----------------------------------------------------------------------
    # [3] Required columns
    # -----------------------------------------------------------------------
    hdr(3, "Required Columns")
    actual_cols = set(df.columns.tolist())
    for col in REQUIRED_COLUMNS:
        check("Column '{}' present".format(col), col in actual_cols)
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in actual_cols]
    if missing_cols:
        print("  Missing columns: {}".format(missing_cols))
        sys.exit(1)

    # -----------------------------------------------------------------------
    # [4] item_id integrity
    # -----------------------------------------------------------------------
    hdr(4, "item_id Integrity")
    n_missing_id  = df["item_id"].isna().sum() + (df["item_id"] == "").sum()
    n_dup_id      = df.duplicated(subset=["item_id"]).sum()
    check("No missing item_id",   int(n_missing_id) == 0,
          "{} missing".format(n_missing_id))
    check("No duplicate item_id", int(n_dup_id) == 0,
          "{} duplicates".format(n_dup_id))

    # -----------------------------------------------------------------------
    # [5] Collection values
    # -----------------------------------------------------------------------
    hdr(5, "Collection Values")
    bad_collection = df[df["collection"] != EXPECTED_COLLECTION]
    check("All collection == '{}'".format(EXPECTED_COLLECTION),
          len(bad_collection) == 0,
          "{} wrong values".format(len(bad_collection)))

    # -----------------------------------------------------------------------
    # [6] Acquisition date range
    # -----------------------------------------------------------------------
    hdr(6, "Acquisition Date Range")
    df_dates = df["acquisition_date"].dropna()
    df_dates = df_dates[df_dates != ""]
    try:
        parsed_dates = pd.to_datetime(df_dates, errors="coerce").dt.date
        n_bad  = parsed_dates.isna().sum()
        n_low  = (parsed_dates < DATE_MIN).sum()
        n_high = (parsed_dates > DATE_MAX).sum()
        check("All dates parseable",            int(n_bad)  == 0,
              "{} unparseable".format(n_bad))
        check("All dates >= 2022-01-01",        int(n_low)  == 0,
              "{} before range".format(n_low))
        check("All dates <= 2024-12-31",        int(n_high) == 0,
              "{} after range".format(n_high))
        print("  Earliest : {}".format(parsed_dates.min()))
        print("  Latest   : {}".format(parsed_dates.max()))
        print("  Unique   : {:,}".format(parsed_dates.nunique()))
    except Exception as exc:
        check("Date parsing succeeded", False, str(exc))

    # -----------------------------------------------------------------------
    # [7] Cloud cover
    # -----------------------------------------------------------------------
    hdr(7, "Cloud Cover Values")
    cc_col = df["cloud_cover"].replace("", float("nan"))
    cc_num = pd.to_numeric(cc_col, errors="coerce")
    n_cc_missing = cc_num.isna().sum()
    n_cc_bad     = (cc_num > MAX_CLOUD_COVER).sum()
    print("  Rows with cloud cover  : {:,}".format(int(cc_num.notna().sum())))
    print("  Rows missing cloud     : {:,}".format(int(n_cc_missing)))
    check("No cloud_cover > {}%".format(MAX_CLOUD_COVER),
          int(n_cc_bad) == 0,
          "{} rows exceed threshold".format(n_cc_bad))

    # -----------------------------------------------------------------------
    # [8] imagery_downloaded always NO
    # -----------------------------------------------------------------------
    hdr(8, "imagery_downloaded Always NO")
    n_not_no = (df["imagery_downloaded"] != "NO").sum()
    check("All imagery_downloaded == NO", int(n_not_no) == 0,
          "{} rows have wrong value".format(n_not_no))

    # -----------------------------------------------------------------------
    # [9] india_intersection
    # -----------------------------------------------------------------------
    hdr(9, "india_intersection Values")
    allowed_vals = {"TRUE", "BBOX_ONLY"}
    actual_vals  = set(df["india_intersection"].dropna().unique())
    bad_india    = actual_vals - allowed_vals - {""}
    false_india  = (df["india_intersection"] == "FALSE").sum()
    check("No india_intersection == FALSE (excluded at filter stage)",
          int(false_india) == 0,
          "{} unexpected FALSE rows".format(false_india))
    check("All india_intersection in {{TRUE, BBOX_ONLY}}",
          len(bad_india) == 0,
          "unexpected values: {}".format(bad_india) if bad_india else "")
    bbox_only_count = (df["india_intersection"] == "BBOX_ONLY").sum()
    if bbox_only_count > 0:
        print()
        print("  [NOTE] {:,} rows have india_intersection = BBOX_ONLY".format(
            int(bbox_only_count)))
        print("         This means india_boundary.geojson was not available.")
        print("         The dataset cannot be claimed India-only until the")
        print("         boundary file is provided and the script re-run.")

    # -----------------------------------------------------------------------
    # [10] STAC URL and S3 path presence
    # -----------------------------------------------------------------------
    hdr(10, "URL / Path Presence")
    n_no_stac = ((df["stac_url"].isna()) | (df["stac_url"] == "")).sum()
    n_no_s3   = ((df["s3_product_path"].isna()) | (df["s3_product_path"] == "")).sum()
    check("STAC URL present on all rows", int(n_no_stac) == 0,
          "{} missing".format(n_no_stac))
    # S3 path is best-effort (may be empty if asset format changed)
    print("  Rows with s3_product_path : {:,}".format(
        ((df["s3_product_path"] != "") & df["s3_product_path"].notna()).sum()))
    if int(n_no_s3) > 0:
        print("  [NOTE] {:,} rows missing s3_product_path (non-fatal)".format(
            int(n_no_s3)))

    # -----------------------------------------------------------------------
    # [11] Platform values
    # -----------------------------------------------------------------------
    hdr(11, "Platform Values")
    platforms_found = set(df["platform"].dropna().unique()) - {""}
    unexpected_plat = platforms_found - EXPECTED_PLATFORMS
    check("All platforms are known Sentinel-2 platforms",
          len(unexpected_plat) == 0,
          "unexpected: {}".format(unexpected_plat) if unexpected_plat else "")
    print("  Platforms found:")
    for p, c in df["platform"].value_counts().items():
        print("    {:30s}: {:,}".format(p, c))

    # -----------------------------------------------------------------------
    # FINAL RESULT
    # -----------------------------------------------------------------------
    print()
    sep()
    print("FINAL RESULT")
    sep()
    if not failures:
        print("RESULT: PASS -- All checks passed.")
        print("        Rows verified : {:,}".format(len(df)))
        print()
        sep()
        sys.exit(0)
    else:
        print("RESULT: FAIL -- {} check(s) failed:".format(len(failures)))
        for f in failures:
            print("  - {}".format(f))
        print()
        sep()
        sys.exit(1)


if __name__ == "__main__":
    main()
