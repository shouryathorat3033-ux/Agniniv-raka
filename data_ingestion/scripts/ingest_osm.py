#!/usr/bin/env python3
"""
HEATWATCH — OSM India PBF Ingestion CLI
=========================================
Downloads and ingests the India OSM PBF extract from Geofabrik
using osmium (Python 3.14 native wheel).

Usage:

    # Download + ingest (recommended first run):
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\ingest_osm.py --download

    # Ingest a PBF already on disk:
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\ingest_osm.py ^
        --path "dataset\\raw\\osm\\india\\india-latest.osm.pbf"

    # Download only, skip ingestion:
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\ingest_osm.py ^
        --download --skip-ingest

    # Custom batch size:
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\ingest_osm.py ^
        --path "dataset\\raw\\osm\\india\\india-latest.osm.pbf" ^
        --batch-size 10000

Old GeoDataFrame pipeline (legacy, Overpass-based) preserved in osm/pipeline.py.
This script uses the new PBF-based pipeline in osm/pbf_pipeline.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

# ── Path setup — absolute, not cwd-relative ────────────────────
_SCRIPT_DIR   = Path(__file__).resolve().parent          # scripts/
_DI_ROOT      = _SCRIPT_DIR.parent                       # data_ingestion/
_PROJECT_ROOT = _DI_ROOT.parent                          # SIH_Hackthon/

sys.path.insert(0, str(_DI_ROOT))

from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env", override=False)
load_dotenv(_DI_ROOT / ".env", override=False)

import click
from common.logging_config import configure_logging
from config import settings


@click.command()
@click.option(
    "--download",
    is_flag=True,
    default=False,
    help="Download the India OSM PBF from the configured URL before ingesting.",
)
@click.option(
    "--path",
    "pbf_path_str",
    default=None,
    type=str,
    help="Path to an existing .osm.pbf file. Overrides the default configured path.",
)
@click.option(
    "--batch-size",
    default=None,
    type=int,
    help="Number of features per database batch (default: OSM_BATCH_SIZE from .env).",
)
@click.option(
    "--skip-ingest",
    is_flag=True,
    default=False,
    help="Download only; do not run the ingestion pipeline.",
)
@click.option(
    "--skip-validation",
    is_flag=True,
    default=False,
    help="Skip PBF file validation check before parsing.",
)
def main(
    download: bool,
    pbf_path_str: str | None,
    batch_size: int | None,
    skip_ingest: bool,
    skip_validation: bool,
) -> None:
    """Run HEATWATCH OSM India PBF ingestion."""
    configure_logging(settings.LOG_LEVEL, settings.LOG_FILE)

    # Late imports (after sys.path is configured)
    from osm.config import (
        OSM_BATCH_SIZE,
        OSM_MAX_RETRIES,
        OSM_PBF_PATH,
        OSM_PBF_URL,
        OSM_REQUEST_TIMEOUT,
    )
    from osm.downloader import download_pbf
    from osm.pbf_pipeline import run_pbf_pipeline

    effective_batch = batch_size or OSM_BATCH_SIZE
    pbf_path = Path(pbf_path_str) if pbf_path_str else OSM_PBF_PATH

    print()
    print("=" * 70)
    print("HEATWATCH — OSM India Ingestion")
    print("=" * 70)
    print(f"  PBF source : {OSM_PBF_URL}")
    print(f"  PBF path   : {pbf_path}")
    print(f"  Batch size : {effective_batch:,}")
    print(f"  Download   : {'yes' if download else 'no'}")
    print()

    # ── Download phase ─────────────────────────────────────────
    if download:
        print("[STEP] Downloading India OSM PBF ...")
        try:
            pbf_path = download_pbf(
                url         = OSM_PBF_URL,
                dest        = pbf_path,
                timeout     = OSM_REQUEST_TIMEOUT,
                max_retries = OSM_MAX_RETRIES,
            )
        except RuntimeError as exc:
            click.echo(f"\n[FAIL] Download failed: {exc}", err=True)
            raise click.exceptions.Exit(1)
    else:
        if not pbf_path.exists():
            click.echo(
                f"\n[FAIL] PBF not found: {pbf_path}\n"
                "       Use --download to fetch it, or provide --path.",
                err=True,
            )
            raise click.exceptions.Exit(1)

    if skip_ingest:
        print("[OK] Download complete. Skipping ingestion (--skip-ingest).")
        raise click.exceptions.Exit(0)

    # ── Ingest phase ───────────────────────────────────────────
    try:
        result = run_pbf_pipeline(
            pbf_path        = pbf_path,
            batch_size      = effective_batch,
            skip_validation = skip_validation,
        )
    except RuntimeError as exc:
        click.echo(f"\n[FAIL] Ingestion failed: {exc}", err=True)
        raise click.exceptions.Exit(1)

    raise click.exceptions.Exit(0 if result.get("status") == "success" else 1)


if __name__ == "__main__":
    main()
