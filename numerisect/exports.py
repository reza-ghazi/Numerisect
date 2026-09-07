# SPDX-License-Identifier: GPL-3.0-or-later
"""Serialisation of completed results into interchange formats.

This module is presentation only. Every value it writes was already computed by a
native engine and stored by :mod:`numerisect.jobs` or :mod:`numerisect.outputs`;
nothing here performs arithmetic beyond counting rows and formatting strings.

Roadmap item 132 (CSV, JSON, JSON Lines, Markdown, LaTeX, and PARI-compatible
exports).
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Iterable, Sequence

FORMATS = ("json", "jsonl", "csv", "markdown", "latex", "pari")

MEDIA_TYPES = {
    "json": "application/json; charset=utf-8",
    "jsonl": "application/x-ndjson; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "markdown": "text/markdown; charset=utf-8",
    "latex": "application/x-latex; charset=utf-8",
    "pari": "text/plain; charset=utf-8",
}

EXTENSIONS = {
    "json": "json",
    "jsonl": "jsonl",
    "csv": "csv",
    "markdown": "md",
    "latex": "tex",
    "pari": "gp",
}

# Job fields exported as flat columns. Nested values (command history, factors)
# are handled separately so tabular formats stay readable.
JOB_COLUMNS: tuple[str, ...] = (
    "id",
    "expression",
    "number",
    "digits",
    "status",
    "phase",
    "requested_backend",
    "selected_backend",
    "threads",
    "priority",
    "created_at",
    "finished_at",
    "elapsed_seconds",
    "error",
)

FACTOR_COLUMNS: tuple[str, ...] = (
    "value",
    "exponent",
    "status",
    "engine",
    "digits",
    "elapsed_seconds",
)


def normalize_format(value: str | None) -> str:
    """Return a supported format name.

    Args:
        value: Requested format, case-insensitive. ``None`` selects ``json``.

    Returns:
        One of :data:`FORMATS`.

    Raises:
        ValueError: If the format is not supported.
    """

    name = (value or "json").strip().lower()
    aliases = {"md": "markdown", "tex": "latex", "ndjson": "jsonl", "gp": "pari"}
    name = aliases.get(name, name)
    if name not in FORMATS:
        raise ValueError(f"Unsupported export format '{value}'. Use one of: {', '.join(FORMATS)}")
    return name


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _escape_markdown(value: Any) -> str:
    return _text(value).replace("|", "\\|").replace("\n", " ")


def _escape_latex(value: Any) -> str:
    text = _text(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text.replace("\n", " ")


def rows_to_csv(columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    """Render rows as RFC 4180 CSV with a header line."""

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(list(columns))
    for row in rows:
        writer.writerow([_text(cell) for cell in row])
    return buffer.getvalue()


def rows_to_markdown(columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    """Render rows as a GitHub-flavoured Markdown table."""

    lines = [
        "| " + " | ".join(_escape_markdown(name) for name in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_escape_markdown(cell) for cell in row) + " |")
    return "\n".join(lines) + "\n"


def rows_to_latex(columns: Sequence[str], rows: Iterable[Sequence[Any]], caption: str = "") -> str:
    """Render rows as a LaTeX ``tabular`` environment."""

    alignment = "l" * len(columns)
    lines = [
        "\\begin{table}[htbp]",
        "\\centering",
        f"\\begin{{tabular}}{{{alignment}}}",
        "\\hline",
        " & ".join(_escape_latex(name) for name in columns) + " \\\\",
        "\\hline",
    ]
    for row in rows:
        lines.append(" & ".join(_escape_latex(cell) for cell in row) + " \\\\")
    lines.extend(["\\hline", "\\end{tabular}"])
    if caption:
        lines.append(f"\\caption{{{_escape_latex(caption)}}}")
    lines.append("\\end{table}")
    return "\n".join(lines) + "\n"


def _pari_scalar(value: Any) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if text.lstrip("-").isdigit():
        return text
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{escaped}"'


def _pari_map(entries: dict[str, Any]) -> str:
    pairs = ", ".join(f'"{key}", {_pari_scalar(value)}' for key, value in entries.items())
    return f"Map([{pairs}])" if pairs else "Map()"


def job_factor_rows(job: dict[str, Any]) -> list[list[Any]]:
    """Return one row per recorded factor of ``job``."""

    rows: list[list[Any]] = []
    for factor in job.get("factors") or []:
        if not isinstance(factor, dict):
            continue
        rows.append([factor.get(column) for column in FACTOR_COLUMNS])
    return rows


def export_job(job: dict[str, Any], fmt: str) -> str:
    """Serialise one factorization job.

    Args:
        job: Decoded job row, including its ``factors`` list.
        fmt: A name accepted by :func:`normalize_format`.

    Returns:
        The serialised document.
    """

    fmt = normalize_format(fmt)
    summary = {column: job.get(column) for column in JOB_COLUMNS}
    factors = job.get("factors") or []
    if fmt == "json":
        return json.dumps({**summary, "factors": factors}, indent=2, default=str) + "\n"
    if fmt == "jsonl":
        lines = [json.dumps({"record": "job", **summary}, default=str)]
        lines.extend(
            json.dumps({"record": "factor", "job_id": job.get("id"), **factor}, default=str)
            for factor in factors
            if isinstance(factor, dict)
        )
        return "\n".join(lines) + "\n"
    rows = job_factor_rows(job)
    if fmt == "csv":
        header = rows_to_csv(JOB_COLUMNS, [[summary[column] for column in JOB_COLUMNS]])
        if not rows:
            return header
        return header + "\n" + rows_to_csv(FACTOR_COLUMNS, rows)
    if fmt == "markdown":
        parts = [
            f"# Factorization {job.get('id', '')}",
            "",
            rows_to_markdown(
                ("field", "value"), [[column, summary[column]] for column in JOB_COLUMNS]
            ),
        ]
        if rows:
            parts.extend(["", "## Factors", "", rows_to_markdown(FACTOR_COLUMNS, rows)])
        return "\n".join(parts)
    if fmt == "latex":
        parts = [
            rows_to_latex(
                ("field", "value"),
                [[column, summary[column]] for column in JOB_COLUMNS],
                caption=f"Numerisect factorization {job.get('id', '')}",
            )
        ]
        if rows:
            parts.append(rows_to_latex(FACTOR_COLUMNS, rows, caption="Factors"))
        return "\n".join(parts)
    # PARI/GP: an assignable record plus a checkable product.
    values = ", ".join(_pari_scalar(factor.get("value")) for factor in factors if isinstance(factor, dict))
    exponents = ", ".join(
        _pari_scalar(factor.get("exponent", 1)) for factor in factors if isinstance(factor, dict)
    )
    lines = [
        "/* Numerisect factorization export (PARI/GP) */",
        f"N = {_pari_scalar(job.get('number'))};",
        f"job = {_pari_map(summary)};",
        f"factors = [{values}];",
        f"exponents = [{exponents}];",
        "product = prod(i = 1, #factors, factors[i]^exponents[i]);",
        "verified = (product == N);",
        'print("product matches input: ", verified);',
    ]
    return "\n".join(lines) + "\n"


def export_jobs(jobs: Sequence[dict[str, Any]], fmt: str) -> str:
    """Serialise a list of jobs (batch or search results)."""

    fmt = normalize_format(fmt)
    summaries = [{column: job.get(column) for column in JOB_COLUMNS} for job in jobs]
    if fmt == "json":
        return json.dumps(
            {"count": len(jobs), "jobs": [{**s, "factors": j.get("factors") or []}
                                          for s, j in zip(summaries, jobs, strict=False)]},
            indent=2,
            default=str,
        ) + "\n"
    if fmt == "jsonl":
        return "\n".join(json.dumps(summary, default=str) for summary in summaries) + "\n"
    rows = [[summary[column] for column in JOB_COLUMNS] for summary in summaries]
    if fmt == "csv":
        return rows_to_csv(JOB_COLUMNS, rows)
    if fmt == "markdown":
        return f"# Factorization jobs ({len(jobs)})\n\n" + rows_to_markdown(JOB_COLUMNS, rows)
    if fmt == "latex":
        return rows_to_latex(JOB_COLUMNS, rows, caption=f"Numerisect jobs ({len(jobs)})")
    lines = ["/* Numerisect job export (PARI/GP) */", "jobs = ["]
    lines.extend(
        f"  {_pari_map(summary)}{',' if index + 1 < len(summaries) else ''}"
        for index, summary in enumerate(summaries)
    )
    lines.append("];")
    return "\n".join(lines) + "\n"


def export_report_text(filename: str, text: str, fmt: str) -> str:
    """Wrap a saved plain-text report in the requested container format.

    The report body is produced by a native engine; only the container changes.
    """

    fmt = normalize_format(fmt)
    lines = text.splitlines()
    if fmt == "json":
        return json.dumps({"filename": filename, "lines": lines}, indent=2) + "\n"
    if fmt == "jsonl":
        return "\n".join(
            json.dumps({"filename": filename, "line": index + 1, "text": line})
            for index, line in enumerate(lines)
        ) + "\n"
    if fmt == "csv":
        return rows_to_csv(("line", "text"), [[index + 1, line] for index, line in enumerate(lines)])
    if fmt == "markdown":
        return f"# {filename}\n\n```text\n{text.rstrip()}\n```\n"
    if fmt == "latex":
        body = "\n".join(lines)
        return (
            "\\begin{verbatim}\n"
            f"{body}\n"
            "\\end{verbatim}\n"
        )
    escaped = text.rstrip().replace("\\", "\\\\").replace("*/", "*\\/")
    return f"/* Numerisect report {filename}\n{escaped}\n*/\n"
