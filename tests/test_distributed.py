"""Distributed CADO-NFS configuration, exposure reporting, and the client-launch fix.

The security-relevant assertions here are about refusing unsafe configurations.
The correctness-relevant one is that CADO is always told where to run clients:
without ``slaves.hostnames`` it starts a bare work-unit server and polls forever.
"""

import json

import pytest
from conftest import requires
from fastapi.testclient import TestClient

from numerisect.distributed import (
    DistributedConfigurationError,
    client_command,
    describe_trust_model,
    validate_configuration,
)
from numerisect.main import app

LOCAL = {
    "address": "127.0.0.1",
    "port": 8790,
    "whitelist": ["127.0.0.1"],
    "ssl": True,
    "clients": 4,
}


@pytest.fixture()
def local_client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    token = client.get("/api/session").json()["request_token"]
    client.headers["X-Numerisect-Token"] = token
    return client


# --- The client-launch fix -------------------------------------------------------


@requires("cado-nfs.py")
def test_slaves_hostnames_is_always_set():
    # CADO only defaults slaves.hostnames to localhost when it uses its OWN default
    # parameter file. Numerisect always passes -p, so omitting this makes CADO queue
    # work units and poll for them forever with no client ever started.
    plan = validate_configuration(**LOCAL)
    assert "slaves.hostnames=localhost" in plan["parameters"]


@requires("cado-nfs.py")
def test_named_workers_replace_the_localhost_default():
    plan = validate_configuration(
        **{**LOCAL, "address": "192.168.1.5", "whitelist": ["192.168.1.0/24"]},
        hostnames=["w1", "w2"],
        script_path="/opt/cado/bin",
    )
    assert "slaves.hostnames=w1,w2" in plan["parameters"]
    assert "slaves.scriptpath=/opt/cado/bin" in plan["parameters"]


def test_the_plain_cado_backend_also_sets_hostnames():
    # Regression guard for the same bug on the non-distributed path.
    import inspect

    from numerisect.jobs import JobManager

    source = inspect.getsource(JobManager._run_cado)
    assert "slaves.hostnames=localhost" in source
    # The integer and its key=value assignments must stay contiguous, or CADO
    # rejects the whole command line.
    assert "command += [str(number), *assignments]" in source


# --- Refusing unsafe configurations ----------------------------------------------


@requires("cado-nfs.py")
def test_a_whitelist_is_required():
    with pytest.raises(DistributedConfigurationError, match="whitelist is required"):
        validate_configuration(**{**LOCAL, "whitelist": []})


@requires("cado-nfs.py")
def test_the_whole_internet_is_refused():
    with pytest.raises(DistributedConfigurationError, match="every address"):
        validate_configuration(**{**LOCAL, "whitelist": ["0.0.0.0/0"]})


@requires("cado-nfs.py")
def test_a_broad_public_range_is_refused():
    with pytest.raises(DistributedConfigurationError, match="public range"):
        validate_configuration(**{**LOCAL, "whitelist": ["8.8.0.0/16"]})


@requires("cado-nfs.py")
def test_binding_a_public_address_is_refused():
    with pytest.raises(DistributedConfigurationError, match="public address"):
        validate_configuration(**{**LOCAL, "address": "8.8.8.8"})


@requires("cado-nfs.py")
def test_remote_workers_require_a_script_path():
    with pytest.raises(DistributedConfigurationError, match="scriptpath"):
        validate_configuration(
            **{**LOCAL, "address": "192.168.1.5", "whitelist": ["192.168.1.0/24"]},
            hostnames=["worker1"],
        )


@requires("cado-nfs.py")
def test_malformed_values_are_refused():
    for bad in (
        {"port": 80},
        {"clients": 0},
        {"whitelist": ["not-an-address"]},
        {"address": ""},
    ):
        with pytest.raises(DistributedConfigurationError):
            validate_configuration(**{**LOCAL, **bad})


# --- Exposure reporting ------------------------------------------------------------


@requires("cado-nfs.py")
def test_a_loopback_run_reports_no_exposure_warnings():
    plan = validate_configuration(**LOCAL)
    assert plan["exposure"]["local_only"] is True
    assert plan["warnings"] == []


@requires("cado-nfs.py")
def test_a_lan_run_warns_about_the_missing_client_authentication():
    plan = validate_configuration(
        **{**LOCAL, "address": "192.168.1.5", "whitelist": ["192.168.1.0/24"]},
        hostnames=["w1"],
        script_path="/opt/cado/bin",
    )
    assert plan["exposure"]["local_only"] is False
    joined = " ".join(plan["warnings"])
    assert "do not authenticate" in joined
    assert "subnet" in joined


@requires("cado-nfs.py")
def test_disabling_tls_is_called_out():
    plan = validate_configuration(**{**LOCAL, "ssl": False})
    assert any("clear text" in warning for warning in plan["warnings"])
    assert "server.ssl=no" in plan["parameters"]


def test_the_trust_model_states_that_clients_are_unauthenticated():
    model = describe_trust_model()
    assert model["client_authentication"] == "none"
    assert "whitelist" in model["access_control"]
    # It must state the mitigation honestly rather than implying safety.
    assert "verifies" in model["mitigation"]


def test_the_worker_command_names_the_server_and_certificate():
    command = client_command("https://192.168.1.5:8790", certsha1="abc123", threads=8)
    assert command[0] == "cado-nfs-client.py"
    assert "--server=https://192.168.1.5:8790" in command
    assert "--certsha1=abc123" in command


# --- API -----------------------------------------------------------------------------


def test_trust_model_route_is_readable_without_enabling_anything(local_client):
    response = local_client.get("/api/distributed/trust-model")
    assert response.status_code == 200
    assert response.json()["client_authentication"] == "none"


@requires("cado-nfs.py")
def test_preview_starts_nothing(local_client):
    response = local_client.post(
        "/api/distributed/preview", json={"expression": "8051", **LOCAL}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["exposure"]["local_only"] is True
    assert "Nothing was started" in payload["note"]
    assert any(item.startswith("slaves.hostnames=") for item in payload["cado_parameters"])


@requires("cado-nfs.py")
def test_preview_refuses_an_unsafe_configuration(local_client):
    response = local_client.post(
        "/api/distributed/preview",
        json={"expression": "8051", **{**LOCAL, "whitelist": ["0.0.0.0/0"]}},
    )
    assert response.status_code == 422


def test_factor_requires_explicit_confirmation(local_client):
    response = local_client.post(
        "/api/distributed/factor", json={"expression": "8051", **LOCAL}
    )
    assert response.status_code == 403
    assert "confirm_network" in response.json()["detail"]


def test_a_run_leaving_the_machine_requires_the_environment_flag(local_client):
    response = local_client.post(
        "/api/distributed/factor",
        json={
            "expression": "8051",
            **{**LOCAL, "address": "192.168.1.5", "whitelist": ["192.168.1.0/24"]},
            "hostnames": ["w1"],
            "script_path": "/opt/cado/bin",
            "confirm_network": True,
        },
    )
    assert response.status_code == 403
    assert "NUMERISECT_ALLOW_NETWORK" in response.json()["detail"]


@requires("cado-nfs.py")
def test_the_stored_plan_round_trips_as_json():
    plan = validate_configuration(**LOCAL)
    restored = json.loads(json.dumps(plan))
    assert restored["parameters"] == plan["parameters"]


# --- End to end -----------------------------------------------------------------------


@requires("cado-nfs.py")
@pytest.mark.slow
def test_a_loopback_distributed_run_actually_factors(tmp_path, monkeypatch):
    """A real CADO run through the job path.

    This is the test that would have caught the missing slaves.hostnames: without
    it CADO queues work units and polls forever, so the job never completes.
    """

    from numerisect import jobs as jobs_module
    from numerisect import outputs as outputs_module
    from numerisect.database import Database
    from numerisect.jobs import JobManager

    job_root = tmp_path / "jobs"
    output_root = tmp_path / "output"
    job_root.mkdir()
    output_root.mkdir()
    monkeypatch.setattr(jobs_module, "JOBS_DIR", job_root)
    monkeypatch.setattr(outputs_module, "OUTPUT_DIR", output_root)

    # 1000003 * 1000033 * 1000037 * 1000039
    number = 1000003 * 1000033 * 1000037 * 1000039
    plan = validate_configuration(
        address="127.0.0.1", port=8799, whitelist=["127.0.0.1"], ssl=True, clients=2
    )
    database = Database(tmp_path / "jobs.sqlite3")
    manager = JobManager(database)
    try:
        created = manager.create(
            expression=str(number), number=number, requested_backend="cado",
            threads=4, pretest_level=20, trial_bound=100_000,
            cado_parameter_size=None, distributed=plan,
        )
        manager._futures[created["id"]].result(timeout=900)
        completed = database.get_job(created["id"])
        assert completed["status"] == "completed", completed.get("error")
        product = 1
        for factor in completed["factors"]:
            product *= int(factor["value"])
        assert product == number
    finally:
        manager.shutdown()
