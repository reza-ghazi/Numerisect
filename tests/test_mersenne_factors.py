"""Mersenne trial factoring over the progression q = 2kp + 1.

Each success-path assertion cites a published factorization. The point of the routine is
that M_p is never constructed, so the tests deliberately include an exponent whose
Mersenne number has more than 300,000 decimal digits.
"""

import pytest
from fastapi.testclient import TestClient

from numerisect import outputs
from numerisect.factor_lab import mersenne_factors, special_form_analysis
from numerisect.main import app
from numerisect.primes import PrimeEngineError


@pytest.fixture()
def local_client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    client.headers["X-Numerisect-Token"] = client.get("/api/session").json()["request_token"]
    return client


@pytest.mark.parametrize("exponent,expected", [
    # M_11 = 23 * 89, M_23 = 47 * 178481, M_29 = 233 * 1103 * 2089,
    # M_43 = 431 * 9719 * 2099863. Every factor here is below the k bound used.
    (11, ["23", "89"]),
    (23, ["47", "178481"]),
    (29, ["233", "1103", "2089"]),
    (43, ["431", "9719", "2099863"]),
])
def test_known_mersenne_factorizations_are_recovered(exponent, expected):
    result = mersenne_factors(exponent, k_limit=30_000, timeout=120)
    assert result["factors"] == expected
    assert result["complete"] is True


def test_every_reported_factor_satisfies_both_congruences():
    """q = 2kp + 1 and q = +/-1 (mod 8) are the reason the search is feasible at all."""

    exponent = 43
    result = mersenne_factors(exponent, k_limit=30_000, timeout=120)
    assert result["rows"]
    for factor, k, digits in result["rows"]:
        q, k = int(factor), int(k)
        assert q == 2 * k * exponent + 1
        assert q % 8 in (1, 7)
        assert len(factor) == int(digits)


def test_a_mersenne_far_too_large_to_construct_is_still_factored():
    """M_1000151 has 301,076 decimal digits and a factor at k = 1.

    Nothing here builds that number. If the routine ever tried to, this test would not
    finish.
    """

    result = mersenne_factors(1000151, k_limit=5, timeout=120)
    assert result["factors"] == ["2000303"]
    assert int(result["mersenne_digits"]) == 301076
    assert int(result["factors"][0]) == 2 * 1 * 1000151 + 1


@pytest.mark.parametrize("exponent,k_limit,expected", [
    # Each of these was verified in a separate PARI/GP session: q prime, k a genuine
    # integer in q = 2kp + 1, q = +/-1 (mod 8), and 2^p = 1 (mod q).
    (600_000_001, 100, ["27600000047"]),          # M_p has 180,617,998 digits
    (999_999_001, 200, ["357999642359"]),         # M_p has 301,029,695 digits
    (30_000_001, 100, ["1380000047"]),            # M_p has   9,030,901 digits
])
def test_factors_are_found_for_exponents_in_the_hundreds_of_millions(
    exponent, k_limit, expected
):
    """The reach of this routine is the whole point, so it is pinned.

    M_999999001 has 301,029,695 decimal digits. If anything here ever starts building
    M_p rather than working modulo the candidate, this test stops finishing.
    """

    result = mersenne_factors(exponent, k_limit=k_limit, timeout=120)
    assert result["factors"] == expected
    for factor in result["factors"]:
        q = int(factor)
        assert (q - 1) % (2 * exponent) == 0
        assert q % 8 in (1, 7)


@pytest.mark.parametrize("exponent", [6_972_593, 20_996_011])
def test_a_known_mersenne_prime_yields_no_factor(exponent):
    """A control. M_6972593 and M_20996011 are prime, so no search can find a factor."""

    result = mersenne_factors(exponent, k_limit=200_000, timeout=180)
    assert result["factors"] == []
    assert result["complete"] is True


def test_finding_nothing_is_inconclusive_not_a_primality_claim():
    result = mersenne_factors(1000003, k_limit=2_000, timeout=120)
    assert result["factors"] == []
    assert result["complete"] is True
    assert "inconclusive" in result["note"]
    assert "says nothing about whether" in result["note"]
    assert "Lucas–Lehmer" in result["note"]


def test_automatic_mode_selects_k_dynamically_and_stops_at_the_first_factor():
    result = mersenne_factors(87083, timeout=30)
    assert result["automatic"] is True
    assert result["factors"] == ["77503871"]
    assert result["scanned_k"] == "445"
    assert result["stop_reason"] == "factor_found"
    assert result["complete"] is False


def test_manual_timeout_preserves_factors_and_reports_actual_k():
    result = mersenne_factors(29, k_limit=50_000_000, timeout=1)
    assert {"233", "1103", "2089"}.issubset(result["factors"])
    assert result["stop_reason"] == "timeout"
    assert 1 <= int(result["scanned_k"]) < 50_000_000
    assert result["complete"] is False


def test_a_composite_exponent_is_rejected_by_the_engine():
    # M_p factors this way only for odd prime p; 2^15 - 1 has factors outside 2kp + 1.
    with pytest.raises(PrimeEngineError):
        mersenne_factors(15, k_limit=100, timeout=60)


def test_bounds_are_enforced():
    for kwargs in (
        {"exponent": 1},
        {"exponent": 2},  # M_2 = 3 is the trivial exception to q = 2kp + 1.
        {"exponent": 11, "k_limit": 0},
        {"exponent": 11, "k_limit": 50_000_001},
        {"exponent": 11, "timeout": 0},
    ):
        with pytest.raises(ValueError):
            mersenne_factors(**kwargs)


# --- the regression that made large Mersenne work possible --------------------------------


@pytest.mark.parametrize("expression,digits", [
    ("2^1061-1", "320"),
    ("10^101-1", "101"),
    ("2^4253-1", "1281"),
])
def test_special_form_analysis_does_not_try_to_factor_the_input(expression, digits):
    """Regression: this routine used to attempt a full factorization of Phi_n(b).

    Phi_n(b) is the whole input when n is prime, so 2^1061 - 1 and 10^101 - 1 both
    exhausted a 180-second budget and returned nothing. They now answer immediately.
    """

    result = special_form_analysis(expression, timeout=60)
    assert result["digits"] == digits
    assert result["complete"] is True


def test_the_snfs_polynomial_for_a_mersenne_is_reported():
    result = special_form_analysis("2^1061-1", timeout=60)
    assert result["snfs_suitable"] is True
    assert result["snfs_polynomial"] == "x^1061 - 1"
    # SNFS difficulty is the size of the number, not of a general 320-digit input.
    assert result["snfs_difficulty"] == "319"
    assert result["forms"][0]["detail"] == "n = 2^1061 - 1"


# --- API -----------------------------------------------------------------------------------


def test_mersenne_route_saves_a_report(local_client, tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    response = local_client.post(
        "/api/factor-lab/mersenne-factors",
        json={"exponent": 23, "k_limit": 30000, "timeout_seconds": 120},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["factors"] == ["47", "178481"]
    assert payload["output_file"].endswith(".txt")


def test_mersenne_route_rejects_a_composite_exponent(local_client):
    response = local_client.post(
        "/api/factor-lab/mersenne-factors", json={"exponent": 15, "k_limit": 100}
    )
    assert response.status_code == 422
