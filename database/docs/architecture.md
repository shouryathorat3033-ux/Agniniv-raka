# HEATWATCH — Database Architecture

## Purpose

This document describes the database architecture for the HEATWATCH Satellite Thermal Intelligence & Industrial Fire Monitoring System.

The database is the **single source of truth** for all persistent data in HEATWATCH. It is designed to be framework-independent — any backend (FastAPI, Flask, Node.js, or a direct psql client) can connect to it.

---

## Why PostgreSQL?

| Requirement | PostgreSQL Capability |
|---|---|
| Relational integrity | Full ACID compliance, FK constraints, transactions |
| Geospatial data | PostGIS extension (geometry, geography, GiST indexes) |
| Vector search | pgvector extension (ANN similarity search) |
| Flexible schema | JSONB columns for feature vectors and evidence |
| Production grade | Battle-tested, horizontal read-scaling, logical replication |
| Open source | No licensing cost, active community |

---

## Why PostGIS?

HEATWATCH processes satellite-derived thermal detections that are fundamentally geospatial:

- **Hotspots** have latitude/longitude coordinates
- **Industrial facilities** have point and polygon geometries
- **Thermal objects** have convex hull geometries
- **Spatial queries** required: KNN nearest facility, radius search, bounding-box viewport

PostGIS enables:
- `GEOMETRY(Point, 4326)` and `GEOMETRY(Polygon, 4326)` column types
- `ST_DWithin` (radius search using geography for metre-accurate distances)
- `<->` KNN operator with GiST indexes
- `ST_Intersects`, `ST_Distance`, `ST_MakeEnvelope`

---

## Why pgvector?

The HEATWATCH supervisor pipeline uses Retrieval-Augmented Generation (RAG):

1. Knowledge documents are chunked and embedded
2. At inference time, query embeddings are compared to chunk embeddings
3. Top-k most similar chunks are retrieved for LLM context

pgvector provides:
- `vector(1536)` column type for storing embeddings
- `<=>` cosine distance operator
- HNSW index for fast Approximate Nearest Neighbour (ANN) search

---

## Database Responsibilities

✅ The database IS responsible for:
- Storing raw hotspot observations
- Storing thermal object clusters
- Storing context (facilities, OSM, land cover)
- Storing ML model results (source attribution, anomaly detection)
- Storing alerts and human reviews
- Storing RAG knowledge base documents and embeddings
- Enforcing data integrity constraints
- Supporting spatial and vector queries

❌ The database is NOT responsible for:
- Running satellite data ingestion
- Running ML inference
- Running the RAG pipeline
- Rendering the frontend
- Serving REST API endpoints

---

## Schema Architecture

Six logical groupings of tables:

```
THERMAL CORE        → hotspots, thermal_objects, thermal_object_observations
CONTEXT             → industrial_facilities, osm_context, land_context
HISTORICAL + ML     → historical_profiles, feature_vectors, model_registry
AI RESULTS          → source_attributions, anomaly_results, supervisor_reviews
ALERTS + FEEDBACK   → alerts, human_reviews, verified_events
RAG KNOWLEDGE       → rag_documents, rag_chunks
```

---

## Technology Stack

| Component | Technology | Version |
|---|---|---|
| Database | PostgreSQL | 16+ |
| Geospatial | PostGIS | 3.x |
| Vector search | pgvector | 0.7+ |
| Docker image | pgvector/pgvector | pg16 |
| UUID generation | uuid-ossp | built-in |
