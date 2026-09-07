"""Application infrastructure: batch import, workspaces, result cache, setup log.

Python only validates, orchestrates PARI/GP for range and polynomial-family
expansion, and persists state.  No arithmetic is performed here.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from .config import (
    MAX_BATCH_IMPORT_ITEMS,
    MAX_BATCH_RANGE_SPAN,
    MAX_RESULT_DIGITS,
    PACKAGE_DIR,
    RESULT_CACHE_MAX_BYTES,
)
from .evaluator import ExpressionError, evaluate_arbitrary_integer
from .installer import ENGINE_SOURCES
from .primes import PrimeEngineError, _run_gp

PROGRAM = PACKAGE_DIR / "workspace.gp"
MAX_IMPORT_BYTES = 2_000_000
FAMILY_SYNTAX = re.compile(
    r"^(?P<poly>[0-9n+\-*^() ]+?)\s+for\s+n\s*(?:=|in)\s*(?P<start>[^.]+?)\.\.(?P<end>.+)$",
    re.IGNORECASE,
)
RANGE_SYNTAX = re.compile(r"^(?P<start>[^.]+?)\.\.(?P<end>[^.]+)$")
POLY_TEXT = re.compile(r"[0-9n+\-*^() ]{1,200}")
POLY_EXPONENT = re.compile(r"\^\s*(\d{1,3})")
POLY_BAD_EXPONENT = re.compile(r"\^\s*[^\d\s]")
MAX_FAMILY_EXPONENT = 64
WORKSPACE_NAME = re.compile(r"[^\x00-\x1f]{1,120}")
REPORT_FILENAME = re.compile(r"[A-Za-z0-9._-]{1,200}")


def _program() -> str:
    try:
        return PROGRAM.read_text(encoding="utf-8")
    except OSError as exc:
        raise PrimeEngineError("The workspace PARI/GP program is unavailable") from exc


# --------------------------------------------------------------------------- batch import


def parse_batch_document(content: str, fmt: str = "auto", filename: str | None = None) -> list[str]:
    """Split TXT/CSV/JSON batch input into raw item strings.

    Args:
        content: The uploaded text.
        fmt: ``auto``, ``txt``, ``csv``, or ``json``.  ``auto`` uses the file
            extension when available and otherwise sniffs JSON.
        filename: Optional original filename (used only for its extension).

    Returns:
        Non-empty item strings in document order (comments starting with ``#``
        are skipped in TXT/CSV input).

    Raises:
        ValueError: On oversized, malformed, or empty input.
    """

    if len(content.encode("utf-8", errors="replace")) > MAX_IMPORT_BYTES:
        raise ValueError("Batch input is limited to 2,000,000 bytes")
    if fmt not in {"auto", "txt", "csv", "json"}:
        raise ValueError("Batch format must be auto, txt, csv, or json")
    if fmt == "auto":
        suffix = Path(filename or "").suffix.lower()
        if suffix == ".json" or content.lstrip().startswith(("[", "{")):
            fmt = "json"
        elif suffix == ".csv":
            fmt = "csv"
        else:
            fmt = "txt"
    items: list[str] = []
    if fmt == "json":
        try:
            document = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Batch JSON is invalid: {exc.msg}") from exc
        if isinstance(document, dict):
            document = document.get("items", document.get("expressions"))
        if not isinstance(document, list):
            raise ValueError("Batch JSON must be an array or an object with an 'items' array")
        for entry in document:
            if isinstance(entry, bool) or not isinstance(entry, (str, int)):
                raise ValueError("Batch JSON items must be strings or integers")
            text = str(entry).strip()
            if text:
                items.append(text)
    elif fmt == "csv":
        reader = csv.reader(io.StringIO(content))
        for row in reader:
            for cell in row:
                text = cell.strip()
                if text and not text.startswith("#"):
                    items.append(text)
    else:
        for line in content.splitlines():
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            if FAMILY_SYNTAX.match(text) or RANGE_SYNTAX.match(text):
                items.append(text)
            else:
                items.extend(part.strip() for part in re.split(r"[;,]", text) if part.strip())
    if not items:
        raise ValueError("The batch document contains no items")
    if len(items) > MAX_BATCH_IMPORT_ITEMS:
        raise ValueError(f"Batch input is limited to {MAX_BATCH_IMPORT_ITEMS:,} items before expansion")
    return items


def _validate_polynomial(poly: str) -> str:
    text = poly.strip()
    if not POLY_TEXT.fullmatch(text):
        raise ValueError("Polynomial families may use digits, n, + - * ^ and parentheses only")
    depth = 0
    for char in text:
        depth += char == "("
        depth -= char == ")"
        if depth < 0:
            raise ValueError("Unbalanced parentheses in polynomial family")
    if depth:
        raise ValueError("Unbalanced parentheses in polynomial family")
    if POLY_BAD_EXPONENT.search(text):
        raise ValueError("Exponents in polynomial families must be integer literals")
    for match in POLY_EXPONENT.finditer(text):
        if int(match.group(1)) > MAX_FAMILY_EXPONENT:
            raise ValueError(f"Polynomial exponents are limited to {MAX_FAMILY_EXPONENT}")
    if "**" in text:
        raise ValueError("Use ^ for exponentiation in polynomial families")
    return text


def classify_batch_item(text: str) -> dict[str, Any]:
    """Classify one item as integer, expression, range, or polynomial family.

    Returns:
        A mapping with ``kind`` and the validated components: ``value`` for
        integers/expressions (decimal string), or ``start``/``end`` (ints) and
        ``polynomial`` for ranges and families.
    """

    item = text.strip()
    family = FAMILY_SYNTAX.match(item)
    if family:
        polynomial = _validate_polynomial(family.group("poly"))
        start, end = _range_bounds(family.group("start"), family.group("end"))
        return {"kind": "family", "polynomial": polynomial, "start": start, "end": end, "source": item}
    range_match = RANGE_SYNTAX.match(item)
    if range_match:
        start, end = _range_bounds(range_match.group("start"), range_match.group("end"))
        return {"kind": "range", "polynomial": "n", "start": start, "end": end, "source": item}
    try:
        value = evaluate_arbitrary_integer(item)
    except ExpressionError as exc:
        raise ValueError(f"'{item[:60]}' is not an integer, expression, range, or family: {exc}") from exc
    kind = "integer" if re.fullmatch(r"[+-]?\d+", item) else "expression"
    return {"kind": kind, "value": str(value), "source": item}


def _range_bounds(start_text: str, end_text: str) -> tuple[int, int]:
    try:
        start = evaluate_arbitrary_integer(start_text)
        end = evaluate_arbitrary_integer(end_text)
    except ExpressionError as exc:
        raise ValueError(f"Range bounds must be integer expressions: {exc}") from exc
    if end < start:
        raise ValueError("Range end must not precede its start")
    if end - start + 1 > MAX_BATCH_RANGE_SPAN:
        raise ValueError(f"Ranges and families are limited to {MAX_BATCH_RANGE_SPAN:,} values each")
    return start, end


def expand_batch_items(
    items: list[str], *, max_total: int = MAX_BATCH_IMPORT_ITEMS, timeout: int = 60
) -> dict[str, Any]:
    """Expand raw items into decimal integers; ranges and families run in PARI/GP.

    Args:
        items: Raw strings from :func:`parse_batch_document`.
        max_total: Upper bound on the expanded list.
        timeout: PARI/GP time limit in seconds.

    Returns:
        ``{"values": [...], "classified": [...], "expanded_count": n}`` where each
        value is a decimal string in input order.
    """

    if not 1 <= timeout <= 3600:
        raise ValueError("Engine time limit must be between 1 and 3,600 seconds")
    classified = [classify_batch_item(item) for item in items]
    projected = sum(
        (entry["end"] - entry["start"] + 1) if entry["kind"] in {"range", "family"} else 1
        for entry in classified
    )
    if projected > max_total:
        raise ValueError(f"The expanded batch would contain {projected:,} values; the limit is {max_total:,}")
    calls: list[str] = []
    for index, entry in enumerate(classified):
        if entry["kind"] in {"range", "family"}:
            calls.append(
                f"ws_expand({index},(n)->{entry['polynomial']},{entry['start']},{entry['end']},"
                f"{MAX_BATCH_RANGE_SPAN},{MAX_RESULT_DIGITS})"
            )
    expanded: dict[int, list[str]] = {}
    if calls:
        lines = _run_gp(f"{_program()}\n" + ";".join(calls) + ";", timeout=timeout)
        counts: dict[int, int] = {}
        for line in lines:
            if line.startswith("ITEM:"):
                index_text, value = line.removeprefix("ITEM:").split("|", 1)
                if not re.fullmatch(r"-?\d+", value.strip()):
                    raise PrimeEngineError("PARI/GP returned a non-integer family value")
                expanded.setdefault(int(index_text), []).append(value.strip())
            elif line.startswith("EXPANDED:"):
                index_text, count = line.removeprefix("EXPANDED:").split("|", 1)
                counts[int(index_text)] = int(count)
        for index, entry in enumerate(classified):
            if entry["kind"] in {"range", "family"}:
                produced = len(expanded.get(index, []))
                if counts.get(index) != produced or produced != entry["end"] - entry["start"] + 1:
                    raise PrimeEngineError("PARI/GP returned an incomplete family expansion")
    values: list[str] = []
    for index, entry in enumerate(classified):
        if entry["kind"] in {"range", "family"}:
            values.extend(expanded[index])
        else:
            values.append(entry["value"])
    return {"values": values, "classified": classified, "expanded_count": len(values)}


# --------------------------------------------------------------------------- workspaces


def validate_workspace_fields(
    *,
    name: str | None,
    notes: str | None,
    job_ids: list[str] | None,
    report_files: list[str] | None,
    ui_state: dict[str, Any] | None,
) -> dict[str, Any]:
    """Validate workspace fields and return only those that were supplied."""

    result: dict[str, Any] = {}
    if name is not None:
        if not WORKSPACE_NAME.fullmatch(name.strip()):
            raise ValueError("Workspace names must be 1–120 printable characters")
        result["name"] = name.strip()
    if notes is not None:
        if len(notes) > 20_000:
            raise ValueError("Workspace notes are limited to 20,000 characters")
        result["notes"] = notes
    if job_ids is not None:
        if len(job_ids) > 500 or any(not re.fullmatch(r"[0-9a-f]{32}", item) for item in job_ids):
            raise ValueError("Workspaces hold up to 500 job identifiers (32 hex characters each)")
        result["job_ids"] = list(dict.fromkeys(job_ids))
    if report_files is not None:
        if len(report_files) > 500 or any(
            not REPORT_FILENAME.fullmatch(item) or Path(item).name != item for item in report_files
        ):
            raise ValueError("Workspaces hold up to 500 bare report filenames")
        result["report_files"] = list(dict.fromkeys(report_files))
    if ui_state is not None:
        encoded = json.dumps(ui_state)
        if len(encoded) > 20_000:
            raise ValueError("Workspace UI state is limited to 20,000 JSON characters")
        result["ui_state"] = ui_state
    return result


def new_workspace_id() -> str:
    return uuid.uuid4().hex


# --------------------------------------------------------------------------- result cache


INCONCLUSIVE_FLAGS = {"truncated", "incomplete", "timed_out", "inconclusive", "limit_reached"}
INCONCLUSIVE_VALUES = {"inconclusive", "unknown", "incomplete", "timed out", "undecided"}
VERDICT_KEYS = {"status", "verdict", "classification", "result", "conclusion", "outcome"}


def payload_is_conclusive(payload: Any, depth: int = 0) -> bool:
    """Return ``False`` when a response carries any inconclusive marker.

    The check is deliberately conservative: unknown structures are treated as
    conclusive only when no recognised flag or verdict text signals a timeout,
    truncation, or open question.
    """

    if depth > 6:
        return True
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = str(key).lower()
            if lowered in INCONCLUSIVE_FLAGS and bool(value):
                return False
            if lowered in VERDICT_KEYS and isinstance(value, str) and value.lower() in INCONCLUSIVE_VALUES:
                return False
            if lowered == "note" and isinstance(value, str):
                text = value.lower()
                if "inconclusive" in text or "timed out" in text or "time limit" in text:
                    return False
            if not payload_is_conclusive(value, depth + 1):
                return False
        return True
    if isinstance(payload, list):
        return all(payload_is_conclusive(item, depth + 1) for item in payload[:2000])
    return True


def _sha256_file(path: Path | None) -> str:
    if not path:
        return "absent"
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return "unreadable"
    return digest.hexdigest()


ENGINE_GROUPS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "/api/primes/": (
        ("gp", "primesieve", "primecount"),
        ("prime_classifier.gp", "prime_reciprocal.gp", "prime_structures.gp"),
    ),
    "/api/number-theory/": (("gp",), ("number_theory.gp",)),
    "/api/zeta/": (("numerisect-zeta",), ()),
}


class EngineFingerprints:
    """Cache engine executable/program hashes for a short time-to-live."""

    def __init__(self, ttl_seconds: float = 60.0):
        self.ttl = ttl_seconds
        self._cache: dict[str, tuple[float, str, str]] = {}

    def for_path(self, path: str) -> tuple[str, str] | None:
        """Return ``(engine_label, revision)`` for a cacheable API path."""

        for prefix, (_commands, _programs) in ENGINE_GROUPS.items():
            if path.startswith(prefix):
                break
        else:
            return None
        cached = self._cache.get(prefix)
        now = time.monotonic()
        if cached and now - cached[0] < self.ttl:
            return cached[1], cached[2]
        parts: list[str] = []
        labels: list[str] = []
        for command in _commands:
            executable = shutil.which(command)
            parts.append(f"{command}={_sha256_file(Path(executable) if executable else None)}")
            for name, source in ENGINE_SOURCES.items():
                if source.command == command:
                    parts.append(f"{name}@{source.revision}")
                    labels.append(name)
        for program in _programs:
            parts.append(f"{program}={_sha256_file(PACKAGE_DIR / program)}")
        revision = hashlib.sha256("\n".join(parts).encode()).hexdigest()
        label = ", ".join(dict.fromkeys(labels)) or ", ".join(_commands)
        self._cache[prefix] = (now, label, revision)
        return label, revision


def canonical_parameters(body: bytes) -> tuple[dict[str, Any], bool] | None:
    """Decode a JSON request body into canonical parameters.

    Returns:
        ``(parameters, use_cache)`` with ``use_cache`` removed from the parameters,
        or ``None`` when the body is not a JSON object.
    """

    if not body:
        return {}, True
    try:
        decoded = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(decoded, dict):
        return None
    use_cache = decoded.pop("use_cache", True)
    if not isinstance(use_cache, bool):
        use_cache = str(use_cache).lower() not in {"0", "false", "no", "off"}
    return decoded, use_cache


def cache_key(operation: str, parameters: dict[str, Any], engine_revision: str) -> str:
    canonical = json.dumps(parameters, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"{operation}\n{canonical}\n{engine_revision}".encode()).hexdigest()


def response_is_cacheable(payload: Any, encoded_length: int) -> bool:
    return (
        isinstance(payload, dict)
        and encoded_length <= RESULT_CACHE_MAX_BYTES
        and "detail" not in payload
        and payload_is_conclusive(payload)
    )

def verify_claimed_factors(number: int, factors: list[str], timeout: int = 60) -> dict[str, Any]:
    """Verify externally claimed factors with PARI/GP.

    Divisibility, primality, the product check, and the cofactor are all decided by
    the native engine; Python only validates input and parses the tagged reply.

    Args:
        number: The integer the claims are about.
        factors: Claimed decimal factors.
        timeout: PARI/GP time limit in seconds.

    Returns:
        ``{"factors": [{"factor", "prime", "divides"}], "product_matches": bool,
        "cofactor": str}``.

    Raises:
        ValueError: If a claimed factor is not a nonzero decimal integer.
        PrimeEngineError: If the engine fails or returns an incomplete result.
    """

    cleaned: list[str] = []
    for value in factors:
        text = str(value).strip()
        if not re.fullmatch(r"-?\d{1,400}", text) or text.lstrip("-").strip("0") == "":
            raise ValueError(f"'{value}' is not a nonzero decimal integer")
        cleaned.append(text)
    if not cleaned:
        return {"factors": [], "product_matches": False, "cofactor": "0"}
    call = f"ws_verify_factors({number},[{','.join(cleaned)}])"
    lines = _run_gp(f"{_program()}\n{call};", timeout=timeout)
    rows: list[dict[str, Any]] = []
    product_matches = False
    cofactor = "0"
    complete = False
    for line in lines:
        if line.startswith("FACTOR:"):
            parts = line[len("FACTOR:"):].split("|")
            if len(parts) == 3:
                rows.append(
                    {"factor": parts[0], "prime": parts[1] == "1", "divides": parts[2] == "1"}
                )
        elif line.startswith("PRODUCT_MATCH:"):
            product_matches = line.split(":", 1)[1].strip() == "1"
        elif line.startswith("COFACTOR:"):
            cofactor = line.split(":", 1)[1].strip()
        elif line.startswith("DONE:"):
            complete = True
    if not complete or len(rows) != len(cleaned):
        raise PrimeEngineError("PARI/GP did not return a complete verification result")
    return {"factors": rows, "product_matches": product_matches, "cofactor": cofactor}
