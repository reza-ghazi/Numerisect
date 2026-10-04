"""The Mertens function and the Brun-type reciprocal sums.

Both helpers are checked against PARI/GP, asked directly, and against published values.
The Mertens helper carries two independent algorithms, so they are also run against each
other; that cross-check is part of the product, not only of this file.
"""

import subprocess

import pytest
from fastapi.testclient import TestClient

from numerisect import outputs
from numerisect.analytic_sums import (
    BRUN_PATTERNS,
    brun_sum,
    mertens_sign_analysis,
    mertens_value,
)
from numerisect.main import app
from numerisect.primes import PrimeEngineError, _run_gp


@pytest.fixture()
def local_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    client = TestClient(app, base_url="http://127.0.0.1")
    client.headers["X-Numerisect-Token"] = client.get("/api/session").json()["request_token"]
    return client


@pytest.mark.parametrize("x,expected", [
    # M(10^k) for k = 1..6, confirmed below against PARI/GP in the same run.
    (10, -1),
    (100, 1),
    (1000, 2),
    (10**4, -23),
    (10**5, -48),
    (10**6, 212),
])
def test_mertens_matches_pari(x, expected):
    """PARI/GP has no M(x) routine, but it does have moebius; it is the reference."""

    assert int(mertens_value(x)["mertens"]) == expected
    lines = _run_gp(f"print(\"M:\", sum(n=1,{x},moebius(n))); print(\"DONE:1\");")
    reference = next(int(line[2:]) for line in lines if line.startswith("M:"))
    assert reference == expected


@pytest.mark.parametrize("x,expected", [
    # Published values of M(10^k); the two algorithms also agree with each other here.
    (10**7, 1037),
    (10**8, 1928),
    (10**9, -222),
    (10**12, 62366),
])
def test_mertens_matches_published_values_at_scale(x, expected):
    result = mertens_value(x)
    assert int(result["mertens"]) == expected
    assert result["method"] == "hyperbola"


def test_the_two_algorithms_check_each_other():
    """The hyperbola identity and the segmented sieve share no path beyond the sieve."""

    result = mertens_value(10**8, cross_check=True)
    assert result["cross_checked"] is True
    assert int(result["mertens"]) == 1928
    assert "segmented" in result["cross_check_method"]


def test_a_disagreement_between_the_algorithms_reports_no_value(monkeypatch):
    """If the two ever disagreed, reporting either number would be the wrong answer."""

    from numerisect import analytic_sums

    real = analytic_sums._run
    calls = {"n": 0}

    def fake(command, timeout):
        lines = real(command, timeout)
        calls["n"] += 1
        if calls["n"] == 2:                       # the cross-check run
            return [line.replace("MERTENS:212", "MERTENS:999") for line in lines]
        return lines

    monkeypatch.setattr(analytic_sums, "_run", fake)
    with pytest.raises(PrimeEngineError, match="disagree"):
        mertens_value(10**6, cross_check=True)


def test_mertens_sign_analysis_matches_pari_on_every_statistic():
    """Sign changes, extrema and their positions all come out of one pass."""

    result = mertens_sign_analysis(10**6)
    lines = _run_gp(
        "m=0;mn=0;mx=0;mnat=0;mxat=0;ch=0;prev=0;"
        "for(n=1,1000000, m+=moebius(n); if(m<mn,mn=m;mnat=n); if(m>mx,mx=m;mxat=n);"
        "s=sign(m); if(s!=0, if(prev!=0 && s!=prev, ch++); prev=s));"
        'print("R:",ch,"|",mn,"|",mnat,"|",mx,"|",mxat); print("DONE:1");'
    )
    row = next(line[2:] for line in lines if line.startswith("R:"))
    changes, minimum, minimum_at, maximum, maximum_at = [
        part.strip() for part in row.split("|")
    ]
    assert result["sign_changes"] == changes
    assert result["minimum"] == minimum and result["minimum_at"] == minimum_at
    assert result["maximum"] == maximum and result["maximum_at"] == maximum_at
    assert int(result["mertens"]) == 212


def test_the_extremal_ratio_ignores_the_trivial_first_term():
    """|M(1)|/sqrt(1) is 1 and would mask every later record."""

    result = mertens_sign_analysis(10**6)
    assert int(result["extreme_ratio_at"]) > 1
    assert 0.0 < float(result["extreme_ratio"]) < 1.0
    assert "Odlyzko" in result["note"]


def test_the_mertens_cross_check_is_refused_where_it_cannot_run():
    with pytest.raises(ValueError, match="only"):
        mertens_value(10**12, cross_check=True)


@pytest.mark.parametrize("x", [0, 10**15])
def test_an_out_of_range_x_is_refused(x):
    with pytest.raises(ValueError, match="x must be between"):
        mertens_value(x)


@pytest.mark.parametrize("pattern,offsets", [
    ("twin", [0, 2]),
    ("cousin", [0, 4]),
    ("sexy", [0, 6]),
    ("quadruplet", [0, 2, 6, 8]),
])
def test_brun_sums_match_pari(pattern, offsets):
    """PARI/GP sums the same finite family, to more digits than are compared."""

    limit = 1000
    result = brun_sum(pattern, limit, digits=12)
    checks = " && ".join(
        f"isprime(p+{offset}) && p+{offset}<={limit}" for offset in offsets
    )
    terms = " + ".join(f"1/(p+{offset})" for offset in offsets)
    lines = _run_gp(
        f"s=0.0;c=0;forprime(p=2,{limit}, if({checks}, c++; s+={terms}));"
        'print("S:", s); print("C:", c); print("DONE:1");'
    )
    reference = next(line[2:].strip() for line in lines if line.startswith("S:"))
    count = next(line[2:].strip() for line in lines if line.startswith("C:"))
    assert result["tuples"] == count
    # Compare the digits this request asked for, not PARI's full precision.
    assert reference.startswith(result["sum"][: result["sum"].index(".") + 10])


def test_prime_triplets_count_both_admissible_shapes_once():
    """(p, p+2, p+6) and (p, p+4, p+6) are both admissible; (p, p+2, p+4) is not."""

    result = brun_sum("triplet", 1000, digits=12)
    lines = _run_gp(
        "s=0.0;c=0;forprime(p=2,1000, my(a=isprime(p+2)&&isprime(p+6)&&p+6<=1000,"
        "b=isprime(p+4)&&isprime(p+6)&&p+6<=1000); if(a||b, c++));"
        'print("C:", c); print("DONE:1");'
    )
    count = next(line[2:].strip() for line in lines if line.startswith("C:"))
    assert result["tuples"] == count == "30"


def test_a_tuple_whose_members_are_not_consecutive_primes_is_still_counted():
    """(3, 7) is a cousin pair with 5 between them; taking the next prime misses it."""

    result = brun_sum("cousin", 10, digits=12)
    assert result["tuples"] == "1"
    assert result["largest"] == "3"


def test_published_twin_counts_are_reproduced():
    """The tuple count is an independent check on the sum: pi_2(x) is published."""

    assert brun_sum("twin", 10**6, digits=6)["tuples"] == "8169"
    assert brun_sum("twin", 10**8, digits=6)["tuples"] == "440312"


def test_a_brun_result_is_never_presented_as_the_constant():
    """The sums converge like 1/log x, so no reachable bound fixes the constant."""

    result = brun_sum("twin", 10**6, digits=12)
    assert float(result["sum"]) < 1.8          # far from the published 1.9021...
    assert "not the constant" in result["note"]
    assert "extrapolation" in result["note"]
    assert result["literature"].startswith("1.902")


def test_the_reported_precision_is_requested_and_the_working_precision_exceeds_it():
    result = brun_sum("twin", 100000, digits=40)
    _, _, fraction = result["sum"].partition(".")
    assert len(fraction) == 40
    assert int(result["precision_bits"]) > 40 * 3.32


@pytest.mark.parametrize("pattern,limit,digits,message", [
    ("nonsense", 1000, 20, "Unknown tuple pattern"),
    ("twin", 2, 20, "limit must be between"),
    ("twin", 1000, 1, "digit count must be between"),
])
def test_invalid_brun_requests_are_refused(pattern, limit, digits, message):
    with pytest.raises(ValueError, match=message):
        brun_sum(pattern, limit, digits=digits)


def test_a_missing_completion_marker_is_an_error(monkeypatch):
    class Completed:
        returncode = 0
        stdout = "MODE:brun\nPATTERN:twin\nSUM:1.5\n"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Completed())
    with pytest.raises(PrimeEngineError, match="completion marker"):
        brun_sum("twin", 1000)


def test_both_helpers_reject_a_bad_invocation():
    from numerisect.native_tools import brun_tool_path, mertens_tool_path

    for tool, arguments in (
        (mertens_tool_path(), ["unknown", "100"]),
        (brun_tool_path(), ["unknown", "100"]),
    ):
        completed = subprocess.run(
            [str(tool), *arguments], capture_output=True, text=True, check=False
        )
        assert completed.returncode != 0
        assert "DONE:" not in completed.stdout


def test_the_mertens_api_serves_both_modes(local_client):
    value = local_client.post(
        "/api/primes/mertens", json={"x": "10^9", "mode": "value"}
    )
    assert value.status_code == 200, value.text
    assert value.json()["mertens"] == "-222"
    assert value.json()["output_file"].startswith("mertens-function")

    signs = local_client.post(
        "/api/primes/mertens", json={"x": "100000", "mode": "signs"}
    )
    assert signs.status_code == 200, signs.text
    payload = signs.json()
    assert int(payload["sign_changes"]) > 0
    assert payload["columns"] == ["n where M changes sign"]
    assert (outputs.OUTPUT_DIR / payload["output_file"]).is_file()


def test_the_brun_api_serves_every_pattern(local_client):
    for pattern in BRUN_PATTERNS:
        response = local_client.post(
            "/api/primes/brun",
            json={"pattern": pattern, "limit": "100000", "digits": 15},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["pattern"] == pattern
        assert float(payload["sum"]) > 0
        report = (outputs.OUTPUT_DIR / payload["output_file"]).read_text(encoding="utf-8")
        assert "truncated sum, not the constant" in report


def test_the_api_refuses_an_impossible_cross_check(local_client):
    response = local_client.post(
        "/api/primes/mertens",
        json={"x": "10^13", "mode": "value", "cross_check": True},
    )
    assert response.status_code == 422
    assert "only" in response.json()["detail"]
