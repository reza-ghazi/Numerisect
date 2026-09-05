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
