"""Faceted job search and saved searches (roadmap item 135).

Search already filtered by text, status, engine and date. What it could not do was say
how much of each kind it had matched, or remember a search worth repeating. Both are
counted and stored in SQLite, under exactly the filters the result list used — a count
taken under different filters would be another question's answer displayed beside it,
which these tests pin.
"""

import pytest
from fastapi.testclient import TestClient

from numerisect import main
from numerisect.database import Database

JOBS = [
    ("a1", "8051", 4, "completed", "pari_trial"),
    ("a2", "10403", 5, "completed", "pari_trial"),
    ("a3", "2^89-1", 27, "failed", "yafu"),
    ("a4", "2^127-1", 39, "completed", "yafu"),
    ("a5", "10^70+7", 71, "cancelled", "cado"),
    ("a6", "10^100+267", 101, "failed", "cado"),
]


def _database(tmp_path) -> Database:
    database = Database(tmp_path / "jobs.sqlite3")
    for identifier, expression, digits, status, backend in JOBS:
        database.create_job({
            "id": identifier,
            "expression": expression,
            "number": "9" * digits,
            "digits": digits,
            "negative": 0,
            "requested_backend": backend,
            "selected_backend": backend,
            "status": status,
            "phase": "done",
            "threads": 1,
            "pretest_level": 20,
            "trial_bound": 100,
            "workdir": "/nowhere",
            "log_path": "/nowhere/job.log",
        })
    return database


# --- Counting ------------------------------------------------------------------------


def test_facets_count_every_job_when_nothing_is_filtered(tmp_path):
    facets = _database(tmp_path).job_facets()
    assert facets["total"] == 6
    assert {row["value"]: row["count"] for row in facets["status"]} == {
        "completed": 3, "failed": 2, "cancelled": 1,
    }
    assert {row["value"]: row["count"] for row in facets["engine"]} == {
        "pari_trial": 2, "yafu": 2, "cado": 2,
    }
    assert {row["value"]: row["count"] for row in facets["digits"]} == {
        "1-19 digits": 2, "20-59 digits": 2, "60-94 digits": 1, "95+ digits": 1,
    }


def test_a_count_answers_how_many_of_these_not_how_many_altogether(tmp_path):
    """The whole point of a facet: it is scoped to the search beside it."""

    database = _database(tmp_path)
    facets = database.job_facets(engine="cado")
    assert facets["total"] == 2
    assert [row["value"] for row in facets["status"]] == ["cancelled", "failed"]
    assert {row["value"] for row in facets["digits"]} == {"60-94 digits", "95+ digits"}
    # And the same filters give the same rows as the search itself.
    assert len(database.search_jobs(engine="cado")) == facets["total"]


def test_text_and_status_filters_reach_the_counts(tmp_path):
    database = _database(tmp_path)
    assert database.job_facets(q="2^")["total"] == 2
    assert database.job_facets(status="failed")["total"] == 2
    assert database.job_facets(status="failed", q="2^89")["total"] == 1
    # An empty band is left out rather than reported as zero.
    assert database.job_facets(status="cancelled")["digits"] == [
        {"value": "60-94 digits", "count": 1}
    ]


def test_a_search_that_matches_nothing_counts_nothing(tmp_path):
    facets = _database(tmp_path).job_facets(q="no such number")
    assert facets["total"] == 0
    assert facets["status"] == [] and facets["engine"] == [] and facets["digits"] == []


def test_the_counts_are_ordered_by_size(tmp_path):
    counts = [row["count"] for row in _database(tmp_path).job_facets()["status"]]
    assert counts == sorted(counts, reverse=True)


# --- Remembering a search ------------------------------------------------------------


def test_a_search_is_saved_listed_and_deleted(tmp_path):
    database = _database(tmp_path)
    saved = database.save_search("failed CADO", {"status": "failed", "engine": "cado"})
    assert saved["query"] == {"status": "failed", "engine": "cado"}
    assert database.get_search(saved["id"])["name"] == "failed CADO"
    assert [row["name"] for row in database.list_searches()] == ["failed CADO"]
    assert database.delete_search(saved["id"]) is True
    assert database.delete_search(saved["id"]) is False
    assert database.get_search(saved["id"]) is None


def test_saving_the_same_name_replaces_the_search_and_keeps_its_identity(tmp_path):
    database = _database(tmp_path)
    first = database.save_search("mine", {"status": "failed"})
    second = database.save_search("mine", {"status": "completed"})
    assert second["id"] == first["id"]
    assert second["created_at"] == first["created_at"]
    assert second["query"] == {"status": "completed"}
    assert len(database.list_searches()) == 1


def test_the_most_recently_updated_search_is_listed_first(tmp_path):
    database = _database(tmp_path)
    database.save_search("older", {"status": "failed"})
    database.save_search("newer", {"engine": "yafu"})
    assert [row["name"] for row in database.list_searches()][0] == "newer"


# --- The API --------------------------------------------------------------------------


@pytest.fixture()
def api(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(main, "database", _database(tmp_path))
    client = TestClient(main.app, base_url="http://127.0.0.1")
    client.headers["X-Numerisect-Token"] = client.get("/api/session").json()["request_token"]
    return client


def test_the_facets_route_is_not_swallowed_by_the_job_route(api):
    """`/api/jobs/facets` must not be read as a job whose id is "facets"."""

    response = api.get("/api/jobs/facets")
    assert response.status_code == 200
    assert response.json()["total"] == 6
    assert api.get("/api/jobs/a1").json()["expression"] == "8051"


def test_the_facets_route_echoes_the_filters_it_counted_under(api):
    payload = api.get("/api/jobs/facets", params={"engine": "yafu"}).json()
    assert payload["filters"] == {"engine": "yafu"}
    assert payload["total"] == 2


def test_a_search_round_trips_through_the_api(api):
    created = api.post(
        "/api/searches", json={"name": "big failures", "query": {"status": "failed"}}
    )
    assert created.status_code == 201
    identifier = created.json()["id"]
    assert [row["name"] for row in api.get("/api/searches").json()["searches"]] == [
        "big failures"
    ]
    assert api.delete(f"/api/searches/{identifier}").status_code == 200
    assert api.delete(f"/api/searches/{identifier}").status_code == 404


@pytest.mark.parametrize("query,message", [
    ({"nonsense": "1"}, "may only hold"),
    ({"sort": "expression"}, "not a sortable column"),
    ({"order": "sideways"}, "'asc' or 'desc'"),
    ({"q": "9" * 201}, "limited to 200 characters"),
])
def test_a_saved_search_cannot_hold_what_the_search_would_refuse(api, query, message):
    response = api.post("/api/searches", json={"name": "bad", "query": query})
    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_blank_filters_are_dropped_rather_than_stored(api):
    """An empty status is not a filter, and must not come back as one."""

    saved = api.post(
        "/api/searches",
        json={"name": "everything", "query": {"q": "", "status": "", "engine": "yafu"}},
    ).json()
    assert saved["query"] == {"engine": "yafu"}


def test_a_nameless_search_is_refused(api):
    assert api.post("/api/searches", json={"name": "", "query": {}}).status_code == 422
