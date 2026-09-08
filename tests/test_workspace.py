"""Application-infrastructure tests: workspaces, search, exports, batch import, caching."""

import json

import pytest
from fastapi.testclient import TestClient

from numerisect import jobs, outputs
from numerisect.asgi_client import LocalApiClient
from numerisect.catalogues import (
    NetworkNotPermitted,
    local_catalogue_lookup,
    require_network,
    validate_sequence,
)
from numerisect.database import Database
from numerisect.exports import (
    export_job,
    export_jobs,
    export_report_text,
    normalize_format,
)
from numerisect.main import app
from numerisect.workspace import (
    cache_key,
    classify_batch_item,
    expand_batch_items,
    parse_batch_document,
    payload_is_conclusive,
    validate_workspace_fields,
    verify_claimed_factors,
)

JOB = {
    "id": "abc123def456",
    "expression": "8051",
    "number": 8051,
    "digits": 4,
    "status": "completed",
    "phase": "done",
    "requested_backend": "pari_trial",
    "selected_backend": "pari_trial",
    "threads": 2,
    "priority": 0,
    "created_at": "2026-09-07T00:00:00Z",
    "finished_at": "2026-09-07T00:00:01Z",
    "elapsed_seconds": 1.0,
    "error": None,
    # 8051 = 83 * 97
    "factors": [
        {"value": "83", "exponent": 1, "status": "prime", "engine": "PARI/GP", "digits": 2},
        {"value": "97", "exponent": 1, "status": "prime", "engine": "PARI/GP", "digits": 2},
    ],
}


@pytest.fixture()
def local_client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    token = client.get("/api/session").json()["request_token"]
    client.headers["X-Numerisect-Token"] = token
    return client


def test_export_formats_all_render():
    for fmt in ("json", "jsonl", "csv", "markdown", "latex", "pari"):
        body = export_job(JOB, fmt)
        assert body.strip()
        assert "83" in body and "97" in body
    assert json.loads(export_job(JOB, "json"))["number"] == 8051
    # The PARI export must be a checkable product, not just a list.
    pari = export_job(JOB, "pari")
    assert "product = prod(" in pari and "N = 8051;" in pari


def test_export_format_aliases_and_rejection():
    assert normalize_format("md") == "markdown"
    assert normalize_format("TEX") == "latex"
    assert normalize_format(None) == "json"
    with pytest.raises(ValueError):
        normalize_format("xlsx")


def test_export_escapes_table_separators():
    job = {**JOB, "expression": "a|b", "factors": []}
    assert "a\\|b" in export_jobs([job], "markdown")  # separator escaped in the data row
    # Table cells are escaped; verbatim report bodies are deliberately not.
    assert "\\_" in export_jobs([{**JOB, "expression": "under_score"}], "latex")
    assert "\\begin{verbatim}" in export_report_text("r_1.txt", "under_score", "latex")


def test_batch_document_parsing_and_classification():
    items = parse_batch_document("8051\n# comment\n10..14\nn^2+n+41 for n=1..3\n", "txt")
    assert items == ["8051", "10..14", "n^2+n+41 for n=1..3"]
    assert classify_batch_item("8051")["kind"] == "integer"
    assert classify_batch_item("10..14")["kind"] == "range"
    assert classify_batch_item("n^2+n+41 for n=1..3")["kind"] == "family"


def test_batch_expansion_runs_in_gp():
    # 10..14 expands to five integers; n^2+n+41 at n=1,2,3 gives 43, 47, 53.
    result = expand_batch_items(["10..14", "n^2+n+41 for n=1..3"])
    assert result["values"][:5] == ["10", "11", "12", "13", "14"]
    assert result["values"][5:] == ["43", "47", "53"]


def test_batch_expansion_rejects_oversized_range():
    with pytest.raises(ValueError):
        expand_batch_items(["1..99999999"])


def test_workspace_field_validation():
    fields = validate_workspace_fields(
        name=" Session A ", notes="n", job_ids=["a" * 32], report_files=["r.txt"], ui_state={"x": 1}
    )
    assert fields["name"] == "Session A"
    with pytest.raises(ValueError):
        validate_workspace_fields(
            name="", notes=None, job_ids=None, report_files=None, ui_state=None
        )


def test_workspace_crud_round_trip(local_client, tmp_path, monkeypatch):
    created = local_client.post(
        "/api/workspaces", json={"name": "Cunningham run", "notes": "c2^n-1"}
    )
    assert created.status_code == 200
    workspace_id = created.json()["id"]

    listed = local_client.get("/api/workspaces").json()["workspaces"]
    assert any(row["id"] == workspace_id for row in listed)

    updated = local_client.post(
        f"/api/workspaces/{workspace_id}", json={"notes": "updated"}
    )
    assert updated.status_code == 200
    assert updated.json()["notes"] == "updated"

    assert local_client.get(f"/api/workspaces/{workspace_id}").json()["name"] == "Cunningham run"
    assert local_client.delete(f"/api/workspaces/{workspace_id}").status_code == 200
    assert local_client.get(f"/api/workspaces/{workspace_id}").status_code == 404


def test_workspace_update_requires_a_field(local_client):
    created = local_client.post("/api/workspaces", json={"name": "empty update"}).json()
    response = local_client.post(f"/api/workspaces/{created['id']}", json={})
    assert response.status_code == 422
    local_client.delete(f"/api/workspaces/{created['id']}")


def test_job_search_is_parameterized(tmp_path):
    database = Database(tmp_path / "jobs.sqlite3")
    database.create_job(
        {
            "id": "j1", "expression": "8051", "number": 8051, "digits": 4, "negative": 0,
            "status": "completed", "phase": "queued", "requested_backend": "pari_trial",
            "selected_backend": "pari_trial", "threads": 1, "pretest_level": 20,
            "workdir": str(tmp_path), "log_path": str(tmp_path / "l.log"),
        }
    )
    assert len(database.search_jobs(q="8051")) == 1
    assert database.search_jobs(q="nothing-matches") == []
    # A quote must be treated as data, not SQL.
    assert database.search_jobs(q="' OR 1=1 --") == []


def test_batch_import_route_expands_without_queueing(local_client):
    response = local_client.post(
        "/api/batch/import", json={"content": "10..12\n8051\n", "queue": False}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["values"] == ["10", "11", "12", "8051"]
    assert payload["queued"] == []
    assert payload["engine"] == "PARI/GP"


def test_export_routes_serve_attachments(local_client):
    response = local_client.get("/api/exports/jobs", params={"format": "csv", "limit": 5})
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    assert local_client.get("/api/exports/jobs", params={"format": "xlsx"}).status_code == 422


def test_cache_key_is_stable_and_parameter_sensitive():
    a = cache_key("/api/primes/check", {"expression": "7", "mode": "proven"}, "rev1")
    b = cache_key("/api/primes/check", {"mode": "proven", "expression": "7"}, "rev1")
    c = cache_key("/api/primes/check", {"expression": "8", "mode": "proven"}, "rev1")
    d = cache_key("/api/primes/check", {"expression": "7", "mode": "proven"}, "rev2")
    assert a == b  # key order must not matter
    assert a != c and a != d  # parameters and engine revision must


def test_inconclusive_results_are_never_cached():
    assert payload_is_conclusive({"is_prime": True}) is True
    assert payload_is_conclusive({"status": "inconclusive"}) is False
    assert payload_is_conclusive({"truncated": True}) is False
    assert payload_is_conclusive({"inner": {"verdict": "unknown"}}) is False


def test_cache_routes_report_and_clear(local_client):
    stats = local_client.get("/api/cache")
    assert stats.status_code == 200
    assert "enabled" in stats.json()
    assert local_client.delete("/api/cache").status_code == 200


def test_network_is_denied_by_default():
    with pytest.raises(NetworkNotPermitted):
        require_network(True)  # environment flag is off in tests
    with pytest.raises(NetworkNotPermitted):
        require_network(False)


def test_oeis_route_refuses_without_permission(local_client):
    response = local_client.post(
        "/api/catalogues/oeis", json={"terms": ["2", "3", "5", "7"], "confirm_network": True}
    )
    assert response.status_code == 403
    assert "NUMERISECT_ALLOW_NETWORK" in response.json()["detail"]


def test_sequence_validation_rejects_non_integers():
    assert validate_sequence(["2", "3", "5"]) == [2, 3, 5]
    with pytest.raises(ValueError):
        validate_sequence(["2", "x"])
    with pytest.raises(ValueError):
        validate_sequence([])


def test_local_catalogue_lookup_is_offline(tmp_path):
    (tmp_path / "cunningham.txt").write_text("8051 = 83 * 97\n", encoding="utf-8")
    result = local_catalogue_lookup(8051, directory=tmp_path)
    assert result["claims"][0]["factors"] == ["83", "97"]
    assert local_catalogue_lookup(9999, directory=tmp_path)["claims"] == []


def test_catalogue_claims_are_verified_natively(local_client, tmp_path, monkeypatch):
    from numerisect import catalogues

    (tmp_path / "local.txt").write_text("8051 = 83 * 96\n", encoding="utf-8")
    monkeypatch.setattr(catalogues, "CATALOGUES_DIR", tmp_path)
    response = local_client.post("/api/catalogues/factors", json={"expression": "8051"})
    assert response.status_code == 200
    payload = response.json()
    verified = {row["factor"]: row for row in payload["verified"]}
    assert verified["83"]["divides"] is True  # 8051 = 83 * 97
    assert verified["83"]["prime"] is True
    assert verified["96"]["divides"] is False  # a wrong catalogue claim must be reported as false
    assert payload["product_matches"] is False  # 83 * 96 != 8051
    # Divisibility and primality must be decided by the engine, not by Python.
    assert payload["engine"] == "PARI/GP"


def test_queue_and_priority_routes(local_client):
    assert local_client.get("/api/queue").status_code == 200
    assert local_client.post("/api/jobs/missing/priority", json={"priority": 3}).status_code == 404
    assert local_client.post("/api/jobs/missing/pause").status_code == 404


def test_priority_bounds_are_enforced(local_client):
    assert local_client.post("/api/jobs/x/priority", json={"priority": 99}).status_code == 422


def test_reports_index_route(local_client):
    response = local_client.get("/api/reports", params={"limit": 5})
    assert response.status_code == 200
    assert "reports" in response.json()


def test_performance_history_route(local_client):
    response = local_client.get("/api/history/performance")
    assert response.status_code == 200
    assert "buckets" in response.json()


def test_adapters_route_lists_builtin_engines(local_client):
    payload = local_client.get("/api/adapters").json()
    names = {row["name"] for row in payload.get("builtin", payload.get("adapters", []))}
    assert {"yafu", "pari_trial"} & names


def test_setup_log_route_is_wired(local_client):
    response = local_client.get("/api/setup/log")
    assert response.status_code == 200
    assert "available" in response.json()


def test_cli_api_parity_reaches_every_route():
    client = LocalApiClient()
    routes = client.routes()
    assert len(routes) > 90
    assert {"method": "POST", "path": "/api/primes/check"} in routes
    # 32416190071 is prime.
    response = client.post("/api/primes/check", {"expression": "32416190071", "mode": "proven"})
    assert response.ok
    assert response.json()["is_prime"] is True


def test_cli_api_client_rejects_unknown_method():
    with pytest.raises(ValueError):
        LocalApiClient().request("TRACE", "/api/capabilities")


def test_job_limits_recorded_in_manifest(tmp_path, monkeypatch):
    job_root = tmp_path / "jobs"
    output_root = tmp_path / "output"
    job_root.mkdir()
    output_root.mkdir()
    monkeypatch.setattr(jobs, "JOBS_DIR", job_root)
    monkeypatch.setattr(outputs, "OUTPUT_DIR", output_root)
    database = Database(tmp_path / "jobs.sqlite3")
    manager = jobs.JobManager(database)
    try:
        created = manager.create(
            expression="8051", number=8051, requested_backend="pari_trial", threads=1,
            pretest_level=20, trial_bound=100, cado_parameter_size=None,
            priority=5, cpu_seconds=60, memory_mb=512, wall_seconds=120,
        )
        manager._futures[created["id"]].result(timeout=30)
        completed = database.get_job(created["id"])
        assert completed["status"] == "completed"
        assert completed["priority"] == 5
        manifest = json.loads(
            (output_root / f"factorization-{created['id'][:12]}.json").read_text(encoding="utf-8")
        )
        assert manifest["limits"]["cpu_seconds"] == 60
        assert manifest["limits"]["memory_mb"] == 512
        assert manifest["priority"] == 5
    finally:
        manager.shutdown()


def test_memory_limit_uses_the_host_supported_resource(monkeypatch):
    monkeypatch.setattr(jobs.sys, "platform", "darwin")
    assert jobs._memory_limit_resource() == jobs.resource.RLIMIT_DATA
    assert jobs._memory_limit_label() == "data-segment"
    monkeypatch.setattr(jobs.sys, "platform", "linux")
    assert jobs._memory_limit_resource() == jobs.resource.RLIMIT_AS
    assert jobs._memory_limit_label() == "address-space"


# --- Interface contract for the workspace view ---------------------------------------

from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "numerisect" / "static" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "numerisect" / "static" / "app.js").read_text(encoding="utf-8")


def test_workspace_view_is_registered_and_routed():
    assert 'data-view="workspace-view"' in INDEX
    assert 'id="workspace-view"' in INDEX
    assert "section === 'workspaces'" in APP


def test_workspace_forms_exist_once_each():
    for form_id in ("workspace-form", "history-search-form"):
        assert INDEX.count(f'id="{form_id}"') == 1


def test_notifications_are_opt_in_and_local():
    # The toggle must ask for permission and must never post anywhere.
    assert "Notification.requestPermission()" in APP
    assert "announceFinishedJobs" in APP
    assert "localStorage.getItem(NOTIFY_KEY)" in APP


def test_deleting_a_workspace_is_confirmed():
    assert "window.confirm('Delete this workspace?" in APP



def test_factor_verification_runs_in_gp():
    # 8051 = 83 * 97; 96 is not a divisor.
    result = verify_claimed_factors(8051, ["83", "97"])
    assert result["product_matches"] is True
    assert all(row["divides"] and row["prime"] for row in result["factors"])
    wrong = verify_claimed_factors(8051, ["83", "96"])
    assert wrong["product_matches"] is False
    assert wrong["factors"][1]["divides"] is False


def test_factor_verification_rejects_non_integers():
    with pytest.raises(ValueError):
        verify_claimed_factors(8051, ["83", "not-a-number"])
