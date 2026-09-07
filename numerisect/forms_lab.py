"""Typed orchestration boundary for the native PARI/GP forms and continued-fraction lab.

The mathematics lives entirely in :mod:`numerisect/forms_lab.gp`, which is a thin driver
over PARI/GP's own routines.  This module validates requests, renders them into a single
PARI/GP call, launches ``gp`` through :func:`numerisect.primes._run_gp`, and parses the
tagged ``TAG:value`` protocol back into report dictionaries.  No arithmetic on a
mathematical quantity happens here: Python only bounds inputs, renders validated integers
into GP literals, parses tags, and formats labels.

Which PARI/GP routine performs each computation
-----------------------------------------------

==========================  ==================================================================
Operation                   PARI/GP routines
==========================  ==================================================================
Reduce a form               ``Qfb`` (construction and discriminant validation), ``qfbred``
                            (full reduction), ``qfbred(f, 1)`` (one reduction step, which is
                            what makes the trace and the indefinite cycle walk possible),
                            ``qfbredsl2`` (the SL(2, Z) matrix), ``matdet``, ``quaddisc``,
                            ``isfundamental``, ``sqrtint``, ``gcd``.
Compose and exponentiate    ``qfbcomp`` and ``qfbcompraw`` (Gaussian composition with and
                            without reduction), ``qfbpow`` and ``qfbpowraw``,
                            ``qfbprimeform(d, 1)`` for the principal form, ``qfbred``.
Prime form                  ``qfbprimeform``, ``qfbred``, ``kronecker``, ``isprime``.
Class number and structure  ``qfbclassno`` (Shanks) cross-checked against
                            ``quadclassunit`` (structure, generators, regulator),
                            ``qfbhclassno`` (Hurwitz class number, negative discriminants),
                            ``quadunit`` for the norm of the fundamental unit.
Enumerate reduced forms     ``quadclassunit`` (class-group generators and cyclic
                            structure), ``qfbpow``/``qfbcomp`` (class representatives),
                            ``qfbred``/``qfbred(f, 1)`` (the reduced form, or the whole
                            cycle for an indefinite form), ``issquare``.
Represent an integer        ``qfbsolve`` with flag 1 (primitive solutions) and flag 3 (all
                            solutions), ``gcd``; every pair is substituted back into Q.
Continued fractions         ``contfrac`` (rational expansions, and the floating-point
                            cross-check for quadratic irrationals), ``contfracpnqn``
                            (convergents), ``bestappr`` (best rational approximation),
                            ``sqrtint``, ``issquare``.
Pell's equation             ``quadunit`` (the fundamental unit of the order of discriminant
                            4d *is* the fundamental solution), ``norm`` (which decides
                            whether the negative Pell equation is solvable),
                            ``quadregulator``, ``quadgen``, ``bestappr`` (cross-check
                            against the convergent), ``issquare``.
==========================  ==================================================================

Two computations have no library routine and are built from PARI primitives, exactly as
the Hensel lift is in :mod:`numerisect.algebra_lab`:

* The exact continued-fraction expansion of a quadratic irrational.  PARI's ``contfrac``
  takes a ``t_REAL``, so its tail is unreliable — ``contfrac(sqrt(13))`` at the default
  precision ends in a spurious 7 — and it reports no period.  The classical ``(P, Q)``
  recursion in the GP program is exact integer arithmetic with ``sqrtint``, detects the
  period by state repetition rather than by guessing, and has its emitted prefix
  cross-checked term by term against ``contfrac`` at raised precision.
* Enumeration of the reduced forms of a discriminant.  PARI exposes the class group and
  the reduction operators but no routine that lists reduced forms, so the enumeration is
  driven by ``quadclassunit``, ``qfbpow``/``qfbcomp`` and single-step ``qfbred``.

Relationship to the factoring tools
-----------------------------------

Both features are the historical ancestry of Numerisect's factoring lab and neither is a
factoring method here.  SQUFOF (``numerisect/native/numerisect_squfof.c``, reachable from
Factor Lab) walks the principal cycle of forms of discriminant ``4kN`` looking for an
ambiguous form, whose leading coefficient exposes a factor of ``N``; the enumeration tool
below shows that cycle and flags exactly those forms.  CFRAC builds congruences of squares
from the convergents of ``sqrt(N)``; Numerisect does not implement CFRAC as a factoring
method because SIQS supersedes it at every size, so the continued-fraction tools are
exposition, not a factoring path.

Resource limits enforced here
-----------------------------

=========================  ======================================================
Bound                      Value
=========================  ======================================================
Engine timeout             1 to 3,600 seconds
Coefficient magnitude      200 decimal digits (form coefficients and targets)
Discriminant magnitude     40 decimal digits
Reduction-trace steps      0 to 100,000
Cycle walk                 1 to 1,000,000 single reduction steps
Class-group generators     1 to 64
Reduced forms enumerated   1 to 100,000
Prime-form primes          1 to 64 per request
Composition exponent       |e| <= 10^6; raw (unreduced) power |e| <= 1,000
Class-order search         1 to 100,000 exponentiations
Partial quotients          1 to 100,000
Convergents returned       1 to 100,000
Pell solutions             1 to 100; each capped at 100,000 decimal digits
Fundamental-unit budget    1 to 3,600 seconds
=========================  ======================================================

Exceeding a bound is always reported as inconclusive — ``complete`` is ``False``, a period
or cycle length reads ``inconclusive``, or the row list is marked truncated.  It never
degrades into a wrong or silently shortened answer.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Sequence

from .prime_manipulation import decimal_integer
from .primes import PrimeEngineError, _run_gp, _tagged_values

PROGRAM = Path(__file__).with_name("forms_lab.gp")

#: Characters PARI/GP may emit inside a plain value column.
_SAFE_TEXT = re.compile(r"[0-9A-Za-z_+*/^()., \[\]~-]+")

MAX_COEFFICIENT_DIGITS = 200
MAX_DISCRIMINANT_DIGITS = 40
MAX_TRACE_STEPS = 100_000
MAX_CYCLE_STEPS = 1_000_000
MAX_GENERATORS = 64
MAX_FORMS = 100_000
MAX_PRIMES = 64
MAX_EXPONENT = 10**6
MAX_RAW_EXPONENT = 1_000
MAX_ORDER_SEARCH = 100_000
MAX_QUOTIENTS = 100_000
MAX_CONVERGENTS = 100_000
MAX_PELL_SOLUTIONS = 100
MAX_PELL_DIGITS = 100_000
#: Terms of the exact expansion compared against PARI's floating-point ``contfrac``.
CROSSCHECK_TERMS = 40
#: Largest solution, in decimal digits, still cross-checked against ``bestappr``.
PELL_CHECK_DIGITS = 500
#: Largest preview width, in decimal digits, a single JSON response may carry.
MAX_PREVIEW_DIGITS = 100_000
#: Values longer than this are abbreviated in the response; the saved report is complete.
DEFAULT_PREVIEW_DIGITS = 2_000

_MODES = {"rational": 0, "quadratic": 1}


def _program() -> str:
    try:
        return PROGRAM.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - packaging failure
        raise PrimeEngineError("The PARI/GP forms laboratory is unavailable") from exc


def _execute(call: str, timeout: int) -> list[str]:
    """Run one forms-laboratory call and return its tagged output lines.

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
        raise PrimeEngineError("PARI/GP returned an incomplete forms-laboratory result")
    return lines


def _one(lines: list[str], tag: str) -> int:
    values = _tagged_values(lines, tag)
    if len(values) != 1:
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} result")
    return values[0]


def _records(lines: Iterable[str], tag: str, width: int) -> list[list[str]]:
    prefix = f"{tag}:"
    rows = [line[len(prefix):].split("|") for line in lines if line.startswith(prefix)]
    if any(
        len(row) != width or any(not _SAFE_TEXT.fullmatch(value) for value in row)
        for row in rows
    ):
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} record")
    return rows


def _text(lines: list[str], tag: str) -> str | None:
    prefix = f"{tag}:"
    values = [line[len(prefix):] for line in lines if line.startswith(prefix)]
    if len(values) > 1 or (values and not _SAFE_TEXT.fullmatch(values[0])):
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} value")
    return values[0] if values else None


def _yes(value: int) -> str:
    return "yes" if value else "no"


def _three_way(value: int) -> str:
    return {1: "yes", 0: "no", -1: "inconclusive"}.get(value, "inconclusive")


def _count(value: int) -> str:
    return "inconclusive" if value < 0 else str(value)


def _coefficient(value: str, label: str) -> int:
    """Validate one decimal coefficient against the documented magnitude bound."""

    number = decimal_integer(value)
    if len(str(abs(number))) > MAX_COEFFICIENT_DIGITS:
        raise ValueError(
            f"The {label} must have at most {MAX_COEFFICIENT_DIGITS:,} decimal digits"
        )
    return number


def _discriminant(value: str) -> int:
    """Validate a discriminant's magnitude; its congruence class is checked by PARI/GP."""

    number = decimal_integer(value)
    if len(str(abs(number))) > MAX_DISCRIMINANT_DIGITS:
        raise ValueError(
            f"The discriminant must have at most {MAX_DISCRIMINANT_DIGITS:,} decimal digits"
        )
    return number


def _form_coefficients(a: str, b: str, c: str) -> tuple[int, int, int]:
    return (
        _coefficient(a, "coefficient a"),
        _coefficient(b, "coefficient b"),
        _coefficient(c, "coefficient c"),
    )


def _invariants(lines: list[str]) -> dict[str, str]:
    """Common discriminant metrics reported by every forms operation."""

    definite = _one(lines, "DEFINITE") == 1
    return {
        "Discriminant D": str(_one(lines, "DISC")),
        "Case": (
            "negative discriminant: positive definite forms"
            if definite
            else "positive discriminant: indefinite forms"
        ),
        "Fundamental discriminant": _yes(_one(lines, "FUNDAMENTAL")),
        "Field discriminant": str(_one(lines, "FIELD_DISC")),
        "Conductor": str(_one(lines, "CONDUCTOR")),
    }


def _case_note(definite: bool) -> str:
    return (
        "D < 0: the forms are positive definite, reduction is |b| <= a <= c with b >= 0 "
        "at either boundary, and every class contains exactly one reduced form."
        if definite
        else "D > 0: the forms are indefinite, reduction has no unique fixed point, and "
        "every class is a periodic cycle of reduced forms."
    )


def _integer_list(values: Sequence[str], *, maximum: int, label: str) -> list[int]:
    if not 1 <= len(values) <= maximum:
        raise ValueError(f"Supply 1 to {maximum} {label}")
    return [_coefficient(value, label) for value in values]


def _vector(values: Sequence[int]) -> str:
    """Render validated integers as a PARI/GP vector literal."""

    return "[" + ",".join(str(value) for value in values) + "]"


# ------------------------------------------------------------------ reduction
def reduce_form(
    a: str,
    b: str,
    c: str,
    step_limit: int = 40,
    cycle_limit: int = 10_000,
    timeout: int = 60,
) -> dict:
    """Reduce the binary quadratic form ``a x^2 + b x y + c y^2``.

    PARI/GP's ``qfbred`` performs the reduction, ``qfbred(f, 1)`` performs one step at a
    time so the trace can be displayed, and ``qfbredsl2`` returns the SL(2, Z) matrix that
    carries the input to its reduced form.

    Args:
        a: Decimal leading coefficient.
        b: Decimal middle coefficient.
        c: Decimal trailing coefficient.
        step_limit: Maximum single reduction steps to trace (0–100,000).
        cycle_limit: Maximum single steps used to measure the cycle of an indefinite
            form (1–1,000,000).
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary with ``metrics``, ``columns``, ``rows`` and ``truncated``.

    Raises:
        ValueError: If a bound is violated or an input is not an integer.
        PrimeEngineError: If ``b^2 - 4ac`` is not a discriminant, the form is negative
            definite, or PARI/GP failed.
    """
    left, middle, right = _form_coefficients(a, b, c)
    if not 0 <= step_limit <= MAX_TRACE_STEPS:
        raise ValueError(f"Step limit must be between 0 and {MAX_TRACE_STEPS:,}")
    if not 1 <= cycle_limit <= MAX_CYCLE_STEPS:
        raise ValueError(f"Cycle limit must be between 1 and {MAX_CYCLE_STEPS:,}")
    lines = _execute(
        f"fl_reduce({left},{middle},{right},{step_limit},{cycle_limit})", timeout
    )
    rows = _records(lines, "STEP", 4)
    if _one(lines, "DONE") != len(rows):
        raise PrimeEngineError("PARI/GP returned an incomplete reduction trace")
    if _one(lines, "MATDET") != 1 or _one(lines, "SL2_AGREES") != 1:
        raise PrimeEngineError("PARI/GP returned an invalid SL(2, Z) reduction matrix")
    definite = _one(lines, "DEFINITE") == 1
    reduced = _records(lines, "REDUCED", 3)[0]
    matrix = _records(lines, "MATRIX", 4)[0]
    cycle = _one(lines, "CYCLE_LENGTH")
    metrics = _invariants(lines)
    metrics.update(
        {
            "Input form (a, b, c)": ", ".join(_records(lines, "INPUT", 3)[0]),
            "Content gcd(a, b, c)": str(_one(lines, "CONTENT")),
            "Reduced form (a, b, c)": ", ".join(reduced),
            "Reducing matrix [p q; r s]": (
                f"[{matrix[0]} {matrix[1]}; {matrix[2]} {matrix[3]}]"
            ),
            "Matrix determinant": "1",
            "Reduced form is ambiguous": _yes(_one(lines, "AMBIGUOUS")),
            "Reduction steps traced": str(_one(lines, "STEPS")),
            "Cycle length of the reduced form": (
                "1 (definite forms have one reduced form per class)"
                if definite
                else _count(cycle)
            ),
        }
    )
    return {
        "definite": definite,
        "metrics": metrics,
        "columns": ["Step", "a", "b", "c"],
        "rows": rows,
        "truncated": _one(lines, "TRUNCATED") == 1,
        "note": (
            "PARI/GP reduced the form with qfbred, replayed the reduction one step at a "
            "time with qfbred(f, 1), and produced the SL(2, Z) transformation with "
            "qfbredsl2; the matrix determinant and the reduced form were re-checked. "
            + _case_note(definite)
            + (
                ""
                if definite
                else " The cycle length was measured by walking single reduction steps; "
                "an exhausted cycle limit reads inconclusive."
            )
        ),
    }


# ------------------------------------------------------------------ composition
def compose_forms(
    a1: str,
    b1: str,
    c1: str,
    a2: str,
    b2: str,
    c2: str,
    exponent: int = 3,
    order_limit: int = 1_000,
    cycle_limit: int = 10_000,
    timeout: int = 60,
) -> dict:
    """Compose two forms of equal discriminant and exponentiate the first.

    ``qfbcomp`` is Gaussian composition followed by reduction, ``qfbcompraw`` the same
    composition without reduction; ``qfbpow`` and ``qfbpowraw`` are the corresponding
    powers.  ``qfbprimeform(D, 1)`` supplies the principal form against which principality
    is decided.

    Args:
        a1: Decimal coefficients of the left form.
        b1: See ``a1``.
        c1: See ``a1``.
        a2: Decimal coefficients of the right form; its discriminant must match.
        b2: See ``a2``.
        c2: See ``a2``.
        exponent: Power applied to the left form; ``|exponent| <= 10^6``.
        order_limit: Maximum exponentiations used to find the order of the left class
            (1–100,000).
        cycle_limit: Maximum single reduction steps used to search the principal cycle of
            an indefinite discriminant (1–1,000,000).
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary; principality and class order read ``inconclusive`` when the
        corresponding cap was exhausted.

    Raises:
        ValueError: If a bound is violated or an input is not an integer.
        PrimeEngineError: If the discriminants differ, are not discriminants, or PARI/GP
            failed.
    """
    left = _form_coefficients(a1, b1, c1)
    right = _form_coefficients(a2, b2, c2)
    if not -MAX_EXPONENT <= exponent <= MAX_EXPONENT:
        raise ValueError(f"The exponent must be between -{MAX_EXPONENT:,} and {MAX_EXPONENT:,}")
    if not 1 <= order_limit <= MAX_ORDER_SEARCH:
        raise ValueError(f"Order limit must be between 1 and {MAX_ORDER_SEARCH:,}")
    if not 1 <= cycle_limit <= MAX_CYCLE_STEPS:
        raise ValueError(f"Cycle limit must be between 1 and {MAX_CYCLE_STEPS:,}")
    arguments = ",".join(str(value) for value in (*left, *right))
    lines = _execute(
        f"fl_compose({arguments},{exponent},{MAX_RAW_EXPONENT},{order_limit},{cycle_limit})",
        timeout,
    )
    if _one(lines, "DONE") != 1:
        raise PrimeEngineError("PARI/GP returned an incomplete composition result")
    definite = _one(lines, "DEFINITE") == 1
    raw_available = _one(lines, "POWRAW_AVAILABLE") == 1
    rows = [
        ["Left form f", *_records(lines, "LEFT", 3)[0], "input"],
        ["Right form g", *_records(lines, "RIGHT", 3)[0], "input"],
        ["Principal form", *_records(lines, "PRINCIPAL", 3)[0], "qfbprimeform(D, 1)"],
        ["f ∘ g", *_records(lines, "COMP", 3)[0], "qfbcomp"],
        ["f ∘ g unreduced", *_records(lines, "COMPRAW", 3)[0], "qfbcompraw"],
        [f"f^{exponent}", *_records(lines, "POW", 3)[0], "qfbpow"],
    ]
    if raw_available:
        rows.append(
            [f"f^{exponent} unreduced", *_records(lines, "POWRAW", 3)[0], "qfbpowraw"]
        )
    order = _one(lines, "ORDER")
    metrics = _invariants(lines)
    metrics.update(
        {
            "Exponent": str(exponent),
            "f ∘ g is principal": _three_way(_one(lines, "COMP_PRINCIPAL")),
            f"f^{exponent} is principal": _three_way(_one(lines, "POW_PRINCIPAL")),
            "Order of the class of f": _count(order),
            "Unreduced power available": _yes(raw_available),
        }
    )
    return {
        "definite": definite,
        "raw_power_available": raw_available,
        "metrics": metrics,
        "columns": ["Form", "a", "b", "c", "Routine"],
        "rows": rows,
        "truncated": not raw_available,
        "note": (
            "PARI/GP composed the forms with qfbcomp and qfbcompraw and exponentiated with "
            "qfbpow and qfbpowraw; the raw variants skip reduction, so their coefficients "
            "grow while the class stays the same. "
            + _case_note(definite)
            + " Principality is decided by comparing reduced forms when D < 0 and by "
            "searching the principal cycle when D > 0; an exhausted cap reads "
            f"inconclusive. The unreduced power is offered only for |exponent| <= "
            f"{MAX_RAW_EXPONENT:,}, beyond which its coefficients are not useful to read."
        ),
    }


# ------------------------------------------------------------------ prime forms
def prime_forms(discriminant: str, primes: list[str], timeout: int = 60) -> dict:
    """Find the prime form of a discriminant for each requested prime.

    ``qfbprimeform(D, p)`` returns the form with leading coefficient ``p``; it exists
    exactly when ``D`` is a square modulo ``4p``, and PARI/GP's refusal is reported as
    "not represented" rather than as an engine failure.  ``kronecker(D, p)`` is shown
    beside it as the splitting symbol.

    Args:
        discriminant: Decimal discriminant, congruent to 0 or 1 modulo 4.
        primes: Decimal primes, 1 to 64 of them.
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary with one row per requested prime.

    Raises:
        ValueError: If a bound is violated or an input is not an integer.
        PrimeEngineError: If the discriminant is invalid or PARI/GP failed.
    """
    value = _discriminant(discriminant)
    values = _integer_list(primes, maximum=MAX_PRIMES, label="primes")
    lines = _execute(f"fl_primeform({value},{_vector(values)})", timeout)
    records = _records(lines, "PRIME", 11)
    if _one(lines, "DONE") != len(records):
        raise PrimeEngineError("PARI/GP returned an incomplete prime-form result")
    rows = []
    represented = 0
    for prime, status, fa, fb, fc, ra, rb, rc, symbol, prime_flag, ambiguous in records:
        found = status == "form"
        represented += 1 if found else 0
        rows.append(
            [
                prime,
                "yes" if prime_flag == "1" else "no",
                symbol,
                f"{fa}, {fb}, {fc}" if found else "no form",
                f"{ra}, {rb}, {rc}" if found else "—",
                _yes(int(ambiguous)) if found else "—",
            ]
        )
    definite = _one(lines, "DEFINITE") == 1
    metrics = _invariants(lines)
    metrics.update(
        {
            "Primes requested": str(len(records)),
            "Primes with a form": str(represented),
        }
    )
    return {
        "definite": definite,
        "metrics": metrics,
        "columns": [
            "p",
            "p is prime",
            "kronecker(D, p)",
            "Prime form (a, b, c)",
            "Reduced (a, b, c)",
            "Ambiguous",
        ],
        "rows": rows,
        "note": (
            "PARI/GP built each prime form with qfbprimeform and reduced it with qfbred. "
            "A form with leading coefficient p exists exactly when D is a square modulo "
            "4p, which is why kronecker(D, p) = -1 leaves the row empty. "
            + _case_note(definite)
        ),
    }


# ------------------------------------------------------------------ class group
def class_group(discriminant: str, generator_limit: int = 16, timeout: int = 120) -> dict:
    """Compute the class number and class-group structure of a discriminant.

    ``qfbclassno`` computes the class number by Shanks's method and ``quadclassunit``
    computes the group structure, its generators and (for ``D > 0``) the regulator; the
    two class numbers are compared and a disagreement is reported rather than hidden.
    ``qfbhclassno`` supplies the Hurwitz class number for a negative discriminant.

    Args:
        discriminant: Decimal discriminant, congruent to 0 or 1 modulo 4.
        generator_limit: Maximum generators to list (1–64).
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary with one row per class-group generator.

    Raises:
        ValueError: If a bound is violated or the discriminant is not an integer.
        PrimeEngineError: If the discriminant is invalid or PARI/GP failed.
    """
    value = _discriminant(discriminant)
    if not 1 <= generator_limit <= MAX_GENERATORS:
        raise ValueError(f"Generator limit must be between 1 and {MAX_GENERATORS}")
    lines = _execute(f"fl_class_group({value},{generator_limit})", timeout)
    rows = _records(lines, "GEN", 6)
    if _one(lines, "DONE") != len(rows):
        raise PrimeEngineError("PARI/GP returned an incomplete class-group result")
    agrees = _one(lines, "AGREE") == 1
    if not agrees:
        raise PrimeEngineError(
            "PARI/GP's qfbclassno and quadclassunit disagreed on the class number"
        )
    definite = _one(lines, "DEFINITE") == 1
    structure = _text(lines, "CYC") or "trivial"
    metrics = _invariants(lines)
    metrics.update(
        {
            "Class number h": str(_one(lines, "CLASSNO")),
            "Class-group structure": (
                "trivial" if structure == "trivial" else f"Z/{structure.replace(',', ' × Z/')}"
            ),
            "Class-group rank": str(_one(lines, "RANK")),
            "qfbclassno and quadclassunit agree": "yes",
        }
    )
    if definite:
        metrics["Hurwitz class number H(-D)"] = _text(lines, "HURWITZ") or "—"
    else:
        metrics["Regulator"] = _text(lines, "REGULATOR") or "—"
        metrics["Norm of the fundamental unit"] = str(
            _one(lines, "FUNDAMENTAL_UNIT_NORM")
        )
    return {
        "definite": definite,
        "metrics": metrics,
        "columns": ["Generator", "a", "b", "c", "Order", "Ambiguous"],
        "rows": rows,
        "truncated": _one(lines, "TRUNCATED") == 1,
        "note": (
            "PARI/GP computed the class number with qfbclassno and the group structure, "
            "generators and regulator with quadclassunit; the two class numbers were "
            "compared and agree. "
            + _case_note(definite)
            + (
                " qfbhclassno gives the Hurwitz class number, which weights the classes of "
                "the forms x²+y² and x²+xy+y² by 1/2 and 1/3."
                if definite
                else " For D > 0 quadclassunit also returns the regulator, the logarithm of "
                "the fundamental unit of the order."
            )
            + " quadclassunit assumes the generalized Riemann hypothesis for the bound on "
            "the generators it uses."
        ),
    }


# ------------------------------------------------------------------ enumeration
def reduced_forms(
    discriminant: str,
    form_limit: int = 200,
    cycle_limit: int = 10_000,
    timeout: int = 120,
) -> dict:
    """Enumerate the reduced forms of a discriminant, class by class.

    Class representatives are the products of the ``quadclassunit`` generators formed with
    ``qfbpow`` and ``qfbcomp``.  For ``D < 0`` each class contributes its single reduced
    form; for ``D > 0`` each class is a cycle, expanded with single-step ``qfbred``.
    Class 1 is the principal class, and for ``D > 0`` its cycle is the one SQUFOF walks.

    Args:
        discriminant: Decimal discriminant, congruent to 0 or 1 modulo 4.
        form_limit: Maximum reduced forms to materialize (1–100,000).
        cycle_limit: Maximum length of any one cycle (1–1,000,000).
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary; ``complete`` is ``False`` when either cap was exhausted, in
        which case the enumeration is a prefix and not the full set.

    Raises:
        ValueError: If a bound is violated or the discriminant is not an integer.
        PrimeEngineError: If the discriminant is invalid or PARI/GP failed.
    """
    value = _discriminant(discriminant)
    if not 1 <= form_limit <= MAX_FORMS:
        raise ValueError(f"Form limit must be between 1 and {MAX_FORMS:,}")
    if not 1 <= cycle_limit <= MAX_CYCLE_STEPS:
        raise ValueError(f"Cycle limit must be between 1 and {MAX_CYCLE_STEPS:,}")
    lines = _execute(f"fl_reduced_forms({value},{form_limit},{cycle_limit})", timeout)
    records = _records(lines, "FORM", 6)
    if _one(lines, "DONE") != len(records):
        raise PrimeEngineError("PARI/GP returned an incomplete form enumeration")
    complete = _one(lines, "COMPLETE") == 1
    definite = _one(lines, "DEFINITE") == 1
    rows = [
        [
            index,
            a,
            b,
            c,
            _yes(int(ambiguous)),
            _yes(int(square)),
        ]
        for index, a, b, c, ambiguous, square in records
    ]
    metrics = _invariants(lines)
    metrics.update(
        {
            "Class number h": str(_one(lines, "CLASSNO")),
            "Classes enumerated": str(_one(lines, "CLASSES_SHOWN")),
            "Reduced forms listed": str(len(rows)),
            "Principal cycle length": (
                "1 (definite forms have one reduced form per class)"
                if definite
                else _count(_one(lines, "PRINCIPAL_CYCLE"))
            ),
            "Ambiguous forms found": str(_one(lines, "AMBIGUOUS")),
            "Enumeration complete": _yes(complete),
        }
    )
    return {
        "definite": definite,
        "complete": complete,
        "metrics": metrics,
        "columns": ["Class", "a", "b", "c", "Ambiguous", "|a| is a square"],
        "rows": rows,
        "truncated": _one(lines, "TRUNCATED") == 1,
        "note": (
            "PARI/GP took the class-group generators from quadclassunit, built one "
            "representative per class with qfbpow and qfbcomp, and reduced with qfbred. "
            + _case_note(definite)
            + " A form is ambiguous when a divides b or a = c, which makes its class its "
            "own inverse. For D = 4kN this is exactly what SQUFOF searches for in the "
            "principal cycle: the leading coefficient of an ambiguous form exposes a "
            "factor of N. See Factor Lab for the SQUFOF implementation itself."
            + (
                ""
                if complete
                else " The enumeration hit its cap, so the list is a prefix and the class "
                "count is inconclusive."
            )
        ),
    }


# ------------------------------------------------------------------ representation
def represent_integer(
    a: str, b: str, c: str, number: str, solution_limit: int = 50, timeout: int = 60
) -> dict:
    """Solve ``a x^2 + b x y + c y^2 = n`` with PARI/GP's ``qfbsolve``.

    Flag 1 returns the primitive solutions up to the automorphism group of the form and
    flag 3 adds the imprimitive ones.  Every returned pair is substituted back into the
    form inside PARI/GP; a mismatch is an engine error, never a returned result.

    Args:
        a: Decimal coefficients of the form.
        b: See ``a``.
        c: See ``a``.
        number: Decimal nonzero integer to represent.
        solution_limit: Maximum solutions to materialize (1–100,000).
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary with one row per solution.

    Raises:
        ValueError: If a bound is violated or an input is not an integer.
        PrimeEngineError: If the discriminant is invalid or PARI/GP failed.
    """
    left, middle, right = _form_coefficients(a, b, c)
    target = _coefficient(number, "integer to represent")
    if not 1 <= solution_limit <= MAX_FORMS:
        raise ValueError(f"Solution limit must be between 1 and {MAX_FORMS:,}")
    lines = _execute(
        f"fl_represent({left},{middle},{right},{target},{solution_limit})", timeout
    )
    records = _records(lines, "SOLUTION", 4)
    if _one(lines, "DONE") != len(records):
        raise PrimeEngineError("PARI/GP returned an incomplete representation result")
    definite = _one(lines, "DEFINITE") == 1
    rows = [[x, y, _yes(int(primitive)), value] for x, y, primitive, value in records]
    metrics = _invariants(lines)
    metrics.update(
        {
            "Form (a, b, c)": ", ".join(_records(lines, "FORM", 3)[0]),
            "Integer n": str(target),
            "Represented": _yes(_one(lines, "REPRESENTED")),
            "Primitive solutions": str(_one(lines, "PRIMITIVE_COUNT")),
            "Solutions found": str(_one(lines, "TOTAL_COUNT")),
        }
    )
    return {
        "definite": definite,
        "represented": _one(lines, "REPRESENTED") == 1,
        "metrics": metrics,
        "columns": ["x", "y", "Primitive", "Q(x, y)"],
        "rows": rows,
        "truncated": _one(lines, "TRUNCATED") == 1,
        "note": (
            "PARI/GP solved the representation with qfbsolve and re-evaluated every pair "
            "in the form. Solutions are listed up to the automorphism group of Q. "
            + _case_note(definite)
            + (
                ""
                if definite
                else " For an indefinite form the automorphism group is infinite, so each "
                "row is the representative of an infinite orbit."
            )
        ),
    }


# ------------------------------------------------------------------ continued fractions
def continued_fraction(
    mode: str = "quadratic",
    numerator: str = "0",
    denominator: str = "1",
    radicand: str = "13",
    quotient_limit: int = 40,
    convergent_limit: int = 40,
    approximation_bound: str = "1000",
    preview_digits: int = DEFAULT_PREVIEW_DIGITS,
    export_path: Path | None = None,
    timeout: int = 60,
) -> dict:
    """Expand a rational or a quadratic irrational as a continued fraction.

    In ``rational`` mode PARI/GP's ``contfrac`` performs the expansion exactly.  In
    ``quadratic`` mode the value is ``(numerator + sqrt(radicand)) / denominator`` and the
    exact ``(P, Q)`` recursion in the GP program produces the expansion with its preperiod
    and period, because ``contfrac`` works on a floating-point real and reports no period;
    the exact prefix is cross-checked against ``contfrac`` at raised precision.
    ``contfracpnqn`` supplies the convergents and ``bestappr`` the best rational
    approximation below the requested denominator bound.

    Args:
        mode: ``"rational"`` or ``"quadratic"``.
        numerator: Decimal numerator ``p``.
        denominator: Decimal nonzero denominator ``q``.
        radicand: Decimal positive non-square ``d``; used in ``quadratic`` mode only.
        quotient_limit: Maximum partial quotients to materialize (1–100,000).
        convergent_limit: Maximum convergents to materialize (1–100,000).
        approximation_bound: Decimal denominator bound handed to ``bestappr``.
        preview_digits: Values longer than this many decimal digits are abbreviated in
            the returned report as ``<first 12>..<last 12> (n digits)`` (1–100,000).  The
            abbreviation is exact at both ends and states the true digit count, and it
            never affects what is written to ``export_path``.
        export_path: When given, PARI/GP writes every partial quotient and every
            convergent to this file at full length, so a convergent with millions of
            digits never passes through the JSON response.
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary; ``complete`` is ``False`` when the period was not closed
        within ``quotient_limit``, which makes the period inconclusive.

    Raises:
        ValueError: If a bound is violated, the mode is unknown, or an input is not an
            integer.
        PrimeEngineError: If ``d`` is a perfect square or PARI/GP failed.
    """
    if mode not in _MODES:
        raise ValueError("Mode must be 'rational' or 'quadratic'")
    top = _coefficient(numerator, "numerator")
    bottom = _coefficient(denominator, "denominator")
    if bottom == 0:
        raise ValueError("The denominator must be nonzero")
    root = _coefficient(radicand, "radicand")
    bound = _coefficient(approximation_bound, "approximation bound")
    if bound < 1:
        raise ValueError("The approximation bound must be at least 1")
    if not 1 <= quotient_limit <= MAX_QUOTIENTS:
        raise ValueError(f"Quotient limit must be between 1 and {MAX_QUOTIENTS:,}")
    if not 1 <= convergent_limit <= MAX_CONVERGENTS:
        raise ValueError(f"Convergent limit must be between 1 and {MAX_CONVERGENTS:,}")
    if not 1 <= preview_digits <= MAX_PREVIEW_DIGITS:
        raise ValueError(f"Preview width must be between 1 and {MAX_PREVIEW_DIGITS:,} digits")
    destination = json.dumps(str(export_path) if export_path is not None else "")
    lines = _execute(
        f"fl_contfrac({_MODES[mode]},{top},{bottom},{root},{quotient_limit},"
        f"{convergent_limit},{bound},{CROSSCHECK_TERMS},{preview_digits},{destination})",
        timeout,
    )
    quotients = _records(lines, "QUOTIENT", 2)
    if _one(lines, "DONE") != len(quotients):
        raise PrimeEngineError("PARI/GP returned an incomplete continued fraction")
    if _one(lines, "CROSSCHECK") == 0:
        raise PrimeEngineError(
            "PARI/GP's contfrac disagreed with the exact continued-fraction expansion"
        )
    if _one(lines, "VERIFIED") == 0:
        raise PrimeEngineError("PARI/GP could not verify the rational convergents")
    convergents = _records(lines, "CONVERGENT", 3)
    widths = _records(lines, "CONVERGENT_DIGITS", 3)
    if len(widths) != len(convergents):
        raise PrimeEngineError("PARI/GP returned an inconsistent convergent width count")
    approximation = _records(lines, "BESTAPPR", 3)[0]
    if _one(lines, "EXPORTED") != (1 if export_path is not None else 0):
        raise PrimeEngineError("PARI/GP did not write the full-precision expansion")
    abbreviated = _one(lines, "ABBREVIATED") == 1
    widest = max((int(row[2]) for row in widths), default=0)
    complete = _one(lines, "COMPLETE") == 1
    period = _one(lines, "PERIOD")
    preperiod = _one(lines, "PREPERIOD")
    quotient_values = {int(index): value for index, value in quotients}
    rows = [
        [
            index,
            p,
            q,
            quotient_values.get(int(index), "—"),
            "terminating"
            if mode == "rational"
            else "periodic"
            if 0 <= preperiod <= int(index)
            else "preperiod",
        ]
        for index, p, q in convergents
    ]
    metrics = {
        "Value": _text(lines, "VALUE") or "—",
        "Kind": "rational" if mode == "rational" else "quadratic irrational",
        "Partial quotients listed": str(len(quotients)),
        "Preperiod length": _count(preperiod) if mode == "quadratic" else "—",
        "Period length": _count(period) if mode == "quadratic" else "—",
        "Period": _text(lines, "PERIOD_TERMS") or "—",
        "Period head is palindromic": (
            _three_way(_one(lines, "PALINDROMIC"))
            if mode == "quadratic"
            else "—"
        ),
        "Cross-checked against contfrac": (
            "—" if mode == "rational" else _three_way(_one(lines, "CROSSCHECK"))
        ),
        "Convergents listed": str(len(convergents)),
        "Widest convergent denominator": f"{widest:,} decimal digits",
        "Values abbreviated in this response": _yes(abbreviated),
        f"Best approximation with denominator ≤ {approximation[2]}": (
            f"{approximation[0]}/{approximation[1]}"
        ),
        "Expansion complete": _yes(complete),
    }
    return {
        "mode": mode,
        "complete": complete,
        "abbreviated": abbreviated,
        "metrics": metrics,
        "columns": ["n", "p_n", "q_n", "a_n", "Segment"],
        "rows": rows,
        "truncated": _one(lines, "TRUNCATED") == 1,
        "note": (
            "PARI/GP expanded the rational with contfrac, formed the convergents with "
            "contfracpnqn, and found the best approximation with bestappr; the final "
            "convergent was compared with the input."
            if mode == "rational"
            else "The exact (P, Q) recursion produced the expansion and its period — "
            "contfrac takes a floating-point real, so its tail is unreliable and it "
            "reports no period — and the prefix was cross-checked against contfrac at "
            "raised precision. contfracpnqn formed the convergents and bestappr the best "
            "approximation. For sqrt(d) the period is [a₁, …, a_{L−1}, 2a₀] with a "
            "palindromic head, and the convergent at the end of the period solves Pell's "
            "equation. CFRAC built congruences of squares from exactly these convergents; "
            "Numerisect does not implement CFRAC as a factoring method because SIQS "
            "supersedes it at every size, so this tool is exposition rather than a "
            "factoring path."
        )
        + ("" if complete else " The period was not closed within the quotient limit, so it "
           "is inconclusive.")
        + (
            f" Values longer than {preview_digits:,} digits are abbreviated above as "
            "first and last twelve digits with an exact digit count; the saved report "
            "carries every partial quotient and convergent at full length."
            if abbreviated
            else ""
        ),
    }


# ------------------------------------------------------------------ Pell
def pell_solutions(
    d: str,
    solution_count: int = 3,
    digit_limit: int = 2_000,
    period_limit: int = 100_000,
    unit_seconds: int = 30,
    export_path: Path | None = None,
    timeout: int = 120,
) -> dict:
    """Solve Pell's equation ``x^2 - d y^2 = 1`` and list further solutions.

    ``quadunit(4d)`` is the fundamental unit ``x + y*sqrt(d)`` of the order ``Z[sqrt(d)]``,
    so it is the fundamental solution of ``x^2 - d y^2 = norm(u)`` directly.  When that
    norm is ``-1`` the negative Pell equation ``x^2 - d y^2 = -1`` is solvable and the
    fundamental Pell solution is the square of the unit; when it is ``+1`` the negative
    equation has no solution.  ``quadregulator(4d)`` is the logarithm of the same unit.
    Every solution is verified in PARI/GP and cross-checked against ``bestappr``.

    Args:
        d: Decimal integer at least 2 and not a perfect square.
        solution_count: How many successive solutions to list (1–100).
        digit_limit: Values longer than this many decimal digits are abbreviated in the
            returned report as ``<first 12>..<last 12> (n digits)`` (1–100,000).  No
            solution is ever omitted, and the abbreviation never affects ``export_path``.
        period_limit: Cap on the continued-fraction period searched for the cross-check
            (1–100,000).
        unit_seconds: Budget for ``quadunit`` (1–3,600 seconds).
        export_path: When given, PARI/GP writes the fundamental unit, the fundamental
            solution and every listed solution to this file at full length.  Pell
            solutions grow without bound — for ``d = 1000099`` the fundamental solution
            already has 1,128 decimal digits and the fourth has 4,513 — so the complete
            values are streamed to the file rather than through the JSON response.
        timeout: Engine time limit in seconds.

    Returns:
        A report dictionary.  ``available`` is ``False`` when ``quadunit`` exceeded its
        budget, in which case no solution is claimed.

    Raises:
        ValueError: If a bound is violated or ``d`` is not an integer.
        PrimeEngineError: If ``d`` is a perfect square, is below 2, or PARI/GP failed.
    """
    value = _coefficient(d, "radicand d")
    if not 1 <= solution_count <= MAX_PELL_SOLUTIONS:
        raise ValueError(f"Solution count must be between 1 and {MAX_PELL_SOLUTIONS}")
    if not 1 <= digit_limit <= MAX_PELL_DIGITS:
        raise ValueError(f"Digit limit must be between 1 and {MAX_PELL_DIGITS:,}")
    if not 1 <= period_limit <= MAX_QUOTIENTS:
        raise ValueError(f"Period limit must be between 1 and {MAX_QUOTIENTS:,}")
    if not 1 <= unit_seconds <= 3600:
        raise ValueError("The fundamental-unit budget must be between 1 and 3,600 seconds")
    destination = json.dumps(str(export_path) if export_path is not None else "")
    lines = _execute(
        f"fl_pell({value},{solution_count},{digit_limit},{period_limit},"
        f"{PELL_CHECK_DIGITS},{unit_seconds},{destination})",
        timeout,
    )
    rows = _records(lines, "SOLUTION", 3)
    if _one(lines, "DONE") != len(rows):
        raise PrimeEngineError("PARI/GP returned an incomplete Pell result")
    available = _one(lines, "AVAILABLE") == 1
    if not available:
        return {
            "available": False,
            "metrics": {
                "d": str(value),
                "Fundamental unit computed": "no",
                "Fundamental solution": "inconclusive",
            },
            "columns": ["k", "x", "y"],
            "rows": [],
            "truncated": True,
            "note": (
                "PARI/GP's quadunit exceeded its budget for this d, so the fundamental "
                "solution is inconclusive. Raise the fundamental-unit budget and retry; "
                "no solution is claimed here."
            ),
        }
    if _one(lines, "VERIFIED") != 1:
        raise PrimeEngineError("PARI/GP could not verify the Pell solutions")
    if _one(lines, "CF_MATCH") == 0:
        raise PrimeEngineError(
            "The fundamental unit disagreed with the continued-fraction convergent"
        )
    if _one(lines, "EXPORTED") != (1 if export_path is not None else 0):
        raise PrimeEngineError("PARI/GP did not write the full-precision Pell solutions")
    abbreviated = _one(lines, "ABBREVIATED") == 1
    negative = _one(lines, "NEGATIVE_SOLVABLE") == 1
    unit_norm = _one(lines, "UNIT_NORM")
    unit_x = _text(lines, "UNIT_X") or "—"
    unit_y = _text(lines, "UNIT_Y") or "—"
    fund_x = _text(lines, "FUND_X") or "—"
    fund_y = _text(lines, "FUND_Y") or "—"
    metrics = {
        "d": str(value),
        "Regulator of Z[√d]": _text(lines, "REGULATOR") or "—",
        "Fundamental unit x + y√d": f"{unit_x} + {unit_y}√{value}",
        "Norm of the fundamental unit": str(unit_norm),
        "x² − dy² = −1 solvable": _yes(negative),
        "Fundamental solution x": fund_x,
        "Fundamental solution y": fund_y,
        "Fundamental solution size": (
            f"x has {_one(lines, 'FUND_X_DIGITS'):,} decimal digits, "
            f"y has {_one(lines, 'FUND_Y_DIGITS'):,}"
        ),
        "Continued-fraction period of √d": _count(_one(lines, "CF_PERIOD")),
        "Matches the convergent at the end of the period": _three_way(
            _one(lines, "CF_MATCH")
        ),
        "Solutions listed": str(len(rows)),
        "Values abbreviated in this response": _yes(abbreviated),
    }
    if negative:
        metrics["Negative Pell solution"] = f"{unit_x}² − {value}·{unit_y}² = −1"
    return {
        "available": True,
        "negative_solvable": negative,
        "abbreviated": abbreviated,
        "metrics": metrics,
        "columns": ["k", "x", "y"],
        "rows": rows,
        "truncated": _one(lines, "TRUNCATED") == 1,
        "note": (
            "PARI/GP computed the fundamental unit of the order Z[√d] with quadunit and "
            "its logarithm with quadregulator; the unit is the fundamental solution "
            "directly, squared when its norm is −1. Successive solutions are its powers, "
            "and every pair was verified as x² − dy² = 1 inside PARI/GP. bestappr "
            "confirmed independently that the fundamental solution is the convergent of "
            "√d at the end of its period, which is the classical link between Pell's "
            "equation and continued fractions."
            + (
                f" Values longer than {digit_limit:,} digits are abbreviated above as "
                "first and last twelve digits with an exact digit count. No solution is "
                "omitted"
                + (
                    "; the saved report carries every value at full length."
                    if export_path is not None
                    else "."
                )
                if abbreviated
                else ""
            )
        ),
    }
