from __future__ import annotations

import json
import os
import re
import resource
import signal
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .adapters import REGISTRY as ADAPTER_REGISTRY
from .config import DEFAULT_CADO_THRESHOLD, JOBS_DIR, MAX_PARALLEL_JOBS
from .database import Database, utc_now
from .engines import (
    CadoParameter,
    cado_parameter_warning,
    discover_cado_parameters,
    executable_path,
    parse_cado_factors,
    parse_ecm_output,
    parse_msieve_factors,
    parse_yafu_factors,
    prime_factor_product,
    product_is_complete,
    select_cado_parameter,
)
from .factor_lab import parse_tune_info, reconcile_factors, squfof, tune_recommendation
from .outputs import save_factorization
from .sievers import siever_directory

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


class LimitExceeded(RuntimeError):
    """A per-job CPU, memory, or wall-clock limit stopped the engine."""


MAX_PRIORITY = 10
MIN_PRIORITY = -10
ACTIVE_STATUSES = frozenset({"queued", "running", "cancelling", "paused"})


def _memory_limit_resource() -> int | None:
    """Return the enforceable per-process memory resource for this POSIX host.

    Darwin reserves a large virtual address map before an engine starts, making a
    practical ``RLIMIT_AS`` prevent ``exec``. Its ``RLIMIT_DATA`` only governs
    ``sbrk`` growth and also prevents PARI/GP from starting at practical limits, while
    ``RLIMIT_RSS`` is advisory. Darwin therefore uses the process-group RSS watchdog
    below. Linux uses the stronger kernel-enforced total-address-space limit.
    """

    return None if sys.platform == "darwin" else resource.RLIMIT_AS


def _memory_limit_label() -> str:
    return "resident-set" if sys.platform == "darwin" else "address-space"


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
        # Explicit priority queue (workspace tranche): entries are
        # (job_id, priority, sequence, resume); dispatch picks the highest priority,
        # then the lowest sequence, while never exceeding MAX_PARALLEL_JOBS.
        self._pending: list[tuple[str, int, int, bool]] = []
        self._running: set[str] = set()
        self._sequence = 0
        self._paused_since: dict[str, float] = {}
        self._paused_total: dict[str, float] = {}
        self._limit_hits: dict[str, str] = {}

    def create(
        self,
        *,
        expression: str,
        number: int,
        requested_backend: str,
        threads: int,
        pretest_level: int,
        trial_bound: int,
        cado_parameter_size: int | None,
        parent_job_id: str | None = None,
        priority: int = 0,
        cpu_seconds: int | None = None,
        memory_mb: int | None = None,
        wall_seconds: int | None = None,
        ecm_b1: int | None = None,
        ecm_b2: str | None = None,
        ecm_curves: int | None = None,
        ecm_sigma: str | None = None,
        ecm_param: int | None = None,
        distributed: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not 2 <= trial_bound <= 100_000_000:
            raise ValueError("Trial-division bound must be between 2 and 100,000,000")
        if not MIN_PRIORITY <= priority <= MAX_PRIORITY:
            raise ValueError(f"Priority must be between {MIN_PRIORITY} and {MAX_PRIORITY}")
        for label, value, upper in (
            ("CPU-second limit", cpu_seconds, 30 * 86400),
            ("memory limit (MB)", memory_mb, 4 * 1024 * 1024),
            ("wall-clock limit", wall_seconds, 30 * 86400),
        ):
            if value is not None and not 1 <= value <= upper:
                raise ValueError(f"The {label} must be between 1 and {upper:,}")
        if requested_backend.startswith("adapter:"):
            adapter = ADAPTER_REGISTRY.get(requested_backend.removeprefix("adapter:"))
            if adapter is None or adapter.builtin:
                raise ValueError("Unknown engine adapter")
            if not adapter.executable():
                raise RuntimeError(f"The '{adapter.command}' executable is not available")
        job_id = uuid.uuid4().hex
        absolute = abs(number)
        digits = len(str(absolute))
        selected = requested_backend
        if requested_backend == "auto":
            selected = "yafu" if digits < DEFAULT_CADO_THRESHOLD else "hybrid"
        if selected in {"cado", "hybrid"} and not executable_path("cado-nfs.py"):
            raise RuntimeError("cado-nfs.py is not available")
        yafu_modes = {
            "yafu", "hybrid", "cross_verify", "yafu_rho",
            "yafu_pm1", "yafu_pp1", "yafu_ecm", "yafu_siqs",
            "yafu_nfs", "yafu_snfs", "yafu_fermat",
        }
        if selected == "ecm_campaign" and not executable_path("ecm"):
            raise RuntimeError("GMP-ECM is required for an ECM campaign")
        if selected == "squfof" and number >= 2**62:
            raise RuntimeError(
                "SQUFOF here is limited to inputs below 2^62; choose SIQS or NFS instead"
            )
        if selected in yafu_modes and not executable_path("yafu"):
            raise RuntimeError("YAFU is not available")
        if selected in {"msieve", "cross_verify"} and not executable_path("msieve"):
            raise RuntimeError("Msieve is not available")
        if selected == "pari_trial" and not executable_path("gp"):
            raise RuntimeError("PARI/GP is not available")

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
                "trial_bound": trial_bound,
                "cado_parameter_size": parameter.size if parameter else None,
                "cado_parameter_file": str(parameter.path) if parameter else None,
                "workdir": str(workdir),
                "log_path": str(log_path),
                "warning": warning,
                "parent_job_id": parent_job_id,
                "priority": priority,
                "cpu_seconds": cpu_seconds,
                "memory_mb": memory_mb,
                "wall_seconds": wall_seconds,
                "ecm_b1": ecm_b1,
                "ecm_b2": ecm_b2,
                "ecm_curves": ecm_curves,
                "ecm_sigma": ecm_sigma,
                "ecm_param": ecm_param,
                "distributed_json": json.dumps(distributed) if distributed else None,
            }
        )
        self._submit(job_id, resume=False)
        return job

    def _submit(self, job_id: str, *, resume: bool) -> None:
        job = self.database.get_job(job_id)
        priority = int(job.get("priority") or 0) if job else 0
        event = threading.Event()
        with self._lock:
            self._cancel_events[job_id] = event
            self._futures[job_id] = Future()
            self._sequence += 1
            self._pending.append((job_id, priority, self._sequence, resume))
        self._dispatch()

    def _dispatch(self) -> None:
        """Start pending jobs in priority order up to MAX_PARALLEL_JOBS."""

        while True:
            with self._lock:
                if not self._pending or len(self._running) >= MAX_PARALLEL_JOBS:
                    return
                self._pending.sort(key=lambda item: (-item[1], item[2]))
                job_id, _, _, resume = self._pending.pop(0)
                future = self._futures.get(job_id)
                if future is None or not future.set_running_or_notify_cancel():
                    continue
                self._running.add(job_id)
            self.executor.submit(self._execute, job_id, resume, future)

    def _execute(self, job_id: str, resume: bool, future: Future[None]) -> None:
        try:
            self._run(job_id, resume)
        except BaseException as exc:  # pragma: no cover - defensive
            future.set_exception(exc)
        else:
            future.set_result(None)
        finally:
            with self._lock:
                self._running.discard(job_id)
            self._dispatch()

    def _limits_preexec(self, job: dict[str, Any]):
        """Return a ``preexec_fn`` applying CPU and host-appropriate memory limits."""

        cpu = job.get("cpu_seconds")
        memory = job.get("memory_mb")
        if not cpu and not memory:
            return None

        def apply() -> None:
            if cpu:
                resource.setrlimit(resource.RLIMIT_CPU, (int(cpu), int(cpu) + 5))
            memory_resource = _memory_limit_resource()
            if memory and memory_resource is not None:
                limit = int(memory) * 1024 * 1024
                resource.setrlimit(memory_resource, (limit, limit))

        return apply

    @staticmethod
    def _process_group_rss_kb(process_group: int) -> int | None:
        """Return Darwin RSS for every process in a process group, in KiB."""

        try:
            result = subprocess.run(
                ["ps", "-axo", "pgid=,rss="],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "LC_ALL": "C"},
            )
        except (OSError, subprocess.SubprocessError):
            return None
        total = 0
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) != 2:
                continue
            try:
                pgid, rss = (int(value) for value in fields)
            except ValueError:
                continue
            if pgid == process_group:
                total += rss
        return total

    def _watch_memory(
        self, job_id: str, process: subprocess.Popen[str], memory_mb: int
    ) -> None:
        """Enforce a process-group resident-set limit on Darwin."""

        limit_kb = memory_mb * 1024
        while process.poll() is None:
            rss_kb = self._process_group_rss_kb(process.pid)
            if rss_kb is not None and rss_kb > limit_kb:
                with self._lock:
                    self._limit_hits[job_id] = "memory"
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                return
            time.sleep(0.25)

    def _watch_wall_clock(self, job_id: str, process: subprocess.Popen[str], wall: int) -> None:
        """Terminate the process group once active (unpaused) time exceeds ``wall``."""

        started = time.monotonic()
        while process.poll() is None:
            time.sleep(0.25)
            with self._lock:
                paused_since = self._paused_since.get(job_id)
                paused_total = self._paused_total.get(job_id, 0.0)
            if paused_since is not None:
                continue
            if time.monotonic() - started - paused_total > wall:
                with self._lock:
                    self._limit_hits[job_id] = "wall"
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                return

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
        current_job = self.database.get_job(job_id) or job
        command_history = [*current_job.get("command_history", []), command]
        self.database.update_job(
            job_id,
            command_json=json.dumps(command),
            command_history_json=json.dumps(command_history),
            phase="Starting process",
        )
        self._append_log(job, f"\n$ {' '.join(command)}\n")
        limits = self.database.get_job(job_id) or job
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
            preexec_fn=self._limits_preexec(limits),
        )
        with self._lock:
            self._processes[job_id] = process
            self._limit_hits.pop(job_id, None)
        self.database.update_job(job_id, pid=process.pid)
        if limits.get("wall_seconds"):
            threading.Thread(
                target=self._watch_wall_clock,
                args=(job_id, process, int(limits["wall_seconds"])),
                name=f"wall-clock-{job_id[:8]}",
                daemon=True,
            ).start()
        if sys.platform == "darwin" and limits.get("memory_mb"):
            threading.Thread(
                target=self._watch_memory,
                args=(job_id, process, int(limits["memory_mb"])),
                name=f"memory-{job_id[:8]}",
                daemon=True,
            ).start()
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
                limit_hit = self._limit_hits.pop(job_id, None)
            self.database.update_job(job_id, pid=None)
        if event.is_set():
            raise Cancelled("Job cancelled")
        if limit_hit == "wall":
            raise LimitExceeded(
                f"The wall-clock limit of {limits.get('wall_seconds')} seconds was exceeded"
            )
        if limit_hit == "memory":
            raise LimitExceeded(
                f"The engine exceeded the {limits.get('memory_mb')} MB "
                f"{_memory_limit_label()} limit"
            )
        if limits.get("cpu_seconds") and return_code in {-signal.SIGXCPU, -signal.SIGKILL}:
            raise LimitExceeded(
                f"The CPU-time limit of {limits.get('cpu_seconds')} seconds was exceeded"
            )
        if limits.get("memory_mb") and return_code in {-signal.SIGABRT, -signal.SIGSEGV}:
            raise LimitExceeded(
                f"The engine aborted under the {limits.get('memory_mb')} MB "
                f"{_memory_limit_label()} limit"
            )
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
        algorithm: str | None = None,
    ) -> tuple[list[dict[str, object]], int]:
        command = ["yafu", "-threads", str(job["threads"]), "-terse"]
        # Without a siever directory YAFU cannot run the number field sieve at all: it
        # reports "possibly bad path to siever" for every relation file and exits
        # non-zero having found nothing, which reads as an engine crash rather than a
        # missing dependency. Pass the discovered directory rather than relying on
        # whatever ggnfs_dir the user's own yafu.ini happens to contain.
        sievers = siever_directory()
        if sievers is not None:
            command += ["-ggnfs_dir", str(sievers).rstrip("/") + "/"]
        if pretest_only:
            command += ["-pretest", str(job["pretest_level"])]
        expression = f"{algorithm}({number})" if algorithm else f"factor({number})"
        return_code, output = self._run_process(
            job,
            command,
            cwd=Path(job["workdir"]),
            stdin_text=f"{expression}\nquit\n",
        )
        if return_code != 0:
            raise RuntimeError(f"YAFU exited with status {return_code}")
        records = [{**record, "engine": "YAFU"} for record in parse_yafu_factors(output)]
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
        return [{**record, "engine": "Msieve"} for record in parse_msieve_factors(output)]

    def _run_tune(self, job: dict[str, Any]) -> list[dict[str, object]]:
        """Run YAFU's own `tune` and report the crossover it measures.

        The measurement is performed entirely by YAFU. Numerisect supplies the
        siever directory and thread count, reads the ``tune_info`` line YAFU writes
        to ``yafu.ini`` in the job directory, and reports a suggested threshold. It
        never rewrites its own configuration.

        Raises:
            RuntimeError: If YAFU or the GGNFS sievers are unavailable, or the run
                produced no tune_info line.
        """

        if not executable_path("yafu"):
            raise RuntimeError("YAFU is required to tune the engine thresholds")
        sievers = siever_directory()
        if sievers is None:
            raise RuntimeError(
                "YAFU's tune needs the GGNFS lattice sievers, and no usable one was "
                "found. Install them, or set NUMERISECT_GGNFS_DIR to a directory "
                "holding gnfs-lasieve4I*e that runs on this CPU."
            )
        workdir = Path(job["workdir"])
        command = [
            "yafu", "-threads", str(job["threads"]), "-ggnfs_dir", str(sievers).rstrip("/") + "/",
        ]
        self.database.update_job(
            job["id"],
            phase="YAFU tune: measuring the SIQS/NFS crossover on this machine",
            progress=5,
        )
        return_code, output = self._run_process(
            job, command, cwd=workdir, stdin_text="tune()\nquit\n"
        )
        if return_code != 0:
            raise RuntimeError(f"YAFU tune exited with status {return_code}")
        # YAFU records the result in yafu.ini next to where it ran.
        ini = workdir / "yafu.ini"
        text = output
        if ini.is_file():
            text = f"{output}\n{ini.read_text(encoding='utf-8', errors='replace')}"
        try:
            parsed = parse_tune_info(text)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
        suggestion = tune_recommendation(parsed, DEFAULT_CADO_THRESHOLD)
        self.database.update_job(
            job["id"],
            warning=(
                f"Measured crossover {suggestion['measured_crossover_digits']} digits; "
                f"current threshold {suggestion['current_threshold']}. "
                + (suggestion["apply_with"] or "no change suggested")
            ),
        )
        # A tuning run produces a measurement, not a factorization.
        return [
            {
                "value": str(suggestion["suggested_threshold"] or DEFAULT_CADO_THRESHOLD),
                "digits": 0,
                "status": "measurement",
                "engine": f"YAFU tune ({suggestion['cpu'] or 'this machine'})",
            }
        ]

    def _run_ecm_campaign(self, job: dict[str, Any], number: int) -> list[dict[str, object]]:
        """Run a resumable GMP-ECM campaign.

        GMP-ECM performs the whole computation, including deciding whether the
        factor and cofactor are prime. Its own ``-save``/``-resume`` residue files
        make the campaign resumable, and ``-c`` bounds the curve count.

        Args:
            job: The job row, carrying ``ecm_b1``, ``ecm_b2``, ``ecm_curves``,
                ``ecm_sigma`` and ``ecm_param``.
            number: The integer to work on.

        Returns:
            Factor records as reported and classified by GMP-ECM.

        Raises:
            RuntimeError: If GMP-ECM is unavailable or fails.
        """

        if not executable_path("ecm"):
            raise RuntimeError("GMP-ECM is not installed")
        workdir = Path(job["workdir"])
        residues = workdir / "ecm-residues.txt"
        b1 = int(job.get("ecm_b1") or 50_000)
        b2 = str(job.get("ecm_b2") or "").strip()
        curves = int(job.get("ecm_curves") or 100)
        sigma = str(job.get("ecm_sigma") or "").strip()
        param = job.get("ecm_param")

        command: list[str] = ["ecm", "-c", str(curves)]
        # Resume from a previous run's stage-1 residues when they exist, so a
        # cancelled campaign continues instead of starting over.
        if residues.is_file() and residues.stat().st_size > 0:
            command += ["-resume", str(residues)]
        else:
            command += ["-save", str(residues)]
        if sigma:
            command += ["-sigma", sigma]
        if param is not None:
            command += ["-param", str(int(param))]
        command.append(str(b1))
        if b2:
            command.append(b2)

        self.database.update_job(
            job["id"],
            phase=f"GMP-ECM campaign: {curves} curves at B1={b1:,}",
            progress=10,
        )
        return_code, output = self._run_process(
            job, command, cwd=workdir, stdin_text=f"{number}\n"
        )
        parsed = parse_ecm_output(output)
        self.database.update_job(
            job["id"], ecm_curves_done=int(parsed["curves_run"] or 0)
        )
        # GMP-ECM uses a bitwise exit status; bit 1 means a factor was found.
        # Any other nonzero status without a factor is a genuine failure.
        if not parsed["factors"] and return_code not in (0,):
            raise RuntimeError(f"GMP-ECM exited with status {return_code}")
        candidates = [int(str(record["value"])) for record in parsed["factors"]]
        if parsed["cofactor"]:
            candidates.append(int(str(parsed["cofactor"])))
        if not candidates:
            return []
        # GMP-ECM peels factors off across curves, so the raw list can overlap and
        # need not multiply to the input. PARI/GP reconciles it into a consistent
        # decomposition and decides primality; nothing is divided out in Python.
        reconciled = reconcile_factors(number, candidates)
        records: list[dict[str, object]] = []
        for entry in reconciled["factors"]:
            for _ in range(int(entry["exponent"])):
                records.append(
                    {
                        "value": entry["value"],
                        "digits": len(entry["value"]),
                        "status": "prime" if entry["prime"] else "composite",
                        "engine": "GMP-ECM",
                    }
                )
        cofactor = str(reconciled["cofactor"])
        if cofactor != "1":
            records.append(
                {
                    "value": cofactor,
                    "digits": len(cofactor),
                    "status": "prime" if reconciled["cofactor_prime"] else "composite",
                    "engine": "GMP-ECM cofactor",
                }
            )
        return records

    def _label_primality(
        self, job: dict[str, Any], values: list[int], engine: str
    ) -> list[dict[str, object]]:
        """Label each value prime or composite using PARI/GP's isprime.

        Primality is decided by the engine, never in Python.

        Raises:
            RuntimeError: If GP fails or does not label every value.
        """

        program = (
            "v=[" + ",".join(str(value) for value in values) + "];"
            'for(i=1,#v,print("NPRIME:",v[i],"|",isprime(v[i])));'
            'print("NPRIME_DONE:",#v);quit\n'
        )
        return_code, output = self._run_process(
            job, ["gp", "-fq"], cwd=Path(job["workdir"]), stdin_text=program
        )
        if return_code != 0:
            raise RuntimeError(f"PARI/GP primality labelling exited with status {return_code}")
        labels: dict[str, bool] = {}
        done: int | None = None
        for line in output.splitlines():
            if line.startswith("NPRIME_DONE:"):
                text = line.removeprefix("NPRIME_DONE:").strip()
                done = int(text) if text.isdigit() else None
            elif line.startswith("NPRIME:"):
                fields = line.removeprefix("NPRIME:").split("|")
                if len(fields) != 2 or not all(re.fullmatch(r"\d+", item.strip()) for item in fields):
                    raise RuntimeError("PARI/GP returned an invalid primality record")
                labels[fields[0].strip()] = fields[1].strip() == "1"
        if done != len(values) or len(labels) != len(values):
            raise RuntimeError("PARI/GP did not label every factor")
        return [
            {
                "value": str(value),
                "digits": len(str(value)),
                "status": "prime" if labels[str(value)] else "composite",
                "engine": engine,
            }
            for value in values
        ]

    def _run_pari_trial(
        self, job: dict[str, Any], number: int
    ) -> list[dict[str, object]]:
        bound = int(job["trial_bound"])
        program = (
            f"f=factor({number},{bound + 1});"
            "for(i=1,matsize(f)[1],"
            'print("NTRIAL:",f[i,1],"|",f[i,2],"|",isprime(f[i,1])));'
            'print("NTRIAL_DONE:",matsize(f)[1]);quit\n'
        )
        return_code, output = self._run_process(
            job, ["gp", "-fq"], cwd=Path(job["workdir"]), stdin_text=program
        )
        if return_code != 0:
            raise RuntimeError(f"PARI/GP trial division exited with status {return_code}")
        records: list[dict[str, object]] = []
        rows = 0
        done: int | None = None
        for line in output.splitlines():
            if line.startswith("NTRIAL_DONE:"):
                value = line.removeprefix("NTRIAL_DONE:")
                done = int(value) if value.isdigit() else None
            elif line.startswith("NTRIAL:"):
                fields = line.removeprefix("NTRIAL:").split("|")
                if len(fields) != 3 or not all(re.fullmatch(r"\d+", item) for item in fields):
                    raise RuntimeError("PARI/GP returned an invalid trial-division record")
                factor, exponent, proven = map(int, fields)
                rows += 1
                records.extend(
                    {
                        "value": str(factor),
                        "digits": len(str(factor)),
                        "status": "prime" if proven else "composite",
                        "engine": f"PARI/GP bounded trial division (B={bound})",
                    }
                    for _ in range(exponent)
                )
        if done is None or done != rows or not records:
            raise RuntimeError("PARI/GP returned an incomplete trial-division result")
        return records

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
            # CADO parses key=value options only when they are CONTIGUOUS with the
            # integer, so every flag goes first and the integer is followed
            # immediately by the parameter assignments. Interleaving them makes
            # cado-nfs.py reject the whole invocation.
            command = [
                "cado-nfs.py",
                "-p",
                parameter_path,
                "-t",
                str(job["threads"]),
                "--workdir",
                str(cado_dir),
            ]
            # Distributed sieving: CADO's own server and client parameters, already
            # validated. Numerisect adds no networking of its own.
            assignments: list[str] = []
            plan = job.get("distributed_json")
            if plan:
                try:
                    settings = json.loads(plan)
                except (TypeError, json.JSONDecodeError):
                    settings = None
                if settings:
                    client_threads = settings.get("client_threads")
                    if client_threads:
                        command += ["--client-threads", str(int(client_threads))]
                    assignments = list(settings.get("parameters") or [])
            if not any(item.startswith("slaves.hostnames=") for item in assignments):
                # Required whenever -p is passed; see the note in distributed.py.
                assignments.append("slaves.hostnames=localhost")
            command += [str(number), *assignments]
        return_code, output = self._run_process(
            job, command, cwd=Path(job["workdir"])
        )
        if return_code != 0:
            raise RuntimeError(f"CADO-NFS exited with status {return_code}")
        records = parse_cado_factors(output, number)
        if not records:
            raise RuntimeError("CADO-NFS finished without a verifiable factorization")
        return [{**record, "engine": "CADO-NFS"} for record in records]

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
            factors.append(
                {"value": "-1", "digits": 1, "status": "unit", "engine": "Numerisect"}
            )
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
                            "engine": "YAFU",
                        }
                    )
            elif backend == "msieve":
                factors.extend(self._run_msieve(job, number))
            elif backend == "pari_trial":
                factors.extend(self._run_pari_trial(job, number))
            elif backend == "cross_verify":
                known, residual = self._run_yafu(job, number, pretest_only=False)
                if residual != 1:
                    known.append(
                        {
                            "value": str(residual),
                            "digits": len(str(residual)),
                            "status": "composite",
                            "engine": "YAFU",
                        }
                    )
                independent = self._run_msieve(job, number)
                left = sorted(int(str(item["value"])) for item in known)
                right = sorted(int(str(item["value"])) for item in independent)
                if left != right:
                    raise RuntimeError(
                        "YAFU and Msieve returned different factor multisets; "
                        "no verified result was accepted"
                    )
                factors.extend(
                    {**item, "engine": "YAFU + Msieve (independently verified)"}
                    for item in known
                )
            elif backend == "tune":
                factors.extend(self._run_tune(job))
            elif backend == "ecm_campaign":
                found = self._run_ecm_campaign(job, number)
                if not found:
                    raise RuntimeError(
                        "The ECM campaign completed its curves without finding a factor. "
                        "This is inconclusive: raise B1 or the curve count, or switch to "
                        "SIQS or NFS."
                    )
                factors.extend(found)
            elif backend == "squfof":
                self.database.update_job(
                    job_id, phase="SQUFOF cycle (numerisect-squfof)", progress=20
                )
                outcome = squfof(number, timeout=3600)
                if outcome["status"] != "found":
                    raise RuntimeError(
                        "SQUFOF did not split the input within its iteration limit; "
                        "this is inconclusive, not a primality claim"
                    )
                parts = [int(str(outcome["factor"])), int(str(outcome["cofactor"]))]
                factors.extend(
                    self._label_primality(job, parts, "numerisect-squfof (C/GMP)")
                )
            elif backend.startswith("yafu_"):
                algorithm = {
                    "yafu_rho": "rho",
                    "yafu_pm1": "pm1",
                    "yafu_pp1": "pp1",
                    "yafu_ecm": "ecm",
                    "yafu_siqs": "siqs",
                    "yafu_nfs": "nfs",
                    "yafu_snfs": "snfs",
                    "yafu_fermat": "fermat",
                }[backend]
                known, residual = self._run_yafu(
                    job, number, pretest_only=False, algorithm=algorithm
                )
                factors.extend(known)
                if residual != 1:
                    factors.append(
                        {
                            "value": str(residual),
                            "digits": len(str(residual)),
                            "status": "composite",
                            "engine": f"YAFU {algorithm}",
                        }
                    )
            elif backend == "cado":
                self.database.update_job(job_id, engine_target=str(number))
                factors.extend(self._run_cado(job, number, resume=False))
            elif backend.startswith("adapter:"):
                factors.extend(self._run_adapter(job, number, backend.removeprefix("adapter:")))
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
                                    "engine": "YAFU",
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
        except LimitExceeded as exc:
            self._append_log(job, f"\nResource limit: {exc}\n")
            self.database.update_job(
                job_id,
                status="failed",
                phase="Stopped by resource limit",
                error=str(exc),
                failure_reason="limit_exceeded",
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
                self._paused_since.pop(job_id, None)
                self._paused_total.pop(job_id, None)

    def cancel(self, job_id: str) -> dict[str, Any]:
        job = self.database.get_job(job_id)
        if not job:
            raise KeyError(job_id)
        if job["status"] not in ACTIVE_STATUSES:
            return job
        if job["status"] == "paused":
            self._continue_process(job_id)
        with self._lock:
            event = self._cancel_events.get(job_id)
            process = self._processes.get(job_id)
            future = self._futures.get(job_id)
            self._pending = [item for item in self._pending if item[0] != job_id]
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
        if job["status"] in ACTIVE_STATUSES:
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
            self._pending.clear()
        for job_id, process in active:
            event = self._cancel_events.get(job_id)
            if event:
                event.set()
            try:
                os.killpg(process.pid, signal.SIGCONT)
                os.killpg(process.pid, signal.SIGINT)
            except ProcessLookupError:
                pass
        self.executor.shutdown(wait=False, cancel_futures=True)

    # ----- workspace tranche: priorities, queue order, pause/resume, adapters ---------

    def queue_snapshot(self) -> list[dict[str, Any]]:
        """Return queued jobs in dispatch order (highest priority, then oldest)."""

        with self._lock:
            ordered = sorted(self._pending, key=lambda item: (-item[1], item[2]))
        result: list[dict[str, Any]] = []
        for position, (job_id, _priority, _, resume) in enumerate(ordered, start=1):
            job = self.database.get_job(job_id)
            if job:
                result.append({**job, "queue_position": position, "resume": resume})
        return result

    def set_priority(self, job_id: str, priority: int) -> dict[str, Any]:
        """Change a job's priority; queued jobs are re-sorted immediately."""

        if not MIN_PRIORITY <= priority <= MAX_PRIORITY:
            raise ValueError(f"Priority must be between {MIN_PRIORITY} and {MAX_PRIORITY}")
        job = self.database.get_job(job_id)
        if not job:
            raise KeyError(job_id)
        with self._lock:
            self._pending = [
                (identifier, priority if identifier == job_id else item_priority, seq, resume)
                for identifier, item_priority, seq, resume in self._pending
            ]
        updated = self.database.update_job(job_id, priority=priority)
        self._dispatch()
        return updated  # type: ignore[return-value]

    def reorder(self, job_ids: list[str]) -> list[dict[str, Any]]:
        """Run the listed queued jobs in the given order.

        Every listed job must currently be queued.  The jobs receive the highest
        priority among them and fresh sequence numbers in list order, so their
        relative order is exact while unrelated queued jobs keep their own priority.
        """

        if len(set(job_ids)) != len(job_ids):
            raise ValueError("Duplicate job identifiers in reorder request")
        with self._lock:
            pending = {item[0]: item for item in self._pending}
            missing = [job_id for job_id in job_ids if job_id not in pending]
            if missing:
                raise ValueError("Only queued jobs can be reordered")
            top = max(pending[job_id][1] for job_id in job_ids) if job_ids else 0
            remaining = [item for item in self._pending if item[0] not in set(job_ids)]
            reordered = []
            for job_id in job_ids:
                self._sequence += 1
                reordered.append((job_id, top, self._sequence, pending[job_id][3]))
            self._pending = remaining + reordered
        for job_id in job_ids:
            self.database.update_job(job_id, priority=top)
        return self.queue_snapshot()

    def _continue_process(self, job_id: str) -> None:
        with self._lock:
            process = self._processes.get(job_id)
            paused_since = self._paused_since.pop(job_id, None)
            if paused_since is not None:
                self._paused_total[job_id] = (
                    self._paused_total.get(job_id, 0.0) + time.monotonic() - paused_since
                )
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGCONT)
            except ProcessLookupError:
                pass

    def pause(self, job_id: str) -> dict[str, Any]:
        """Suspend a running engine with SIGSTOP on its process group."""

        job = self.database.get_job(job_id)
        if not job:
            raise KeyError(job_id)
        if job["status"] == "paused":
            return job
        if job["status"] != "running":
            raise ValueError("Only a running job can be paused")
        with self._lock:
            process = self._processes.get(job_id)
        if not process or process.poll() is not None:
            raise ValueError("The job has no running engine process to pause")
        try:
            os.killpg(process.pid, signal.SIGSTOP)
        except ProcessLookupError as exc:
            raise ValueError("The engine process already exited") from exc
        with self._lock:
            self._paused_since[job_id] = time.monotonic()
        self._append_log(job, "\n--- Paused (SIGSTOP) ---\n")
        return self.database.update_job(  # type: ignore[return-value]
            job_id, status="paused", paused_at=utc_now()
        )

    def resume_paused(self, job_id: str) -> dict[str, Any]:
        """Continue a paused engine with SIGCONT."""

        job = self.database.get_job(job_id)
        if not job:
            raise KeyError(job_id)
        if job["status"] != "paused":
            raise ValueError("Only a paused job can be continued")
        self._continue_process(job_id)
        self._append_log(job, "\n--- Continued (SIGCONT) ---\n")
        return self.database.update_job(  # type: ignore[return-value]
            job_id, status="running", paused_at=None
        )

    def _run_adapter(
        self, job: dict[str, Any], number: int, name: str
    ) -> list[dict[str, object]]:
        """Run a declarative user adapter and label its factors with PARI ``isprime``."""

        adapter = ADAPTER_REGISTRY.get(name)
        if adapter is None or adapter.builtin:
            raise RuntimeError(f"Unknown engine adapter: {name}")
        request = {
            "number": str(number),
            "threads": str(job["threads"]),
            "workdir": str(job["workdir"]),
            "trial_bound": str(job["trial_bound"]),
            "pretest_level": str(job["pretest_level"]),
            "parameter_file": job.get("cado_parameter_file") or "",
        }
        return_code, output = self._run_process(
            job,
            adapter.build_command(request),
            cwd=Path(job["workdir"]),
            stdin_text=adapter.build_stdin(request),
        )
        if return_code != 0:
            raise RuntimeError(f"Adapter '{name}' exited with status {return_code}")
        records = adapter.parse_factors(output, number)
        if not records:
            raise RuntimeError(f"Adapter '{name}' produced no parsable factors")
        values = [int(str(record["value"])) for record in records]
        if any(value in {0, 1, -1} for value in values):
            raise RuntimeError(f"Adapter '{name}' returned a unit or zero as a factor")
        program = (
            "v=[" + ",".join(str(abs(value)) for value in values) + "];"
            'for(i=1,#v,print("ADAPTER_PRIME:",v[i],"|",isprime(v[i])));'
            'print("ADAPTER_DONE:",#v);quit\n'
        )
        code, verdicts = self._run_process(
            job, ["gp", "-fq"], cwd=Path(job["workdir"]), stdin_text=program
        )
        if code != 0:
            raise RuntimeError("PARI/GP could not classify the adapter factors")
        proven: dict[str, bool] = {}
        done: int | None = None
        for line in verdicts.splitlines():
            if line.startswith("ADAPTER_PRIME:"):
                value, flag = line.removeprefix("ADAPTER_PRIME:").split("|", 1)
                proven[value] = flag.strip() == "1"
            elif line.startswith("ADAPTER_DONE:"):
                text = line.removeprefix("ADAPTER_DONE:").strip()
                done = int(text) if text.isdigit() else None
        if done != len(values) or len(proven) != len(set(map(abs, values))):
            raise RuntimeError("PARI/GP returned an incomplete adapter classification")
        labelled: list[dict[str, object]] = []
        for record in records:
            value = str(abs(int(str(record["value"]))))
            labelled.append(
                {
                    **record,
                    "value": value,
                    "status": "prime" if proven[value] else "composite",
                    "engine": f"adapter:{name} (PARI/GP isprime)",
                }
            )
        return labelled
