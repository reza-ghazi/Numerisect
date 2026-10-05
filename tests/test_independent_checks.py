"""Independent agreement: a second engine asking the same question.

An engine cannot tell you it is right. These checks exist because several unrelated
implementations agreeing is the strongest statement available without a proof — and
where two of them are proof engines, the agreement is stronger still.

The engines are real here: PARI/GP and primesieve are present in CI, YAFU is not, so the
YAFU-dependent assertions tolerate its absence rather than skipping the whole test.
"""

import shutil

import pytest
from fastapi.testclient import TestClient

from numerisect import outputs
from numerisect.main import app
from numerisect.primes import pari_real
from numerisect.verification import (
    _yafu_answer,
    _yafu_verdict,
    cross_check_mersenne,
    cross_check_nth_prime,
    cross_check_primality,
)

HAS_YAFU = shutil.which("yafu") is not None


@pytest.fixture()
def local_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    client = TestClient(app, base_url="http://127.0.0.1")
    client.headers["X-Numerisect-Token"] = client.get("/api/session").json()["request_token"]
    return client


# --- Reading YAFU, which answers in prose ----------------------------------------------


def test_a_yafu_verdict_is_read_from_its_text_not_its_return_value():
    """YAFU prints the verdict and returns the input, so `ans` is not the answer.

    `aprcl(1000003)` prints "Input is prime." and sets `ans = 1000003`. Reading `ans`
    would make every verdict truthy, which is why the text is parsed.
    """

    assert _yafu_verdict("P = 2, Q = 3\nInput is prime.  P7\n\nans = 1000003\n") is True
    assert _yafu_verdict("Input is composite.  C7\n\nans = 1000001\n") is False
    # Neither phrase, or both, is no verdict at all.
    assert _yafu_verdict("ans = 1000003\n") is None
    assert _yafu_verdict("Input is prime.\nInput is composite.\n") is None


def test_the_llt_answer_is_read_from_the_assignment():
    """`llt` is the one YAFU function whose verdict really is the returned value."""

    assert _yafu_answer("ans = 1\n") == "1"
    assert _yafu_answer("ans = 0\n") == "0"
    assert _yafu_answer("llt(127)\n\nans = 1\n\neof\n") == "1"
    assert _yafu_answer("no assignment here") is None


# --- PARI prints an exponent with a space ----------------------------------------------


@pytest.mark.parametrize("text,expected", [
    ("1.0000000000000000000000000000000000000 E-5", "1.0000000000000000000000000000000000000E-5"),
    ("-5.6312994977126352300 e-5", "-5.6312994977126352300e-5"),
    ("4118052494", "4118052494"),
    ("3948131653.66592570591935380833", "3948131653.66592570591935380833"),
])
def test_a_real_as_pari_prints_it_is_accepted(text, expected):
    """Four separate validators assumed `1e-5` and rejected the engine's own output.

    The approximation comparison failed outright at x = 10^11 although it advertised
    10^31, because PARI writes the exponent as " e-5".
    """

    assert pari_real(text) == expected


@pytest.mark.parametrize("text", ["abc", "1.2.3", "", "e-5", "--1"])
def test_text_that_is_not_a_real_is_rejected(text):
    assert pari_real(text) is None


def test_the_approximation_comparison_works_where_it_used_to_fail():
    """x = 10^11 and above reach exponential notation in the relative error."""

    from numerisect.number_theory import prime_approximation_comparison

    for x in ("100000000000", "10000000000000"):
        result = prime_approximation_comparison(x, 2)
        assert len(result["rows"]) == 4
        riemann = result["rows"][-1]
        assert riemann[0].startswith("Riemann")
        # The normalised value is parseable as a float, space removed, digits intact.
        assert float(riemann[3]) < 0


def test_primesieve_r_of_x_is_compared_with_primecounts():
    """primesieve implements R(x) in a separate codebase from primecount's."""

    from numerisect.number_theory import prime_approximation_comparison

    result = prime_approximation_comparison("1000000000", 2)
    if shutil.which("primesieve") is None:
        assert "R(x), primesieve" not in result["metrics"]
        return
    assert result["metrics"]["R(x) agreement"] == "yes"
    # primecount rounds R(x) to an integer; primesieve prints fractional digits, which
    # is why the comparison is on the integer part rather than on equality.
    assert "." in result["metrics"]["R(x), primesieve"]
    assert "agrees with primecount" in result["note"]


# --- Two Lucas-Lehmer implementations --------------------------------------------------


@pytest.mark.parametrize("exponent,prime", [
    (127, True),       # M_127, prime, known since 1876
    (11, False),       # M_11 = 2047 = 23 * 89
    (2203, True),
    (2207, False),
])
def test_mersenne_primality_agrees_across_engines(exponent, prime):
    result = cross_check_mersenne(exponent, timeout=600)
    assert result["prime"] is prime
    assert result["agree"] is True
    assert result["proven"] is True
    engines = {source["engine"] for source in result["sources"] if source["prime"] is not None}
    assert "PARI/GP Lucas-Lehmer" in engines
    if HAS_YAFU:
        assert "YAFU Lucas-Lehmer" in engines
        assert result["engines"] == 2
        assert "2 independent Lucas-Lehmer implementations agree" in result["note"]


def test_a_composite_exponent_is_refused_rather_than_answered():
    """2^9 - 1 is composite, but not for a Lucas-Lehmer reason.

    YAFU answers 0 for a composite exponent, so continuing would present a one-engine
    verdict as a cross-checked Lucas-Lehmer proof. The refusal states the algebraic
    reason instead.
    """

    with pytest.raises(ValueError, match="divides 2\\^\\(ab\\) - 1"):
        cross_check_mersenne(9, timeout=120)


def test_one_engine_answering_is_not_called_a_cross_check(monkeypatch):
    """A single verdict is that engine's, and the note must not imply agreement."""

    from numerisect import verification

    monkeypatch.setattr(verification, "_yafu", lambda expression, timeout: None)
    result = cross_check_mersenne(127, timeout=300)
    assert result["engines"] == 1
    assert result["prime"] is True
    assert "Only one engine answered" in result["note"]


@pytest.mark.parametrize("exponent", [1, 10_000_001])
def test_an_out_of_range_exponent_is_refused(exponent):
    with pytest.raises(ValueError, match="between 2 and"):
        cross_check_mersenne(exponent)


# --- Two n-th prime implementations ----------------------------------------------------


@pytest.mark.parametrize("index,expected", [
    (1_000_000, "15485863"),          # the millionth prime
    (1_000_000_000, "22801763489"),
])
def test_the_nth_prime_agrees_across_engines(index, expected):
    result = cross_check_nth_prime(index, timeout=600)
    assert result["prime"] == expected
    assert result["agree"] is True
    assert result["engines"] >= 1
    if shutil.which("primecount") and shutil.which("primesieve"):
        assert result["engines"] == 2
        assert "2 independent implementations agree" in result["note"]


def test_an_out_of_range_index_is_refused():
    with pytest.raises(ValueError, match="between 1 and"):
        cross_check_nth_prime(0)


# --- YAFU's APR-CL as a second proof engine --------------------------------------------


def test_the_primality_check_counts_its_proof_engines():
    """PARI's isprime and YAFU's APR-CL are the two proof engines installed."""

    result = cross_check_primality(1000003, timeout=300)
    assert result["prime"] is True and result["agree"] is True and result["proven"] is True
    if HAS_YAFU:
        assert "YAFU APR-CL" in result["proofs"]
        assert len(result["proofs"]) == 2
        assert "Two independent proof engines" in result["note"]
    else:
        assert result["proofs"] == ["PARI/GP isprime"]


def test_a_composite_is_agreed_by_every_engine():
    result = cross_check_primality(1000001, timeout=300)
    assert result["prime"] is False and result["agree"] is True
    assert result["proven"] is False          # proving compositeness is not a prime proof
    for source in result["sources"]:
        assert source["prime"] in (False, None)


def test_aprcl_above_its_proof_range_is_not_labelled_a_proof(monkeypatch):
    """YAFU documents APR-CL as a proof below 6021 digits and BPSW above it."""

    from numerisect import verification

    monkeypatch.setattr(
        verification, "_yafu",
        lambda expression, timeout: ("Input is prime.  P7\n", 0.01),
    )
    big = 10**6100 + 1
    monkeypatch.setattr(verification, "_run_gp", lambda *args, **kwargs: ["1", "1"])
    monkeypatch.setattr(
        verification, "bigsieve_tool_path", lambda: (_ for _ in ()).throw(RuntimeError("off"))
    )
    result = cross_check_primality(big, timeout=60)
    yafu = next(source for source in result["sources"] if source["engine"] == "YAFU APR-CL")
    assert yafu["proof"] is False


# --- The API ---------------------------------------------------------------------------


def test_the_api_serves_both_new_cross_checks(local_client):
    mersenne = local_client.post("/api/verify/mersenne", json={"exponent": 2203})
    assert mersenne.status_code == 200, mersenne.text
    assert mersenne.json()["prime"] is True
    assert (outputs.OUTPUT_DIR / mersenne.json()["output_file"]).is_file()

    nth = local_client.post("/api/verify/nth-prime", json={"index": "10^6"})
    assert nth.status_code == 200, nth.text
    assert nth.json()["prime"] == "15485863"
    report = (outputs.OUTPUT_DIR / nth.json()["output_file"]).read_text(encoding="utf-8")
    assert "15485863" in report


def test_the_api_refuses_a_composite_mersenne_exponent(local_client):
    response = local_client.post("/api/verify/mersenne", json={"exponent": 9})
    assert response.status_code == 422
    assert "Lucas-Lehmer applies to prime exponents" in response.json()["detail"]
