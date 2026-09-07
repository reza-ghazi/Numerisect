from __future__ import annotations

import math
import re
import subprocess

from .native_tools import zeta_tool_path


class ZetaEngineError(RuntimeError):
    pass


REAL_PATTERN = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def validated_real(value: str, name: str) -> str:
    normalized = value.strip().replace("_", "")
    if len(normalized) > 10_000 or not REAL_PATTERN.fullmatch(normalized):
        raise ValueError(f"{name} must be a finite decimal number")
    return normalized


def _run_zeta(arguments: list[str], timeout_seconds: int = 0) -> list[str]:
    try:
        tool = zeta_tool_path()
    except (OSError, RuntimeError) as exc:
        raise ZetaEngineError(str(exc)) from exc
    try:
        result = subprocess.run(
            [str(tool), *arguments],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=None if timeout_seconds == 0 else timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ZetaEngineError(
            f"FLINT exceeded the selected {timeout_seconds}-second time limit"
        ) from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ZetaEngineError(f"FLINT zeta engine failed: {detail[-2000:]}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _single_tag(lines: list[str], tag: str) -> str:
    prefix = f"{tag}:"
    values = [line[len(prefix):] for line in lines if line.startswith(prefix)]
    if len(values) != 1:
        raise ZetaEngineError(f"FLINT returned an invalid {tag.lower()} result")
    return values[0]


def evaluate_zeta(
    sigma: str, ordinate: str, precision: int, timeout_seconds: int = 0
) -> dict[str, object]:
    sigma = validated_real(sigma, "Real part")
    ordinate = validated_real(ordinate, "Imaginary part")
    lines = _run_zeta(
        ["evaluate", sigma, ordinate, str(precision)], timeout_seconds
    )
    return {
        "sigma": sigma,
        "ordinate": ordinate,
        "precision": precision,
        "real": _single_tag(lines, "REAL"),
        "imaginary": _single_tag(lines, "IMAG"),
        "magnitude": _single_tag(lines, "ABS"),
        "argument": _single_tag(lines, "ARG"),
        "engine": "FLINT/Arb",
        "rigorous": True,
        "note": "Each displayed value is an Arb enclosure, not an unbounded floating-point estimate.",
    }


def evaluate_hardy_z(ordinate: str, precision: int, timeout_seconds: int = 0) -> dict[str, object]:
    ordinate = validated_real(ordinate, "Ordinate")
    lines = _run_zeta(["hardy", ordinate, str(precision)], timeout_seconds)
    return {
        "function": "Riemann–Siegel Z", "input": ordinate,
        "real": _single_tag(lines, "VALUE_REAL"),
        "imaginary": _single_tag(lines, "VALUE_IMAG"),
        "engine": "FLINT/Arb", "rigorous": True,
        "note": "FLINT/Arb evaluated Hardy's real-valued Z(t) as a rigorous complex ball enclosure.",
    }


def evaluate_xi_eta(kind: str, sigma: str, ordinate: str, precision: int,
                    timeout_seconds: int = 0) -> dict[str, object]:
    if kind not in {"xi", "eta"}:
        raise ValueError("Function must be xi or eta")
    sigma = validated_real(sigma, "Real part")
    ordinate = validated_real(ordinate, "Imaginary part")
    lines = _run_zeta([kind, sigma, ordinate, str(precision)], timeout_seconds)
    return {
        "function": "Completed xi" if kind == "xi" else "Dirichlet eta",
        "sigma": sigma, "ordinate": ordinate,
        "real": _single_tag(lines, "VALUE_REAL"),
        "imaginary": _single_tag(lines, "VALUE_IMAG"),
        "engine": "FLINT/Arb", "rigorous": True,
        "note": f"FLINT/Arb evaluated the {kind} function with rigorous ball arithmetic.",
    }


def stieltjes_constant(index: str, precision: int,
                       timeout_seconds: int = 0) -> dict[str, object]:
    normalized = index.strip().replace("_", "")
    if len(normalized) > 10_000 or not re.fullmatch(r"\d+", normalized):
        raise ValueError("The Stieltjes index must be nonnegative")
    lines = _run_zeta(["stieltjes", normalized, str(precision)], timeout_seconds)
    return {
        "index": normalized, "real": _single_tag(lines, "VALUE_REAL"),
        "imaginary": _single_tag(lines, "VALUE_IMAG"),
        "engine": "FLINT/Arb", "rigorous": True,
        "note": "FLINT/Arb enclosed the Stieltjes constant from the Laurent expansion of ζ(s) at s=1.",
    }


def gram_point(index: str, precision: int, timeout_seconds: int = 0) -> dict[str, object]:
    normalized = index.strip().replace("_", "")
    if len(normalized) > 10_000 or not re.fullmatch(r"-?\d+", normalized) or int(normalized) < -1:
        raise ValueError("The Gram-point index must be an integer of at least −1")
    lines = _run_zeta(["gram", normalized, str(precision)], timeout_seconds)
    return {
        "index": normalized, "value": _single_tag(lines, "VALUE"),
        "engine": "FLINT/Arb", "rigorous": True,
        "note": "FLINT/Arb rigorously enclosed the Gram point satisfying θ(gₙ)=πn.",
    }


def verify_functional_equation(sigma: str, ordinate: str, precision: int,
                               timeout_seconds: int = 0) -> dict[str, object]:
    sigma = validated_real(sigma, "Real part")
    ordinate = validated_real(ordinate, "Imaginary part")
    lines = _run_zeta(["functional", sigma, ordinate, str(precision)], timeout_seconds)
    overlap = _single_tag(lines, "OVERLAP")
    if overlap not in {"0", "1"}:
        raise ZetaEngineError("FLINT returned an invalid functional-equation verdict")
    return {
        "sigma": sigma, "ordinate": ordinate, "verified": overlap == "1",
        "left_real": _single_tag(lines, "LEFT_REAL"),
        "left_imaginary": _single_tag(lines, "LEFT_IMAG"),
        "right_real": _single_tag(lines, "RIGHT_REAL"),
        "right_imaginary": _single_tag(lines, "RIGHT_IMAG"),
        "residual_real": _single_tag(lines, "RESIDUAL_REAL"),
        "residual_imaginary": _single_tag(lines, "RESIDUAL_IMAG"),
        "engine": "FLINT/Arb", "rigorous": True,
        "note": "Both independently evaluated sides overlap as Arb enclosures. This verifies the functional equation at the selected point and precision." if overlap == "1" else "The enclosures did not overlap; increase precision or inspect the selected point.",
    }


def find_zeta_zeros(
    start_index: int | str,
    count: int,
    precision: int,
    threads: int,
    timeout_seconds: int = 0,
) -> list[dict[str, str]]:
    start_text = str(start_index).strip().replace("_", "")
    if len(start_text) > 10_000 or not re.fullmatch(r"[1-9]\d*", start_text):
        raise ValueError("The starting zero index must be a positive integer")
    lines = _run_zeta(
        ["zeros", start_text, str(count), str(precision), str(threads)],
        timeout_seconds,
    )
    zeros: list[dict[str, str]] = []
    for line in lines:
        if not line.startswith("ZERO:"):
            continue
        fields = line[len("ZERO:"):].split("|", 3)
        if len(fields) != 4 or not fields[0].isdigit():
            raise ZetaEngineError("FLINT returned an invalid zero record")
        zeros.append(
            {
                "index": fields[0],
                "ordinate": fields[1],
                "radius": fields[2],
                "interval": fields[3],
            }
        )
    if len(zeros) != count:
        raise ZetaEngineError("FLINT did not return every requested zero")
    return zeros


def count_zeta_zeros(
    height: str, precision: int, threads: int, timeout_seconds: int = 0
) -> dict[str, str]:
    height = validated_real(height, "Height")
    lines = _run_zeta(
        ["count", height, str(precision), str(threads)], timeout_seconds
    )
    count = _single_tag(lines, "COUNT")
    if not re.fullmatch(r"\d+", count):
        raise ZetaEngineError("FLINT returned an invalid exact zero count")
    return {"height": height, "count": count, "interval": _single_tag(lines, "INTERVAL")}


def _parse_point(line: str, fields: int) -> list[float | None]:
    values = line[len("POINT:"):].split("|")
    if len(values) != fields:
        raise ZetaEngineError("FLINT returned an invalid plot sample")
    try:
        parsed = [float(value) for value in values]
    except ValueError as exc:
        raise ZetaEngineError("FLINT returned a nonnumeric plot sample") from exc
    # The zeta function has a pole at s=1. JSON has no portable NaN or infinity,
    # so preserve such native samples as null for the visualization layer.
    return [value if math.isfinite(value) else None for value in parsed]


def sample_zeta_line(
    lower: str,
    upper: str,
    samples: int,
    precision: int,
    threads: int,
    timeout_seconds: int = 0,
) -> list[dict[str, float | None]]:
    lower = validated_real(lower, "Lower ordinate")
    upper = validated_real(upper, "Upper ordinate")
    lines = _run_zeta(
        ["line", lower, upper, str(samples), str(precision), str(threads)],
        timeout_seconds,
    )
    points = [_parse_point(line, 5) for line in lines if line.startswith("POINT:")]
    if len(points) != samples:
        raise ZetaEngineError("FLINT did not return every critical-line sample")
    return [
        {"t": p[0], "real": p[1], "imaginary": p[2], "magnitude": p[3], "argument": p[4]}
        for p in points
    ]


def sample_zeta_heatmap(
    sigma_min: str,
    sigma_max: str,
    t_min: str,
    t_max: str,
    nx: int,
    ny: int,
    precision: int,
    threads: int,
    timeout_seconds: int = 0,
) -> list[dict[str, float | None]]:
    values = [
        validated_real(sigma_min, "Minimum real part"),
        validated_real(sigma_max, "Maximum real part"),
        validated_real(t_min, "Minimum ordinate"),
        validated_real(t_max, "Maximum ordinate"),
    ]
    lines = _run_zeta(
        ["heatmap", *values, str(nx), str(ny), str(precision), str(threads)],
        timeout_seconds,
    )
    grid = _single_tag(lines, "GRID")
    if grid != f"{nx}|{ny}":
        raise ZetaEngineError("FLINT returned an invalid heatmap grid")
    points = [_parse_point(line, 6) for line in lines if line.startswith("POINT:")]
    if len(points) != nx * ny:
        raise ZetaEngineError("FLINT did not return every heatmap sample")
    return [
        {
            "sigma": p[0],
            "t": p[1],
            "real": p[2],
            "imaginary": p[3],
            "magnitude": p[4],
            "argument": p[5],
        }
        for p in points
    ]


def _decimal_integer(value: str, name: str, minimum: int, maximum: int) -> int:
    """Validate a plain decimal integer supplied by the browser or CLI."""

    normalized = value.strip().replace("_", "")
    if len(normalized) > 100 or not re.fullmatch(r"-?\d+", normalized):
        raise ValueError(f"{name} must be a decimal integer")
    number = int(normalized)
    if not minimum <= number <= maximum:
        raise ValueError(f"{name} must lie between {minimum} and {maximum}")
    return number


def _records(lines: list[str], tag: str, width: int) -> list[list[str]]:
    """Split every ``TAG:a|b|c`` line into exactly ``width`` fields."""

    prefix = f"{tag}:"
    rows = [line[len(prefix):].split("|") for line in lines if line.startswith(prefix)]
    if any(len(row) != width for row in rows):
        raise ZetaEngineError(f"FLINT returned an invalid {tag.lower()} record")
    return rows


def _expected_count(lines: list[str], rows: list[list[str]], tag: str = "COUNT") -> int:
    """Require the helper's completion marker to match the parsed row count."""

    text = _single_tag(lines, tag)
    if not re.fullmatch(r"\d+", text) or int(text) != len(rows):
        raise ZetaEngineError("FLINT did not return every requested record")
    return len(rows)


def _float(value: str) -> float | None:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ZetaEngineError("FLINT returned a nonnumeric sample") from exc
    return parsed if math.isfinite(parsed) else None


def explicit_prime_count(
    bound: str,
    zeros: int,
    precision: int,
    threads: int,
    timeout_seconds: int = 0,
) -> dict[str, object]:
    """Approximate π(x) from certified zeta zeros with Riemann's explicit formula.

    The ``explicit-pi`` subcommand of the FLINT helper evaluates every term:
    ``acb_dirichlet_hardy_z_zeros`` supplies the certified zero ordinates,
    ``arb_hypgeom_li`` the principal term, ``acb_hypgeom_ei`` each ``li(x^ρ)``,
    and ``n_moebius_mu`` the Möbius coefficients. The exact comparison value
    π(x) comes from ``primecount`` through :func:`numerisect.primes.prime_count`.
    Python performs no arithmetic on any of these quantities.

    Args:
        bound: Decimal integer x with 2 ≤ x ≤ 10^12.
        zeros: How many certified zeros enter the truncated sum.
        precision: Working decimal precision for the Arb enclosures.
        threads: OpenMP worker count for the per-zero term evaluation.
        timeout_seconds: Zero disables the helper time limit.

    Returns:
        A convergence table whose estimates are explicitly exploratory because
        the sum over zeros is truncated, alongside the exact π(x).

    Raises:
        ValueError: The bound or zero count is outside the supported range.
        ZetaEngineError: primecount or the FLINT helper failed.
    """

    from .primes import PrimeEngineError, prime_count

    number = _decimal_integer(bound, "The evaluation point x", 2, 10**12)
    try:
        exact = prime_count(number)
    except (PrimeEngineError, ValueError) as exc:
        raise ZetaEngineError(f"The exact π(x) reference is unavailable: {exc}") from exc
    lines = _run_zeta(
        ["explicit-pi", str(number), str(exact), str(zeros), str(precision), str(threads)],
        timeout_seconds,
    )
    rows = _records(lines, "TERM", 5)
    _expected_count(lines, rows)
    return {
        "bound": str(number),
        "exact": str(exact),
        "exact_enclosure": _single_tag(lines, "EXACT"),
        "zeros": int(_single_tag(lines, "ZEROS")),
        "moebius_terms": int(_single_tag(lines, "MOEBIUS_TERMS")),
        "terms": [
            {
                "zeros": int(row[0]),
                "estimate": row[1],
                "error": row[2],
                "estimate_value": _float(row[3]),
                "error_value": _float(row[4]),
            }
            for row in rows
        ],
        "engine": "FLINT/Arb",
        "rigorous": False,
        "note": (
            "The zero ordinates and every individual term are certified Arb enclosures, "
            "but the sum over zeros is truncated, so each estimate is exploratory. "
            f"The exact π({number}) = {exact} came from primecount."
        ),
    }


def chebyshev_psi_formula(
    bound: str,
    zeros: int,
    precision: int,
    threads: int,
    timeout_seconds: int = 0,
) -> dict[str, object]:
    """Reconstruct Chebyshev's ψ(x) from certified zeta zeros.

    The ``psi`` subcommand evaluates ψ_N(x) = x − Σ 2Re(x^ρ/ρ) − log 2π −
    ½log(1 − x⁻²) with ``acb_dirichlet_hardy_z_zeros`` for the certified zeros
    and Arb primitives for every power and logarithm. The exact ψ(x) is summed
    over prime powers enumerated by FLINT's ``n_primes_t`` sieve.

    Args:
        bound: Decimal integer x with 2 ≤ x ≤ 10^7.
        zeros: How many certified zeros enter the truncated sum.
        precision: Working decimal precision for the Arb enclosures.
        threads: OpenMP worker count for the per-zero term evaluation.
        timeout_seconds: Zero disables the helper time limit.

    Returns:
        A convergence table plus the exact ψ(x) enclosure.

    Raises:
        ValueError: The bound or zero count is outside the supported range.
        ZetaEngineError: The FLINT helper failed.
    """

    number = _decimal_integer(bound, "The evaluation point x", 2, 10_000_000)
    lines = _run_zeta(
        ["psi", str(number), str(zeros), str(precision), str(threads)], timeout_seconds
    )
    rows = _records(lines, "TERM", 5)
    _expected_count(lines, rows)
    return {
        "bound": str(number),
        "exact": _single_tag(lines, "EXACT"),
        "exact_value": _float(_single_tag(lines, "EXACT_MID")),
        "limit": _single_tag(lines, "LIMIT"),
        "zeros": int(_single_tag(lines, "ZEROS")),
        "terms": [
            {
                "zeros": int(row[0]),
                "estimate": row[1],
                "error": row[2],
                "estimate_value": _float(row[3]),
                "error_value": _float(row[4]),
            }
            for row in rows
        ],
        "engine": "FLINT/Arb",
        "rigorous": False,
        "note": (
            "The exact ψ(x) is a certified Arb enclosure summed over the prime powers "
            "FLINT's sieve enumerated. Every explicit-formula estimate truncates the sum "
            "over zeros and is therefore exploratory, not a certification."
        ),
    }


def riemann_siegel_remainder(
    sigma: str,
    ordinate: str,
    terms: int,
    precision: int,
    timeout_seconds: int = 0,
) -> dict[str, object]:
    """Compare the Riemann–Siegel expansion with the rigorous value of ζ(s).

    ``acb_dirichlet_zeta_rs`` evaluates the main sum with K correction terms,
    ``acb_dirichlet_zeta_rs_bound`` supplies FLINT's rigorous remainder bound,
    and ``acb_dirichlet_zeta`` provides the reference enclosure.

    Args:
        sigma: Real part of s.
        ordinate: Imaginary part of s; the expansion requires t ≥ 10.
        terms: Largest number K of correction terms to report.
        precision: Working decimal precision.
        timeout_seconds: Zero disables the helper time limit.

    Returns:
        One row per K with the value, the deviation from the reference, and the
        remainder bound. Every row is a certified enclosure.

    Raises:
        ValueError: An input is not a finite decimal number.
        ZetaEngineError: The FLINT helper failed or t was below 10.
    """

    sigma = validated_real(sigma, "Real part")
    ordinate = validated_real(ordinate, "Imaginary part")
    lines = _run_zeta(
        ["riemann-siegel", sigma, ordinate, str(terms), str(precision)], timeout_seconds
    )
    rows = _records(lines, "RS", 6)
    _expected_count(lines, rows)
    return {
        "sigma": sigma,
        "ordinate": ordinate,
        "reference_real": _single_tag(lines, "REFERENCE_REAL"),
        "reference_imaginary": _single_tag(lines, "REFERENCE_IMAG"),
        "rows": [
            {
                "terms": int(row[0]),
                "real": row[1],
                "imaginary": row[2],
                "deviation": row[3],
                "bound": row[4],
                "deviation_value": _float(row[5]),
            }
            for row in rows
        ],
        "engine": "FLINT/Arb",
        "rigorous": True,
        "note": (
            "acb_dirichlet_zeta_rs already includes its rigorous remainder bound in the "
            "returned ball, so both the values and the deviations from acb_dirichlet_zeta "
            "are certified enclosures."
        ),
    }


def euler_product_comparison(
    sigma: str,
    ordinate: str,
    primes: int,
    precision: int,
    threads: int,
    timeout_seconds: int = 0,
) -> dict[str, object]:
    """Compare truncated Euler products with ζ(s) for Re(s) > 1.

    Each local factor is built from ``acb_pow`` over the primes enumerated by
    FLINT's ``n_primes_t`` sieve, ``acb_dirichlet_zeta`` supplies the reference,
    and ``_acb_dirichlet_euler_product_real_ui`` contributes FLINT's own
    certified Euler-product value whenever s is a real integer.

    Args:
        sigma: Real part of s; must satisfy Re(s) > 1.
        ordinate: Imaginary part of s.
        primes: How many primes the longest product uses.
        precision: Working decimal precision.
        threads: OpenMP worker count for the local factors.
        timeout_seconds: Zero disables the helper time limit.

    Returns:
        A checkpoint table with the partial product, its rigorous truncation
        bound, and the deviation from ζ(s).

    Raises:
        ValueError: An input is not a finite decimal number.
        ZetaEngineError: Re(s) ≤ 1 or the FLINT helper failed.
    """

    sigma = validated_real(sigma, "Real part")
    ordinate = validated_real(ordinate, "Imaginary part")
    lines = _run_zeta(
        ["euler-product", sigma, ordinate, str(primes), str(precision), str(threads)],
        timeout_seconds,
    )
    rows = _records(lines, "EULER", 7)
    _expected_count(lines, rows)
    certified = [line[len("CERTIFIED_EULER:"):] for line in lines
                 if line.startswith("CERTIFIED_EULER:")]
    return {
        "sigma": sigma,
        "ordinate": ordinate,
        "primes": int(_single_tag(lines, "PRIMES")),
        "reference_real": _single_tag(lines, "REFERENCE_REAL"),
        "reference_imaginary": _single_tag(lines, "REFERENCE_IMAG"),
        "certified_euler": certified[0] if len(certified) == 1 else None,
        "rows": [
            {
                "primes": int(row[0]),
                "largest_prime": row[1],
                "real": row[2],
                "imaginary": row[3],
                "deviation": row[4],
                "truncation_bound": row[5],
                "deviation_value": _float(row[6]),
            }
            for row in rows
        ],
        "engine": "FLINT/Arb",
        "rigorous": True,
        "note": (
            "Every partial product and deviation is an Arb enclosure and the truncation "
            "bound is rigorous. The bound grows without limit as Re(s) approaches 1, "
            "which is exactly why the Euler product cannot be continued to the critical strip."
        ),
    }


def zero_spacing_histogram(
    start_index: str,
    count: int,
    bins: int,
    precision: int,
    threads: int,
    timeout_seconds: int = 0,
) -> dict[str, object]:
    """Histogram normalized gaps between consecutive certified zeta zeros.

    ``acb_dirichlet_hardy_z_zeros`` isolates the zeros and
    ``acb_dirichlet_hardy_theta`` unfolds each ordinate to unit mean spacing.
    The GUE Wigner surmise is integrated in closed form with ``arb_hypgeom_erf``.

    Args:
        start_index: First zero index, a positive decimal integer.
        count: How many consecutive zeros to sample (gaps = count − 1).
        bins: Histogram resolution across the fixed window [0, 3].
        precision: Working decimal precision.
        threads: OpenMP worker count.
        timeout_seconds: Zero disables the helper time limit.

    Returns:
        Bin counts with observed and GUE-predicted densities plus summary
        statistics. The histogram is exploratory; the zeros are certified.

    Raises:
        ValueError: The starting index is not a positive integer.
        ZetaEngineError: The FLINT helper failed.
    """

    start_text = str(start_index).strip().replace("_", "")
    if len(start_text) > 10_000 or not re.fullmatch(r"[1-9]\d*", start_text):
        raise ValueError("The starting zero index must be a positive integer")
    lines = _run_zeta(
        ["zero-spacing", start_text, str(count), str(bins), str(precision), str(threads)],
        timeout_seconds,
    )
    rows = _records(lines, "BIN", 6)
    _expected_count(lines, rows)
    statistics = _records(lines, "STATS", 4)
    if len(statistics) != 1:
        raise ZetaEngineError("FLINT returned invalid spacing statistics")
    mean, variance, minimum, maximum = statistics[0]
    return {
        "start_index": start_text,
        "samples": int(_single_tag(lines, "SAMPLES")),
        "overflow": int(_single_tag(lines, "OVERFLOW")),
        "mean": _float(mean),
        "variance": _float(variance),
        "minimum": _float(minimum),
        "maximum": _float(maximum),
        "bins": [
            {
                "index": int(row[0]),
                "lower": _float(row[1]),
                "upper": _float(row[2]),
                "count": int(row[3]),
                "observed": _float(row[4]),
                "predicted": _float(row[5]),
            }
            for row in rows
        ],
        "engine": "FLINT/Arb",
        "rigorous": False,
        "note": (
            "The zero ordinates are certified enclosures and the Riemann–Siegel theta "
            "unfolding is rigorous, but a finite histogram is exploratory statistics and "
            "certifies nothing about the GUE conjecture."
        ),
    }


def zero_pair_correlation(
    start_index: str,
    count: int,
    bins: int,
    window: int,
    precision: int,
    threads: int,
    timeout_seconds: int = 0,
) -> dict[str, object]:
    """Estimate the pair correlation of certified zeros against the GUE law.

    ``acb_dirichlet_hardy_z_zeros`` supplies the zeros and
    ``acb_dirichlet_hardy_theta`` unfolds them; the C helper bins every pair
    difference below the window and evaluates 1 − (sin πu / πu)² with Arb.

    Args:
        start_index: First zero index, a positive decimal integer.
        count: How many consecutive zeros to sample.
        bins: Histogram resolution across [0, window].
        window: Upper limit on the normalized difference u.
        precision: Working decimal precision.
        threads: OpenMP worker count.
        timeout_seconds: Zero disables the helper time limit.

    Returns:
        Bin counts with observed and Montgomery/GUE-predicted correlations.

    Raises:
        ValueError: The starting index is not a positive integer.
        ZetaEngineError: The FLINT helper failed.
    """

    start_text = str(start_index).strip().replace("_", "")
    if len(start_text) > 10_000 or not re.fullmatch(r"[1-9]\d*", start_text):
        raise ValueError("The starting zero index must be a positive integer")
    lines = _run_zeta(
        [
            "pair-correlation", start_text, str(count), str(bins), str(window),
            str(precision), str(threads),
        ],
        timeout_seconds,
    )
    rows = _records(lines, "BIN", 6)
    _expected_count(lines, rows)
    return {
        "start_index": start_text,
        "samples": int(_single_tag(lines, "SAMPLES")),
        "pairs": int(_single_tag(lines, "PAIRS")),
        "window": window,
        "bins": [
            {
                "index": int(row[0]),
                "lower": _float(row[1]),
                "upper": _float(row[2]),
                "count": int(row[3]),
                "observed": _float(row[4]),
                "predicted": _float(row[5]),
            }
            for row in rows
        ],
        "engine": "FLINT/Arb",
        "rigorous": False,
        "note": (
            "Certified zeros, exploratory statistics: a finite pair-correlation histogram "
            "illustrates the GUE prediction 1 − (sin πu/πu)² but proves nothing."
        ),
    }


def gram_block_structure(
    start_index: str,
    count: int,
    precision: int,
    threads: int,
    timeout_seconds: int = 0,
) -> dict[str, object]:
    """Test Gram's law over an index range and report the block structure.

    ``acb_dirichlet_gram_point`` encloses every Gram point and
    ``acb_dirichlet_hardy_z`` encloses Z(gₙ); a Gram point counts as good only
    when the enclosure of (−1)ⁿZ(gₙ) is strictly positive, so each verdict is
    certified and an indeterminate sign is reported as inconclusive.

    Args:
        start_index: First Gram index, an integer of at least −1.
        count: How many consecutive Gram points to examine.
        precision: Working decimal precision.
        threads: OpenMP worker count.
        timeout_seconds: Zero disables the helper time limit.

    Returns:
        Per-index verdicts, the exception list, and the Gram blocks of length
        two or more.

    Raises:
        ValueError: The starting index is below −1.
        ZetaEngineError: The FLINT helper failed.
    """

    start = _decimal_integer(start_index, "The starting Gram index", -1, 10**9)
    lines = _run_zeta(
        ["gram-blocks", str(start), str(count), str(precision), str(threads)],
        timeout_seconds,
    )
    rows = _records(lines, "GRAM", 4)
    _expected_count(lines, rows)
    exceptions = _records(lines, "EXCEPTION", 3)
    blocks = _records(lines, "BLOCK", 3)
    if len(exceptions) != int(_single_tag(lines, "EXCEPTIONS")):
        raise ZetaEngineError("FLINT returned an inconsistent Gram exception count")
    if len(blocks) != int(_single_tag(lines, "BLOCKS")):
        raise ZetaEngineError("FLINT returned an inconsistent Gram block count")
    return {
        "start_index": str(start),
        "count": len(rows),
        "inconclusive": int(_single_tag(lines, "INCONCLUSIVE")),
        "points": [
            {
                "index": row[0],
                "gram_point": _float(row[1]),
                "hardy_z": _float(row[2]),
                "status": row[3],
            }
            for row in rows
        ],
        "exceptions": [
            {"index": row[0], "gram_point": row[1], "hardy_z": row[2]}
            for row in exceptions
        ],
        "blocks": [
            {"start_index": row[0], "length": int(row[1]), "pattern": row[2]}
            for row in blocks
        ],
        "engine": "FLINT/Arb",
        "rigorous": True,
        "note": (
            "Each verdict is certified: a Gram point is only called good or bad when the "
            "Arb enclosure of (−1)ⁿZ(gₙ) excludes zero, and an enclosure that straddles "
            "zero is reported as inconclusive rather than as a decision."
        ),
    }


def backlund_remainder(
    lower: str,
    upper: str,
    samples: int,
    precision: int,
    threads: int,
    timeout_seconds: int = 0,
) -> dict[str, object]:
    """Enclose the zero-counting remainder S(T) and sample it over a range.

    ``acb_dirichlet_backlund_s`` encloses S(T), ``acb_dirichlet_backlund_s_bound``
    supplies the rigorous magnitude bound, ``acb_dirichlet_zeta_nzeros`` certifies
    N(T) by the Turing method, and ``acb_dirichlet_hardy_theta`` supplies θ(T).

    Args:
        lower: Lower ordinate of the plotted range.
        upper: Upper ordinate; S(T), N(T) and θ(T) are certified here.
        samples: How many plot samples to draw across the range.
        precision: Working decimal precision.
        threads: OpenMP worker count.
        timeout_seconds: Zero disables the helper time limit.

    Returns:
        The certified endpoint quantities and the exploratory plot samples.

    Raises:
        ValueError: An input is not a finite decimal number.
        ZetaEngineError: The FLINT helper failed.
    """

    lower = validated_real(lower, "Lower ordinate")
    upper = validated_real(upper, "Upper ordinate")
    lines = _run_zeta(
        ["backlund", lower, upper, str(samples), str(precision), str(threads)],
        timeout_seconds,
    )
    rows = _records(lines, "POINT", 2)
    _expected_count(lines, rows)
    zero_count = _single_tag(lines, "NZEROS")
    if zero_count != "inconclusive" and not re.fullmatch(r"\d+", zero_count):
        raise ZetaEngineError("FLINT returned an invalid certified zero count")
    return {
        "lower": lower,
        "upper": upper,
        "remainder": _single_tag(lines, "SVALUE"),
        "remainder_bound": _single_tag(lines, "SBOUND"),
        "theta": _single_tag(lines, "THETA"),
        "zero_count": zero_count,
        "zero_count_interval": _single_tag(lines, "NZEROS_INTERVAL"),
        "points": [{"t": _float(row[0]), "s": _float(row[1])} for row in rows],
        "engine": "FLINT/Arb",
        "rigorous": True,
        "note": (
            "S(T), N(T) and θ(T) at the upper endpoint are certified enclosures; the plotted "
            "samples are enclosure midpoints for exploration only. An indeterminate Turing "
            "count is reported as inconclusive rather than as a number."
        ),
    }


def dirichlet_characters(modulus: str, limit: int, timeout_seconds: int = 0) -> dict[str, object]:
    """Enumerate the Dirichlet characters modulo q with their invariants.

    ``dirichlet_group_init`` builds the group and the ``dirichlet_char_*``
    family supplies each Conrey label, conductor, parity, order, primitivity,
    reality and principality. Python performs no group arithmetic.

    Args:
        modulus: The modulus q with 1 ≤ q ≤ 100000.
        limit: Maximum number of characters to list.
        timeout_seconds: Zero disables the helper time limit.

    Returns:
        The character table plus the group order and primitive-character total.

    Raises:
        ValueError: The modulus is outside the supported range.
        ZetaEngineError: The FLINT helper failed.
    """

    q = _decimal_integer(modulus, "The modulus", 1, 100_000)
    lines = _run_zeta(["characters", str(q), str(limit)], timeout_seconds)
    rows = _records(lines, "CHAR", 8)
    _expected_count(lines, rows)
    truncated = _single_tag(lines, "TRUNCATED")
    if truncated not in {"0", "1"}:
        raise ZetaEngineError("FLINT returned an invalid truncation flag")
    return {
        "modulus": str(q),
        "group_order": _single_tag(lines, "GROUP_ORDER"),
        "primitive_total": _single_tag(lines, "PRIMITIVE_TOTAL"),
        "truncated": truncated == "1",
        "characters": [
            {
                "index": int(row[0]),
                "number": row[1],
                "conductor": row[2],
                "parity": "odd" if row[3] == "1" else "even",
                "order": row[4],
                "primitive": row[5] == "1",
                "real": row[6] == "1",
                "principal": row[7] == "1",
            }
            for row in rows
        ],
        "engine": "FLINT/Arb",
        "rigorous": True,
        "note": (
            "Conductor, parity and order are exact integer invariants computed by FLINT's "
            "dirichlet_char_* routines."
            + (" The listing was truncated by the requested row limit." if truncated == "1" else "")
        ),
    }


def _character_metadata(lines: list[str]) -> dict[str, object]:
    return {
        "modulus": _single_tag(lines, "MODULUS"),
        "number": _single_tag(lines, "NUMBER"),
        "conductor": _single_tag(lines, "CONDUCTOR"),
        "parity": "odd" if _single_tag(lines, "PARITY") == "1" else "even",
        "order": _single_tag(lines, "ORDER"),
        "primitive": _single_tag(lines, "PRIMITIVE") == "1",
        "real_character": _single_tag(lines, "REAL_CHARACTER") == "1",
        "principal": _single_tag(lines, "PRINCIPAL") == "1",
    }


def dirichlet_l_value(
    modulus: str,
    number: str,
    sigma: str,
    ordinate: str,
    precision: int,
    timeout_seconds: int = 0,
) -> dict[str, object]:
    """Evaluate L(s, χ) as a rigorous ball with two independent FLINT routines.

    ``acb_dirichlet_l`` produces the primary enclosure and
    ``acb_dirichlet_l_hurwitz`` an independent cross-check; primitive characters
    additionally report ``acb_dirichlet_root_number`` and ``acb_dirichlet_gauss_sum``.

    Args:
        modulus: The modulus q.
        number: The Conrey label m of the character, coprime to q.
        sigma: Real part of s.
        ordinate: Imaginary part of s.
        precision: Working decimal precision.
        timeout_seconds: Zero disables the helper time limit.

    Returns:
        The enclosure, the cross-check, the overlap verdict and the character
        invariants.

    Raises:
        ValueError: The modulus or character label is outside the valid range.
        ZetaEngineError: The label is not coprime to q, s is the principal pole,
            or the FLINT helper failed.
    """

    q = _decimal_integer(modulus, "The modulus", 1, 100_000)
    m = _decimal_integer(number, "The character number", 1, 100_000)
    sigma = validated_real(sigma, "Real part")
    ordinate = validated_real(ordinate, "Imaginary part")
    lines = _run_zeta(
        ["l-function", str(q), str(m), sigma, ordinate, str(precision)], timeout_seconds
    )
    overlap = _single_tag(lines, "OVERLAP")
    if overlap not in {"0", "1"}:
        raise ZetaEngineError("FLINT returned an invalid cross-check verdict")
    result: dict[str, object] = {
        **_character_metadata(lines),
        "sigma": sigma,
        "ordinate": ordinate,
        "real": _single_tag(lines, "VALUE_REAL"),
        "imaginary": _single_tag(lines, "VALUE_IMAG"),
        "cross_real": _single_tag(lines, "CROSS_REAL"),
        "cross_imaginary": _single_tag(lines, "CROSS_IMAG"),
        "verified": overlap == "1",
        "engine": "FLINT/Arb",
        "rigorous": True,
        "note": (
            "acb_dirichlet_l and acb_dirichlet_l_hurwitz produced overlapping rigorous "
            "enclosures at this point and precision."
            if overlap == "1"
            else "The two independent enclosures did not overlap; raise the precision."
        ),
    }
    if any(line.startswith("ROOT_NUMBER_REAL:") for line in lines):
        result["root_number_real"] = _single_tag(lines, "ROOT_NUMBER_REAL")
        result["root_number_imaginary"] = _single_tag(lines, "ROOT_NUMBER_IMAG")
        result["gauss_sum_real"] = _single_tag(lines, "GAUSS_SUM_REAL")
        result["gauss_sum_imaginary"] = _single_tag(lines, "GAUSS_SUM_IMAG")
    return result


def dirichlet_l_zeros(
    modulus: str,
    number: str,
    lower: str,
    upper: str,
    samples: int,
    precision: int,
    threads: int,
    timeout_seconds: int = 0,
) -> dict[str, object]:
    """Isolate critical-line sign changes of L(s, χ) or locate |L| minima.

    For a real primitive character the helper evaluates ``acb_dirichlet_hardy_z``
    on a grid and bisects every strict sign change into a certified bracket, so
    each reported interval provably contains a zero of odd order on the critical
    line. For a complex character it reports minima of |L(½+it, χ)| computed with
    ``acb_dirichlet_l``, which are explicitly exploratory. The smooth
    Riemann–von Mangoldt count comes from ``acb_dirichlet_hardy_theta``.

    Args:
        modulus: The modulus q.
        number: The Conrey label m; the character must be primitive.
        lower: Lower ordinate of the search range.
        upper: Upper ordinate of the search range.
        samples: Grid resolution for the initial sign or magnitude scan.
        precision: Working decimal precision.
        threads: OpenMP worker count.
        timeout_seconds: Zero disables the helper time limit.

    Returns:
        Certified sign-change brackets or exploratory magnitude minima, the
        smooth expected count, and the sampled curve.

    Raises:
        ValueError: The modulus or character label is outside the valid range.
        ZetaEngineError: The character is imprimitive or the helper failed.
    """

    q = _decimal_integer(modulus, "The modulus", 1, 100_000)
    m = _decimal_integer(number, "The character number", 1, 100_000)
    lower = validated_real(lower, "Lower ordinate")
    upper = validated_real(upper, "Upper ordinate")
    lines = _run_zeta(
        [
            "l-zeros", str(q), str(m), lower, upper, str(samples), str(precision),
            str(threads),
        ],
        timeout_seconds,
    )
    points = _records(lines, "POINT", 3)
    _expected_count(lines, points)
    mode = _single_tag(lines, "MODE")
    if mode not in {"sign-changes", "magnitude-minima"}:
        raise ZetaEngineError("FLINT returned an unknown zero-search mode")
    changes = _records(lines, "SIGN_CHANGE", 3)
    minima = _records(lines, "MINIMUM", 3)
    if len(changes) != int(_single_tag(lines, "CHANGES")):
        raise ZetaEngineError("FLINT returned an inconsistent sign-change count")
    if len(minima) != int(_single_tag(lines, "MINIMA")):
        raise ZetaEngineError("FLINT returned an inconsistent minimum count")
    certified = mode == "sign-changes"
    return {
        **_character_metadata(lines),
        "mode": mode,
        "lower": lower,
        "upper": upper,
        "samples": len(points),
        "smooth_count": _single_tag(lines, "SMOOTH_COUNT"),
        "sign_changes": [
            {"index": int(row[0]), "lower": _float(row[1]), "upper": _float(row[2])}
            for row in changes
        ],
        "minima": [
            {"index": int(row[0]), "t": _float(row[1]), "magnitude": _float(row[2])}
            for row in minima
        ],
        "points": [
            {"t": _float(row[0]), "hardy_z": _float(row[1]), "magnitude": _float(row[2])}
            for row in points
        ],
        "engine": "FLINT/Arb",
        "rigorous": certified,
        "note": (
            "Every listed bracket is a certified sign change of Hardy's Z(t, χ) and so "
            "contains a critical-line zero of odd order. The count is a certified lower "
            "bound only: a coarse grid can miss closely spaced pairs, and the smooth "
            "θ(T,χ)/π count is the asymptotic main term, not a certification."
            if certified
            else "This character is complex, so Z(t, χ) is not real valued. The listed "
            "|L(½+it, χ)| minima are exploratory indicators of nearby zeros and certify "
            "nothing; the smooth θ(T,χ)/π count is the asymptotic main term."
        ),
    }
