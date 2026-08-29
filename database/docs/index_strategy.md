# HEATWATCH — Index Strategy

## Guiding Principles

1. **GiST** for all PostGIS geometry columns (spatial filtering and KNN)
2. **HNSW** for pgvector embedding column (ANN similarity search)
3. **BRIN** for append-heavy timestamp columns on large tables
4. **Partial B-Tree** for operational hot paths (open alerts, active objects, pending reviews)
5. **GIN** for JSONB columns only where JSON key queries are justified

---

## Index Inventory

### Spatial Indexes (GiST)

| Index | Table | Column | Purpose |
|---|---|---|---|
| `idx_hotspots_location` | hotspots | location | Map viewport, proximity queries |
| `idx_thermal_objects_centroid` | thermal_objects | centroid | KNN, bounding-box |
| `idx_thermal_objects_geometry` | thermal_objects | object_geometry | Polygon intersection |
| `idx_facilities_location` | industrial_facilities | location | KNN nearest-facility |
| `idx_facilities_boundary` | industrial_facilities | boundary | Polygon intersection |
| `idx_osm_context_geometry` | osm_context | geometry | Spatial context lookup |

### Vector Index (HNSW)

| Index | Table | Column | Distance | m | ef_construction |
|---|---|---|---|---|---|
| `idx_rag_chunks_embedding_hnsw` | rag_chunks | embedding | cosine | 16 | 64 |

**Why HNSW over IVFFlat:**
- No training step (works at any cardinality)
- Supports incremental inserts without rebuild
- ~10ms P99 recall at <5M vectors
- IVFFlat requires knowing dataset size upfront and periodic retraining

**Tuning:**
- `m=16`: good balance of recall vs. memory (higher m = better recall, more RAM)
- `ef_construction=64`: build quality vs. speed tradeoff
- At query time: `SET hnsw.ef_search = 100;` for higher recall if needed

### BRIN Indexes (Append-Heavy Time-Series)

| Index | Table | Column | Benefit |
|---|---|---|---|
| `idx_hotspots_acq_time_brin` | hotspots | acquisition_time | 200× cheaper than B-Tree for sequential scans on millions of rows |

### Partial B-Tree Indexes (Hot Query Paths)

| Index | Filter | Purpose |
|---|---|---|
| `idx_thermal_objects_status` | `WHERE status = 'ACTIVE'` | Dashboard: active objects only |
| `idx_anomaly_results_high` | `WHERE anomaly_level = 'HIGH'` | Operator triage queue |
| `idx_alerts_open` | `WHERE status NOT IN ('CLOSED','VERIFIED')` | Open alert dashboard |
| `idx_human_reviews_pending` | `WHERE review_status = 'PENDING'` | Analyst review queue |
| `idx_verified_events_eligible` | `WHERE eligible_for_training = TRUE` | Training pipeline |
| `idx_model_registry_active` | `WHERE is_active = TRUE` | Active model lookup |

### GIN Indexes (JSONB)

| Index | Table | Column | Justification |
|---|---|---|---|
| `idx_feature_vectors_features_gin` | feature_vectors | features | Key existence checks during schema migration validation and data quality audits |
| `idx_rag_documents_metadata_gin` | rag_documents | metadata | Topic tag filtering before vector retrieval |
| `idx_rag_chunks_metadata_gin` | rag_chunks | metadata | Chunk-level metadata filter for pre-retrieval narrowing |

GIN indexes are NOT created on every JSONB column. Only where JSON key queries occur in practice.

---

## Index Maintenance

```sql
-- Check index usage statistics
SELECT * FROM hw_index_usage;    -- custom view in maintenance_functions.sql

-- Rebuild bloated indexes
REINDEX INDEX CONCURRENTLY idx_hotspots_location;

-- Update statistics after bulk loads
ANALYZE hotspots;
ANALYZE thermal_objects;
ANALYZE rag_chunks;
```
