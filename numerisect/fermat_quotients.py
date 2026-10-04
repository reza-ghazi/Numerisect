"""Typed orchestration boundary for the Fermat-quotient prime searches.

Computation attribution.  No congruence is evaluated in this module.  Every answer it
returns was produced by the ``numerisect-fermatq`` C program, which searches for

* **Wieferich** primes to any base: ``a^(p-1) = 1 (mod p^2)``, with the Fermat quotient
  reported for near-misses,
* **Wall-Sun-Sun** primes: ``p^2 | F_{p - (5|p)}``, by Fibonacci fast doubling,
* **Wilson** primes: ``(p-1)! = -1 (mod p^2)``,
* **Wolstenholme** primes: ``H_{p-1} = 0 (mod p^3)`` for the modular harmonic sum.

The program enumerates candidates with **primesieve**, uses a 64-bit modulus with
128-bit products while the relevant power of ``p`` fits, and continues in **GMP** above
that for the two logarithmic-cost predicates.  Python validates input, launches one
process, enforces the completion marker and parses the tagged protocol.

Exhausting a range is not a proof of absence beyond it, so ``scanned_to`` and ``status``
are part of every result: a search that ran out of time reports ``timeout`` and the
largest prime it finished, and candidates whose modulus leaves the supported range are
reported as ``refused`` rather than counted as tested.
"""

from __future__ import annotations

import subprocess
from typing import Any

from .native_tools import fermatq_tool_path
from .primes import PrimeEngineError

#: The four predicates, with the congruence each one tests and its practical ceiling.
#: The ceilings are the moduli leaving 64 bits (``p^2`` at 2^32, ``p^3`` at 2,642,246)
#: for the predicates whose cost is linear in ``p``; the two logarithmic ones continue
#: in GMP and are bounded only by patience.
SEARCH_KINDS: dict[str, dict[str, Any]] = {
    "wieferich": {
        "mode": "wieferich",
        "label": "Wieferich primes",
        "congruence": "a^(p-1) = 1 (mod p^2)",
        "takes_base": True,
        "ceiling": None,
        "known": "1093 and 3511 in base 2",
    },
    "wall_sun_sun": {
        "mode": "wall-sun-sun",
        "label": "Wall-Sun-Sun primes",
        "congruence": "p^2 divides F_{p - (5|p)}",
        "takes_base": False,
        "ceiling": None,
        "known": "none; every search so far has returned nothing",
    },
    "wilson": {
        "mode": "wilson",
        "label": "Wilson primes",
        "congruence": "(p-1)! = -1 (mod p^2)",
        "takes_base": False,
        "ceiling": 2**32,
        "known": "5, 13 and 563",
    },
    "wolstenholme": {
        "mode": "wolstenholme",
        "label": "Wolstenholme primes",
        "congruence": "H_{p-1} = 0 (mod p^3)",
        "takes_base": False,
        "ceiling": 2642246,
        "known": "16843 and 2124679",
    },
}

MAX_RANGE_END = 10**13
MAX_BASE = 10**9
MAX_NEAR_BOUND = 10**12


def _argument(value: int) -> str:
    """Render a validated integer as a command-line argument.

    Every numeric argument these helpers take passes through here, so an argv entry is
    an integer by construction rather than by inspection. The helpers are launched as
    argument arrays with no shell, and each argument is parsed by ``strtoull``.
    """

    return str(int(value))


def _one(lines: list[str], tag: str) -> str:
    """Return the single value carried by ``tag``, or raise if it is absent."""

    prefix = f"{tag}:"
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix):]
    raise PrimeEngineError(f"The Fermat-quotient scanner omitted its {tag} marker")


def fermat_quotient_search(
    kind: str,
    start: int,
    end: int,
    *,
    base: int = 2,
    near_bound: int = 0,
    seconds: int = 300,
) -> dict[str, Any]:
    """Search ``[start, end]`` for primes satisfying one Fermat-quotient congruence.

    Args:
        kind: One of the keys of :data:`SEARCH_KINDS`.
        start: Lower end of the search range, at least 2.
        end: Upper end of the search range.
        base: Base ``a`` for the Wieferich congruence; refused for the other kinds,
            which have no base to vary.
        near_bound: Report a prime as a near-miss when its Fermat quotient satisfies
            ``|A| <= near_bound``. Wieferich only; 0 reports hits alone.
        seconds: Wall-clock budget handed to the program, which reports a timeout
            itself rather than being killed mid-range.

    Returns:
        A dict carrying ``kind``, ``label``, ``congruence``, ``start``, ``end``,
        ``base`` (Wieferich only), ``hits``, ``near_misses``, ``rows``, ``tested``,
        ``refused``, ``first_refused``, ``scanned_to``, ``status`` and ``note``.

    Raises:
        ValueError: On an unknown kind, an inverted or out-of-range interval, a base
            or near-miss bound outside its limits, or a base given for a kind that
            takes none.
        PrimeEngineError: If the program fails, omits a marker, or returns a hit
            count that disagrees with the rows it printed.
    """

    if kind not in SEARCH_KINDS:
        known = ", ".join(sorted(SEARCH_KINDS))
        raise ValueError(f"Unknown search kind '{kind}'; choose one of {known}")
    specification = SEARCH_KINDS[kind]
    if not 2 <= start <= end:
        raise ValueError("The range must satisfy 2 <= start <= end")
    if end > MAX_RANGE_END:
        raise ValueError(f"The range end may not exceed {MAX_RANGE_END:,}")
    if not 1 <= seconds <= 86400:
        raise ValueError("The time budget must be between 1 and 86,400 seconds")
    if specification["takes_base"]:
        if not 2 <= base <= MAX_BASE:
            raise ValueError(f"The base must be between 2 and {MAX_BASE:,}")
        if not 0 <= near_bound <= MAX_NEAR_BOUND:
            raise ValueError(f"The near-miss bound must be between 0 and {MAX_NEAR_BOUND:,}")
    elif base != 2:
        raise ValueError(f"{specification['label']} have no base to vary")
    elif near_bound:
        raise ValueError("Near-misses are reported for the Wieferich congruence only")

    tool = fermatq_tool_path()
    # The subcommand is this module's own constant, looked up by the validated key, so
    # no request string reaches the command line at all.
    mode = str(specification["mode"])
    command = [str(tool), mode, _argument(start), _argument(end)]
    if specification["takes_base"]:
        command += [_argument(base), _argument(near_bound)]
    command.append(_argument(seconds))
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, check=False,
            # The program owns the budget and reports a timeout in its own output; this
            # is only a backstop against a wedged process.
            timeout=seconds + 60,
        )
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - backstop only
        raise PrimeEngineError(
            "The Fermat-quotient scanner did not return within its budget"
        ) from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "no diagnostic"
        raise PrimeEngineError(f"The Fermat-quotient scanner failed: {detail}")
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not any(line.startswith("DONE:") for line in lines):
        raise PrimeEngineError("The Fermat-quotient scanner omitted its completion marker")

    hits: list[int] = []
    near_misses: list[tuple[int, int]] = []
    for line in lines:
        if line.startswith("HIT:"):
            hits.append(int(line[len("HIT:"):].split("|", 1)[0]))
        elif line.startswith("NEAR:"):
            prime, _, quotient = line[len("NEAR:"):].partition("|")
            near_misses.append((int(prime), int(quotient)))
    reported = int(_one(lines, "HITS"))
    if reported != len(hits) + len(near_misses):
        raise PrimeEngineError(
            "The Fermat-quotient scanner reported a count that disagrees with its rows"
        )
    status = _one(lines, "STATUS")
    tested = int(_one(lines, "TESTED"))
    refused = int(_one(lines, "REFUSED"))
    scanned_to = int(_one(lines, "SCANNED_TO"))

    rows = [[str(prime), "hit", ""] for prime in hits]
    rows += [[str(prime), "near-miss", str(quotient)] for prime, quotient in near_misses]
    rows.sort(key=lambda row: int(row[0]))

    notes = []
    if status == "complete":
        notes.append(
            f"Exhausted every prime in [{start:,}, {end:,}]. Finding none says nothing "
            "about primes outside that range."
        )
    elif status == "timeout":
        notes.append(
            f"The budget of {seconds} s expired. Primes up to {scanned_to:,} were fully "
            "searched; the rest of the range is untested, not clear."
        )
    if refused:
        ceiling = specification["ceiling"]
        notes.append(
            f"{refused:,} candidate(s) were refused rather than tested: this congruence "
            f"costs O(p) and is supported below {ceiling:,}, where the modulus still fits "
            "64 bits. An untested candidate is never reported as a passing one."
        )
    notes.append(f"Known members: {specification['known']}.")

    result: dict[str, Any] = {
        "kind": kind,
        "label": specification["label"],
        "congruence": specification["congruence"],
        "start": str(start),
        "end": str(end),
        "hits": [str(prime) for prime in hits],
        "near_misses": [[str(prime), str(quotient)] for prime, quotient in near_misses],
        "rows": rows,
        "tested": str(tested),
        "refused": str(refused),
        "first_refused": _one(lines, "FIRST_REFUSED") if refused else "",
        "scanned_to": str(scanned_to),
        "status": status,
        "complete": status == "complete",
        "note": " ".join(notes),
    }
    if specification["takes_base"]:
        result["base"] = str(base)
        result["near_bound"] = str(near_bound)
    return result
