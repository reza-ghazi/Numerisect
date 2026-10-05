"""NFS polynomial selection: Msieve as its own stage, and CADO's selection keys.

Selection is the first phase of the number field sieve and the one whose result is
reused, so both engines expose knobs for it that Numerisect did not reach. The engines
are stubbed here, so these run where neither Msieve nor CADO is installed; the Msieve
fixture is real output captured from a 91-digit run.
"""

import pytest

from numerisect import jobs, outputs
from numerisect.database import Database
from numerisect.engines import (
    parse_msieve_polynomial,
    validate_cado_polyselect_parameters,
    validate_msieve_polyselect_parameters,
)
from numerisect.jobs import JobManager

# Captured from `msieve -v -np "poly_deadline=20" -nf poly.fb -s msieve.dat <91 digits>`.
MSIEVE_OUTPUT = """save 1.579001e-12 -4.7353 578946.79 3.631973e-08 rroots 2
save 1.742122e-12 -5.8012 1049584.90 3.774784e-08 rroots 2
hashtable: 512 entries,  0.01 MB
polynomial selection complete
R0: -6985661004471969578205
R1: 1772669054239
A0: -399845697430959745068138464
A1: 1895269242184159135816
A2: 320512938895331
A3: -906842524
A4: 1260
skew 1049584.90, size 1.387e-12, alpha -5.801, combined = 3.775e-08 rroots = 2
elapsed time 00:00:41"""


def _manager(tmp_path, monkeypatch) -> JobManager:
    job_root = tmp_path / "jobs"
    output_root = tmp_path / "output"
    job_root.mkdir()
    output_root.mkdir()
    monkeypatch.setattr(jobs, "JOBS_DIR", job_root)
    monkeypatch.setattr(outputs, "OUTPUT_DIR", output_root)
    monkeypatch.setattr(jobs, "executable_path", lambda name: f"/usr/bin/{name}")
    return JobManager(Database(tmp_path / "jobs.sqlite3"))


def _capture(manager, monkeypatch, output):
    commands: list[list[str]] = []

    def fake_run(job, command, **kwargs):
        commands.append(list(command))
        return 0, output

    monkeypatch.setattr(manager, "_run_process", fake_run)
    return commands


# --- Reading Msieve's selection output --------------------------------------------------


def test_the_polynomial_is_read_with_its_quality_metrics():
    polynomial = parse_msieve_polynomial(MSIEVE_OUTPUT)
    assert polynomial["complete"] is True
    assert polynomial["degree"] == 4
    assert polynomial["skew"] == "1049584.90"
    assert polynomial["alpha"] == "-5.801"
    assert polynomial["combined"] == "3.775e-08"
    assert polynomial["rroots"] == "2"
    assert polynomial["rational"] == ["-6985661004471969578205", "1772669054239"]
    assert polynomial["algebraic"][0] == "-399845697430959745068138464"
    assert polynomial["algebraic"][-1] == "1260"
    assert polynomial["candidates"] == 2


def test_a_single_stage_reports_candidates_and_claims_no_polynomial():
    """Only a full run finishes a polynomial; a stage saves candidates.

    Inferring a polynomial from stage output would be inventing one.
    """

    polynomial = parse_msieve_polynomial(
        "save 1.1e-12 -4.0 500.00 3.0e-08 rroots 2\nsave 1.2e-12 -4.1 600.00 3.1e-08 rroots 2\n"
    )
    assert polynomial["complete"] is False
    assert polynomial["degree"] is None
    assert polynomial["rational"] == [] and polynomial["algebraic"] == []
    assert polynomial["candidates"] == 2


# --- Validating what reaches each engine ------------------------------------------------


def test_msieve_options_become_the_single_parameter_string_it_expects():
    rendered = validate_msieve_polyselect_parameters(
        {"degree": 5, "deadline": 60, "min_coeff": 1, "max_coeff": 1000}
    )
    assert rendered == "polydegree=5 poly_deadline=60 min_coeff=1 max_coeff=1000"
    assert validate_msieve_polyselect_parameters({}) == ""


def test_cado_options_become_namespaced_overrides():
    assert validate_cado_polyselect_parameters({"P": 10000, "nq": 256}) == [
        "tasks.polyselect.P=10000",
        "tasks.polyselect.nq=256",
    ]
    # The effort knobs are fractional, and CADO's own parameter files write them so.
    assert validate_cado_polyselect_parameters({"ropteffort": 0.4}) == [
        "tasks.polyselect.ropteffort=0.4"
    ]


@pytest.mark.parametrize("options,message", [
    ({"nonsense": 1}, "not a supported Msieve polyselect parameter"),
    ({"degree": 9}, "must be between 4 and 6"),
    ({"deadline": 0}, "must be between"),
    ({"min_coeff": 10, "max_coeff": 2}, "min_coeff must not exceed max_coeff"),
    ({"degree": "five"}, "must be an integer"),
])
def test_invalid_msieve_options_are_refused(options, message):
    with pytest.raises(ValueError, match=message):
        validate_msieve_polyselect_parameters(options)


@pytest.mark.parametrize("options,message", [
    ({"nonsense": 1}, "not a supported CADO polyselect parameter"),
    ({"P": 1}, "must be between"),
    ({"admin": 100, "admax": 10}, "admin must be below admax"),
    ({"nq": "many"}, "must be a number"),
])
def test_invalid_cado_options_are_refused(options, message):
    with pytest.raises(ValueError, match=message):
        validate_cado_polyselect_parameters(options)


# --- What reaches the engines ------------------------------------------------------------


def test_the_msieve_selection_command_carries_the_stage_and_its_options(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch)
    commands = _capture(manager, monkeypatch, MSIEVE_OUTPUT)
    try:
        created = manager.create(
            expression="10403", number=10403, requested_backend="msieve_poly", threads=4,
            pretest_level=20, trial_bound=100, cado_parameter_size=None,
            polyselect_stage="full", polyselect_options={"degree": 4, "deadline": 15},
        )
        manager._futures[created["id"]].result(timeout=60)
        row = manager.database.get_job(created["id"])
    finally:
        manager.shutdown()
    command = commands[0]
    assert "-np" in command
    assert "polydegree=4 poly_deadline=15" in command
    assert command[command.index("-t") + 1] == "4"
    assert any(part.endswith("poly.fb") for part in command)
    assert row["status"] == "completed"


@pytest.mark.parametrize("stage,flag", [
    ("stage1", "-np1"), ("size", "-nps"), ("root", "-npr"),
])
def test_each_stage_uses_its_own_msieve_flag(tmp_path, monkeypatch, stage, flag):
    manager = _manager(tmp_path, monkeypatch)
    commands = _capture(manager, monkeypatch, "save 1.1e-12 -4.0 500.00 3.0e-08 rroots 2\n")
    try:
        created = manager.create(
            expression="10403", number=10403, requested_backend="msieve_poly", threads=1,
            pretest_level=20, trial_bound=100, cado_parameter_size=None,
            polyselect_stage=stage,
        )
        manager._futures[created["id"]].result(timeout=60)
        row = manager.database.get_job(created["id"])
    finally:
        manager.shutdown()
    assert flag in commands[0]
    # A stage that saves candidates is a completed report, not a failed factorization.
    assert row["status"] == "completed"
    assert row["factors"][0]["status"] == "candidates"


def test_a_full_selection_that_never_completes_is_an_error(tmp_path, monkeypatch):
    """Msieve exiting zero without a polynomial must not read as a finished selection."""

    manager = _manager(tmp_path, monkeypatch)
    _capture(manager, monkeypatch, "save 1.1e-12 -4.0 500.00 3.0e-08 rroots 2\n")
    try:
        created = manager.create(
            expression="10403", number=10403, requested_backend="msieve_poly", threads=1,
            pretest_level=20, trial_bound=100, cado_parameter_size=None,
        )
        manager._futures[created["id"]].result(timeout=60)
        row = manager.database.get_job(created["id"])
    finally:
        manager.shutdown()
    assert row["status"] == "failed"
    assert "inconclusive" in (row["error"] or "")


def test_cado_receives_the_selection_overrides(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch)
    # CADO's own parameter discovery is not needed for command assembly.
    monkeypatch.setattr(manager, "parameters", [])
    monkeypatch.setattr(
        jobs, "select_cado_parameter",
        lambda digits, parameters, requested=None: jobs.CadoParameter(90, tmp_path / "params.c90"),
    )
    commands = _capture(manager, monkeypatch, "Factors: 101 103\n")
    try:
        created = manager.create(
            expression="10403", number=10403, requested_backend="cado", threads=2,
            pretest_level=20, trial_bound=100, cado_parameter_size=None,
            polyselect_options={"P": 20000, "admax": 50000, "ropteffort": 0.5},
        )
        manager._futures[created["id"]].result(timeout=60)
    finally:
        manager.shutdown()
    command = commands[0]
    assert "tasks.polyselect.P=20000" in command
    assert "tasks.polyselect.admax=50000" in command
    assert "tasks.polyselect.ropteffort=0.5" in command
    # The required assignment is still added alongside them.
    assert "slaves.hostnames=localhost" in command
    # Assignments must stay after the integer: CADO rejects them interleaved with flags.
    assert command.index("10403") < command.index("tasks.polyselect.P=20000")


# --- Validation at creation time --------------------------------------------------------


def test_an_option_is_validated_against_the_engine_that_will_receive_it(tmp_path, monkeypatch):
    """`deadline` is Msieve's and `nq` is CADO's; neither engine understands the other."""

    manager = _manager(tmp_path, monkeypatch)
    try:
        with pytest.raises(ValueError, match="not a supported CADO"):
            manager.create(
                expression="10403", number=10403, requested_backend="cado", threads=1,
                pretest_level=20, trial_bound=100, cado_parameter_size=None,
                polyselect_options={"deadline": 60},
            )
        with pytest.raises(ValueError, match="not a supported Msieve"):
            manager.create(
                expression="10403", number=10403, requested_backend="msieve_poly", threads=1,
                pretest_level=20, trial_bound=100, cado_parameter_size=None,
                polyselect_options={"nq": 256},
            )
        with pytest.raises(ValueError, match="selection stage must be one of"):
            manager.create(
                expression="10403", number=10403, requested_backend="msieve_poly", threads=1,
                pretest_level=20, trial_bound=100, cado_parameter_size=None,
                polyselect_stage="nonsense",
            )
    finally:
        manager.shutdown()


# --- The completeness gate --------------------------------------------------------------


def test_a_reporting_backend_completes_instead_of_failing_the_product_check(tmp_path, monkeypatch):
    """A measurement cannot multiply to the input, and must not be judged as if it could.

    `tune` always ended as failed with "The returned factors do not multiply to the
    input", however well it ran, because the completeness gate was applied to a job that
    has no factor multiset at all.
    """

    manager = _manager(tmp_path, monkeypatch)
    monkeypatch.setattr(
        manager, "_run_tune",
        lambda job: [{"value": "95", "digits": 0, "status": "measurement",
                      "engine": "YAFU tune (stub)"}],
    )
    try:
        created = manager.create(
            expression="10403", number=10403, requested_backend="tune", threads=1,
            pretest_level=20, trial_bound=100, cado_parameter_size=None,
        )
        manager._futures[created["id"]].result(timeout=60)
        row = manager.database.get_job(created["id"])
    finally:
        manager.shutdown()
    assert row["status"] == "completed"
    assert row["phase"] == "Complete"
    assert row["error"] is None


def test_a_factoring_backend_still_has_to_reconstruct_the_input(tmp_path, monkeypatch):
    """The gate must stay strict everywhere it applies."""

    manager = _manager(tmp_path, monkeypatch)
    # YAFU reporting a factor that does not divide 10403.
    _capture(manager, monkeypatch, "***factors found***\n\nP2 = 97\n")
    try:
        created = manager.create(
            expression="10403", number=10403, requested_backend="yafu", threads=1,
            pretest_level=20, trial_bound=100, cado_parameter_size=None,
        )
        manager._futures[created["id"]].result(timeout=60)
        row = manager.database.get_job(created["id"])
    finally:
        manager.shutdown()
    assert row["status"] == "failed"


def test_the_report_states_a_result_rather_than_a_false_equation(tmp_path, monkeypatch):
    """"N = degree 4, skew ..." would be a false statement about the input."""

    manager = _manager(tmp_path, monkeypatch)
    _capture(manager, monkeypatch, MSIEVE_OUTPUT)
    try:
        created = manager.create(
            expression="10403", number=10403, requested_backend="msieve_poly", threads=1,
            pretest_level=20, trial_bound=100, cado_parameter_size=None,
        )
        manager._futures[created["id"]].result(timeout=60)
    finally:
        manager.shutdown()
    report = (tmp_path / "output" / f"factorization-{created['id'][:12]}.txt").read_text(
        encoding="utf-8"
    )
    assert "Report for 10403" in report
    assert "10403 = degree" not in report
    assert "Result:" in report
    # The polynomial is written in Msieve's own field order, ready to paste.
    assert "SKEW 1049584.90" in report
    assert "R0 -6985661004471969578205" in report
    assert "A4 1260" in report
