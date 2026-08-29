"""
HeatWatch -- India-Only Sentinel-2 L2A Metadata Discovery  (v2)
================================================================
Project  : Urban/Industrial Heat & Thermal Anomaly Detection
Purpose  : Retrieve METADATA ONLY for Sentinel-2 L2A scenes covering
           India for 2022-01-01 through 2024-12-31.

KEY FIXES IN v2
---------------
1. Correct pagination: follows next-link body (POST) exactly as returned
   by the CDSE STAC API.  Does NOT attempt to reconstruct tokens or GET
   the next URL.
2. Correct STAC endpoint:
     Initial search : https://catalogue.dataspace.copernicus.eu/stac/search
     Pagination     : https://stac.dataspace.copernicus.eu/v1/search
   (Next-link href is used verbatim -- no substitution.)
3. India boundary spatial filter:
     - Attempts to load dataset/raw/boundaries/india_boundary.geojson.
     - If found: uses Shapely to test footprint intersection with India polygon.
     - If missing: runs with bbox-only; sets india_intersection = BBOX_ONLY;
       clearly labels output as NOT verified India-only.
     - NEVER fabricates or approximates the boundary.

HARD REQUIREMENTS
-----------------
* NO imagery downloaded (no TIFF, JP2, SAFE, ZIP).
* NO FIRMS dataset modified.
* Credentials NEVER printed or written.
* Output: metadata-only CSV + plain-text report.

PAGINATION (confirmed from debug_stac_pagination_report.txt)
------------------------------------------------------------
The CDSE STAC API returns:
  links[0].rel    = "next"
  links[0].href   = "https://stac.dataspace.copernicus.eu/v1/search"
  links[0].method = "POST"
  links[0].body   = { "collections": [...], "bbox": [...], "datetime": "...",
                       "limit": N, "token": "next:<id>" }

Therefore: send the body verbatim to the href via POST.
Do NOT reconstruct the token. Do NOT GET the next URL.

GEOGRAPHIC FILTER
-----------------
Initial filter : India bbox [68.1, 7.9, 97.4, 37.1]  (STAC query)
Precise filter : India polygon from india_boundary.geojson (Shapely)
Fallback       : BBOX_ONLY if boundary file is missing

Scenes are RETAINED if their STAC footprint geometry INTERSECTS India.
Footprint intersection (not centroid) is used because S-2 tiles span borders.
"""

import csv
import sys
import json
import time
import datetime
from pathlib import Path
from collections import defaultdict
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Dependency guards
# ---------------------------------------------------------------------------
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("[ERROR] requests not installed.  pip install requests")
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("[ERROR] pandas not installed.  pip install pandas")
    sys.exit(1)

# Shapely is optional: used for India polygon intersection if boundary available
SHAPELY_AVAILABLE = False
try:
    from shapely.geometry import shape as shapely_shape, mapping
    from shapely.ops import unary_union
    SHAPELY_AVAILABLE = True
except ImportError:
    pass   # handled gracefully below

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR   = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent

BOUNDARY_FILE = PROJECT_ROOT / "dataset" / "raw" / "boundaries" / "india_boundary.geojson"
OUTPUT_CSV    = SCRIPT_DIR / "sentinel2_india_2022_2024_metadata.csv"
OUTPUT_REPORT = SCRIPT_DIR / "sentinel2_india_2022_2024_metadata_report.txt"

# ---------------------------------------------------------------------------
# Search configuration
# ---------------------------------------------------------------------------
# Initial search endpoint (confirmed working for page 1)
STAC_SEARCH_URL_INITIAL = "https://catalogue.dataspace.copernicus.eu/stac/search"

COLLECTION   = "sentinel-2-l2a"
INDIA_BBOX   = [68.1, 7.9, 97.4, 37.1]

# Year-by-year search ranges.
# CDSE returns results newest-first, so a combined 2022-2024 search with
# MAX_ITEMS=5000 would fill the cap with late-2024 data only.
# Searching each year independently guarantees coverage of all three years.
SEARCH_YEARS = [
    ("2022", "2022-01-01T00:00:00Z", "2022-12-31T23:59:59Z"),
    ("2023", "2023-01-01T00:00:00Z", "2023-12-31T23:59:59Z"),
    ("2024", "2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z"),
]

# Keep these for report backward-compat
DATE_START = SEARCH_YEARS[0][1]
DATE_END   = SEARCH_YEARS[-1][2]

MAX_ITEMS       = 5000   # hard safety cap
MAX_CLOUD_COVER = 20     # initial screening threshold (%)
PAGE_SIZE       = 100    # items per page (CDSE max = 100)
HTTP_TIMEOUT    = 60     # seconds
POLITE_DELAY    = 0.5    # seconds between pages (slightly longer to reduce ChunkedEncoding)

# Retry configuration for network errors
RETRY_MAX       = 5      # maximum attempts per page before giving up
RETRY_DELAYS    = [5, 15, 30, 60, 120]  # seconds to wait before each retry attempt

# ---------------------------------------------------------------------------
# CSV columns
# ---------------------------------------------------------------------------
CSV_FIELDS = [
    "item_id",
    "source_year",       # which year's search produced this row
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ts_utc():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def sep(w=62):
    print("=" * w)

def hdr(n, title):
    print()
    sep()
    print("[{}] {}".format(n, title))
    sep()

def make_session():
    s = requests.Session()
    retry = Retry(
        total            = 3,
        backoff_factor   = 2,
        status_forcelist = [429, 500, 502, 503, 504],
        allowed_methods  = ["GET", "POST"],
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"Accept": "application/geo+json",
                       "Content-Type": "application/json"})
    return s

# ---------------------------------------------------------------------------
# India boundary loading
# ---------------------------------------------------------------------------

def load_india_boundary():
    """
    Load the India polygon from india_boundary.geojson using Shapely.
    Returns (india_geom, status_message) where india_geom may be None.
    """
    if not SHAPELY_AVAILABLE:
        return None, "Shapely not installed -- spatial filter not available"

    if not BOUNDARY_FILE.exists():
        return None, (
            "MISSING: {} not found.\n"
            "  India-only spatial filtering DISABLED.\n"
            "  See dataset/raw/boundaries/README.md for instructions.\n"
            "  All retained items will be labelled india_intersection=BBOX_ONLY."
            .format(BOUNDARY_FILE)
        )

    try:
        with open(BOUNDARY_FILE, encoding="utf-8") as fh:
            gj = json.load(fh)
    except Exception as exc:
        return None, "Could not parse {}: {}".format(BOUNDARY_FILE, exc)

    try:
        geoms = []
        if gj.get("type") == "FeatureCollection":
            for feat in gj.get("features", []):
                geoms.append(shapely_shape(feat["geometry"]))
        elif gj.get("type") == "Feature":
            geoms.append(shapely_shape(gj["geometry"]))
        else:
            # Bare geometry
            geoms.append(shapely_shape(gj))

        india = unary_union(geoms)
        return india, "Loaded from {}  ({} feature(s))".format(
            BOUNDARY_FILE.name, len(geoms))

    except Exception as exc:
        return None, "Could not build India geometry: {}".format(exc)


def check_india_intersection(feature, india_geom):
    """
    Returns 'TRUE', 'FALSE', or 'BBOX_ONLY' based on whether the
    STAC item footprint intersects India.
    """
    if india_geom is None:
        return "BBOX_ONLY"

    raw_geom = feature.get("geometry")
    if raw_geom is None:
        return "BBOX_ONLY"

    try:
        item_shape = shapely_shape(raw_geom)
        return "TRUE" if item_shape.intersects(india_geom) else "FALSE"
    except Exception:
        return "BBOX_ONLY"

# ---------------------------------------------------------------------------
# Parse a single STAC feature into a CSV row dict
# ---------------------------------------------------------------------------

def parse_feature(feature, india_geom, source_year=""):
    props = feature.get("properties", {})
    links = {lnk["rel"]: lnk.get("href", "")
             for lnk in feature.get("links", []) if "rel" in lnk}

    item_id  = feature.get("id", "")
    bbox_raw = feature.get("bbox") or []

    acq_dt = (props.get("datetime") or
               props.get("created", ""))
    acq_date = acq_dt[:10] if acq_dt else ""

    cloud_cover  = props.get("eo:cloud_cover")
    platform     = props.get("platform", "")
    constellation= props.get("constellation", props.get("mission", ""))
    mgrs_tile    = props.get("s2:mgrs_tile", "")

    stac_url = links.get("self", "")

    # S3 path: pull from any asset with s3:// href
    import re
    s3_path = ""
    for asset_val in feature.get("assets", {}).values():
        href = asset_val.get("href", "")
        if href.startswith("s3://"):
            m = re.search(
                r"(s3://eodata/Sentinel-2/[^/]+/[^/]+/\d{4}/\d{2}/\d{2}/[^/]+\.SAFE)",
                href)
            if m:
                s3_path = m.group(1)
                break

    geom_available = "TRUE" if feature.get("geometry") is not None else "FALSE"
    india_val      = check_india_intersection(feature, india_geom)

    return {
        "item_id"             : item_id,
        "source_year"         : source_year,
        "collection"          : COLLECTION,
        "acquisition_datetime": acq_dt,
        "acquisition_date"    : acq_date,
        "cloud_cover"         : "" if cloud_cover is None else cloud_cover,
        "platform"            : platform,
        "constellation"       : constellation,
        "mgrs_tile"           : mgrs_tile,
        "bbox_min_lon"        : bbox_raw[0] if len(bbox_raw) >= 4 else "",
        "bbox_min_lat"        : bbox_raw[1] if len(bbox_raw) >= 4 else "",
        "bbox_max_lon"        : bbox_raw[2] if len(bbox_raw) >= 4 else "",
        "bbox_max_lat"        : bbox_raw[3] if len(bbox_raw) >= 4 else "",
        "geometry_available"  : geom_available,
        "india_intersection"  : india_val,
        "stac_url"            : stac_url,
        "s3_product_path"     : s3_path,
        "imagery_downloaded"  : "NO",
    }

# ---------------------------------------------------------------------------
# STAC pagination -- POST-only, using next link body verbatim
# ---------------------------------------------------------------------------

def _post_with_retry(session, href, body, page_num):
    """
    POST to href with body, retrying up to RETRY_MAX times on:
      - ChunkedEncodingError
      - ConnectionError
      - Timeout
      - HTTP 429 (rate-limit)
      - HTTP 5xx (server errors)
    Returns (response, api_calls_made) or raises RuntimeError after all retries fail.
    """
    api_calls = 0
    for attempt in range(RETRY_MAX):
        try:
            resp = session.post(href, json=body, timeout=HTTP_TIMEOUT)
            api_calls += 1

            if resp.status_code == 429:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                print("  [RATE LIMIT] HTTP 429 on page {} attempt {}/{} -- "
                      "waiting {}s ...".format(page_num, attempt + 1, RETRY_MAX, delay))
                time.sleep(delay)
                continue  # retry without counting as a page

            if resp.status_code >= 500:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                print("  [RETRY {}/{}] HTTP {} on page {} -- "
                      "waiting {}s ...".format(
                          attempt + 1, RETRY_MAX, resp.status_code, page_num, delay))
                time.sleep(delay)
                continue

            return resp, api_calls  # success (could still be 4xx -- caller checks)

        except requests.exceptions.ChunkedEncodingError as exc:
            delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
            print("  [RETRY {}/{}] ChunkedEncodingError on page {} -- "
                  "waiting {}s ...".format(attempt + 1, RETRY_MAX, page_num, delay))
            time.sleep(delay)

        except requests.exceptions.ConnectionError as exc:
            delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
            print("  [RETRY {}/{}] ConnectionError on page {} -- "
                  "waiting {}s ...".format(attempt + 1, RETRY_MAX, page_num, delay))
            time.sleep(delay)

        except requests.exceptions.Timeout:
            delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
            print("  [RETRY {}/{}] Timeout on page {} -- "
                  "waiting {}s ...".format(attempt + 1, RETRY_MAX, page_num, delay))
            time.sleep(delay)

        except requests.exceptions.RequestException as exc:
            # Non-retryable network error
            raise RuntimeError("Non-retryable error on page {}: {} {}".format(
                page_num, type(exc).__name__, exc))

    raise RuntimeError(
        "Page {} failed after {} attempts -- giving up.".format(page_num, RETRY_MAX))


def run_discovery(session, india_geom, date_range, year_label):
    """
    Page through CDSE STAC results for ONE year's date range.

    Parameters
    ----------
    date_range : str   e.g. "2022-01-01T00:00:00Z/2022-12-31T23:59:59Z"
    year_label : str   e.g. "2022"  (used for display only)

    PAGINATION PROTOCOL (confirmed from debug_stac_pagination_report.txt):
      Every response includes a 'next' link with:
        rel    = "next"
        method = "POST"
        href   = "https://stac.dataspace.copernicus.eu/v1/search"
        body   = { full payload including token }

    We POST the body verbatim to the href.
    We NEVER reconstruct the token.  We NEVER GET the next URL.

    RETRY:
      ChunkedEncodingError, ConnectionError, Timeout, HTTP 5xx and 429
      are all retried up to RETRY_MAX times with increasing delays.

    DEDUPLICATION:
      A seen_ids set ensures no duplicate item_ids even on retried pages.
    """
    seen_ids      = set()   # deduplication within this year's search
    all_features  = []      # unique raw items (before cloud/India filter)
    api_requests  = 0
    total_retries = 0
    pages_ok      = 0
    capped        = False

    # ---- page 1: POST to initial endpoint with per-year date range ----
    payload = {
        "collections": [COLLECTION],
        "bbox"        : INDIA_BBOX,
        "datetime"    : date_range,
        "limit"       : PAGE_SIZE,
    }
    next_href   = STAC_SEARCH_URL_INITIAL
    next_body   = payload
    next_method = "POST"

    while True:
        remaining = MAX_ITEMS - len(all_features)
        if remaining <= 0:
            capped = True
            break

        if next_body.get("limit", PAGE_SIZE) > remaining:
            next_body = dict(next_body)
            next_body["limit"] = remaining

        page_num = pages_ok + 1
        try:
            resp, calls = _post_with_retry(session, next_href, next_body, page_num)
            api_requests  += calls
            total_retries += max(0, calls - 1)
        except RuntimeError as exc:
            print("  [ERROR] {}".format(exc))
            print("  Stopping pagination after {} successful pages.".format(pages_ok))
            break

        if resp.status_code != 200:
            print("  [ERROR] HTTP {} on page {} after retries.".format(
                resp.status_code, page_num))
            print("          Snippet: {}".format(resp.text[:300]))
            sys.exit(1)

        try:
            data = resp.json()
        except Exception:
            print("  [ERROR] Could not parse JSON on page {}.".format(page_num))
            sys.exit(1)

        raw_features = data.get("features", [])
        pages_ok += 1

        if not raw_features:
            break

        new_features = []
        for f in raw_features:
            fid = f.get("id", "")
            if fid and fid not in seen_ids:
                seen_ids.add(fid)
                new_features.append(f)

        all_features.extend(new_features)
        print("  [{}] Page {:>4d} : {:>4d} items ({:>4d} new)  |  unique: {:>5,}".format(
            year_label, pages_ok, len(raw_features), len(new_features), len(all_features)))

        next_href   = None
        next_body   = None
        next_method = None
        for lnk in data.get("links", []):
            if lnk.get("rel") == "next":
                next_href   = lnk.get("href")
                next_body   = lnk.get("body")
                next_method = lnk.get("method", "GET").upper()
                break

        if not next_href or not next_body:
            break

        if next_method != "POST":
            print("  [WARNING] Next link method is '{}' (expected POST). Stopping.".format(
                next_method))
            break

        if len(all_features) >= MAX_ITEMS:
            capped = True
            all_features = all_features[:MAX_ITEMS]
            break

        time.sleep(POLITE_DELAY)

    # ------ Apply filters ------
    kept          = []
    skipped_cloud = 0
    skipped_india = 0
    missing_cloud = 0

    for feat in all_features:
        cc = feat.get("properties", {}).get("eo:cloud_cover")
        if cc is None:
            missing_cloud += 1
        elif float(cc) > MAX_CLOUD_COVER:
            skipped_cloud += 1
            continue
        india_val = check_india_intersection(feat, india_geom)
        if india_val == "FALSE":
            skipped_india += 1
            continue
        kept.append(feat)

    return {
        "year"          : year_label,
        "date_range"    : date_range,
        "all_features"  : all_features,
        "kept"          : kept,
        "pages"         : pages_ok,
        "api_requests"  : api_requests,
        "total_retries" : total_retries,
        "capped"        : capped,
        "skipped_cloud" : skipped_cloud,
        "skipped_india" : skipped_india,
        "missing_cloud" : missing_cloud,
    }

# ---------------------------------------------------------------------------
# Write CSV
# ---------------------------------------------------------------------------

def write_csv(year_results, india_geom):
    """Combine kept features from all years into one CSV."""
    rows = []
    for yr in year_results:
        for f in yr["kept"]:
            rows.append(parse_feature(f, india_geom, source_year=yr["year"]))
    df = pd.DataFrame(rows, columns=CSV_FIELDS)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    return df

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def write_report(run_ts, boundary_status, india_geom,
                 year_results, df):
    acq_dates  = sorted(df["acquisition_date"].dropna().unique())
    acq_min    = acq_dates[0]  if len(acq_dates) else "N/A"
    acq_max    = acq_dates[-1] if len(acq_dates) else "N/A"
    n_dates    = len(acq_dates)
    n_tiles    = df["mgrs_tile"].nunique()
    platforms  = df["platform"].value_counts().to_dict()
    n_written  = len(df)

    spatial_filter = ("Shapely polygon intersection with india_boundary.geojson"
                      if india_geom is not None
                      else "BBOX_ONLY (boundary file missing -- see README)")

    required_years = [yr["year"] for yr in year_results]
    missing_years  = [yr["year"] for yr in year_results if len(yr["kept"]) == 0]
    completeness   = "COMPLETE" if not missing_years else "INCOMPLETE -- missing: {}".format(
        ", ".join(missing_years))

    n_raw_total    = sum(len(yr["all_features"]) for yr in year_results)
    n_kept_total   = sum(len(yr["kept"])         for yr in year_results)
    total_pages    = sum(yr["pages"]             for yr in year_results)
    total_api      = sum(yr["api_requests"]      for yr in year_results)
    total_retries  = sum(yr["total_retries"]     for yr in year_results)
    total_cloud    = sum(yr["skipped_cloud"]      for yr in year_results)
    total_india    = sum(yr["skipped_india"]      for yr in year_results)
    total_nocc     = sum(yr["missing_cloud"]      for yr in year_results)

    lines = [
        "=" * 62,
        "HeatWatch -- Sentinel-2 India Metadata Discovery Report (v3)",
        "=" * 62,
        "Timestamp             : {}".format(run_ts),
        "Script                : {}".format(Path(__file__).resolve()),
        "",
        "SEARCH PARAMETERS",
        "-" * 40,
        "Strategy              : Year-by-year (avoids CDSE reverse-chron cap)",
        "STAC endpoint         : {}".format(STAC_SEARCH_URL_INITIAL),
        "Collection            : {}".format(COLLECTION),
        "India bbox            : {}".format(INDIA_BBOX),
        "Years searched        : {}".format(", ".join(required_years)),
        "Cloud threshold       : <= {}%  (client-side)".format(MAX_CLOUD_COVER),
        "Max items cap/year    : {:,}".format(MAX_ITEMS),
        "Page size             : {}".format(PAGE_SIZE),
        "Retry max             : {} attempts".format(RETRY_MAX),
        "",
        "BOUNDARY DATASET",
        "-" * 40,
        "File                  : {}".format(BOUNDARY_FILE),
        "Status                : {}".format(boundary_status),
        "Spatial filter        : {}".format(spatial_filter),
        "",
        "TOTALS ACROSS ALL YEARS",
        "-" * 40,
        "Total pages           : {:,}".format(total_pages),
        "Total API requests    : {:,}".format(total_api),
        "Total retries         : {:,}".format(total_retries),
        "Raw unique items      : {:,}".format(n_raw_total),
        "Skipped cloud > {}%   : {:,}".format(MAX_CLOUD_COVER, total_cloud),
        "Missing cloud kept    : {:,}".format(total_nocc),
        "Skipped outside India : {:,}".format(total_india),
        "Total retained        : {:,}".format(n_kept_total),
        "Rows written to CSV   : {:,}".format(n_written),
        "",
        "YEAR-BY-YEAR BREAKDOWN",
        "-" * 40,
    ]
    for yr in year_results:
        yr_df    = df[df["source_year"] == yr["year"]]
        yr_dates = sorted(yr_df["acquisition_date"].dropna().unique())
        yr_min   = yr_dates[0]  if yr_dates else "N/A"
        yr_max   = yr_dates[-1] if yr_dates else "N/A"
        lines += [
            "",
            "  Year {}  ({})".format(yr["year"], yr["date_range"]),
            "    Pages          : {:,}".format(yr["pages"]),
            "    API requests   : {:,}".format(yr["api_requests"]),
            "    Retries        : {:,}".format(yr["total_retries"]),
            "    Raw unique     : {:,}".format(len(yr["all_features"])),
            "    Cloud rejected : {:,}".format(yr["skipped_cloud"]),
            "    India rejected : {:,}".format(yr["skipped_india"]),
            "    Retained       : {:,}".format(len(yr["kept"])),
            "    Earliest       : {}".format(yr_min),
            "    Latest         : {}".format(yr_max),
            "    Cap reached    : {}".format("YES" if yr["capped"] else "NO"),
        ]
    lines += [
        "",
        "YEAR COMPLETENESS     : {}".format(completeness),
        "",
        "ACQUISITION STATISTICS",
        "-" * 40,
        "Earliest acquisition  : {}".format(acq_min),
        "Latest   acquisition  : {}".format(acq_max),
        "Unique dates          : {:,}".format(n_dates),
        "Unique MGRS tiles     : {:,}".format(n_tiles),
        "Platform breakdown    :",
    ]
    for plat, cnt in sorted(platforms.items()):
        lines.append("  {:30s}: {:,}".format(plat, cnt))

    india_status = ("INDIA-ONLY (polygon intersection)" if india_geom is not None
                    else "BBOX_ONLY (not verified -- boundary file missing)")
    lines += [
        "",
        "IMAGERY DOWNLOADED    : NO",
        "",
        "=" * 62,
        "INDIA-ONLY VALIDATION",
        "=" * 62,
        "",
        "DATE RANGE:",
        "2022-01-01 -> 2024-12-31",
        "",
        "GEOGRAPHIC FILTER:",
        "India  --  {}".format(india_status),
        "Initial India bounding-box filter used as STAC query optimisation.",
        ("Results spatially verified against india_boundary.geojson."
         if india_geom is not None
         else "Spatial verification NOT performed -- india_boundary.geojson missing."),
        "",
        "SENTINEL COLLECTION:",
        "sentinel-2-l2a",
        "",
        "IMAGERY DOWNLOADED:",
        "NO",
        "",
        "METADATA QUERY STATUS:",
        "{} -- {:,} rows written to CSV.".format(
            "SUCCESS" if n_written > 0 else "FAIL", n_written),
        "",
        "=" * 62,
        "",
    ]
    OUTPUT_REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("  Report : {}".format(OUTPUT_REPORT))

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    run_ts  = ts_utc()
    session = make_session()

    sep()
    print("HeatWatch -- India Sentinel-2 L2A Metadata Discovery  (v3)")
    sep()
    print("Timestamp      : {}".format(run_ts))
    print("Strategy       : Year-by-year search (2022 / 2023 / 2024 separately)")
    print("METADATA ONLY  -- no imagery downloaded.")

    # -----------------------------------------------------------------------
    # [0] India boundary
    # -----------------------------------------------------------------------
    hdr(0, "India Boundary")
    india_geom, boundary_status = load_india_boundary()
    if india_geom is not None:
        print("  [OK] {}".format(boundary_status))
    else:
        print("  [WARNING] {}".format(boundary_status))
        if not SHAPELY_AVAILABLE:
            print("  Install shapely: pip install shapely")

    # -----------------------------------------------------------------------
    # [1] Year-by-year STAC discovery
    # -----------------------------------------------------------------------
    hdr(1, "Year-by-Year STAC Catalogue Search")
    print("  Collection      : {}".format(COLLECTION))
    print("  BBox (India)    : {}".format(INDIA_BBOX))
    print("  Cloud filter    : <= {}% (client-side)".format(MAX_CLOUD_COVER))
    print("  Hard cap/year   : {:,} items".format(MAX_ITEMS))
    print("  Retry policy    : up to {} attempts; delays {}".format(RETRY_MAX, RETRY_DELAYS))
    print("  Pagination      : POST next-link body verbatim (no reconstruction)")
    print()

    year_results = []
    for (year_label, date_start, date_end) in SEARCH_YEARS:
        date_range = "{}/{}".format(date_start, date_end)
        print("  --- {} : {} ---".format(year_label, date_range))
        result = run_discovery(session, india_geom, date_range, year_label)
        year_results.append(result)
        yr_raw  = len(result["all_features"])
        yr_kept = len(result["kept"])
        print("  {} summary: pages={} | raw={:,} | cloud_rej={:,} | india_rej={:,} | kept={:,}{}".format(
            year_label,
            result["pages"],
            yr_raw,
            result["skipped_cloud"],
            result["skipped_india"],
            yr_kept,
            "  [CAP REACHED]" if result["capped"] else "",
        ))
        print()

    any_features = any(len(yr["all_features"]) > 0 for yr in year_results)
    if not any_features:
        print("[FAIL] No items returned from STAC for any year. Check network / endpoint.")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # [2] Write combined CSV
    # -----------------------------------------------------------------------
    hdr(2, "Writing Combined Metadata CSV")
    df = write_csv(year_results, india_geom)
    print("  Rows written : {:,}".format(len(df)))
    print("  CSV          : {}".format(OUTPUT_CSV))

    # -----------------------------------------------------------------------
    # [3] Summary Statistics + Year Coverage
    # -----------------------------------------------------------------------
    hdr(3, "Summary Statistics")
    acq_dates = sorted(df["acquisition_date"].dropna().unique())
    print("  Earliest acquisition : {}".format(acq_dates[0]  if acq_dates else "N/A"))
    print("  Latest   acquisition : {}".format(acq_dates[-1] if acq_dates else "N/A"))
    print("  Total unique dates   : {:,}".format(len(acq_dates)))
    print("  Total unique products: {:,}".format(df["item_id"].nunique()))
    print("  Total unique MGRS    : {:,}".format(df["mgrs_tile"].nunique()))
    print("  Platforms:")
    for plat, cnt in df["platform"].value_counts().items():
        print("    {:30s}: {:,}".format(plat, cnt))

    print()
    print("  YEAR-WISE COVERAGE:")
    print("  {:<6}  {:>8}  {:>10}  {:>10}  {:>10}  {:>12}  {:>12}  {}".format(
        "Year", "Raw", "CloudRej", "IndiaRej", "Retained", "Earliest", "Latest", "Cap"))
    print("  " + "-" * 88)

    missing_years = []
    for yr in year_results:
        yr_df    = df[df["source_year"] == yr["year"]]
        yr_dates = sorted(yr_df["acquisition_date"].dropna().unique())
        yr_min   = yr_dates[0]  if yr_dates else "N/A"
        yr_max   = yr_dates[-1] if yr_dates else "N/A"
        if len(yr["kept"]) == 0:
            missing_years.append(yr["year"])
        print("  {:<6}  {:>8,}  {:>10,}  {:>10,}  {:>10,}  {:>12}  {:>12}  {}".format(
            yr["year"],
            len(yr["all_features"]),
            yr["skipped_cloud"],
            yr["skipped_india"],
            len(yr["kept"]),
            yr_min,
            yr_max,
            "CAP" if yr["capped"] else "",
        ))

    print()
    if missing_years:
        print("  WARNING: YEAR COVERAGE INCOMPLETE")
        for yr in missing_years:
            print("    - {} has 0 retained records".format(yr))
    else:
        print("  YEAR COVERAGE: COMPLETE (2022, 2023, 2024 all present)")

    # -----------------------------------------------------------------------
    # [4] Report
    # -----------------------------------------------------------------------
    hdr(4, "Writing Report")
    write_report(run_ts, boundary_status, india_geom, year_results, df)

    # -----------------------------------------------------------------------
    # India-only validation
    # -----------------------------------------------------------------------
    print()
    sep()
    print("INDIA-ONLY VALIDATION")
    sep()
    print()
    print("DATE RANGE:")
    print("2022-01-01 -> 2024-12-31 (searched year-by-year)")
    print()
    print("GEOGRAPHIC FILTER:")
    if india_geom is not None:
        print("India polygon (shapely intersection with india_boundary.geojson)")
    else:
        print("BBOX_ONLY -- india_boundary.geojson NOT found.")
        print("See dataset/raw/boundaries/README.md for instructions.")
        print("Dataset is NOT claimed to be India-only until boundary is provided.")
    print()
    print("SENTINEL COLLECTION:")
    print("sentinel-2-l2a")
    print()
    print("IMAGERY DOWNLOADED:")
    print("NO")
    print()
    print("METADATA QUERY STATUS:")
    if len(df) > 0:
        print("SUCCESS -- {:,} Sentinel-2 L2A metadata records written.".format(len(df)))
        if missing_years:
            print("WARNING: years {} have 0 retained records.".format(missing_years))
        sep()
        sys.exit(0)
    else:
        print("FAIL -- 0 rows written.")
        sep()
        sys.exit(1)


if __name__ == "__main__":
    main()
