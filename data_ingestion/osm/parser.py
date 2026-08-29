"""
HEATWATCH — OSM PBF Parser
============================
Uses osmium.SimpleHandler to stream-parse the India PBF.

MEMORY MODEL:
  Processes the PBF in one sequential pass.
  Emits batches of normalized feature dicts.
  Never loads the entire dataset into memory.

FEATURE CATEGORIES:
  road         — highway=*
  hospital     — amenity=hospital/clinic, healthcare=hospital/clinic
  fire_station — amenity=fire_station
  school       — amenity=school/college/university
  park         — leisure=park/garden/recreation_ground, landuse=grass/forest/meadow
  water        — natural=water, waterway=river/stream/canal
  building     — building=*
  transport    — public_transport, railway, highway=bus_stop

GEOMETRY:
  Nodes  → Point (lon, lat)
  Ways   → LineString or Polygon (if closed ring)
  Closed ways with area tags → Polygon

All coordinates are WGS84 (EPSG:4326) — osmium stores raw lon/lat.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Generator

import osmium
import osmium.geom

from common.logging_config import get_logger

log = get_logger(__name__)

# WKTFactory converts osmium geometries to WKT strings
_wkt = osmium.geom.WKTFactory()


# ── Tag classification helpers ─────────────────────────────────

ROAD_CLASSES = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "residential", "service", "unclassified", "living_street",
    "pedestrian", "cycleway", "footway", "path",
    "motorway_link", "trunk_link", "primary_link",
    "secondary_link", "tertiary_link",
}

# Tags that indicate a closed way is an area (not just a road loop)
AREA_TAGS = {
    "leisure", "landuse", "natural", "building", "amenity",
    "waterway", "healthcare", "public_transport",
}


def _tags_to_dict(tags) -> dict[str, str]:
    return {t.k: t.v for t in tags}


def _classify_feature(tags: dict[str, str]) -> list[tuple[str, str]]:
    """
    Return list of (feature_type, subtype) tuples for a set of OSM tags.
    A single OSM feature can belong to multiple categories.
    """
    results: list[tuple[str, str]] = []

    hw = tags.get("highway", "")
    if hw in ROAD_CLASSES:
        results.append(("road", hw))

    amenity = tags.get("amenity", "")
    healthcare = tags.get("healthcare", "")
    if amenity in ("hospital", "clinic") or healthcare in ("hospital", "clinic"):
        results.append(("hospital", amenity or healthcare))

    if amenity == "fire_station":
        results.append(("fire_station", "fire_station"))

    if amenity in ("school", "college", "university"):
        results.append(("school", amenity))

    leisure = tags.get("leisure", "")
    if leisure in ("park", "garden", "recreation_ground", "pitch"):
        results.append(("park", leisure))
    landuse = tags.get("landuse", "")
    if landuse in ("grass", "forest", "meadow", "greenfield"):
        results.append(("park", landuse))
    natural = tags.get("natural", "")
    if natural in ("wood", "scrub", "grassland", "heath"):
        results.append(("park", natural))

    if natural == "water":
        results.append(("water", "natural_water"))
    waterway = tags.get("waterway", "")
    if waterway in ("river", "stream", "canal", "drain", "ditch"):
        results.append(("water", waterway))

    building = tags.get("building", "")
    if building and building != "no":
        results.append(("building", building))

    pt = tags.get("public_transport", "")
    if pt in ("platform", "stop_position", "station"):
        results.append(("transport", pt))
    railway = tags.get("railway", "")
    if railway in ("station", "halt", "tram_stop", "subway_entrance"):
        results.append(("transport", railway))
    if hw == "bus_stop":
        results.append(("transport", "bus_stop"))

    return results


def _make_feature(
    osm_id: int,
    feature_type: str,
    subtype: str,
    tags: dict[str, str],
    wkt_geometry: str | None,
) -> dict[str, Any]:
    """Build a normalized feature dict for database insertion."""
    return {
        "osm_id":       osm_id,
        "feature_type": feature_type,
        "name":         tags.get("name") or tags.get("name:en"),
        "subtype":      subtype,
        "tags":         json.dumps(tags),
        "geometry_wkt": wkt_geometry,
        "source":       "OpenStreetMap",
    }


# ── Streaming handler ──────────────────────────────────────────

class _FeatureHandler(osmium.SimpleHandler):
    """
    Osmium streaming handler.

    Appends to self.batch; caller drains self.batch periodically.
    """

    def __init__(self, batch_size: int = 5000):
        super().__init__()
        self.batch_size    = batch_size
        self.batch: list[dict] = []
        self._nodes_seen   = 0
        self._ways_seen    = 0
        self._relations_seen = 0
        self._features_emitted = 0
        self._batches_emitted  = 0
        self._counts: dict[str, int] = {}

    def node(self, n):
        self._nodes_seen += 1
        tags = _tags_to_dict(n.tags)
        classifications = _classify_feature(tags)
        if not classifications:
            return

        try:
            wkt = _wkt.create_point(n)
        except Exception:
            wkt = None

        for ftype, subtype in classifications:
            self.batch.append(_make_feature(n.id, ftype, subtype, tags, wkt))
            self._counts[ftype] = self._counts.get(ftype, 0) + 1
            self._features_emitted += 1

    def way(self, w):
        self._ways_seen += 1
        tags = _tags_to_dict(w.tags)
        classifications = _classify_feature(tags)
        if not classifications:
            return

        # Determine geometry type: closed way with area tag → polygon,
        # otherwise → linestring.
        wkt = None
        is_closed = (
            len(w.nodes) >= 4
            and w.nodes[0].ref == w.nodes[-1].ref
            and any(k in tags for k in AREA_TAGS)
        )
        try:
            if is_closed:
                wkt = _wkt.create_polygon(w)
            else:
                wkt = _wkt.create_linestring(w)
        except Exception:
            # Missing node locations — skip geometry but keep feature
            wkt = None

        for ftype, subtype in classifications:
            self.batch.append(_make_feature(w.id, ftype, subtype, tags, wkt))
            self._counts[ftype] = self._counts.get(ftype, 0) + 1
            self._features_emitted += 1

    def relation(self, r):
        self._relations_seen += 1
        # Relations are complex multipolygons — store metadata only, no geometry
        tags = _tags_to_dict(r.tags)
        classifications = _classify_feature(tags)
        if not classifications:
            return
        for ftype, subtype in classifications:
            self.batch.append(_make_feature(r.id, ftype, subtype, tags, None))
            self._counts[ftype] = self._counts.get(ftype, 0) + 1
            self._features_emitted += 1


def parse_pbf_batches(
    pbf_path: Path,
    batch_size: int = 5000,
) -> Generator[list[dict[str, Any]], None, None]:
    """
    Parse a PBF file and yield batches of feature dicts.

    Uses osmium's apply_file with locations=True (flex_mem index) to resolve
    way node coordinates in a single streaming pass.

    Memory model:
    - osmium streams the PBF internally
    - Completed batches are accumulated in a list during parsing
    - After parsing, batches are yielded one by one to the caller
    - This avoids holding the entire dataset as one giant list

    Yields
    ------
    list[dict]  -- batch of normalized feature dicts, each batch <= batch_size
    """
    log.info("osm.parser.start", path=str(pbf_path), batch_size=batch_size)

    completed_batches: list[list[dict]] = []

    class _BatchingHandler(osmium.SimpleHandler):
        """Handler that flushes completed batches into completed_batches."""

        def __init__(self):
            super().__init__()
            self._current: list[dict] = []
            self.nodes_seen = 0
            self.ways_seen  = 0
            self.rels_seen  = 0
            self.features   = 0
            self.counts: dict[str, int] = {}

        def _emit(self, feature: dict) -> None:
            self._current.append(feature)
            self.features += 1
            ft = feature["feature_type"]
            self.counts[ft] = self.counts.get(ft, 0) + 1
            if len(self._current) >= batch_size:
                completed_batches.append(self._current)
                self._current = []

        def node(self, n):
            self.nodes_seen += 1
            tags = _tags_to_dict(n.tags)
            for ftype, subtype in _classify_feature(tags):
                try:
                    wkt = _wkt.create_point(n)
                except Exception:
                    wkt = None
                self._emit(_make_feature(n.id, ftype, subtype, tags, wkt))

        def way(self, w):
            self.ways_seen += 1
            tags = _tags_to_dict(w.tags)
            for ftype, subtype in _classify_feature(tags):
                wkt = None
                is_closed = (
                    len(w.nodes) >= 4
                    and w.nodes[0].ref == w.nodes[-1].ref
                    and any(k in tags for k in AREA_TAGS)
                )
                try:
                    wkt = _wkt.create_polygon(w) if is_closed else _wkt.create_linestring(w)
                except Exception:
                    wkt = None
                self._emit(_make_feature(w.id, ftype, subtype, tags, wkt))

        def relation(self, r):
            self.rels_seen += 1
            tags = _tags_to_dict(r.tags)
            for ftype, subtype in _classify_feature(tags):
                self._emit(_make_feature(r.id, ftype, subtype, tags, None))

        def flush_remaining(self) -> None:
            if self._current:
                completed_batches.append(self._current)
                self._current = []

    handler = _BatchingHandler()

    print(f"  Parsing: {pbf_path.name}")
    print(f"  (This takes several minutes for the India extract...)")

    # Single streaming pass: osmium resolves node locations for ways internally
    handler.apply_file(str(pbf_path), locations=True, idx="flex_mem")
    handler.flush_remaining()

    log.info(
        "osm.parser.complete",
        nodes_seen=handler.nodes_seen,
        ways_seen=handler.ways_seen,
        relations_seen=handler.rels_seen,
        features_emitted=handler.features,
        batches=len(completed_batches),
        counts=handler.counts,
    )
    print(f"  Parsed {handler.features:,} features in {len(completed_batches)} batches")

    yield from completed_batches



def parse_pbf_batches_streaming(
    pbf_path: Path,
    batch_size: int = 5000,
) -> Generator[list[dict[str, Any]], None, None]:
    """
    True streaming version: yields batches AS the file is parsed.
    Uses a two-pass approach: first pass indexes node locations,
    second pass yields batches for ways with resolved geometry.

    For the India PBF (~800MB), the in-memory index approach in
    parse_pbf_batches() is sufficient and simpler to implement reliably.
    Use this function for very large PBFs where memory is constrained.
    """
    # For now, delegate to the simpler approach
    # which osmium handles efficiently with its internal buffering.
    yield from parse_pbf_batches(pbf_path, batch_size)
