"""Typed orchestration boundary for the visualization and education workbench.

Every number rendered by the browser originates in a mature library routine.
This module validates requests, launches the native engines, parses the tagged
protocol strictly, and shapes JSON-friendly results; it never computes a
mathematical quantity itself.

Library routine supplying the numbers for each visualization:

===========================  ==========================================================
Visualization                Routine
===========================  ==========================================================
Prime spirals (Ulam, Sacks,  primesieve ``primesieve`` CLI for an unhighlighted range
polar)                       inside 2^64; otherwise PARI ``forprime`` + ``isprime``,
                             with highlight membership from PARI ``issquare``
Eisenstein lattice           PARI ``isprime`` and ``sqrtint``
Modular wheel                PARI ``isprime``, ``gcd``, ``eulerphi``
Residue-class heatmap        PARI ``forprime`` + ``isprime`` + ``gcd``
Prime-gap timeline           PARI ``forprime`` + ``isprime`` + ``log``
Prime race                   PARI ``forprime`` + ``isprime`` + ``gcd``
Sieve animations             the classical sieves executed step by step in GP,
                             verified against PARI ``primes(primepi(n))``
===========================  ==========================================================

The sieve animation is the single deliberate exception to "always call the
library routine": Eratosthenes, segmented Eratosthenes, Sundaram and Atkin are
run explicitly because the algorithms themselves are what the animation
teaches.  Those traces are educational and bounded (``n`` up to 5,000), and
every other tool here — and all real enumeration in the application — uses
primesieve or PARI's ``forprime``/``isprime``.

The complexity dashboard is not a mathematical computation at all: its
reference table is cited literature and its timing summary is bookkeeping over
wall-clock seconds in the persisted job history.
"""

from __future__ import annotations

import re
import statistics
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .primes import PrimeEngineError, _run_gp, _tagged_values, primes_in_range

PROGRAM = Path(__file__).with_name("visual_lab.gp")

HIGHLIGHT_MODES: dict[str, int] = {"none": 0, "residue": 1, "polynomial": 2}
SPIRAL_LAYOUTS: tuple[str, ...] = ("ulam", "sacks", "polar")
SIEVE_KINDS: dict[str, int] = {"eratosthenes": 0, "segmented": 1, "sundaram": 2, "atkin": 3}
EISENSTEIN_KINDS: dict[int, str] = {
    1: "split (norm is a rational prime ≡ 1 mod 3)",
    2: "inert associate (unit × rational prime ≡ 2 mod 3)",
    3: "ramified (norm 3, associate of 1 − ω)",
}
SIEVE_STEP_KINDS: dict[int, str] = {
    1: "select prime",
    2: "strike multiple",
    3: "survivor declared prime",
    4: "Sundaram strike i + j + 2ij",
    5: "Atkin toggle 4x² + y²",
    6: "Atkin toggle 3x² + y²",
    7: "Atkin toggle 3x² − y²",
    8: "Atkin square-multiple elimination",
    9: "segment boundary",
}

MAX_SPIRAL_CELLS = 1_000_000
MAX_SPIRAL_CELLS_ABOVE_64_BITS = 100_000
MAX_SPAN = 10_000_000
MAX_SPAN_ABOVE_64_BITS = 100_000
MAX_START_DIGITS = 60
MAX_SIEVE_N = 5_000
MAX_NORM_BOUND = 200_000
MAX_MODULUS = 360
MAX_WHEEL_BASE = 10_000
MAX_WHEEL_CELLS = 200_000
WORD_LIMIT = 2**64 - 1

_INTEGER = re.compile(r"-?\d+")
_DECIMAL = re.compile(r"-?\d+\.\d+")

#: Asymptotic reference table for roadmap item 128.  Each entry cites the
#: standard source for the stated bound; L_n[α, c] denotes
#: exp((c + o(1)) (ln n)^α (ln ln n)^(1−α)).
COMPLEXITY_REFERENCE: list[dict[str, str]] = [
    {
        "algorithm": "Trial division",
        "category": "factoring (exponential)",
        "time": "O(n^(1/2)) divisions; O(p) to find a factor p",
        "memory": "O(1) (O(π(√n)) with a stored prime table)",
        "source": "Crandall & Pomerance, Prime Numbers: A Computational Perspective, 2nd ed., §3.1",
    },
    {
        "algorithm": "Pollard rho (Brent cycle finding)",
        "category": "factoring (special purpose)",
        "time": "expected O(√p) ≈ O(n^(1/4)) modular multiplications (heuristic)",
        "memory": "O(1)",
        "source": "Pollard, BIT 15 (1975); Brent, BIT 20 (1980)",
    },
    {
        "algorithm": "Pollard p − 1",
        "category": "factoring (special purpose)",
        "time": "O(B₁ log B₁) multiplications for stage 1; succeeds when p − 1 is B₁-smooth",
        "memory": "O(1) for stage 1; stage 2 stores O(B₂ / log B₂) residues or a polynomial table",
        "source": "Pollard, Proc. Cambridge Philos. Soc. 76 (1974); Montgomery, Math. Comp. 48 (1987)",
    },
    {
        "algorithm": "Elliptic-curve method (ECM)",
        "category": "factoring (special purpose)",
        "time": "L_p[1/2, √2] per factor p (heuristic); independent of the size of n",
        "memory": "O(log n) per curve; stage 2 memory grows with B₂",
        "source": "H. W. Lenstra Jr., Annals of Mathematics 126 (1987); Zimmermann & Dodson, ANTS VII (2006)",
    },
    {
        "algorithm": "Self-initializing quadratic sieve (SIQS)",
        "category": "factoring (general purpose)",
        "time": "L_n[1/2, 1] (heuristic)",
        "memory": "sub-exponential: factor base, sieve block, and sparse relation matrix",
        "source": "Pomerance, Eurocrypt '84 (1985); Contini, M.Sc. thesis, University of Georgia (1997)",
    },
    {
        "algorithm": "General number field sieve (GNFS)",
        "category": "factoring (general purpose)",
        "time": "L_n[1/3, (64/9)^(1/3) ≈ 1.923] (heuristic)",
        "memory": "sub-exponential: sieve regions plus a sparse matrix with millions of rows",
        "source": "Lenstra & Lenstra (eds.), The Development of the Number Field Sieve, LNM 1554 (1993)",
    },
    {
        "algorithm": "Special number field sieve (SNFS)",
        "category": "factoring (special form)",
        "time": "L_n[1/3, (32/9)^(1/3) ≈ 1.526] (heuristic)",
        "memory": "sub-exponential, smaller than GNFS at equal size",
        "source": "Lenstra, Lenstra, Manasse & Pollard, Math. Comp. 61 (1993)",
    },
    {
        "algorithm": "AKS primality test",
        "category": "primality (deterministic, proven)",
        "time": "Õ(log⁶ n) (Lenstra–Pomerance variant); original bound Õ(log^(10.5) n)",
        "memory": "polynomial in log n",
        "source": "Agrawal, Kayal & Saxena, Annals of Mathematics 160 (2004); Lenstra & Pomerance, J. Eur. Math. Soc. 21 (2019)",
    },
    {
        "algorithm": "Elliptic-curve primality proving (ECPP)",
        "category": "primality (certificate)",
        "time": "Õ(log⁴ n) heuristic (fastECPP); certificate verification Õ(log³ n)",
        "memory": "polynomial in log n",
        "source": "Atkin & Morain, Math. Comp. 61 (1993); Morain, Math. Comp. 76 (2007)",
    },
    {
        "algorithm": "APR-CL (Adleman–Pomerance–Rumely, Cohen–Lenstra)",
        "category": "primality (deterministic, proven)",
        "time": "(log n)^(O(log log log n)) — superpolynomial but practically fast",
        "memory": "polynomial in log n",
        "source": "Adleman, Pomerance & Rumely, Annals of Mathematics 117 (1983); Cohen & Lenstra, Math. Comp. 42 (1984)",
    },
    {
        "algorithm": "Sieve of Eratosthenes",
        "category": "sieve",
        "time": "O(n log log n)",
        "memory": "O(n) bits",
        "source": "Crandall & Pomerance, §3.2; Sorenson, Technical Report 909, U. Wisconsin (1990)",
    },
    {
        "algorithm": "Segmented sieve of Eratosthenes",
        "category": "sieve",
        "time": "O(n log log n)",
        "memory": "O(√n) plus one cache-sized segment",
        "source": "Bays & Hudson, BIT 17 (1977); Sorenson (1990)",
    },
    {
        "algorithm": "Sieve of Sundaram",
        "category": "sieve",
        "time": "O(n log n)",
        "memory": "O(n) bits",
        "source": "Sundaram (1934), as described in Aiyar, Math. Student 2 (1934); Crandall & Pomerance, §3.2",
    },
    {
        "algorithm": "Sieve of Atkin",
        "category": "sieve",
        "time": "O(n / log log n)",
        "memory": "O(n^(1/2 + o(1)))",
        "source": "Atkin & Bernstein, Math. Comp. 73 (2004)",
    },
]


def _program() -> str:
    try:
        return PROGRAM.read_text(encoding="utf-8")
    except OSError as exc:
        raise PrimeEngineError("The visualization PARI/GP program is unavailable") from exc


def _execute(call: str, timeout: int) -> list[str]:
    if not 1 <= timeout <= 3600:
        raise ValueError("Engine time limit must be between 1 and 3,600 seconds")
    lines = _run_gp(f"{_program()}\n{call};", timeout=timeout)
    if not _tagged_values(lines, "DONE"):
        raise PrimeEngineError("PARI/GP returned an incomplete visualization result")
    return lines


def _one(lines: list[str], tag: str) -> int:
    values = _tagged_values(lines, tag)
    if len(values) != 1:
        raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} result")
    return values[0]


def _fields(
    lines: Iterable[str], tag: str, width: int, patterns: tuple[re.Pattern[str], ...] = ()
) -> list[list[str]]:
    prefix = f"{tag}:"
    rows = [line[len(prefix):].split("|") for line in lines if line.startswith(prefix)]
    for row in rows:
        if len(row) != width:
            raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} record")
        for index, value in enumerate(row):
            pattern = patterns[index] if index < len(patterns) else _INTEGER
            if not pattern.fullmatch(value):
                raise PrimeEngineError(f"PARI/GP returned an invalid {tag.lower()} record")
    return rows


def _check_range(start: int, end: int, *, span_limit: int = MAX_SPAN) -> None:
    if start < 1:
        raise ValueError("The range must start at a positive integer")
    if start > end:
        raise ValueError("Range start must not exceed range end")
    if len(str(start)) > MAX_START_DIGITS:
        raise ValueError(f"The range start may have at most {MAX_START_DIGITS} decimal digits")
    span = end - start + 1
    if span > span_limit:
        raise ValueError(f"The range may span at most {span_limit:,} integers")
    if end > WORD_LIMIT and span > MAX_SPAN_ABOVE_64_BITS:
        raise ValueError(
            f"Ranges above 2^64 may span at most {MAX_SPAN_ABOVE_64_BITS:,} integers"
        )


def spiral_primes(
    start: int,
    count: int,
    layout: str = "ulam",
    highlight: str = "none",
    a: int = 1,
    b: int = 1,
    c: int = 41,
    modulus: int = 4,
    residue: int = 1,
    timeout: int = 60,
) -> dict[str, object]:
    """List the primes among ``count`` consecutive integers from ``start``.

    The browser lays the integers out as an Ulam, Sacks, or polar spiral and
    needs only the prime indicator plus an optional highlight flag.  Highlight
    membership (a residue class, or the values of ``a·k² + b·k + c`` over the
    integers ``k``) is decided by PARI/GP.  When no highlight is requested and
    the range fits in 64 bits, primesieve enumerates the primes instead.

    Args:
        start: First integer of the spiral (≥ 1, at most 60 decimal digits).
        count: Number of consecutive integers (1–1,000,000; 100,000 above 2^64).
        layout: ``"ulam"``, ``"sacks"``, or ``"polar"``; the layout only tells the
            browser which coordinate map to apply and never changes the mathematics.
        highlight: ``"none"``, ``"residue"``, or ``"polynomial"``.
        a: Quadratic coefficient for polynomial highlighting.
        b: Linear coefficient for polynomial highlighting.
        c: Constant term for polynomial highlighting.
        modulus: Modulus for residue-class highlighting (2–1,000,000).
        residue: Residue for residue-class highlighting (0 ≤ residue < modulus).
        timeout: PARI/GP time limit in seconds (1–3,600).

    Returns:
        A dictionary with decimal ``primes``, the ``highlighted`` subset, counts,
        the engine used, and an explanatory note.

    Raises:
        ValueError: On invalid bounds or highlight parameters.
        PrimeEngineError: When the native engine fails or returns an incomplete result.
    """
    if layout not in SPIRAL_LAYOUTS:
        raise ValueError("Spiral layout must be ulam, sacks, or polar")
    if highlight not in HIGHLIGHT_MODES:
        raise ValueError("Highlight mode must be none, residue, or polynomial")
    if not 1 <= count <= MAX_SPIRAL_CELLS:
        raise ValueError(f"The spiral may cover 1 to {MAX_SPIRAL_CELLS:,} integers")
    end = start + count - 1
    _check_range(start, end, span_limit=MAX_SPIRAL_CELLS)
    if end > WORD_LIMIT and count > MAX_SPIRAL_CELLS_ABOVE_64_BITS:
        raise ValueError(
            f"Spirals above 2^64 may cover at most {MAX_SPIRAL_CELLS_ABOVE_64_BITS:,} integers"
        )
    if not all(-1_000_000 <= value <= 1_000_000 for value in (a, b, c)):
        raise ValueError("Polynomial coefficients must lie between -1,000,000 and 1,000,000")
    if not 2 <= modulus <= 1_000_000 or not 0 <= residue < modulus:
        raise ValueError("Require 2 ≤ modulus ≤ 1,000,000 and 0 ≤ residue < modulus")
    if not 1 <= timeout <= 3600:
        raise ValueError("Engine time limit must be between 1 and 3,600 seconds")
    if highlight == "none" and end <= WORD_LIMIT:
        values, truncated, _ = primes_in_range(start, end, count)
        if truncated:
            raise PrimeEngineError("primesieve returned more primes than integers in the range")
        primes = [str(value) for value in values]
        highlighted: list[str] = []
        engine = "primesieve"
    else:
        mode = HIGHLIGHT_MODES[highlight]
        lines = _execute(
            f"vl_spiral({start},{count},{mode},{a},{b},{c},{modulus},{residue})", timeout
        )
        rows = _fields(lines, "PRIME", 2)
        if len(rows) != _one(lines, "PRIME_COUNT"):
            raise PrimeEngineError("PARI/GP returned an incomplete spiral prime list")
        primes = [row[0] for row in rows]
        highlighted = [row[0] for row in rows if row[1] == "1"]
        if len(highlighted) != _one(lines, "HIGHLIGHT_COUNT"):
            raise PrimeEngineError("PARI/GP returned an inconsistent highlight count")
        engine = "PARI/GP"
    if highlight == "residue":
        description = f"primes ≡ {residue} (mod {modulus})"
    elif highlight == "polynomial":
        description = f"prime values of {a}k² + {b}k + {c} for integer k"
    else:
        description = "no highlight"
    return {
        "start": str(start),
        "end": str(end),
        "count": count,
        "layout": layout,
        "prime_count": len(primes),
        "highlight": highlight,
        "highlight_description": description,
        "highlight_count": len(highlighted),
        "primes": primes,
        "highlighted": highlighted,
        "engine": engine,
        "note": (
            f"{engine} enumerated every prime in the range"
            + (" with rigorous isprime confirmation" if engine == "PARI/GP" else "")
            + f"; highlight: {description}. JavaScript only assigns spiral coordinates."
        ),
    }


def eisenstein_lattice(norm_bound: int, limit: int = 20_000, timeout: int = 60) -> dict[str, object]:
    """Enumerate the Eisenstein primes ``a + bω`` with norm ``a² − ab + b² ≤ norm_bound``.

    PARI/GP applies the same criterion as the single-element Eisenstein tool:
    the norm is a rational prime, or the element is an associate of a rational
    prime congruent to 2 modulo 3.

    Args:
        norm_bound: Maximum norm (2–200,000).
        limit: Maximum number of points to return (1–200,000).
        timeout: PARI/GP time limit in seconds.

    Returns:
        A dictionary with the lattice ``points`` (``a``, ``b``, ``norm``, ``kind``),
        the kind legend, the per-kind counts computed by PARI/GP, and truncation state.
    """
    if not 2 <= norm_bound <= MAX_NORM_BOUND:
        raise ValueError(f"The norm bound must be between 2 and {MAX_NORM_BOUND:,}")
    if not 1 <= limit <= 200_000:
        raise ValueError("The point limit must be between 1 and 200,000")
    lines = _execute(f"vl_eisenstein_lattice({norm_bound},{limit})", timeout)
    rows = _fields(lines, "EPOINT", 4)
    if len(rows) != _one(lines, "COUNT"):
        raise PrimeEngineError("PARI/GP returned an incomplete Eisenstein lattice")
    points = [
        {"a": int(row[0]), "b": int(row[1]), "norm": int(row[2]), "kind": int(row[3])}
        for row in rows
    ]
    if any(point["kind"] not in EISENSTEIN_KINDS for point in points):
        raise PrimeEngineError("PARI/GP returned an unknown Eisenstein-prime kind")
    kind_rows = _fields(lines, "KIND", 2)
    if len(kind_rows) != len(EISENSTEIN_KINDS):
        raise PrimeEngineError("PARI/GP returned an incomplete Eisenstein kind summary")
    kind_counts = {row[0]: int(row[1]) for row in kind_rows}
    truncated = _one(lines, "TRUNCATED") == 1
    return {
        "norm_bound": norm_bound,
        "count": len(points),
        "points": points,
        "kind_counts": kind_counts,
        "kinds": {str(key): value for key, value in EISENSTEIN_KINDS.items()},
        "truncated": truncated,
        "next_start": None,
        "engine": "PARI/GP",
        "note": (
            "PARI/GP applied the exact Eisenstein norm/axis criterion with rigorous rational "
            "primality tests at every lattice point; JavaScript only places a + bω on the "
            "hexagonal lattice."
        ),
    }


def modular_wheel(
    modulus: int = 30, start: int = 0, count: int = 300, timeout: int = 60
) -> dict[str, object]:
    """Lay out ``count`` consecutive integers from ``start`` on a wheel of ``modulus`` spokes.

    This extends the Prime Structures wheel, which always starts at 0 and caps
    the base at 360 with at most 20,001 cells.  PARI/GP decides primality with
    ``isprime``, computes each residue, ring index, and coprimality flag, counts
    the primes on every spoke, and evaluates Euler's totient; the browser only
    turns ``(residue, ring)`` into polar coordinates.

    Args:
        modulus: Wheel base, i.e. the number of spokes (2–10,000).
        start: First integer placed on the wheel (≥ 0).
        count: Number of consecutive integers (1–200,000).
        timeout: PARI/GP time limit in seconds (1–3,600).

    Returns:
        A dictionary with the wheel ``cells`` (``value``, ``residue``, ``ring``,
        ``is_prime``, ``coprime``), per-spoke prime counts, the totient, and totals.

    Raises:
        ValueError: When the base, start, count, or time limit is out of range.
        PrimeEngineError: When PARI/GP fails or returns an incomplete wheel.
    """
    if not 2 <= modulus <= MAX_WHEEL_BASE:
        raise ValueError(f"The wheel base must be between 2 and {MAX_WHEEL_BASE:,}")
    if start < 0:
        raise ValueError("The wheel must start at a nonnegative integer")
    if len(str(start)) > MAX_START_DIGITS:
        raise ValueError(f"The wheel start may have at most {MAX_START_DIGITS} decimal digits")
    if not 1 <= count <= MAX_WHEEL_CELLS:
        raise ValueError(f"The wheel may cover 1 to {MAX_WHEEL_CELLS:,} integers")
    lines = _execute(f"vl_modular_wheel({modulus},{start},{count})", timeout)
    rows = _fields(lines, "CELL", 5)
    if len(rows) != _one(lines, "CELL_COUNT") or len(rows) != count:
        raise PrimeEngineError("PARI/GP did not return every modular-wheel cell")
    spokes = _fields(lines, "SPOKE", 3)
    if len(spokes) != modulus:
        raise PrimeEngineError("PARI/GP returned an incomplete spoke summary")
    cells = [
        {
            "value": int(row[0]),
            "residue": int(row[1]),
            "ring": int(row[2]),
            "is_prime": row[3] == "1",
            "coprime": row[4] == "1",
        }
        for row in rows
    ]
    return {
        "modulus": modulus,
        "start": start,
        "count": count,
        "end": start + count - 1,
        "cells": cells,
        "spokes": [
            {"residue": int(row[0]), "coprime": row[1] == "1", "prime_count": int(row[2])}
            for row in spokes
        ],
        "spokes_with_primes": _one(lines, "LOADED_SPOKES"),
        "totient": _one(lines, "TOTIENT"),
        "ring_count": _one(lines, "RING_COUNT"),
        "prime_count": _one(lines, "PRIME_COUNT"),
        "coprime_count": _one(lines, "COPRIME_COUNT"),
        "engine": "PARI/GP",
        "note": (
            "PARI/GP computed every residue, ring index, coprimality flag, rigorous primality "
            f"result, per-spoke prime count, and φ({modulus}); JavaScript only places the cells "
            "on the wheel. Dirichlet's theorem guarantees that only the φ(m) spokes coprime to "
            "the base can carry primes beyond the base itself."
        ),
    }


def residue_heatmap(
    start: int, end: int, modulus: int = 30, bins: int = 50, timeout: int = 120
) -> dict[str, object]:
    """Count primes per residue class per interval bin over ``[start, end]``.

    Args:
        start: Range start (≥ 1).
        end: Range end; the span is limited to 10,000,000 integers (100,000 above 2^64).
        modulus: Residue modulus (2–360).
        bins: Number of equal-width interval bins (1–200).
        timeout: PARI/GP time limit in seconds.

    Returns:
        A dictionary with one row per bin (``counts`` indexed by residue), residue
        totals with coprimality flags, and the maximum cell count.
    """
    _check_range(start, end)
    if not 2 <= modulus <= MAX_MODULUS:
        raise ValueError(f"The modulus must be between 2 and {MAX_MODULUS}")
    if not 1 <= bins <= 200:
        raise ValueError("Request between 1 and 200 bins")
    lines = _execute(f"vl_residue_heatmap({start},{end},{modulus},{bins})", timeout)
    rows = _fields(lines, "BIN", 3 + modulus)
    if len(rows) != _one(lines, "BIN_COUNT"):
        raise PrimeEngineError("PARI/GP returned an incomplete heatmap")
    residues = _fields(lines, "RESIDUE", 3)
    if len(residues) != modulus:
        raise PrimeEngineError("PARI/GP returned an incomplete residue summary")
    return {
        "start": str(start),
        "end": str(end),
        "modulus": modulus,
        "bin_count": len(rows),
        "bins": [
            {"index": int(row[0]), "start": row[1], "end": row[2], "counts": [int(v) for v in row[3:]]}
            for row in rows
        ],
        "residues": [
            {"residue": int(row[0]), "coprime": row[1] == "1", "total": int(row[2])}
            for row in residues
        ],
        "prime_count": _one(lines, "PRIME_COUNT"),
        "max_cell": _one(lines, "MAX_CELL"),
        "engine": "PARI/GP",
        "note": (
            "PARI/GP sieved the range with rigorous isprime confirmation and counted every "
            "prime by residue class and interval bin; JavaScript only maps counts to colours."
        ),
    }


def gap_timeline(start: int, end: int, limit: int = 20_000, timeout: int = 120) -> dict[str, object]:
    """Return consecutive prime gaps and the record gaps over ``[start, end]``.

    A record gap is one exceeding every earlier gap in the scanned range; when
    the scan starts at 2 these are exactly the maximal prime gaps.  The merit
    ``g / ln p`` is evaluated by PARI/GP.

    Args:
        start: Range start (≥ 1).
        end: Range end; the span is limited to 10,000,000 integers (100,000 above 2^64).
        limit: Maximum number of timeline gaps returned (1–200,000); records are
            always complete.
        timeout: PARI/GP time limit in seconds.

    Returns:
        A dictionary with the ``gaps`` timeline, complete ``records``, the largest
        gap, and truncation state.
    """
    _check_range(start, end)
    if not 1 <= limit <= 200_000:
        raise ValueError("The gap limit must be between 1 and 200,000")
    lines = _execute(f"vl_gap_timeline({start},{end},{limit})", timeout)
    gaps = _fields(lines, "GAP", 2)
    if len(gaps) != _one(lines, "SHOWN"):
        raise PrimeEngineError("PARI/GP returned an incomplete gap timeline")
    records = _fields(lines, "RECORD", 4, (_INTEGER, _INTEGER, _INTEGER, _DECIMAL))
    if len(records) != _one(lines, "RECORD_COUNT"):
        raise PrimeEngineError("PARI/GP returned an incomplete record list")
    count = _one(lines, "GAP_COUNT")
    return {
        "start": str(start),
        "end": str(end),
        "first_prime": str(_one(lines, "FIRST")),
        "last_prime": str(_one(lines, "LAST")),
        "gap_count": count,
        "record_count": _one(lines, "RECORD_COUNT"),
        "shown": len(gaps),
        "gaps": [{"prime": row[0], "gap": int(row[1])} for row in gaps],
        "records": [
            {"from": row[0], "to": row[1], "gap": int(row[2]), "merit": row[3]} for row in records
        ],
        "max_gap": _one(lines, "MAX_GAP"),
        "max_gap_at": str(_one(lines, "MAX_GAP_AT")),
        "truncated": _one(lines, "TRUNCATED") == 1,
        "next_start": None,
        "engine": "PARI/GP",
        "note": (
            "PARI/GP scanned every consecutive prime pair with rigorous isprime confirmation; "
            "records are maximal within the scanned range (exact maximal gaps when the scan "
            "starts at 2) and merits are g / ln p. The timeline may be truncated at the limit; "
            "the record list never is."
        ),
    }


def prime_race(
    start: int,
    end: int,
    modulus: int = 4,
    checkpoints: int = 200,
    event_limit: int = 5_000,
    timeout: int = 120,
) -> dict[str, object]:
    """Trace a Chebyshev prime race between the reduced residue classes modulo ``modulus``.

    PARI/GP records the running class counts at equally spaced checkpoints and
    every exact lead change (ties keep the previous leader).  The browser only
    replays those frames.

    Args:
        start: Range start (≥ 1).
        end: Range end; the span is limited to 10,000,000 integers (100,000 above 2^64).
        modulus: Race modulus (2–360).
        checkpoints: Number of animation frames (1–1,000).
        event_limit: Maximum lead-change events returned (1–100,000).
        timeout: PARI/GP time limit in seconds.

    Returns:
        A dictionary with ``classes``, ``checkpoints`` (``x``, ``leader``, ``counts``),
        lead-change ``events``, final counts, and the final leader.
    """
    _check_range(start, end)
    if not 2 <= modulus <= MAX_MODULUS:
        raise ValueError(f"The modulus must be between 2 and {MAX_MODULUS}")
    if not 1 <= checkpoints <= 1_000:
        raise ValueError("Request between 1 and 1,000 checkpoints")
    if not 1 <= event_limit <= 100_000:
        raise ValueError("The event limit must be between 1 and 100,000")
    lines = _execute(
        f"vl_prime_race({start},{end},{modulus},{checkpoints},{event_limit})", timeout
    )
    class_rows = [
        line[len("CLASSES:"):].split("|") for line in lines if line.startswith("CLASSES:")
    ]
    if len(class_rows) != 1 or not all(_INTEGER.fullmatch(value) for value in class_rows[0]):
        raise PrimeEngineError("PARI/GP returned an invalid residue-class list")
    classes = [int(value) for value in class_rows[0]]
    frames = _fields(lines, "CHECK", 2 + len(classes))
    if len(frames) != checkpoints:
        raise PrimeEngineError("PARI/GP returned an incomplete prime-race timeline")
    events = _fields(lines, "LEAD", 2)
    event_count = _one(lines, "EVENT_COUNT")
    truncated = _one(lines, "EVENT_TRUNCATED") == 1
    if len(events) != min(event_count, event_limit):
        raise PrimeEngineError("PARI/GP returned an inconsistent lead-change list")
    finals = _fields(lines, "FINAL", 2)
    if len(finals) != len(classes):
        raise PrimeEngineError("PARI/GP returned incomplete final counts")
    return {
        "start": str(start),
        "end": str(end),
        "modulus": modulus,
        "classes": classes,
        "checkpoints": [
            {"x": row[0], "leader": int(row[1]), "counts": [int(v) for v in row[2:]]}
            for row in frames
        ],
        "events": [{"prime": row[0], "leader": int(row[1])} for row in events],
        "event_count": event_count,
        "event_truncated": truncated,
        "final": [{"residue": int(row[0]), "count": int(row[1])} for row in finals],
        "leader": _one(lines, "LEADER"),
        "max_count": _one(lines, "MAX_COUNT"),
        "prime_count": _one(lines, "PRIME_COUNT"),
        "engine": "PARI/GP",
        "note": (
            "PARI/GP counted primes in each reduced residue class with rigorous isprime "
            "confirmation and recorded every exact lead change (ties keep the previous "
            "leader; -1 means no leader yet). JavaScript only replays the frames."
        ),
    }


def sieve_trace(
    kind: str, n: int, segment_size: int | None = None, timeout: int = 60
) -> dict[str, object]:
    """Produce the exact step trace of a classical sieve up to ``n``.

    PARI/GP emits every selection, strike, toggle, elimination, and survivor
    declaration in execution order and verifies the survivors against its own
    prime table before reporting success.

    This is the one visualization that does not delegate to a library
    enumeration routine, because the algorithms themselves are the subject of
    the animation.  The trace is bounded at ``n = 5,000`` and PARI/GP refuses
    to report it unless the survivors match its own ``primes(primepi(n))``
    table.  All real prime enumeration in Numerisect uses primesieve or
    ``forprime``, never these traces.

    Args:
        kind: ``"eratosthenes"``, ``"segmented"``, ``"sundaram"``, or ``"atkin"``.
        n: Sieve limit (2–5,000).
        segment_size: Segment length for the segmented sieve. ``None`` asks
            PARI/GP for its default block size ``sqrtint(n) + 1``; Python never
            derives it.
        timeout: PARI/GP time limit in seconds.

    Returns:
        A dictionary with the ordered ``steps`` (``[kind, value, a, b, flag]``), the
        step-kind legend, the verified ``primes``, and counts.
    """
    if kind not in SIEVE_KINDS:
        raise ValueError("Sieve kind must be eratosthenes, segmented, sundaram, or atkin")
    if not 2 <= n <= MAX_SIEVE_N:
        raise ValueError(f"Sieve traces cover n between 2 and {MAX_SIEVE_N:,}")
    if segment_size is not None and not 1 <= segment_size <= n:
        raise ValueError("The segment size must be between 1 and n")
    requested = 0 if segment_size is None else segment_size
    lines = _execute(f"vl_sieve_trace({SIEVE_KINDS[kind]},{n},{requested})", timeout)
    steps = _fields(lines, "STEP", 5)
    if len(steps) != _one(lines, "STEP_COUNT"):
        raise PrimeEngineError("PARI/GP returned an incomplete sieve trace")
    primes = _tagged_values(lines, "PRIME")
    if len(primes) != _one(lines, "PRIME_COUNT") or _one(lines, "VERIFIED") != 1:
        raise PrimeEngineError("PARI/GP did not verify the sieve trace")
    return {
        "kind": kind,
        "n": n,
        "segment_size": _one(lines, "SEGMENT") if kind == "segmented" else None,
        "steps": [[int(value) for value in row] for row in steps],
        "step_kinds": {str(key): value for key, value in SIEVE_STEP_KINDS.items()},
        "step_count": len(steps),
        "primes": primes,
        "prime_count": len(primes),
        "verified": True,
        "engine": "PARI/GP",
        "note": (
            f"PARI/GP executed the {kind} sieve step by step and verified the survivors "
            "against its prime table; JavaScript only replays the recorded steps."
        ),
    }


def _job_seconds(job: dict[str, object]) -> float | None:
    started, finished = job.get("started_at"), job.get("finished_at")
    if not isinstance(started, str) or not isinstance(finished, str):
        return None
    try:
        seconds = (datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds()
    except ValueError:
        return None
    return seconds if seconds >= 0 else None


def _digit_bucket(digits: int, width: int = 10) -> str:
    low = ((max(digits, 1) - 1) // width) * width + 1
    return f"{low}–{low + width - 1}"


def complexity_dashboard(jobs: Iterable[dict[str, object]]) -> dict[str, object]:
    """Combine the asymptotic reference table with measured factorization timings.

    The reference rows are literature values with citations.  The measured rows
    are bookkeeping over completed jobs from the persisted history: elapsed
    seconds grouped by selected engine and 10-digit input-size bucket.

    Args:
        jobs: Job records as returned by ``Database.list_jobs``.

    Returns:
        A dictionary with the ``reference`` table, the measured ``groups``, and counts.
    """
    samples: dict[tuple[str, int], list[float]] = {}
    considered = 0
    for job in jobs:
        if job.get("status") != "completed":
            continue
        seconds = _job_seconds(job)
        digits = job.get("digits")
        engine = job.get("selected_backend")
        if seconds is None or not isinstance(digits, int) or not isinstance(engine, str):
            continue
        considered += 1
        samples.setdefault((engine, ((max(digits, 1) - 1) // 10)), []).append(seconds)
    groups = []
    for (engine, bucket), values in sorted(samples.items()):
        groups.append(
            {
                "engine": engine,
                "digits": _digit_bucket(bucket * 10 + 1),
                "runs": len(values),
                "min_seconds": round(min(values), 3),
                "median_seconds": round(statistics.median(values), 3),
                "mean_seconds": round(statistics.fmean(values), 3),
                "max_seconds": round(max(values), 3),
            }
        )
    return {
        "reference": [dict(row) for row in COMPLEXITY_REFERENCE],
        "groups": groups,
        "measured_jobs": considered,
        "engine": "job history",
        "note": (
            "The reference table lists published asymptotic bounds with citations (heuristic "
            "bounds are marked). Measured timings are wall-clock seconds of completed "
            "factorization jobs grouped by engine and 10-digit input size; they are "
            "bookkeeping over the local job history, not new computation."
        ),
    }
