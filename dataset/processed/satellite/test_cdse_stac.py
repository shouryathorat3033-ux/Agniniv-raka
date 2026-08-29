"""
HeatWatch -- CDSE S3 Connectivity & Sentinel-2 Access Test
===========================================================
Project  : Urban/Industrial Heat & Thermal Anomaly Detection
Purpose  : Verify that the project can authenticate to the Copernicus
           Data Space Ecosystem (CDSE) via S3 credentials and confirm
           that Sentinel-2 Level-2A data is discoverable.

THIS SCRIPT PERFORMS METADATA/LISTING ONLY.
-------------------------------------------
* No TIFF, JP2, or ZIP files are downloaded.
* No Sentinel-2 imagery is stored locally.
* No FIRMS data is modified.
* Credentials are NEVER printed, logged, or written to any file.

Official CDSE S3 reference
---------------------------
https://documentation.dataspace.copernicus.eu/APIs/S3.html

CDSE S3 parameters (from official docs)
----------------------------------------
  Endpoint : https://eodata.dataspace.copernicus.eu
  Bucket   : eodata
  Region   : default
  Auth     : AWS Signature v4 with CDSE S3 access/secret key

Credential variables in database/.env
--------------------------------------
  CDSE_S3_ACCESS_KEY   -- Access Key from CDSE S3 Keys Manager
  CDSE_S3_SECRET_KEY   -- Secret Key from CDSE S3 Keys Manager

Generate keys at: https://eodata-s3keysmanager.dataspace.copernicus.eu/

Also preserves STAC connectivity check (no auth required for STAC search).
"""

import sys
import json
import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependency guards
# ---------------------------------------------------------------------------
try:
    from dotenv import dotenv_values
except ImportError:
    print("[ERROR] python-dotenv not installed.  pip install python-dotenv")
    sys.exit(1)

try:
    import boto3
    from botocore.exceptions import (
        ClientError,
        NoCredentialsError,
        EndpointResolutionError,
        ConnectTimeoutError,
    )
    from botocore.config import Config
except ImportError:
    print("[ERROR] boto3 not installed.  pip install boto3")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("[ERROR] requests not installed.  pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR   = Path(__file__).resolve().parent          # .../satellite/
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent           # C:\SIH_Hackthon
ENV_FILE     = PROJECT_ROOT / "database" / ".env"
REPORT_FILE  = SCRIPT_DIR / "cdse_s3_test_report.txt"

# ---------------------------------------------------------------------------
# CDSE S3 constants  (official values from documentation)
# ---------------------------------------------------------------------------
CDSE_S3_ENDPOINT   = "https://eodata.dataspace.copernicus.eu"
CDSE_S3_BUCKET     = "eodata"
CDSE_S3_REGION     = "default"

# Sentinel-2 L2A path prefix inside the bucket
# Structure: Sentinel-2/MSI/L2A/YYYY/MM/DD/<product>.SAFE/
S2_PREFIX          = "Sentinel-2/MSI/L2A/"

# Max keys to list when verifying Sentinel-2 presence (metadata only)
S2_LIST_MAX_KEYS   = 5

# STAC endpoint (public, no auth needed for metadata search)
STAC_ROOT          = "https://catalogue.dataspace.copernicus.eu/stac"
STAC_COLLECTION    = "sentinel-2-l2a"
HTTP_TIMEOUT       = 20

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sep(char="=", width=62):
    print(char * width)

def step(n, title):
    print()
    sep()
    print("[{}] {}".format(n, title))
    sep()

def cred_present(val):
    return bool(val and str(val).strip())

def ts():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

# ---------------------------------------------------------------------------
# Step 1 -- Load and validate credentials
# ---------------------------------------------------------------------------

def load_credentials():
    if not ENV_FILE.exists():
        print("  [ERROR] .env not found: {}".format(ENV_FILE))
        sys.exit(1)

    cfg = dotenv_values(ENV_FILE)

    access_key = cfg.get("CDSE_S3_ACCESS_KEY", "")
    secret_key = cfg.get("CDSE_S3_SECRET_KEY", "")

    ak_ok = cred_present(access_key)
    sk_ok = cred_present(secret_key)

    print("  CDSE_S3_ACCESS_KEY : {}".format("PRESENT" if ak_ok else "MISSING"))
    print("  CDSE_S3_SECRET_KEY : {}".format("PRESENT" if sk_ok else "MISSING"))

    if not ak_ok or not sk_ok:
        print()
        print("  [ACTION REQUIRED]")
        print("  Add your S3 credentials to database/.env:")
        print("    CDSE_S3_ACCESS_KEY=<your access key>")
        print("    CDSE_S3_SECRET_KEY=<your secret key>")
        print()
        print("  Generate keys at:")
        print("    https://eodata-s3keysmanager.dataspace.copernicus.eu/")
        print()
        print("  [FAIL] Missing S3 credentials -- cannot continue.")
        return None, None

    # Values are returned but NEVER printed
    return access_key, secret_key

# ---------------------------------------------------------------------------
# Step 2 -- Create boto3 S3 client
# ---------------------------------------------------------------------------

def make_s3_client(access_key, secret_key):
    """
    Build a boto3 S3 client pointing at the official CDSE S3 endpoint.
    Credentials are held only in the session object in memory.
    """
    session = boto3.session.Session()
    client = session.client(
        service_name          = "s3",
        endpoint_url          = CDSE_S3_ENDPOINT,
        aws_access_key_id     = access_key,
        aws_secret_access_key = secret_key,
        region_name           = CDSE_S3_REGION,
        config                = Config(
            signature_version     = "s3v4",
            connect_timeout       = HTTP_TIMEOUT,
            read_timeout          = HTTP_TIMEOUT,
            retries               = {"max_attempts": 1},
        ),
    )
    return client

# ---------------------------------------------------------------------------
# Step 3 -- Verify S3 endpoint reachability (head_bucket)
# ---------------------------------------------------------------------------

def check_s3_endpoint(client):
    """
    Use head_bucket on the 'eodata' bucket to verify:
      (a) the endpoint is reachable
      (b) the credentials authenticate successfully

    head_bucket returns 200 on success, 403 on bad credentials,
    and raises ConnectionError if the endpoint is unreachable.

    No data is downloaded.
    """
    print("  Endpoint : {}".format(CDSE_S3_ENDPOINT))
    print("  Bucket   : {}".format(CDSE_S3_BUCKET))
    print("  Region   : {}".format(CDSE_S3_REGION))
    print()

    try:
        resp = client.head_bucket(Bucket=CDSE_S3_BUCKET)
        http_code = resp["ResponseMetadata"]["HTTPStatusCode"]
        print("  Endpoint reachable : YES")
        print("  Authentication     : SUCCESS  (HTTP {})".format(http_code))
        return True, True

    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        msg  = exc.response["Error"]["Message"]
        if code in ("403", "AccessDenied"):
            print("  Endpoint reachable : YES")
            print("  Authentication     : FAIL  (HTTP 403 -- Access Denied)")
            print("  Hint: Verify that CDSE_S3_ACCESS_KEY and CDSE_S3_SECRET_KEY")
            print("        match the credentials shown in the CDSE dashboard.")
            print("        S3 credentials expire -- regenerate if needed.")
            return True, False
        elif code in ("404", "NoSuchBucket"):
            print("  Endpoint reachable : YES")
            print("  Bucket '{}' not found (HTTP 404)".format(CDSE_S3_BUCKET))
            return True, False
        else:
            print("  S3 error: {} -- {}".format(code, msg))
            return True, False

    except NoCredentialsError:
        print("  [ERROR] boto3 could not find credentials.")
        return False, False

    except Exception as exc:
        exc_type = type(exc).__name__
        # Check for connection-level errors by name (avoids importing private classes)
        if "Connect" in exc_type or "Endpoint" in exc_type or "Connection" in exc_type:
            print("  Endpoint reachable : NO")
            print("  [ERROR] Could not connect to CDSE S3: {}".format(exc_type))
        else:
            print("  [ERROR] Unexpected error ({}): {}".format(exc_type, exc))
        return False, False

# ---------------------------------------------------------------------------
# Step 4 -- Verify Sentinel-2 data is accessible via S3 listing
# ---------------------------------------------------------------------------

def check_sentinel2_access(client):
    """
    List up to S2_LIST_MAX_KEYS objects under the Sentinel-2/MSI/L2A/ prefix.
    This is a pure metadata operation -- no data is downloaded.
    """
    print("  Bucket prefix : {}/{}".format(CDSE_S3_BUCKET, S2_PREFIX))
    print("  Max keys      : {} (metadata listing only)".format(S2_LIST_MAX_KEYS))
    print()

    try:
        resp = client.list_objects_v2(
            Bucket    = CDSE_S3_BUCKET,
            Prefix    = S2_PREFIX,
            Delimiter = "/",            # list top-level year folders only
            MaxKeys   = S2_LIST_MAX_KEYS,
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        print("  [FAIL] S3 listing error: {}".format(code))
        return False, []
    except Exception as exc:
        print("  [ERROR] Unexpected error during listing: {}".format(type(exc).__name__))
        return False, []

    # Common prefixes = year directories (e.g. Sentinel-2/MSI/L2A/2024/)
    prefixes = [p["Prefix"] for p in resp.get("CommonPrefixes", [])]
    objects  = [o["Key"]    for o in resp.get("Contents", [])]
    all_keys = prefixes + objects

    if all_keys:
        print("  Sentinel-2 L2A accessible : YES")
        print("  Sample top-level entries:")
        for k in all_keys[:S2_LIST_MAX_KEYS]:
            print("    {}".format(k))
        return True, all_keys
    else:
        print("  Sentinel-2 L2A accessible : NO result returned")
        print("  (Prefix may be correct but credentials may lack read permission)")
        return False, []

# ---------------------------------------------------------------------------
# Step 5 -- STAC endpoint check (public, no auth needed)
# ---------------------------------------------------------------------------

def check_stac(headers=None):
    """
    Confirm the public STAC catalogue endpoint is reachable and the
    sentinel-2-l2a collection is listed.  No credentials involved.
    """
    headers = headers or {}
    print("  STAC root  : {}".format(STAC_ROOT))
    try:
        resp = requests.get(STAC_ROOT, timeout=HTTP_TIMEOUT)
        if resp.status_code == 200:
            title = resp.json().get("title", "(no title)")
            print("  Reachable  : YES  -- {}".format(title))
            stac_ok = True
        else:
            print("  Reachable  : NO  (HTTP {})".format(resp.status_code))
            stac_ok = False
    except Exception as exc:
        print("  Reachable  : NO  ({})".format(type(exc).__name__))
        stac_ok = False

    if not stac_ok:
        return False

    # Check sentinel-2-l2a collection (public endpoint)
    coll_url = "{}/collections/{}".format(STAC_ROOT, STAC_COLLECTION)
    try:
        resp = requests.get(coll_url, timeout=HTTP_TIMEOUT)
        if resp.status_code == 200:
            cid = resp.json().get("id", "?")
            print("  Collection : {}  FOUND".format(cid))
            return True
        else:
            print("  Collection : {} HTTP {}".format(STAC_COLLECTION, resp.status_code))
            return False
    except Exception as exc:
        print("  Collection check error: {}".format(type(exc).__name__))
        return False

# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(timestamp, endpoint_ok, auth_ok, s2_ok, stac_ok,
                 s2_samples, failures):
    lines = [
        "=" * 62,
        "HeatWatch -- CDSE S3 Test Report",
        "=" * 62,
        "Timestamp         : {}".format(timestamp),
        "Script            : {}".format(Path(__file__).resolve()),
        "",
        "ENDPOINTS TESTED",
        "-" * 30,
        "S3  endpoint      : {}".format(CDSE_S3_ENDPOINT),
        "S3  bucket        : {}".format(CDSE_S3_BUCKET),
        "STAC endpoint     : {}".format(STAC_ROOT),
        "",
        "RESULTS",
        "-" * 30,
        "S3 endpoint reachable     : {}".format("YES" if endpoint_ok else "NO"),
        "S3 authentication         : {}".format("SUCCESS" if auth_ok   else "FAIL"),
        "Sentinel-2 L2A accessible : {}".format("YES" if s2_ok        else "NO"),
        "STAC catalogue reachable  : {}".format("YES" if stac_ok      else "NO"),
        "",
        "FILES DOWNLOADED          : NONE (metadata listing only)",
        "",
        "S3 SAMPLE ENTRIES (prefix listing, no data downloaded)",
        "-" * 55,
    ]
    if s2_samples:
        for s in s2_samples:
            lines.append("  {}".format(s))
    else:
        lines.append("  (none returned)")

    lines += ["", "ISSUES", "-" * 30]
    if failures:
        for f in failures:
            lines.append("  - {}".format(f))
    else:
        lines.append("  None -- all checks passed.")

    lines += ["", "SECURITY NOTE",
              "-" * 30,
              "  Access keys and secret keys are NEVER written to this report.",
              "",
              "=" * 62, ""]

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print("\n  Report written: {}".format(REPORT_FILE))

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    run_ts = ts()
    failures = []

    sep("=", 62)
    print("HeatWatch -- CDSE S3 Connectivity & Sentinel-2 Access Test")
    sep("=", 62)
    print()
    print("NOTE: Metadata/listing ONLY.  No imagery downloaded.")
    print("      Credentials are never printed.")
    print("      Timestamp: {}".format(run_ts))

    # -----------------------------------------------------------------------
    # [1] Credentials
    # -----------------------------------------------------------------------
    step(1, "Load S3 Credentials from database/.env")
    access_key, secret_key = load_credentials()
    creds_ok = (access_key is not None)
    if not creds_ok:
        failures.append("S3 credentials missing in database/.env")

    # -----------------------------------------------------------------------
    # [2] S3 endpoint + authentication
    # -----------------------------------------------------------------------
    endpoint_ok = False
    auth_ok     = False

    if creds_ok:
        step(2, "S3 Endpoint Reachability & Authentication")
        client = make_s3_client(access_key, secret_key)
        endpoint_ok, auth_ok = check_s3_endpoint(client)
        if not endpoint_ok:
            failures.append("S3 endpoint unreachable: {}".format(CDSE_S3_ENDPOINT))
        if endpoint_ok and not auth_ok:
            failures.append("S3 authentication failed -- check credentials.")
    else:
        step(2, "S3 Endpoint Reachability & Authentication")
        print("  [SKIPPED] No credentials available.")
        client = None

    # -----------------------------------------------------------------------
    # [3] Sentinel-2 L2A listing (metadata only)
    # -----------------------------------------------------------------------
    s2_ok      = False
    s2_samples = []

    step(3, "Sentinel-2 L2A Access (S3 prefix listing -- no download)")
    if auth_ok and client is not None:
        s2_ok, s2_samples = check_sentinel2_access(client)
        if not s2_ok:
            failures.append("Sentinel-2 L2A prefix listing returned no results.")
    else:
        print("  [SKIPPED] S3 authentication not available.")

    # -----------------------------------------------------------------------
    # [4] STAC catalogue (public endpoint, no credentials needed)
    # -----------------------------------------------------------------------
    step(4, "STAC Catalogue Check (public -- no S3 credentials needed)")
    stac_ok = check_stac()
    if not stac_ok:
        failures.append("STAC catalogue endpoint not reachable.")

    # -----------------------------------------------------------------------
    # Write report
    # -----------------------------------------------------------------------
    write_report(run_ts, endpoint_ok, auth_ok, s2_ok, stac_ok,
                 s2_samples, failures)

    # -----------------------------------------------------------------------
    # FINAL RESULT
    # -----------------------------------------------------------------------
    print()
    sep("=", 62)
    print("FINAL RESULT")
    sep("=", 62)

    checks = [
        ("S3 credentials loaded from database/.env",     creds_ok),
        ("S3 endpoint reachable",                        endpoint_ok),
        ("S3 authentication successful",                 auth_ok),
        ("Sentinel-2 L2A data accessible via S3",        s2_ok),
        ("STAC catalogue reachable (public endpoint)",   stac_ok),
    ]

    all_passed = True
    for label, passed in checks:
        status = "PASS" if passed else "FAIL"
        print("[{}] {}".format(status, label))
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("RESULT: PASS -- CDSE S3 access validated successfully.")
        print("        Sentinel-2 L2A data is accessible for future ingestion.")
    else:
        print("RESULT: FAIL -- Issues detected:")
        for f in failures:
            print("  - {}".format(f))

    sep("=", 62)
    sys.exit(0 if all_passed else 1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
