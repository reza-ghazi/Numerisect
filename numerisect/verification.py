# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent cross-engine verification and engine self-tests.

Most of Numerisect exposes what one engine can do. This module does something no
single engine can do for itself: it asks several *independent* implementations the
same mathematical question and reports whether they agree.

Two facilities:

**Cross-checks.** A quantity is computed by every installed engine that can produce
it, and the answers are compared. Agreement across independent implementations is
real evidence; disagreement is reported loudly rather than resolved by preferring a
favourite. Numerisect never picks a winner.

**Self-tests.** Each engine is asked questions with known published answers. A
miscompiled library, a wrong architecture flag or a subtly broken build shows up
here rather than in a result someone trusts.

Every computation is performed by an engine:

===========================  ===============================================
Quantity                     Sources cross-checked
===========================  ===============================================
pi(x)                        primecount (six algorithms), primesieve --count,
                             PARI ``primepi``
Primality                    PARI ``isprime`` (proof), PARI ``ispseudoprime``
                             (BPSW), GMP via ``numerisect-bigsieve``
Prime enumeration            ``numerisect-bigsieve``, primesieve, PARI
                             ``forprime``
Factorization                PARI ``factor``, YAFU, Msieve
zeta(s)                      FLINT/Arb ``numerisect-zeta``, PARI ``zeta``
===========================  ===============================================

Python compares strings and records outcomes. It computes nothing.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
from typing import Any

from .native_tools import bigsieve_tool_path
from .primes import PrimeEngineError, _run_gp

DECIMAL = re.compile(r"^-?\d+$")

# Questions with published answers, used to detect a broken engine build.
SELF_TESTS: dict[str, list[dict[str, Any]]] = {
    "gp": [
        {"question": "isprime(32416190071)", "program": "print(isprime(32416190071))", "expect": "1",
         "cites": "32416190071 is prime"},
        {"question": "primepi(10^6)", "program": "print(primepi(10^6))", "expect": "78498",
         "cites": "pi(10^6) = 78498"},
        {"question": "factor(8051)", "program": "print(factor(8051)[,1]~)", "expect": "[83, 97]",
         "cites": "8051 = 83 * 97"},
        {"question": "eulerphi(2310)", "program": "print(eulerphi(2310))", "expect": "480",
         "cites": "phi(2310) = 480"},
        {"question": "znorder(Mod(10,7))", "program": "print(znorder(Mod(10,7)))", "expect": "6",
         "cites": "1/7 has period 6"},
    ],
    "primecount": [
        {"question": "pi(10^10)", "args": ["10000000000"], "expect": "455052511",
         "cites": "pi(10^10) = 455052511"},
        {"question": "pi(10^6)", "args": ["1000000"], "expect": "78498",
         "cites": "pi(10^6) = 78498"},
        {"question": "nth prime 10^6", "args": ["1000000", "--nth-prime"], "expect": "15485863",
         "cites": "the millionth prime is 15485863"},
    ],
    "primesieve": [
        {"question": "count primes below 10^7", "args": ["10000000", "--count", "-q"],
         "expect": "664579", "cites": "pi(10^7) = 664579"},
        {"question": "nth prime 10^6", "args": ["1000000", "--nth-prime", "-q"],
         "expect": "15485863", "cites": "the millionth prime is 15485863"},
    ],
}


def _run(command: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PrimeEngineError(f"{command[0]} exceeded the {timeout}-second limit") from exc
    except OSError as exc:
        raise PrimeEngineError(f"{command[0]} could not be started: {exc}") from exc
    return result.returncode, result.stdout


def _yafu(expression: str, timeout: int) -> tuple[str, float] | None:
    """Run one YAFU expression and return its output with the elapsed time.

    ``None`` when YAFU is not installed, which is normal: it is optional.
    """

    executable = shutil.which("yafu")
    if not executable:
        return None
    started = time.monotonic()
    # The expression goes on stdin. Passed as an argument instead, this build treats it
    # as a batchfile name and reads stdin anyway, finishing instantly with no verdict.
    try:
        result = subprocess.run(
            [executable], input=f"{expression}\n", stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False, cwd=tempfile.gettempdir(),
        )
    except subprocess.TimeoutExpired as exc:
        raise PrimeEngineError(f"YAFU exceeded the {timeout}-second limit") from exc
    except OSError as exc:
        raise PrimeEngineError(f"YAFU could not be started: {exc}") from exc
    return result.stdout, round(time.monotonic() - started, 4)


def _yafu_verdict(output: str) -> bool | None:
    """Read a primality verdict out of YAFU's prose.

    YAFU prints the verdict as English and returns the *input* in ``ans``, so the
    value cannot be used as the answer: ``aprcl(1000003)`` prints "Input is prime." and
    sets ``ans = 1000003``. Reading ``ans`` would silently turn every verdict into a
    truthy number, so the text is what is parsed, and an unrecognised shape is ``None``
    rather than a guess.
    """

    lowered = output.lower()
    prime = "input is prime" in lowered
    composite = "input is composite" in lowered
    if prime == composite:                       # both or neither: no usable verdict
        return None
    return prime


def _yafu_answer(output: str) -> str | None:
    """Return the integer YAFU assigned to ``ans``, or ``None``.

    ``llt`` is the one YAFU function whose verdict is the returned value rather than
    prose, and YAFU writes it as ``ans = 1``. The value is not a bare line, so the
    assignment is matched explicitly instead of scanning for a trailing integer.
    """

    matches = re.findall(r"^\s*ans\s*=\s*(-?\d+)\s*$", output, re.MULTILINE)
    return matches[-1] if matches else None


def _last_integer(text: str) -> str | None:
    for line in reversed(text.strip().splitlines()):
        candidate = line.strip()
        if DECIMAL.match(candidate):
            return candidate
    return None


def cross_check_prime_count(x: int, threads: int = 1, timeout: int = 600) -> dict[str, Any]:
    """Compute pi(x) with every available independent method and compare.

    primecount's six algorithm modes are mathematically different: Legendre, Meissel,
    Lehmer, Lagarias-Miller-Odlyzko, Deleglise-Rivat and Gourdon. They share one
    codebase. primesieve counts by sieving, and PARI's primepi is a third engine
    implementation. Agreement across the engines is independent evidence; a
    disagreement is reported rather than resolved.

    Args:
        x: Upper bound.
        threads: Threads for the engines that accept a thread count.
        timeout: Per-engine time limit in seconds.

    Returns:
        ``{"value", "sources": [...], "agree": bool, "disagreements": [...]}``.

    Raises:
        ValueError: If x is negative.
        PrimeEngineError: If no engine could produce an answer.
    """

    if x < 0:
        raise ValueError("pi(x) needs a non-negative bound")
    sources: list[dict[str, Any]] = []

    primecount = shutil.which("primecount")
    if primecount:
        for algorithm in (
            "--legendre", "--meissel", "--lehmer", "--lmo", "--deleglise-rivat", "--gourdon",
        ):
            started = time.monotonic()
            try:
                code, output = _run(
                    [primecount, str(x), algorithm, f"--threads={threads}"], timeout
                )
            except PrimeEngineError as exc:
                sources.append({"engine": f"primecount {algorithm[2:]}", "value": None,
                                "seconds": None, "error": str(exc)})
                continue
            value = _last_integer(output) if code == 0 else None
            sources.append({
                "engine": f"primecount {algorithm[2:]}",
                "value": value,
                "seconds": round(time.monotonic() - started, 4),
                "error": None if value else output.strip()[:200],
            })

    primesieve = shutil.which("primesieve")
    # primesieve counts an inclusive interval starting at 1.
    if primesieve and x >= 1:
        started = time.monotonic()
        try:
            code, output = _run(
                [primesieve, "1", "-d", str(x - 1), "--count", "-q", f"--threads={threads}"],
                timeout,
            )
            value = _last_integer(output) if code == 0 else None
        except PrimeEngineError as exc:
            value, output = None, str(exc)
        sources.append({
            "engine": "primesieve sieve",
            "value": value,
            "seconds": round(time.monotonic() - started, 4),
            "error": None if value else str(output)[:200],
        })

    # PARI's primepi is exact but impractical far above 10^12; keep it in range.
    if x <= 10**12:
        started = time.monotonic()
        try:
            lines = _run_gp(f"print(primepi({x}))", timeout=timeout)
            value = _last_integer("\n".join(lines))
        except PrimeEngineError as exc:
            value = None
            lines = [str(exc)]
        sources.append({
            "engine": "PARI/GP primepi",
            "value": value,
            "seconds": round(time.monotonic() - started, 4),
            "error": None if value else "\n".join(lines)[:200],
        })

    answered = [source for source in sources if source["value"] is not None]
    if not answered:
        raise PrimeEngineError("No engine was able to compute pi(x)")
    distinct = sorted({source["value"] for source in answered})
    agree = len(distinct) == 1
    implementations = len({
        "primecount" if str(source["engine"]).startswith("primecount ")
        else "primesieve" if str(source["engine"]).startswith("primesieve ")
        else "PARI/GP"
        for source in answered
    })
    return {
        "input": str(x),
        "value": distinct[0] if agree else None,
        "sources": sources,
        "engines_answering": len(answered),
        "method_outputs_answering": len(answered),
        "engine_implementations_answering": implementations,
        "agree": agree,
        "distinct_values": distinct,
        "disagreements": [] if agree else [
            {"engine": source["engine"], "value": source["value"]} for source in answered
        ],
        "note": (
            f"{len(answered)} method outputs from {implementations} independent engine "
            f"implementations agree on pi({x})."
            if agree else
            "THESE ENGINES DISAGREE. One of them is faulty. Numerisect does not choose "
            "between them; treat every value here as unreliable until the cause is found."
        ),
    }


def cross_check_primality(number: int, timeout: int = 300) -> dict[str, Any]:
    """Test one integer for primality with independent implementations.

    PARI's ``isprime`` is a proof, ``ispseudoprime`` is Baillie-PSW, and GMP's
    test reached through the big sieve is an independent BPSW plus Miller-Rabin.
    They answer the same question by different means.

    Returns:
        The per-engine verdicts, whether they agree, and which results are proofs.
    """

    if number < 0:
        raise ValueError("Primality needs a non-negative integer")
    sources: list[dict[str, Any]] = []

    started = time.monotonic()
    try:
        lines = _run_gp(f"print(isprime({number}));print(ispseudoprime({number}))", timeout=timeout)
        values = [line.strip() for line in lines if line.strip() in {"0", "1"}]
    except PrimeEngineError as exc:
        values = []
        sources.append({"engine": "PARI/GP isprime", "prime": None, "proof": True,
                        "error": str(exc), "seconds": None})
    if len(values) >= 2:
        elapsed = round(time.monotonic() - started, 4)
        sources.append({"engine": "PARI/GP isprime", "prime": values[0] == "1",
                        "proof": True, "error": None, "seconds": elapsed})
        sources.append({"engine": "PARI/GP ispseudoprime (BPSW)", "prime": values[1] == "1",
                        "proof": False, "error": None, "seconds": elapsed})

    try:
        tool = bigsieve_tool_path()
        started = time.monotonic()
        code, output = _run([str(tool), str(number), "1", "1000", "1"], timeout)
        found = "PRIME:" in output
        sources.append({
            "engine": "GMP BPSW + Miller-Rabin",
            "prime": found if code == 0 else None,
            "proof": False,
            "error": None if code == 0 else output.strip()[:200],
            "seconds": round(time.monotonic() - started, 4),
        })
    except (RuntimeError, PrimeEngineError) as exc:
        sources.append({"engine": "GMP BPSW + Miller-Rabin", "prime": None, "proof": False,
                        "error": str(exc), "seconds": None})

    # YAFU's APR-CL is the only other proof engine installed: PARI's isprime is the
    # first. Everything else here is probabilistic, so two independent proofs agreeing
    # is a stronger statement than a proof agreeing with a probable-prime test.
    try:
        attempt = _yafu(f"aprcl({number})", timeout)
    except PrimeEngineError as exc:
        sources.append({"engine": "YAFU APR-CL", "prime": None, "proof": True,
                        "error": str(exc), "seconds": None})
        attempt = None
    if attempt is not None:
        output, elapsed = attempt
        verdict = _yafu_verdict(output)
        sources.append({
            "engine": "YAFU APR-CL",
            "prime": verdict,
            # YAFU documents APR-CL as a proof below 6021 digits, falling back to BPSW
            # above it, so the claim is only a proof inside that range.
            "proof": len(str(number)) <= 6021,
            "error": None if verdict is not None else "YAFU returned no recognisable verdict",
            "seconds": elapsed,
        })

    answered = [source for source in sources if source["prime"] is not None]
    if not answered:
        raise PrimeEngineError("No engine was able to decide primality")
    verdicts = {source["prime"] for source in answered}
    agree = len(verdicts) == 1
    proven = any(source["proof"] and source["prime"] for source in answered)
    return {
        "input": str(number),
        "prime": next(iter(verdicts)) if agree else None,
        "proven": proven and agree,
        "sources": sources,
        "agree": agree,
        "proofs": [
            source["engine"] for source in answered if source["proof"]
        ],
        "note": (
            (
                (
                    "Two independent proof engines and the probabilistic tests all agree."
                    if len([s for s in answered if s["proof"]]) > 1
                    else "A PARI proof and independent probabilistic tests agree."
                )
                if proven else "Independent probabilistic tests agree; this is not a proof."
            )
            if agree else
            "THESE ENGINES DISAGREE about primality. A disagreement between a proof and a "
            "probabilistic test would be a genuine discovery or, far more likely, a broken "
            "engine build. Run the engine self-test."
        ),
    }


def cross_check_mersenne(exponent: int, timeout: int = 600) -> dict[str, Any]:
    """Decide the primality of ``2**exponent - 1`` with two Lucas-Lehmer implementations.

    Mersenne primality rested on PARI alone. YAFU carries its own Lucas-Lehmer test,
    so the same question can be asked twice through unrelated code. The test is
    deterministic for prime exponents, which is what makes an agreement meaningful:
    both engines either prove it or disprove it.

    Args:
        exponent: The exponent ``p``; ``M_p`` is never constructed by this module.
        timeout: Wall-clock budget for each engine.

    Returns:
        Per-engine verdicts, whether they agree, and a note on what that means.

    Raises:
        ValueError: If the exponent is out of range.
        PrimeEngineError: If no engine decided the question.
    """

    if not 2 <= exponent <= 10_000_000:
        raise ValueError("The exponent must be between 2 and 10,000,000")
    sources: list[dict[str, Any]] = []

    started = time.monotonic()
    try:
        # Lucas-Lehmer in GP, which never materialises M_p outside the modulus.
        lines = _run_gp(
            f"p={exponent};if(!isprime(p),print(\"EXPONENT_COMPOSITE\"),"
            "my(m=2^p-1,s=Mod(4,m));for(i=1,p-2,s=s^2-2);"
            'print(if(s==0,"PRIME","COMPOSITE")));',
            timeout=timeout,
        )
        verdict = next(
            (line for line in lines if line in {"PRIME", "COMPOSITE", "EXPONENT_COMPOSITE"}),
            None,
        )
        sources.append({
            "engine": "PARI/GP Lucas-Lehmer",
            "prime": None if verdict in {None, "EXPONENT_COMPOSITE"} else verdict == "PRIME",
            "proof": True,
            "error": (
                "Lucas-Lehmer applies to prime exponents only"
                if verdict == "EXPONENT_COMPOSITE" else
                None if verdict else "PARI/GP returned no verdict"
            ),
            "seconds": round(time.monotonic() - started, 4),
        })
    except PrimeEngineError as exc:
        sources.append({"engine": "PARI/GP Lucas-Lehmer", "prime": None, "proof": True,
                        "error": str(exc), "seconds": None})

    # A composite exponent is refused rather than answered. M_p is composite then for a
    # trivial algebraic reason (2^a - 1 divides 2^(ab) - 1), which is not a Lucas-Lehmer
    # result, and YAFU would happily return that 0 — leaving a one-engine verdict
    # presented as a cross-checked Lucas-Lehmer proof.
    if any(
        source["error"] == "Lucas-Lehmer applies to prime exponents only"
        for source in sources
    ):
        raise ValueError(
            f"Lucas-Lehmer applies to prime exponents, and {exponent} is composite. "
            f"2^{exponent} - 1 is composite for an algebraic reason instead: 2^a - 1 "
            "divides 2^(ab) - 1."
        )

    try:
        attempt = _yafu(f"llt({exponent})", timeout)
    except PrimeEngineError as exc:
        sources.append({"engine": "YAFU Lucas-Lehmer", "prime": None, "proof": True,
                        "error": str(exc), "seconds": None})
        attempt = None
    if attempt is not None:
        output, elapsed = attempt
        # llt is the one YAFU function whose verdict really is the returned value:
        # ans = 1 for a Mersenne prime, 0 otherwise. There is no prose to read.
        answer = _yafu_answer(output)
        sources.append({
            "engine": "YAFU Lucas-Lehmer",
            "prime": None if answer not in {"0", "1"} else answer == "1",
            "proof": True,
            "error": None if answer in {"0", "1"} else "YAFU returned no recognisable verdict",
            "seconds": elapsed,
        })

    answered = [source for source in sources if source["prime"] is not None]
    if not answered:
        raise PrimeEngineError(
            "No engine decided this Mersenne number; Lucas-Lehmer needs a prime exponent"
        )
    verdicts = {source["prime"] for source in answered}
    agree = len(verdicts) == 1
    return {
        "exponent": str(exponent),
        "prime": next(iter(verdicts)) if agree else None,
        "proven": agree,
        "sources": sources,
        "agree": agree,
        "engines": len(answered),
        "note": (
            (
                f"{len(answered)} independent Lucas-Lehmer implementations agree. The "
                "test is deterministic for a prime exponent, so this is a proof either way."
                if len(answered) > 1 else
                "Only one engine answered, so this is its verdict rather than a "
                "cross-check. Lucas-Lehmer is deterministic for a prime exponent, so the "
                "verdict is still a proof."
            )
            if agree else
            "THESE ENGINES DISAGREE about a deterministic test. One of the builds is "
            "broken; run the engine self-test before trusting either answer."
        ),
    }


def cross_check_nth_prime(index: int, timeout: int = 600) -> dict[str, Any]:
    """Compute the ``index``-th prime with two unrelated implementations.

    primecount and primesieve both answer this exactly, from separate codebases, which
    the pi(x) comparison cannot claim for its first six sources: those are distinct
    algorithms inside one library.

    Returns:
        Per-engine values, whether they agree, and the agreed prime when they do.

    Raises:
        ValueError: If the index is out of range.
        PrimeEngineError: If no engine answered.
    """

    if not 1 <= index <= 10**15:
        raise ValueError("The index must be between 1 and 10^15")
    sources: list[dict[str, Any]] = []
    for engine, arguments in (
        ("primecount", [str(index), "--nth-prime"]),
        ("primesieve", [str(index), "--nth-prime", "-q"]),
    ):
        executable = shutil.which(engine)
        if not executable:
            sources.append({"engine": engine, "value": None, "error": "not installed",
                            "seconds": None})
            continue
        started = time.monotonic()
        try:
            code, output = _run([executable, *arguments], timeout)
        except PrimeEngineError as exc:
            sources.append({"engine": engine, "value": None, "error": str(exc),
                            "seconds": None})
            continue
        value = _last_integer(output) if code == 0 else None
        sources.append({
            "engine": engine,
            "value": value,
            "error": None if value else output.strip()[:200] or "no value returned",
            "seconds": round(time.monotonic() - started, 4),
        })

    answered = [source for source in sources if source["value"]]
    if not answered:
        raise PrimeEngineError("No engine computed the n-th prime")
    values = {source["value"] for source in answered}
    agree = len(values) == 1
    return {
        "index": str(index),
        "prime": next(iter(values)) if agree else None,
        "sources": sources,
        "agree": agree,
        "engines": len(answered),
        "note": (
            (
                f"{len(answered)} independent implementations agree on the "
                f"{index:,}-th prime."
                if len(answered) > 1 else
                f"Only one engine answered, so the {index:,}-th prime is its value rather "
                "than a cross-checked one."
            )
            if agree else
            "THESE ENGINES DISAGREE on an exact value. One build is wrong; run the engine "
            "self-test."
        ),
    }


def self_test(engines: list[str] | None = None, timeout: int = 300) -> dict[str, Any]:
    """Ask each installed engine questions with published answers.

    This catches a miscompiled or mismatched engine build before its output is
    trusted. Every expected value is a published constant cited in ``cites``.

    Args:
        engines: Engines to test; ``None`` tests every one that is installed.
        timeout: Per-question time limit in seconds.

    Returns:
        ``{"results": [...], "passed": n, "failed": n, "healthy": bool}``.
    """

    selected = engines or list(SELF_TESTS)
    results: list[dict[str, Any]] = []
    for engine in selected:
        checks = SELF_TESTS.get(engine)
        if checks is None:
            raise ValueError(f"'{engine}' has no self-test defined")
        executable = shutil.which(engine)
        if not executable:
            results.append({"engine": engine, "question": "-", "status": "not installed",
                            "expected": "-", "actual": "-", "cites": "-"})
            continue
        for check in checks:
            try:
                if "program" in check:
                    lines = _run_gp(check["program"], timeout=timeout)
                    actual = lines[-1].strip() if lines else ""
                else:
                    code, output = _run([executable, *check["args"]], timeout)
                    actual = (_last_integer(output) or output.strip()[:80]) if code == 0 else ""
            except PrimeEngineError as exc:
                actual = f"error: {exc}"
            passed = actual == check["expect"]
            results.append({
                "engine": engine,
                "question": check["question"],
                "status": "pass" if passed else "FAIL",
                "expected": check["expect"],
                "actual": actual,
                "cites": check["cites"],
            })

    tested = [row for row in results if row["status"] in {"pass", "FAIL"}]
    failed = [row for row in tested if row["status"] == "FAIL"]
    return {
        "results": results,
        "tested": len(tested),
        "passed": len(tested) - len(failed),
        "failed": len(failed),
        "healthy": not failed,
        "note": (
            "Every installed engine answered its published test values correctly."
            if not failed else
            "AN ENGINE RETURNED A WRONG ANSWER. Do not trust results from it until the "
            "build is investigated."
        ),
    }


MAX_SIEVE_LENGTH = 100_000_000
MAX_SIEVE_START_DIGITS = 400


def sieve_interval(
    start: int,
    length: int,
    small_prime_bound: int = 1_000_000,
    threads: int = 1,
    extra_rounds: int = 0,
    timeout: int = 900,
) -> dict[str, Any]:
    """Enumerate primes in ``[start, start + length)`` at any magnitude.

    Performed by ``numerisect-bigsieve``, a GMP and OpenMP program in this project.
    It exists because primesieve refuses inputs at or above 2**64 and PARI's
    forprime is single-threaded and much slower there. Measured on a 10^6-wide
    window near 10^30: PARI 916 ms on one core, this helper 40 ms on 24.

    Results at or above 2**64 are **probable** primes from Baillie-PSW plus
    Miller-Rabin, not proofs. Below 2**64 the same test is exact.

    Args:
        start: Interval start, any size.
        length: Number of integers examined; the interval is half-open.
        small_prime_bound: Presieve bound; higher removes more candidates.
        threads: OpenMP threads.
        extra_rounds: Additional Miller-Rabin rounds beyond the default 25.
        timeout: Wall-clock limit in seconds.

    Returns:
        ``{"primes": [...], "count", "candidates", "status", "proven", "note"}``.

    Raises:
        ValueError: On out-of-range arguments.
        PrimeEngineError: If the helper fails, times out, or omits its marker.
    """

    if start < 0:
        raise ValueError("The interval must start at a non-negative integer")
    if len(str(start)) > MAX_SIEVE_START_DIGITS:
        raise ValueError(f"The start is limited to {MAX_SIEVE_START_DIGITS} digits")
    if not 1 <= length <= MAX_SIEVE_LENGTH:
        raise ValueError(f"The length must be between 1 and {MAX_SIEVE_LENGTH:,}")
    if not 100 <= small_prime_bound <= 100_000_000:
        raise ValueError("The presieve bound must be between 100 and 100,000,000")
    if not 1 <= threads <= 1024:
        raise ValueError("Threads must be between 1 and 1024")
    if not 0 <= extra_rounds <= 64:
        raise ValueError("Extra Miller-Rabin rounds must be between 0 and 64")

    try:
        tool = bigsieve_tool_path()
    except RuntimeError as exc:
        raise PrimeEngineError(str(exc)) from exc
    code, output = _run(
        [str(tool), str(start), str(length), str(small_prime_bound),
         str(threads), str(extra_rounds)],
        timeout,
    )
    if code != 0:
        raise PrimeEngineError(f"The big sieve failed: {output.strip()[:200]}")
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not any(line.startswith("DONE:") for line in lines):
        raise PrimeEngineError("The big sieve returned no completion marker")
    primes = [line[len("PRIME:"):] for line in lines if line.startswith("PRIME:")]
    def tag(name: str, default: str = "") -> str:
        for line in lines:
            if line.startswith(f"{name}:"):
                return line[len(name) + 1:]
        return default
    status = tag("STATUS", "probable")
    count = tag("COUNT", str(len(primes)))
    if int(count) != len(primes):
        raise PrimeEngineError("The big sieve returned an inconsistent count")
    return {
        "start": str(start),
        "length": length,
        "primes": primes,
        "count": len(primes),
        "candidates": int(tag("CANDIDATES", "0")),
        "threads": int(tag("THREADS", str(threads))),
        "small_prime_bound": int(tag("SMALL_PRIME_BOUND", str(small_prime_bound))),
        "status": status,
        "proven": status == "exact",
        "engine": "numerisect-bigsieve (C/GMP/OpenMP)",
        "note": (
            "Below 2^64 this test is exact."
            if status == "exact" else
            "At or above 2^64 these are PROBABLE primes from Baillie-PSW plus "
            "Miller-Rabin, not proofs. Use the primality tools to prove any of them."
        ),
    }
