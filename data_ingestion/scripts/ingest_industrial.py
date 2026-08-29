#!/usr/bin/env python3
"""
HEATWATCH — Industrial Facility Ingestion Script
Usage:
    python scripts/ingest_industrial.py --path ../dataset/raw/industrial/gem_2024.csv
    python scripts/ingest_industrial.py --path ../dataset/raw/industrial/gppd.geojson \
        --source GPPD --dataset-id GPPD_v13
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import click
from common.logging_config import configure_logging
from config import settings
from industrial.pipeline import run_industrial_pipeline


@click.command()
@click.option("--path", required=True, type=click.Path(exists=True),
              help="Path to industrial facility CSV/GeoJSON/GeoPackage")
@click.option("--source", default="INDUSTRIAL_DB", help="Source name for DB (default: INDUSTRIAL_DB)")
@click.option("--dataset-id", default=None, help="Dataset version ID (e.g. GEM_2024)")
def main(path: str, source: str, dataset_id: str | None) -> None:
    configure_logging(settings.LOG_LEVEL, settings.LOG_FILE)
    result = run_industrial_pipeline(
        Path(path),
        source_name=source,
        dataset_id=dataset_id,
    )
    click.echo(result.summary_line())
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
