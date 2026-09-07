from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
BASE_DIR = PACKAGE_DIR.parent
STATIC_DIR = PACKAGE_DIR / "static"
NATIVE_DIR = PACKAGE_DIR / "native"
SOURCE_CHECKOUT = (BASE_DIR / "pyproject.toml").is_file()
USER_DATA_ROOT = Path(
    os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
) / "numerisect"
DEFAULT_STATE_DIR = BASE_DIR / "data" if SOURCE_CHECKOUT else USER_DATA_ROOT / "state"
DEFAULT_OUTPUT_DIR = BASE_DIR / "output" if SOURCE_CHECKOUT else USER_DATA_ROOT / "output"
STATE_DIR = Path(os.environ.get("NUMERISECT_STATE_DIR", DEFAULT_STATE_DIR))
JOBS_DIR = STATE_DIR / "jobs"
DATABASE_PATH = STATE_DIR / "numerisect.sqlite3"
OUTPUT_DIR = Path(os.environ.get("NUMERISECT_OUTPUT_DIR", DEFAULT_OUTPUT_DIR))
TOOLS_DIR = STATE_DIR / "tools"
TOOLS_BIN_DIR = TOOLS_DIR / "bin"
TOOLS_SOURCE_DIR = TOOLS_DIR / "src"

DEFAULT_CADO_THRESHOLD = int(os.environ.get("NUMERISECT_CADO_THRESHOLD", "95"))
DEFAULT_PRETEST_LEVEL = int(os.environ.get("NUMERISECT_PRETEST_LEVEL", "20"))
MAX_EXPRESSION_CHARACTERS = int(
    os.environ.get("NUMERISECT_MAX_EXPRESSION_CHARACTERS", "100000")
)
MAX_RESULT_DIGITS = int(os.environ.get("NUMERISECT_MAX_RESULT_DIGITS", "100000"))
MAX_PARALLEL_JOBS = int(os.environ.get("NUMERISECT_MAX_PARALLEL_JOBS", "1"))


def ensure_state_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOLS_BIN_DIR.mkdir(parents=True, exist_ok=True)
    TOOLS_SOURCE_DIR.mkdir(parents=True, exist_ok=True)


def prepend_managed_tools_to_path() -> None:
    current = os.environ.get("PATH", "")
    entries = current.split(os.pathsep) if current else []
    managed = str(TOOLS_BIN_DIR)
    if managed not in entries:
        os.environ["PATH"] = os.pathsep.join([managed, *entries])
    current_lib = os.environ.get("LD_LIBRARY_PATH", "")
    lib_entries = current_lib.split(os.pathsep) if current_lib else []
    managed_libs = [
        str(TOOLS_DIR / "prefix" / "lib"),
        str(TOOLS_DIR / "prefix" / "lib64"),
    ]
    os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(
        [path for path in managed_libs if path not in lib_entries] + lib_entries
    )


# --- Application-infrastructure knobs (workspace tranche) -------------------------------
ADAPTERS_DIR = STATE_DIR / "adapters"
CATALOGUES_DIR = STATE_DIR / "catalogues"
ALLOW_NETWORK = os.environ.get("NUMERISECT_ALLOW_NETWORK", "0") == "1"
NETWORK_TIMEOUT_SECONDS = int(os.environ.get("NUMERISECT_NETWORK_TIMEOUT", "15"))
OEIS_SEARCH_URL = os.environ.get("NUMERISECT_OEIS_URL", "https://oeis.org/search")
CATALOGUE_LOOKUP_URL = os.environ.get("NUMERISECT_CATALOGUE_URL", "")
RESULT_CACHE_ENABLED = os.environ.get("NUMERISECT_RESULT_CACHE", "1") == "1"
RESULT_CACHE_MAX_ROWS = int(os.environ.get("NUMERISECT_RESULT_CACHE_MAX_ROWS", "2000"))
RESULT_CACHE_MAX_BYTES = int(os.environ.get("NUMERISECT_RESULT_CACHE_MAX_BYTES", "2000000"))
MAX_BATCH_IMPORT_ITEMS = int(os.environ.get("NUMERISECT_MAX_BATCH_IMPORT_ITEMS", "500"))
MAX_BATCH_RANGE_SPAN = int(os.environ.get("NUMERISECT_MAX_BATCH_RANGE_SPAN", "10000"))


# Directory holding the GGNFS lattice sievers (gnfs-lasieve4I*e). YAFU needs it for
# NFS work and for `tune`. Empty means "not configured"; nothing is auto-discovered
# outside the managed tools directory.
GGNFS_DIR = os.environ.get("NUMERISECT_GGNFS_DIR", "")
