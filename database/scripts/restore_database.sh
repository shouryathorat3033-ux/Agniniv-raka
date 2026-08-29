#!/usr/bin/env bash
# =============================================================
# HEATWATCH — Database Restore Script
# database/scripts/restore_database.sh
# =============================================================
# Restores from a pg_dump custom-format backup.
#
# Usage:
#   bash scripts/restore_database.sh <backup_file>
#
# WARNING: This will drop and recreate the target database.
#          Use ONLY on development/staging environments.
# =============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="${SCRIPT_DIR}/.."

if [[ -f "${DB_DIR}/.env" ]]; then
  set -a; source "${DB_DIR}/.env"; set +a
fi

BACKUP_FILE="${1:-}"
if [[ -z "${BACKUP_FILE}" || ! -f "${BACKUP_FILE}" ]]; then
  echo "ERROR: Provide a valid backup file path."
  echo "Usage: bash scripts/restore_database.sh <backup_file.pgdump>"
  exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL not set."
  exit 1
fi

echo "=============================================="
echo "  HEATWATCH — Database Restore"
echo "  Backup:  ${BACKUP_FILE}"
echo "  Target:  ${DATABASE_URL//:*@/:**@}"
echo "=============================================="
echo ""
echo "⚠  WARNING: This will RESTORE the database from backup."
echo "   All current data will be replaced."
echo ""
read -rp "Type 'yes' to confirm: " confirm

if [[ "${confirm}" != "yes" ]]; then
  echo "Restore cancelled."
  exit 0
fi

echo ""
echo "Restoring from backup …"

pg_restore \
  --format=custom \
  --verbose \
  --no-password \
  --clean \
  --if-exists \
  --dbname "${DATABASE_URL}" \
  "${BACKUP_FILE}"

echo ""
echo "✔  Restore complete."
echo "   Run verify_database.sh to confirm database health."
