"""Known-answer, invalid-input, and inconclusive-path tests for the forms laboratory.

Every success-path assertion cites a standard reference value in a comment.  The
mathematics is performed by PARI/GP through ``numerisect/forms_lab.gp``; these tests
check that the orchestration layer bounds, parses and reports it faithfully.
"""

import pytest
from fastapi.testclient import TestClient

from numerisect import outputs
from numerisect.forms_lab import (
    class_group,
    compose_forms,
    continued_fraction,
    pell_solutions,
    prime_forms,
    reduce_form,
    reduced_forms,
    represent_integer,
)
from numerisect.main import app
from numerisect.primes import PrimeEngineError


def local_client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    token = client.get("/api/session").json()["request_token"]
    client.headers["X-Numerisect-Token"] = token
    return client


# ------------------------------------------------------------------ reduction
def test_reduction_of_a_positive_definite_form():
    # 10x^2 + 7xy + 3y^2 has discriminant 49 - 120 = -71 and reduces to (3, -1, 6),
    # the unique reduced form of its class (|b| <= a <= c).
    result = reduce_form("10", "7", "3")
    assert result["definite"] is True
    assert result["metrics"]["Discriminant D"] == "-71"
    assert result["metrics"]["Reduced form (a, b, c)"] == "3, -1, 6"
    assert result["metrics"]["Matrix determinant"] == "1"
    assert "positive definite" in result["metrics"]["Case"]

    # Qfb(1, 1, 6) of discriminant -23 is already reduced, and it is the principal form.
    principal = reduce_form("1", "1", "6")
    assert principal["metrics"]["Discriminant D"] == "-23"
    assert principal["metrics"]["Reduced form (a, b, c)"] == "1, 1, 6"
    assert principal["metrics"]["Reduced form is ambiguous"] == "yes"
    assert principal["metrics"]["Field discriminant"] == "-23"
    assert principal["metrics"]["Conductor"] == "1"


def test_reduction_of_an_indefinite_form_reports_its_cycle():
    # D = 4*1817 = 7268 with 1817 = 23 * 79.  The principal cycle has 28 reduced forms;
    # this is the cycle SQUFOF walks.
    result = reduce_form("1", "84", "-53", step_limit=5, cycle_limit=200)
    assert result["definite"] is False
    assert result["metrics"]["Discriminant D"] == "7268"
    assert result["metrics"]["Cycle length of the reduced form"] == "28"
    assert "indefinite" in result["metrics"]["Case"]
    # The trace is capped at five single reduction steps.
    assert len(result["rows"]) == 5
    assert result["truncated"] is True


def test_reduction_reports_an_exhausted_cycle_limit_as_inconclusive():
    capped = reduce_form("1", "84", "-53", step_limit=1, cycle_limit=5)
    assert capped["metrics"]["Cycle length of the reduced form"] == "inconclusive"


def test_reduction_rejects_non_discriminants_and_bad_bounds():
    with pytest.raises(PrimeEngineError):
        reduce_form("1", "2", "1")  # b^2 - 4ac = 0 is not a discriminant
    with pytest.raises(PrimeEngineError):
        reduce_form("1", "1", "0")  # b^2 - 4ac = 1 is a square: the form is reducible
    # b^2 - 4ac is always 0 or 1 modulo 4, so the congruence rejection is reachable only
    # from the tools that take a discriminant directly; see the class-group test below.
    with pytest.raises(PrimeEngineError):
        reduce_form("-1", "1", "6")  # negative definite is not represented by PARI
    with pytest.raises(ValueError):
        reduce_form("not an integer", "1", "6")
    with pytest.raises(ValueError):
        reduce_form("1", "1", "6", step_limit=-1)
    with pytest.raises(ValueError):
        reduce_form("1", "1", "6", cycle_limit=0)


# ------------------------------------------------------------------ composition
def test_composition_and_powers_of_the_prime_form_of_discriminant_minus_23():
    # h(-23) = 3, so the class of Qfb(2, 1, 3) has order 3 and its cube is the principal
    # form Qfb(1, 1, 6); its square is the inverse class Qfb(2, -1, 3).
    result = compose_forms("2", "1", "3", "2", "1", "3", exponent=3)
    rows = {row[0]: row[1:4] for row in result["rows"]}
    assert rows["Principal form"] == ["1", "1", "6"]
    assert rows["f ∘ g"] == ["2", "-1", "3"]
    assert rows["f^3"] == ["1", "1", "6"]
    # qfbcompraw skips reduction, so the unreduced composition has larger coefficients.
    assert rows["f ∘ g unreduced"] == ["4", "5", "3"]
    assert result["metrics"]["f^3 is principal"] == "yes"
    assert result["metrics"]["f ∘ g is principal"] == "no"
    assert result["metrics"]["Order of the class of f"] == "3"


def test_composition_reports_exhausted_caps_as_inconclusive():
    capped = compose_forms("2", "1", "3", "2", "1", "3", exponent=3, order_limit=1)
    assert capped["metrics"]["Order of the class of f"] == "inconclusive"
    # The unreduced power is offered only for small exponents.
    large = compose_forms("2", "1", "3", "2", "1", "3", exponent=1001)
    assert large["raw_power_available"] is False
    assert large["metrics"]["Unreduced power available"] == "no"
    assert not any(row[0].endswith("unreduced") and row[4] == "qfbpowraw" for row in large["rows"])


def test_composition_rejects_mismatched_discriminants_and_bad_bounds():
    with pytest.raises(PrimeEngineError):
        compose_forms("2", "1", "3", "1", "1", "1")  # -23 against -3
    with pytest.raises(ValueError):
        compose_forms("2", "1", "3", "2", "1", "3", exponent=10**7)
    with pytest.raises(ValueError):
        compose_forms("2", "1", "3", "2", "1", "3", order_limit=0)


# ------------------------------------------------------------------ prime forms
def test_prime_forms_of_discriminant_minus_23():
    # qfbprimeform(-23, 2) = Qfb(2, 1, 3).  5 and 7 are inert: (-23/5) = (-23/7) = -1,
    # so no form of discriminant -23 has leading coefficient 5 or 7.
    result = prime_forms("-23", ["2", "3", "5", "7"])
    rows = {row[0]: row for row in result["rows"]}
    assert rows["2"][3] == "2, 1, 3"
    assert rows["2"][2] == "1"
    assert rows["3"][3] == "3, 1, 2"
    assert rows["3"][4] == "2, -1, 3"
    assert rows["5"][3] == "no form"
    assert rows["7"][3] == "no form"
    assert result["metrics"]["Primes with a form"] == "2"


def test_prime_forms_reject_invalid_input():
    with pytest.raises(PrimeEngineError):
        prime_forms("2", ["3"])  # 2 is neither 0 nor 1 modulo 4
    with pytest.raises(ValueError):
        prime_forms("-23", [])
    with pytest.raises(ValueError):
        prime_forms("-23", ["2"] * 65)


# ------------------------------------------------------------------ class group
def test_class_numbers_of_the_classical_discriminants():
    # h(-23) = 3 with class group Z/3, generated by Qfb(2, 1, 3).
    small = class_group("-23")
    assert small["metrics"]["Class number h"] == "3"
    assert small["metrics"]["Class-group structure"] == "Z/3"
    assert small["rows"][0][1:4] == ["2", "1", "3"]
    # The Hurwitz class number H(23) is also 3.
    assert small["metrics"]["Hurwitz class number H(-D)"] == "3"

    # h(-163) = 1: the largest Heegner discriminant, so the class group is trivial.
    heegner = class_group("-163")
    assert heegner["metrics"]["Class number h"] == "1"
    assert heegner["metrics"]["Class-group structure"] == "trivial"
    assert heegner["rows"] == []

    # D = 40 > 0 is indefinite: h = 2, and the fundamental unit 3 + sqrt(10) of
    # discriminant 40 has norm -1.
    indefinite = class_group("40")
    assert indefinite["definite"] is False
    assert indefinite["metrics"]["Class number h"] == "2"
    assert indefinite["metrics"]["Norm of the fundamental unit"] == "-1"
    assert indefinite["metrics"]["Regulator"].startswith("1.81")
    assert "indefinite" in indefinite["metrics"]["Case"]


def test_class_group_rejects_non_discriminants():
    with pytest.raises(PrimeEngineError):
        class_group("2")  # 2 mod 4 is not a discriminant
    with pytest.raises(PrimeEngineError):
        class_group("3")  # 3 mod 4 is not a discriminant
    with pytest.raises(PrimeEngineError):
        class_group("9")  # a square discriminant gives a reducible form
    with pytest.raises(PrimeEngineError):
        class_group("0")
    with pytest.raises(ValueError):
        class_group("-23", generator_limit=0)
    with pytest.raises(ValueError):
        class_group("-" + "9" * 41)


# ------------------------------------------------------------------ enumeration
def test_reduced_form_enumeration_for_a_negative_discriminant():
    # h(-47) = 5, so there are exactly five reduced forms, one per class, and the
    # principal one is Qfb(1, 1, 12).
    result = reduced_forms("-47")
    assert result["complete"] is True
    assert result["metrics"]["Class number h"] == "5"
    assert len(result["rows"]) == 5
    assert result["rows"][0][1:4] == ["1", "1", "12"]
    # Only the principal class is ambiguous when h is odd.
    assert result["metrics"]["Ambiguous forms found"] == "1"


def test_reduced_form_enumeration_shows_the_squfof_cycle():
    # D = 4N with N = 1817 = 23 * 79.  The principal cycle has 28 reduced forms and
    # contains the ambiguous form Qfb(23, 46, -56); 23 divides 46, and 23 is exactly the
    # factor of N that SQUFOF extracts from an ambiguous form of the principal cycle.
    result = reduced_forms("7268")
    assert result["definite"] is False
    assert result["metrics"]["Principal cycle length"] == "28"
    ambiguous = [row[1:4] for row in result["rows"] if row[4] == "yes"]
    assert ["23", "46", "-56"] in ambiguous
    assert "SQUFOF" in result["note"]


def test_reduced_form_enumeration_reports_an_exhausted_cap_as_inconclusive():
    capped = reduced_forms("-47", form_limit=2)
    assert capped["complete"] is False
    assert capped["metrics"]["Enumeration complete"] == "no"
    assert len(capped["rows"]) == 2
    assert "inconclusive" in capped["note"]


def test_reduced_form_enumeration_rejects_non_discriminants():
    with pytest.raises(PrimeEngineError):
        reduced_forms("6")
    with pytest.raises(ValueError):
        reduced_forms("-47", form_limit=0)
    with pytest.raises(ValueError):
        reduced_forms("-47", cycle_limit=0)


# ------------------------------------------------------------------ representation
def test_1729_is_represented_by_x_squared_plus_three_y_squared():
    # 1729 = 23^2 + 3*20^2 = 1^2 + 3*24^2 = 31^2 + 3*16^2 = 41^2 + 3*4^2.  qfbsolve
    # returns all eight signed primitive solutions of x^2 + 3y^2 = 1729.
    result = represent_integer("1", "0", "3", "1729")
    assert result["represented"] is True
    assert result["metrics"]["Solutions found"] == "8"
    assert result["metrics"]["Primitive solutions"] == "8"
    pairs = {(row[0], row[1]) for row in result["rows"]}
    assert ("23", "-20") in pairs
    assert ("31", "16") in pairs
    assert all(row[3] == "1729" for row in result["rows"])

    # 5 is not represented by x^2 + 3y^2: it is not 0 or 1 modulo 3 in the right way.
    assert represent_integer("1", "0", "3", "5")["rows"] == []


def test_representation_respects_its_solution_cap():
    capped = represent_integer("1", "0", "3", "1729", solution_limit=3)
    assert len(capped["rows"]) == 3
    assert capped["truncated"] is True
    assert capped["metrics"]["Solutions found"] == "8"


def test_representation_rejects_invalid_input():
    with pytest.raises(PrimeEngineError):
        represent_integer("1", "0", "3", "0")  # zero is not a target
    with pytest.raises(PrimeEngineError):
        represent_integer("1", "1", "0", "7")  # discriminant 1 is a square
    with pytest.raises(ValueError):
        represent_integer("1", "0", "3", "7", solution_limit=0)


# ------------------------------------------------------------------ continued fractions
def test_continued_fraction_of_a_rational():
    # 13/7 = [1; 1, 6] with convergents 1/1, 2/1, 13/7.
    result = continued_fraction("rational", "13", "7")
    assert result["complete"] is True
    assert [row[3] for row in result["rows"]] == ["1", "1", "6"]
    assert [(row[1], row[2]) for row in result["rows"]] == [("1", "1"), ("2", "1"), ("13", "7")]
    assert result["metrics"]["Kind"] == "rational"


def test_continued_fraction_of_sqrt_13_has_the_expected_period():
    # sqrt(13) = [3; 1, 1, 1, 1, 6] repeating: preperiod 1, period 5, and the head
    # [1, 1, 1, 1] of the period is palindromic with last term 2*a0 = 6.
    result = continued_fraction("quadratic", "0", "1", "13", quotient_limit=12, convergent_limit=12)
    assert result["complete"] is True
    assert result["metrics"]["Preperiod length"] == "1"
    assert result["metrics"]["Period length"] == "5"
    assert result["metrics"]["Period"] == "1,1,1,1,6"
    assert result["metrics"]["Period head is palindromic"] == "yes"
    assert result["metrics"]["Cross-checked against contfrac"] == "yes"
    # The convergent at the end of the second period is the Pell solution 649/180.
    assert (result["rows"][9][1], result["rows"][9][2]) == ("649", "180")
    assert result["metrics"]["Best approximation with denominator ≤ 1000"] == "649/180"


def test_continued_fraction_of_the_golden_ratio():
    # (1 + sqrt(5))/2 = [1; 1, 1, ...] with Fibonacci convergents.
    result = continued_fraction("quadratic", "1", "2", "5", quotient_limit=10, convergent_limit=10)
    assert result["metrics"]["Period length"] == "1"
    assert result["metrics"]["Period"] == "1"
    assert [row[3] for row in result["rows"]] == ["1"] * 10
    assert (result["rows"][9][1], result["rows"][9][2]) == ("89", "55")


def test_continued_fraction_reports_an_unclosed_period_as_inconclusive():
    capped = continued_fraction("quadratic", "0", "1", "13", quotient_limit=3, convergent_limit=3)
    assert capped["complete"] is False
    assert capped["metrics"]["Period length"] == "inconclusive"
    assert capped["metrics"]["Preperiod length"] == "inconclusive"
    assert "inconclusive" in capped["note"]


def test_continued_fraction_rejects_invalid_input():
    with pytest.raises(PrimeEngineError):
        continued_fraction("quadratic", "0", "1", "16")  # a perfect square is rational
    with pytest.raises(PrimeEngineError):
        continued_fraction("quadratic", "0", "1", "-3")  # the radicand must be positive
    with pytest.raises(ValueError):
        continued_fraction("bogus")
    with pytest.raises(ValueError):
        continued_fraction("rational", "13", "0")
    with pytest.raises(ValueError):
        continued_fraction("quadratic", "0", "1", "13", quotient_limit=0)
    with pytest.raises(ValueError):
        continued_fraction("quadratic", "0", "1", "13", approximation_bound="0")


# ------------------------------------------------------------------ Pell
def test_pell_fundamental_solution_for_d_equal_13():
    # x^2 - 13y^2 = 1 has fundamental solution (649, 180).  The fundamental unit of
    # Z[sqrt(13)] is 18 + 5*sqrt(13) of norm -1, so 18^2 - 13*5^2 = -1 solves the
    # negative Pell equation and the Pell solution is the square of that unit.
    result = pell_solutions("13")
    assert result["available"] is True
    assert result["metrics"]["Fundamental solution x"] == "649"
    assert result["metrics"]["Fundamental solution y"] == "180"
    assert result["metrics"]["Norm of the fundamental unit"] == "-1"
    assert result["metrics"]["x² − dy² = −1 solvable"] == "yes"
    assert result["metrics"]["Continued-fraction period of √d"] == "5"
    assert result["metrics"]["Matches the convergent at the end of the period"] == "yes"
    # Further solutions are powers: (649 + 180*sqrt(13))^2 = 842401 + 233640*sqrt(13).
    assert result["rows"][0][1:] == ["649", "180"]
    assert result["rows"][1][1:] == ["842401", "233640"]


def test_pell_fundamental_solution_for_d_equal_61():
    # The classical hard case: x^2 - 61y^2 = 1 has fundamental solution
    # (1766319049, 226153980), and the period of sqrt(61) is 11.
    result = pell_solutions("61", solution_count=1)
    assert result["metrics"]["Fundamental solution x"] == "1766319049"
    assert result["metrics"]["Fundamental solution y"] == "226153980"
    assert result["metrics"]["Continued-fraction period of √d"] == "11"


def test_pell_negative_equation_is_unsolvable_for_d_equal_3():
    # The fundamental unit 2 + sqrt(3) of Z[sqrt(3)] has norm +1, so x^2 - 3y^2 = -1
    # has no solution and (2, 1) is already the fundamental Pell solution.
    result = pell_solutions("3", solution_count=2)
    assert result["metrics"]["Norm of the fundamental unit"] == "1"
    assert result["metrics"]["x² − dy² = −1 solvable"] == "no"
    assert result["rows"][0][1:] == ["2", "1"]
    assert result["rows"][1][1:] == ["7", "4"]


def test_pell_reports_an_exhausted_digit_limit_as_truncated():
    capped = pell_solutions("13", solution_count=3, digit_limit=5)
    assert capped["truncated"] is True
    assert len(capped["rows"]) == 1
    assert "digit limit" in capped["note"]


def test_pell_rejects_invalid_input():
    with pytest.raises(PrimeEngineError):
        pell_solutions("16")  # a perfect square makes the equation degenerate
    with pytest.raises(PrimeEngineError):
        pell_solutions("1")  # d must be at least 2
    with pytest.raises(PrimeEngineError):
        pell_solutions("0")
    with pytest.raises(ValueError):
        pell_solutions("13", solution_count=0)
    with pytest.raises(ValueError):
        pell_solutions("13", digit_limit=0)
    with pytest.raises(ValueError):
        pell_solutions("13", unit_seconds=0)


# ---------------------------------------------------------------- API layer
def test_forms_api_saves_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    client = local_client()
    cases = [
        ("reduce", {"a": "10", "b": "7", "c": "3"}, "Reduced form (a, b, c)"),
        (
            "compose",
            {"a1": "2", "b1": "1", "c1": "3", "a2": "2", "b2": "1", "c2": "3",
             "exponent": 3},
            "Order of the class of f",
        ),
        ("prime-form", {"discriminant": "-23", "primes": ["2", "3"]}, "Primes with a form"),
        ("class-group", {"discriminant": "-23"}, "Class number h"),
        ("reduced-forms", {"discriminant": "-47"}, "Reduced forms listed"),
        (
            "represent",
            {"a": "1", "b": "0", "c": "3", "number": "1729"},
            "Primitive solutions",
        ),
        (
            "continued-fraction",
            {"mode": "quadratic", "numerator": "0", "denominator": "1",
             "radicand": "13", "quotient_limit": 12, "convergent_limit": 12},
            "Period length",
        ),
        ("pell", {"d": "13", "solution_count": 2}, "Fundamental solution x"),
    ]
    for endpoint, payload, metric in cases:
        response = client.post(f"/api/forms/{endpoint}", json=payload)
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
    ("reduce", {"a": "1", "b": "2", "c": "1"}),
    ("reduce", {"a": "1", "b": "1", "c": "6", "step_limit": -1}),
    ("compose", {"a1": "2", "b1": "1", "c1": "3", "a2": "1", "b2": "1", "c2": "1"}),
    ("prime-form", {"discriminant": "2", "primes": ["3"]}),
    ("prime-form", {"discriminant": "-23", "primes": []}),
    ("class-group", {"discriminant": "9"}),
    ("class-group", {"discriminant": "-23", "generator_limit": 0}),
    ("reduced-forms", {"discriminant": "6"}),
    ("represent", {"a": "1", "b": "0", "c": "3", "number": "0"}),
    ("continued-fraction", {"mode": "quadratic", "radicand": "16"}),
    ("continued-fraction", {"mode": "wrong"}),
    ("pell", {"d": "16"}),
    ("pell", {"d": "13", "solution_count": 0}),
])
def test_forms_api_failures_do_not_save(endpoint, payload, tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    response = local_client().post(f"/api/forms/{endpoint}", json=payload)
    assert response.status_code == 422, response.text
    assert list(tmp_path.iterdir()) == []
