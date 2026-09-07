"""Known-answer, invalid-input, and inconclusive-path tests for the algebra laboratory.

Every success-path assertion cites a standard reference value in a comment.
"""

import pytest
from fastapi.testclient import TestClient

from numerisect import algebra_lab, outputs
from numerisect.algebra_lab import (
    chebotarev_density,
    congruence_solutions,
    cornacchia_representations,
    discrete_logarithm_lab,
    divisor_lattice,
    finite_field_arithmetic,
    number_field_analysis,
    quadratic_ring_analysis,
    reciprocity_trace,
    record_divisor_numbers,
    smoothness_profile,
    sociable_cycles,
    weird_number_analysis,
)
from numerisect.main import app
from numerisect.primes import PrimeEngineError


def local_client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    token = client.get("/api/session").json()["request_token"]
    client.headers["X-Numerisect-Token"] = token
    return client


# ------------------------------------------------------------------ item 45
def test_reciprocity_trace_matches_the_native_kronecker_symbol():
    # (30/101): 101 is prime and 30 is a quadratic residue mod 101 (17^2 = 289 = 30 + 2*101).
    result = reciprocity_trace("30", "101")
    assert result["metrics"]["Symbol value"] == "1"
    assert result["metrics"]["Native kronecker(a, n)"] == "1"
    assert result["metrics"]["Trace verified"] == "yes"
    assert result["metrics"]["Legendre symbol applicable"] == "yes"
    assert [row[1] for row in result["rows"]][0] == "two-power"
    assert result["truncated"] is False

    # (2/5) = -1: 2 is a non-residue modulo 5.
    assert reciprocity_trace("2", "5")["metrics"]["Symbol value"] == "-1"
    # (5/9) = 1 as a Jacobi symbol, but 9 is composite so it is not a Legendre symbol.
    jacobi = reciprocity_trace("5", "9")
    assert jacobi["metrics"]["Legendre symbol applicable"] == "no"
    assert "Jacobi symbol" in jacobi["note"]
    # gcd(a, n) > 1 gives the symbol 0.
    assert reciprocity_trace("6", "9")["metrics"]["Symbol value"] == "0"


def test_reciprocity_trace_truncates_without_losing_the_step_count():
    full = reciprocity_trace("30", "101")
    short = reciprocity_trace("30", "101", trace_limit=2)
    assert len(short["rows"]) == 2
    assert short["truncated"] is True
    assert short["metrics"]["Reduction steps"] == full["metrics"]["Reduction steps"]


def test_reciprocity_trace_rejects_invalid_input():
    with pytest.raises(PrimeEngineError):
        reciprocity_trace("3", "10")  # even denominator
    with pytest.raises(ValueError):
        reciprocity_trace("3", "11", trace_limit=-1)
    with pytest.raises(ValueError):
        reciprocity_trace("not an integer", "11")


# ------------------------------------------------------------------ item 48
def test_congruence_solver_handles_composite_moduli():
    # x^2 + 1 = 0 (mod 65) has the four roots 8, 18, 47, 57 (CRT of +-8 mod 65).
    result = congruence_solutions(["1", "0", "1"], "65")
    assert sorted(int(row[0]) for row in result["rows"]) == [8, 18, 47, 57]
    assert result["complete"] is True
    assert result["metrics"]["Solution count"] == "4"

    # x^2 - 1 = 0 (mod 8) has the four roots 1, 3, 5, 7 (the singular Hensel branch).
    squares = congruence_solutions(["-1", "0", "1"], "8")
    assert sorted(int(row[0]) for row in squares["rows"]) == [1, 3, 5, 7]

    # 3x - 6 = 0 (mod 12) has gcd(3, 12) = 3 solutions: 2, 6, 10.
    linear = congruence_solutions(["-6", "3"], "12")
    assert sorted(int(row[0]) for row in linear["rows"]) == [2, 6, 10]

    # 2x - 3 = 0 (mod 4) is unsolvable because 2 does not divide 3 modulo 4.
    assert congruence_solutions(["-3", "2"], "4")["rows"] == []


def test_congruence_solver_reports_an_exhausted_root_cap_as_inconclusive():
    capped = congruence_solutions(["-1", "0", "1"], "8", limit=2)
    assert capped["complete"] is False
    assert capped["metrics"]["Solution count"] == "inconclusive"
    assert "inconclusive" in capped["note"]


def test_congruence_solver_rejects_invalid_input():
    with pytest.raises(ValueError):
        congruence_solutions(["1"], "10")
    with pytest.raises(ValueError):
        congruence_solutions(["1", "0"], "10")  # zero leading coefficient
    with pytest.raises(ValueError):
        congruence_solutions(["1", "1"], "1")
    with pytest.raises(ValueError):
        congruence_solutions(["1", "1"], "10", limit=0)


# ------------------------------------------------------------------ item 50
@pytest.mark.parametrize("algorithm", ["bsgs", "pohlig_hellman", "pollard_rho", "native"])
def test_discrete_logarithm_algorithms_agree(algorithm):
    # 2 is a primitive root modulo 101 and 2^24 = 5 (mod 101).
    result = discrete_logarithm_lab("5", "2", "101", algorithm)
    assert result["status"] == "solved"
    assert result["metrics"]["Least logarithm"] == "24"
    assert result["metrics"]["Order of g"] == "100"


def test_discrete_logarithm_distinguishes_no_solution_from_inconclusive():
    # 4 generates the index-2 subgroup of squares modulo 101, and 3 is a non-residue.
    exhausted = discrete_logarithm_lab("3", "4", "101", "bsgs")
    assert exhausted["status"] == "no solution"
    assert exhausted["metrics"]["Step budget exhausted"] == "no"

    # A one-step budget cannot decide anything about a 10^6-element group.
    starved = discrete_logarithm_lab("5", "2", "1000003", "bsgs", step_limit=10)
    assert starved["status"] == "inconclusive"
    assert starved["metrics"]["Step budget exhausted"] == "yes"
    assert "inconclusive" in starved["note"]


def test_discrete_logarithm_rejects_invalid_input():
    with pytest.raises(ValueError):
        discrete_logarithm_lab("5", "2", "101", "index_calculus")
    with pytest.raises(ValueError):
        discrete_logarithm_lab("5", "2", "101", "bsgs", step_limit=0)
    with pytest.raises(PrimeEngineError):
        discrete_logarithm_lab("5", "10", "100", "bsgs")  # base is not a unit


# ------------------------------------------------------------------ item 57
def test_finite_field_arithmetic_over_an_extension():
    # F_8 = F_2[a]/(a^3 + a^2 + 1) from ffinit; a is primitive of order 7.
    result = finite_field_arithmetic("2", 3, [], ["0", "1"], ["1", "1"], 5)
    assert result["metrics"]["Field order p^m"] == "8"
    assert result["metrics"]["Order of a"] == "7"
    assert result["metrics"]["a is primitive"] == "yes"
    operations = dict(result["rows"])
    # a + (a + 1) = 1 in characteristic two.
    assert operations["sum a + b"] == "1,0,0"

    # F_9 = F_3[a]/(a^2 + 1); (1 + a)(2 + a) = 2 + 3a + a^2 = 1.
    nine = finite_field_arithmetic("3", 2, ["1", "0", "1"], ["1", "1"], ["2", "1"], 3)
    nine_operations = dict(nine["rows"])
    assert nine_operations["product a · b"] == "1,0"
    assert nine_operations["difference a − b"] == "2,0"
    assert nine["metrics"]["Order of a"] == "8"  # 1 + a generates F_9^*


def test_finite_field_arithmetic_over_a_prime_field():
    # F_7: 3 * 5 = 15 = 1, and 3 is a primitive root of order 6.
    result = finite_field_arithmetic("7", 1, [], ["3"], ["5"], 4)
    operations = dict(result["rows"])
    assert operations["product a · b"] == "1"
    assert result["metrics"]["Order of a"] == "6"
    assert result["metrics"]["Order of the modulus root"] == "not applicable"


def test_finite_field_rejects_invalid_input():
    with pytest.raises(PrimeEngineError):
        finite_field_arithmetic("4", 2, [], ["1"], ["1"])  # PARI's isprime rejects p = 4
    with pytest.raises(ValueError):
        finite_field_arithmetic("2", 0, [], ["1"], ["1"])
    with pytest.raises(ValueError):
        finite_field_arithmetic("2", 3, ["1", "1"], ["1"], ["1"])  # wrong modulus degree
    with pytest.raises(PrimeEngineError):
        # x^2 + 1 factors as (x + 1)^2 over F_2, so it is not a valid reduction polynomial.
        finite_field_arithmetic("2", 2, ["1", "0", "1"], ["1"], ["1"])


# ------------------------------------------------------------------ item 61
def test_divisor_lattice_enumerates_divisors_and_covering_edges():
    # 60 = 2^2 * 3 * 5 has 12 divisors, sigma(60) = 168, and 20 covering pairs.
    result = divisor_lattice("60")
    assert result["metrics"]["Divisor count τ(n)"] == "12"
    assert result["metrics"]["Divisor sum σ(n)"] == "168"
    assert result["metrics"]["Lattice covering edges"] == "20"
    assert len(result["rows"]) == 12
    assert ["4", "15", "2", "no"] in result["rows"]  # factor pair 4 * 15 = 60
    assert result["truncated"] is False


def test_divisor_lattice_respects_its_row_and_lattice_caps():
    capped = divisor_lattice("60", divisor_limit=4, lattice_cap=3)
    assert len(capped["rows"]) == 4
    assert capped["truncated"] is True
    assert capped["metrics"]["Lattice covering edges"] == "not enumerated"


def test_divisor_lattice_rejects_invalid_input():
    with pytest.raises(ValueError):
        divisor_lattice("0")
    with pytest.raises(ValueError):
        divisor_lattice("60", divisor_limit=0)


# ------------------------------------------------------------------ item 68
def test_smoothness_profile_is_exact():
    # 720 = 2^4 * 3^2 * 5 is 5-smooth but not 5-powersmooth because 2^4 = 16 > 5.
    result = smoothness_profile("720", "5", "3")
    assert result["metrics"]["Smoothness bound (exact)"] == "5"
    assert result["metrics"]["Powersmoothness bound (exact)"] == "16"
    assert result["metrics"]["Roughness bound (exact)"] == "2"
    assert result["metrics"]["5-smooth"] == "yes"
    assert result["metrics"]["5-powersmooth"] == "no"
    assert result["metrics"]["3-rough"] == "no"

    # 1001 = 7 * 11 * 13 is 7-rough and 13-smooth.
    rough = smoothness_profile("1001", "13", "7")
    assert rough["metrics"]["7-rough"] == "yes"
    assert rough["metrics"]["13-smooth"] == "yes"


def test_smoothness_profile_rejects_invalid_input():
    with pytest.raises(ValueError):
        smoothness_profile("1", "10", "2")
    with pytest.raises(ValueError):
        smoothness_profile("30", "1", "2")


# ------------------------------------------------------------------ item 69
def test_record_number_families():
    # 60 is highly composite, superabundant, superior highly composite, and
    # colossally abundant (Ramanujan 1915; Alaoglu-Erdos 1944).
    result = record_divisor_numbers("60", "200", 20)
    assert result["metrics"]["Highly composite"] == "yes"
    assert result["metrics"]["Superabundant"] == "yes"
    assert result["metrics"]["Superior highly composite"] == "yes"
    assert result["metrics"]["Colossally abundant"] == "yes"
    families = {row[0] for row in result["rows"]}
    assert families == {
        "highly composite", "superabundant",
        "superior highly composite", "colossally abundant",
    }
    highly_composite = [row[1] for row in result["rows"] if row[0] == "highly composite"]
    # A005180: 1, 2, 4, 6, 12, 24, 36, 48, 60, 120, 180 below 200.
    assert highly_composite == ["1", "2", "4", "6", "12", "24", "36", "48", "60", "120", "180"]

    # 8 is neither highly composite (tau(8) = 4 = tau(6)) nor superabundant.
    assert record_divisor_numbers("8", "100", 20)["metrics"]["Highly composite"] == "no"


def test_record_numbers_rejects_invalid_input():
    with pytest.raises(ValueError):
        record_divisor_numbers("0", "100")
    with pytest.raises(ValueError):
        record_divisor_numbers("60", "10" + "0" * 20)


# ------------------------------------------------------------------ item 70
def test_weird_and_abundance_classification():
    # 70 is the smallest weird number: abundant (sigma = 144) but not semiperfect.
    weird = weird_number_analysis("70")
    assert weird["metrics"]["σ(n)"] == "144"
    assert weird["metrics"]["Abundance σ(n) − 2n"] == "4"
    assert weird["metrics"]["Classification"] == "abundant"
    assert weird["semiperfect"] == "no"
    assert weird["weird"] == "yes"
    assert weird["rows"] == []

    # 12 is abundant and semiperfect: 1 + 2 + 3 + 6 = 12.
    semiperfect = weird_number_analysis("12")
    assert semiperfect["semiperfect"] == "yes"
    assert semiperfect["weird"] == "no"
    assert sum(int(row[0]) for row in semiperfect["rows"]) == 12

    # 6 is perfect, 8 is deficient, 120 is 3-multiperfect, 16 is almost perfect.
    assert weird_number_analysis("6")["metrics"]["Classification"] == "perfect"
    assert weird_number_analysis("8")["metrics"]["Classification"] == "deficient"
    assert weird_number_analysis("120")["metrics"]["Multiperfect multiplier k"] == "3"
    assert weird_number_analysis("16")["metrics"]["Almost perfect"] == "yes"


def test_weird_analysis_reports_an_exhausted_subset_cap_as_inconclusive():
    capped = weird_number_analysis("70", subset_cap=2)
    assert capped["semiperfect"] == "inconclusive"
    assert capped["weird"] == "inconclusive"
    assert "inconclusive" in capped["note"]


def test_weird_analysis_rejects_invalid_input():
    with pytest.raises(ValueError):
        weird_number_analysis("0")
    with pytest.raises(ValueError):
        weird_number_analysis("70", subset_cap=0)


# ------------------------------------------------------------------ item 71
def test_amicable_and_sociable_cycles():
    # 220 and 284 are the classical amicable pair.
    amicable = sociable_cycles("200", "300", 12, "1000000000000", 50)
    cycles = [row for row in amicable["rows"] if row[0].startswith("2 (")]
    assert cycles == [["2 (amicable pair)", "220", "220,284"]]

    # 12496 heads the first sociable 5-cycle (Poulet 1918).
    sociable = sociable_cycles("12496", "12496", 10, "1000000000000", 10, dedupe=False)
    assert sociable["rows"][0][0] == "5 (sociable chain)"
    assert sociable["rows"][0][2] == "12496,14288,15472,14536,14264"

    # 6 is perfect, so it is a cycle of length one.
    perfect = sociable_cycles("6", "6", 4, "1000", 10, dedupe=False)
    assert perfect["rows"][0][0] == "1 (perfect number)"


def test_sociable_search_reports_open_trajectories_as_inconclusive():
    open_run = sociable_cycles("276", "276", 10, "10000", 10, dedupe=False)
    assert open_run["inconclusive"] == 1
    assert open_run["open_runs"][0]["start"] == "276"
    assert "inconclusive" in open_run["note"]


def test_sociable_search_rejects_invalid_input():
    with pytest.raises(ValueError):
        sociable_cycles("300", "200")
    with pytest.raises(ValueError):
        sociable_cycles("1", "100", term_bound="10")
    with pytest.raises(ValueError):
        sociable_cycles("1", "100", max_length=0)


# ------------------------------------------------------------------ item 74
def test_cornacchia_finds_the_classical_representations():
    # 101 = 10^2 + 1^2, and the eight sign/swap images are the only integer solutions.
    result = cornacchia_representations("1", "101")
    assert result["complete"] is True
    assert result["cross_checked"] is True
    assert ["representation", "10", "1", "primitive"] in result["rows"]
    assert result["metrics"]["Total integer solutions"] == "8"
    assert result["metrics"]["Native qfbcornacchia"] == "x = 10, y = 1"
    assert any(row[0].startswith("descent step") for row in result["rows"])

    # 1729 = 1^2 + 3*24^2 = 23^2 + 3*20^2 = 31^2 + 3*16^2 = 41^2 + 3*4^2.
    taxicab = cornacchia_representations("3", "1729")
    pairs = {(row["x"], row["y"]) for row in taxicab["solutions"]}
    assert pairs == {("1", "24"), ("23", "20"), ("31", "16"), ("41", "4")}


def test_cornacchia_cross_check_agrees_for_imprimitive_and_swapped_solutions():
    # Regression: the qfbsolve cross-check must be order- and symmetry-insensitive.
    # 25 = 5^2 + 0^2 = 0^2 + 5^2 = 4^2 + 3^2, giving 12 integer solutions in all.
    squared = cornacchia_representations("1", "25")
    assert squared["cross_checked"] is True
    assert squared["metrics"]["Total integer solutions"] == "12"
    assert {(row["x"], row["y"]) for row in squared["solutions"]} == {
        ("0", "5"), ("4", "3"), ("5", "0"),
    }
    # 50 = 5^2 + 5^2 (imprimitive) = 7^2 + 1^2, giving 12 integer solutions.
    fifty = cornacchia_representations("1", "50")
    assert fifty["cross_checked"] is True
    assert fifty["metrics"]["Total integer solutions"] == "12"
    # d > 1 keeps only the sign symmetry: 9 = 3^2 + 5*0^2 = 2^2 + 5*1^2 gives six.
    assert cornacchia_representations("5", "9")["metrics"]["Total integer solutions"] == "6"
    # 3 is not a sum of two squares.
    empty = cornacchia_representations("1", "3")
    assert empty["solutions"] == []
    assert empty["metrics"]["Native qfbcornacchia"] == "no primitive representation"


def test_cornacchia_rejects_invalid_input():
    with pytest.raises(ValueError):
        cornacchia_representations("0", "101")
    with pytest.raises(ValueError):
        cornacchia_representations("1", "101", trace_limit=-1)


# ------------------------------------------------------------ items 110-111
def test_quadratic_ring_norms_units_and_splitting():
    # Z[i]: 1 + 2i has norm 5 and is prime; 5 splits as (1+2i)(1-2i); h = 1.
    gaussian = quadratic_ring_analysis("-1", "1", "2", "5")
    assert gaussian["metrics"]["Field discriminant"] == "-4"
    assert gaussian["metrics"]["Norm N(a + bω)"] == "5"
    assert gaussian["metrics"]["Element is prime in the ring"] == "yes (prime norm)"
    assert gaussian["metrics"]["Roots of unity"] == "4"
    assert gaussian["metrics"]["Class number h"] == "1"
    assert gaussian["metrics"]["Behavior of p"] == "split"
    assert len(gaussian["rows"]) == 2

    # Z[sqrt(-5)] has class number 2, and 2 ramifies into a non-principal ideal.
    non_principal = quadratic_ring_analysis("-5", "1", "1", "2")
    assert non_principal["metrics"]["Class number h"] == "2"
    assert non_principal["metrics"]["Class group"] == "C2"
    assert non_principal["metrics"]["Behavior of p"] == "ramified"
    assert non_principal["rows"][0][4] == "non-principal"

    # Z[sqrt(2)] has fundamental unit 1 + sqrt(2) of norm -1; 3 + 2*sqrt(2) is a unit.
    real = quadratic_ring_analysis("2", "3", "2", "7")
    assert real["metrics"]["Element is a unit"] == "yes"
    assert real["metrics"]["Fundamental unit"].startswith("1 + 1ω")
    assert "norm -1" in real["metrics"]["Fundamental unit"]


def test_quadratic_ring_rejects_invalid_input():
    with pytest.raises(PrimeEngineError):
        quadratic_ring_analysis("9", "1", "1", "5")  # PARI's issquare rejects the radicand
    with pytest.raises(ValueError):
        quadratic_ring_analysis("1", "1", "1", "5")
    with pytest.raises(PrimeEngineError):
        quadratic_ring_analysis("-1", "1", "1", "4")  # 4 is not prime


# ------------------------------------------------------------ items 112-113
def test_number_field_prime_decomposition():
    # x^3 - x - 1 has discriminant -23, Galois group S3, and class number 1.
    # 23 = p^2 * q ramifies, 59 splits completely, 2 and 3 are inert.
    result = number_field_analysis(["-1", "-1", "0", "1"], ["2", "3", "23", "59"])
    assert result["metrics"]["Field discriminant"] == "-23"
    assert result["metrics"]["Galois group"] == "S3"
    assert result["metrics"]["Signature (r₁, r₂)"] == "(1, 1)"
    assert result["metrics"]["Class number h"] == "1"
    behaviour = {row["prime"]: row["behavior"] for row in result["primes"]}
    assert behaviour == {
        "2": "inert", "3": "inert", "23": "ramified", "59": "totally split",
    }
    # Sum of e*f over the ideals above each prime equals the degree 3.
    for prime in ("2", "3", "23", "59"):
        above = [ideal for ideal in result["ideals"] if ideal["prime"] == prime]
        assert sum(int(ideal["e"]) * int(ideal["f"]) for ideal in above) == 3


def test_number_field_element_factorization():
    # In Q(sqrt(-5)) the element 1 + sqrt(-5) has norm 6 and factors into two ideals.
    result = number_field_analysis(["5", "0", "1"], ["2", "3"], ["1", "1"])
    assert result["metrics"]["Element norm"] == "6"
    assert len(result["element_factors"]) == 2
    assert result["metrics"]["Class number h"] == "2"


def test_number_field_reports_an_exhausted_class_budget_as_inconclusive():
    # A degree-six field with a 40-digit discriminant cannot be resolved in one second.
    result = number_field_analysis(
        ["-3000001", "-2000000", "0", "0", "0", "0", "1"], ["2", "3"], class_seconds=1
    )
    assert result["metrics"]["Class number h"] == "inconclusive"
    assert result["metrics"]["Class number certified"] == "inconclusive"
    assert "inconclusive" in result["note"]
    # The prime decomposition itself is unaffected.
    assert {row["prime"] for row in result["primes"]} == {"2", "3"}


def test_number_field_rejects_invalid_input():
    with pytest.raises(ValueError):
        number_field_analysis(["-1", "1"], ["2"])  # degree one
    with pytest.raises(ValueError):
        number_field_analysis(["-1", "-1", "0", "2"], ["2"])  # not monic
    with pytest.raises(ValueError):
        number_field_analysis(["-1", "-1", "0", "1"], [])
    with pytest.raises(ValueError):
        number_field_analysis(["-1", "-1", "0", "1"], ["2"], ["1", "1", "1", "1"])
    with pytest.raises(PrimeEngineError):
        number_field_analysis(["-1", "0", "0", "1"], ["2"])  # x^3 - 1 is reducible


# ------------------------------------------------------------------ item 115
def test_chebotarev_density_for_the_smallest_s3_field():
    # x^3 - x - 1 has Galois group S3 of order 6: the identity class (pattern 1,1,1)
    # has density 1/6, the three transpositions (2,1) 1/2, and the two 3-cycles 1/3.
    result = chebotarev_density(["-1", "-1", "0", "1"], "2000")
    assert result["metrics"]["Galois group"] == "S3"
    assert result["metrics"]["Galois group order"] == "6"
    assert result["predicted_available"] is True
    predicted = {row[0]: (row[3], float(row[4].rstrip("%"))) for row in result["rows"]}
    assert predicted["1,1,1"][0] == "1"
    assert predicted["2,1"][0] == "3"
    assert predicted["3"][0] == "2"
    assert predicted["1,1,1"][1] == pytest.approx(100 / 6, abs=1e-4)
    assert predicted["2,1"][1] == pytest.approx(50.0, abs=1e-4)
    # The observed densities must be close to the prediction by 2000.
    observed = {row[0]: float(row[2].rstrip("%")) for row in result["rows"]}
    for key in observed:
        assert abs(observed[key] - predicted[key][1]) < 5.0
    assert sum(int(row[1]) for row in result["rows"]) == int(
        result["metrics"]["Unramified primes used"]
    )


def test_chebotarev_reports_an_exhausted_group_budget_as_inconclusive():
    # x^7 - 7x + 3 has Galois group PSL(3,2) of order 168; its splitting field cannot
    # be built in one second, so only the observed densities remain available.
    result = chebotarev_density(
        ["3", "-7", "0", "0", "0", "0", "0", "1"], "300", group_seconds=1
    )
    assert result["metrics"]["Galois group order"] == "168"
    assert result["predicted_available"] is False
    assert all(row[4] == "inconclusive" for row in result["rows"])
    assert "inconclusive" in result["note"]


def test_chebotarev_rejects_invalid_input():
    with pytest.raises(ValueError):
        chebotarev_density(["1", "1"], "1000")  # degree one
    with pytest.raises(ValueError):
        chebotarev_density(["-1", "-1", "0", "2"], "1000")  # not monic
    with pytest.raises(ValueError):
        chebotarev_density(["-1", "-1", "0", "1"], "5")  # bound below 10
    with pytest.raises(PrimeEngineError):
        chebotarev_density(["0", "-1", "0", "1"], "1000")  # x^3 - x is reducible


# ------------------------------------------------ engine-boundary behaviour
def test_engine_timeout_bounds_are_enforced():
    with pytest.raises(ValueError):
        reciprocity_trace("30", "101", timeout=0)
    with pytest.raises(ValueError):
        reciprocity_trace("30", "101", timeout=3601)


def test_a_missing_completion_marker_is_an_error_not_an_empty_success(monkeypatch):
    monkeypatch.setattr(algebra_lab, "_run_gp", lambda program, timeout: ["VALUE:1"])
    with pytest.raises(PrimeEngineError, match="incomplete"):
        reciprocity_trace("30", "101")


def test_a_native_timeout_is_reported_as_an_engine_error(monkeypatch):
    def explode(program, timeout):
        raise PrimeEngineError(f"PARI/GP exceeded the {timeout}-second operation limit")

    monkeypatch.setattr(algebra_lab, "_run_gp", explode)
    with pytest.raises(PrimeEngineError, match="exceeded"):
        chebotarev_density(["-1", "-1", "0", "1"], "2000")


def test_a_missing_engine_program_is_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(algebra_lab, "PROGRAM", tmp_path / "absent.gp")
    with pytest.raises(PrimeEngineError, match="unavailable"):
        reciprocity_trace("30", "101")


def test_arbitrary_precision_inputs_are_supported():
    # 2^127 - 1 is the Mersenne prime M127; (2/M127) = 1 because M127 = 7 (mod 8).
    mersenne = str(2**127 - 1)
    assert reciprocity_trace("2", mersenne)["metrics"]["Symbol value"] == "1"
    # 10^39 + 37 is the least 40-digit prime that is 1 mod 4, so it is a sum of two
    # squares: 24898363632488690006^2 + 19495422242782139999^2 (PARI qfbcornacchia).
    big = cornacchia_representations("1", "1000000000000000000000000000000000000037")
    assert big["complete"] is True
    assert big["cross_checked"] is True
    assert big["metrics"]["Native qfbcornacchia"] == (
        "x = 24898363632488690006, y = 19495422242782139999"
    )
    x, y = int(big["solutions"][0]["x"]), int(big["solutions"][0]["y"])
    assert x * x + y * y == 10**39 + 37


# ---------------------------------------------------------------- API layer
def test_algebra_api_saves_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    client = local_client()
    cases = [
        ("reciprocity", {"a": "30", "n": "101"}, "Symbol value"),
        ("congruence", {"coefficients": ["1", "0", "1"], "modulus": "65"}, "Solution count"),
        ("discrete-log", {"target": "5", "base": "2", "modulus": "101"}, "Least logarithm"),
        (
            "finite-field",
            {
                "characteristic": "2", "degree": 3, "modulus_coefficients": [],
                "a_coefficients": ["0", "1"], "b_coefficients": ["1", "1"], "exponent": 5,
            },
            "Field order p^m",
        ),
        ("divisor-lattice", {"number": "60"}, "Divisor count τ(n)"),
        ("smoothness", {"number": "720", "smooth_bound": "5", "rough_bound": "3"}, "5-smooth"),
        ("record-numbers", {"number": "60", "bound": "200", "limit": 20}, "Highly composite"),
        ("weird-numbers", {"number": "70"}, "Weird"),
        (
            "sociable",
            {"start": "200", "end": "300", "max_length": 12, "limit": 50},
            "Cycles found",
        ),
        ("cornacchia", {"d": "1", "number": "101"}, "qfbsolve cross-check"),
        ("quadratic-ring", {"radicand": "-1", "a": "1", "b": "2", "prime": "5"}, "Class number h"),
        (
            "number-field",
            {"coefficients": ["-1", "-1", "0", "1"], "primes": ["2", "23"]},
            "Field discriminant",
        ),
        (
            "chebotarev",
            {"coefficients": ["-1", "-1", "0", "1"], "bound": "500"},
            "Galois group",
        ),
    ]
    for endpoint, payload, metric in cases:
        response = client.post(f"/api/algebra/{endpoint}", json=payload)
        assert response.status_code == 200, (endpoint, response.text)
        result = response.json()
        assert metric in result["metrics"]
        assert result["engine"] == "PARI/GP"
        report = (tmp_path / result["output_file"]).read_text()
        assert result["note"].split(".")[0] in report
        download = client.get(f'/api/outputs/{result["output_file"]}')
        assert download.status_code == 200
        assert download.text == report
    assert len(list(tmp_path.iterdir())) == len(cases)


@pytest.mark.parametrize("endpoint,payload", [
    ("reciprocity", {"a": "3", "n": "10"}),
    ("reciprocity", {"a": "3", "n": "11", "trace_limit": -1}),
    ("congruence", {"coefficients": ["1"], "modulus": "10"}),
    ("congruence", {"coefficients": ["1", "1"], "modulus": "1"}),
    ("discrete-log", {"target": "5", "base": "2", "modulus": "101", "algorithm": "quantum"}),
    ("discrete-log", {"target": "5", "base": "10", "modulus": "100"}),
    ("finite-field", {"characteristic": "4", "degree": 2,
                      "a_coefficients": ["1"], "b_coefficients": ["1"]}),
    ("divisor-lattice", {"number": "0"}),
    ("smoothness", {"number": "1", "smooth_bound": "10"}),
    ("record-numbers", {"number": "0"}),
    ("weird-numbers", {"number": "0"}),
    ("sociable", {"start": "300", "end": "200"}),
    ("cornacchia", {"d": "0", "number": "101"}),
    ("quadratic-ring", {"radicand": "9"}),
    ("number-field", {"coefficients": ["-1", "-1", "0", "2"], "primes": ["2"]}),
    ("chebotarev", {"coefficients": ["-1", "-1", "0", "1"], "bound": "5"}),
])
def test_algebra_api_failures_do_not_save(endpoint, payload, tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    response = local_client().post(f"/api/algebra/{endpoint}", json=payload)
    assert response.status_code == 422, response.text
    assert list(tmp_path.iterdir()) == []
