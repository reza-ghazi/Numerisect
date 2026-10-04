"""CFRAC, Lehman's deterministic method and Hart's one-line factorization.

Every split is checked by multiplying the parts back and by asking PARI/GP for the
factorization independently, so a shared mistake in the helper and the test cannot make
a wrong answer look right. The methods are not expected to be fast: the point of each is
recorded in `CLASSIC_METHODS`, and the tests cover what each one is for.
"""

import subprocess

import pytest
from fastapi.testclient import TestClient

from numerisect import outputs
from numerisect.factor_lab import CLASSIC_METHODS, classic_factor
from numerisect.main import app
from numerisect.native_tools import classic_tool_path
from numerisect.primes import PrimeEngineError, _run_gp

# Two primes near each other, and two far apart, each product well inside every method's
# reach. The 26-digit semiprime is the case CFRAC exists for.
CLOSE_SEMIPRIME = 1000003 * 1000033
WIDE_SEMIPRIME = 30000000001181000000000429          # 1000000000039 * 30000000000011


@pytest.fixture()
def local_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    client = TestClient(app, base_url="http://127.0.0.1")
    client.headers["X-Numerisect-Token"] = client.get("/api/session").json()["request_token"]
    return client


def _pari_factors(number: int) -> set[str]:
    lines = _run_gp(
        f'f=factor({number});for(i=1,#f~,print("P:",f[i,1]));print("DONE:1");'
    )
    return {line[2:].strip() for line in lines if line.startswith("P:")}


@pytest.mark.parametrize("method", sorted(CLASSIC_METHODS))
def test_every_method_splits_a_semiprime_with_close_factors(method):
    """1000003 * 1000033: Hart's best case, and within reach of all three."""

    result = classic_factor(method, CLOSE_SEMIPRIME, timeout=120)
    assert result["status"] == "factor-found"
    assert int(result["factor"]) * int(result["cofactor"]) == CLOSE_SEMIPRIME
    assert {result["factor"], result["cofactor"]} == _pari_factors(CLOSE_SEMIPRIME)
    assert result["factor_status"] == result["cofactor_status"] == "proven_prime"


def test_cfrac_splits_a_26_digit_semiprime_with_distant_factors():
    """The case CFRAC is for: relations from the continued fraction, no sieve interval."""

    result = classic_factor("cfrac", WIDE_SEMIPRIME, 4000, timeout=180)
    assert result["status"] == "factor-found"
    assert int(result["factor"]) * int(result["cofactor"]) == WIDE_SEMIPRIME
    assert {result["factor"], result["cofactor"]} == _pari_factors(WIDE_SEMIPRIME)
    assert int(result["relations"]) > 0
    assert int(result["base_size"]) > 1
    assert "congruence of squares" in result["how"]


def test_cfrac_reaches_a_32_digit_semiprime():
    """A 32-digit input is comfortably inside CFRAC's historical range."""

    number = 60000000000002257000000000001369     # 1000000000000037 * 60000000000000037
    result = classic_factor("cfrac", number, 8000, timeout=300)
    assert result["status"] == "factor-found"
    assert int(result["factor"]) * int(result["cofactor"]) == number


def test_hart_finds_two_close_factors_almost_immediately():
    """10403 = 101 * 103 falls out on the first iteration."""

    result = classic_factor("hart", 10403, timeout=60)
    assert result["status"] == "factor-found"
    assert int(result["iterations"]) <= 5
    assert {result["factor"], result["cofactor"]} == {"101", "103"}


def test_lehman_finds_a_small_factor_by_its_own_trial_division():
    """Lehman's first phase divides below N^(1/3); the split must still be exact."""

    number = 3 * 1000003
    result = classic_factor("lehman", number, timeout=60)
    assert result["status"] == "factor-found"
    assert int(result["factor"]) * int(result["cofactor"]) == number
    assert "trial division" in result["how"] or "congruence" in result["how"]


def test_an_exhausted_bound_is_inconclusive_and_not_a_primality_claim():
    """Hart with a tight bound on a lopsided semiprime finds nothing, and says so."""

    number = 1009 * 100000000000000000039
    result = classic_factor("hart", number, 5000, timeout=120)
    assert result["status"] == "exhausted"
    assert result["factor"] is None
    assert "not evidence that the number is prime" in result["note"]


def test_a_factor_base_too_small_to_yield_relations_exhausts_cleanly():
    """No relation can be smooth over seven primes; that is not a failure to report."""

    result = classic_factor("cfrac", WIDE_SEMIPRIME, 40, timeout=120)
    assert result["status"] == "exhausted"
    assert int(result["relations"]) == 0
    assert result["factor"] is None


def test_a_prime_input_is_reported_as_such_rather_than_searched():
    """There is no split to find, and the methods must not imply they looked for one."""

    result = classic_factor("cfrac", 1000003, 200, timeout=60)
    assert result["status"] == "prime-input"
    assert "no split to find" in result["note"]


@pytest.mark.parametrize("method,number,bound,message", [
    ("nonsense", 100, None, "Unknown classical method"),
    ("cfrac", 2, None, "at least 4"),
    ("lehman", 100, 50, "takes no bound"),
    ("cfrac", 100, 5, "factor-base bound must be between"),
    ("hart", 100, 10**10, "iteration limit must be between"),
])
def test_invalid_requests_are_refused(method, number, bound, message):
    with pytest.raises(ValueError, match=message):
        classic_factor(method, number, bound)


def test_a_missing_completion_marker_is_an_error(monkeypatch):
    class Completed:
        returncode = 0
        stdout = "MODE:hart\nN:10403\nFACTOR:101|103|Hart one-line\n"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Completed())
    with pytest.raises(PrimeEngineError):
        classic_factor("hart", 10403)


def test_the_helper_rejects_a_bad_invocation():
    tool = classic_tool_path()
    for arguments in (["unknown", "10403"], ["hart", "2"]):
        completed = subprocess.run(
            [str(tool), *arguments], capture_output=True, text=True, check=False
        )
        assert completed.returncode != 0
        assert "DONE:" not in completed.stdout


def test_the_reported_divisor_is_verified_before_it_is_printed():
    """The helper divides to confirm; a non-divisor must never reach the output."""

    completed = subprocess.run(
        [str(classic_tool_path()), "cfrac", str(WIDE_SEMIPRIME), "4000", "120"],
        capture_output=True, text=True, check=False,
    )
    rows = [line for line in completed.stdout.splitlines() if line.startswith("FACTOR:")]
    assert rows
    for row in rows:
        factor, cofactor, _ = row[len("FACTOR:"):].split("|", 2)
        assert int(factor) * int(cofactor) == WIDE_SEMIPRIME


def test_the_api_serves_every_method_and_saves_a_report(local_client):
    for method in sorted(CLASSIC_METHODS):
        response = local_client.post(
            "/api/factor-lab/classic",
            json={"expression": str(CLOSE_SEMIPRIME), "method": method,
                  "timeout_seconds": 120},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["method"] == method
        assert int(payload["factor"]) * int(payload["cofactor"]) == CLOSE_SEMIPRIME
        assert payload["output_file"]
        assert (outputs.OUTPUT_DIR / payload["output_file"]).is_file()


def test_the_api_refuses_a_bound_for_lehman(local_client):
    response = local_client.post(
        "/api/factor-lab/classic",
        json={"expression": str(CLOSE_SEMIPRIME), "method": "lehman", "bound": 100},
    )
    assert response.status_code == 422
    assert "takes no bound" in response.json()["detail"]
