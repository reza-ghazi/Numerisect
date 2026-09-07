from conftest import requires
import pytest
from fastapi.testclient import TestClient

from numerisect import distribution_lab, outputs
from numerisect.distribution_lab import (
    approximation_error,
    bateman_horn,
    density_surface,
    maximal_gap_search,
    nth_prime_bounds,
    pnt_convergence,
    prime_race,
    progression_deviation,
    short_interval_matrix,
    singular_series,
    tuple_prediction,
)
from numerisect.main import app
from numerisect.primes import PrimeEngineError


def local_client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    token = client.get("/api/session").json()["request_token"]
    client.headers["X-Numerisect-Token"] = token
    return client


def test_module_names_the_engine_behind_every_feature():
    docstring = distribution_lab.__doc__ or ""
    for engine in ("primecount", "primesieve", "PARI/GP", "eint1", "polrootsmod", "intnum"):
        assert engine in docstring


# ---------------------------------------------------------------- item 76 ---

@requires("primecount")
def test_approximation_error_reproduces_known_prime_counts():
    result = approximation_error(3, 6, 4, 1)
    # pi(10^3) = 168, pi(10^6) = 78498; li(10^6) = 78627.5491594621819...
    assert [row[0] for row in result["rows"]] == ["1000", "10000", "100000", "1000000"]
    assert [row[1] for row in result["rows"]] == ["168", "1229", "9592", "78498"]
    assert result["rows"][-1][3].startswith("78627.5491594621")
    assert result["metrics"]["Exact π at the largest endpoint"] == "78498"
    assert result["chart"] == "approximation-error"


@pytest.mark.parametrize("arguments", [
    (6, 3, 4, 1),      # descending grid
    (3, 6, 1, 1),      # too few points
    (0, 6, 4, 1),      # exponent below 1
    (3, 6, 4, 0),      # thread count below 1
])
def test_approximation_error_rejects_invalid_grids(arguments):
    with pytest.raises(ValueError):
        approximation_error(*arguments)


# ---------------------------------------------------------------- item 82 ---

def test_pnt_convergence_ratios_approach_one():
    result = pnt_convergence(3, 6, 4, 1)
    # pi(10^6)/li(10^6) = 78498 / 78627.549159... = 0.99835...
    assert result["rows"][-1][3].startswith("0.99835")
    # pi(x)/(x/log x) decreases towards 1 across the grid.
    assert 1 < float(result["rows"][-1][2]) < float(result["rows"][0][2])
    assert result["metrics"]["Sign changes of π(x) − li(x) on this grid"] == "0"
    assert result["sign_changes"] == 0


def test_pnt_convergence_rejects_invalid_grid():
    with pytest.raises(ValueError):
        pnt_convergence(3, 3, 4, 1)


# ---------------------------------------------------------------- item 81 ---

def test_nth_prime_bounds_hold_against_exact_values():
    result = nth_prime_bounds(1, 6, 6, 1)
    # p_10 = 29, p_100 = 541, p_1000 = 7919, p_10^4 = 104729,
    # p_10^5 = 1299709, p_10^6 = 15485863
    assert result["metrics"]["Exact p_n at the largest index"] == "15485863"
    assert result["violations"] == 0
    exact = {row[0]: row[1] for row in result["rows"]}
    assert exact == {
        "10": "29", "100": "541", "1000": "7919",
        "10000": "104729", "100000": "1299709", "1000000": "15485863",
    }
    rosser = [row for row in result["rows"] if row[0] == "1000000" and "Rosser 1939" in row[2]]
    assert len(rosser) == 1 and rosser[0][6] == "holds"
    outside = [row for row in result["rows"] if row[6] == "outside the published validity range"]
    # Dusart 2010's upper bound is only stated for n >= 688383.
    assert any("Dusart 2010 Prop 5.15 upper" in row[2] for row in outside)


def test_nth_prime_bounds_reject_invalid_grid():
    with pytest.raises(ValueError):
        nth_prime_bounds(9, 1, 4, 1)


# ---------------------------------------------------------------- item 83 ---

def test_prime_race_reproduces_the_chebyshev_bias():
    result = prime_race("4", "1000000", 4)
    # pi(10^6; 4, 1) = 39175 and pi(10^6; 4, 3) = 39322: the 4k+3 class leads.
    final = [row for row in result["rows"] if row[0] == "1000000"]
    assert [row[1:3] for row in final] == [["1", "39175"], ["3", "39322"]]
    assert result["metrics"]["Leader at x"] == "3"
    assert result["metrics"]["Reduced residue classes φ(q)"] == "2"


@pytest.mark.parametrize("arguments", [
    ("2", "1000000", 4),        # modulus below 3
    ("4", "5", 4),              # endpoint below 10
    ("4", "1000000", 0),        # no checkpoints
    ("four", "1000000", 4),     # not a decimal integer
])
def test_prime_race_rejects_invalid_input(arguments):
    with pytest.raises(ValueError):
        prime_race(*arguments)


def test_prime_race_class_cap_is_inconclusive_not_empty():
    # phi(211) = 210 exceeds the documented 64-class cap: the engine must refuse.
    with pytest.raises(PrimeEngineError):
        prime_race("211", "100000", 2)


def test_prime_race_timeout_is_reported_as_an_engine_error():
    with pytest.raises(PrimeEngineError):
        prime_race("4", "10000000000", 64, timeout=1)


# ---------------------------------------------------------------- item 84 ---

def test_progression_deviation_matches_known_counts():
    result = progression_deviation("4", "1000000")
    assert [row[:2] for row in result["rows"]] == [["1", "39175"], ["3", "39322"]]
    assert result["metrics"]["li(x)"].startswith("78627.5491594621")
    assert result["metrics"]["Primes dividing q (excluded)"] == "1"


@pytest.mark.parametrize("arguments", [("1", "1000"), ("12", "5"), ("12", "x")])
def test_progression_deviation_rejects_invalid_input(arguments):
    with pytest.raises(ValueError):
        progression_deviation(*arguments)


# ---------------------------------------------------------------- item 85 ---

def test_singular_series_reproduces_the_twin_prime_constant():
    result = singular_series([0, 2], 1_000_000)
    # The twin-prime constant is C2 = 0.6601618158..., so S = 2*C2 = 1.3203236316...
    assert result["admissible"] is True
    assert result["metrics"]["Singular series 𝔖 (estimate)"].startswith("1.3203237")
    low = float(result["metrics"]["𝔖 lower bound"])
    high = float(result["metrics"]["𝔖 upper bound"])
    assert low < 1.3203236316 < high
    assert "ESTIMATE" in result["note"]


def test_singular_series_rejects_an_inadmissible_pattern():
    result = singular_series([0, 2, 4], 1000)
    assert result["admissible"] is False
    assert result["obstructions"] == [["3", "3"]]
    assert result["metrics"]["Singular series 𝔖 (estimate)"] == "0"


@pytest.mark.parametrize("arguments", [
    ([2, 4], 1000),         # offsets do not start at 0
    ([0], 1000),            # fewer than two offsets
    ([0, 2], 10),           # cutoff below the documented minimum
    ([0, 0], 1000),         # repeated offset
])
def test_singular_series_rejects_invalid_patterns(arguments):
    with pytest.raises(ValueError):
        singular_series(*arguments)


# ---------------------------------------------------------------- item 86 ---

def test_twin_primes_are_counted_by_primesieve():
    result = tuple_prediction([0, 2], "2", "1000000", 1_000_000)
    # There are 8169 twin-prime pairs entirely below 10^6.
    assert result["observed"] == 8169
    assert result["counted_by"] == "primesieve --count"
    assert 0.9 < float(result["metrics"]["Observed / predicted"]) < 1.1


def test_custom_constellations_are_counted_by_pari():
    result = tuple_prediction([0, 2, 6], "2", "1000000", 100_000)
    # 1393 prime triplets of the form (p, p+2, p+6) lie below 10^6.
    assert result["observed"] == 1393
    assert result["counted_by"] == "PARI/GP forprime window"


@pytest.mark.parametrize("arguments", [
    ([0, 2], "2", "1", 1000),                     # empty range
    ([0, 2], "2", "1000000000000", 1000),         # range above the documented cap
    ([0, 2], "1", "1000", 1000),                  # range starts below 2
])
def test_tuple_prediction_rejects_invalid_ranges(arguments):
    with pytest.raises(ValueError):
        tuple_prediction(*arguments)


# ---------------------------------------------------------------- item 87 ---

def test_bateman_horn_predicts_prime_values_of_n_squared_plus_one():
    result = bateman_horn([["1", "0", "1"]], "1", "100000", 100_000)
    # 6656 values of n <= 10^5 give a prime n^2 + 1; the Hardy-Littlewood
    # constant for n^2 + 1 is 1.3728134628...
    assert result["observed"] == 6656
    assert result["rows"] == [["1", "x^2 + 1", "2"]]
    assert result["metrics"]["Local product ∏(1 − ω(p)/p)/(1 − 1/p)^k (estimate)"].startswith("1.372")
    assert 0.9 < float(result["metrics"]["Observed / predicted"]) < 1.1
    assert "ESTIMATE" in result["note"]


def test_bateman_horn_refuses_a_reducible_polynomial():
    with pytest.raises(PrimeEngineError):
        bateman_horn([["-1", "0", "1"]], "1", "1000", 1000)


@pytest.mark.parametrize("arguments", [
    ([["1", "0", "-1"]], "1", "1000", 1000),        # negative leading coefficient
    ([["1"]], "1", "1000", 1000),                   # fewer than two coefficients
    ([["1", "0", "1"]], "1", "10000000", 1000),     # span above the documented cap
    ([["1", "0", "1"]], "1", "1000", 2),            # cutoff below the minimum
])
def test_bateman_horn_rejects_invalid_input(arguments):
    with pytest.raises(ValueError):
        bateman_horn(*arguments)


# ------------------------------------------------------- items 88, 89, 90, 91 ---

def test_maximal_gap_search_matches_the_published_table():
    result = maximal_gap_search("2", "1000000", 0, 10_000_000)
    # The first maximal gaps are 1, 2, 4, 6, 8 (A005250) at 2, 3, 7, 23, 89 (A002386).
    assert [row[2] for row in result["rows"][:5]] == ["1", "2", "4", "6", "8"]
    assert [row[0] for row in result["rows"][:5]] == ["2", "3", "7", "23", "89"]
    assert result["mismatches"] == 0
    assert result["table_applicable"] is True
    assert result["complete"] is True
    assert all(row[2] == "confirmed" for row in result["table_rows"])
    # The record gap of 34 after 1327 has merit 34/log(1327) = 4.7283454...,
    # Cramer-Shanks ratio 34/log^2(1327) = 0.6575661..., and satisfies the
    # Firoozbakht-implied bound log^2 p - log p - 1.
    record = [row for row in result["rows"] if row[0] == "1327"][0]
    assert record[2] == "34"
    assert record[3].startswith("4.72834")
    assert record[4].startswith("0.6575661")
    assert record[5].startswith("0.5855864")
    assert record[7] == "holds"
    assert record[8] == "yes"


def test_maximal_gap_search_reports_the_scan_cap_as_incomplete():
    result = maximal_gap_search("2", "10000000", 0, 1000)
    assert result["truncated"] is True
    assert result["complete"] is False
    assert result["metrics"]["Completed"].startswith("no")
    assert result["metrics"]["Resume from"] == "7919"
    assert result["metrics"]["Largest gap found"] == "34"


def test_maximal_gap_search_skips_verification_outside_the_table_domain():
    result = maximal_gap_search("1000000", "1100000", 0, 1_000_000)
    assert result["table_applicable"] is False
    assert result["table_rows"] == []
    assert "skipped" in result["metrics"]["Published table verification"]


@pytest.mark.parametrize("arguments", [
    ("10", "2", 0, 1000),               # empty range
    ("1", "1000", 0, 1000),             # start below 2
    ("2", "1000", 0, 1),                # scan cap below the minimum
    ("2", "100000000000000", 0, 1000),  # range above the documented cap
])
def test_maximal_gap_search_rejects_invalid_input(arguments):
    with pytest.raises(ValueError):
        maximal_gap_search(*arguments)


def test_maximal_gap_search_timeout_is_an_engine_error():
    with pytest.raises(PrimeEngineError):
        maximal_gap_search("2", "100000000000", 0, 10_000_000_000, timeout=1)


# ---------------------------------------------------------------- item 92 ---

def test_short_interval_matrix_counts_every_requested_row():
    result = short_interval_matrix("9699690", "1000", 6, 1000)
    assert len(result["rows"]) == 6
    assert result["rows"][0][:3] == ["1000", "9699690001", "9699691000"]
    assert result["metrics"]["Rows"] == "6"
    assert float(result["metrics"]["Minimum ratio"]) <= float(result["metrics"]["Maximum ratio"])


@pytest.mark.parametrize("arguments", [
    ("1", "1000", 4, 1000),       # modulus below 2
    ("30", "0", 4, 1000),         # first row below 1
    ("30", "1000", 0, 1000),      # no rows
    ("30", "1000", 4, 1),         # row length below 2
])
def test_short_interval_matrix_rejects_invalid_input(arguments):
    with pytest.raises(ValueError):
        short_interval_matrix(*arguments)


# ---------------------------------------------------------------- item 93 ---

def test_density_surface_returns_a_complete_grid():
    result = density_surface("1000000", "1100000", 4, "12")
    assert result["classes"] == 4
    assert len(result["rows"]) == 16
    assert result["residues"] == ["1", "5", "7", "11"]
    assert len(result["block_rows"]) == 4
    assert result["metrics"]["Block width"] == "25000"


@pytest.mark.parametrize("arguments", [
    ("1000", "100", 4, "12"),          # empty range
    ("1", "1000", 4, "12"),            # start below 2
    ("1000", "2000", 0, "12"),         # no blocks
    ("1000", "2000", 4, "1"),          # modulus below 2
    ("1000", "20000000000", 4, "12"),  # span above the documented cap
])
def test_density_surface_rejects_invalid_input(arguments):
    with pytest.raises(ValueError):
        density_surface(*arguments)


# --------------------------------------------------------------------- API ---

@requires("primecount")
def test_distribution_routes_save_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    client = local_client()

    response = client.post("/api/distribution/approximation-error", json={
        "exponent_from": 3, "exponent_to": 6, "points": 4, "threads": 1,
    })
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["rows"][-1][1] == "78498"
    report = (tmp_path / payload["output_file"]).read_text(encoding="utf-8")
    assert "78498" in report and "primecount" in report
    assert client.get(f'/api/outputs/{payload["output_file"]}').text == report

    gaps = client.post("/api/distribution/maximal-gaps", json={
        "start": "2", "end": "1000000", "baseline": 0, "prime_cap": 10000000,
    })
    assert gaps.status_code == 200, gaps.text
    gap_payload = gaps.json()
    assert gap_payload["mismatches"] == 0
    gap_report = (tmp_path / gap_payload["output_file"]).read_text(encoding="utf-8")
    assert "A002386" in gap_report
    assert "Published maximal-gap table verification" in gap_report

    surface = client.post("/api/distribution/density-surface", json={
        "start": "1000000", "end": "1100000", "blocks": 4, "modulus": "12",
    })
    assert surface.status_code == 200, surface.text
    assert surface.json()["classes"] == 4
    assert len(list(tmp_path.iterdir())) == 3


@pytest.mark.parametrize("endpoint,payload", [
    ("approximation-error", {"exponent_from": 9, "exponent_to": 3}),
    ("pnt-convergence", {"exponent_from": 3, "exponent_to": 3}),
    ("nth-prime-bounds", {"exponent_from": 9, "exponent_to": 2}),
    ("prime-race", {"modulus": "2", "endpoint": "1000"}),
    ("progressions", {"modulus": "12", "endpoint": "5"}),
    ("singular-series", {"offsets": [1, 3]}),
    ("tuple-prediction", {"offsets": [0, 2], "start": "2", "end": "2"}),
    ("bateman-horn", {"polynomials": [["1", "0", "-1"]]}),
    ("maximal-gaps", {"start": "10", "end": "2"}),
    ("short-interval", {"modulus": "1", "first_row": "10"}),
    ("density-surface", {"start": "1000", "end": "100"}),
])
def test_distribution_routes_reject_invalid_input(endpoint, payload, tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    response = local_client().post(f"/api/distribution/{endpoint}", json=payload)
    assert response.status_code == 422, response.text
    assert list(tmp_path.iterdir()) == []
