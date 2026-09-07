# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional, explicitly permissioned external catalogue lookups.

Numerisect is offline by default. Every function here refuses to touch the
network unless BOTH of the following hold:

1. the process was started with ``NUMERISECT_ALLOW_NETWORK=1``, and
2. the individual request carries ``confirm_network: true``.

Only the query itself is transmitted. No credentials, no identifiers, no
telemetry, and no result data are ever sent. Local catalogue files under
``STATE_DIR/catalogues`` are read without any network access at all.

Roadmap items 147 (OEIS lookup) and 148 (Cunningham/known-factor catalogues).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .config import (
    ALLOW_NETWORK,
    CATALOGUE_LOOKUP_URL,
    CATALOGUES_DIR,
    NETWORK_TIMEOUT_SECONDS,
    OEIS_SEARCH_URL,
)

USER_AGENT = "Numerisect/local (offline-by-default research tool)"
MAX_RESPONSE_BYTES = 2_000_000
MAX_SEQUENCE_TERMS = 64
SEQUENCE_TERM = re.compile(r"^-?\d{1,120}$")
CATALOGUE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


class NetworkNotPermitted(PermissionError):
    """Raised when a lookup is attempted without both required approvals."""


class CatalogueError(RuntimeError):
    """Raised when a catalogue request fails or returns unusable data."""


def _catalogue_dir(directory: Path | None) -> Path:
    """Resolve the catalogue directory, honouring runtime overrides."""

    if directory is not None:
        return directory
    import numerisect.catalogues as module

    return module.CATALOGUES_DIR


def network_status() -> dict[str, Any]:
    """Describe the current network permission state for the UI and diagnostics."""

    return {
        "allowed_by_environment": ALLOW_NETWORK,
        "environment_variable": "NUMERISECT_ALLOW_NETWORK",
        "requires_request_confirmation": True,
        "timeout_seconds": NETWORK_TIMEOUT_SECONDS,
        "oeis_configured": bool(OEIS_SEARCH_URL),
        "catalogue_url_configured": bool(CATALOGUE_LOOKUP_URL),
        "local_catalogue_directory": str(CATALOGUES_DIR),
    }


def require_network(confirm_network: bool) -> None:
    """Enforce the two-key network policy.

    Args:
        confirm_network: The per-request confirmation flag supplied by the caller.

    Raises:
        NetworkNotPermitted: If either approval is missing.
    """

    if not ALLOW_NETWORK:
        raise NetworkNotPermitted(
            "Outbound lookups are disabled. Restart Numerisect with "
            "NUMERISECT_ALLOW_NETWORK=1 to enable them."
        )
    if not confirm_network:
        raise NetworkNotPermitted(
            "This request did not set confirm_network=true, so no data was sent."
        )


def _fetch(url: str) -> bytes:
    """Perform one bounded GET request. Only ``url`` leaves the machine."""

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise CatalogueError("Catalogue lookups require an https URL")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT_SECONDS) as response:
            return response.read(MAX_RESPONSE_BYTES + 1)[:MAX_RESPONSE_BYTES]
    except urllib.error.HTTPError as exc:
        raise CatalogueError(f"The catalogue returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CatalogueError(f"The catalogue could not be reached: {exc}") from exc


def validate_sequence(terms: list[str]) -> list[int]:
    """Validate a user-supplied integer sequence for an OEIS query.

    Args:
        terms: Decimal integer strings.

    Returns:
        The parsed integers.

    Raises:
        ValueError: If the sequence is empty, too long, or not all integers.
    """

    if not terms:
        raise ValueError("Supply at least one integer term")
    if len(terms) > MAX_SEQUENCE_TERMS:
        raise ValueError(f"Supply at most {MAX_SEQUENCE_TERMS} terms")
    parsed: list[int] = []
    for term in terms:
        text = str(term).strip()
        if not SEQUENCE_TERM.match(text):
            raise ValueError(f"'{term}' is not a decimal integer")
        parsed.append(int(text))
    return parsed


def oeis_lookup(terms: list[str], confirm_network: bool, limit: int = 5) -> dict[str, Any]:
    """Search OEIS for a sequence.

    Only the comma-separated integer terms are transmitted.

    Args:
        terms: The sequence to search for.
        confirm_network: Per-request network confirmation.
        limit: Maximum number of matches to return (1-20).

    Returns:
        A dictionary with the query, the matches, and an explicit provenance note.
    """

    values = validate_sequence(terms)
    require_network(confirm_network)
    if not OEIS_SEARCH_URL:
        raise CatalogueError("No OEIS endpoint is configured")
    limit = max(1, min(int(limit), 20))
    query = ",".join(str(value) for value in values)
    url = f"{OEIS_SEARCH_URL}?{urllib.parse.urlencode({'q': query, 'fmt': 'json'})}"
    raw = _fetch(url)
    try:
        document = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise CatalogueError("The OEIS response was not valid JSON") from exc
    entries = document if isinstance(document, list) else document.get("results") or []
    matches = []
    for entry in entries[:limit]:
        if not isinstance(entry, dict):
            continue
        number = entry.get("number")
        matches.append(
            {
                "id": f"A{int(number):06d}" if isinstance(number, int) else str(number),
                "name": str(entry.get("name", ""))[:400],
                "terms": str(entry.get("data", ""))[:400],
                "keywords": str(entry.get("keyword", ""))[:200],
            }
        )
    return {
        "query": query,
        "term_count": len(values),
        "matches": matches,
        "match_count": len(matches),
        "source": "oeis.org",
        "note": (
            "Results are unverified external claims retrieved from OEIS. "
            "Numerisect transmitted only the integer terms shown in 'query'."
        ),
    }


def _read_local_catalogue(path: Path) -> list[dict[str, Any]]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise CatalogueError(f"Could not read catalogue '{path.name}': {exc}") from exc
    entries: list[dict[str, Any]] = []
    if path.suffix.lower() == ".json":
        try:
            document = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CatalogueError(f"Catalogue '{path.name}' is not valid JSON") from exc
        records = document if isinstance(document, list) else document.get("entries") or []
        for record in records:
            if isinstance(record, dict) and "number" in record:
                entries.append(record)
        return entries
    # Plain text: "<number> = <factor> * <factor> ..." or "<number>: <factors>"
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        separator = "=" if "=" in text else (":" if ":" in text else None)
        if separator is None:
            continue
        left, right = text.split(separator, 1)
        number = left.strip()
        if not number.lstrip("-").isdigit():
            continue
        factors = [part.strip() for part in re.split(r"[*x,\s]+", right) if part.strip().isdigit()]
        entries.append({"number": number, "factors": factors})
    return entries


def list_local_catalogues(directory: Path | None = None) -> list[dict[str, Any]]:
    """List importable catalogue files. Never touches the network."""

    directory = _catalogue_dir(directory)
    if not directory.is_dir():
        return []
    listing = []
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix.lower() in {".json", ".txt"}:
            listing.append({"name": path.name, "bytes": path.stat().st_size})
    return listing


def local_catalogue_lookup(
    number: int, catalogue: str | None = None, directory: Path | None = None
) -> dict[str, Any]:
    """Look up known factors of ``number`` in local catalogue files.

    Args:
        number: The integer to look up.
        catalogue: Optional single catalogue filename; otherwise all are searched.
        directory: Catalogue directory.

    Returns:
        A dictionary of claimed factors, always labelled unverified.
    """

    if catalogue is not None and not CATALOGUE_NAME.match(catalogue):
        raise ValueError("Invalid catalogue name")
    directory = _catalogue_dir(directory)
    if not directory.is_dir():
        return {"number": str(number), "claims": [], "searched": [], "note": _UNVERIFIED}
    searched: list[str] = []
    claims: list[dict[str, Any]] = []
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".json", ".txt"}:
            continue
        if catalogue is not None and path.name != catalogue:
            continue
        searched.append(path.name)
        for entry in _read_local_catalogue(path):
            if str(entry.get("number")).strip() == str(number):
                claims.append(
                    {
                        "catalogue": path.name,
                        "factors": [str(value) for value in entry.get("factors", [])],
                        "note": str(entry.get("note", ""))[:200],
                    }
                )
    return {"number": str(number), "claims": claims, "searched": searched, "note": _UNVERIFIED}


def remote_catalogue_lookup(number: int, confirm_network: bool) -> dict[str, Any]:
    """Query the configured remote known-factor catalogue.

    Only the decimal integer is transmitted. Claimed factors are returned as
    unverified until Numerisect re-checks divisibility with a native engine.
    """

    require_network(confirm_network)
    if not CATALOGUE_LOOKUP_URL:
        raise CatalogueError(
            "No remote catalogue is configured. Set NUMERISECT_CATALOGUE_URL to an https endpoint."
        )
    url = f"{CATALOGUE_LOOKUP_URL}?{urllib.parse.urlencode({'query': str(number)})}"
    raw = _fetch(url)
    text = raw.decode("utf-8", errors="replace")
    factors = [value for value in re.findall(r"\b\d{1,120}\b", text) if value not in {"0", "1"}]
    return {
        "number": str(number),
        "claimed_factors": factors[:64],
        "source": urllib.parse.urlparse(CATALOGUE_LOOKUP_URL).netloc,
        "note": _UNVERIFIED,
    }


_UNVERIFIED = (
    "Catalogue entries are unverified external claims. Numerisect verifies each "
    "claimed factor with a native engine before treating it as a factorization."
)
