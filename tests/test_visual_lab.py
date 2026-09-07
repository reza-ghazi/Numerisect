"""Known-answer, validation, and API tests for the visualization workbench.

Every mathematical assertion here is a published or hand-checkable value; the
numbers are produced by PARI/GP (``numerisect/visual_lab.gp``) or primesieve,
never by Python.
"""

import pytest
from fastapi.testclient import TestClient

from numerisect import outputs
from numerisect.main import app
from numerisect.primes import PrimeEngineError
from numerisect.visual_lab import (
    COMPLEXITY_REFERENCE,
    complexity_dashboard,
    eisenstein_lattice,
    gap_timeline,
    modular_wheel,
    prime_race,
    residue_heatmap,
    sieve_trace,
    spiral_primes,
)


def local_client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    token = client.get("/api/session").json()["request_token"]
    client.headers["X-Numerisect-Token"] = token
    return client


# --- spirals (roadmap 117, 118, 119) ---------------------------------------


def test_spiral_lists_the_nine_primes_below_25():
    # 2, 3, 5, 7, 11, 13, 17, 19, 23 are the nine primes below 25.
    result = spiral_primes(1, 25)
    assert result["prime_count"] == 9
    assert result["primes"] == ["2", "3", "5", "7", "11", "13", "17", "19", "23"]
    assert result["highlight_count"] == 0
    assert result["layout"] == "ulam"


@pytest.mark.parametrize("layout", ["ulam", "sacks", "polar"])
def test_every_spiral_layout_reports_the_same_prime_count(layout):
    # pi(1000) = 168 (Gauss's table; A000720), independent of how it is drawn.
    result = spiral_primes(1, 1000, layout=layout)
    assert result["prime_count"] == 168
    assert result["layout"] == layout


def test_spiral_highlights_the_euler_polynomial_family():
    # k^2 + k + 41 is prime for k = 0..39 (Euler 1772); the first four values
    # are 41, 43, 47, 53.
    result = spiral_primes(1, 60, highlight="polynomial", a=1, b=1, c=41)
    assert result["engine"] == "PARI/GP"
    assert result["highlighted"][:4] == ["41", "43", "47", "53"]
    assert result["highlight_count"] == 4


def test_spiral_highlights_a_residue_class():
    # 87 of the 168 primes below 1000 are congruent to 3 modulo 4.
    result = spiral_primes(1, 1000, highlight="residue", modulus=4, residue=3)
    assert result["prime_count"] == 168
    assert result["highlight_count"] == 87
    assert all(int(value) % 4 == 3 for value in result["highlighted"])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start": 0, "count": 10},
        {"start": 1, "count": 0},
        {"start": 1, "count": 2_000_000},
        {"start": 1, "count": 10, "layout": "hexagon"},
        {"start": 1, "count": 10, "highlight": "square"},
        {"start": 1, "count": 10, "highlight": "residue", "modulus": 1},
        {"start": 1, "count": 10, "highlight": "residue", "modulus": 4, "residue": 4},
        {"start": 1, "count": 10, "highlight": "polynomial", "a": 10**7},
        {"start": 1, "count": 10, "timeout": 0},
    ],
)
def test_spiral_rejects_invalid_input(kwargs):
    with pytest.raises(ValueError):
        spiral_primes(**kwargs)


# --- Eisenstein lattice (roadmap 121) --------------------------------------


def test_eisenstein_lattice_separates_split_inert_and_ramified_primes():
    result = eisenstein_lattice(20, 500)
    points = {(point["a"], point["b"]): point for point in result["points"]}
    # 1 - omega has norm 3 and is the ramified prime of Z[omega].
    assert points[(1, -1)]["norm"] == 3
    assert points[(1, -1)]["kind"] == 3
    # 2 is inert because 2 = 2 (mod 3); its norm 4 is not a rational prime.
    assert points[(2, 0)]["norm"] == 4
    assert points[(2, 0)]["kind"] == 2
    # 3 + omega... the split primes have prime norm, e.g. norm 7 = 1 (mod 3).
    assert points[(3, 1)]["norm"] == 7
    assert points[(3, 1)]["kind"] == 1
    assert result["truncated"] is False
    assert all(point["norm"] <= 20 for point in result["points"])


def test_eisenstein_lattice_truncates_at_the_requested_limit():
    result = eisenstein_lattice(200, 5)
    assert result["count"] == 5
    assert result["truncated"] is True


@pytest.mark.parametrize("kwargs", [
    {"norm_bound": 1},
    {"norm_bound": 300_000},
    {"norm_bound": 20, "limit": 0},
    {"norm_bound": 20, "limit": 10, "timeout": 0},
])
def test_eisenstein_lattice_rejects_invalid_input(kwargs):
    with pytest.raises(ValueError):
        eisenstein_lattice(**kwargs)


# --- modular wheel with an arbitrary base (roadmap 122) --------------------


def test_modular_wheel_reports_spokes_totient_and_rings():
    result = modular_wheel(6, 10, 8)
    # 11, 13, 17 are the primes in [10, 17]; phi(6) = 2 (spokes 1 and 5).
    assert result["prime_count"] == 3
    assert result["totient"] == 2
    assert result["ring_count"] == 2
    spokes = {spoke["residue"]: spoke for spoke in result["spokes"]}
    assert spokes[5]["prime_count"] == 2 and spokes[5]["coprime"] is True
    assert spokes[1]["prime_count"] == 1 and spokes[1]["coprime"] is True
    assert spokes[0]["prime_count"] == 0 and spokes[0]["coprime"] is False
    assert result["cells"][1] == {
        "value": 11, "residue": 5, "ring": 0, "is_prime": True, "coprime": True
    }


def test_modular_wheel_accepts_a_base_above_the_prime_structures_cap():
    # The Prime Structures wheel caps the base at 360; this one accepts 2,310.
    result = modular_wheel(2310, 0, 100)
    assert result["modulus"] == 2310
    assert result["totient"] == 480  # phi(2*3*5*7*11) = 1*2*4*6*10
    assert result["prime_count"] == 25  # pi(99) = 25


@pytest.mark.parametrize("kwargs", [
    {"modulus": 1},
    {"modulus": 20_000},
    {"modulus": 30, "start": -1},
    {"modulus": 30, "count": 0},
    {"modulus": 30, "count": 300_000},
    {"modulus": 30, "count": 10, "timeout": 0},
])
def test_modular_wheel_rejects_invalid_input(kwargs):
    with pytest.raises(ValueError):
        modular_wheel(**kwargs)


# --- residue-class heatmap (roadmap 123) -----------------------------------


def test_residue_heatmap_counts_match_the_prime_count():
    result = residue_heatmap(1, 100, 4, 2)
    # pi(100) = 25; below 100 there are 11 primes = 1 (mod 4), 13 primes
    # = 3 (mod 4), plus 2 itself (residue 2) and no prime = 0 (mod 4).
    assert result["prime_count"] == 25
    totals = {item["residue"]: item["total"] for item in result["residues"]}
    assert totals == {0: 0, 1: 11, 2: 1, 3: 13}
    assert sum(totals.values()) == 25
    coprime = {item["residue"]: item["coprime"] for item in result["residues"]}
    assert coprime == {0: False, 1: True, 2: False, 3: True}
    assert result["bin_count"] == 2
    assert sum(sum(row["counts"]) for row in result["bins"]) == 25
    assert result["max_cell"] == max(max(row["counts"]) for row in result["bins"])


@pytest.mark.parametrize("kwargs", [
    {"start": 0, "end": 100},
    {"start": 100, "end": 1},
    {"start": 1, "end": 20_000_000},
    {"start": 1, "end": 100, "modulus": 1},
    {"start": 1, "end": 100, "modulus": 400},
    {"start": 1, "end": 100, "bins": 0},
    {"start": 1, "end": 100, "bins": 500},
    {"start": 1, "end": 100, "timeout": 0},
])
def test_residue_heatmap_rejects_invalid_input(kwargs):
    with pytest.raises(ValueError):
        residue_heatmap(**kwargs)


# --- gap timeline and record gaps (roadmap 124) ----------------------------


def test_gap_timeline_finds_the_record_gaps_below_100():
    result = gap_timeline(1, 100, 500)
    # The maximal gaps starting from 2 are 1 (2->3), 2 (3->5), 4 (7->11),
    # 6 (23->29) and 8 (89->97): OEIS A002386 / A005250.
    assert [(record["from"], record["gap"]) for record in result["records"]] == [
        ("2", 1), ("3", 2), ("7", 4), ("23", 6), ("89", 8)
    ]
    assert result["max_gap"] == 8
    assert result["max_gap_at"] == "89"
    assert result["gap_count"] == 24  # pi(100) - 1 = 25 - 1 consecutive pairs
    assert result["first_prime"] == "2" and result["last_prime"] == "97"
    assert result["truncated"] is False
    assert float(result["records"][-1]["merit"]) == pytest.approx(8 / 4.4886, rel=1e-3)


def test_gap_timeline_truncates_the_timeline_but_never_the_records():
    result = gap_timeline(1, 100, 3)
    assert result["shown"] == 3
    assert result["truncated"] is True
    assert len(result["records"]) == 5


@pytest.mark.parametrize("kwargs", [
    {"start": 0, "end": 100},
    {"start": 100, "end": 1},
    {"start": 1, "end": 20_000_000},
    {"start": 1, "end": 100, "limit": 0},
    {"start": 1, "end": 100, "timeout": 0},
])
def test_gap_timeline_rejects_invalid_input(kwargs):
    with pytest.raises(ValueError):
        gap_timeline(**kwargs)


# --- prime race (roadmap 125) ----------------------------------------------


def test_prime_race_modulo_four_reproduces_the_chebyshev_bias():
    result = prime_race(1, 1000, 4, 5, 100)
    # Below 1000 there are 80 primes = 1 (mod 4) and 87 = 3 (mod 4); the
    # class 3 leads, which is the classic Chebyshev bias.
    assert result["classes"] == [1, 3]
    assert result["final"] == [{"residue": 1, "count": 80}, {"residue": 3, "count": 87}]
    assert result["leader"] == 3
    assert result["prime_count"] == 167  # 168 primes below 1000, minus 2 itself
    assert len(result["checkpoints"]) == 5
    assert result["checkpoints"][-1]["counts"] == [80, 87]
    # The only lead change in [1, 1000] happens at 3, the first prime placed.
    assert result["events"] == [{"prime": "3", "leader": 3}]
    assert result["event_count"] == 1
    assert result["event_truncated"] is False


def test_prime_race_modulo_three_also_favours_the_non_residue_class():
    result = prime_race(1, 1000, 3, 4, 100)
    assert result["classes"] == [1, 2]
    counts = {item["residue"]: item["count"] for item in result["final"]}
    assert counts == {1: 80, 2: 87}
    assert result["leader"] == 2


@pytest.mark.parametrize("kwargs", [
    {"start": 0, "end": 100},
    {"start": 100, "end": 1},
    {"start": 1, "end": 20_000_000},
    {"start": 1, "end": 100, "modulus": 1},
    {"start": 1, "end": 100, "modulus": 400},
    {"start": 1, "end": 100, "checkpoints": 0},
    {"start": 1, "end": 100, "checkpoints": 5000},
    {"start": 1, "end": 100, "event_limit": 0},
    {"start": 1, "end": 100, "timeout": 0},
])
def test_prime_race_rejects_invalid_input(kwargs):
    with pytest.raises(ValueError):
        prime_race(**kwargs)


def test_prime_race_reports_a_timeout_rather_than_an_empty_success(monkeypatch):
    # The contract is that an engine timeout becomes an error, never a partial or
    # empty success. Asserting that by racing the wall clock is unreliable on
    # varying hardware, so the timeout is injected at the subprocess boundary and
    # the boundary's handling of it is what gets checked.
    from numerisect import primes as primes_module

    def timing_out(*args, **kwargs):
        raise primes_module.PrimeEngineError(
            "PARI/GP exceeded the 1-second operation limit"
        )

    from numerisect import visual_lab

    monkeypatch.setattr(visual_lab, "_run_gp", timing_out)
    with pytest.raises(PrimeEngineError) as failure:
        prime_race(1, 10_000_000, 360, 1000, 100_000, timeout=1)
    message = str(failure.value)
    assert "1-second" in message or "timeout" in message.lower()
    # It must not have degraded into an empty result.
    assert "0 results" not in message


# --- sieve traces (roadmap 126) --------------------------------------------


def test_eratosthenes_trace_strikes_the_multiples_of_two_first():
    result = sieve_trace("eratosthenes", 30)
    # Step kind 1 selects a prime, kind 2 strikes a multiple: the sieve picks
    # 2 and then strikes 4, 6, 8, ... before touching any other prime.
    assert result["steps"][0] == [1, 2, 0, 0, 0]
    assert [step[1] for step in result["steps"][1:4]] == [4, 6, 8]
    assert all(step[2] == 2 for step in result["steps"][1:4])
    assert result["primes"] == [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
    assert result["verified"] is True
    assert result["step_count"] == len(result["steps"])


@pytest.mark.parametrize("kind", ["eratosthenes", "segmented", "sundaram", "atkin"])
def test_every_sieve_trace_reproduces_pi_of_1000(kind):
    # pi(1000) = 168; the GP program refuses to report a trace whose survivors
    # disagree with PARI's own prime table.
    result = sieve_trace(kind, 1000)
    assert result["prime_count"] == 168
    assert result["primes"][:5] == [2, 3, 5, 7, 11]
    assert result["primes"][-1] == 997
    assert result["verified"] is True
    assert set(step[0] for step in result["steps"]) <= set(range(1, 10))


def test_segmented_sieve_records_its_segment_boundaries():
    result = sieve_trace("segmented", 100, 10)
    assert result["segment_size"] == 10
    boundaries = [(step[1], step[2]) for step in result["steps"] if step[0] == 9]
    assert boundaries[0] == (11, 20)
    assert boundaries[-1][1] == 100


def test_sundaram_trace_uses_its_own_step_code():
    result = sieve_trace("sundaram", 100)
    # Kind 4 is the Sundaram strike of 2m+1 for m = i + j + 2ij.
    strikes = [step for step in result["steps"] if step[0] == 4]
    assert strikes
    for _, value, i, j, _ in strikes:
        assert value == 2 * (i + j + 2 * i * j) + 1


@pytest.mark.parametrize("kwargs", [
    {"kind": "wheel", "n": 100},
    {"kind": "eratosthenes", "n": 1},
    {"kind": "eratosthenes", "n": 10_000},
    {"kind": "eratosthenes", "n": 100, "segment_size": 0},
    {"kind": "eratosthenes", "n": 100, "segment_size": 200},
    {"kind": "eratosthenes", "n": 100, "timeout": 0},
])
def test_sieve_trace_rejects_invalid_input(kwargs):
    with pytest.raises(ValueError):
        sieve_trace(**kwargs)


# --- complexity dashboard (roadmap 128) ------------------------------------


def test_complexity_reference_table_cites_every_required_algorithm():
    names = " | ".join(row["algorithm"] for row in COMPLEXITY_REFERENCE)
    for algorithm in [
        "Trial division", "Pollard rho", "Pollard p", "Elliptic-curve method",
        "quadratic sieve", "General number field sieve", "Special number field sieve",
        "AKS", "ECPP", "APR-CL", "Eratosthenes", "Segmented", "Sundaram", "Atkin",
    ]:
        assert algorithm in names
    for row in COMPLEXITY_REFERENCE:
        assert row["source"] and row["time"] and row["memory"] and row["category"]


def test_complexity_dashboard_groups_measured_jobs_by_engine_and_size():
    jobs = [
        {"status": "completed", "digits": 45, "selected_backend": "yafu",
         "started_at": "2026-01-01T00:00:00", "finished_at": "2026-01-01T00:00:10"},
        {"status": "completed", "digits": 49, "selected_backend": "yafu",
         "started_at": "2026-01-01T00:00:00", "finished_at": "2026-01-01T00:00:20"},
        {"status": "completed", "digits": 95, "selected_backend": "cado",
         "started_at": "2026-01-01T00:00:00", "finished_at": "2026-01-01T00:01:00"},
        {"status": "failed", "digits": 45, "selected_backend": "yafu",
         "started_at": "2026-01-01T00:00:00", "finished_at": "2026-01-01T00:00:01"},
        {"status": "completed", "digits": 45, "selected_backend": "yafu",
         "started_at": None, "finished_at": None},
    ]
    result = complexity_dashboard(jobs)
    assert result["measured_jobs"] == 3
    groups = {(group["engine"], group["digits"]): group for group in result["groups"]}
    assert groups[("yafu", "41–50")]["runs"] == 2
    assert groups[("yafu", "41–50")]["median_seconds"] == 15.0
    assert groups[("yafu", "41–50")]["min_seconds"] == 10.0
    assert groups[("cado", "91–100")]["median_seconds"] == 60.0
    assert len(result["reference"]) == len(COMPLEXITY_REFERENCE)


def test_complexity_dashboard_without_history_still_returns_the_reference():
    result = complexity_dashboard([])
    assert result["groups"] == []
    assert result["measured_jobs"] == 0
    assert len(result["reference"]) == len(COMPLEXITY_REFERENCE)


# --- HTTP API ---------------------------------------------------------------


@pytest.mark.parametrize("path,payload,check", [
    ("/api/visual/spiral", {"start": "1", "count": 25},
     lambda body: body["prime_count"] == 9 and body["layout"] == "ulam"),
    ("/api/visual/eisenstein-lattice", {"norm_bound": 20, "limit": 500},
     lambda body: body["count"] == 48),
    ("/api/visual/modular-wheel", {"modulus": 6, "start": 10, "count": 8},
     lambda body: body["prime_count"] == 3 and body["totient"] == 2),
    ("/api/visual/residue-heatmap", {"start": "1", "end": "100", "modulus": 4, "bins": 2},
     lambda body: body["prime_count"] == 25),
    ("/api/visual/gap-timeline", {"start": "1", "end": "100", "limit": 500},
     lambda body: body["max_gap"] == 8 and body["max_gap_at"] == "89"),
    ("/api/visual/prime-race", {"start": "1", "end": "1000", "modulus": 4, "checkpoints": 5},
     lambda body: body["leader"] == 3),
    ("/api/visual/sieve-trace", {"kind": "eratosthenes", "n": 100},
     lambda body: body["prime_count"] == 25 and body["verified"] is True),
    ("/api/visual/complexity", {"job_limit": 10},
     lambda body: len(body["reference"]) == len(COMPLEXITY_REFERENCE)),
])
def test_visual_routes_save_a_report(path, payload, check, tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    client = local_client()
    response = client.post(path, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert check(body)
    assert body["note"]
    report = (tmp_path / body["output_file"]).read_text()
    assert body["note"] in report
    download = client.get(f'/api/outputs/{body["output_file"]}')
    assert download.status_code == 200
    assert download.text == report


@pytest.mark.parametrize("path,payload", [
    ("/api/visual/spiral", {"start": "1", "count": 0}),
    ("/api/visual/spiral", {"start": "0", "count": 10}),
    ("/api/visual/spiral", {"start": "not an integer", "count": 10}),
    ("/api/visual/spiral", {"start": "1", "count": 10, "layout": "hexagon"}),
    ("/api/visual/eisenstein-lattice", {"norm_bound": 1}),
    ("/api/visual/modular-wheel", {"modulus": 30, "count": 0}),
    ("/api/visual/modular-wheel", {"modulus": 20000, "count": 10}),
    ("/api/visual/residue-heatmap", {"start": "100", "end": "1"}),
    ("/api/visual/gap-timeline", {"start": "100", "end": "1"}),
    ("/api/visual/prime-race", {"start": "1", "end": "100", "modulus": 1}),
    ("/api/visual/sieve-trace", {"kind": "eratosthenes", "n": 100, "segment_size": 200}),
    ("/api/visual/sieve-trace", {"kind": "wheel", "n": 100}),
])
def test_visual_routes_reject_invalid_requests_without_saving(path, payload, tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    response = local_client().post(path, json=payload)
    assert response.status_code == 422
    assert list(tmp_path.iterdir()) == []


# --- browser wiring ---------------------------------------------------------


def test_every_visual_form_is_registered_and_has_a_canvas():
    from pathlib import Path

    root = Path(__file__).parents[1]
    index = (root / "numerisect" / "static" / "index.html").read_text(encoding="utf-8")
    app_js = (root / "numerisect" / "static" / "app.js").read_text(encoding="utf-8")
    forms = [
        "visual-spiral-form", "visual-eisenstein-form", "visual-wheel-form",
        "visual-heatmap-form", "visual-gap-timeline-form", "visual-prime-race-form",
        "visual-sieve-form", "visual-complexity-form",
    ]
    catalogue = app_js.split("const primeSections = {", 1)[1].split("const primeTools", 1)[0]
    assert "label: 'Visualization & education'" in catalogue
    for form in forms:
        assert f'<form id="{form}"' in index
        assert f"'{form}'" in catalogue
        markup = index.split(f'<form id="{form}"', 1)[1].split("</form>", 1)[0]
        assert 'class="math-canvas' in markup or 'visual-canvas' in markup
        assert "<canvas" in markup
        assert f"$('#{form}').addEventListener('submit'" in app_js


# --- native computation policy ----------------------------------------------


def test_engine_supplies_every_derived_quantity_the_browser_shows():
    """The browser must never recompute a count, a total, or an axis maximum."""
    lattice = eisenstein_lattice(20, 500)
    assert lattice["kind_counts"] == {"1": 36, "2": 6, "3": 6}
    assert sum(lattice["kind_counts"].values()) == lattice["count"]

    wheel = modular_wheel(30, 0, 300)
    assert wheel["spokes_with_primes"] == len(
        [spoke for spoke in wheel["spokes"] if spoke["prime_count"]]
    )

    timeline = gap_timeline(1, 1000, 5000)
    assert timeline["record_count"] == len(timeline["records"])
    assert timeline["max_gap"] == max(item["gap"] for item in timeline["gaps"])

    race = prime_race(1, 1000, 4, 5, 100)
    assert race["max_count"] == max(item["count"] for item in race["final"])


def test_segmented_sieve_block_size_is_derived_by_the_engine():
    # sqrtint(100) + 1 = 11; Python must not compute the default itself.
    assert sieve_trace("segmented", 100)["segment_size"] == 11
    assert sieve_trace("segmented", 1000)["segment_size"] == 32  # sqrtint(1000) = 31
    assert sieve_trace("segmented", 100, 10)["segment_size"] == 10


def test_only_the_sieve_animation_runs_a_hand_written_enumeration():
    """117-125 must use library routines; 126 is the documented exception."""
    from pathlib import Path

    program = (Path(__file__).parents[1] / "numerisect" / "visual_lab.gp").read_text(
        encoding="utf-8"
    )
    library_backed, traces = program.split("\\\\ Sieve step traces.", 1)
    # No tool outside the sieve traces builds its own strike table.
    assert "vector(n)" not in library_backed
    for routine in ["vl_spiral", "vl_residue_heatmap", "vl_gap_timeline", "vl_prime_race"]:
        body = library_backed.split(f"{routine}(", 1)[1]
        assert "forprime(" in body and "isprime(" in body
    assert "isprime(norm)" in library_backed  # Eisenstein lattice
    assert "eulerphi(modulus)" in traces or "eulerphi(modulus)" in library_backed
    # The exception verifies itself against PARI's own table.
    assert "expected = primes(primepi(n))" in traces
    assert "The sieve trace disagrees with PARI's prime table" in traces
