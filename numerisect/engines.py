from __future__ import annotations

import math
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import TOOLS_SOURCE_DIR


@dataclass(frozen=True)
class CadoParameter:
    size: int
    path: Path


def executable_path(name: str) -> str | None:
    return shutil.which(name)


def discover_cado_parameters() -> list[CadoParameter]:
    directories = sorted(Path("/usr/local/share").glob("cado-nfs-*/factor"))
    directories += sorted(Path("/usr/share").glob("cado-nfs*/factor"))
    directories += sorted(TOOLS_SOURCE_DIR.glob("cado*nfs*/parameters/factor"))
    found: dict[int, Path] = {}
    for directory in directories:
        for path in directory.glob("params.c*"):
            match = re.fullmatch(r"params\.c(\d+)", path.name)
            if match:
                found[int(match.group(1))] = path
    return [CadoParameter(size, found[size]) for size in sorted(found)]


def select_cado_parameter(
    digits: int,
    parameters: Iterable[CadoParameter],
    requested_size: int | None = None,
) -> CadoParameter:
    available = list(parameters)
    if not available:
        raise RuntimeError("No CADO-NFS factor parameter files were found")
    if requested_size is not None:
        for parameter in available:
            if parameter.size == requested_size:
                return parameter
        raise ValueError(f"CADO parameter size c{requested_size} is not installed")
    for parameter in available:
        if parameter.size >= digits:
            return parameter
    return available[-1]


_YAFU_FACTOR = re.compile(r"^(P|PRP|C|U)(\d+)\s*=\s*(-?\d+)\s*$", re.I)
_MSIEVE_FACTOR = re.compile(r"^(p|prp|c)(\d+):\s*(-?\d+)\s*$", re.I)


def parse_yafu_factors(output: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    in_final_section = False
    for raw_line in output.replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if line == "***factors found***":
            records = []
            in_final_section = True
            continue
        if in_final_section and line.startswith("***"):
            in_final_section = False
        if not in_final_section:
            continue
        match = _YAFU_FACTOR.fullmatch(line)
        if not match:
            continue
        kind = match.group(1).upper()
        value = match.group(3)
        status = {
            "P": "prime",
            "PRP": "probable_prime",
            "C": "composite",
            "U": "unknown",
        }[kind]
        records.append(
            {"value": value, "digits": int(match.group(2)), "status": status}
        )
    return records


def parse_msieve_factors(output: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for raw_line in output.splitlines():
        match = _MSIEVE_FACTOR.fullmatch(raw_line.strip())
        if not match:
            continue
        kind = match.group(1).lower()
        status = {"p": "prime", "prp": "probable_prime", "c": "composite"}[kind]
        records.append(
            {
                "value": match.group(3),
                "digits": int(match.group(2)),
                "status": status,
            }
        )
    return records


def parse_cado_factors(output: str, target: int) -> list[dict[str, object]]:
    candidates: list[list[int]] = []
    for raw_line in output.replace("\r", "\n").splitlines():
        line = raw_line.strip()
        match = re.search(r"\bFactors:\s*((?:\d+\s+)*\d+)\s*$", line)
        text = match.group(1) if match else line
        if not re.fullmatch(r"\d+(?:\s+\d+)+", text):
            continue
        values = [int(value) for value in text.split()]
        if math.prod(values) == target:
            candidates.append(values)
    if not candidates:
        return []
    return [
        {
            "value": str(value),
            "digits": len(str(abs(value))),
            "status": "probable_prime",
        }
        for value in candidates[-1]
    ]


def prime_factor_product(records: Iterable[dict[str, object]]) -> int:
    product = 1
    for record in records:
        if record.get("status") in {"prime", "probable_prime"}:
            product *= abs(int(str(record["value"])))
    return product


def product_is_complete(records: Iterable[dict[str, object]], number: int) -> bool:
    values = [abs(int(str(record["value"]))) for record in records]
    return bool(values) and math.prod(values) == abs(number)


def cado_parameter_warning(digits: int, parameter: CadoParameter) -> str | None:
    if parameter.size == digits:
        return None
    if parameter.size < digits:
        return (
            f"No parameters at or above {digits} digits are installed; using the largest "
            f"available set, c{parameter.size}. Expert review is recommended."
        )
    return f"Using the next installed CADO parameter set, c{parameter.size}, for a c{digits} input."

# GMP-ECM reports a discovered factor on its own line, then classifies it and the
# cofactor. The classification lines are what give prime/composite status; the
# "Factor found" line alone does not.
_ECM_FACTOR_FOUND = re.compile(r"Factor found in step \d+:\s*(\d+)")
_ECM_CLASSIFIED = re.compile(
    r"Found (prime|probable prime|composite) factor of \s*\d+ digits:\s*(\d+)", re.I
)
_ECM_COFACTOR = re.compile(
    r"(Prime|Probable prime|Composite) cofactor\s+(\d+)\s+has", re.I
)
_ECM_CURVE = re.compile(r"Run (\d+) out of (\d+)")
_ECM_SIGMA = re.compile(r"sigma=([0-9:]+)")


def parse_ecm_output(output: str) -> dict[str, object]:
    """Parse GMP-ECM output into factors, cofactor, and campaign progress.

    GMP-ECM decides primality of the factor and cofactor itself and prints it;
    this function only reads those decisions.

    Args:
        output: Combined stdout/stderr from ``ecm``.

    Returns:
        ``{"factors": [...], "cofactor": str | None, "curves_run": int,
        "curves_requested": int, "sigmas": [...]}``.
    """

    status_map = {
        "prime": "prime",
        "probable prime": "probable_prime",
        "composite": "composite",
    }
    factors: list[dict[str, object]] = []
    seen: set[str] = set()
    cofactor: str | None = None
    curves_run = 0
    curves_requested = 0
    sigmas: list[str] = []
    text = output.replace("\r", "\n")

    for match in _ECM_CURVE.finditer(text):
        curves_run = max(curves_run, int(match.group(1)))
        curves_requested = max(curves_requested, int(match.group(2)))
    for match in _ECM_SIGMA.finditer(text):
        sigmas.append(match.group(1))

    for match in _ECM_CLASSIFIED.finditer(text):
        kind, value = match.group(1).lower(), match.group(2)
        if value in seen:
            continue
        seen.add(value)
        factors.append(
            {
                "value": value,
                "digits": len(value),
                "status": status_map.get(kind, "composite"),
                "engine": "GMP-ECM",
            }
        )
    # A factor announced but never classified is still a factor of unknown status.
    for match in _ECM_FACTOR_FOUND.finditer(text):
        value = match.group(1)
        if value not in seen:
            seen.add(value)
            factors.append(
                {
                    "value": value,
                    "digits": len(value),
                    "status": "unknown",
                    "engine": "GMP-ECM",
                }
            )

    cofactor_match = _ECM_COFACTOR.search(text)
    if cofactor_match:
        cofactor = cofactor_match.group(2)
    return {
        "factors": factors,
        "cofactor": cofactor,
        "curves_run": curves_run,
        "curves_requested": curves_requested,
        "sigmas": sigmas,
    }



#: Msieve's own polynomial-selection options, verified against `msieve -h`. They are
#: passed as one parameter string after the stage flag, which is how Msieve takes them.
MSIEVE_POLYSELECT_PARAMETERS: dict[str, tuple[str, int, int]] = {
    "degree": ("polydegree", 4, 6),
    "min_coeff": ("min_coeff", 1, 10**18),
    "max_coeff": ("max_coeff", 1, 10**18),
    "stage1_norm": ("stage1_norm", 1, 10**30),
    "stage2_norm": ("stage2_norm", 1, 10**30),
    "min_evalue": ("min_evalue", 1, 10**30),
    "deadline": ("poly_deadline", 1, 86400),
}

#: The stage flags. Only `full` yields a finished polynomial; the others are the
#: individual stages, useful for splitting a long selection or inspecting its parts.
MSIEVE_POLYSELECT_STAGES: dict[str, str] = {
    "full": "-np",
    "stage1": "-np1",
    "size": "-nps",
    "root": "-npr",
}

#: CADO-NFS polynomial-selection keys, verified against the installed `params.cNN`
#: files. Values are passed as `tasks.polyselect.<key>=<value>` overrides, which
#: cado-nfs.py accepts on the command line.
CADO_POLYSELECT_PARAMETERS: dict[str, tuple[float, float]] = {
    "degree": (4, 6),
    "P": (100, 10**9),
    "admin": (0, 10**15),
    "admax": (1, 10**15),
    "incr": (1, 10**6),
    "nrkeep": (1, 10_000),
    "adrange": (1, 10**12),
    "nq": (1, 10**6),
    "sopteffort": (0, 100),
    "ropteffort": (0, 100),
}


def validate_msieve_polyselect_parameters(options: dict[str, object]) -> str:
    """Render Msieve's selection options as the single parameter string it expects.

    Args:
        options: Request fields keyed by the names in
            :data:`MSIEVE_POLYSELECT_PARAMETERS`; ``None`` values are ignored.

    Returns:
        The parameter string, empty when nothing was requested.

    Raises:
        ValueError: If a field is unknown, not an integer, out of range, or if the
            coefficient range is inverted.
    """

    parts: list[str] = []
    numbers: dict[str, int] = {}
    for field, value in options.items():
        if value is None:
            continue
        if field not in MSIEVE_POLYSELECT_PARAMETERS:
            raise ValueError(f"'{field}' is not a supported Msieve polyselect parameter")
        key, low, high = MSIEVE_POLYSELECT_PARAMETERS[field]
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"'{field}' must be an integer") from exc
        if not low <= number <= high:
            raise ValueError(f"'{field}' must be between {low:,} and {high:,}")
        numbers[field] = number
        parts.append(f"{key}={number}")
    if "min_coeff" in numbers and "max_coeff" in numbers:
        if numbers["min_coeff"] > numbers["max_coeff"]:
            raise ValueError("min_coeff must not exceed max_coeff")
    return " ".join(parts)


#: CADO-NFS's own workflow stages, in the order its harness runs them for a
#: factorization, with the parameter that disables each one and a human label.
#:
#: Every CADO task accepts a `run` parameter, and setting it false makes the harness
#: stop *at* that task — it logs "Stopping at <task>", finishes with status 0, and
#: leaves everything before it complete in the working directory. A later invocation on
#: the same working directory continues from there, because CADO's own state database
#: records which tasks have run. So running the stages one at a time needs no
#: reimplementation of the upstream harness: it is a parameter, and the stage after the
#: one requested is the one disabled.
#:
#: Verified on this workstation against CADO-NFS 3.0.0 with a 60-digit input: a run
#: gated at `sieving` stopped after polynomial selection, a second run on the same
#: working directory gated at `purge` sieved and removed duplicates, and a third with
#: no gate finished and returned both 30-digit primes.
CADO_STAGES: tuple[tuple[str, str, str], ...] = (
    ("polyselect_size", "tasks.polyselect.polyselect1.run",
     "Polynomial selection, size optimization"),
    ("polyselect_root", "tasks.polyselect.polyselect2.run",
     "Polynomial selection, root optimization"),
    ("factorbase", "tasks.sieve.factorbase.run", "Factor base generation"),
    ("freerel", "tasks.sieve.freerel.run", "Free relations"),
    ("sieving", "tasks.sieve.sieving.run", "Lattice sieving"),
    ("duplicates1", "tasks.filter.duplicates1.run", "Duplicate removal, pass 1"),
    ("duplicates2", "tasks.filter.duplicates2.run", "Duplicate removal, pass 2"),
    ("purge", "tasks.filter.purge.run", "Singleton removal"),
    ("merge", "tasks.filter.mergetask.run", "Matrix merging"),
    ("linalg", "tasks.linalg.linalg.run", "Linear algebra"),
    ("characters", "tasks.linalg.characters.run", "Quadratic characters"),
    ("sqrt", "tasks.sqrt.sqrt.run", "Square root, and the factors"),
)

#: The stage slugs in order, for validation and for comparing two stages.
CADO_STAGE_ORDER: tuple[str, ...] = tuple(slug for slug, _, _ in CADO_STAGES)


def cado_stage_label(stage: str) -> str:
    """The human label for a stage slug."""

    for slug, _, label in CADO_STAGES:
        if slug == stage:
            return label
    raise ValueError(f"'{stage}' is not a CADO-NFS workflow stage")


def cado_stage_gate(stage: str) -> str | None:
    """The assignment that stops CADO after ``stage``.

    Returns:
        ``tasks.<path>.<task>.run=false`` for the stage *following* the requested one,
        or ``None`` when the requested stage is the last, since a run that reaches the
        square root is an ordinary complete factorization.

    Raises:
        ValueError: If the stage is not one of :data:`CADO_STAGES`.
    """

    if stage not in CADO_STAGE_ORDER:
        raise ValueError(f"'{stage}' is not a CADO-NFS workflow stage")
    index = CADO_STAGE_ORDER.index(stage)
    if index + 1 >= len(CADO_STAGES):
        return None
    return f"{CADO_STAGES[index + 1][1]}=false"


#: What CADO prints as each stage finishes. Each pattern reads one fact out of its own
#: log line; nothing here is computed.
_CADO_STOPPED = re.compile(r"Stopping at (\w+)")
_CADO_STAGE_START = re.compile(r"^Info:([^:]+): Starting$", re.M)
_CADO_MURPHY = re.compile(
    r"(?:Finished, best polynomial has|Best polynomial previously has) "
    r"Murphy_E = ([0-9.e+-]+)"
)
_CADO_FREE = re.compile(r"Found (\d+) free relations")
_CADO_RELATIONS = re.compile(r"Total number of relations: (\d+)")
_CADO_UNIQUE = re.compile(r"(\d+) unique relations remain in total")
_CADO_PURGED = re.compile(
    r"After purge, (\d+) relations with (\d+) primes remain with weight (\d+)"
)
_CADO_MATRIX = re.compile(r"Merged matrix has (\d+) rows and total weight (\d+)")


def parse_cado_stage_report(output: str) -> dict[str, object]:
    """Read what a staged CADO run achieved out of its own log.

    Args:
        output: The combined output of one `cado-nfs.py` invocation.

    Returns:
        A mapping with ``stopped_at`` (the task the gate halted, or ``None`` for a run
        that was not gated), ``stages`` (the task titles that started, in order), and
        whichever of ``murphy_e``, ``free_relations``, ``relations``,
        ``unique_relations``, ``purged_relations``, ``purged_primes``,
        ``purged_weight``, ``matrix_rows`` and ``matrix_weight`` the run printed. A
        value that was not printed is absent rather than zero.
    """

    plain = re.sub(r"\x1b\[[0-9;]*m", "", output)
    stopped = _CADO_STOPPED.search(plain)
    report: dict[str, object] = {
        "stopped_at": stopped.group(1) if stopped else None,
        "stages": _CADO_STAGE_START.findall(plain),
    }
    single = {
        "murphy_e": _CADO_MURPHY,
        "free_relations": _CADO_FREE,
        "relations": _CADO_RELATIONS,
        "unique_relations": _CADO_UNIQUE,
    }
    for key, pattern in single.items():
        found = pattern.findall(plain)
        if found:
            report[key] = found[-1]
    purged = _CADO_PURGED.findall(plain)
    if purged:
        relations, primes, weight = purged[-1]
        report.update(
            purged_relations=relations, purged_primes=primes, purged_weight=weight
        )
    matrix = _CADO_MATRIX.findall(plain)
    if matrix:
        rows, weight = matrix[-1]
        report.update(matrix_rows=rows, matrix_weight=weight)
    return report


def validate_cado_polyselect_parameters(options: dict[str, object]) -> list[str]:
    """Render CADO polynomial-selection overrides as `key=value` arguments.

    Raises:
        ValueError: If a key is unknown, not numeric, out of range, or if the leading
            coefficient range is inverted.
    """

    assignments: list[str] = []
    numbers: dict[str, float] = {}
    for key, value in options.items():
        if value is None:
            continue
        if key not in CADO_POLYSELECT_PARAMETERS:
            raise ValueError(f"'{key}' is not a supported CADO polyselect parameter")
        low, high = CADO_POLYSELECT_PARAMETERS[key]
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"'{key}' must be a number") from exc
        if not low <= number <= high:
            raise ValueError(f"'{key}' must be between {low:g} and {high:g}")
        numbers[key] = number
        # Integral values are written without a decimal point: CADO reads both, and the
        # parameter files use plain integers everywhere except the effort knobs.
        rendered = f"{number:g}" if number != int(number) else str(int(number))
        assignments.append(f"tasks.polyselect.{key}={rendered}")
    if "admin" in numbers and "admax" in numbers and numbers["admin"] >= numbers["admax"]:
        raise ValueError("admin must be below admax")
    return assignments


def parse_msieve_polynomial(output: str) -> dict[str, object]:
    """Read the polynomial, its quality metrics and the candidate count from Msieve.

    Only the full selection prints a finished polynomial; the individual stages print
    saved candidates instead, so a missing polynomial is reported as such rather than
    inferred.

    Returns:
        ``{"complete", "skew", "rational", "algebraic", "degree", "size", "alpha",
        "combined", "rroots", "candidates"}``.
    """

    rational: dict[int, str] = {}
    algebraic: dict[int, str] = {}
    quality: dict[str, str] = {}
    candidates = 0
    complete = False
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("save "):
            candidates += 1
            continue
        if stripped == "polynomial selection complete":
            complete = True
            continue
        rational_match = re.fullmatch(r"R(\d+)[: ]\s*(-?\d+)", stripped)
        if rational_match:
            rational[int(rational_match.group(1))] = rational_match.group(2)
            continue
        algebraic_match = re.fullmatch(r"A(\d+)[: ]\s*(-?\d+)", stripped)
        if algebraic_match:
            algebraic[int(algebraic_match.group(1))] = algebraic_match.group(2)
            continue
        summary = re.fullmatch(
            r"skew ([\d.]+), size ([\d.eE+-]+), alpha (-?[\d.]+), "
            r"combined = ([\d.eE+-]+) rroots = (\d+)",
            stripped,
        )
        if summary:
            quality = {
                "skew": summary.group(1),
                "size": summary.group(2),
                "alpha": summary.group(3),
                "combined": summary.group(4),
                "rroots": summary.group(5),
            }
    return {
        "complete": complete,
        "skew": quality.get("skew"),
        "rational": [rational[index] for index in sorted(rational)],
        "algebraic": [algebraic[index] for index in sorted(algebraic)],
        "degree": (max(algebraic) if algebraic else None),
        "size": quality.get("size"),
        "alpha": quality.get("alpha"),
        "combined": quality.get("combined"),
        "rroots": quality.get("rroots"),
        "candidates": candidates,
    }
