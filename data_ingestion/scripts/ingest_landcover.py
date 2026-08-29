#!/usr/bin/env python3
"""
HEATWATCH — Land Cover Ingestion Script

Supports:
    1. A single GeoTIFF file
    2. A directory containing multiple GeoTIFF tiles

Examples:

Single file:
    python data_ingestion/scripts/ingest_landcover.py `
        --path "dataset/raw/landcover/worldcover_2021/tile.tif"

Directory:
    python data_ingestion/scripts/ingest_landcover.py `
        --path "dataset/raw/landcover/worldcover_2021"

With thermal objects:
    python data_ingestion/scripts/ingest_landcover.py `
        --path "dataset/raw/landcover/worldcover_2021" `
        --thermal-objects thermal_objects.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make data_ingestion importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_INGESTION_ROOT = PROJECT_ROOT / "data_ingestion"

sys.path.insert(0, str(DATA_INGESTION_ROOT))

from dotenv import load_dotenv

# Load project-root .env (has real DATABASE_URL with correct port),
# then data_ingestion/.env as a legacy fallback.
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(DATA_INGESTION_ROOT / ".env", override=False)

import click

from common.logging_config import configure_logging
from config import settings
from landcover.pipeline import run_landcover_pipeline


def find_geotiffs(path: Path) -> list[Path]:
    """
    Return all GeoTIFF files from a file or directory.

    If path is a file:
        return [path]

    If path is a directory:
        recursively find *.tif and *.tiff files.
    """

    if path.is_file():
        suffix = path.suffix.lower()

        if suffix not in {".tif", ".tiff"}:
            raise click.ClickException(
                f"Expected a GeoTIFF file (.tif/.tiff), got: {path.name}"
            )

        return [path]

    if path.is_dir():
        files = sorted(
            [
                p
                for p in path.rglob("*")
                if p.is_file()
                and p.suffix.lower() in {".tif", ".tiff"}
            ]
        )

        if not files:
            raise click.ClickException(
                f"No GeoTIFF files found inside directory:\n{path}"
            )

        return files

    raise click.ClickException(
        f"Path does not exist or is not accessible:\n{path}"
    )


def load_thermal_objects(path: str | None):
    """Load thermal objects JSON if supplied."""

    if not path:
        return None

    thermal_path = Path(path)

    try:
        data = json.loads(
            thermal_path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise click.ClickException(
            f"Invalid JSON in thermal objects file: {thermal_path}\n{exc}"
        ) from exc

    if not isinstance(data, list):
        raise click.ClickException(
            "Thermal objects JSON must contain a JSON list."
        )

    return data


@click.command()
@click.option(
    "--path",
    required=True,
    type=click.Path(
        exists=True,
        path_type=Path,
        file_okay=True,
        dir_okay=True,
    ),
    help="Path to a GeoTIFF file OR directory containing GeoTIFF tiles.",
)
@click.option(
    "--thermal-objects",
    default=None,
    type=click.Path(
        exists=True,
        path_type=Path,
        file_okay=True,
        dir_okay=False,
    ),
    help="JSON file listing thermal objects for batch lookup.",
)
@click.option(
    "--buffer",
    default=0.01,
    type=float,
    show_default=True,
    help="Buffer radius in degrees (0.01 ~= 1 km).",
)
def main(
    path: Path,
    thermal_objects: Path | None,
    buffer: float,
) -> None:
    """Run HEATWATCH land-cover ingestion."""

    # ---------------------------------------------------------
    # Logging
    # ---------------------------------------------------------
    configure_logging(
        settings.LOG_LEVEL,
        settings.LOG_FILE,
    )

    # ---------------------------------------------------------
    # Validate buffer
    # ---------------------------------------------------------
    if buffer <= 0:
        raise click.ClickException(
            "--buffer must be greater than 0."
        )

    # ---------------------------------------------------------
    # Find GeoTIFF files
    # ---------------------------------------------------------
    try:
        raster_files = find_geotiffs(path)
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(
            f"Unable to discover GeoTIFF files: {exc}"
        ) from exc

    click.echo("")
    click.echo("=" * 70)
    click.echo("HEATWATCH — LAND COVER INGESTION")
    click.echo("=" * 70)
    click.echo(f"Input path : {path}")
    click.echo(f"GeoTIFFs   : {len(raster_files)}")
    click.echo(f"Buffer     : {buffer} degrees")
    click.echo("=" * 70)
    click.echo("")

    # ---------------------------------------------------------
    # Thermal objects
    # ---------------------------------------------------------
    objs = load_thermal_objects(
        str(thermal_objects) if thermal_objects else None
    )

    if objs is None:
        click.echo(
            "Mode: Registration-only "
            "(no thermal objects supplied)"
        )
    else:
        click.echo(
            f"Mode: Thermal-object lookup "
            f"({len(objs)} objects)"
        )

    click.echo("")

    # ---------------------------------------------------------
    # Process every GeoTIFF
    # ---------------------------------------------------------
    successful = 0
    failed = 0

    failures: list[tuple[Path, str]] = []

    for index, raster_path in enumerate(
        raster_files,
        start=1,
    ):
        click.echo(
            f"[{index}/{len(raster_files)}] "
            f"Processing: {raster_path.name}"
        )

        try:
            result = run_landcover_pipeline(
                raster_path,
                thermal_objects=objs,
                buffer_degrees=buffer,
            )

            click.echo(
                f"    {result.summary_line()}"
            )

            if result.success:
                successful += 1
            else:
                failed += 1
                failures.append(
                    (
                        raster_path,
                        result.summary_line(),
                    )
                )

        except Exception as exc:
            failed += 1

            error_message = (
                f"{type(exc).__name__}: {exc}"
            )

            failures.append(
                (
                    raster_path,
                    error_message,
                )
            )

            click.echo(
                f"    FAILED: {error_message}"
            )

    # ---------------------------------------------------------
    # Final report
    # ---------------------------------------------------------
    click.echo("")
    click.echo("=" * 70)
    click.echo("LAND COVER INGESTION COMPLETE")
    click.echo("=" * 70)
    click.echo(f"Total GeoTIFFs : {len(raster_files)}")
    click.echo(f"Successful     : {successful}")
    click.echo(f"Failed         : {failed}")
    click.echo("=" * 70)

    if failures:
        click.echo("")
        click.echo("FAILED FILES:")
        click.echo("-" * 70)

        for raster_path, error in failures:
            click.echo(
                f"{raster_path.name}\n"
                f"  {error}\n"
            )

        # Non-zero exit code tells scripts/CI that ingestion
        # was not completely successful.
        raise click.exceptions.Exit(1)

    click.echo("")
    click.echo("All GeoTIFF files processed successfully.")
    raise click.exceptions.Exit(0)


if __name__ == "__main__":
    main()