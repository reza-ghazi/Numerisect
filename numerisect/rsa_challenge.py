"""The RSA Factoring Challenge: catalogue, engine verification, and cost estimates.

Numerisect could always factor an RSA number, because an RSA number is an ordinary
semiprime and the automatic pipeline routes it to CADO-NFS like any other input of its
size.  What it could not do was tell you *which* number you were holding, whether the
published factorization is genuine, or what attempting an unfactored one would cost.
This module supplies those three things and hands the factoring itself to the existing
job pipeline.

Where the mathematics happens
-----------------------------
All of it is in :mod:`numerisect/rsa_challenge.gp`.  PARI/GP proves the value composite,
recomputes its decimal and bit length, multiplies the claimed factors back together,
tests each factor for primality, and evaluates the number field sieve cost model.  This
module validates arguments, resolves a catalogue entry, renders one GP call, and parses
tagged output.  No arithmetic on a mathematical quantity happens in Python.

The catalogue is data, not authority
------------------------------------
``rsa_challenge.toml`` carries values transcribed from a published source, and a
transcribed constant is an unverified claim.  Every report re-derives the claim in
PARI/GP before stating it, exactly as catalogue factor lookups do elsewhere in
Numerisect.  A mistyped entry surfaces as a failed check, never as a fact.
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path
from typing import Any

from .primes import PrimeEngineError, _run_gp, _tagged_values

PROGRAM = Path(__file__).with_name("rsa_challenge.gp")
CATALOGUE = Path(__file__).with_name("rsa_challenge.toml")

#: The published measurement the cost model is anchored on.
ANCHOR_NAME = "RSA-250"
ANCHOR_CORE_YEARS = 2700
ANCHOR_CITATION = (
    "F. Boudot, P. Gaudry, A. Guillevic, N. Heninger, E. Thomé and P. Zimmermann, "
    "'Comparing the difficulty of factorization and discrete logarithm: a 240-digit "
    "experiment', CRYPTO 2020. RSA-250 needed roughly 2,700 core-years on Intel Xeon "
    "Gold 6130 cores."
)
MAX_PROOF_SECONDS = 3600
_NAME = re.compile(r"RSA-\d{2,4}")


def _load() -> list[dict[str, Any]]:
    """Read and strictly validate the challenge catalogue at import time."""

    try:
        raw = tomllib.loads(CATALOGUE.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:  # pragma: no cover - packaging
        raise PrimeEngineError("The RSA challenge catalogue is unavailable") from exc
    entries = raw.get("number")
    if not isinstance(entries, list) or not entries:
        raise PrimeEngineError("The RSA challenge catalogue is empty")
    for entry in entries:
        if set(entry) - {"name", "digits", "bits", "status", "value", "factors"}:
            raise PrimeEngineError(f"Unexpected field in catalogue entry {entry!r}")
        if not _NAME.fullmatch(str(entry.get("name", ""))):
            raise PrimeEngineError(f"Malformed catalogue name {entry.get('name')!r}")
        if entry["status"] not in {"factored", "open"}:
            raise PrimeEngineError(f"Unknown status for {entry['name']}")
        if not str(entry["value"]).isdigit():
            raise PrimeEngineError(f"Non-decimal value for {entry['name']}")
        if (entry["status"] == "factored") != ("factors" in entry):
            raise PrimeEngineError(f"Status and factors disagree for {entry['name']}")
        for factor in entry.get("factors", []):
            if not str(factor).isdigit():
                raise PrimeEngineError(f"Non-decimal factor for {entry['name']}")
    return entries


ENTRIES: list[dict[str, Any]] = _load()
BY_NAME: dict[str, dict[str, Any]] = {e["name"]: e for e in ENTRIES}
BY_VALUE: dict[str, dict[str, Any]] = {e["value"]: e for e in ENTRIES}
SOURCE: str = tomllib.loads(CATALOGUE.read_text(encoding="utf-8")).get("source", "")


def catalogue() -> dict[str, Any]:
    """List every challenge number with its size and published status.

    The decimal values are omitted; they are large and the list is for orientation.
    """

    rows = [
        [e["name"], str(e["digits"]), str(e["bits"]), e["status"],
         "yes" if e["status"] == "factored" else "no"]
        for e in ENTRIES
    ]
    factored = sum(1 for e in ENTRIES if e["status"] == "factored")
    return {
        "columns": ["Challenge", "Decimal digits", "Bits", "Status", "Factors published"],
        "rows": rows,
        "metrics": {
            "Challenge numbers listed": str(len(ENTRIES)),
            "Factored": str(factored),
            "Still open": str(len(ENTRIES) - factored),
            "Smallest": f"{ENTRIES[0]['name']} ({ENTRIES[0]['digits']} digits)",
            "Largest": f"{ENTRIES[-1]['name']} ({ENTRIES[-1]['digits']} digits)",
            "Source": SOURCE,
        },
        "note": (
            "Sizes come from the catalogue and are re-derived by PARI/GP whenever a "
            "single entry is reported. An open challenge number is unfactored, which is "
            "a statement about the effort spent so far and not a claim that it cannot "
            "be factored."
        ),
    }


def _cores() -> int:
    return os.cpu_count() or 1


def _text(lines: list[str], tag: str) -> str:
    prefix = f"{tag}:"
    values = [line[len(prefix):].strip() for line in lines if line.startswith(prefix)]
    if len(values) != 1:
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} value")
    return values[0]


def _one(lines: list[str], tag: str) -> int:
    values = _tagged_values(lines, tag)
    if len(values) != 1:
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} result")
    return values[0]


def _real(lines: list[str], tag: str) -> float:
    """Parse one PARI/GP real.

    GP writes an exponent with a space in front of it, as in ``2.48... E-5``, which
    Python's float() rejects. Only the whitespace is removed; no rounding or arithmetic
    happens here.
    """

    raw = _text(lines, tag).replace(" ", "")
    try:
        return float(raw)
    except ValueError as exc:
        raise PrimeEngineError(f"PARI/GP returned an unreadable {tag.lower()}") from exc


def _duration(years: float) -> str:
    """Render a core-year figure at a scale a reader can act on."""

    if years < 0:
        return "not estimated"
    seconds = years * 365.25 * 24 * 3600
    for limit, unit, factor in (
        (120, "seconds", 1.0),
        (7200, "minutes", 60.0),
        (172800, "hours", 3600.0),
        (63113852, "days", 86400.0),
    ):
        if seconds < limit:
            return f"{seconds / factor:,.1f} {unit}"
    if years < 1e6:
        return f"{years:,.0f} years"
    return f"{years:.3g} years"


def challenge_report(
    target: str,
    prove_factors: bool = False,
    proof_seconds: int = 60,
    timeout: int = 300,
) -> dict[str, Any]:
    """Report on one RSA challenge number, verifying every claim in PARI/GP.

    Args:
        target: A challenge name such as ``"RSA-250"``, or the decimal value itself.
        prove_factors: Demand a primality *proof* of each published factor rather than
            Baillie-PSW.  Expensive for the larger entries; an exceeded budget is
            reported as inconclusive rather than downgraded silently.
        proof_seconds: Budget for each primality proof, 1 to 3,600 seconds.
        timeout: PARI/GP time limit in seconds.

    Returns:
        A report dictionary carrying the engine's findings, the estimated effort, and
        whether the input is a recognised challenge number.

    Raises:
        ValueError: If the target is neither a known name nor a decimal integer, or a
            bound is violated.
        PrimeEngineError: If PARI/GP failed or contradicted the catalogue.
    """

    clean = target.strip().upper().replace(" ", "")
    if not 1 <= proof_seconds <= MAX_PROOF_SECONDS:
        raise ValueError(f"Proof budget must be between 1 and {MAX_PROOF_SECONDS:,} seconds")
    if not 1 <= timeout <= 3600:
        raise ValueError("Engine time limit must be between 1 and 3,600 seconds")

    if clean in BY_NAME:
        entry = BY_NAME[clean]
    elif clean.isdigit():
        entry = BY_VALUE.get(clean) or {
            "name": "not a challenge number",
            "value": clean,
            "status": "unlisted",
            "digits": None,
            "bits": None,
        }
    else:
        raise ValueError(
            "Supply an RSA challenge name such as RSA-250, or its decimal value"
        )

    factors = entry.get("factors") or []
    p, q = (factors + ["0", "0"])[:2]
    anchor = BY_NAME[ANCHOR_NAME]
    call = (
        f"rc_report({entry['value']},{p},{q},{1 if prove_factors else 0},"
        f"{_cores()},{anchor['value']},{ANCHOR_CORE_YEARS},{proof_seconds})"
    )
    try:
        program = PROGRAM.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - packaging failure
        raise PrimeEngineError("The RSA challenge program is unavailable") from exc
    lines = _run_gp(f"{program}\n{call};", timeout=timeout)
    if not _tagged_values(lines, "DONE"):
        raise PrimeEngineError("PARI/GP returned an incomplete RSA challenge report")

    digits, bits = _one(lines, "DIGITS"), _one(lines, "BITS")
    composite = _one(lines, "COMPOSITE") == 1
    if not composite:
        raise PrimeEngineError(
            f"PARI/GP found {entry['name']} is not composite; the catalogue is wrong"
        )
    if entry.get("digits") is not None and digits != entry["digits"]:
        raise PrimeEngineError(f"Catalogue digit count for {entry['name']} is wrong")
    if entry.get("bits") is not None and bits != entry["bits"]:
        raise PrimeEngineError(f"Catalogue bit length for {entry['name']} is wrong")

    verified = None
    if factors:
        if _one(lines, "PRODUCT") != 1:
            raise PrimeEngineError(
                f"The catalogue factors for {entry['name']} do not multiply to the value"
            )
        strength = _text(lines, "FACTOR_PRIMALITY")
        both_prime = _one(lines, "P_PRIME") == 1 and _one(lines, "Q_PRIME") == 1
        if strength != "inconclusive" and not both_prime:
            raise PrimeEngineError(
                f"A catalogue factor of {entry['name']} is not prime"
            )
        verified = strength

    core_years = _real(lines, "CORE_YEARS")
    wall_years = _real(lines, "WALL_YEARS")
    cores = _one(lines, "CORES")

    metrics: dict[str, str] = {
        "Challenge": entry["name"],
        "Recognised": "yes" if entry["status"] != "unlisted" else "no",
        "Decimal digits": f"{digits:,}",
        "Bits": f"{bits:,}",
        "Composite": "yes, proven by a failed Miller–Rabin round",
        "Published status": entry["status"],
        "Estimated GNFS effort": f"{_duration(core_years)} of core time",
        f"Estimated wall-clock on {cores} cores": _duration(wall_years),
        "Cost model anchored on": f"{ANCHOR_NAME}, {ANCHOR_CORE_YEARS:,} core-years",
    }
    if factors:
        metrics["Published factors multiply to the value"] = "yes, checked in PARI/GP"
        metrics["Factor sizes"] = (
            f"{_one(lines, 'P_DIGITS'):,} and {_one(lines, 'Q_DIGITS'):,} decimal digits"
        )
        metrics["Both factors prime"] = {
            "proven": "yes, proven with isprime",
            "probable": "yes, Baillie–PSW; not a proof",
            "inconclusive": "inconclusive, the proof budget was exhausted",
        }[str(verified)]

    if entry["status"] == "factored":
        guidance = (
            "This challenge number is already factored and the published factors were "
            "re-checked here. Factoring it again is a benchmark, not a discovery."
        )
    elif entry["status"] == "open":
        guidance = (
            "This challenge number is unfactored. That is a statement about the effort "
            "spent so far, not a proof that it resists factoring."
        )
    else:
        guidance = (
            "This value is not one of the published challenge numbers. The size and "
            "effort estimate still apply to it as an ordinary semiprime target."
        )

    return {
        "name": entry["name"],
        "recognised": entry["status"] != "unlisted",
        "status": entry["status"],
        "digits": digits,
        "bits": bits,
        "factors": list(factors),
        "factor_verification": verified,
        "core_years": core_years,
        "wall_years": wall_years,
        "cores": cores,
        "metrics": metrics,
        "columns": ["Quantity", "Value"],
        "rows": [[key, value] for key, value in metrics.items()],
        "note": (
            f"{guidance} PARI/GP proved the value composite, recomputed its size, and "
            "where factors are published multiplied them back together and tested each "
            "for primality; nothing here is taken from the catalogue on trust. The "
            "effort figure is a heuristic planning estimate from the conjectured number "
            "field sieve complexity L[1/3, (64/9)^(1/3)], anchored on a published "
            f"measurement ({ANCHOR_CITATION}) and scaled to this machine. The sieve has "
            "no proven running time and the estimate ignores memory, the linear-algebra "
            "step and parameter tuning, so treat it as an order of magnitude only."
        ),
    }
