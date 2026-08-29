#!/usr/bin/env bash
# =============================================================
# HEATWATCH — Database Migration Script
# database/scripts/migrate.sh
# =============================================================
# Runs all SQL migration files in order.
# Stops immediately on any SQL failure.
#
# Usage:
#   cd database
#   cp .env.example .env         # fill in credentials
#   source .env
#   bash scripts/migrate.sh
#
# OR supply DATABASE_URL directly:
#   DATABASE_URL=postgresql://user:pass@localhost:5432/heatwatch \
#     bash scripts/migrate.sh
# =============================================================

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────
MIGRATIONS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/migrations"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL is not set."
  echo "Export it or create a .env file:"
  echo "  export DATABASE_URL=postgresql://user:pass@host:5432/dbname"
  exit 1
fi

# ── Migration files in order ──────────────────────────────────
MIGRATION_FILES=(
  "000_enable_extensions.sql"
  "001_create_enums.sql"
  "002_create_core_tables.sql"
  "003_create_context_tables.sql"
  "004_create_ai_result_tables.sql"
  "005_create_feedback_tables.sql"
  "006_create_rag_tables.sql"
  "007_create_model_registry.sql"
  "008_create_indexes.sql"
  "009_create_views.sql"
)

echo "=============================================="
echo "  HEATWATCH Database Migration"
echo "  Target: ${DATABASE_URL//:*@/:**@}"
echo "=============================================="

PASS=0
FAIL=0

for filename in "${MIGRATION_FILES[@]}"; do
  filepath="${MIGRATIONS_DIR}/${filename}"

  if [[ ! -f "${filepath}" ]]; then
    echo "ERROR: Migration file not found: ${filepath}"
    exit 1
  fi

  echo ""
  echo "Running: ${filename} …"

  if psql "${DATABASE_URL}" \
       --set ON_ERROR_STOP=1 \
       --file "${filepath}" \
       --quiet 2>&1; then
    echo "  ✔  ${filename} — SUCCESS"
    PASS=$((PASS + 1))
  else
    echo "  ✘  ${filename} — FAILED"
    FAIL=$((FAIL + 1))
    echo ""
    echo "Migration failed. Stopping immediately."
    echo "Fix the error in ${filename} and re-run."
    exit 1
  fi
done

echo ""
echo "=============================================="
echo "  Migration complete: ${PASS} succeeded, ${FAIL} failed"
echo "=============================================="

# Run database functions after migrations
FUNCTIONS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/functions"
echo ""
echo "Installing database functions …"
for fn_file in "${FUNCTIONS_DIR}"/*.sql; do
  echo "  Loading: $(basename "${fn_file}") …"
  psql "${DATABASE_URL}" --set ON_ERROR_STOP=1 --file "${fn_file}" --quiet
  echo "  ✔  $(basename "${fn_file}")"
done

echo ""
echo "✔  All migrations and functions installed successfully."
