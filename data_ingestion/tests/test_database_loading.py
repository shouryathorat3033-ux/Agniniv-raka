"""
Database loading tests.
These are INTEGRATION tests requiring a running PostgreSQL database.
Mark: pytest -m integration

All tests are isolated — they clean up after themselves.
"""
import pytest
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

pytestmark = pytest.mark.integration


@pytest.fixture
def db_conn():
    """Provide a live DB connection. Skip if DATABASE_URL not set."""
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        pytest.skip("DATABASE_URL not set — skipping integration test")
    import psycopg
    conn = psycopg.connect(db_url)
    yield conn
    conn.close()


def test_postgis_available(db_conn):
    result = db_conn.execute("SELECT postgis_lib_version()").fetchone()
    assert result is not None
    assert len(result[0]) > 0


def test_hotspots_table_exists(db_conn):
    result = db_conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='hotspots'"
    ).fetchone()
    assert result[0] == 1


def test_insert_and_rollback_hotspot(db_conn):
    """Insert a synthetic hotspot row and rollback — no permanent data."""
    db_conn.autocommit = False
    try:
        db_conn.execute("""
            INSERT INTO hotspots (
                source, latitude, longitude, location, acquisition_time,
                satellite, confidence
            ) VALUES (
                'OTHER', 21.2034, 72.8765,
                ST_SetSRID(ST_MakePoint(72.8765, 21.2034), 4326),
                NOW(), 'TEST_UNIT', 'nominal'
            )
        """)
        count = db_conn.execute(
            "SELECT COUNT(*) FROM hotspots WHERE satellite='TEST_UNIT'"
        ).fetchone()[0]
        assert count >= 1
    finally:
        db_conn.rollback()  # Always rollback — no persistent test data


def test_industrial_facilities_table_exists(db_conn):
    result = db_conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='industrial_facilities'"
    ).fetchone()
    assert result[0] == 1


def test_geometry_make_point(db_conn):
    row = db_conn.execute(
        "SELECT ST_AsText(ST_SetSRID(ST_MakePoint(72.8765, 21.2034), 4326))"
    ).fetchone()
    assert "POINT" in row[0]
    assert "72.8765" in row[0]
