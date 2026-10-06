#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check that the installed distribution — not the checkout — is what runs.

Why this exists
---------------
A smoke test that imports `numerisect` while the current directory is the source
checkout imports the checkout: `python -c` puts the working directory first on
`sys.path`, so every assertion about "the wheel" passes whether or not the wheel
contains anything. That is how a packaging check can be green and prove nothing.

This script is run by the *installed* interpreter and asserts the import came out of
that environment's site-packages before it checks anything else. It lives in
`scripts/`, so its own directory holds no `numerisect/` package to shadow the
installed one. Then it checks the resources a wheel has to carry — the GP programs,
the C sources, the browser assets, the pinned engine manifest — and finally runs the
installed console script against a real engine, because a wheel that imports but
cannot compute is not an installation.

Usage
-----
    /path/to/venv/bin/python scripts/check_installed_distribution.py

Exits non-zero with the reason on the first failure.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def check_import_came_from_the_installation() -> Path:
    """Locate the imported package and refuse a checkout or editable install."""

    import numerisect

    location = Path(numerisect.__file__).resolve().parent
    if CHECKOUT in location.parents:
        fail(f"imported the checkout at {location}, not an installed distribution")
    site = {
        Path(path).resolve()
        for key in ("purelib", "platlib")
        if (path := sysconfig.get_paths().get(key))
    }
    if not any(root == location.parent for root in site):
        fail(f"imported {location}, which is not in this environment's site-packages")
    print(f"ok: imported {location}")
    return location


def check_packaged_resources() -> None:
    """Assert the data files a working installation needs are present."""

    from numerisect.config import NATIVE_DIR, STATIC_DIR
    from numerisect.installer import load_engine_manifest
    from numerisect.rsa_challenge import ENTRIES

    for asset in ("index.html", "app.js", "styles.css"):
        if not (STATIC_DIR / asset).is_file():
            fail(f"the browser asset {asset} is missing from the installation")
    sources = sorted(path.name for path in NATIVE_DIR.glob("numerisect_*.c"))
    kernels = sorted(path.name for path in NATIVE_DIR.glob("numerisect_*.cu"))
    if len(sources) < 8 or len(kernels) < 2:
        fail(f"expected the C and CUDA sources; found {sources} and {kernels}")
    programs = sorted(path.name for path in STATIC_DIR.parent.glob("*.gp"))
    if len(programs) < 11:
        fail(f"expected at least 11 GP programs; found {len(programs)}")
    engines = load_engine_manifest()
    if len(engines) != 9:
        fail(f"the engine manifest shipped {len(engines)} entries, expected 9")
    if len(ENTRIES) != 54:
        fail(f"the RSA challenge table shipped {len(ENTRIES)} entries, expected 54")
    print(f"ok: {len(programs)} GP programs, {len(sources)} C sources, {len(engines)} engines")


def check_the_console_script_computes() -> None:
    """Factor a number through the installed entry point and a real engine."""

    executable = Path(sys.executable).parent / "numerisect"
    if not executable.is_file():
        fail(f"the console script is missing at {executable}")
    if shutil.which("gp") is None:
        fail("PARI/GP is not installed, so this check cannot tell a working "
             "installation from a broken one; install it rather than skipping")
    for arguments, expected in (
        (["routes", "--filter", "/api/"], "/api/session"),
        (["--json", "factor", "8051", "--engine", "pari_trial", "--trial-bound", "200"], '"97"'),
        (["--json", "prime", "32416190071"], '"is_prime": true'),
    ):
        finished = subprocess.run(
            [str(executable), *arguments], capture_output=True, text=True, timeout=600,
            cwd=str(executable.parent),
        )
        if finished.returncode != 0:
            fail(f"`numerisect {' '.join(arguments)}` exited {finished.returncode}:"
                 f"\n{finished.stderr.strip()}")
        if expected not in finished.stdout:
            fail(f"`numerisect {' '.join(arguments)}` did not report {expected}:"
                 f"\n{finished.stdout.strip()[:400]}")
        print(f"ok: `numerisect {' '.join(arguments)}` reported {expected}")


def main() -> int:
    check_import_came_from_the_installation()
    check_packaged_resources()
    check_the_console_script_computes()
    print("The installed distribution imports, carries its resources, and computes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
