"""Tests for the prime-counting and integer-structure laboratory.

Every expected value below is a published constant, cited in the comment beside
it. The point of the counting feature is that independent algorithms agree, so
the tests check both that agreement is reported when it holds and that a
fabricated disagreement is surfaced rather than silently resolved.
"""

import pytest
from conftest import requires
from fastapi.testclient import TestClient

from numerisect import counting_lab
from numerisect.counting_lab import (
    ALGORITHMS,
    FACTORINT_FLAGS,
    PARI_PRIMEPI_LIMIT,
    counting_algorithm_comparison,
    factorint_strategies,
    integer_structure,
    legendre_phi,
    lenstra_divisors,
    nth_prime_inverses,
)
from numerisect.main import app
from numerisect.primes import PrimeEngineError, integer_arithmetic_profile


def local_client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    token = client.get("/api/session").json()["request_token"]
    client.headers["X-Numerisect-Token"] = token
    return client


def test_module_names_the_routine_behind_every_operation():
    docstring = counting_lab.__doc__ or ""
    for routine in (
        "primecount", "PARI/GP", "primepi", "--legendre", "--meissel", "--lehmer",
        "--lmo", "--deleglise-rivat", "--gourdon", "--double-check", "--phi",
        "--Li-inverse", "--RiemannR-inverse", "isprimepower", "ispseudoprimepower",
        "ispowerful", "istotient", "isfundamental", "ispolygonal", "divisorslenstra",
        "factorint", "gettime",
    ):
        assert routine in docstring, f"{routine} is not attributed in the module docstring"


def test_all_six_primecount_algorithms_are_exposed():
    assert set(ALGORITHMS) == {
        "legendre", "meissel", "lehmer", "lmo", "deleglise-rivat", "gourdon"
    }


# -------------------------------------------------- algorithm comparison ---

@requires("primecount")
def test_every_algorithm_agrees_on_pi_of_ten_to_the_tenth():
    # pi(10^10) = 455,052,511 (Deleglise-Rivat / Gourdon; OEIS A006880).
    result = counting_algorithm_comparison("10000000000", threads=2, timeout=1200)
    assert result["consensus"] == "455052511"
    assert result["agree"] is True
    assert result["disagreement"] is False
    assert result["distinct_values"] == 1
    # Six primecount algorithms + --double-check + PARI primepi (10^10 <= 10^11).
    assert len(result["rows"]) == 8
    assert {row[2] for row in result["rows"]} == {"455052511"}
    assert result["metrics"]["All sources agree"] == "yes"
    assert result["metrics"]["Spread (largest − smallest)"] == "0"
    assert result["metrics"]["PARI/GP primepi included"] == "yes"


@requires("primecount")
def test_pi_of_a_million_agrees_and_is_labelled_as_a_local_measurement():
    # pi(10^6) = 78,498.
    result = counting_algorithm_comparison("1000000", threads=1, timeout=600)
    assert result["consensus"] == "78498"
    assert all(row[2] == "78498" for row in result["rows"])
    assert all(row[4] == "yes" for row in result["rows"])
    assert "Seconds (single local measurement)" in result["columns"]
    assert "not a benchmark of the algorithms" in result["note"]


@requires("primecount")
def test_a_subset_of_algorithms_can_be_selected():
    result = counting_algorithm_comparison(
        "1000000", algorithms=["lmo", "gourdon"], double_check=False,
        include_pari=False, threads=1, timeout=600,
    )
    assert [row[1] for row in result["rows"]] == [
        "primecount --lmo", "primecount --gourdon"
    ]
    assert result["metrics"]["PARI/GP primepi included"] == "not requested"


@requires("primecount")
def test_pari_primepi_is_reported_as_out_of_range_above_its_bound():
    # PARI primepi sieves, so it is only used while x <= 10^11.
    assert PARI_PRIMEPI_LIMIT == 10**11
    result = counting_algorithm_comparison(
        str(PARI_PRIMEPI_LIMIT * 10), algorithms=["gourdon"], double_check=False,
        include_pari=True, threads=2, timeout=1200,
    )
    assert result["metrics"]["PARI/GP primepi included"] == "out of range above 10^11"
    assert len(result["rows"]) == 1


@pytest.mark.parametrize("arguments", [
    {"algorithms": []},                              # nothing selected
    {"algorithms": ["gourdon", "gourdon"]},          # duplicate selection
    {"algorithms": ["atkin"]},                       # unknown algorithm
    {"x": "0"},                                      # x below 1
    {"x": "1" + "0" * 32},                           # x above primecount's 10^31
    {"x": "100000000000000000", "algorithms": ["legendre"]},  # 10^17 elementary
    {"threads": 0},                                  # thread count below 1
    {"timeout": 0},                                  # invalid time limit
])
def test_algorithm_comparison_rejects_invalid_requests(arguments):
    request = {"x": "1000000", "threads": 1, "timeout": 60}
    request.update(arguments)
    with pytest.raises(ValueError):
        counting_algorithm_comparison(**request)


def test_a_fabricated_disagreement_is_reported_and_never_resolved(monkeypatch):
    """A wrong count from one source must surface, not be quietly outvoted.

    The comparison exists to catch exactly this, so the engine boundary is
    replaced with one that returns a corrupted value for a single algorithm.
    """

    truth = 78498  # pi(10^6)
    calls: list[str] = []

    def fake_primecount(arguments, timeout):
        option = next((item for item in arguments if item.startswith("--")), "")
        calls.append(option)
        if option == "--lehmer":
            return truth + 1, "0.001"
        return truth, "0.001"

    monkeypatch.setattr(counting_lab, "_primecount", fake_primecount)
    result = counting_algorithm_comparison(
        "1000000", double_check=False, include_pari=False, threads=1, timeout=60
    )
    assert result["disagreement"] is True
    assert result["agree"] is False
    assert result["distinct_values"] == 2
    assert result["metrics"]["All sources agree"] == "NO — SOURCES DISAGREE"
    assert result["metrics"]["Spread (largest − smallest)"] == "1"
    assert result["note"].startswith("DISAGREEMENT:")
    # The dissenting row is still shown with its own value and its difference.
    dissenting = [row for row in result["rows"] if row[4] == "NO"]
    assert len(dissenting) == 1
    assert dissenting[0][1] == "primecount --lehmer"
    assert dissenting[0][2] == str(truth + 1)
    assert dissenting[0][3] == "1"
    # The majority is reported as a consensus, not as a verdict that ends it.
    assert result["consensus"] == str(truth)
    assert result["metrics"]["Sources holding the consensus"] == "5"


def test_a_missing_primecount_engine_is_reported_rather_than_approximated(monkeypatch):
    monkeypatch.setattr(counting_lab.shutil, "which", lambda name: None)
    with pytest.raises(PrimeEngineError, match="primecount"):
        counting_algorithm_comparison("1000000", algorithms=["gourdon"], timeout=60)


# ------------------------------------------------------- Legendre's phi ---

@requires("primecount")
def test_legendre_phi_of_a_million_and_ten():
    # phi(10^6, 10) = 157,939: the integers in [1, 10^6] divisible by none of
    # 2, 3, 5, 7, 11, 13, 17, 19, 23, 29.
    result = legendre_phi("1000000", 10, threads=1, timeout=600)
    assert result["phi"] == "157939"
    assert result["metrics"]["phi(x, a)"] == "157939"
    # p_10 = 29 and p_11 = 31; 10^6 >= 31^2, so the Legendre identity cannot apply.
    assert result["metrics"]["Identity π(x) = phi(x, a) + a − 1 applies"] == "no, x ≥ p_(a+1)²"
    assert result["identity_applies"] is False
    assert ["a-th prime p_a", "29", "PARI/GP prime"] in result["rows"]
    assert ["Next prime p_(a+1)", "31", "PARI/GP prime"] in result["rows"]
    # The Legendre product x * prod (1 - 1/p) = 157947.223101952238931736...
    product = next(row for row in result["rows"] if row[0].startswith("Legendre product"))
    assert product[1].startswith("157947.2231019522")


@requires("primecount")
def test_the_legendre_identity_is_verified_inside_its_window():
    # p_10 = 29, p_11 = 31 and 900 < 31^2 = 961, so every integer counted by
    # phi(900, 10) above 1 is prime: pi(900) = phi(900, 10) + 10 - 1.
    # phi(900, 10) = 145 and pi(900) = 154.
    result = legendre_phi("900", 10, threads=1, timeout=300)
    assert result["phi"] == "145"
    assert result["identity_applies"] is True
    assert result["identity_verified"] is True
    assert result["metrics"]["Identity verified"] == "yes"
    assert ["π(x)", "154", "PARI/GP primepi"] in result["rows"]


@pytest.mark.parametrize("arguments", [
    ("0", 10, 1, 60),          # x below 1
    ("1000000", -1, 1, 60),    # a below 0
    ("1000000", 100001, 1, 60),  # a above the supported bound
    ("1000000", 10, 0, 60),    # thread count below 1
    ("1" + "0" * 19, 10, 1, 60),  # x above 10^18
])
def test_legendre_phi_rejects_invalid_requests(arguments):
    with pytest.raises(ValueError):
        legendre_phi(*arguments)


# ---------------------------------------- inverse approximations to p_n ---

@requires("primecount")
def test_inverse_approximations_bracket_the_millionth_prime():
    # The 1,000,000th prime is 15,485,863; Li^-1 gives 15,479,083 and
    # R^-1 gives 15,484,039, so R^-1 is the closer of the two.
    result = nth_prime_inverses("1000000", threads=1, timeout=600)
    assert result["exact"] == "15485863"
    assert [row[2] for row in result["rows"]] == ["15479083", "15484039"]
    assert [row[3] for row in result["rows"]] == ["-6780", "-1824"]
    assert result["metrics"]["Closest approximation (chosen by PARI/GP)"] == "R⁻¹(n)"
    assert result["rows"][0][1] == "primecount --Li-inverse"
    assert result["rows"][1][1] == "primecount --RiemannR-inverse"


@pytest.mark.parametrize("arguments", [
    ("0", 1, 60),               # n below 1
    ("1" + "0" * 17, 1, 60),    # n above 10^16
    ("1000000", 0, 60),         # thread count below 1
    ("1000000", 1, 0),          # invalid time limit
])
def test_nth_prime_inverses_rejects_invalid_requests(arguments):
    with pytest.raises(ValueError):
        nth_prime_inverses(*arguments)


# --------------------------------------------- integer-structure predicates ---

def test_isprimepower_returns_the_exponent_of_a_prime_power():
    # 1024 = 2^10, so isprimepower(1024) = 10 with base 2.
    result = integer_structure(1024, 3)
    assert result["prime_power_exponent"] == 10
    assert result["prime_power_base"] == "2"
    assert result["metrics"]["Prime-power exponent"] == "10"
    row = next(row for row in result["rows"] if row[0] == "isprimepower(n)")
    assert row[1] == "PARI/GP isprimepower"
    assert row[2] == "yes"
    assert row[3] == "n = 2^10"


def test_powerful_and_totient_predicates():
    # 72 = 2^3 * 3^2, so every prime valuation is at least 2: ispowerful(72) is true.
    assert integer_structure(72, 3)["is_powerful"] is True
    # 96 is a totient: phi(m) = 96 is solvable, so istotient(96) is true.
    totient = integer_structure(96, 3)
    assert totient["is_totient"] is True
    assert totient["totient_witness"] != "0"
    # 15 = 3 * 5 has two prime valuations equal to 1, so it is not powerful.
    assert integer_structure(15, 3)["is_powerful"] is False


def test_fundamental_discriminant_predicate():
    # -23 is a fundamental discriminant (-23 = 1 mod 4 and squarefree).
    assert integer_structure(-23, 3)["is_fundamental"] is True
    # -24 = 4 * (-6) with -6 = 2 mod 4, so -24 is fundamental as well.
    assert integer_structure(-24, 3)["is_fundamental"] is True
    # -27 = 1 mod 4 but 27 = 3^3 is not squarefree, so -27 is not fundamental.
    assert integer_structure(-27, 3)["is_fundamental"] is False


def test_polygonal_predicate_separates_a_triangular_number_from_its_neighbour():
    # 36 is the 8th triangular number, so ispolygonal(36, 3) is true with index 8.
    triangular = integer_structure(36, 3)
    assert triangular["is_polygonal"] is True
    assert triangular["polygonal_index"] == "8"
    # 35 is not triangular, so ispolygonal(35, 3) is false.
    assert integer_structure(35, 3)["is_polygonal"] is False
    # 36 is also the 6th square number: ispolygonal(36, 4) is true with index 6.
    square = integer_structure(36, 4)
    assert square["is_polygonal"] is True
    assert square["polygonal_index"] == "6"


def test_every_structure_predicate_names_its_pari_routine():
    result = integer_structure(1024, 3)
    routines = {row[1] for row in result["rows"]}
    assert routines == {
        "PARI/GP isprimepower", "PARI/GP ispseudoprimepower", "PARI/GP ispowerful",
        "PARI/GP istotient", "PARI/GP isfundamental", "PARI/GP ispolygonal",
    }


@pytest.mark.parametrize("arguments", [
    (1024, 2, 300),        # a polygon needs at least three sides
    (1024, 3, 0),          # invalid time limit
    (10**2001, 3, 300),    # integer above the supported size
])
def test_integer_structure_rejects_invalid_requests(arguments):
    with pytest.raises(ValueError):
        integer_structure(*arguments)


def test_the_integer_arithmetic_profile_carries_the_same_predicates():
    """The profile gained the predicates that fit it, from the same routines."""

    profile = integer_arithmetic_profile(1024, 0)
    assert profile["prime_power_exponent"] == "10"
    assert profile["prime_power_base"] == "2"
    assert profile["is_powerful"] is True
    assert profile["is_totient"] is True
    assert integer_arithmetic_profile(-23, 0)["is_fundamental_discriminant"] is True
    assert integer_arithmetic_profile(360, 0)["is_powerful"] is False


# ------------------------------------------ divisors in a residue class ---

def test_lenstra_finds_the_divisors_of_a_residue_class():
    # The divisors of 1000 are 1, 2, 4, 5, 8, 10, 20, 25, 40, 50, 100, 125,
    # 200, 250, 500, 1000; the only one congruent to 3 modulo 11 is 25.
    result = lenstra_divisors(1000, 3, 11)
    assert [row[0] for row in result["rows"]] == ["25"]
    assert result["rows"][0][1] == "40"  # cofactor 1000/25
    assert result["metrics"]["Divisors of N in total (τ)"] == "16"
    assert result["found"] == 1


def test_lenstra_reports_an_empty_residue_class():
    # 101 is prime, so its divisors are 1 and 101; 1 = 1 and 101 = 2 modulo 11,
    # and neither is 3 modulo 11.
    result = lenstra_divisors(101, 3, 11)
    assert result["rows"] == []
    assert result["found"] == 0


@pytest.mark.parametrize("arguments", [
    (0, 1, 11),      # N below 1
    (1000, 1, 1),    # modulus below 2
    (1000, 11, 11),  # residue not less than the modulus
    (1000, 22, 11),  # residue outside [0, s)
])
def test_lenstra_rejects_invalid_requests(arguments):
    with pytest.raises(ValueError):
        lenstra_divisors(*arguments)


@pytest.mark.parametrize("arguments", [
    (1000, 1, 3),    # s^3 = 27 is not greater than N: the answer would be partial
    (1000, 7, 14),   # gcd(7, 14) = 7, so the class is not invertible
])
def test_lenstra_refuses_requests_that_violate_its_hypotheses(arguments):
    """PARI returns a silently incomplete list; the engine must refuse instead."""

    with pytest.raises(ValueError):
        lenstra_divisors(*arguments)


# ---------------------------------------------- factorint strategy masks ---

def test_every_factorint_mask_recovers_the_same_factorization():
    # 1000003 and 1000033 are prime, so 1000003 * 1000033 = 1000036000099.
    result = factorint_strategies(1000003 * 1000033, [0, 1, 2, 4, 8], timeout=900)
    assert [row[0] for row in result["rows"]] == ["0", "1", "2", "4", "8"]
    assert all(row[4] == "yes" for row in result["rows"])   # product equals n
    assert all(row[5] == "yes" for row in result["rows"])   # every base certified prime
    assert result["metrics"]["All masks returned the same factorization"] == "yes"
    bases = {row[1] for row in result["sections"][0]["rows"]}
    assert bases == {"1000003", "1000033"}


def test_each_factorint_mask_documents_what_it_disables():
    assert "MPQS" in FACTORINT_FLAGS[1]
    assert "first-stage ECM" in FACTORINT_FLAGS[2]
    assert "Pollard–Brent rho" in FACTORINT_FLAGS[4] and "SQUFOF" in FACTORINT_FLAGS[4]
    assert "final ECM" in FACTORINT_FLAGS[8]
    result = factorint_strategies(1000003 * 1000033, [4], timeout=900)
    assert result["rows"][0][1] == FACTORINT_FLAGS[4]
    # PARI has no standalone SQUFOF entry point, which the report must say.
    assert "no standalone entry point" in result["note"]


@pytest.mark.parametrize("arguments", [
    (1000, []),          # nothing selected
    (1000, [0, 0]),      # duplicate mask
    (1000, [16]),        # mask outside [0, 15]
    (1000, [-1]),        # negative mask
    (1, [0]),            # n below 2
])
def test_factorint_strategies_rejects_invalid_requests(arguments):
    with pytest.raises(ValueError):
        factorint_strategies(*arguments)


# --------------------------------------------------------------- routes ---

@requires("primecount")
def test_counting_routes_save_a_report_and_return_its_filename():
    client = local_client()
    for path, payload in (
        ("/api/counting/algorithm-comparison",
         {"x": "1000000", "algorithms": ["lmo", "gourdon"], "threads": 1}),
        ("/api/counting/phi", {"x": "1000000", "a": 10}),
        ("/api/counting/nth-prime-inverses", {"n": "1000000"}),
    ):
        response = client.post(path, json=payload)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["output_file"].endswith(".txt")
        assert client.get(f"/api/outputs/{body['output_file']}").status_code == 200


def test_structure_routes_save_a_report_and_return_its_filename():
    client = local_client()
    for path, payload in (
        ("/api/structure/predicates", {"expression": "1024", "sides": 3}),
        ("/api/structure/lenstra-divisors",
         {"expression": "1000", "residue": "3", "modulus": "11"}),
        ("/api/structure/factorint-strategies",
         {"expression": "1000036000099", "flags": [0, 4]}),
    ):
        response = client.post(path, json=payload)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["output_file"].endswith(".txt")
        assert client.get(f"/api/outputs/{body['output_file']}").status_code == 200


def test_routes_reject_out_of_bound_requests():
    client = local_client()
    for path, payload in (
        ("/api/counting/algorithm-comparison", {"x": "1000000", "algorithms": ["atkin"]}),
        ("/api/counting/algorithm-comparison", {"x": "1000000", "threads": 0}),
        ("/api/counting/phi", {"x": "1000000", "a": -1}),
        ("/api/counting/nth-prime-inverses", {"n": "0"}),
        ("/api/structure/predicates", {"expression": "1024", "sides": 2}),
        ("/api/structure/lenstra-divisors",
         {"expression": "1000", "residue": "1", "modulus": "3"}),
        ("/api/structure/factorint-strategies", {"expression": "1000", "flags": [16]}),
    ):
        assert client.post(path, json=payload).status_code == 422
