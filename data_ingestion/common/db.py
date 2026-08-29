"""
HEATWATCH Data Ingestion — Database Connection
==============================================
Provides a psycopg3 connection pool and transaction helper.

KEY RULES:
  • Reads DATABASE_URL from environment (never hardcoded).
  • Verifies PostGIS is installed before any pipeline runs.
  • Uses parameterized queries ONLY — no string interpolation.
  • Does NOT create or modify database schema.
  • All mutations go through explicit transactions.
"""
from __future__ import annotations

import contextlib
import os
from typing import Generator

import psycopg
import psycopg_pool

from common.exceptions import DatabaseConnectionError
from common.logging_config import get_logger

log = get_logger(__name__)

# ── Module-level pool (initialized on first call) ─────────────
_pool: psycopg_pool.ConnectionPool | None = None


def _get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise DatabaseConnectionError(
            "DATABASE_URL environment variable is not set. "
            "Copy data_ingestion/.env.example to .env and fill in credentials."
        )
    return url


def get_pool() -> psycopg_pool.ConnectionPool:
    """Return the shared connection pool, initializing it on first call."""
    global _pool
    if _pool is None:
        url = _get_database_url()
        log.info("db.pool.init", url=url.split("@")[-1])  # log host/db only, not password
        _pool = psycopg_pool.ConnectionPool(
            conninfo=url,
            min_size=1,
            max_size=int(os.getenv("DB_POOL_SIZE", "5")),
            open=True,
        )
    return _pool


def get_connection() -> psycopg.Connection:
    """
    Return a raw psycopg3 connection from the pool.
    Caller is responsible for closing / returning it.
    Prefer using the `transaction()` context manager instead.
    """
    return get_pool().getconn()


@contextlib.contextmanager
def transaction() -> Generator[psycopg.Connection, None, None]:
    """
    Context manager providing a database connection inside a transaction.

    Usage::

        with transaction() as conn:
            conn.execute("INSERT INTO hotspots ...")

    Commits on normal exit; rolls back and re-raises on exception.
    """
    pool = get_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = False
        yield conn
        conn.commit()
        log.debug("db.transaction.committed")
    except Exception as exc:
        conn.rollback()
        log.error("db.transaction.rolled_back", error=str(exc))
        raise
    finally:
        pool.putconn(conn)


def verify_postgis(conn: psycopg.Connection) -> str:
    """
    Verify PostGIS is installed and return its version string.
    Raises DatabaseConnectionError if PostGIS is not available.
    """
    try:
        row = conn.execute("SELECT postgis_full_version()").fetchone()
        if row is None:
            raise DatabaseConnectionError("postgis_full_version() returned no result")
        version: str = row[0]
        log.info("db.postgis.verified", version=version[:80])
        return version
    except psycopg.errors.UndefinedFunction as exc:
        raise DatabaseConnectionError(
            "PostGIS is not installed on this PostgreSQL server. "
            "Run migration 000_enable_extensions.sql first."
        ) from exc


def verify_tables_exist(conn: psycopg.Connection, table_names: list[str]) -> None:
    """
    Raise DatabaseConnectionError if any required table is missing.
    Does NOT create tables.
    """
    rows = conn.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = ANY(%s)
        """,
        (table_names,),
    ).fetchall()
    found = {r[0] for r in rows}
    missing = set(table_names) - found
    if missing:
        raise DatabaseConnectionError(
            f"Required tables are missing: {sorted(missing)}. "
            "Run database migrations first."
        )
    log.info("db.tables.verified", tables=table_names)


def close_pool() -> None:
    """Close the connection pool. Call during shutdown."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
        log.info("db.pool.closed")
