# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal in-process ASGI caller used for full command-line/API parity.

The command line drives the very same FastAPI application object the browser
talks to, without opening a socket and without adding an HTTP client to the
runtime dependencies. The per-process session token is attached automatically,
so every protected route is reachable headlessly.

Roadmap items 20 and 131 (complete CLI/API parity).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urlencode, urlsplit

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
LOOPBACK_HOST = "127.0.0.1"
LOOPBACK_PORT = 8765


class AsgiResponse:
    """The result of one in-process request."""

    def __init__(self, status: int, headers: list[tuple[bytes, bytes]], body: bytes) -> None:
        self.status = status
        self.headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in headers}
        self.body = body

    @property
    def text(self) -> str:
        """Decode the body as UTF-8."""

        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        """Parse the body as JSON.

        Raises:
            ValueError: If the body is not valid JSON.
        """

        try:
            return json.loads(self.text or "null")
        except json.JSONDecodeError as exc:
            raise ValueError(f"Response was not JSON (HTTP {self.status}): {self.text[:200]}") from exc

    @property
    def ok(self) -> bool:
        """Whether the status code indicates success."""

        return 200 <= self.status < 300


async def _call(
    app: Any,
    method: str,
    path: str,
    body: bytes,
    headers: list[tuple[bytes, bytes]],
) -> AsgiResponse:
    split = urlsplit(path)
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": split.path or "/",
        "raw_path": (split.path or "/").encode(),
        "query_string": split.query.encode(),
        "root_path": "",
        "headers": headers,
        "client": (LOOPBACK_HOST, 54321),
        "server": (LOOPBACK_HOST, LOOPBACK_PORT),
    }
    messages: list[dict[str, Any]] = []
    request_sent = False

    async def receive() -> dict[str, Any]:
        nonlocal request_sent
        if request_sent:
            return {"type": "http.disconnect"}
        request_sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await app(scope, receive, send)

    status = 500
    response_headers: list[tuple[bytes, bytes]] = []
    chunks: list[bytes] = []
    for message in messages:
        if message["type"] == "http.response.start":
            status = int(message["status"])
            response_headers = list(message.get("headers") or [])
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body") or b"")
    return AsgiResponse(status, response_headers, b"".join(chunks))


class LocalApiClient:
    """Call Numerisect HTTP routes in-process, with the session token attached."""

    def __init__(self, app: Any | None = None, token: str | None = None) -> None:
        if app is None:
            from .main import app as default_app

            app = default_app
        self.app = app
        if token is None:
            from .security import REQUEST_TOKEN

            token = REQUEST_TOKEN
        self.token = token

    def request(
        self,
        method: str,
        path: str,
        data: Any = None,
        params: dict[str, Any] | None = None,
    ) -> AsgiResponse:
        """Issue one request against the application.

        Args:
            method: HTTP method.
            path: Route path, optionally with a query string.
            data: Optional JSON-serialisable request body.
            params: Optional query parameters merged into ``path``.

        Returns:
            The response.

        Raises:
            ValueError: If the method is unsupported.
        """

        upper = method.upper()
        if upper not in METHODS:
            raise ValueError(f"Unsupported method '{method}'. Use one of: {', '.join(METHODS)}")
        if not path.startswith("/"):
            path = "/" + path
        if params:
            joiner = "&" if "?" in path else "?"
            path = f"{path}{joiner}{urlencode(params)}"
        body = b""
        headers = [
            (b"host", f"{LOOPBACK_HOST}:{LOOPBACK_PORT}".encode()),
            (b"x-numerisect-token", self.token.encode()),
            (b"accept", b"application/json"),
            (b"user-agent", b"numerisect-cli"),
        ]
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers.append((b"content-type", b"application/json"))
            headers.append((b"content-length", str(len(body)).encode()))
        return asyncio.run(_call(self.app, upper, path, body, headers))

    def get(self, path: str, **params: Any) -> AsgiResponse:
        """Issue a GET request."""

        return self.request("GET", path, params=params or None)

    def post(self, path: str, data: Any = None) -> AsgiResponse:
        """Issue a POST request."""

        return self.request("POST", path, data=data)

    def routes(self) -> list[dict[str, str]]:
        """List every registered API route as ``{method, path}`` records."""

        listing: list[dict[str, str]] = []
        for route in getattr(self.app, "routes", []):
            path = getattr(route, "path", None)
            methods = getattr(route, "methods", None)
            if not path or not methods:
                continue
            for method in sorted(methods):
                if method in {"HEAD", "OPTIONS"}:
                    continue
                listing.append({"method": method, "path": path})
        listing.sort(key=lambda item: (item["path"], item["method"]))
        return listing
