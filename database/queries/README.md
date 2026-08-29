# HEATWATCH — Query Library

Ready-to-run SQL queries for common HEATWATCH operations.

## Files

| File | Contents |
|---|---|
| `spatial_queries.sql` | Bounding-box, radius, KNN, buffer, intersection queries |
| `hotspot_queries.sql` | Recent detections, satellite breakdown, duplicates, unassigned |
| `thermal_object_queries.sql` | Persistence, recent activity, observation history, statistics |
| `alert_queries.sql` | Priority queue, recent alerts, anomaly breakdown, resolution time |
| `human_feedback_queries.sql` | Review queue, confirmed events, AI vs human disagreement, training data |
| `rag_similarity_queries.sql` | Vector similarity, metadata filter, document listing, insertion examples |

## Usage

```bash
# Run any query file directly
psql $DATABASE_URL -f queries/spatial_queries.sql

# Or copy individual queries into your preferred SQL client
```

## Notes on Vector Queries

The `rag_similarity_queries.sql` file uses a placeholder 5-dimension vector
`[0.01,0.02,0.03,0.04,0.05]` for readability.

In your application, replace this with real embeddings:
- Default dimension: **1536** (OpenAI text-embedding-3-small)
- Use `vector_cosine_ops` (cosine distance, `<=>` operator)
