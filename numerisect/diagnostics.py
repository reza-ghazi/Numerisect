"""Sanitized local capability diagnostics; no network access or data upload."""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path

from . import __version__
from .config import DEFAULT_CADO_THRESHOLD, MAX_PARALLEL_JOBS, TOOLS_DIR
from .engines import discover_cado_parameters, executable_path
from .installer import ENGINE_SOURCES


def _memory_total() -> str:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                kibibytes = int(line.split()[1])
                return f"{kibibytes / 1024**2:.2f} GiB"
    except (OSError, ValueError, IndexError):
        pass
    return "not reported by this platform"


def system_diagnostics() -> dict[str, object]:
    engines: list[list[str]] = []
    missing: list[str] = []
    for name, source in ENGINE_SOURCES.items():
        resolved = executable_path(source.command)
        if resolved:
            try:
                location = "managed" if Path(resolved).resolve().is_relative_to(TOOLS_DIR.resolve()) else "system"
            except OSError:
                location = "available"
            availability = f"ready ({location})"
        else:
            availability = "missing"
            missing.append(name)
        engines.append(
            [name, availability, source.upstream_ref, source.revision[:12], source.license]
        )
    prerequisites = [
        [command, "ready" if shutil.which(command) else "missing"]
        for command in ("git", "cmake", "make", "pkg-config", "cc", "c++")
    ]
    parameter_sizes = [str(item.size) for item in discover_cado_parameters()]
    metrics = {
        "Numerisect version": __version__,
        "Operating system": f"{platform.system()} {platform.release()}",
        "Architecture": platform.machine() or "unknown",
        "Python interface": platform.python_version(),
        "Logical CPUs": str(os.cpu_count() or 1),
        "Reported memory": _memory_total(),
        "Maximum parallel jobs": str(MAX_PARALLEL_JOBS),
        "Automatic CADO threshold": f"{DEFAULT_CADO_THRESHOLD} digits",
        "CADO parameter sets": ", ".join(parameter_sizes) or "none discovered",
        "Missing native engines": ", ".join(missing) or "none",
    }
    return {
        "metrics": metrics,
        "columns": ["Engine", "Status", "Pinned source", "Revision", "License"],
        "rows": engines,
        "prerequisites": prerequisites,
        "note": (
            "This diagnostic is generated locally and contains no hostname, username, "
            "IP address, absolute path, job input, or calculation result. Nothing is uploaded."
        ),
    }
