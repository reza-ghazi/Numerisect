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
