#!/usr/bin/env python3
"""
HEATWATCH — Validate Dataset Script
=====================================
Validates a dataset without loading it into the database.

Usage:
    python scripts/validate_dataset.py --dataset firms --path ../dataset/raw/firms/file.csv
    python scripts/validate_dataset.py --dataset osm   --path ../dataset/raw/osm/extract.geojson
    python scripts/validate_dataset.py --dataset landcover --path ../dataset/raw/landcover/file.tif
    python scripts/validate_dataset.py --dataset industrial --path ../dataset/raw/industrial/gem.csv
    python scripts/validate_dataset.py --dataset satellite  --path ../dataset/raw/satellite/

Supported datasets: firms, historical_firms, osm, landcover, industrial, satellite
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import click
from common.logging_config import configure_logging
from config import settings

SUPPORTED = ["firms", "historical_firms", "osm", "landcover", "industrial", "satellite"]


@click.command()
@click.option("--dataset", required=True, type=click.Choice(SUPPORTED), help="Dataset type")
@click.option("--path", required=True, type=click.Path(exists=True), help="Path to file or directory")
def main(dataset: str, path: str) -> None:
    configure_logging(settings.LOG_LEVEL)
    p = Path(path)
    errors: list[str] = []
    click.echo(f"Validating [{dataset}]: {p}")

    if dataset in ("firms", "historical_firms"):
        from firms.reader import read_firms_csv
        from firms.validator import validate_firms_dataframe
        files = [p] if p.is_file() else sorted(p.glob("*.csv"))
        for f in files:
            df = read_firms_csv(f)
            valid, rejected = validate_firms_dataframe(df)
            click.echo(f"  {f.name}: {len(df)} rows, {len(valid)} valid, {len(rejected)} rejected")
            errors += list(rejected.get("rejection_reason", []))

    elif dataset == "osm":
        from osm.reader import read_osm_file, list_osm_files
        from osm.validator import validate_osm_dataframe
        files = [p] if p.is_file() else list_osm_files(p)
        for f in files:
            gdf = read_osm_file(f)
            valid, rejected = validate_osm_dataframe(gdf)
            click.echo(f"  {f.name}: {len(gdf)} features, {len(valid)} valid, {len(rejected)} rejected")

    elif dataset == "landcover":
        from landcover.reader import validate_raster, read_raster_metadata
        errs = validate_raster(p)
        if errs:
            for e in errs:
                click.echo(f"  WARNING: {e}")
        else:
            meta = read_raster_metadata(p)
            click.echo(f"  CRS: {meta['crs']}, Size: {meta['width']}x{meta['height']}, "
                       f"Res: {meta['res_x']:.5f}°")
            click.echo(f"  Bounds: {meta['bounds']}")

    elif dataset == "industrial":
        from industrial.reader import read_industrial_file
        from industrial.validator import validate_industrial_dataframe
        gdf = read_industrial_file(p)
        valid, rejected = validate_industrial_dataframe(gdf)
        click.echo(f"  {len(gdf)} rows, {len(valid)} valid, {len(rejected)} rejected")

    elif dataset == "satellite":
        from satellite.scene_reader import list_scene_sources, read_sentinel2_metadata, read_scene_json
        from satellite.validator import validate_scene_metadata
        sources = [p] if p.is_file() or (p.is_dir() and p.suffix == ".SAFE") else list_scene_sources(p)
        for src in sources:
            try:
                if src.is_dir():
                    meta = read_sentinel2_metadata(src)
                else:
                    meta = read_scene_json(src)
                errs = validate_scene_metadata(meta)
                status = "VALID" if not errs else f"INVALID: {'; '.join(errs)}"
                click.echo(f"  {src.name}: {status}")
            except Exception as exc:
                click.echo(f"  {src.name}: ERROR — {exc}")

    click.echo(f"\nValidation complete. Errors found: {len(errors)}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
