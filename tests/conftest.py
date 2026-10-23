"""Shared fixtures and optional-engine guards.

PARI/GP and FLINT are required to run the suite. The heavier or less commonly
packaged engines are optional: a machine without them should report the affected
tests as skipped rather than failed, which is what CONTRIBUTING.md promises.

Use it as::

    def test_something(require_engine):
        require_engine("primecount")
"""

from __future__ import annotations

import shutil
import time
from typing import Any

import pytest

# Engines the suite can exercise when present. PARI/GP is deliberately absent:
# it is a hard requirement, and its absence should fail loudly, not skip.
OPTIONAL_ENGINES = {
    "primecount": "exact prime counting and indexed primes",
    "primesieve": "high-performance interval sieving",
    "ecm": "GMP-ECM campaigns",
    "yafu": "YAFU factoring strategies",
    "msieve": "Msieve factoring and cross-verification",
    "cado-nfs.py": "CADO-NFS number field sieve",
}


def engine_available(name: str) -> bool:
    """Whether an engine executable is on PATH."""

    return shutil.which(name) is not None


@pytest.fixture()
def require_engine():
    """Skip the calling test when an optional engine is not installed."""

    def _require(*names: str) -> None:
        missing = [name for name in names if not engine_available(name)]
        if missing:
            described = ", ".join(
                f"{name} ({OPTIONAL_ENGINES.get(name, 'optional engine')})"
                for name in missing
            )
            pytest.skip(f"Optional engine not installed: {described}")

    return _require


def requires(*names: str):
    """Decorator form for module-level use on tests that need an optional engine."""

    missing = [name for name in names if not engine_available(name)]
    reason = "Optional engine not installed: " + ", ".join(missing) if missing else ""
    return pytest.mark.skipif(bool(missing), reason=reason)


#: Statuses a job no longer moves out of.
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def wait_for_job(manager: Any, job_id: str, timeout: float = 60) -> dict[str, Any]:
    """Wait for one factorization job to finish, and return its stored row.

    `JobManager` drops a job's future in the `finally` of its worker, *after* writing
    the terminal row, so `manager._futures[job_id]` is a race: a job that finishes
    before the test looks it up raises `KeyError`. Every job test used that expression
    directly, and it flaked in CI on a stubbed run that completed immediately.

    Waiting on the future when it is still there keeps the exact behaviour tests
    relied on, including propagating a worker exception. A missing future means the
    row is already terminal, because the status is written before the future is
    dropped; the short poll covers the gap between those two statements.

    Args:
        manager: The `JobManager` under test.
        job_id: The job to wait for.
        timeout: Seconds to wait before failing.

    Returns:
        The job row, with its terminal status.

    Raises:
        AssertionError: If the job has not reached a terminal status in time.
    """

    future = manager._futures.get(job_id)
    if future is not None:
        future.result(timeout=timeout)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = manager.database.get_job(job_id)
        if row and row["status"] in TERMINAL_STATUSES:
            return row
        time.sleep(0.02)
    row = manager.database.get_job(job_id)
    raise AssertionError(
        f"job {job_id} did not finish within {timeout}s; "
        f"status was {row['status'] if row else 'missing'}"
    )
