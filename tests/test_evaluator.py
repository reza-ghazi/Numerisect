import pytest

from numerisect.evaluator import (
    ExpressionError,
    evaluate_arbitrary_integer,
    evaluate_integer,
)


def test_plain_integer():
    assert evaluate_integer("12345678901234567890") == 12345678901234567890


def test_number_theory_power_syntax():
    assert evaluate_integer("2^64 + 1") == 2**64 + 1


def test_integer_operations():
    assert evaluate_integer("(10**8 - 1) // 9") == 11111111


@pytest.mark.parametrize("expression, expected", [("0", 0), ("1", 1), ("-10", -10)])
def test_arbitrary_integer_for_prime_tools(expression, expected):
    assert evaluate_arbitrary_integer(expression) == expected


@pytest.mark.parametrize("expression", ["1", "0", "2/3", "open('/tmp/x')", "2**-1"])
def test_rejects_invalid_factor_inputs(expression):
    with pytest.raises(ExpressionError):
        evaluate_integer(expression)
