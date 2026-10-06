"""CADO-NFS one stage at a time, which turned out to be a parameter after all.

The ledger recorded for a long time that isolating a CADO stage would mean reproducing
its upstream Python harness's bookkeeping. It does not: every CADO task takes a `run`
parameter, and disabling the task after the one you want makes the harness stop there,
exit cleanly, and leave the finished work in its working directory.

The excerpts below are real output from CADO-NFS 3.0.0 on this workstation: a 60-digit
input run in three gated passes over one working directory, which finished with both
30-digit primes. The engine is stubbed in the job tests, so these run where CADO is not
installed — CI has none.
"""

import pytest
from fastapi.testclient import TestClient

from numerisect import jobs, main, outputs
from numerisect.database import Database
from numerisect.engines import (
    CADO_STAGE_ORDER,
    CADO_STAGES,
    cado_stage_gate,
    cado_stage_label,
    parse_cado_stage_report,
)
from numerisect.jobs import JobManager

# Gated at sieving: polynomial selection ran, the sieve did not.
STOPPED_AT_SIEVING = """Info:Polynomial Selection (size optimized): Starting
Info:Polynomial Selection (root optimized): Starting
Info:Polynomial Selection (root optimized): Finished, best polynomial has Murphy_E = 1.233e-05
Info:Generate Factor Base: Starting
Info:Generate Free Relations: Starting
Info:Generate Free Relations: Found 969 free relations
Info:Lattice Sieving: Stopping at sieving
Info:Complete Factorization / Discrete logarithm / Class group: Finishing early: Job stops \
here because of a forcibly disabled task -- stopped at sieving
"""

# The next pass over the same working directory, gated at singleton removal.
STOPPED_AT_PURGE = """Info:Polynomial Selection (root optimized): Best polynomial previously \
has Murphy_E = 1.233e-05
Info:Lattice Sieving: Starting
Info:Lattice Sieving: Total number of relations: 52723
Info:Filtering - Duplicate Removal, removal pass: Starting
Info:Filtering - Duplicate Removal, removal pass: 50077 unique relations remain in total
Info:Filtering - Singleton removal: Stopping at purge
"""

# The ungated pass that finished.
FINISHED = """Info:Filtering - Singleton removal: After purge, 19399 relations with 19239 \
primes remain with weight 292046 and excess 160
Info:Filtering - Merging: Merged matrix has 5422 rows and total weight 725584 (133.8 entries \
per row on average)
Info:Linear Algebra: Starting
Info:Square Root: Starting
100000000000000000000000000319 100000000000000000000000005277
Info:Complete Factorization / Discrete logarithm / Class group: Total cpu/elapsed time for \
entire Complete Factorization 31.9/25.2813
"""

NUMBER = 100000000000000000000000000319 * 100000000000000000000000005277


# --- The stage table ------------------------------------------------------------------


def test_the_stages_are_cado_tasks_in_the_order_its_harness_runs_them():
    assert len(CADO_STAGES) == 12
    assert CADO_STAGE_ORDER[0] == "polyselect_size"
    assert CADO_STAGE_ORDER[-1] == "sqrt"
    assert CADO_STAGE_ORDER.index("sieving") < CADO_STAGE_ORDER.index("purge")
    for _, parameter, label in CADO_STAGES:
        assert parameter.startswith("tasks.") and parameter.endswith(".run")
        assert label


def test_the_gate_disables_the_stage_after_the_one_requested():
    """Disabling a task stops the workflow *at* it, so the gate is one stage later."""

    assert cado_stage_gate("polyselect_root") == "tasks.sieve.factorbase.run=false"
    assert cado_stage_gate("freerel") == "tasks.sieve.sieving.run=false"
    assert cado_stage_gate("purge") == "tasks.filter.mergetask.run=false"
    # The square root is the last stage, so a run that reaches it is simply complete.
    assert cado_stage_gate("sqrt") is None


@pytest.mark.parametrize("stage", ["", "sieve", "polyselect", "SQRT"])
def test_an_unknown_stage_is_refused(stage):
    with pytest.raises(ValueError, match="not a CADO-NFS workflow stage"):
        cado_stage_gate(stage)
    with pytest.raises(ValueError, match="not a CADO-NFS workflow stage"):
        cado_stage_label(stage)


# --- Reading CADO's own log -----------------------------------------------------------


def test_the_stop_marker_and_the_stage_figures_are_read():
    report = parse_cado_stage_report(STOPPED_AT_SIEVING)
    assert report["stopped_at"] == "sieving"
    assert report["murphy_e"] == "1.233e-05"
    assert report["free_relations"] == "969"
    assert "Lattice Sieving" not in report["stages"]
    assert "Polynomial Selection (root optimized)" in report["stages"]
    # Nothing the run did not print is reported, not even as zero.
    assert "relations" not in report and "matrix_rows" not in report


def test_a_later_pass_reports_what_it_added():
    report = parse_cado_stage_report(STOPPED_AT_PURGE)
    assert report["stopped_at"] == "purge"
    assert report["relations"] == "52723"
    assert report["unique_relations"] == "50077"
    assert "Lattice Sieving" in report["stages"]


def test_an_ungated_run_has_no_stop_marker_and_reports_the_matrix():
    report = parse_cado_stage_report(FINISHED)
    assert report["stopped_at"] is None
    assert report["purged_relations"] == "19399"
    assert report["purged_primes"] == "19239"
    assert report["matrix_rows"] == "5422"
    assert report["matrix_weight"] == "725584"


def test_colour_codes_in_the_log_do_not_hide_the_marker():
    """cado-nfs.py colours its own output; the parser strips the escapes."""

    coloured = "\x1b[32;1mInfo\x1b[0m:Lattice Sieving: Stopping at sieving\n"
    assert parse_cado_stage_report(coloured)["stopped_at"] == "sieving"


# --- The job manager ------------------------------------------------------------------


def _manager(tmp_path, monkeypatch) -> JobManager:
    (tmp_path / "jobs").mkdir()
    (tmp_path / "output").mkdir()
    monkeypatch.setattr(jobs, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(jobs, "executable_path", lambda name: f"/usr/bin/{name}")
    manager = JobManager(Database(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(manager, "parameters", [])
    monkeypatch.setattr(
        jobs, "select_cado_parameter",
        lambda digits, parameters, requested=None: jobs.CadoParameter(
            60, tmp_path / "params.c60"
        ),
    )
    return manager


def _capture(manager, monkeypatch, outputs_by_call: list[str]) -> list[list[str]]:
    commands: list[list[str]] = []
    remaining = list(outputs_by_call)

    def fake_run(job, command, **kwargs):
        commands.append(list(command))
        return 0, remaining.pop(0) if remaining else ""

    monkeypatch.setattr(manager, "_run_process", fake_run)
    return commands


def _staged(manager, stage: str, number: int = NUMBER) -> dict:
    return manager.create(
        expression=str(number), number=number, requested_backend="cado_stage",
        threads=2, pretest_level=20, trial_bound=100, cado_parameter_size=None,
        cado_stage=stage,
    )


def test_a_staged_run_gates_the_next_task_and_reports_the_stage(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch)
    commands = _capture(manager, monkeypatch, [STOPPED_AT_SIEVING])
    try:
        created = _staged(manager, "freerel")
        manager._futures[created["id"]].result(timeout=60)
        row = manager.database.get_job(created["id"])
    finally:
        manager.shutdown()
    assert "tasks.sieve.sieving.run=false" in commands[0]
    assert commands[0].index(str(NUMBER)) < commands[0].index("tasks.sieve.sieving.run=false")
    assert row["status"] == "completed"
    # A stage is a report: the completeness check cannot apply, since there is no
    # factor multiset to reconstruct the input from.
    assert [factor["status"] for factor in row["factors"]] == ["stage"]
    detail = row["factors"][0]["cado_stage"]
    assert detail["stage"] == "freerel"
    assert detail["stopped_before"] == "sieving"
    assert detail["murphy_e"] == "1.233e-05"
    assert detail["free_relations"] == "969"
    assert "Free relations" in row["factors"][0]["value"]
    report = (tmp_path / "output" / f"factorization-{created['id'][:12]}.txt")
    assert "Report for" in report.read_text(encoding="utf-8")


def test_a_gated_run_without_the_stop_marker_fails(tmp_path, monkeypatch):
    """Exiting zero is not evidence the stage ran; the marker is."""

    manager = _manager(tmp_path, monkeypatch)
    _capture(manager, monkeypatch, ["Info:Polynomial Selection (size optimized): Starting\n"])
    try:
        created = _staged(manager, "freerel")
        manager._futures[created["id"]].result(timeout=60)
        row = manager.database.get_job(created["id"])
    finally:
        manager.shutdown()
    assert row["status"] == "failed"
    assert "without stopping at sieving" in (row["error"] or "")


def test_the_last_stage_is_an_ordinary_complete_factorization(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch)
    commands = _capture(manager, monkeypatch, [FINISHED])
    try:
        created = _staged(manager, "sqrt")
        manager._futures[created["id"]].result(timeout=60)
        row = manager.database.get_job(created["id"])
    finally:
        manager.shutdown()
    assert not [item for item in commands[0] if item.endswith(".run=false")]
    assert row["status"] == "completed"
    assert sorted(factor["value"] for factor in row["factors"]) == [
        "100000000000000000000000000319", "100000000000000000000000005277",
    ]


def test_the_last_stage_without_factors_is_inconclusive(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch)
    _capture(manager, monkeypatch, ["Info:Square Root: Starting\n"])
    try:
        created = _staged(manager, "sqrt")
        manager._futures[created["id"]].result(timeout=60)
        row = manager.database.get_job(created["id"])
    finally:
        manager.shutdown()
    assert row["status"] == "failed"
    assert "inconclusive" in (row["error"] or "")


def test_advancing_continues_in_the_same_working_directory(tmp_path, monkeypatch):
    """The second pass must not use the parameters snapshot: it records the old gate."""

    manager = _manager(tmp_path, monkeypatch)
    commands = _capture(manager, monkeypatch, [STOPPED_AT_SIEVING, STOPPED_AT_PURGE])
    try:
        created = _staged(manager, "freerel")
        manager._futures[created["id"]].result(timeout=60)
        # A snapshot exists after the first pass, as it would in a real run.
        snapshot = tmp_path / "jobs" / created["id"] / "cado"
        snapshot.mkdir(parents=True, exist_ok=True)
        (snapshot / "c60.parameters_snapshot.0").write_text("N=1\n", encoding="utf-8")
        advanced = manager.advance_cado_stage(created["id"], "duplicates2")
        assert advanced["cado_stage"] == "duplicates2"
        manager._futures[created["id"]].result(timeout=60)
        row = manager.database.get_job(created["id"])
    finally:
        manager.shutdown()
    second = commands[1]
    assert "tasks.filter.purge.run=false" in second
    assert not any("parameters_snapshot" in item for item in second)
    assert "--workdir" in second
    assert row["status"] == "completed"
    assert row["factors"][0]["cado_stage"]["stage"] == "duplicates2"
    assert row["factors"][0]["cado_stage"]["relations"] == "52723"


def test_an_earlier_stage_cannot_be_re_run(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch)
    _capture(manager, monkeypatch, [STOPPED_AT_SIEVING])
    try:
        created = _staged(manager, "sieving")
        manager._futures[created["id"]].result(timeout=60)
        with pytest.raises(ValueError, match="must come after 'sieving'"):
            manager.advance_cado_stage(created["id"], "freerel")
        with pytest.raises(ValueError, match="must come after 'sieving'"):
            manager.advance_cado_stage(created["id"], "sieving")
        with pytest.raises(ValueError, match="must be one of"):
            manager.advance_cado_stage(created["id"], "nonsense")
    finally:
        manager.shutdown()


def test_only_a_staged_job_can_be_advanced(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch)
    _capture(manager, monkeypatch, ["Factors: 101 103\n"])
    try:
        created = manager.create(
            expression="10403", number=10403, requested_backend="cado", threads=1,
            pretest_level=20, trial_bound=100, cado_parameter_size=None,
        )
        manager._futures[created["id"]].result(timeout=60)
        with pytest.raises(ValueError, match="Only a staged CADO-NFS job"):
            manager.advance_cado_stage(created["id"], "sieving")
        with pytest.raises(KeyError):
            manager.advance_cado_stage("missing", "sieving")
    finally:
        manager.shutdown()


def test_a_staged_job_needs_a_stage_and_the_stage_must_exist(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch)
    try:
        with pytest.raises(ValueError, match="needs the stage to run up to"):
            manager.create(
                expression="10403", number=10403, requested_backend="cado_stage",
                threads=1, pretest_level=20, trial_bound=100, cado_parameter_size=None,
            )
        with pytest.raises(ValueError, match="must be one of"):
            manager.create(
                expression="10403", number=10403, requested_backend="cado_stage",
                threads=1, pretest_level=20, trial_bound=100, cado_parameter_size=None,
                cado_stage="sieve",
            )
    finally:
        manager.shutdown()


# --- The API --------------------------------------------------------------------------


@pytest.fixture()
def api(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(main, "database", Database(tmp_path / "api.sqlite3"))
    client = TestClient(main.app, base_url="http://127.0.0.1")
    client.headers["X-Numerisect-Token"] = client.get("/api/session").json()["request_token"]
    return client


def test_the_stage_list_is_served_in_order(api):
    payload = api.get("/api/factor/cado-stages").json()
    assert [item["stage"] for item in payload["stages"]] == list(CADO_STAGE_ORDER)
    assert payload["stages"][4]["parameter"] == "tasks.sieve.sieving.run"
    assert "continues from there" in payload["note"]


def test_advancing_an_unknown_job_is_not_found(api):
    response = api.post("/api/jobs/missing/cado-stage", json={"stage": "sieving"})
    assert response.status_code == 404


def test_an_invalid_stage_is_rejected_by_the_api(api):
    response = api.post("/api/jobs/missing/cado-stage", json={"stage": "x" * 80})
    assert response.status_code == 422
