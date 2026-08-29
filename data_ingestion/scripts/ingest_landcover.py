#!/usr/bin/env python3
"""
HEATWATCH — Land Cover Ingestion Script
Usage:
    # Registration only (validate + manifest):
    python scripts/ingest_landcover.py --path ../dataset/raw/landcover/ESA_WorldCover_v200.tif

    # With thermal object lookup (requires a JSON file listing thermal objects):
    python scripts/ingest_landcover.py \
        --path ../dataset/raw/landcover/ESA_WorldCover_v200.tif \
        --thermal-objects thermal_objects.json

thermal_objects.json format:
  [{"thermal_object_id": "uuid", "lon": 72.8, "lat": 21.2}, ...]
"""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import click
from common.logging_config import configure_logging
from config import settings
from landcover.pipeline import run_landcover_pipeline


@click.command()
@click.option("--path", required=True, type=click.Path(exists=True), help="Path to land-cover GeoTIFF")
@click.option("--thermal-objects", default=None, type=click.Path(exists=True),
              help="JSON file listing thermal objects for batch lookup")
@click.option("--buffer", default=0.01, type=float, help="Buffer radius in degrees (default 0.01 ≈ 1 km)")
def main(path: str, thermal_objects: str | None, buffer: float) -> None:
    configure_logging(settings.LOG_LEVEL, settings.LOG_FILE)
    raster_path = Path(path)
    objs = None
    if thermal_objects:
        objs = json.loads(Path(thermal_objects).read_text())
        click.echo(f"Batch lookup for {len(objs)} thermal objects")
    else:
        click.echo("Registration-only mode (no thermal objects supplied)")

    result = run_landcover_pipeline(raster_path, thermal_objects=objs, buffer_degrees=buffer)
    click.echo(result.summary_line())
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
