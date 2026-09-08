"""Typed orchestration boundary for the native PARI/GP workbenches."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

from .prime_manipulation import decimal_integer
from .primes import PrimeEngineError, _run_gp, _tagged_values, prime_count

PROGRAM = Path(__file__).with_name("number_theory.gp")
_SAFE_TEXT = re.compile(r"[0-9A-Za-z_+*/^()., \[\]~-]+")
_SPECIAL_FAMILY_CODES = {
    "mersenne": 0,
    "fermat": 1,
    "cullen": 2,
    "woodall": 3,
    "wagstaff": 4,
    "repunit": 5,
    "primorial": 6,
    "factorial": 7,
}


def _program() -> str:
    try:
        return PROGRAM.read_text(encoding="utf-8")
    except OSError as exc:
        raise PrimeEngineError("The advanced PARI/GP program is unavailable") from exc


def _execute(call: str, timeout: int = 60) -> list[str]:
    if not 1 <= timeout <= 3600:
        raise ValueError("Engine time limit must be between 1 and 3,600 seconds")
    lines = _run_gp(f"{_program()}\n{call};", timeout=timeout)
    if not _tagged_values(lines, "DONE"):
        raise PrimeEngineError("PARI/GP returned an incomplete advanced-workbench result")
    return lines


def _one(lines: list[str], tag: str) -> int:
    values = _tagged_values(lines, tag)
    if len(values) != 1:
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} result")
    return values[0]


def _optional(lines: list[str], tag: str) -> int | None:
    values = _tagged_values(lines, tag)
    if len(values) > 1:
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} result")
    return values[0] if values else None


def _records(lines: Iterable[str], tag: str, width: int) -> list[list[str]]:
    prefix = f"{tag}:"
    rows = [line[len(prefix):].split("|") for line in lines if line.startswith(prefix)]
    if any(len(row) != width or any(not _SAFE_TEXT.fullmatch(value) for value in row) for row in rows):
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} record")
    return rows


def character_symbols(a: str, n: str, timeout: int = 60) -> dict:
    left, right = decimal_integer(a), decimal_integer(n)
    lines = _execute(f"nt_symbols({left},{right})", timeout)
    jacobi = _optional(lines, "JACOBI")
    legendre = _optional(lines, "LEGENDRE")
    return {
        "metrics": {
            "a": str(left),
            "n": str(right),
            "a normalized modulo |n|": str(_one(lines, "NORMALIZED")),
            "Kronecker (a/n)": str(_one(lines, "KRONECKER")),
            "Jacobi (a/n)": "not applicable" if jacobi is None else str(jacobi),
            "Legendre (a/n)": "not applicable" if legendre is None else str(legendre),
        },
        "columns": ["Symbol", "Value"],
        "rows": [
            ["Kronecker", str(_one(lines, "KRONECKER"))],
            ["Jacobi", "not applicable" if jacobi is None else str(jacobi)],
            ["Legendre", "not applicable" if legendre is None else str(legendre)],
        ],
        "note": "PARI/GP evaluated the symbols exactly. Legendre requires an odd prime denominator; Jacobi requires a positive odd denominator.",
    }


def chinese_remainder(residues: list[str], moduli: list[str], timeout: int = 60) -> dict:
    if not 1 <= len(residues) <= 256 or len(residues) != len(moduli):
        raise ValueError("Supply 1–256 residue/modulus pairs")
    a = [decimal_integer(value) for value in residues]
    m = [decimal_integer(value) for value in moduli]
    if any(value <= 0 for value in m):
        raise ValueError("CRT moduli must be positive")
    av, mv = "[" + ",".join(map(str, a)) + "]", "[" + ",".join(map(str, m)) + "]"
    lines = _execute(f"nt_crt({av},{mv})", timeout)
    compatible = _one(lines, "COMPATIBLE") == 1
    result = _optional(lines, "RESULT")
    combined = _optional(lines, "MODULUS")
    if compatible != (result is not None and combined is not None):
        raise PrimeEngineError("PARI/GP returned an inconsistent CRT result")
    return {
        "compatible": compatible,
        "metrics": {
            "Equations": str(len(a)),
            "Compatible": "yes" if compatible else "no",
            "Least nonnegative solution": str(result) if compatible else "none",
            "Combined modulus": str(combined) if compatible else "none",
        },
        "columns": ["Residue", "Modulus"],
        "rows": [[str(x % y), str(y)] for x, y in zip(a, m, strict=True)],
        "note": (
            "The exact generalized CRT solution includes non-coprime moduli."
            if compatible
            else "The congruences are incompatible; no integer satisfies all equations."
        ),
    }


def modular_roots(a: str, exponent: int, modulus: str, limit: int, timeout: int = 60) -> dict:
    value, prime = decimal_integer(a), decimal_integer(modulus)
    if not 1 <= exponent <= 1_000_000 or not 1 <= limit <= 100_000:
        raise ValueError("Require exponent 1–1,000,000 and result limit 1–100,000")
    lines = _execute(f"nt_modular_roots({value},{exponent},{prime},{limit})", timeout)
    roots = _tagged_values(lines, "ROOT")
    count = _one(lines, "ROOT_COUNT")
    truncated = _one(lines, "TRUNCATED") == 1
    if len(roots) != min(count, limit):
        raise PrimeEngineError("PARI/GP returned an incomplete modular-root list")
    return {
        "metrics": {"Prime modulus": str(prime), "Exponent": str(exponent), "Root count": str(count)},
        "columns": [f"x satisfying x^{exponent} ≡ {value} (mod {prime})"],
        "rows": [[str(root)] for root in roots],
        "truncated": truncated,
        "note": "PARI/GP solved the power congruence exactly over the prime field.",
    }


def discrete_logarithm(target: str, base: str, modulus: str, timeout: int = 60) -> dict:
    a, g, n = map(decimal_integer, (target, base, modulus))
    lines = _execute(f"nt_discrete_log({a},{g},{n})", timeout)
    solvable = _one(lines, "SOLVABLE") == 1
    value = _optional(lines, "LOG")
    if solvable != (value is not None):
        raise PrimeEngineError("PARI/GP returned an inconsistent discrete logarithm")
    return {
        "metrics": {
            "Modulus": str(n), "Base": str(g % n), "Target": str(a % n),
            "Base order": str(_one(lines, "ORDER")),
            "Least logarithm": str(value) if solvable else "no solution in generated subgroup",
        },
        "columns": ["Equation", "Result"],
        "rows": [[f"{g}^x ≡ {a} (mod {n})", str(value) if solvable else "no solution"]],
        "note": "PARI/GP selects Pohlig–Hellman, baby-step/giant-step, Pollard rho, or index calculus according to the group and factorization of its order.",
    }


def unit_group(modulus: str, limit: int, timeout: int = 60) -> dict:
    n = decimal_integer(modulus)
    if not 1 <= limit <= 100_000:
        raise ValueError("Result limit must be between 1 and 100,000")
    lines = _execute(f"nt_unit_group({n},{limit})", timeout)
    factors = _tagged_values(lines, "CYCLIC_FACTOR")
    generators = _tagged_values(lines, "GENERATOR")
    roots = _tagged_values(lines, "PRIMITIVE")
    cyclic = _one(lines, "CYCLIC") == 1
    return {
        "metrics": {
            "Modulus": str(n), "Group order φ(n)": str(_one(lines, "ORDER")),
            "Cyclic": "yes" if cyclic else "no",
            "Invariant factors": " × ".join(f"C{v}" for v in factors) or "trivial",
            "Primitive-root count": str(_one(lines, "PRIMITIVE_COUNT")),
        },
        "columns": ["Component generator"],
        "rows": [[str(v)] for v in generators] + [[f"primitive root: {v}"] for v in roots],
        "truncated": _one(lines, "ENUMERATION_COMPLETE") == 0,
        "note": "PARI/GP computed the exact invariant-factor decomposition of (ℤ/nℤ)×. Primitive roots exist exactly when this group is cyclic.",
    }


def factor_polynomial(coefficients: list[str], prime_modulus: str, timeout: int = 60) -> dict:
    if not 2 <= len(coefficients) <= 101:
        raise ValueError("Supply 2–101 coefficients in ascending order")
    coeffs = [decimal_integer(value) for value in coefficients]
    if coeffs[-1] == 0:
        raise ValueError("The leading coefficient must be nonzero")
    p = decimal_integer(prime_modulus)
    vector = "[" + ",".join(map(str, coeffs)) + "]"
    lines = _execute(f"nt_polynomial({vector},{p})", timeout)
    polynomial = [line[11:] for line in lines if line.startswith("POLYNOMIAL:")]
    if len(polynomial) != 1 or not _SAFE_TEXT.fullmatch(polynomial[0]):
        raise PrimeEngineError("PARI/GP returned an invalid polynomial")
    rational = _records(lines, "QFACTOR", 2)
    finite = _records(lines, "FFFACTOR", 2)
    roots = _tagged_values(lines, "ROOT")
    return {
        "metrics": {"Polynomial": polynomial[0], "Prime modulus": str(p)},
        "columns": ["Domain", "Factor", "Exponent"],
        "rows": [["ℚ", *row] for row in rational] + [[f"𝔽_{p}", *row] for row in finite],
        "roots": [str(root) for root in roots],
        "note": f"PARI/GP factored the polynomial over ℚ and 𝔽_{p}; roots modulo {p}: " + (", ".join(map(str, roots)) or "none"),
    }


def arithmetic_functions(n: str, k: int, bound: str, form_d: int,
                         divisor_limit: int, timeout: int = 60) -> dict:
    value, smooth = decimal_integer(n), decimal_integer(bound)
    if not 0 <= k <= 1_000 or not 1 <= form_d <= 1_000_000:
        raise ValueError("Require 0 ≤ k ≤ 1,000 and 1 ≤ d ≤ 1,000,000")
    if not 0 <= divisor_limit <= 100_000:
        raise ValueError("Divisor preview limit must be between 0 and 100,000")
    lines = _execute(f"nt_arithmetic({value},{k},{smooth},{form_d},{divisor_limit})", timeout)
    factors = _records(lines, "FACTOR", 2)
    divisors = _tagged_values(lines, "DIVISOR")
    form_rep = _records(lines, "FORM_REP", 2)
    difference = _records(lines, "DIFFERENCE_REP", 2)
    mangoldt = _one(lines, "VON_MANGOLDT_BASE")
    metrics = {
        "Integer": str(value), "Factorization": " × ".join(
            f"{p}^{e}" if e != "1" else p for p, e in factors
        ) or "1",
        f"Generalized divisor sum σ_{k}": str(_one(lines, "SIGMA_K")),
        f"Jordan totient J_{k}": str(_one(lines, "JORDAN")),
        "Dedekind ψ": str(_one(lines, "DEDEKIND_PSI")),
        "Liouville λ": str(_one(lines, "LIOUVILLE")),
        "Von Mangoldt Λ": "0" if mangoldt == 0 else f"log({mangoldt})",
        "Radical": str(_one(lines, "RADICAL")),
        "Squarefree kernel": str(_one(lines, "SQUAREFREE_KERNEL")),
        "Least prime factor": str(_one(lines, "LEAST_PRIME_FACTOR")),
        "Largest prime factor": str(_one(lines, "LARGEST_PRIME_FACTOR")),
        f"{smooth}-smooth": "yes" if _one(lines, "B_SMOOTH") else "no",
        f"{smooth}-powersmooth": "yes" if _one(lines, "B_POWER_SMOOTH") else "no",
        "Ordered two-square representations": str(_one(lines, "SUM_TWO_SQUARE_COUNT")),
        "Ordered four-square representations": str(_one(lines, "SUM_FOUR_SQUARE_COUNT")),
        f"x² + {form_d}y² representation": "none" if not form_rep else f"{form_rep[0][0]}, {form_rep[0][1]}",
        "Difference of squares": "none" if not difference else f"{difference[0][0]}² − {difference[0][1]}²",
    }
    return {
        "metrics": metrics,
        "columns": ["Divisor preview"], "rows": [[str(v)] for v in divisors],
        "truncated": _one(lines, "DIVISORS_COMPLETE") == 0,
        "note": "PARI/GP factored |n| and derived every arithmetic function, smoothness result, and representation exactly.",
    }


def primality_laboratory(n: str, base: str, proof_mode: int, timeout: int = 60) -> dict:
    value, witness = decimal_integer(n), decimal_integer(base)
    if proof_mode not in {0, 1, 2, 3}:
        raise ValueError("Proof mode must select automatic, N−1, APR-CL, or ECPP")
    lines = _execute(f"nt_primality_lab({value},{witness},{proof_mode})", timeout)
    labels = [
        ("Fermat probable-prime test", "FERMAT", False),
        ("Euler–Jacobi test", "EULER_JACOBI", False),
        ("Strong Miller–Rabin test", "MILLER_RABIN", False),
        ("Baillie–PSW test", "BPSW", False),
        (("Automatic proof", "N−1 proof", "APR-CL proof", "ECPP proof")[proof_mode], "PROVEN", True),
    ]
    rows = [[label, "pass" if _one(lines, tag) else "fail", "rigorous" if rigorous else "probable/compositeness"] for label, tag, rigorous in labels]
    proven = _one(lines, "PROVEN") == 1
    return {
        "metrics": {"Integer": str(value), "Selected base": str(witness), "Rigorous verdict": "prime" if proven else "composite"},
        "columns": ["Test", "Outcome", "Meaning"], "rows": rows,
        "note": "PARI/GP ran each native test independently. Probable-prime passes are not proofs; only the selected rigorous mode supplies the final verdict.",
    }


def special_form_test(kind: str, parameter: str, timeout: int = 60) -> dict:
    value = decimal_integer(parameter)
    if kind == "mersenne":
        if not 2 <= value <= 10_000_000:
            raise ValueError("The Mersenne exponent must be between 2 and 10,000,000")
        call = f"nt_lucas_lehmer({value})"
        name = f"M_{value} = 2^{value} − 1"
        method = "Lucas–Lehmer"
    elif kind == "fermat":
        if not 0 <= value <= 30:
            raise ValueError("The Fermat index must be between 0 and 30")
        call = f"nt_pepin({value})"
        name = f"F_{value} = 2^(2^{value}) + 1"
        method = "Pépin"
    else:
        raise ValueError("Unknown special-form test")
    lines = _execute(call, timeout)
    passed = _one(lines, "PASSES") == 1
    number = _one(lines, "NUMBER")
    factor_search = kind == "mersenne" and not passed and value >= 3
    return {
        "metrics": {"Number": str(number), "Form": name, "Test": method, "Rigorous verdict": "prime" if passed else "composite"},
        "columns": ["Test", "Outcome"], "rows": [[method, "pass" if passed else "fail"]],
        "factor_search": (
            {"kind": "mersenne", "exponent": str(value)} if factor_search else None
        ),
        "note": (
            f"The native {method} criterion is necessary and sufficient for this special "
            "form, so the result is a proof. "
            + (
                "Lucas–Lehmer does not produce a divisor; open the Mersenne factor "
                "search to test q = 2kp + 1 candidates without constructing M_p."
                if factor_search
                else "A primality proof does not require or produce a factorization."
            )
        ),
    }


def perfect_power(n: str, timeout: int = 60) -> dict:
    value = decimal_integer(n)
    lines = _execute(f"nt_perfect_power({value})", timeout)
    is_power = _one(lines, "IS_POWER") == 1
    base, exponent = _one(lines, "BASE"), _one(lines, "EXPONENT")
    return {
        "is_power": is_power,
        "metrics": {"Integer": str(value), "Perfect power": "yes" if is_power else "no", "Maximal base": str(base), "Maximal exponent": str(exponent)},
        "columns": ["Decomposition"], "rows": [[f"{value} = {base}^{exponent}"]] if is_power else [[f"{value} is not a nontrivial perfect power"]],
        "note": "PARI/GP computed the maximal perfect-power exponent exactly.",
    }


def factor_strategy(n: str, trial_bound: int, cado_threshold: int,
                    timeout: int = 60) -> dict:
    value = decimal_integer(n)
    if not 2 <= trial_bound <= 1_000_000:
        raise ValueError("Trial-division bound must be between 2 and 1,000,000")
    if not 20 <= cado_threshold <= 1_000:
        raise ValueError("CADO routing threshold must be between 20 and 1,000 digits")
    lines = _execute(
        f"nt_factor_strategy({value},{trial_bound},{cado_threshold})", timeout
    )
    strategies = [line[9:] for line in lines if line.startswith("STRATEGY:")]
    if len(strategies) != 1 or not re.fullmatch(r"[a-z_]+", strategies[0]):
        raise PrimeEngineError("PARI/GP returned an invalid factorization strategy")
    labels = {
        "complete_by_trial_division": "Completed by native trial division",
        "factor_perfect_power_base": "Factor the perfect-power base, then expand multiplicities",
        "yafu": "YAFU automatic pipeline",
        "hybrid_yafu_cado": "YAFU pretest followed by CADO-NFS",
    }
    factors = _records(lines, "SMALL_FACTOR", 2)
    power_minus = _records(lines, "POWER_MINUS_ONE", 2)
    power_plus = _records(lines, "POWER_PLUS_ONE", 2)
    mersenne = _one(lines, "MERSENNE_FORM")
    fermat = _one(lines, "FERMAT_FORM")
    special_forms: list[str] = []
    if mersenne:
        special_forms.append(f"Mersenne form 2^{mersenne} − 1")
    if fermat >= 0:
        special_forms.append(f"Fermat form 2^(2^{fermat}) + 1")
    if power_minus:
        special_forms.append(f"{power_minus[0][0]}^{power_minus[0][1]} − 1")
    if power_plus:
        special_forms.append(f"{power_plus[0][0]}^{power_plus[0][1]} + 1")
    exponent = _one(lines, "POWER_EXPONENT")
    metrics = {
        "Input digits": str(_one(lines, "DIGITS")),
        "Probable prime": "yes" if _one(lines, "PROBABLE_PRIME") else "no",
        "Perfect power": "no" if not exponent else f"{_one(lines, 'POWER_BASE')}^{exponent}",
        "Detected special forms": "; ".join(dict.fromkeys(special_forms)) or "none",
        "Trial bound": str(trial_bound),
        "Remaining cofactor": str(_one(lines, "RESIDUAL")),
        "Remaining digits": str(_one(lines, "RESIDUAL_DIGITS")),
        "Recommended strategy": labels[strategies[0]],
    }
    rows = [[prime, exponent_value] for prime, exponent_value in factors]
    return {
        "strategy": strategies[0], "metrics": metrics,
        "columns": ["Small factor", "Exponent"], "rows": rows,
        "note": "PARI/GP performed perfect-power, probable-prime, special-form, and bounded trial-division analysis before applying Numerisect's engine threshold. Special forms should be reviewed for algebraic/SNFS treatment before GNFS.",
    }


def eisenstein_prime(a: str, b: str, timeout: int = 60) -> dict:
    left, right = decimal_integer(a), decimal_integer(b)
    lines = _execute(f"nt_eisenstein({left},{right})", timeout)
    prime = _one(lines, "PRIME") == 1
    return {
        "metrics": {"Element": f"{left} + {right}ω", "Norm": str(_one(lines, "NORM")), "Eisenstein prime": "yes" if prime else "no"},
        "columns": ["Classification"], "rows": [["Eisenstein prime" if prime else "not an Eisenstein prime"]],
        "note": "PARI/GP applied the exact norm and ramified-axis criteria in ℤ[ω].",
    }


def quadratic_prime_decomposition(radicand: str, prime: str, timeout: int = 60) -> dict:
    d, p = decimal_integer(radicand), decimal_integer(prime)
    lines = _execute(f"nt_quadratic_prime_decomposition({d},{p})", timeout)
    ideals = _records(lines, "PRIME_IDEAL", 4)
    symbol = _one(lines, "KRONECKER")
    classification = "split" if len(ideals) == 2 else "ramified" if symbol == 0 else "inert"
    return {
        "metrics": {"Field": f"ℚ(√{d})", "Field discriminant": str(_one(lines, "FIELD_DISCRIMINANT")), "Rational prime": str(p), "Behavior": classification, "Kronecker symbol": str(symbol)},
        "columns": ["Prime ideal", "Ramification e", "Inertia f", "Norm"], "rows": ideals,
        "note": "PARI/GP constructed the maximal quadratic order and computed the rigorous prime-ideal decomposition.",
    }


def _primecount_option(value: int, option: str, threads: int, timeout: int) -> int:
    executable = shutil.which("primecount")
    if not executable:
        raise PrimeEngineError("The primecount engine is required for this comparison")
    try:
        result = subprocess.run(
            [executable, str(value), option, f"--threads={threads}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PrimeEngineError(f"primecount exceeded the {timeout}-second limit") from exc
    output = result.stdout.strip()
    if result.returncode or not re.fullmatch(r"\d+", output):
        raise PrimeEngineError(f"primecount failed: {(result.stderr.strip() or output)[-1000:]}")
    return int(output)


def prime_approximation_comparison(x: str, threads: int, timeout: int = 300) -> dict:
    value = decimal_integer(x)
    if not 3 <= value <= 10**31:
        raise ValueError("Approximation comparison supports 3 ≤ x ≤ 10^31")
    if not 1 <= threads <= 256:
        raise ValueError("Thread count must be between 1 and 256")
    exact = prime_count(value, threads)
    li = _primecount_option(value, "--Li", threads, timeout)
    riemann = _primecount_option(value, "--RiemannR", threads, timeout)
    lines = _execute(f"nt_prime_approximations({value},{exact},{li},{riemann})", timeout)
    rows = [line[len("APPROX:"):].split("|") for line in lines if line.startswith("APPROX:")]
    numeric = re.compile(r"[+-]?(?:\d+(?:\.\d*)?)(?:e[+-]?\d+)?", re.I)
    if len(rows) != 4 or any(
        len(row) != 4 or not all(numeric.fullmatch(item) for item in row[1:]) for row in rows
    ):
        raise PrimeEngineError("Native engines returned an invalid approximation comparison")
    return {
        "metrics": {"x": str(value), "Exact π(x)": str(exact), "CPU threads": str(threads)},
        "columns": ["Method", "Estimate", "Signed error", "Relative error (%)"],
        "rows": rows,
        "note": "primecount computed exact π(x), Li(x), and Riemann R(x); PARI/GP computed x/log(x) and every signed and relative error at high precision.",
    }


def summatory_functions(x: str, timeout: int = 300) -> dict:
    value = decimal_integer(x)
    if not 1 <= value <= 10_000_000:
        raise ValueError("Summatory analysis supports 1 ≤ x ≤ 10,000,000")
    lines = _execute(f"nt_summatory_functions({value})", timeout)
    decimals: dict[str, str] = {}
    for tag in ("THETA", "PSI"):
        matches = [line[len(tag) + 1:] for line in lines if line.startswith(f"{tag}:")]
        if len(matches) != 1 or not re.fullmatch(r"[+-]?\d+(?:\.\d*)?(?:e[+-]?\d+)?", matches[0], re.I):
            raise PrimeEngineError(f"PARI/GP returned an invalid {tag} value")
        decimals[tag] = matches[0]
    metrics = {
        "Endpoint x": str(value), "Mertens M(x)": str(_one(lines, "MERTENS")),
        "Summatory Liouville L(x)": str(_one(lines, "SUM_LIOUVILLE")),
        "Chebyshev θ(x)": decimals["THETA"], "Chebyshev ψ(x)": decimals["PSI"],
    }
    return {
        "metrics": metrics, "columns": ["Function", "Value"],
        "rows": [[key, value] for key, value in metrics.items()][1:],
        "note": "PARI/GP evaluated Möbius and Liouville sums and prime-power Chebyshev sums natively and exactly except for the displayed rigorously computed real logarithms.",
    }


def special_prime_family(
    kind: str, start_index: int, end_index: int, limit: int, timeout: int = 300
) -> dict:
    if kind not in _SPECIAL_FAMILY_CODES:
        raise ValueError("Unknown special-prime family")
    if not 0 <= start_index <= end_index <= 10_000 or end_index - start_index > 10_000:
        raise ValueError("Require 0 ≤ start ≤ end ≤ 10,000")
    if kind == "fermat" and end_index > 20:
        raise ValueError("Fermat-family search is limited to indices through 20")
    if not 1 <= limit <= 100_000:
        raise ValueError("Result limit must be between 1 and 100,000")
    lines = _execute(
        f"nt_special_prime_family({_SPECIAL_FAMILY_CODES[kind]},{start_index},{end_index},{limit})",
        timeout,
    )
    rows = _records(lines, "FAMILY", 3)
    if _one(lines, "DONE") != len(rows):
        raise PrimeEngineError("PARI/GP returned an incomplete special-prime search")
    auxiliary = {
        "mersenne": "Exponent p",
        "fermat": "Index n",
        "cullen": "Index n",
        "woodall": "Index n",
        "wagstaff": "Exponent p",
        "repunit": "Decimal length n",
        "primorial": "Sign",
        "factorial": "Sign",
    }[kind]
    return {
        "metrics": {
            "Family": kind.title(),
            "Index interval": f"{start_index} through {end_index}",
            "Proven primes found": str(len(rows)),
        },
        "columns": ["Index", "Prime", auxiliary],
        "rows": rows,
        "truncated": _one(lines, "TRUNCATED") == 1,
        "note": (
            "PARI/GP constructed every candidate in the requested special family and "
            "returned only candidates proven prime by isprime."
        ),
    }


def cunningham_chain(
    start_prime: str, length: int, kind: int, timeout: int = 300
) -> dict:
    start = decimal_integer(start_prime)
    if not 1 <= length <= 100_000 or kind not in {1, 2}:
        raise ValueError("Require chain length 1–100,000 and kind 1 or 2")
    lines = _execute(f"nt_cunningham_chain({start},{length},{kind})", timeout)
    rows = _records(lines, "CHAIN", 3)
    if _one(lines, "DONE") != len(rows):
        raise PrimeEngineError("PARI/GP returned an incomplete Cunningham chain")
    complete = len(rows) == length and all(row[2] == "1" for row in rows)
    display_rows = [
        [index, value, "proven prime" if status == "1" else "composite"]
        for index, value, status in rows
    ]
    recurrence = "p(k+1) = 2p(k) + 1" if kind == 1 else "p(k+1) = 2p(k) − 1"
    return {
        "complete": complete,
        "metrics": {
            "Starting prime": str(start),
            "Kind": str(kind),
            "Recurrence": recurrence,
            "Requested length": str(length),
            "Proven chain length": str(sum(row[2] == "1" for row in rows)),
        },
        "columns": ["Position", "Value", "Status"],
        "rows": display_rows,
        "note": (
            "PARI/GP proved every displayed prime. The requested Cunningham chain is complete."
            if complete
            else "PARI/GP stopped at the first composite term; the requested chain is not complete."
        ),
    }


def ntt_primes(
    bits: int, power_two: int, count: int, candidate_limit: int, timeout: int = 300
) -> dict:
    if not 2 <= bits <= 1_000_000 or not 1 <= power_two < bits:
        raise ValueError("Require 2 ≤ bit length ≤ 1,000,000 and 1 ≤ m < bit length")
    if not 1 <= count <= 100_000 or not 1 <= candidate_limit <= 10_000_000:
        raise ValueError("Require 1–100,000 primes and a candidate limit of 1–10,000,000")
    lines = _execute(f"nt_ntt_primes({bits},{power_two},{count},{candidate_limit})", timeout)
    rows = _records(lines, "NTT", 2)
    found, tested = _one(lines, "FOUND"), _one(lines, "TESTED")
    if found != len(rows) or _one(lines, "DONE") != found:
        raise PrimeEngineError("PARI/GP returned an incomplete NTT-prime search")
    complete = found == count
    return {
        "complete": complete,
        "metrics": {
            "Bit length": str(bits),
            "Required power of two": f"2^{power_two}",
            "Requested": str(count),
            "Found": str(found),
            "Candidates tested": str(tested),
        },
        "columns": ["Multiplier k", f"Proven prime p = k·2^{power_two} + 1"],
        "rows": rows,
        "note": (
            "PARI/GP proved every returned NTT-friendly prime with isprime."
            if complete
            else "The configured candidate limit or bit interval was exhausted; returned primes are proven, but the requested count was not reached."
        ),
    }


def tonelli_shanks(a: str, prime: str, trace_limit: int, timeout: int = 60) -> dict:
    value, p = decimal_integer(a), decimal_integer(prime)
    if not 0 <= trace_limit <= 100_000:
        raise ValueError("Trace limit must be between 0 and 100,000")
    lines = _execute(f"nt_tonelli_shanks({value},{p},{trace_limit})", timeout)
    roots = _tagged_values(lines, "ROOT")
    traces = _records(lines, "TRACE", 5)
    setup = _records(lines, "SETUP", 3)
    if any((root * root - value) % p for root in roots):
        raise PrimeEngineError("PARI/GP returned an invalid modular square root")
    metrics = {
        "Value a": str(value % p),
        "Prime modulus p": str(p),
        "Legendre symbol": str(_one(lines, "LEGENDRE")),
        "Root count": str(len(roots)),
    }
    if setup:
        metrics.update({"Odd part q": setup[0][0], "Power s": setup[0][1], "Nonresidue z": setup[0][2]})
    return {
        "metrics": metrics,
        "columns": ["Step", "Candidate x", "Residual t", "Coefficient c", "Exponent m"],
        "rows": traces,
        "roots": [str(root) for root in roots],
        "truncated": bool(_optional(lines, "TRACE_COMPLETE") == 0),
        "note": (
            "PARI/GP executed Tonelli–Shanks and independently verified every returned square root. "
            + (f"Roots: {', '.join(map(str, roots))}." if roots else "The value is a quadratic nonresidue, so no root exists.")
        ),
    }


def hensel_roots(
    coefficients: list[str], prime: str, exponent: int, limit: int, timeout: int = 60
) -> dict:
    if not 2 <= len(coefficients) <= 101:
        raise ValueError("Supply 2–101 coefficients in ascending order")
    values = [decimal_integer(value) for value in coefficients]
    if values[-1] == 0:
        raise ValueError("The leading coefficient must be nonzero")
    p = decimal_integer(prime)
    if not 1 <= exponent <= 100_000 or not 1 <= limit <= 100_000:
        raise ValueError("Require exponent and result limit between 1 and 100,000")
    vector = "[" + ",".join(map(str, values)) + "]"
    lines = _execute(f"nt_hensel_roots({vector},{p},{exponent},{limit})", timeout)
    roots = _tagged_values(lines, "ROOT")
    count = _one(lines, "ROOT_COUNT")
    complete = _one(lines, "COMPLETE") == 1
    if (complete and len(roots) != min(count, limit)) or (not complete and count != -1):
        raise PrimeEngineError("PARI/GP returned an incomplete Hensel-lift result")
    polynomial = [line[11:] for line in lines if line.startswith("POLYNOMIAL:")]
    if len(polynomial) != 1 or not _SAFE_TEXT.fullmatch(polynomial[0]):
        raise PrimeEngineError("PARI/GP returned an invalid Hensel polynomial")
    return {
        "complete": complete,
        "metrics": {"Polynomial": polynomial[0], "Prime": str(p), "Exponent": str(exponent), "Modulus": str(_one(lines, "MODULUS")), "Root count": str(count) if complete else f"more than {limit}"},
        "columns": [f"Root modulo {p}^{exponent}"],
        "rows": [[str(root)] for root in roots],
        "truncated": _one(lines, "TRUNCATED") == 1,
        "note": "PARI/GP lifted every root digit by digit and materialized exact residues modulo p^k." if complete else "The singular Hensel tree exceeded the configured root limit. Every displayed residue is exact, but the full root count is inconclusive.",
    }


def order_distribution(modulus: str, limit: int, timeout: int = 60) -> dict:
    n = decimal_integer(modulus)
    if not 1 <= limit <= 100_000:
        raise ValueError("Result limit must be between 1 and 100,000")
    lines = _execute(f"nt_order_distribution({n},{limit})", timeout)
    rows = _records(lines, "ORDER_ROW", 2)
    if _one(lines, "DONE") != len(rows):
        raise PrimeEngineError("PARI/GP returned an incomplete order distribution")
    return {
        "metrics": {"Modulus": str(n), "Units": str(_one(lines, "UNIT_COUNT")), "Distinct orders": str(_one(lines, "ORDER_COUNT"))},
        "columns": ["Multiplicative order", "Number of units"], "rows": rows,
        "truncated": _one(lines, "TRUNCATED") == 1,
        "note": "PARI/GP enumerated the units and computed every multiplicative order exactly.",
    }


def power_residue_distribution(
    prime: str, exponent: int, limit: int, timeout: int = 60
) -> dict:
    p = decimal_integer(prime)
    if not 1 <= exponent <= 1_000_000 or not 1 <= limit <= 100_000:
        raise ValueError("Require exponent and result limit between 1 and their documented limits")
    lines = _execute(f"nt_power_residues({p},{exponent},{limit})", timeout)
    rows = _records(lines, "RESIDUE", 2)
    if _one(lines, "DONE") != len(rows):
        raise PrimeEngineError("PARI/GP returned an incomplete residue distribution")
    return {
        "metrics": {"Prime modulus": str(p), "Power": str(exponent), "Distinct residues": str(_one(lines, "DISTINCT"))},
        "columns": ["Power residue", "Number of preimages"], "rows": rows,
        "truncated": _one(lines, "TRUNCATED") == 1,
        "note": "PARI/GP enumerated the complete power map over the finite field; the result limit affects only displayed rows.",
    }


def p_adic_valuation(n: str, prime: str, timeout: int = 60) -> dict:
    value, p = decimal_integer(n), decimal_integer(prime)
    lines = _execute(f"nt_valuation({value},{p})", timeout)
    valuation_value, unit = _one(lines, "VALUATION"), _one(lines, "UNIT_PART")
    return {
        "metrics": {"Integer": str(value), "Prime p": str(p), "Valuation vₚ(n)": str(valuation_value), "p-adic unit part": str(unit)},
        "columns": ["Exact decomposition"], "rows": [[f"{value} = {p}^{valuation_value} × {unit}"]],
        "note": "PARI/GP computed the exact p-adic valuation and coprime unit part.",
    }


def cyclotomic_polynomial(index: int, prime: str, timeout: int = 60) -> dict:
    p = decimal_integer(prime)
    if not 1 <= index <= 10_000:
        raise ValueError("Cyclotomic index must be between 1 and 10,000")
    lines = _execute(f"nt_cyclotomic({index},{p})", timeout)
    factors = _records(lines, "CYCLO_FACTOR", 2)
    polynomial = [line[11:] for line in lines if line.startswith("POLYNOMIAL:")]
    if len(polynomial) != 1 or not _SAFE_TEXT.fullmatch(polynomial[0]):
        raise PrimeEngineError("PARI/GP returned an invalid cyclotomic polynomial")
    return {
        "metrics": {"Index n": str(index), "Degree φ(n)": str(_one(lines, "DEGREE")), "Prime modulus": str(p), "Polynomial": polynomial[0]},
        "columns": [f"Factor over 𝔽_{p}", "Exponent"], "rows": factors,
        "note": "PARI/GP constructed the exact cyclotomic polynomial and factored it over the selected finite field.",
    }


def aliquot_sequence(n: str, max_steps: int, timeout: int = 300) -> dict:
    value = decimal_integer(n)
    if not 1 <= max_steps <= 100_000:
        raise ValueError("Step limit must be between 1 and 100,000")
    lines = _execute(f"nt_aliquot({value},{max_steps})", timeout)
    rows = _records(lines, "ALIQUOT", 2)
    status = _one(lines, "STATUS")
    labels = {0: "step limit reached", 1: "terminated at zero", 2: "cycle detected"}
    if status not in labels:
        raise PrimeEngineError("PARI/GP returned an invalid aliquot status")
    return {
        "complete": status != 0,
        "metrics": {"Starting integer": str(value), "Terms returned": str(len(rows)), "Status": labels[status], "Cycle/termination index": str(_one(lines, "STOP_INDEX")) if status else "not applicable"},
        "columns": ["Index", "Aliquot term"], "rows": rows,
        "note": "PARI/GP factored each term through its native divisor-sum implementation and detected termination or an exact repeated value.",
    }


def divisor_classification(n: str, timeout: int = 60) -> dict:
    value = decimal_integer(n)
    lines = _execute(f"nt_divisor_classification({value})", timeout)
    abundance = _one(lines, "ABUNDANCE")
    label = {-1: "deficient", 0: "perfect", 1: "abundant"}.get(abundance)
    if label is None:
        raise PrimeEngineError("PARI/GP returned an invalid abundance classification")
    multiplier = _one(lines, "MULTIPERFECT_K")
    metrics = {
        "Integer": str(value), "σ(n)": str(_one(lines, "SIGMA")),
        "Proper-divisor sum": str(_one(lines, "PROPER_SUM")), "Classification": label,
        "Perfect": "yes" if _one(lines, "PERFECT") else "no",
        "Almost perfect": "yes" if _one(lines, "ALMOST_PERFECT") else "no",
        "Multiperfect multiplier": str(multiplier) if multiplier >= 2 else "none",
        "Aliquot partner": str(_one(lines, "ALIQUOT_PARTNER")),
        "Amicable pair": "yes" if _one(lines, "AMICABLE_PAIR") else "no",
    }
    return {
        "metrics": metrics, "columns": ["Property", "Value"],
        "rows": [[key, value] for key, value in metrics.items()][1:],
        "note": "PARI/GP factored the integer and applied exact divisor-sum definitions. Weirdness and sociable-cycle searches remain separate bounded research operations.",
    }
