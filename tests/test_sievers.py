"""GGNFS lattice siever discovery, CPU validation, and reporting.

CI has no sievers installed, so the discovery logic is exercised against fabricated
directories rather than whatever happens to be on the machine. The two cases that matter
are a siever that runs and a siever that cannot run here, because the second one is
silently accepted by YAFU and then fails mid-sieve.
"""

import signal
import stat
import subprocess

import pytest
from fastapi.testclient import TestClient

from numerisect import outputs, sievers
from numerisect.main import app
from numerisect.sievers import (
    SIEVER,
    cpu_features,
    discover,
    probe,
    report,
    siever_directory,
)


def _fake_siever(directory, index, script="#!/bin/sh\necho 'Bad job file'\nexit 1\n"):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"gnfs-lasieve4I{index}e"
    path.write_text(script)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


@pytest.fixture()
def local_client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    client.headers["X-Numerisect-Token"] = client.get("/api/session").json()["request_token"]
    return client


# --- name matching ---------------------------------------------------------------------


def test_only_ggnfs_siever_names_are_recognised():
    for name in ("gnfs-lasieve4I11e", "gnfs-lasieve4I16e"):
        assert SIEVER.match(name)
    for name in ("gnfs-lasieve4I1e", "lasieve4I13e", "gnfs-lasieve4I13", "yafu", "makefb"):
        assert not SIEVER.match(name)


# --- discovery -------------------------------------------------------------------------


def test_discovery_finds_sievers_and_records_their_digest(tmp_path, monkeypatch):
    directory = tmp_path / "ggnfs" / "bin"
    for index in ("11", "13", "16"):
        _fake_siever(directory, index)
    monkeypatch.setattr(sievers, "candidate_directories", lambda: [directory])

    groups = discover()
    assert len(groups) == 1
    group = groups[0]
    assert group.indices == [11, 13, 16]
    assert group.line.startswith("lasieve4")
    for siever in group.sievers:
        assert len(siever.sha256) == 64
        assert siever.runnable is True


def test_the_line_is_read_from_the_directory_and_never_guessed(tmp_path, monkeypatch):
    """lasieve4 and lasieve5 share file names, so an unnamed directory stays unidentified."""

    five = tmp_path / "factor" / "lasieve5_64" / "bin"
    plain = tmp_path / "somewhere" / "bin"
    _fake_siever(five, "15")
    _fake_siever(plain, "15")
    monkeypatch.setattr(sievers, "candidate_directories", lambda: [five, plain])

    lines = [group.line for group in discover()]
    assert lines[0].startswith("lasieve5")
    assert lines[1] == "unidentified"


def test_a_siever_that_cannot_run_here_is_reported_not_offered(tmp_path, monkeypatch):
    """An AVX-512 build on a CPU without AVX-512 dies with SIGILL.

    The path is right and the file is present, so nothing else catches this. YAFU would
    accept the directory and fail once sieving began.
    """

    directory = tmp_path / "avx512"
    _fake_siever(directory, "14")
    monkeypatch.setattr(sievers, "candidate_directories", lambda: [directory])

    real = subprocess.run

    def killed_by_sigill(command, **kwargs):
        if "lasieve" in str(command[0]):
            return subprocess.CompletedProcess(command, -signal.SIGILL, b"", b"")
        return real(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", killed_by_sigill)
    groups = discover()
    assert groups[0].sievers[0].runnable is False
    assert "illegal instruction" in groups[0].sievers[0].detail
    assert groups[0].usable == []
    assert siever_directory() is None

    summary = report()
    assert "none of them runs on this CPU" in summary["note"]
    assert "AVX-512" in summary["note"]


def test_the_first_usable_directory_is_selected(tmp_path, monkeypatch):
    broken = tmp_path / "broken"
    working = tmp_path / "working"
    _fake_siever(broken, "12", script="#!/bin/sh\nexit 0\n")
    _fake_siever(working, "12")
    monkeypatch.setattr(sievers, "candidate_directories", lambda: [broken, working])
    # Both run here, so the first wins.
    assert siever_directory() == broken


def test_a_non_executable_file_is_not_a_siever(tmp_path, monkeypatch):
    directory = tmp_path / "bin"
    directory.mkdir(parents=True)
    (directory / "gnfs-lasieve4I13e").write_text("not executable")
    monkeypatch.setattr(sievers, "candidate_directories", lambda: [directory])
    assert discover() == []
    assert siever_directory() is None


def test_probe_reports_a_missing_binary_rather_than_raising(tmp_path):
    runnable, detail = probe(tmp_path / "does-not-exist")
    assert runnable is False
    assert detail


# --- reporting ---------------------------------------------------------------------------


def test_report_is_honest_when_nothing_is_installed(monkeypatch):
    monkeypatch.setattr(sievers, "candidate_directories", list)
    summary = report()
    assert summary["rows"] == []
    assert summary["metrics"]["Selected directory"] == "none"
    assert summary["metrics"]["Available sieve indices"] == "none"
    # A missing siever disables NFS in YAFU; it must not read as a total failure.
    assert "quadratic sieve" in summary["note"]
    assert "CADO-NFS is an independent alternative" in summary["note"]


def test_report_names_the_cpu_features_it_checked():
    summary = report()
    assert "CPU features" in summary["metrics"]
    assert summary["metrics"]["AVX-512"] in {"yes", "no"}
    assert isinstance(cpu_features(), list)


def test_siever_route(local_client, tmp_path, monkeypatch):
    monkeypatch.setattr(outputs, "OUTPUT_DIR", tmp_path)
    response = local_client.get("/api/factor-lab/sievers")
    assert response.status_code == 200
    payload = response.json()
    assert "Selected directory" in payload["metrics"]
    assert payload["output_file"].endswith(".txt")


# --- the reason this module exists --------------------------------------------------------


def test_yafu_is_given_the_siever_directory(tmp_path, monkeypatch):
    """Regression: YAFU used to be launched with no siever directory at all.

    It then reported "possibly bad path to siever" for every relation file and exited
    non-zero having found nothing, which looks like an engine crash rather than a missing
    dependency.
    """

    from numerisect import jobs

    directory = tmp_path / "ggnfs" / "bin"
    _fake_siever(directory, "13")
    monkeypatch.setattr(jobs, "siever_directory", lambda: directory)

    captured: dict[str, list[str]] = {}

    def capture(self, job, command, **kwargs):
        captured["command"] = command
        return 0, "***factors found***\n"

    monkeypatch.setattr(jobs.JobManager, "_run_process", capture)
    manager = object.__new__(jobs.JobManager)
    job = {"threads": 4, "pretest_level": 0, "workdir": str(tmp_path)}
    try:
        manager._run_yafu(job, 8051, pretest_only=False)
    except Exception:
        pass  # the fake output does not parse; only the command matters here
    assert "-ggnfs_dir" in captured["command"]
    assert captured["command"][captured["command"].index("-ggnfs_dir") + 1].endswith("/")
