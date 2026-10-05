"""Coppersmith's method: a divisor recovered from partial knowledge of it.

This is the one factoring capability here that does not scale with the size of N: it
scales with how much of a factor is unknown. A 1024-bit modulus splits in milliseconds
when 200 bits of its 512-bit prime are unknown, which no sieve could approach, and the
same method finds nothing at all when one more bit is hidden than the proven window
allows. Both behaviours are pinned below, because the second is what keeps the first
honest.

Every modulus here is built from two primes this test knows, so a recovered divisor is
checked against the actual factor rather than against a second implementation.
"""

import pytest
from fastapi.testclient import TestClient

from numerisect import outputs
from numerisect.factor_lab import coppersmith_small_roots
from numerisect.main import app
from numerisect.primes import PrimeEngineError


@pytest.fixture()
def local_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    client = TestClient(app, base_url="http://127.0.0.1")
    client.headers["X-Numerisect-Token"] = client.get("/api/session").json()["request_token"]
    return client


def _modulus(bits: int) -> tuple[int, int, int]:
    """Two primes near 2**bits and their product, from PARI/GP."""

    from numerisect.primes import _run_gp

    lines = _run_gp(
        f'print("P:", nextprime(2^{bits} + 12345));'
        f'print("Q:", nextprime(2^{bits} + 67891)); print("DONE:1");'
    )
    values = {line[:1]: int(line[2:]) for line in lines if line[:2] in {"P:", "Q:"}}
    return values["P"], values["Q"], values["P"] * values["Q"]


@pytest.mark.parametrize("bits,unknown", [
    (64, 16),
    (128, 40),
    (256, 100),
])
def test_a_factor_is_recovered_from_its_leading_bits(bits, unknown):
    prime, _, number = _modulus(bits)
    known = (prime >> unknown) << unknown
    result = coppersmith_small_roots(number, [known, 1], unknown, timeout=120)
    assert result["feasible"] is True
    assert int(result["found"]) >= 1
    assert any(root["divisor"] == str(prime) for root in result["roots"])
    assert all(root["divisor_status"] == "proven_prime" for root in result["roots"])


def test_a_1024_bit_modulus_splits_with_200_bits_of_its_factor_unknown():
    """The headline case, and the reason this method is here at all.

    No general factoring method reaches a 309-digit modulus; this one does it in
    milliseconds, because the work depends on the 200 unknown bits rather than on N.
    """

    prime, _, number = _modulus(512)
    known = (prime >> 200) << 200
    result = coppersmith_small_roots(number, [known, 1], 200, timeout=300)
    assert len(result["number"]) == 309
    assert any(root["divisor"] == str(prime) for root in result["roots"])


def test_the_product_of_the_reported_parts_is_the_modulus():
    """A divisor is only useful if it really divides; the cofactor is reported too."""

    prime, _, number = _modulus(128)
    known = (prime >> 40) << 40
    result = coppersmith_small_roots(number, [known, 1], 40, timeout=120)
    for root in result["roots"]:
        assert int(root["divisor"]) * int(root["cofactor"]) == number


def test_hiding_more_than_the_window_allows_is_reported_as_infeasible():
    """Outside the proven window, silence is not evidence, and must not look like it."""

    prime, _, number = _modulus(128)
    unknown = 120                      # far beyond exp((log B)^2 / log N) for this N
    known = (prime >> unknown) << unknown
    result = coppersmith_small_roots(number, [known, 1], unknown, timeout=120)
    assert result["feasible"] is False
    assert "outside the method's proven window" in result["note"]
    assert "nothing here says anything about the input" in result["note"]
    # PARI raises "bound too large" for such a request, so it is refused before the
    # call rather than surfacing as an engine error.
    assert result["roots"] == [] and int(result["found"]) == 0
    assert "not attempted" in result["engine_refusal"]


def test_the_divisor_bound_is_derived_when_it_is_not_given():
    """For `known + x` the divisor has about as many bits as the known part.

    PARI/GP derives it, so no bit length is computed outside an engine.
    """

    prime, _, number = _modulus(128)
    known = (prime >> 40) << 40
    derived = coppersmith_small_roots(number, [known, 1], 40, timeout=120)
    assert derived["lower_bound_derived"] is True
    assert int(derived["lower_bound"]) > 1
    explicit = coppersmith_small_roots(number, [known, 1], 40, 2**127, timeout=120)
    assert explicit["lower_bound_derived"] is False
    assert explicit["lower_bound"] == str(2**127)
    assert explicit["roots"] == derived["roots"]


def test_a_wrong_known_part_finds_nothing_and_says_so():
    """The method must not manufacture a divisor when the premise is false."""

    prime, _, number = _modulus(128)
    known = ((prime >> 40) << 40) + 2**39      # a known part that is simply wrong
    result = coppersmith_small_roots(number, [known, 1], 8, timeout=120)
    assert int(result["found"]) == 0
    assert result["roots"] == []
    assert "evidence about this polynomial and bound, not about the modulus" in result["note"]


@pytest.mark.parametrize("coefficients,unknown,message", [
    ([1], 8, "at least two coefficients"),
    ([1] * 12, 8, "degree may not exceed"),
    ([1, 0], 8, "leading coefficient must not be zero"),
    ([1, 1], 0, "unknown-bit count must be between"),
    ([1, 1], 2000, "unknown-bit count must be between"),
])
def test_invalid_requests_are_refused(coefficients, unknown, message):
    with pytest.raises(ValueError, match=message):
        coppersmith_small_roots(10403, coefficients, unknown)


def test_a_modulus_below_four_is_refused():
    with pytest.raises(ValueError, match="modulus of at least 4"):
        coppersmith_small_roots(3, [1, 1], 4)


def test_a_root_count_that_disagrees_with_the_rows_is_an_error(monkeypatch):
    from numerisect import factor_lab

    def fake(call, timeout):
        return [
            "DEGREE:1", "POLYNOMIAL:x + 10", "LOWER_BOUND:100", "LOWER_BOUND_DERIVED:0",
            "X_LIMIT:1000", "FEASIBLE:1", "ROOTS:3", "FOUND:0", "DONE:1",
        ]

    monkeypatch.setattr(factor_lab, "_gp_call", fake)
    with pytest.raises(PrimeEngineError, match="root count that disagrees"):
        coppersmith_small_roots(10403, [10, 1], 8)


def test_the_api_serves_it_and_saves_a_report(local_client):
    prime, _, number = _modulus(128)
    known = (prime >> 40) << 40
    response = local_client.post(
        "/api/factor-lab/coppersmith",
        json={
            "expression": str(number),
            "coefficients": [str(known), "1"],
            "unknown_bits": 40,
            "timeout_seconds": 120,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert any(root["divisor"] == str(prime) for root in payload["roots"])
    report = (outputs.OUTPUT_DIR / payload["output_file"]).read_text(encoding="utf-8")
    assert "Proven window" in report
    assert str(prime) in report


def test_the_api_accepts_the_known_part_as_an_expression(local_client):
    """A 512-bit known part is unreadable as a literal; expressions are the point."""

    response = local_client.post(
        "/api/factor-lab/coppersmith",
        json={
            "expression": "(2^64+13)*(2^64+67)",
            "coefficients": ["2^64", "1"],
            "unknown_bits": 8,
            "timeout_seconds": 60,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["polynomial"].startswith("x + ")
