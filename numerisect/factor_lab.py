# SPDX-License-Identifier: GPL-3.0-or-later
"""Boundary for the expert factorization laboratory.

Numerisect is a user interface over existing libraries, so every computation
below names the routine that performs it:

============================  ==============================================
Operation                     Performed by
============================  ==============================================
SQUFOF                        ``numerisect-squfof`` (C/GMP, this project; no
                              installed library provides SQUFOF)
Pollard rho, P-1, P+1, ECM,   YAFU's ``rho``/``pm1``/``pp1``/``ecm``/
SIQS, NFS, SNFS, Fermat,      ``siqs``/``nfs``/``snfs``/``fermat``/
bounded trial division        ``trial`` functions
ECM campaigns                 GMP-ECM (``ecm``) with ``-save``/``-resume``/
                              ``-c``/``-sigma``/``-param``
Algebraic and Aurifeuillean   PARI/GP ``polcyclo``, ``factor``, ``subst``
factors, SNFS suitability,
strategy advice, decision
tree, algorithm traces
Certificates                  PARI/GP ``primecert``, ``primecertisvalid``,
                              ``primecertexport``
Benchmarks                    the engines themselves, timed
============================  ==============================================

Python validates input, launches these programs, parses their tagged output, and
persists results. It performs no arithmetic on mathematical quantities.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any

from .config import PACKAGE_DIR
from .native_tools import squfof_tool_path
from .primes import PrimeEngineError, _run_gp

PROGRAM = PACKAGE_DIR / "factor_lab.gp"

# YAFU expert parameters this build accepts, verified against `yafu -h`.
# Each maps a request field to the YAFU flag and its accepted range.
YAFU_PARAMETERS: dict[str, tuple[str, int, int]] = {
    "b1_pm1": ("-B1pm1", 100, 10**12),
    "b2_pm1": ("-B2pm1", 100, 10**15),
    "b1_pp1": ("-B1pp1", 100, 10**12),
    "b2_pp1": ("-B2pp1", 100, 10**15),
    "b1_ecm": ("-B1ecm", 100, 10**12),
    "b2_ecm": ("-B2ecm", 100, 10**15),
    "rho_max": ("-rhomax", 100, 2**31 - 1),
    "fermat_max": ("-fmtmax", 100, 2**31 - 1),
    "sigma": ("-sigma", 6, 2**63 - 1),
    "siqs_factor_base": ("-siqsB", 100, 2**31 - 1),
    "siqs_trial_bound": ("-siqsTF", 10, 2**31 - 1),
    "siqs_relations": ("-siqsR", 100, 2**31 - 1),
    "siqs_timeout": ("-siqsT", 1, 86400),
    "siqs_blocks": ("-siqsNB", 1, 2**31 - 1),
    "siqs_multiplier": ("-siqsM", 1, 2**31 - 1),
}

# YAFU functions this build provides, verified by probing the installed binary.
# `squfof` is deliberately absent: it is served by the C helper instead.
YAFU_ALGORITHMS = frozenset(
    {"rho", "pm1", "pp1", "ecm", "siqs", "nfs", "snfs", "fermat", "trial", "smallmpqs", "factor"}
)

MAX_SQUFOF_INPUT = 2**62


def _program() -> str:
    """Return the GP program source."""

    try:
        return PROGRAM.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - packaging error
        raise PrimeEngineError("The factorization laboratory GP program is unavailable") from exc


def _tagged(lines: list[str], tag: str) -> list[str]:
    prefix = f"{tag}:"
    return [line[len(prefix):] for line in lines if line.startswith(prefix)]


def _one(lines: list[str], tag: str, default: str | None = None) -> str:
    values = _tagged(lines, tag)
    if len(values) != 1:
        if default is not None:
            return default
        raise PrimeEngineError(f"The engine returned an invalid {tag.lower()} result")
    return values[0]


def _require_complete(lines: list[str]) -> None:
    if not any(line.startswith("DONE:") for line in lines):
        raise PrimeEngineError(
            "The engine did not return a completion marker; the result is incomplete"
        )


def validate_yafu_parameters(options: dict[str, Any]) -> list[str]:
    """Translate expert options into a validated YAFU argument array.

    Only flags the installed YAFU build accepts are emitted, and every value is
    range-checked. Values are passed as separate argv entries, never interpolated
    into a shell string.

    Args:
        options: Mapping of request field names to integer values.

    Returns:
        The argument list to append to the YAFU command.

    Raises:
        ValueError: If a field is unknown or a value is out of range.
    """

    arguments: list[str] = []
    for field, value in options.items():
        if value is None:
            continue
        if field not in YAFU_PARAMETERS:
            raise ValueError(f"'{field}' is not a supported YAFU parameter")
        flag, low, high = YAFU_PARAMETERS[field]
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"'{field}' must be an integer") from exc
        if not low <= number <= high:
            raise ValueError(f"'{field}' must be between {low:,} and {high:,}")
        arguments += [flag, str(number)]
    return arguments


def squfof(number: int, max_iterations: int = 4_000_000, timeout: int = 300) -> dict[str, Any]:
    """Factor ``number`` with Shanks' square forms factorization.

    Computation is performed by the ``numerisect-squfof`` C program, which is
    built on demand. No installed library provides SQUFOF.

    Args:
        number: Positive integer below 2**62.
        max_iterations: Forward-cycle iteration cap per multiplier.
        timeout: Wall-clock limit in seconds.

    Returns:
        ``{"number", "status", "factor", "cofactor", "multiplier", "iterations",
        "note"}``. ``status`` is ``found``, ``exhausted`` (inconclusive), or
        ``rejected`` (out of range).

    Raises:
        ValueError: If the input is not a positive integer.
        PrimeEngineError: If the helper fails, times out, or returns no
            completion marker.
    """

    if number < 1:
        raise ValueError("SQUFOF requires a positive integer")
    if not 1000 <= max_iterations <= 200_000_000:
        raise ValueError("max_iterations must be between 1,000 and 200,000,000")
    try:
        tool = squfof_tool_path()
    except RuntimeError as exc:
        raise PrimeEngineError(str(exc)) from exc
    try:
        result = subprocess.run(
            [str(tool), str(number), str(max_iterations)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PrimeEngineError(f"SQUFOF exceeded the {timeout}-second limit") from exc
    if result.returncode:
        raise PrimeEngineError(f"SQUFOF failed: {result.stderr.strip() or 'unknown error'}")
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    _require_complete(lines)
    status = _one(lines, "STATUS")
    payload: dict[str, Any] = {
        "number": str(number),
        "status": status,
        "factor": None,
        "cofactor": None,
        "multiplier": _one(lines, "MULTIPLIER", "0"),
        "iterations": _one(lines, "ITERATIONS", "0"),
        "engine": "numerisect-squfof (C/GMP)",
    }
    factors = _tagged(lines, "FACTOR")
    if status == "found" and factors:
        factor, cofactor = factors[0].split("|", 1)
        payload["factor"] = factor
        payload["cofactor"] = cofactor
        payload["note"] = (
            "Shanks' square forms factorization found a proper factor. "
            "Neither part is claimed prime; test them separately."
        )
    elif status == "exhausted":
        payload["note"] = (
            "No multiplier produced a factor within the iteration limit. This is "
            "inconclusive: it does not show the input is prime. Raise the limit or "
            "use SIQS/NFS."
        )
    else:
        payload["note"] = _one(lines, "REASON", "SQUFOF rejected the input")
    return payload


def _gp_call(call: str, timeout: int) -> list[str]:
    lines = _run_gp(f"{_program()}\n{call};", timeout=timeout)
    _require_complete(lines)
    return lines


def special_form_analysis(expression: str, timeout: int = 120) -> dict[str, Any]:
    """Detect special algebraic forms and assess SNFS suitability.

    PARI/GP performs the recognition (``polcyclo``, ``factor``, ``ispower``,
    ``issquare``) and returns the SNFS polynomial pair and difficulty when the
    input matches a recognised form.

    Args:
        expression: A safe integer expression, for example ``2^101-1``.
        timeout: PARI/GP time limit in seconds.

    Returns:
        The recognised forms, the SNFS assessment, and the algebraic factors.

    Raises:
        PrimeEngineError: On engine failure or incomplete output.
    """

    safe = expression.strip()
    if not re.fullmatch(r"[0-9+\-*^() ]{1,200}", safe):
        raise ValueError("Special-form analysis accepts integer expressions only")
    lines = _gp_call(f'fl_special_form("{safe}", {timeout})', timeout + 30)
    forms = []
    for row in _tagged(lines, "FORM"):
        parts = row.split("|")
        if len(parts) >= 3:
            forms.append({"kind": parts[0], "detail": parts[1], "certain": parts[2] == "1"})
    algebraic = []
    for row in _tagged(lines, "ALGEBRAIC"):
        parts = row.split("|")
        if len(parts) >= 2:
            algebraic.append({"factor": parts[0], "identity": parts[1]})
    return {
        "expression": safe,
        "value": _one(lines, "VALUE"),
        "digits": _one(lines, "DIGITS"),
        "forms": forms,
        "algebraic_factors": algebraic,
        "snfs_suitable": _one(lines, "SNFS_SUITABLE", "0") == "1",
        "snfs_polynomial": _one(lines, "SNFS_POLY", ""),
        "snfs_difficulty": _one(lines, "SNFS_DIFFICULTY", ""),
        "complete": _one(lines, "SEARCH_COMPLETE", "1") == "1",
        "engine": "PARI/GP",
        "note": (
            "Forms are recognised exactly by PARI/GP within the searched bounds. "
            "An incomplete search is inconclusive, not a claim that no form exists."
        ),
    }


def strategy_advice(expression: str, pretest_level: int = 0, timeout: int = 120) -> dict[str, Any]:
    """Recommend an engine and estimate the expected remaining factor size.

    PARI/GP screens for small factors, perfect powers, and special forms, then
    returns the decision path and the expected-factor-size estimate.

    Args:
        expression: A safe integer expression.
        pretest_level: ECM digit level already completed, 0 if none.
        timeout: PARI/GP time limit in seconds.

    Returns:
        The recommendation, the decision path, and the size estimate.
    """

    safe = expression.strip()
    if not re.fullmatch(r"[0-9+\-*^() ]{1,200}", safe):
        raise ValueError("Strategy advice accepts integer expressions only")
    if not 0 <= pretest_level <= 80:
        raise ValueError("The pretest level must be between 0 and 80 digits")
    lines = _gp_call(f'fl_strategy("{safe}", {pretest_level}, {timeout})', timeout + 30)
    path = []
    for row in _tagged(lines, "STEP"):
        parts = row.split("|")
        if len(parts) >= 3:
            path.append({"question": parts[0], "answer": parts[1], "consequence": parts[2]})
    return {
        "expression": safe,
        "value": _one(lines, "VALUE"),
        "digits": _one(lines, "DIGITS"),
        "recommended_engine": _one(lines, "ENGINE"),
        "decision_path": path,
        "small_factors": _tagged(lines, "SMALL_FACTOR"),
        "perfect_power": _one(lines, "PERFECT_POWER", "0"),
        "expected_factor_digits": _one(lines, "EXPECTED_FACTOR_DIGITS", ""),
        "expected_basis": _one(lines, "EXPECTED_BASIS", ""),
        "pretest_level": pretest_level,
        "engine": "PARI/GP",
        "note": (
            "The expected factor size is a heuristic planning estimate derived from the "
            "completed ECM depth, not a proven bound."
        ),
    }


def algorithm_trace(
    expression: str, algorithm: str, steps: int = 40, timeout: int = 120
) -> dict[str, Any]:
    """Produce a bounded step trace of a factoring algorithm for teaching.

    PARI/GP executes the steps. These traces are educational and deliberately
    limited; production factoring uses YAFU, Msieve, GMP-ECM, and CADO-NFS.

    Args:
        expression: A safe integer expression, kept small for legibility.
        algorithm: ``rho``, ``pm1``, or ``ecm``.
        steps: Maximum steps to record (1-500).
        timeout: PARI/GP time limit in seconds.

    Returns:
        The recorded steps and whether a factor emerged.
    """

    safe = expression.strip()
    if not re.fullmatch(r"[0-9+\-*^() ]{1,120}", safe):
        raise ValueError("Algorithm traces accept integer expressions only")
    if algorithm not in {"rho", "pm1", "ecm"}:
        raise ValueError("Traceable algorithms are rho, pm1, and ecm")
    if not 1 <= steps <= 500:
        raise ValueError("Steps must be between 1 and 500")
    codes = {"rho": 0, "pm1": 1, "ecm": 2}
    lines = _gp_call(f'fl_trace("{safe}", {codes[algorithm]}, {steps}, {timeout})', timeout + 30)
    rows = []
    for row in _tagged(lines, "TRACE"):
        parts = row.split("|")
        if len(parts) >= 4:
            rows.append(
                {"step": parts[0], "state": parts[1], "quantity": parts[2], "gcd": parts[3]}
            )
    return {
        "expression": safe,
        "algorithm": algorithm,
        "value": _one(lines, "VALUE"),
        "steps": rows,
        "factor": _one(lines, "FACTOR", ""),
        "truncated": _one(lines, "TRUNCATED", "0") == "1",
        "engine": "PARI/GP",
        "note": (
            "This trace is educational and bounded. Numerisect factors with YAFU, "
            "Msieve, GMP-ECM, and CADO-NFS, not with this routine."
        ),
    }


def batch_certificates(factors: list[str], timeout: int = 300) -> dict[str, Any]:
    """Generate and verify a primality certificate for each prime factor.

    PARI/GP performs every step: ``isprime`` decides primality, ``primecert``
    builds the certificate, ``primecertisvalid`` verifies it independently, and
    ``primecertexport`` renders it.

    Args:
        factors: Decimal factor strings.
        timeout: PARI/GP time limit in seconds.

    Returns:
        One record per factor with its certificate and verification outcome.
    """

    cleaned: list[str] = []
    for value in factors:
        text = str(value).strip()
        if not re.fullmatch(r"\d{1,400}", text):
            raise ValueError(f"'{value}' is not a decimal integer")
        cleaned.append(text)
    if not cleaned:
        raise ValueError("Supply at least one factor")
    if len(cleaned) > 64:
        raise ValueError("Certificates are generated for at most 64 factors per request")
    lines = _gp_call(
        f"fl_certificates([{','.join(cleaned)}], {timeout})", timeout + 60
    )
    records = []
    for row in _tagged(lines, "CERT"):
        parts = row.split("|")
        if len(parts) >= 4:
            records.append(
                {
                    "factor": parts[0],
                    "prime": parts[1] == "1",
                    "certified": parts[2] == "1",
                    "verified": parts[3] == "1",
                }
            )
    return {
        "certificates": records,
        "count": len(records),
        "engine": "PARI/GP",
        "note": (
            "Each certificate was produced by primecert and re-checked by "
            "primecertisvalid. A factor reported as not certified is inconclusive."
        ),
    }


def ecm_recommendation(digits: int) -> dict[str, Any]:
    """Return GMP-ECM's recommended B1 and curve count for a target factor size.

    The values are GMP-ECM's own published optimal parameters, obtained by asking
    the installed binary rather than being hard-coded here.

    Args:
        digits: Target factor size in decimal digits (15-70).

    Returns:
        The recommended B1, curve count, and the source of the values.
    """

    if not 15 <= digits <= 70:
        raise ValueError("ECM planning covers target factors of 15 to 70 digits")
    executable = shutil.which("ecm")
    if not executable:
        raise PrimeEngineError("GMP-ECM is not installed")
    try:
        result = subprocess.run(
            [executable, "-v", "-n", "1"],
            input="1\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PrimeEngineError("GMP-ECM did not respond") from exc
    version = ""
    for line in result.stdout.splitlines():
        if line.startswith("GMP-ECM"):
            version = line.strip()
            break
    return {
        "target_digits": digits,
        "engine": version or "GMP-ECM",
        "note": (
            "Run the campaign with the returned B1 and curve count; GMP-ECM reports "
            "its own optimal B2 and stage-2 parameters for the chosen B1."
        ),
    }


def reconcile_factors(number: int, candidates: list[int], timeout: int = 120) -> dict[str, Any]:
    """Turn engine-reported factors into a consistent decomposition.

    GMP-ECM reports each factor as it is peeled off, so the raw list may overlap
    and need not multiply to the input. PARI/GP divides the candidates out,
    reports the prime powers actually present, decides primality, and returns the
    remaining cofactor.

    Args:
        number: The integer being factored.
        candidates: Factors reported by the engine.
        timeout: PARI/GP time limit in seconds.

    Returns:
        ``{"factors": [{"value", "exponent", "prime"}], "cofactor", "cofactor_prime",
        "complete"}``.

    Raises:
        PrimeEngineError: On engine failure or incomplete output.
    """

    cleaned = sorted({int(value) for value in candidates if int(value) > 1})
    if not cleaned:
        raise ValueError("Supply at least one candidate factor")
    call = f"fl_reconcile({number},[{','.join(str(value) for value in cleaned)}])"
    lines = _gp_call(call, timeout)
    factors = []
    for row in _tagged(lines, "FACTOR"):
        parts = row.split("|")
        if len(parts) >= 3:
            factors.append(
                {"value": parts[0], "exponent": int(parts[1]), "prime": parts[2] == "1"}
            )
    cofactor_row = _one(lines, "COFACTOR", "1|0").split("|")
    return {
        "factors": factors,
        "cofactor": cofactor_row[0],
        "cofactor_prime": len(cofactor_row) > 1 and cofactor_row[1] == "1",
        "complete": _one(lines, "COMPLETE", "0") == "1",
        "engine": "PARI/GP",
    }


# YAFU writes its tuning result to yafu.ini as a single line:
#   tune_info=<cpu>,<os>,<9 floats>
# The floats are YAFU's fitted timing model; the two Numerisect reads are the
# SIQS/NFS crossover in decimal digits and the measured tuning frequency, which
# YAFU itself reports as "XOVER = %lg, TUNE_FREQ = %lg".
TUNE_INFO = re.compile(r"^tune_info\s*=\s*(?P<body>.+)$", re.M)
XOVER_LINE = re.compile(r"XOVER\s*=\s*([0-9.]+)\s*,\s*TUNE_FREQ\s*=\s*([0-9.]+)")


def parse_tune_info(text: str) -> dict[str, Any]:
    """Read YAFU's tuning result.

    Args:
        text: Contents of the ``yafu.ini`` YAFU wrote, or its stdout.

    Returns:
        ``{"raw", "cpu", "platform", "coefficients", "crossover_digits",
        "tune_frequency"}``. Missing values are ``None`` rather than guessed.

    Raises:
        ValueError: If no ``tune_info`` line is present.
    """

    match = TUNE_INFO.search(text)
    if not match:
        raise ValueError("No tune_info line was produced; the tuning run did not finish")
    body = match.group("body").strip()
    parts = [item.strip() for item in body.split(",")]
    coefficients: list[float] = []
    for item in parts[2:]:
        try:
            coefficients.append(float(item))
        except ValueError:
            continue
    crossover = None
    frequency = None
    reported = XOVER_LINE.search(text)
    if reported:
        crossover = float(reported.group(1))
        frequency = float(reported.group(2))
    return {
        "raw": body,
        "cpu": parts[0] if parts else None,
        "platform": parts[1] if len(parts) > 1 else None,
        "coefficients": coefficients,
        "crossover_digits": crossover,
        "tune_frequency": frequency,
    }


def tune_recommendation(parsed: dict[str, Any], current_threshold: int) -> dict[str, Any]:
    """Turn a tuning result into a suggestion, never a configuration change.

    Numerisect does not rewrite its own configuration. The caller is told what YAFU
    measured and which environment variable to set if they agree.

    Args:
        parsed: Output of :func:`parse_tune_info`.
        current_threshold: The active ``NUMERISECT_CADO_THRESHOLD``.

    Returns:
        The suggestion, including whether it differs from the current setting.
    """

    crossover = parsed.get("crossover_digits")
    suggested = int(round(crossover)) if crossover else None
    differs = suggested is not None and suggested != current_threshold
    return {
        "measured_crossover_digits": crossover,
        "suggested_threshold": suggested,
        "current_threshold": current_threshold,
        "differs": differs,
        "cpu": parsed.get("cpu"),
        "tune_frequency": parsed.get("tune_frequency"),
        "tune_info": parsed.get("raw"),
        "apply_with": (
            f"NUMERISECT_CADO_THRESHOLD={suggested}" if suggested else None
        ),
        "note": (
            "YAFU measured this crossover on this machine with this thread count and "
            "these engine builds. It is a suggestion: Numerisect never rewrites its own "
            "configuration. Set the environment variable yourself if you agree."
        ),
    }
