from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

JOB_COLUMNS = {
    "id",
    "created_at",
    "updated_at",
    "started_at",
    "finished_at",
    "expression",
    "number",
    "digits",
    "negative",
    "requested_backend",
    "selected_backend",
    "status",
    "phase",
    "progress",
    "threads",
    "pretest_level",
    "cado_parameter_size",
    "cado_parameter_file",
    "workdir",
    "log_path",
    "command_json",
    "factors_json",
    "engine_target",
    "warning",
    "error",
    "pid",
    "result_path",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _initialize(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    expression TEXT NOT NULL,
                    number TEXT NOT NULL,
                    digits INTEGER NOT NULL,
                    negative INTEGER NOT NULL DEFAULT 0,
                    requested_backend TEXT NOT NULL,
                    selected_backend TEXT NOT NULL,
                    status TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0,
                    threads INTEGER NOT NULL,
                    pretest_level INTEGER NOT NULL,
                    cado_parameter_size INTEGER,
                    cado_parameter_file TEXT,
                    workdir TEXT NOT NULL,
                    log_path TEXT NOT NULL,
                    command_json TEXT NOT NULL DEFAULT '[]',
                    factors_json TEXT NOT NULL DEFAULT '[]',
                    engine_target TEXT,
                    warning TEXT,
                    error TEXT,
                    pid INTEGER,
                    result_path TEXT
                )
                """
            )
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
            }
            if "result_path" not in columns:
                conn.execute("ALTER TABLE jobs ADD COLUMN result_path TEXT")
            conn.execute(
                """
                UPDATE jobs
                SET status='failed', phase='Interrupted by application restart',
                    error='The application stopped while this job was active.',
                    updated_at=?, finished_at=?
                WHERE status IN ('queued', 'running', 'cancelling')
                """,
                (utc_now(), utc_now()),
            )

    @staticmethod
    def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        result["negative"] = bool(result["negative"])
        for source, target in (
            ("command_json", "command"),
            ("factors_json", "factors"),
        ):
            try:
                result[target] = json.loads(result[source])
            except (TypeError, json.JSONDecodeError):
                result[target] = []
            del result[source]
        return result

    def create_job(self, values: dict[str, Any]) -> dict[str, Any]:
        data = dict(values)
        data.setdefault("created_at", utc_now())
        data.setdefault("updated_at", data["created_at"])
        data.setdefault("command_json", "[]")
        data.setdefault("factors_json", "[]")
        columns = list(data)
        placeholders = ",".join("?" for _ in columns)
        with self.connect() as conn:
            conn.execute(
                f"INSERT INTO jobs ({','.join(columns)}) VALUES ({placeholders})",
                [data[column] for column in columns],
            )
        return self.get_job(data["id"])  # type: ignore[return-value]

    def update_job(self, job_id: str, **values: Any) -> dict[str, Any] | None:
        invalid = set(values) - JOB_COLUMNS
        if invalid:
            raise ValueError(f"Unknown job columns: {sorted(invalid)}")
        values["updated_at"] = utc_now()
        assignments = ",".join(f"{key}=?" for key in values)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE jobs SET {assignments} WHERE id=?",
                [*values.values(), job_id],
            )
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._decode(row)

    def list_jobs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._decode(row) for row in rows]  # type: ignore[misc]
