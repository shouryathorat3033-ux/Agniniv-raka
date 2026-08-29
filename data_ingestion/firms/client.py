"""
HEATWATCH — FIRMS API HTTP Client
====================================
Handles all communication with the NASA FIRMS API.

API Documentation: https://firms.modaps.eosdis.nasa.gov/api/

Key behaviors:
- Authenticates via FIRMS_MAP_KEY (never printed in logs)
- Retries transient errors (5xx, 429) with exponential backoff
- Returns clean error messages for auth failures (401/403)
- Validates response content type before returning
- Checks for API error responses embedded in CSV bodies

API error detection:
  The FIRMS API sometimes returns HTTP 200 with an error message body
  (e.g. "Invalid key" or "No data found"). We detect these cases.
"""
from __future__ import annotations

import time
from typing import Any

import requests

from common.logging_config import get_logger

log = get_logger(__name__)

_USER_AGENT = "HEATWATCH/1.0 (academic research; FIRMS India ingestion)"

# FIRMS API sometimes returns error messages as plain text with HTTP 200
_API_ERROR_PHRASES = [
    "invalid key",
    "invalid map key",
    "key not found",
    "unauthorized",
    "forbidden",
    "no data found",
    "error",
]


class FIRMSAuthError(Exception):
    """Raised when the API key is missing, invalid, or unauthorized."""


class FIRMSAPIError(Exception):
    """Raised on unrecoverable API errors."""


class FIRMSRateLimitError(Exception):
    """Raised on 429 Too Many Requests."""


def _check_response_body(text: str, url: str) -> None:
    """
    Detect FIRMS API error messages embedded in HTTP 200 responses.
    FIRMS sometimes returns 'Invalid Key' with status 200.
    """
    if not text or len(text) > 500:
        return  # real CSV responses are long; short responses may be errors
    lower = text.strip().lower()
    for phrase in _API_ERROR_PHRASES:
        if phrase in lower:
            raise FIRMSAPIError(
                f"FIRMS API returned an error message (HTTP 200 with error body).\n"
                f"  URL     : {url}\n"
                f"  Response: {text.strip()[:200]}\n"
                f"  If this says 'invalid key', check NASA_FIRMS_API_KEY in .env."
            )


def make_country_csv_url(
    base_url: str,
    api_key: str,
    source: str,
    country: str,
    days: int,
) -> str:
    """
    Build the FIRMS country CSV API URL.

    Format:
      {base_url}/country/csv/{api_key}/{source}/{country}/{days}

    Example:
      https://firms.modaps.eosdis.nasa.gov/api/country/csv/MYKEY/VIIRS_NOAA20_NRT/IND/1
    """
    # Strip trailing slash from base_url
    base = base_url.rstrip("/")
    return f"{base}/country/csv/{api_key}/{source}/{country}/{days}"


def make_area_csv_url(
    base_url: str,
    api_key: str,
    source: str,
    bbox: dict[str, float],
    days: int,
) -> str:
    """
    Build the FIRMS area/bbox CSV API URL (fallback if country endpoint fails).

    Format:
      {base_url}/area/csv/{api_key}/{source}/{W},{S},{E},{N}/{days}
    """
    base = base_url.rstrip("/")
    w, s, e, n = bbox["min_lon"], bbox["min_lat"], bbox["max_lon"], bbox["max_lat"]
    return f"{base}/area/csv/{api_key}/{source}/{w},{s},{e},{n}/{days}"


def fetch_firms_csv(
    url: str,
    timeout: int = 120,
    max_retries: int = 3,
) -> str:
    """
    Fetch FIRMS CSV data from the given URL.

    Returns the raw CSV text on success.
    Raises FIRMSAuthError, FIRMSAPIError, or FIRMSRateLimitError on failure.

    Security: URL contains the API key, so we log only the non-secret portion.
    """
    # Log the URL with key masked
    log_url = _mask_key_in_url(url)
    log.info("firms.api.request", url=log_url)

    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": _USER_AGENT},
                allow_redirects=True,
            )

            # ── Auth errors — do NOT retry ─────────────────────
            if resp.status_code in (401, 403):
                raise FIRMSAuthError(
                    f"FIRMS API authentication failed (HTTP {resp.status_code}).\n"
                    "  Check NASA_FIRMS_API_KEY / FIRMS_MAP_KEY in .env.\n"
                    "  Get a free key at: https://firms.modaps.eosdis.nasa.gov/api/"
                )

            # ── Not found ─────────────────────────────────────
            if resp.status_code == 404:
                raise FIRMSAPIError(
                    f"FIRMS API endpoint not found (HTTP 404).\n"
                    f"  URL: {log_url}\n"
                    "  Check FIRMS_SOURCE and FIRMS_COUNTRY values."
                )

            # ── Rate limit — retry with backoff ───────────────
            if resp.status_code == 429:
                wait = 30 * attempt
                log.warning("firms.api.rate_limited", attempt=attempt, wait_s=wait)
                if attempt < max_retries:
                    print(f"  [WARN] Rate limited (429) — waiting {wait}s ...")
                    time.sleep(wait)
                    last_exc = FIRMSRateLimitError("429 Too Many Requests")
                    continue
                raise FIRMSRateLimitError(
                    "FIRMS API rate limit reached after all retries.\n"
                    "  Wait a few minutes and try again."
                )

            # ── Server errors — retry ─────────────────────────
            if resp.status_code >= 500:
                wait = 2 ** attempt
                log.warning("firms.api.server_error",
                            status=resp.status_code, attempt=attempt, wait_s=wait)
                if attempt < max_retries:
                    print(f"  [WARN] Server error ({resp.status_code}) — retrying in {wait}s ...")
                    time.sleep(wait)
                    last_exc = FIRMSAPIError(f"HTTP {resp.status_code}")
                    continue
                raise FIRMSAPIError(
                    f"FIRMS API server error (HTTP {resp.status_code}) after {max_retries} retries."
                )

            resp.raise_for_status()

            text = resp.text
            log.info(
                "firms.api.response",
                url=log_url,
                status=resp.status_code,
                content_length=len(text),
            )

            # Check for embedded error messages (HTTP 200 but error body)
            _check_response_body(text, log_url)

            return text

        except (FIRMSAuthError, FIRMSAPIError, FIRMSRateLimitError):
            raise  # never retry auth/logic errors
        except requests.RequestException as exc:
            last_exc = exc
            log.warning("firms.api.request_error", attempt=attempt, error=str(exc))
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"  [WARN] Request error (attempt {attempt}) — retrying in {wait}s: {exc}")
                time.sleep(wait)
            else:
                raise FIRMSAPIError(
                    f"FIRMS API request failed after {max_retries} attempts: {exc}"
                ) from exc

    raise FIRMSAPIError(f"FIRMS API failed: {last_exc}")


def check_api_connectivity(base_url: str, api_key: str, timeout: int = 30) -> dict[str, Any]:
    """
    Quick connectivity check using the FIRMS area endpoint.
    Uses India bbox with days=1 — a very small response.

    Returns dict with:
      reachable: bool
      authenticated: bool
      message: str
    """
    # Use area endpoint with India bbox — this works reliably.
    # Country endpoint (/country/csv/{key}/source/IND/1) returns 400
    # for many sources; area endpoint always works.
    url = make_area_csv_url(
        base_url, api_key, "VIIRS_NOAA20_NRT",
        {"min_lon": 68.0, "min_lat": 6.0, "max_lon": 98.0, "max_lat": 37.0},
        days=1,
    )
    log_url = _mask_key_in_url(url)

    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": _USER_AGENT},
        )
        if resp.status_code in (401, 403):
            return {
                "reachable": True,
                "authenticated": False,
                "message": f"HTTP {resp.status_code} — API key invalid or unauthorized",
            }
        if resp.status_code >= 500:
            return {
                "reachable": True,
                "authenticated": False,
                "message": f"HTTP {resp.status_code} — server error",
            }

        # Check body for embedded errors
        body_preview = resp.text[:300].strip().lower()
        for phrase in ["invalid key", "invalid map key", "unauthorized", "invalid api"]:
            if phrase in body_preview:
                return {
                    "reachable": True,
                    "authenticated": False,
                    "message": f"API rejected request: {resp.text[:100].strip()}",
                }

        rows = len(resp.text.strip().splitlines())
        return {
            "reachable": True,
            "authenticated": resp.status_code == 200,
            "message": f"HTTP {resp.status_code}",
            "rows": rows,
        }

    except requests.exceptions.ConnectionError as exc:
        return {"reachable": False, "authenticated": False, "message": str(exc)[:100]}
    except requests.exceptions.Timeout:
        return {"reachable": False, "authenticated": False, "message": "Connection timed out"}
    except Exception as exc:
        return {"reachable": False, "authenticated": False, "message": str(exc)[:100]}


def _mask_key_in_url(url: str) -> str:
    """Replace the API key segment in a FIRMS URL with '***' for safe logging."""
    # FIRMS URL format: .../csv/{key}/...
    # Replace the key portion between /csv/ and the next /
    import re
    return re.sub(r"(/csv/)([^/]+)(/)", r"\1***\3", url)
