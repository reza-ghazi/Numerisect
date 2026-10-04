import json

import pytest

from numerisect import jobs, outputs
from numerisect.database import Database
from numerisect.jobs import JobManager


def test_bounded_native_trial_job_and_reproducible_manifest(tmp_path, monkeypatch):
    job_root = tmp_path / "jobs"
    output_root = tmp_path / "output"
    job_root.mkdir()
    output_root.mkdir()
    monkeypatch.setattr(jobs, "JOBS_DIR", job_root)
    monkeypatch.setattr(outputs, "OUTPUT_DIR", output_root)
    database = Database(tmp_path / "jobs.sqlite3")
    manager = JobManager(database)
    try:
        created = manager.create(
            expression="8051",
            number=8051,
            requested_backend="pari_trial",
            threads=2,
            pretest_level=20,
            trial_bound=100,
            cado_parameter_size=None,
        )
        manager._futures[created["id"]].result(timeout=10)
        completed = database.get_job(created["id"])
        assert completed is not None
        assert completed["status"] == "completed"
        assert [factor["value"] for factor in completed["factors"]] == ["83", "97"]
        report = output_root / f"factorization-{created['id'][:12]}.txt"
        manifest_path = report.with_suffix(".json")
        assert f"output/{manifest_path.name}" in report.read_text(encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["schema"] == "org.numerisect.factorization-manifest.v1"
        assert manifest["commands"] == [["gp", "-fq"]]
        assert manifest["trial_bound"] == 100
        assert manifest["engines"][0]["name"] == "PARI/GP"
        assert len(manifest["engines"][0]["executable_sha256"]) == 64
    finally:
        manager.shutdown()


def _manager(tmp_path, monkeypatch):
    """A manager whose job tree and output directory live under ``tmp_path``."""

    job_root = tmp_path / "jobs"
    output_root = tmp_path / "output"
    job_root.mkdir()
    output_root.mkdir()
    monkeypatch.setattr(jobs, "JOBS_DIR", job_root)
    monkeypatch.setattr(outputs, "OUTPUT_DIR", output_root)
    return JobManager(Database(tmp_path / "jobs.sqlite3"))


def _capture(manager, monkeypatch, output):
    """Record every command the manager launches and answer with ``output``."""

    commands: list[list[str]] = []

    def fake_run(job, command, **kwargs):
        commands.append(list(command))
        return 0, output

    monkeypatch.setattr(manager, "_run_process", fake_run)
    return commands


def test_yafu_expert_parameters_reach_the_engine(tmp_path, monkeypatch):
    """The validated expert bounds were dead code: nothing passed them to YAFU.

    The engines are stubbed, so this runs where YAFU is not installed.
    """

    monkeypatch.setattr(jobs, "executable_path", lambda name: f"/usr/bin/{name}")
    manager = _manager(tmp_path, monkeypatch)
    commands = _capture(manager, monkeypatch, "***factors found***\n\nP2 = 83\nP2 = 97\n")
    try:
        created = manager.create(
            expression="8051", number=8051, requested_backend="yafu", threads=1,
            pretest_level=20, trial_bound=100, cado_parameter_size=None,
            yafu_options={"b1_ecm": 50_000, "siqs_relations": 100_000},
        )
        manager._futures[created["id"]].result(timeout=30)
    finally:
        manager.shutdown()
    assert commands, "YAFU was never launched"
    command = commands[0]
    assert command[command.index("-B1ecm") + 1] == "50000"
    assert command[command.index("-siqsR") + 1] == "100000"


def test_an_unknown_or_out_of_range_yafu_parameter_is_refused_at_creation(tmp_path, monkeypatch):
    """A job that would die on a malformed flag must never be queued."""

    monkeypatch.setattr(jobs, "executable_path", lambda name: f"/usr/bin/{name}")
    manager = _manager(tmp_path, monkeypatch)
    try:
        for options in ({"b1_squfof": 1000}, {"b1_ecm": 1}):
            with pytest.raises(ValueError):
                manager.create(
                    expression="8051", number=8051, requested_backend="yafu", threads=1,
                    pretest_level=20, trial_bound=100, cado_parameter_size=None,
                    yafu_options=options,
                )
    finally:
        manager.shutdown()


def test_ecm_campaign_passes_the_stage_two_and_special_form_flags(tmp_path, monkeypatch):
    """Stage-2 shape and the base-2 and group-order shortcuts must reach GMP-ECM."""

    monkeypatch.setattr(jobs, "executable_path", lambda name: f"/usr/bin/{name}")
    manager = _manager(tmp_path, monkeypatch)
    commands = _capture(
        manager, monkeypatch,
        "Found prime factor of 2 digits: 83\nPrime cofactor 97 has 2 digits\n",
    )
    try:
        created = manager.create(
            expression="8051", number=8051, requested_backend="ecm_campaign", threads=1,
            pretest_level=20, trial_bound=100, cado_parameter_size=None,
            ecm_b1=50_000, ecm_curves=10, ecm_maxmem=512, ecm_stage2_steps=4,
            ecm_base2=-101, ecm_group_order="2*101",
        )
        manager._futures[created["id"]].result(timeout=60)
    finally:
        manager.shutdown()
    assert commands, "GMP-ECM was never launched"
    command = commands[0]
    assert command[command.index("-maxmem") + 1] == "512"
    assert command[command.index("-k") + 1] == "4"
    assert command[command.index("-base2") + 1] == "-101"
    assert command[command.index("-go") + 1] == "2*101"
