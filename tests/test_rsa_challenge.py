"""RSA Factoring Challenge catalogue, engine verification and effort estimates.

The catalogue is transcribed data, so the test that matters most re-derives every entry
in PARI/GP. A mistyped digit fails the suite instead of reaching a user as a fact.
"""

import pytest
from fastapi.testclient import TestClient

from numerisect import outputs
from numerisect.main import app
from numerisect.primes import _run_gp
from numerisect.rsa_challenge import (
    ANCHOR_CORE_YEARS,
    ANCHOR_NAME,
    BY_NAME,
    ENTRIES,
    catalogue,
    challenge_report,
)

# RSA-100, the smallest challenge number, and its published factorization.
RSA_100 = (
    "1522605027922533360535618378132637429718068114961380688657908494580122963258952"
    "897654000350692006139"
)
RSA_100_P = "37975227936943673922808872755445627854565536638199"
RSA_100_Q = "40094690950920881030683735292761468389214899724061"


@pytest.fixture()
def local_client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    client.headers["X-Numerisect-Token"] = client.get("/api/session").json()["request_token"]
    return client


# --- the catalogue is data, and data can be wrong -------------------------------------


def test_every_catalogue_entry_is_verified_by_the_engine():
    """The integrity test for the whole file, in one PARI/GP run.

    For all 54 entries: the recorded digit and bit lengths must match the value, and the
    value must be composite, which a failed Miller-Rabin round proves outright. For the
    24 entries carrying factors, p * q must reproduce the value and both factors must
    pass Baillie-PSW.
    """

    program = []
    for entry in ENTRIES:
        program.append(f'N={entry["value"]};')
        program.append(
            f'print("{entry["name"]}|", #Str(N), "|", #binary(N), "|",'
            f' if(ispseudoprime(N), 0, 1));'
        )
        if entry["status"] == "factored":
            p, q = entry["factors"]
            program.append(f"p={p}; q={q};")
            program.append(
                f'print("{entry["name"]}|F|", if(p*q == N, 1, 0), "|",'
                f' if(ispseudoprime(p), 1, 0), "|", if(ispseudoprime(q), 1, 0));'
            )
    lines = _run_gp("\n".join(program), timeout=1800)

    sizes, factorizations = {}, {}
    for line in lines:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 4 and parts[1].isdigit():
            sizes[parts[0]] = (int(parts[1]), int(parts[2]), parts[3] == "1")
        elif len(parts) == 5 and parts[1] == "F":
            factorizations[parts[0]] = tuple(p == "1" for p in parts[2:])

    assert len(sizes) == len(ENTRIES) == 54
    for entry in ENTRIES:
        digits, bits, composite = sizes[entry["name"]]
        assert digits == entry["digits"], f"{entry['name']} digit count is wrong"
        assert bits == entry["bits"], f"{entry['name']} bit length is wrong"
        assert composite, f"{entry['name']} is not composite"
        if entry["status"] == "factored":
            product, p_prime, q_prime = factorizations[entry["name"]]
            assert product, f"{entry['name']} factors do not multiply to the value"
            assert p_prime and q_prime, f"{entry['name']} has a composite factor"

    assert len(factorizations) == 24


def test_the_catalogue_lists_every_challenge_number():
    result = catalogue()
    assert len(result["rows"]) == 54
    assert result["metrics"]["Factored"] == "24"
    assert result["metrics"]["Still open"] == "30"
    assert result["metrics"]["Source"]


def test_the_cost_anchor_is_itself_in_the_catalogue():
    """The estimate is scaled from a published measurement, so the anchor must exist."""

    assert ANCHOR_NAME in BY_NAME
    assert BY_NAME[ANCHOR_NAME]["status"] == "factored"
    assert ANCHOR_CORE_YEARS == 2700


# --- reports ---------------------------------------------------------------------------


def test_rsa_100_report_matches_the_published_record():
    result = challenge_report("RSA-100")
    assert result["recognised"] is True
    assert result["digits"] == 100
    assert result["bits"] == 330
    assert result["status"] == "factored"
    assert result["factors"] == [RSA_100_P, RSA_100_Q]
    assert result["factor_verification"] == "probable"
    assert "checked in PARI/GP" in result["metrics"]["Published factors multiply to the value"]


def test_a_challenge_number_can_be_recognised_from_its_value():
    result = challenge_report(RSA_100)
    assert result["name"] == "RSA-100"
    assert result["recognised"] is True


def test_an_open_challenge_is_not_called_unfactorable():
    result = challenge_report("RSA-2048")
    assert result["status"] == "open"
    assert result["factors"] == []
    assert result["digits"] == 617
    assert result["bits"] == 2048
    assert "not a proof that it resists factoring" in result["note"]


def test_an_unlisted_semiprime_is_reported_without_pretending_it_is_a_challenge():
    # 8051 = 83 * 97, far too small to be a challenge number.
    result = challenge_report("8051")
    assert result["recognised"] is False
    assert result["status"] == "unlisted"
    assert result["factors"] == []
    assert "not one of the published challenge numbers" in result["note"]


def test_the_effort_estimate_grows_with_size_and_is_labelled_heuristic():
    small = challenge_report("RSA-100")
    large = challenge_report("RSA-2048")
    assert large["core_years"] > small["core_years"]
    # The anchor must reproduce its own published figure.
    anchor = challenge_report(ANCHOR_NAME)
    assert abs(anchor["core_years"] - ANCHOR_CORE_YEARS) / ANCHOR_CORE_YEARS < 0.01
    for report in (small, large, anchor):
        assert "heuristic planning estimate" in report["note"]
        assert "no proven running time" in report["note"]


def test_the_factors_can_be_proven_prime_rather_than_probable():
    probable = challenge_report("RSA-100")
    assert probable["factor_verification"] == "probable"
    assert "not a proof" in probable["metrics"]["Both factors prime"]

    proven = challenge_report("RSA-100", prove_factors=True, proof_seconds=120)
    assert proven["factor_verification"] == "proven"
    assert "proven with isprime" in proven["metrics"]["Both factors prime"]


def test_an_exhausted_proof_budget_is_inconclusive_not_a_weaker_claim(monkeypatch):
    """A proof that ran out of time must not silently become a probable-prime claim.

    PARI proves the published factors quickly even at 130 digits, so the exhausted path
    is forced here rather than waited for.
    """

    from numerisect import rsa_challenge

    real = rsa_challenge._run_gp

    def timed_out(program, timeout=None):
        lines = real(program, timeout=timeout)
        return [
            "FACTOR_PRIMALITY:inconclusive" if line.startswith("FACTOR_PRIMALITY:") else line
            for line in lines
        ]

    monkeypatch.setattr(rsa_challenge, "_run_gp", timed_out)
    starved = challenge_report("RSA-250", prove_factors=True, proof_seconds=1)
    assert starved["factor_verification"] == "inconclusive"
    assert "inconclusive" in starved["metrics"]["Both factors prime"]


def test_invalid_input_is_rejected():
    for bad in ("", "RSA-999999999", "not a number", "12x34"):
        with pytest.raises(ValueError):
            challenge_report(bad)
    with pytest.raises(ValueError):
        challenge_report("RSA-100", proof_seconds=0)
    with pytest.raises(ValueError):
        challenge_report("RSA-100", timeout=0)


# --- API ---------------------------------------------------------------------------------


def test_catalogue_route(local_client, tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    response = local_client.get("/api/factor-lab/rsa-catalogue")
    assert response.status_code == 200
    assert len(response.json()["rows"]) == 54


def test_report_route_saves_a_report(local_client, tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    response = local_client.post(
        "/api/factor-lab/rsa-challenge", json={"target": "RSA-129"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["digits"] == 129
    assert payload["output_file"].endswith(".txt")


def test_report_route_rejects_an_unknown_name(local_client):
    response = local_client.post(
        "/api/factor-lab/rsa-challenge", json={"target": "RSA-not-a-thing"}
    )
    assert response.status_code == 422
