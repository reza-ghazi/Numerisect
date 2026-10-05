"""The local factor catalogue, built here rather than imported from a published table.

The catalogue feature always worked and was always empty: nothing is bundled, so a
lookup searched zero files. Shipping the Cunningham tables would mean vendoring
third-party data whose licence would have to be argued, so the script computes the
entries with the installed engine instead and records which engine produced each one.
"""

import json
import subprocess
import sys
from pathlib import Path

from numerisect.catalogues import local_catalogue_lookup

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_factor_catalogue.py"


def _build(destination: Path, *arguments: str) -> dict:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(destination), "--quiet", *arguments],
        capture_output=True, text=True, check=False, cwd=ROOT,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(destination.read_text(encoding="utf-8"))


def test_the_catalogue_is_computed_and_names_the_engine_that_computed_it(tmp_path):
    catalogue = _build(tmp_path / "cunningham.json", "--bases", "2", "--max-exponent", "12")
    assert catalogue["schema"] == "org.numerisect.factor-catalogue.v1"
    assert catalogue["engine"].startswith("PARI/GP ")
    assert "Computed locally by PARI/GP, not imported" in catalogue["note"]
    # 2^11 - 1 = 23 * 89 and 2^12 - 1 = 3^2 * 5 * 7 * 13, both published values.
    entries = {entry["number"]: entry for entry in catalogue["entries"]}
    assert entries["2047"]["factors"] == ["23", "89"]
    assert entries["4095"]["factors"] == ["3", "3", "5", "7", "13"]
    assert entries["2047"]["note"].startswith("2^11-1;")


def test_a_generated_catalogue_is_found_by_the_local_lookup(tmp_path):
    """The point of generating it is that the existing lookup then has something to find."""

    _build(tmp_path / "cunningham.json", "--bases", "2", "--max-exponent", "12")
    found = local_catalogue_lookup(2047, directory=tmp_path)
    assert found["searched"] == ["cunningham.json"]
    assert found["claims"][0]["factors"] == ["23", "89"]
    # Claims stay labelled unverified: the catalogue is a source, not an authority.
    assert "unverified" in found["note"].lower()
    assert local_catalogue_lookup(999983, directory=tmp_path)["claims"] == []


def test_each_sign_can_be_built_alone(tmp_path):
    minus = _build(tmp_path / "minus.json", "--bases", "2", "--max-exponent", "8",
                   "--minus-only")
    plus = _build(tmp_path / "plus.json", "--bases", "2", "--max-exponent", "8",
                  "--plus-only")
    assert all("-1;" in entry["note"] for entry in minus["entries"])
    assert all("+1;" in entry["note"] for entry in plus["entries"])
    assert minus["entries"] and plus["entries"]


def test_a_number_the_budget_cannot_finish_is_skipped_rather_than_partial(tmp_path):
    """An entry must be complete and verified, or absent. Never half a factorization."""

    # A narrow slice of hard numbers: 3^400 and its neighbours do not factor in a
    # second, which keeps this test to a handful of engine calls.
    catalogue = _build(
        tmp_path / "wide.json", "--bases", "3", "--min-exponent", "400",
        "--max-exponent", "402", "--seconds", "1",
    )
    assert catalogue["skipped"], "no number near 3^400 exceeded a one-second budget"
    for entry in catalogue["entries"]:
        assert entry["factors"]
    numbers = {entry["number"] for entry in catalogue["entries"]}
    assert "3" not in catalogue["skipped"]        # the skip list holds expressions
    assert all(expression.startswith("3^") for expression in catalogue["skipped"])
    assert numbers.isdisjoint(set(catalogue["skipped"]))


def test_invalid_arguments_are_refused(tmp_path):
    for arguments in (
        ["--bases", "1"],
        ["--max-exponent", "1"],
        ["--plus-only", "--minus-only"],
        ["--min-exponent", "40", "--max-exponent", "10"],
    ):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--output", str(tmp_path / "x.json"), *arguments],
            capture_output=True, text=True, check=False, cwd=ROOT,
        )
        assert completed.returncode != 0
