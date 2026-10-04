"""The Fermat-quotient searches: Wieferich, Wall-Sun-Sun, Wilson, Wolstenholme.

Every success-path assertion names published values, so the predicates are checked
against the literature rather than against a second implementation written here. The
Wolstenholme case also validates the criterion actually implemented: the helper tests
the harmonic form H_{p-1} = 0 (mod p^3), and recovering 16843 is the evidence that this
agrees with the usual binomial definition.
"""

import subprocess

import pytest
from fastapi.testclient import TestClient

from numerisect import outputs
from numerisect.fermat_quotients import SEARCH_KINDS, fermat_quotient_search
from numerisect.main import app
from numerisect.native_tools import fermatq_tool_path
from numerisect.primes import PrimeEngineError


@pytest.fixture()
def local_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    client = TestClient(app, base_url="http://127.0.0.1")
    client.headers["X-Numerisect-Token"] = client.get("/api/session").json()["request_token"]
    return client


@pytest.mark.parametrize("base,end,expected", [
    # The only known Wieferich primes in each base, within the range searched.
    (2, 10**7, ["1093", "3511"]),
    (3, 2 * 10**6, ["11", "1006003"]),
    (5, 100_000, ["2", "20771", "40487"]),
])
def test_known_wieferich_primes_are_recovered(base, end, expected):
    result = fermat_quotient_search("wieferich", 2, end, base=base)
    assert result["hits"] == expected
    assert result["status"] == "complete"
    assert int(result["scanned_to"]) == end


def test_known_wilson_primes_are_recovered():
    """5, 13 and 563 are the only Wilson primes known, and the only ones below 10^4."""

    result = fermat_quotient_search("wilson", 2, 10_000)
    assert result["hits"] == ["5", "13", "563"]
    assert result["complete"] is True


def test_the_harmonic_criterion_recovers_the_known_wolstenholme_prime():
    """16843 is a Wolstenholme prime; nothing below it is.

    This is the check that the implemented congruence, H_{p-1} = 0 (mod p^3), is the
    right one: an off-by-one power would either find nothing or flag every prime.
    """

    result = fermat_quotient_search("wolstenholme", 2, 20_000)
    assert result["hits"] == ["16843"]
    assert int(result["tested"]) == 2262


def test_no_wall_sun_sun_prime_is_claimed_and_absence_is_not_a_proof():
    """None is known. An exhausted range must say so without implying more."""

    result = fermat_quotient_search("wall_sun_sun", 2, 10**6)
    assert result["hits"] == []
    assert result["status"] == "complete"
    assert "says nothing about primes outside that range" in result["note"]


def test_the_fermat_quotient_matches_pari_above_the_64_bit_modulus():
    """Past 2^32 the modulus leaves 64 bits and GMP takes over; the answers must agree.

    PARI/GP is the reference, asked directly rather than reimplemented here.
    """

    from numerisect.primes import _run_gp

    start, end = 2**32, 2**32 + 300
    result = fermat_quotient_search(
        "wieferich", start, end, base=2, near_bound=10**12
    )
    mine = {prime: quotient for prime, quotient in result["near_misses"]}
    lines = _run_gp(
        f"forprime(p={start},{end}, my(m=p^2, r=lift(Mod(2,m)^(p-1)), A=((r-1)/p)%p); "
        'if(A>p/2, A-=p); print("Q:", p, "|", A)); print("DONE:1");'
    )
    reference = {}
    for line in lines:
        if line.startswith("Q:"):
            prime, _, quotient = line[2:].partition("|")
            reference[prime.strip()] = quotient.strip()
    assert reference, "PARI/GP returned no reference values"
    assert mine == reference


def test_near_misses_are_reported_separately_from_hits():
    """A near-miss is not a hit, and the quotient is what makes it interesting."""

    result = fermat_quotient_search("wieferich", 2, 1000, base=2, near_bound=1)
    assert result["hits"] == []
    assert result["near_misses"], "no near-miss found with |A| <= 1 below 1000"
    for prime, quotient in result["near_misses"]:
        assert abs(int(quotient)) <= 1
        assert prime not in result["hits"]


def test_a_candidate_beyond_the_supported_modulus_is_refused_not_skipped():
    """An untested candidate must never read as one that failed the congruence."""

    result = fermat_quotient_search("wilson", 2**32, 2**32 + 200)
    assert int(result["tested"]) == 0
    assert int(result["refused"]) > 0
    assert result["status"] == "refused-wide"
    assert result["complete"] is False
    assert "never reported as a passing one" in result["note"]


def test_an_expired_budget_reports_a_timeout_and_the_range_it_finished():
    """The O(p) predicates cannot finish a wide range; that must not look empty."""

    result = fermat_quotient_search("wilson", 2, 10**9, seconds=1)
    assert result["status"] == "timeout"
    assert result["complete"] is False
    assert "untested, not clear" in result["note"]


@pytest.mark.parametrize("kind,kwargs,message", [
    ("nonsense", {}, "Unknown search kind"),
    ("wilson", {"base": 7}, "no base to vary"),
    ("wolstenholme", {"near_bound": 5}, "Wieferich congruence only"),
    ("wieferich", {"base": 1}, "base must be between"),
])
def test_invalid_requests_are_refused(kind, kwargs, message):
    with pytest.raises(ValueError, match=message):
        fermat_quotient_search(kind, 2, 1000, **kwargs)


def test_an_inverted_or_oversized_range_is_refused():
    with pytest.raises(ValueError, match="2 <= start <= end"):
        fermat_quotient_search("wieferich", 1000, 10)
    with pytest.raises(ValueError, match="may not exceed"):
        fermat_quotient_search("wieferich", 2, 10**14)


def test_a_missing_completion_marker_is_an_error_not_an_empty_result(monkeypatch):
    """Truncated engine output must fail loudly rather than report no hits."""

    class Completed:
        returncode = 0
        stdout = "MODE:wilson\nSTART:2\nEND:1000\n"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Completed())
    with pytest.raises(PrimeEngineError, match="completion marker"):
        fermat_quotient_search("wilson", 2, 1000)


def test_a_hit_count_that_disagrees_with_the_rows_is_an_error(monkeypatch):
    """The count is the cross-check on the rows; a mismatch means output was lost."""

    class Completed:
        returncode = 0
        stdout = (
            "MODE:wilson\nSTART:2\nEND:1000\nHIT:5|\nTESTED:168\nREFUSED:0\n"
            "SCANNED_TO:1000\nHITS:3\nSTATUS:complete\nDONE:1\n"
        )
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Completed())
    with pytest.raises(PrimeEngineError, match="disagrees with its rows"):
        fermat_quotient_search("wilson", 2, 1000)


def test_the_scanner_rejects_a_bad_invocation_rather_than_guessing():
    tool = fermatq_tool_path()
    for arguments in (["unknown-mode", "2", "100"], ["wilson", "100", "2"]):
        completed = subprocess.run(
            [str(tool), *arguments], capture_output=True, text=True, check=False
        )
        assert completed.returncode != 0
        assert "DONE:" not in completed.stdout


def test_every_kind_is_reachable_through_the_api(local_client):
    """Each congruence must be served, and each report must name its own file."""

    for kind in SEARCH_KINDS:
        response = local_client.post(
            "/api/primes/fermat-quotients",
            json={"kind": kind, "start": "2", "end": "5000", "seconds": 120},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["kind"] == kind
        assert payload["columns"] == ["Prime", "Result", "Fermat quotient"]
        assert payload["output_file"].startswith("fermat-quotient-search")
        assert (outputs.OUTPUT_DIR / payload["output_file"]).is_file()
        assert payload["engine"].startswith("numerisect-fermatq")


def test_the_api_refuses_a_base_for_a_congruence_without_one(local_client):
    response = local_client.post(
        "/api/primes/fermat-quotients",
        json={"kind": "wilson", "start": "2", "end": "1000", "base": 7},
    )
    assert response.status_code == 422
    assert "no base to vary" in response.json()["detail"]


def test_the_api_reports_wieferich_hits_with_the_expected_report_body(local_client):
    response = local_client.post(
        "/api/primes/fermat-quotients",
        json={"kind": "wieferich", "start": "2", "end": "5000", "base": 2},
    )
    payload = response.json()
    assert payload["hits"] == ["1093", "3511"]
    report = (outputs.OUTPUT_DIR / payload["output_file"]).read_text(encoding="utf-8")
    assert "a^(p-1) = 1 (mod p^2)" in report
    assert "1093" in report and "3511" in report
