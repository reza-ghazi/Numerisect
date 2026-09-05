from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
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
from .prime_manipulation import batch_primality, progression_primes, prime_modular
from .outputs import (
    finalize_native_output,
    native_output_paths,
    safe_output_path,
    save_prime_output,
)
from .primes import (
    PrimeEngineError,
    absolute_primes_in_range,
    analyze_gaussian_integer,
    analyze_miller_rabin_witnesses,
    analyze_prime_reciprocal,
    classify_prime,
    coprime_profile,
    contiguous_digit_primes,
    digit_constrained_primes,
    factor_count_distribution,
    full_reptend_primes_in_range,
    gaussian_primes_in_box,
    generate_even_perfect_numbers,
    generate_primorials,
    generate_primes,
    generate_special_primes,
    goldbach_partitions,
    integer_arithmetic_profile,
    integers_with_three_prime_factors,
    modular_wheel_cells,
    nth_prime,
    nth_prime_near,
    palindrome_derived_primes,
    paterson_primes_in_range,
    prime_count,
    prime_gaps,
    prime_gap_statistics,
    prime_indicator_constant,
    prime_insertion_pyramid,
    prime_multiplication_pyramid,
    prime_polynomial_analysis,
    prime_distribution,
    prime_square_sum_solutions,
    primality_result,
    prime_tuples_in_range,
    primes_after,
    primes_before,
    primes_in_range,
    quartan_primes_in_range,
    random_primes_in_range,
    sigma_fourth_power_square_primes,
    special_numbers_in_range,
)
from .zeta import (
    ZetaEngineError,
    count_zeta_zeros,
    evaluate_zeta,
    find_zeta_zeros,
    sample_zeta_heatmap,
    sample_zeta_line,
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


@app.middleware("http")
async def prevent_stale_interface_assets(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Numerisect-UI"] = "workstation-20260905"
    return response


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


class PrimeReciprocalRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=100_000)
    digit_limit: int = Field(default=1000, ge=0, le=100_000)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


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


class RelativePrimeRequest(BaseModel):
    start: str = Field(min_length=1, max_length=100_000)
    index: int = Field(ge=1, le=100_000)
    direction: Literal["after", "before"] = "after"


class PrimeCountRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=100_000)


class BatchPrimalityRequest(BaseModel):
    integers: str = Field(min_length=1, max_length=200_000)
    mode: Literal["proven", "fast"] = "proven"
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class ProgressionPrimeRequest(BaseModel):
    start: str = Field(min_length=1, max_length=100_000)
    end: str = Field(min_length=1, max_length=100_000)
    modulus: str = Field(min_length=1, max_length=100_000)
    residue: str = Field(default="1", min_length=1, max_length=100_000)
    limit: int = Field(default=1000, ge=1, le=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class PrimeModularRequest(BaseModel):
    modulus: str = Field(min_length=1, max_length=100_000)
    value: str = Field(default="1", min_length=1, max_length=100_000)
    exponent: str = Field(default="2", min_length=1, max_length=100_000)
    operation: Literal["inverse", "power", "order", "roots", "generator"] = "inverse"
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class PrimeGapRequest(PrimeRangeRequest):
    pass


class PrimeTupleRequest(BaseModel):
    start: str = Field(min_length=1, max_length=100_000)
    end: str = Field(min_length=1, max_length=100_000)
    offsets: list[int] = Field(min_length=2, max_length=32)
    limit: int = Field(default=10_000, ge=1, le=100_000)


class AbsolutePrimeRequest(PrimeRangeRequest):
    limit: int = Field(default=1_000, ge=1, le=10_000)


class GaussianCheckRequest(BaseModel):
    real: str = Field(min_length=1, max_length=100_000)
    imaginary: str = Field(min_length=1, max_length=100_000)


class GaussianRangeRequest(BaseModel):
    bound: int = Field(default=20, ge=1, le=500)
    limit: int = Field(default=10_000, ge=1, le=100_000)


class ModularWheelRequest(BaseModel):
    modulus: int = Field(default=30, ge=2, le=360)
    maximum: int = Field(default=300, ge=0, le=20_000)


class PatersonPrimeRequest(PrimeRangeRequest):
    limit: int = Field(default=1_000, ge=1, le=10_000)


class PerfectNumberRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=20)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class PrimePyramidRequest(BaseModel):
    kind: Literal["insertion", "multiplication"] = "insertion"
    size: int = Field(default=8, ge=1, le=100)


class SpecialNumberRangeRequest(PrimeRangeRequest):
    kind: Literal[
        "carmichael",
        "fermat_pseudoprime_base2",
        "strong_pseudoprime_bases2_3",
        "lucky_prime",
        "jacobsthal_prime",
    ]
    limit: int = Field(default=1_000, ge=1, le=10_000)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class MillerRabinWitnessRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=100_000)
    base: str = Field(default="2", min_length=1, max_length=100_000)
    preview_limit: int = Field(default=1_000, ge=0, le=10_000)


class PrimorialRequest(BaseModel):
    count: int = Field(default=10, ge=1, le=500)


class RandomPrimeRangeRequest(BaseModel):
    start: str = Field(min_length=1, max_length=100_000)
    end: str = Field(min_length=1, max_length=100_000)
    count: int = Field(default=10, ge=1, le=10_000)


class DigitPrimeRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=100_000)


class GoldbachRequest(DigitPrimeRequest):
    limit: int = Field(default=10_000, ge=1, le=100_000)


class PrimeProblemRequest(BaseModel):
    kind: Literal["square_sum", "quartan", "three_factors", "sigma_square"]
    start: str = Field(default="2", min_length=1, max_length=100_000)
    end: str = Field(default="1000", min_length=1, max_length=100_000)
    limit: int = Field(default=1_000, ge=1, le=10_000)


class IntegerProfileRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=100_000)
    divisor_limit: int = Field(default=1_000, ge=0, le=100_000)


class CoprimeProfileRequest(BaseModel):
    modulus: str = Field(min_length=1, max_length=100_000)
    start: str = Field(default="0", min_length=1, max_length=100_000)
    count: int = Field(default=20, ge=1, le=100_000)
    residue_limit: int = Field(default=1_000, ge=0, le=100_000)


class PrimeDistributionRequest(BaseModel):
    start: str = Field(default="2", min_length=1, max_length=100_000)
    end: str = Field(default="100000", min_length=1, max_length=100_000)
    bins: int = Field(default=50, ge=2, le=500)
    modulus: int = Field(default=30, ge=2, le=360)


class FactorCountDistributionRequest(BaseModel):
    start: str = Field(default="1", min_length=1, max_length=100_000)
    end: str = Field(default="10000", min_length=1, max_length=100_000)


class DigitConstrainedPrimeRequest(BaseModel):
    allowed_digits: str = Field(default="1379", min_length=1, max_length=10)
    minimum_digits: int = Field(default=1, ge=1, le=1_000)
    maximum_digits: int = Field(default=6, ge=1, le=1_000)
    limit: int = Field(default=1_000, ge=1, le=100_000)


class PrimePolynomialRequest(BaseModel):
    k: str = Field(default="41", min_length=1, max_length=100_000)
    start: str = Field(default="0", min_length=1, max_length=100_000)
    end: str = Field(default="100", min_length=1, max_length=100_000)
    limit: int = Field(default=1_000, ge=1, le=100_000)
    obstruction_bound: int = Field(default=100, ge=2, le=1_000)


class PalindromeDerivedRequest(PrimeRangeRequest):
    limit: int = Field(default=1_000, ge=1, le=100_000)


class PrimeConstantRequest(BaseModel):
    decimal_digits: int = Field(default=100, ge=1, le=100_000)


class ZetaEvaluateRequest(BaseModel):
    sigma: str = Field(default="0.5", min_length=1, max_length=10_000)
    ordinate: str = Field(default="14.134725", min_length=1, max_length=10_000)
    precision: int = Field(default=50, ge=16, le=1000)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class ZetaZerosRequest(BaseModel):
    start_index: str = Field(default="1", min_length=1, max_length=10_000)
    count: int = Field(default=10, ge=1, le=1000)
    precision: int = Field(default=50, ge=16, le=1000)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class ZetaCountRequest(BaseModel):
    height: str = Field(default="100", min_length=1, max_length=10_000)
    precision: int = Field(default=50, ge=16, le=1000)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class ZetaLineRequest(BaseModel):
    lower: str = Field(default="0", min_length=1, max_length=10_000)
    upper: str = Field(default="50", min_length=1, max_length=10_000)
    samples: int = Field(default=800, ge=2, le=10_000)
    precision: int = Field(default=30, ge=16, le=1000)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class ZetaHeatmapRequest(BaseModel):
    sigma_min: str = Field(default="-2", min_length=1, max_length=10_000)
    sigma_max: str = Field(default="2", min_length=1, max_length=10_000)
    t_min: str = Field(default="-30", min_length=1, max_length=10_000)
    t_max: str = Field(default="30", min_length=1, max_length=10_000)
    width: int = Field(default=120, ge=2, le=500)
    height: int = Field(default=100, ge=2, le=500)
    precision: int = Field(default=20, ge=16, le=1000)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


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
                "flint/zeta": executable_path("numerisect-zeta"),
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


def _save_manipulation_report(kind: str, heading: str, result: dict) -> dict:
    lines = [result["note"], ""]
    lines.extend(f"{key}: {value}" for key, value in result.get("metrics", {}).items())
    lines.extend(["", " | ".join(result["columns"])])
    lines.extend(" | ".join(row) for row in result["rows"])
    path = save_prime_output(kind, heading, lines)
    return {**result, "output_file": path.name, "engine": "PARI/GP"}


@app.post("/api/primes/batch-check")
def check_prime_batch(request: BatchPrimalityRequest) -> dict:
    try:
        result = batch_primality(request.integers, request.mode, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("batch-primality", "Batch primality results", result)


@app.post("/api/primes/progression")
def find_progression_primes(request: ProgressionPrimeRequest) -> dict:
    try:
        result = progression_primes(request.start, request.end, request.modulus,
                                    request.residue, request.limit, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("progression-primes", "Primes in a residue class", result)


@app.post("/api/primes/modular")
def calculate_prime_modular(request: PrimeModularRequest) -> dict:
    try:
        result = prime_modular(request.modulus, request.value, request.exponent,
                               request.operation, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("prime-modular", "Arithmetic modulo a prime", result)


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


@app.post("/api/primes/reciprocal")
def analyze_reciprocal_of_prime(request: PrimeReciprocalRequest) -> dict[str, object]:
    try:
        number = evaluate_arbitrary_integer(request.expression)
    except ExpressionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    temporary_path, output_path = native_output_paths("prime-reciprocal")
    try:
        result = analyze_prime_reciprocal(
            number,
            digit_limit=request.digit_limit,
            timeout_seconds=request.timeout_seconds,
            export_path=temporary_path,
        )
        finalize_native_output(temporary_path, output_path)
    except ValueError as exc:
        temporary_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (OSError, PrimeEngineError) as exc:
        temporary_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    result["output_file"] = output_path.name
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


@app.post("/api/primes/nth-near")
def find_relative_prime(request: RelativePrimeRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        value = nth_prime_near(start, request.index, request.direction)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    label = f"Prime #{request.index:,} strictly {request.direction} {start}"
    note = "The starting integer is excluded. Every counted prime was rigorously proven by PARI/GP."
    path = save_prime_output("nth-near-prime", label, [str(value), note])
    return {
        "start": str(start), "index": request.index, "direction": request.direction,
        "label": label, "value": str(value), "output_file": path.name, "note": note,
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


@app.post("/api/primes/absolute")
def find_absolute_primes(request: AbsolutePrimeRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        end = evaluate_arbitrary_integer(request.end)
        groups, truncated, next_start = absolute_primes_in_range(
            start, end, request.limit
        )
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "absolute-primes",
        f"Absolute primes from {start} through {end}",
        (
            f"{item['representative']}: {', '.join(item['rotations'])}"
            for item in groups
        ),
    )
    return {
        "start": str(start),
        "end": str(end),
        "count": len(groups),
        "groups": groups,
        "truncated": truncated,
        "next_start": str(next_start) if next_start is not None else None,
        "output_file": path.name,
        "note": "One representative is shown per decimal rotation orbit; PARI/GP rigorously proved every rotation prime.",
    }


@app.post("/api/primes/gaussian/check")
def check_gaussian_prime(request: GaussianCheckRequest) -> dict[str, object]:
    try:
        real = evaluate_arbitrary_integer(request.real)
        imaginary = evaluate_arbitrary_integer(request.imaginary)
        result = analyze_gaussian_integer(real, imaginary)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    lines = [
        f"Gaussian integer: {real} + ({imaginary})i",
        f"Norm: {result['norm']}",
        f"Gaussian prime: {'yes' if result['is_gaussian_prime'] else 'no'}",
        f"Norm is a rational prime: {'yes' if result['norm_is_rational_prime'] else 'no'}",
    ]
    for factor in result["factors"]:
        lines.append(f"Gaussian factor: {factor['real']} + ({factor['imaginary']})i")
    path = save_prime_output("gaussian-prime", "Gaussian-prime analysis", lines)
    result["output_file"] = path.name
    return result


@app.post("/api/primes/gaussian/range")
def find_gaussian_primes(request: GaussianRangeRequest) -> dict[str, object]:
    try:
        values, truncated = gaussian_primes_in_box(request.bound, request.limit)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "gaussian-primes",
        f"Gaussian primes in the box [-{request.bound}, {request.bound}]²",
        (f"{item['real']} + ({item['imaginary']})i; norm {item['norm']}" for item in values),
    )
    return {
        "bound": request.bound,
        "count": len(values),
        "points": values,
        "truncated": truncated,
        "next_start": None,
        "output_file": path.name,
        "note": "PARI/GP applied the exact Gaussian-prime criterion at every lattice point.",
    }


@app.post("/api/primes/modular-wheel")
def create_modular_wheel(request: ModularWheelRequest) -> dict[str, object]:
    try:
        cells = modular_wheel_cells(request.modulus, request.maximum)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "modular-wheel",
        f"Modular wheel modulo {request.modulus} through {request.maximum}",
        (
            f"{cell['value']}: residue {cell['residue']}, ring {cell['ring']}, "
            f"prime {'yes' if cell['is_prime'] else 'no'}, "
            f"coprime {'yes' if cell['coprime'] else 'no'}"
            for cell in cells
        ),
    )
    return {
        "modulus": request.modulus,
        "maximum": request.maximum,
        "cells": cells,
        "output_file": path.name,
        "note": "PARI/GP computed every residue, ring, coprimality result, and rigorous primality result; JavaScript only draws the wheel.",
    }


@app.post("/api/primes/paterson")
def find_paterson_primes(request: PatersonPrimeRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        end = evaluate_arbitrary_integer(request.end)
        values, truncated, next_start = paterson_primes_in_range(
            start, end, request.limit
        )
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "paterson-primes",
        f"Paterson primes from {start} through {end}",
        (
            f"{item['prime']}: base 4 = {item['base4']}; decimal companion = {item['decimal_companion']}"
            for item in values
        ),
    )
    return {
        "start": str(start),
        "end": str(end),
        "count": len(values),
        "values": values,
        "truncated": truncated,
        "next_start": str(next_start) if next_start is not None else None,
        "output_file": path.name,
        "note": "For each result, PARI/GP proved both p and the decimal integer formed by its base-4 digits prime.",
    }


@app.post("/api/primes/perfect")
def create_perfect_numbers(request: PerfectNumberRequest) -> dict[str, object]:
    try:
        values = generate_even_perfect_numbers(request.count, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "perfect-numbers",
        f"First {request.count} even perfect numbers",
        (
            f"q={item['exponent']}; 2^q-1={item['mersenne_prime']}; N={item['value']}"
            for item in values
        ),
    )
    return {
        "count": len(values),
        "values": values,
        "output_file": path.name,
        "note": "Generated exactly with the Euclid–Euler theorem after PARI/GP rigorously proved each Mersenne prime.",
    }


@app.post("/api/primes/reptend")
def find_full_reptend_primes(request: PrimeRangeRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        end = evaluate_arbitrary_integer(request.end)
        values, truncated, next_start = full_reptend_primes_in_range(
            start, end, request.limit
        )
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "full-reptend-primes",
        f"Full-reptend primes from {start} through {end}",
        (f"p={item['prime']}; decimal period={item['period']}" for item in values),
    )
    return {
        "start": str(start),
        "end": str(end),
        "count": len(values),
        "values": values,
        "truncated": truncated,
        "next_start": str(next_start) if next_start is not None else None,
        "output_file": path.name,
        "note": "PARI/GP proved each p prime and computed the exact multiplicative order ordₚ(10)=p−1.",
    }


@app.post("/api/primes/pyramid")
def create_prime_pyramid(request: PrimePyramidRequest) -> dict[str, object]:
    if request.kind == "insertion" and request.size > 30:
        raise HTTPException(
            status_code=422,
            detail="The insertion pyramid is limited to 30 levels because its rows grow rapidly",
        )
    try:
        if request.kind == "insertion":
            levels = prime_insertion_pyramid(request.size)
            report = (
                f"Level {item['level']}; inserted sum {item['inserted_sum']}: {item['value']}"
                for item in levels
            )
            payload: dict[str, object] = {"levels": levels}
        else:
            rows = prime_multiplication_pyramid(request.size)
            report = (
                f"Row {row_index}: " + " ".join(
                    f"{cell['value']}{'*' if cell['is_prime'] else ''}" for cell in row
                )
                for row_index, row in enumerate(rows, 1)
            )
            payload = {"rows": rows}
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "prime-pyramid",
        f"{request.kind.title()} prime pyramid with {request.size} levels",
        report,
    )
    return {
        "kind": request.kind,
        "size": request.size,
        **payload,
        "output_file": path.name,
        "note": "PARI/GP constructed every level and performed all primality tests; the interface only formats the pyramid.",
    }


@app.post("/api/primes/special-numbers")
def find_special_numbers(request: SpecialNumberRangeRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        end = evaluate_arbitrary_integer(request.end)
        values, truncated, next_start = special_numbers_in_range(
            request.kind,
            start,
            end,
            request.limit,
            request.timeout_seconds,
        )
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    labels = {
        "carmichael": "Carmichael numbers",
        "fermat_pseudoprime_base2": "base-2 Fermat pseudoprimes",
        "strong_pseudoprime_bases2_3": "strong pseudoprimes to bases 2 and 3",
        "lucky_prime": "lucky primes",
        "jacobsthal_prime": "Jacobsthal primes",
    }
    path = save_prime_output(
        "special-numbers",
        f"{labels[request.kind]} from {start} through {end}",
        (f"{item['value']}: {item['detail']}" for item in values),
    )
    return {
        "kind": request.kind,
        "start": str(start),
        "end": str(end),
        "count": len(values),
        "values": values,
        "truncated": truncated,
        "next_start": str(next_start) if next_start is not None else None,
        "output_file": path.name,
        "note": "PARI/GP performed the finite-range search using exact definitions; primes are excluded from both pseudoprime classes.",
    }


@app.post("/api/primes/miller-rabin-witnesses")
def analyze_witnesses(request: MillerRabinWitnessRequest) -> dict[str, object]:
    try:
        number = evaluate_arbitrary_integer(request.expression)
        base = evaluate_arbitrary_integer(request.base)
        result = analyze_miller_rabin_witnesses(number, base, request.preview_limit)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    lines = [
        f"n = {result['number']} = 2^{result['s']} × {result['d']} + 1",
        f"Selected base: {result['base']}",
        f"gcd(base, n): {result['gcd']}",
        f"Strong Miller–Rabin result: {'passes' if result['passes'] else 'fails'}",
        f"Composite witness: {'yes' if result['is_witness'] else 'no'}",
    ]
    if result["distribution_complete"]:
        lines.extend(
            [
                "",
                f"All tested bases: {result['base_count']}",
                f"Witness bases: {result['witness_count']}",
                f"Passing bases: {result['passing_count']}",
                "",
                "Witness preview: " + ", ".join(result["witnesses"]),
                "Passing-base preview: " + ", ".join(result["passing_bases"]),
            ]
        )
    path = save_prime_output(
        "miller-rabin-witnesses", "Miller–Rabin witness analysis", lines
    )
    result["output_file"] = path.name
    return result


@app.post("/api/primes/gap-statistics")
def calculate_prime_gap_statistics(request: PrimeGapRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        end = evaluate_arbitrary_integer(request.end)
        result = prime_gap_statistics(start, end, request.limit)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    lines = [f"Range: {start} through {end}", f"Gap count: {result['count']}"]
    if int(result["count"]):
        lines.extend(
            [
                f"Minimum: {result['minimum']}",
                f"Maximum: {result['maximum']}",
                f"Mean: {result['mean']['numerator']}/{result['mean']['denominator']}",
                f"Median: {result['median']['numerator']}/{result['median']['denominator']}",
                f"Mode: {result['mode']['gap']} (frequency {result['mode']['frequency']})",
                "",
                "Frequencies",
                "-----------",
            ]
        )
        lines.extend(
            f"Gap {item['gap']}: {item['frequency']}" for item in result["frequencies"]
        )
    path = save_prime_output("prime-gap-statistics", "Prime-gap statistics", lines)
    return {
        "start": str(start),
        "end": str(end),
        **result,
        "output_file": path.name,
        "note": "PARI/GP computed the exact distribution, rational mean and median, mode, and extrema over the scanned consecutive gaps.",
    }


@app.post("/api/primes/primorials")
def create_primorials(request: PrimorialRequest) -> dict[str, object]:
    try:
        values = generate_primorials(request.count)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "primorials",
        f"First {request.count} primorials",
        (f"#{item['index']}: {item['prime']}# = {item['value']}" for item in values),
    )
    return {
        "count": len(values),
        "values": values,
        "output_file": path.name,
        "note": "PARI/GP rigorously generated each successive prime and multiplied the primorial exactly.",
    }


@app.post("/api/primes/random-range")
def create_random_range_primes(request: RandomPrimeRangeRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        end = evaluate_arbitrary_integer(request.end)
        values = random_primes_in_range(start, end, request.count)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "random-range-primes",
        f"{request.count} random primes from {start} through {end}",
        map(str, values),
    )
    return {
        "start": str(start), "end": str(end), "count": len(values),
        "primes": [str(value) for value in values], "output_file": path.name,
        "note": "PARI/GP sampled distinct values in the interval and rigorously proved every returned prime.",
    }


@app.post("/api/primes/contiguous-digits")
def find_contiguous_digit_primes(request: DigitPrimeRequest) -> dict[str, object]:
    try:
        number = evaluate_arbitrary_integer(request.expression)
        values = contiguous_digit_primes(number)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "contiguous-digit-primes",
        f"Prime contiguous substrings of {number}",
        map(str, values),
    )
    return {
        "number": str(number), "count": len(values), "primes": [str(value) for value in values],
        "output_file": path.name,
        "note": "PARI/GP tested every distinct contiguous decimal substring rigorously without reordering digits.",
    }


@app.post("/api/primes/goldbach")
def find_goldbach_partitions(request: GoldbachRequest) -> dict[str, object]:
    try:
        number = evaluate_arbitrary_integer(request.expression)
        values, truncated = goldbach_partitions(number, request.limit)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "goldbach-partitions",
        f"Goldbach partitions of {number}",
        (f"{number} = {item['left']} + {item['right']}" for item in values),
    )
    return {
        "number": str(number), "count": len(values), "partitions": values,
        "truncated": truncated, "next_start": None, "output_file": path.name,
        "note": "PARI/GP rigorously proved both members of every displayed Goldbach partition. This computation verifies only the supplied integer, not the general conjecture.",
    }


@app.post("/api/primes/problems")
def solve_prime_problem(request: PrimeProblemRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        end = evaluate_arbitrary_integer(request.end)
        if request.kind == "square_sum":
            if end > 100_000:
                raise ValueError("The p²+1=q²+r² search supports p through 100,000 per request")
            values, truncated = prime_square_sum_solutions(end, request.limit)
        elif request.kind == "quartan":
            if end > 10**12:
                raise ValueError("The fourth-power search supports result bounds through 10^12 per request")
            values, truncated = quartan_primes_in_range(end, request.limit)
        elif request.kind == "three_factors":
            values, truncated = integers_with_three_prime_factors(start, end, request.limit)
        else:
            if end > 1_000_000:
                raise ValueError("The divisor-sum search supports the first 1,000,000 prime candidates per request")
            values, truncated = sigma_fourth_power_square_primes(end, request.limit)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "prime-problem", f"Prime problem: {request.kind}",
        (str(item) for item in values),
    )
    return {
        "kind": request.kind, "start": str(start), "end": str(end),
        "count": len(values), "values": values, "truncated": truncated,
        "next_start": None, "output_file": path.name,
        "note": "PARI/GP performed the complete bounded search and rigorously checked every reported prime and factorization condition.",
    }


@app.post("/api/primes/integer-profile")
def create_integer_profile(request: IntegerProfileRequest) -> dict[str, object]:
    try:
        number = evaluate_arbitrary_integer(request.expression)
        result = integer_arithmetic_profile(number, request.divisor_limit)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    factors = result["factors"]
    factorization = " × ".join(
        f"{item['prime']}^{item['exponent']}" if item["exponent"] != "1" else item["prime"]
        for item in factors
    ) or "1"
    lines = [
        f"Integer: {result['number']}",
        f"Factorization of |n|: {factorization}",
        f"Prime: {'yes' if result['is_prime'] else 'no'}",
        f"Semiprime: {'yes' if result['is_semiprime'] else 'no'}",
        f"ω(n): {result['omega']}",
        f"Ω(n): {result['big_omega']}",
        f"τ(n): {result['divisor_count']}",
        f"σ(n): {result['divisor_sum']}",
        f"Aliquot sum: {result['aliquot_sum']}",
        f"φ(n): {result['totient']}",
        f"λ(n): {result['carmichael']}",
        f"μ(n): {result['mobius']}",
        f"rad(n): {result['radical']}",
        f"Divisor class: {result['divisor_class']}",
        "",
        "Divisor preview",
        "---------------",
        ", ".join(result["divisors"]) or "No divisors requested",
    ]
    if not result["divisors_complete"]:
        lines.append(f"Preview limited to {request.divisor_limit:,} of {result['divisor_count']} divisors.")
    path = save_prime_output("integer-profile", "Integer arithmetic profile", lines)
    result["factorization"] = factorization
    result["output_file"] = path.name
    return result


@app.post("/api/primes/coprimes")
def create_coprime_profile(request: CoprimeProfileRequest) -> dict[str, object]:
    try:
        modulus = evaluate_arbitrary_integer(request.modulus)
        start = evaluate_arbitrary_integer(request.start)
        result = coprime_profile(modulus, start, request.count, request.residue_limit)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    lines = [
        f"Modulus: {modulus}",
        f"Euler totient φ(m): {result['totient']}",
        f"First {request.count} coprimes strictly after {start}:",
        ", ".join(result["after"]),
        "",
        "Reduced residue system preview:",
        ", ".join(result["residues"]) or "No residues requested",
    ]
    path = save_prime_output("coprimes", "Coprime analysis", lines)
    result["output_file"] = path.name
    return result


@app.post("/api/primes/distribution")
def create_prime_distribution(request: PrimeDistributionRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        end = evaluate_arbitrary_integer(request.end)
        result = prime_distribution(start, end, request.bins, request.modulus)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    lines = [
        f"Range: {start} through {end}",
        f"Prime count: {result['count']}",
        f"Twin pairs within the range: {result['twin_count']}",
        f"Maximum internal gap: {result['maximum_gap']} after {result['maximum_gap_at']}",
        "",
        "Bins",
        "----",
    ]
    lines.extend(f"{item['start']}..{item['end']}: {item['count']}" for item in result["bins"])
    lines.extend(["", f"Residues modulo {request.modulus}", "----------------"])
    lines.extend(f"{item['residue']}: {item['count']}" for item in result["residues"])
    path = save_prime_output("prime-distribution", "Prime distribution", lines)
    result["output_file"] = path.name
    return result


@app.post("/api/primes/factor-count-distribution")
def create_factor_count_distribution(
    request: FactorCountDistributionRequest,
) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        end = evaluate_arbitrary_integer(request.end)
        result = factor_count_distribution(start, end)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    lines = [
        f"Range: {start} through {end}",
        f"Integers analyzed: {result['total']}",
        "",
        "k: ω(n) count; Ω(n) count",
        "-------------------------",
    ]
    lines.extend(
        f"{item['factor_count']}: {item['distinct_count']}; {item['multiplicity_count']}"
        for item in result["distribution"]
    )
    path = save_prime_output(
        "factor-count-distribution", "Prime-factor-count distribution", lines
    )
    result["output_file"] = path.name
    return result


@app.post("/api/primes/digit-constrained")
def create_digit_constrained_primes(request: DigitConstrainedPrimeRequest) -> dict[str, object]:
    try:
        result = digit_constrained_primes(
            request.allowed_digits,
            request.minimum_digits,
            request.maximum_digits,
            request.limit,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "digit-constrained-primes",
        f"Primes using only digits {result['allowed_digits']}",
        result["primes"],
    )
    result["output_file"] = path.name
    result["next_start"] = None
    if result["candidate_limited"]:
        result["note"] += " The native search stopped at the 2,000,000-candidate resource limit."
    return result


@app.post("/api/primes/polynomial")
def create_prime_polynomial_analysis(request: PrimePolynomialRequest) -> dict[str, object]:
    try:
        k = evaluate_arbitrary_integer(request.k)
        start = evaluate_arbitrary_integer(request.start)
        end = evaluate_arbitrary_integer(request.end)
        result = prime_polynomial_analysis(
            k, start, end, request.limit, request.obstruction_bound
        )
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    lines = [
        f"Polynomial: n² − n + {k}",
        f"Index range: {start} through {end}",
        f"Prime values: {result['count']}",
        f"Longest consecutive prime run: {result['longest_run']} starting at n={result['longest_run_start']}",
        "",
        "Prime values",
        "------------",
    ]
    lines.extend(f"n={item['n']}: {item['value']}" for item in result["values"])
    lines.extend(["", "Modular divisibility classes", "----------------------------"])
    lines.extend(
        f"mod {item['prime']}: n ≡ {', '.join(item['residues'])}"
        for item in result["obstructions"]
    )
    path = save_prime_output("prime-polynomial", "Prime polynomial analysis", lines)
    result["output_file"] = path.name
    result["next_start"] = None
    return result


@app.post("/api/primes/palindrome-derived")
def create_palindrome_derived_primes(request: PalindromeDerivedRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        end = evaluate_arbitrary_integer(request.end)
        result = palindrome_derived_primes(start, end, request.limit)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "palindrome-derived-primes",
        f"Prime values of |n−reverse(n)|+1 for {start} through {end}",
        (
            f"n={item['n']}; reverse={item['reverse']}; prime={item['prime']}"
            for item in result["values"]
        ),
    )
    result["output_file"] = path.name
    result["next_start"] = None
    return result


@app.post("/api/primes/indicator-constant")
def create_prime_indicator_constant(request: PrimeConstantRequest) -> dict[str, object]:
    try:
        result = prime_indicator_constant(request.decimal_digits)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "prime-indicator-constant",
        "Prime-indicator binary constant",
        [
            f"Decimal value: {result['value']}",
            f"Encoded primality bits: {result['terms']}",
            f"Tail bound: {result['error_bound']}",
        ],
    )
    result["output_file"] = path.name
    return result


@app.post("/api/zeta/evaluate")
def calculate_zeta(request: ZetaEvaluateRequest) -> dict[str, object]:
    try:
        result = evaluate_zeta(
            request.sigma, request.ordinate, request.precision, request.timeout_seconds
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "zeta-value",
        f"Riemann zeta at {result['sigma']} + {result['ordinate']}i",
        [
            f"Real: {result['real']}",
            f"Imaginary: {result['imaginary']}",
            f"Magnitude: {result['magnitude']}",
            f"Argument: {result['argument']}",
            f"Decimal precision: {request.precision}",
            "Engine: FLINT/Arb rigorous ball arithmetic",
        ],
    )
    result["output_file"] = path.name
    return result


@app.post("/api/zeta/zeros")
def calculate_zeta_zeros(request: ZetaZerosRequest) -> dict[str, object]:
    try:
        zeros = find_zeta_zeros(
            request.start_index,
            request.count,
            request.precision,
            request.threads,
            request.timeout_seconds,
        )
    except (ValueError, ZetaEngineError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "zeta-zeros",
        f"Riemann zeta zeros {zeros[0]['index']} through {zeros[-1]['index']}",
        (
            f"#{item['index']}: t={item['ordinate']}; radius={item['radius']}; interval={item['interval']}"
            for item in zeros
        ),
    )
    return {
        "start_index": zeros[0]["index"],
        "count": len(zeros),
        "zeros": zeros,
        "precision": request.precision,
        "threads": request.threads,
        "output_file": path.name,
        "note": "FLINT/Arb rigorously isolated consecutive Hardy Z zeros on the critical line.",
    }


@app.post("/api/zeta/count")
def calculate_zeta_zero_count(request: ZetaCountRequest) -> dict[str, object]:
    try:
        result = count_zeta_zeros(
            request.height, request.precision, request.threads, request.timeout_seconds
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "zeta-zero-count",
        f"Nontrivial Riemann zeta zeros through height {result['height']}",
        [
            f"N({result['height']}) = {result['count']}",
            f"Certified enclosure: {result['interval']}",
            "Method: FLINT/Arb Turing-method zero count",
        ],
    )
    return {
        **result,
        "label": f"N({result['height']})",
        "value": result["count"],
        "engine": "FLINT/Arb",
        "rigorous": True,
        "output_file": path.name,
        "note": "Exact count of all nontrivial zeros with ordinates from 0 through the requested height, certified by FLINT's Turing method.",
    }


@app.post("/api/zeta/line")
def create_zeta_line(request: ZetaLineRequest) -> dict[str, object]:
    try:
        points = sample_zeta_line(
            request.lower,
            request.upper,
            request.samples,
            request.precision,
            request.threads,
            request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "zeta-critical-line",
        f"Zeta samples on Re(s)=1/2 from {request.lower} through {request.upper}",
        (
            "t={t:.17g}\tre={real:.17g}\tim={imaginary:.17g}\tabs={magnitude:.17g}\targ={argument:.17g}".format(**point)
            for point in points
        ),
    )
    return {
        "lower": request.lower,
        "upper": request.upper,
        "samples": len(points),
        "points": points,
        "output_file": path.name,
        "note": "FLINT/Arb evaluated every sample; the chart displays enclosure midpoints for exploration.",
    }


@app.post("/api/zeta/heatmap")
def create_zeta_heatmap(request: ZetaHeatmapRequest) -> dict[str, object]:
    try:
        points = sample_zeta_heatmap(
            request.sigma_min,
            request.sigma_max,
            request.t_min,
            request.t_max,
            request.width,
            request.height,
            request.precision,
            request.threads,
            request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    def report_lines():
        for point in points:
            values = [point[key] for key in ("sigma", "t", "real", "imaginary", "magnitude", "argument")]
            yield "\t".join("undefined" if value is None else f"{value:.17g}" for value in values)

    path = save_prime_output(
        "zeta-heatmap",
        f"Zeta heatmap {request.sigma_min}≤Re(s)≤{request.sigma_max}, {request.t_min}≤Im(s)≤{request.t_max}",
        report_lines(),
    )
    return {
        "width": request.width,
        "height": request.height,
        "points": points,
        "output_file": path.name,
        "note": "FLINT/Arb evaluated every grid point; JavaScript only maps the native magnitude and argument samples to color.",
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
