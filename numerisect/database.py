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
    "trial_bound",
    "cado_parameter_size",
    "cado_parameter_file",
    "workdir",
    "log_path",
    "command_json",
    "command_history_json",
    "factors_json",
    "engine_target",
    "warning",
    "error",
    "pid",
    "result_path",
    "parent_job_id",
    # workspace tranche: scheduling, resource limits, pause/resume
    "priority",
    "cpu_seconds",
    "memory_mb",
    "wall_seconds",
    "failure_reason",
    "paused_at",
}

ECM_COLUMNS = {"ecm_b1", "ecm_b2", "ecm_curves", "ecm_sigma", "ecm_param", "ecm_curves_done"}
WORKSPACE_COLUMNS = {"name", "notes", "job_ids_json", "report_files_json", "ui_state_json"}
JOB_SORT_COLUMNS = {
    "created_at",
    "updated_at",
    "finished_at",
    "digits",
    "status",
    "selected_backend",
    "priority",
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
                    trial_bound INTEGER NOT NULL DEFAULT 100000,
                    cado_parameter_size INTEGER,
                    cado_parameter_file TEXT,
                    workdir TEXT NOT NULL,
                    log_path TEXT NOT NULL,
                    command_json TEXT NOT NULL DEFAULT '[]',
                    command_history_json TEXT NOT NULL DEFAULT '[]',
                    factors_json TEXT NOT NULL DEFAULT '[]',
                    engine_target TEXT,
                    warning TEXT,
                    error TEXT,
                    pid INTEGER,
                    result_path TEXT,
                    parent_job_id TEXT
                )
                """
            )
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
            }
            if "result_path" not in columns:
                conn.execute("ALTER TABLE jobs ADD COLUMN result_path TEXT")
            if "parent_job_id" not in columns:
                conn.execute("ALTER TABLE jobs ADD COLUMN parent_job_id TEXT")
            if "command_history_json" not in columns:
                conn.execute(
                    "ALTER TABLE jobs ADD COLUMN command_history_json TEXT NOT NULL DEFAULT '[]'"
                )
            if "trial_bound" not in columns:
                conn.execute(
                    "ALTER TABLE jobs ADD COLUMN trial_bound INTEGER NOT NULL DEFAULT 100000"
                )
            self._initialize_workspace_schema(conn, columns)
            conn.execute(
                """
                UPDATE jobs
                SET status='failed', phase='Interrupted by application restart',
                    error='The application stopped while this job was active.',
                    updated_at=?, finished_at=?
                WHERE status IN ('queued', 'running', 'cancelling', 'paused')
                """,
                (utc_now(), utc_now()),
            )

    @staticmethod
    def _initialize_workspace_schema(conn: sqlite3.Connection, columns: set[str]) -> None:
        """Additive migrations for scheduling, workspaces, reports, and caching."""

        additions = {
            "priority": "INTEGER NOT NULL DEFAULT 0",
            "cpu_seconds": "INTEGER",
            "memory_mb": "INTEGER",
            "wall_seconds": "INTEGER",
            "failure_reason": "TEXT",
            "paused_at": "TEXT",
            "ecm_b1": "INTEGER",
            "ecm_b2": "TEXT",
            "ecm_curves": "INTEGER",
            "ecm_sigma": "TEXT",
            "ecm_param": "INTEGER",
            "ecm_curves_done": "INTEGER NOT NULL DEFAULT 0",
        }
        for column, definition in additions.items():
            if column not in columns:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {column} {definition}")
        conn.execute("CREATE INDEX IF NOT EXISTS jobs_status_idx ON jobs(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS jobs_created_idx ON jobs(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS jobs_backend_idx ON jobs(selected_backend)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                job_ids_json TEXT NOT NULL DEFAULT '[]',
                report_files_json TEXT NOT NULL DEFAULT '[]',
                ui_state_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                filename TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                created_at TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                job_id TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS reports_kind_idx ON reports(kind)")
        conn.execute("CREATE INDEX IF NOT EXISTS reports_created_idx ON reports(created_at)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS result_cache (
                cache_key TEXT PRIMARY KEY,
                operation TEXT NOT NULL,
                engine TEXT NOT NULL,
                engine_revision TEXT NOT NULL,
                parameters_json TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                hits INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS cache_operation_idx ON result_cache(operation)")

    @staticmethod
    def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        result["negative"] = bool(result["negative"])
        for source, target in (
            ("command_json", "command"),
            ("command_history_json", "command_history"),
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
        data.setdefault("command_history_json", "[]")
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
        invalid = set(values) - JOB_COLUMNS - ECM_COLUMNS
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

    # ----- workspace tranche: search, workspaces, reports, cache, history -------------

    def search_jobs(
        self,
        *,
        q: str | None = None,
        status: str | None = None,
        engine: str | None = None,
        since: str | None = None,
        until: str | None = None,
        sort: str = "created_at",
        descending: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Filter jobs with parameterized SQL.

        Args:
            q: Substring matched against the expression, number, and factor list.
            status: Exact job status.
            engine: Substring matched against the requested or selected backend.
            since: ISO-8601 lower bound on ``created_at`` (inclusive).
            until: ISO-8601 upper bound on ``created_at`` (inclusive).
            sort: One of ``JOB_SORT_COLUMNS``.
            descending: Sort direction.
            limit: Maximum rows.
            offset: Rows to skip.

        Returns:
            Decoded job rows.
        """

        if sort not in JOB_SORT_COLUMNS:
            raise ValueError(f"Unsupported sort column: {sort}")
        clauses: list[str] = []
        values: list[Any] = []
        if q:
            pattern = f"%{q}%"
            clauses.append("(expression LIKE ? OR number LIKE ? OR factors_json LIKE ?)")
            values.extend([pattern, pattern, pattern])
        if status:
            clauses.append("status = ?")
            values.append(status)
        if engine:
            clauses.append("(selected_backend LIKE ? OR requested_backend LIKE ?)")
            values.extend([f"%{engine}%", f"%{engine}%"])
        if since:
            clauses.append("created_at >= ?")
            values.append(since)
        if until:
            clauses.append("created_at <= ?")
            values.append(until)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        direction = "DESC" if descending else "ASC"
        query = (
            f"SELECT * FROM jobs {where} ORDER BY {sort} {direction}, created_at DESC "
            "LIMIT ? OFFSET ?"
        )
        with self.connect() as conn:
            rows = conn.execute(query, [*values, limit, offset]).fetchall()
        return [self._decode(row) for row in rows]  # type: ignore[misc]

    def list_queued_jobs(self) -> list[dict[str, Any]]:
        """Return queued jobs ordered by priority (high first) then creation time."""

        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status='queued' ORDER BY priority DESC, created_at ASC"
            ).fetchall()
        return [self._decode(row) for row in rows]  # type: ignore[misc]

    @staticmethod
    def _decode_workspace(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        for source, target, default in (
            ("job_ids_json", "job_ids", []),
            ("report_files_json", "report_files", []),
            ("ui_state_json", "ui_state", {}),
        ):
            try:
                result[target] = json.loads(result[source])
            except (TypeError, json.JSONDecodeError):
                result[target] = default
            del result[source]
        return result

    def create_workspace(
        self,
        *,
        workspace_id: str,
        name: str,
        notes: str,
        job_ids: list[str],
        report_files: list[str],
        ui_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Insert a workspace row and return it."""

        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO workspaces (id, name, created_at, updated_at, notes, job_ids_json, "
                "report_files_json, ui_state_json) VALUES (?,?,?,?,?,?,?,?)",
                (
                    workspace_id, name, now, now, notes, json.dumps(job_ids),
                    json.dumps(report_files), json.dumps(ui_state, sort_keys=True),
                ),
            )
        return self.get_workspace(workspace_id)  # type: ignore[return-value]

    def get_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM workspaces WHERE id=?", (workspace_id,)).fetchone()
        return self._decode_workspace(row)

    def list_workspaces(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM workspaces ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._decode_workspace(row) for row in rows]  # type: ignore[misc]

    def update_workspace(self, workspace_id: str, **values: Any) -> dict[str, Any] | None:
        """Update selected workspace fields (``job_ids``/``report_files``/``ui_state`` are JSON)."""

        encoded: dict[str, Any] = {}
        for key, value in values.items():
            if key == "job_ids":
                encoded["job_ids_json"] = json.dumps(value)
            elif key == "report_files":
                encoded["report_files_json"] = json.dumps(value)
            elif key == "ui_state":
                encoded["ui_state_json"] = json.dumps(value, sort_keys=True)
            elif key in {"name", "notes"}:
                encoded[key] = value
            else:
                raise ValueError(f"Unknown workspace field: {key}")
        if not encoded:
            return self.get_workspace(workspace_id)
        encoded["updated_at"] = utc_now()
        assignments = ",".join(f"{key}=?" for key in encoded)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE workspaces SET {assignments} WHERE id=?",
                [*encoded.values(), workspace_id],
            )
        return self.get_workspace(workspace_id)

    def delete_workspace(self, workspace_id: str) -> bool:
        with self.connect() as conn:
            cursor = conn.execute("DELETE FROM workspaces WHERE id=?", (workspace_id,))
        return cursor.rowcount > 0

    def register_report(
        self, filename: str, kind: str, summary: str, job_id: str | None = None
    ) -> None:
        """Insert or refresh one saved-report index entry."""

        with self.connect() as conn:
            conn.execute(
                "INSERT INTO reports (filename, kind, created_at, summary, job_id) "
                "VALUES (?,?,?,?,?) ON CONFLICT(filename) DO UPDATE SET kind=excluded.kind, "
                "summary=excluded.summary, job_id=COALESCE(excluded.job_id, reports.job_id)",
                (filename, kind, utc_now(), summary[:2000], job_id),
            )

    def search_reports(
        self,
        *,
        q: str | None = None,
        kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        if q:
            clauses.append("(filename LIKE ? OR summary LIKE ? OR kind LIKE ?)")
            values.extend([f"%{q}%"] * 3)
        if kind:
            clauses.append("kind = ?")
            values.append(kind)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM reports {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                [*values, limit, offset],
            ).fetchall()
        return [dict(row) for row in rows]

    def report_count(self) -> int:
        with self.connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0])

    def cache_get(self, cache_key: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM result_cache WHERE cache_key=?", (cache_key,)
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE result_cache SET hits=hits+1 WHERE cache_key=?", (cache_key,)
            )
        return dict(row)

    def cache_put(
        self,
        *,
        cache_key: str,
        operation: str,
        engine: str,
        engine_revision: str,
        parameters_json: str,
        response_json: str,
        max_rows: int,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO result_cache (cache_key, operation, engine, "
                "engine_revision, parameters_json, response_json, created_at, hits) "
                "VALUES (?,?,?,?,?,?,?,0)",
                (
                    cache_key, operation, engine, engine_revision,
                    parameters_json, response_json, utc_now(),
                ),
            )
            conn.execute(
                "DELETE FROM result_cache WHERE cache_key IN (SELECT cache_key FROM "
                "result_cache ORDER BY created_at DESC LIMIT -1 OFFSET ?)",
                (max_rows,),
            )

    def cache_clear(self, operation: str | None = None) -> int:
        with self.connect() as conn:
            if operation:
                cursor = conn.execute(
                    "DELETE FROM result_cache WHERE operation=?", (operation,)
                )
            else:
                cursor = conn.execute("DELETE FROM result_cache")
        return cursor.rowcount

    def cache_stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS entries, COALESCE(SUM(hits), 0) AS hits, "
                "COALESCE(SUM(LENGTH(response_json)), 0) AS bytes FROM result_cache"
            ).fetchone()
            operations = conn.execute(
                "SELECT operation, COUNT(*) AS entries FROM result_cache "
                "GROUP BY operation ORDER BY operation"
            ).fetchall()
        return {
            "entries": int(row["entries"]),
            "hits": int(row["hits"]),
            "bytes": int(row["bytes"]),
            "operations": [dict(item) for item in operations],
        }

    def performance_history(self, bucket_digits: int = 10) -> list[dict[str, Any]]:
        """Aggregate completed-job timings by engine and decimal-digit bucket.

        The aggregation is plain SQL over stored timestamps; no mathematics is
        performed on the factorization results themselves.
        """

        if not 1 <= bucket_digits <= 1000:
            raise ValueError("Digit bucket width must be between 1 and 1,000")
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT selected_backend AS engine,
                       (digits / ?) * ? AS bucket_start,
                       COUNT(*) AS jobs,
                       AVG((julianday(finished_at) - julianday(started_at)) * 86400.0) AS mean_seconds,
                       MIN((julianday(finished_at) - julianday(started_at)) * 86400.0) AS min_seconds,
                       MAX((julianday(finished_at) - julianday(started_at)) * 86400.0) AS max_seconds,
                       MAX(finished_at) AS latest
                FROM jobs
                WHERE status='completed' AND started_at IS NOT NULL AND finished_at IS NOT NULL
                GROUP BY selected_backend, bucket_start
                ORDER BY selected_backend, bucket_start
                """,
                (bucket_digits, bucket_digits),
            ).fetchall()
        return [
            {
                "engine": row["engine"],
                "digits_from": int(row["bucket_start"]),
                "digits_to": int(row["bucket_start"]) + bucket_digits - 1,
                "jobs": int(row["jobs"]),
                "mean_seconds": round(float(row["mean_seconds"] or 0), 3),
                "min_seconds": round(float(row["min_seconds"] or 0), 3),
                "max_seconds": round(float(row["max_seconds"] or 0), 3),
                "latest": row["latest"],
            }
            for row in rows
        ]
