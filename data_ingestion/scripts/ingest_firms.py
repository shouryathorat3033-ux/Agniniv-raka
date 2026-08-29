#!/usr/bin/env python3
"""
HEATWATCH — FIRMS Ingestion Script
=====================================
Usage:
    python scripts/ingest_firms.py --path ../dataset/raw/firms/firms_viirs_20240615.csv

Options:
    --path        Path to FIRMS CSV file (required)
    --batch-size  Records per DB transaction (default: 1000)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import click
from common.logging_config import configure_logging, get_logger
from config import settings
from firms.pipeline import run_firms_pipeline

log = get_logger(__name__)


@click.command()
@click.option("--path", required=True, type=click.Path(exists=True), help="Path to FIRMS CSV file")
@click.option("--batch-size", default=None, type=int, help="Records per DB transaction")
def main(path: str, batch_size: int | None) -> None:
    configure_logging(settings.LOG_LEVEL, settings.LOG_FILE)
    csv_path = Path(path)
    click.echo(f"Ingesting FIRMS: {csv_path}")
    result = run_firms_pipeline(csv_path, batch_size=batch_size)
    click.echo(result.summary_line())
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
