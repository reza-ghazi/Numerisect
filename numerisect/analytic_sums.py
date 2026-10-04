"""Typed orchestration boundary for the two summatory-function helpers.

Computation attribution.  Nothing is summed in this module.

* **M(x), its sign changes and the extremal ratio** come from ``numerisect-mertens``
  (C, segmented Moebius sieve plus the hyperbola identity ``sum_{n<=x} M(x/n) = 1``).
  The two algorithms share no path beyond the sieve, so the ``cross_check`` option runs
  both and refuses to report a value if they disagree.
* **Brun-type constants** come from ``numerisect-brun`` (C, primesieve for the prime
  tuples and MPFR for the sum).

Python validates input, launches one process per request, enforces the completion
marker and parses the tagged protocol.

What the results claim.  M(x) is exact: it is an integer sum of integers. A Brun-type
result is an exactly computed **truncated** sum, never the constant itself; these sums
converge like 1/log x, so no reachable bound determines the constant's leading digits,
and this module never presents an extrapolation as a computed value.
"""

from __future__ import annotations

import subprocess
from typing import Any

from .native_tools import brun_tool_path, mertens_tool_path
from .primes import PrimeEngineError

#: Highest x accepted for the hyperbola method. The table it needs is 4 bytes per entry
#: up to a cut of about x**(2/3), so this bounds memory as well as time.
MAX_MERTENS_X = 10**14
#: Highest x accepted for the linear sieve, which must touch every integer.
MAX_MERTENS_SIEVE_X = 10**11
#: Highest bound accepted for a Brun-type sum.
MAX_BRUN_LIMIT = 10**12

#: The tuple patterns the Brun helper supports, with their literature values. The
#: estimates are published extrapolations, quoted for comparison only; nothing here
#: computes them, and a truncated sum must never be presented as approaching one
#: except as the comparison it is.
BRUN_PATTERNS: dict[str, dict[str, str]] = {
    "twin": {
        "mode": "twin",
        "label": "Twin primes (p, p+2)",
        "constant": "B2",
        "literature": "1.902160583104 (Klyve, extrapolated)",
    },
    "cousin": {
        "mode": "cousin",
        "label": "Cousin primes (p, p+4)",
        "constant": "B4",
        "literature": "1.1970449 (extrapolated, excluding the pair (3, 7))",
    },
    "sexy": {
        "mode": "sexy",
        "label": "Sexy primes (p, p+6)",
        "constant": "B6",
        "literature": "no standard published value",
    },
    "triplet": {
        "mode": "triplet",
        "label": "Prime triplets (p, p+2, p+6) and (p, p+4, p+6)",
        "constant": "B(3)",
        "literature": "no standard published value",
    },
    "quadruplet": {
        "mode": "quadruplet",
        "label": "Prime quadruplets (p, p+2, p+6, p+8)",
        "constant": "B(4)",
        "literature": "0.8705883800 (extrapolated)",
    },
}


def _argument(value: int) -> str:
    """Render a validated integer as a command-line argument.

    Every numeric argument passes through here, so an argv entry is an integer by
    construction. The helpers are launched as argument arrays with no shell.
    """

    return str(int(value))


def _tagged(lines: list[str], tag: str) -> str:
    prefix = f"{tag}:"
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix):]
    raise PrimeEngineError(f"The helper omitted its {tag} marker")


def _run(command: list[str], timeout: int) -> list[str]:
    """Run a helper and return its tagged lines, or raise with its diagnostic."""

    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        raise PrimeEngineError(
            "The helper did not return within its wall-clock budget"
        ) from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "no diagnostic"
        raise PrimeEngineError(f"The helper failed: {detail}")
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not any(line.startswith("DONE:") for line in lines):
        raise PrimeEngineError("The helper omitted its completion marker")
    return lines


def mertens_value(x: int, *, cross_check: bool = False, seconds: int = 3600) -> dict[str, Any]:
    """Compute M(x) = sum of the Moebius function up to ``x``.

    Args:
        x: Upper bound, at least 1.
        cross_check: Also compute M(x) with the independent segmented sieve and refuse
            to report a value if the two disagree. Linear in ``x``, so it is accepted
            only up to :data:`MAX_MERTENS_SIEVE_X`.
        seconds: Wall-clock budget for the subprocess.

    Returns:
        A dict with ``x``, ``mertens``, ``method``, ``ratio`` (``|M(x)|/sqrt(x)``),
        ``cut``, ``seconds``, ``cross_checked``, ``status`` and ``note``.

    Raises:
        ValueError: If ``x`` is out of range, or a cross-check is asked for above the
            sieve's limit.
        PrimeEngineError: If the helper fails, refuses the request for memory, or the
            two algorithms disagree.
    """

    if not 1 <= x <= MAX_MERTENS_X:
        raise ValueError(f"x must be between 1 and {MAX_MERTENS_X:,}")
    if cross_check and x > MAX_MERTENS_SIEVE_X:
        raise ValueError(
            "The cross-check sieves every integer up to x, so it is available only "
            f"through {MAX_MERTENS_SIEVE_X:,}"
        )
    tool = mertens_tool_path()
    lines = _run([str(tool), "mertens", _argument(x)], seconds)
    status = _tagged(lines, "STATUS")
    if status == "refused-memory":
        raise PrimeEngineError(
            "The hyperbola method needs a table covering sqrt(x) and the cap is lower; "
            "this x is refused rather than answered outside the method's validity"
        )
    value = int(_tagged(lines, "MERTENS"))
    result: dict[str, Any] = {
        "x": str(x),
        "mertens": str(value),
        "method": _tagged(lines, "METHOD"),
        "cut": _tagged(lines, "CUT"),
        "ratio": _tagged(lines, "RATIO"),
        "seconds": _tagged(lines, "SECONDS"),
        "status": status,
        "cross_checked": False,
    }
    if cross_check:
        sieve_lines = _run([str(tool), "mertens-sieve", _argument(x), "0"], seconds)
        sieve_value = int(_tagged(sieve_lines, "MERTENS"))
        if sieve_value != value:
            raise PrimeEngineError(
                f"The two algorithms disagree for x={x}: the hyperbola identity gives "
                f"{value} and the segmented sieve gives {sieve_value}. No value is "
                "reported."
            )
        result["cross_checked"] = True
        result["cross_check_method"] = _tagged(sieve_lines, "METHOD")
    result["note"] = (
        "M(x) is an exact integer sum. "
        + (
            "Both the hyperbola identity and an independent segmented Moebius sieve "
            "returned this value."
            if cross_check
            else "Computed by the hyperbola identity; enable the cross-check to confirm "
            "it with an independent segmented sieve."
        )
    )
    return result


def mertens_sign_analysis(x: int, *, seconds: int = 3600) -> dict[str, Any]:
    """Track M(n) for every n up to ``x``: sign changes, extrema and the ratio.

    The Mertens conjecture claimed ``|M(n)| < sqrt(n)`` for all n. Odlyzko and te Riele
    disproved it in 1985 without exhibiting a counterexample, and none is known below
    the ranges reachable here, so a maximal ratio below 1 is expected and is evidence
    about this range only.

    Args:
        x: Upper bound, at least 1 and at most :data:`MAX_MERTENS_SIEVE_X`.
        seconds: Wall-clock budget; the helper reports a timeout itself.

    Returns:
        A dict with ``x``, ``mertens``, ``reached``, ``sign_changes``,
        ``first_sign_change``, ``minimum``, ``maximum``, ``extreme_ratio``,
        ``changes``, ``rows``, ``status`` and ``note``.
    """

    if not 1 <= x <= MAX_MERTENS_SIEVE_X:
        raise ValueError(f"x must be between 1 and {MAX_MERTENS_SIEVE_X:,}")
    tool = mertens_tool_path()
    lines = _run([str(tool), "signs", _argument(x), _argument(max(1, seconds - 30))], seconds)
    minimum, _, minimum_at = _tagged(lines, "MINIMUM").partition("|")
    maximum, _, maximum_at = _tagged(lines, "MAXIMUM").partition("|")
    ratio, _, ratio_at = _tagged(lines, "EXTREME_RATIO").partition("|")
    changes = [line[len("CHANGE:"):] for line in lines if line.startswith("CHANGE:")]
    listed = int(_tagged(lines, "LISTED"))
    if listed != len(changes):
        raise PrimeEngineError(
            "The helper reported a sign-change count that disagrees with its rows"
        )
    status = _tagged(lines, "STATUS")
    reached = _tagged(lines, "REACHED")
    total_changes = int(_tagged(lines, "SIGN_CHANGES"))
    note = [
        f"M(n) changes sign {total_changes:,} times for n up to {int(reached):,}.",
        f"The largest |M(n)|/sqrt(n) over 2 <= n <= {int(reached):,} is {ratio} at "
        f"n = {int(ratio_at):,}.",
        "The Mertens conjecture |M(n)| < sqrt(n) is false (Odlyzko and te Riele, 1985), "
        "but no counterexample is known in this range, so a ratio below 1 here says "
        "nothing about larger n.",
    ]
    if status == "timeout":
        note.append(
            f"The budget expired at n = {int(reached):,}; the rest of the range is "
            "unexamined, not quiet."
        )
    return {
        "x": str(x),
        "mertens": _tagged(lines, "MERTENS"),
        "reached": reached,
        "method": _tagged(lines, "METHOD"),
        "sign_changes": str(total_changes),
        "first_sign_change": _tagged(lines, "FIRST_SIGN_CHANGE"),
        "minimum": minimum,
        "minimum_at": minimum_at,
        "maximum": maximum,
        "maximum_at": maximum_at,
        "extreme_ratio": ratio,
        "extreme_ratio_at": ratio_at,
        "changes": changes,
        "listed": str(listed),
        "truncated": listed < total_changes,
        "rows": [[value] for value in changes],
        "seconds": _tagged(lines, "SECONDS"),
        "status": status,
        "complete": status == "complete",
        "note": " ".join(note),
    }


def brun_sum(
    pattern: str, limit: int, *, digits: int = 20, seconds: int = 3600
) -> dict[str, Any]:
    """Sum the reciprocals of one prime-tuple family up to ``limit``.

    Args:
        pattern: One of the keys of :data:`BRUN_PATTERNS`.
        limit: Upper bound on every member of a counted tuple.
        digits: Decimal digits to report, 3 through 1000; the helper works at a higher
            internal precision.
        seconds: Wall-clock budget; the helper reports a timeout itself.

    Returns:
        A dict with ``pattern``, ``label``, ``constant``, ``limit``, ``reached``,
        ``sum``, ``tuples``, ``members``, ``largest``, ``digits``,
        ``precision_bits``, ``literature``, ``status`` and ``note``.

    Raises:
        ValueError: On an unknown pattern or an out-of-range limit or digit count.
        PrimeEngineError: If the helper fails or omits a marker.
    """

    if pattern not in BRUN_PATTERNS:
        known = ", ".join(sorted(BRUN_PATTERNS))
        raise ValueError(f"Unknown tuple pattern '{pattern}'; choose one of {known}")
    if not 5 <= limit <= MAX_BRUN_LIMIT:
        raise ValueError(f"The limit must be between 5 and {MAX_BRUN_LIMIT:,}")
    if not 3 <= digits <= 1000:
        raise ValueError("The digit count must be between 3 and 1000")
    specification = BRUN_PATTERNS[pattern]
    # The pattern argument is this module's own constant, not the request's string.
    lines = _run(
        [str(brun_tool_path()), str(specification["mode"]), _argument(limit),
         _argument(digits), _argument(max(1, seconds - 30))],
        seconds,
    )
    status = _tagged(lines, "STATUS")
    reached = int(_tagged(lines, "REACHED"))
    note = [
        f"This is the exact truncated sum over tuples with every member at most "
        f"{reached:,}, not the constant.",
        "Brun-type sums converge like 1/log x, so the leading digits of the constant "
        "are not determined by any bound reachable here.",
        f"Published estimate for comparison: {specification['literature']}. Those "
        "figures come from extrapolation models this program deliberately does not "
        "apply.",
    ]
    if status == "timeout":
        note.insert(1, f"The budget expired at {reached:,}, short of the requested limit.")
    return {
        "pattern": pattern,
        "label": specification["label"],
        "constant": specification["constant"],
        "limit": str(limit),
        "reached": str(reached),
        "sum": _tagged(lines, "SUM"),
        "tuples": _tagged(lines, "TUPLES"),
        "members": _tagged(lines, "MEMBERS"),
        "largest": _tagged(lines, "LARGEST"),
        "digits": _tagged(lines, "DIGITS"),
        "precision_bits": _tagged(lines, "PRECISION_BITS"),
        "literature": specification["literature"],
        "seconds": _tagged(lines, "SECONDS"),
        "status": status,
        "complete": status == "complete",
        "note": " ".join(note),
    }
