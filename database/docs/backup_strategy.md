# HEATWATCH — Backup Strategy

## Overview

| Environment | Strategy | Frequency | Retention |
|---|---|---|---|
| Development | Manual pg_dump | On demand | 7 days |
| Staging | Automated pg_dump | Daily | 30 days |
| Production | WAL archiving + pg_dump | Continuous + Daily | 1 year minimum |

---

## Development Backup

```bash
bash database/scripts/backup_database.sh          # default: ./backups/
bash database/scripts/backup_database.sh /mnt/backups/
```

Output: `heatwatch_YYYYMMDD_HHMMSSz.pgdump` (PostgreSQL custom format, compressed)

---

## Restore

```bash
bash database/scripts/restore_database.sh backups/heatwatch_20250615_120000Z.pgdump
```

⚠ Restoring will replace all current data. Confirm the prompt.

---

## Production Recommendations

### WAL Archiving (RPO < 5 minutes)

```
postgresql.conf:
  archive_mode = on
  archive_command = 'pgbackrest --stanza=heatwatch archive-push %p'
  wal_level = replica
```

Use **pgBackRest** or **Barman** for WAL management.

### Daily Base Backup

```bash
pg_dump --format=custom --compress=9 --file=heatwatch_$(date +%Y%m%d).pgdump $DATABASE_URL
```

### PostGIS Compatibility

Always restore to a PostgreSQL server with the **same or newer** PostGIS version.
PostGIS stores geometry binary format — version mismatches can corrupt spatial data.

Verify PostGIS version matches before restore:
```sql
SELECT postgis_full_version();
```

### pgvector Compatibility

pgvector embeddings are stored as binary vectors.
Restore requires the **same or newer** pgvector version.
Verify after restore:
```sql
SELECT * FROM pg_extension WHERE extname = 'vector';
```

---

## Retention Policy

| Data | Hot Tier | Archive |
|---|---|---|
| hotspots | 90 days (active queries) | 7 years (regulatory) |
| thermal_objects | Forever | — |
| alerts, reviews | Forever | — |
| verified_events | Forever | — |
| rag_chunks | Active version | Superseded chunks compressed |
| model_registry | Forever | — |

---

## What NOT to store in PostgreSQL backups

- ML model binary weights (store in object storage: S3/GCS)
- Raw satellite download files (store in object storage)
- Large imagery files

Only metadata and artifact URIs live in the database.
