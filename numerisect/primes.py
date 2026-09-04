from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Literal


class PrimeEngineError(RuntimeError):
    pass


PrimeKind = Literal["prime", "safe", "sophie", "blum", "congruence"]

CLASSIFIER_PROGRAM = Path(__file__).with_name("prime_classifier.gp")

PRIME_CLASSIFICATIONS: dict[str, tuple[str, str]] = {
    "balanced": ("Balanced", "The nearest lower and upper prime gaps are equal."),
    "chen": ("Chen", "p + 2 is prime or semiprime."),
    "circular": ("Circular", "Every cyclic rotation of the decimal digits is prime."),
    "cluster": ("Cluster", "Every eligible even difference occurs between primes not exceeding p."),
    "cousin": ("Cousin", "Has a prime partner at distance 4."),
    "cuban": ("Cuban", "Has one of the two cubic-difference forms."),
    "cullen": ("Cullen", "Has the form n·2ⁿ + 1."),
    "delicate": ("Digitally delicate", "Every one-digit decimal replacement is composite."),
    "dihedral": ("Dihedral", "Seven-segment rotations and reflections remain prime."),
    "double_mersenne": ("Double Mersenne", "Has the form 2^(2^q−1) − 1 for prime q."),
    "emirp": ("Emirp", "Its distinct decimal reversal is also prime."),
    "even": ("Even", "The unique even prime."),
    "factorial": ("Factorial", "Differs by one from a factorial."),
    "fermat": ("Fermat", "Has the form 2^(2^n) + 1."),
    "fibonacci": ("Fibonacci", "Occurs in the Fibonacci sequence."),
    "fortunate": ("Fortunate", "Occurs as the least prime offset after a primorial."),
    "good": ("Good", "Dominates every symmetric pair of surrounding primes."),
    "happy": ("Happy", "Repeated decimal digit-square sums reach 1."),
    "higgs": ("Higgs", "Belongs to the exponent-2 Higgs-prime sequence."),
    "left_and_right_truncatable": ("Left-and-right truncatable", "Simultaneous outer truncations remain prime."),
    "left_truncatable": ("Left-truncatable", "Every successive left truncation remains prime."),
    "lucas": ("Lucas", "Occurs in the Lucas sequence."),
    "mersenne": ("Mersenne", "Is one less than a power of two."),
    "mills": ("Mills", "Occurs in the established Mills-prime sequence."),
    "minimal": ("Minimal", "No shorter decimal digit subsequence forms a prime."),
    "motzkin": ("Motzkin", "Occurs in the Motzkin-number sequence."),
    "non_insertable": ("Non-insertable", "Inserting any decimal digit produces a composite."),
    "newman_shanks_williams": ("Newman–Shanks–Williams", "Occurs at an eligible odd index in the NSW sequence."),
    "palindromic": ("Palindromic", "Its decimal digits read the same in reverse."),
    "pell": ("Pell", "Occurs in the Pell sequence."),
    "pell_lucas": ("Pell–Lucas", "Occurs in the half-companion Pell sequence."),
    "permutable": ("Permutable", "All decimal digit permutations are prime."),
    "pierpont": ("Pierpont", "Has the form 2^u·3^v + 1."),
    "pillai": ("Pillai", "Satisfies the defining factorial congruence for some n."),
    "prime_quadruplet": ("Prime quadruplet", "Belongs to a {q,q+2,q+6,q+8} constellation."),
    "prime_triplet": ("Prime triplet", "Belongs to a three-prime constellation of diameter 6."),
    "primorial": ("Primorial", "Differs by one from a prime primorial."),
    "proth": ("Proth", "Has the form k·2^n + 1 with odd k < 2^n."),
    "pythagorean": ("Pythagorean", "Is congruent to 1 modulo 4."),
    "quartan": ("Quartan", "Is a sum of two positive fourth powers."),
    "repunit": ("Repunit", "Its decimal representation contains only ones."),
    "right_truncatable": ("Right-truncatable", "Every successive right truncation remains prime."),
    "safe": ("Safe", "(p − 1)/2 is prime."),
    "sexy": ("Sexy", "Has a prime partner at distance 6."),
    "sophie_germain": ("Sophie Germain", "2p + 1 is prime."),
    "strobogrammatic": ("Strobogrammatic", "Its decimal display is unchanged by a 180° rotation."),
    "strong": ("Strong", "Exceeds the mean of its nearest prime neighbors."),
    "superprime": ("Superprime", "Its index in the prime sequence is itself prime."),
    "supersingular": ("Supersingular", "Divides the order of the Monster group."),
    "twin": ("Twin", "Has a prime partner at distance 2."),
    "wagstaff": ("Wagstaff", "Has the form (2^q + 1)/3 for an odd prime q."),
    "wieferich": ("Wieferich", "Satisfies 2^(p−1) ≡ 1 modulo p²."),
    "williams": ("Williams", "Has the form (b−1)b^n − 1 for a tested base."),
    "wilson": ("Wilson", "Satisfies (p−1)! ≡ −1 modulo p²."),
    "wolstenholme": ("Wolstenholme", "Satisfies the strengthened Wolstenholme congruence."),
    "woodall": ("Woodall", "Has the form n·2ⁿ − 1."),
}


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
        raise PrimeEngineError(f"PARI/GP exceeded the {timeout}-second operation limit") from exc
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


def classify_prime(number: int, *, per_test_seconds: int = 2) -> dict[str, object]:
    if not 1 <= per_test_seconds <= 10:
        raise ValueError("The per-class time budget must be between 1 and 10 seconds")
    try:
        classifier = CLASSIFIER_PROGRAM.read_text(encoding="utf-8")
    except OSError as exc:
        raise PrimeEngineError("The PARI/GP prime-classification program is unavailable") from exc

    # Allow every native classification to consume its own budget before the
    # subprocess-level safety timeout can fire.
    timeout = max(60, per_test_seconds * len(PRIME_CLASSIFICATIONS) + 30)
    lines = _run_gp(
        f"{classifier}\nclassify_prime({number},{per_test_seconds});",
        timeout=timeout,
    )
    prime_values = _tagged_values(lines, "PRIME")
    if len(prime_values) != 1:
        raise PrimeEngineError("PARI/GP did not return a prime-classification verdict")
    is_prime = prime_values[0] == 1

    matches: list[dict[str, str]] = []
    inconclusive: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in lines:
        if not (line.startswith("CLASS:") or line.startswith("UNKNOWN:")):
            continue
        status, identifier, detail = (line.split(":", 2) + [""])[:3]
        if identifier not in PRIME_CLASSIFICATIONS or identifier in seen:
            raise PrimeEngineError("PARI/GP produced an unexpected classification result")
        seen.add(identifier)
        name, description = PRIME_CLASSIFICATIONS[identifier]
        item = {
            "id": identifier,
            "name": name,
            "description": description,
            "detail": detail.strip(),
        }
        (matches if status == "CLASS" else inconclusive).append(item)

    tested = len(PRIME_CLASSIFICATIONS) if is_prime else 0
    return {
        "number": str(number),
        "digits": len(str(abs(number))),
        "is_prime": is_prime,
        "classification": "prime" if is_prime else "composite",
        "matches": matches,
        "inconclusive": inconclusive,
        "tested": tested,
        "not_matched": tested - len(matches) - len(inconclusive),
        "engine": "PARI/GP",
        "note": (
            f"PARI/GP rigorously proved the input prime and evaluated {tested} classifications."
            if is_prime
            else "PARI/GP rigorously determined that the input is composite; prime classifications were not run."
        ),
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
