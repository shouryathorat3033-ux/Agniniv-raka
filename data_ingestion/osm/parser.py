"""
HEATWATCH - OSM PBF Parser  (streaming rewrite)
=================================================
ROOT CAUSE OF PREVIOUS HANG:
  apply_file(locations=True) was run synchronously, blocking until the ENTIRE
  1.7 GB PBF was read + the full node-location index (~1.3 GB RAM) was built.
  ALL extracted batches were also accumulated in a list before any batch could
  be yielded.  For India this caused 2.3 GB RAM usage and OS page-swapping,
  making the process appear frozen for hours.

THIS VERSION:
  * Uses a Queue + background thread so batches are yielded to the DB
    insertion loop AS they are extracted -- not after the whole file is parsed.
  * Queue maxsize limits RAM to batch_size x ~300 bytes x maxsize (< 100 MB).
  * A progress thread prints live stats every 30 s so the console is not silent.
  * Adds a fast sample_parse() (NO location index) for quick end-to-end tests.

GEOMETRY STRATEGY:
  Nodes  -> Point    (direct lat/lon from osmium, no index needed)
  Ways   -> LineString or Polygon  (resolved via locations=True index)
  Relations -> NULL  (multipolygon assembly needs a third-party library)

All coordinates are WGS84 (EPSG:4326).
"""
from __future__ import annotations

import json
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any, Generator

import osmium
import osmium.geom

from common.logging_config import get_logger

log = get_logger(__name__)

_wkt = osmium.geom.WKTFactory()

# ---------------------------------------------------------------------------
# Tag classification helpers
# ---------------------------------------------------------------------------

ROAD_CLASSES = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "residential", "service", "unclassified", "living_street",
    "pedestrian", "cycleway", "footway", "path",
    "motorway_link", "trunk_link", "primary_link",
    "secondary_link", "tertiary_link",
}

AREA_TAGS = {
    "leisure", "landuse", "natural", "building", "amenity",
    "waterway", "healthcare", "public_transport", "area",
}


def _tags_to_dict(tags) -> dict[str, str]:
    return {t.k: t.v for t in tags}


def _classify_feature(tags: dict[str, str]) -> list[tuple[str, str]]:
    """Return [(feature_type, subtype), ...] for a tag dict.  Empty = not wanted."""
    results: list[tuple[str, str]] = []

    hw = tags.get("highway", "")
    if hw in ROAD_CLASSES:
        results.append(("road", hw))

    amenity   = tags.get("amenity", "")
    healthcare = tags.get("healthcare", "")
    if amenity in ("hospital", "clinic") or healthcare in ("hospital", "clinic"):
        results.append(("hospital", amenity or healthcare))
    if amenity == "fire_station":
        results.append(("fire_station", "fire_station"))
    if amenity in ("school", "college", "university"):
        results.append(("school", amenity))
    if amenity == "bus_station":
        results.append(("transport", "bus_station"))

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
    return {
        "osm_id":       osm_id,
        "feature_type": feature_type,
        "name":         tags.get("name") or tags.get("name:en"),
        "subtype":      subtype,
        "tags":         json.dumps(tags),
        "geometry_wkt": wkt_geometry,
        "source":       "OpenStreetMap",
    }


# ---------------------------------------------------------------------------
# Streaming handler - puts batches in a Queue as they are filled
# ---------------------------------------------------------------------------

_SENTINEL = object()   # signals end of stream


class _QueueHandler(osmium.SimpleHandler):
    """
    Osmium handler that fills a Queue with completed batches.

    The handler runs inside a background thread (see parse_pbf_streaming).
    Batches are placed in the queue as they are filled -- the main thread
    can start inserting into the database immediately after the first batch.

    Statistics are safe to READ from the main thread at any time (simple
    integer increments; Python GIL provides sufficient atomicity here).
    """

    def __init__(self, batch_size: int, batch_queue: "queue.Queue[Any]",
                 max_features: int | None = None):
        super().__init__()
        self.batch_size   = batch_size
        self._queue       = batch_queue
        self.max_features = max_features
        self._current: list[dict] = []
        self._stop        = False    # set when max_features reached

        # stats (readable from progress thread without a lock -- GIL-safe)
        self.nodes_seen  = 0
        self.ways_seen   = 0
        self.rels_seen   = 0
        self.features    = 0
        self.geom_ok     = 0
        self.geom_null   = 0
        self.counts: dict[str, int] = {}

    # ------------------------------------------------------------------
    def _emit(self, feature: dict) -> None:
        if self._stop:
            return
        self._current.append(feature)
        self.features += 1
        ft = feature["feature_type"]
        self.counts[ft] = self.counts.get(ft, 0) + 1
        if feature["geometry_wkt"] is not None:
            self.geom_ok += 1
        else:
            self.geom_null += 1

        if len(self._current) >= self.batch_size:
            self._queue.put(list(self._current))   # copy -- handler clears below
            self._current = []

        if self.max_features and self.features >= self.max_features:
            self._stop = True
            # Flush whatever is in _current so it is not lost
            if self._current:
                self._queue.put(list(self._current))
                self._current = []
            raise StopIteration   # signals osmium to stop apply_file early

    # ------------------------------------------------------------------
    def node(self, n):
        self.nodes_seen += 1
        if self._stop:
            return
        tags = _tags_to_dict(n.tags)
        for ftype, subtype in _classify_feature(tags):
            wkt = None
            try:
                wkt = _wkt.create_point(n)
            except Exception:
                pass
            self._emit(_make_feature(n.id, ftype, subtype, tags, wkt))

    def way(self, w):
        self.ways_seen += 1
        if self._stop:
            return
        tags = _tags_to_dict(w.tags)
        classifications = _classify_feature(tags)
        if not classifications:
            return
        is_closed = (
            len(w.nodes) >= 4
            and w.nodes[0].ref == w.nodes[-1].ref
            and any(k in tags for k in AREA_TAGS)
        )
        for ftype, subtype in classifications:
            wkt = None
            try:
                wkt = _wkt.create_polygon(w) if is_closed else _wkt.create_linestring(w)
            except Exception:
                pass
            self._emit(_make_feature(w.id, ftype, subtype, tags, wkt))

    def relation(self, r):
        self.rels_seen += 1
        if self._stop:
            return
        tags = _tags_to_dict(r.tags)
        for ftype, subtype in _classify_feature(tags):
            # Relations: store tags/metadata only; no geometry (needs separate pass)
            self._emit(_make_feature(r.id, ftype, subtype, tags, None))

    def flush_remaining(self) -> None:
        if self._current:
            self._queue.put(list(self._current))
            self._current = []


# ---------------------------------------------------------------------------
# Public API: true streaming generator
# ---------------------------------------------------------------------------

def parse_pbf_streaming(
    pbf_path: Path,
    batch_size: int = 5000,
    with_way_geometry: bool = True,
    max_features: int | None = None,
) -> Generator[list[dict[str, Any]], None, None]:
    """
    Parse a PBF file and yield feature-dict batches AS they are extracted.

    Architecture
    ------------
    * A background thread runs osmium.apply_file().
    * The handler puts completed batches into a queue.
    * The main thread yields batches from the queue and can immediately
      insert them into the database -- no waiting for the full parse.
    * Queue maxsize=30 provides backpressure; the parser thread blocks if
      the DB thread is slower, preventing RAM from filling up.

    Parameters
    ----------
    pbf_path          : path to the .osm.pbf file
    batch_size        : features per batch (default 5000)
    with_way_geometry : if True, use locations=True to resolve way node coords
                        (slower, uses ~1.3 GB RAM for India).
                        if False, ways get NULL geometry but parsing is fast.
    max_features      : stop after this many features (useful for quick tests)

    Yields
    ------
    list[dict]  -- one batch of normalized feature dicts
    """
    log.info("osm.parser.streaming.start",
             path=str(pbf_path), batch_size=batch_size,
             with_way_geometry=with_way_geometry, max_features=max_features)

    pbf_str  = str(pbf_path)
    size_mb  = pbf_path.stat().st_size / 1_000_000
    # Queue: max 30 batches buffered (30 x 5000 x ~400B = ~60 MB max)
    batch_q: queue.Queue = queue.Queue(maxsize=30)
    handler  = _QueueHandler(batch_size, batch_q, max_features=max_features)
    error_holder: list[Exception] = []

    # Progress thread: prints live stats every 30 s
    _stop_progress = threading.Event()

    def _progress_loop():
        t0 = time.monotonic()
        while not _stop_progress.wait(30):
            elapsed = time.monotonic() - t0
            n, w, r = handler.nodes_seen, handler.ways_seen, handler.rels_seen
            f, g  = handler.features, handler.geom_ok
            print(
                f"  [PARSING] {elapsed:5.0f}s | "
                f"nodes={n:>10,}  ways={w:>8,}  rels={r:>6,} | "
                f"features_extracted={f:>8,}  geom_ok={g:>8,}"
            )
            sys.stdout.flush()

    progress_thread = threading.Thread(target=_progress_loop, daemon=True)

    # Parse thread
    def _parse():
        try:
            if with_way_geometry:
                handler.apply_file(pbf_str, locations=True, idx="flex_mem")
            else:
                handler.apply_file(pbf_str)
        except StopIteration:
            pass   # raised by handler when max_features is hit -- normal exit
        except Exception as exc:
            error_holder.append(exc)
        finally:
            handler.flush_remaining()
            batch_q.put(_SENTINEL)

    parse_thread = threading.Thread(target=_parse, daemon=True, name="osm-parser")

    # -----------------------------------------------------------------------
    print(f"  PBF   : {pbf_path.name}  ({size_mb:.0f} MB)")
    if with_way_geometry:
        print("  Index : flex_mem (node location index for way geometry)")
        print("  Note  : building location index -- first batch may take a few minutes")
    else:
        print("  Index : none  (node points only, way geometry = NULL)")
    if max_features:
        print(f"  Limit : stop after {max_features:,} features (sample mode)")
    sys.stdout.flush()

    progress_thread.start()
    parse_thread.start()

    t_start = time.monotonic()
    batch_count = 0
    try:
        while True:
            try:
                item = batch_q.get(timeout=600)   # 10 min timeout per batch
            except queue.Empty:
                raise RuntimeError(
                    "Parser produced no batch for 10 minutes. "
                    "The PBF may be corrupt or the system is severely memory-constrained."
                )
            if item is _SENTINEL:
                break
            batch_count += 1
            yield item
    finally:
        _stop_progress.set()
        parse_thread.join(timeout=30)

    if error_holder:
        raise RuntimeError(f"PBF parse error: {error_holder[0]}") from error_holder[0]

    elapsed = time.monotonic() - t_start
    log.info(
        "osm.parser.streaming.complete",
        elapsed_s=round(elapsed, 1),
        nodes_seen=handler.nodes_seen,
        ways_seen=handler.ways_seen,
        relations_seen=handler.rels_seen,
        features=handler.features,
        geom_ok=handler.geom_ok,
        geom_null=handler.geom_null,
        batches=batch_count,
        counts=handler.counts,
    )
    print(
        f"  Parse done in {elapsed:.0f}s | "
        f"features={handler.features:,} | "
        f"geom_ok={handler.geom_ok:,} | geom_null={handler.geom_null:,}"
    )
    print(f"  Breakdown: {dict(sorted(handler.counts.items()))}")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Legacy alias kept for any external callers
# ---------------------------------------------------------------------------

def parse_pbf_batches(
    pbf_path: Path,
    batch_size: int = 5000,
) -> Generator[list[dict[str, Any]], None, None]:
    """Streams batches with full way geometry.  Delegates to parse_pbf_streaming."""
    yield from parse_pbf_streaming(pbf_path, batch_size=batch_size, with_way_geometry=True)


# ---------------------------------------------------------------------------
# Fast sample parse (NO location index -- nodes only, instant start)
# ---------------------------------------------------------------------------

def parse_pbf_sample(
    pbf_path: Path,
    batch_size: int = 5000,
    max_features: int = 50_000,
) -> Generator[list[dict[str, Any]], None, None]:
    """
    Fast node-only parse.  No location index.  Way geometry is NULL.

    Used for quick end-to-end tests:
      - starts immediately (no multi-minute indexing delay)
      - proves DB insertion, upsert, geometry, checkpoint, manifest all work
      - stops after max_features (default 50k)

    Run with: ingest_osm.py --sample
    """
    yield from parse_pbf_streaming(
        pbf_path,
        batch_size=batch_size,
        with_way_geometry=False,
        max_features=max_features,
    )


# ---------------------------------------------------------------------------
# Dry-run: parse without inserting into DB
# ---------------------------------------------------------------------------

def parse_pbf_dry_run(
    pbf_path: Path,
    batch_size: int = 5000,
    with_way_geometry: bool = True,
    max_features: int | None = None,
) -> dict[str, Any]:
    """
    Dry-run: read + classify + geometry but NO database writes.
    Drains parse_pbf_streaming and returns summary statistics.
    """
    log.info("osm.parser.dry_run.start", path=str(pbf_path))
    total = 0
    counts: dict[str, int] = {}
    geom_ok = geom_null = 0

    for batch in parse_pbf_streaming(
        pbf_path,
        batch_size=batch_size,
        with_way_geometry=with_way_geometry,
        max_features=max_features,
    ):
        for feat in batch:
            total += 1
            ft = feat["feature_type"]
            counts[ft] = counts.get(ft, 0) + 1
            if feat["geometry_wkt"] is not None:
                geom_ok += 1
            else:
                geom_null += 1

    log.info(
        "osm.parser.dry_run.complete",
        features=total, geom_ok=geom_ok, geom_null=geom_null, counts=counts,
    )
    return {
        "features":  total,
        "geom_ok":   geom_ok,
        "geom_null": geom_null,
        "counts":    counts,
    }