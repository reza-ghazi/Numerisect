import pytest
from conftest import requires

from numerisect.number_theory import (
    aliquot_sequence,
    arithmetic_functions,
    character_symbols,
    chinese_remainder,
    cunningham_chain,
    cyclotomic_polynomial,
    discrete_logarithm,
    divisor_classification,
    eisenstein_prime,
    factor_polynomial,
    factor_strategy,
    hensel_roots,
    modular_roots,
    ntt_primes,
    order_distribution,
    p_adic_valuation,
    perfect_power,
    power_residue_distribution,
    primality_laboratory,
    prime_approximation_comparison,
    quadratic_prime_decomposition,
    special_form_test,
    special_prime_family,
    summatory_functions,
    tonelli_shanks,
    unit_group,
)


def test_character_symbol_domains_are_explicit():
    result = character_symbols("5", "11")
    assert result["metrics"]["Legendre (a/n)"] == "1"
    assert character_symbols("5", "12")["metrics"]["Legendre (a/n)"] == "not applicable"


def test_generalized_crt_handles_non_coprime_systems():
    compatible = chinese_remainder(["2", "5"], ["6", "9"])
    assert compatible["metrics"]["Least nonnegative solution"] == "14"
    assert compatible["metrics"]["Combined modulus"] == "18"
    assert chinese_remainder(["2", "3"], ["6", "9"])["compatible"] is False


def test_modular_roots_and_discrete_logarithm():
    assert modular_roots("4", 2, "7", 10)["rows"] == [["2"], ["5"]]
    assert discrete_logarithm("5", "2", "101")["metrics"]["Least logarithm"] == "24"


def test_unit_group_and_polynomial_factorization():
    group = unit_group("14", 20)
    assert group["metrics"]["Invariant factors"] == "C6"
    assert group["metrics"]["Primitive-root count"] == "2"
    polynomial = factor_polynomial(["-1", "0", "1"], "5")
    assert polynomial["roots"] == ["1", "4"]
    assert ["ℚ", "x - 1", "1"] in polynomial["rows"]


def test_extended_arithmetic_functions_are_exact():
    result = arithmetic_functions("360", 2, "10", 1, 100)
    metrics = result["metrics"]
    assert metrics["Generalized divisor sum σ_2"] == "201110"
    assert metrics["Jordan totient J_2"] == "82944"
    assert metrics["Dedekind ψ"] == "864"
    assert metrics["Squarefree kernel"] == "10"
    assert metrics["10-smooth"] == "yes"


def test_primality_comparison_preserves_probable_vs_proven():
    result = primality_laboratory("561", "2", 0)
    assert result["rows"][0][1] == "pass"
    assert result["rows"][2][1] == "fail"
    assert result["metrics"]["Rigorous verdict"] == "composite"


@pytest.mark.parametrize(
    ("kind", "parameter", "verdict"),
    [("mersenne", "5", "prime"), ("mersenne", "11", "composite"), ("fermat", "2", "prime")],
)
def test_special_form_proofs(kind, parameter, verdict):
    result = special_form_test(kind, parameter)
    assert result["metrics"]["Rigorous verdict"] == verdict
    if kind == "mersenne" and verdict == "composite":
        assert result["factor_search"] == {"kind": "mersenne", "exponent": parameter}
        assert "does not produce a divisor" in result["note"]
    else:
        assert result["factor_search"] is None


def test_perfect_power_and_algebraic_primes():
    power = perfect_power("-64")
    assert power["metrics"]["Maximal base"] == "-4"
    assert power["metrics"]["Maximal exponent"] == "3"
    assert eisenstein_prime("1", "-1")["metrics"]["Eisenstein prime"] == "yes"
    decomposition = quadratic_prime_decomposition("5", "11")
    assert decomposition["metrics"]["Behavior"] == "split"
    assert len(decomposition["rows"]) == 2


def test_factor_strategy_detects_forms_and_small_factors():
    result = factor_strategy("8051", 100, 95)
    assert result["strategy"] == "complete_by_trial_division"
    assert result["rows"] == [["83", "1"], ["97", "1"]]
    assert "Mersenne" in factor_strategy("31", 100, 95)["metrics"]["Detected special forms"]


def test_invalid_native_workbench_inputs_are_rejected():
    with pytest.raises(ValueError):
        chinese_remainder(["1"], ["0"])
    with pytest.raises(ValueError):
        factor_polynomial(["1", "0"], "5")


@requires("primecount")
def test_prime_approximations_and_summatory_functions():
    comparison = prime_approximation_comparison("1000000", 2)
    assert comparison["metrics"]["Exact π(x)"] == "78498"
    assert comparison["rows"][0] == ["Exact pi(x)", "78498", "0", "0"]
    summatory = summatory_functions("1000")
    assert summatory["metrics"]["Mertens M(x)"] == "2"
    assert summatory["metrics"]["Summatory Liouville L(x)"] == "-14"


def test_special_prime_families_are_proven_natively():
    mersenne = special_prime_family("mersenne", 2, 13, 20)
    assert [row[1] for row in mersenne["rows"]] == ["3", "7", "31", "127", "8191"]
    primorial = special_prime_family("primorial", 1, 5, 20)
    assert ["3", "29", "-1"] in primorial["rows"]


def test_cunningham_chain_stops_at_first_composite():
    complete = cunningham_chain("2", 5, 1)
    assert complete["complete"] is True
    assert [row[1] for row in complete["rows"]] == ["2", "5", "11", "23", "47"]
    stopped = cunningham_chain("3", 5, 1)
    assert stopped["complete"] is False
    assert stopped["rows"][-1] == ["3", "15", "composite"]


def test_ntt_prime_generation_preserves_partial_status():
    result = ntt_primes(16, 8, 3, 100_000)
    assert result["complete"] is True
    assert len(result["rows"]) == 3
    assert all((int(prime) - 1) % 256 == 0 for _, prime in result["rows"])


def test_tonelli_shanks_and_hensel_lifting():
    square_roots = tonelli_shanks("10", "13", 20)
    assert square_roots["roots"] == ["6", "7"]
    assert square_roots["rows"][-1][2] == "1"
    lifted = hensel_roots(["-1", "0", "1"], "3", 3, 20)
    assert lifted["rows"] == [["1"], ["26"]]
    singular = hensel_roots(["0", "0", "1"], "2", 3, 20)
    assert singular["rows"] == [["0"], ["4"]]


def test_order_and_power_residue_distributions():
    orders = order_distribution("14", 100)
    assert orders["rows"] == [["1", "1"], ["2", "1"], ["3", "2"], ["6", "2"]]
    residues = power_residue_distribution("11", 2, 100)
    assert residues["metrics"]["Distinct residues"] == "6"
    assert ["0", "1"] in residues["rows"]


def test_valuation_cyclotomic_and_divisor_dynamics():
    valuation = p_adic_valuation("360", "3")
    assert valuation["metrics"]["Valuation vₚ(n)"] == "2"
    cyclotomic = cyclotomic_polynomial(5, "2")
    assert cyclotomic["metrics"]["Degree φ(n)"] == "4"
    assert divisor_classification("220")["metrics"]["Amicable pair"] == "yes"
    aliquot = aliquot_sequence("12", 20)
    assert aliquot["complete"] is True
    assert aliquot["rows"][-1] == ["7", "0"]


def test_a_result_past_cpython_s_integer_string_limit_is_parsed():
    """Regression: engine results above 4,300 digits raised ValueError.

    CPython refuses to convert an integer of more than 4,300 digits to or from a string.
    Engine output routinely exceeds that: Lucas-Lehmer on M_19937 returns 6,002 digits.
    The guard used to be lifted only as a side effect of importing the expression
    evaluator, so the web app worked while importing a boundary module directly did not.
    """

    from numerisect.number_theory import special_form_test

    result = special_form_test("mersenne", "19937", timeout=600)
    assert result["metrics"]["Rigorous verdict"] == "prime"
    assert len(result["metrics"]["Number"]) == 6002


def test_every_engine_boundary_lifts_the_integer_string_limit():
    """The guard must not depend on which module a caller happens to import first."""

    import subprocess
    import sys

    for module in (
        "primes", "number_theory", "factor_lab", "primality_lab", "forms_lab",
        "distribution_lab", "algebra_lab", "visual_lab", "zeta_fields", "verification",
    ):
        limit = subprocess.run(
            [sys.executable, "-c",
             f"import sys, numerisect.{module}; print(sys.get_int_max_str_digits())"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        assert limit == "0", f"numerisect.{module} left the limit at {limit}"
