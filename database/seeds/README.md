# HEATWATCH — Seed Data

Demo/development seed data for the HEATWATCH database.

## ⚠ Important Warning

All seed files contain **FICTIONAL DEMO DATA** only.
- NOT real satellite observations
- NOT real industrial facilities
- NOT real incident data

**Never load seed data into a production database.**
Seeds are guarded with `current_database()` checks that abort if the DB is named `heatwatch_prod`.

## Files

| File | Contents |
|---|---|
| `seed_industrial_facilities.sql` | 8 fictional illustrative industrial sites |
| `seed_demo_data.sql` | 3 hotspots, 2 thermal objects, AI results, 2 alerts, 1 RAG doc |
| `seed_land_context.sql` | Land cover context for demo thermal objects |

## Execution Order

```bash
# 1. Industrial facilities (no dependencies)
psql $DATABASE_URL -f seeds/seed_industrial_facilities.sql

# 2. Full demo data (hotspots, thermal objects, alerts)
psql $DATABASE_URL -f seeds/seed_demo_data.sql

# 3. Land context (requires thermal objects from step 2)
psql $DATABASE_URL -f seeds/seed_land_context.sql
```

## Resetting Demo Data

Re-running any seed file deletes and re-inserts demo rows.
All demo rows are tagged with `source = 'DEMO_SEED'` or `model_version = 'DEMO_v1'`
for easy identification and cleanup.
