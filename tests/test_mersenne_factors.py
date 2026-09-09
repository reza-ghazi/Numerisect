"""Mersenne trial factoring over the progression q = 2kp + 1.

Each success-path assertion cites a published factorization. The point of the routine is
that M_p is never constructed, so the tests deliberately include an exponent whose
Mersenne number has more than 300,000 decimal digits.
"""

import subprocess

import pytest
from fastapi.testclient import TestClient

import numerisect.factor_lab as factor_lab
from numerisect import outputs
from numerisect.factor_lab import (
    _mersenne_confirm,
    _mersenne_native_scan,
    mersenne_factor_hunt,
    mersenne_factors,
    special_form_analysis,
)
from numerisect.main import app
from numerisect.native_tools import (
    build_mfactor_cuda_tool,
    cuda_compiler,
    mfactor_tool_path,
)


@pytest.fixture()
def local_client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    client.headers["X-Numerisect-Token"] = client.get("/api/session").json()["request_token"]
    return client


@pytest.mark.parametrize("exponent,expected", [
    # M_11 = 23 * 89, M_23 = 47 * 178481, M_29 = 233 * 1103 * 2089,
    # M_43 = 431 * 9719 * 2099863. Every factor here is below the k bound used.
    (11, ["23", "89"]),
    (23, ["47", "178481"]),
    (29, ["233", "1103", "2089"]),
    (43, ["431", "9719", "2099863"]),
])
def test_known_mersenne_factorizations_are_recovered(exponent, expected):
    result = mersenne_factors(exponent, k_limit=30_000, timeout=120)
    assert result["factors"] == expected
    assert result["complete"] is True


def test_every_reported_factor_satisfies_both_congruences():
    """q = 2kp + 1 and q = +/-1 (mod 8) are the reason the search is feasible at all."""

    exponent = 43
    result = mersenne_factors(exponent, k_limit=30_000, timeout=120)
    assert result["rows"]
    for factor, k, order, digits in result["rows"]:
        q, k, order = int(factor), int(k), int(order)
        assert q == 2 * k * order + 1
        assert order == exponent
        assert q % 8 in (1, 7)
        assert len(factor) == int(digits)


def test_a_mersenne_far_too_large_to_construct_is_still_factored():
    """M_1000151 has 301,076 decimal digits and a factor at k = 1.

    Nothing here builds that number. If the routine ever tried to, this test would not
    finish.
    """

    result = mersenne_factors(1000151, k_limit=5, timeout=120)
    assert result["factors"] == ["2000303"]
    assert int(result["mersenne_digits"]) == 301076
    assert int(result["factors"][0]) == 2 * 1 * 1000151 + 1


@pytest.mark.parametrize("exponent,k_limit,expected", [
    # Each of these was verified in a separate PARI/GP session: q prime, k a genuine
    # integer in q = 2kp + 1, q = +/-1 (mod 8), and 2^p = 1 (mod q).
    (600_000_001, 100, ["27600000047"]),          # M_p has 180,617,998 digits
    (999_999_001, 200, ["357999642359"]),         # M_p has 301,029,695 digits
    (30_000_001, 100, ["1380000047"]),            # M_p has   9,030,901 digits
])
def test_factors_are_found_for_exponents_in_the_hundreds_of_millions(
    exponent, k_limit, expected
):
    """The reach of this routine is the whole point, so it is pinned.

    M_999999001 has 301,029,695 decimal digits. If anything here ever starts building
    M_p rather than working modulo the candidate, this test stops finishing.
    """

    result = mersenne_factors(exponent, k_limit=k_limit, timeout=120)
    assert result["factors"] == expected
    for factor in result["factors"]:
        q = int(factor)
        assert (q - 1) % (2 * exponent) == 0
        assert q % 8 in (1, 7)


@pytest.mark.parametrize("exponent", [6_972_593, 20_996_011])
def test_a_known_mersenne_prime_yields_no_factor(exponent):
    """A control. M_6972593 and M_20996011 are prime, so no search can find a factor."""

    result = mersenne_factors(exponent, k_limit=200_000, timeout=180)
    assert result["factors"] == []
    assert result["complete"] is True


def test_finding_nothing_is_inconclusive_not_a_primality_claim():
    result = mersenne_factors(1000003, k_limit=2_000, timeout=120)
    assert result["factors"] == []
    assert result["complete"] is True
    assert "inconclusive" in result["note"]
    assert "says nothing about whether" in result["note"]
    assert "Lucas–Lehmer" in result["note"]


def test_automatic_mode_selects_k_dynamically_and_stops_at_the_first_factor():
    result = mersenne_factors(87083, timeout=30)
    assert result["automatic"] is True
    assert result["factors"] == ["77503871"]
    assert result["scanned_k"] == "445"
    assert result["stop_reason"] == "factor_found"
    assert result["complete"] is False


def test_manual_timeout_preserves_factors_and_reports_actual_k(monkeypatch):
    """PARI/GP's manual path must still preserve findings when its budget expires.

    The compiled scanner now handles finite ranges and finishes this range far inside a
    one-second budget, so the PARI/GP behaviour is exercised by forcing the fallback.
    """

    def unavailable():
        raise RuntimeError("scanner unavailable for this test")

    monkeypatch.setattr(factor_lab, "mfactor_tool_path", unavailable)
    result = mersenne_factors(29, k_limit=50_000_000, timeout=1)
    assert {"233", "1103", "2089"}.issubset(result["factors"])
    assert result["stop_reason"] == "timeout"
    assert 1 <= int(result["scanned_k"]) < 50_000_000
    assert result["complete"] is False


def test_the_scanner_finishes_the_range_that_used_to_time_out():
    """The same request the fallback cannot finish in a second, the scanner completes."""

    result = mersenne_factors(29, k_limit=50_000_000, timeout=120)
    assert {"233", "1103", "2089"}.issubset(result["factors"])
    assert result["stop_reason"] == "ceiling"
    assert result["complete"] is True


def test_staged_hunt_finishes_when_the_remaining_cofactor_is_prime():
    # M_11 = 23 * 89. Trial factoring finds 23 at k=1 and PARI/GP proves 89.
    result = mersenne_factor_hunt(11, trial_k_limit=1, trial_seconds=30)
    assert result["complete"] is True
    assert result["cofactor"] == "89"
    assert result["cofactor_status"] == "proven_prime"
    assert result["factors"] == [{
        "value": "23", "exponent": 1, "status": "proven_prime",
        "engine": "PARI/GP Mersenne trial factoring",
    }]
    assert all(stage["status"] == "not_needed" for stage in result["stages"][1:])


def test_staged_hunt_reconciles_native_engine_factors(monkeypatch):
    # M_43 = 431 * 9719 * 2099863. The bounded trial stage sees only 431;
    # a mocked GMP-ECM boundary reports 9719 and GP owns all resulting arithmetic.
    calls = []

    def native_stage(cofactor, method, b1, curves, timeout, threads):
        calls.append((cofactor, method, b1, curves, timeout, threads))
        return {"status": "factor_found", "factors": ["9719"],
                "detail": "1 divisor(s) reported"}

    monkeypatch.setattr(factor_lab, "_run_ecm_factor_stage", native_stage)
    result = mersenne_factor_hunt(43, trial_k_limit=5, trial_seconds=30)
    assert result["complete"] is True
    assert result["cofactor"] == "2099863"
    assert [item["value"] for item in result["factors"]] == ["431", "9719"]
    assert calls and calls[0][1] == "pm1"
    assert result["stages"][2]["status"] == "not_needed"


def test_staged_hunt_keeps_an_unresolved_composite_explicit(monkeypatch):
    monkeypatch.setattr(
        factor_lab, "_run_ecm_factor_stage",
        lambda *args: {"status": "completed", "factors": [], "detail": "no factor found"},
    )
    result = mersenne_factor_hunt(43, trial_k_limit=5, trial_seconds=30)
    assert result["complete"] is False
    assert result["cofactor_status"] == "composite"
    assert result["cofactor"] == str(9719 * 2099863)
    assert "unresolved" in result["note"]


def test_ecm_does_not_accept_the_whole_cofactor_as_a_proper_factor(monkeypatch):
    class Completed:
        returncode = 2
        stdout = "Factor found in step 1: 439125228929\nFound input number N\n"
        stderr = ""

    monkeypatch.setattr(factor_lab.shutil, "which", lambda name: "/usr/bin/ecm")
    monkeypatch.setattr(factor_lab.subprocess, "run", lambda *args, **kwargs: Completed())
    result = factor_lab._run_ecm_factor_stage("439125228929", "ecm", 1000, 3, 10, 2)
    assert result["factors"] == []
    assert result["status"] == "completed"


def test_an_odd_composite_exponent_searches_every_order_divisor():
    # 1603 = 7 * 229, so M_7 divides M_1603 and contributes 127 at d=7, k=9.
    result = mersenne_factors(1603, k_limit=100, timeout=60)
    assert result["exponent_prime"] is False
    assert result["exponent_factorization"] == "7 * 229"
    assert ["127", "9", "7", "3"] in result["rows"]
    assert result["metrics"]["Order divisors completed"] == "3 of 3"


def test_bounds_are_enforced():
    for kwargs in (
        {"exponent": 1},
        {"exponent": 2},  # M_2 = 3 is the trivial exception to q = 2kp + 1.
        {"exponent": 11, "k_limit": 0},
        {"exponent": 11, "k_limit": 100_000_000_001},
        {"exponent": 11, "timeout": 0},
    ):
        with pytest.raises(ValueError):
            mersenne_factors(**kwargs)


# --- the regression that made large Mersenne work possible --------------------------------


@pytest.mark.parametrize("expression,digits", [
    ("2^1061-1", "320"),
    ("10^101-1", "101"),
    ("2^4253-1", "1281"),
])
def test_special_form_analysis_does_not_try_to_factor_the_input(expression, digits):
    """Regression: this routine used to attempt a full factorization of Phi_n(b).

    Phi_n(b) is the whole input when n is prime, so 2^1061 - 1 and 10^101 - 1 both
    exhausted a 180-second budget and returned nothing. They now answer immediately.
    """

    result = special_form_analysis(expression, timeout=60)
    assert result["digits"] == digits
    assert result["complete"] is True


def test_the_snfs_polynomial_for_a_mersenne_is_reported():
    result = special_form_analysis("2^1061-1", timeout=60)
    assert result["snfs_suitable"] is True
    assert result["snfs_polynomial"] == "x^1061 - 1"
    # SNFS difficulty is the size of the number, not of a general 320-digit input.
    assert result["snfs_difficulty"] == "319"
    assert result["forms"][0]["detail"] == "n = 2^1061 - 1"


# --- API -----------------------------------------------------------------------------------


def test_mersenne_route_saves_a_report(local_client, tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    response = local_client.post(
        "/api/factor-lab/mersenne-factors",
        json={"exponent": 23, "k_limit": 30000, "timeout_seconds": 120},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["factors"] == ["47", "178481"]
    assert payload["output_file"].endswith(".txt")


def test_staged_hunt_route_saves_exact_cofactor(local_client, tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    response = local_client.post(
        "/api/factor-lab/mersenne-hunt",
        json={"exponent": 11, "trial_k_limit": 1, "trial_seconds": 30},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["complete"] is True
    assert payload["cofactor"] == "89"
    report = (tmp_path / payload["output_file"]).read_text(encoding="utf-8")
    assert "Exact remaining cofactor (2 digits; proven_prime):\n89" in report


def test_mersenne_route_accepts_an_odd_composite_exponent(local_client):
    response = local_client.post(
        "/api/factor-lab/mersenne-factors", json={"exponent": 1603, "k_limit": 100}
    )
    assert response.status_code == 200
    assert "127" in response.json()["factors"]


# --- the compiled scanner ------------------------------------------------------------


def test_the_scanner_emits_a_completion_marker():
    tool = mfactor_tool_path()
    output = subprocess.run(
        [str(tool), "11", "1", "1000", "1000"], capture_output=True, text=True
    ).stdout
    assert "DONE:1" in output
    assert "STATUS:complete" in output


def test_the_scanner_rejects_an_even_or_tiny_order():
    tool = mfactor_tool_path()
    for argv in (["4", "1", "10"], ["1", "1", "10"], ["11", "0", "10"], ["11", "5", "1"]):
        result = subprocess.run([str(tool), *argv], capture_output=True, text=True)
        assert result.returncode == 2, argv


@pytest.mark.parametrize("order,k_limit,expected", [
    (11, 20_000, ["23", "89"]),
    (23, 20_000, ["47", "178481"]),
    (43, 30_000, ["431", "9719", "2099863"]),
    (2_000_003, 3_000_000, ["160000241", "8924785387159"]),
    (999_999_001, 200_000_000, ["357999642359", "216674111542346329"]),
])
def test_the_scanner_recovers_every_known_factor(order, k_limit, expected):
    """The same answers PARI/GP gives, from the compiled path."""

    hits, _ = _mersenne_native_scan([order], k_limit, timeout=600, threads=None)
    assert sorted(int(q) for q, _, _ in hits) == sorted(int(q) for q in expected)


def test_the_scanner_handles_candidates_above_2_64_with_gmp():
    """Beyond 2^64 the 64-bit path cannot run and GMP takes over.

    q = 18446744073709551697 is prime, exceeds 2^64, and the order of 2 modulo it is
    384307168202282327, which places it at k = 24 in that progression. A scanner that
    silently skipped wide candidates would report nothing here.
    """

    order = 384307168202282327
    tool = mfactor_tool_path()
    output = subprocess.run(
        [str(tool), str(order), "1", "60", "100000"], capture_output=True, text=True
    ).stdout
    assert "FACTOR:18446744073709551697|24" in output
    # WIDE counts the candidates that needed GMP; this one must be among them.
    wide = int([line for line in output.splitlines() if line.startswith("WIDE:")][0][5:])
    assert wide >= 1


def test_scanned_candidates_are_confirmed_by_the_engine_not_trusted():
    """The scanner reports divisors of 2^d - 1; primality is PARI/GP's call.

    9 divides nothing relevant and is composite, so confirmation must drop it while
    keeping the genuine factor.
    """

    kept = _mersenne_confirm([("127", 9, 7), ("9", 1, 7)], timeout=60)
    assert [q for q, _, _ in kept] == ["127"]


SCANNERS = {
    "numerisect-mfactor with PARI/GP confirmation",
    "numerisect-mfactor-cuda with PARI/GP confirmation",
}


def test_the_public_search_uses_a_compiled_scanner_for_a_finite_range():
    """Either scanner is acceptable; PARI/GP alone is not, for a finite range."""

    result = mersenne_factors(43, k_limit=30_000, timeout=120)
    assert result["engine"] in SCANNERS
    assert result["factors"] == ["431", "9719", "2099863"]
    assert result["complete"] is True


def test_the_public_search_falls_back_to_pari_when_the_scanner_is_missing(monkeypatch):
    """A machine with no C compiler must still be able to run this search."""

    from numerisect import factor_lab

    def unavailable():
        raise RuntimeError("no compiler")

    monkeypatch.setattr(factor_lab, "mfactor_tool_path", unavailable)
    result = mersenne_factors(43, k_limit=30_000, timeout=180)
    assert result["engine"] == "PARI/GP"
    assert result["factors"] == ["431", "9719", "2099863"]


def test_automatic_mode_still_runs_in_pari():
    """Stop-at-first-factor and budget semantics live in PARI/GP, not the scanner."""

    result = mersenne_factors(2_000_003, k_limit=None, timeout=120)
    assert result["engine"] == "PARI/GP"
    assert result["automatic"] is True


# --- the optional CUDA accelerator ------------------------------------------------------


def test_cuda_is_optional_and_its_absence_is_not_an_error():
    """A driver without a toolkit must not be mistaken for a usable compiler.

    nvcc-gpp15 is a wrapper that execs nvcc. On a machine with the driver but no
    toolkit the wrapper exists and the compiler does not, so detection probes rather
    than trusting PATH.
    """

    compiler = cuda_compiler()
    if compiler is None:
        assert build_mfactor_cuda_tool() is None
    else:
        built = build_mfactor_cuda_tool()
        assert built is not None and built.is_file()


def test_the_response_names_the_engine_that_actually_ran(local_client):
    """A report must not credit PARI/GP with work the compiled scanner did.

    The shared report saver overwrote the engine label unconditionally, so a scan run
    entirely by numerisect-mfactor came back labelled PARI/GP.
    """

    scanned = local_client.post(
        "/api/factor-lab/mersenne-factors",
        json={"exponent": 43, "k_limit": 30000, "timeout_seconds": 120},
    ).json()
    assert scanned["engine"] in SCANNERS
    # The label must name the scanner that actually ran, CPU or device.
    assert scanned["metrics"]["Scanner"].startswith("numerisect-mfactor")
    assert ("cuda" in scanned["engine"]) == ("cuda" in scanned["metrics"]["Scanner"])

    automatic = local_client.post(
        "/api/factor-lab/mersenne-factors",
        json={"exponent": 2000003, "timeout_seconds": 120},
    ).json()
    assert automatic["engine"] == "PARI/GP"


def test_the_gpu_is_used_only_inside_the_montgomery_bound():
    """Speed must never come at the cost of leaving candidates untested.

    Montgomery REDC on the device needs q < 2**63. Where the requested range would
    exceed that, the C helper must run instead, because it tests wide candidates with
    GMP rather than deferring them.
    """

    from numerisect.factor_lab import MONTGOMERY_LIMIT
    from numerisect.native_tools import mfactor_cuda_tool_path

    inside = mersenne_factors(999_999_001, k_limit=1_000_000, timeout=300)
    assert 2 * 1_000_000 * 999_999_001 + 1 < MONTGOMERY_LIMIT
    if mfactor_cuda_tool_path() is not None:
        assert "cuda" in inside["engine"]

    # This order puts every candidate beyond the bound, so the C helper must take it.
    order = 384307168202282327
    assert 2 * 60 * order + 1 > MONTGOMERY_LIMIT
    hits, gpu_used = _mersenne_native_scan([order], 60, timeout=300, threads=None)
    assert gpu_used is False
    assert [q for q, _, _ in hits] == ["18446744073709551697"]


def test_the_two_scanners_agree():
    """Two independent implementations of the same search must not disagree."""

    from numerisect.native_tools import mfactor_cuda_tool_path

    if mfactor_cuda_tool_path() is None:
        pytest.skip("no CUDA accelerator built")

    import subprocess as sp

    from numerisect.native_tools import mfactor_tool_path

    order, k_limit = 2_000_003, 3_000_000

    def factors(tool, extra):
        out = sp.run([str(tool), str(order), "1", str(k_limit), "1000000", *extra],
                     capture_output=True, text=True).stdout
        return sorted(int(line.split(":", 1)[1].split("|")[0])
                      for line in out.splitlines() if line.startswith("FACTOR:"))

    assert factors(mfactor_cuda_tool_path(), []) == factors(mfactor_tool_path(), ["24"])
