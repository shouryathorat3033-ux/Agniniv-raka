#!/usr/bin/env bash
# =============================================================
# HEATWATCH — Database Verification Script
# database/scripts/verify_database.sh
# =============================================================
# Verifies database health:
#   - Connection
#   - PostGIS availability
#   - pgvector availability
#   - All 17 required tables
#   - Required views
#   - Spatial query capability
#   - Vector operator capability
#
# Exit code: 0 = all checks passed, 1 = one or more failed
# =============================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="${SCRIPT_DIR}/.."

if [[ -f "${DB_DIR}/.env" ]]; then
  set -a; source "${DB_DIR}/.env"; set +a
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL not set."
  exit 1
fi

PASS=0
FAIL=0

check() {
  local label="$1"
  local sql="$2"
  local result
  result=$(psql "${DATABASE_URL}" -tAc "${sql}" 2>&1)
  if [[ "${result}" == "t" || "${result}" == "1" || "${result}" =~ ^[0-9]+$ ]]; then
    echo "  ✔  PASS — ${label}"
    PASS=$((PASS + 1))
  else
    echo "  ✘  FAIL — ${label} (got: ${result})"
    FAIL=$((FAIL + 1))
  fi
}

echo "=============================================="
echo "  HEATWATCH — Database Verification"
echo "  Target: ${DATABASE_URL//:*@/:**@}"
echo "=============================================="

# ── Connection ────────────────────────────────────────────────
echo ""
echo "[ Connection ]"
if psql "${DATABASE_URL}" -c "SELECT 1;" &>/dev/null; then
  echo "  ✔  PASS — PostgreSQL connection successful"
  PASS=$((PASS + 1))
else
  echo "  ✘  FAIL — Cannot connect to PostgreSQL"
  echo "  Check DATABASE_URL and that the server is running."
  exit 1
fi

# ── Extensions ────────────────────────────────────────────────
echo ""
echo "[ Extensions ]"
check "PostGIS available" \
  "SELECT COUNT(*)::text FROM pg_extension WHERE extname='postgis';"
check "pgvector available" \
  "SELECT COUNT(*)::text FROM pg_extension WHERE extname='vector';"
check "uuid-ossp available" \
  "SELECT COUNT(*)::text FROM pg_extension WHERE extname='uuid-ossp';"

# ── Tables ────────────────────────────────────────────────────
echo ""
echo "[ Tables (17 required) ]"
REQUIRED_TABLES=(
  hotspots thermal_objects thermal_object_observations
  industrial_facilities osm_context land_context
  historical_profiles feature_vectors
  source_attributions anomaly_results supervisor_reviews
  alerts human_reviews verified_events
  rag_documents rag_chunks model_registry
)

for tbl in "${REQUIRED_TABLES[@]}"; do
  check "Table: ${tbl}" \
    "SELECT COUNT(*)::text FROM information_schema.tables
     WHERE table_schema='public' AND table_name='${tbl}';"
done

# ── Views ─────────────────────────────────────────────────────
echo ""
echo "[ Views ]"
REQUIRED_VIEWS=(
  v_active_thermal_objects v_alert_dashboard v_training_candidates
  v_open_alerts_spatial v_human_review_queue
)
for vw in "${REQUIRED_VIEWS[@]}"; do
  check "View: ${vw}" \
    "SELECT COUNT(*)::text FROM information_schema.views
     WHERE table_schema='public' AND table_name='${vw}';"
done

# ── Key indexes ───────────────────────────────────────────────
echo ""
echo "[ Key Indexes ]"
check "GiST index: hotspots.location" \
  "SELECT COUNT(*)::text FROM pg_indexes
   WHERE indexname='idx_hotspots_location';"
check "GiST index: thermal_objects.centroid" \
  "SELECT COUNT(*)::text FROM pg_indexes
   WHERE indexname='idx_thermal_objects_centroid';"
check "HNSW index: rag_chunks.embedding" \
  "SELECT COUNT(*)::text FROM pg_indexes
   WHERE indexname='idx_rag_chunks_embedding_hnsw';"

# ── Spatial query ─────────────────────────────────────────────
echo ""
echo "[ Spatial Query Capability ]"
check "ST_MakePoint executes" \
  "SELECT ST_X(ST_SetSRID(ST_MakePoint(77.0, 28.0), 4326))::text = '77';"
check "ST_Distance executes" \
  "SELECT (ST_Distance(
     ST_SetSRID(ST_MakePoint(0,0),4326)::geography,
     ST_SetSRID(ST_MakePoint(1,0),4326)::geography
   ) > 0)::text;"

# ── Vector capability ─────────────────────────────────────────
echo ""
echo "[ Vector Operator Capability ]"
check "Cosine distance operator <=>" \
  "SELECT (('[1.0,0.0,0.0]'::vector(3) <=> '[0.0,1.0,0.0]'::vector(3)) > 0.9)::text;"

# ── Summary ───────────────────────────────────────────────────
echo ""
echo "=============================================="
echo "  Verification complete: ${PASS} PASS, ${FAIL} FAIL"
echo "=============================================="

if [[ ${FAIL} -gt 0 ]]; then
  echo "  ✘  ${FAIL} check(s) failed. Review output above."
  exit 1
else
  echo "  ✔  All checks passed. Database is healthy."
  exit 0
fi
