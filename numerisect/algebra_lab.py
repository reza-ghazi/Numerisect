"""Typed orchestration boundary for the native PARI/GP algebra laboratory.

The mathematics lives entirely in :mod:`numerisect/algebra_lab.gp`, which is a thin
driver over PARI/GP's own routines.  This module validates requests, renders them into
a single PARI/GP call, launches ``gp`` through :func:`numerisect.primes._run_gp`, and
parses the tagged ``TAG:value`` protocol back into report dictionaries.  No arithmetic
on a mathematical quantity happens here: Python only bounds inputs, renders validated
integers into a GP vector literal, parses tags, formats labels, and re-checks a few
engine invariants defensively.

Which PARI/GP routine performs each computation
-----------------------------------------------

===========================  =================================================================
Feature (roadmap item)       PARI/GP routines
===========================  =================================================================
Reciprocity trace (45)       ``kronecker`` (cross-check), ``valuation``, ``gcd``, ``isprime``.
                             The reduction steps themselves are written out on purpose --
                             the whole point of the tool is to show them -- and the
                             accumulated sign is verified against ``kronecker``.
Congruences (48)             ``factor``, ``polrootsmod`` (roots modulo each prime),
                             ``chinese`` (recombination), ``deriv``/``subst`` (Hensel step
                             and verification).  PARI has no routine for *all* roots modulo
                             ``p^k``: ``polrootspadic`` returns only the p-adically liftable
                             roots and misses singular ones such as 3 and 5 for
                             ``x^2-1`` mod 8, so the digit-by-digit lift is required and
                             mirrors the existing ``nt_hensel_roots`` implementation.
Discrete logarithms (50)     ``znlog`` (the ``native`` algorithm), ``znorder``, ``factor``,
                             ``chinese``.  The BSGS, Pohlig-Hellman, and Pollard-rho paths
                             are written out deliberately because the tool exists to compare
                             the algorithms and their step counts; every answer is verified
                             by re-exponentiating in the group.
Finite fields (57)           ``ffinit``, ``ffgen``, ``fforder``, ``ffprimroot``, ``minpoly``,
                             ``polisirreducible``, and native ``t_FFELT`` arithmetic.
Divisors and lattice (61)    ``factor``, ``divisors``, ``sigma``, ``numdiv``, ``bigomega``,
                             ``isprime``.
Smoothness/roughness (68)    ``factor``.
Divisor records (69)         ``numdiv``, ``sigma``, ``nextprime``, ``log`` at 80 digits.
                             No library enumerates highly composite or colossally abundant
                             numbers; the candidate sieve and the epsilon-interval test are
                             the definitions of the families, evaluated with PARI functions.
Abundance and weird (70)     ``sigma``, ``divisors``, and PARI's arbitrary-precision bit
                             operations ``shift``/``bitor``/``bitand``/``bittest`` for the
                             subset-sum decision.  No library exposes a subset-sum routine.
Amicable/sociable (71)       ``sigma``.
Cornacchia (74)              ``qfbsolve`` and ``qfbcornacchia`` (cross-checks),
                             ``polrootsmod`` via the item-48 root solver, ``issquare``,
                             ``sqrtint``, ``fordiv``.  The Euclidean descent is written out
                             because the tool exists to trace it, and the resulting solution
                             set is compared with ``qfbsolve``'s as a set.
Quadratic rings (110-111)    ``core``, ``quaddisc``, ``quadgen``, ``norm``, ``trace``,
                             ``quadunit``, ``quadclassunit``, ``bnfinit``, ``bnfcertify``,
                             ``kronecker``, ``idealprimedec``, ``bnfisprincipal``,
                             ``nfbasistoalg``.
Number fields (112-113)      ``nfinit`` (with ``K.zk``/``K.disc``/``K.index`` from
                             ``nfbasis``/``nfdisc``), ``idealprimedec``, ``idealfactor``,
                             ``nfeltnorm``, ``polgalois``, ``bnfinit``, ``bnfcertify``.
Chebotarev (115)             ``factormod``, ``polgalois``, ``nfsplitting``, ``nfgaloisconj``,
                             ``permcycles``, ``partitions``.  ``galoisconjclasses`` is not
                             used because it needs ``galoisinit``, which PARI restricts to
                             weakly super-solvable groups and therefore cannot cover the
                             degree-<=7 groups supported here; tallying cycle types over the
                             automorphisms returned by ``nfgaloisconj`` is complete.  For
                             ``S_n`` and ``A_n`` the class sizes come from the closed-form
                             cycle-type identity so that no splitting field of degree ``n!``
                             is required.
===========================  =================================================================

Every operation is bounded.  A run that exceeds its bound (engine timeout, iteration
cap, class-group certification budget, or enumeration limit) is reported as
*inconclusive*: it never degrades into an empty successful result.

Resource limits enforced here:

======================  =====================================================
Bound                   Value
======================  =====================================================
Engine timeout          1 to 3,600 seconds (per-operation default below)
Polynomial degree       64 (congruences), 12 (number fields), 7 (Chebotarev)
Coefficient magnitude   1,000 decimal digits (congruences), 30 (number fields)
Field characteristic    < 2^64; extension degree m <= 16
Trace / result limits   0 to 100,000 rows
Discrete-log steps      1 to 100,000,000 group operations
======================  =====================================================
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Sequence

from .prime_manipulation import decimal_integer
from .primes import PrimeEngineError, _run_gp, _tagged_values

PROGRAM = Path(__file__).with_name("algebra_lab.gp")

#: Characters PARI/GP may emit inside a plain value column.
_SAFE_TEXT = re.compile(r"[0-9A-Za-z_+*/^()., \[\]~-]+")
#: Wider set for human-readable explanations and Galois-group labels.
_SAFE_LABEL = re.compile(r"[0-9A-Za-z_+*/^()., :=\[\]~-]+")

_DLOG_ALGORITHMS: dict[str, int] = {
    "bsgs": 0,
    "pohlig_hellman": 1,
    "pollard_rho": 2,
    "native": 3,
}
_DLOG_LABELS: dict[str, str] = {
    "bsgs": "Baby-step/giant-step",
    "pohlig_hellman": "Pohlig–Hellman with baby-step/giant-step sub-logarithms",
    "pollard_rho": "Pollard rho for logarithms",
    "native": "PARI/GP znlog",
}

MAX_STEP_LIMIT = 100_000_000
MAX_CONGRUENCE_DEGREE = 64
MAX_CONGRUENCE_DIGITS = 1_000
MAX_FIELD_DEGREE = 12
MAX_FIELD_COEFFICIENT_DIGITS = 30
MAX_CHEBOTAREV_DEGREE = 7
MAX_EXTENSION_DEGREE = 16


def _program() -> str:
    try:
        return PROGRAM.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - packaging failure
        raise PrimeEngineError("The PARI/GP algebra laboratory is unavailable") from exc


def _execute(call: str, timeout: int) -> list[str]:
    """Run one algebra-laboratory call and return its tagged output lines.

    Args:
        call: The complete PARI/GP call, already rendered from validated integers.
        timeout: Wall-clock limit in seconds, between 1 and 3,600.

    Returns:
        Every non-empty stripped output line.

    Raises:
        ValueError: If ``timeout`` is outside the documented range.
        PrimeEngineError: If ``gp`` failed or omitted the mandatory ``DONE:`` marker.
    """
    if not 1 <= timeout <= 3600:
        raise ValueError("Engine time limit must be between 1 and 3,600 seconds")
    lines = _run_gp(f"{_program()}\n{call};", timeout=timeout)
    if not _tagged_values(lines, "DONE"):
        raise PrimeEngineError("PARI/GP returned an incomplete algebra-laboratory result")
    return lines


def _one(lines: list[str], tag: str) -> int:
    values = _tagged_values(lines, tag)
    if len(values) != 1:
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} result")
    return values[0]


def _optional(lines: list[str], tag: str) -> int | None:
    values = _tagged_values(lines, tag)
    if len(values) > 1:
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} result")
    return values[0] if values else None


def _records(
    lines: Iterable[str], tag: str, width: int, pattern: re.Pattern[str] = _SAFE_TEXT
) -> list[list[str]]:
    prefix = f"{tag}:"
    rows = [line[len(prefix):].split("|") for line in lines if line.startswith(prefix)]
    if any(
        len(row) != width or any(not pattern.fullmatch(value) for value in row)
        for row in rows
    ):
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} record")
    return rows


def _text(lines: list[str], tag: str, pattern: re.Pattern[str] = _SAFE_LABEL) -> str | None:
    prefix = f"{tag}:"
    values = [line[len(prefix):] for line in lines if line.startswith(prefix)]
    if len(values) > 1 or (values and not pattern.fullmatch(values[0])):
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} value")
    return values[0] if values else None


def _yes(value: int) -> str:
    return "yes" if value else "no"


def _signed(coefficient: str, symbol: str) -> str:
    """Render ``a + bω`` style terms without a doubled sign."""
    return f"− {coefficient[1:]}{symbol}" if coefficient.startswith("-") else f"+ {coefficient}{symbol}"


def _three_way(value: int) -> str:
    return {1: "yes", 0: "no", -1: "inconclusive"}.get(value, "inconclusive")


def _coefficients(
    values: Sequence[str], *, maximum_degree: int, maximum_digits: int, label: str
) -> list[int]:
    """Validate an ascending coefficient list and return it as Python integers.

    Args:
        values: Decimal coefficient strings, constant term first.
        maximum_degree: Largest permitted polynomial degree.
        maximum_digits: Largest permitted decimal length of any single coefficient.
        label: Name used in error messages.

    Returns:
        The coefficients as integers, constant term first, with a nonzero leader.

    Raises:
        ValueError: If the list is empty, too long, has a zero leading coefficient,
            or contains a coefficient outside the documented magnitude bound.
    """
    if not 2 <= len(values) <= maximum_degree + 1:
        raise ValueError(
            f"Supply 2 to {maximum_degree + 1} {label} coefficients in ascending order"
        )
    numbers = [decimal_integer(value) for value in values]
    if any(len(str(abs(number))) > maximum_digits for number in numbers):
        raise ValueError(
            f"Each {label} coefficient must have at most {maximum_digits:,} decimal digits"
        )
    if numbers[-1] == 0:
        raise ValueError("The leading coefficient must be nonzero")
    return numbers


def _vector(values: Sequence[int]) -> str:
    """Render validated integers as a PARI/GP vector literal."""
    return "[" + ",".join(str(value) for value in values) + "]"


# ------------------------------------------------------------------ item 45
def reciprocity_trace(a: str, n: str, trace_limit: int = 1_000, timeout: int = 60) -> dict:
    """Trace the Jacobi-symbol reduction of ``(a/n)`` step by step.

    Every step is one rule of quadratic reciprocity: reduction modulo ``n``, extraction
    of the power of two through the supplementary law, or the reciprocity flip itself.
    PARI/GP cross-checks the accumulated sign against its native ``kronecker``.

    Args:
        a: Decimal numerator, any sign, arbitrary size.
        n: Decimal denominator; must be a positive odd integer.
        trace_limit: Maximum number of trace rows to materialize (0–100,000).
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary with ``metrics``, ``columns``, ``rows`` and ``truncated``.

    Raises:
        ValueError: If the trace limit is out of range or the inputs are not integers.
        PrimeEngineError: If PARI/GP failed or its own cross-check disagreed.
    """
    numerator, denominator = decimal_integer(a), decimal_integer(n)
    if not 0 <= trace_limit <= 100_000:
        raise ValueError("Trace limit must be between 0 and 100,000")
    lines = _execute(f"al_reciprocity({numerator},{denominator},{trace_limit})", timeout)
    rows = _records(lines, "STEP", 6, _SAFE_LABEL)
    if _one(lines, "DONE") != len(rows):
        raise PrimeEngineError("PARI/GP returned an incomplete reciprocity trace")
    if _one(lines, "VERIFIED") != 1:
        raise PrimeEngineError("PARI/GP could not verify the reciprocity trace")
    value = _one(lines, "VALUE")
    legendre = _one(lines, "LEGENDRE_AVAILABLE") == 1
    return {
        "metrics": {
            "Numerator a": str(numerator),
            "Denominator n": str(denominator),
            "Symbol value": str(value),
            "Native kronecker(a, n)": str(_one(lines, "KRONECKER")),
            "Trace verified": "yes",
            "Legendre symbol applicable": _yes(legendre),
            "Reduction steps": str(_one(lines, "STEPS")),
        },
        "columns": ["Step", "Rule", "a", "n", "Factor", "Explanation"],
        "rows": rows,
        "truncated": _one(lines, "TRUNCATED") == 1,
        "note": (
            "PARI/GP applied quadratic reciprocity, the supplementary law for 2, and "
            "modular reduction, then independently confirmed the accumulated sign against "
            "its native Kronecker symbol. "
            + (
                "The denominator is an odd prime, so this Jacobi symbol is also the "
                "Legendre symbol and therefore decides quadratic residuosity."
                if legendre
                else "The denominator is not an odd prime, so the value is a Jacobi symbol: "
                "+1 does not by itself prove that a is a quadratic residue."
            )
        ),
    }


# ------------------------------------------------------------------ item 48
def congruence_solutions(
    coefficients: list[str], modulus: str, limit: int = 10_000, timeout: int = 60
) -> dict:
    """Solve a linear or polynomial congruence modulo an arbitrary composite.

    PARI/GP factors the modulus, solves modulo each prime, lifts by Hensel's lemma
    (branching over every digit at a singular root), and recombines with the Chinese
    remainder theorem.

    Args:
        coefficients: Ascending decimal coefficients, constant term first.
        modulus: Decimal modulus, at least 2.
        limit: Maximum number of residues to materialize (1–100,000).
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary; ``complete`` is ``False`` when the singular Hensel tree
        exceeded the configured cap, which makes the solution count inconclusive.

    Raises:
        ValueError: If the coefficient list or the modulus is out of range.
        PrimeEngineError: If PARI/GP failed or returned an inconsistent solution set.
    """
    values = _coefficients(
        coefficients,
        maximum_degree=MAX_CONGRUENCE_DEGREE,
        maximum_digits=MAX_CONGRUENCE_DIGITS,
        label="congruence",
    )
    m = decimal_integer(modulus)
    if m < 2:
        raise ValueError("The congruence modulus must be at least 2")
    if not 1 <= limit <= 100_000:
        raise ValueError("Result limit must be between 1 and 100,000")
    lines = _execute(f"al_congruence({_vector(values)},{m},{limit})", timeout)
    roots = _tagged_values(lines, "SOLUTION")
    count = _one(lines, "SOLUTION_COUNT")
    complete = _one(lines, "COMPLETE") == 1
    if _one(lines, "DONE") != len(roots):
        raise PrimeEngineError("PARI/GP returned an incomplete congruence solution set")
    if complete and len(roots) != min(count, limit):
        raise PrimeEngineError("PARI/GP returned an inconsistent congruence solution count")
    polynomial = _text(lines, "POLYNOMIAL", _SAFE_TEXT)
    reduced = _text(lines, "REDUCED", _SAFE_TEXT)
    if polynomial is None or reduced is None:
        raise PrimeEngineError("PARI/GP returned an invalid congruence polynomial")
    prime_powers = _records(lines, "PRIME_POWER", 4)
    breakdown = " × ".join(
        f"{p}^{e}: " + ("inconclusive" if roots_count == "-1" else f"{roots_count} root(s)")
        for p, e, roots_count, _ in prime_powers
    )
    return {
        "complete": complete,
        "metrics": {
            "Polynomial": polynomial,
            "Reduced modulo m": reduced,
            "Modulus": str(m),
            "Solution count": str(count) if complete else "inconclusive",
            "Prime-power breakdown": breakdown or "none",
        },
        "columns": [f"Residue x with P(x) ≡ 0 (mod {m})"],
        "rows": [[str(root)] for root in roots],
        "prime_powers": [
            {
                "prime": p,
                "exponent": e,
                "roots": "inconclusive" if roots_count == "-1" else roots_count,
                "complete": done == "1",
            }
            for p, e, roots_count, done in prime_powers
        ],
        "truncated": _one(lines, "TRUNCATED") == 1,
        "note": (
            "PARI/GP factored the modulus, solved modulo each prime power by Hensel "
            "lifting, and recombined every branch with the Chinese remainder theorem. "
            "Each displayed residue was substituted back into the polynomial and verified."
            if complete
            else "The singular Hensel branching exceeded the configured root cap, so the "
            "total number of solutions is inconclusive rather than zero."
        ),
    }


# ------------------------------------------------------------------ item 50
def discrete_logarithm_lab(
    target: str,
    base: str,
    modulus: str,
    algorithm: str = "bsgs",
    step_limit: int = 1_000_000,
    timeout: int = 60,
) -> dict:
    """Solve ``base^x ≡ target (mod n)`` with a selectable algorithm and a step budget.

    Args:
        target: Decimal target residue; must be a unit modulo ``modulus``.
        base: Decimal base; must be a unit modulo ``modulus``.
        modulus: Decimal modulus, at least 2.
        algorithm: One of ``bsgs``, ``pohlig_hellman``, ``pollard_rho`` or ``native``.
        step_limit: Maximum number of group operations (1–100,000,000).
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary whose ``status`` is ``solved``, ``no solution`` or
        ``inconclusive``.  A step budget exhausted before a decision is inconclusive.

    Raises:
        ValueError: If the algorithm name or the step limit is invalid.
        PrimeEngineError: If PARI/GP failed or reported an unknown status.
    """
    if algorithm not in _DLOG_ALGORITHMS:
        raise ValueError(
            "Algorithm must be bsgs, pohlig_hellman, pollard_rho, or native"
        )
    if not 1 <= step_limit <= MAX_STEP_LIMIT:
        raise ValueError(f"Step limit must be between 1 and {MAX_STEP_LIMIT:,}")
    h, g, n = (decimal_integer(value) for value in (target, base, modulus))
    lines = _execute(
        f"al_dlog({h},{g},{n},{_DLOG_ALGORITHMS[algorithm]},{step_limit})", timeout
    )
    status = _one(lines, "STATUS")
    if status not in {-1, 0, 1}:
        raise PrimeEngineError("PARI/GP returned an unknown discrete-logarithm status")
    limit_reached = _one(lines, "LIMIT_REACHED") == 1
    logarithm = _optional(lines, "LOG")
    if (status == 1) != (logarithm is not None):
        raise PrimeEngineError("PARI/GP returned an inconsistent discrete logarithm")
    verdict = "solved" if status == 1 else ("inconclusive" if limit_reached else "no solution")
    order = _one(lines, "ORDER")
    baby = _tagged_values(lines, "BABY_STEPS")
    giant = _tagged_values(lines, "GIANT_STEPS")
    sublogs = _records(lines, "SUBLOG", 4)
    rows = [["Order of the base g", str(order)]]
    if baby:
        rows.append(["Baby-step block sizes", ", ".join(map(str, baby))])
    if giant:
        rows.append(["Giant-step blocks searched", ", ".join(map(str, giant))])
    rows += [
        [f"x mod {q}^{e}", "not reached" if digit == "-1" else digit]
        for q, e, digit, _ in sublogs
    ]
    rows.append(["Group operations used", str(_one(lines, "STEPS"))])
    rows.append([
        "Least logarithm x",
        str(logarithm) if logarithm is not None else verdict,
    ])
    return {
        "status": verdict,
        "metrics": {
            "Modulus n": str(n),
            "Base g": str(_one(lines, "BASE")),
            "Target h": str(_one(lines, "TARGET")),
            "Order of g": str(order),
            "Algorithm": _DLOG_LABELS[algorithm],
            "Group operations used": str(_one(lines, "STEPS")),
            "Step budget": str(step_limit),
            "Step budget exhausted": _yes(limit_reached),
            "Least logarithm": str(logarithm) if logarithm is not None else verdict,
            "Baby-step blocks": ", ".join(map(str, baby)) or "not applicable",
            "Giant-step blocks": ", ".join(map(str, giant)) or "not applicable",
            "Collision restarts": str(_optional(lines, "COLLISIONS") or 0),
        },
        "columns": ["Stage", "Value"],
        "rows": rows,
        "sub_logarithms": [
            {"prime": q, "exponent": e, "value": digit, "digits": levels}
            for q, e, digit, levels in sublogs
        ],
        "note": (
            f"PARI/GP solved g^x ≡ h (mod {n}) with {_DLOG_LABELS[algorithm]} and verified "
            "the exponent by re-exponentiating in the group."
            if verdict == "solved"
            else (
                "The configured step budget was exhausted before the search could decide. "
                "This is inconclusive, not a proof that no logarithm exists."
                if verdict == "inconclusive"
                else "The search covered the entire cyclic subgroup generated by the base, "
                "so no logarithm exists."
            )
        ),
    }


# ------------------------------------------------------------------ item 57
def finite_field_arithmetic(
    characteristic: str,
    degree: int,
    modulus_coefficients: list[str],
    a_coefficients: list[str],
    b_coefficients: list[str],
    exponent: int = 2,
    timeout: int = 60,
) -> dict:
    """Compute in ``F_p`` or ``F_{p^m}`` with an optional user-supplied modulus.

    Args:
        characteristic: Decimal prime ``p``; must be proven prime and below ``2^64``.
        degree: Extension degree ``m`` between 1 and 16.
        modulus_coefficients: Ascending coefficients of a degree-``m`` irreducible
            polynomial over ``F_p``.  An empty list asks PARI/GP for ``ffinit``.
        a_coefficients: Ascending coordinates of the first element in the power basis.
        b_coefficients: Ascending coordinates of the second element.
        exponent: Integer exponent applied to the first element.
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary listing both elements, their orders, minimal polynomials,
        Frobenius images, and the four field operations plus a power.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP failed or returned inconsistent records.
    """
    p = decimal_integer(characteristic)
    if not 2 <= p < 2**64:
        raise ValueError("The field characteristic must be a prime below 2^64")
    if not 1 <= degree <= MAX_EXTENSION_DEGREE:
        raise ValueError(f"The extension degree must be between 1 and {MAX_EXTENSION_DEGREE}")
    if not -10**6 <= exponent <= 10**6:
        raise ValueError("The exponent must be between -1,000,000 and 1,000,000")
    if modulus_coefficients:
        modulus = _coefficients(
            modulus_coefficients,
            maximum_degree=MAX_EXTENSION_DEGREE,
            maximum_digits=MAX_FIELD_COEFFICIENT_DIGITS,
            label="modulus",
        )
        if len(modulus) != degree + 1:
            raise ValueError("The modulus polynomial must have exactly degree m")
    else:
        modulus = []
    coordinates = []
    for values, label in ((a_coefficients, "element a"), (b_coefficients, "element b")):
        if not 1 <= len(values) <= degree:
            raise ValueError(f"Supply 1 to {degree} coordinates for {label}")
        numbers = [decimal_integer(value) for value in values]
        if any(len(str(abs(number))) > MAX_FIELD_COEFFICIENT_DIGITS for number in numbers):
            raise ValueError(
                f"Each coordinate of {label} must have at most "
                f"{MAX_FIELD_COEFFICIENT_DIGITS} decimal digits"
            )
        coordinates.append(numbers)
    lines = _execute(
        f"al_finite_field({p},{degree},{_vector(modulus)},"
        f"{_vector(coordinates[0])},{_vector(coordinates[1])},{exponent})",
        timeout,
    )
    elements = {row[0]: row for row in _records(lines, "ELEMENT", 3)}
    orders = {row[0]: row for row in _records(lines, "ORDER", 3)}
    minimal = {row[0]: row for row in _records(lines, "MINPOLY", 2)}
    frobenius = {row[0]: row for row in _records(lines, "FROBENIUS", 2)}
    results = {row[0]: row[1] for row in _records(lines, "RESULT", 2)}
    if set(elements) != {"a", "b"}:
        raise PrimeEngineError("PARI/GP returned an incomplete finite-field element list")
    generator_order = _one(lines, "GENERATOR_ORDER")
    rows = [["sum a + b", results.get("sum", "undefined")],
            ["difference a − b", results.get("difference", "undefined")],
            ["product a · b", results.get("product", "undefined")],
            ["quotient a / b", results.get("quotient", "undefined (b is zero)")],
            [f"power a^{exponent}", results.get("power", "undefined (a is zero)")]]
    for name in ("a", "b"):
        rows.append([f"minimal polynomial of {name}", minimal.get(name, ["", "not defined"])[1]])
        rows.append([f"Frobenius {name}^p", frobenius.get(name, ["", "not defined"])[1]])
    modulus_text = _text(lines, "MODULUS", _SAFE_TEXT)
    return {
        "metrics": {
            "Characteristic p": str(p),
            "Extension degree m": str(degree),
            "Field order p^m": str(_one(lines, "FIELD_ORDER")),
            "Reduction polynomial (ascending)": modulus_text or "not reported",
            "Element a (ascending)": elements["a"][1],
            "Element b (ascending)": elements["b"][1],
            "Order of a": orders["a"][1] if "a" in orders else "zero has no order",
            "a is primitive": _yes(int(orders["a"][2])) if "a" in orders else "no",
            "Order of b": orders["b"][1] if "b" in orders else "zero has no order",
            "b is primitive": _yes(int(orders["b"][2])) if "b" in orders else "no",
            "Primitive element (ascending)": _text(lines, "PRIMITIVE_ELEMENT", _SAFE_TEXT) or "",
            "Order of the modulus root": (
                str(generator_order) if generator_order else "not applicable"
            ),
        },
        "columns": ["Operation", "Result (ascending coordinates)"],
        "rows": rows,
        "note": (
            f"PARI/GP built F_{p}^{degree} with an irreducible reduction polynomial, "
            "verified irreducibility, and performed every operation in the native "
            "t_FFELT representation.  Coordinates are listed constant term first in the "
            "power basis of the reduction polynomial's root."
        ),
    }


# ------------------------------------------------------------------ item 61
def divisor_lattice(
    n: str, divisor_limit: int = 10_000, lattice_cap: int = 1_000, timeout: int = 60
) -> dict:
    """Enumerate every divisor of ``n`` with factor pairs and the divisor lattice.

    Args:
        n: Decimal positive integer.
        divisor_limit: Maximum number of divisor rows to materialize (1–100,000).
        lattice_cap: Maximum divisor count for which the covering relation (the Hasse
            diagram of the divisor lattice) is emitted (0–20,000).
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary containing divisor rows, factor pairs, and lattice edges.

    Raises:
        ValueError: If a bound is violated.
        PrimeEngineError: If PARI/GP failed or returned inconsistent counts.
    """
    value = decimal_integer(n)
    if value < 1:
        raise ValueError("Divisor enumeration requires a positive integer")
    if not 1 <= divisor_limit <= 100_000:
        raise ValueError("Divisor limit must be between 1 and 100,000")
    if not 0 <= lattice_cap <= 20_000:
        raise ValueError("Lattice cap must be between 0 and 20,000")
    lines = _execute(f"al_divisor_lattice({value},{divisor_limit},{lattice_cap})", timeout)
    divisors = _records(lines, "DIVISOR", 4)
    if _one(lines, "DONE") != len(divisors):
        raise PrimeEngineError("PARI/GP returned an incomplete divisor enumeration")
    edges = _records(lines, "EDGE", 3)
    if _one(lines, "EDGE_COUNT") != len(edges):
        raise PrimeEngineError("PARI/GP returned an incomplete divisor lattice")
    lattice_complete = _one(lines, "LATTICE_COMPLETE") == 1
    factors = _records(lines, "PRIME", 2)
    return {
        "metrics": {
            "Integer": str(value),
            "Factorization": " × ".join(
                f"{p}^{e}" if e != "1" else p for p, e in factors
            ) or "1",
            "Divisor count τ(n)": str(_one(lines, "DIVISOR_COUNT")),
            "Divisor sum σ(n)": str(_one(lines, "SIGMA")),
            "Lattice covering edges": str(len(edges)) if lattice_complete else "not enumerated",
        },
        "columns": ["Divisor d", "Cofactor n/d", "Ω(d)", "d is prime"],
        "rows": [[d, cofactor, omega, _yes(int(flag))] for d, cofactor, omega, flag in divisors],
        "edges": [{"from": a, "to": b, "prime": p} for a, b, p in edges],
        "truncated": _one(lines, "DIVISORS_COMPLETE") == 0,
        "note": (
            "PARI/GP factored the integer and enumerated every divisor with its factor "
            "pair. " + (
                "The covering relation d ⋖ dp of the divisor lattice is complete."
                if lattice_complete
                else "The divisor count exceeded the lattice cap, so the covering relation "
                "was not enumerated."
            )
        ),
    }


# ------------------------------------------------------------------ item 68
def smoothness_profile(
    n: str, smooth_bound: str = "100", rough_bound: str = "2", timeout: int = 60
) -> dict:
    """Report smoothness, powersmoothness, and roughness data for ``n``.

    Args:
        n: Decimal integer with ``|n| >= 2``.
        smooth_bound: Decimal bound ``B`` for ``B``-smooth and ``B``-powersmooth tests.
        rough_bound: Decimal bound ``R`` for the ``R``-rough test.
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary with per-prime rows and the exact smoothness bounds.

    Raises:
        ValueError: If the bounds are below 2.
        PrimeEngineError: If PARI/GP failed.
    """
    value = decimal_integer(n)
    b, r = decimal_integer(smooth_bound), decimal_integer(rough_bound)
    if b < 2 or r < 2:
        raise ValueError("The smoothness and roughness bounds must be at least 2")
    if abs(value) < 2:
        raise ValueError("Smoothness analysis requires |n| of at least 2")
    lines = _execute(f"al_smoothness({value},{b},{r})", timeout)
    rows = _records(lines, "PRIME", 6)
    return {
        "metrics": {
            "Integer": str(value),
            "Least prime factor": str(_one(lines, "LEAST_PRIME_FACTOR")),
            "Largest prime factor": str(_one(lines, "LARGEST_PRIME_FACTOR")),
            "Largest prime power": str(_one(lines, "LARGEST_PRIME_POWER")),
            "Smoothness bound (exact)": str(_one(lines, "SMOOTHNESS_BOUND")),
            "Powersmoothness bound (exact)": str(_one(lines, "POWERSMOOTHNESS_BOUND")),
            "Roughness bound (exact)": str(_one(lines, "ROUGHNESS_BOUND")),
            f"{b}-smooth": _yes(_one(lines, "B_SMOOTH")),
            f"{b}-powersmooth": _yes(_one(lines, "B_POWERSMOOTH")),
            f"{r}-rough": _yes(_one(lines, "B_ROUGH")),
            f"{b}-smooth part": str(_one(lines, "SMOOTH_PART")),
            "Remaining rough part": str(_one(lines, "ROUGH_PART")),
        },
        "columns": [
            "Prime p", "Exponent e", "Prime power p^e",
            f"p ≤ {b}", f"p^e ≤ {b}", f"p ≥ {r}",
        ],
        "rows": [
            [p, e, power, _yes(int(smooth)), _yes(int(powersmooth)), _yes(int(rough))]
            for p, e, power, smooth, powersmooth, rough in rows
        ],
        "note": (
            "PARI/GP factored |n| completely, so the smoothness bound (largest prime "
            "factor), powersmoothness bound (largest prime power), and roughness bound "
            "(least prime factor) are exact rather than estimated."
        ),
    }


# ------------------------------------------------------------------ item 69
def record_divisor_numbers(
    n: str, bound: str = "10000", limit: int = 200, timeout: int = 300
) -> dict:
    """Classify ``n`` against the highly composite and abundance record families.

    Four families are tested: highly composite (record ``τ``), superabundant (record
    ``σ(n)/n``), superior highly composite, and colossally abundant.  The last two are
    decided by the exact feasibility of the defining ``ε``-interval, which yields a
    three-way answer.

    Args:
        n: Decimal positive integer to classify.
        bound: Decimal upper bound for the enumerated record sequences.
        limit: Maximum number of rows per family (1–10,000).
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary with the classification metrics and the record sequences.

    Raises:
        ValueError: If a bound is violated.
        PrimeEngineError: If PARI/GP failed.
    """
    value, ceiling = decimal_integer(n), decimal_integer(bound)
    if value < 1 or ceiling < 1:
        raise ValueError("Record-number analysis requires positive integers")
    if ceiling > 10**18:
        raise ValueError("The record-sequence bound must not exceed 10^18")
    if not 1 <= limit <= 10_000:
        raise ValueError("Result limit must be between 1 and 10,000")
    lines = _execute(f"al_record_numbers({value},{ceiling},{limit})", timeout)
    hcn = _records(lines, "HCN", 2)
    superabundant = _records(lines, "SA", 2)
    shcn = _records(lines, "SHCN", 4)
    colossal = _records(lines, "CA", 4)
    if _one(lines, "SHCN_COUNT") != len(shcn) or _one(lines, "CA_COUNT") != len(colossal):
        raise PrimeEngineError("PARI/GP returned an incomplete record-number sequence")
    shcn_interval = _records(lines, "SHCN_EPSILON", 2)
    ca_interval = _records(lines, "CA_EPSILON", 2)
    metrics = {
        "Integer": str(value),
        "τ(n)": str(_one(lines, "NUMDIV")),
        "σ(n)": str(_one(lines, "SIGMA")),
        "Highly composite": _yes(_one(lines, "IS_HCN")),
        "Superabundant": _yes(_one(lines, "IS_SUPERABUNDANT")),
        "Superior highly composite": _three_way(_one(lines, "IS_SHCN")),
        "Colossally abundant": _three_way(_one(lines, "IS_CA")),
        "Enumeration bound": str(ceiling),
    }
    if shcn_interval:
        metrics["Superior highly composite ε-interval"] = (
            f"({shcn_interval[0][0]}, {shcn_interval[0][1]})"
        )
    if ca_interval:
        metrics["Colossally abundant ε-interval"] = (
            f"({ca_interval[0][0]}, {ca_interval[0][1]})"
        )
    rows: list[list[str]] = []
    rows += [["highly composite", v, d, ""] for v, d in hcn]
    rows += [["superabundant", v, "", s] for v, s in superabundant]
    rows += [["superior highly composite", v, d, s] for v, d, s, _ in shcn]
    rows += [["colossally abundant", v, d, s] for v, d, s, _ in colossal]
    return {
        "metrics": metrics,
        "columns": ["Family", "Value", "τ", "σ"],
        "rows": rows,
        "truncated": (
            len(hcn) >= limit
            or len(superabundant) >= limit
            or _optional(lines, "THRESHOLD_TIE") == 1
        ),
        "note": (
            "PARI/GP enumerated only candidates with non-increasing exponents over "
            "consecutive primes, which provably contains every highly composite and "
            "superabundant number, and decided the superior-highly-composite and "
            "colossally-abundant properties from the exact feasibility of their "
            "ε-intervals at 80 digits of working precision."
        ),
    }


# ------------------------------------------------------------------ item 70
def weird_number_analysis(
    n: str, subset_cap: int = 512, witness_bits: int = 8_000_000, timeout: int = 300
) -> dict:
    """Classify ``n`` by its proper-divisor sum and decide semiperfection.

    Deficient, perfect, abundant, almost perfect, quasiperfect, and multiperfect are
    exact divisor-sum tests.  Weirdness additionally requires that no subset of the
    proper divisors sums to ``n``; that subset-sum question is answered by a native
    bitset dynamic program, and a semiperfect verdict comes with an explicit witness
    subset whenever the reconstruction table fits in the configured bit budget.

    Args:
        n: Decimal positive integer.
        subset_cap: Maximum number of proper divisors for which the subset-sum
            decision is attempted (1–4,096).
        witness_bits: Bit budget for storing the reconstruction table (0–2^31).
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary; ``semiperfect`` and ``weird`` are three-way values.

    Raises:
        ValueError: If a bound is violated.
        PrimeEngineError: If PARI/GP failed or its witness did not sum to ``n``.
    """
    value = decimal_integer(n)
    if value < 1:
        raise ValueError("Divisor classification requires a positive integer")
    if not 1 <= subset_cap <= 4_096:
        raise ValueError("Subset cap must be between 1 and 4,096")
    if not 0 <= witness_bits <= 2**31:
        raise ValueError("Witness bit budget must be between 0 and 2^31")
    lines = _execute(f"al_weird({value},{subset_cap},{witness_bits})", timeout)
    witness = _tagged_values(lines, "WITNESS")
    semiperfect = _one(lines, "SEMIPERFECT")
    weird = _one(lines, "WEIRD")
    # PARI/GP verifies inside the engine that the witness subset sums to n and aborts
    # if it does not, so no arithmetic is repeated here.
    if semiperfect == 1 and not witness and _one(lines, "WITNESS_AVAILABLE") == 1:
        raise PrimeEngineError("PARI/GP returned a semiperfect verdict without its witness")
    abundance_class = {-1: "deficient", 0: "perfect", 1: "abundant"}.get(_one(lines, "CLASS"))
    if abundance_class is None:
        raise PrimeEngineError("PARI/GP returned an invalid abundance classification")
    multiplier = _one(lines, "MULTIPERFECT_K")
    return {
        "semiperfect": _three_way(semiperfect),
        "weird": _three_way(weird),
        "metrics": {
            "Integer": str(value),
            "σ(n)": str(_one(lines, "SIGMA")),
            "Proper-divisor sum s(n)": str(_one(lines, "PROPER_SUM")),
            "Abundance σ(n) − 2n": str(_one(lines, "ABUNDANCE")),
            "Divisor count": str(_one(lines, "DIVISOR_COUNT")),
            "Classification": abundance_class,
            "Almost perfect": _yes(_one(lines, "ALMOST_PERFECT")),
            "Quasiperfect": _yes(_one(lines, "QUASIPERFECT")),
            "Multiperfect multiplier k": str(multiplier) if multiplier >= 2 else "none",
            "Semiperfect": _three_way(semiperfect),
            "Weird": _three_way(weird),
        },
        "columns": ["Witness divisor summing to n"],
        "rows": [[str(divisor)] for divisor in witness],
        "note": (
            "PARI/GP decided semiperfection with an exact bitset subset-sum over the "
            "proper divisors and reconstructed the displayed witness, which it verified "
            "sums to n."
            if semiperfect == 1 and witness
            else (
                "PARI/GP proved by exhaustive bitset subset-sum that no subset of the "
                "proper divisors sums to n, so an abundant n is weird."
                if semiperfect == 0
                else (
                    "PARI/GP decided semiperfection exactly; the witness subset was not "
                    "reconstructed because the table exceeded the configured bit budget."
                    if semiperfect == 1
                    else "The proper-divisor count exceeded the subset-sum cap, so "
                    "semiperfection and weirdness are inconclusive rather than negative."
                )
            )
        ),
    }


# ------------------------------------------------------------------ item 71
def sociable_cycles(
    start: str,
    end: str,
    max_length: int = 10,
    term_bound: str = "1000000000000",
    limit: int = 1_000,
    dedupe: bool = True,
    timeout: int = 300,
) -> dict:
    """Search an interval for aliquot cycles: amicable pairs and sociable chains.

    A cycle of length 1 is a perfect number, length 2 an amicable pair, and length at
    least 3 a sociable chain.

    Args:
        start: Decimal lower endpoint, at least 1.
        end: Decimal upper endpoint, at least ``start``.
        max_length: Maximum cycle length to close (1–1,000).
        term_bound: Decimal ceiling above which an aliquot term aborts the trajectory.
        limit: Maximum number of cycles to report (1–100,000).
        dedupe: Report each cycle once, from its least member.
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary; ``inconclusive`` counts the starting points whose
        trajectory neither closed nor terminated inside the configured budget.

    Raises:
        ValueError: If a bound is violated.
        PrimeEngineError: If PARI/GP failed or returned inconsistent counts.
    """
    lower, upper = decimal_integer(start), decimal_integer(end)
    ceiling = decimal_integer(term_bound)
    if lower < 1 or upper < lower:
        raise ValueError("The search range must satisfy 1 ≤ start ≤ end")
    if upper - lower > 10_000_000:
        raise ValueError("The search interval must span at most 10,000,000 integers")
    if not 1 <= max_length <= 1_000:
        raise ValueError("Maximum cycle length must be between 1 and 1,000")
    if ceiling < upper:
        raise ValueError("The term bound must be at least the interval endpoint")
    if not 1 <= limit <= 100_000:
        raise ValueError("Result limit must be between 1 and 100,000")
    lines = _execute(
        f"al_sociable({lower},{upper},{max_length},{ceiling},{limit},{int(dedupe)})",
        timeout,
    )
    cycles = _records(lines, "CYCLE", 3)
    if _one(lines, "DONE") != len(cycles):
        raise PrimeEngineError("PARI/GP returned an incomplete sociable-cycle search")
    open_runs = _records(lines, "INCONCLUSIVE", 3, _SAFE_LABEL)
    if _one(lines, "INCONCLUSIVE_SHOWN") != len(open_runs):
        raise PrimeEngineError("PARI/GP returned an inconsistent inconclusive list")
    inconclusive = _one(lines, "INCONCLUSIVE_COUNT")
    lengths = _records(lines, "LENGTH_COUNT", 2)
    kinds = {"1": "perfect number", "2": "amicable pair"}
    return {
        "inconclusive": inconclusive,
        "metrics": {
            "Interval": f"{lower} through {upper}",
            "Maximum cycle length": str(max_length),
            "Aliquot term bound": str(ceiling),
            "Cycles found": str(len(cycles)),
            "Cycle lengths": ", ".join(f"length {k}: {v}" for k, v in lengths) or "none",
            "Inconclusive starting points": str(inconclusive),
        },
        "columns": ["Cycle length", "Least member", "Members"],
        "rows": [
            [f"{length} ({kinds.get(length, 'sociable chain')})", least, members]
            for length, least, members in cycles
        ] + [
            [
                "inconclusive (term bound)" if reason == "bound" else "inconclusive (length cap)",
                n,
                f"last term {term}",
            ]
            for n, reason, term in open_runs
        ],
        "open_runs": [
            {"start": n, "reason": reason, "last_term": term} for n, reason, term in open_runs
        ],
        "truncated": _one(lines, "TRUNCATED") == 1,
        "note": (
            "PARI/GP iterated s(n) = σ(n) − n with exact divisor sums and reported only "
            "trajectories that returned to their starting value. "
            + (
                f"{inconclusive:,} starting point(s) exceeded the term bound or the length "
                "cap; those remain inconclusive rather than cycle-free."
                if inconclusive
                else "Every trajectory in the interval either closed or terminated, so the "
                "search is complete for the configured cycle length."
            )
        ),
    }


_QFBCORNACCHIA = re.compile(r"none|(-?\d+)\|(-?\d+)")


def _qfbcornacchia(lines: list[str]) -> str:
    """Render the native ``qfbcornacchia`` cross-check, which runs only for prime n."""
    prefix = "QFBCORNACCHIA:"
    values = [line[len(prefix):] for line in lines if line.startswith(prefix)]
    if not values:
        return "not applicable (n is not prime)"
    match = _QFBCORNACCHIA.fullmatch(values[0]) if len(values) == 1 else None
    if match is None:
        raise PrimeEngineError("PARI/GP returned an invalid qfbcornacchia value")
    if values[0] == "none":
        return "no primitive representation"
    return f"x = {match.group(1)}, y = {match.group(2)}"


# ------------------------------------------------------------------ item 74
def cornacchia_representations(
    d: str, n: str, trace_limit: int = 1_000, timeout: int = 60
) -> dict:
    """Solve ``x² + d·y² = n`` by Cornacchia's algorithm with a step trace.

    Every representation is cross-checked against PARI/GP's ``qfbsolve``: both solution
    sets are closed up under the automorphism group of the form (``{±1}`` in general,
    and additionally the coordinate swap when ``d = 1``) and compared as sets, so the
    check is independent of ordering and of representative choice.

    Args:
        d: Decimal positive coefficient of ``y²``.
        n: Decimal positive target.
        trace_limit: Maximum number of Euclidean-descent rows (0–100,000).
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary; ``cross_checked`` reports the set comparison.

    Raises:
        ValueError: If a bound is violated.
        PrimeEngineError: If PARI/GP failed or its cross-check disagreed.
    """
    coefficient, target = decimal_integer(d), decimal_integer(n)
    if coefficient < 1 or target < 1:
        raise ValueError("Cornacchia requires d ≥ 1 and n ≥ 1")
    if not 0 <= trace_limit <= 100_000:
        raise ValueError("Trace limit must be between 0 and 100,000")
    form = "x² + y²" if coefficient == 1 else f"x² + {coefficient}y²"
    lines = _execute(f"al_cornacchia({coefficient},{target},{trace_limit})", timeout)
    complete = _one(lines, "ROOTS_COMPLETE") == 1
    solutions = _records(lines, "SOLUTION", 3)
    if _one(lines, "DONE") != len(solutions):
        raise PrimeEngineError("PARI/GP returned an incomplete Cornacchia solution set")
    if not complete:
        return {
            "complete": False,
            "cross_checked": False,
            "metrics": {
                "Form": f"x² + {coefficient}y²",
                "Target n": str(target),
                "Status": "inconclusive",
            },
            "columns": ["Stage", "x or a", "y or b", "Detail"],
            "rows": [],
            "note": (
                "The square-root enumeration modulo a divisor of n exceeded the native "
                "root cap, so the representation search is inconclusive, not empty."
            ),
        }
    cross_checked = _one(lines, "CROSS_CHECK") == 1
    if not cross_checked:
        raise PrimeEngineError(
            "PARI/GP's qfbsolve cross-check disagreed with the Cornacchia trace"
        )
    native = _qfbcornacchia(lines)
    trace = _records(lines, "TRACE", 5)
    outcomes = _records(lines, "TRACE_RESULT", 4)
    return {
        "complete": True,
        "cross_checked": True,
        "metrics": {
            "Form": form,
            "Target n": str(target),
            "Representations up to sign and symmetry": str(len(solutions)),
            "Total integer solutions": str(_one(lines, "NATIVE_TOTAL")),
            "qfbsolve cross-check": "sets agree",
            "Native qfbcornacchia": native,
        },
        "columns": ["Stage", "x or a", "y or b", "Detail"],
        "rows": (
            [
                ["representation", x, y, "primitive" if primitive == "1" else "imprimitive"]
                for x, y, primitive in solutions
            ]
            + [
                [f"descent step {step}", a, b, f"square divisor {g}, root r = {r}"]
                for g, r, step, a, b in trace
            ]
            + [
                [
                    "descent outcome",
                    x,
                    "none" if y == "-1" else y,
                    f"square divisor {g}, root r = {r}",
                ]
                for g, r, x, y in outcomes
            ]
        ),
        "solutions": [
            {"x": x, "y": y, "primitive": primitive == "1"} for x, y, primitive in solutions
        ],
        "trace": [
            {"square_divisor": g, "root": r, "step": step, "a": a, "b": b}
            for g, r, step, a, b in trace
        ],
        "trace_results": [
            {"square_divisor": g, "root": r, "x": x, "y": ("none" if y == "-1" else y)}
            for g, r, x, y in outcomes
        ],
        "truncated": len(trace) >= trace_limit > 0,
        "note": (
            "PARI/GP solved r² ≡ −d (mod m) for every square divisor of n, ran the "
            "Euclidean descent to the √m threshold, verified x² + dy² = n for each "
            "representation, and confirmed the complete solution set against qfbsolve."
        ),
    }


# ------------------------------------------------------------ items 110-111
def quadratic_ring_analysis(
    radicand: str,
    a: str = "1",
    b: str = "1",
    prime: str = "5",
    certify_seconds: int = 10,
    timeout: int = 300,
) -> dict:
    """Analyze norms, units, primality, and prime splitting in ``ℚ(√d)``.

    Args:
        radicand: Decimal nonsquare integer other than 0 and 1.
        a: Decimal rational part of the element ``a + b·ω``.
        b: Decimal coefficient of the ring generator ``ω``.
        prime: Decimal rational prime to decompose.
        certify_seconds: Budget for ``bnfcertify`` (1–3,600 seconds).
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary with the element's norm and trace, the unit data, the class
        number, and the prime-ideal decomposition with explicit generators when the
        ideals are principal.

    Raises:
        ValueError: If a bound is violated.
        PrimeEngineError: If PARI/GP failed.
    """
    d = decimal_integer(radicand)
    x, y = decimal_integer(a), decimal_integer(b)
    p = decimal_integer(prime)
    if d in {0, 1}:
        raise ValueError("The radicand must be a nonsquare integer other than 0 and 1")
    if not 1 <= certify_seconds <= 3600:
        raise ValueError("The certification budget must be between 1 and 3,600 seconds")
    if p < 2:
        raise ValueError("The rational prime must be at least 2")
    lines = _execute(f"al_quadratic_ring({d},{x},{y},{p},{certify_seconds})", timeout)
    ideals = _records(lines, "PRIME_IDEAL", 7)
    if _one(lines, "IDEAL_COUNT") != len(ideals):
        raise PrimeEngineError("PARI/GP returned an incomplete prime-ideal decomposition")
    discriminant = _one(lines, "DISCRIMINANT")
    symbol = _one(lines, "KRONECKER")
    behaviour = _text(lines, "BEHAVIOR", _SAFE_TEXT) or "unknown"
    unit = _records(lines, "FUNDAMENTAL_UNIT", 3)
    element_prime = {0: "no", 1: "yes (prime norm)", 2: "yes (inert rational prime)"}[
        _one(lines, "ELEMENT_PRIME")
    ]
    certified = _one(lines, "CLASS_CERTIFIED")
    cycles = _tagged_values(lines, "CLASS_CYCLE")
    metrics = {
        "Field": f"ℚ(√{d})",
        "Squarefree core": str(_one(lines, "CORE")),
        "Field discriminant": str(discriminant),
        "Ring of integers": "ℤ[(1+√d)/2]" if _one(lines, "RING") else "ℤ[√d]",
        "Element": f"{x} {_signed(str(y), 'ω')}",
        "Norm N(a + bω)": str(_one(lines, "NORM")),
        "Trace Tr(a + bω)": str(_one(lines, "TRACE")),
        "Element is a unit": _yes(_one(lines, "IS_UNIT")),
        "Element is prime in the ring": element_prime,
        "Roots of unity": str(_one(lines, "ROOTS_OF_UNITY")),
        "Fundamental unit": (
            f"{unit[0][0]} {_signed(unit[0][1], 'ω')} (norm {unit[0][2]})"
            if unit else "none beyond the roots of unity (imaginary field)"
        ),
        "Class number h": str(_one(lines, "CLASS_NUMBER")),
        "Class group": " × ".join(f"C{value}" for value in cycles) or "trivial",
        "Class number certified": _three_way(certified),
        "Rational prime p": str(p),
        "Kronecker (disc/p)": str(symbol),
        "Behavior of p": behaviour,
    }
    rows = [
        [
            index,
            e,
            f,
            norm,
            "principal" if principal == "1" else "non-principal",
            f"{u} {_signed(v, 'ω')}" if principal == "1" else "—",
        ]
        for index, e, f, norm, principal, u, v in ideals
    ]
    return {
        "metrics": metrics,
        "columns": ["Ideal", "Ramification e", "Inertia f", "Norm", "Class", "Generator"],
        "rows": rows,
        "note": (
            "PARI/GP built the maximal quadratic order, computed the exact norm, trace, "
            "unit group, and class group, and decomposed p with idealprimedec. "
            + (
                "The class number is certified unconditionally."
                if certified == 1
                else "The class-number certification budget was exhausted, so the class "
                "number is conditional on the generalized Riemann hypothesis; that part "
                "of the result is inconclusive."
            )
        ),
    }


# ------------------------------------------------------------ items 112-113
def number_field_analysis(
    coefficients: list[str],
    primes: list[str],
    element_coefficients: list[str] | None = None,
    class_seconds: int = 10,
    timeout: int = 300,
) -> dict:
    """Decompose rational primes in a general number field and factor an element.

    Args:
        coefficients: Ascending coefficients of a monic irreducible defining polynomial
            of degree 2 to 12.
        primes: Decimal rational primes to decompose (1 to 32 entries).
        element_coefficients: Optional ascending coordinates of an element in the power
            basis, whose ideal factorization is reported.
        class_seconds: Budget for ``bnfinit`` and ``bnfcertify`` (1–3,600 seconds).
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary listing splitting, inertia, and ramification per prime, the
        prime-ideal decomposition, and (when computed inside the budget) the class group.

    Raises:
        ValueError: If a bound is violated.
        PrimeEngineError: If PARI/GP failed or returned inconsistent counts.
    """
    values = _coefficients(
        coefficients,
        maximum_degree=MAX_FIELD_DEGREE,
        maximum_digits=MAX_FIELD_COEFFICIENT_DIGITS,
        label="defining-polynomial",
    )
    if len(values) < 3:
        raise ValueError("The defining polynomial must have degree at least 2")
    if values[-1] != 1:
        raise ValueError("The defining polynomial must be monic")
    if not 1 <= len(primes) <= 32:
        raise ValueError("Supply 1 to 32 rational primes")
    prime_list = [decimal_integer(value) for value in primes]
    if any(value < 2 or len(str(value)) > 40 for value in prime_list):
        raise ValueError("Each rational prime must be at least 2 and below 10^40")
    if not 1 <= class_seconds <= 3600:
        raise ValueError("The class-group budget must be between 1 and 3,600 seconds")
    element: list[int] = []
    if element_coefficients:
        if len(element_coefficients) >= len(values):
            raise ValueError("Element coordinates must number fewer than the field degree")
        element = [decimal_integer(value) for value in element_coefficients]
        if any(len(str(abs(value))) > MAX_FIELD_COEFFICIENT_DIGITS for value in element):
            raise ValueError(
                f"Each element coordinate must have at most "
                f"{MAX_FIELD_COEFFICIENT_DIGITS} decimal digits"
            )
        if not any(element):
            raise ValueError("The element must be nonzero")
    lines = _execute(
        f"al_number_field({_vector(values)},{_vector(prime_list)},"
        f"{_vector(element)},{class_seconds})",
        timeout,
    )
    prime_rows = _records(lines, "PRIME", 6)
    ideal_rows = _records(lines, "PRIME_IDEAL", 5)
    if len(prime_rows) != len(prime_list):
        raise PrimeEngineError("PARI/GP returned an incomplete prime decomposition")
    factor_rows = _records(lines, "ELEMENT_FACTOR", 5)
    factor_count = _optional(lines, "ELEMENT_FACTOR_COUNT")
    if factor_count is not None and factor_count != len(factor_rows):
        raise PrimeEngineError("PARI/GP returned an incomplete element factorization")
    galois = _records(lines, "GALOIS", 3)
    class_number = _one(lines, "CLASS_NUMBER")
    certified = _one(lines, "CLASS_CERTIFIED")
    signature = _records(lines, "SIGNATURE", 2)
    degree = _one(lines, "DEGREE")
    metrics = {
        "Degree": str(degree),
        "Field discriminant": str(_one(lines, "DISCRIMINANT")),
        "Polynomial discriminant": str(_one(lines, "POLYNOMIAL_DISCRIMINANT")),
        "Signature (r₁, r₂)": f"({signature[0][0]}, {signature[0][1]})" if signature else "unknown",
        "Index [O_K : ℤ[θ]]": str(_one(lines, "INDEX")),
        "Galois group": _text(lines, "GALOIS_NAME") or "degree above 7; not computed",
        "Galois group order": galois[0][0] if galois else "not computed",
        "Class number h": str(class_number) if class_number >= 0 else "inconclusive",
        "Class group": " × ".join(f"C{v}" for v in _tagged_values(lines, "CLASS_CYCLE")) or (
            "trivial" if class_number == 1 else "inconclusive"
        ),
        "Class number certified": _three_way(certified),
    }
    if element:
        metrics["Element norm"] = str(_one(lines, "ELEMENT_NORM"))
    behaviours = {row[0]: row[5] for row in prime_rows}
    rows = [
        [p, behaviours.get(p, "unknown"), index, e, f, norm]
        for p, index, e, f, norm in ideal_rows
    ]
    if factor_rows:
        metrics["Element ideal factorization"] = " × ".join(
            f"𝔭({p}, f={f})^{mult}" for p, _e, f, mult, _norm in factor_rows
        )
    basis = [row[1] for row in _records(lines, "BASIS", 2)]
    metrics["Integral basis"] = ", ".join(basis)
    return {
        "metrics": metrics,
        "columns": [
            "Rational prime p", "Behavior", "Ideal index",
            "Ramification e", "Inertia f", "Norm N(𝔭)",
        ],
        "rows": rows,
        "primes": [
            {
                "prime": p,
                "behavior": behaviours[p],
                "ideal_count": ideal_count,
                "maximum_e": e_max,
                "kronecker": symbol,
            }
            for p, ideal_count, e_max, symbol, _ramified, _behavior in prime_rows
        ],
        "ideals": [
            {"prime": p, "index": index, "e": e, "f": f, "norm": norm}
            for p, index, e, f, norm in ideal_rows
        ],
        "element_factors": [
            {"prime": p, "e": e, "f": f, "multiplicity": mult, "norm": norm}
            for p, e, f, mult, norm in factor_rows
        ],
        "integral_basis": basis,
        "note": (
            "PARI/GP built the maximal order with nfinit and decomposed each rational "
            "prime with idealprimedec, so the ramification indices, inertia degrees, and "
            "ideal norms are exact and satisfy Σ e_i f_i = n. "
            + (
                "The class group was computed and certified unconditionally."
                if certified == 1 and class_number >= 0
                else "The class-group budget was exhausted, so the class number is "
                "inconclusive; the prime decomposition above is unaffected."
            )
        ),
    }


# ------------------------------------------------------------------ item 115
def chebotarev_density(
    coefficients: list[str], bound: str = "2000", group_seconds: int = 20, timeout: int = 300
) -> dict:
    """Compare observed Frobenius factorization patterns with Chebotarev's prediction.

    For each unramified prime ``p`` below the bound, PARI/GP factors the polynomial
    modulo ``p``; the multiset of factor degrees is the cycle type of the Frobenius
    class.  Chebotarev's density theorem predicts that the proportion of primes with a
    given cycle type tends to the relative size of that conjugacy class in the Galois
    group of the splitting field.

    Args:
        coefficients: Ascending coefficients of a monic irreducible polynomial of degree
            2 to 7.
        bound: Decimal prime bound (at least 10, at most 10^7).
        group_seconds: Budget for computing the splitting field when the Galois group is
            not the full symmetric or alternating group (1–3,600 seconds).
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary comparing observed and predicted densities.  Predicted
        columns read ``inconclusive`` when the group budget was exhausted.

    Raises:
        ValueError: If a bound is violated.
        PrimeEngineError: If PARI/GP failed or returned inconsistent counts.
    """
    values = _coefficients(
        coefficients,
        maximum_degree=MAX_CHEBOTAREV_DEGREE,
        maximum_digits=MAX_FIELD_COEFFICIENT_DIGITS,
        label="polynomial",
    )
    if len(values) < 3:
        raise ValueError("The polynomial must have degree at least 2")
    if values[-1] != 1:
        raise ValueError("The polynomial must be monic")
    ceiling = decimal_integer(bound)
    if not 10 <= ceiling <= 10**7:
        raise ValueError("The prime bound must be between 10 and 10,000,000")
    if not 1 <= group_seconds <= 3600:
        raise ValueError("The group budget must be between 1 and 3,600 seconds")
    lines = _execute(
        f"al_chebotarev({_vector(values)},{ceiling},{group_seconds})", timeout
    )
    patterns = _records(lines, "PATTERN", 5)
    if _one(lines, "DONE") != len(patterns):
        raise PrimeEngineError("PARI/GP returned an incomplete Chebotarev experiment")
    predicted = _one(lines, "PREDICTED_AVAILABLE") == 1
    used = _one(lines, "PRIMES_USED")
    order = _one(lines, "GROUP_ORDER")
    # Parse checksum only: the per-pattern row counts must account for every prime the
    # engine reported using, otherwise the tagged output was truncated.
    if used != sum(int(row[1]) for row in patterns):
        raise PrimeEngineError("PARI/GP returned inconsistent Chebotarev counts")
    rows = [
        [
            key,
            observed,
            f"{observed_percent}%",
            size if predicted else "inconclusive",
            f"{predicted_percent}%" if predicted else "inconclusive",
        ]
        for key, observed, observed_percent, size, predicted_percent in patterns
    ]
    return {
        "predicted_available": predicted,
        "metrics": {
            "Degree": str(_one(lines, "DEGREE")),
            "Polynomial discriminant": str(_one(lines, "DISCRIMINANT")),
            "Galois group": _text(lines, "GROUP_NAME") or "unknown",
            "Galois group order": str(order),
            "Prime bound": str(ceiling),
            "Unramified primes used": str(used),
            "Ramified primes skipped": str(_one(lines, "PRIMES_SKIPPED")),
            "Conjugacy-class sizes available": _yes(predicted),
        },
        "columns": [
            "Factorization pattern (degrees)", "Primes observed", "Observed density",
            "Conjugacy-class size", "Chebotarev density",
        ],
        "rows": rows,
        "note": (
            "PARI/GP factored the polynomial modulo every unramified prime below the "
            "bound and computed the conjugacy-class sizes of the Galois group exactly. "
            "Observed densities are a finite experiment, not a proof: they approach the "
            "predicted densities only as the bound grows."
            if predicted
            else "PARI/GP measured the observed factorization patterns exactly, but the "
            "splitting-field computation exceeded its budget, so the predicted "
            "Chebotarev densities are inconclusive."
        ),
    }
