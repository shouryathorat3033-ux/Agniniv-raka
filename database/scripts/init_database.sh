#!/usr/bin/env bash
# =============================================================
# HEATWATCH — Database Initialization Script
# database/scripts/init_database.sh
# =============================================================
# Full initialization:
#   1. Start Docker database (if not running)
#   2. Wait for PostgreSQL to be ready
#   3. Run all migrations
#   4. Load demo seed data (optional)
#
# Usage:
#   bash scripts/init_database.sh [--with-seeds]
# =============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="${SCRIPT_DIR}/.."

WITH_SEEDS=false
if [[ "${1:-}" == "--with-seeds" ]]; then
  WITH_SEEDS=true
fi

# Load .env if present
if [[ -f "${DB_DIR}/.env" ]]; then
  set -a
  source "${DB_DIR}/.env"
  set +a
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL not set. Copy .env.example to .env and fill credentials."
  exit 1
fi

echo "=============================================="
echo "  HEATWATCH — Database Initialization"
echo "=============================================="

# ── Step 1: Check if Docker is available ──────────────────────
if command -v docker &>/dev/null; then
  echo ""
  echo "Docker detected. Checking database container …"

  if ! docker compose -f "${DB_DIR}/docker-compose.yml" ps --quiet db 2>/dev/null | grep -q .; then
    echo "Starting database container …"
    docker compose -f "${DB_DIR}/docker-compose.yml" up -d db
  else
    echo "Database container is already running."
  fi
else
  echo "Docker not found — assuming PostgreSQL is already running externally."
fi

# ── Step 2: Wait for PostgreSQL ───────────────────────────────
echo ""
echo "Waiting for PostgreSQL to accept connections …"
MAX_RETRIES=30
RETRY=0
until psql "${DATABASE_URL}" -c "SELECT 1;" &>/dev/null; do
  RETRY=$((RETRY + 1))
  if [[ ${RETRY} -ge ${MAX_RETRIES} ]]; then
    echo "ERROR: PostgreSQL did not become ready after ${MAX_RETRIES} seconds."
    exit 1
  fi
  echo "  Waiting … (attempt ${RETRY}/${MAX_RETRIES})"
  sleep 1
done
echo "✔  PostgreSQL is ready."

# ── Step 3: Run migrations ────────────────────────────────────
echo ""
bash "${SCRIPT_DIR}/migrate.sh"

# ── Step 4: Optional seeds ────────────────────────────────────
if [[ "${WITH_SEEDS}" == "true" ]]; then
  echo ""
  echo "Loading demo seed data …"
  psql "${DATABASE_URL}" -f "${DB_DIR}/seeds/seed_industrial_facilities.sql" --quiet
  psql "${DATABASE_URL}" -f "${DB_DIR}/seeds/seed_demo_data.sql" --quiet
  psql "${DATABASE_URL}" -f "${DB_DIR}/seeds/seed_land_context.sql" --quiet
  echo "✔  Demo seed data loaded."
fi

echo ""
echo "=============================================="
echo "  ✔  Database initialization complete."
echo "  Connect with:"
echo "     psql ${DATABASE_URL//:*@/:**@}"
echo "=============================================="
