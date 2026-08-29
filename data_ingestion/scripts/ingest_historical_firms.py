#!/usr/bin/env python3
"""
HEATWATCH — Historical FIRMS Ingestion Script
Usage:
    python scripts/ingest_historical_firms.py --path ../dataset/raw/historical_firms/
    python scripts/ingest_historical_firms.py --path ../dataset/raw/historical_firms/archive_2020.csv
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import click
from common.logging_config import configure_logging, get_logger
from config import settings
from historical_firms.pipeline import run_historical_firms_pipeline
from historical_firms.reader import list_historical_files
from firms.pipeline import run_firms_pipeline

log = get_logger(__name__)


@click.command()
@click.option("--path", required=True, type=click.Path(exists=True),
              help="Path to a directory of historical FIRMS CSVs, or a single CSV file")
@click.option("--chunk-size", default=None, type=int, help="Rows per chunk for large files")
def main(path: str, chunk_size: int | None) -> None:
    configure_logging(settings.LOG_LEVEL, settings.LOG_FILE)
    p = Path(path)

    if p.is_dir():
        click.echo(f"Ingesting historical FIRMS from directory: {p}")
        results = run_historical_firms_pipeline(source_dir=p, chunk_size=chunk_size)
        total_inserted = sum(r.records_inserted for r in results)
        success = all(r.success for r in results)
        click.echo(f"Done: {len(results)} file(s), {total_inserted} inserted. Success={success}")
    elif p.is_file():
        click.echo(f"Ingesting historical FIRMS single file: {p}")
        result = run_firms_pipeline(p)
        click.echo(result.summary_line())
        success = result.success
    else:
        click.echo(f"ERROR: {p} is not a file or directory", err=True)
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
