# HEATWATCH — Entity Relationship Diagram

## Text ER Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         HEATWATCH DATABASE                              │
│                         Entity Relationships                             │
└─────────────────────────────────────────────────────────────────────────┘

RAW OBSERVATIONS
────────────────

  ┌────────────────┐
  │    hotspots    │   Raw satellite pixel detections (NASA FIRMS)
  │────────────────│   One row = one pixel detection event
  │ id (PK)        │
  │ source         │
  │ latitude       │
  │ longitude      │
  │ location       │ ← PostGIS Point(4326)
  │ acquisition_   │
  │   time         │
  │ frp            │
  │ confidence     │
  └───────┬────────┘
          │ M
          │ thermal_object_observations (bridge)
          │ M
          ▼
  ┌───────────────────────────────────────────────────────────┐
  │                    thermal_objects                        │
  │───────────────────────────────────────────────────────────│
  │ id (PK)            centroid (PostGIS Point)               │
  │ object_geometry    first_seen    last_seen                 │
  │ observation_count  duration_hours (generated)             │
  │ persistence_score  status                                 │
  └───┬───────────────────────────────────────────────────────┘
      │
      │  1:M (one thermal_object → many related records)
      │
      ├──────────────────────────────────────────────────────────────────
      │                        CONTEXT
      ├──────────────────────────────────────────────────────────────────
      │  ┌────────────────────────────────────────────────────────────┐
      │  │  osm_context      │  land_context     │ historical_profiles│
      │  │ (OSM features)    │  (land cover)     │ (baselines)        │
      │  └────────────────────────────────────────────────────────────┘
      │
      ├──────────────────────────────────────────────────────────────────
      │                      ML PIPELINE
      ├──────────────────────────────────────────────────────────────────
      │  ┌──────────────────┐    ┌───────────────────────────────────┐
      │  │  feature_vectors  │    │            model_registry          │
      │  │ (engineered ML    │    │ (model versions + artifact refs)  │
      │  │  features, JSONB) │    └───────────────────────────────────┘
      │  └──────────────────┘             ↑ referenced by version TEXT
      │
      │  ┌──────────────────────┐
      │  │  source_attributions  │  ← Brain 1 outputs
      │  │ (INDUSTRIAL_FIRE,     │
      │  │  FOREST_FIRE, etc.)   │
      │  └──────────┬───────────┘
      │             │
      │  ┌──────────▼───────────┐
      │  │   anomaly_results    │  ← Brain 2 outputs
      │  │ (NORMAL/ELEVATED/    │
      │  │  HIGH, anomaly_score) │
      │  └──────────┬───────────┘
      │             │
      │  ┌──────────▼───────────┐
      │  │  supervisor_reviews  │  ← RAG + LLM synthesis
      │  │ (ACCEPTED/FLAGGED/   │    rag_sources JSONB
      │  │  REJECTED)           │    references rag_chunks
      │  └──────────┬───────────┘
      │             │
      ├──────────────────────────────────────────────────────────────────
      │                      ALERTS
      ├──────────────────────────────────────────────────────────────────
      │  ┌──────────────────────────────────────────────────────────┐
      │  │                       alerts                             │
      │  │  priority | severity | status | title | description      │
      │  │  Lifecycle: NEW → INVESTIGATING → FLAGGED/VERIFIED/CLOSED │
      │  └──────────────────────────────────────────────────────────┘
      │             │
      ├──────────────────────────────────────────────────────────────────
      │                    HUMAN FEEDBACK
      ├──────────────────────────────────────────────────────────────────
      │  ┌──────────────────────┐
      │  │    human_reviews     │  ← Analyst decisions
      │  │ original_prediction  │    (immutable AI prediction preserved)
      │  │ reviewer_category    │
      │  │ review_status        │
      │  └──────────┬───────────┘
      │             │ 1:1 (only confirmed reviews)
      │  ┌──────────▼───────────┐
      │  │   verified_events    │  ← Curated training candidates
      │  │ eligible_for_         │    DEFAULT eligible_for_training=FALSE
      │  │   training=FALSE     │    Model predictions NEVER auto-inserted
      │  └──────────────────────┘

SPATIAL CONTEXT (joined to thermal_objects via spatial queries)
─────────────────────────────────────────────────────────────

  ┌──────────────────────┐
  │ industrial_facilities │   ST_DWithin / KNN <-> thermal_objects.centroid
  │ location (Point)     │
  │ boundary (Polygon)   │
  └──────────────────────┘

RAG KNOWLEDGE BASE (isolated from thermal observation pipeline)
──────────────────────────────────────────────────────────────

  ┌────────────────────┐      1:M     ┌─────────────────────────────┐
  │   rag_documents    │ ──────────► │        rag_chunks             │
  │ (full source text) │             │ embedding vector(1536)        │
  │ classification     │             │ HNSW index (cosine similarity) │
  │ policy docs, etc.  │             └─────────────────────────────┘
  └────────────────────┘
```

## Table Count: 17

| # | Table | Schema Group |
|---|---|---|
| 1 | hotspots | Thermal Core |
| 2 | thermal_objects | Thermal Core |
| 3 | thermal_object_observations | Thermal Core (Bridge) |
| 4 | industrial_facilities | Context |
| 5 | osm_context | Context |
| 6 | land_context | Context |
| 7 | historical_profiles | Historical/ML |
| 8 | feature_vectors | Historical/ML |
| 9 | source_attributions | AI Results |
| 10 | anomaly_results | AI Results |
| 11 | supervisor_reviews | AI Results |
| 12 | alerts | Alerts |
| 13 | human_reviews | Feedback |
| 14 | verified_events | Feedback |
| 15 | rag_documents | RAG |
| 16 | rag_chunks | RAG |
| 17 | model_registry | ML Registry |
