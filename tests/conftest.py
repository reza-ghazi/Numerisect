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
