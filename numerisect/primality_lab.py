"""Typed orchestration boundary for the PARI/GP primality laboratory.

Every primality decision, witness search, certificate, and special-form search
exposed here is computed by ``numerisect/primality_lab.gp`` inside PARI/GP.
Python validates the request, launches ``gp`` under a bounded wall-clock
timeout, requires the mandatory ``DONE:`` completion marker, parses the tagged
protocol, and assembles report rows. It never reimplements the mathematics.

Result semantics follow the repository-wide three-way contract:

* ``1`` — proven (a rigorous PARI/GP proof or a necessary-and-sufficient
  criterion established the verdict);
* ``0`` — proven composite (a witness, a factor, or a failed necessary
  condition established the verdict);
* ``-1`` — inconclusive (a time budget expired, a search bound was reached, or
  the applied criterion simply yields no verdict for this input).

An inconclusive result is never reported as a negative one.

Library routines behind each feature
------------------------------------
All computation happens inside PARI/GP 2.18 (``numerisect/primality_lab.gp``) or
``primesieve``. Wherever PARI publishes a routine it is called directly; GP code
is written only where a feature must expose an algorithm's individual steps,
which no library routine reports.

===================================  ==========================================
Feature                              Library routine performing the computation
===================================  ==========================================
Comparison laboratory (item 21)      ``ispseudoprime`` (Baillie-PSW),
                                     ``isprime(n, 2)`` (APR-CL),
                                     ``isprime(n, 3)`` (ECPP), ``kronecker``,
                                     ``Mod``/``Mod(...)^k`` modular powering;
                                     the individual Fermat, Solovay-Strassen,
                                     Miller-Rabin, Lucas and Frobenius steps are
                                     driven in GP because PARI reports only a
                                     combined verdict.
Deterministic witnesses (item 22)    ``primes``, ``valuation``, ``Mod`` powering;
                                     cross-checked with ``isprime``.
Pocklington proof (item 23)          ``factor``, ``isprime``, ``gcd``, ``Mod``;
                                     cross-checked with ``primecert(n, 1)`` and
                                     ``primecertisvalid``.
Pratt certificate (item 24)          ``factor``, ``znprimroot``,
                                     ``ispseudoprime``, ``Mod`` powering.
Proth / generalized Proth (27, 33)   ``kronecker``, ``factor``, ``Mod``;
                                     cross-checked with ``isprime``.
Lucas / N+1 (item 28)                PARI matrix powering over ``Mod`` for the
                                     Lucas sequences (PARI 2.18 publishes no
                                     ``lucasU``/``lucasV``), ``kronecker``,
                                     ``factor``, ``isprime``.
Probable-prime taxonomy (item 29)    ``ispseudoprime``, ``kronecker``, ``Mod``
                                     powering, ``isprime`` for the reference.
Carmichael analyzer (item 30)        ``factor``, ``znstar`` (Carmichael lambda as
                                     the largest invariant factor of
                                     ``(Z/nZ)^*``), ``eulerphi``, ``gcd``.
Chernick construction (item 30)      ``isprime``.
Generalized repunits (item 36)       ``ispseudoprime``, ``isprime``.
Sierpinski / Riesel (item 37)        ``ispseudoprime``, ``isprime``, ``factor``,
                                     ``znorder`` semantics via ``Mod`` powering.
Bi-twin chains, ladders (item 40)    ``isprime``, ``digits``.
Constrained primes (42, 43)          ``nextprime``, ``ispseudoprime``,
                                     ``isprime``, ``primecert``,
                                     ``primecertisvalid``, ``primecertexport``.
Lucas-Lehmer viewer (item 130)       GP iteration (PARI publishes no
                                     Lucas-Lehmer routine); the point of the page
                                     is the residue trace itself.
ECPP viewer (item 130)               ``primecert``, ``primecertisvalid``,
                                     ``coredisc``.
Prime k-tuplets (item 14)            ``primesieve --print=<k>`` below 2^64,
                                     PARI ``forprime``/``isprime`` otherwise.
===================================  ==========================================
"""

from __future__ import annotations

import re
import secrets
from pathlib import Path

from .prime_manipulation import decimal_integer
from .primes import PrimeEngineError, _run_gp, _tagged_values

PROGRAM = Path(__file__).with_name("primality_lab.gp")

MAX_TIMEOUT_SECONDS = 3600
MAX_BUDGET_SECONDS = 3600
MAX_DISPLAY_DIGITS = 400

#: Text fields carried inside pipe-separated records may hold any printable
#: character except the separator itself and control characters.
_SAFE_FIELD = re.compile(r"[^|\x00-\x1f]{0,200000}")
#: Certificates are re-injected into GP, so only vector syntax is accepted.
_CERTIFICATE_TEXT = re.compile(r"\[[0-9,\[\]\s-]{1,200000}\]")

VERDICTS: dict[int, str] = {
    1: "proven prime",
    0: "proven composite",
    -1: "inconclusive",
}

_CERTIFICATE_KINDS: dict[str, str] = {
    "pocklington": "pl_verify_pocklington",
    "pratt": "pl_verify_pratt",
}

_CONSTRAINED_KINDS: dict[str, int] = {"any": 0, "safe": 1, "strong": 2}


# ---------------------------------------------------------------------------
# Engine boundary
# ---------------------------------------------------------------------------
def _program() -> str:
    """Return the PARI/GP primality-laboratory source.

    Returns:
        The complete text of ``primality_lab.gp``.

    Raises:
        PrimeEngineError: If the packaged GP program cannot be read.
    """
    try:
        return PROGRAM.read_text(encoding="utf-8")
    except OSError as exc:
        raise PrimeEngineError("The PARI/GP primality laboratory is unavailable") from exc


def _check_timeout(timeout: int) -> None:
    """Validate the wall-clock limit applied to the ``gp`` subprocess."""
    if not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
        raise ValueError("Engine time limit must be between 1 and 3,600 seconds")


def _check_budget(budget: int) -> None:
    """Validate the in-engine proof budget passed to PARI ``alarm``."""
    if not 1 <= budget <= MAX_BUDGET_SECONDS:
        raise ValueError("The proof time budget must be between 1 and 3,600 seconds")


def _execute(call: str, timeout: int) -> list[str]:
    """Run one primality-laboratory entry point and return its tagged output.

    Args:
        call: The GP call, already assembled from validated integers.
        timeout: Wall-clock limit in seconds for the ``gp`` subprocess.

    Returns:
        The non-empty stripped output lines produced by PARI/GP.

    Raises:
        ValueError: If the timeout is outside the documented bounds.
        PrimeEngineError: If GP fails or omits its ``DONE:`` completion marker.
    """
    _check_timeout(timeout)
    lines = _run_gp(f"{_program()}\n{call};", timeout=timeout)
    if not _tagged_values(lines, "DONE"):
        raise PrimeEngineError("PARI/GP returned an incomplete primality-laboratory result")
    return lines


def _one(lines: list[str], tag: str) -> int:
    """Return the single integer carried by ``tag``."""
    values = _tagged_values(lines, tag)
    if len(values) != 1:
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} result")
    return values[0]


def _optional(lines: list[str], tag: str) -> int | None:
    """Return the integer carried by ``tag``, or ``None`` when it is absent."""
    values = _tagged_values(lines, tag)
    if len(values) > 1:
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} result")
    return values[0] if values else None


def _records(lines: list[str], tag: str, width: int) -> list[list[str]]:
    """Return every ``TAG:a|b|c`` record with the expected field count."""
    prefix = f"{tag}:"
    rows = [line[len(prefix):].split("|") for line in lines if line.startswith(prefix)]
    if any(
        len(row) != width or any(not _SAFE_FIELD.fullmatch(field) for field in row)
        for row in rows
    ):
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} record")
    return rows


def _text(lines: list[str], tag: str) -> str | None:
    """Return the single free-text payload of ``tag``, or ``None`` when absent."""
    prefix = f"{tag}:"
    values = [line[len(prefix):].strip() for line in lines if line.startswith(prefix)]
    if len(values) > 1 or any(not _SAFE_FIELD.fullmatch(value) for value in values):
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} value")
    return values[0] if values else None


def _block(lines: list[str], start_marker: str, end_marker: str, joiner: str = "\n") -> str:
    """Return the text between two literal marker lines, or an empty string."""
    if start_marker not in lines or end_marker not in lines:
        return ""
    start = lines.index(start_marker) + 1
    end = lines.index(end_marker)
    return joiner.join(lines[start:end]).strip()


def _display(value: int) -> str:
    """Render a possibly enormous integer compactly for metrics and reports."""
    text = str(value)
    if len(text) <= MAX_DISPLAY_DIGITS:
        return text
    return f"{text[:32]}…{text[-32:]} ({len(text)} digits)"


def _verdict(flag: int) -> str:
    """Map an engine verdict flag onto its documented label."""
    if flag not in VERDICTS:
        raise PrimeEngineError("PARI/GP returned an unknown primality verdict")
    return VERDICTS[flag]


def _flag(value: int) -> str:
    """Render a 0/1 engine flag as ``yes``/``no``."""
    return "yes" if value else "no"


def _three_way(flag: int) -> str:
    """Render a 1/0/-1 engine flag as ``yes``/``no``/``inconclusive``."""
    if flag not in {1, 0, -1}:
        raise PrimeEngineError("PARI/GP returned an unknown three-way flag")
    return {1: "yes", 0: "no", -1: "inconclusive"}[flag]


def _integer_vector(values: list[str], *, maximum: int, label: str,
                    minimum_value: int = 1) -> tuple[list[int], str]:
    """Validate a list of decimal integers and format it as a GP vector."""
    if not 1 <= len(values) <= maximum:
        raise ValueError(f"Supply 1–{maximum} {label}")
    numbers = [decimal_integer(text) for text in values]
    if any(number < minimum_value for number in numbers):
        raise ValueError(f"Every entry in {label} must be at least {minimum_value}")
    return numbers, "[" + ",".join(str(number) for number in numbers) + "]"


# ---------------------------------------------------------------------------
# Item 21: primality-test comparison laboratory
# ---------------------------------------------------------------------------
def compare_primality_tests(number: str, bases: list[str], budget_seconds: int = 30,
                    timeout: int = 300) -> dict:
    """Run Fermat, Solovay–Strassen, Miller–Rabin, Lucas, Frobenius, BPSW, APR-CL and ECPP.

    Args:
        number: Decimal integer ``n ≥ 2``.
        bases: 1–32 decimal test bases used by the compositeness tests.
        budget_seconds: PARI ``alarm`` budget applied to each rigorous proof.
        timeout: Wall-clock limit for the whole ``gp`` run.

    Returns:
        A report dictionary with one row per executed test.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP fails or returns an inconsistent verdict.
    """
    value = decimal_integer(number)
    if value < 2:
        raise ValueError("Primality comparison requires an integer at least 2")
    _check_budget(budget_seconds)
    _, vector = _integer_vector(bases, maximum=32, label="test bases")
    lines = _execute(f"pl_compare({value},{vector},{budget_seconds})", timeout)
    tests = _records(lines, "TEST", 5)
    if not tests:
        raise PrimeEngineError("PARI/GP returned no primality-test results")
    proven = _one(lines, "PROVEN")
    inconclusive = [row[0] for row in tests if row[1] == "inconclusive"]
    return {
        "verdict": _verdict(proven),
        "metrics": {
            "Integer": _display(value),
            "Decimal digits": str(_one(lines, "DIGITS")),
            "Tests executed": str(len(tests)),
            "Rigorous verdict": _verdict(proven),
            "Proof budget (seconds)": str(budget_seconds),
            "Inconclusive tests": ", ".join(inconclusive) or "none",
        },
        "columns": ["Test", "Outcome", "Evidence", "Milliseconds", "Strength"],
        "rows": tests,
        "note": (
            "PARI/GP executed every test independently. Rows marked 'probable' are "
            "compositeness tests: a pass is evidence, never a proof. Only the APR-CL and "
            "ECPP rows are proofs, and an exhausted time budget is reported as "
            "inconclusive rather than as a negative result."
        ),
    }


# ---------------------------------------------------------------------------
# Item 22: deterministic Miller–Rabin witness sets
# ---------------------------------------------------------------------------
def deterministic_witness_test(number: str, timeout: int = 300) -> dict:
    """Apply the published sufficient Miller–Rabin witness set for ``n``.

    The engine holds the classical bounds of Jaeschke (1993) and their
    extensions by Sorenson and Webster (2015); the largest covered range is
    ``n < 3,317,044,064,679,887,385,961,981`` with the first thirteen primes.

    Args:
        number: Decimal integer ``n ≥ 2``.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary listing every base in the sufficient set together
        with its squaring chain.

    Raises:
        ValueError: If ``n < 2``.
        PrimeEngineError: If PARI/GP fails or contradicts ``isprime``.
    """
    value = decimal_integer(number)
    if value < 2:
        raise ValueError("Deterministic Miller-Rabin requires an integer at least 2")
    lines = _execute(f"pl_deterministic_mr({value})", timeout)
    available = _one(lines, "SET_AVAILABLE") == 1
    proven = _one(lines, "PROVEN")
    crosscheck = _optional(lines, "CROSSCHECK")
    if crosscheck is not None and proven >= 0 and crosscheck != proven:
        raise PrimeEngineError("The deterministic witness set disagrees with PARI isprime")
    witnesses = _records(lines, "WITNESS", 3)
    bases = _tagged_values(lines, "BASE")
    if available and len(bases) != _one(lines, "SET_SIZE"):
        raise PrimeEngineError("PARI/GP returned an incomplete deterministic witness set")
    bound = _optional(lines, "BOUND")
    return {
        "verdict": _verdict(proven),
        "deterministic": available,
        "metrics": {
            "Integer": _display(value),
            "Sufficient set available": _flag(available),
            "Proven below": _display(bound) if bound is not None else "not applicable",
            "Witness bases": ", ".join(str(base) for base in bases) or "none",
            "Verdict": _verdict(proven),
        },
        "columns": ["Base", "Outcome", "Strong-test chain"],
        "rows": witnesses,
        "note": (
            "The listed bases form a published sufficient witness set for this range, so a "
            "unanimous pass is a proof of primality. Above the largest tabulated bound no "
            "sufficient set is known and the result is reported as inconclusive rather than "
            "as a probable prime."
            if available
            else
            "No published sufficient witness set covers this magnitude, so deterministic "
            "Miller-Rabin yields no verdict. Use the APR-CL or ECPP proofs instead."
        ),
    }


# ---------------------------------------------------------------------------
# Item 23: Pocklington N-1 proofs
# ---------------------------------------------------------------------------
def pocklington_proof(number: str, budget_seconds: int = 60, witness_limit: int = 200,
                      timeout: int = 300) -> dict:
    """Prove ``n`` prime with the Pocklington ``N−1`` criterion and emit a certificate.

    Args:
        number: Decimal integer ``n ≥ 3``.
        budget_seconds: PARI ``alarm`` budget for factoring ``n − 1``.
        witness_limit: Largest trial base searched for each prime factor of ``F``.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary carrying the factored part, the per-factor witnesses,
        and the machine-readable certificate when the proof succeeds.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP fails.
    """
    value = decimal_integer(number)
    if value < 3:
        raise ValueError("Pocklington proofs require an integer at least 3")
    _check_budget(budget_seconds)
    if not 2 <= witness_limit <= 100_000:
        raise ValueError("The witness search limit must be between 2 and 100,000")
    lines = _execute(
        f"pl_pocklington({value},{budget_seconds},{witness_limit})", timeout
    )
    proven = _one(lines, "PROVEN")
    status = _text(lines, "FACTOR_STATUS") or "not attempted"
    if status not in {"complete", "timeout", "not attempted"}:
        raise PrimeEngineError("PARI/GP returned an unknown factorization status")
    factored = _optional(lines, "FACTORED_PART")
    cofactor = _optional(lines, "COFACTOR")
    certificate = _text(lines, "CERT") or ""
    fermat_witness = _optional(lines, "FERMAT_WITNESS")
    factor_found = _optional(lines, "FACTOR_FOUND")
    reason = _text(lines, "REASON")
    metrics = {
        "Integer": _display(value),
        "Factorization of N−1": status,
        "Factored part F": _display(factored) if factored is not None else "none",
        "Unfactored cofactor R": _display(cofactor) if cofactor is not None else "none",
        "(F+1)² > N": _flag(_optional(lines, "BOUND_OK") or 0),
        "gcd(F, R) = 1": _flag(_optional(lines, "COPRIME") or 0),
        "PARI N−1 certificate valid": {1: "yes", 0: "no", -1: "inconclusive", None: "not requested"}[
            _optional(lines, "PARI_N_MINUS_1")
        ],
        "Verdict": _verdict(proven),
    }
    if fermat_witness is not None:
        metrics["Fermat compositeness witness"] = str(fermat_witness)
    if factor_found is not None:
        metrics["Factor discovered while proving"] = _display(factor_found)
    if reason:
        metrics["Reason"] = reason
    return {
        "verdict": _verdict(proven),
        "certificate": certificate,
        "metrics": metrics,
        "columns": ["Prime factor p of F", "Exponent", "Witness a", "p proven prime"],
        "rows": [
            [row[0], row[1], row[2] if row[2] != "0" else "none found", _three_way(int(row[3]))]
            for row in _records(lines, "WITNESS", 4)
        ],
        "note": (
            "Pocklington's criterion is a proof: with a fully factored F dividing N−1, "
            "gcd(F, (N−1)/F) = 1 and (F+1)² > N, a witness a for every prime p | F proves N "
            "prime. A factoring timeout or a missing witness leaves the result inconclusive, "
            "never composite."
            + (f" Machine-readable certificate: {certificate}" if certificate else "")
        ),
    }


# ---------------------------------------------------------------------------
# Items 23, 24: independent certificate verification
# ---------------------------------------------------------------------------
def verify_certificate(kind: str, certificate: str, timeout: int = 300) -> dict:
    """Re-check a Pocklington or Pratt certificate from first principles.

    Args:
        kind: ``"pocklington"`` or ``"pratt"``.
        certificate: The GP vector printed by the corresponding proof page.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary with one row per individual condition checked.

    Raises:
        ValueError: If the kind is unknown or the certificate is not a plain
            integer vector.
        PrimeEngineError: If PARI/GP fails or omits its completion marker.
    """
    if kind not in _CERTIFICATE_KINDS:
        raise ValueError("Select the Pocklington or the Pratt certificate format")
    text = " ".join(certificate.split())
    if not _CERTIFICATE_TEXT.fullmatch(text):
        raise ValueError(
            "A certificate must be a bracketed vector of integers, exactly as printed by "
            "the proof page"
        )
    lines = _execute(f"{_CERTIFICATE_KINDS[kind]}({text})", timeout)
    checks = _records(lines, "CHECK", 2)
    valid = _one(lines, "VALID") == 1
    if not checks:
        raise PrimeEngineError("PARI/GP returned no certificate conditions")
    return {
        "valid": valid,
        "metrics": {
            "Certificate format": kind,
            "Certified integer": _display(_one(lines, "N")),
            "Conditions checked": str(len(checks)),
            "Conditions failed": str(sum(1 for row in checks if row[1] != "1")),
            "Certificate valid": _flag(valid),
        },
        "columns": ["Condition", "Holds"],
        "rows": [[row[0], _flag(int(row[1] == "1"))] for row in checks],
        "note": (
            "PARI/GP re-derived every condition from the certificate alone; the original "
            "proof run was not consulted. A valid certificate is a complete proof of "
            "primality, and any failed condition invalidates the whole certificate."
        ),
    }


# ---------------------------------------------------------------------------
# Item 24: Pratt certificate trees
# ---------------------------------------------------------------------------
def pratt_certificate(number: str, max_nodes: int = 500, budget_seconds: int = 60,
                      timeout: int = 300) -> dict:
    """Build the recursive Pratt certificate tree for ``n``.

    Args:
        number: Decimal integer ``n ≥ 2``.
        max_nodes: Maximum number of distinct primes certified before the search
            is truncated.
        budget_seconds: PARI ``alarm`` budget for each ``n − 1`` factorization.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary with an indented node table, the edge list, and the
        machine-readable certificate when the tree is complete.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP fails or the node count is inconsistent.
    """
    value = decimal_integer(number)
    if value < 2:
        raise ValueError("Pratt certificates require an integer at least 2")
    _check_budget(budget_seconds)
    if not 1 <= max_nodes <= 100_000:
        raise ValueError("The certificate node limit must be between 1 and 100,000")
    lines = _execute(f"pl_pratt({value},{max_nodes},{budget_seconds})", timeout)
    nodes = _records(lines, "NODE", 6)
    edges = _records(lines, "EDGE", 4)
    total = _one(lines, "NODES")
    if len(nodes) != total or _tagged_values(lines, "DONE") != [total]:
        raise PrimeEngineError("PARI/GP returned an incomplete Pratt certificate tree")
    truncated = _one(lines, "TRUNCATED") == 1
    proven = _one(lines, "PROVEN")
    certificate = _text(lines, "CERT") or ""
    rows = [
        [node[0], node[1], ("· " * int(node[4])) + node[2], node[3],
         {"1": "verified", "0": "not verified", "-1": "inconclusive"}.get(node[5], node[5])]
        for node in nodes
    ]
    return {
        "verdict": _verdict(proven),
        "certificate": certificate,
        "nodes": nodes,
        "edges": edges,
        "truncated": truncated,
        "metrics": {
            "Integer": _display(value),
            "Certified primes in tree": str(total),
            "Tree edges": str(len(edges)),
            "Maximum depth": str(max((int(node[4]) for node in nodes), default=0)),
            "Node limit reached": _flag(truncated),
            "Verdict": _verdict(proven),
        },
        "columns": ["Node", "Parent", "Prime (indented by depth)", "Primitive root", "Status"],
        "rows": rows,
        "note": (
            "Each node records a primitive root g modulo p together with the complete "
            "factorization of p − 1, and every factor appears as its own node, so the tree "
            "is a self-contained proof. Reaching the node limit or a factoring timeout "
            "truncates the tree and is reported as inconclusive."
            + (f" Machine-readable certificate: {certificate}" if certificate else "")
        ),
    }


# ---------------------------------------------------------------------------
# Items 27 and 33: Proth and generalized Proth numbers
# ---------------------------------------------------------------------------
def proth_test(k: str, exponent: int, base: int = 2, witness_limit: int = 200,
               budget_seconds: int = 60, timeout: int = 300) -> dict:
    """Test ``N = k·b^n + 1`` with Proth's theorem or its generalized N−1 form.

    Args:
        k: Decimal multiplier ``k ≥ 1``.
        exponent: Exponent ``n ≥ 1``.
        base: Base ``b ≥ 2``; ``b = 2`` uses the classical Proth criterion.
        witness_limit: Largest trial witness searched.
        budget_seconds: PARI ``alarm`` budget for the independent ``isprime`` cross-check.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary describing the criterion, its witnesses, and the verdict.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP fails or contradicts ``isprime``.
    """
    multiplier = decimal_integer(k)
    if multiplier < 1:
        raise ValueError("The Proth multiplier k must be at least 1")
    if not 1 <= exponent <= 1_000_000:
        raise ValueError("The Proth exponent must be between 1 and 1,000,000")
    if not 2 <= base <= 1_000_000:
        raise ValueError("The Proth base must be between 2 and 1,000,000")
    if not 2 <= witness_limit <= 100_000:
        raise ValueError("The witness search limit must be between 2 and 100,000")
    _check_budget(budget_seconds)
    lines = _execute(
        f"pl_proth({multiplier},{exponent},{base},{witness_limit},{budget_seconds})", timeout
    )
    proven = _one(lines, "PROVEN")
    crosscheck = _one(lines, "CROSSCHECK")
    normalized = _records(lines, "NORMALIZED", 2)
    certificate = _text(lines, "CERT") or ""
    condition = _one(lines, "PROTH_CONDITION") == 1
    return {
        "verdict": _verdict(proven),
        "certificate": certificate,
        "metrics": {
            "Candidate": _display(_one(lines, "N")),
            "Form": f"{multiplier}·{base}^{exponent} + 1",
            "Normalized (k, n)": f"({normalized[0][0]}, {normalized[0][1]})" if normalized else "unchanged",
            "Proth condition k < b^n": _flag(condition),
            "Decimal digits": str(_one(lines, "DIGITS")),
            "Criterion verdict": _verdict(proven),
            "Independent isprime cross-check": _verdict(crosscheck),
        },
        "columns": ["Prime divisor of the base", "Witness"],
        "rows": _records(lines, "WITNESS", 2),
        "note": (
            "For b = 2 and odd k < 2^n Proth's theorem is necessary and sufficient: N is "
            "prime exactly when some a with Jacobi (a/N) = −1 satisfies a^((N−1)/2) ≡ −1. "
            "For other bases the generalized N−1 (Pocklington) criterion is used, which "
            "requires a witness for every prime divisor of b. When no witness is found "
            "within the search limit the criterion gives no verdict and the result is "
            "inconclusive."
            + (f" Machine-readable certificate: {certificate}" if certificate else "")
        ),
    }


def proth_search(k: str, base: int, n_start: int, n_end: int, limit: int = 100,
                 witness_limit: int = 200, budget_seconds: int = 60,
                 timeout: int = 600) -> dict:
    """Search ``N = k·b^n + 1`` over a bounded exponent range.

    Args:
        k: Decimal multiplier ``k ≥ 1``.
        base: Base ``b ≥ 2``.
        n_start: First exponent, at least 1.
        n_end: Last exponent, not below ``n_start``.
        limit: Maximum number of reported hits.
        witness_limit: Largest trial witness searched per candidate.
        budget_seconds: PARI ``alarm`` budget per candidate proof.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary with one row per prime or probable prime found.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP fails or the row count disagrees with ``DONE``.
    """
    multiplier = decimal_integer(k)
    if multiplier < 1:
        raise ValueError("The Proth multiplier k must be at least 1")
    if not 2 <= base <= 1_000_000:
        raise ValueError("The Proth base must be between 2 and 1,000,000")
    if not 1 <= n_start <= n_end <= 100_000:
        raise ValueError("Require 1 ≤ start exponent ≤ end exponent ≤ 100,000")
    if not 1 <= limit <= 10_000:
        raise ValueError("The result limit must be between 1 and 10,000")
    if not 2 <= witness_limit <= 100_000:
        raise ValueError("The witness search limit must be between 2 and 100,000")
    _check_budget(budget_seconds)
    lines = _execute(
        f"pl_proth_search({multiplier},{base},{n_start},{n_end},{limit},"
        f"{witness_limit},{budget_seconds})",
        timeout,
    )
    hits = _records(lines, "PROTH", 5)
    found = _tagged_values(lines, "DONE")
    if found != [len(hits)]:
        raise PrimeEngineError("PARI/GP returned an incomplete generalized Proth search")
    truncated = _one(lines, "TRUNCATED") == 1
    rows = [
        [row[0], row[1], _verdict(int(row[2])), row[3],
         row[4] if row[4] != "0" else "value withheld (over 20,000 digits)"]
        for row in hits
    ]
    return {
        "truncated": truncated,
        "metrics": {
            "Form": f"{multiplier}·{base}^n + 1",
            "Exponent range": f"{n_start}–{n_end}",
            "Hits reported": str(len(hits)),
            "Inconclusive candidates": str(_one(lines, "INCONCLUSIVE")),
            "Result limit reached": _flag(truncated),
        },
        "columns": ["Exponent n", "Decimal digits", "Verdict", "Criterion", "Value"],
        "rows": rows,
        "note": (
            "Every reported exponent first passes a BPSW probable-prime filter and is then "
            "settled by the Proth criterion or by PARI isprime. Candidates whose proof "
            "budget expired are counted as inconclusive and are listed with that verdict, "
            "never dropped silently."
        ),
    }


# ---------------------------------------------------------------------------
# Item 28: Lucas sequences, N−1/N+1 tests, Lucas–Lehmer–Riesel
# ---------------------------------------------------------------------------
def lucas_sequence_proof(number: str, p: int = 1, q: int = -1, selfridge: bool = True,
                         budget_seconds: int = 60, witness_limit: int = 40,
                         timeout: int = 300) -> dict:
    """Run Lucas, strong Lucas, Frobenius, Lucas–Lehmer–Riesel, and the Morrison N+1 proof.

    Args:
        number: Odd decimal integer ``n ≥ 3``.
        p: Lucas parameter ``P`` (ignored when ``selfridge`` is true).
        q: Lucas parameter ``Q`` (ignored when ``selfridge`` is true).
        selfridge: Select ``(P, Q)`` by Selfridge's method A.
        budget_seconds: PARI ``alarm`` budget for factoring ``n + 1``.
        witness_limit: Number of ``(P, Q)`` pairs tried per prime factor of ``F``.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary describing each Lucas criterion and the N+1 certificate.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP fails.
    """
    value = decimal_integer(number)
    if value < 3:
        raise ValueError("Lucas tests require an odd integer at least 3")
    if not -1_000_000 <= p <= 1_000_000 or not -1_000_000 <= q <= 1_000_000:
        raise ValueError("The Lucas parameters P and Q must lie between −1,000,000 and 1,000,000")
    if not 1 <= witness_limit <= 10_000:
        raise ValueError("The witness search limit must be between 1 and 10,000")
    _check_budget(budget_seconds)
    lines = _execute(
        f"pl_lucas_tests({value},{p},{q},{int(selfridge)},{budget_seconds},{witness_limit})",
        timeout,
    )
    proven = _one(lines, "PROVEN")
    params = _records(lines, "PARAMS", 4)
    square = _optional(lines, "SQUARE")
    llr = _records(lines, "LLR", 4)
    factor_found = _optional(lines, "FACTOR_FOUND")
    certificate = _text(lines, "CERT") or ""
    rows: list[list[str]] = []
    if square == 1:
        rows.append(["Selfridge parameter search", "fail", "n is a perfect square"])
    for label, tag, detail in (
        ("Lucas probable prime", "LUCAS_PRP", "U(n − (D/n)) ≡ 0 (mod n)"),
        ("Strong Lucas probable prime", "STRONG_LUCAS", "U(d) ≡ 0 or V(d·2^r) ≡ 0 (mod n)"),
        ("Lucas V check", "V_CHECK", "V(n − (D/n)) ≡ 2Q or 2 (mod n)"),
        ("Quadratic Frobenius", "FROBENIUS", "x^n ≡ Frobenius image mod (n, x² − Px + Q)"),
    ):
        flag = _optional(lines, tag)
        if flag is not None:
            rows.append([label, "pass" if flag == 1 else "fail", detail])
    if llr:
        rows.append([
            "Lucas–Lehmer–Riesel",
            "pass" if llr[0][3] == "1" else "fail",
            f"n + 1 = {llr[0][0]}·2^{llr[0][1]} with Lucas parameter P = {llr[0][2]}",
        ])
    nplus1 = _optional(lines, "NPLUS1")
    if nplus1 is not None:
        rows.append([
            "Morrison N+1 proof", _verdict(nplus1),
            f"factored part F = {_display(_optional(lines, 'NPLUS1_F') or 0)}",
        ])
    metrics = {
        "Integer": _display(value),
        "Parameters (P, Q, D, Jacobi)": " | ".join(params[0]) if params else "not selected",
        "Parameter selection": "Selfridge method A" if selfridge else "user supplied",
        "gcd(n, 2QD)": _display(_optional(lines, "GCD_2QD") or 0),
        "Strong Lucas index r": str(_optional(lines, "STRONG_INDEX")),
        "N+1 bound (F−1)² > N": _flag(_optional(lines, "NPLUS1_BOUND") or 0),
        "Verdict": _verdict(proven),
    }
    if factor_found is not None:
        metrics["Factor discovered"] = _display(factor_found)
    return {
        "verdict": _verdict(proven),
        "certificate": certificate,
        "metrics": metrics,
        "columns": ["Criterion", "Outcome", "Detail"],
        "rows": rows + [
            [f"N+1 witness for p = {row[0]}", "pass" if row[4] == "1" else "fail",
             f"exponent {row[1]}, P = {row[2]}, Q = {row[3]}"]
            for row in _records(lines, "NPLUS1_WITNESS", 5)
        ],
        "note": (
            "Lucas, strong Lucas and Frobenius passes are probable-prime evidence only. "
            "Lucas–Lehmer–Riesel and the Morrison N+1 criterion are proofs when they apply; "
            "when (D/n) ≠ −1 or n + 1 cannot be factored far enough the result stays "
            "inconclusive rather than becoming a negative answer."
            + (f" Machine-readable certificate: {certificate}" if certificate else "")
        ),
    }


# ---------------------------------------------------------------------------
# Item 29: probable-prime taxonomy
# ---------------------------------------------------------------------------
def pseudoprime_taxonomy(number: str, bases: list[str], p: int = 1, q: int = -1,
                         selfridge: bool = True, budget_seconds: int = 60,
                         timeout: int = 300) -> dict:
    """Classify ``n`` against every probable-prime family for the supplied bases.

    Args:
        number: Odd decimal integer ``n ≥ 3``.
        bases: 1–32 decimal Fermat/Euler/strong bases.
        p: Lucas parameter ``P`` (ignored when ``selfridge`` is true).
        q: Lucas parameter ``Q`` (ignored when ``selfridge`` is true).
        selfridge: Select ``(P, Q)`` by Selfridge's method A.
        budget_seconds: PARI ``alarm`` budget for the rigorous ``isprime`` reference.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary with one row per test and the derived pseudoprime labels.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP fails.
    """
    value = decimal_integer(number)
    if value < 3:
        raise ValueError("Pseudoprime taxonomy applies to odd integers at least 3")
    if not -1_000_000 <= p <= 1_000_000 or not -1_000_000 <= q <= 1_000_000:
        raise ValueError("The Lucas parameters P and Q must lie between −1,000,000 and 1,000,000")
    _check_budget(budget_seconds)
    _, vector = _integer_vector(bases, maximum=32, label="test bases")
    lines = _execute(
        f"pl_taxonomy({value},{vector},{p},{q},{int(selfridge)},{budget_seconds})", timeout
    )
    prime_status = _one(lines, "PRIME")
    records = _records(lines, "TAX", 4)
    if not records:
        raise PrimeEngineError("PARI/GP returned no taxonomy rows")
    labels = {
        "Fermat": "Fermat pseudoprime",
        "Euler": "Euler–Jacobi pseudoprime",
        "Strong": "strong pseudoprime",
        "Lucas": "Lucas pseudoprime",
        "Strong Lucas": "strong Lucas pseudoprime",
        "Frobenius": "Frobenius pseudoprime",
        "Baillie-PSW": "Baillie–PSW probable prime",
    }
    families = sorted({
        labels[row[0]] for row in records
        if row[2] == "1" and row[0] in labels and prime_status == 0
    })
    return {
        "prime_status": _verdict(prime_status),
        "metrics": {
            "Integer": _display(value),
            "Rigorous status": _verdict(prime_status),
            "Tests executed": str(len(records)),
            "Tests passed": str(sum(1 for row in records if row[2] == "1")),
            "Pseudoprime families": ", ".join(families) or (
                "none" if prime_status == 0 else "not applicable to a prime"
            ),
        },
        "columns": ["Test", "Parameters", "Passes", "Criterion"],
        "rows": [[row[0], row[1], _flag(int(row[2] == "1")), row[3]] for row in records],
        "note": (
            "Pseudoprime labels are per base: a composite that passes a test is a "
            "pseudoprime of that family to that base, and the summary lists every family in "
            "which at least one supplied base was fooled. A prime passes every test by "
            "definition and is not a pseudoprime. The rigorous status comes from PARI "
            "isprime and is reported as inconclusive when its budget expires."
        ),
    }


# ---------------------------------------------------------------------------
# Item 30: Carmichael numbers
# ---------------------------------------------------------------------------
def carmichael_analysis(number: str, base_limit: int = 10_000, budget_seconds: int = 60,
                        timeout: int = 300) -> dict:
    """Apply the Korselt criterion and count Fermat liars for ``n``.

    Args:
        number: Decimal integer ``n ≥ 3``.
        base_limit: Largest base included in the exhaustive Fermat scan.
        budget_seconds: PARI ``alarm`` budget for factoring ``n``.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary with the factorization, the Korselt conditions, the
        Carmichael function λ(n), and the Fermat-liar census.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP fails.
    """
    value = decimal_integer(number)
    if value < 3:
        raise ValueError("Carmichael analysis requires an integer at least 3")
    if not 2 <= base_limit <= 10_000_000:
        raise ValueError("The Fermat base limit must be between 2 and 10,000,000")
    _check_budget(budget_seconds)
    lines = _execute(f"pl_carmichael({value},{base_limit},{budget_seconds})", timeout)
    carmichael = _one(lines, "CARMICHAEL")
    verdict = _three_way(carmichael)
    status = _text(lines, "FACTOR_STATUS")
    if status == "timeout":
        return {
            "carmichael": verdict,
            "metrics": {
                "Integer": _display(value),
                "Factorization": "time budget exhausted",
                "Carmichael number": verdict,
            },
            "columns": ["Prime factor", "Exponent", "(n − 1) mod (p − 1)"],
            "rows": [],
            "note": (
                "Factoring n did not finish inside the time budget, so the Korselt criterion "
                "could not be evaluated. This is an inconclusive result, not a negative one."
            ),
        }
    factors = _records(lines, "FACTOR", 3)
    if len(factors) != _one(lines, "PRIME_FACTORS"):
        raise PrimeEngineError("PARI/GP returned an incomplete Carmichael factorization")
    liars = _one(lines, "FERMAT_LIARS")
    tested = _one(lines, "BASES_TESTED")
    passed = _one(lines, "BASES_PASSED")
    exhaustive = _one(lines, "EXHAUSTIVE") == 1
    if exhaustive and carmichael == 1 and passed != tested:
        raise PrimeEngineError("A Carmichael verdict disagrees with the exhaustive Fermat scan")
    return {
        "carmichael": verdict,
        "metrics": {
            "Integer": _display(value),
            "Composite": _flag(_one(lines, "COMPOSITE")),
            "Squarefree": _flag(_one(lines, "SQUAREFREE")),
            "Odd": _flag(_one(lines, "ODD")),
            "Korselt: (p − 1) | (n − 1) for every p": _flag(_one(lines, "KORSELT")),
            "Carmichael number": verdict,
            "Carmichael function λ(n)": _display(_one(lines, "LAMBDA")),
            "λ(n) divides n − 1": _flag(_one(lines, "LAMBDA_DIVIDES")),
            "Euler totient φ(n)": _display(_one(lines, "TOTIENT")),
            "Fermat liars in [1, n]": _display(liars),
            "Coprime bases scanned": f"{tested} (passed {passed}, failed {_one(lines, 'BASES_FAILED')})",
            "Scan exhaustive": _flag(exhaustive),
        },
        "columns": ["Prime factor", "Exponent", "(n − 1) mod (p − 1)"],
        "rows": factors,
        "note": (
            "Korselt's criterion is necessary and sufficient: an odd squarefree composite n "
            "with (p − 1) | (n − 1) for every prime p | n is a Carmichael number, i.e. every "
            "base coprime to n is a Fermat liar. A bounded base scan confirms but never "
            "establishes that property; the exact liar count is derived from the "
            "factorization instead."
        ),
    }


def chernick_search(k_start: int, k_end: int, limit: int = 100, timeout: int = 300) -> dict:
    """Search Chernick's ``(6k+1)(12k+1)(18k+1)`` Carmichael construction.

    Args:
        k_start: First parameter ``k ≥ 1``.
        k_end: Last parameter, not below ``k_start``.
        limit: Maximum number of reported constructions.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary with one row per Chernick Carmichael number.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP fails or the row count disagrees with ``DONE``.
    """
    if not 1 <= k_start <= k_end <= 100_000_000:
        raise ValueError("Require 1 ≤ start ≤ end ≤ 100,000,000")
    if not 1 <= limit <= 10_000:
        raise ValueError("The result limit must be between 1 and 10,000")
    lines = _execute(f"pl_chernick({k_start},{k_end},{limit})", timeout)
    rows = _records(lines, "CHERNICK", 6)
    if _tagged_values(lines, "DONE") != [len(rows)]:
        raise PrimeEngineError("PARI/GP returned an incomplete Chernick search")
    truncated = _one(lines, "TRUNCATED") == 1
    if any(row[5] != "1" for row in rows):
        raise PrimeEngineError("A Chernick construction failed the Korselt criterion")
    return {
        "truncated": truncated,
        "metrics": {
            "Parameter range": f"{k_start}–{k_end}",
            "Carmichael numbers found": str(len(rows)),
            "Result limit reached": _flag(truncated),
        },
        "columns": ["k", "6k+1", "12k+1", "18k+1", "Carmichael number", "Korselt verified"],
        "rows": [[*row[:5], _flag(int(row[5] == "1"))] for row in rows],
        "note": (
            "Chernick's theorem: when 6k+1, 12k+1 and 18k+1 are all prime their product is a "
            "Carmichael number. PARI/GP proves each factor prime and re-verifies Korselt's "
            "criterion for every reported product."
        ),
    }


# ---------------------------------------------------------------------------
# Item 36: generalized repunit primes
# ---------------------------------------------------------------------------
def repunit_search(base: int, n_start: int, n_end: int, limit: int = 100,
                   budget_seconds: int = 60, timeout: int = 600) -> dict:
    """Search generalized repunits ``(b^n − 1)/(b − 1)`` over a bounded exponent range.

    Args:
        base: Repunit base ``b ≥ 2``.
        n_start: First exponent, at least 1.
        n_end: Last exponent, not below ``n_start``.
        limit: Maximum number of reported hits.
        budget_seconds: PARI ``alarm`` budget per candidate proof.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary with one row per repunit prime or probable prime.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP fails or the row count disagrees with ``DONE``.
    """
    if not 2 <= base <= 1_000_000:
        raise ValueError("The repunit base must be between 2 and 1,000,000")
    if not 1 <= n_start <= n_end <= 100_000:
        raise ValueError("Require 1 ≤ start exponent ≤ end exponent ≤ 100,000")
    if not 1 <= limit <= 10_000:
        raise ValueError("The result limit must be between 1 and 10,000")
    _check_budget(budget_seconds)
    lines = _execute(
        f"pl_repunit({base},{n_start},{n_end},{limit},{budget_seconds})", timeout
    )
    hits = _records(lines, "REPUNIT", 4)
    if _tagged_values(lines, "DONE") != [len(hits)]:
        raise PrimeEngineError("PARI/GP returned an incomplete repunit search")
    truncated = _one(lines, "TRUNCATED") == 1
    return {
        "truncated": truncated,
        "metrics": {
            "Form": f"({base}^n − 1)/({base} − 1)",
            "Exponent range": f"{n_start}–{n_end}",
            "Prime exponents tested": str(_one(lines, "TESTED")),
            "Hits reported": str(len(hits)),
            "Inconclusive candidates": str(_one(lines, "INCONCLUSIVE")),
            "Result limit reached": _flag(truncated),
        },
        "columns": ["Exponent n", "Decimal digits", "Verdict", "Value"],
        "rows": [
            [row[0], row[1], _verdict(int(row[2])),
             row[3] if row[3] != "0" else "value withheld (over 20,000 digits)"]
            for row in hits
        ],
        "note": (
            "A generalized repunit can only be prime when its exponent n is prime, so "
            "composite exponents are skipped natively. Every reported value passes BPSW and "
            "is then settled by PARI isprime; an expired budget is counted as inconclusive."
        ),
    }


# ---------------------------------------------------------------------------
# Item 37: Sierpiński and Riesel numbers
# ---------------------------------------------------------------------------
def sierpinski_riesel_search(k: str, kind: str = "sierpinski", n_max: int = 1000,
                             budget_seconds: int = 30, timeout: int = 600) -> dict:
    """Search for a prime ``k·2^n ± 1`` witnessing that ``k`` is not Sierpiński/Riesel.

    Args:
        k: Decimal multiplier ``k ≥ 1``.
        kind: ``"sierpinski"`` for ``k·2^n + 1`` or ``"riesel"`` for ``k·2^n − 1``.
        n_max: Largest exponent scanned.
        budget_seconds: PARI ``alarm`` budget per candidate proof.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary reporting the first prime found, a probable prime whose
        proof timed out, or an exhausted scan.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP fails or returns an unknown status.
    """
    multiplier = decimal_integer(k)
    if multiplier < 1:
        raise ValueError("The multiplier k must be at least 1")
    if kind not in {"sierpinski", "riesel"}:
        raise ValueError("Select the Sierpiński (+1) or the Riesel (−1) family")
    if not 1 <= n_max <= 100_000:
        raise ValueError("The exponent bound must be between 1 and 100,000")
    _check_budget(budget_seconds)
    sign = 1 if kind == "sierpinski" else -1
    lines = _execute(
        f"pl_sierpinski_search({multiplier},{sign},{n_max},{budget_seconds})", timeout
    )
    status = _text(lines, "STATUS")
    if status not in {"found", "probable", "exhausted"}:
        raise PrimeEngineError("PARI/GP returned an unknown Sierpinski/Riesel status")
    found = _records(lines, "FOUND", 3)
    probable = _optional(lines, "PROBABLE")
    verdicts = {
        "found": "k is not a Sierpiński/Riesel number (a proven prime exists)",
        "probable": "a probable prime was found but its proof budget expired",
        "exhausted": "no prime up to the exponent bound (inconclusive)",
    }
    rows = [[row[0], row[1], "proven prime",
             row[2] if row[2] != "0" else "value withheld (over 20,000 digits)"]
            for row in found]
    if probable is not None:
        rows.append([str(probable), "unknown", "probable prime", "proof budget expired"])
    return {
        "status": status,
        "metrics": {
            "Multiplier k": _display(multiplier),
            "Family": f"k·2^n {'+' if sign == 1 else '−'} 1",
            "Exponents tested": str(_one(lines, "TESTED")),
            "Exponent bound": str(n_max),
            "Outcome": verdicts[status],
        },
        "columns": ["Exponent n", "Decimal digits", "Status", "Value"],
        "rows": rows,
        "note": (
            "Finding one proven prime settles that k is not a Sierpiński (resp. Riesel) "
            "number. Exhausting the exponent bound proves nothing on its own: a Sierpiński "
            "number is established only by a covering set, which the covering-set page "
            "verifies exactly."
        ),
    }


def covering_set_check(k: str, kind: str = "sierpinski", period: int = 36,
                       candidates: list[str] | None = None, timeout: int = 300) -> dict:
    """Verify exactly that a prime set covers every exponent class of ``k·2^n ± 1``.

    Args:
        k: Decimal multiplier ``k ≥ 1``.
        kind: ``"sierpinski"`` for ``k·2^n + 1`` or ``"riesel"`` for ``k·2^n − 1``.
        period: Common period of the covering primes; ``2^period ≡ 1`` must hold
            modulo every member.
        candidates: The covering primes; when empty the engine uses the prime
            divisors of ``2^period − 1``.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary with the covering prime for every residue class.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP fails or the class count is wrong.
    """
    multiplier = decimal_integer(k)
    if multiplier < 1:
        raise ValueError("The multiplier k must be at least 1")
    if kind not in {"sierpinski", "riesel"}:
        raise ValueError("Select the Sierpiński (+1) or the Riesel (−1) family")
    if not 1 <= period <= 1_000:
        raise ValueError("The covering period must be between 1 and 1,000")
    if candidates:
        _, vector = _integer_vector(candidates, maximum=64, label="covering primes",
                                    minimum_value=2)
    else:
        vector = "[]"
    sign = 1 if kind == "sierpinski" else -1
    lines = _execute(f"pl_covering_set({multiplier},{sign},{period},{vector})", timeout)
    covers = _records(lines, "COVER", 2)
    if _one(lines, "PERIOD") != period:
        raise PrimeEngineError("PARI/GP verified a different covering period")
    if _tagged_values(lines, "DONE") != [period] or len(covers) != period:
        raise PrimeEngineError("PARI/GP returned an incomplete covering-set verification")
    covered = _one(lines, "COVERED") == 1
    used = _tagged_values(lines, "USED")
    not_periodic = _tagged_values(lines, "NOT_PERIODIC")
    return {
        "covered": covered,
        "metrics": {
            "Multiplier k": _display(multiplier),
            "Family": f"k·2^n {'+' if sign == 1 else '−'} 1",
            "Period": str(period),
            "Candidate primes": ", ".join(str(v) for v in _tagged_values(lines, "CANDIDATE")),
            "All primes have order dividing the period": _flag(_one(lines, "PERIODIC")),
            "Primes actually used": ", ".join(str(v) for v in used) or "none",
            "Every exponent class covered": _flag(covered),
            "Smallest member exceeds the largest covering prime": _flag(
                _one(lines, "SIZE_CONDITION")
            ),
            "Non-periodic candidates": ", ".join(str(v) for v in not_periodic) or "none",
        },
        "columns": ["Exponent class n mod period", "Covering prime"],
        "rows": [[row[0], row[1] if row[1] != "0" else "uncovered"] for row in covers],
        "note": (
            "A covering set is a proof: if every residue class of n modulo the period "
            "contributes a fixed prime divisor, then k·2^n ± 1 is composite for every n and k "
            "is a Sierpiński (resp. Riesel) number. An uncovered class means this particular "
            "set does not settle k; it does not mean k has no covering set."
        ),
    }


# ---------------------------------------------------------------------------
# Item 40: bi-twin chains and prime ladders
# ---------------------------------------------------------------------------
def bitwin_chain_search(start: str, end: str, min_length: int = 2, limit: int = 100,
                        timeout: int = 600) -> dict:
    """Search maximal bi-twin chains ``n·2^i ± 1`` inside ``[start, end]``.

    Args:
        start: First decimal candidate ``≥ 2``.
        end: Last decimal candidate, not below ``start``.
        min_length: Shortest chain reported.
        limit: Maximum number of reported chains.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary with one row per bi-twin chain.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP fails or the row count disagrees with ``DONE``.
    """
    first, last = decimal_integer(start), decimal_integer(end)
    if first < 2 or last < first:
        raise ValueError("Require 2 ≤ start ≤ end")
    # Resource limit only: the interval width bounds how long the engine may run.
    if last - first > 10**9:
        raise ValueError("The bi-twin search interval may not exceed 10^9 candidates")
    if not 1 <= min_length <= 32:
        raise ValueError("The minimum chain length must be between 1 and 32")
    if not 1 <= limit <= 10_000:
        raise ValueError("The result limit must be between 1 and 10,000")
    lines = _execute(f"pl_bitwin({first},{last},{min_length},{limit})", timeout)
    chains = _records(lines, "BITWIN", 3)
    if _tagged_values(lines, "DONE") != [len(chains)]:
        raise PrimeEngineError("PARI/GP returned an incomplete bi-twin chain search")
    truncated = _one(lines, "TRUNCATED") == 1
    return {
        "truncated": truncated,
        "metrics": {
            "Interval": f"[{_display(first)}, {_display(last)}]",
            "Minimum length": str(min_length),
            "Chains found": str(len(chains)),
            "Longest chain": str(max((int(row[1]) for row in chains), default=0)),
            "Result limit reached": _flag(truncated),
        },
        "columns": ["Chain origin n", "Length", "Members n·2^i − 1 / n·2^i + 1"],
        "rows": chains,
        "note": (
            "A bi-twin chain of length L consists of the twin pairs n·2^i ± 1 for "
            "i = 0 … L−1, all proven prime by PARI/GP. Chains that merely continue a longer "
            "chain starting at n/2 are suppressed, so every reported chain is maximal at its "
            "left end."
        ),
    }


def prime_ladder(start_prime: str, end_prime: str, max_steps: int = 20,
                 timeout: int = 300) -> dict:
    """Find a shortest single-digit-change ladder between two primes of equal width.

    Args:
        start_prime: Decimal proven prime.
        end_prime: Decimal proven prime with the same number of digits.
        max_steps: Maximum breadth-first search depth.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary with one row per rung of the ladder.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP fails or returns an unknown status.
    """
    first, last = decimal_integer(start_prime), decimal_integer(end_prime)
    if first < 2 or last < 2:
        raise ValueError("Prime ladders need two primes at least 2")
    if len(str(first)) != len(str(last)):
        raise ValueError("Both primes must have the same number of decimal digits")
    if len(str(first)) > 9:
        raise ValueError("Prime ladders are limited to 9-digit endpoints")
    if not 1 <= max_steps <= 100:
        raise ValueError("The search depth must be between 1 and 100")
    lines = _execute(f"pl_prime_ladder({first},{last},{max_steps})", timeout)
    status = _text(lines, "STATUS")
    if status not in {"found", "none", "bound"}:
        raise PrimeEngineError("PARI/GP returned an unknown prime-ladder status")
    rungs = _records(lines, "RUNG", 2)
    outcomes = {
        "found": "a shortest ladder exists",
        "none": "no ladder exists: the search exhausted every reachable prime",
        "bound": "the search depth was reached before the target (inconclusive)",
    }
    return {
        "status": status,
        "metrics": {
            "From": str(first),
            "To": str(last),
            "Digits": str(len(str(first))),
            "Ladder length (steps)": str(max(len(rungs) - 1, 0)) if status == "found" else "none",
            "Primes visited": str(_one(lines, "VISITED")),
            "Outcome": outcomes[status],
        },
        "columns": ["Rung", "Prime"],
        "rows": rungs,
        "note": (
            "Each rung changes exactly one decimal digit and every intermediate value is a "
            "proven prime; leading zeros are never introduced. Breadth-first search makes a "
            "reported ladder shortest. Exhausting the depth limit is inconclusive, whereas "
            "exhausting the reachable component proves no ladder exists."
        ),
    }


# ---------------------------------------------------------------------------
# Items 42 and 43: constrained and cryptographic prime construction
# ---------------------------------------------------------------------------
def constrained_prime(bits: int, kind: str = "any", modulus: str = "1", residue: str = "0",
                      certificate: bool = False, seed: str | None = None,
                      budget_seconds: int = 60, candidate_limit: int = 100_000,
                      timeout: int = 600) -> dict:
    """Generate a proven prime of an exact bit length under structural constraints.

    When ``seed`` is omitted the search seed is a raw ``secrets.randbits`` draw;
    that CSPRNG draw is the only use of Python randomness, and PARI/GP alone maps
    it into the requested bit interval. This laboratory is an educational tool,
    **not** audited cryptographic software.

    Args:
        bits: Exact bit length ``8 ≤ bits ≤ 1024``.
        kind: ``"any"``, ``"safe"`` (``p = 2q + 1`` with ``q`` proven prime), or
            ``"strong"`` (Gordon's algorithm).
        modulus: Decimal modulus for an optional residue condition.
        residue: Decimal residue required modulo ``modulus``.
        certificate: Emit a PARI primality certificate for the result.
        seed: Optional decimal search seed making the run reproducible; omitted
            means a fresh CSPRNG draw. PARI/GP places the seed inside the
            interval, so it is not used literally.
        budget_seconds: PARI ``alarm`` budget per candidate proof.
        candidate_limit: Maximum number of candidates examined.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary carrying the proven prime and its optional certificate.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP fails or returns an unknown status.
    """
    if not 8 <= bits <= 1024:
        raise ValueError("The bit length must be between 8 and 1,024")
    if kind not in _CONSTRAINED_KINDS:
        raise ValueError("Select an unconstrained, safe, or strong prime")
    if kind == "strong" and bits < 32:
        raise ValueError("Gordon strong primes require at least 32 bits")
    m, r = decimal_integer(modulus), decimal_integer(residue)
    if m < 1 or not 0 <= r < m:
        raise ValueError("Require modulus ≥ 1 and 0 ≤ residue < modulus")
    _check_budget(budget_seconds)
    if not 1 <= candidate_limit <= 10_000_000:
        raise ValueError("The candidate limit must be between 1 and 10,000,000")
    if seed is None:
        seeds = [secrets.randbits(bits), secrets.randbits(bits)]
        entropy = "CSPRNG (secrets.randbits)"
    else:
        drawn = decimal_integer(seed)
        if drawn < 0:
            raise ValueError("The search seed must be a nonnegative integer")
        seeds = [drawn, drawn]
        entropy = "user-supplied deterministic seed"
    lines = _execute(
        f"pl_constrained_prime({bits},{m},{r},{_CONSTRAINED_KINDS[kind]},"
        f"[{seeds[0]},{seeds[1]}],{int(certificate)},{budget_seconds},{candidate_limit})",
        timeout,
    )
    status = _text(lines, "STATUS")
    if status not in {"proven", "probable", "exhausted", "bound"}:
        raise PrimeEngineError("PARI/GP returned an unknown constrained-prime status")
    prime = _optional(lines, "PRIME")
    candidate = _optional(lines, "CANDIDATE")
    proof = _block(lines, "CERTBEGIN", "CERTEND")
    proof_data = _block(lines, "CERTDATABEGIN", "CERTDATAEND", joiner="")
    certificate_status = _optional(lines, "CERT_STATUS")
    metrics = {
        "Requested bit length": str(bits),
        "Constraint": {"any": "none", "safe": "safe prime p = 2q + 1",
                       "strong": "Gordon strong prime"}[kind],
        "Residue condition": f"p ≡ {r} (mod {m})" if m > 1 else "none",
        "Search seed": entropy,
        "Candidates examined": str(_one(lines, "TESTED")),
        "Status": {
            "proven": "proven prime", "probable": "probable prime (proof budget expired)",
            "exhausted": "no value in range (inconclusive)",
            "bound": "candidate limit reached (inconclusive)",
        }[status],
    }
    rows: list[list[str]] = []
    if prime is not None:
        metrics["Prime"] = _display(prime)
        metrics["Actual bit length"] = str(_one(lines, "BITS"))
        metrics["Residue condition satisfied"] = _flag(_one(lines, "RESIDUE_OK"))
        rows.append(["p", _display(prime)])
    if candidate is not None:
        metrics["Probable prime"] = _display(candidate)
        rows.append(["candidate (unproven)", _display(candidate)])
    q = _optional(lines, "Q")
    if q is not None:
        metrics["Sophie Germain prime q = (p − 1)/2"] = _display(q)
        rows.append(["q = (p − 1)/2", _display(q)])
    for label, tag in (("Gordon auxiliary prime s", "S"), ("Gordon auxiliary prime t", "T"),
                       ("Gordon auxiliary prime r = 2it + 1", "R")):
        auxiliary = _optional(lines, tag)
        if auxiliary is not None:
            metrics[label] = _display(auxiliary)
            rows.append([label, _display(auxiliary)])
    if certificate_status is not None:
        metrics["Primality certificate"] = {
            1: "valid", 0: "invalid", -1: "not produced within the budget",
        }[certificate_status]
    return {
        "status": status,
        "certificate": proof,
        "certificate_data": proof_data,
        "metrics": metrics,
        "columns": ["Quantity", "Value"],
        "rows": rows,
        "note": (
            "Experimental educational tool: this is not audited cryptographic software and "
            "must not be used to generate production keys. PARI/GP performs every primality "
            "decision; Python only draws the random search start with the operating-system "
            "CSPRNG. A prime is reported as proven only after PARI isprime succeeds; an "
            "expired budget yields a probable prime, and an exhausted range or candidate "
            "limit is inconclusive."
            + (f" Certificate: {proof}" if proof else "")
        ),
    }


# ---------------------------------------------------------------------------
# Item 130: educational proof viewer
# ---------------------------------------------------------------------------
def lucas_lehmer_steps(exponent: int, show_limit: int = 20, timeout: int = 600) -> dict:
    """Show the Lucas–Lehmer iteration proving or refuting ``M_p = 2^p − 1``.

    Args:
        exponent: Prime Mersenne exponent ``p``.
        show_limit: Number of leading iterations materialized in the report.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary with the displayed iterations and the final verdict.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP fails.
    """
    if not 2 <= exponent <= 100_000:
        raise ValueError("The Mersenne exponent must be between 2 and 100,000")
    if not 0 <= show_limit <= 10_000:
        raise ValueError("The step display limit must be between 0 and 10,000")
    lines = _execute(f"pl_lucas_lehmer_steps({exponent},{show_limit})", timeout)
    steps = _records(lines, "STEP", 2)
    proven = _one(lines, "PROVEN")
    shown = _one(lines, "SHOWN")
    iterations = _one(lines, "ITERATIONS")
    if len(steps) < min(shown, iterations):
        raise PrimeEngineError("PARI/GP returned an incomplete Lucas-Lehmer trace")
    final = str(iterations)
    return {
        "verdict": _verdict(proven),
        "metrics": {
            "Mersenne exponent p": str(exponent),
            "M_p = 2^p − 1": _display(_one(lines, "N")),
            "Iterations required": str(iterations),
            "Iterations displayed": str(len(steps)),
            "Verdict": _verdict(proven),
        },
        "columns": ["Iteration i", "s_i mod M_p"],
        "rows": [
            [row[0], row[1] if row[1] != "0" or row[0] == final
             else "residue withheld (over 5,000 digits)"]
            for row in steps
        ],
        "note": (
            "The Lucas–Lehmer test is necessary and sufficient for Mersenne numbers with "
            "prime exponent: M_p is prime exactly when s_{p−2} ≡ 0 (mod M_p) starting from "
            "s_0 = 4. The final iteration is always shown; intermediate residues wider than "
            "5,000 digits are withheld from the table and shown as 0."
        ),
    }


def ecpp_steps(number: str, budget_seconds: int = 120, timeout: int = 600) -> dict:
    """Expand a PARI ECPP certificate into its elliptic-curve descent steps.

    Args:
        number: Decimal integer ``n ≥ 2``.
        budget_seconds: PARI ``alarm`` budget for building the certificate.
        timeout: Wall-clock limit for the ``gp`` run.

    Returns:
        A report dictionary with one row per Atkin–Morain descent step.

    Raises:
        ValueError: If any bound is violated.
        PrimeEngineError: If PARI/GP fails.
    """
    value = decimal_integer(number)
    if value < 2:
        raise ValueError("ECPP certificates require an integer at least 2")
    _check_budget(budget_seconds)
    lines = _execute(f"pl_ecpp_steps({value},{budget_seconds})", timeout)
    steps = _records(lines, "ECPP", 11)
    proven = _one(lines, "PROVEN")
    valid = _optional(lines, "VALID")
    small = _optional(lines, "SMALL") == 1
    if steps and _tagged_values(lines, "DONE") != [len(steps)]:
        raise PrimeEngineError("PARI/GP returned an incomplete ECPP certificate")
    return {
        "verdict": _verdict(proven),
        "metrics": {
            "Integer": _display(value),
            "Descent steps": str(len(steps)),
            "Certificate re-verified": {1: "yes", 0: "no", None: "not applicable"}[valid],
            "Below the 2^64 deterministic threshold": _flag(small),
            "Verdict": _verdict(proven),
        },
        "columns": ["Step", "N", "Trace t", "s", "Curve a", "Curve b", "Point x", "Point y",
                    "m = N + 1 − t", "q = m/s", "Discriminant"],
        "rows": [[row[0], _display(int(row[1])), row[2], row[3], row[4], row[5],
                  _display(int(row[6])), _display(int(row[7])), _display(int(row[8])),
                  _display(int(row[9])), row[10]] for row in steps],
        "note": (
            "Each Atkin–Morain step exhibits an elliptic curve y² = x³ + ax + b over Z/NZ, a "
            "point P of order m = N + 1 − t, and a probable prime q = m/s that is certified "
            "by the next step, so the chain terminates in a small proven prime. PARI/GP "
            "re-validated the whole certificate with primecertisvalid. Numbers below 2^64 "
            "are settled by PARI's deterministic test and produce no descent chain."
        ),
    }
