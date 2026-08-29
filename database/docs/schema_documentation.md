# HEATWATCH — Schema Documentation

## Table Reference

---

### 1. `hotspots`
**Purpose:** Raw and FIRMS-normalized thermal pixel detection events.  
**One row = one satellite pixel detection event.**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Auto-generated |
| `source` | TEXT | NOT NULL, CHECK | Satellite source name |
| `external_detection_id` | TEXT | nullable | Provider-native pixel ID |
| `latitude` | DOUBLE PRECISION | NOT NULL, CHECK(-90..90) | WGS84 latitude |
| `longitude` | DOUBLE PRECISION | NOT NULL, CHECK(-180..180) | WGS84 longitude |
| `location` | GEOMETRY(Point,4326) | NOT NULL | PostGIS point |
| `acquisition_time` | TIMESTAMPTZ | NOT NULL | UTC acquisition time |
| `frp` | NUMERIC | nullable | Fire Radiative Power (MW) |
| `confidence` | TEXT | nullable | 'low'/'nominal'/'high' |
| `raw_payload` | JSONB | nullable | Original ingested record |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Ingestion time |

**Indexes:** GiST on `location`, BRIN on `acquisition_time`, composite on `(source, acquisition_time)`  
**Unique:** `(source, external_detection_id)` and `(source, latitude, longitude, acquisition_time)`

---

### 2. `thermal_objects`
**Purpose:** Spatiotemporal clusters of hotspot observations.  
**One row = one tracked heat source.**

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Auto-generated |
| `centroid` | GEOMETRY(Point,4326) | NOT NULL | Cluster centroid |
| `object_geometry` | GEOMETRY | nullable | Convex hull/polygon |
| `first_seen` | TIMESTAMPTZ | NOT NULL | Earliest observation |
| `last_seen` | TIMESTAMPTZ | NOT NULL | Latest observation |
| `duration_hours` | NUMERIC | GENERATED STORED | Computed from timestamps |
| `observation_count` | INTEGER | NOT NULL, >=0 | Hotspot count |
| `persistence_score` | NUMERIC | CHECK(0..1) | Persistence metric |
| `status` | thermal_object_status | NOT NULL | ACTIVE/COOLING/etc. |

**Indexes:** GiST on `centroid` and `object_geometry`, partial on `status='ACTIVE'`

---

### 3. `thermal_object_observations`
**Purpose:** Bridge table linking hotspots to thermal objects.

| Column | Constraints |
|---|---|
| `thermal_object_id` | FK → thermal_objects, CASCADE |
| `hotspot_id` | FK → hotspots, CASCADE |
| `assigned_at` | TIMESTAMPTZ DEFAULT NOW() |
| Composite PK | `(thermal_object_id, hotspot_id)` |

---

### 4. `industrial_facilities`
**Purpose:** Known industrial sites for spatial proximity matching.

| Column | Type | Description |
|---|---|---|
| `facility_type` | facility_type ENUM | REFINERY/POWER_PLANT/etc. |
| `location` | GEOMETRY(Point,4326) | Site centroid |
| `boundary` | GEOMETRY(Geometry,4326) | Optional polygon footprint |
| `confidence` | NUMERIC(5,4) | Data quality 0–1 |
| `metadata` | JSONB | Country, capacity, permits, etc. |

---

### 5. `osm_context`
**Purpose:** Cached OpenStreetMap features near thermal objects.  
Populated by external enrichment service — not by this database module.

---

### 6. `land_context`
**Purpose:** Land-cover classification fractional scores per thermal object.  
Score columns: `built_up_score`, `cropland_score`, `tree_cover_score`, etc. (all CHECK 0–1).

---

### 7. `historical_profiles`
**Purpose:** Baseline behaviour statistics used by anomaly detection.  
Versioned via `profile_version`. Supports multiple baselines per object.

---

### 8. `feature_vectors`
**Purpose:** Engineered ML features stored as JSONB.  
`feature_schema_version` tracks which feature set is stored.  
GIN index on `features` for key existence queries.

---

### 9. `source_attributions`
**Purpose:** Brain 1 classification outputs.  
`original_prediction` is immutable after insert.  
`conflicting_evidence` stored separately for transparency.

---

### 10. `anomaly_results`
**Purpose:** Brain 2 anomaly detection outputs.  
Boolean flags per anomaly component (frp_anomaly, spatial_anomaly, etc.).

---

### 11. `supervisor_reviews`
**Purpose:** RAG-grounded LLM supervisor assessments.  
Does NOT overwrite deterministic AI results.  
`rag_sources` JSONB preserves retrieval audit trail.

---

### 12. `alerts`
**Purpose:** Actionable incidents for operator triage.  
Lifecycle: `NEW → INVESTIGATING → FLAGGED/VERIFIED/CLOSED`.  
Partial index covers only open alerts.

---

### 13. `human_reviews`
**Purpose:** Human analyst decisions on thermal objects.  
`original_prediction` is immutable — both AI and human decisions preserved.  
`eligible_for_training` defaults to FALSE.

---

### 14. `verified_events`
**Purpose:** Curated training dataset candidates.  
Populated ONLY from confirmed human reviews.  
`eligible_for_training = FALSE` by default — requires explicit approval.

**Data Governance Rule:**  
> Model predictions are NEVER automatically inserted into `verified_events`.  
> Only human-confirmed, explicitly approved records qualify.

---

### 15. `rag_documents`
**Purpose:** Full-text knowledge base documents.  
Includes classification policies, evidence policies, scientific papers, model docs.  
Content stored for re-chunking without re-fetch.

---

### 16. `rag_chunks`
**Purpose:** Chunked text with pgvector embeddings.  
`embedding vector(1536)` — change dimension in migration 006 if needed.  
HNSW index for ANN retrieval.  
Completely isolated from thermal observation tables.

---

### 17. `model_registry`
**Purpose:** ML model version tracking.  
`artifact_location` stores URI only — no binary weights in PostgreSQL.  
`is_active = TRUE` marks the deployed version per model type.
