from __future__ import annotations

import re
import shutil
import subprocess


class PrimeEngineError(RuntimeError):
    pass


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


def primality_result(number: int) -> dict[str, object]:
    lines = _run_gp(f"print(\"RESULT:\",isprime({number}))")
    values = _tagged_values(lines, "RESULT")
    if len(values) != 1:
        raise PrimeEngineError("PARI/GP did not return a primality result")
    result = values[0] == 1
    return {
        "number": str(number),
        "digits": len(str(abs(number))),
        "is_prime": result,
        "classification": "prime" if result else "composite",
        "deterministic": True,
        "note": "Tested by PARI/GP isprime; a positive result is a proven prime.",
        "engine": "PARI/GP",
    }


def generate_primes(count: int, digits: int) -> list[int]:
    if digits == 1 and count > 4:
        raise ValueError("There are only four distinct one-digit primes")
    program = (
        f"lo=10^({digits}-1); hi=10^{digits}-1; v=Set(); "
        f"while(#v<{count},v=setunion(v,Set([randomprime([lo,hi])]))); "
        "for(i=1,#v,print(\"P:\",v[i]))"
    )
    values = _tagged_values(_run_gp(program), "P")
    if len(values) != count:
        raise PrimeEngineError("PARI/GP did not generate the requested number of primes")
    return values


def primes_in_range(start: int, end: int, limit: int) -> tuple[list[int], bool, int | None]:
    if start > end:
        raise ValueError("Range start must not exceed range end")
    program = (
        f"c=0; nx=0; forprime(p={start},{end},"
        f"if(c>={limit},nx=p;break);print(\"P:\",p);c++);print(\"NEXT:\",nx)"
    )
    lines = _run_gp(program)
    values = _tagged_values(lines, "P")
    next_values = _tagged_values(lines, "NEXT")
    next_start = next_values[0] if next_values and next_values[0] else None
    return values, next_start is not None, next_start


def primes_after(start: int, count: int) -> list[int]:
    program = f"p={start}; for(i=1,{count},p=nextprime(p+1);print(\"P:\",p))"
    values = _tagged_values(_run_gp(program), "P")
    if len(values) != count:
        raise PrimeEngineError("PARI/GP did not return the requested number of primes")
    return values


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
    checks = "&&".join(f"isprime(p+{offset})" for offset in normalized[1:])
    printed = '",",'.join(f"p+{offset}" for offset in normalized)
    program = (
        f"c=0; nx=0; forprime(p={start},{end - normalized[-1]},"
        f"if(c>={limit},nx=p;break);if({checks},print(\"T:\",{printed});c++));"
        "print(\"NEXT:\",nx)"
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
