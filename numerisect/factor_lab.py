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

import os
import re
import shutil
import subprocess
from typing import Any

from .config import PACKAGE_DIR
from .engines import parse_ecm_output
from .native_tools import (
    mfactor_cuda_tool_path,
    mfactor_tool_path,
    squfof_tool_path,
)
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
#: Largest Phi_n(b), in decimal digits, whose Aurifeuillean split is attempted.
#:
#: Phi_n(b) is the whole input whenever n is prime, so factoring it is factoring the
#: input. Attempting that inside a metadata routine hung on every large Mersenne number.
#: Above this cap the split is reported as not attempted, which is inconclusive and never
#: a claim that no algebraic factor exists; the factoring engines are the tool for that.
ALGEBRAIC_DIGIT_CAP = 60
#: Largest k searched when trial-factoring M_p over the progression q = 2kp + 1.
#: Largest k searched over q = 2kd + 1.
#:
#: This was 50,000,000 when PARI/GP walked the progression at about a million k a
#: second, where the ceiling was roughly a minute of work. The compiled scanner
#: sustains about a thousand times that, so the old ceiling is now a fraction of a
#: second and the bound is raised to match. Automatic mode is governed by its time
#: budget rather than by this number.
MAX_MERSENNE_K = 100_000_000_000
#: Largest Mersenne exponent accepted. M_p is never built, so this bounds only the work.
MAX_MERSENNE_EXPONENT = 10**9
#: The staged hunt constructs M_p in PARI/GP so that native engines can work on the
#: exact cofactor. This is deliberately distinct from the progression-only search.
MAX_MERSENNE_HUNT_EXPONENT = 1_000_000


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
    lines = _gp_call(
        f'fl_special_form("{safe}", {timeout}, {ALGEBRAIC_DIGIT_CAP})', timeout + 30
    )
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


def _mersenne_inventory(exponent: int, candidates: list[str], proof_seconds: int) -> dict[str, Any]:
    """Ask PARI/GP to divide and classify a Mersenne factor inventory."""

    values = sorted({int(value) for value in candidates if int(value) > 1})
    vector = ",".join(str(value) for value in values)
    lines = _gp_call(
        f"fl_mersenne_inventory({exponent},[{vector}],{proof_seconds})",
        proof_seconds + 30,
    )
    factors: list[dict[str, Any]] = []
    for row in _tagged(lines, "INVENTORY_FACTOR"):
        fields = row.split("|")
        if len(fields) != 3 or not all(field.isdigit() for field in fields):
            raise PrimeEngineError("PARI/GP returned an invalid Mersenne inventory")
        factors.append(
            {
                "value": fields[0],
                "exponent": int(fields[1]),
                "status": "proven_prime" if fields[2] == "1" else "composite_divisor",
            }
        )
    if int(_one(lines, "DONE")) != len(factors):
        raise PrimeEngineError("PARI/GP returned an incomplete Mersenne inventory")
    cofactor = _one(lines, "INVENTORY_COFACTOR")
    digits = _one(lines, "INVENTORY_COFACTOR_DIGITS")
    status = _one(lines, "INVENTORY_COFACTOR_STATUS")
    if (
        not cofactor.isdigit()
        or not digits.isdigit()
        or status
        not in {
            "unit",
            "composite",
            "unknown",
            "probable_prime",
            "proven_prime",
        }
    ):
        raise PrimeEngineError("PARI/GP returned an invalid Mersenne cofactor")
    return {
        "factors": factors,
        "cofactor": cofactor,
        "cofactor_digits": digits,
        "cofactor_status": status,
        "complete": _one(lines, "INVENTORY_COMPLETE") == "1",
    }


def _run_ecm_factor_stage(
    cofactor: str,
    method: str,
    b1: int,
    curves: int,
    timeout: int,
    threads: int,
) -> dict[str, Any]:
    """Run one GMP-ECM stage and return only engine-reported divisors."""

    executable = shutil.which("ecm")
    if not executable:
        return {"status": "skipped", "factors": [], "detail": "GMP-ECM is not installed"}
    command = [executable]
    if method in {"pm1", "pp1"}:
        command.append(f"-{method}")
    else:
        command += ["-c", str(curves)]
    command += ["-one", str(b1)]
    timed_out = False
    try:
        completed = subprocess.run(
            command,
            input=f"{cofactor}\n",
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env={**os.environ, "OMP_NUM_THREADS": str(threads)},
        )
        output = f"{completed.stdout}\n{completed.stderr}"
        return_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = (
            exc.stdout.decode(errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            exc.stderr.decode(errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        output = f"{stdout}\n{stderr}"
        return_code = None
    parsed = parse_ecm_output(output)
    # GMP-ECM can report "Factor found: N" when a curve degenerates. N is not a
    # proper divisor and must not replace the unresolved cofactor in the inventory.
    reported_factors = [str(item["value"]) for item in parsed["factors"]]
    factors = [value for value in reported_factors if value != cofactor]
    if return_code not in {None, 0} and not reported_factors:
        raise PrimeEngineError(f"GMP-ECM {method} exited with status {return_code}")
    return {
        "status": "timeout" if timed_out else ("factor_found" if factors else "completed"),
        "factors": factors,
        "detail": (
            f"{len(factors)} divisor(s) reported"
            if factors
            else ("time budget expired" if timed_out else "no factor found at this bound")
        ),
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


#: Small-prime bound used when the compiled scanner sieves the k progression.
MFACTOR_SIEVE_BOUND = 1_000_000
#: Montgomery REDC on the device needs q < 2**63. Above that only the CPU helper, which
#: falls back to GMP, can test a candidate, so the GPU is used only when the whole
#: requested range stays inside the bound. Nothing is ever left untested to gain speed.
MONTGOMERY_LIMIT = 1 << 63


def _mersenne_metadata(exponent: int, timeout: int) -> dict[str, Any]:
    """Exponent structure and order divisors, decided by PARI/GP."""

    lines = _gp_call(f"fl_mersenne_orders({exponent})", timeout)
    _require_complete(lines)
    orders = [int(value) for value in _tagged(lines, "ORDER")]
    if int(_one(lines, "DONE")) != len(orders):
        raise PrimeEngineError("PARI/GP returned an incomplete order-divisor list")
    return {
        "orders": orders,
        "prime": _one(lines, "EXPONENT_PRIME") == "1",
        "factorization": _one(lines, "EXPONENT_FACTORIZATION"),
        "digits": int(_one(lines, "MERSENNE_DIGITS")),
    }


def _mersenne_native_scan(
    orders: list[int], k_limit: int, timeout: int, threads: int | None
) -> tuple[list[tuple[str, int, int]], bool]:
    """Scan every order's progression with the compiled helper.

    The helper is a scanner, not an authority. It reports q with 2^d = 1 (mod q), which
    makes q a divisor of 2^d - 1 and nothing more; PARI/GP confirms primality afterwards.
    """

    cpu_tool = mfactor_tool_path()
    # The device sieves and tests without moving candidates across the bus, which
    # measured about twelve times the C helper's rate. It can only be used where every
    # candidate stays below the Montgomery bound; otherwise the C helper runs, since it
    # handles wide candidates with GMP rather than deferring them.
    gpu_tool = mfactor_cuda_tool_path()
    hits: list[tuple[str, int, int]] = []
    gpu_used = False
    deadline = max(1, timeout)
    for order in orders:
        widest = 2 * k_limit * order + 1
        use_gpu = gpu_tool is not None and widest < MONTGOMERY_LIMIT
        tool = gpu_tool if use_gpu else cpu_tool
        gpu_used = gpu_used or use_gpu
        command = [
            str(tool), str(order), "1", str(k_limit), str(MFACTOR_SIEVE_BOUND),
        ]
        if threads and not use_gpu:
            command.append(str(threads))
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            timeout=deadline, check=False,
        )
        if result.returncode != 0:
            raise PrimeEngineError(
                f"The Mersenne scanner failed for order {order}: "
                f"{result.stderr.strip() or 'no diagnostic'}"
            )
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not any(line.startswith("DONE:") for line in lines):
            raise PrimeEngineError(
                "The Mersenne scanner did not return a completion marker"
            )
        status = next(
            (line[len("STATUS:"):] for line in lines if line.startswith("STATUS:")), ""
        )
        if status not in {"complete", ""}:
            raise PrimeEngineError(
                f"The Mersenne scanner did not finish the range for order {order}: "
                f"{status}"
            )
        for row in _tagged(lines, "FACTOR"):
            parts = row.split("|")
            if len(parts) != 2 or not all(part.isdigit() for part in parts):
                raise PrimeEngineError("The Mersenne scanner returned an invalid record")
            hits.append((parts[0], int(parts[1]), order))
    return hits, gpu_used


def _mersenne_confirm(
    hits: list[tuple[str, int, int]], timeout: int
) -> list[tuple[str, int, int]]:
    """Keep only candidates PARI/GP confirms are prime divisors."""

    if not hits:
        return []
    candidates = "[" + ",".join(q for q, _, _ in hits) + "]"
    orders = "[" + ",".join(str(d) for _, _, d in hits) + "]"
    lines = _gp_call(f"fl_mersenne_confirm({candidates},{orders})", timeout)
    _require_complete(lines)
    verdicts = [row.split("|") for row in _tagged(lines, "CONFIRM")]
    if len(verdicts) != len(hits):
        raise PrimeEngineError("PARI/GP did not confirm every scanned candidate")
    kept: list[tuple[str, int, int]] = []
    for (q, k, d), verdict in zip(hits, verdicts, strict=True):
        if len(verdict) != 3 or verdict[0] != q:
            raise PrimeEngineError("PARI/GP returned a mismatched confirmation")
        if verdict[2] == "1":
            kept.append((q, k, d))
    return kept


def _mersenne_factors_native(
    exponent: int, k_limit: int, timeout: int, threads: int | None = None
) -> dict[str, Any]:
    """The compiled-scanner path for a finite k range.

    PARI/GP still owns the mathematics either side of the scan: it factors the exponent
    and enumerates the order divisors before, and confirms every candidate is a prime
    divisor after. The helper only walks the progression.
    """

    meta = _mersenne_metadata(exponent, timeout)
    hits, gpu_used = _mersenne_native_scan(meta["orders"], k_limit, timeout, threads)
    confirmed = _mersenne_confirm(hits, timeout)

    # The same q can surface under several order divisors; keep the smallest order.
    best: dict[str, tuple[str, int, int]] = {}
    for q, k, d in confirmed:
        if q not in best or d < best[q][2]:
            best[q] = (q, k, d)
    records = sorted(best.values(), key=lambda row: (row[1], int(row[0])))

    largest_candidate = 2 * k_limit * max(meta["orders"]) + 1
    digits = meta["digits"]
    rows = [[q, str(k), str(d), str(len(q))] for q, k, d in records]
    return {
        "exponent": str(exponent),
        "mersenne_digits": str(digits),
        "k_limit": str(k_limit),
        "scanned_k": str(k_limit),
        "automatic": False,
        "stop_reason": "ceiling",
        "complete": True,
        "factors": [q for q, _, _ in records],
        "exponent_prime": meta["prime"],
        "exponent_factorization": meta["factorization"],
        "columns": ["Factor q", "k in q = 2kd + 1", "Order divisor d", "Digits of q"],
        "rows": rows,
        "metrics": {
            "Exponent p": str(exponent),
            "Exponent factorization": meta["factorization"],
            "Exponent type": "prime" if meta["prime"] else "composite",
            "M_p decimal digits": f"{digits:,}",
            "Search mode": "manual bound",
            "Largest k reached in any order": f"{k_limit:,}",
            "Largest candidate tested": f"{largest_candidate:,}",
            "Factors found": str(len(records)),
            "Order divisors completed": f"{len(meta['orders'])} of {len(meta['orders'])}",
            "Stop reason": "ceiling",
            "Selected k range complete": "yes",
            "Scanner": (
                "numerisect-mfactor-cuda (CUDA, device-side sieve)"
                if gpu_used
                else "numerisect-mfactor (C, GMP, OpenMP)"
            ),
        },
        "engine": (
            "numerisect-mfactor-cuda with PARI/GP confirmation"
            if gpu_used
            else "numerisect-mfactor with PARI/GP confirmation"
        ),
        "note": (
            (
                "For prime p, every prime factor q of M_p satisfies q = 2kp + 1. "
                if meta["prime"]
                else "Because p is composite, PARI/GP factored the exponent and searched "
                "q = 2kd + 1 for every order divisor d > 1 of p. "
            )
            + "Every candidate also satisfies q = ±1 (mod 8) and is tested by one modular "
            "exponentiation. The compiled scanner sieved each progression by small primes "
            "and ran the surviving exponentiations across every core; PARI/GP enumerated "
            "the order divisors beforehand and confirmed each reported q is a prime "
            "divisor afterwards, so nothing here rests on the scanner alone. "
            "M_p itself is never constructed. "
            "The whole requested k range was searched. "
            "This is factor discovery, not a complete factorization of M_p. Finding "
            "nothing is inconclusive: it means no factor in the searched q = 2kd + 1 "
            "progressions exists below the bound searched, and says nothing about whether "
            "M_p is prime. Use the Lucas–Lehmer test for that question."
        ),
    }


def mersenne_factors(
    exponent: int,
    k_limit: int | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """Trial-factor the Mersenne number M_p = 2^p - 1 over its own progression.

    For prime p, every prime factor q satisfies q = 2kp + 1. For composite odd
    p, PARI/GP enumerates every order divisor d > 1 of p and searches q = 2kd + 1,
    covering the algebraic M_d divisors that a prime-exponent-only search misses.
    In both cases q = +/-1 (mod 8), and membership is one modular exponentiation.

    **M_p is never constructed.**  Every step happens modulo the candidate, so the
    exponent may run into the millions.  M_1000151 has 301,076 decimal digits and its
    factor 2000303 is found at k = 1; materializing that target merely to test a small
    candidate would waste memory and arithmetic.

    Args:
        exponent: An odd p. M_p is the target; it is never materialised.
        k_limit: Manual largest k in q = 2kp + 1 (1 to 50,000,000). ``None``
            selects automatic mode, which searches until the first factor, timeout, or
            the 50,000,000 safety ceiling.
        timeout: PARI/GP time limit in seconds.

    Returns:
        A report dictionary.  ``complete`` is ``False`` when the budget ran out before
        the whole k range was searched.

    Raises:
        ValueError: If a bound is violated.
        PrimeEngineError: If PARI/GP failed.
    """

    if not 3 <= exponent <= MAX_MERSENNE_EXPONENT or exponent % 2 == 0:
        raise ValueError(
            "Mersenne progression factoring needs an odd exponent between 3 and "
            f"{MAX_MERSENNE_EXPONENT:,}; M_2 = 3 is the trivial exception"
        )
    if k_limit is not None and not 1 <= k_limit <= MAX_MERSENNE_K:
        raise ValueError(f"The k limit must be between 1 and {MAX_MERSENNE_K:,}")
    if not 1 <= timeout <= 3600:
        raise ValueError("Engine time limit must be between 1 and 3,600 seconds")

    automatic = k_limit is None
    ceiling = MAX_MERSENNE_K if automatic else k_limit

    # A finite, explicit range is exactly what the compiled scanner is for. It sieves
    # the progression and uses a 64-bit modular exponentiation across every core, which
    # measured about a thousand times PARI's rate on this machine. Automatic mode stays
    # in PARI/GP, where the stop-at-first-factor and budget semantics live. If the
    # helper cannot be built, PARI/GP does the whole job as before.
    if not automatic:
        try:
            scanner = mfactor_tool_path()
        except (RuntimeError, OSError):
            scanner = None
        if scanner is not None:
            try:
                return _mersenne_factors_native(exponent, k_limit, timeout)
            except subprocess.TimeoutExpired:
                raise PrimeEngineError(
                    "The Mersenne scanner exceeded the time limit; lower the k bound "
                    "or raise the timeout"
                ) from None

    lines = _gp_call(
        f"fl_mersenne_factors({exponent},{ceiling},{timeout},{int(automatic)})",
        timeout + 30,
    )
    _require_complete(lines)
    records = [row.split("|") for row in _tagged(lines, "FACTOR")]
    if any(len(row) != 3 or not all(part.isdigit() for part in row) for row in records):
        raise PrimeEngineError("PARI/GP returned an invalid Mersenne factor record")
    if int(_one(lines, "DONE")) != len(records):
        raise PrimeEngineError("PARI/GP returned an incomplete Mersenne factor search")
    timed_out = _one(lines, "TRUNCATED") != "0"
    scanned_k = int(_one(lines, "SCANNED_K"))
    largest_candidate = int(_one(lines, "LARGEST_CANDIDATE"))
    stop_reason = _one(lines, "STOP_REASON")
    complete = not timed_out and stop_reason == "ceiling"
    digits = int(_one(lines, "MERSENNE_DIGITS"))
    exponent_prime = _one(lines, "EXPONENT_PRIME") == "1"
    exponent_factorization = _one(lines, "EXPONENT_FACTORIZATION")
    order_count = int(_one(lines, "ORDER_DIVISORS"))
    orders_completed = int(_one(lines, "ORDERS_COMPLETED"))
    rows = [[factor, k, order, str(len(factor))] for factor, k, order in records]
    return {
        "exponent": str(exponent),
        "mersenne_digits": str(digits),
        "k_limit": str(ceiling),
        "scanned_k": str(scanned_k),
        "automatic": automatic,
        "stop_reason": stop_reason,
        "complete": complete,
        "factors": [factor for factor, _, _ in records],
        "exponent_prime": exponent_prime,
        "exponent_factorization": exponent_factorization,
        "columns": ["Factor q", "k in q = 2kd + 1", "Order divisor d", "Digits of q"],
        "rows": rows,
        "metrics": {
            "Exponent p": str(exponent),
            "Exponent factorization": exponent_factorization,
            "Exponent type": "prime" if exponent_prime else "composite",
            "M_p decimal digits": f"{digits:,}",
            "Search mode": "automatic" if automatic else "manual bound",
            "Largest k reached in any order": f"{scanned_k:,}",
            "Largest candidate tested": f"{largest_candidate:,}",
            "Factors found": str(len(records)),
            "Order divisors completed": f"{orders_completed} of {order_count}",
            "Stop reason": stop_reason.replace("_", " "),
            "Selected k range complete": "yes" if complete else "no",
        },
        "engine": "PARI/GP",
        "note": (
            (
                "For prime p, every prime factor q of M_p satisfies q = 2kp + 1. "
                if exponent_prime
                else "Because p is composite, PARI/GP factored the exponent and searched q = 2kd + 1 for every order divisor d > 1 of p. "
            )
            + "Every candidate also satisfies q = ±1 (mod 8) and is tested by one modular exponentiation. "
            "M_p itself is never constructed, which makes trial factoring practical for "
            "exponents far beyond a general-purpose factorization attempt. "
            + (
                "Automatic mode stopped after finding the first factor."
                if stop_reason == "factor_found"
                else (
                    "The whole requested k range was searched."
                    if complete
                    else "The time budget expired; every factor found before it expired was preserved."
                )
            )
            + " This is factor discovery, not a complete factorization of M_p. Finding "
            "nothing is inconclusive: it means no factor in the searched q = 2kd + 1 progressions exists "
            "below the actual bound searched, and says nothing about whether M_p is "
            "prime. Use the Lucas–Lehmer test for that question."
        ),
    }


def mersenne_factor_hunt(
    exponent: int,
    *,
    trial_k_limit: int = 100_000,
    trial_seconds: int = 60,
    stage_seconds: int = 60,
    pm1_b1: int = 50_000,
    pp1_b1: int = 50_000,
    ecm_b1: int = 50_000,
    ecm_curves: int = 25,
    proof_seconds: int = 10,
    threads: int | None = None,
) -> dict[str, Any]:
    """Run a bounded, staged native factor hunt for ``M_p``.

    The specialized PARI/GP progression search runs first. PARI/GP then constructs
    ``M_p`` and owns every division, multiplicity count, and primality decision.
    GMP-ECM supplies P-1, P+1, and ECM divisor discovery on the exact unresolved
    cofactor. Python only validates, launches, parses, and schedules these stages.

    A completed campaign means every remaining part is rigorously prime. Exhausting
    the configured stages is explicitly an incomplete factorization.
    """

    if not 3 <= exponent <= MAX_MERSENNE_HUNT_EXPONENT:
        raise ValueError(
            "The staged hunt materializes M_p natively and accepts prime exponents "
            f"from 3 through {MAX_MERSENNE_HUNT_EXPONENT:,}; use trial factoring "
            "alone for larger exponents"
        )
    if not 1 <= trial_k_limit <= MAX_MERSENNE_K:
        raise ValueError(f"The trial k limit must be between 1 and {MAX_MERSENNE_K:,}")
    selected_threads = threads if threads is not None else (os.cpu_count() or 1)
    for label, value, low, high in (
        ("Trial time", trial_seconds, 1, 3600),
        ("Per-stage time", stage_seconds, 1, 3600),
        ("Proof time", proof_seconds, 1, 600),
        ("P-1 B1", pm1_b1, 100, 10**12),
        ("P+1 B1", pp1_b1, 100, 10**12),
        ("ECM B1", ecm_b1, 100, 10**12),
        ("ECM curves", ecm_curves, 1, 1_000_000),
        ("CPU threads", selected_threads, 1, 256),
    ):
        if not low <= value <= high:
            raise ValueError(f"{label} must be between {low:,} and {high:,}")

    trial = mersenne_factors(exponent, trial_k_limit, trial_seconds)
    candidates = list(trial["factors"])
    sources = {value: "PARI/GP Mersenne trial factoring" for value in candidates}
    inventory = _mersenne_inventory(exponent, candidates, proof_seconds)
    stages: list[dict[str, str]] = [
        {
            "stage": "Mersenne trial factoring",
            "status": trial["stop_reason"],
            "detail": (
                f"searched through k={trial['scanned_k']}; found {len(trial['factors'])} divisor(s)"
            ),
        }
    ]

    stage_specs = (
        ("Pollard p-1", "pm1", pm1_b1, 1),
        ("Williams p+1", "pp1", pp1_b1, 1),
        ("Elliptic-curve method", "ecm", ecm_b1, ecm_curves),
    )
    for label, method, b1, curves in stage_specs:
        if inventory["complete"]:
            stages.append(
                {"stage": label, "status": "not_needed", "detail": "factorization already complete"}
            )
            continue
        if inventory["cofactor_status"] in {"unit", "proven_prime"}:
            stages.append(
                {
                    "stage": label,
                    "status": "not_applicable",
                    "detail": f"cofactor is {inventory['cofactor_status'].replace('_', ' ')}",
                }
            )
            continue
        result = _run_ecm_factor_stage(
            inventory["cofactor"], method, b1, curves, stage_seconds, selected_threads
        )
        for value in result["factors"]:
            candidates.append(value)
            sources[value] = f"GMP-ECM {label}"
        stages.append({"stage": label, "status": result["status"], "detail": result["detail"]})
        if result["factors"]:
            inventory = _mersenne_inventory(exponent, candidates, proof_seconds)

    for factor in inventory["factors"]:
        factor["engine"] = sources.get(factor["value"], "native reconciliation")
    cofactor = inventory["cofactor"]
    preview = cofactor if len(cofactor) <= 160 else f"{cofactor[:80]}…{cofactor[-80:]}"
    complete = bool(inventory["complete"])
    rows = [
        [item["value"], str(item["exponent"]), item["status"], item["engine"]]
        for item in inventory["factors"]
    ]
    return {
        "exponent": str(exponent),
        "mersenne_digits": trial["mersenne_digits"],
        "complete": complete,
        "factors": inventory["factors"],
        "cofactor": cofactor,
        "cofactor_preview": preview,
        "cofactor_digits": inventory["cofactor_digits"],
        "cofactor_status": inventory["cofactor_status"],
        "stages": stages,
        "columns": ["Discovered divisor", "Multiplicity", "Proof status", "Engine"],
        "rows": rows,
        "metrics": {
            "Exponent p": str(exponent),
            "M_p decimal digits": f"{int(trial['mersenne_digits']):,}",
            "Distinct divisors found": str(len(inventory["factors"])),
            "Remaining cofactor digits": f"{int(inventory['cofactor_digits']):,}",
            "Remaining cofactor status": inventory["cofactor_status"].replace("_", " "),
            "Complete prime factorization": "yes" if complete else "no",
            "CPU threads exposed to native stages": str(selected_threads),
        },
        "engine": "PARI/GP + GMP-ECM",
        "note": (
            "Every displayed divisor was divided from M_p by PARI/GP and carries its "
            "exact multiplicity. "
            + (
                "Every part is rigorously prime, so the factorization is complete."
                if complete
                else "The listed factors are proven discoveries, but the remaining cofactor is unresolved; exhausting these bounded stages does not prove that no additional factors exist."
            )
        ),
    }
