"""
pytest configuration for HEATWATCH data_ingestion tests.
Adds the data_ingestion/ directory to sys.path so all imports resolve.
Loads .env if present.
"""
import sys
from pathlib import Path

# ── Add data_ingestion/ to path ───────────────────────────────
ROOT = Path(__file__).parent.parent  # data_ingestion/
sys.path.insert(0, str(ROOT))

# ── Load .env if present ──────────────────────────────────────
env_file = ROOT / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file, override=False)
    except ImportError:
        pass  # dotenv not installed — env vars must be set externally
