import re

from numerisect.primes import (
    CLASSIFIER_PROGRAM,
    PRIME_CLASSIFICATIONS,
    classify_prime,
    generate_primes,
    generate_special_primes,
    nth_prime,
    prime_count,
    prime_gaps,
    primality_result,
    prime_tuples_in_range,
    primes_after,
    primes_before,
    primes_in_range,
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
