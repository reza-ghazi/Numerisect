from __future__ import annotations

import ast
import math
import sys

from .config import MAX_EXPRESSION_CHARACTERS, MAX_RESULT_DIGITS


sys.set_int_max_str_digits(0)


class ExpressionError(ValueError):
    pass


_MAX_BITS = int(MAX_RESULT_DIGITS * math.log2(10)) + 1
_MAX_NODES = 256
_MAX_EXPONENT = 1_000_000


def _check_size(value: int) -> int:
    if abs(value).bit_length() > _MAX_BITS:
        raise ExpressionError(
            f"Expression result exceeds the configured {MAX_RESULT_DIGITS:,}-digit limit"
        )
    return value


def _evaluate(node: ast.AST) -> int:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return _check_size(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _evaluate(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left = _evaluate(node.left)
        right = _evaluate(node.right)
        if isinstance(node.op, ast.Add):
            result = left + right
        elif isinstance(node.op, ast.Sub):
            result = left - right
        elif isinstance(node.op, ast.Mult):
            if left and right and left.bit_length() + right.bit_length() > _MAX_BITS + 1:
                raise ExpressionError("Multiplication result is too large")
            result = left * right
        elif isinstance(node.op, ast.FloorDiv):
            if right == 0:
                raise ExpressionError("Division by zero")
            result = left // right
        elif isinstance(node.op, ast.Mod):
            if right == 0:
                raise ExpressionError("Division by zero")
            result = left % right
        elif isinstance(node.op, ast.Pow):
            if right < 0:
                raise ExpressionError("Negative exponents do not produce integers")
            if right > _MAX_EXPONENT:
                raise ExpressionError(
                    f"Exponent exceeds the configured {_MAX_EXPONENT:,} limit"
                )
            if abs(left) > 1 and left.bit_length() * right > _MAX_BITS + 1:
                raise ExpressionError("Power result is too large")
            result = pow(left, right)
        else:
            raise ExpressionError("Unsupported operator")
        return _check_size(result)
    raise ExpressionError(
        "Use integers, parentheses, and the operators +, -, *, //, %, ^, or **"
    )


def evaluate_arbitrary_integer(expression: str) -> int:
    text = expression.strip()
    if not text:
        raise ExpressionError("Enter an integer or expression")
    if len(text) > MAX_EXPRESSION_CHARACTERS:
        raise ExpressionError("Expression is too long")

    # In number-theory tools users normally expect ^ to mean exponentiation.
    normalized = text.replace("^", "**")
    try:
        tree = ast.parse(normalized, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise ExpressionError("Invalid integer expression") from exc
    if sum(1 for _ in ast.walk(tree)) > _MAX_NODES:
        raise ExpressionError("Expression is too complex")

    return _evaluate(tree)


def evaluate_integer(expression: str) -> int:
    value = evaluate_arbitrary_integer(expression)
    if abs(value) < 2:
        raise ExpressionError("Only integers with absolute value at least 2 can be factored")
    return value
