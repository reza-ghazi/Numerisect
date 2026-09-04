from numerisect.primes import (
    generate_primes,
    primality_result,
    prime_tuples_in_range,
    primes_after,
    primes_in_range,
)


def test_primality_check():
    assert primality_result(32416190071)["is_prime"] is True
    assert primality_result(32416190070)["is_prime"] is False


def test_generate_exact_digit_primes():
    values = generate_primes(4, 6)
    assert len(values) == len(set(values)) == 4
    assert all(len(str(value)) == 6 for value in values)


def test_primes_after_example():
    assert primes_after(5000, 4) == [5003, 5009, 5011, 5021]


def test_prime_range():
    values, truncated, next_start = primes_in_range(10, 30, 100)
    assert values == [11, 13, 17, 19, 23, 29]
    assert truncated is False
    assert next_start is None


def test_twin_primes():
    tuples, truncated, _ = prime_tuples_in_range(2, 30, [0, 2], 100)
    assert tuples == [[3, 5], [5, 7], [11, 13], [17, 19]]
    assert truncated is False
