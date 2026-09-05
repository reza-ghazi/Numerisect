import re

import pytest

from numerisect.primes import (
    CLASSIFIER_PROGRAM,
    PRIME_CLASSIFICATIONS,
    absolute_primes_in_range,
    analyze_gaussian_integer,
    analyze_miller_rabin_witnesses,
    analyze_prime_reciprocal,
    classify_prime,
    coprime_profile,
    contiguous_digit_primes,
    digit_constrained_primes,
    factor_count_distribution,
    full_reptend_primes_in_range,
    gaussian_primes_in_box,
    generate_even_perfect_numbers,
    generate_primorials,
    generate_primes,
    generate_special_primes,
    goldbach_partitions,
    integer_arithmetic_profile,
    integers_with_three_prime_factors,
    modular_wheel_cells,
    nth_prime,
    nth_prime_near,
    palindrome_derived_primes,
    paterson_primes_in_range,
    prime_count,
    prime_gaps,
    prime_gap_statistics,
    prime_indicator_constant,
    prime_insertion_pyramid,
    prime_multiplication_pyramid,
    prime_polynomial_analysis,
    prime_distribution,
    prime_square_sum_solutions,
    primality_result,
    prime_tuples_in_range,
    primes_after,
    primes_before,
    primes_in_range,
    quartan_primes_in_range,
    random_primes_in_range,
    sigma_fourth_power_square_primes,
    special_numbers_in_range,
)


def classification_ids(result):
    return {item["id"] for item in result["matches"]}


def test_primality_check():
    assert primality_result(32416190071)["is_prime"] is True
    assert primality_result(32416190070)["is_prime"] is False


def test_fast_primality_and_certificate():
    fast = primality_result(32416190071, mode="fast")
    assert fast["classification"] == "probable prime"
    assert fast["deterministic"] is False
    proven = primality_result(32416190071, certificate=True)
    assert proven["classification"] == "prime"
    assert "is prime" in str(proven["certificate"])


def test_prime_classifier_uses_native_pari_program():
    result = classify_prime(17, per_test_seconds=1)
    assert result["is_prime"] is True
    assert result["tested"] == len(PRIME_CLASSIFICATIONS) == 56
    assert {"fermat", "proth", "pythagorean", "quartan"} <= classification_ids(result)


def test_prime_classifier_catalogue_and_native_dispatch_stay_synchronized():
    program = CLASSIFIER_PROGRAM.read_text(encoding="utf-8")
    dispatched = re.findall(r'pc_(?:run|emit)\("([a-z_]+)"', program)
    assert len(dispatched) == len(set(dispatched)) == 56
    assert set(dispatched) == set(PRIME_CLASSIFICATIONS)


def test_prime_classifier_skips_classes_for_composites():
    result = classify_prime(15, per_test_seconds=1)
    assert result["classification"] == "composite"
    assert result["tested"] == 0
    assert result["matches"] == []


def test_prime_reciprocal_period_and_full_reptend():
    result = analyze_prime_reciprocal(7, digit_limit=100)
    assert result["period"] == "6"
    assert result["primitive_root_10"] is True
    assert result["full_reptend"] is True
    assert result["decimal_digits"] == "142857"
    assert result["digits_complete"] is True


def test_prime_reciprocal_preserves_leading_zero_and_only_truncates_preview(tmp_path):
    export_path = tmp_path / "reciprocal.txt"
    result = analyze_prime_reciprocal(13, digit_limit=3, export_path=export_path)
    assert result["period"] == "6"
    assert result["primitive_root_10"] is False
    assert result["decimal_digits"] == "076"
    assert result["digits_generated"] == 3
    assert result["digits_complete"] is False
    assert result["exported_digits"] == "6"
    assert result["export_complete"] is True
    assert export_path.read_text(encoding="utf-8").endswith("0.076923\n")


def test_prime_reciprocal_streams_across_native_blocks(tmp_path):
    export_path = tmp_path / "long-reciprocal.txt"
    result = analyze_prime_reciprocal(10007, digit_limit=10, export_path=export_path)
    decimal = export_path.read_text(encoding="utf-8").splitlines()[-1]
    assert result["period"] == result["exported_digits"] == "10006"
    assert len(decimal) == 10008
    assert decimal.startswith("0.0000999300")


def test_terminating_prime_reciprocal_and_composite_rejection():
    result = analyze_prime_reciprocal(2)
    assert result["terminating"] is True
    assert result["period"] == "0"
    assert result["decimal_digits"] == "5"
    with pytest.raises(ValueError, match="proven prime"):
        analyze_prime_reciprocal(21)


def test_generate_exact_digit_primes():
    values = generate_primes(4, 6)
    assert len(values) == len(set(values)) == 4
    assert all(len(str(value)) == 6 for value in values)


def test_primes_after_example():
    assert primes_after(5000, 4) == [5003, 5009, 5011, 5021]


def test_primes_before_example():
    assert primes_before(5000, 4) == [4999, 4993, 4987, 4973]


def test_index_and_count():
    assert nth_prime(100) == 541
    assert prime_count(1000) == 168


@pytest.mark.parametrize("start,index,direction,expected", [
    (1289, 100, "after", 2039),
    (98798, 50, "before", 98221),
    (13, 1, "after", 17),
    (13, 1, "before", 11),
    (13, 5, "before", 2),
    (-100, 1, "after", 2),
    (2**127 - 1, 1, "after", 170141183460469231731687303715884105757),
])
def test_relative_prime(start, index, direction, expected):
    assert nth_prime_near(start, index, direction) == expected


@pytest.mark.parametrize("start,index", [(13, 6), (2, 1), (1, 1), (-100, 1)])
def test_relative_prime_exhaustion(start, index):
    with pytest.raises(ValueError, match="does not exist"):
        nth_prime_near(start, index, "before")


@pytest.mark.parametrize("index,direction", [(0, "after"), (100001, "after"), (1, "sideways")])
def test_relative_prime_validation(index, direction):
    with pytest.raises(ValueError):
        nth_prime_near(13, index, direction)


def test_relative_prime_rejects_incomplete_engine_output(monkeypatch):
    from numerisect import primes
    monkeypatch.setattr(primes, "_run_gp", lambda program: ["RESULT:17"])
    with pytest.raises(primes.PrimeEngineError, match="incomplete"):
        nth_prime_near(13, 1, "after")


def test_relative_prime_engine_timeout(monkeypatch):
    from numerisect import primes
    import subprocess
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("gp", 3600)
    monkeypatch.setattr(primes.subprocess, "run", timeout)
    with pytest.raises(primes.PrimeEngineError, match="operation limit"):
        nth_prime_near(13, 1, "after")


def test_prime_range():
    values, truncated, next_start = primes_in_range(10, 30, 100)
    assert values == [11, 13, 17, 19, 23, 29]
    assert truncated is False
    assert next_start is None


def test_twin_primes():
    tuples, truncated, _ = prime_tuples_in_range(2, 30, [0, 2], 100)
    assert tuples == [[3, 5], [5, 7], [11, 13], [17, 19]]
    assert truncated is False


def test_prime_gaps():
    gaps, truncated, _ = prime_gaps(2, 30, 100)
    assert gaps[-1] == {"from": 23, "to": 29, "gap": 6}
    assert truncated is False


def test_special_prime_generators():
    safe = generate_special_primes(2, 3, "safe")
    sophie = generate_special_primes(2, 3, "sophie")
    blum = generate_special_primes(2, 3, "blum")
    modular = generate_special_primes(2, 3, "congruence", 5, 1)
    assert all(primality_result((value - 1) // 2)["is_prime"] for value in safe)
    assert all(primality_result(2 * value + 1)["is_prime"] for value in sophie)
    assert all(value % 4 == 3 for value in blum)
    assert all(value % 5 == 1 for value in modular)


def test_absolute_prime_orbits():
    groups, truncated, next_start = absolute_primes_in_range(2, 200, 100)
    assert {item["representative"] for item in groups} >= {"2", "13", "197"}
    assert next(item for item in groups if item["representative"] == "13")["rotations"] == ["13", "31"]
    assert truncated is False
    assert next_start is None


def test_gaussian_prime_criterion_and_lattice():
    axis = analyze_gaussian_integer(5, 0)
    assert axis["is_gaussian_prime"] is False
    assert axis["factors"] == [{"real": "2", "imaginary": "1"}, {"real": "2", "imaginary": "-1"}]
    assert analyze_gaussian_integer(3, 0)["is_gaussian_prime"] is True
    assert analyze_gaussian_integer(1, 2)["is_gaussian_prime"] is True
    points, truncated = gaussian_primes_in_box(2, 100)
    assert {("1", "2"), ("-1", "-2")} <= {(item["real"], item["imaginary"]) for item in points}
    assert truncated is False


def test_modular_wheel_is_computed_natively():
    cells = modular_wheel_cells(6, 10)
    assert cells[7] == {"value": 7, "residue": 1, "ring": 1, "is_prime": True, "coprime": True}
    assert len(cells) == 11


def test_paterson_primes():
    values, truncated, _ = paterson_primes_in_range(2, 20, 100)
    assert [(item["prime"], item["base4"], item["decimal_companion"]) for item in values] == [
        ("2", "2", "2"), ("3", "3", "3"), ("5", "11", "11"),
        ("7", "13", "13"), ("11", "23", "23"), ("13", "31", "31"),
        ("17", "101", "101"), ("19", "103", "103"),
    ]
    assert truncated is False


def test_even_perfect_numbers():
    values = generate_even_perfect_numbers(5)
    assert [item["value"] for item in values] == ["6", "28", "496", "8128", "33550336"]
    assert [item["exponent"] for item in values] == ["2", "3", "5", "7", "13"]


def test_full_reptend_prime_search():
    values, truncated, _ = full_reptend_primes_in_range(3, 30, 100)
    assert [item["prime"] for item in values] == ["7", "17", "19", "23", "29"]
    assert all(item["period"] == str(int(item["prime"]) - 1) for item in values)
    assert truncated is False


def test_prime_pyramids_reproduce_source_constructions():
    levels = prime_insertion_pyramid(4)
    assert [item["value"] for item in levels] == ["11", "121", "13231", "1432341"]
    rows = prime_multiplication_pyramid(3)
    assert rows[1][0] == {"column": 1, "value": "2", "is_prime": True}
    assert rows[2][1] == {"column": 2, "value": "6", "is_prime": False}


def test_corrected_special_number_searches():
    carmichael, _, _ = special_numbers_in_range("carmichael", 2, 2000, 100)
    fermat, _, _ = special_numbers_in_range("fermat_pseudoprime_base2", 2, 700, 100)
    lucky, _, _ = special_numbers_in_range("lucky_prime", 2, 40, 100)
    jacobsthal, _, _ = special_numbers_in_range("jacobsthal_prime", 2, 1000, 100)
    assert [item["value"] for item in carmichael] == ["561", "1105", "1729"]
    assert [item["value"] for item in fermat] == ["341", "561", "645"]
    assert [item["value"] for item in lucky] == ["3", "7", "13", "31", "37"]
    assert [item["value"] for item in jacobsthal] == ["3", "5", "11", "43", "683"]


def test_miller_rabin_witness_analysis_corrects_incomplete_source_test():
    result = analyze_miller_rabin_witnesses(91, 2, 100)
    assert result["s"] == "1" and result["d"] == "45"
    assert result["is_witness"] is True
    assert result["witness_count"] == "72"
    assert result["passing_count"] == "16"
    assert "9" in result["passing_bases"]


def test_native_prime_gap_statistics():
    result = prime_gap_statistics(2, 30, 100)
    assert result["count"] == 9
    assert result["minimum"] == "1" and result["maximum"] == "6"
    assert result["mean"] == {"numerator": "3", "denominator": "1"}
    assert result["median"] == {"numerator": "2", "denominator": "1"}
    assert result["mode"] == {"gap": "2", "frequency": 4}


def test_primorial_generation():
    values = generate_primorials(5)
    assert [item["value"] for item in values] == ["2", "6", "30", "210", "2310"]


def test_prime_problem_searches():
    square_sums, _ = prime_square_sum_solutions(20, 100)
    assert square_sums[:2] == [{"p": "13", "q": "11", "r": "7"}, {"p": "17", "q": "13", "r": "11"}]
    quartans, _ = quartan_primes_in_range(300, 100)
    assert {item["prime"] for item in quartans} == {"2", "17", "97", "257"}
    factored, _ = integers_with_three_prime_factors(3, 10, 100)
    assert [item["n"] for item in factored] == ["3", "8", "10"]
    sigma, _ = sigma_fourth_power_square_primes(100, 100)
    assert sigma == [{"prime": "3", "sigma": "121", "root": "11", "index": "2"}]


def test_digit_random_and_goldbach_tools():
    assert contiguous_digit_primes(3797) == [3, 7, 37, 79, 97, 379, 797, 3797]
    random_values = random_primes_in_range(100, 200, 5)
    assert len(random_values) == len(set(random_values)) == 5
    assert all(100 <= value <= 200 and primality_result(value)["is_prime"] for value in random_values)
    partitions, truncated = goldbach_partitions(26, 100)
    assert partitions == [
        {"left": "3", "right": "23"},
        {"left": "7", "right": "19"},
        {"left": "13", "right": "13"},
    ]
    assert truncated is False


def test_integer_arithmetic_profile_and_semiprime_detection():
    result = integer_arithmetic_profile(60, 10)
    assert result["factors"] == [
        {"prime": "2", "exponent": "2"},
        {"prime": "3", "exponent": "1"},
        {"prime": "5", "exponent": "1"},
    ]
    assert result["divisor_count"] == "12"
    assert result["divisor_sum"] == "168"
    assert result["totient"] == "16"
    assert result["carmichael"] == "4"
    assert result["radical"] == "30"
    assert result["divisor_class"] == "abundant"
    assert result["divisors_complete"] is False
    assert integer_arithmetic_profile(49)["is_semiprime"] is True


def test_coprime_profile_and_reduced_residues():
    result = coprime_profile(10, 20, 5, 10)
    assert result["totient"] == "4"
    assert result["after"] == ["21", "23", "27", "29", "31"]
    assert result["residues"] == ["1", "3", "7", "9"]
    assert result["residues_complete"] is True


def test_native_prime_distribution():
    result = prime_distribution(2, 30, 4, 6)
    assert result["count"] == 10
    assert result["twin_count"] == 4
    assert [item["count"] for item in result["bins"]] == ["4", "2", "3", "1"]
    assert result["residues"][5] == {"residue": "5", "count": "5"}


def test_native_prime_factor_count_distribution():
    result = factor_count_distribution(1, 10)
    by_count = {item["factor_count"]: item for item in result["distribution"]}
    assert result["total"] == 10
    assert by_count["0"] == {
        "factor_count": "0",
        "distinct_count": "1",
        "multiplicity_count": "1",
    }
    assert by_count["1"]["distinct_count"] == "7"
    assert by_count["3"]["multiplicity_count"] == "1"


def test_digit_constrained_prime_search():
    result = digit_constrained_primes("137", 1, 2, 100)
    assert result["primes"] == ["3", "7", "11", "13", "17", "31", "37", "71", "73"]
    assert result["candidates_tested"] == 12
    assert result["candidate_limited"] is False


def test_exact_prime_polynomial_analysis():
    result = prime_polynomial_analysis(41, 0, 10, 100, 50)
    assert result["count"] == 11
    assert result["longest_run"] == 11
    assert result["longest_run_start"] == "0"
    assert result["values"][-1] == {"n": "10", "value": "131"}
    assert any(item["prime"] == "41" and item["residues"] == ["0", "1"] for item in result["obstructions"])


def test_palindrome_derived_sequence_and_prime_indicator_constant():
    result = palindrome_derived_primes(1, 20, 100)
    assert result["values"] == [
        {"n": "13", "reverse": "31", "prime": "19"},
        {"n": "15", "reverse": "51", "prime": "37"},
        {"n": "19", "reverse": "91", "prime": "73"},
        {"n": "20", "reverse": "2", "prime": "19"},
    ]
    constant = prime_indicator_constant(12)
    assert constant["value"] == "0.414682509851"
    assert constant["error_bound"].startswith("2^-")
