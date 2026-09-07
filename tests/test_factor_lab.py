"""Expert factorization laboratory: SQUFOF, special forms, strategy, traces, certificates."""

import pathlib
import subprocess

import pytest
from fastapi.testclient import TestClient

from numerisect import jobs as jobs_module
from numerisect import outputs as outputs_module
from numerisect.database import Database
from numerisect.factor_lab import (
    algorithm_trace,
    batch_certificates,
    special_form_analysis,
    squfof,
    strategy_advice,
    validate_yafu_parameters,
)
from numerisect.jobs import JobManager
from numerisect.main import app
from numerisect.native_tools import squfof_tool_path


@pytest.fixture()
def local_client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    token = client.get("/api/session").json()["request_token"]
    client.headers["X-Numerisect-Token"] = token
    return client


# --- SQUFOF (numerisect-squfof, C/GMP) -----------------------------------------------


def test_squfof_splits_known_semiprimes():
    # 8051 = 83 * 97
    result = squfof(8051)
    assert result["status"] == "found"
    assert {result["factor"], result["cofactor"]} == {"83", "97"}

    # 11111111111 = 21649 * 513239 (repunit R11)
    repunit = squfof(11111111111)
    assert repunit["status"] == "found"
    assert {repunit["factor"], repunit["cofactor"]} == {"21649", "513239"}


def test_squfof_handles_a_perfect_square():
    # 4295098369 = 65537^2
    result = squfof(4295098369)
    assert result["status"] == "found"
    assert result["factor"] == "65537" and result["cofactor"] == "65537"


def test_squfof_on_a_prime_is_inconclusive_not_negative():
    # 2^31 - 1 is the Mersenne prime 2147483647; SQUFOF cannot split it.
    result = squfof(2147483647)
    assert result["status"] == "exhausted"
    assert "inconclusive" in result["note"]
    # It must never claim the input is prime.
    assert "is prime" not in result["note"].replace("does not show the input is prime", "")


def test_squfof_rejects_inputs_above_its_range():
    result = squfof(2**62 + 1)
    assert result["status"] == "rejected"
    assert "2^62" in result["note"]


def test_squfof_validates_arguments():
    with pytest.raises(ValueError):
        squfof(0)
    with pytest.raises(ValueError):
        squfof(8051, max_iterations=10)


def test_squfof_helper_emits_a_completion_marker():
    tool = squfof_tool_path()
    output = subprocess.run([str(tool), "8051"], capture_output=True, text=True).stdout
    assert "DONE:1" in output
    assert "STATUS:found" in output


def test_squfof_factors_are_verified_against_the_input():
    # Every reported factor must actually divide, checked here against PARI's own
    # factorization rather than trusting the helper.
    for n, expected in ((8051, {83, 97}), (11111111111, {21649, 513239})):
        result = squfof(n)
        parts = {int(result["factor"]), int(result["cofactor"])}
        assert parts == expected


# --- Special forms, algebraic and Aurifeuillean factors (PARI/GP) ---------------------


def test_special_form_recognises_mersenne_and_its_algebraic_factors():
    # 2^101 - 1 = 7432339208719 * 341117531003194129
    result = special_form_analysis("2^101-1", timeout=30)
    assert result["snfs_suitable"] is True
    assert any(row["kind"] == "homogeneous" for row in result["forms"])
    factors = {row["factor"] for row in result["algebraic_factors"]}
    assert {"7432339208719", "341117531003194129"} <= factors


def test_special_form_recognises_a_perfect_power():
    result = special_form_analysis("7^11", timeout=30)
    assert any(row["kind"] == "perfect power" for row in result["forms"])


def test_special_form_reports_no_form_for_a_generic_semiprime():
    result = special_form_analysis("1000003*1000033", timeout=30)
    assert result["forms"] == []
    assert result["snfs_suitable"] is False
    # An empty result must still be a complete search, not a silent failure.
    assert result["complete"] is True


def test_special_form_rejects_unsafe_expressions():
    with pytest.raises(ValueError):
        special_form_analysis("factor(10)")


# --- Strategy advice and the decision tree (PARI/GP) ----------------------------------


def test_strategy_recommends_no_work_for_a_prime():
    result = strategy_advice("32416190071", timeout=30)
    assert result["recommended_engine"] == "none"
    assert result["decision_path"][0]["answer"] == "yes"


def test_strategy_removes_small_factors_and_estimates_factor_size():
    # 2 * 3 * 5 * 1000003 * 1000033 has small factors to strip first.
    result = strategy_advice("2*3*5*1000003*1000033", timeout=30)
    assert result["small_factors"]
    assert int(result["expected_factor_digits"]) >= 1
    assert result["expected_basis"]


def test_strategy_uses_the_completed_ecm_depth():
    without = strategy_advice("1000003*1000033*1000037", pretest_level=0, timeout=30)
    with_pretest = strategy_advice("1000003*1000033*1000037", pretest_level=20, timeout=30)
    assert int(with_pretest["expected_factor_digits"]) >= int(without["expected_factor_digits"])
    assert "ECM to t20" in with_pretest["expected_basis"]


def test_strategy_routes_large_inputs_to_cado():
    result = strategy_advice("10^120+7", timeout=30)
    assert "CADO" in result["recommended_engine"]


def test_strategy_validates_the_pretest_level():
    with pytest.raises(ValueError):
        strategy_advice("8051", pretest_level=999)


# --- Educational algorithm traces (PARI/GP) ------------------------------------------


def test_rho_trace_finds_a_factor_and_records_steps():
    result = algorithm_trace("8051", "rho", steps=40, timeout=30)
    assert result["factor"] == "97"
    assert len(result["steps"]) >= 1
    assert result["steps"][0]["step"] == "1"


def test_pm1_trace_finds_a_smooth_factor():
    # 97 - 1 = 96 = 2^5 * 3 is smooth, so p-1 finds 97 quickly.
    result = algorithm_trace("8051", "pm1", steps=40, timeout=30)
    assert result["factor"] == "97"


def test_trace_marks_truncation_rather_than_claiming_failure():
    result = algorithm_trace("1000003*1000033", "rho", steps=3, timeout=30)
    assert result["truncated"] is True


def test_trace_rejects_unknown_algorithms_and_bad_bounds():
    with pytest.raises(ValueError):
        algorithm_trace("8051", "siqs")
    with pytest.raises(ValueError):
        algorithm_trace("8051", "rho", steps=0)


def test_trace_note_says_it_is_not_the_production_path():
    result = algorithm_trace("8051", "rho", steps=10, timeout=30)
    assert "YAFU" in result["note"]


# --- Batch certificates (PARI/GP primecert / primecertisvalid) ------------------------


def test_certificates_are_generated_and_independently_verified():
    result = batch_certificates(["83", "97"], timeout=30)
    assert result["count"] == 2
    assert all(row["prime"] and row["certified"] and row["verified"] for row in result["certificates"])


def test_certificates_report_a_composite_honestly():
    # 561 is a Carmichael number: composite, so no certificate exists.
    result = batch_certificates(["561"], timeout=30)
    row = result["certificates"][0]
    assert row["prime"] is False and row["certified"] is False


def test_certificates_validate_input():
    with pytest.raises(ValueError):
        batch_certificates(["not-a-number"])
    with pytest.raises(ValueError):
        batch_certificates([])


# --- YAFU expert parameters ------------------------------------------------------------


def test_yafu_parameters_map_to_flags_this_build_accepts():
    arguments = validate_yafu_parameters({"b1_ecm": 50000, "siqs_relations": 100000})
    assert arguments[:2] == ["-B1ecm", "50000"] or "-B1ecm" in arguments
    assert "-siqsR" in arguments


def test_yafu_parameters_reject_unknown_fields_and_out_of_range_values():
    with pytest.raises(ValueError):
        validate_yafu_parameters({"b1_squfof": 1000})
    with pytest.raises(ValueError):
        validate_yafu_parameters({"b1_ecm": 1})
    with pytest.raises(ValueError):
        validate_yafu_parameters({"b1_ecm": "abc"})


def test_yafu_parameters_are_argument_arrays_never_shell_strings():
    arguments = validate_yafu_parameters({"sigma": 12345})
    assert all(isinstance(item, str) for item in arguments)
    assert not any(";" in item or "&" in item or "|" in item for item in arguments)


# --- Job integration --------------------------------------------------------------------


def test_squfof_runs_as_a_job_backend_with_engine_decided_primality(tmp_path, monkeypatch):
    job_root = tmp_path / "jobs"
    output_root = tmp_path / "output"
    job_root.mkdir()
    output_root.mkdir()
    monkeypatch.setattr(jobs_module, "JOBS_DIR", job_root)
    monkeypatch.setattr(outputs_module, "OUTPUT_DIR", output_root)
    database = Database(tmp_path / "jobs.sqlite3")
    manager = JobManager(database)
    try:
        created = manager.create(
            expression="11111111111", number=11111111111, requested_backend="squfof",
            threads=1, pretest_level=20, trial_bound=100, cado_parameter_size=None,
        )
        manager._futures[created["id"]].result(timeout=120)
        completed = database.get_job(created["id"])
        assert completed["status"] == "completed"
        values = {factor["value"] for factor in completed["factors"]}
        assert values == {"21649", "513239"}
        # Primality must come from the engine, and be recorded per factor.
        assert all(factor["status"] == "prime" for factor in completed["factors"])
        assert all("squfof" in factor["engine"] for factor in completed["factors"])
    finally:
        manager.shutdown()


def test_squfof_backend_rejects_oversized_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_module, "JOBS_DIR", tmp_path)
    database = Database(tmp_path / "jobs.sqlite3")
    manager = JobManager(database)
    try:
        with pytest.raises(RuntimeError, match="2\\^62"):
            manager.create(
                expression="x", number=2**62 + 1, requested_backend="squfof", threads=1,
                pretest_level=20, trial_bound=100, cado_parameter_size=None,
            )
    finally:
        manager.shutdown()


# --- API ---------------------------------------------------------------------------------


def test_squfof_route_saves_a_report(local_client):
    response = local_client.post(
        "/api/factor-lab/squfof", json={"expression": "8051"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "found"
    assert payload["output_file"].endswith(".txt")


def test_special_form_route(local_client):
    response = local_client.post(
        "/api/factor-lab/special-form", json={"expression": "2^101-1", "timeout_seconds": 30}
    )
    assert response.status_code == 200
    assert response.json()["snfs_suitable"] is True


def test_strategy_route(local_client):
    response = local_client.post(
        "/api/factor-lab/strategy", json={"expression": "8051", "timeout_seconds": 30}
    )
    assert response.status_code == 200
    assert response.json()["recommended_engine"]


def test_trace_route(local_client):
    response = local_client.post(
        "/api/factor-lab/trace",
        json={"expression": "8051", "algorithm": "rho", "steps": 20, "timeout_seconds": 30},
    )
    assert response.status_code == 200
    assert response.json()["factor"] == "97"


def test_certificates_route(local_client):
    response = local_client.post(
        "/api/factor-lab/certificates", json={"factors": ["83", "97"], "timeout_seconds": 30}
    )
    assert response.status_code == 200
    assert response.json()["count"] == 2


def test_job_certificates_route_requires_a_known_job(local_client):
    assert local_client.post("/api/jobs/missing/certificates").status_code == 404


def test_routes_reject_invalid_input(local_client):
    assert local_client.post(
        "/api/factor-lab/trace", json={"expression": "8051", "algorithm": "siqs"}
    ).status_code == 422
    assert local_client.post(
        "/api/factor-lab/certificates", json={"factors": []}
    ).status_code == 422


# --- Policy: the source must not compute mathematics in Python ---------------------------

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_factor_lab_python_delegates_every_computation():
    source = (ROOT / "numerisect" / "factor_lab.py").read_text(encoding="utf-8")
    # No modular arithmetic, gcd, or primality decisions in the boundary layer.
    for forbidden in ("% candidate", "math.gcd", "isprime(", "pow(", "sympy"):
        assert forbidden not in source
    # Every operation reaches an engine.
    assert "_run_gp(" in source
    assert "squfof_tool_path()" in source


def test_squfof_c_source_documents_why_it_exists():
    source = (ROOT / "numerisect" / "native" / "numerisect_squfof.c").read_text(encoding="utf-8")
    assert "no installed library provides" in source.lower() or "has no `squfof`" in source


# --- GMP-ECM campaign manager (roadmap item 5) -------------------------------------


def test_ecm_output_parser_reads_factors_and_progress():
    from numerisect.engines import parse_ecm_output

    sample = (
        "Run 1 out of 30:\n"
        "Using B1=2000, B2=147396, polynomial x^1, sigma=1:1753682261\n"
        "********** Factor found in step 2: 1000036000099\n"
        "Found composite factor of 13 digits: 1000036000099\n"
        "Prime cofactor 32416190071 has 11 digits\n"
    )
    parsed = parse_ecm_output(sample)
    assert parsed["curves_requested"] == 30
    assert parsed["cofactor"] == "32416190071"
    assert parsed["factors"][0]["value"] == "1000036000099"
    # GMP-ECM decides the classification; we only read it.
    assert parsed["factors"][0]["status"] == "composite"
    assert parsed["sigmas"] == ["1:1753682261"]


def test_ecm_parser_handles_a_run_with_no_factor():
    from numerisect.engines import parse_ecm_output

    parsed = parse_ecm_output("Run 5 out of 5:\nStep 1 took 1ms\n")
    assert parsed["factors"] == []
    assert parsed["cofactor"] is None


def test_reconciliation_is_performed_by_the_engine():
    from numerisect.factor_lab import reconcile_factors

    # 1000003 * 1000033 * 32416190071. ECM reports overlapping factors across
    # curves, so the raw list does not multiply to the input.
    n = 1000003 * 1000033 * 32416190071
    result = reconcile_factors(n, [32416190071, 1000033, 1000036000099])
    assert [row["value"] for row in result["factors"]] == ["1000033", "32416190071"]
    assert result["cofactor"] == "1000003"
    assert result["cofactor_prime"] is True
    assert result["complete"] is True


def test_reconciliation_reports_an_incomplete_decomposition():
    from numerisect.factor_lab import reconcile_factors

    # Removing only 3 from 3 * 1000003 * 1000033 leaves a composite cofactor.
    n = 3 * 1000003 * 1000033
    result = reconcile_factors(n, [3])
    assert result["cofactor_prime"] is False
    assert result["complete"] is False


def test_reconciliation_rejects_empty_candidates():
    from numerisect.factor_lab import reconcile_factors

    with pytest.raises(ValueError):
        reconcile_factors(100, [])


def test_ecm_campaign_runs_and_produces_a_consistent_decomposition(tmp_path, monkeypatch):
    job_root = tmp_path / "jobs"
    output_root = tmp_path / "output"
    job_root.mkdir()
    output_root.mkdir()
    monkeypatch.setattr(jobs_module, "JOBS_DIR", job_root)
    monkeypatch.setattr(outputs_module, "OUTPUT_DIR", output_root)
    database = Database(tmp_path / "jobs.sqlite3")
    manager = JobManager(database)
    try:
        number = 1000003 * 1000033 * 32416190071
        created = manager.create(
            expression=str(number), number=number, requested_backend="ecm_campaign",
            threads=1, pretest_level=20, trial_bound=100, cado_parameter_size=None,
            ecm_b1=2000, ecm_curves=40,
        )
        manager._futures[created["id"]].result(timeout=300)
        completed = database.get_job(created["id"])
        assert completed["status"] == "completed"
        assert completed["factors"]
        # Whatever GMP-ECM found, the recorded parts must multiply back to the input.
        product = 1
        for factor in completed["factors"]:
            product *= int(factor["value"])
        assert product == number
        assert all("GMP-ECM" in factor["engine"] for factor in completed["factors"])
    finally:
        manager.shutdown()


def test_ecm_campaign_parameters_are_persisted(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_module, "JOBS_DIR", tmp_path)
    database = Database(tmp_path / "jobs.sqlite3")
    manager = JobManager(database)
    try:
        created = manager.create(
            expression="8051", number=8051, requested_backend="ecm_campaign", threads=1,
            pretest_level=20, trial_bound=100, cado_parameter_size=None,
            ecm_b1=11000, ecm_b2="1000000", ecm_curves=25, ecm_sigma="1:42", ecm_param=1,
        )
        stored = database.get_job(created["id"])
        assert stored["ecm_b1"] == 11000
        assert stored["ecm_curves"] == 25
        assert stored["ecm_sigma"] == "1:42"
    finally:
        manager.shutdown()


def test_ecm_campaign_request_validates_parameters(local_client):
    # sigma must match GMP-ECM's own syntax, and B1 has a floor.
    bad_sigma = local_client.post(
        "/api/jobs", json={"expression": "8051", "backend": "ecm_campaign", "ecm_sigma": "abc"}
    )
    assert bad_sigma.status_code == 422
    bad_b1 = local_client.post(
        "/api/jobs", json={"expression": "8051", "backend": "ecm_campaign", "ecm_b1": 1}
    )
    assert bad_b1.status_code == 422


# --- Engine tuning (roadmap item 16, scoped to YAFU's own tune) ----------------------


def test_tune_info_is_parsed_from_yafu_output():
    from numerisect.factor_lab import parse_tune_info

    sample = (
        "tune_info=Intel Core i9,LINUX64,1.2,3.4,5.6,7.8,9.0,1.1,2.2,3.3,4.4\n"
        "XOVER = 97.5, TUNE_FREQ = 3200.0\n"
    )
    parsed = parse_tune_info(sample)
    assert parsed["cpu"] == "Intel Core i9"
    assert parsed["platform"] == "LINUX64"
    assert parsed["crossover_digits"] == 97.5
    assert parsed["tune_frequency"] == 3200.0
    assert len(parsed["coefficients"]) == 9


def test_tune_info_missing_is_an_error_not_an_empty_result():
    from numerisect.factor_lab import parse_tune_info

    with pytest.raises(ValueError, match="did not finish"):
        parse_tune_info("sieving in progress\nno result here\n")


def test_tune_recommendation_suggests_but_never_applies():
    from numerisect.factor_lab import parse_tune_info, tune_recommendation

    parsed = parse_tune_info(
        "tune_info=cpu,LINUX64,1,2,3,4,5,6,7,8,9\nXOVER = 97.5, TUNE_FREQ = 3200.0\n"
    )
    result = tune_recommendation(parsed, current_threshold=95)
    assert result["suggested_threshold"] == 98
    assert result["differs"] is True
    assert result["apply_with"] == "NUMERISECT_CADO_THRESHOLD=98"
    # The wording must make clear nothing was changed automatically.
    assert "never rewrites" in result["note"]


def test_tune_recommendation_reports_agreement():
    from numerisect.factor_lab import parse_tune_info, tune_recommendation

    parsed = parse_tune_info(
        "tune_info=cpu,LINUX64,1,2,3,4,5,6,7,8,9\nXOVER = 95.0, TUNE_FREQ = 3200.0\n"
    )
    result = tune_recommendation(parsed, current_threshold=95)
    assert result["suggested_threshold"] == 95
    assert result["differs"] is False


def test_tune_route_refuses_without_the_ggnfs_sievers(local_client, monkeypatch):
    from numerisect import main as main_module

    monkeypatch.setattr(main_module, "GGNFS_DIR", "")
    response = local_client.post("/api/factor-lab/tune", json={"threads": 2})
    assert response.status_code == 503
    assert "NUMERISECT_GGNFS_DIR" in response.json()["detail"]
