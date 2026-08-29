"""
HeatWatch -- Extract India Boundary from Natural Earth Countries
===============================================================
Purpose : Filter the full Natural Earth Admin-0 Countries GeoJSON
          (248 features) to a single India-only GeoJSON.

Source   : dataset/raw/boundaries/india_boundary.geojson
           (Natural Earth 10m Admin-0 Countries -- all countries)

Filter   : ADMIN == "India"  AND  ISO_A3 == "IND"
           (double key to unambiguously exclude "Indian Ocean Territories"
           and "British Indian Ocean Territory")

Output   : dataset/raw/boundaries/india_boundary.geojson
           (OVERWRITES the original -- original is backed up first)

Backup   : dataset/raw/boundaries/india_boundary.all_countries.bak.geojson
           (the full 248-country file, preserved untouched)

Rules:
  * No external downloads.
  * No CDSE API calls.
  * No imagery.
  * No FIRMS modification.
  * Original all-countries file backed up before overwrite.

Exit codes:
  0 = success
  1 = failure
"""

import sys
import json
import shutil
import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR   = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent

BOUNDARY_DIR  = PROJECT_ROOT / "dataset" / "raw" / "boundaries"
SOURCE_FILE   = BOUNDARY_DIR / "india_boundary.geojson"
BACKUP_FILE   = BOUNDARY_DIR / "india_boundary.all_countries.bak.geojson"
OUTPUT_FILE   = BOUNDARY_DIR / "india_boundary.geojson"   # same path as source

# Filter criteria (both must match)
FILTER_ADMIN  = "India"
FILTER_ISO_A3 = "IND"

# Expected India bounding box tolerances
INDIA_MIN_LON = 66.0
INDIA_MAX_LON = 100.0
INDIA_MIN_LAT =  5.0
INDIA_MAX_LAT = 39.0

# ---------------------------------------------------------------------------

def ts():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def flat_coords(geom):
    gt = geom.get("type", "")
    c  = geom.get("coordinates", [])
    if gt == "Polygon":
        for ring in c:
            for pt in ring:
                yield pt[0], pt[1]
    elif gt == "MultiPolygon":
        for poly in c:
            for ring in poly:
                for pt in ring:
                    yield pt[0], pt[1]

def sep():
    print("=" * 62)

def main():
    sep()
    print("HeatWatch -- Extract India Boundary")
    sep()
    print("Timestamp : {}".format(ts()))
    print()

    # -----------------------------------------------------------------------
    # Step 1 -- Verify source exists
    # -----------------------------------------------------------------------
    print("[1] Verifying source file ...")
    if not SOURCE_FILE.exists():
        print("  [FAIL] Source not found: {}".format(SOURCE_FILE))
        sys.exit(1)
    size_mb = SOURCE_FILE.stat().st_size / (1024 * 1024)
    print("  Source  : {}".format(SOURCE_FILE))
    print("  Size    : {:.2f} MB".format(size_mb))

    # -----------------------------------------------------------------------
    # Step 2 -- Load and verify it's the all-countries file
    # -----------------------------------------------------------------------
    print()
    print("[2] Loading source GeoJSON ...")
    with open(SOURCE_FILE, encoding="utf-8") as fh:
        gj = json.load(fh)

    n_features = len(gj.get("features", []))
    print("  GeoJSON type : {}".format(gj.get("type")))
    print("  Features     : {}".format(n_features))

    if n_features < 2:
        print("  [FAIL] Expected the all-countries file (248 features). "
              "Got only {} feature(s).".format(n_features))
        print("         The file may already be India-only.")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Step 3 -- Back up the original BEFORE any modification
    # -----------------------------------------------------------------------
    print()
    print("[3] Backing up original (all-countries) file ...")
    shutil.copy2(SOURCE_FILE, BACKUP_FILE)
    bak_size_mb = BACKUP_FILE.stat().st_size / (1024 * 1024)
    print("  Backup  : {}".format(BACKUP_FILE))
    print("  Size    : {:.2f} MB  (original preserved)".format(bak_size_mb))

    # -----------------------------------------------------------------------
    # Step 4 -- Filter to India
    # -----------------------------------------------------------------------
    print()
    print("[4] Filtering to India (ADMIN='{}', ISO_A3='{}') ...".format(
        FILTER_ADMIN, FILTER_ISO_A3))

    india_features = []
    for feat in gj["features"]:
        props = feat.get("properties") or {}
        admin   = props.get("ADMIN",   "")
        iso_a3  = props.get("ISO_A3",  "")
        if admin == FILTER_ADMIN and iso_a3 == FILTER_ISO_A3:
            india_features.append(feat)
            print("  MATCH: ADMIN={!r}  ISO_A3={!r}  ISO_A2={!r}".format(
                admin, iso_a3, props.get("ISO_A2", "?")))

    if len(india_features) == 0:
        print("  [FAIL] No feature matched ADMIN='{}' AND ISO_A3='{}'.".format(
            FILTER_ADMIN, FILTER_ISO_A3))
        print("         Check the property names in the source file.")
        sys.exit(1)

    if len(india_features) > 1:
        print("  [WARNING] {} features matched -- expected exactly 1. "
              "Using all matched features.".format(len(india_features)))

    print("  {} feature(s) selected for India.".format(len(india_features)))

    # -----------------------------------------------------------------------
    # Step 5 -- Validate geometry bounds before writing
    # -----------------------------------------------------------------------
    print()
    print("[5] Validating India geometry bounds ...")
    lons = []
    lats = []
    for feat in india_features:
        geom = feat.get("geometry") or {}
        for lon, lat in flat_coords(geom):
            lons.append(lon)
            lats.append(lat)

    if not lons:
        print("  [FAIL] No coordinates found in India feature geometry.")
        sys.exit(1)

    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)
    print("  Bounding box:")
    print("    min_lon : {:.6f}  (expect >= {})".format(min_lon, INDIA_MIN_LON))
    print("    max_lon : {:.6f}  (expect <= {})".format(max_lon, INDIA_MAX_LON))
    print("    min_lat : {:.6f}  (expect >= {})".format(min_lat, INDIA_MIN_LAT))
    print("    max_lat : {:.6f}  (expect <= {})".format(max_lat, INDIA_MAX_LAT))

    bbox_ok = (
        INDIA_MIN_LON <= min_lon and max_lon <= INDIA_MAX_LON and
        INDIA_MIN_LAT <= min_lat and max_lat <= INDIA_MAX_LAT
    )
    if not bbox_ok:
        print("  [FAIL] Bounding box is outside expected India extent.")
        print("         The selected feature may not be India.")
        # Restore from backup and abort
        shutil.copy2(BACKUP_FILE, SOURCE_FILE)
        print("  [RESTORED] Original file restored from backup.")
        sys.exit(1)

    print("  Bounding box is within expected India extent. OK.")

    # -----------------------------------------------------------------------
    # Step 6 -- Build output GeoJSON and write
    # -----------------------------------------------------------------------
    print()
    print("[6] Writing India-only GeoJSON ...")

    out_gj = {
        "type"    : "FeatureCollection",
        "features": india_features,
    }
    # Preserve CRS if original had one
    if "crs" in gj:
        out_gj["crs"] = gj["crs"]

    out_json = json.dumps(out_gj, separators=(",", ":"))
    OUTPUT_FILE.write_text(out_json, encoding="utf-8")

    out_size_kb = OUTPUT_FILE.stat().st_size / 1024
    print("  Output  : {}".format(OUTPUT_FILE))
    print("  Size    : {:.1f} KB".format(out_size_kb))
    print("  Features: {}".format(len(india_features)))

    # -----------------------------------------------------------------------
    # Step 7 -- Final verification read-back
    # -----------------------------------------------------------------------
    print()
    print("[7] Read-back verification ...")
    with open(OUTPUT_FILE, encoding="utf-8") as fh:
        verify = json.load(fh)
    n_out = len(verify.get("features", []))
    geom_types = set(
        f.get("geometry", {}).get("type", "?")
        for f in verify["features"]
    )
    admin_values = set(
        (f.get("properties") or {}).get("ADMIN", "?")
        for f in verify["features"]
    )
    print("  Features in output file : {}".format(n_out))
    print("  Geometry types          : {}".format(geom_types))
    print("  ADMIN values            : {}".format(admin_values))

    ok = (n_out == len(india_features) and
          admin_values == {"India"} and
          geom_types <= {"Polygon", "MultiPolygon"})

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print()
    sep()
    if ok:
        print("RESULT: PASS")
        print()
        print("  Original (all countries) preserved at:")
        print("    {}".format(BACKUP_FILE))
        print()
        print("  India-only boundary written to:")
        print("    {}".format(OUTPUT_FILE))
        print()
        print("  Next step:")
        print("    Run validate_india_boundary.py to confirm the new file passes.")
        print("    Then re-run discover_india_sentinel2.py for true India filtering.")
        sep()
        sys.exit(0)
    else:
        print("RESULT: FAIL -- read-back verification failed.")
        print("  Restoring original from backup ...")
        shutil.copy2(BACKUP_FILE, OUTPUT_FILE)
        print("  Original restored.")
        sep()
        sys.exit(1)


if __name__ == "__main__":
    main()
