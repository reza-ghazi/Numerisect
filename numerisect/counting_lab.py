"""Typed orchestration boundary for the prime-counting and integer-structure laboratory.

Computation attribution.  No mathematical quantity is evaluated in this module;
every number it returns was produced by an engine:

* the six independent prime-counting algorithms come from the **primecount**
  engine, one process each: ``primecount x --legendre``, ``--meissel``,
  ``--lehmer``, ``--lmo``, ``--deleglise-rivat`` and ``--gourdon``.  The
  recomputation with alternative alpha tuning is ``primecount x --double-check``.
* Legendre's ``phi(x, a)`` comes from ``primecount --phi <x> <a>``.
* the exact ``n``-th prime comes from ``primecount n --nth-prime``, and the two
  inverse approximations from ``primecount n --Li-inverse`` and
  ``primecount n --RiemannR-inverse``.
* elapsed times are primecount's own ``--time`` measurement and PARI's own
  ``gettime`` timer.  They are single local measurements on one machine, not a
  benchmark of the algorithms.
* the seventh, engine-independent ``pi(x)`` is **PARI/GP** ``primepi``, used
  while ``x <= PARI_PRIMEPI_LIMIT`` (10^11, about six seconds on the
  development machine).
* every remaining quantity is computed by ``numerisect/counting_lab.gp`` inside
  **PARI/GP**: the agreement analysis (``Set``, ``vecmin``, ``vecmax`` and the
  signed differences), the Legendre product and the identity
  ``pi(x) = phi(x, a) + a - 1`` through ``prime``, ``forprime`` and ``primepi``,
  the n-th prime error terms, the integer-structure predicates
  ``isprimepower``, ``ispseudoprimepower``, ``ispowerful``, ``istotient``,
  ``isfundamental`` and ``ispolygonal``, the residue-class divisor search
  ``divisorslenstra``, and the ``factorint(n, flag)`` strategy race timed by
  ``gettime`` and audited by ``isprime``.

Python validates input, launches the engines, enforces the completion markers,
parses the tagged protocol and hands rows to the report writer.  It never
decides whether the sources agree: PARI does, and this module refuses to
reconcile a disagreement it is handed.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from .evaluator import ExpressionError, evaluate_arbitrary_integer
from .prime_manipulation import decimal_integer
from .primes import PrimeEngineError, _run_gp, _tagged_values

PROGRAM = Path(__file__).with_name("counting_lab.gp")

#: primecount's own documented ceiling for exact pi(x).
PRIMECOUNT_LIMIT = 10**31

#: Legendre's, Meissel's and Lehmer's formulas are the historical, higher
#: complexity members of the family.  They stay comfortably interactive to
#: 10^16 and are refused above it so a comparison cannot silently become a
#: multi-hour run.
ELEMENTARY_LIMIT = 10**16

#: PARI/GP ``primepi`` is an independent implementation, but it sieves: it needs
#: roughly six seconds at 10^11 on the development machine and grows linearly.
#: Above this bound the seventh source is reported as out of range rather than
#: attempted.
PARI_PRIMEPI_LIMIT = 10**11

#: Slug -> (display name, primecount option, is an elementary formula).
ALGORITHMS: dict[str, tuple[str, str, bool]] = {
    "legendre": ("Legendre's formula", "--legendre", True),
    "meissel": ("Meissel's formula", "--meissel", True),
    "lehmer": ("Lehmer's formula", "--lehmer", True),
    "lmo": ("Lagarias–Miller–Odlyzko", "--lmo", False),
    "deleglise-rivat": ("Deléglise–Rivat", "--deleglise-rivat", False),
    "gourdon": ("Gourdon", "--gourdon", False),
}

#: factorint's second argument is a bitmask of methods to AVOID.
FACTORINT_FLAGS: dict[int, str] = {
    0: "Full default strategy: trial division, Pollard–Brent rho, Shanks SQUFOF, ECM, MPQS",
    1: "Avoid MPQS (the multiple-polynomial quadratic sieve)",
    2: "Avoid the first-stage ECM (PARI may still fall back on ECM later)",
    4: "Avoid Pollard–Brent rho and Shanks SQUFOF",
    8: "Skip the final ECM; a huge composite may then be declared prime",
}

_SECONDS = re.compile(r"\d+(?:\.\d+)?")
_DECIMAL = re.compile(r"-?\d+(?:\.\d+)?(?:e[+-]?\d+)?", re.IGNORECASE)

_LOCAL_TIMING_NOTE = (
    "Every elapsed time is a single measurement of one run on this machine, taken by "
    "primecount's own --time option and by PARI's gettime. It reflects this input, this "
    "hardware, this thread count and this build, and it is not a benchmark of the "
    "algorithms."
)



def _integer(text: str) -> int:
    """Accept a decimal integer or a safe integer expression.

    Every other numeric input in the application accepts expressions such as
    ``10^10`` or ``2^61-1``, so these tools do too. Falls back to the strict
    decimal parser so its error message is preserved for plainly bad input.
    """

    try:
        return evaluate_arbitrary_integer(text)
    except ExpressionError:
        return decimal_integer(text)


def _program() -> str:
    try:
        return PROGRAM.read_text(encoding="utf-8")
    except OSError as exc:
        raise PrimeEngineError("The prime-counting PARI/GP program is unavailable") from exc


_USER_ERROR = re.compile(r"user error:\s*(.+)")


def _execute(call: str, timeout: int) -> list[str]:
    """Run one counting_lab.gp entry point and require its completion marker.

    A hypothesis the engine rejects (``gcd(r, s) = 1``, ``s^3 > N``, an
    out-of-range polygonal side count) surfaces as a PARI ``user error``. Those
    are request problems, not engine failures, so they are re-raised as
    ``ValueError`` with PARI's own wording and become a 422 rather than a 500.
    """

    if not 1 <= timeout <= 3600:
        raise ValueError("Engine time limit must be between 1 and 3,600 seconds")
    try:
        lines = _run_gp(f"{_program()}\n{call};", timeout=timeout)
    except PrimeEngineError as exc:
        reported = _USER_ERROR.search(str(exc))
        if reported:
            raise ValueError(reported.group(1).strip()) from exc
        raise
    if not _tagged_values(lines, "DONE"):
        raise PrimeEngineError("PARI/GP returned an incomplete counting-laboratory result")
    return lines


def _one(lines: list[str], tag: str) -> int:
    values = _tagged_values(lines, tag)
    if len(values) != 1:
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} result")
    return values[0]


def _decimal(lines: list[str], tag: str) -> str:
    prefix = f"{tag}:"
    values = [line[len(prefix):] for line in lines if line.startswith(prefix)]
    if len(values) != 1 or not _DECIMAL.fullmatch(values[0]):
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} value")
    return values[0]


def _records(lines: Sequence[str], tag: str, width: int) -> list[list[str]]:
    prefix = f"{tag}:"
    rows = [line[len(prefix):].split("|") for line in lines if line.startswith(prefix)]
    for row in rows:
        if len(row) != width or any(not re.fullmatch(r"-?\d+", value) for value in row):
            raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} record")
    return rows


def _vector(values: Sequence[int]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"


def _primecount(arguments: Sequence[str], timeout: int) -> tuple[int, str]:
    """Run one primecount process and return its integer result and elapsed seconds."""

    # Arguments are validated before the engine is looked for, so an invalid request
    # is reported as invalid whether or not primecount happens to be installed.
    if not 1 <= timeout <= 3600:
        raise ValueError("Engine time limit must be between 1 and 3,600 seconds")
    executable = shutil.which("primecount")
    if not executable:
        raise PrimeEngineError(
            "The primecount engine is required for the prime-counting laboratory"
        )
    try:
        result = subprocess.run(
            [executable, *arguments, "--time"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PrimeEngineError(f"primecount exceeded the {timeout}-second limit") from exc
    reported = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if result.returncode or len(reported) != 2 or not re.fullmatch(r"\d+", reported[0]):
        detail = (result.stderr.strip() or result.stdout.strip())[-1000:]
        raise PrimeEngineError(f"primecount failed: {detail}")
    if not reported[1].startswith("Seconds:"):
        raise PrimeEngineError("primecount did not report an elapsed time")
    seconds = reported[1].split(":", 1)[1].strip()
    if not _SECONDS.fullmatch(seconds):
        raise PrimeEngineError("primecount reported an unreadable elapsed time")
    return int(reported[0]), seconds


def _threads(threads: int) -> str:
    if not 1 <= threads <= 256:
        raise ValueError("Thread count must be between 1 and 256")
    return f"--threads={threads}"


def counting_algorithm_comparison(
    x: str = "10000000000",
    algorithms: Sequence[str] | None = None,
    double_check: bool = True,
    include_pari: bool = True,
    threads: int = 1,
    timeout: int = 900,
) -> dict:
    """Count pi(x) with several independent algorithms and report any disagreement.

    Each selected primecount algorithm runs in its own process, PARI's
    ``primepi`` is added as a seventh independent source while
    ``x <= PARI_PRIMEPI_LIMIT``, and ``numerisect/counting_lab.gp`` performs the
    agreement analysis.  Agreement across independent implementations of
    different formulas is a correctness check no single algorithm can provide,
    so a disagreement is reported prominently and never reconciled here.

    Args:
        x: Decimal upper bound for pi(x).
        algorithms: Slugs from :data:`ALGORITHMS`; all six when omitted.
        double_check: Also run ``primecount x --double-check``.
        include_pari: Also run PARI ``primepi`` when x is within range.
        threads: primecount worker threads.
        timeout: Per-engine time limit in seconds.

    Returns:
        A report dictionary with ``disagreement`` set when the sources differ.

    Raises:
        ValueError: The request is out of bounds.
        PrimeEngineError: An engine is missing, failed, or returned junk.
    """

    selected = list(algorithms) if algorithms is not None else list(ALGORITHMS)
    if not selected:
        raise ValueError("Select at least one prime-counting algorithm")
    if len(set(selected)) != len(selected):
        raise ValueError("Each prime-counting algorithm may be selected only once")
    unknown = [slug for slug in selected if slug not in ALGORITHMS]
    if unknown:
        raise ValueError(f"Unknown prime-counting algorithm: {', '.join(sorted(unknown))}")
    value = _integer(x)
    if not 1 <= value <= PRIMECOUNT_LIMIT:
        raise ValueError("The algorithm comparison supports 1 ≤ x ≤ 10^31")
    elementary = [slug for slug in selected if ALGORITHMS[slug][2]]
    if elementary and value > ELEMENTARY_LIMIT:
        raise ValueError(
            "Legendre's, Meissel's and Lehmer's formulas are limited to x ≤ 10^16 here; "
            "deselect them or lower x"
        )
    thread_option = _threads(threads)

    labels: list[str] = []
    routines: list[str] = []
    counts: list[int] = []
    seconds: list[str] = []
    for slug in selected:
        name, option, _ = ALGORITHMS[slug]
        count, elapsed = _primecount([str(value), option, thread_option], timeout)
        labels.append(name)
        routines.append(f"primecount {option}")
        counts.append(count)
        seconds.append(elapsed)
    if double_check:
        count, elapsed = _primecount([str(value), "--double-check", thread_option], timeout)
        labels.append("Default algorithm, alternative alpha tuning")
        routines.append("primecount --double-check")
        counts.append(count)
        seconds.append(elapsed)
    pari_in_range = value <= PARI_PRIMEPI_LIMIT
    if include_pari and pari_in_range:
        lines = _execute(f"cl_primepi({value})", timeout)
        labels.append("PARI/GP exact prime counter")
        routines.append("PARI/GP primepi")
        counts.append(_one(lines, "PRIMEPI"))
        seconds.append(_decimal(lines, "PRIMEPI_SECONDS"))

    analysis = _execute(f"cl_count_agreement({_vector(counts)})", timeout)
    deltas = _records(analysis, "DELTA", 4)
    distinct = _records(analysis, "VALUE", 2)
    if _one(analysis, "DONE") != len(deltas) or len(deltas) != len(counts):
        raise PrimeEngineError("PARI/GP returned an incomplete agreement analysis")
    agree = _one(analysis, "AGREE") == 1
    consensus = str(_one(analysis, "CONSENSUS"))
    rows = [
        [labels[index], routines[index], delta[1], delta[2],
         "yes" if delta[3] == "1" else "NO", seconds[index]]
        for index, delta in enumerate(deltas)
    ]
    metrics = {
        "x": str(value),
        "Independent sources compared": str(len(counts)),
        "Distinct values returned": str(_one(analysis, "DISTINCT")),
        "All sources agree": "yes" if agree else "NO — SOURCES DISAGREE",
        "Consensus π(x)": consensus,
        "Sources holding the consensus": str(_one(analysis, "CONSENSUS_MULTIPLICITY")),
        "Spread (largest − smallest)": str(_one(analysis, "SPREAD")),
        "primecount threads": str(threads),
        "PARI/GP primepi included": (
            "yes" if include_pari and pari_in_range
            else ("out of range above 10^11" if include_pari else "not requested")
        ),
    }
    note = (
        "Six primecount algorithms are independent implementations of different "
        "prime-counting formulas, and PARI/GP primepi shares no code with any of them. "
        "Agreement between them is a correctness check that no single algorithm can give "
        "for itself. PARI/GP performed the agreement analysis; this application never "
        "reconciles a disagreement. "
        + _LOCAL_TIMING_NOTE
    )
    if not agree:
        note = (
            "DISAGREEMENT: the selected sources did not all return the same π(x). "
            "Treat every value below as unverified and report the mismatch upstream. "
        ) + note
    return {
        "metrics": metrics,
        "columns": [
            "Source", "Routine", "π(x)", "Difference from consensus", "Agrees",
            "Seconds (single local measurement)",
        ],
        "rows": rows,
        "sections": [
            {
                "title": "Distinct values returned",
                "columns": ["π(x)", "Sources reporting it"],
                "rows": distinct,
            }
        ],
        "disagreement": not agree,
        "agree": agree,
        "consensus": consensus,
        "distinct_values": len(distinct),
        "note": note,
    }


def legendre_phi(
    x: str = "1000000",
    a: int = 10,
    threads: int = 1,
    timeout: int = 900,
) -> dict:
    """Legendre's phi(x, a) with the PARI context that explains the value.

    ``primecount --phi <x> <a>`` computes phi; ``counting_lab.gp`` adds the a-th
    prime, the Legendre product and — when ``x < p_(a+1)^2`` — the exact identity
    ``pi(x) = phi(x, a) + a - 1`` verified against PARI ``primepi``.
    """

    value = _integer(x)
    if not 1 <= value <= 10**18:
        raise ValueError("phi(x, a) supports 1 ≤ x ≤ 10^18")
    if not 0 <= a <= 100_000:
        raise ValueError("phi(x, a) supports 0 ≤ a ≤ 100,000")
    thread_option = _threads(threads)
    phi, elapsed = _primecount(["--phi", str(value), str(a), thread_option], timeout)
    lines = _execute(f"cl_phi_context({value},{a},{phi})", timeout)
    applies = _one(lines, "PHI_IDENTITY_APPLIES") == 1
    rows = [
        ["phi(x, a)", str(phi), "primecount --phi"],
        ["a-th prime p_a", str(_one(lines, "PHI_A_TH_PRIME")), "PARI/GP prime"],
        ["Next prime p_(a+1)", str(_one(lines, "PHI_NEXT_PRIME")), "PARI/GP prime"],
        [
            "Legendre product x·∏(1 − 1/p)",
            _decimal(lines, "PHI_LEGENDRE_PRODUCT"),
            "PARI/GP forprime",
        ],
        ["phi(x, a) / Legendre product", _decimal(lines, "PHI_RATIO"), "PARI/GP"],
    ]
    metrics = {
        "x": str(value),
        "a": str(a),
        "phi(x, a)": str(phi),
        "Seconds (single local measurement)": elapsed,
        "Identity π(x) = phi(x, a) + a − 1 applies": "yes" if applies else "no, x ≥ p_(a+1)²",
    }
    if applies:
        exact = _one(lines, "PHI_PI")
        identity = _one(lines, "PHI_IDENTITY_VALUE")
        matched = _one(lines, "PHI_IDENTITY_MATCH") == 1
        rows.append(["phi(x, a) + a − 1", str(identity), "PARI/GP"])
        rows.append(["π(x)", str(exact), "PARI/GP primepi"])
        metrics["Identity verified"] = "yes" if matched else "NO — IDENTITY FAILED"
    return {
        "metrics": metrics,
        "columns": ["Quantity", "Value", "Computed by"],
        "rows": rows,
        "identity_applies": applies,
        "identity_verified": bool(applies and _one(lines, "PHI_IDENTITY_MATCH") == 1),
        "phi": str(phi),
        "note": (
            "phi(x, a) counts the integers in [1, x] divisible by none of the first a "
            "primes; it is the partial sieve at the heart of Legendre's, Meissel's and "
            "Lehmer's formulas. primecount computed it. PARI/GP supplied p_a, the "
            "Legendre product and, while x < p_(a+1)², the exact identity "
            "π(x) = phi(x, a) + a − 1 checked against primepi. Above that window every "
            "surviving integer need not be prime, so the identity is reported as "
            "inapplicable rather than approximated. " + _LOCAL_TIMING_NOTE
        ),
    }


def nth_prime_inverses(
    n: str = "1000000",
    threads: int = 1,
    timeout: int = 900,
) -> dict:
    """Compare Li^-1(n) and R^-1(n) with the exact n-th prime.

    ``primecount n --nth-prime`` gives the exact value; ``--Li-inverse`` and
    ``--RiemannR-inverse`` give the two approximations; ``counting_lab.gp``
    computes every signed and relative error at 60-digit precision.
    """

    index = _integer(n)
    if not 1 <= index <= 10**16:
        raise ValueError("The n-th prime comparison supports 1 ≤ n ≤ 10^16")
    thread_option = _threads(threads)
    exact, exact_seconds = _primecount([str(index), "--nth-prime", thread_option], timeout)
    li_inverse, li_seconds = _primecount([str(index), "--Li-inverse", thread_option], timeout)
    r_inverse, r_seconds = _primecount(
        [str(index), "--RiemannR-inverse", thread_option], timeout
    )
    lines = _execute(
        f"cl_nth_prime_errors({index},{exact},{_vector([li_inverse, r_inverse])})", timeout
    )
    prefix = "ROW:"
    parsed = [line[len(prefix):].split("|") for line in lines if line.startswith(prefix)]
    if _one(lines, "DONE") != len(parsed) or len(parsed) != 2:
        raise PrimeEngineError("PARI/GP returned an incomplete n-th prime comparison")
    for row in parsed:
        if len(row) != 4 or not all(_DECIMAL.fullmatch(field) for field in row):
            raise PrimeEngineError("PARI/GP returned an invalid n-th prime error record")
    names = ["Li⁻¹(n)", "R⁻¹(n)"]
    routines = ["primecount --Li-inverse", "primecount --RiemannR-inverse"]
    measured = [li_seconds, r_seconds]
    closest = _one(lines, "NTH_CLOSEST")
    if not 1 <= closest <= len(names):
        raise PrimeEngineError("PARI/GP returned an invalid closest-approximation index")
    rows = [
        [names[position], routines[position], row[1], row[2], row[3], measured[position]]
        for position, row in enumerate(parsed)
    ]
    return {
        "metrics": {
            "n": str(index),
            "Exact n-th prime": str(exact),
            "Exact value computed by": "primecount --nth-prime",
            "Seconds for the exact value (single local measurement)": exact_seconds,
            "Closest approximation (chosen by PARI/GP)": names[closest - 1],
        },
        "columns": [
            "Approximation", "Routine", "Estimate", "Signed error",
            "Relative error (%)", "Seconds (single local measurement)",
        ],
        "rows": rows,
        "exact": str(exact),
        "note": (
            "primecount computed the exact n-th prime and both inverse approximations; "
            "PARI/GP computed every signed and relative error at 60-digit precision. "
            "Li⁻¹ inverts the Eulerian logarithmic integral and R⁻¹ inverts the Riemann "
            "R function, which is why R⁻¹ is normally the closer of the two. "
            + _LOCAL_TIMING_NOTE
        ),
    }


def integer_structure(number: int, sides: int = 3, timeout: int = 300) -> dict:
    """Run PARI's integer-structure predicates on one integer.

    Every verdict comes from a PARI library routine: ``isprimepower`` (returning
    the exponent), ``ispseudoprimepower``, ``ispowerful``, ``istotient``,
    ``isfundamental`` and ``ispolygonal``.
    """

    if abs(number) > 10**2000:
        raise ValueError("The structure predicates accept integers below 10^2000")
    if not 3 <= sides <= 1_000_000:
        raise ValueError("A polygonal side count must satisfy 3 ≤ s ≤ 1,000,000")
    lines = _execute(f"cl_integer_predicates({number},{sides})", timeout)
    exponent = _one(lines, "PRIMEPOWER")
    pseudo = _one(lines, "PSEUDOPRIMEPOWER")
    powerful = _one(lines, "POWERFUL") == 1
    totient = _one(lines, "TOTIENT") == 1
    fundamental = _one(lines, "FUNDAMENTAL") == 1
    polygonal = _one(lines, "POLYGONAL") == 1
    base = _one(lines, "PRIMEPOWER_BASE")
    pseudo_base = _one(lines, "PSEUDOPRIMEPOWER_BASE")
    witness = _one(lines, "TOTIENT_WITNESS")
    position = _one(lines, "POLYGONAL_INDEX")
    rows = [
        [
            "isprimepower(n)", "PARI/GP isprimepower",
            "yes" if exponent else "no",
            f"n = {base}^{exponent}" if exponent else "not a prime power",
        ],
        [
            "ispseudoprimepower(n)", "PARI/GP ispseudoprimepower",
            "yes" if pseudo else "no",
            f"n = {pseudo_base}^{pseudo} with a pseudo-prime base" if pseudo
            else "not a pseudo-prime power",
        ],
        [
            "ispowerful(n)", "PARI/GP ispowerful",
            "yes" if powerful else "no",
            "every prime valuation is at least 2" if powerful
            else "some prime divides n exactly once",
        ],
        [
            "istotient(n)", "PARI/GP istotient",
            "yes" if totient else "no",
            f"φ({witness}) = n" if totient else "n is a nontotient",
        ],
        [
            "isfundamental(n)", "PARI/GP isfundamental",
            "yes" if fundamental else "no",
            "n is a fundamental discriminant" if fundamental
            else "n is not a fundamental discriminant",
        ],
        [
            f"ispolygonal(n, {sides})", "PARI/GP ispolygonal",
            "yes" if polygonal else "no",
            f"n is the {position}-th {sides}-gonal number" if polygonal
            else f"n is not {sides}-gonal",
        ],
    ]
    return {
        "metrics": {
            "n": str(_one(lines, "PREDICATE_N")),
            "Polygonal side count s": str(sides),
            "Prime-power exponent": str(exponent),
        },
        "columns": ["Predicate", "Routine", "Verdict", "Witness"],
        "rows": rows,
        "prime_power_exponent": exponent,
        "prime_power_base": str(base),
        "is_powerful": powerful,
        "is_totient": totient,
        "totient_witness": str(witness),
        "is_fundamental": fundamental,
        "is_polygonal": polygonal,
        "polygonal_index": str(position),
        "note": (
            "PARI/GP decided every predicate. isprimepower returns the exponent k of "
            "n = p^k rather than a bare flag, ispseudoprimepower repeats the test with a "
            "pseudo-prime base, istotient returns a witness m with φ(m) = n, and "
            "ispolygonal returns the index of n in the s-gonal sequence. Negative and "
            "zero inputs are meaningful only for isfundamental, and the remaining "
            "predicates report 'no' for them."
        ),
    }


def lenstra_divisors(
    number: int, residue: int = 1, modulus: int = 11, timeout: int = 300
) -> dict:
    """List the divisors of N lying in a fixed residue class, by Lenstra's algorithm.

    ``divisorslenstra`` is the PARI routine; it is factoring-adjacent because it
    finds divisors without a full factorization, and it is correct only when
    ``gcd(r, s) = 1`` and ``s^3 > N``.  ``counting_lab.gp`` enforces both.
    """

    if number < 1 or number > 10**200:
        raise ValueError("Lenstra's divisor search requires 1 ≤ N < 10^200")
    if modulus < 2 or modulus > 10**100:
        raise ValueError("The residue modulus must satisfy 2 ≤ s < 10^100")
    if not 0 <= residue < modulus:
        raise ValueError("The residue must satisfy 0 ≤ r < s")
    lines = _execute(f"cl_divisors_lenstra({number},{residue},{modulus})", timeout)
    found = _records(lines, "DIVISOR", 3)
    if _one(lines, "DONE") != len(found):
        raise PrimeEngineError("PARI/GP returned an incomplete Lenstra divisor list")
    rows = [
        [row[0], row[1], "yes" if row[2] == "1" else "no"] for row in found
    ]
    return {
        "metrics": {
            "N": str(_one(lines, "LENSTRA_N")),
            "Residue class": f"{residue} mod {modulus}",
            "Divisors of N in total (τ)": str(_one(lines, "LENSTRA_TAU")),
            "Divisors in this class": str(_one(lines, "LENSTRA_FOUND")),
        },
        "columns": ["Divisor d", "Cofactor N/d", "d is prime"],
        "rows": rows,
        "found": len(rows),
        "note": (
            "PARI/GP ran divisorslenstra, Lenstra's algorithm for the divisors of N "
            "congruent to r modulo s. The algorithm is only correct when gcd(r, s) = 1 "
            "and s³ > N, so the engine refuses any other request instead of returning a "
            "silently incomplete list. isprime labelled each divisor."
        ),
    }


def factorint_strategies(
    number: int, flags: Sequence[int] | None = None, timeout: int = 900
) -> dict:
    """Factor one integer under several factorint strategy masks and time each run.

    ``factorint(n, flag)`` is the PARI routine; the flag is a bitmask of methods
    to AVOID.  PARI's ``gettime`` measures each run and ``isprime`` audits every
    returned base.
    """

    masks = list(flags) if flags is not None else [0, 1, 2, 4, 8]
    if not masks:
        raise ValueError("Select at least one factorint strategy mask")
    if len(set(masks)) != len(masks):
        raise ValueError("Each factorint strategy mask may be selected only once")
    if any(not 0 <= mask <= 15 for mask in masks):
        raise ValueError("A factorint strategy mask must lie between 0 and 15")
    if number < 2 or number > 10**80:
        raise ValueError("The strategy race requires 2 ≤ n < 10^80")
    lines = _execute(f"cl_factorint_strategies({number},{_vector(masks)})", timeout)
    strategies = _records(lines, "STRATEGY", 5)
    factors = _records(lines, "FACTOR", 4)
    if _one(lines, "DONE") != len(strategies) or len(strategies) != len(masks):
        raise PrimeEngineError("PARI/GP returned an incomplete factorint strategy race")
    rows = [
        [
            row[0],
            FACTORINT_FLAGS.get(int(row[0]), "Combined mask"),
            row[1],
            row[2],
            "yes" if row[3] == "1" else "NO",
            "yes" if row[4] == "1" else "NO — a base is composite",
        ]
        for row in strategies
    ]
    factor_rows = [
        [row[0], row[1], row[2], "yes" if row[3] == "1" else "no"] for row in factors
    ]
    grouped: dict[str, list[tuple[str, str]]] = {}
    for row in factors:
        grouped.setdefault(row[0], []).append((row[1], row[2]))
    signatures = {tuple(sorted(items)) for items in grouped.values()}
    return {
        "metrics": {
            "n": str(number),
            "Strategy masks run": str(len(strategies)),
            "All masks returned the same factorization": "yes" if len(signatures) <= 1 else "NO",
            "Fastest mask (this run, this machine)": min(
                strategies, key=lambda row: int(row[1])
            )[0],
        },
        "columns": [
            "factorint flag", "Methods avoided", "Milliseconds (single local measurement)",
            "Distinct bases", "Product equals n", "Every base certified prime",
        ],
        "rows": rows,
        "sections": [
            {
                "title": "Factor bases per mask",
                "columns": ["Flag", "Base", "Exponent", "Base is prime"],
                "rows": factor_rows,
            }
        ],
        "note": (
            "PARI/GP factored n once per mask. The second argument of factorint is a "
            "bitmask of methods to AVOID: 1 avoids MPQS, 2 avoids the first-stage ECM "
            "(PARI may still fall back on ECM later), 4 avoids Pollard–Brent rho and "
            "Shanks SQUFOF, and 8 skips the final ECM, after which a huge composite may "
            "be declared prime — the 'every base certified prime' column is what exposes "
            "that. PARI implements SQUFOF internally, inside factorint, but exposes no "
            "standalone entry point for it, so mask 4 is the only handle on it. "
            + _LOCAL_TIMING_NOTE
        ),
    }
