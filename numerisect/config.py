from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
NATIVE_DIR = BASE_DIR / "native"
STATE_DIR = Path(os.environ.get("NUMERISECT_STATE_DIR", BASE_DIR / "data"))
JOBS_DIR = STATE_DIR / "jobs"
DATABASE_PATH = STATE_DIR / "numerisect.sqlite3"
OUTPUT_DIR = Path(os.environ.get("NUMERISECT_OUTPUT_DIR", BASE_DIR / "output"))
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
