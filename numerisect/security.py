# SPDX-License-Identifier: GPL-3.0-or-later
"""Loopback request protections for the local Numerisect service."""

from __future__ import annotations

import hmac
import secrets
from urllib.parse import urlsplit

from fastapi import Request

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
REQUEST_TOKEN = secrets.token_urlsafe(32)
REQUEST_TOKEN_COOKIE = "numerisect_session"
REQUEST_TOKEN_HEADER = "X-Numerisect-Token"


def host_header_is_allowed(value: str) -> bool:
    """Validate an HTTP Host header, including bracketed IPv6 loopback."""

    if not value or any(character in value for character in "\r\n/\\"):
        return False
    try:
        parsed = urlsplit(f"//{value}")
        _ = parsed.port
    except ValueError:
        return False
    return parsed.hostname in LOOPBACK_HOSTS


def is_local_origin(value: str, request: Request) -> bool:
    """Return whether an Origin or Referer URL matches this loopback service."""

    try:
        candidate = urlsplit(value)
    except ValueError:
        return False
    if candidate.scheme not in {"http", "https"} or candidate.hostname not in LOOPBACK_HOSTS:
        return False

    request_host = request.url.hostname
    if request_host not in LOOPBACK_HOSTS:
        return False
    candidate_port = candidate.port or (443 if candidate.scheme == "https" else 80)
    request_port = request.url.port or (443 if request.url.scheme == "https" else 80)
    return (
        candidate.scheme == request.url.scheme
        and candidate.hostname == request_host
        and candidate_port == request_port
    )


def request_has_valid_token(request: Request) -> bool:
    """Check the per-process token in either the API header or strict cookie."""

    supplied = request.headers.get(REQUEST_TOKEN_HEADER) or request.cookies.get(
        REQUEST_TOKEN_COOKIE
    )
    if supplied is None:
        return False
    return hmac.compare_digest(supplied, REQUEST_TOKEN)


def request_origin_is_safe(request: Request) -> bool:
    """Reject explicit cross-site browser metadata and non-loopback origins."""

    if request.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
        return False
    origin = request.headers.get("Origin")
    if origin:
        return is_local_origin(origin, request)
    referer = request.headers.get("Referer")
    if referer:
        return is_local_origin(referer, request)
    return True
