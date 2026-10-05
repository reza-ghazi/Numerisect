#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a local known-factor catalogue by factoring Cunningham-style numbers here.

Why this generates rather than ships data
-----------------------------------------
The local catalogue feature has always worked and has always been empty: nothing is
bundled, so a lookup searches zero files. The obvious fix is to ship the Cunningham
tables, and that is exactly what this project refuses to do — vendoring third-party data
whose licence and provenance would have to be argued, when the engines on this machine
can produce the same factorizations and say where each one came from.

So this script computes the catalogue. Every factorization is performed by PARI/GP, which
also decides primality and verifies that the factors multiply back to the number; nothing
is multiplied, divided or tested in Python. The result records the expression, the engine
and its version, so a reader can tell a locally computed entry from an imported one.

A catalogue built this way is small by construction: it holds what the installed engines
can factor inside the given budget, which is the honest limit of what this machine knows.

Usage
-----
    python scripts/build_factor_catalogue.py                 # 2,3,5,6,7,10 up to n=48
    python scripts/build_factor_catalogue.py --bases 2 --max-exponent 128 --seconds 20
    python scripts/build_factor_catalogue.py --output /tmp/cunningham.json --quiet

The file lands in the state directory's `catalogues/` folder by default, where
`GET /api/catalogues` and `POST /api/catalogues/factors` read it with no network access.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from numerisect.catalogues import CATALOGUES_DIR  # noqa: E402
from numerisect.primes import PrimeEngineError, _run_gp  # noqa: E402

#: Bases the Cunningham project tabulates. Any base is accepted on the command line.
DEFAULT_BASES = (2, 3, 5, 6, 7, 10)
SCHEMA = "org.numerisect.factor-catalogue.v1"


def gp_version() -> str:
    """Ask PARI/GP to identify itself, so each entry records what produced it."""

    lines = _run_gp(
        'my(v = version()); print("V:PARI/GP ", v[1], ".", v[2], ".", v[3]);'
        'print("DONE:1");',
        timeout=60,
    )
    for line in lines:
        if line.startswith("V:"):
            return line[2:].strip()
    raise PrimeEngineError("PARI/GP did not report its version")


def factor_entry(base: int, exponent: int, sign: int, seconds: int) -> dict[str, object] | None:
    """Factor ``base**exponent + sign`` in PARI/GP under a wall-clock budget.

    PARI performs the factorization, proves each factor prime, and checks the product
    against the input. Python only reads the tagged lines.

    Returns:
        The catalogue entry, or ``None`` when the budget expired, which is a limit of
        this run and never a statement about the number.
    """

    expression = f"{base}^{exponent}{'+' if sign > 0 else '-'}1"
    program = (
        f"alarm({seconds}, my(n = {expression}, f = factor(n), parts = List(), ok = 1);"
        'for(i = 1, #f~, for(j = 1, f[i,2], listput(parts, f[i,1])));'
        'for(i = 1, #parts, if(!isprime(parts[i]), ok = 0));'
        'if(prod(i = 1, #parts, parts[i]) != n, ok = 0);'
        'print("N:", n); print("F:", Vec(parts)); print("OK:", ok));'
        'print("DONE:1");'
    )
    try:
        lines = _run_gp(program, timeout=seconds + 30)
    except PrimeEngineError:
        return None
    values: dict[str, str] = {}
    for line in lines:
        for tag in ("N", "F", "OK"):
            if line.startswith(f"{tag}:"):
                values[tag] = line[len(tag) + 1:].strip()
    if {"N", "F", "OK"} - set(values) or values["OK"] != "1":
        return None
    factors = [part.strip() for part in values["F"].strip("[]").split(",") if part.strip()]
    if not factors:
        return None
    return {
        "number": values["N"],
        "factors": factors,
        "note": f"{expression}; factored and verified by",
    }


def build(
    bases: list[int], min_exponent: int, max_exponent: int, seconds: int,
    signs: list[int], quiet: bool,
) -> dict[str, object]:
    """Factor every b^n ± 1 in range, skipping what the budget cannot finish."""

    version = gp_version()
    entries: list[dict[str, object]] = []
    skipped: list[str] = []
    began = time.monotonic()
    for base in bases:
        for exponent in range(min_exponent, max_exponent + 1):
            for sign in signs:
                expression = f"{base}^{exponent}{'+' if sign > 0 else '-'}1"
                entry = factor_entry(base, exponent, sign, seconds)
                if entry is None:
                    skipped.append(expression)
                    if not quiet:
                        print(f"  skipped {expression} (budget)", file=sys.stderr)
                    continue
                entry["note"] = f"{entry['note']} {version}"
                entries.append(entry)
                if not quiet:
                    print(f"  {expression}: {len(entry['factors'])} prime factor(s)")
    return {
        "schema": SCHEMA,
        "engine": version,
        "bases": bases,
        "min_exponent": min_exponent,
        "max_exponent": max_exponent,
        "seconds_per_number": seconds,
        "entries": entries,
        "skipped": skipped,
        "elapsed_seconds": round(time.monotonic() - began, 3),
        "note": (
            "Computed locally by PARI/GP, not imported from any published table. Each "
            "factorization was verified against its input and every factor proven prime "
            "by the engine. Numbers the budget could not finish are listed in 'skipped' "
            "and are absent rather than partial."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bases", type=int, nargs="+", default=list(DEFAULT_BASES))
    parser.add_argument("--min-exponent", type=int, default=2,
                        help="lowest exponent, for extending a catalogue in slices")
    parser.add_argument("--max-exponent", type=int, default=48)
    parser.add_argument("--seconds", type=int, default=10,
                        help="per-number PARI/GP budget (default 10)")
    parser.add_argument("--plus-only", action="store_true", help="only b^n + 1")
    parser.add_argument("--minus-only", action="store_true", help="only b^n - 1")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--quiet", action="store_true")
    arguments = parser.parse_args()
    if arguments.plus_only and arguments.minus_only:
        parser.error("choose at most one of --plus-only and --minus-only")
    if any(base < 2 for base in arguments.bases) or arguments.max_exponent < 2:
        parser.error("bases must be at least 2 and the exponent bound at least 2")
    if arguments.min_exponent < 2 or arguments.min_exponent > arguments.max_exponent:
        parser.error("the exponent range must satisfy 2 <= min <= max")
    signs = [1] if arguments.plus_only else [-1] if arguments.minus_only else [-1, 1]

    catalogue = build(
        arguments.bases, arguments.min_exponent, arguments.max_exponent,
        arguments.seconds, signs, arguments.quiet,
    )
    destination = arguments.output or (CATALOGUES_DIR / "cunningham.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    entries = len(catalogue["entries"])
    skipped = len(catalogue["skipped"])
    print(
        f"Wrote {entries} entr{'y' if entries == 1 else 'ies'} to {destination}"
        + (f"; {skipped} number(s) exceeded the budget" if skipped else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
