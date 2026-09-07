"""Typed orchestration boundary for the analytic prime-distribution laboratory.

Computation attribution. No mathematical quantity is evaluated in this module:

* exact ``pi(x)``, the exact ``n``-th prime and ``R(x)`` come from the
  **primecount** engine (``primecount x``, ``--nth-prime``, ``--RiemannR``);
  ``primes.prime_count`` and ``primes.nth_prime`` own those subprocesses.
* prime k-tuplet counts come from **primesieve** ``--count=k`` whenever the
  requested pattern is one of primesieve's single-pattern constellations and
  the whole range stays below ``2^64``.
* everything else is computed by ``numerisect/distribution_lab.gp`` inside
  **PARI/GP**: ``li(x)`` through ``eint1``, ``x/log x``, every absolute and
  relative error, the Rosser-Schoenfeld and Dusart ``n``-th prime bounds,
  residue-class counts through ``forprime``, the Hardy-Littlewood singular
  series with its rigorous truncation bound, the Bateman-Horn constant through
  ``polisirreducible``/``polrootsmod``/``intnum``, the bounded record-gap search
  with merits and the Cramer/Granville/Firoozbakht comparisons, the
  Maier-matrix row counts and the prime-density surface.

Python validates input, launches the engines, enforces the completion markers,
parses the tagged protocol and hands rows to the report writer.  JavaScript only
paints the strings produced here.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Sequence

from .number_theory import _primecount_option
from .prime_manipulation import decimal_integer
from .primes import PrimeEngineError, _run_gp, _tagged_values, nth_prime, prime_count

PROGRAM = Path(__file__).with_name("distribution_lab.gp")

_REAL = re.compile(r"-?\d+(?:\.\d+)?(?:e[+-]?\d+)?", re.IGNORECASE)
_LABEL = re.compile(r"[0-9A-Za-z_+*/^()., \[\]-]+")
_UINT64 = 18_446_744_073_709_551_615

#: primesieve counts exactly one constellation pattern for these sizes, so its
#: ``--count=k`` output can be compared with a Hardy-Littlewood prediction.
#: (k = 3 and k = 5 mix two patterns and are therefore counted by PARI/GP.)
PRIMESIEVE_PATTERNS: dict[tuple[int, ...], int] = {
    (0, 2): 2,
    (0, 2, 6, 8): 4,
    (0, 4, 6, 10, 12, 16): 6,
}


def _program() -> str:
    try:
        return PROGRAM.read_text(encoding="utf-8")
    except OSError as exc:
        raise PrimeEngineError("The prime-distribution PARI/GP program is unavailable") from exc


def _execute(call: str, timeout: int) -> list[str]:
    if not 1 <= timeout <= 3600:
        raise ValueError("Engine time limit must be between 1 and 3,600 seconds")
    lines = _run_gp(f"{_program()}\n{call};", timeout=timeout)
    if not _tagged_values(lines, "DONE"):
        raise PrimeEngineError("PARI/GP returned an incomplete distribution result")
    return lines


def _one(lines: list[str], tag: str) -> int:
    values = _tagged_values(lines, tag)
    if len(values) != 1:
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} result")
    return values[0]


def _decimal(lines: list[str], tag: str) -> str:
    prefix = f"{tag}:"
    values = [line[len(prefix):] for line in lines if line.startswith(prefix)]
    if len(values) != 1 or not _REAL.fullmatch(values[0]):
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} value")
    return values[0]


def _records(lines: Iterable[str], tag: str, width: int) -> list[list[str]]:
    prefix = f"{tag}:"
    rows = [line[len(prefix):].split("|") for line in lines if line.startswith(prefix)]
    for row in rows:
        if len(row) != width or any(not _LABEL.fullmatch(value) for value in row):
            raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} record")
    return rows


def _vector(values: Sequence[int]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"


def _grid_bounds(exponent_from: int, exponent_to: int, points: int, ceiling: int) -> None:
    if not 1 <= exponent_from < exponent_to <= ceiling:
        raise ValueError(
            f"Grid exponents must satisfy 1 ≤ from < to ≤ {ceiling}"
        )
    if not 2 <= points <= 24:
        raise ValueError("A grid needs between 2 and 24 points")


def _log_grid(exponent_from: int, exponent_to: int, points: int, timeout: int) -> list[int]:
    lines = _execute(f"dl_grid({exponent_from},{exponent_to},{points})", timeout)
    values = _tagged_values(lines, "GRID")
    if not values or _one(lines, "DONE") != len(values):
        raise PrimeEngineError("PARI/GP returned an incomplete evaluation grid")
    return values


def approximation_error(
    exponent_from: int = 3,
    exponent_to: int = 12,
    points: int = 10,
    threads: int = 1,
    timeout: int = 600,
) -> dict:
    """Roadmap item 76: absolute and relative approximation error charts.

    ``primecount`` supplies exact ``pi(x)`` and ``R(x)``; PARI/GP supplies
    ``x/log x``, ``li(x)`` and every error term.
    """
    _grid_bounds(exponent_from, exponent_to, points, 19)
    if not 1 <= threads <= 256:
        raise ValueError("Thread count must be between 1 and 256")
    grid = _log_grid(exponent_from, exponent_to, points, timeout)
    exact = [prime_count(value, threads) for value in grid]
    riemann = [_primecount_option(value, "--RiemannR", threads, timeout) for value in grid]
    lines = _execute(
        f"dl_approximation_error({_vector(grid)},{_vector(exact)},{_vector(riemann)})",
        timeout,
    )
    rows = _records(lines, "ROW", 11)
    if _one(lines, "DONE") != len(rows) or len(rows) != len(grid):
        raise PrimeEngineError("PARI/GP returned an incomplete approximation-error table")
    return {
        "metrics": {
            "Grid": f"10^{exponent_from} … 10^{exponent_to}",
            "Grid points": str(len(rows)),
            "Largest endpoint": rows[-1][0],
            "Exact π at the largest endpoint": rows[-1][1],
            "CPU threads": str(threads),
        },
        "columns": [
            "x", "Exact π(x)", "x/log x", "li(x)", "R(x)",
            "x/log x − π(x)", "li(x) − π(x)", "R(x) − π(x)",
            "x/log x relative (%)", "li(x) relative (%)", "R(x) relative (%)",
        ],
        "rows": rows,
        "chart": "approximation-error",
        "note": (
            "primecount computed exact π(x) and R(x); PARI/GP computed x/log(x), "
            "li(x) through eint1, and every signed and relative error at 60-digit "
            "precision. R(x) is primecount's rounded Riemann R estimate, so its "
            "error column is exact to within one unit."
        ),
    }


def pnt_convergence(
    exponent_from: int = 3,
    exponent_to: int = 12,
    points: int = 10,
    threads: int = 1,
    timeout: int = 600,
) -> dict:
    """Roadmap item 82: prime-number-theorem convergence laboratory."""
    _grid_bounds(exponent_from, exponent_to, points, 19)
    if not 1 <= threads <= 256:
        raise ValueError("Thread count must be between 1 and 256")
    grid = _log_grid(exponent_from, exponent_to, points, timeout)
    exact = [prime_count(value, threads) for value in grid]
    lines = _execute(f"dl_pnt_convergence({_vector(grid)},{_vector(exact)})", timeout)
    rows = _records(lines, "ROW", 7)
    changes = _records(lines, "SIGNCHANGE", 3)
    if _one(lines, "DONE") != len(rows) or len(rows) != len(grid):
        raise PrimeEngineError("PARI/GP returned an incomplete convergence table")
    if _one(lines, "SIGN_CHANGES") != len(changes):
        raise PrimeEngineError("PARI/GP returned an inconsistent sign-change count")
    return {
        "metrics": {
            "Grid": f"10^{exponent_from} … 10^{exponent_to}",
            "Grid points": str(len(rows)),
            "π(x)/(x/log x) at the largest endpoint": rows[-1][2],
            "π(x)/li(x) at the largest endpoint": rows[-1][3],
            "π(x) − li(x) at the largest endpoint": rows[-1][4],
            "Sign changes of π(x) − li(x) on this grid": str(len(changes)),
        },
        "columns": [
            "x", "Exact π(x)", "π(x)/(x/log x)", "π(x)/li(x)",
            "π(x) − li(x)", "(π(x) − li(x))·log x/√x", "sign",
        ],
        "rows": rows,
        "sections": [
            {
                "title": "Sign changes detected between consecutive grid points",
                "columns": ["First x with the new sign", "Previous sign", "New sign"],
                "rows": changes,
            }
        ],
        "sign_changes": len(changes),
        "chart": "pnt-convergence",
        "note": (
            "primecount computed exact π(x); PARI/GP computed li(x) through eint1 and "
            "every ratio, difference and normalisation. A grid samples finitely many "
            "points, so an absence of sign changes here is not evidence that π(x) − li(x) "
            "keeps its sign — Littlewood proved it changes sign infinitely often."
        ),
    }


_BOUND_SIDES = {"-1": "lower", "1": "upper"}


def nth_prime_bounds(
    exponent_from: int = 1,
    exponent_to: int = 9,
    points: int = 9,
    threads: int = 1,
    timeout: int = 600,
) -> dict:
    """Roadmap item 81: explicit n-th prime bounds against the exact p_n.

    Bounds, each with its published validity range:

    * Rosser (1939), ``p_n > n log n`` for ``n ≥ 1``.
    * Rosser and Schoenfeld (1962), *Illinois J. Math.* 6, (3.12) and (3.13).
    * Dusart (1999), Theorem 3.
    * Dusart (2010), Proposition 5.15 (lower for ``n ≥ 3``, upper for
      ``n ≥ 688383``).
    """
    _grid_bounds(exponent_from, exponent_to, points, 17)
    if not 1 <= threads <= 256:
        raise ValueError("Thread count must be between 1 and 256")
    grid = _log_grid(exponent_from, exponent_to, points, timeout)
    exact = [nth_prime(index, threads) for index in grid]
    lines = _execute(f"dl_nth_prime_bounds({_vector(grid)},{_vector(exact)})", timeout)
    rows = _records(lines, "BOUND", 9)
    if _one(lines, "DONE") != len(rows) or len(rows) != len(grid) * 6:
        raise PrimeEngineError("PARI/GP returned an incomplete n-th prime bound table")
    display: list[list[str]] = []
    violations = 0
    for row in rows:
        index, prime, _, name, value, side, valid, holds, difference = row
        if valid == "0":
            verdict = "outside the published validity range"
        elif holds == "1":
            verdict = "holds"
        else:
            verdict = "VIOLATED"
            violations += 1
        display.append(
            [index, prime, name, _BOUND_SIDES[side], value, difference, verdict]
        )
    return {
        "metrics": {
            "Index grid": f"10^{exponent_from} … 10^{exponent_to}",
            "Indices tested": str(len(grid)),
            "Bounds per index": "6",
            "Largest index": str(grid[-1]),
            "Exact p_n at the largest index": str(exact[-1]),
            "Violations inside a stated validity range": str(violations),
        },
        "columns": [
            "n", "Exact p_n", "Bound (with citation)", "Side",
            "Bound value", "Bound − p_n", "Verdict",
        ],
        "rows": display,
        "violations": violations,
        "note": (
            "primecount computed the exact n-th prime; PARI/GP evaluated every bound at "
            "60-digit precision. Citations: Rosser (1939); Rosser and Schoenfeld, "
            "Approximate formulas for some functions of prime numbers, Illinois J. Math. 6 "
            "(1962), formulas (3.12) and (3.13); Dusart, The k-th prime is greater than "
            "k(ln k + ln ln k − 1) for k ≥ 2, Math. Comp. 68 (1999), Theorem 3; Dusart, "
            "Estimates of some functions over primes without R.H. (2010), Proposition 5.15. "
            "A bound evaluated outside its stated range is reported as inapplicable, never "
            "as a failure."
        ),
    }


def prime_race(
    modulus: str, endpoint: str, checkpoints: int = 12, timeout: int = 600
) -> dict:
    """Roadmap item 83: prime races and Chebyshev bias."""
    q = decimal_integer(modulus)
    x = decimal_integer(endpoint)
    if not 3 <= q <= 5040:
        raise ValueError("The race modulus must satisfy 3 ≤ q ≤ 5,040")
    if not 10 <= x <= 10**10:
        raise ValueError("The race endpoint must satisfy 10 ≤ x ≤ 10^10")
    if not 1 <= checkpoints <= 64:
        raise ValueError("Use between 1 and 64 checkpoints")
    lines = _execute(f"dl_prime_race({q},{x},{checkpoints})", timeout)
    rows = _records(lines, "RACE", 4)
    leads = _records(lines, "LEAD", 4)
    classes = _one(lines, "CLASSES")
    stops = _one(lines, "CHECKPOINTS")
    if _one(lines, "DONE") != len(rows) or len(rows) != classes * stops:
        raise PrimeEngineError("PARI/GP returned an incomplete prime-race table")
    if len(leads) != stops:
        raise PrimeEngineError("PARI/GP returned an incomplete race-leader table")
    lead_rows = [
        [stop, "tied" if leader == "-1" else leader, count, total]
        for stop, leader, count, total in leads
    ]
    return {
        "metrics": {
            "Modulus q": str(q),
            "Reduced residue classes φ(q)": str(classes),
            "Endpoint x": str(x),
            "Checkpoints": str(stops),
            "Primes counted": str(_one(lines, "RACE_TOTAL")),
            "Lead changes": str(_one(lines, "LEAD_CHANGES")),
            "Leader at x": lead_rows[-1][1],
        },
        "columns": ["x", "Residue a mod q", "π(x; q, a)", "Normalised bias"],
        "rows": rows,
        "sections": [
            {
                "title": "Leader at each checkpoint",
                "columns": ["x", "Leading residue", "Its count", "Primes counted"],
                "rows": lead_rows,
            }
        ],
        "classes": classes,
        "checkpoints": stops,
        "lead_changes": _one(lines, "LEAD_CHANGES"),
        "chart": "prime-race",
        "note": (
            "PARI/GP made one forprime pass over [2, x], counted each reduced residue "
            "class exactly, and computed li(x) through eint1. The normalised bias is "
            "(π(x; q, a) − li(x)/φ(q))·log x/√x, the Rubinstein–Sarnak scaling. Lead "
            "changes are only those visible at the sampled checkpoints; the race can "
            "change lead between them, so this count is a lower bound."
        ),
    }


def progression_deviation(modulus: str, endpoint: str, timeout: int = 600) -> dict:
    """Roadmap item 84: π(x; q, a) against li(x)/φ(q)."""
    q = decimal_integer(modulus)
    x = decimal_integer(endpoint)
    if not 2 <= q <= 5040:
        raise ValueError("The progression modulus must satisfy 2 ≤ q ≤ 5,040")
    if not 10 <= x <= 10**10:
        raise ValueError("The progression endpoint must satisfy 10 ≤ x ≤ 10^10")
    lines = _execute(f"dl_progression_deviation({q},{x})", timeout)
    rows = _records(lines, "PROG", 6)
    classes = _one(lines, "PROG_CLASSES")
    if _one(lines, "DONE") != len(rows) or len(rows) != classes:
        raise PrimeEngineError("PARI/GP returned an incomplete progression table")
    return {
        "metrics": {
            "Modulus q": str(q),
            "Endpoint x": str(x),
            "Reduced residue classes φ(q)": str(classes),
            "Primes in reduced classes": str(_one(lines, "PROG_TOTAL")),
            "Primes dividing q (excluded)": str(_one(lines, "PROG_EXCLUDED")),
            "li(x)": _decimal(lines, "PROG_LI"),
            "Expected li(x)/φ(q)": _decimal(lines, "PROG_EXPECTED"),
            "Largest deviation in class": str(_one(lines, "PROG_WORST")),
            "Largest absolute deviation": _decimal(lines, "PROG_WORST_DEVIATION"),
        },
        "columns": [
            "Residue a mod q", "π(x; q, a)", "Expected li(x)/φ(q)",
            "Deviation", "Deviation (%)", "Deviation·log x/√x",
        ],
        "rows": rows,
        "classes": classes,
        "chart": "progression-deviation",
        "note": (
            "PARI/GP counted every prime up to x by residue class in one forprime pass "
            "and evaluated li(x) through eint1. li(x)/φ(q) is the expected count under "
            "the prime-number theorem for arithmetic progressions; the deviations shown "
            "are observed, not predicted."
        ),
    }


def _validate_offsets(offsets: Sequence[int]) -> list[int]:
    if not 2 <= len(offsets) <= 32:
        raise ValueError("A prime constellation needs between 2 and 32 offsets")
    ordered = sorted(set(offsets))
    if len(ordered) != len(offsets):
        raise ValueError("Constellation offsets must be distinct")
    if ordered[0] != 0:
        raise ValueError("Constellation offsets must start at 0")
    if ordered[-1] > 4096:
        raise ValueError("The largest constellation offset may not exceed 4,096")
    return ordered


def _singular_series_metrics(lines: list[str]) -> dict[str, str]:
    return {
        "Pattern size k": str(_one(lines, "TUPLE_SIZE")),
        "Pattern diameter": str(_one(lines, "TUPLE_SPAN")),
        "Admissible": "yes" if _one(lines, "ADMISSIBLE") else "no",
        "Singular series 𝔖 (estimate)": _decimal(lines, "SINGULAR_SERIES"),
        "Euler-product cutoff": str(_one(lines, "SINGULAR_CUTOFF")),
        "Rigorous relative tail bound": _decimal(lines, "SINGULAR_TAIL_BOUND"),
        "𝔖 lower bound": _decimal(lines, "SINGULAR_LOW"),
        "𝔖 upper bound": _decimal(lines, "SINGULAR_HIGH"),
    }


_SINGULAR_NOTE = (
    "PARI/GP evaluated the Hardy–Littlewood singular series as a truncated Euler "
    "product over forprime, using Set() to count the occupied residues w(p). The "
    "value is an ESTIMATE; the truncation is bounded rigorously because w(p) = k for "
    "every prime above the pattern diameter, giving |log tail| < k²/P and hence the "
    "stated relative bound exp(k²/P) − 1 with the enclosing interval."
)


def singular_series(offsets: list[int], cutoff: int = 1_000_000, timeout: int = 600) -> dict:
    """Roadmap item 85: Hardy–Littlewood k-tuple singular series."""
    ordered = _validate_offsets(offsets)
    if not 100 <= cutoff <= 100_000_000:
        raise ValueError("The Euler-product cutoff must lie between 100 and 10^8")
    lines = _execute(f"dl_singular_series_report({_vector(ordered)},{cutoff})", timeout)
    obstructions = _records(lines, "OBSTRUCTION", 2)
    metrics = _singular_series_metrics(lines)
    admissible = metrics["Admissible"] == "yes"
    if admissible != (not obstructions):
        raise PrimeEngineError("PARI/GP returned an inconsistent admissibility verdict")
    return {
        "admissible": admissible,
        "metrics": {"Pattern": ", ".join(str(value) for value in ordered), **metrics},
        "columns": ["Property", "Value"],
        "rows": [[key, value] for key, value in metrics.items()],
        "sections": [
            {
                "title": "Admissibility obstructions (a prime whose residues are all covered)",
                "columns": ["Prime p", "Residues occupied w(p)"],
                "rows": obstructions,
            }
        ],
        "obstructions": obstructions,
        "note": (
            _SINGULAR_NOTE
            + (
                ""
                if admissible
                else " The pattern is inadmissible: it covers every residue class modulo the "
                "listed prime, so only finitely many translates can be all-prime and the "
                "singular series is exactly zero."
            )
        ),
    }


def tuple_prediction(
    offsets: list[int],
    start: str = "2",
    end: str = "1000000",
    cutoff: int = 1_000_000,
    timeout: int = 600,
) -> dict:
    """Roadmap item 86: observed versus predicted constellation counts."""
    ordered = _validate_offsets(offsets)
    low, high = decimal_integer(start), decimal_integer(end)
    if not 100 <= cutoff <= 100_000_000:
        raise ValueError("The Euler-product cutoff must lie between 100 and 10^8")
    if low < 2 or high <= low:
        raise ValueError("Require 2 ≤ start < end for the constellation range")
    if high > 10**11:
        raise ValueError("The constellation range may not exceed 10^11")
    counted_by_primesieve = False
    observed = -1
    executable = shutil.which("primesieve")
    pattern = tuple(ordered)
    if executable and pattern in PRIMESIEVE_PATTERNS and high <= _UINT64:
        observed = _primesieve_tuplet_count(
            executable, low, high, PRIMESIEVE_PATTERNS[pattern], timeout
        )
        counted_by_primesieve = True
    lines = _execute(
        f"dl_tuple_prediction({_vector(ordered)},{low},{high},{cutoff},{observed})",
        timeout,
    )
    metrics = _singular_series_metrics(lines)
    engine_flag = _one(lines, "TUPLE_COUNTED_BY")
    if engine_flag != int(not counted_by_primesieve):
        raise PrimeEngineError("PARI/GP disagreed about which engine counted the pattern")
    reported = _one(lines, "TUPLE_OBSERVED")
    if counted_by_primesieve and reported != observed:
        raise PrimeEngineError("PARI/GP did not preserve the primesieve constellation count")
    counter = "primesieve --count" if counted_by_primesieve else "PARI/GP forprime window"
    summary = {
        "Pattern": ", ".join(str(value) for value in ordered),
        "Range": f"{low} … {high}",
        **metrics,
        "Integral ∫ dt/log^k t": _decimal(lines, "TUPLE_INTEGRAL"),
        "Predicted count (estimate)": _decimal(lines, "TUPLE_PREDICTED"),
        "Observed count (exact)": str(reported),
        "Counted by": counter,
        "Observed / predicted": _decimal(lines, "TUPLE_RATIO"),
        "Observed − predicted": _decimal(lines, "TUPLE_DIFFERENCE"),
    }
    return {
        "admissible": metrics["Admissible"] == "yes",
        "observed": reported,
        "counted_by": counter,
        "metrics": summary,
        "columns": ["Property", "Value"],
        "rows": [[key, value] for key, value in summary.items()],
        "note": (
            _SINGULAR_NOTE
            + " The prediction is 𝔖 times PARI's intnum evaluation of ∫ dt/log^k t over the "
            "range and is an ESTIMATE. The observed count is exact and counts only "
            "constellations lying entirely inside the range, the convention primesieve uses."
        ),
    }


def _primesieve_tuplet_count(
    executable: str, start: int, end: int, size: int, timeout: int
) -> int:
    try:
        result = subprocess.run(
            [executable, str(start), str(end), f"--count={size}", "-q", "--no-status"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PrimeEngineError(
            f"primesieve exceeded the {timeout}-second constellation limit"
        ) from exc
    output = result.stdout.strip()
    if result.returncode or not re.fullmatch(r"\d+", output):
        raise PrimeEngineError(
            f"primesieve failed: {(result.stderr.strip() or output)[-1000:]}"
        )
    return int(output)


def bateman_horn(
    polynomials: list[list[str]],
    start: str = "1",
    end: str = "100000",
    cutoff: int = 100_000,
    timeout: int = 600,
) -> dict:
    """Roadmap item 87: Bateman–Horn predictions for user polynomials."""
    if not 1 <= len(polynomials) <= 8:
        raise ValueError("Supply between 1 and 8 polynomials")
    vectors: list[str] = []
    for coefficients in polynomials:
        if not 2 <= len(coefficients) <= 11:
            raise ValueError("Each polynomial needs 2–11 ascending coefficients")
        values = [decimal_integer(item) for item in coefficients]
        if values[-1] <= 0:
            raise ValueError("Each polynomial needs a positive leading coefficient")
        if any(abs(value) > 10**12 for value in values):
            raise ValueError("Polynomial coefficients are limited to 12 digits")
        vectors.append(_vector(values))
    low, high = decimal_integer(start), decimal_integer(end)
    if low < 1 or high <= low:
        raise ValueError("Require 1 ≤ start < end for the Bateman–Horn range")
    if high - low > 1_000_000:
        raise ValueError("The Bateman–Horn range may span at most 1,000,000 integers")
    if not 3 <= cutoff <= 1_000_000:
        raise ValueError("The Bateman–Horn cutoff must lie between 3 and 1,000,000")
    call = f"dl_bateman_horn([{','.join(vectors)}],{low},{high},{cutoff})"
    lines = _execute(call, timeout)
    described = _records(lines, "POLYNOMIAL", 3)
    if len(described) != len(polynomials):
        raise PrimeEngineError("PARI/GP did not describe every requested polynomial")
    hits = _tagged_values(lines, "HIT")
    shown = _one(lines, "BH_SHOWN")
    observed = _one(lines, "BH_OBSERVED")
    if len(hits) != shown or shown > observed:
        raise PrimeEngineError("PARI/GP returned an inconsistent Bateman–Horn hit list")
    fixed = _records(lines, "FIXED_DIVISOR", 2)
    metrics = {
        "Polynomials": str(_one(lines, "BH_POLYNOMIALS")),
        "Range": f"{low} … {high}",
        "Product of degrees": str(_one(lines, "BH_DEGREE_PRODUCT")),
        "Euler-product cutoff": str(_one(lines, "BH_CUTOFF")),
        "Local product ∏(1 − ω(p)/p)/(1 − 1/p)^k (estimate)": _decimal(lines, "BH_PRODUCT"),
        "Bateman–Horn constant C (estimate)": _decimal(lines, "BH_CONSTANT"),
        "Integral ∫ dt/log^k t": _decimal(lines, "BH_INTEGRAL"),
        "Predicted count (estimate)": _decimal(lines, "BH_PREDICTED"),
        "Observed count (exact)": str(observed),
        "Observed / predicted": _decimal(lines, "BH_RATIO"),
        "First n with all values prime": str(_one(lines, "BH_FIRST")),
        "Last n with all values prime": str(_one(lines, "BH_LAST")),
        "Fixed prime divisors found": str(len(fixed)),
    }
    return {
        "metrics": metrics,
        "columns": ["Index", "Irreducible polynomial", "Degree"],
        "rows": described,
        "sections": [
            {
                "title": f"First {shown} values of n with every polynomial prime",
                "columns": ["n"],
                "rows": [[str(value)] for value in hits],
            },
            {
                "title": "Primes dividing every value of the product (the prediction is then 0)",
                "columns": ["Prime p", "Roots ω(p)"],
                "rows": fixed,
            },
        ],
        "hits": [str(value) for value in hits],
        "observed": observed,
        "note": (
            "PARI/GP proved each polynomial irreducible over ℚ with polisirreducible, "
            "counted ω(p) with polrootsmod for every prime up to the cutoff, evaluated "
            "∫ dt/log^k t with intnum, and tested every value with isprime. The "
            "Bateman–Horn constant is an ESTIMATE: unlike the k-tuple singular series its "
            "local factors have no elementary tail bound, because they average to 1 only "
            "through equidistribution, so no rigorous truncation error is claimed."
        ),
    }


_FIROOZBAKHT = {
    "1": "holds",
    "0": "VIOLATED",
    "-1": "p ≤ 29, outside the stated range",
}


def maximal_gap_search(
    start: str = "2",
    end: str = "10000000",
    baseline: int = 0,
    prime_cap: int = 10_000_000,
    timeout: int = 900,
) -> dict:
    """Roadmap items 88–91: bounded record-gap search with merits and bounds."""
    low, high = decimal_integer(start), decimal_integer(end)
    if low < 2 or high <= low:
        raise ValueError("Require 2 ≤ start < end for the record-gap search")
    if high > 10**13:
        raise ValueError("The record-gap search may not scan beyond 10^13")
    if not 0 <= baseline <= 100_000:
        raise ValueError("The record baseline must lie between 0 and 100,000")
    if not 100 <= prime_cap <= 10_000_000_000:
        raise ValueError("The scan cap must lie between 100 and 10^10 primes")
    lines = _execute(f"dl_maximal_gaps({low},{high},{baseline},{prime_cap})", timeout)
    rows = _records(lines, "RECORD", 9)
    checks = _records(lines, "TABLECHECK", 3)
    progress = _records(lines, "PROGRESS", 2)
    if _one(lines, "DONE") != len(rows):
        raise PrimeEngineError("PARI/GP returned an incomplete record-gap table")
    if _one(lines, "RECORD_COUNT") != len(rows):
        raise PrimeEngineError("PARI/GP returned an inconsistent record count")
    if _one(lines, "TABLE_CHECKED") != len(checks):
        raise PrimeEngineError("PARI/GP returned an inconsistent table-verification count")
    truncated = _one(lines, "TRUNCATED") == 1
    applicable = _one(lines, "TABLE_APPLICABLE") == 1
    mismatches = _one(lines, "TABLE_MISMATCHES")
    display = [
        [p, following, gap, merit, cramer, granville, bound,
         _FIROOZBAKHT[verdict], "yes" if found == "1" else "no"]
        for p, following, gap, merit, cramer, granville, bound, verdict, found in rows
    ]
    table_rows = [
        [gap, prime, "confirmed" if status == "1" else "MISMATCH"]
        for gap, prime, status in checks
    ]
    metrics = {
        "Scanned range": f"{low} … {high}",
        "Primes visited": str(_one(lines, "SCANNED")),
        "Last prime visited": str(_one(lines, "LAST_PRIME")),
        "Record gaps found": str(len(rows)),
        "Largest gap found": str(_one(lines, "LARGEST_GAP")),
        "Record baseline": str(baseline),
        "Scan cap (primes)": str(prime_cap),
        "Completed": "no — the scan cap was reached" if truncated else "yes",
        "Resume from": str(_one(lines, "NEXT_START")) if truncated else "not applicable",
        "Published table entries checked": str(len(checks)),
        "Published table agreements": str(_one(lines, "TABLE_AGREEMENTS")),
        "Published table mismatches": str(mismatches),
        "Published table size": str(_one(lines, "TABLE_SIZE")),
        "Progress checkpoints": str(len(progress)),
    }
    if not applicable:
        metrics["Published table verification"] = (
            "skipped — verification requires start = 2 and baseline = 0"
        )
    return {
        "truncated": truncated,
        "complete": not truncated,
        "mismatches": mismatches,
        "table_applicable": applicable,
        "metrics": metrics,
        "columns": [
            "Prime p starting the gap", "Next prime", "Gap g", "Merit g/log p",
            "Cramér–Shanks g/log²p", "Granville g/(2e^−γ log²p)",
            "Firoozbakht bound log²p − log p − 1", "Firoozbakht verdict",
            "In published table",
        ],
        "rows": display,
        "sections": [
            {
                "title": "Published maximal-gap table verification (A002386 / A005250)",
                "columns": ["Published gap", "Published prime", "Result"],
                "rows": table_rows,
            },
            {
                "title": "Search progress checkpoints",
                "columns": ["Prime reached", "Primes visited"],
                "rows": progress,
            },
        ],
        "progress": progress,
        "table_rows": table_rows,
        "chart": "maximal-gaps",
        "note": (
            "PARI/GP scanned the range with forprime, recorded every gap larger than all "
            "earlier ones, and computed each merit and conjectural comparison at 60-digit "
            "precision. Reference table: OEIS A002386 (the prime that starts each maximal "
            "gap) with A005250 (the gap), after Thomas R. Nicely's first-occurrence prime-gap "
            "tables; the embedded copy covers every maximal gap through 4.3·10^9. "
            "Cramér (1936) conjectured limsup g/log²p = 1; Granville (1995) argued the "
            "limsup is at least 2e^−γ = 1.1229…; Kourbatov (2015) showed Firoozbakht's "
            "conjecture implies g < log²p − log p − 1 for every p > 29. Reaching the scan "
            "cap makes the result incomplete, never a proof that no larger gap exists."
        ),
    }


def short_interval_matrix(
    modulus: str = "9699690",
    first_row: str = "1000",
    rows: int = 64,
    length: int = 1000,
    timeout: int = 900,
) -> dict:
    """Roadmap item 92: Maier-matrix style short-interval experiment."""
    q = decimal_integer(modulus)
    k = decimal_integer(first_row)
    if not 2 <= q <= 10**15:
        raise ValueError("The matrix modulus must satisfy 2 ≤ q ≤ 10^15")
    if not 1 <= k <= 10**15:
        raise ValueError("The first matrix row must satisfy 1 ≤ k ≤ 10^15")
    if not 1 <= rows <= 512:
        raise ValueError("Use between 1 and 512 matrix rows")
    if not 2 <= length <= 1_000_000:
        raise ValueError("Row length must lie between 2 and 1,000,000")
    lines = _execute(f"dl_short_interval({q},{k},{rows},{length})", timeout)
    matrix = _records(lines, "MATRIX", 6)
    if _one(lines, "DONE") != len(matrix) or len(matrix) != rows:
        raise PrimeEngineError("PARI/GP returned an incomplete short-interval matrix")
    return {
        "metrics": {
            "Matrix modulus q": str(q),
            "First row k": str(k),
            "Rows": str(_one(lines, "MATRIX_ROWS")),
            "Row length y": str(length),
            "Primes found": str(_one(lines, "MATRIX_TOTAL")),
            "Empty rows": str(_one(lines, "MATRIX_EMPTY")),
            "Mean observed/expected": _decimal(lines, "MATRIX_MEAN_RATIO"),
            "Maximum ratio": _decimal(lines, "MATRIX_MAX_RATIO"),
            "Maximum at row": str(_one(lines, "MATRIX_MAX_ROW")),
            "Minimum ratio": _decimal(lines, "MATRIX_MIN_RATIO"),
            "Minimum at row": str(_one(lines, "MATRIX_MIN_ROW")),
        },
        "columns": [
            "Row k", "Interval start", "Interval end", "Primes",
            "Expected y/log(qk)", "Observed / expected",
        ],
        "rows": matrix,
        "chart": "short-interval",
        "note": (
            "PARI/GP counted the primes in each row interval [qk + 1, qk + y] with forprime "
            "and compared them with the naive expectation y/log(qk). Choosing q as a "
            "primorial reproduces Maier's matrix construction, in which short intervals in "
            "rows coprime to q are systematically richer or poorer than y/log x; the "
            "spread reported here is observed, not predicted."
        ),
    }


def density_surface(
    start: str = "1000000",
    end: str = "2000000",
    blocks: int = 32,
    modulus: str = "30",
    timeout: int = 900,
) -> dict:
    """Roadmap item 93: prime-density surface over position and residue class."""
    low, high = decimal_integer(start), decimal_integer(end)
    q = decimal_integer(modulus)
    if low < 2 or high <= low:
        raise ValueError("Require 2 ≤ start < end for the density surface")
    if high - low > 10**9:
        raise ValueError("A density surface may span at most 10^9 integers")
    if not 1 <= blocks <= 64:
        raise ValueError("Use between 1 and 64 blocks")
    if not 2 <= q <= 256:
        raise ValueError("The residue modulus must satisfy 2 ≤ q ≤ 256")
    lines = _execute(f"dl_density_surface({low},{high},{blocks},{q})", timeout)
    cells = _records(lines, "CELL", 4)
    block_rows = _records(lines, "BLOCK", 3)
    classes = _one(lines, "SURFACE_CLASSES")
    if _one(lines, "DONE") != len(cells) or len(cells) != blocks * classes:
        raise PrimeEngineError("PARI/GP returned an incomplete density surface")
    if len(block_rows) != blocks:
        raise PrimeEngineError("PARI/GP returned an incomplete block index")
    residues = [row[1] for row in cells[:classes]]
    return {
        "metrics": {
            "Range": f"{low} … {high}",
            "Blocks": str(_one(lines, "SURFACE_BLOCKS")),
            "Block width": str(_one(lines, "SURFACE_WIDTH")),
            "Modulus q": str(q),
            "Reduced residue classes φ(q)": str(classes),
            "Primes counted": str(_one(lines, "SURFACE_TOTAL")),
            "Maximum normalised density": _decimal(lines, "SURFACE_MAX_DENSITY"),
        },
        "columns": ["Block", "Residue a mod q", "Primes", "Normalised density"],
        "rows": cells,
        "sections": [
            {
                "title": "Block index",
                "columns": ["Block", "First integer", "Last integer"],
                "rows": block_rows,
            }
        ],
        "blocks": blocks,
        "classes": classes,
        "residues": residues,
        "block_rows": block_rows,
        "chart": "density-surface",
        "note": (
            "PARI/GP made one forprime pass over the range and binned every prime by block "
            "and reduced residue class. The normalised density is count·φ(q)·log(block "
            "start)/width, which tends to 1 under the prime-number theorem for arithmetic "
            "progressions. JavaScript only maps these numbers to colours."
        ),
    }
