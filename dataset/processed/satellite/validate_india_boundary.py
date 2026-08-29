"""
HeatWatch -- India Boundary GeoJSON Validation
===============================================
Purpose : Validate that dataset/raw/boundaries/india_boundary.geojson
          is a usable India polygon for spatial filtering.

Checks:
  [1] File exists and is readable
  [2] Valid JSON
  [3] Valid GeoJSON type (FeatureCollection or Feature)
  [4] At least one feature
  [5] Geometry type is Polygon or MultiPolygon
  [6] Geometry is not empty/null
  [7] Bounding box is within reasonable lon/lat limits (-180..180, -90..90)
  [8] Bounding box roughly covers India
        Expected: min_lon ~68, min_lat ~7, max_lon ~98, max_lat ~37
  [9] Shapely can construct and validate the geometry
  [10] Geometry is topologically valid (Shapely is_valid)

Exit codes:
  0 = PASS
  1 = FAIL
"""

import sys
import json
import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR    = Path(__file__).resolve().parent
PROJECT_ROOT  = SCRIPT_DIR.parent.parent.parent

BOUNDARY_FILE = PROJECT_ROOT / "dataset" / "raw" / "boundaries" / "india_boundary.geojson"
REPORT_FILE   = SCRIPT_DIR / "india_boundary_validation_report.txt"

# ---------------------------------------------------------------------------
# India rough bounding box tolerances
# The actual India bbox is approx [68.1, 7.9, 97.4, 37.1].
# We allow +-2 degrees of tolerance to accommodate different data sources.
# ---------------------------------------------------------------------------
INDIA_MIN_LON_EXPECTED = 66.0
INDIA_MAX_LON_EXPECTED = 100.0
INDIA_MIN_LAT_EXPECTED = 5.0
INDIA_MAX_LAT_EXPECTED = 39.0

# ---------------------------------------------------------------------------
# Shapely optional
# ---------------------------------------------------------------------------
SHAPELY_AVAILABLE = False
try:
    from shapely.geometry import shape as shapely_shape
    from shapely.ops import unary_union
    SHAPELY_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ts():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def sep(w=62):
    print("=" * w)

def hdr(n, title):
    print()
    sep()
    print("[{}] {}".format(n, title))
    sep()

failures = []
warnings = []

def ck(label, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    line   = "  [{}] {}".format(status, label)
    if detail:
        line += "  -- {}".format(detail)
    print(line)
    if not passed:
        failures.append(label + (": " + detail if detail else ""))
    return passed

def warn(msg):
    print("  [WARN] {}".format(msg))
    warnings.append(msg)

def flat_coords(geom_obj):
    """Yield all (lon, lat) pairs from any GeoJSON geometry dict."""
    gt = geom_obj.get("type", "")
    coords = geom_obj.get("coordinates", [])
    if gt == "Point":
        yield tuple(coords[:2])
    elif gt in ("MultiPoint", "LineString"):
        for c in coords:
            yield tuple(c[:2])
    elif gt in ("MultiLineString", "Polygon"):
        for ring in coords:
            for c in ring:
                yield tuple(c[:2])
    elif gt == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                for c in ring:
                    yield tuple(c[:2])
    elif gt == "GeometryCollection":
        for sub in geom_obj.get("geometries", []):
            yield from flat_coords(sub)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    run_ts = ts()
    sep()
    print("HeatWatch -- India Boundary GeoJSON Validation")
    sep()
    print("Timestamp : {}".format(run_ts))
    print("File      : {}".format(BOUNDARY_FILE))
    print("Shapely   : {}".format("available" if SHAPELY_AVAILABLE else "NOT installed"))

    report_lines = []  # collected for report file

    # -----------------------------------------------------------------------
    # [1] File existence and size
    # -----------------------------------------------------------------------
    hdr(1, "File Existence and Readability")
    if not ck("File exists", BOUNDARY_FILE.exists(),
               str(BOUNDARY_FILE)):
        print("\n[FATAL] File not found -- cannot continue.")
        _write_report(report_lines, run_ts, {})
        sys.exit(1)

    file_size   = BOUNDARY_FILE.stat().st_size
    size_kb     = file_size / 1024
    ck("File size > 0 bytes", file_size > 0,
       "{:.1f} KB ({:,} bytes)".format(size_kb, file_size))
    print("  File size : {:.1f} KB ({:,} bytes)".format(size_kb, file_size))

    try:
        raw_text = BOUNDARY_FILE.read_text(encoding="utf-8")
        ck("File readable as UTF-8", True)
    except UnicodeDecodeError:
        try:
            raw_text = BOUNDARY_FILE.read_text(encoding="latin-1")
            warn("File read as latin-1 (not UTF-8) -- should be UTF-8 for GeoJSON standard")
        except Exception as exc:
            ck("File readable", False, str(exc))
            sys.exit(1)

    # -----------------------------------------------------------------------
    # [2] JSON validity
    # -----------------------------------------------------------------------
    hdr(2, "JSON Validity")
    try:
        gj = json.loads(raw_text)
        ck("Valid JSON", True)
    except json.JSONDecodeError as exc:
        ck("Valid JSON", False, "Line {}: {}".format(exc.lineno, exc.msg))
        sys.exit(1)

    # -----------------------------------------------------------------------
    # [3] GeoJSON type
    # -----------------------------------------------------------------------
    hdr(3, "GeoJSON Type")
    gj_type = gj.get("type", "(missing)")
    print("  type field : {}".format(gj_type))
    valid_types = {"FeatureCollection", "Feature",
                   "Polygon", "MultiPolygon",
                   "GeometryCollection"}
    ck("type field present and known", gj_type in valid_types,
       "got '{}'".format(gj_type))

    # Normalise to a list of geometry dicts
    geom_dicts = []
    feature_props = []
    n_features = 0

    if gj_type == "FeatureCollection":
        features = gj.get("features", [])
        n_features = len(features)
        ck("FeatureCollection has at least 1 feature", n_features >= 1,
           "{} features".format(n_features))
        for feat in features:
            g = feat.get("geometry")
            if g:
                geom_dicts.append(g)
            feature_props.append(feat.get("properties") or {})
    elif gj_type == "Feature":
        n_features = 1
        ck("Feature present", True)
        g = gj.get("geometry")
        if g:
            geom_dicts.append(g)
        feature_props.append(gj.get("properties") or {})
    else:
        # Bare geometry
        n_features = 1
        ck("Bare geometry (Polygon/MultiPolygon)", gj_type in
           ("Polygon", "MultiPolygon"), "got '{}'".format(gj_type))
        geom_dicts.append(gj)

    print("  Features   : {}".format(n_features))

    # -----------------------------------------------------------------------
    # [4] Geometry types
    # -----------------------------------------------------------------------
    hdr(4, "Geometry Types")
    if not geom_dicts:
        ck("At least one non-null geometry found", False,
           "all geometries are null/missing")
        sys.exit(1)

    geom_types = [g.get("type", "?") for g in geom_dicts]
    type_counts = {}
    for t in geom_types:
        type_counts[t] = type_counts.get(t, 0) + 1
    print("  Geometry types found:")
    for t, c in type_counts.items():
        print("    {:20s}: {:,}".format(t, c))

    allowed_geom_types = {"Polygon", "MultiPolygon", "GeometryCollection"}
    bad_types = set(geom_types) - allowed_geom_types
    ck("All geometries are Polygon / MultiPolygon",
       len(bad_types) == 0,
       "unexpected: {}".format(bad_types) if bad_types else "")
    ck("At least one Polygon or MultiPolygon present",
       bool({"Polygon", "MultiPolygon"} & set(geom_types)))

    # -----------------------------------------------------------------------
    # [5] Coordinate range and bounding box
    # -----------------------------------------------------------------------
    hdr(5, "Coordinate Range and Bounding Box")
    all_lons = []
    all_lats = []
    for g in geom_dicts:
        for lon, lat in flat_coords(g):
            all_lons.append(lon)
            all_lats.append(lat)

    if all_lons:
        min_lon = min(all_lons)
        max_lon = max(all_lons)
        min_lat = min(all_lats)
        max_lat = max(all_lats)

        print("  Computed bounding box:")
        print("    min_lon : {:>12.6f}".format(min_lon))
        print("    min_lat : {:>12.6f}".format(min_lat))
        print("    max_lon : {:>12.6f}".format(max_lon))
        print("    max_lat : {:>12.6f}".format(max_lat))

        ck("Longitudes in [-180, 180]",
           -180 <= min_lon <= 180 and -180 <= max_lon <= 180,
           "got [{:.3f}, {:.3f}]".format(min_lon, max_lon))
        ck("Latitudes  in [-90,  90]",
           -90  <= min_lat <= 90  and -90  <= max_lat <= 90,
           "got [{:.3f}, {:.3f}]".format(min_lat, max_lat))

        # India approximate check (tolerant)
        lon_ok = (INDIA_MIN_LON_EXPECTED <= min_lon <= max_lon <= INDIA_MAX_LON_EXPECTED)
        lat_ok = (INDIA_MIN_LAT_EXPECTED <= min_lat <= max_lat <= INDIA_MAX_LAT_EXPECTED)

        ck("Bounding box min_lon in India range ({:.0f}..{:.0f})".format(
            INDIA_MIN_LON_EXPECTED, INDIA_MAX_LON_EXPECTED),
           lon_ok,
           "min={:.3f} max={:.3f}".format(min_lon, max_lon))
        ck("Bounding box min_lat in India range ({:.0f}..{:.0f})".format(
            INDIA_MIN_LAT_EXPECTED, INDIA_MAX_LAT_EXPECTED),
           lat_ok,
           "min={:.3f} max={:.3f}".format(min_lat, max_lat))

        if not lon_ok or not lat_ok:
            warn("Bounding box does not match expected India extent -- "
                 "verify the correct country was exported.")
    else:
        ck("Coordinates extractable", False, "no coordinate pairs found")
        min_lon = max_lon = min_lat = max_lat = None

    # -----------------------------------------------------------------------
    # [6] Shapely construction and validity
    # -----------------------------------------------------------------------
    hdr(6, "Shapely Geometry Validation")
    shapely_geom = None

    if not SHAPELY_AVAILABLE:
        warn("Shapely not installed -- skipping topology checks.")
        print("  Install: pip install shapely")
    else:
        shapes = []
        shape_errors = 0
        for g in geom_dicts:
            try:
                s = shapely_shape(g)
                shapes.append(s)
            except Exception as exc:
                shape_errors += 1
                warn("Could not build Shapely shape: {}".format(exc))

        ck("Shapely can load all geometries", shape_errors == 0,
           "{} error(s)".format(shape_errors) if shape_errors else "")

        if shapes:
            try:
                shapely_geom = unary_union(shapes)
                ck("unary_union succeeds", True)
                ck("Combined geometry is valid (is_valid)", shapely_geom.is_valid,
                   "run shapely.make_valid() to fix" if not shapely_geom.is_valid else "")
                ck("Combined geometry is not empty", not shapely_geom.is_empty)

                # Area sanity check (WGS-84 degrees squared -- rough only)
                area_deg2 = shapely_geom.area
                print("  Shapely area (deg^2)  : {:.2f}  "
                      "(India ~950 for reference)".format(area_deg2))
                ck("Area > 100 deg^2 (sanity: geometry is not tiny)",
                   area_deg2 > 100,
                   "{:.2f} deg^2".format(area_deg2))

            except Exception as exc:
                ck("unary_union and geometry ops succeed", False, str(exc))

    # -----------------------------------------------------------------------
    # [7] CRS check
    # -----------------------------------------------------------------------
    hdr(7, "CRS / Coordinate Reference System")
    crs = gj.get("crs")
    if crs is None:
        print("  No 'crs' member in GeoJSON (correct -- RFC 7946 default is WGS-84).")
        ck("CRS assumption: WGS-84 (EPSG:4326)", True)
    else:
        print("  'crs' member present: {}".format(json.dumps(crs)[:120]))
        # Old-style GeoJSON with explicit CRS
        crs_name = ""
        try:
            crs_name = crs.get("properties", {}).get("name", "")
        except Exception:
            pass
        is_wgs84 = ("4326" in crs_name or "WGS" in crs_name.upper()
                    or "CRS84" in crs_name.upper())
        ck("CRS is WGS-84 / EPSG:4326", is_wgs84,
           "crs.name='{}'".format(crs_name))
        if not is_wgs84:
            warn("Non-WGS-84 CRS detected. Re-project to EPSG:4326 "
                 "before using with STAC (which returns WGS-84 coordinates).")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print()
    sep()
    print("SUMMARY")
    sep()
    usable = len(failures) == 0

    stats = {
        "file"          : str(BOUNDARY_FILE),
        "file_size_kb"  : "{:.1f}".format(size_kb),
        "gj_type"       : gj_type,
        "n_features"    : n_features,
        "geom_types"    : type_counts,
        "min_lon"       : "{:.6f}".format(min_lon) if min_lon is not None else "N/A",
        "min_lat"       : "{:.6f}".format(min_lat) if min_lat is not None else "N/A",
        "max_lon"       : "{:.6f}".format(max_lon) if max_lon is not None else "N/A",
        "max_lat"       : "{:.6f}".format(max_lat) if max_lat is not None else "N/A",
        "shapely_valid" : (str(shapely_geom.is_valid) if shapely_geom else "N/A"),
        "warnings"      : warnings,
        "failures"      : failures,
        "usable"        : usable,
    }

    if usable:
        print("RESULT: PASS")
        print("  The India boundary file is valid and usable for spatial filtering.")
        print("  Re-run discover_india_sentinel2.py to apply the true India polygon.")
    else:
        print("RESULT: FAIL")
        for f in failures:
            print("  - {}".format(f))

    if warnings:
        print()
        print("WARNINGS:")
        for w in warnings:
            print("  ! {}".format(w))

    _write_report([run_ts], run_ts, stats)
    print()
    print("  Report : {}".format(REPORT_FILE))
    sep()
    sys.exit(0 if usable else 1)


def _write_report(_, run_ts, stats):
    lines = [
        "=" * 62,
        "HeatWatch -- India Boundary Validation Report",
        "=" * 62,
        "Timestamp       : {}".format(run_ts),
        "",
        "FILE",
        "-" * 40,
        "Path            : {}".format(stats.get("file", "N/A")),
        "Size            : {} KB".format(stats.get("file_size_kb", "N/A")),
        "",
        "GEOJSON STRUCTURE",
        "-" * 40,
        "GeoJSON type    : {}".format(stats.get("gj_type", "N/A")),
        "Features        : {}".format(stats.get("n_features", "N/A")),
        "Geometry types  : {}".format(stats.get("geom_types", "N/A")),
        "",
        "BOUNDING BOX",
        "-" * 40,
        "min_lon         : {}".format(stats.get("min_lon", "N/A")),
        "min_lat         : {}".format(stats.get("min_lat", "N/A")),
        "max_lon         : {}".format(stats.get("max_lon", "N/A")),
        "max_lat         : {}".format(stats.get("max_lat", "N/A")),
        "",
        "SHAPELY",
        "-" * 40,
        "Geometry valid  : {}".format(stats.get("shapely_valid", "N/A")),
        "",
    ]
    warnings = stats.get("warnings", [])
    failures = stats.get("failures", [])
    if warnings:
        lines.append("WARNINGS")
        lines.append("-" * 40)
        for w in warnings:
            lines.append("  ! {}".format(w))
        lines.append("")
    if failures:
        lines.append("FAILURES")
        lines.append("-" * 40)
        for f in failures:
            lines.append("  - {}".format(f))
        lines.append("")

    usable = stats.get("usable", False)
    lines += [
        "RESULT          : {}".format("PASS" if usable else "FAIL"),
        "Usable for spatial filtering: {}".format("YES" if usable else "NO"),
        "",
        "=" * 62,
        "",
    ]
    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
