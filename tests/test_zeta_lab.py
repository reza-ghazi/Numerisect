"""Explicit formulas, zero statistics, and Dirichlet/Dedekind L-functions.

Every value asserted here is produced by FLINT/Arb (``acb_dirichlet_*``,
``acb_hypgeom_*``, ``dirichlet_*``) or by PARI/GP (``nfinit``, ``lfuncreate``,
``lfun``, ``lfunzeros``, ``lfunrootres``, ``lfuncheckfeq``). The tests only
compare those engine results against published constants.
"""

import pytest
from fastapi.testclient import TestClient

from numerisect import outputs
from numerisect.main import app
from numerisect.zeta import (
    ZetaEngineError,
    backlund_remainder,
    chebyshev_psi_formula,
    dirichlet_characters,
    dirichlet_l_value,
    dirichlet_l_zeros,
    euler_product_comparison,
    explicit_prime_count,
    gram_block_structure,
    riemann_siegel_remainder,
    zero_pair_correlation,
    zero_spacing_histogram,
)
from numerisect.zeta_fields import dedekind_zeta


def local_client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    token = client.get("/api/session").json()["request_token"]
    client.headers["X-Numerisect-Token"] = token
    return client


def test_explicit_formula_converges_to_the_exact_prime_count():
    # pi(100) = 25 (exact value supplied by primecount, never recomputed here).
    result = explicit_prime_count("100", 64, 30, 2)
    assert result["exact"] == "25"
    assert result["rigorous"] is False
    assert "exploratory" in str(result["note"])
    assert [term["zeros"] for term in result["terms"]][:3] == [1, 2, 4]
    assert result["terms"][-1]["zeros"] == 64
    # Riemann's formula for x = 100 uses the Moebius indices m with 100^(1/m) >= 2.
    assert result["moebius_terms"] == 6
    first = abs(result["terms"][0]["error_value"])
    last = abs(result["terms"][-1]["error_value"])
    assert last < first < 1.0


def test_chebyshev_psi_matches_the_exact_prime_power_sum():
    # psi(10) = 3*log 2 + 2*log 3 + log 5 + log 7 = 7.8320141805054689907...
    result = chebyshev_psi_formula("10", 64, 30, 2)
    assert result["exact"].startswith("[7.83201418050546899")
    assert result["exact_value"] == pytest.approx(7.832014180505469, abs=1e-12)
    assert result["limit"] == "10"
    assert result["rigorous"] is False
    assert abs(result["terms"][-1]["error_value"]) < 0.5


def test_riemann_siegel_remainder_shrinks_with_more_correction_terms():
    result = riemann_siegel_remainder("0.5", "100", 4, 25)
    assert result["rigorous"] is True
    assert result["reference_real"].startswith("[2.69261988568132409")
    deviations = [row["deviation_value"] for row in result["rows"]]
    assert len(deviations) == 5
    assert deviations[4] < deviations[1]
    assert all(row["bound"] for row in result["rows"])


def test_riemann_siegel_refuses_ordinates_below_its_validity_range():
    with pytest.raises(ZetaEngineError, match="t >= 10"):
        riemann_siegel_remainder("0.5", "5", 2, 25)


def test_euler_product_approaches_zeta_and_reports_a_rigorous_tail_bound():
    # zeta(2) = 1.6449340668482264365...
    result = euler_product_comparison("2", "0", 64, 25, 2)
    assert result["reference_real"].startswith("[1.644934066848226436")
    # FLINT's own certified Euler product for an integer argument.
    assert result["certified_euler"].startswith("[1.6447")
    assert result["rigorous"] is True
    deviations = [row["deviation_value"] for row in result["rows"]]
    assert deviations[-1] < deviations[0]
    bounds = [float(row["truncation_bound"]) for row in result["rows"]]
    assert bounds[-1] < bounds[0]

    # The rigorous truncation bound must blow up as Re(s) approaches 1.
    near_one = euler_product_comparison("1.05", "0", 64, 25, 2)
    assert float(near_one["rows"][-1]["truncation_bound"]) > bounds[-1]


def test_euler_product_refuses_the_critical_strip():
    with pytest.raises(ZetaEngineError, match="Re\\(s\\) > 1"):
        euler_product_comparison("0.5", "10", 16, 25, 1)


def test_zero_spacing_histogram_unfolds_to_unit_mean_spacing():
    result = zero_spacing_histogram("1", 400, 12, 25, 2)
    assert result["samples"] == 399
    assert result["mean"] == pytest.approx(1.0, abs=0.02)
    assert sum(row["count"] for row in result["bins"]) + result["overflow"] == 399
    assert result["rigorous"] is False
    assert "exploratory" in str(result["note"])
    # The GUE Wigner surmise vanishes at zero spacing and peaks near s ~ 0.9.
    assert result["bins"][0]["predicted"] < result["bins"][3]["predicted"]


def test_pair_correlation_tracks_the_gue_prediction():
    result = zero_pair_correlation("1", 400, 10, 3, 25, 2)
    assert result["samples"] == 400
    assert result["pairs"] > 0
    # 1 - (sin(pi u)/(pi u))^2 is small near u = 0 and approaches 1 for large u.
    assert result["bins"][0]["predicted"] < 0.2
    assert result["bins"][-1]["predicted"] == pytest.approx(1.0, abs=0.05)
    assert result["bins"][-1]["observed"] == pytest.approx(1.0, abs=0.3)
    assert result["rigorous"] is False


def test_gram_law_exception_at_index_126_is_certified():
    # The first failure of Gram's law occurs at n = 126, where Z(g_126) < 0
    # although 126 is even. g_126 = 282.4547208... and Z(g_126) = -0.0276294...
    result = gram_block_structure("120", 12, 30, 4)
    assert result["count"] == 12
    assert result["inconclusive"] == 0
    assert [row["index"] for row in result["exceptions"]] == ["126"]
    assert result["exceptions"][0]["gram_point"].startswith("[282.4547208234621746")
    assert result["exceptions"][0]["hardy_z"].startswith("[-0.0276294988571999")
    assert result["blocks"] == [
        {"start_index": "125", "length": 2, "pattern": "gbg"}
    ]
    assert result["rigorous"] is True
    statuses = {row["status"] for row in result["points"]}
    assert statuses <= {"good", "bad", "inconclusive"}


def test_gram_point_zero_and_backlund_remainder_are_certified():
    # g_0 = 17.8455995404... and N(100) = 29 nontrivial zeros with 0 < t <= 100.
    blocks = gram_block_structure("0", 2, 30, 1)
    assert blocks["points"][0]["gram_point"] == pytest.approx(17.8455995404, abs=1e-9)
    result = backlund_remainder("0", "100", 8, 30, 2)
    assert result["zero_count"] == "29"
    assert result["theta"].startswith("[87.9721652317872196")
    assert abs(float(result["remainder_bound"])) >= 1.0
    assert len(result["points"]) == 8
    assert result["rigorous"] is True
    assert "midpoints" in str(result["note"])


def test_dirichlet_character_table_reports_exact_invariants():
    result = dirichlet_characters("5", 20)
    assert result["group_order"] == "4"
    assert result["primitive_total"] == "3"
    assert result["truncated"] is False
    labels = {row["number"]: row for row in result["characters"]}
    assert labels["1"]["principal"] is True and labels["1"]["conductor"] == "1"
    # The quadratic character mod 5 is real, even, and of order 2.
    assert labels["4"]["order"] == "2"
    assert labels["4"]["real"] is True
    assert labels["4"]["parity"] == "even"
    assert labels["2"]["order"] == "4" and labels["2"]["real"] is False

    truncated = dirichlet_characters("5", 2)
    assert len(truncated["characters"]) == 2
    assert truncated["truncated"] is True


def test_dirichlet_l_value_reproduces_the_leibniz_constant():
    # L(1, chi_-4) = pi/4 = 0.78539816339744830961566084581987572105...
    result = dirichlet_l_value("4", "3", "1", "0", 30)
    assert result["real"].startswith("[0.785398163397448309615660")
    assert result["imaginary"] == "0"
    assert result["verified"] is True
    assert result["primitive"] is True and result["real_character"] is True
    assert result["conductor"] == "4" and result["parity"] == "odd"
    assert result["root_number_real"].startswith("[1.0000000")
    assert result["rigorous"] is True


def test_dirichlet_l_value_rejects_a_non_coprime_character():
    with pytest.raises(ZetaEngineError, match="coprime"):
        dirichlet_l_value("4", "2", "2", "0", 25)
    with pytest.raises(ValueError):
        dirichlet_l_value("0", "1", "2", "0", 25)


def test_dirichlet_l_zeros_certify_sign_changes_for_a_real_character():
    # The first critical-line zero of L(s, chi_-4) is t = 6.0209489046975966549...
    result = dirichlet_l_zeros("4", "3", "0.5", "30", 400, 25, 4)
    assert result["mode"] == "sign-changes"
    assert result["rigorous"] is True
    assert len(result["sign_changes"]) == 10
    first = result["sign_changes"][0]
    assert first["lower"] <= 6.020948904697597 <= first["upper"]
    assert first["upper"] - first["lower"] < 1e-12
    assert float(result["smooth_count"].strip("[]").split()[0]) == pytest.approx(9.5, abs=0.1)
    assert "lower bound" in str(result["note"])


def test_dirichlet_l_zeros_are_explicitly_exploratory_for_a_complex_character():
    # The first zero of L(s, chi_5(2, .)) sits near t = 6.1835781954508539.
    result = dirichlet_l_zeros("5", "2", "0.5", "20", 200, 25, 4)
    assert result["mode"] == "magnitude-minima"
    assert result["rigorous"] is False
    assert result["sign_changes"] == []
    assert result["minima"][0]["t"] == pytest.approx(6.1835781954, abs=0.05)
    assert "certify nothing" in str(result["note"])


def test_dirichlet_l_zeros_require_a_primitive_character():
    with pytest.raises(ZetaEngineError, match="primitive"):
        dirichlet_l_zeros("8", "1", "1", "20", 64, 25, 1)


def test_flint_time_limit_surfaces_as_an_engine_error():
    with pytest.raises(ZetaEngineError, match="time limit"):
        chebyshev_psi_formula("10000000", 5000, 200, 1, timeout_seconds=1)


def test_dedekind_zeta_of_the_gaussian_field_matches_pari():
    # zeta_K(2) for K = Q(i) is 1.50670300992298503088656504818...
    # and the residue at s = 1 is pi/4 = 0.785398163397448309615660845...
    result = dedekind_zeta(
        "quadratic", parameter="-1", sigma="2", ordinate="0",
        zero_height=15, zero_limit=10, class_data=True, precision=38,
        timeout_seconds=300,
    )
    assert result["polynomial"] == "x^2+1"
    assert result["degree"] == "2"
    assert (result["real_places"], result["complex_places"]) == ("0", "1")
    assert result["discriminant"] == "-4"
    assert int(result["functional_equation_log2_error"]) < -50
    assert result["value_real"].startswith("1.5067030099229850308")
    assert result["poles"][0]["point"] == "1"
    assert result["poles"][0]["residue"].startswith("0.78539816339744830961")
    assert result["class_number"] == "1"
    assert float(result["residue_difference"]) < 1e-30
    # zeta_K = zeta * L(s, chi_-4), so the first ordinates interleave both sets.
    ordinates = [float(zero["ordinate"]) for zero in result["zeros"]]
    assert ordinates[0] == pytest.approx(6.020948904697597, abs=1e-9)
    assert 14.134725141734694 in [pytest.approx(value, abs=1e-9) for value in ordinates]
    assert result["rigorous"] is False
    assert "not Arb ball enclosures" in str(result["note"])


def test_dedekind_zeta_of_a_cyclotomic_field_and_its_bounds():
    result = dedekind_zeta(
        "cyclotomic", parameter="5", sigma="2", ordinate="0",
        zero_height=10, zero_limit=5, class_data=False, precision=38,
    )
    assert result["degree"] == "4"
    assert result["discriminant"] == "125"
    assert result["value_real"].startswith("1.0923496617309697823")
    assert "class_number" not in result
    assert result["zeros"][0]["ordinate"].startswith("4.132903705212851595")

    with pytest.raises(ValueError):
        dedekind_zeta("cyclotomic", parameter="2")
    # PARI/GP owns the squarefree test, so a non-squarefree radicand is an
    # explicit engine refusal rather than a silent Python decision.
    with pytest.raises(ZetaEngineError, match="squarefree"):
        dedekind_zeta("quadratic", parameter="4")
    with pytest.raises(ValueError):
        dedekind_zeta("polynomial", polynomial="system('rm -rf /')")
    with pytest.raises(ValueError):
        dedekind_zeta("quadratic", parameter="-1", sigma="1", ordinate="0")


def test_dedekind_zeta_rejects_fields_beyond_the_configured_bounds():
    # Degree 9 exceeds MAX_DEGREE, so PARI/GP must fail loudly.
    with pytest.raises(ZetaEngineError):
        dedekind_zeta("polynomial", polynomial="x^9 - x - 1", zero_height=2, class_data=False)


def test_zeta_lab_api_saves_reports_and_rejects_invalid_input(tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    client = local_client()

    explicit = client.post("/api/zeta/explicit-prime-count", json={
        "bound": "100", "zeros": 32, "precision": 30, "threads": 2,
    })
    assert explicit.status_code == 200
    payload = explicit.json()
    assert payload["exact"] == "25"
    report = (tmp_path / payload["output_file"]).read_text()
    assert "Exact pi(x) from primecount: 25" in report
    assert "exploratory" in report

    gram = client.post("/api/zeta/gram-blocks", json={
        "start_index": "120", "count": 12, "precision": 30, "threads": 2,
    })
    assert gram.status_code == 200
    assert [row["index"] for row in gram.json()["exceptions"]] == ["126"]
    assert "n=126" in (tmp_path / gram.json()["output_file"]).read_text()

    lvalue = client.post("/api/zeta/l-function", json={
        "modulus": "4", "number": "3", "sigma": "1", "ordinate": "0", "precision": 30,
    })
    assert lvalue.status_code == 200
    assert lvalue.json()["real"].startswith("[0.7853981633974483096")

    dedekind = client.post("/api/zeta/dedekind", json={
        "family": "quadratic", "parameter": "-1", "sigma": "2",
        "zero_height": 10, "zero_limit": 5, "class_data": False,
    })
    assert dedekind.status_code == 200
    assert "PARI floating-point results" in dedekind.json()["note"]

    assert client.post("/api/zeta/euler-product", json={
        "sigma": "0.5", "ordinate": "0", "primes": 8, "precision": 25, "threads": 1,
    }).status_code == 503
    assert client.post("/api/zeta/characters", json={
        "modulus": "0", "limit": 10,
    }).status_code == 422
    assert client.post("/api/zeta/dedekind", json={
        "family": "quadratic", "parameter": "1",
    }).status_code == 422
    assert client.post("/api/zeta/chebyshev-psi", json={
        "bound": "1", "zeros": 4,
    }).status_code == 422
