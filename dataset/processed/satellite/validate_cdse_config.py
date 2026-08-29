"""
HeatWatch -- Copernicus Data Space Credential Validation
=========================================================
Project  : Urban/Industrial Heat & Thermal Anomaly Detection
Purpose  : Validate that Copernicus Data Space credentials stored in
           database/.env can be loaded successfully.

Rules
-----
* Read-only -- this script never modifies any file or dataset.
* Credential VALUES are never printed.
* No Copernicus API calls are made.
* No Sentinel-2 data is accessed or downloaded.
* Uses python-dotenv to load database/.env.

Exit codes
----------
  0 = all required credentials are PRESENT
  1 = one or more credentials are MISSING, or .env cannot be loaded
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# python-dotenv is the only non-stdlib dependency
# ---------------------------------------------------------------------------
try:
    from dotenv import dotenv_values
except ImportError:
    print("[ERROR] python-dotenv is not installed.")
    print("        Install it with:  pip install python-dotenv")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# Resolve relative to the project root (two levels up from this script):
#   dataset/processed/satellite/validate_cdse_config.py
#   -> dataset/processed/satellite/
#   -> dataset/processed/
#   -> dataset/
#   -> <project-root>/          (C:\SIH_Hackthon)
# ---------------------------------------------------------------------------
SCRIPT_DIR   = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
ENV_FILE     = PROJECT_ROOT / "database" / ".env"

# ---------------------------------------------------------------------------
# Copernicus credential variable names expected in database/.env
# (Names only -- values are never printed)
# ---------------------------------------------------------------------------
REQUIRED_CDSE_VARS = [
    "COPERNICUS_CLIENT_ID",
    "COPERNICUS_CLIENT_SECRET",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def banner(title):
    print("=" * 60)
    print(title)
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    banner("HeatWatch -- CDSE Credential Validation")

    # ------------------------------------------------------------------
    # 1. Check .env file exists
    # ------------------------------------------------------------------
    print("\n[Step 1] Locating .env file ...")
    print("         Project root : {}".format(PROJECT_ROOT))
    print("         .env path    : {}".format(ENV_FILE))

    if not ENV_FILE.exists():
        print("\n[ERROR] .env file not found: {}".format(ENV_FILE))
        print("        Please create database/.env with the Copernicus credentials.")
        print("\n[FAIL] Cannot proceed -- .env is missing.")
        sys.exit(1)

    print("         Status       : FOUND")

    # ------------------------------------------------------------------
    # 2. Load the .env file (values are not echoed)
    # ------------------------------------------------------------------
    print("\n[Step 2] Loading .env with python-dotenv ...")
    try:
        config = dotenv_values(ENV_FILE)
    except Exception as exc:
        print("\n[ERROR] Failed to parse .env: {}".format(exc))
        print("[FAIL] .env could not be loaded.")
        sys.exit(1)

    n_total = len(config)
    print("         Total variables loaded : {}".format(n_total))
    print("         (Values are not displayed for security)")

    # ------------------------------------------------------------------
    # 3. Check each required Copernicus credential
    # ------------------------------------------------------------------
    print("\n[Step 3] Checking required Copernicus credentials ...\n")
    print("  {:<35s}  {}".format("Variable", "Status"))
    print("  " + "-" * 50)

    all_present = True
    missing_vars = []

    for var in REQUIRED_CDSE_VARS:
        # A variable is PRESENT if it exists in the file AND is non-empty
        value = config.get(var, "")
        if value and value.strip():
            status = "PRESENT"
        else:
            status = "MISSING"
            all_present = False
            missing_vars.append(var)
        print("  {:<35s}  {}".format(var, status))

    # ------------------------------------------------------------------
    # 4. Final result
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("FINAL RESULT")
    print("=" * 60)

    if all_present:
        print("[PASS] All required Copernicus credentials are PRESENT.")
        print("       The .env is correctly configured for CDSE access.")
        sys.exit(0)
    else:
        print("[FAIL] The following credentials are MISSING or EMPTY:")
        for var in missing_vars:
            print("       - {}".format(var))
        print()
        print("       Add the missing variables to: {}".format(ENV_FILE))
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
