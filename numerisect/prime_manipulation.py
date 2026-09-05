"""Validation, GP orchestration, and tabular output for prime manipulation."""

import re

from .primes import PrimeEngineError, _run_gp, _structure_program, _tagged_values


def decimal_integer(text: str) -> int:
    text = text.strip()
    if len(text) > 100_000 or not re.fullmatch(r"[+-]?[0-9]+", text):
        raise ValueError("Enter a decimal integer (up to 100,000 characters)")
    return int(text)


def _execute(call: str, width: int, timeout: int) -> tuple[list[list[str]], list[str]]:
    if not 1 <= timeout <= 3600:
        raise ValueError("Engine time limit must be between 1 and 3,600 seconds")
    lines = _run_gp(f"{_structure_program()}\n{call};", timeout=timeout)
    rows = [line[4:].split("|") for line in lines if line.startswith("ROW:")]
    done = _tagged_values(lines, "DONE")
    if done != [len(rows)] or any(
        len(row) != width or any(not re.fullmatch(r"-?[0-9]+", v) for v in row)
        for row in rows
    ):
        raise PrimeEngineError("PARI/GP returned an incomplete manipulation result")
    return rows, lines


def batch_primality(text: str, mode: str = "proven", timeout: int = 60) -> dict:
    if len(text) > 200_000:
        raise ValueError("Batch input is limited to 200,000 characters")
    tokens = re.split(r"[\s,;]+", text.strip())
    if not 1 <= len(tokens) <= 1000 or mode not in {"proven", "fast"}:
        raise ValueError("Supply 1–1,000 integers and select proven or fast mode")
    values = [decimal_integer(token) for token in tokens]
    vector = "[" + ",".join(map(str, values)) + "]"
    rows, _ = _execute(f"ps_batch_primality({vector},{int(mode == 'fast')})", 2, timeout)
    if len(rows) != len(values) or [row[0] for row in rows] != list(map(str, values)):
        raise PrimeEngineError("PARI/GP did not preserve batch input order")
    labels = {"-1": "Neither prime nor composite", "0": "Composite",
              "1": "Probable prime" if mode == "fast" else "Proven prime"}
    if any(row[1] not in labels for row in rows):
        raise PrimeEngineError("PARI/GP returned an invalid primality status")
    return {
        "columns": ["Integer", "Classification"],
        "rows": [[row[0], labels[row[1]]] for row in rows],
        "note": "Input order and duplicates are preserved. " + (
            "Positive fast-test results are probable primes, not proofs."
            if mode == "fast" else "Every positive result is rigorously proven by PARI/GP."
        ),
    }


def progression_primes(start: str, end: str, modulus: str, residue: str,
                       limit: int = 1000, timeout: int = 60) -> dict:
    lo, hi, m, r = map(decimal_integer, (start, end, modulus, residue))
    if lo > hi or m < 1 or not 1 <= limit <= 100_000:
        raise ValueError("Require start ≤ end, modulus ≥ 1, and result limit 1–100,000")
    rows, lines = _execute(f"ps_progression_primes({lo},{hi},{m},{r},{limit})", 1, timeout)
    tags = {tag: _tagged_values(lines, tag) for tag in ("SUM", "RESIDUE", "NEXT")}
    if any(len(v) != 1 for v in tags.values()) or len(rows) > limit:
        raise PrimeEngineError("PARI/GP returned an incomplete progression summary")
    next_start = tags["NEXT"][0]
    return {
        "columns": ["Proven prime"], "rows": rows,
        "metrics": {"Start (inclusive)": str(lo), "End (inclusive)": str(hi),
                    "Modulus": str(m), "Normalized residue": str(tags["RESIDUE"][0]),
                    "Returned primes": str(len(rows)), "Sum of returned primes": str(tags["SUM"][0])},
        "next_start": str(next_start) if next_start else None,
        "note": "Every returned prime satisfies p ≡ r (mod m) and is proven by PARI/GP. " + (
            f"More results exist. Continue with start = {next_start}; the sum covers only this page."
            if next_start else "The interval scan is complete."
        ),
    }


MODULAR_OPERATIONS = {
    "inverse": (0, "Multiplicative inverse"), "power": (1, "Modular power"),
    "order": (2, "Multiplicative order"), "roots": (3, "Square roots"),
    "generator": (4, "Primitive root"),
}


def prime_modular(modulus: str, value: str, exponent: str = "2",
                  operation: str = "inverse", timeout: int = 60) -> dict:
    if operation not in MODULAR_OPERATIONS:
        raise ValueError("Unknown modular operation")
    p, a, e = map(decimal_integer, (modulus, value, exponent))
    code, label = MODULAR_OPERATIONS[operation]
    rows, _ = _execute(f"ps_prime_modular({p},{a},{e},{code})", 1, timeout)
    if (operation != "roots" and len(rows) != 1) or len(rows) > 2:
        raise PrimeEngineError("PARI/GP returned an unexpected modular result count")
    metrics = {"Prime modulus": str(p), "Operation": label}
    if operation != "generator":
        metrics["Input integer"] = str(a)
    if operation == "power":
        metrics["Exponent"] = str(e)
    return {
        "columns": [label], "rows": rows, "metrics": metrics,
        "note": "The modulus is rigorously proven prime; arithmetic is exact in PARI/GP. " + (
            "No square root exists for this residue." if not rows else
            "All square roots are listed." if operation == "roots" else
            "The primitive root is a generator, not necessarily the smallest one."
            if operation == "generator" else ""
        ),
    }
