from pathlib import Path
import re
import json
from shapely.geometry import shape, box

BOUNDARY = Path("dataset/raw/boundaries/india_boundary.geojson")
INVENTORY = Path("dataset/processed/landcover/worldcover_inventory.txt")

print("=" * 70)
print("HeatWatch - INDIA WorldCover Download Size Check")
print("=" * 70)

# Load India boundary
with open(BOUNDARY, "r", encoding="utf-8") as f:
    data = json.load(f)

india_geom = shape(data["features"][0]["geometry"])

print("\nIndia boundary:")
print(f"  Geometry : {india_geom.geom_type}")
print(f"  Bounds   : {india_geom.bounds}")

# Read AWS inventory
with open(INVENTORY, "r", encoding="utf-16") as f:
    lines = f.readlines()

pattern = re.compile(
    r"ESA_WorldCover_10m_2021_v200_"
    r"([NS])(\d+)([EW])(\d+)_Map\.tif$"
)

selected = []

for line in lines:
    parts = line.split()

    if len(parts) < 4:
        continue

    size_bytes = int(parts[2])
    key = parts[-1]
    filename = Path(key).name

    match = pattern.match(filename)

    if not match:
        continue

    lat_dir, lat_value, lon_dir, lon_value = match.groups()

    lat = int(lat_value)
    lon = int(lon_value)

    if lat_dir == "S":
        lat = -lat

    if lon_dir == "W":
        lon = -lon

    tile = box(lon, lat, lon + 3, lat + 3)

    if tile.intersects(india_geom):
        selected.append((filename, size_bytes, key))

selected = sorted(set(selected))

total_bytes = sum(x[1] for x in selected)

print("\n" + "=" * 70)
print("INDIA-INTERSECTING TILES")
print("=" * 70)

print(f"\nNumber of tiles : {len(selected)}")
print(f"Total size      : {total_bytes / (1024**3):.2f} GB")
print(f"Total size      : {total_bytes / (1024**2):.0f} MB")

print("\nTiles:")

for i, (filename, size, key) in enumerate(selected, 1):
    print(
        f"{i:2}. {filename:<65} "
        f"{size / (1024**2):7.1f} MB"
    )

# Save the exact India-only tile list
TILE_LIST = Path("dataset/processed/landcover/india_worldcover_tiles.txt")

with open(TILE_LIST, "w", encoding="utf-8") as f:
    for filename, size, key in selected:
        f.write(key + "\n")

print("\n" + "=" * 70)
print("INDIA TILE LIST SAVED")
print("=" * 70)

print(f"Tiles saved : {len(selected)}")
print(f"List file   : {TILE_LIST}")
print(f"Total size  : {total_bytes / (1024**3):.2f} GB")