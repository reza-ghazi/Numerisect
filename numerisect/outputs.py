from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Iterable

from .config import OUTPUT_DIR
from .installer import ENGINE_SOURCES

# Report-index listeners (workspace tranche). main.py registers the database so
# every saved report is indexed; failures never prevent the report from being saved.
ReportListener = Callable[[dict[str, Any]], None]
_report_listeners: list[ReportListener] = []


def add_report_listener(listener: ReportListener) -> None:
    """Register a callback invoked with ``{filename, kind, summary, job_id}`` per saved report."""

    if listener not in _report_listeners:
        _report_listeners.append(listener)


def _notify_report(filename: str, kind: str, summary: str, job_id: str | None = None) -> None:
    for listener in list(_report_listeners):
        try:
            listener({"filename": filename, "kind": kind, "summary": summary, "job_id": job_id})
        except Exception:  # noqa: BLE001 - indexing must never break persistence
            continue


def _atomic_write(path: Path, content: str) -> Path:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
    return path


def _sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError:
        return None


def _factorization_manifest(
    job: dict[str, Any], factors: list[dict[str, object]], equation: str
) -> dict[str, object]:
    signed_input = f"-{job['number']}" if job["negative"] else str(job["number"])
    used: set[str] = set()
    for factor in factors:
        engine = str(factor.get("engine", ""))
        used.update(name for name in ENGINE_SOURCES if name.lower() in engine.lower())
    selected = str(job["selected_backend"])
    if selected in {"yafu", "hybrid", "cross_verify"} or selected.startswith("yafu_"):
        used.add("YAFU")
    if selected in {"msieve", "cross_verify"}:
        used.add("Msieve")
    if selected in {"cado", "hybrid"}:
        used.add("CADO-NFS")
    engines: list[dict[str, object]] = []
    for name in sorted(used):
        source = ENGINE_SOURCES[name]
        executable = shutil.which(source.command)
        engines.append(
            {
                "name": name,
                "configured_upstream_ref": source.upstream_ref,
                "configured_revision": source.revision,
                "command": source.command,
                "executable_sha256": _sha256_file(Path(executable)) if executable else None,
            }
        )
    return {
        "schema": "org.numerisect.factorization-manifest.v1",
        "job_id": job["id"],
        "parent_job_id": job.get("parent_job_id"),
        "created_at": job["created_at"],
        "finished_at": job.get("finished_at"),
        "expression": job["expression"],
        "input": signed_input,
        "input_sha256": hashlib.sha256(signed_input.encode()).hexdigest(),
        "requested_strategy": job["requested_backend"],
        "selected_strategy": selected,
        "threads": job["threads"],
        "pretest_level": job["pretest_level"],
        "trial_bound": job["trial_bound"],
        "cado_parameter_size": job.get("cado_parameter_size"),
        "commands": job.get("command_history") or [job.get("command") or []],
        "factors": factors,
        "equation_sha256": hashlib.sha256(equation.encode()).hexdigest(),
        "engines": engines,
        "priority": job.get("priority", 0),
        "limits": {
            "cpu_seconds": job.get("cpu_seconds"),
            "memory_mb": job.get("memory_mb"),
            "wall_seconds": job.get("wall_seconds"),
        },
    }


def save_factorization(job: dict[str, Any], factors: list[dict[str, object]]) -> Path:
    filename = f"factorization-{job['id'][:12]}.txt"
    path = OUTPUT_DIR / filename
    signed_number = f"-{job['number']}" if job["negative"] else job["number"]
    values = [str(factor["value"]) for factor in factors]
    equation = f"{signed_number} = {' * '.join(values)}"
    details = "\n".join(
        f"  {factor['value']}  [{factor['status']}, {factor['digits']} digits; "
        f"discovered by {factor.get('engine', job['selected_backend'])}]"
        for factor in factors
    )
    command = " ".join(job.get("command") or [])
    manifest_path = path.with_suffix(".json")
    manifest = _factorization_manifest(job, factors, equation)
    _atomic_write(
        manifest_path,
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    )
    content = (
        "Numerisect result\n"
        "=================\n\n"
        f"Expression: {job['expression']}\n"
        f"Input: {signed_number}\n"
        f"Decimal digits: {job['digits']}\n"
        f"Strategy: {job['selected_backend']}\n"
        f"Status: completed\n\n"
        f"{equation}\n\n"
        f"Factors:\n{details}\n\n"
        f"Last engine command: {command}\n"
        f"Reproducible manifest: output/{manifest_path.name}\n"
        f"Requested strategy: {job['requested_backend']}\n"
        f"CPU threads: {job['threads']}\n"
        f"Trial-division bound: {job['trial_bound']}\n"
        f"CADO parameter set: {job.get('cado_parameter_size') or 'not used'}\n"
        f"Job ID: {job['id']}\n"
        f"Parent job: {job.get('parent_job_id') or 'none'}\n"
        f"Created: {job['created_at']}\n"
        f"Finished: {job.get('finished_at') or ''}\n"
    )
    saved = _atomic_write(path, content)
    _notify_report(
        saved.name, "factorization",
        f"{job['expression']} ({job['digits']} digits, {job['selected_backend']})",
        str(job["id"]),
    )
    return saved


def save_prime_output(kind: str, heading: str, lines: Iterable[str]) -> Path:
    filename = f"{kind}-{uuid.uuid4().hex[:12]}.txt"
    path = OUTPUT_DIR / filename
    content = f"Numerisect · {heading}\n{'=' * (13 + len(heading))}\n\n"
    content += "\n".join(lines) + "\n"
    saved = _atomic_write(path, content)
    _notify_report(saved.name, kind, heading)
    return saved


def native_output_paths(kind: str) -> tuple[Path, Path]:
    filename = f"{kind}-{uuid.uuid4().hex[:12]}.txt"
    final_path = OUTPUT_DIR / filename
    temporary_path = final_path.with_suffix(final_path.suffix + ".tmp")
    return temporary_path, final_path


def finalize_native_output(temporary_path: Path, final_path: Path) -> Path:
    if not temporary_path.is_file():
        raise OSError("The native engine did not create its output file")
    temporary_path.replace(final_path)
    kind = final_path.name.rsplit("-", 1)[0] if "-" in final_path.name else "native"
    _notify_report(final_path.name, kind, "native output streamed directly by the engine")
    return final_path


def safe_output_path(filename: str) -> Path | None:
    if Path(filename).name != filename:
        return None
    path = OUTPUT_DIR / filename
    return path if path.is_file() else None
