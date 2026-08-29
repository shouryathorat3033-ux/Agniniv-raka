"""
HeatWatch -- CDSE STAC Pagination Diagnostics
=============================================
Purpose : Make ONE single STAC search request with limit=3 and print
          the COMPLETE pagination-relevant response structure so we
          can understand exactly how to implement correct pagination.

Rules:
* ONE HTTP request only.
* NO pagination attempted.
* NO imagery downloaded.
* NO credentials printed.
* NO FIRMS files touched.
* NO discover_india_sentinel2.py modified.
"""

import sys
import json
import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("[ERROR] requests not installed.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config -- identical to discover_india_sentinel2.py
# ---------------------------------------------------------------------------
STAC_SEARCH_URL = "https://catalogue.dataspace.copernicus.eu/stac/search"
COLLECTION      = "sentinel-2-l2a"
INDIA_BBOX      = [68.1, 7.9, 97.4, 37.1]
DATE_RANGE      = "2022-01-01T00:00:00Z/2024-12-31T23:59:59Z"
LIMIT           = 3     # deliberately tiny -- we need only the structure

SCRIPT_DIR  = Path(__file__).resolve().parent
REPORT_FILE = SCRIPT_DIR / "debug_stac_pagination_report.txt"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sep(w=62):
    print("=" * w)

def hdr(title, w=62):
    print()
    sep(w)
    print(title)
    sep(w)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    sep()
    print("HeatWatch -- CDSE STAC Pagination Diagnostics")
    sep()
    print("Timestamp : {}".format(ts))
    print("ONE request only.  No pagination.  No imagery.")

    payload = {
        "collections": [COLLECTION],
        "bbox"        : INDIA_BBOX,
        "datetime"    : DATE_RANGE,
        "limit"       : LIMIT,
    }

    hdr("REQUEST")
    print("Method  : POST")
    print("URL     : {}".format(STAC_SEARCH_URL))
    print("Payload : {}".format(json.dumps(payload, indent=2)))

    # -----------------------------------------------------------------------
    # Single POST request
    # -----------------------------------------------------------------------
    hdr("RAW HTTP RESPONSE")
    try:
        resp = requests.post(
            STAC_SEARCH_URL,
            json    = payload,
            timeout = 30,
            headers = {"Accept": "application/geo+json"},
        )
    except Exception as exc:
        print("[ERROR] Request failed: {} {}".format(type(exc).__name__, exc))
        sys.exit(1)

    print("HTTP status : {}".format(resp.status_code))
    print("Content-Type: {}".format(resp.headers.get("Content-Type", "(none)")))

    if resp.status_code != 200:
        print("[ERROR] Non-200 response body:")
        print(resp.text[:500])
        sys.exit(1)

    try:
        data = resp.json()
    except Exception as exc:
        print("[ERROR] Could not parse JSON: {}".format(exc))
        print("Raw body snippet: {}".format(resp.text[:300]))
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Top-level structure
    # -----------------------------------------------------------------------
    hdr("TOP-LEVEL JSON KEYS")
    for k, v in data.items():
        if k == "features":
            print("  {:20s} : list of {} items".format(k, len(v)))
        elif k == "links":
            print("  {:20s} : list of {} links".format(k, len(v)))
        elif isinstance(v, (dict, list)):
            print("  {:20s} : {} (len={})".format(k, type(v).__name__, len(v)))
        else:
            print("  {:20s} : {}".format(k, repr(v)))

    # -----------------------------------------------------------------------
    # All links -- printed COMPLETE (this is what tells us how to paginate)
    # -----------------------------------------------------------------------
    hdr("ALL LINKS (complete -- key to pagination)")
    links = data.get("links", [])
    if not links:
        print("  (no links in response)")
    for i, lnk in enumerate(links):
        print()
        print("  Link [{}]".format(i))
        print("    rel     : {}".format(lnk.get("rel", "(none)")))
        href = lnk.get("href", "(none)")
        print("    href    : {}".format(href))
        print("    type    : {}".format(lnk.get("type", "(not specified)")))
        method = lnk.get("method", "(not specified)")
        print("    method  : {}".format(method))
        # Print body if present (OGC STAC API 1.0 POST pagination)
        body = lnk.get("body")
        if body is not None:
            print("    body    : {}".format(json.dumps(body, indent=6)))
        else:
            print("    body    : (not present)")
        headers_lnk = lnk.get("headers")
        if headers_lnk:
            print("    headers : {}".format(json.dumps(headers_lnk)))
        else:
            print("    headers : (not present)")

    # -----------------------------------------------------------------------
    # Next-link analysis
    # -----------------------------------------------------------------------
    hdr("NEXT LINK ANALYSIS")
    next_links = [lnk for lnk in links if lnk.get("rel") == "next"]
    if not next_links:
        print("  NO 'next' link found in response.")
        print("  This means either:")
        print("    (a) The API returned fewer items than the limit (all results fit on page 1)")
        print("    (b) The API does not support cursor/token pagination for this query")
        print("    (c) The response format is unexpected")
    else:
        nl = next_links[0]
        print("  'next' link FOUND.")
        print()
        print("  rel    : {}".format(nl.get("rel")))
        print("  href   : {}".format(nl.get("href", "(none)")))
        method = nl.get("method", "(not specified in link)")
        print("  method : {}".format(method))
        body   = nl.get("body")
        print("  body   : {}".format(
            json.dumps(body, indent=4) if body is not None else "(not present)"))
        print()
        if method.upper() == "GET":
            print("  => Next page should be fetched with GET to the href above.")
        elif method.upper() == "POST":
            print("  => Next page should be fetched with POST using the body above.")
        else:
            print("  => Method not explicitly specified.")
            print("     Likely GET (default for STAC link following).")
            print("     If 'body' is present, POST is implied by OGC STAC spec.")

    # -----------------------------------------------------------------------
    # Context / numbersMatched (if present)
    # -----------------------------------------------------------------------
    hdr("PAGINATION CONTEXT / COUNTS")
    ctx = data.get("context", data.get("numberMatched", None))
    if ctx is not None:
        print("  context / numberMatched: {}".format(ctx))
    else:
        print("  No 'context' or 'numberMatched' field in response.")
    nm = data.get("numberMatched")
    nr = data.get("numberReturned")
    print("  numberMatched   : {}".format(nm if nm is not None else "(not present)"))
    print("  numberReturned  : {}".format(nr if nr is not None else "(not present)"))

    # -----------------------------------------------------------------------
    # Feature summary (no geometry, no assets)
    # -----------------------------------------------------------------------
    hdr("FEATURE SUMMARY (IDs and dates only -- no geometry/assets)")
    features = data.get("features", [])
    print("  Features returned: {}".format(len(features)))
    for i, feat in enumerate(features):
        fid  = feat.get("id", "(no id)")
        dt   = feat.get("properties", {}).get("datetime", "(no date)")
        cc   = feat.get("properties", {}).get("eo:cloud_cover", "(no cc)")
        bbox = feat.get("bbox", "(no bbox)")
        print()
        print("  Feature [{}]".format(i))
        print("    id             : {}".format(fid))
        print("    datetime       : {}".format(dt))
        print("    eo:cloud_cover : {}".format(cc))
        print("    bbox           : {}".format(bbox))
        feat_links = feat.get("links", [])
        print("    links          : {} link(s)".format(len(feat_links)))
        for fl in feat_links:
            print("      rel={} href={}".format(
                fl.get("rel", "?"), fl.get("href", "?")[:80]))

    # -----------------------------------------------------------------------
    # Write report
    # -----------------------------------------------------------------------
    hdr("WRITING DIAGNOSTIC REPORT")

    report_lines = [
        "=" * 62,
        "HeatWatch -- STAC Pagination Diagnostic Report",
        "=" * 62,
        "Timestamp        : {}".format(ts),
        "Endpoint         : {}".format(STAC_SEARCH_URL),
        "Collection       : {}".format(COLLECTION),
        "BBox             : {}".format(INDIA_BBOX),
        "Date range       : {}".format(DATE_RANGE),
        "Limit requested  : {}".format(LIMIT),
        "HTTP status      : {}".format(resp.status_code),
        "Features returned: {}".format(len(features)),
        "",
        "ALL LINKS",
        "-" * 40,
    ]
    for i, lnk in enumerate(links):
        report_lines.append("  Link [{}]".format(i))
        report_lines.append("    rel    : {}".format(lnk.get("rel", "(none)")))
        report_lines.append("    href   : {}".format(lnk.get("href", "(none)")))
        report_lines.append("    type   : {}".format(lnk.get("type", "(none)")))
        report_lines.append("    method : {}".format(lnk.get("method", "(not specified)")))
        body = lnk.get("body")
        if body is not None:
            report_lines.append("    body   : {}".format(json.dumps(body)))
        else:
            report_lines.append("    body   : (not present)")
        report_lines.append("")

    report_lines += [
        "NEXT LINK PRESENT : {}".format("YES" if next_links else "NO"),
        "",
        "IMAGERY DOWNLOADED: NO",
        "",
        "=" * 62,
        "",
    ]
    REPORT_FILE.write_text("\n".join(report_lines), encoding="utf-8")
    print("  Report : {}".format(REPORT_FILE))

    hdr("DONE -- Inspect the 'NEXT LINK ANALYSIS' section above")
    print("  No pagination was attempted.")
    print("  No imagery was downloaded.")
    print()


if __name__ == "__main__":
    main()
