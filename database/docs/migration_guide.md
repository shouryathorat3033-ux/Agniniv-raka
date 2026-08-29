# HEATWATCH — Migration Guide

## Prerequisites

- PostgreSQL 16+ server (or Docker)
- `psql` client installed
- PostGIS 3.x installed on the server
- pgvector 0.7+ installed on the server

The Docker image `pgvector/pgvector:pg16` bundles all three.

---

## Step 1 — Start the Database

### Using Docker (recommended)

```bash
cd database
cp .env.example .env      # fill in credentials
docker compose --env-file .env up -d
docker compose ps         # wait for "healthy"
```

### Using an existing PostgreSQL server

Ensure PostGIS and pgvector are installed, then set `DATABASE_URL` and proceed.

---

## Step 2 — Configure Environment

```bash
cd database
cp .env.example .env
# Edit .env with your credentials
```

Key variables:

| Variable | Description |
|---|---|
| `DATABASE_URL` | Full connection string |
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Password (never commit) |
| `PGVECTOR_EMBEDDING_DIMENSION` | Embedding dimension (default: 1536) |

---

## Step 3 — Run Migrations

### Linux / macOS / WSL

```bash
cd database
source .env
bash scripts/migrate.sh
```

### Windows PowerShell

```powershell
cd database
$env:PGPASSWORD = "your_password"
$DB = "postgresql://heatwatch_user:your_password@localhost:5432/heatwatch"

$migrations = @(
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
)

foreach ($file in $migrations) {
    Write-Host "Running $file ..."
    psql $DB -f "migrations/$file" -v ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) { throw "Migration failed: $file" }
    Write-Host "  ✔ $file"
}

# Load functions
psql $DB -f "functions/spatial_functions.sql"
psql $DB -f "functions/maintenance_functions.sql"
```

---

## Step 4 — Verify

```bash
bash scripts/verify_database.sh
```

---

## Step 5 — Load Demo Data (optional)

```bash
psql $DATABASE_URL -f seeds/seed_industrial_facilities.sql
psql $DATABASE_URL -f seeds/seed_demo_data.sql
psql $DATABASE_URL -f seeds/seed_land_context.sql
```

---

## Step 6 — Run Tests

```bash
psql $DATABASE_URL -f tests/test_schema.sql
psql $DATABASE_URL -f tests/test_constraints.sql
psql $DATABASE_URL -f tests/test_spatial_queries.sql
psql $DATABASE_URL -f tests/test_vector_queries.sql
```

---

## Notes on Embedding Dimension

The default embedding dimension is **1536** (OpenAI text-embedding-3-small).

If you use a different model:
1. Edit `migrations/006_create_rag_tables.sql` — change `vector(1536)` to your dimension
2. Re-run migration 006 on a fresh database
3. Re-embed all existing RAG documents

**Changing dimension after data insertion requires:**
```sql
ALTER TABLE rag_chunks DROP COLUMN embedding;
ALTER TABLE rag_chunks ADD COLUMN embedding vector(YOUR_DIM) NOT NULL;
DROP INDEX idx_rag_chunks_embedding_hnsw;
-- Re-run migration 008 indexes section
```
