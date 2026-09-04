from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .config import (
    DATABASE_PATH,
    DEFAULT_CADO_THRESHOLD,
    DEFAULT_PRETEST_LEVEL,
    OUTPUT_DIR,
    STATIC_DIR,
    ensure_state_dirs,
    prepend_managed_tools_to_path,
)
from .database import Database
from .engines import discover_cado_parameters, executable_path
from .evaluator import ExpressionError, evaluate_arbitrary_integer, evaluate_integer
from .jobs import JobManager
from .installer import EngineInstaller
from .outputs import safe_output_path, save_prime_output
from .primes import (
    PrimeEngineError,
    classify_prime,
    generate_primes,
    generate_special_primes,
    nth_prime,
    prime_count,
    prime_gaps,
    primality_result,
    prime_tuples_in_range,
    primes_after,
    primes_before,
    primes_in_range,
)


ensure_state_dirs()
prepend_managed_tools_to_path()
database = Database(DATABASE_PATH)
manager = JobManager(database)
installer = EngineInstaller()


@asynccontextmanager
async def lifespan(_: FastAPI):
    installer.start_if_needed()
    yield
    manager.shutdown()


app = FastAPI(
    title="Numerisect",
    version=__version__,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
)
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


Backend = Literal["auto", "yafu", "hybrid", "cado", "msieve"]


class JobRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=100_000)
    backend: Backend = "auto"
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    pretest_level: int = Field(default=DEFAULT_PRETEST_LEVEL, ge=1, le=100)
    cado_parameter_size: int | None = Field(default=None, ge=1, le=10000)


class PrimeCheckRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=100_000)
    mode: Literal["fast", "proven"] = "proven"
    certificate: bool = False


class PrimeClassificationRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=100_000)
    per_test_seconds: int = Field(default=2, ge=1, le=10)


class PrimeGenerateRequest(BaseModel):
    count: int = Field(ge=1, le=500)
    digits: int = Field(ge=1, le=10_000)


class SpecialPrimeRequest(PrimeGenerateRequest):
    kind: Literal["safe", "sophie", "blum", "congruence"]
    modulus: int | None = Field(default=None, ge=2, le=1_000_000)
    remainder: int | None = None


class PrimeRangeRequest(BaseModel):
    start: str = Field(min_length=1, max_length=100_000)
    end: str = Field(min_length=1, max_length=100_000)
    limit: int = Field(default=10_000, ge=1, le=100_000)


class PrimesAfterRequest(BaseModel):
    start: str = Field(min_length=1, max_length=100_000)
    count: int = Field(ge=1, le=100_000)


class PrimeIndexRequest(BaseModel):
    index: int = Field(ge=1, le=100_000_000_000)


class PrimeCountRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=100_000)


class PrimeGapRequest(PrimeRangeRequest):
    pass


class PrimeTupleRequest(BaseModel):
    start: str = Field(min_length=1, max_length=100_000)
    end: str = Field(min_length=1, max_length=100_000)
    offsets: list[int] = Field(min_length=2, max_length=32)
    limit: int = Field(default=10_000, ge=1, le=100_000)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/capabilities")
def capabilities() -> dict[str, object]:
    parameters = discover_cado_parameters()
    return {
        "version": __version__,
        "cpu_count": os.cpu_count() or 1,
        "cado_threshold": DEFAULT_CADO_THRESHOLD,
        "engines": {
            name: {"available": bool(path), "path": path}
            for name, path in {
                "yafu": executable_path("yafu"),
                "msieve": executable_path("msieve"),
                "cado": executable_path("cado-nfs.py"),
                "ecm": executable_path("ecm"),
                "pari/gp": executable_path("gp"),
            }.items()
        },
        "cado_parameters": [
            {"size": parameter.size, "path": str(parameter.path)}
            for parameter in parameters
        ],
        "setup": installer.status(),
    }


@app.get("/api/setup")
def setup_status() -> dict[str, object]:
    return installer.status()


@app.post("/api/setup/install", status_code=202)
def install_missing_engines() -> dict[str, object]:
    installer.start_if_needed()
    return installer.status()


@app.get("/api/setup/log")
def setup_log() -> dict[str, str]:
    path = installer.log_path
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    return {"text": text}


@app.post("/api/primes/check")
def check_prime(request: PrimeCheckRequest) -> dict[str, object]:
    try:
        number = evaluate_arbitrary_integer(request.expression)
    except ExpressionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        result = primality_result(
            number, mode=request.mode, certificate=request.certificate
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PrimeEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    certificate = str(result.pop("certificate"))
    lines = [
        f"Input: {number}",
        f"Mode: {request.mode}",
        f"Classification: {result['classification']}",
        str(result["note"]),
    ]
    if certificate:
        lines.extend(["", "Primality certificate", "---------------------", certificate])
    path = save_prime_output(
        "primality",
        "Primality check",
        lines,
    )
    result["output_file"] = path.name
    result["certificate_included"] = bool(certificate)
    return result


@app.post("/api/primes/classify")
def classify_prime_number(request: PrimeClassificationRequest) -> dict[str, object]:
    try:
        number = evaluate_arbitrary_integer(request.expression)
        result = classify_prime(number, per_test_seconds=request.per_test_seconds)
    except (ExpressionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PrimeEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    lines = [
        f"Input: {number}",
        f"Verdict: {result['classification']}",
        f"Engine: {result['engine']}",
        "",
        "Matched classifications",
        "-----------------------",
    ]
    matches = result["matches"]
    if isinstance(matches, list) and matches:
        for item in matches:
            detail = f" — {item['detail']}" if item["detail"] else ""
            lines.append(f"{item['name']}{detail}: {item['description']}")
    else:
        lines.append("None")

    inconclusive = result["inconclusive"]
    if isinstance(inconclusive, list) and inconclusive:
        lines.extend(["", "Inconclusive classifications", "----------------------------"])
        for item in inconclusive:
            lines.append(f"{item['name']}: {item['detail']}")

    path = save_prime_output("prime-classification", "Prime classification", lines)
    result["output_file"] = path.name
    return result


@app.post("/api/primes/generate")
def create_primes(request: PrimeGenerateRequest) -> dict[str, object]:
    try:
        values = generate_primes(request.count, request.digits)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "generated-primes",
        f"{request.count} generated {request.digits}-digit primes",
        (str(value) for value in values),
    )
    return {
        "count": len(values),
        "digits": request.digits,
        "primes": [str(value) for value in values],
        "output_file": path.name,
        "note": "Generated values are distinct primes produced and proven by PARI/GP.",
    }


@app.post("/api/primes/generate-special")
def create_special_primes(request: SpecialPrimeRequest) -> dict[str, object]:
    try:
        values = generate_special_primes(
            request.count,
            request.digits,
            request.kind,
            request.modulus,
            request.remainder,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    label = {
        "safe": "safe primes",
        "sophie": "Sophie Germain primes",
        "blum": "Blum primes",
        "congruence": "modular primes",
    }[request.kind]
    detail = ""
    if request.kind == "congruence":
        detail = f" congruent to {request.remainder} modulo {request.modulus}"
    path = save_prime_output(
        "special-primes",
        f"{request.count} {request.digits}-digit {label}{detail}",
        (str(value) for value in values),
    )
    return {
        "kind": request.kind,
        "count": len(values),
        "digits": request.digits,
        "primes": [str(value) for value in values],
        "output_file": path.name,
        "note": f"Generated {label}; every returned value was rigorously proven by PARI/GP.",
    }


@app.post("/api/primes/range")
def create_prime_range(request: PrimeRangeRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        end = evaluate_arbitrary_integer(request.end)
        values, truncated, next_start = primes_in_range(start, end, request.limit)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "prime-range",
        f"Primes from {start} through {end}",
        (str(value) for value in values),
    )
    return {
        "start": str(start),
        "end": str(end),
        "count": len(values),
        "primes": [str(value) for value in values],
        "truncated": truncated,
        "next_start": str(next_start) if next_start is not None else None,
        "output_file": path.name,
        "note": "Every returned value was rigorously proven by PARI/GP.",
    }


@app.post("/api/primes/after")
def create_primes_after(request: PrimesAfterRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        values = primes_after(start, request.count)
    except (ExpressionError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "next-primes",
        f"{request.count} primes after {start}",
        (str(value) for value in values),
    )
    return {
        "start": str(start),
        "count": len(values),
        "primes": [str(value) for value in values],
        "output_file": path.name,
        "note": "Every returned value was rigorously proven by PARI/GP.",
    }


@app.post("/api/primes/before")
def create_primes_before(request: PrimesAfterRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        values = primes_before(start, request.count)
    except (ExpressionError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "previous-primes",
        f"{len(values)} primes before {start}",
        (str(value) for value in values),
    )
    note = "Every returned value was rigorously proven by PARI/GP."
    if len(values) < request.count:
        note += " The sequence reached the beginning of the positive primes."
    return {
        "start": str(start),
        "count": len(values),
        "primes": [str(value) for value in values],
        "output_file": path.name,
        "note": note,
    }


@app.post("/api/primes/nth")
def find_nth_prime(request: PrimeIndexRequest) -> dict[str, object]:
    try:
        value = nth_prime(request.index)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "nth-prime", f"Prime number {request.index}", [str(value)]
    )
    return {
        "label": f"p({request.index:,})",
        "value": str(value),
        "digits": len(str(value)),
        "output_file": path.name,
        "note": "Calculated by PARI/GP's indexed-prime table and sieve.",
    }


@app.post("/api/primes/count")
def count_primes(request: PrimeCountRequest) -> dict[str, object]:
    try:
        number = evaluate_arbitrary_integer(request.expression)
        value = prime_count(number)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "prime-count", f"Prime count through {number}", [f"pi({number}) = {value}"]
    )
    return {
        "label": f"π({number})",
        "value": str(value),
        "output_file": path.name,
        "note": "Exact count of positive primes less than or equal to the input.",
    }


@app.post("/api/primes/gaps")
def analyze_prime_gaps(request: PrimeGapRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        end = evaluate_arbitrary_integer(request.end)
        gaps, truncated, next_start = prime_gaps(start, end, request.limit)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    largest = max(gaps, key=lambda item: item["gap"], default=None)
    path = save_prime_output(
        "prime-gaps",
        f"Prime gaps from {start} through {end}",
        (
            f"{item['from']} -> {item['to']}  gap {item['gap']}"
            for item in gaps
        ),
    )
    return {
        "start": str(start),
        "end": str(end),
        "count": len(gaps),
        "gaps": [
            {"from": str(item["from"]), "to": str(item["to"]), "gap": item["gap"]}
            for item in gaps
        ],
        "largest": (
            {"from": str(largest["from"]), "to": str(largest["to"]), "gap": largest["gap"]}
            if largest
            else None
        ),
        "truncated": truncated,
        "next_start": str(next_start) if next_start is not None else None,
        "output_file": path.name,
        "note": "Gaps are measured between consecutive proven primes inside the interval.",
    }


@app.post("/api/primes/tuples")
def create_prime_tuples(request: PrimeTupleRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        end = evaluate_arbitrary_integer(request.end)
        tuples, truncated, next_start = prime_tuples_in_range(
            start, end, request.offsets, request.limit
        )
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    offsets = sorted(set(request.offsets))
    path = save_prime_output(
        "prime-tuples",
        f"Prime tuples with offsets {offsets} from {start} through {end}",
        ("  ".join(str(value) for value in values) for values in tuples),
    )
    return {
        "start": str(start),
        "end": str(end),
        "offsets": offsets,
        "count": len(tuples),
        "tuples": [[str(value) for value in values] for values in tuples],
        "truncated": truncated,
        "next_start": str(next_start) if next_start is not None else None,
        "output_file": path.name,
        "note": "Every member of every tuple was rigorously proven by PARI/GP.",
    }


@app.get("/api/outputs/{filename}")
def download_output(filename: str) -> FileResponse:
    path = safe_output_path(filename)
    if not path:
        raise HTTPException(status_code=404, detail="Output file not found")
    return FileResponse(path, filename=path.name, media_type="text/plain")


@app.post("/api/jobs", status_code=202)
def create_job(request: JobRequest) -> dict[str, object]:
    try:
        number = evaluate_integer(request.expression)
        return manager.create(
            expression=request.expression,
            number=number,
            requested_backend=request.backend,
            threads=request.threads,
            pretest_level=request.pretest_level,
            cado_parameter_size=request.cado_parameter_size,
        )
    except (ExpressionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/jobs")
def list_jobs(limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, object]]:
    return database.list_jobs(limit)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    job = database.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/jobs/{job_id}/export")
def export_job(job_id: str) -> FileResponse:
    job = database.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result_path = job.get("result_path")
    if not result_path or not Path(result_path).is_file():
        raise HTTPException(status_code=409, detail="This job has no completed export")
    path = Path(result_path)
    if path.parent.resolve() != OUTPUT_DIR.resolve():
        raise HTTPException(status_code=403, detail="Invalid output path")
    return FileResponse(path, filename=path.name, media_type="text/plain")


@app.get("/api/jobs/{job_id}/log")
def get_log(
    job_id: str, tail: int = Query(default=120_000, ge=1, le=2_000_000)
) -> dict[str, object]:
    job = database.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    path = Path(job["log_path"])
    if not path.exists():
        return {"text": "", "size": 0, "truncated": False}
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > tail:
            handle.seek(size - tail)
        content = handle.read().decode("utf-8", errors="replace")
    return {"text": content, "size": size, "truncated": size > tail}


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, object]:
    try:
        return manager.cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc


@app.post("/api/jobs/{job_id}/resume", status_code=202)
def resume_job(job_id: str) -> dict[str, object]:
    try:
        return manager.resume(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def run() -> None:
    uvicorn.run("numerisect.main:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    run()
