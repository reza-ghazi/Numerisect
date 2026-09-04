from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Iterable

from .config import OUTPUT_DIR


def _atomic_write(path: Path, content: str) -> Path:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
    return path


def save_factorization(job: dict[str, Any], factors: list[dict[str, object]]) -> Path:
    filename = f"factorization-{job['id'][:12]}.txt"
    path = OUTPUT_DIR / filename
    signed_number = f"-{job['number']}" if job["negative"] else job["number"]
    values = [str(factor["value"]) for factor in factors]
    equation = f"{signed_number} = {' * '.join(values)}"
    details = "\n".join(
        f"  {factor['value']}  [{factor['status']}, {factor['digits']} digits]"
        for factor in factors
    )
    command = " ".join(job.get("command") or [])
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
        f"Job ID: {job['id']}\n"
        f"Created: {job['created_at']}\n"
        f"Finished: {job.get('finished_at') or ''}\n"
    )
    return _atomic_write(path, content)


def save_prime_output(kind: str, heading: str, lines: Iterable[str]) -> Path:
    filename = f"{kind}-{uuid.uuid4().hex[:12]}.txt"
    path = OUTPUT_DIR / filename
    content = f"Numerisect · {heading}\n{'=' * (13 + len(heading))}\n\n"
    content += "\n".join(lines) + "\n"
    return _atomic_write(path, content)


def safe_output_path(filename: str) -> Path | None:
    if Path(filename).name != filename:
        return None
    path = OUTPUT_DIR / filename
    return path if path.is_file() else None
