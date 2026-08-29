#!/usr/bin/env python3
"""
HEATWATCH — Satellite Metadata Ingestion Script
Usage:
    python scripts/ingest_satellite_metadata.py --path ../dataset/raw/satellite/
    python scripts/ingest_satellite_metadata.py --path ../dataset/raw/satellite/S2A_MSIL2A_20240615.SAFE
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import click
from common.logging_config import configure_logging
from config import settings
from satellite.pipeline import run_satellite_pipeline


@click.command()
@click.option("--path", required=True, type=click.Path(exists=True),
              help="Path to satellite scene directory or SAFE directory")
def main(path: str) -> None:
    configure_logging(settings.LOG_LEVEL, settings.LOG_FILE)
    p = Path(path)
    source_dir = p if p.is_dir() else p.parent
    click.echo(f"Processing satellite metadata from: {source_dir}")
    result = run_satellite_pipeline(source_dir=source_dir)
    click.echo(result.summary_line())
    if result.warnings:
        click.echo(f"Warnings: {len(result.warnings)}")
        for w in result.warnings[:5]:
            click.echo(f"  {w}")
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
