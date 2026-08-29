#!/usr/bin/env python3
"""
HEATWATCH — Ingest All Datasets
==================================
Runs all available ingestion pipelines in dependency-aware order:

  1. Industrial facilities (no dependencies)
  2. OSM (no dependencies)
  3. Historical FIRMS → hotspots
  4. Current FIRMS → hotspots
  5. Land-cover (registration only unless --with-landcover-lookup)
  6. Satellite metadata (registration only)

Usage:
    python scripts/ingest_all.py
    python scripts/ingest_all.py --skip-firms --skip-historical

The script only processes datasets that have files in their raw/ directories.
It does NOT download any data.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import click
from common.logging_config import configure_logging, get_logger
from config import settings

log = get_logger(__name__)

PASS = "✔"
FAIL = "✘"
SKIP = "↷"


def _has_files(directory: Path, pattern: str = "*") -> bool:
    return directory.exists() and bool(list(directory.glob(pattern)))


@click.command()
@click.option("--skip-industrial", is_flag=True, help="Skip industrial facility ingestion")
@click.option("--skip-osm",        is_flag=True, help="Skip OSM ingestion")
@click.option("--skip-historical", is_flag=True, help="Skip historical FIRMS ingestion")
@click.option("--skip-firms",      is_flag=True, help="Skip current FIRMS ingestion")
@click.option("--skip-landcover",  is_flag=True, help="Skip land-cover registration")
@click.option("--skip-satellite",  is_flag=True, help="Skip satellite metadata")
def main(
    skip_industrial: bool,
    skip_osm: bool,
    skip_historical: bool,
    skip_firms: bool,
    skip_landcover: bool,
    skip_satellite: bool,
) -> None:
    configure_logging(settings.LOG_LEVEL, settings.LOG_FILE)
    results: dict[str, str] = {}

    click.echo("=" * 60)
    click.echo("  HEATWATCH — Ingest All")
    click.echo("=" * 60)

    # ── 1. Industrial ─────────────────────────────────────────
    if not skip_industrial:
        files = list(settings.INDUSTRIAL_RAW_PATH.glob("*.csv")) + \
                list(settings.INDUSTRIAL_RAW_PATH.glob("*.geojson"))
        if files:
            from industrial.pipeline import run_industrial_pipeline
            for f in files:
                click.echo(f"\n[industrial] {f.name}")
                r = run_industrial_pipeline(f)
                results[f"industrial:{f.name}"] = r.summary_line()
                click.echo(f"  {PASS if r.success else FAIL} {r.summary_line()}")
        else:
            click.echo(f"\n[industrial] {SKIP} No files in {settings.INDUSTRIAL_RAW_PATH}")
    else:
        results["industrial"] = "SKIPPED"

    # ── 2. OSM ────────────────────────────────────────────────
    if not skip_osm and _has_files(settings.OSM_RAW_PATH, "*.geojson"):
        from osm.pipeline import run_osm_pipeline
        click.echo(f"\n[osm]")
        r = run_osm_pipeline()
        results["osm"] = r.summary_line()
        click.echo(f"  {PASS if r.success else FAIL} {r.summary_line()}")
    else:
        click.echo(f"\n[osm] {SKIP} No GeoJSON files or skipped")
        results["osm"] = "SKIPPED"

    # ── 3. Historical FIRMS ───────────────────────────────────
    if not skip_historical and _has_files(settings.HISTORICAL_FIRMS_RAW_PATH, "*.csv"):
        from historical_firms.pipeline import run_historical_firms_pipeline
        click.echo(f"\n[historical_firms]")
        rs = run_historical_firms_pipeline()
        for r in rs:
            click.echo(f"  {PASS if r.success else FAIL} {r.summary_line()}")
        results["historical_firms"] = f"{len(rs)} files"
    else:
        click.echo(f"\n[historical_firms] {SKIP} No CSV files or skipped")
        results["historical_firms"] = "SKIPPED"

    # ── 4. Current FIRMS ──────────────────────────────────────
    if not skip_firms and _has_files(settings.FIRMS_RAW_PATH, "*.csv"):
        from firms.pipeline import run_firms_pipeline
        from firms.reader import list_firms_files
        csv_files = list_firms_files(settings.FIRMS_RAW_PATH)
        click.echo(f"\n[firms] {len(csv_files)} file(s)")
        for f in csv_files:
            r = run_firms_pipeline(f)
            results[f"firms:{f.name}"] = r.summary_line()
            click.echo(f"  {PASS if r.success else FAIL} {r.summary_line()}")
    else:
        click.echo(f"\n[firms] {SKIP} No CSV files or skipped")
        results["firms"] = "SKIPPED"

    # ── 5. Land-cover ─────────────────────────────────────────
    if not skip_landcover:
        tif_files = list(settings.LANDCOVER_RAW_PATH.glob("*.tif")) + \
                    list(settings.LANDCOVER_RAW_PATH.glob("*.tiff"))
        if tif_files:
            from landcover.pipeline import run_landcover_pipeline
            click.echo(f"\n[landcover] registration-only")
            r = run_landcover_pipeline(tif_files[0])
            results["landcover"] = r.summary_line()
            click.echo(f"  {PASS if r.success else FAIL} {r.summary_line()}")
        else:
            click.echo(f"\n[landcover] {SKIP} No GeoTIFF files")
            results["landcover"] = "SKIPPED"
    else:
        results["landcover"] = "SKIPPED"

    # ── 6. Satellite ──────────────────────────────────────────
    if not skip_satellite and settings.SATELLITE_RAW_PATH.exists():
        from satellite.pipeline import run_satellite_pipeline
        click.echo(f"\n[satellite]")
        r = run_satellite_pipeline()
        results["satellite"] = r.summary_line()
        click.echo(f"  {PASS if r.success else FAIL} {r.summary_line()}")
    else:
        click.echo(f"\n[satellite] {SKIP}")
        results["satellite"] = "SKIPPED"

    click.echo("\n" + "=" * 60)
    click.echo("  Summary")
    click.echo("=" * 60)
    for k, v in results.items():
        click.echo(f"  {k}: {v}")


if __name__ == "__main__":
    main()
