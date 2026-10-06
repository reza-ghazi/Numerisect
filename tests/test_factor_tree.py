"""The factor tree: the hierarchy a run actually produced, and when each part appeared.

The job view listed factors flat because nothing computed the numbers between them.
A hierarchy needs n/p1, then (n/p1)/p2, with a label for each cofactor, and those
divisions are arithmetic: PARI/GP performs every one of them in `fl_factor_tree`.

The ordering comes from a second addition — the moment each factor was first printed by
the engine. That is an observation of the engine's own output, not a measurement of the
algorithm, and the tests below pin that distinction: a factor the engines never printed
as a whole number carries no time at all rather than inheriting the job's elapsed time.
"""

import pytest
from fastapi.testclient import TestClient

from numerisect import jobs, main, outputs
from numerisect.database import Database
from numerisect.factor_lab import MAX_TREE_FACTORS, factor_tree
from numerisect.jobs import JobManager
from numerisect.primes import PrimeEngineError

# --- PARI/GP builds the chain ---------------------------------------------------------


def test_the_cofactor_chain_is_computed_and_labelled_by_the_engine():
    result = factor_tree(5040, [2, 2, 2, 2, 3, 3, 5, 7])
    assert result["complete"] is True
    assert result["remaining"] == "1"
    assert result["engine"] == "PARI/GP"
    assert [node["after"] for node in result["nodes"]] == [
        "2520", "1260", "630", "315", "105", "35", "7", "1",
    ]
    assert {node["status"] for node in result["nodes"]} == {"prime"}
    # The last division leaves 1; every earlier cofactor is a real number with a label.
    assert result["nodes"][-1]["cofactor_status"] == "one"
    assert result["nodes"][-2]["cofactor_status"] == "prime"
    assert result["nodes"][0]["cofactor_status"] == "composite"


def test_a_semiprime_gives_one_internal_cofactor():
    result = factor_tree(10403, [101, 103])          # 101 * 103
    assert [node["before"] for node in result["nodes"]] == ["10403", "103"]
    assert result["nodes"][0]["cofactor_status"] == "prime"
    assert result["complete"] is True


def test_a_factor_that_does_not_divide_is_marked_rather_than_applied():
    """A value that does not divide must not silently change the chain."""

    result = factor_tree(100, [7])
    assert result["nodes"][0]["kind"] == "nondivisor"
    assert result["nodes"][0]["before"] == result["nodes"][0]["after"] == "100"
    assert result["complete"] is False
    assert result["remaining"] == "100"


def test_an_incomplete_chain_says_so_rather_than_implying_a_factorization():
    result = factor_tree(2 * 3 * 1009, [2, 3])
    assert result["complete"] is False
    assert result["remaining"] == "1009"
    assert "not a complete factorization" in result["note"]


def test_a_large_cofactor_is_divided_by_the_engine_not_the_interface():
    """The point of the GP routine: a 60-digit cofactor is never divided in Python."""

    prime = 10**30 + 57                              # the smallest 31-digit prime
    result = factor_tree(prime * prime * 3, [3, prime])
    assert result["nodes"][-1]["after"] == str(prime)
    assert result["nodes"][-1]["cofactor_status"] == "prime"


@pytest.mark.parametrize("number,values,timeout,message", [
    (0, [2], 60, "nonzero integer"),
    (12, [], 60, "at least one factor"),
    (12, [2] * (MAX_TREE_FACTORS + 1), 60, "At most"),
    (12, [2], 0, "between 1 and 3600"),
    (12, [2], 4000, "between 1 and 3600"),
])
def test_invalid_tree_requests_are_refused(number, values, timeout, message):
    with pytest.raises(ValueError, match=message):
        factor_tree(number, values, timeout=timeout)


def test_a_node_count_that_disagrees_with_the_rows_is_an_error(monkeypatch):
    from numerisect import factor_lab

    monkeypatch.setattr(
        factor_lab, "_gp_call",
        lambda call, timeout: ["REMAINING:1", "COMPLETE:1", "DONE:4"],
    )
    with pytest.raises(PrimeEngineError, match="reported 4 tree nodes but printed 0"):
        factor_tree(12, [2, 2, 3])


# --- The job manager records when each factor was first printed -----------------------


def _manager(tmp_path, monkeypatch) -> JobManager:
    (tmp_path / "jobs").mkdir()
    (tmp_path / "output").mkdir()
    monkeypatch.setattr(jobs, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path / "output")
    return JobManager(Database(tmp_path / "jobs.sqlite3"))


def test_discovery_times_are_recorded_from_the_engine_output(tmp_path, monkeypatch):
    """1022117 = 1009 * 1013, both printed by PARI/GP as it factors."""

    manager = _manager(tmp_path, monkeypatch)
    try:
        created = manager.create(
            expression="1022117", number=1022117, requested_backend="pari_trial",
            threads=1, pretest_level=20, trial_bound=2000, cado_parameter_size=None,
        )
        manager._futures[created["id"]].result(timeout=60)
        completed = manager.database.get_job(created["id"])
        assert completed is not None and completed["status"] == "completed"
        times = [factor.get("first_seen_seconds") for factor in completed["factors"]]
        assert all(isinstance(value, (int, float)) for value in times), completed["factors"]
        assert all(0 <= value < 60 for value in times)
        for factor in completed["factors"]:
            assert factor["first_seen_note"] == "first printed by the engine at this offset"
        report = (tmp_path / "output" / f"factorization-{created['id'][:12]}.txt")
        assert "first printed" in report.read_text(encoding="utf-8")
    finally:
        manager.shutdown()


def test_a_factor_the_engines_never_printed_carries_no_time(tmp_path, monkeypatch):
    """83 and 97 are too short to track, and inventing a time would be a claim.

    Short numbers appear in engine output for every other reason — curve counts, line
    numbers, bounds — so a three-digit factor cannot be timed from the log. The absent
    key is the honest answer.
    """

    manager = _manager(tmp_path, monkeypatch)
    try:
        created = manager.create(
            expression="8051", number=8051, requested_backend="pari_trial",
            threads=1, pretest_level=20, trial_bound=100, cado_parameter_size=None,
        )
        manager._futures[created["id"]].result(timeout=30)
        completed = manager.database.get_job(created["id"])
        assert completed is not None
        assert [factor["value"] for factor in completed["factors"]] == ["83", "97"]
        for factor in completed["factors"]:
            assert "first_seen_seconds" not in factor
    finally:
        manager.shutdown()


def test_the_sighting_table_is_bounded(tmp_path, monkeypatch):
    """A CADO run prints millions of lines; the bookkeeping must not grow with them."""

    manager = _manager(tmp_path, monkeypatch)
    try:
        manager._first_seen["j"] = {}
        manager._job_clock["j"] = 0.0
        monkeypatch.setattr(JobManager, "MAX_TRACKED_SIGHTINGS", 10)
        for index in range(1000):
            manager._note_sightings("j", f"relation {100000 + index} found\n")
        assert len(manager._first_seen["j"]) == 10
    finally:
        manager.shutdown()


# --- The API arranges a stored job into a tree ----------------------------------------


@pytest.fixture()
def api(tmp_path, monkeypatch) -> TestClient:
    database = Database(tmp_path / "api-jobs.sqlite3")
    monkeypatch.setattr(main, "database", database)
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    client = TestClient(main.app, base_url="http://127.0.0.1")
    client.headers["X-Numerisect-Token"] = client.get("/api/session").json()["request_token"]
    client.database = database                       # type: ignore[attr-defined]
    return client


def _store(database, job_id: str, number: int, factors: list[dict], **extra) -> None:
    import json as _json

    database.create_job({
        "id": job_id,
        "expression": str(number),
        "number": str(number),
        "digits": len(str(number)),
        "negative": 0,
        "requested_backend": "pari_trial",
        "selected_backend": "pari_trial",
        "status": "completed",
        "phase": "Complete",
        "threads": 1,
        "pretest_level": 20,
        "trial_bound": 100000,
        "workdir": "/nowhere",
        "log_path": "/nowhere/job.log",
        "factors_json": _json.dumps(factors),
        **extra,
    })


def test_the_tree_route_returns_the_hierarchy_with_times(api):
    _store(api.database, "tree0001", 1022117, [
        {"value": "1013", "digits": 4, "status": "prime", "engine": "PARI/GP",
         "first_seen_seconds": 0.9},
        {"value": "1009", "digits": 4, "status": "prime", "engine": "PARI/GP",
         "first_seen_seconds": 0.4},
    ])
    payload = api.get("/api/jobs/tree0001/tree").json()
    assert payload["ordered_by"] == "discovery time"
    assert payload["complete"] is True
    kinds = [(node["kind"], node["value"], node["parent"]) for node in payload["nodes"]]
    # Peeled in the order the engine printed them: 1009 first, so 1013 is the cofactor.
    assert kinds == [
        ("input", "1022117", None),
        ("factor", "1009", 0),
        ("cofactor", "1013", 0),
        ("factor", "1013", 2),
    ]
    assert payload["nodes"][1]["first_seen_seconds"] == 0.4
    assert payload["nodes"][2]["child_job_id"] is None
    assert payload["engine"] == "PARI/GP"


def test_untimed_factors_fall_back_to_the_recorded_order(api):
    _store(api.database, "tree0002", 8051, [
        {"value": "83", "digits": 2, "status": "prime", "engine": "PARI/GP"},
        {"value": "97", "digits": 2, "status": "prime", "engine": "PARI/GP"},
    ])
    payload = api.get("/api/jobs/tree0002/tree").json()
    assert payload["ordered_by"] == "recorded order"
    assert [node["value"] for node in payload["nodes"]] == ["8051", "83", "97", "97"]
    assert all(node["first_seen_seconds"] is None for node in payload["nodes"])


def test_a_continued_cofactor_links_to_its_child_job(api):
    """The tree spans runs: a composite cofactor factored later is an internal node."""

    _store(api.database, "parent01", 3 * 1009 * 1013, [
        {"value": "3", "digits": 1, "status": "prime", "engine": "YAFU"},
        {"value": "1009", "digits": 4, "status": "prime", "engine": "YAFU"},
        {"value": "1013", "digits": 4, "status": "prime", "engine": "YAFU"},
    ])
    _store(api.database, "child001", 1009 * 1013, [], parent_job_id="parent01")
    payload = api.get("/api/jobs/parent01/tree").json()
    cofactors = [node for node in payload["nodes"] if node["kind"] == "cofactor"]
    assert [node["value"] for node in cofactors] == ["1022117", "1013"]
    assert cofactors[0]["child_job_id"] == "child001"
    assert cofactors[0]["status"] == "composite"
    assert payload["children"] == [{"job_id": "child001", "number": "1022117"}]


def test_an_incomplete_factor_set_is_not_drawn_as_a_factorization(api):
    _store(api.database, "tree0003", 2 * 3 * 1009, [
        {"value": "2", "digits": 1, "status": "prime", "engine": "YAFU"},
        {"value": "3", "digits": 1, "status": "prime", "engine": "YAFU"},
    ])
    payload = api.get("/api/jobs/tree0003/tree").json()
    assert payload["complete"] is False
    assert payload["remaining"] == "1009"
    assert "not a complete factorization" in payload["note"]


def test_a_report_only_job_has_no_tree(api):
    """A tune measurement is a report about the input, not a decomposition of it."""

    _store(api.database, "tree0004", 8051, [
        {"value": "crossover at 95 digits", "digits": 0, "status": "measurement",
         "engine": "YAFU"},
    ])
    response = api.get("/api/jobs/tree0004/tree")
    assert response.status_code == 409
    assert "no factors to arrange" in response.json()["detail"]


def test_an_unknown_job_is_not_found(api):
    assert api.get("/api/jobs/missing/tree").status_code == 404
