from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .config import DEFAULT_CADO_THRESHOLD, JOBS_DIR, MAX_PARALLEL_JOBS
from .database import Database, utc_now
from .engines import (
    CadoParameter,
    cado_parameter_warning,
    discover_cado_parameters,
    executable_path,
    parse_cado_factors,
    parse_msieve_factors,
    parse_yafu_factors,
    prime_factor_product,
    product_is_complete,
    select_cado_parameter,
)
from .outputs import save_factorization

PHASES = (
    ("trial", "Trial division", 8),
    ("fmt:", "Fermat search", 12),
    ("rho:", "Pollard rho", 18),
    ("pm1:", "Pollard p−1", 24),
    ("pp1:", "Williams p+1", 28),
    ("ecm:", "Elliptic-curve pretest", 35),
    ("starting siqs", "Self-initializing quadratic sieve", 55),
    ("polynomial selection", "NFS polynomial selection", 18),
    ("generate factor base", "Generating factor base", 28),
    ("lattice sieving", "NFS lattice sieving", 55),
    ("filtering", "Filtering relations", 75),
    ("linear algebra", "Linear algebra", 88),
    ("square root", "Square-root phase", 96),
)


class Cancelled(RuntimeError):
    pass


class JobManager:
    def __init__(self, database: Database):
        self.database = database
        self.executor = ThreadPoolExecutor(
            max_workers=MAX_PARALLEL_JOBS, thread_name_prefix="factor-job"
        )
        self._lock = threading.Lock()
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._futures: dict[str, Future[None]] = {}
        self.parameters = discover_cado_parameters()

    def create(
        self,
        *,
        expression: str,
        number: int,
        requested_backend: str,
        threads: int,
        pretest_level: int,
        cado_parameter_size: int | None,
    ) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        absolute = abs(number)
        digits = len(str(absolute))
        selected = requested_backend
        if requested_backend == "auto":
            selected = "yafu" if digits < DEFAULT_CADO_THRESHOLD else "hybrid"
        if selected in {"cado", "hybrid"} and not executable_path("cado-nfs.py"):
            raise RuntimeError("cado-nfs.py is not available")
        if selected in {"yafu", "hybrid"} and not executable_path("yafu"):
            raise RuntimeError("YAFU is not available")
        if selected == "msieve" and not executable_path("msieve"):
            raise RuntimeError("Msieve is not available")

        warning: str | None = None
        parameter: CadoParameter | None = None
        if selected in {"cado", "hybrid"}:
            # A first-run installer may have added CADO after this manager was created.
            self.parameters = discover_cado_parameters()
            parameter = select_cado_parameter(
                digits, self.parameters, cado_parameter_size
            )
            warning = cado_parameter_warning(digits, parameter)
        if number < 0:
            warning = "Negative input: factoring its absolute value; −1 is included." + (
                f" {warning}" if warning else ""
            )

        workdir = JOBS_DIR / job_id
        workdir.mkdir(parents=True, exist_ok=False)
        log_path = workdir / "job.log"
        log_path.touch()
        job = self.database.create_job(
            {
                "id": job_id,
                "expression": expression,
                "number": str(absolute),
                "digits": digits,
                "negative": int(number < 0),
                "requested_backend": requested_backend,
                "selected_backend": selected,
                "status": "queued",
                "phase": "Waiting for worker",
                "progress": 0,
                "threads": threads,
                "pretest_level": pretest_level,
                "cado_parameter_size": parameter.size if parameter else None,
                "cado_parameter_file": str(parameter.path) if parameter else None,
                "workdir": str(workdir),
                "log_path": str(log_path),
                "warning": warning,
            }
        )
        self._submit(job_id, resume=False)
        return job

    def _submit(self, job_id: str, *, resume: bool) -> None:
        event = threading.Event()
        with self._lock:
            self._cancel_events[job_id] = event
            self._futures[job_id] = self.executor.submit(self._run, job_id, resume)

    def _append_log(self, job: dict[str, Any], text: str) -> None:
        with Path(job["log_path"]).open("a", encoding="utf-8", errors="replace") as handle:
            handle.write(text)

    def _set_phase_from_line(self, job_id: str, line: str) -> None:
        lower = line.lower()
        for needle, phase, progress in PHASES:
            if needle in lower:
                self.database.update_job(job_id, phase=phase, progress=progress)
                return

    def _run_process(
        self,
        job: dict[str, Any],
        command: list[str],
        *,
        cwd: Path,
        stdin_text: str | None = None,
    ) -> tuple[int, str]:
        job_id = job["id"]
        event = self._cancel_events[job_id]
        self.database.update_job(
            job_id,
            command_json=json.dumps(command),
            phase="Starting process",
        )
        self._append_log(job, f"\n$ {' '.join(command)}\n")
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            start_new_session=True,
        )
        with self._lock:
            self._processes[job_id] = process
        self.database.update_job(job_id, pid=process.pid)
        if stdin_text is not None and process.stdin is not None:
            process.stdin.write(stdin_text)
            process.stdin.close()

        captured: list[str] = []
        assert process.stdout is not None
        try:
            for line in process.stdout:
                captured.append(line)
                self._append_log(job, line)
                self._set_phase_from_line(job_id, line)
                if event.is_set():
                    raise Cancelled("Job cancelled")
            return_code = process.wait()
        finally:
            with self._lock:
                self._processes.pop(job_id, None)
            self.database.update_job(job_id, pid=None)
        if event.is_set():
            raise Cancelled("Job cancelled")
        return return_code, "".join(captured)

    @staticmethod
    def _known_factors(records: list[dict[str, object]]) -> list[dict[str, object]]:
        return [
            record
            for record in records
            if record.get("status") in {"prime", "probable_prime"}
        ]

    def _run_yafu(
        self,
        job: dict[str, Any],
        number: int,
        *,
        pretest_only: bool,
    ) -> tuple[list[dict[str, object]], int]:
        command = ["yafu", "-threads", str(job["threads"]), "-terse"]
        if pretest_only:
            command += ["-pretest", str(job["pretest_level"])]
        return_code, output = self._run_process(
            job,
            command,
            cwd=Path(job["workdir"]),
            stdin_text=f"factor({number})\nquit\n",
        )
        if return_code != 0:
            raise RuntimeError(f"YAFU exited with status {return_code}")
        records = parse_yafu_factors(output)
        known = self._known_factors(records)
        product = prime_factor_product(known)
        if number % product != 0:
            raise RuntimeError("YAFU returned factors that do not divide the input")
        return known, number // product

    def _run_msieve(self, job: dict[str, Any], number: int) -> list[dict[str, object]]:
        command = ["msieve", "-v", "-t", str(job["threads"]), str(number)]
        return_code, output = self._run_process(
            job, command, cwd=Path(job["workdir"])
        )
        if return_code != 0:
            raise RuntimeError(f"Msieve exited with status {return_code}")
        return parse_msieve_factors(output)

    def _snapshot(self, job: dict[str, Any]) -> Path | None:
        cado_dir = Path(job["workdir"]) / "cado"
        snapshots = sorted(cado_dir.glob("*.parameters_snapshot.*"))
        return snapshots[-1] if snapshots else None

    def _run_cado(
        self,
        job: dict[str, Any],
        number: int,
        *,
        resume: bool,
    ) -> list[dict[str, object]]:
        snapshot = self._snapshot(job) if resume else None
        if snapshot:
            command = ["cado-nfs.py", str(snapshot)]
        else:
            cado_dir = Path(job["workdir"]) / "cado"
            parameter_path = job["cado_parameter_file"]
            if not parameter_path:
                parameter = select_cado_parameter(len(str(number)), self.parameters)
                parameter_path = str(parameter.path)
                self.database.update_job(
                    job["id"],
                    cado_parameter_size=parameter.size,
                    cado_parameter_file=parameter_path,
                )
            command = [
                "cado-nfs.py",
                "-p",
                parameter_path,
                str(number),
                "-t",
                str(job["threads"]),
                "--workdir",
                str(cado_dir),
            ]
        return_code, output = self._run_process(
            job, command, cwd=Path(job["workdir"])
        )
        if return_code != 0:
            raise RuntimeError(f"CADO-NFS exited with status {return_code}")
        records = parse_cado_factors(output, number)
        if not records:
            raise RuntimeError("CADO-NFS finished without a verifiable factorization")
        return records

    def _run(self, job_id: str, resume: bool) -> None:
        job = self.database.get_job(job_id)
        if not job:
            return
        event = self._cancel_events[job_id]
        if event.is_set():
            self.database.update_job(
                job_id,
                status="cancelled",
                phase="Cancelled before start",
                finished_at=utc_now(),
            )
            return
        self.database.update_job(
            job_id,
            status="running",
            phase="Preparing input",
            progress=2,
            started_at=utc_now(),
            finished_at=None,
            error=None,
        )
        job = self.database.get_job(job_id)
        assert job is not None
        number = int(job["number"])
        factors: list[dict[str, object]] = []
        if job["negative"]:
            factors.append({"value": "-1", "digits": 1, "status": "unit"})
        try:
            backend = job["selected_backend"]
            if resume and backend in {"cado", "hybrid"} and self._snapshot(job):
                existing = [
                    factor
                    for factor in job["factors"]
                    if factor.get("status") in {"prime", "probable_prime", "unit"}
                ]
                factors = existing
                target = int(job.get("engine_target") or number)
                factors.extend(self._run_cado(job, target, resume=True))
            elif backend == "yafu":
                known, residual = self._run_yafu(job, number, pretest_only=False)
                factors.extend(known)
                if residual != 1:
                    factors.append(
                        {
                            "value": str(residual),
                            "digits": len(str(residual)),
                            "status": "composite",
                        }
                    )
            elif backend == "msieve":
                factors.extend(self._run_msieve(job, number))
            elif backend == "cado":
                self.database.update_job(job_id, engine_target=str(number))
                factors.extend(self._run_cado(job, number, resume=False))
            elif backend == "hybrid":
                self.database.update_job(
                    job_id, phase="YAFU small-factor and ECM pretest", progress=5
                )
                known, residual = self._run_yafu(job, number, pretest_only=True)
                factors.extend(known)
                self.database.update_job(
                    job_id, factors_json=json.dumps(factors), engine_target=str(residual)
                )
                if residual > 1:
                    residual_digits = len(str(residual))
                    if residual_digits < DEFAULT_CADO_THRESHOLD:
                        self._append_log(
                            job,
                            "\nHybrid decision: residual is below the CADO threshold; "
                            "finishing with YAFU.\n",
                        )
                        extra, final_residual = self._run_yafu(
                            job, residual, pretest_only=False
                        )
                        factors.extend(extra)
                        if final_residual != 1:
                            factors.append(
                                {
                                    "value": str(final_residual),
                                    "digits": len(str(final_residual)),
                                    "status": "composite",
                                }
                            )
                    else:
                        parameter = select_cado_parameter(
                            residual_digits,
                            self.parameters,
                            job["cado_parameter_size"],
                        )
                        self.database.update_job(
                            job_id,
                            cado_parameter_size=parameter.size,
                            cado_parameter_file=str(parameter.path),
                            engine_target=str(residual),
                            warning=cado_parameter_warning(residual_digits, parameter),
                        )
                        job = self.database.get_job(job_id) or job
                        factors.extend(self._run_cado(job, residual, resume=False))
            else:
                raise RuntimeError(f"Unsupported backend: {backend}")

            verification_factors = [
                factor for factor in factors if factor.get("status") != "unit"
            ]
            complete = product_is_complete(verification_factors, number)
            finished_at = utc_now()
            self.database.update_job(
                job_id,
                status="completed" if complete else "failed",
                phase="Complete" if complete else "Incomplete factorization",
                progress=100 if complete else 99,
                factors_json=json.dumps(factors),
                error=None if complete else "The returned factors do not multiply to the input.",
                finished_at=finished_at,
            )
            if complete:
                completed_job = self.database.get_job(job_id)
                assert completed_job is not None
                try:
                    result_path = save_factorization(completed_job, factors)
                    self.database.update_job(job_id, result_path=str(result_path))
                except OSError as exc:
                    warning = completed_job.get("warning")
                    export_warning = f"Could not save the text export: {exc}"
                    self.database.update_job(
                        job_id,
                        warning=f"{warning} {export_warning}" if warning else export_warning,
                    )
        except Cancelled:
            self.database.update_job(
                job_id,
                status="cancelled",
                phase="Cancelled",
                factors_json=json.dumps(factors),
                finished_at=utc_now(),
            )
        except Exception as exc:
            self._append_log(job, f"\nApplication error: {exc}\n")
            self.database.update_job(
                job_id,
                status="failed",
                phase="Failed",
                error=str(exc),
                factors_json=json.dumps(factors),
                finished_at=utc_now(),
            )
        finally:
            with self._lock:
                self._cancel_events.pop(job_id, None)
                self._futures.pop(job_id, None)

    def cancel(self, job_id: str) -> dict[str, Any]:
        job = self.database.get_job(job_id)
        if not job:
            raise KeyError(job_id)
        if job["status"] not in {"queued", "running", "cancelling"}:
            return job
        with self._lock:
            event = self._cancel_events.get(job_id)
            process = self._processes.get(job_id)
            future = self._futures.get(job_id)
        if event:
            event.set()
        if future and future.cancel():
            cancelled = self.database.update_job(
                job_id,
                status="cancelled",
                phase="Cancelled before start",
                finished_at=utc_now(),
            )
            with self._lock:
                self._cancel_events.pop(job_id, None)
                self._futures.pop(job_id, None)
            return cancelled  # type: ignore[return-value]
        self.database.update_job(job_id, status="cancelling", phase="Stopping process")
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGINT)
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        return self.database.get_job(job_id)  # type: ignore[return-value]

    def resume(self, job_id: str) -> dict[str, Any]:
        job = self.database.get_job(job_id)
        if not job:
            raise KeyError(job_id)
        if job["status"] in {"queued", "running", "cancelling"}:
            raise ValueError("Job is already active")
        self._append_log(job, "\n--- Resuming job ---\n")
        self.database.update_job(
            job_id,
            status="queued",
            phase="Waiting to resume",
            progress=0,
            error=None,
            finished_at=None,
        )
        self._submit(job_id, resume=True)
        return self.database.get_job(job_id)  # type: ignore[return-value]

    def shutdown(self) -> None:
        with self._lock:
            active = list(self._processes.items())
        for job_id, process in active:
            event = self._cancel_events.get(job_id)
            if event:
                event.set()
            try:
                os.killpg(process.pid, signal.SIGINT)
            except ProcessLookupError:
                pass
        self.executor.shutdown(wait=False, cancel_futures=True)
