#!/usr/bin/env bash
# =============================================================
# HEATWATCH — Database Backup Script
# database/scripts/backup_database.sh
# =============================================================
# Creates a compressed pg_dump backup.
#
# Usage:
#   bash scripts/backup_database.sh [output_directory]
#
# Default output directory: ./backups/
# =============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_DIR="${SCRIPT_DIR}/.."

if [[ -f "${DB_DIR}/.env" ]]; then
  set -a; source "${DB_DIR}/.env"; set +a
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL not set."
  exit 1
fi

BACKUP_DIR="${1:-${DB_DIR}/backups}"
mkdir -p "${BACKUP_DIR}"

TIMESTAMP=$(date -u +"%Y%m%d_%H%M%SZ")
BACKUP_FILE="${BACKUP_DIR}/heatwatch_${TIMESTAMP}.pgdump"

echo "Starting backup …"
echo "  Destination: ${BACKUP_FILE}"

pg_dump \
  --format=custom \
  --compress=9 \
  --no-password \
  --verbose \
  "${DATABASE_URL}" \
  --file "${BACKUP_FILE}"

SIZE=$(du -sh "${BACKUP_FILE}" | cut -f1)
echo ""
echo "✔  Backup complete."
echo "   File:   ${BACKUP_FILE}"
echo "   Size:   ${SIZE}"
echo "   Format: PostgreSQL custom format (pg_dump -Fc)"
echo ""
echo "To restore:"
echo "   bash scripts/restore_database.sh ${BACKUP_FILE}"
