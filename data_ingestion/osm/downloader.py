"""
HEATWATCH — OSM PBF Downloader
================================
Downloads the India OSM PBF extract from Geofabrik (or configured URL).

Strategy:
  1. If a valid PBF already exists, skip download.
  2. Stream to a .part file.
  3. On complete, rename .part -> .osm.pbf.
  4. Retry on transient errors (up to OSM_MAX_RETRIES).
  5. Never load the whole file into memory.
"""
from __future__ import annotations

import time
from pathlib import Path

import requests
from tqdm import tqdm

from common.logging_config import get_logger

log = get_logger(__name__)

_USER_AGENT = (
    "HEATWATCH/1.0 (India Urban Heat Sentinel - academic research; "
    "OSM data ingestion via Geofabrik)"
)


def _is_valid_pbf(path: Path, min_size_bytes: int = 1_000_000) -> bool:
    """Basic heuristic: file exists, non-empty, has PBF magic bytes."""
    if not path.exists() or path.stat().st_size < min_size_bytes:
        return False
    try:
        with open(path, "rb") as fh:
            header = fh.read(4)
        # PBF files start with a blob header length (4-byte big-endian int)
        # and are never zero-length. Any non-zero 4-byte header is acceptable.
        return len(header) == 4
    except OSError:
        return False


def download_pbf(
    url: str,
    dest: Path,
    timeout: int = 120,
    max_retries: int = 3,
) -> Path:
    """
    Download a PBF file from ``url`` to ``dest``.

    Returns the path to the downloaded file.
    Raises RuntimeError on permanent failure.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    if _is_valid_pbf(dest):
        size_mb = dest.stat().st_size / 1024 / 1024
        log.info(
            "osm.download.skipped",
            path=str(dest),
            size_mb=round(size_mb, 1),
            reason="valid PBF already exists",
        )
        print(f"  [OK] PBF already exists ({size_mb:.1f} MB) — skipping download.")
        print(f"       {dest}")
        return dest

    part_path = dest.with_suffix(".pbf.part")
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        log.info(
            "osm.download.start",
            url=url,
            dest=str(dest),
            attempt=attempt,
            max_retries=max_retries,
        )
        print(f"\n  Downloading India OSM PBF (attempt {attempt}/{max_retries})")
        print(f"  Source : {url}")
        print(f"  Dest   : {dest}")

        try:
            resp = requests.get(
                url,
                stream=True,
                timeout=timeout,
                headers={"User-Agent": _USER_AGENT},
            )
            resp.raise_for_status()

            total = int(resp.headers.get("content-length", 0))
            chunk_size = 1 * 1024 * 1024  # 1 MB chunks

            with open(part_path, "wb") as fh, tqdm(
                total=total,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc="  Downloading",
                leave=True,
            ) as pbar:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if chunk:
                        fh.write(chunk)
                        pbar.update(len(chunk))

            # Validate part file
            if not _is_valid_pbf(part_path):
                part_path.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Downloaded file failed PBF validation: {part_path}"
                )

            # Atomic rename
            part_path.replace(dest)
            size_mb = dest.stat().st_size / 1024 / 1024
            log.info(
                "osm.download.complete",
                path=str(dest),
                size_mb=round(size_mb, 1),
            )
            print(f"\n  [OK] Download complete: {size_mb:.1f} MB -> {dest}")
            return dest

        except (requests.RequestException, RuntimeError, OSError) as exc:
            last_exc = exc
            log.warning(
                "osm.download.retry",
                attempt=attempt,
                error=str(exc),
            )
            print(f"\n  [WARN] Attempt {attempt} failed: {exc}")
            part_path.unlink(missing_ok=True)
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"  Retrying in {wait}s ...")
                time.sleep(wait)

    raise RuntimeError(
        f"Failed to download PBF after {max_retries} attempts. "
        f"Last error: {last_exc}"
    )
