# SPDX-License-Identifier: GPL-3.0-or-later
"""A dependency-free client for the local Numerisect HTTP API.

Intended for scripts, Jupyter, and SageMath sessions that talk to a running
``numerisect serve`` instance. It uses only the Python standard library and
handles the per-launch session token automatically.

For headless use without a running server, prefer
:class:`numerisect.asgi_client.LocalApiClient`, which drives the application
in-process.

Roadmap item 150 (notebook integration) and part of 149 (client examples).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:8765"


class NumerisectError(RuntimeError):
    """Raised when the API returns an error response."""

    def __init__(self, status: int, detail: Any) -> None:
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


class NumerisectClient:
    """Talk to a running local Numerisect server.

    Example:
        >>> with NumerisectClient() as client:  # doctest: +SKIP
        ...     client.check_prime("32416190071")["is_prime"]
        True
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 300.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(),
        )
        self._token: str | None = None

    def __enter__(self) -> NumerisectClient:
        self.connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        """Release the underlying opener."""

        self._opener.close()

    def connect(self) -> str:
        """Fetch and remember the per-launch session token."""

        payload = self._request("GET", "/api/session", authenticated=False)
        self._token = str(payload["request_token"])
        return self._token

    def _request(
        self,
        method: str,
        path: str,
        data: Any = None,
        params: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> Any:
        if authenticated and self._token is None:
            self.connect()
        url = self.base_url + path
        if params:
            clean = {key: value for key, value in params.items() if value is not None}
            if clean:
                url = f"{url}?{urllib.parse.urlencode(clean)}"
        body = None
        headers = {"Accept": "application/json"}
        if authenticated and self._token:
            headers["X-Numerisect-Token"] = self._token
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                text = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(raw).get("detail", raw)
            except json.JSONDecodeError:
                detail = raw
            raise NumerisectError(exc.code, detail) from exc
        except urllib.error.URLError as exc:
            raise NumerisectError(
                0, f"Could not reach Numerisect at {self.base_url}: {exc.reason}"
            ) from exc
        return json.loads(text) if text else None

    def get(self, path: str, **params: Any) -> Any:
        """Issue a GET request."""

        return self._request("GET", path, params=params)

    def post(self, path: str, **data: Any) -> Any:
        """Issue a POST request with a JSON body."""

        return self._request("POST", path, data=data)

    def delete(self, path: str, **params: Any) -> Any:
        """Issue a DELETE request."""

        return self._request("DELETE", path, params=params)

    # Convenience wrappers for the most common operations.

    def check_prime(self, expression: str, mode: str = "proven", certificate: bool = False) -> Any:
        """Test one integer for primality."""

        return self.post(
            "/api/primes/check", expression=expression, mode=mode, certificate=certificate
        )

    def factor(self, expression: str, engine: str = "auto", threads: int = 1, **options: Any) -> Any:
        """Queue a factorization job and return it immediately."""

        return self.post(
            "/api/jobs", expression=expression, backend=engine, threads=threads, **options
        )

    def job(self, job_id: str) -> Any:
        """Fetch one job's current state."""

        return self.get(f"/api/jobs/{job_id}")

    def wait(self, job_id: str, poll_seconds: float = 1.0, max_seconds: float = 3600.0) -> Any:
        """Poll a job until it reaches a terminal state.

        Raises:
            TimeoutError: If the job is still running after ``max_seconds``.
        """

        import time

        deadline = time.monotonic() + max_seconds
        while True:
            job = self.job(job_id)
            if job["status"] in {"completed", "failed", "cancelled"}:
                return job
            if time.monotonic() > deadline:
                raise TimeoutError(f"Job {job_id} did not finish within {max_seconds} seconds")
            time.sleep(poll_seconds)

    def capabilities(self) -> Any:
        """Report which native engines are available."""

        return self.get("/api/capabilities")

    def routes(self) -> Any:
        """List every route the running server exposes."""

        return self.get("/openapi.json")["paths"]
