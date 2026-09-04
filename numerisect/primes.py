from __future__ import annotations

import re
import shutil
import subprocess
from typing import Literal


class PrimeEngineError(RuntimeError):
    pass


PrimeKind = Literal["prime", "safe", "sophie", "blum", "congruence"]


def _run_gp(program: str, timeout: int = 3600) -> list[str]:
    gp = shutil.which("gp")
    if not gp:
        raise PrimeEngineError("PARI/GP is not installed yet")
    try:
        result = subprocess.run(
            [gp, "-fq", "-s", "256M"],
            input=program + "\nquit\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PrimeEngineError("PARI/GP exceeded the one-hour operation limit") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise PrimeEngineError(f"PARI/GP failed: {detail[-1000:]}")
    if "***" in result.stderr:
        raise PrimeEngineError(f"PARI/GP failed: {result.stderr.strip()[-1000:]}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _tagged_values(lines: list[str], tag: str) -> list[int]:
    prefix = f"{tag}:"
    values: list[int] = []
    for line in lines:
        if line.startswith(prefix):
            text = line[len(prefix):].strip()
            if not re.fullmatch(r"-?\d+", text):
                raise PrimeEngineError("PARI/GP produced an unexpected integer result")
            values.append(int(text))
    return values


def primality_result(
    number: int, *, mode: Literal["fast", "proven"] = "proven", certificate: bool = False
) -> dict[str, object]:
    if mode == "fast" and certificate:
        raise ValueError("Certificates require rigorous proven mode")
    if certificate:
        lines = _run_gp(
            f'c=primecert({number});print("RESULT:",c!=0);'
            'if(c!=0,print("CERTBEGIN");print(primecertexport(c));print("CERTEND"))'
        )
    else:
        function = "ispseudoprime" if mode == "fast" else "isprime"
        lines = _run_gp(f'print("RESULT:",{function}({number}))')
    values = _tagged_values(lines, "RESULT")
    if len(values) != 1:
        raise PrimeEngineError("PARI/GP did not return a primality result")
    passed = values[0] == 1
    classification = (
        "probable prime" if mode == "fast" and passed else "prime" if passed else "composite"
    )
    proof = ""
    if certificate and passed:
        start = lines.index("CERTBEGIN") + 1
        end = lines.index("CERTEND")
        proof = "\n".join(lines[start:end]).strip()
    note = (
        "Fast PARI/GP BPSW probable-prime test; a positive result is not a proof."
        if mode == "fast"
        else "Tested rigorously by PARI/GP; a positive result is a proven prime."
    )
    if proof:
        note += " A human-readable ECPP/primality certificate is included in the export."
    return {
        "number": str(number),
        "digits": len(str(abs(number))),
        "is_prime": passed,
        "classification": classification,
        "deterministic": mode == "proven",
        "mode": mode,
        "note": note,
        "engine": "PARI/GP",
        "certificate": proof,
    }


def generate_primes(count: int, digits: int) -> list[int]:
    return generate_special_primes(count, digits, "prime")


def generate_special_primes(
    count: int,
    digits: int,
    kind: PrimeKind,
    modulus: int | None = None,
    remainder: int | None = None,
) -> list[int]:
    if kind == "prime" and digits == 1 and count > 4:
        raise ValueError("There are only four distinct one-digit primes")
    if kind == "congruence":
        if modulus is None or remainder is None:
            raise ValueError("Modulus and remainder are required for modular primes")
        if modulus < 2 or modulus > 1_000_000:
            raise ValueError("Modulus must be between 2 and 1,000,000")
        remainder %= modulus
    lo = f"10^({digits}-1)"
    hi = f"10^{digits}-1"
    if kind == "safe":
        candidate = f"q=randomprime([max(2,({lo}-1)\\2),({hi}-1)\\2]);p=2*q+1"
        condition = f"p>={lo}&&p<={hi}&&isprime(q)&&isprime(p)"
    else:
        candidate = f"p=randomprime([{lo},{hi}])"
        conditions = {
            "prime": "isprime(p)",
            "sophie": "isprime(p)&&isprime(2*p+1)",
            "blum": "p%4==3&&isprime(p)",
            "congruence": f"p%{modulus}=={remainder}&&isprime(p)",
        }
        condition = conditions[kind]
    attempts = max(10_000, count * 5_000)
    program = (
        f"v=Set();tries=0;while(#v<{count}&&tries<{attempts},"
        f"{candidate};if({condition},v=setunion(v,Set([p])));tries++);"
        'for(i=1,#v,print("P:",v[i]));print("FOUND:",#v)'
    )
    lines = _run_gp(program)
    values = _tagged_values(lines, "P")
    if len(values) != count:
        raise PrimeEngineError(
            f"Found {len(values)} of {count} requested values before the search limit; "
            "try fewer values or a larger digit size"
        )
    return values


def primes_in_range(start: int, end: int, limit: int) -> tuple[list[int], bool, int | None]:
    if start > end:
        raise ValueError("Range start must not exceed range end")
    program = (
        f"c=0;nx=0;forprime(p={start},{end},if(isprime(p),"
        f'if(c>={limit},nx=p;break);print("P:",p);c++));print("NEXT:",nx)'
    )
    lines = _run_gp(program)
    values = _tagged_values(lines, "P")
    next_values = _tagged_values(lines, "NEXT")
    next_start = next_values[0] if next_values and next_values[0] else None
    return values, next_start is not None, next_start


def primes_after(start: int, count: int) -> list[int]:
    program = (
        f"p={start}+1;c=0;while(c<{count},p=nextprime(p);"
        'if(isprime(p),print("P:",p);c++);p++)'
    )
    values = _tagged_values(_run_gp(program), "P")
    if len(values) != count:
        raise PrimeEngineError("PARI/GP did not return the requested number of primes")
    return values


def primes_before(start: int, count: int) -> list[int]:
    program = (
        f"p={start}-1;c=0;while(c<{count}&&p>=2,p=precprime(p);"
        'if(p>=2&&isprime(p),print("P:",p);c++);p--);print("FOUND:",c)'
    )
    return _tagged_values(_run_gp(program), "P")


def nth_prime(index: int) -> int:
    if index < 1:
        raise ValueError("Prime index must be positive")
    if index > 100_000_000_000:
        raise ValueError("The n-th-prime tool supports indices up to 100,000,000,000")
    values = _tagged_values(_run_gp(f'print("RESULT:",prime({index}))'), "RESULT")
    if len(values) != 1:
        raise PrimeEngineError("PARI/GP did not return the requested indexed prime")
    return values[0]


def prime_count(number: int) -> int:
    if number < 0:
        return 0
    if number > 1_000_000_000_000:
        raise ValueError(
            "Exact pi(x) is intentionally limited to 10^12 because PARI/GP primepi uses "
            "a memory-intensive sieve"
        )
    values = _tagged_values(_run_gp(f'print("RESULT:",primepi({number}))'), "RESULT")
    if len(values) != 1:
        raise PrimeEngineError("PARI/GP did not return a prime count")
    return values[0]


def prime_gaps(
    start: int, end: int, limit: int
) -> tuple[list[dict[str, int]], bool, int | None]:
    if start > end:
        raise ValueError("Range start must not exceed range end")
    program = (
        f"prev=0;c=0;nx=0;forprime(p={start},{end},if(isprime(p),if(prev,"
        f'if(c>={limit},nx=prev;break);print("G:",prev,",",p,",",p-prev);c++);'
        'prev=p));print("NEXT:",nx)'
    )
    lines = _run_gp(program)
    gaps: list[dict[str, int]] = []
    for line in lines:
        if not line.startswith("G:"):
            continue
        values = line[2:].strip().split(",")
        if len(values) != 3 or not all(re.fullmatch(r"\d+", value) for value in values):
            raise PrimeEngineError("PARI/GP produced an unexpected prime-gap result")
        left, right, size = map(int, values)
        gaps.append({"from": left, "to": right, "gap": size})
    next_values = _tagged_values(lines, "NEXT")
    next_start = next_values[0] if next_values and next_values[0] else None
    return gaps, next_start is not None, next_start


def prime_tuples_in_range(
    start: int,
    end: int,
    offsets: list[int],
    limit: int,
) -> tuple[list[list[int]], bool, int | None]:
    if start > end:
        raise ValueError("Range start must not exceed range end")
    normalized = sorted(set(offsets))
    if not normalized or normalized[0] != 0:
        raise ValueError("Prime-tuple offsets must start with 0")
    if len(normalized) < 2:
        raise ValueError("A prime tuple needs at least two offsets")
    if normalized[-1] > 1_000_000:
        raise ValueError("The largest tuple offset may not exceed 1,000,000")
    checks = "&&".join(f"isprime(p+{offset})" for offset in normalized)
    printed = '",",'.join(f"p+{offset}" for offset in normalized)
    program = (
        f"c=0;nx=0;forprime(p={start},{end - normalized[-1]},"
        f'if({checks},if(c>={limit},nx=p;break);print("T:",{printed});c++));'
        'print("NEXT:",nx)'
    )
    lines = _run_gp(program)
    tuples: list[list[int]] = []
    for line in lines:
        if not line.startswith("T:"):
            continue
        values = line[2:].strip().split(",")
        if not all(re.fullmatch(r"\d+", value) for value in values):
            raise PrimeEngineError("PARI/GP produced an unexpected prime-tuple result")
        tuples.append([int(value) for value in values])
    next_values = _tagged_values(lines, "NEXT")
    next_start = next_values[0] if next_values and next_values[0] else None
    return tuples, next_start is not None, next_start
