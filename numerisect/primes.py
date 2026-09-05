from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Literal


class PrimeEngineError(RuntimeError):
    pass


PrimeKind = Literal["prime", "safe", "sophie", "blum", "congruence"]

CLASSIFIER_PROGRAM = Path(__file__).with_name("prime_classifier.gp")
RECIPROCAL_PROGRAM = Path(__file__).with_name("prime_reciprocal.gp")
STRUCTURE_PROGRAM = Path(__file__).with_name("prime_structures.gp")

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


def _run_gp(program: str, timeout: int | None = 3600) -> list[str]:
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


def analyze_prime_reciprocal(
    number: int,
    *,
    digit_limit: int = 1000,
    timeout_seconds: int = 0,
    export_path: Path | None = None,
) -> dict[str, object]:
    if not 0 <= digit_limit <= 100_000:
        raise ValueError("The decimal digit limit must be between 0 and 100,000")
    if not 0 <= timeout_seconds <= 3600:
        raise ValueError("The operation time limit must be 0 or between 1 and 3,600 seconds")
    try:
        reciprocal_program = RECIPROCAL_PROGRAM.read_text(encoding="utf-8")
    except OSError as exc:
        raise PrimeEngineError("The PARI/GP reciprocal-prime program is unavailable") from exc

    gp_export_path = json.dumps(str(export_path) if export_path is not None else "")
    lines = _run_gp(
        f"{reciprocal_program}\n"
        f"analyze_prime_reciprocal({number},{digit_limit},{gp_export_path});",
        timeout=None if timeout_seconds == 0 else timeout_seconds,
    )
    prime_values = _tagged_values(lines, "PRIME")
    if len(prime_values) != 1:
        raise PrimeEngineError("PARI/GP did not return a reciprocal-prime verdict")
    if prime_values[0] != 1:
        raise ValueError("The reciprocal analyzer requires a rigorously proven prime input")

    integer_tags = {
        tag: _tagged_values(lines, tag)
        for tag in (
            "TERMINATING",
            "PERIOD",
            "PRIMITIVE",
            "GENERATED",
            "COMPLETE",
            "EXPORTED",
        )
    }
    if any(len(values) != 1 for values in integer_tags.values()):
        raise PrimeEngineError("PARI/GP returned an incomplete reciprocal analysis")
    digits_lines = [line[len("DIGITS:"):] for line in lines if line.startswith("DIGITS:")]
    if len(digits_lines) != 1 or not re.fullmatch(r"\d*", digits_lines[0]):
        raise PrimeEngineError("PARI/GP returned invalid reciprocal digits")

    terminating = integer_tags["TERMINATING"][0] == 1
    period = integer_tags["PERIOD"][0]
    primitive = integer_tags["PRIMITIVE"][0] == 1
    generated = integer_tags["GENERATED"][0]
    complete = integer_tags["COMPLETE"][0] == 1
    exported = integer_tags["EXPORTED"][0]
    digits = digits_lines[0]
    if generated != len(digits):
        raise PrimeEngineError("PARI/GP returned an inconsistent reciprocal digit count")
    expected_export = (1 if terminating else period) if export_path is not None else 0
    if exported != expected_export:
        raise PrimeEngineError("PARI/GP returned an incomplete reciprocal export")

    if terminating:
        note = "The decimal expansion terminates, so it has no repeating period."
        if not complete:
            note += " No decimal digits were requested."
    else:
        note = (
            "The period is the exact multiplicative order of 10 modulo p, computed by "
            "PARI/GP."
        )
        if not complete and digit_limit:
            note += f" The browser preview is limited to {digit_limit:,} digits."
        elif not complete:
            note += " No decimal digits were requested."
    if export_path is not None:
        note += " The complete finite expansion or repetend was streamed to the text report."
    return {
        "number": str(number),
        "digits": len(str(number)),
        "is_prime": True,
        "terminating": terminating,
        "period": str(period),
        "primitive_root_10": primitive,
        "full_reptend": primitive and not terminating,
        "decimal_digits": digits,
        "digits_generated": generated,
        "digits_complete": complete,
        "digit_limit": digit_limit,
        "exported_digits": str(exported),
        "export_complete": export_path is not None and exported == expected_export,
        "engine": "PARI/GP",
        "note": note,
    }


def _structure_program() -> str:
    try:
        return STRUCTURE_PROGRAM.read_text(encoding="utf-8")
    except OSError as exc:
        raise PrimeEngineError("The PARI/GP structural-prime program is unavailable") from exc


def absolute_primes_in_range(
    start: int, end: int, limit: int
) -> tuple[list[dict[str, object]], bool, int | None]:
    if start > end:
        raise ValueError("Range start must not exceed range end")
    lines = _run_gp(
        f"{_structure_program()}\nps_find_absolute_primes({start},{end},{limit});"
    )
    groups: list[dict[str, object]] = []
    for line in lines:
        if not line.startswith("ABSOLUTE:"):
            continue
        fields = line[len("ABSOLUTE:"):].split("|", 1)
        if len(fields) != 2 or not re.fullmatch(r"\d+", fields[0]):
            raise PrimeEngineError("PARI/GP returned an invalid absolute-prime group")
        rotations = re.findall(r"\d+", fields[1])
        if not rotations:
            raise PrimeEngineError("PARI/GP returned an empty absolute-prime orbit")
        groups.append({"representative": fields[0], "rotations": rotations})
    next_values = _tagged_values(lines, "NEXT")
    next_start = next_values[0] if next_values and next_values[0] else None
    return groups, next_start is not None, next_start


def analyze_gaussian_integer(real: int, imaginary: int) -> dict[str, object]:
    lines = _run_gp(
        f"{_structure_program()}\nps_analyze_gaussian({real},{imaginary});"
    )
    gaussian = _tagged_values(lines, "GAUSSIAN")
    norm = _tagged_values(lines, "NORM")
    norm_prime = _tagged_values(lines, "NORM_PRIME")
    if not (len(gaussian) == len(norm) == len(norm_prime) == 1):
        raise PrimeEngineError("PARI/GP returned an incomplete Gaussian-prime result")
    factors: list[dict[str, str]] = []
    for line in lines:
        if not line.startswith("FACTOR:"):
            continue
        fields = line[len("FACTOR:"):].split("|")
        if len(fields) != 2 or not all(re.fullmatch(r"-?\d+", item) for item in fields):
            raise PrimeEngineError("PARI/GP returned an invalid Gaussian factor")
        factors.append({"real": fields[0], "imaginary": fields[1]})
    return {
        "real": str(real),
        "imaginary": str(imaginary),
        "norm": str(norm[0]),
        "norm_is_rational_prime": norm_prime[0] == 1,
        "is_gaussian_prime": gaussian[0] == 1,
        "factors": factors,
        "engine": "PARI/GP",
        "note": "Applied the exact Gaussian-prime norm and axis criteria with rigorous rational primality tests.",
    }


def gaussian_primes_in_box(bound: int, limit: int) -> tuple[list[dict[str, str]], bool]:
    lines = _run_gp(
        f"{_structure_program()}\nps_find_gaussian_primes({bound},{limit});"
    )
    values: list[dict[str, str]] = []
    for line in lines:
        if not line.startswith("GAUSSIAN_POINT:"):
            continue
        fields = line[len("GAUSSIAN_POINT:"):].split("|")
        if len(fields) != 3 or not all(re.fullmatch(r"-?\d+", item) for item in fields):
            raise PrimeEngineError("PARI/GP returned an invalid Gaussian-prime point")
        values.append({"real": fields[0], "imaginary": fields[1], "norm": fields[2]})
    truncated_values = _tagged_values(lines, "TRUNCATED")
    if len(truncated_values) != 1:
        raise PrimeEngineError("PARI/GP did not return Gaussian-search completeness")
    return values, truncated_values[0] == 1


def modular_wheel_cells(modulus: int, maximum: int) -> list[dict[str, object]]:
    lines = _run_gp(f"{_structure_program()}\nps_modular_wheel({modulus},{maximum});")
    cells: list[dict[str, object]] = []
    for line in lines:
        if not line.startswith("CELL:"):
            continue
        fields = line[len("CELL:"):].split("|")
        if len(fields) != 5 or not all(re.fullmatch(r"\d+", item) for item in fields):
            raise PrimeEngineError("PARI/GP returned an invalid modular-wheel cell")
        cells.append(
            {
                "value": int(fields[0]),
                "residue": int(fields[1]),
                "ring": int(fields[2]),
                "is_prime": fields[3] == "1",
                "coprime": fields[4] == "1",
            }
        )
    if len(cells) != maximum + 1:
        raise PrimeEngineError("PARI/GP did not return every modular-wheel cell")
    return cells


def paterson_primes_in_range(
    start: int, end: int, limit: int
) -> tuple[list[dict[str, str]], bool, int | None]:
    if start > end:
        raise ValueError("Range start must not exceed range end")
    lines = _run_gp(
        f"{_structure_program()}\nps_find_paterson_primes({start},{end},{limit});"
    )
    values: list[dict[str, str]] = []
    for line in lines:
        if not line.startswith("PATERSON:"):
            continue
        fields = line[len("PATERSON:"):].split("|", 2)
        if len(fields) != 3 or not all(re.fullmatch(r"\d+", item) for item in fields[:2]):
            raise PrimeEngineError("PARI/GP returned an invalid Paterson-prime record")
        base4_digits = re.findall(r"\d+", fields[2])
        if not base4_digits:
            raise PrimeEngineError("PARI/GP returned an invalid base-4 representation")
        values.append(
            {
                "prime": fields[0],
                "base4": "".join(base4_digits),
                "decimal_companion": fields[1],
            }
        )
    next_values = _tagged_values(lines, "NEXT")
    next_start = next_values[0] if next_values and next_values[0] else None
    return values, next_start is not None, next_start


def generate_even_perfect_numbers(
    count: int, timeout_seconds: int = 0
) -> list[dict[str, str]]:
    lines = _run_gp(
        f"{_structure_program()}\nps_generate_even_perfect_numbers({count});",
        timeout=None if timeout_seconds == 0 else timeout_seconds,
    )
    values: list[dict[str, str]] = []
    for line in lines:
        if not line.startswith("PERFECT:"):
            continue
        fields = line[len("PERFECT:"):].split("|")
        if len(fields) != 3 or not all(re.fullmatch(r"\d+", item) for item in fields):
            raise PrimeEngineError("PARI/GP returned an invalid perfect-number record")
        values.append({"exponent": fields[0], "mersenne_prime": fields[1], "value": fields[2]})
    if len(values) != count:
        raise PrimeEngineError("PARI/GP did not return every requested perfect number")
    return values


def full_reptend_primes_in_range(
    start: int, end: int, limit: int
) -> tuple[list[dict[str, str]], bool, int | None]:
    if start > end:
        raise ValueError("Range start must not exceed range end")
    lines = _run_gp(
        f"{_structure_program()}\nps_find_full_reptend_primes({start},{end},{limit});"
    )
    values: list[dict[str, str]] = []
    for line in lines:
        if not line.startswith("REPTEND:"):
            continue
        fields = line[len("REPTEND:"):].split("|")
        if len(fields) != 2 or not all(re.fullmatch(r"\d+", item) for item in fields):
            raise PrimeEngineError("PARI/GP returned an invalid full-reptend prime")
        values.append({"prime": fields[0], "period": fields[1]})
    next_values = _tagged_values(lines, "NEXT")
    next_start = next_values[0] if next_values and next_values[0] else None
    return values, next_start is not None, next_start


def prime_insertion_pyramid(levels: int) -> list[dict[str, object]]:
    lines = _run_gp(f"{_structure_program()}\nps_prime_insertion_pyramid({levels});")
    values: list[dict[str, object]] = []
    for line in lines:
        if not line.startswith("INSERTION_LEVEL:"):
            continue
        fields = line[len("INSERTION_LEVEL:"):].split("|")
        if len(fields) != 3 or not all(re.fullmatch(r"\d+", item) for item in fields):
            raise PrimeEngineError("PARI/GP returned an invalid insertion-pyramid level")
        values.append({"level": int(fields[0]), "inserted_sum": int(fields[1]), "value": fields[2]})
    if len(values) != levels:
        raise PrimeEngineError("PARI/GP did not return every insertion-pyramid level")
    return values


def prime_multiplication_pyramid(rows: int) -> list[list[dict[str, object]]]:
    lines = _run_gp(f"{_structure_program()}\nps_prime_multiplication_pyramid({rows});")
    result: list[list[dict[str, object]]] = [[] for _ in range(rows)]
    for line in lines:
        if not line.startswith("PYRAMID_CELL:"):
            continue
        fields = line[len("PYRAMID_CELL:"):].split("|")
        if len(fields) != 4 or not all(re.fullmatch(r"\d+", item) for item in fields):
            raise PrimeEngineError("PARI/GP returned an invalid multiplication-pyramid cell")
        row, column, value, prime = map(int, fields)
        if row < 1 or row > rows or column < 1 or column > row:
            raise PrimeEngineError("PARI/GP returned an out-of-range pyramid cell")
        result[row - 1].append({"column": column, "value": str(value), "is_prime": prime == 1})
    if sum(map(len, result)) != rows * (rows + 1) // 2:
        raise PrimeEngineError("PARI/GP did not return every multiplication-pyramid cell")
    return result


SpecialNumberKind = Literal[
    "carmichael",
    "fermat_pseudoprime_base2",
    "strong_pseudoprime_bases2_3",
    "lucky_prime",
    "jacobsthal_prime",
]


def special_numbers_in_range(
    kind: SpecialNumberKind,
    start: int,
    end: int,
    limit: int,
    timeout_seconds: int = 0,
) -> tuple[list[dict[str, str]], bool, int | None]:
    if start > end:
        raise ValueError("Range start must not exceed range end")
    if end - start > 10_000_000:
        raise ValueError("A special-number search interval may span at most 10,000,000 integers")
    if kind == "lucky_prime" and end > 2_000_000:
        raise ValueError("The native lucky-number sieve supports upper endpoints through 2,000,000")
    gp_kind = json.dumps(kind)
    lines = _run_gp(
        f"{_structure_program()}\nps_find_special_numbers({gp_kind},{start},{end},{limit});",
        timeout=None if timeout_seconds == 0 else timeout_seconds,
    )
    values: list[dict[str, str]] = []
    for line in lines:
        if not line.startswith("SPECIAL:"):
            continue
        fields = line[len("SPECIAL:"):].split("|", 1)
        if len(fields) != 2 or not re.fullmatch(r"\d+", fields[0]):
            raise PrimeEngineError("PARI/GP returned an invalid special-number record")
        values.append({"value": fields[0], "detail": fields[1]})
    next_values = _tagged_values(lines, "NEXT")
    next_start = next_values[0] if next_values and next_values[0] else None
    return values, next_start is not None, next_start


def analyze_miller_rabin_witnesses(
    number: int, base: int, preview_limit: int = 1000
) -> dict[str, object]:
    if number < 5 or number % 2 == 0:
        raise ValueError("Miller–Rabin witness analysis requires an odd integer of at least 5")
    if base < 2 or base > number - 2:
        raise ValueError("The witness base must be between 2 and n−2")
    enumerate_all = number <= 1_000_000
    lines = _run_gp(
        f"{_structure_program()}\n"
        f"ps_analyze_miller_rabin({number},{base},{preview_limit},{1 if enumerate_all else 0});"
    )
    required = {
        tag: _tagged_values(lines, tag)
        for tag in ("MR_PRIME", "MR_S", "MR_D", "MR_BASE", "MR_GCD", "MR_PASSES", "MR_WITNESS")
    }
    if any(len(values) != 1 for values in required.values()):
        raise PrimeEngineError("PARI/GP returned an incomplete Miller–Rabin analysis")
    witnesses = _tagged_values(lines, "MR_WITNESS_BASE")
    passing = _tagged_values(lines, "MR_PASSING_BASE")
    result: dict[str, object] = {
        "number": str(number),
        "is_prime": required["MR_PRIME"][0] == 1,
        "s": str(required["MR_S"][0]),
        "d": str(required["MR_D"][0]),
        "base": str(required["MR_BASE"][0]),
        "gcd": str(required["MR_GCD"][0]),
        "passes": required["MR_PASSES"][0] == 1,
        "is_witness": required["MR_WITNESS"][0] == 1,
        "witnesses": [str(value) for value in witnesses],
        "passing_bases": [str(value) for value in passing],
        "distribution_complete": enumerate_all,
        "engine": "PARI/GP",
    }
    if enumerate_all:
        counts = {
            tag: _tagged_values(lines, tag)
            for tag in ("MR_WITNESS_COUNT", "MR_PASSING_COUNT", "MR_BASE_COUNT")
        }
        if any(len(values) != 1 for values in counts.values()):
            raise PrimeEngineError("PARI/GP returned an incomplete Miller–Rabin base distribution")
        result.update(
            witness_count=str(counts["MR_WITNESS_COUNT"][0]),
            passing_count=str(counts["MR_PASSING_COUNT"][0]),
            base_count=str(counts["MR_BASE_COUNT"][0]),
        )
    else:
        result.update(witness_count=None, passing_count=None, base_count=None)
    result["note"] = (
        "Applied the complete strong Miller–Rabin witness criterion. Exact all-base counts are included."
        if enumerate_all
        else "Applied the complete strong Miller–Rabin witness criterion to the selected base. All-base enumeration is limited to n ≤ 1,000,000."
    )
    return result


def prime_gap_statistics(start: int, end: int, limit: int) -> dict[str, object]:
    if start > end:
        raise ValueError("Range start must not exceed range end")
    lines = _run_gp(f"{_structure_program()}\nps_gap_statistics({start},{end},{limit});")
    count = _tagged_values(lines, "GAPSTAT_COUNT")
    truncated = _tagged_values(lines, "GAPSTAT_TRUNCATED")
    next_start = _tagged_values(lines, "GAPSTAT_NEXT")
    if not (len(count) == len(truncated) == len(next_start) == 1):
        raise PrimeEngineError("PARI/GP returned incomplete gap statistics")
    result: dict[str, object] = {
        "count": count[0],
        "truncated": truncated[0] == 1,
        "next_start": str(next_start[0]) if next_start[0] else None,
        "frequencies": [],
    }
    if count[0] == 0:
        return result
    for tag, key in (("GAPSTAT_MIN", "minimum"), ("GAPSTAT_MAX", "maximum")):
        value = _tagged_values(lines, tag)
        if len(value) != 1:
            raise PrimeEngineError("PARI/GP returned incomplete gap statistics")
        result[key] = str(value[0])
    for tag, key in (("GAPSTAT_MEAN", "mean"), ("GAPSTAT_MEDIAN", "median")):
        value = _single_pipe_record(lines, tag, 2)
        numerator, denominator = map(int, value)
        result[key] = {
            "numerator": str(numerator),
            "denominator": str(denominator),
        }
    mode = _single_pipe_record(lines, "GAPSTAT_MODE", 2)
    result["mode"] = {"gap": mode[0], "frequency": int(mode[1])}
    frequencies: list[dict[str, object]] = []
    for line in lines:
        if line.startswith("GAPSTAT_FREQ:"):
            gap, frequency = line[len("GAPSTAT_FREQ:"):].split("|", 1)
            frequencies.append({"gap": gap, "frequency": int(frequency)})
    result["frequencies"] = frequencies
    return result


def _single_pipe_record(lines: list[str], tag: str, count: int) -> list[str]:
    prefix = f"{tag}:"
    values = [line[len(prefix):].split("|") for line in lines if line.startswith(prefix)]
    if len(values) != 1 or len(values[0]) != count or not all(
        re.fullmatch(r"-?\d+", item) for item in values[0]
    ):
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} record")
    return values[0]


def generate_primorials(count: int) -> list[dict[str, str]]:
    lines = _run_gp(f"{_structure_program()}\nps_generate_primorials({count});")
    values: list[dict[str, str]] = []
    for line in lines:
        if line.startswith("PRIMORIAL:"):
            index, prime, value = line[len("PRIMORIAL:"):].split("|", 2)
            if not all(re.fullmatch(r"\d+", item) for item in (index, prime, value)):
                raise PrimeEngineError("PARI/GP returned an invalid primorial")
            values.append({"index": index, "prime": prime, "value": value})
    if len(values) != count:
        raise PrimeEngineError("PARI/GP did not return every primorial")
    return values


def prime_square_sum_solutions(bound: int, limit: int) -> tuple[list[dict[str, str]], bool]:
    lines = _run_gp(f"{_structure_program()}\nps_problem_prime_square_sums({bound},{limit});")
    values = _parse_three_field_records(lines, "PROBLEM_SQUARE_SUM", ("p", "q", "r"))
    return values, _truncated(lines)


def quartan_primes_in_range(bound: int, limit: int) -> tuple[list[dict[str, str]], bool]:
    lines = _run_gp(f"{_structure_program()}\nps_problem_quartan_primes({bound},{limit});")
    values = _parse_three_field_records(lines, "PROBLEM_QUARTAN", ("prime", "a", "b"))
    return values, _truncated(lines)


def integers_with_three_prime_factors(
    start: int, end: int, limit: int
) -> tuple[list[dict[str, str]], bool]:
    if start > end:
        raise ValueError("Range start must not exceed range end")
    if end - start > 1_000_000:
        raise ValueError("This factor search may span at most 1,000,000 integers")
    lines = _run_gp(
        f"{_structure_program()}\nps_problem_three_prime_factors({start},{end},{limit});"
    )
    values: list[dict[str, str]] = []
    for line in lines:
        if line.startswith("PROBLEM_THREE_FACTORS:"):
            fields = line[len("PROBLEM_THREE_FACTORS:"):].split("|", 3)
            if len(fields) != 4 or not all(re.fullmatch(r"\d+", item) for item in fields[:3]):
                raise PrimeEngineError("PARI/GP returned an invalid factor-search record")
            values.append({"n": fields[0], "value": fields[1], "factorization": fields[3]})
    return values, _truncated(lines)


def sigma_fourth_power_square_primes(
    prime_candidates: int, limit: int
) -> tuple[list[dict[str, str]], bool]:
    lines = _run_gp(
        f"{_structure_program()}\nps_problem_sigma_square({prime_candidates},{limit});"
    )
    values: list[dict[str, str]] = []
    for line in lines:
        if line.startswith("PROBLEM_SIGMA_SQUARE:"):
            fields = line[len("PROBLEM_SIGMA_SQUARE:"):].split("|")
            if len(fields) != 4 or not all(re.fullmatch(r"\d+", item) for item in fields):
                raise PrimeEngineError("PARI/GP returned an invalid divisor-sum record")
            values.append({"prime": fields[0], "sigma": fields[1], "root": fields[2], "index": fields[3]})
    return values, _truncated(lines)


def contiguous_digit_primes(number: int) -> list[int]:
    if len(str(abs(number))) > 1_000:
        raise ValueError("Contiguous-digit analysis supports inputs through 1,000 decimal digits")
    lines = _run_gp(f"{_structure_program()}\nps_contiguous_digit_primes({number});")
    return _tagged_values(lines, "DIGIT_PRIME")


def random_primes_in_range(start: int, end: int, count: int) -> list[int]:
    if start > end:
        raise ValueError("Range start must not exceed range end")
    lines = _run_gp(
        f"{_structure_program()}\nps_random_primes_in_range({start},{end},{count});"
    )
    values = _tagged_values(lines, "RANDOM_PRIME")
    found = _tagged_values(lines, "FOUND")
    if len(found) != 1 or found[0] != count:
        raise PrimeEngineError(
            f"Found {len(values)} of {count} distinct primes; widen the range or request fewer"
        )
    return values


def goldbach_partitions(number: int, limit: int) -> tuple[list[dict[str, str]], bool]:
    if number <= 2 or number % 2:
        raise ValueError("Goldbach analysis requires an even integer greater than 2")
    lines = _run_gp(f"{_structure_program()}\nps_goldbach_partitions({number},{limit});")
    values: list[dict[str, str]] = []
    for line in lines:
        if line.startswith("GOLDBACH:"):
            left, right = line[len("GOLDBACH:"):].split("|", 1)
            if not re.fullmatch(r"\d+", left) or not re.fullmatch(r"\d+", right):
                raise PrimeEngineError("PARI/GP returned an invalid Goldbach partition")
            values.append({"left": left, "right": right})
    return values, _truncated(lines)


def integer_arithmetic_profile(number: int, divisor_limit: int = 1_000) -> dict[str, object]:
    if number == 0:
        raise ValueError("The arithmetic profile requires a nonzero integer")
    if not 0 <= divisor_limit <= 100_000:
        raise ValueError("The divisor preview limit must be between 0 and 100,000")
    lines = _run_gp(f"{_structure_program()}\nps_integer_profile({number},{divisor_limit});")
    integer_tags = {
        tag: _tagged_values(lines, tag)
        for tag in (
            "PROFILE_NUMBER",
            "PROFILE_ABSOLUTE",
            "PROFILE_PRIME",
            "PROFILE_SEMIPRIME",
            "PROFILE_OMEGA",
            "PROFILE_BIGOMEGA",
            "PROFILE_TAU",
            "PROFILE_SIGMA",
            "PROFILE_ALIQUOT",
            "PROFILE_PHI",
            "PROFILE_LAMBDA",
            "PROFILE_MOBIUS",
            "PROFILE_RADICAL",
            "PROFILE_DIVISORS_SHOWN",
        )
    }
    if any(len(values) != 1 for values in integer_tags.values()):
        raise PrimeEngineError("PARI/GP returned an incomplete arithmetic profile")
    factors: list[dict[str, str]] = []
    for line in lines:
        if line.startswith("PROFILE_FACTOR:"):
            fields = line[len("PROFILE_FACTOR:"):].split("|")
            if len(fields) != 2 or not all(re.fullmatch(r"\d+", field) for field in fields):
                raise PrimeEngineError("PARI/GP returned an invalid factor record")
            factors.append({"prime": fields[0], "exponent": fields[1]})
    divisors = _tagged_values(lines, "PROFILE_DIVISOR")
    classes = [line[len("PROFILE_CLASS:"):] for line in lines if line.startswith("PROFILE_CLASS:")]
    if len(classes) != 1 or classes[0] not in {"unit", "deficient", "perfect", "abundant"}:
        raise PrimeEngineError("PARI/GP returned an invalid divisor classification")
    tau = integer_tags["PROFILE_TAU"][0]
    return {
        "number": str(integer_tags["PROFILE_NUMBER"][0]),
        "absolute": str(integer_tags["PROFILE_ABSOLUTE"][0]),
        "is_prime": integer_tags["PROFILE_PRIME"][0] == 1,
        "is_semiprime": integer_tags["PROFILE_SEMIPRIME"][0] == 1,
        "omega": str(integer_tags["PROFILE_OMEGA"][0]),
        "big_omega": str(integer_tags["PROFILE_BIGOMEGA"][0]),
        "divisor_count": str(tau),
        "divisor_sum": str(integer_tags["PROFILE_SIGMA"][0]),
        "aliquot_sum": str(integer_tags["PROFILE_ALIQUOT"][0]),
        "totient": str(integer_tags["PROFILE_PHI"][0]),
        "carmichael": str(integer_tags["PROFILE_LAMBDA"][0]),
        "mobius": str(integer_tags["PROFILE_MOBIUS"][0]),
        "radical": str(integer_tags["PROFILE_RADICAL"][0]),
        "divisor_class": classes[0],
        "factors": factors,
        "divisors": [str(value) for value in divisors],
        "divisors_complete": len(divisors) == tau,
        "engine": "PARI/GP",
        "note": "PARI/GP factored the integer and evaluated every arithmetic function exactly.",
    }


def coprime_profile(
    modulus: int, start: int, count: int, residue_limit: int = 1_000
) -> dict[str, object]:
    if modulus < 2:
        raise ValueError("The coprime modulus must be at least 2")
    lines = _run_gp(
        f"{_structure_program()}\nps_coprime_profile({modulus},{start},{count},{residue_limit});"
    )
    phi = _tagged_values(lines, "COPRIME_PHI")
    shown = _tagged_values(lines, "COPRIME_RESIDUES_SHOWN")
    after = _tagged_values(lines, "COPRIME_AFTER")
    residues = _tagged_values(lines, "COPRIME_RESIDUE")
    if len(phi) != 1 or len(shown) != 1 or len(after) != count or shown[0] != len(residues):
        raise PrimeEngineError("PARI/GP returned an incomplete coprime profile")
    return {
        "modulus": str(modulus),
        "start": str(start),
        "totient": str(phi[0]),
        "after": [str(value) for value in after],
        "residues": [str(value) for value in residues],
        "residues_complete": len(residues) == phi[0],
        "engine": "PARI/GP",
        "note": "PARI/GP computed Euler's totient and every displayed gcd exactly.",
    }


def prime_distribution(
    start: int, end: int, bins: int, modulus: int
) -> dict[str, object]:
    if start > end:
        raise ValueError("Range start must not exceed range end")
    if end - start > 10_000_000:
        raise ValueError("A distribution scan may span at most 10,000,000 integers")
    lines = _run_gp(
        f"{_structure_program()}\nps_prime_distribution({start},{end},{bins},{modulus});"
    )
    required = {
        tag: _tagged_values(lines, tag)
        for tag in (
            "DISTRIBUTION_COUNT",
            "DISTRIBUTION_TWINS",
            "DISTRIBUTION_MAX_GAP",
            "DISTRIBUTION_MAX_GAP_AT",
        )
    }
    if any(len(values) != 1 for values in required.values()):
        raise PrimeEngineError("PARI/GP returned incomplete prime-distribution statistics")
    bin_values = _parse_pipe_records(
        lines, "DISTRIBUTION_BIN", ("start", "end", "count"), signed_fields=2
    )
    residue_values = _parse_pipe_records(
        lines, "DISTRIBUTION_RESIDUE", ("residue", "count")
    )
    if len(bin_values) != bins or len(residue_values) != modulus:
        raise PrimeEngineError("PARI/GP returned an incomplete distribution table")
    return {
        "start": str(start),
        "end": str(end),
        "count": required["DISTRIBUTION_COUNT"][0],
        "twin_count": required["DISTRIBUTION_TWINS"][0],
        "maximum_gap": str(required["DISTRIBUTION_MAX_GAP"][0]),
        "maximum_gap_at": str(required["DISTRIBUTION_MAX_GAP_AT"][0]),
        "bins": bin_values,
        "modulus": modulus,
        "residues": residue_values,
        "engine": "PARI/GP",
        "note": "PARI/GP enumerated proven primes once and computed exact bin, residue, twin, and gap statistics.",
    }


def factor_count_distribution(start: int, end: int) -> dict[str, object]:
    if start < 1 or start > end:
        raise ValueError("The factor-count distribution requires 1 ≤ start ≤ end")
    if end - start > 1_000_000:
        raise ValueError("A factor-count scan may span at most 1,000,000 integers")
    lines = _run_gp(
        f"{_structure_program()}\nps_factor_count_distribution({start},{end});",
        timeout=None,
    )
    totals = _tagged_values(lines, "FACTOR_DISTRIBUTION_TOTAL")
    values = _parse_pipe_records(
        lines,
        "FACTOR_DISTRIBUTION",
        ("factor_count", "distinct_count", "multiplicity_count"),
    )
    if len(totals) != 1 or sum(int(item["distinct_count"]) for item in values) != totals[0]:
        raise PrimeEngineError("PARI/GP returned an incomplete factor-count distribution")
    if sum(int(item["multiplicity_count"]) for item in values) != totals[0]:
        raise PrimeEngineError("PARI/GP returned an incomplete multiplicity distribution")
    return {
        "start": str(start),
        "end": str(end),
        "total": totals[0],
        "distribution": values,
        "engine": "PARI/GP",
        "note": "PARI/GP factored every integer and counted exact ω(n) and Ω(n) frequencies.",
    }


def digit_constrained_primes(
    allowed_digits: str,
    minimum_digits: int,
    maximum_digits: int,
    limit: int,
    candidate_limit: int = 2_000_000,
) -> dict[str, object]:
    if not re.fullmatch(r"[0-9]+", allowed_digits):
        raise ValueError("Allowed digits must contain only decimal digits")
    allowed = sorted({int(digit) for digit in allowed_digits})
    if not any(allowed):
        raise ValueError("At least one nonzero digit is required")
    if minimum_digits > maximum_digits:
        raise ValueError("Minimum digits must not exceed maximum digits")
    gp_allowed = "[" + ",".join(map(str, allowed)) + "]"
    lines = _run_gp(
        f"{_structure_program()}\nps_digit_constrained_primes("
        f"{gp_allowed},{minimum_digits},{maximum_digits},{limit},{candidate_limit});"
    )
    values = _tagged_values(lines, "CONSTRAINED_PRIME")
    candidates = _tagged_values(lines, "CONSTRAINED_CANDIDATES")
    truncated = _tagged_values(lines, "CONSTRAINED_TRUNCATED")
    candidate_limited = _tagged_values(lines, "CONSTRAINED_CANDIDATE_LIMITED")
    if not (len(candidates) == len(truncated) == len(candidate_limited) == 1):
        raise PrimeEngineError("PARI/GP returned incomplete constrained-digit search status")
    return {
        "allowed_digits": "".join(map(str, allowed)),
        "minimum_digits": minimum_digits,
        "maximum_digits": maximum_digits,
        "count": len(values),
        "primes": [str(value) for value in values],
        "candidates_tested": candidates[0],
        "truncated": truncated[0] == 1,
        "candidate_limited": candidate_limited[0] == 1,
        "engine": "PARI/GP",
        "note": "PARI/GP generated only numbers from the selected digit alphabet and rigorously tested each candidate.",
    }


def prime_polynomial_analysis(
    k: int, start: int, end: int, limit: int, obstruction_bound: int
) -> dict[str, object]:
    if start > end:
        raise ValueError("Range start must not exceed range end")
    if end - start > 1_000_000:
        raise ValueError("A polynomial scan may span at most 1,000,000 indices")
    lines = _run_gp(
        f"{_structure_program()}\nps_prime_polynomial("
        f"{k},{start},{end},{limit},{obstruction_bound});"
    )
    values = _parse_pipe_records(lines, "POLYNOMIAL_PRIME", ("n", "value"), signed_fields=2)
    required = {
        tag: _tagged_values(lines, tag)
        for tag in (
            "POLYNOMIAL_TOTAL",
            "POLYNOMIAL_TRUNCATED",
            "POLYNOMIAL_LONGEST",
            "POLYNOMIAL_LONGEST_START",
        )
    }
    if any(len(items) != 1 for items in required.values()):
        raise PrimeEngineError("PARI/GP returned incomplete polynomial statistics")
    obstructions: list[dict[str, object]] = []
    for line in lines:
        if not line.startswith("POLYNOMIAL_ROOTS:"):
            continue
        prime_text, roots_text = line[len("POLYNOMIAL_ROOTS:"):].split("|", 1)
        roots = re.findall(r"\d+", roots_text)
        if not re.fullmatch(r"\d+", prime_text) or not roots:
            raise PrimeEngineError("PARI/GP returned invalid polynomial modular roots")
        obstructions.append({"prime": prime_text, "residues": roots})
    return {
        "k": str(k),
        "start": str(start),
        "end": str(end),
        "count": required["POLYNOMIAL_TOTAL"][0],
        "values": values,
        "truncated": required["POLYNOMIAL_TRUNCATED"][0] == 1,
        "longest_run": required["POLYNOMIAL_LONGEST"][0],
        "longest_run_start": str(required["POLYNOMIAL_LONGEST_START"][0]),
        "obstructions": obstructions,
        "engine": "PARI/GP",
        "note": "PARI/GP evaluated n²−n+k exactly, rigorously proved prime values, and found exact modular divisibility classes.",
    }


def palindrome_derived_primes(
    start: int, end: int, limit: int
) -> dict[str, object]:
    if start < 1 or start > end:
        raise ValueError("The sequence requires 1 ≤ start ≤ end")
    if end - start > 10_000_000:
        raise ValueError("A palindrome-derived scan may span at most 10,000,000 integers")
    lines = _run_gp(
        f"{_structure_program()}\nps_palindrome_derived_primes({start},{end},{limit});"
    )
    values = _parse_pipe_records(
        lines, "PALINDROME_DERIVED", ("n", "reverse", "prime")
    )
    totals = _tagged_values(lines, "PALINDROME_TOTAL")
    truncated = _tagged_values(lines, "PALINDROME_TRUNCATED")
    if len(totals) != 1 or len(truncated) != 1:
        raise PrimeEngineError("PARI/GP returned incomplete palindrome-derived statistics")
    return {
        "start": str(start),
        "end": str(end),
        "count": totals[0],
        "values": values,
        "truncated": truncated[0] == 1,
        "engine": "PARI/GP",
        "note": "PARI/GP reversed each decimal integer exactly and rigorously tested |n−reverse(n)|+1.",
    }


def prime_indicator_constant(decimal_digits: int) -> dict[str, object]:
    lines = _run_gp(
        f"{_structure_program()}\nps_prime_indicator_constant({decimal_digits});",
        timeout=None,
    )
    values = [line[len("PRIME_CONSTANT:"):] for line in lines if line.startswith("PRIME_CONSTANT:")]
    terms = _tagged_values(lines, "PRIME_CONSTANT_TERMS")
    error_power = _tagged_values(lines, "PRIME_CONSTANT_ERROR_POWER")
    if (
        len(values) != 1
        or not re.fullmatch(r"0\.\d+", values[0])
        or len(terms) != 1
        or len(error_power) != 1
    ):
        raise PrimeEngineError("PARI/GP returned an invalid prime-indicator constant")
    return {
        "value": values[0],
        "decimal_digits": decimal_digits,
        "terms": terms[0],
        "error_bound": f"2^-{error_power[0]}",
        "engine": "PARI/GP",
        "note": "PARI/GP rigorously tested every encoded index; matching rounded lower and upper tail bounds certify the displayed decimal.",
    }


def _parse_three_field_records(
    lines: list[str], tag: str, keys: tuple[str, str, str]
) -> list[dict[str, str]]:
    prefix = f"{tag}:"
    result: list[dict[str, str]] = []
    for line in lines:
        if line.startswith(prefix):
            fields = line[len(prefix):].split("|")
            if len(fields) != 3 or not all(re.fullmatch(r"\d+", item) for item in fields):
                raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} record")
            result.append(dict(zip(keys, fields, strict=True)))
    return result


def _parse_pipe_records(
    lines: list[str],
    tag: str,
    keys: tuple[str, ...],
    *,
    signed_fields: int = 0,
) -> list[dict[str, str]]:
    prefix = f"{tag}:"
    result: list[dict[str, str]] = []
    for line in lines:
        if not line.startswith(prefix):
            continue
        fields = line[len(prefix):].split("|")
        if len(fields) != len(keys):
            raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} record")
        for index, field in enumerate(fields):
            pattern = r"-?\d+" if index < signed_fields else r"\d+"
            if not re.fullmatch(pattern, field):
                raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} record")
        result.append(dict(zip(keys, fields, strict=True)))
    return result


def _truncated(lines: list[str]) -> bool:
    values = _tagged_values(lines, "TRUNCATED")
    if len(values) != 1:
        raise PrimeEngineError("PARI/GP did not return search completeness")
    return values[0] == 1


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


def nth_prime_near(start: int, index: int, direction: Literal["after", "before"]) -> int:
    """Count proven primes strictly from start in GP, returning only the last one."""
    if not 1 <= index <= 100_000:
        raise ValueError("Relative prime index must be between 1 and 100,000")
    if direction not in ("after", "before"):
        raise ValueError("Direction must be after or before")
    if direction == "after":
        walk = (
            f"p=max(2,{start}+1);while(c<{index},p=nextprime(p);"
            "if(isprime(p),v=p;c++);p++)"
        )
    else:
        walk = (
            f"p={start}-1;while(c<{index}&&p>=2,p=precprime(p);"
            "if(p>=2&&isprime(p),v=p;c++);p--)"
        )
    lines = _run_gp(f'c=0;v=0;{walk};print("FOUND:",c);print("RESULT:",v)')
    found = _tagged_values(lines, "FOUND")
    values = _tagged_values(lines, "RESULT")
    if len(found) != 1 or len(values) != 1 or not 0 <= found[0] <= index:
        raise PrimeEngineError("PARI/GP returned an incomplete relative-prime result")
    if found[0] < index:
        if direction == "before":
            raise ValueError(
                f"The requested prime does not exist: only {found[0]} primes are strictly before {start}"
            )
        raise PrimeEngineError("PARI/GP did not finish the requested prime search")
    value = values[0]
    if value < 2 or (direction == "after" and value <= start) or (direction == "before" and value >= start):
        raise PrimeEngineError("PARI/GP returned an invalid relative-prime result")
    return value


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
