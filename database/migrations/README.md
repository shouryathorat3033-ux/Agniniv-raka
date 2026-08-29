# HEATWATCH — Database Migrations

## Overview

Migrations are numbered SQL files executed in order.
Each file is idempotent where possible.

## Migration Inventory

| File | Tables / Objects Created |
|---|---|
| `000_enable_extensions.sql` | PostGIS, pgvector, uuid-ossp, btree_gist |
| `001_create_enums.sql` | All PostgreSQL ENUM types |
| `002_create_core_tables.sql` | hotspots, thermal_objects, thermal_object_observations |
| `003_create_context_tables.sql` | industrial_facilities, osm_context, land_context, historical_profiles, feature_vectors |
| `004_create_ai_result_tables.sql` | source_attributions, anomaly_results, supervisor_reviews, alerts |
| `005_create_feedback_tables.sql` | human_reviews, verified_events |
| `006_create_rag_tables.sql` | rag_documents, rag_chunks |
| `007_create_model_registry.sql` | model_registry |
| `008_create_indexes.sql` | All spatial, vector, and B-Tree indexes |
| `009_create_views.sql` | v_active_thermal_objects, v_alert_dashboard, v_training_candidates, v_open_alerts_spatial, v_human_review_queue |

## Running Migrations

### Using the migrate script (Linux/Mac)
```bash
cd database
cp .env.example .env        # fill in real credentials
bash scripts/migrate.sh
```

### Manual psql execution (any OS including Windows)
```powershell
# Set variables
$env:PGPASSWORD = "your_password"

# Run each migration in order
@(
  "000_enable_extensions.sql",
  "001_create_enums.sql",
  "002_create_core_tables.sql",
  "003_create_context_tables.sql",
  "004_create_ai_result_tables.sql",
  "005_create_feedback_tables.sql",
  "006_create_rag_tables.sql",
  "007_create_model_registry.sql",
  "008_create_indexes.sql",
  "009_create_views.sql"
) | ForEach-Object {
    Write-Host "Running $_..."
    psql -h localhost -p 5432 -U heatwatch_user -d heatwatch -f "migrations/$_"
    if ($LASTEXITCODE -ne 0) { throw "Migration $_ failed!" }
}
```

## Notes

- Run `000_enable_extensions.sql` as a PostgreSQL superuser.
- All other migrations can run as `heatwatch_user` (if granted CREATE privileges).
- Migrations are NOT automatically tracked. Run them once on a fresh database.
- For production, use a proper migration manager (Flyway, Liquibase, or Alembic).
