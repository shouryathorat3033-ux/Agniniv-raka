# HEATWATCH — Database Tests

SQL-based tests verifying schema correctness, constraints, spatial queries, and vector operations.

## Files

| File | What It Tests |
|---|---|
| `test_schema.sql` | All 17 tables and 5 views exist; critical columns present |
| `test_constraints.sql` | Invalid coordinates, confidence ranges, FK violations, duplicates |
| `test_spatial_queries.sql` | PostGIS bounding-box, KNN, ST_DWithin, ST_Distance, custom functions |
| `test_vector_queries.sql` | pgvector extension, embedding column, HNSW index, cosine operator |

## Running Tests

```bash
# Run all tests in order
psql $DATABASE_URL -f tests/test_schema.sql
psql $DATABASE_URL -f tests/test_constraints.sql
psql $DATABASE_URL -f tests/test_spatial_queries.sql
psql $DATABASE_URL -f tests/test_vector_queries.sql
```

## Notes

- `test_schema.sql` — read-only; safe on any environment
- `test_constraints.sql` — inserts and rolls back test data; safe but generates NOTICE messages
- `test_spatial_queries.sql` — requires demo seed data
- `test_vector_queries.sql` — requires pgvector extension; uses temp tables for small-dim tests
