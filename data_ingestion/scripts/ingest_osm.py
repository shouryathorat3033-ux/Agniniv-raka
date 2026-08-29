#!/usr/bin/env python3
"""
HEATWATCH — OSM Ingestion Script
Usage:
    python scripts/ingest_osm.py --path ../dataset/raw/osm/
    python scripts/ingest_osm.py --path ../dataset/raw/osm/india_industrial.geojson
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import click
from common.logging_config import configure_logging
from config import settings
from osm.pipeline import run_osm_pipeline


@click.command()
@click.option("--path", required=True, type=click.Path(exists=True),
              help="Path to OSM extract file or directory")
def main(path: str) -> None:
    configure_logging(settings.LOG_LEVEL, settings.LOG_FILE)
    p = Path(path)
    source = p if p.is_dir() else p.parent
    click.echo(f"Ingesting OSM data from: {source}")
    result = run_osm_pipeline(source_path=source)
    click.echo(result.summary_line())
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
