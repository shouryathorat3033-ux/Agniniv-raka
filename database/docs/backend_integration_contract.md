# HEATWATCH — Backend Integration Contract

## Purpose

This document defines how a future backend application should connect to and use the HEATWATCH database.

**This document does NOT include backend code.**
It is a contract for backend developers.

---

## 1. Connection

### Environment Variable

```
DATABASE_URL=postgresql://heatwatch_user:password@localhost:5432/heatwatch
```

### Connection Requirements

- Driver must support PostgreSQL 16+
- PostGIS geometry types require GeoAlchemy2 (Python) or equivalent
- pgvector requires the `pgvector` Python package or equivalent driver extension

### Python (SQLAlchemy 2.x)
```python
from sqlalchemy import create_engine
engine = create_engine(os.environ["DATABASE_URL"])
```

### Python (psycopg 3)
```python
import psycopg
conn = psycopg.connect(os.environ["DATABASE_URL"])
```

### Node.js (pg)
```javascript
const { Pool } = require('pg')
const pool = new Pool({ connectionString: process.env.DATABASE_URL })
```

---

## 2. Available Operations

### Insert FIRMS/VIIRS hotspot observation
```sql
INSERT INTO hotspots
    (source, latitude, longitude, location, acquisition_time, frp, confidence, ...)
VALUES ($1, $2, $3, ST_SetSRID(ST_MakePoint($4, $5), 4326), $6, $7, $8, ...);
```

### Query thermal objects (map viewport)
```sql
SELECT * FROM thermal_objects
WHERE centroid && ST_MakeEnvelope($min_lon, $min_lat, $max_lon, $max_lat, 4326)
  AND status = 'ACTIVE';
```

### Find nearest industrial facility
```sql
SELECT * FROM industrial_facilities
ORDER BY location <-> ST_SetSRID(ST_MakePoint($lon, $lat), 4326)
LIMIT 1;
```

### Save source attribution result (Brain 1)
```sql
INSERT INTO source_attributions
    (thermal_object_id, predicted_category, confidence, model_version, evidence)
VALUES ($1, $2, $3, $4, $5);
```

### Save anomaly result (Brain 2)
```sql
INSERT INTO anomaly_results
    (thermal_object_id, anomaly_level, anomaly_score, model_version, ...)
VALUES ($1, $2, $3, $4, ...);
```

### Create alert
```sql
INSERT INTO alerts
    (thermal_object_id, priority, severity, status, title, description, ...)
VALUES ($1, $2, $3, 'NEW', $4, $5, ...);
```

### Save human review
```sql
INSERT INTO human_reviews
    (thermal_object_id, original_prediction, original_confidence,
     reviewer_category, reviewer_note, reviewer_confidence,
     review_status, reviewer_identifier, reviewed_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW());
```

### Retrieve training candidates (verified events)
```sql
SELECT * FROM v_training_candidates;
-- Only returns eligible_for_training=TRUE human-confirmed records
```

### Insert RAG document
```sql
INSERT INTO rag_documents (title, source, source_type, content, version)
VALUES ($1, $2, $3, $4, '1') RETURNING id;
```

### Insert RAG chunk with embedding
```sql
INSERT INTO rag_chunks (document_id, chunk_index, chunk_text, embedding, metadata)
VALUES ($1, $2, $3, $4::vector, $5);
-- $4 is the embedding as a float array string: '[0.1, 0.2, ...]'
```

### Vector similarity search (RAG retrieval)
```sql
SELECT rc.chunk_text, rd.title,
       1 - (rc.embedding <=> $1::vector) AS similarity
FROM rag_chunks rc
JOIN rag_documents rd ON rd.id = rc.document_id
ORDER BY rc.embedding <=> $1::vector
LIMIT 5;
```

---

## 3. Recommended Boundary Rules

| Concern | Location |
|---|---|
| SQL queries | Database (via ORM or direct SQL) |
| Data validation | Application layer (before insert) + DB constraints |
| Business logic | Application layer |
| ML inference | External ML pipeline (writes results to DB) |
| RAG pipeline | External LLM service (writes results to DB) |
| Frontend rendering | Frontend layer |

---

## 4. Important Constraints for Backend

- `eligible_for_training` defaults to `FALSE` — never auto-set to TRUE
- `original_prediction` in `human_reviews` must never be updated after insert
- `verified_events` must only be populated from confirmed `human_reviews`
- Model binary weights are NOT stored in PostgreSQL
- RAG embeddings belong in `rag_chunks` only, NOT on hotspot or thermal_object rows

---

## 5. Useful Views

| View | Use case |
|---|---|
| `v_active_thermal_objects` | Dashboard: active events with AI results |
| `v_alert_dashboard` | Alert priority queue for operators |
| `v_open_alerts_spatial` | Map display of open alerts with coordinates |
| `v_training_candidates` | ML training pipeline: eligible labeled examples |
| `v_human_review_queue` | Analyst queue: pending reviews sorted by priority |
