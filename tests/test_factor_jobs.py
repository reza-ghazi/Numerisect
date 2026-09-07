import json

from numerisect import jobs, outputs
from numerisect.database import Database
from numerisect.jobs import JobManager


def test_bounded_native_trial_job_and_reproducible_manifest(tmp_path, monkeypatch):
    job_root = tmp_path / "jobs"
    output_root = tmp_path / "output"
    job_root.mkdir()
    output_root.mkdir()
    monkeypatch.setattr(jobs, "JOBS_DIR", job_root)
    monkeypatch.setattr(outputs, "OUTPUT_DIR", output_root)
    database = Database(tmp_path / "jobs.sqlite3")
    manager = JobManager(database)
    try:
        created = manager.create(
            expression="8051",
            number=8051,
            requested_backend="pari_trial",
            threads=2,
            pretest_level=20,
            trial_bound=100,
            cado_parameter_size=None,
        )
        manager._futures[created["id"]].result(timeout=10)
        completed = database.get_job(created["id"])
        assert completed is not None
        assert completed["status"] == "completed"
        assert [factor["value"] for factor in completed["factors"]] == ["83", "97"]
        report = output_root / f"factorization-{created['id'][:12]}.txt"
        manifest_path = report.with_suffix(".json")
        assert f"output/{manifest_path.name}" in report.read_text(encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["schema"] == "org.numerisect.factorization-manifest.v1"
        assert manifest["commands"] == [["gp", "-fq"]]
        assert manifest["trial_bound"] == 100
        assert manifest["engines"][0]["name"] == "PARI/GP"
        assert len(manifest["engines"][0]["executable_sha256"]) == 64
    finally:
        manager.shutdown()
