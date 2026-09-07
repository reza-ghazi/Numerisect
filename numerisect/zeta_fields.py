"""PARI/GP boundary for Dedekind zeta functions of bounded number fields.

PARI/GP is the engine for this tranche because FLINT/Arb has no Dedekind zeta
implementation. ``numerisect/zeta_fields.gp`` performs every computation with
``nfinit``, ``bnfinit``, ``polcyclo``, ``lfuncreate``, ``lfuncheckfeq``,
``lfun``, ``lfunrootres`` and ``lfunzeros``; this module only validates the
request, launches ``gp``, and parses the tagged output.

Unlike the FLINT-backed tools in :mod:`numerisect.zeta`, PARI returns
floating-point values at a requested ``realprecision`` with no rigorous error
bound. Nothing produced here is an Arb ball enclosure, and every response says
so explicitly.
"""

from __future__ import annotations

import re
from pathlib import Path

from .primes import PrimeEngineError, _run_gp
from .zeta import ZetaEngineError, validated_real

PROGRAM = Path(__file__).with_name("zeta_fields.gp")

#: Largest field degree accepted; ``lfunzeros`` becomes impractical beyond this.
MAX_DEGREE = 8
#: Largest absolute field discriminant accepted.
MAX_DISCRIMINANT = 10**12
#: Default wall-clock limit for a single ``gp`` invocation, in seconds.
DEFAULT_TIMEOUT = 300

FIELD_FAMILIES = ("quadratic", "cyclotomic", "polynomial")
_POLYNOMIAL = re.compile(r"[0-9x^*+\- ]{1,200}")
_NUMBER = re.compile(r"[+-]?\d+(?:\.\d*)?(?:E[+-]?\d+)?")


def _program() -> str:
    try:
        return PROGRAM.read_text(encoding="utf-8")
    except OSError as exc:
        raise ZetaEngineError("The PARI/GP Dedekind-zeta program is unavailable") from exc


def _execute(call: str, precision: int, timeout: int) -> list[str]:
    program = f"default(realprecision,{precision});\n{_program()}\n{call};"
    try:
        lines = _run_gp(program, timeout=timeout)
    except PrimeEngineError as exc:
        raise ZetaEngineError(str(exc)) from exc
    if not any(line.startswith("DONE:") for line in lines):
        raise ZetaEngineError("PARI/GP returned an incomplete Dedekind-zeta result")
    return lines


def _tag(lines: list[str], tag: str) -> str:
    prefix = f"{tag}:"
    values = [line[len(prefix):].replace(" ", "") for line in lines if line.startswith(prefix)]
    if len(values) != 1:
        raise ZetaEngineError(f"PARI/GP returned an invalid {tag.lower()} result")
    return values[0]


def _optional_tag(lines: list[str], tag: str) -> str | None:
    prefix = f"{tag}:"
    values = [line[len(prefix):].replace(" ", "") for line in lines if line.startswith(prefix)]
    if len(values) > 1:
        raise ZetaEngineError(f"PARI/GP returned an invalid {tag.lower()} result")
    return values[0] if values else None


def _rows(lines: list[str], tag: str, width: int) -> list[list[str]]:
    prefix = f"{tag}:"
    rows = [line[len(prefix):].replace(" ", "").split("|")
            for line in lines if line.startswith(prefix)]
    if any(len(row) != width for row in rows):
        raise ZetaEngineError(f"PARI/GP returned an invalid {tag.lower()} record")
    return rows


def _number(value: str) -> float:
    if not _NUMBER.fullmatch(value):
        raise ZetaEngineError("PARI/GP returned a nonnumeric value")
    return float(value)


def _field_call(family: str, parameter: str, polynomial: str) -> str:
    """Build the validated PARI expression that defines the number field."""

    if family not in FIELD_FAMILIES:
        raise ValueError("Field family must be quadratic, cyclotomic, or polynomial")
    if family == "polynomial":
        text = polynomial.strip()
        if not text or not _POLYNOMIAL.fullmatch(text):
            raise ValueError(
                "The defining polynomial may only use x, digits, spaces and + - * ^"
            )
        return f"({text})"
    normalized = parameter.strip().replace("_", "")
    if not re.fullmatch(r"-?\d+", normalized):
        raise ValueError("The field parameter must be a decimal integer")
    number = int(normalized)
    if family == "quadratic":
        if not -10**6 <= number <= 10**6 or number in (0, 1):
            raise ValueError("The quadratic radicand must be a nonzero integer up to 10^6")
        return f"zf_field_polynomial(0,{number})"
    if not 3 <= number <= 200:
        raise ValueError("The cyclotomic index must lie between 3 and 200")
    return f"zf_field_polynomial(1,{number})"


def dedekind_zeta(
    family: str,
    parameter: str = "-1",
    polynomial: str = "",
    sigma: str = "2",
    ordinate: str = "0",
    zero_height: int = 30,
    zero_limit: int = 50,
    class_data: bool = True,
    precision: int = 38,
    timeout_seconds: int = DEFAULT_TIMEOUT,
) -> dict[str, object]:
    """Analyse the Dedekind zeta function of a bounded number field with PARI/GP.

    Every quantity is produced by PARI: ``nfinit`` (field data), ``polcyclo``
    (cyclotomic defining polynomial), ``lfuncreate`` (the L-function object),
    ``lfuncheckfeq`` (functional-equation self-test), ``lfun`` (the value at s),
    ``lfunrootres`` (the pole and its residue), ``lfunzeros`` (critical-line
    ordinates) and ``bnfinit`` (class number, regulator, torsion) for the
    analytic class-number-formula cross-check.

    Args:
        family: ``quadratic``, ``cyclotomic`` or ``polynomial``.
        parameter: Radicand for a quadratic field or index for a cyclotomic one.
        polynomial: Defining polynomial when ``family`` is ``polynomial``.
        sigma: Real part of the evaluation point; s = 1 is the pole.
        ordinate: Imaginary part of the evaluation point.
        zero_height: Upper ordinate for ``lfunzeros``.
        zero_limit: Maximum number of zero rows returned.
        class_data: Run ``bnfinit`` for the class-number-formula cross-check.
        precision: PARI ``realprecision`` in decimal digits.
        timeout_seconds: Wall-clock limit for the ``gp`` process.

    Returns:
        Field invariants, the value of ζ_K(s), the residue at s = 1, the
        class-number-formula comparison and the located zero ordinates. Every
        value uses PARI floating-point precision semantics, not Arb balls.

    Raises:
        ValueError: An input failed validation or exceeded a configured bound.
        ZetaEngineError: PARI/GP failed, timed out, or returned an incomplete
            result (degree or discriminant beyond the configured bounds).
    """

    if not 1 <= zero_height <= 200:
        raise ValueError("The zero height must lie between 1 and 200")
    if not 1 <= zero_limit <= 500:
        raise ValueError("The zero limit must lie between 1 and 500")
    if not 20 <= precision <= 200:
        raise ValueError("PARI realprecision must lie between 20 and 200 digits")
    if not 1 <= timeout_seconds <= 3600:
        raise ValueError("The engine time limit must lie between 1 and 3,600 seconds")
    sigma = validated_real(sigma, "Real part")
    ordinate = validated_real(ordinate, "Imaginary part")
    if sigma == "1" and float(ordinate) == 0.0:
        raise ValueError("s = 1 is the simple pole of every Dedekind zeta function")
    call = (
        f"zf_dedekind({_field_call(family, parameter, polynomial)},{sigma},{ordinate},"
        f"{zero_height},{zero_limit},{MAX_DEGREE},{MAX_DISCRIMINANT},"
        f"{1 if class_data else 0})"
    )
    lines = _execute(call, precision, timeout_seconds)

    value = _rows(lines, "LVALUE", 2)
    if len(value) != 1:
        raise ZetaEngineError("PARI/GP returned an invalid L-value")
    poles = _rows(lines, "POLE", 2)
    if len(poles) != int(_tag(lines, "POLECOUNT")):
        raise ZetaEngineError("PARI/GP returned an inconsistent pole count")
    zeros = _rows(lines, "ZERO", 2)
    if len(zeros) != int(_tag(lines, "DONE")):
        raise ZetaEngineError("PARI/GP did not return every located zero")
    truncated = _tag(lines, "TRUNCATED")
    if truncated not in {"0", "1"}:
        raise ZetaEngineError("PARI/GP returned an invalid truncation flag")
    signature = _rows(lines, "SIGNATURE", 2)
    if len(signature) != 1:
        raise ZetaEngineError("PARI/GP returned an invalid field signature")

    residue = _optional_tag(lines, "CNF_RESIDUE")
    analytic = poles[0][1] if poles else None
    result: dict[str, object] = {
        "family": family,
        "polynomial": _tag(lines, "POLYNOMIAL"),
        "degree": _tag(lines, "DEGREE"),
        "real_places": signature[0][0],
        "complex_places": signature[0][1],
        "discriminant": _tag(lines, "DISCRIMINANT"),
        "functional_equation_log2_error": _tag(lines, "FEQ"),
        "sigma": sigma,
        "ordinate": ordinate,
        "value_real": value[0][0],
        "value_imaginary": value[0][1],
        "poles": [{"point": row[0], "residue": row[1]} for row in poles],
        "zero_height": zero_height,
        "zeros_found": _tag(lines, "ZEROCOUNT"),
        "truncated": truncated == "1",
        "zeros": [{"index": row[0], "ordinate": row[1]} for row in zeros],
        "engine": "PARI/GP",
        "rigorous": False,
    }
    if residue is not None:
        result["class_number"] = _tag(lines, "CLASSNUMBER")
        result["regulator"] = _tag(lines, "REGULATOR")
        result["torsion_units"] = _tag(lines, "TORSION")
        result["class_number_formula_residue"] = residue
        if analytic is not None:
            difference = abs(_number(analytic) - _number(residue))
            result["residue_difference"] = f"{difference:.6g}"
    result["note"] = (
        "PARI/GP computed every value with lfuncreate(nfinit(...)), lfun, lfunrootres, "
        f"lfuncheckfeq and lfunzeros at realprecision {precision}. These are PARI "
        "floating-point results, not Arb ball enclosures: they carry no rigorous error "
        "bound, so treat them as high-precision numerics rather than certifications. "
        f"lfuncheckfeq reports the base-2 logarithm of the functional-equation error "
        f"({_tag(lines, 'FEQ')}); a large negative value means the object is consistent. "
        f"The field is capped at degree {MAX_DEGREE} and |disc| ≤ {MAX_DISCRIMINANT}, and "
        f"the run is capped at {timeout_seconds} seconds."
    )
    return result
