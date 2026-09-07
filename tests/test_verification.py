"""Cross-engine verification, engine self-tests, and large-interval sieving.

These features exist to catch a wrong answer, so the tests are mostly about what
happens when engines disagree or an engine is broken.
"""

import subprocess

import pytest
from conftest import requires
from fastapi.testclient import TestClient

from numerisect.main import app
from numerisect.native_tools import bigsieve_tool_path
from numerisect.primes import PrimeEngineError
from numerisect.verification import (
    SELF_TESTS,
    cross_check_primality,
    cross_check_prime_count,
    self_test,
    sieve_interval,
)


@pytest.fixture()
def local_client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    token = client.get("/api/session").json()["request_token"]
    client.headers["X-Numerisect-Token"] = token
    return client


# --- pi(x) cross-check ---------------------------------------------------------------


@requires("primecount")
def test_independent_methods_agree_on_a_known_prime_count():
    # pi(10^8) = 5761455.
    result = cross_check_prime_count(10**8, threads=4)
    assert result["agree"] is True
    assert result["value"] == "5761455"
    # primecount's six algorithms plus primesieve plus PARI.
    assert result["engines_answering"] >= 3
    assert result["disagreements"] == []


@requires("primecount")
def test_every_primecount_algorithm_is_actually_exercised():
    result = cross_check_prime_count(10**6, threads=2)
    engines = {row["engine"] for row in result["sources"]}
    for algorithm in ("legendre", "meissel", "lehmer", "lmo", "deleglise-rivat", "gourdon"):
        assert f"primecount {algorithm}" in engines


@requires("primecount")
def test_a_disagreement_is_reported_and_no_winner_is_chosen(monkeypatch):
    from numerisect import verification

    real = verification._run

    def wrong_for_one_algorithm(command, timeout=120):
        code, output = real(command, timeout)
        if "--gourdon" in command:
            return code, "999999999\n"  # a deliberately wrong answer
        return code, output

    monkeypatch.setattr(verification, "_run", wrong_for_one_algorithm)
    result = cross_check_prime_count(10**6, threads=2)
    assert result["agree"] is False
    # It must refuse to pick a value rather than trusting the majority.
    assert result["value"] is None
    assert len(result["distinct_values"]) > 1
    assert "DISAGREE" in result["note"]


def test_prime_count_rejects_a_negative_bound():
    with pytest.raises(ValueError):
        cross_check_prime_count(-1)


# --- primality cross-check -----------------------------------------------------------


def test_primality_cross_check_agrees_and_marks_the_proof():
    # 32416190071 is prime.
    result = cross_check_primality(32416190071)
    assert result["agree"] is True
    assert result["prime"] is True
    assert result["proven"] is True
    assert any(row["proof"] and row["prime"] for row in result["sources"])


def test_primality_cross_check_on_a_carmichael_number():
    # 561 = 3 * 11 * 17 is composite but a Fermat pseudoprime to every coprime base.
    result = cross_check_primality(561)
    assert result["agree"] is True
    assert result["prime"] is False


def test_a_probable_result_is_not_called_proven():
    result = cross_check_primality(2**89 - 1)  # a Mersenne prime, but large
    assert result["prime"] is True
    for row in result["sources"]:
        if not row["proof"]:
            assert "BPSW" in row["engine"] or "pseudoprime" in row["engine"]


# --- engine self-test ------------------------------------------------------------------


def test_installed_engines_answer_their_published_constants():
    result = self_test()
    assert result["failed"] == 0, [row for row in result["results"] if row["status"] == "FAIL"]
    assert result["healthy"] is True
    assert result["passed"] >= 5


def test_every_self_test_cites_its_source():
    for engine, checks in SELF_TESTS.items():
        for check in checks:
            assert check["cites"], f"{engine} check has no citation"
            assert check["expect"], f"{engine} check has no expected value"


def test_a_wrong_answer_is_detected(monkeypatch):
    # Simulate a broken engine build and confirm the self-test catches it.
    from numerisect import verification

    monkeypatch.setitem(
        verification.SELF_TESTS,
        "gp",
        [{"question": "deliberately wrong", "program": "print(2+2)", "expect": "5",
          "cites": "a value that is not 4"}],
    )
    result = self_test(["gp"])
    assert result["healthy"] is False
    assert result["failed"] == 1
    assert "WRONG ANSWER" in result["note"]


def test_an_unknown_engine_is_rejected():
    with pytest.raises(ValueError):
        self_test(["not-an-engine"])


# --- large-interval sieve --------------------------------------------------------------


def test_the_sieve_matches_a_known_count_below_2_64():
    # pi(200) - pi(100) = 46 - 25 = 21.
    result = sieve_interval(100, 100, threads=2)
    assert result["count"] == 21
    assert result["status"] == "exact"
    assert result["proven"] is True


def test_the_sieve_includes_small_primes_at_the_interval_start():
    result = sieve_interval(2, 20, small_prime_bound=100, threads=1)
    assert result["primes"][:4] == ["2", "3", "5", "7"]


def test_the_sieve_keeps_primes_below_the_presieve_bound():
    """Regression: a window containing the presieve primes themselves.

    The presieve marks multiples of every small prime. The prime's own position is
    not generally the first multiple in the window, so guarding only the first
    multiple silently deleted 2, 3, 5 and 7 from [0, 10). Every window here starts
    below the presieve bound, which the random cross-checks never generated.
    """

    assert sieve_interval(0, 10, small_prime_bound=1000)["primes"] == ["2", "3", "5", "7"]
    assert sieve_interval(1, 30, small_prime_bound=1000)["primes"][:5] == [
        "2", "3", "5", "7", "11"
    ]
    # pi(100) = 25.
    assert sieve_interval(0, 100, small_prime_bound=1000)["count"] == 25
    # A window starting between small primes must not lose the ones inside it.
    assert sieve_interval(90, 20, small_prime_bound=1000)["primes"] == [
        "97", "101", "103", "107", "109"
    ]


@requires("primesieve")
def test_the_sieve_agrees_with_primesieve_across_random_windows():
    import random

    random.seed(11)
    for _ in range(5):
        start = random.randint(2, 10**11)
        length = random.randint(500, 20000)
        mine = sieve_interval(start, length, small_prime_bound=10000, threads=4)
        # primesieve's -d is inclusive; our interval is half-open.
        reference = subprocess.run(
            ["primesieve", str(start), "-d", str(length - 1), "--count", "-q"],
            capture_output=True, text=True,
        ).stdout.strip().splitlines()[-1]
        assert mine["count"] == int(reference), (start, length)


def test_above_2_64_results_are_probable_and_labelled_so():
    # primesieve refuses this range entirely; PARI is single-threaded there.
    result = sieve_interval(10**30, 5000, threads=4)
    assert result["status"] == "probable"
    assert result["proven"] is False
    assert "not proofs" in result["note"]
    assert result["count"] > 0


def test_the_sieve_agrees_with_pari_above_2_64():
    from numerisect.primes import _run_gp

    start, length = 10**25, 20000
    mine = sieve_interval(start, length, threads=4)
    lines = _run_gp(f"c=0;forprime(p={start},{start + length - 1},c++);print(c)", timeout=300)
    assert mine["count"] == int(lines[-1].strip())


def test_the_sieve_validates_its_arguments():
    for bad in (
        {"start": -1, "length": 10},
        {"start": 100, "length": 0},
        {"start": 100, "length": 10, "small_prime_bound": 1},
        {"start": 100, "length": 10, "threads": 0},
        {"start": 100, "length": 10, "extra_rounds": 999},
    ):
        with pytest.raises(ValueError):
            sieve_interval(**bad)


def test_the_helper_emits_a_completion_marker():
    tool = bigsieve_tool_path()
    output = subprocess.run(
        [str(tool), "100", "100", "1000", "1"], capture_output=True, text=True
    ).stdout
    assert "DONE:1" in output
    assert "STATUS:exact" in output


def test_a_missing_completion_marker_is_an_error(monkeypatch):
    from numerisect import verification

    monkeypatch.setattr(verification, "_run", lambda *a, **k: (0, "PRIME:101\nCOUNT:1\n"))
    with pytest.raises(PrimeEngineError, match="completion marker"):
        sieve_interval(100, 10)


def test_an_inconsistent_count_is_an_error(monkeypatch):
    from numerisect import verification

    monkeypatch.setattr(
        verification, "_run",
        lambda *a, **k: (0, "PRIME:101\nCOUNT:7\nSTATUS:exact\nDONE:1\n"),
    )
    with pytest.raises(PrimeEngineError, match="inconsistent count"):
        sieve_interval(100, 10)


# --- API --------------------------------------------------------------------------------


@requires("primecount")
def test_prime_count_route_saves_a_report(local_client):
    response = local_client.post(
        "/api/verify/prime-count", json={"expression": "10^6", "threads": 2}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["agree"] is True
    assert payload["output_file"].endswith(".txt")


def test_primality_route(local_client):
    response = local_client.post(
        "/api/verify/primality", json={"expression": "32416190071"}
    )
    assert response.status_code == 200
    assert response.json()["prime"] is True


def test_self_test_route(local_client):
    response = local_client.post("/api/verify/self-test", json={})
    assert response.status_code == 200
    assert response.json()["failed"] == 0


def test_sieve_route_caps_the_response_but_saves_everything(local_client):
    response = local_client.post(
        "/api/primes/sieve-interval",
        json={"start": "10^25", "length": 20000, "threads": 4, "preview": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["primes"]) == 5
    assert payload["preview_truncated"] is True
    assert payload["count"] > 5
    assert payload["output_file"].endswith(".txt")


def test_sieve_route_rejects_an_oversized_length(local_client):
    response = local_client.post(
        "/api/primes/sieve-interval", json={"start": "100", "length": 999_999_999}
    )
    assert response.status_code == 422


def test_the_sieve_is_deterministic_across_thread_counts():
    """The parallel presieve and testing must not race.

    The window is split into contiguous chunks so no two threads write the same
    byte; this checks that property holds in practice rather than only by argument.
    """

    reference = None
    for threads in (1, 2, 3, 8, 24):
        result = sieve_interval(10**24, 20000, small_prime_bound=100000, threads=threads)
        if reference is None:
            reference = result["primes"]
        assert result["primes"] == reference, f"thread count {threads} changed the output"
    assert reference
