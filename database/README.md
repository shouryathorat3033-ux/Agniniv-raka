# HEATWATCH — Database Module

**Satellite Thermal Intelligence & Industrial Fire Monitoring System**

This is the self-contained, framework-independent database module for HEATWATCH.
It defines the PostgreSQL schema, migrations, spatial functions, query library,
seed data, tests, and documentation.

---

## What This Module Provides

- **17 production-ready database tables** with constraints, indexes, and FK integrity
- **PostGIS** for geospatial geometry, spatial indexing, and proximity queries
- **pgvector** for RAG knowledge base embeddings and similarity search
- **10 SQL migrations** in numbered order
- **5 database views** for common operational query patterns
- **Spatial functions** for nearest-facility, bounding-box, and radius queries
- **Demo seed data** for development and testing
- **SQL test suite** for schema, constraints, spatial queries, and vector operations
- **Backup/restore scripts** using `pg_dump`
- **Docker Compose** setup for local development
- **Documentation** covering architecture, ER diagram, index strategy, migration guide

---

## Required Software

| Requirement | Version | Notes |
|---|---|---|
| PostgreSQL | 16+ | via Docker or native |
| PostGIS | 3.x | Bundled in Docker image |
| pgvector | 0.7+ | Bundled in Docker image |
| Docker + Docker Compose | Any recent | For local development |
| psql | Any | PostgreSQL client CLI |

---

## Quick Start (Docker)

### 1. Configure environment

```bash
cd database
cp .env.example .env
# Edit .env with your credentials
```

### 2. Start the database container

```bash
docker compose --env-file .env up -d
docker compose ps   # wait for status "healthy"
```

### 3. Run all migrations

```bash
source .env
bash scripts/migrate.sh
```

### 4. Verify database health

```bash
bash scripts/verify_database.sh
```

### 5. Load demo data (optional, development only)

```bash
psql $DATABASE_URL -f seeds/seed_industrial_facilities.sql
psql $DATABASE_URL -f seeds/seed_demo_data.sql
psql $DATABASE_URL -f seeds/seed_land_context.sql
```

---

## Windows PowerShell (no Docker)

```powershell
$env:PGPASSWORD = "your_password"
$DB = "postgresql://heatwatch_user:your_password@localhost:5432/heatwatch"

$migrations = @(
  "000_enable_extensions.sql", "001_create_enums.sql",
  "002_create_core_tables.sql", "003_create_context_tables.sql",
  "004_create_ai_result_tables.sql", "005_create_feedback_tables.sql",
  "006_create_rag_tables.sql", "007_create_model_registry.sql",
  "008_create_indexes.sql", "009_create_views.sql"
)

foreach ($f in $migrations) {
    Write-Host "Running $f ..."
    psql $DB -f "migrations/$f" -v ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) { throw "Failed: $f" }
}

psql $DB -f "functions/spatial_functions.sql"
psql $DB -f "functions/maintenance_functions.sql"
```

---

## Running Tests

```bash
psql $DATABASE_URL -f tests/test_schema.sql
psql $DATABASE_URL -f tests/test_constraints.sql
psql $DATABASE_URL -f tests/test_spatial_queries.sql
psql $DATABASE_URL -f tests/test_vector_queries.sql
```

---

## Backup and Restore

```bash
# Backup
bash scripts/backup_database.sh

# Restore (development/staging only)
bash scripts/restore_database.sh backups/heatwatch_TIMESTAMP.pgdump
```

---

## How a Backend Connects

Set `DATABASE_URL` and use any PostgreSQL-compatible client.
See [`docs/backend_integration_contract.md`](docs/backend_integration_contract.md) for:
- SQL operation examples
- Boundary rules
- Important constraints
- Useful views

---

## Folder Structure

```
database/
├── .env.example                 ← Environment configuration template
├── docker-compose.yml           ← PostgreSQL + PostGIS + pgvector container
├── init.sql                     ← Bootstrap entry point + platform instructions
├── README.md                    ← This file
│
├── config/
│   ├── database.env.example     ← Config directory env template
│   └── README.md
│
├── migrations/                  ← SQL migrations (run in numeric order)
│   ├── 000_enable_extensions.sql
│   ├── 001_create_enums.sql
│   ├── 002_create_core_tables.sql
│   ├── 003_create_context_tables.sql
│   ├── 004_create_ai_result_tables.sql
│   ├── 005_create_feedback_tables.sql
│   ├── 006_create_rag_tables.sql
│   ├── 007_create_model_registry.sql
│   ├── 008_create_indexes.sql
│   ├── 009_create_views.sql
│   └── README.md
│
├── functions/                   ← Reusable PostgreSQL functions
│   ├── spatial_functions.sql
│   ├── maintenance_functions.sql
│   └── README.md
│
├── seeds/                       ← Demo/development seed data (NOT production)
│   ├── seed_industrial_facilities.sql
│   ├── seed_demo_data.sql
│   ├── seed_land_context.sql
│   └── README.md
│
├── queries/                     ← Runnable example query library
│   ├── spatial_queries.sql
│   ├── hotspot_queries.sql
│   ├── thermal_object_queries.sql
│   ├── alert_queries.sql
│   ├── human_feedback_queries.sql
│   ├── rag_similarity_queries.sql
│   └── README.md
│
├── scripts/                     ← Shell scripts for operations
│   ├── init_database.sh         ← Full init (Docker + migrations + seeds)
│   ├── migrate.sh               ← Run migrations only
│   ├── verify_database.sh       ← Health check
│   ├── backup_database.sh       ← pg_dump backup
│   └── restore_database.sh      ← pg_restore
│
├── tests/                       ← SQL test suite
│   ├── test_schema.sql
│   ├── test_constraints.sql
│   ├── test_spatial_queries.sql
│   ├── test_vector_queries.sql
│   └── README.md
│
└── docs/                        ← Documentation
    ├── architecture.md
    ├── er_diagram.md
    ├── schema_documentation.md
    ├── index_strategy.md
    ├── migration_guide.md
    ├── backup_strategy.md
    └── backend_integration_contract.md
```

---

## 17 Database Tables

| # | Table | Purpose |
|---|---|---|
| 1 | `hotspots` | Raw satellite thermal pixel detections |
| 2 | `thermal_objects` | Spatiotemporal heat source clusters |
| 3 | `thermal_object_observations` | Hotspot ↔ thermal object bridge |
| 4 | `industrial_facilities` | Known industrial sites (spatial) |
| 5 | `osm_context` | Cached OpenStreetMap context |
| 6 | `land_context` | Land-cover classification scores |
| 7 | `historical_profiles` | Behavioural baselines |
| 8 | `feature_vectors` | Engineered ML features (JSONB) |
| 9 | `source_attributions` | Brain 1 classification results |
| 10 | `anomaly_results` | Brain 2 anomaly detection results |
| 11 | `supervisor_reviews` | RAG/LLM supervisor assessments |
| 12 | `alerts` | Operator actionable incidents |
| 13 | `human_reviews` | Analyst validation decisions |
| 14 | `verified_events` | Curated training dataset candidates |
| 15 | `rag_documents` | Knowledge base full documents |
| 16 | `rag_chunks` | Chunked text with pgvector embeddings |
| 17 | `model_registry` | ML model version tracking |
