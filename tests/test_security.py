# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from fastapi.testclient import TestClient

from numerisect.main import app
from numerisect.security import host_header_is_allowed

LOCAL_URL = "http://127.0.0.1:8765"


def session_client(host: str = LOCAL_URL) -> TestClient:
    client = TestClient(app, base_url=host)
    response = client.get("/api/session")
    assert response.status_code == 200
    client.headers["X-Numerisect-Token"] = response.json()["request_token"]
    return client


def test_untrusted_host_is_rejected():
    response = TestClient(app, base_url="http://attacker.example").get("/")
    assert response.status_code == 400


def test_localhost_and_loopback_hosts_are_accepted():
    for base_url in (LOCAL_URL, "http://localhost:8765"):
        response = session_client(base_url).get("/api/capabilities")
        assert response.status_code == 200
    assert host_header_is_allowed("[::1]:8765")


def test_api_requires_per_launch_token():
    client = TestClient(app, base_url=LOCAL_URL)
    response = client.post("/api/setup/install", json={"confirm": True})
    assert response.status_code == 403
    assert "token" in response.json()["detail"].lower()


def test_foreign_origin_and_cross_site_fetch_are_rejected(monkeypatch):
    client = session_client()
    monkeypatch.setattr("numerisect.main.installer.start_if_needed", lambda: False)
    foreign = client.post(
        "/api/setup/install",
        json={"confirm": True},
        headers={"Origin": "https://attacker.example"},
    )
    assert foreign.status_code == 403
    cross_site = client.post(
        "/api/setup/install",
        json={"confirm": True},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert cross_site.status_code == 403
    hostname_mismatch = client.post(
        "/api/setup/install",
        json={"confirm": True},
        headers={"Origin": "http://localhost:8765"},
    )
    assert hostname_mismatch.status_code == 403


def test_local_origin_can_start_explicit_install(monkeypatch):
    client = session_client()
    started = []
    monkeypatch.setattr(
        "numerisect.main.installer.start_if_needed", lambda: started.append(True) or True
    )
    response = client.post(
        "/api/setup/install",
        json={"confirm": True},
        headers={"Origin": LOCAL_URL, "Sec-Fetch-Site": "same-origin"},
    )
    assert response.status_code == 202
    assert started == [True]


def test_engine_install_requires_explicit_confirmation(monkeypatch):
    client = session_client()
    started = []
    monkeypatch.setattr(
        "numerisect.main.installer.start_if_needed", lambda: started.append(True)
    )
    response = client.post("/api/setup/install", json={"confirm": False})
    assert response.status_code == 422
    assert started == []


def test_startup_does_not_install_engines():
    source = __import__("inspect").getsource(app.router.lifespan_context)
    assert "start_if_needed" not in source


def test_ordinary_status_does_not_disclose_absolute_paths(monkeypatch):
    client = session_client()
    monkeypatch.setattr(
        "numerisect.main.installer.status",
        lambda: {
            "state": "idle",
            "missing": ["YAFU"],
            "log_path": "/home/example/private/engine.log",
            "managed_bin": "/home/example/private/bin",
        },
    )
    payload = client.get("/api/setup").json()
    assert "log_path" not in payload
    assert "managed_bin" not in payload
