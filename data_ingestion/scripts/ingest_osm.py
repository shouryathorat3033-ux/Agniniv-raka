#!/usr/bin/env python3
"""
HEATWATCH - OSM India PBF Ingestion CLI
=========================================
Usage:

    # Quick end-to-end sample test (node-only, no location index, ~30 s):
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\ingest_osm.py --sample

    # Dry-run (parses full PBF + geometry, no DB writes):
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\ingest_osm.py --dry-run

    # Full ingestion (streaming, way geometry enabled):
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\ingest_osm.py

    # Full ingestion using specific PBF:
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\ingest_osm.py ^
        --path "dataset\\raw\\osm\\india\\india-latest.osm.pbf"

    # Download then ingest:
    .venv\\Scripts\\python.exe data_ingestion\\scripts\\ingest_osm.py --download
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPT_DIR   = Path(__file__).resolve().parent
_DI_ROOT      = _SCRIPT_DIR.parent
_PROJECT_ROOT = _DI_ROOT.parent

sys.path.insert(0, str(_DI_ROOT))

from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env", override=True)
load_dotenv(_DI_ROOT / ".env", override=False)

import click
from common.logging_config import configure_logging
from config import settings


@click.command()
@click.option("--download", is_flag=True, default=False,
              help="Download the India OSM PBF from Geofabrik before ingesting.")
@click.option("--path", "pbf_path_str", default=None, type=str,
              help="Path to an existing .osm.pbf file.")
@click.option("--batch-size", default=None, type=int,
              help="Features per database batch (default: OSM_BATCH_SIZE from .env).")
@click.option("--skip-ingest", is_flag=True, default=False,
              help="Download only; do not run ingestion.")
@click.option("--skip-validation", is_flag=True, default=False,
              help="Skip PBF file validation.")
@click.option("--dry-run", is_flag=True, default=False,
              help="Parse PBF + create geometries but do NOT write to database.")
@click.option("--sample", is_flag=True, default=False,
              help=(
                  "Fast end-to-end test: parse node-only (no location index), "
                  "insert up to --sample-limit features into DB. "
                  "Completes in ~30 s. Use to verify the full pipeline before "
                  "committing to a multi-hour full ingestion."
              ))
@click.option("--sample-limit", default=50_000, type=int, show_default=True,
              help="Max features to extract in --sample mode.")
@click.option("--no-way-geometry", is_flag=True, default=False,
              help=(
                  "Full ingestion without building the node-location index. "
                  "Ways get NULL geometry but the run completes much faster. "
                  "Useful when RAM is limited."
              ))
def main(
    download: bool,
    pbf_path_str: str | None,
    batch_size: int | None,
    skip_ingest: bool,
    skip_validation: bool,
    dry_run: bool,
    sample: bool,
    sample_limit: int,
    no_way_geometry: bool,
) -> None:
    """Run HEATWATCH OSM India PBF ingestion."""
    configure_logging(settings.LOG_LEVEL, settings.LOG_FILE)

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
    with_way_geom = not no_way_geometry

    print()
    print("=" * 72)
    print("HEATWATCH -- OSM India Ingestion")
    print("=" * 72)
    print(f"  Source : {OSM_PBF_URL}")
    print(f"  PBF    : {pbf_path}")
    print(f"  Batch  : {effective_batch:,}")
    flags = []
    if dry_run:   flags.append("dry-run")
    if sample:    flags.append(f"sample ({sample_limit:,} features)")
    if not with_way_geom: flags.append("no-way-geometry")
    print(f"  Mode   : {', '.join(flags) or 'full ingestion'}")
    print()

    # Download
    if download:
        print("[STEP] Downloading India OSM PBF ...")
        try:
            pbf_path = download_pbf(
                url=OSM_PBF_URL,
                dest=pbf_path,
                timeout=OSM_REQUEST_TIMEOUT,
                max_retries=OSM_MAX_RETRIES,
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

    if skip_ingest and not dry_run:
        print("[OK] Download complete.  Skipping ingestion (--skip-ingest).")
        raise click.exceptions.Exit(0)

    try:
        result = run_pbf_pipeline(
            pbf_path=pbf_path,
            batch_size=effective_batch,
            skip_validation=skip_validation,
            dry_run=dry_run,
            sample=sample,
            sample_limit=sample_limit,
            with_way_geometry=with_way_geom,
        )
    except RuntimeError as exc:
        click.echo(f"\n[FAIL] Ingestion failed: {exc}", err=True)
        raise click.exceptions.Exit(1)

    raise click.exceptions.Exit(
        0 if result.get("status") in ("success", "dry_run") else 1
    )


if __name__ == "__main__":
    main()