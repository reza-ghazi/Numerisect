from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .adapters import REGISTRY
from .algebra_lab import (
    chebotarev_density,
    congruence_solutions,
    cornacchia_representations,
    discrete_logarithm_lab,
    divisor_lattice,
    finite_field_arithmetic,
    number_field_analysis,
    quadratic_ring_analysis,
    reciprocity_trace,
    record_divisor_numbers,
    smoothness_profile,
    sociable_cycles,
    weird_number_analysis,
)
from .catalogues import (
    ALLOW_NETWORK,
    CatalogueError,
    NetworkNotPermitted,
    list_local_catalogues,
    local_catalogue_lookup,
    network_status,
    oeis_lookup,
    remote_catalogue_lookup,
)
from .config import (
    BASE_DIR,
    DATABASE_PATH,
    DEFAULT_CADO_THRESHOLD,
    DEFAULT_PRETEST_LEVEL,
    GGNFS_DIR,
    MAX_EXPRESSION_CHARACTERS,
    MAX_PARALLEL_JOBS,
    OUTPUT_DIR,
    RESULT_CACHE_ENABLED,
    STATE_DIR,
    STATIC_DIR,
    ensure_state_dirs,
    prepend_managed_tools_to_path,
)
from .database import Database
from .diagnostics import system_diagnostics
from .distributed import (
    DistributedConfigurationError,
    client_command,
    describe_trust_model,
    find_client_script,
    validate_configuration,
)
from .distribution_lab import (
    approximation_error,
    bateman_horn,
    density_surface,
    maximal_gap_search,
    nth_prime_bounds,
    pnt_convergence,
    prime_race,
    progression_deviation,
    short_interval_matrix,
    singular_series,
    tuple_prediction,
)
from .engines import discover_cado_parameters, executable_path
from .evaluator import ExpressionError, evaluate_arbitrary_integer, evaluate_integer
from .exports import (
    EXTENSIONS,
    MEDIA_TYPES,
    export_report_text,
    normalize_format,
)
from .exports import (
    export_job as serialize_job,
)
from .exports import (
    export_jobs as serialize_jobs,
)
from .factor_lab import (
    algorithm_trace,
    batch_certificates,
    mersenne_factor_hunt,
    mersenne_factors,
    special_form_analysis,
    squfof,
    strategy_advice,
)
from .installer import EngineInstaller
from .jobs import JobManager
from .number_theory import (
    aliquot_sequence,
    arithmetic_functions,
    character_symbols,
    chinese_remainder,
    cunningham_chain,
    cyclotomic_polynomial,
    discrete_logarithm,
    divisor_classification,
    eisenstein_prime,
    factor_polynomial,
    factor_strategy,
    hensel_roots,
    modular_roots,
    ntt_primes,
    order_distribution,
    p_adic_valuation,
    perfect_power,
    power_residue_distribution,
    primality_laboratory,
    prime_approximation_comparison,
    quadratic_prime_decomposition,
    special_form_test,
    special_prime_family,
    summatory_functions,
    tonelli_shanks,
    unit_group,
)
from .outputs import (
    add_report_listener,
    finalize_native_output,
    native_output_paths,
    safe_output_path,
    save_prime_output,
)
from .primality_lab import (
    bitwin_chain_search,
    carmichael_analysis,
    chernick_search,
    compare_primality_tests,
    constrained_prime,
    covering_set_check,
    deterministic_witness_test,
    ecpp_steps,
    lucas_lehmer_steps,
    lucas_sequence_proof,
    pocklington_proof,
    pratt_certificate,
    prime_ladder,
    proth_search,
    proth_test,
    pseudoprime_taxonomy,
    repunit_search,
    sierpinski_riesel_search,
    verify_certificate,
)
from .prime_manipulation import batch_primality, prime_modular, progression_primes
from .primes import (
    PrimeEngineError,
    absolute_primes_in_range,
    analyze_gaussian_integer,
    analyze_miller_rabin_witnesses,
    analyze_prime_reciprocal,
    classify_prime,
    contiguous_digit_primes,
    coprime_profile,
    digit_constrained_primes,
    factor_count_distribution,
    full_reptend_primes_in_range,
    gaussian_primes_in_box,
    generate_even_perfect_numbers,
    generate_primes,
    generate_primorials,
    generate_special_primes,
    goldbach_partitions,
    integer_arithmetic_profile,
    integers_with_three_prime_factors,
    modular_wheel_cells,
    nth_prime,
    nth_prime_near,
    palindrome_derived_primes,
    paterson_primes_in_range,
    primality_result,
    prime_count,
    prime_distribution,
    prime_gap_statistics,
    prime_gaps,
    prime_indicator_constant,
    prime_insertion_pyramid,
    prime_multiplication_pyramid,
    prime_polynomial_analysis,
    prime_square_sum_solutions,
    prime_tuples_in_range,
    primes_after,
    primes_before,
    primes_in_range,
    quartan_primes_in_range,
    random_primes_in_range,
    sigma_fourth_power_square_primes,
    special_numbers_in_range,
    verify_primality_certificate,
)
from .rsa_challenge import catalogue as rsa_catalogue
from .rsa_challenge import challenge_report as rsa_challenge_report
from .security import (
    LOOPBACK_HOSTS,
    REQUEST_TOKEN,
    REQUEST_TOKEN_COOKIE,
    host_header_is_allowed,
    request_has_valid_token,
    request_origin_is_safe,
)
from .sievers import report as siever_report
from .verification import (
    cross_check_primality,
    cross_check_prime_count,
    self_test,
    sieve_interval,
)
from .visual_lab import (
    complexity_dashboard,
    eisenstein_lattice,
    gap_timeline,
    modular_wheel,
    residue_heatmap,
    sieve_trace,
    spiral_primes,
)
from .visual_lab import (
    prime_race as visual_prime_race,
)
from .workspace import (
    expand_batch_items,
    new_workspace_id,
    parse_batch_document,
    validate_workspace_fields,
    verify_claimed_factors,
)
from .zeta import (
    ZetaEngineError,
    backlund_remainder,
    chebyshev_psi_formula,
    count_zeta_zeros,
    dirichlet_characters,
    dirichlet_l_value,
    dirichlet_l_zeros,
    euler_product_comparison,
    evaluate_hardy_z,
    evaluate_xi_eta,
    evaluate_zeta,
    explicit_prime_count,
    find_zeta_zeros,
    gram_block_structure,
    gram_point,
    riemann_siegel_remainder,
    sample_zeta_heatmap,
    sample_zeta_line,
    stieltjes_constant,
    verify_functional_equation,
    zero_pair_correlation,
    zero_spacing_histogram,
)
from .zeta_fields import dedekind_zeta

ensure_state_dirs()
prepend_managed_tools_to_path()
database = Database(DATABASE_PATH)
manager = JobManager(database)
installer = EngineInstaller()
add_report_listener(
    lambda entry: database.register_report(
        entry['filename'], entry['kind'], entry['summary'], entry.get('job_id')
    )
)


@asynccontextmanager
async def lifespan(_: FastAPI):
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
async def protect_local_api(request: Request, call_next):
    """Require same-loopback browser context and a per-process API token."""

    if not host_header_is_allowed(request.headers.get("Host", "")):
        return JSONResponse(status_code=400, content={"detail": "Invalid Host header"})
    path = request.url.path
    if path.startswith("/api/") and path != "/api/session":
        if not request_origin_is_safe(request):
            return JSONResponse(
                status_code=403,
                content={"detail": "Cross-site requests are not permitted"},
            )
        if not request_has_valid_token(request):
            return JSONResponse(
                status_code=403,
                content={"detail": "A valid local session token is required"},
            )
    return await call_next(request)


@app.middleware("http")
async def prevent_stale_interface_assets(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Numerisect-UI"] = "workstation-20260907"
    return response


app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


Backend = Literal[
    "auto", "yafu", "hybrid", "cado", "msieve", "cross_verify",
    "pari_trial", "squfof", "ecm_campaign", "tune", "yafu_rho", "yafu_pm1", "yafu_pp1",
    "yafu_ecm", "yafu_siqs", "yafu_nfs", "yafu_snfs", "yafu_fermat",
]


class JobRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=100_000)
    backend: Backend = "auto"
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    pretest_level: int = Field(default=DEFAULT_PRETEST_LEVEL, ge=1, le=100)
    trial_bound: int = Field(default=100_000, ge=2, le=100_000_000)
    cado_parameter_size: int | None = Field(default=None, ge=1, le=10000)
    # GMP-ECM campaign parameters (roadmap item 5); ignored by other backends.
    ecm_b1: int | None = Field(default=None, ge=100, le=10**12)
    ecm_b2: str | None = Field(default=None, max_length=40, pattern=r"^\d+(-\d+)?$")
    ecm_curves: int | None = Field(default=None, ge=1, le=1_000_000)
    ecm_sigma: str | None = Field(default=None, max_length=40, pattern=r"^\d+(:\d+)?$")
    ecm_param: int | None = Field(default=None, ge=0, le=3)


class BatchJobRequest(BaseModel):
    expressions: list[str] = Field(min_length=1, max_length=100)
    backend: Backend = "auto"
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    pretest_level: int = Field(default=DEFAULT_PRETEST_LEVEL, ge=1, le=100)
    trial_bound: int = Field(default=100_000, ge=2, le=100_000_000)
    cado_parameter_size: int | None = Field(default=None, ge=1, le=10000)


class BatchExportRequest(BaseModel):
    job_ids: list[str] = Field(min_length=1, max_length=100)


class EngineInstallRequest(BaseModel):
    confirm: Literal[True]


class ContinueCofactorRequest(BaseModel):
    factor_index: int = Field(ge=0, le=100_000)
    backend: Backend = "auto"
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    pretest_level: int = Field(default=DEFAULT_PRETEST_LEVEL, ge=1, le=100)
    trial_bound: int = Field(default=100_000, ge=2, le=100_000_000)


class PrimeCheckRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=100_000)
    mode: Literal["fast", "proven"] = "proven"
    certificate: bool = False


class PrimeClassificationRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=100_000)
    per_test_seconds: int = Field(default=2, ge=1, le=10)


class CertificateVerifyRequest(BaseModel):
    certificate_data: str = Field(min_length=1, max_length=2_000_000)


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
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)


class PrimesAfterRequest(BaseModel):
    start: str = Field(min_length=1, max_length=100_000)
    count: int = Field(ge=1, le=100_000)


class PrimeIndexRequest(BaseModel):
    index: int = Field(ge=1, le=10**29)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)


class RelativePrimeRequest(BaseModel):
    start: str = Field(min_length=1, max_length=100_000)
    index: int = Field(ge=1, le=100_000)
    direction: Literal["after", "before"] = "after"


class PrimeCountRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=100_000)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)


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


class CharacterSymbolRequest(BaseModel):
    a: str = Field(min_length=1, max_length=100_000)
    n: str = Field(min_length=1, max_length=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class ChineseRemainderRequest(BaseModel):
    residues: list[str] = Field(min_length=1, max_length=256)
    moduli: list[str] = Field(min_length=1, max_length=256)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class ModularRootRequest(BaseModel):
    value: str = Field(min_length=1, max_length=100_000)
    exponent: int = Field(ge=1, le=1_000_000)
    modulus: str = Field(min_length=1, max_length=100_000)
    limit: int = Field(default=10_000, ge=1, le=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class DiscreteLogRequest(BaseModel):
    target: str = Field(min_length=1, max_length=100_000)
    base: str = Field(min_length=1, max_length=100_000)
    modulus: str = Field(min_length=1, max_length=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class UnitGroupRequest(BaseModel):
    modulus: str = Field(min_length=1, max_length=100_000)
    limit: int = Field(default=1_000, ge=1, le=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class PolynomialFactorRequest(BaseModel):
    coefficients: list[str] = Field(min_length=2, max_length=101)
    prime_modulus: str = Field(min_length=1, max_length=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class ArithmeticFunctionsRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    divisor_exponent: int = Field(default=2, ge=0, le=1_000)
    smooth_bound: str = Field(default="100", min_length=1, max_length=100_000)
    quadratic_form_d: int = Field(default=1, ge=1, le=1_000_000)
    divisor_limit: int = Field(default=1_000, ge=0, le=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class PrimalityLaboratoryRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    base: str = Field(default="2", min_length=1, max_length=100_000)
    proof_mode: Literal["automatic", "n_minus_1", "aprcl", "ecpp"] = "automatic"
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class SpecialFormTestRequest(BaseModel):
    kind: Literal["mersenne", "fermat"]
    parameter: str = Field(min_length=1, max_length=100_000)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class PerfectPowerRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class FactorStrategyRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    trial_bound: int = Field(default=10_000, ge=2, le=1_000_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class PrimeApproximationRequest(BaseModel):
    x: str = Field(min_length=1, max_length=100_000)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class SummatoryFunctionsRequest(BaseModel):
    x: str = Field(min_length=1, max_length=100_000)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class EisensteinPrimeRequest(BaseModel):
    a: str = Field(min_length=1, max_length=100_000)
    b: str = Field(min_length=1, max_length=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class QuadraticPrimeDecompositionRequest(BaseModel):
    radicand: str = Field(min_length=1, max_length=100_000)
    prime: str = Field(min_length=1, max_length=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class SpecialPrimeFamilyRequest(BaseModel):
    kind: Literal[
        "mersenne", "fermat", "cullen", "woodall", "wagstaff",
        "repunit", "primorial", "factorial",
    ]
    start_index: int = Field(default=1, ge=0, le=10_000)
    end_index: int = Field(default=100, ge=0, le=10_000)
    limit: int = Field(default=1_000, ge=1, le=100_000)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class CunninghamChainRequest(BaseModel):
    start_prime: str = Field(min_length=1, max_length=100_000)
    length: int = Field(default=10, ge=1, le=100_000)
    kind: Literal[1, 2] = 1
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class NttPrimeRequest(BaseModel):
    bits: int = Field(default=64, ge=2, le=1_000_000)
    power_two: int = Field(default=20, ge=1, le=999_999)
    count: int = Field(default=10, ge=1, le=100_000)
    candidate_limit: int = Field(default=1_000_000, ge=1, le=10_000_000)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class TonelliShanksRequest(BaseModel):
    value: str = Field(min_length=1, max_length=100_000)
    prime: str = Field(min_length=1, max_length=100_000)
    trace_limit: int = Field(default=1_000, ge=0, le=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class HenselRootsRequest(BaseModel):
    coefficients: list[str] = Field(min_length=2, max_length=101)
    prime: str = Field(min_length=1, max_length=100_000)
    exponent: int = Field(default=2, ge=1, le=100_000)
    limit: int = Field(default=10_000, ge=1, le=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class DistributionRequest(BaseModel):
    modulus: str = Field(min_length=1, max_length=100_000)
    limit: int = Field(default=10_000, ge=1, le=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class PowerResidueRequest(DistributionRequest):
    exponent: int = Field(default=2, ge=1, le=1_000_000)


class ValuationRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    prime: str = Field(min_length=1, max_length=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class CyclotomicRequest(BaseModel):
    index: int = Field(default=5, ge=1, le=10_000)
    prime: str = Field(default="2", min_length=1, max_length=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class AliquotRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    max_steps: int = Field(default=100, ge=1, le=100_000)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class DivisorClassificationRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class ZetaEvaluateRequest(BaseModel):
    sigma: str = Field(default="0.5", min_length=1, max_length=10_000)
    ordinate: str = Field(default="14.134725", min_length=1, max_length=10_000)
    precision: int = Field(default=50, ge=16, le=1000)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class ZetaHardyRequest(BaseModel):
    ordinate: str = Field(default="14.134725", min_length=1, max_length=10_000)
    precision: int = Field(default=50, ge=16, le=1000)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class ZetaXiEtaRequest(ZetaEvaluateRequest):
    kind: Literal["xi", "eta"] = "xi"


class ZetaIndexedRequest(BaseModel):
    index: str = Field(default="0", min_length=1, max_length=10_000)
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


class ZetaExplicitPrimeCountRequest(BaseModel):
    bound: str = Field(default="100", min_length=1, max_length=100)
    zeros: int = Field(default=200, ge=1, le=5000)
    precision: int = Field(default=30, ge=16, le=1000)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class ZetaChebyshevPsiRequest(BaseModel):
    bound: str = Field(default="100", min_length=1, max_length=100)
    zeros: int = Field(default=200, ge=1, le=5000)
    precision: int = Field(default=30, ge=16, le=1000)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class ZetaRiemannSiegelRequest(BaseModel):
    sigma: str = Field(default="0.5", min_length=1, max_length=10_000)
    ordinate: str = Field(default="1000", min_length=1, max_length=10_000)
    terms: int = Field(default=6, ge=0, le=20)
    precision: int = Field(default=30, ge=16, le=1000)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class ZetaEulerProductRequest(BaseModel):
    sigma: str = Field(default="2", min_length=1, max_length=10_000)
    ordinate: str = Field(default="0", min_length=1, max_length=10_000)
    primes: int = Field(default=4096, ge=1, le=200_000)
    precision: int = Field(default=30, ge=16, le=1000)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class ZetaSpacingRequest(BaseModel):
    start_index: str = Field(default="1", min_length=1, max_length=10_000)
    count: int = Field(default=500, ge=2, le=20_000)
    bins: int = Field(default=30, ge=4, le=200)
    precision: int = Field(default=25, ge=16, le=1000)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class ZetaPairCorrelationRequest(BaseModel):
    start_index: str = Field(default="1", min_length=1, max_length=10_000)
    count: int = Field(default=1000, ge=2, le=20_000)
    bins: int = Field(default=60, ge=4, le=400)
    window: int = Field(default=3, ge=1, le=20)
    precision: int = Field(default=25, ge=16, le=1000)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class ZetaGramBlockRequest(BaseModel):
    start_index: str = Field(default="0", min_length=1, max_length=100)
    count: int = Field(default=200, ge=2, le=20_000)
    precision: int = Field(default=30, ge=16, le=1000)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class ZetaBacklundRequest(BaseModel):
    lower: str = Field(default="0", min_length=1, max_length=10_000)
    upper: str = Field(default="1000", min_length=1, max_length=10_000)
    samples: int = Field(default=600, ge=1, le=20_000)
    precision: int = Field(default=25, ge=16, le=1000)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class ZetaCharacterRequest(BaseModel):
    modulus: str = Field(default="12", min_length=1, max_length=100)
    limit: int = Field(default=200, ge=1, le=100_000)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class ZetaLFunctionRequest(BaseModel):
    modulus: str = Field(default="4", min_length=1, max_length=100)
    number: str = Field(default="3", min_length=1, max_length=100)
    sigma: str = Field(default="1", min_length=1, max_length=10_000)
    ordinate: str = Field(default="0", min_length=1, max_length=10_000)
    precision: int = Field(default=50, ge=16, le=1000)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class ZetaLZerosRequest(BaseModel):
    modulus: str = Field(default="4", min_length=1, max_length=100)
    number: str = Field(default="3", min_length=1, max_length=100)
    lower: str = Field(default="0.5", min_length=1, max_length=10_000)
    upper: str = Field(default="50", min_length=1, max_length=10_000)
    samples: int = Field(default=1000, ge=8, le=200_000)
    precision: int = Field(default=25, ge=16, le=1000)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    timeout_seconds: int = Field(default=0, ge=0, le=3600)


class ZetaDedekindRequest(BaseModel):
    family: Literal["quadratic", "cyclotomic", "polynomial"] = "quadratic"
    parameter: str = Field(default="-1", min_length=1, max_length=100)
    polynomial: str = Field(default="", max_length=200)
    sigma: str = Field(default="2", min_length=1, max_length=10_000)
    ordinate: str = Field(default="0", min_length=1, max_length=10_000)
    zero_height: int = Field(default=30, ge=1, le=200)
    zero_limit: int = Field(default=50, ge=1, le=500)
    class_data: bool = True
    precision: int = Field(default=38, ge=20, le=200)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/session", include_in_schema=False)
def create_browser_session(request: Request) -> JSONResponse:
    if request.url.hostname not in LOOPBACK_HOSTS:
        raise HTTPException(status_code=400, detail="A loopback host is required")
    response = JSONResponse({"request_token": REQUEST_TOKEN})
    response.set_cookie(
        REQUEST_TOKEN_COOKIE,
        REQUEST_TOKEN,
        httponly=True,
        samesite="strict",
        path="/api",
    )
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


def _public_setup_status() -> dict[str, object]:
    status = installer.status()
    allowed = {
        "state",
        "message",
        "missing",
        "requested",
        "current",
        "updated_at",
    }
    return {key: value for key, value in status.items() if key in allowed}


def _public_job(job: dict[str, object]) -> dict[str, object]:
    allowed = {
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
        "ecm_b1",
        "ecm_b2",
        "ecm_curves",
        "ecm_sigma",
        "ecm_curves_done",
        "cado_parameter_size",
        "factors",
        "warning",
        "error",
        "parent_job_id",
    }
    result = {key: value for key, value in job.items() if key in allowed}
    result["result_available"] = bool(job.get("result_path"))
    if job.get("result_path"):
        manifest = Path(str(job["result_path"])).with_suffix(".json")
        result["manifest_file"] = manifest.name if manifest.is_file() else None
    else:
        result["manifest_file"] = None
    return result


@app.get("/api/capabilities")
def capabilities() -> dict[str, object]:
    parameters = discover_cado_parameters()
    return {
        "version": __version__,
        "cpu_count": os.cpu_count() or 1,
        "cado_threshold": DEFAULT_CADO_THRESHOLD,
        "engines": {
            name: {"available": bool(path)}
            for name, path in {
                "yafu": executable_path("yafu"),
                "msieve": executable_path("msieve"),
                "cado": executable_path("cado-nfs.py"),
                "ecm": executable_path("ecm"),
                "pari/gp": executable_path("gp"),
                "flint/zeta": executable_path("numerisect-zeta"),
                "primesieve": executable_path("primesieve"),
                "primecount": executable_path("primecount"),
            }.items()
        },
        "cado_parameters": [
            {"size": parameter.size}
            for parameter in parameters
        ],
        "setup": _public_setup_status(),
    }


@app.get("/api/setup")
def setup_status() -> dict[str, object]:
    return _public_setup_status()


@app.post("/api/setup/install", status_code=202)
def install_missing_engines(_: EngineInstallRequest) -> dict[str, object]:
    installer.start_if_needed()
    return _public_setup_status()


@app.get("/api/setup/log")
def setup_log() -> dict[str, str]:
    path = installer.log_path
    return {
        "available": "yes" if path.exists() else "no",
        "note": "The detailed engine setup log is available only in the local state directory.",
    }


@app.post("/api/diagnostics")
def create_diagnostic_report() -> dict[str, object]:
    result = system_diagnostics()
    lines = [str(result["note"]), ""]
    lines.extend(f"{key}: {value}" for key, value in result["metrics"].items())
    lines.extend(["", "Engine | Status | Pinned source | Revision | License"])
    lines.extend(" | ".join(row) for row in result["rows"])
    lines.extend(["", "Build prerequisite | Status"])
    lines.extend(" | ".join(row) for row in result["prerequisites"])
    path = save_prime_output("diagnostics", "Sanitized system diagnostics", lines)
    return {**result, "output_file": path.name}


# --- Application infrastructure: workspaces, search, exports, batch import, ------------
# --- caching, scheduling, adapters, catalogues, and performance history. ---------------


class WorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    notes: str = Field("", max_length=20000)
    job_ids: list[str] = Field(default_factory=list, max_length=500)
    report_files: list[str] = Field(default_factory=list, max_length=500)
    ui_state: dict = Field(default_factory=dict)


class WorkspaceUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    notes: str | None = Field(None, max_length=20000)
    job_ids: list[str] | None = Field(None, max_length=500)
    report_files: list[str] | None = Field(None, max_length=500)
    ui_state: dict | None = None


class BatchImportRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2_000_000)
    format: Literal["auto", "txt", "csv", "json"] = "auto"
    filename: str | None = Field(None, max_length=200)
    queue: bool = False
    threads: int = Field(1, ge=1, le=256)
    priority: int = Field(0, ge=-10, le=10)
    timeout_seconds: int = Field(60, ge=1, le=600)


class PriorityRequest(BaseModel):
    priority: int = Field(..., ge=-10, le=10)


class ReorderRequest(BaseModel):
    job_ids: list[str] = Field(..., min_length=1, max_length=500)


class OeisRequest(BaseModel):
    terms: list[str] = Field(..., min_length=1, max_length=64)
    limit: int = Field(5, ge=1, le=20)
    confirm_network: bool = False


class CatalogueRequest(BaseModel):
    expression: str = Field(..., min_length=1, max_length=MAX_EXPRESSION_CHARACTERS)
    catalogue: str | None = Field(None, max_length=80)
    remote: bool = False
    confirm_network: bool = False


def _workspace_or_404(workspace_id: str) -> dict:
    record = database.get_workspace(workspace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return record


@app.post("/api/workspaces")
def create_workspace(request: WorkspaceRequest) -> dict:
    """Save a named workspace referencing jobs, reports, and interface state."""

    try:
        fields = validate_workspace_fields(
            name=request.name,
            notes=request.notes,
            job_ids=request.job_ids,
            report_files=request.report_files,
            ui_state=request.ui_state,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return database.create_workspace(
        workspace_id=new_workspace_id(),
        name=fields["name"],
        notes=fields.get("notes", ""),
        job_ids=fields.get("job_ids", []),
        report_files=fields.get("report_files", []),
        ui_state=fields.get("ui_state", {}),
    )


@app.get("/api/workspaces")
def list_workspaces(limit: int = Query(200, ge=1, le=1000)) -> dict:
    """List saved workspaces, newest first."""

    return {"workspaces": database.list_workspaces(limit=limit)}


@app.get("/api/workspaces/{workspace_id}")
def read_workspace(workspace_id: str) -> dict:
    """Load one workspace."""

    return _workspace_or_404(workspace_id)


@app.post("/api/workspaces/{workspace_id}")
def update_workspace(workspace_id: str, request: WorkspaceUpdateRequest) -> dict:
    """Update selected fields of one workspace."""

    _workspace_or_404(workspace_id)
    try:
        fields = validate_workspace_fields(
            name=request.name,
            notes=request.notes,
            job_ids=request.job_ids,
            report_files=request.report_files,
            ui_state=request.ui_state,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not fields:
        raise HTTPException(status_code=422, detail="Supply at least one field to update")
    updated = database.update_workspace(workspace_id, **fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return updated


@app.delete("/api/workspaces/{workspace_id}")
def delete_workspace(workspace_id: str) -> dict:
    """Delete one workspace. Jobs and reports are not affected."""

    if not database.delete_workspace(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"deleted": workspace_id}


@app.get("/api/reports")
def search_reports(
    q: str | None = Query(None, max_length=200),
    kind: str | None = Query(None, max_length=60),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    """Search the index of saved report files."""

    rows = database.search_reports(q=q, kind=kind, limit=limit, offset=offset)
    return {"reports": rows, "count": len(rows), "total": database.report_count()}


@app.get("/api/history/performance")
def performance_history(bucket_digits: int = Query(10, ge=1, le=100)) -> dict:
    """Aggregate completed-job runtimes by engine and decimal-digit bucket."""

    return {
        "buckets": database.performance_history(bucket_digits=bucket_digits),
        "bucket_digits": bucket_digits,
        "note": "Timings are measured locally and depend on hardware, threads, and input.",
    }


@app.get("/api/queue")
def read_queue() -> dict:
    """Show queued and running jobs in dispatch order."""

    return {"queue": manager.queue_snapshot(), "max_parallel_jobs": MAX_PARALLEL_JOBS}


@app.post("/api/jobs/{job_id}/priority")
def set_job_priority(job_id: str, request: PriorityRequest) -> dict:
    """Change one job's scheduling priority; higher runs sooner."""

    try:
        return _public_job(manager.set_priority(job_id, request.priority))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/jobs/reorder")
def reorder_jobs(request: ReorderRequest) -> dict:
    """Reorder queued jobs; the supplied order becomes the dispatch order."""

    try:
        return {"queue": [_public_job(job) for job in manager.reorder(request.job_ids)]}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/jobs/{job_id}/pause")
def pause_job(job_id: str) -> dict:
    """Suspend a running job's process group with SIGSTOP."""

    try:
        return _public_job(manager.pause(job_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/jobs/{job_id}/resume-paused")
def resume_paused_job(job_id: str) -> dict:
    """Continue a paused job's process group with SIGCONT."""

    try:
        return _public_job(manager.resume_paused(job_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/batch/import")
def import_batch(request: BatchImportRequest) -> dict:
    """Expand a TXT/CSV/JSON document of integers, ranges, expressions, and families.

    Ranges and polynomial families are expanded by PARI/GP, never in Python.
    """

    try:
        items = parse_batch_document(request.content, request.format, request.filename)
        expanded = expand_batch_items(items, timeout=request.timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PrimeEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    queued: list[dict] = []
    if request.queue:
        for value in expanded["values"]:
            try:
                number = evaluate_integer(value)
            except ExpressionError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            try:
                job = manager.create(
                    expression=value,
                    number=number,
                    requested_backend="auto",
                    threads=request.threads,
                    pretest_level=DEFAULT_PRETEST_LEVEL,
                    trial_bound=100_000,
                    cado_parameter_size=None,
                    priority=request.priority,
                )
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            queued.append(_public_job(job))
    return {
        "items": expanded["classified"],
        "values": expanded["values"],
        "expanded_count": expanded["expanded_count"],
        "queued": queued,
        "engine": "PARI/GP",
    }


@app.get("/api/exports/jobs")
def export_job_search(
    format: str = Query("json", max_length=20),
    q: str | None = Query(None, max_length=200),
    status: str | None = Query(None, max_length=40),
    engine: str | None = Query(None, max_length=60),
    limit: int = Query(100, ge=1, le=1000),
) -> Response:
    """Export job search results in any supported interchange format."""

    try:
        chosen = normalize_format(format)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    rows = database.search_jobs(q=q, status=status, engine=engine, limit=limit)
    body = serialize_jobs(rows, chosen)
    filename = f"numerisect-jobs.{EXTENSIONS[chosen]}"
    return Response(
        content=body,
        media_type=MEDIA_TYPES[chosen],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/exports/jobs/{job_id}")
def export_single_job(job_id: str, format: str = Query("json", max_length=20)) -> Response:
    """Export one factorization job in any supported interchange format."""

    try:
        chosen = normalize_format(format)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    job = database.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    body = serialize_job(job, chosen)
    filename = f"numerisect-{job_id[:12]}.{EXTENSIONS[chosen]}"
    return Response(
        content=body,
        media_type=MEDIA_TYPES[chosen],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/exports/reports/{filename}")
def export_saved_report(filename: str, format: str = Query("json", max_length=20)) -> Response:
    """Re-container a saved text report; the engine-produced body is unchanged."""

    try:
        chosen = normalize_format(format)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = safe_output_path(filename)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    body = export_report_text(path.name, path.read_text(encoding="utf-8", errors="replace"), chosen)
    return Response(
        content=body,
        media_type=MEDIA_TYPES[chosen],
        headers={
            "Content-Disposition": f'attachment; filename="{path.stem}.{EXTENSIONS[chosen]}"'
        },
    )


@app.get("/api/cache")
def read_cache_stats() -> dict:
    """Report result-cache size and hit counts."""

    return {**database.cache_stats(), "enabled": RESULT_CACHE_ENABLED}


@app.delete("/api/cache")
def clear_cache(operation: str | None = Query(None, max_length=200)) -> dict:
    """Discard cached results, optionally for one operation path only."""

    return {"removed": database.cache_clear(operation)}


@app.get("/api/adapters")
def list_adapters() -> dict:
    """List built-in and user-declared engine adapters."""

    return REGISTRY.describe()


@app.get("/api/catalogues")
def list_catalogues() -> dict:
    """Show local catalogue files and the current network permission state."""

    return {"local": list_local_catalogues(), "network": network_status()}


@app.post("/api/catalogues/oeis")
def lookup_oeis(request: OeisRequest) -> dict:
    """Search OEIS for a sequence. Disabled unless explicitly permitted."""

    try:
        return oeis_lookup(request.terms, request.confirm_network, request.limit)
    except NetworkNotPermitted as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CatalogueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/catalogues/factors")
def lookup_known_factors(request: CatalogueRequest) -> dict:
    """Look up claimed factors locally, or remotely when explicitly permitted.

    Claimed factors are verified natively before being reported as divisors.
    """

    try:
        number = evaluate_arbitrary_integer(request.expression)
    except ExpressionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        if request.remote:
            result = remote_catalogue_lookup(number, request.confirm_network)
            claimed = result.get("claimed_factors", [])
        else:
            result = local_catalogue_lookup(number, request.catalogue)
            claimed = [value for claim in result["claims"] for value in claim["factors"]]
    except NetworkNotPermitted as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CatalogueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    unique = [value for value in dict.fromkeys(claimed) if str(value).strip() not in {"", "0", "1"}]
    try:
        verification = verify_claimed_factors(number, unique)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PrimeEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        **result,
        "verified": verification["factors"],
        "product_matches": verification["product_matches"],
        "cofactor": verification["cofactor"],
        "verification": "PARI/GP divisibility, primality, and product check",
        "engine": "PARI/GP",
    }


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
    certificate_data = str(result.pop("certificate_data"))
    lines = [
        f"Input: {number}",
        f"Mode: {request.mode}",
        f"Classification: {result['classification']}",
        str(result["note"]),
    ]
    if certificate:
        lines.extend(
            [
                "", "Primality certificate", "---------------------", certificate,
                "", "Machine-readable PARI certificate", "---------------------------------",
                certificate_data,
            ]
        )
    path = save_prime_output(
        "primality",
        "Primality check",
        lines,
    )
    result["output_file"] = path.name
    result["certificate_included"] = bool(certificate)
    return result


@app.post("/api/primes/verify-certificate")
def verify_prime_certificate(request: CertificateVerifyRequest) -> dict[str, object]:
    try:
        result = verify_primality_certificate(request.certificate_data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PrimeEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    table = {
        **result,
        "metrics": {
            "Certificate number": result["number"],
            "Valid": "yes" if result["valid"] else "no",
        },
        "columns": ["Verification", "Verdict"],
        "rows": [["PARI ECPP certificate", "valid" if result["valid"] else "invalid"]],
    }
    return _save_manipulation_report(
        "certificate-verification", "Primality certificate verification", table
    )


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
        values, truncated, next_start = primes_in_range(
            start, end, request.limit, request.threads
        )
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
        "note": "Every returned value is exact. primesieve is used for 64-bit intervals; arbitrary-precision intervals fall back to rigorously checked PARI/GP iteration.",
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
        value = nth_prime(request.index, request.threads)
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
        "note": "Calculated exactly by parallel primecount when available, with a rigorous PARI/GP fallback.",
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
        value = prime_count(number, request.threads)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = save_prime_output(
        "prime-count", f"Prime count through {number}", [f"pi({number}) = {value}"]
    )
    return {
        "label": f"π({number})",
        "value": str(value),
        "output_file": path.name,
        "note": "Exact count of positive primes less than or equal to the input, calculated by primecount when available (through 10^31) with PARI/GP fallback.",
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
    # PARI structure predicates, rendered before the report is assembled so the
    # f-strings below stay valid on Python 3.11 (no nested same-quote f-strings).
    prime_power_summary = (
        f"{result['prime_power_base']}^{result['prime_power_exponent']}"
        if result["is_prime_power"] else "no"
    )
    totient_summary = (
        f"yes, phi({result['totient_witness']}) = n" if result["is_totient"] else "no"
    )
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
        f"Prime power (PARI isprimepower): {prime_power_summary}",
        f"Powerful (PARI ispowerful): {'yes' if result['is_powerful'] else 'no'}",
        f"Totient value (PARI istotient): {totient_summary}",
        f"Fundamental discriminant (PARI isfundamental): {'yes' if result['is_fundamental_discriminant'] else 'no'}",
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


class VisualSpiralRequest(BaseModel):
    start: str = Field(default="1", min_length=1, max_length=10_000)
    count: int = Field(default=10_000, ge=1, le=1_000_000)
    layout: Literal["ulam", "sacks", "polar"] = "ulam"
    highlight: Literal["none", "residue", "polynomial"] = "none"
    a: int = Field(default=1, ge=-1_000_000, le=1_000_000)
    b: int = Field(default=1, ge=-1_000_000, le=1_000_000)
    c: int = Field(default=41, ge=-1_000_000, le=1_000_000)
    modulus: int = Field(default=4, ge=2, le=1_000_000)
    residue: int = Field(default=1, ge=0, le=999_999)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class VisualEisensteinRequest(BaseModel):
    norm_bound: int = Field(default=2_000, ge=2, le=200_000)
    limit: int = Field(default=20_000, ge=1, le=200_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class VisualWheelRequest(BaseModel):
    modulus: int = Field(default=30, ge=2, le=10_000)
    start: int = Field(default=0, ge=0)
    count: int = Field(default=600, ge=1, le=200_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class VisualHeatmapRequest(BaseModel):
    start: str = Field(default="1", min_length=1, max_length=10_000)
    end: str = Field(default="100000", min_length=1, max_length=10_000)
    modulus: int = Field(default=30, ge=2, le=360)
    bins: int = Field(default=50, ge=1, le=200)
    timeout_seconds: int = Field(default=120, ge=1, le=3600)


class VisualGapTimelineRequest(BaseModel):
    start: str = Field(default="1", min_length=1, max_length=10_000)
    end: str = Field(default="100000", min_length=1, max_length=10_000)
    limit: int = Field(default=20_000, ge=1, le=200_000)
    timeout_seconds: int = Field(default=120, ge=1, le=3600)


class VisualPrimeRaceRequest(BaseModel):
    start: str = Field(default="1", min_length=1, max_length=10_000)
    end: str = Field(default="100000", min_length=1, max_length=10_000)
    modulus: int = Field(default=4, ge=2, le=360)
    checkpoints: int = Field(default=200, ge=1, le=1_000)
    event_limit: int = Field(default=5_000, ge=1, le=100_000)
    timeout_seconds: int = Field(default=120, ge=1, le=3600)


class VisualSieveRequest(BaseModel):
    kind: Literal["eratosthenes", "segmented", "sundaram", "atkin"] = "eratosthenes"
    n: int = Field(default=200, ge=2, le=5_000)
    segment_size: int | None = Field(default=None, ge=1, le=5_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class VisualComplexityRequest(BaseModel):
    job_limit: int = Field(default=500, ge=1, le=500)


def _save_visual_report(kind: str, heading: str, result: dict, lines: list[str]) -> dict:
    path = save_prime_output(kind, heading, [result["note"], ""] + lines)
    return {**result, "output_file": path.name}


@app.post("/api/visual/spiral")
def create_visual_spiral(request: VisualSpiralRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        result = spiral_primes(
            start,
            request.count,
            layout=request.layout,
            highlight=request.highlight,
            a=request.a,
            b=request.b,
            c=request.c,
            modulus=request.modulus,
            residue=request.residue,
            timeout=request.timeout_seconds,
        )
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    highlighted = set(result["highlighted"])
    return _save_visual_report(
        "visual-spiral",
        f"{result['layout'].title()} spiral over {result['start']} through {result['end']}",
        result,
        [f"{prime}{' *' if prime in highlighted else ''}" for prime in result["primes"]],
    )


@app.post("/api/visual/eisenstein-lattice")
def create_visual_eisenstein_lattice(request: VisualEisensteinRequest) -> dict[str, object]:
    try:
        result = eisenstein_lattice(request.norm_bound, request.limit, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    kinds = result["kinds"]
    return _save_visual_report(
        "visual-eisenstein-lattice",
        f"Eisenstein primes of norm at most {result['norm_bound']}",
        result,
        [
            f"{point['a']} + {point['b']}ω: norm {point['norm']}, {kinds[str(point['kind'])]}"
            for point in result["points"]
        ],
    )


@app.post("/api/visual/modular-wheel")
def create_visual_modular_wheel(request: VisualWheelRequest) -> dict[str, object]:
    try:
        result = modular_wheel(
            request.modulus, request.start, request.count, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_visual_report(
        "visual-modular-wheel",
        f"Modular wheel base {result['modulus']} from {result['start']}",
        result,
        [f"Euler totient φ({result['modulus']}) = {result['totient']}", ""]
        + [
            f"spoke {spoke['residue']}: {spoke['prime_count']} primes, "
            f"coprime {'yes' if spoke['coprime'] else 'no'}"
            for spoke in result["spokes"]
        ],
    )


@app.post("/api/visual/residue-heatmap")
def create_visual_residue_heatmap(request: VisualHeatmapRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        end = evaluate_arbitrary_integer(request.end)
        result = residue_heatmap(
            start, end, request.modulus, request.bins, request.timeout_seconds
        )
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_visual_report(
        "visual-residue-heatmap",
        f"Residue-class heatmap modulo {result['modulus']}",
        result,
        [
            f"{row['start']}-{row['end']}: "
            + " ".join(str(count) for count in row["counts"])
            for row in result["bins"]
        ]
        + [""]
        + [
            f"residue {item['residue']}: {item['total']} primes, "
            f"coprime {'yes' if item['coprime'] else 'no'}"
            for item in result["residues"]
        ],
    )


@app.post("/api/visual/gap-timeline")
def create_visual_gap_timeline(request: VisualGapTimelineRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        end = evaluate_arbitrary_integer(request.end)
        result = gap_timeline(start, end, request.limit, request.timeout_seconds)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_visual_report(
        "visual-gap-timeline",
        f"Prime-gap timeline for {result['start']} through {result['end']}",
        result,
        [
            f"record gap {record['gap']} from {record['from']} to {record['to']} "
            f"(merit {record['merit']})"
            for record in result["records"]
        ]
        + [""]
        + [f"{gap['prime']} +{gap['gap']}" for gap in result["gaps"]],
    )


@app.post("/api/visual/prime-race")
def create_visual_prime_race(request: VisualPrimeRaceRequest) -> dict[str, object]:
    try:
        start = evaluate_arbitrary_integer(request.start)
        end = evaluate_arbitrary_integer(request.end)
        result = visual_prime_race(
            start,
            end,
            request.modulus,
            request.checkpoints,
            request.event_limit,
            request.timeout_seconds,
        )
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_visual_report(
        "visual-prime-race",
        f"Prime race modulo {result['modulus']}",
        result,
        [f"final leader: class {result['leader']}", ""]
        + [f"class {item['residue']}: {item['count']} primes" for item in result["final"]]
        + [""]
        + [
            f"lead change at {event['prime']} to class {event['leader']}"
            for event in result["events"]
        ],
    )


@app.post("/api/visual/sieve-trace")
def create_visual_sieve_trace(request: VisualSieveRequest) -> dict[str, object]:
    try:
        result = sieve_trace(
            request.kind, request.n, request.segment_size, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    legend = result["step_kinds"]
    return _save_visual_report(
        "visual-sieve-trace",
        f"{result['kind'].title()} sieve trace to {result['n']}",
        result,
        [
            f"step {index + 1}: {legend[str(step[0])]} value {step[1]} "
            f"(a={step[2]}, b={step[3]}, flag={step[4]})"
            for index, step in enumerate(result["steps"])
        ]
        + ["", "verified survivors: " + " ".join(str(prime) for prime in result["primes"])],
    )


@app.post("/api/visual/complexity")
def create_visual_complexity_dashboard(request: VisualComplexityRequest) -> dict[str, object]:
    result = complexity_dashboard(database.list_jobs(request.job_limit))
    return _save_visual_report(
        "visual-complexity",
        "Algorithm complexity and measured timings",
        result,
        [
            f"{row['algorithm']} [{row['category']}]: time {row['time']}; "
            f"memory {row['memory']}; source {row['source']}"
            for row in result["reference"]
        ]
        + [""]
        + [
            f"{group['engine']} @ {group['digits']} digits: {group['runs']} runs, "
            f"median {group['median_seconds']} s (min {group['min_seconds']} s, "
            f"max {group['max_seconds']} s)"
            for group in result["groups"]
        ],
    )


@app.post("/api/number-theory/symbols")
def calculate_character_symbols(request: CharacterSymbolRequest) -> dict:
    try:
        result = character_symbols(request.a, request.n, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("character-symbols", "Character symbols", result)


@app.post("/api/number-theory/crt")
def calculate_chinese_remainder(request: ChineseRemainderRequest) -> dict:
    try:
        result = chinese_remainder(request.residues, request.moduli, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("chinese-remainder", "Chinese remainder system", result)


@app.post("/api/number-theory/modular-roots")
def calculate_modular_roots(request: ModularRootRequest) -> dict:
    try:
        result = modular_roots(
            request.value, request.exponent, request.modulus, request.limit,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("modular-roots", "Power congruence roots", result)


@app.post("/api/number-theory/discrete-log")
def calculate_discrete_logarithm(request: DiscreteLogRequest) -> dict:
    try:
        result = discrete_logarithm(
            request.target, request.base, request.modulus, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("discrete-log", "Discrete logarithm", result)


@app.post("/api/number-theory/unit-group")
def calculate_unit_group(request: UnitGroupRequest) -> dict:
    try:
        result = unit_group(request.modulus, request.limit, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("unit-group", "Multiplicative group structure", result)


@app.post("/api/number-theory/polynomial")
def calculate_polynomial_factorization(request: PolynomialFactorRequest) -> dict:
    try:
        result = factor_polynomial(
            request.coefficients, request.prime_modulus, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("polynomial-factorization", "Polynomial factorization", result)


@app.post("/api/number-theory/arithmetic-functions")
def calculate_arithmetic_functions(request: ArithmeticFunctionsRequest) -> dict:
    try:
        result = arithmetic_functions(
            request.number,
            request.divisor_exponent,
            request.smooth_bound,
            request.quadratic_form_d,
            request.divisor_limit,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("arithmetic-functions", "Extended arithmetic functions", result)


@app.post("/api/number-theory/primality-lab")
def run_primality_laboratory(request: PrimalityLaboratoryRequest) -> dict:
    modes = {"automatic": 0, "n_minus_1": 1, "aprcl": 2, "ecpp": 3}
    try:
        result = primality_laboratory(
            request.number, request.base, modes[request.proof_mode], request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("primality-laboratory", "Primality-test comparison", result)


@app.post("/api/number-theory/special-form-test")
def run_special_form_test(request: SpecialFormTestRequest) -> dict:
    try:
        result = special_form_test(request.kind, request.parameter, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("special-form-test", "Special-form primality test", result)


# ---------------------------------------------------------------------------
# Primality laboratory (numerisect/primality_lab.gp via numerisect/primality_lab.py)
# ---------------------------------------------------------------------------
class PrimalityComparisonRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    bases: list[str] = Field(default=["2", "3", "5", "7"], min_length=1, max_length=32)
    budget_seconds: int = Field(default=30, ge=1, le=3600)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class DeterministicWitnessRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class PocklingtonProofRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    budget_seconds: int = Field(default=60, ge=1, le=3600)
    witness_limit: int = Field(default=200, ge=2, le=100_000)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class PrattCertificateRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    max_nodes: int = Field(default=500, ge=1, le=100_000)
    budget_seconds: int = Field(default=60, ge=1, le=3600)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class PrimalityCertificateRequest(BaseModel):
    kind: Literal["pocklington", "pratt"] = "pocklington"
    certificate: str = Field(min_length=3, max_length=200_000)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class ProthTestRequest(BaseModel):
    k: str = Field(default="5", min_length=1, max_length=100_000)
    exponent: int = Field(default=3, ge=1, le=1_000_000)
    base: int = Field(default=2, ge=2, le=1_000_000)
    witness_limit: int = Field(default=200, ge=2, le=100_000)
    budget_seconds: int = Field(default=60, ge=1, le=3600)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class ProthSearchRequest(BaseModel):
    k: str = Field(default="5", min_length=1, max_length=100_000)
    base: int = Field(default=2, ge=2, le=1_000_000)
    n_start: int = Field(default=1, ge=1, le=100_000)
    n_end: int = Field(default=100, ge=1, le=100_000)
    limit: int = Field(default=100, ge=1, le=10_000)
    witness_limit: int = Field(default=200, ge=2, le=100_000)
    budget_seconds: int = Field(default=60, ge=1, le=3600)
    timeout_seconds: int = Field(default=600, ge=1, le=3600)


class LucasSequenceRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    p: int = Field(default=1, ge=-1_000_000, le=1_000_000)
    q: int = Field(default=-1, ge=-1_000_000, le=1_000_000)
    selfridge: bool = True
    witness_limit: int = Field(default=40, ge=1, le=10_000)
    budget_seconds: int = Field(default=60, ge=1, le=3600)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class PseudoprimeTaxonomyRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    bases: list[str] = Field(default=["2", "3"], min_length=1, max_length=32)
    p: int = Field(default=1, ge=-1_000_000, le=1_000_000)
    q: int = Field(default=-1, ge=-1_000_000, le=1_000_000)
    selfridge: bool = True
    budget_seconds: int = Field(default=60, ge=1, le=3600)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class CarmichaelRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    base_limit: int = Field(default=10_000, ge=2, le=10_000_000)
    budget_seconds: int = Field(default=60, ge=1, le=3600)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class ChernickRequest(BaseModel):
    k_start: int = Field(default=1, ge=1, le=100_000_000)
    k_end: int = Field(default=1000, ge=1, le=100_000_000)
    limit: int = Field(default=100, ge=1, le=10_000)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class RepunitSearchRequest(BaseModel):
    base: int = Field(default=10, ge=2, le=1_000_000)
    n_start: int = Field(default=1, ge=1, le=100_000)
    n_end: int = Field(default=100, ge=1, le=100_000)
    limit: int = Field(default=100, ge=1, le=10_000)
    budget_seconds: int = Field(default=60, ge=1, le=3600)
    timeout_seconds: int = Field(default=600, ge=1, le=3600)


class SierpinskiRieselRequest(BaseModel):
    k: str = Field(default="78557", min_length=1, max_length=100_000)
    kind: Literal["sierpinski", "riesel"] = "sierpinski"
    n_max: int = Field(default=1000, ge=1, le=100_000)
    budget_seconds: int = Field(default=30, ge=1, le=3600)
    timeout_seconds: int = Field(default=600, ge=1, le=3600)


class CoveringSetRequest(BaseModel):
    k: str = Field(default="78557", min_length=1, max_length=100_000)
    kind: Literal["sierpinski", "riesel"] = "sierpinski"
    period: int = Field(default=36, ge=1, le=1_000)
    candidates: list[str] = Field(default=[], max_length=64)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class BiTwinChainRequest(BaseModel):
    start: str = Field(default="2", min_length=1, max_length=100_000)
    end: str = Field(default="100000", min_length=1, max_length=100_000)
    min_length: int = Field(default=2, ge=1, le=32)
    limit: int = Field(default=100, ge=1, le=10_000)
    timeout_seconds: int = Field(default=600, ge=1, le=3600)


class PrimeLadderRequest(BaseModel):
    start_prime: str = Field(min_length=1, max_length=10)
    end_prime: str = Field(min_length=1, max_length=10)
    max_steps: int = Field(default=20, ge=1, le=100)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class ConstrainedPrimeRequest(BaseModel):
    bits: int = Field(default=64, ge=8, le=1024)
    kind: Literal["any", "safe", "strong"] = "any"
    modulus: str = Field(default="1", min_length=1, max_length=100_000)
    residue: str = Field(default="0", min_length=1, max_length=100_000)
    certificate: bool = False
    seed: str | None = Field(default=None, max_length=100_000)
    candidate_limit: int = Field(default=100_000, ge=1, le=10_000_000)
    budget_seconds: int = Field(default=60, ge=1, le=3600)
    timeout_seconds: int = Field(default=600, ge=1, le=3600)


class LucasLehmerStepsRequest(BaseModel):
    exponent: int = Field(default=13, ge=2, le=100_000)
    show_limit: int = Field(default=20, ge=0, le=10_000)
    timeout_seconds: int = Field(default=600, ge=1, le=3600)


class EcppStepsRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    budget_seconds: int = Field(default=120, ge=1, le=3600)
    timeout_seconds: int = Field(default=600, ge=1, le=3600)


@app.post("/api/primality-lab/compare")
def run_primality_comparison(request: PrimalityComparisonRequest) -> dict:
    try:
        result = compare_primality_tests(
            request.number, request.bases, request.budget_seconds, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "primality-comparison", "Primality-test comparison laboratory", result
    )


@app.post("/api/primality-lab/deterministic-witnesses")
def run_deterministic_witnesses(request: DeterministicWitnessRequest) -> dict:
    try:
        result = deterministic_witness_test(request.number, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "deterministic-witnesses", "Deterministic Miller-Rabin witness set", result
    )


@app.post("/api/primality-lab/pocklington")
def run_pocklington_proof(request: PocklingtonProofRequest) -> dict:
    try:
        result = pocklington_proof(
            request.number, request.budget_seconds, request.witness_limit,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("pocklington-proof", "Pocklington N-1 proof", result)


@app.post("/api/primality-lab/pratt")
def run_pratt_certificate(request: PrattCertificateRequest) -> dict:
    try:
        result = pratt_certificate(
            request.number, request.max_nodes, request.budget_seconds, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("pratt-certificate", "Pratt certificate tree", result)


@app.post("/api/primality-lab/verify-certificate")
def run_primality_certificate_verification(request: PrimalityCertificateRequest) -> dict:
    try:
        result = verify_certificate(request.kind, request.certificate, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "primality-certificate", "Independent certificate verification", result
    )


@app.post("/api/primality-lab/proth")
def run_proth_test(request: ProthTestRequest) -> dict:
    try:
        result = proth_test(
            request.k, request.exponent, request.base, request.witness_limit,
            request.budget_seconds, request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("proth-test", "Generalized Proth primality test", result)


@app.post("/api/primality-lab/proth-search")
def run_proth_search(request: ProthSearchRequest) -> dict:
    try:
        result = proth_search(
            request.k, request.base, request.n_start, request.n_end, request.limit,
            request.witness_limit, request.budget_seconds, request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("proth-search", "Generalized Proth prime search", result)


@app.post("/api/primality-lab/lucas-sequence")
def run_lucas_sequence_proof(request: LucasSequenceRequest) -> dict:
    try:
        result = lucas_sequence_proof(
            request.number, request.p, request.q, request.selfridge,
            request.budget_seconds, request.witness_limit, request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "lucas-sequence-proof", "Lucas sequence and N+1 proof", result
    )


@app.post("/api/primality-lab/taxonomy")
def run_pseudoprime_taxonomy(request: PseudoprimeTaxonomyRequest) -> dict:
    try:
        result = pseudoprime_taxonomy(
            request.number, request.bases, request.p, request.q, request.selfridge,
            request.budget_seconds, request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "pseudoprime-taxonomy", "Probable-prime taxonomy", result
    )


@app.post("/api/primality-lab/carmichael")
def run_carmichael_analysis(request: CarmichaelRequest) -> dict:
    try:
        result = carmichael_analysis(
            request.number, request.base_limit, request.budget_seconds, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("carmichael-analysis", "Carmichael-number analysis", result)


@app.post("/api/primality-lab/chernick")
def run_chernick_search(request: ChernickRequest) -> dict:
    try:
        result = chernick_search(
            request.k_start, request.k_end, request.limit, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "chernick-carmichael", "Chernick Carmichael construction", result
    )


@app.post("/api/primality-lab/repunit")
def run_repunit_search(request: RepunitSearchRequest) -> dict:
    try:
        result = repunit_search(
            request.base, request.n_start, request.n_end, request.limit,
            request.budget_seconds, request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("repunit-search", "Generalized repunit primes", result)


@app.post("/api/primality-lab/sierpinski")
def run_sierpinski_riesel_search(request: SierpinskiRieselRequest) -> dict:
    try:
        result = sierpinski_riesel_search(
            request.k, request.kind, request.n_max, request.budget_seconds,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "sierpinski-riesel", "Sierpinski and Riesel explorer", result
    )


@app.post("/api/primality-lab/covering-set")
def run_covering_set_check(request: CoveringSetRequest) -> dict:
    try:
        result = covering_set_check(
            request.k, request.kind, request.period, request.candidates, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("covering-set", "Covering-set verification", result)


@app.post("/api/primality-lab/bitwin-chains")
def run_bitwin_chain_search(request: BiTwinChainRequest) -> dict:
    try:
        result = bitwin_chain_search(
            request.start, request.end, request.min_length, request.limit,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("bitwin-chains", "Bi-twin chain search", result)


@app.post("/api/primality-lab/prime-ladder")
def run_prime_ladder(request: PrimeLadderRequest) -> dict:
    try:
        result = prime_ladder(
            request.start_prime, request.end_prime, request.max_steps, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("prime-ladder", "Prime ladder", result)


@app.post("/api/primality-lab/constrained-prime")
def run_constrained_prime(request: ConstrainedPrimeRequest) -> dict:
    try:
        result = constrained_prime(
            request.bits, request.kind, request.modulus, request.residue,
            request.certificate, request.seed, request.budget_seconds,
            request.candidate_limit, request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "constrained-prime", "Constrained prime construction (experimental)", result
    )


@app.post("/api/primality-lab/lucas-lehmer-steps")
def run_lucas_lehmer_steps(request: LucasLehmerStepsRequest) -> dict:
    try:
        result = lucas_lehmer_steps(
            request.exponent, request.show_limit, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "lucas-lehmer-steps", "Lucas-Lehmer proof steps", result
    )


@app.post("/api/primality-lab/ecpp-steps")
def run_ecpp_steps(request: EcppStepsRequest) -> dict:
    try:
        result = ecpp_steps(request.number, request.budget_seconds, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("ecpp-steps", "ECPP certificate steps", result)


@app.post("/api/number-theory/perfect-power")
def calculate_perfect_power(request: PerfectPowerRequest) -> dict:
    try:
        result = perfect_power(request.number, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("perfect-power", "Perfect-power decomposition", result)


@app.post("/api/number-theory/factor-strategy")
def calculate_factor_strategy(request: FactorStrategyRequest) -> dict:
    try:
        result = factor_strategy(
            request.number,
            request.trial_bound,
            DEFAULT_CADO_THRESHOLD,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "factor-strategy", "Factorization strategy analysis", result
    )


@app.post("/api/number-theory/prime-approximations")
def calculate_prime_approximations(request: PrimeApproximationRequest) -> dict:
    try:
        result = prime_approximation_comparison(
            request.x, request.threads, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "prime-approximations", "Prime-counting approximation comparison", result
    )


@app.post("/api/number-theory/summatory-functions")
def calculate_summatory_functions(request: SummatoryFunctionsRequest) -> dict:
    try:
        result = summatory_functions(request.x, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "summatory-functions", "Summatory arithmetic functions", result
    )


class DistributionGridRequest(BaseModel):
    exponent_from: int = Field(default=3, ge=1, le=18)
    exponent_to: int = Field(default=12, ge=2, le=19)
    points: int = Field(default=10, ge=2, le=24)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    timeout_seconds: int = Field(default=600, ge=1, le=3600)


class NthPrimeBoundRequest(BaseModel):
    exponent_from: int = Field(default=1, ge=1, le=16)
    exponent_to: int = Field(default=9, ge=2, le=17)
    points: int = Field(default=9, ge=2, le=24)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)
    timeout_seconds: int = Field(default=600, ge=1, le=3600)


class PrimeRaceRequest(BaseModel):
    modulus: str = Field(default="4", min_length=1, max_length=8)
    endpoint: str = Field(default="1000000", min_length=1, max_length=16)
    checkpoints: int = Field(default=12, ge=1, le=64)
    timeout_seconds: int = Field(default=600, ge=1, le=3600)


class ProgressionDeviationRequest(BaseModel):
    modulus: str = Field(default="12", min_length=1, max_length=8)
    endpoint: str = Field(default="1000000", min_length=1, max_length=16)
    timeout_seconds: int = Field(default=600, ge=1, le=3600)


class SingularSeriesRequest(BaseModel):
    offsets: list[int] = Field(default=[0, 2], min_length=2, max_length=32)
    cutoff: int = Field(default=1_000_000, ge=100, le=100_000_000)
    timeout_seconds: int = Field(default=600, ge=1, le=3600)


class TuplePredictionRequest(SingularSeriesRequest):
    start: str = Field(default="2", min_length=1, max_length=16)
    end: str = Field(default="1000000", min_length=1, max_length=16)


class BatemanHornRequest(BaseModel):
    polynomials: list[list[str]] = Field(min_length=1, max_length=8)
    start: str = Field(default="1", min_length=1, max_length=16)
    end: str = Field(default="100000", min_length=1, max_length=16)
    cutoff: int = Field(default=100_000, ge=3, le=1_000_000)
    timeout_seconds: int = Field(default=600, ge=1, le=3600)


class MaximalGapRequest(BaseModel):
    start: str = Field(default="2", min_length=1, max_length=16)
    end: str = Field(default="10000000", min_length=1, max_length=16)
    baseline: int = Field(default=0, ge=0, le=100_000)
    prime_cap: int = Field(default=10_000_000, ge=100, le=10_000_000_000)
    timeout_seconds: int = Field(default=900, ge=1, le=3600)


class ShortIntervalRequest(BaseModel):
    modulus: str = Field(default="9699690", min_length=1, max_length=16)
    first_row: str = Field(default="1000", min_length=1, max_length=16)
    rows: int = Field(default=64, ge=1, le=512)
    length: int = Field(default=1000, ge=2, le=1_000_000)
    timeout_seconds: int = Field(default=900, ge=1, le=3600)


class DensitySurfaceRequest(BaseModel):
    start: str = Field(default="1000000", min_length=1, max_length=16)
    end: str = Field(default="2000000", min_length=1, max_length=16)
    blocks: int = Field(default=32, ge=1, le=64)
    modulus: str = Field(default="30", min_length=1, max_length=8)
    timeout_seconds: int = Field(default=900, ge=1, le=3600)


def _save_distribution_report(kind: str, heading: str, result: dict) -> dict:
    """Persist an analytic-distribution report, including its extra sections."""
    lines = [result["note"], ""]
    lines.extend(f"{key}: {value}" for key, value in result.get("metrics", {}).items())
    lines.extend(["", " | ".join(result["columns"])])
    lines.extend(" | ".join(row) for row in result["rows"])
    for section in result.get("sections", []):
        lines.extend(["", section["title"], " | ".join(section["columns"])])
        lines.extend(" | ".join(row) for row in section["rows"])
    path = save_prime_output(kind, heading, lines)
    return {**result, "output_file": path.name, "engine": "PARI/GP"}


@app.post("/api/distribution/approximation-error")
def calculate_approximation_error(request: DistributionGridRequest) -> dict:
    try:
        result = approximation_error(
            request.exponent_from, request.exponent_to, request.points,
            request.threads, request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_distribution_report(
        "approximation-error", "Prime-counting approximation error", result
    )


@app.post("/api/distribution/pnt-convergence")
def calculate_pnt_convergence(request: DistributionGridRequest) -> dict:
    try:
        result = pnt_convergence(
            request.exponent_from, request.exponent_to, request.points,
            request.threads, request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_distribution_report(
        "pnt-convergence", "Prime-number-theorem convergence", result
    )


@app.post("/api/distribution/nth-prime-bounds")
def calculate_nth_prime_bounds(request: NthPrimeBoundRequest) -> dict:
    try:
        result = nth_prime_bounds(
            request.exponent_from, request.exponent_to, request.points,
            request.threads, request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_distribution_report(
        "nth-prime-bounds", "Explicit n-th prime bounds", result
    )


@app.post("/api/distribution/prime-race")
def calculate_prime_race(request: PrimeRaceRequest) -> dict:
    try:
        result = prime_race(
            request.modulus, request.endpoint, request.checkpoints, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_distribution_report("prime-race", "Prime race and Chebyshev bias", result)


@app.post("/api/distribution/progressions")
def calculate_progression_deviation(request: ProgressionDeviationRequest) -> dict:
    try:
        result = progression_deviation(
            request.modulus, request.endpoint, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_distribution_report(
        "progression-deviation", "Primes in arithmetic progressions", result
    )


@app.post("/api/distribution/singular-series")
def calculate_singular_series(request: SingularSeriesRequest) -> dict:
    try:
        result = singular_series(request.offsets, request.cutoff, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_distribution_report(
        "singular-series", "Hardy–Littlewood singular series", result
    )


@app.post("/api/distribution/tuple-prediction")
def calculate_tuple_prediction(request: TuplePredictionRequest) -> dict:
    try:
        result = tuple_prediction(
            request.offsets, request.start, request.end,
            request.cutoff, request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_distribution_report(
        "tuple-prediction", "Predicted versus observed constellations", result
    )


@app.post("/api/distribution/bateman-horn")
def calculate_bateman_horn(request: BatemanHornRequest) -> dict:
    try:
        result = bateman_horn(
            request.polynomials, request.start, request.end,
            request.cutoff, request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_distribution_report("bateman-horn", "Bateman–Horn prediction", result)


@app.post("/api/distribution/maximal-gaps")
def calculate_maximal_gaps(request: MaximalGapRequest) -> dict:
    try:
        result = maximal_gap_search(
            request.start, request.end, request.baseline,
            request.prime_cap, request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_distribution_report("maximal-gaps", "Record prime-gap search", result)


@app.post("/api/distribution/short-interval")
def calculate_short_interval(request: ShortIntervalRequest) -> dict:
    try:
        result = short_interval_matrix(
            request.modulus, request.first_row, request.rows,
            request.length, request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_distribution_report(
        "short-interval", "Maier-matrix short-interval experiment", result
    )


@app.post("/api/distribution/density-surface")
def calculate_density_surface(request: DensitySurfaceRequest) -> dict:
    try:
        result = density_surface(
            request.start, request.end, request.blocks,
            request.modulus, request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_distribution_report("density-surface", "Prime-density surface", result)


# ---------------------------------------------------------------------------
# Prime-counting algorithm comparison and integer-structure predicates.
# Kept as one contiguous block -- import, request models, report writer and
# routes together -- so the feature can be reviewed and moved as a unit.
# Computation attribution: numerisect/counting_lab.py and counting_lab.gp,
# documented in docs/COUNTING_LAB.md. Nothing below computes mathematics.
# ---------------------------------------------------------------------------
from .counting_lab import (  # noqa: E402
    counting_algorithm_comparison,
    factorint_strategies,
    integer_structure,
    legendre_phi,
    lenstra_divisors,
    nth_prime_inverses,
)

CountingAlgorithm = Literal[
    "legendre", "meissel", "lehmer", "lmo", "deleglise-rivat", "gourdon"
]


class CountingComparisonRequest(BaseModel):
    x: str = Field(default="10000000000", min_length=1, max_length=200)
    algorithms: list[CountingAlgorithm] = Field(
        default=["legendre", "meissel", "lehmer", "lmo", "deleglise-rivat", "gourdon"],
        min_length=1, max_length=6,
    )
    double_check: bool = True
    include_pari: bool = True
    threads: int = Field(default=1, ge=1, le=256)
    timeout_seconds: int = Field(default=900, ge=1, le=3600)


class LegendrePhiRequest(BaseModel):
    x: str = Field(default="1000000", min_length=1, max_length=19)
    a: int = Field(default=10, ge=0, le=100_000)
    threads: int = Field(default=1, ge=1, le=256)
    timeout_seconds: int = Field(default=900, ge=1, le=3600)


class NthPrimeInverseRequest(BaseModel):
    n: str = Field(default="1000000", min_length=1, max_length=17)
    threads: int = Field(default=1, ge=1, le=256)
    timeout_seconds: int = Field(default=900, ge=1, le=3600)


class IntegerStructureRequest(BaseModel):
    expression: str = Field(default="1024", min_length=1, max_length=2000)
    sides: int = Field(default=3, ge=3, le=1_000_000)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class LenstraDivisorRequest(BaseModel):
    expression: str = Field(default="1000", min_length=1, max_length=2000)
    residue: str = Field(default="3", min_length=1, max_length=120)
    modulus: str = Field(default="11", min_length=1, max_length=120)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class FactorintStrategyRequest(BaseModel):
    expression: str = Field(default="1000036000099", min_length=1, max_length=200)
    flags: list[int] = Field(default=[0, 1, 2, 4, 8], min_length=1, max_length=16)
    timeout_seconds: int = Field(default=900, ge=1, le=3600)


def _save_counting_report(kind: str, heading: str, result: dict) -> dict:
    """Persist a counting-laboratory report, including its extra sections."""
    lines = [result["note"], ""]
    lines.extend(f"{key}: {value}" for key, value in result.get("metrics", {}).items())
    lines.extend(["", " | ".join(result["columns"])])
    lines.extend(" | ".join(row) for row in result["rows"])
    for section in result.get("sections", []):
        lines.extend(["", section["title"], " | ".join(section["columns"])])
        lines.extend(" | ".join(row) for row in section["rows"])
    path = save_prime_output(kind, heading, lines)
    return {**result, "output_file": path.name, "engine": "primecount + PARI/GP"}


@app.post("/api/counting/algorithm-comparison")
def compare_counting_algorithms(request: CountingComparisonRequest) -> dict:
    try:
        result = counting_algorithm_comparison(
            request.x, request.algorithms, request.double_check,
            request.include_pari, request.threads, request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_counting_report(
        "counting-comparison", "Prime-counting algorithm comparison", result
    )


@app.post("/api/counting/phi")
def calculate_legendre_phi(request: LegendrePhiRequest) -> dict:
    try:
        result = legendre_phi(request.x, request.a, request.threads, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_counting_report("legendre-phi", "Legendre partial sieve phi(x, a)", result)


@app.post("/api/counting/nth-prime-inverses")
def calculate_nth_prime_inverses(request: NthPrimeInverseRequest) -> dict:
    try:
        result = nth_prime_inverses(request.n, request.threads, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_counting_report(
        "nth-prime-inverses", "Inverse approximations to the n-th prime", result
    )


@app.post("/api/structure/predicates")
def calculate_integer_structure(request: IntegerStructureRequest) -> dict:
    try:
        number = evaluate_arbitrary_integer(request.expression)
        result = integer_structure(number, request.sides, request.timeout_seconds)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_counting_report("integer-structure", "Integer-structure predicates", result)


@app.post("/api/structure/lenstra-divisors")
def calculate_lenstra_divisors(request: LenstraDivisorRequest) -> dict:
    try:
        number = evaluate_arbitrary_integer(request.expression)
        residue = evaluate_arbitrary_integer(request.residue)
        modulus = evaluate_arbitrary_integer(request.modulus)
        result = lenstra_divisors(number, residue, modulus, request.timeout_seconds)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_counting_report(
        "lenstra-divisors", "Divisors in a residue class (Lenstra)", result
    )


@app.post("/api/structure/factorint-strategies")
def calculate_factorint_strategies(request: FactorintStrategyRequest) -> dict:
    try:
        number = evaluate_arbitrary_integer(request.expression)
        result = factorint_strategies(number, request.flags, request.timeout_seconds)
    except (ExpressionError, ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_counting_report(
        "factorint-strategies", "PARI factorint strategy comparison", result
    )


@app.post("/api/number-theory/eisenstein")
def calculate_eisenstein_prime(request: EisensteinPrimeRequest) -> dict:
    try:
        result = eisenstein_prime(request.a, request.b, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("eisenstein-prime", "Eisenstein-prime analysis", result)


@app.post("/api/number-theory/quadratic-decomposition")
def calculate_quadratic_prime_decomposition(
    request: QuadraticPrimeDecompositionRequest,
) -> dict:
    try:
        result = quadratic_prime_decomposition(
            request.radicand, request.prime, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "quadratic-prime-decomposition", "Quadratic-field prime decomposition", result
    )


@app.post("/api/number-theory/special-prime-family")
def find_special_prime_family(request: SpecialPrimeFamilyRequest) -> dict:
    try:
        result = special_prime_family(
            request.kind,
            request.start_index,
            request.end_index,
            request.limit,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "special-prime-family", "Special-prime family search", result
    )


@app.post("/api/number-theory/cunningham-chain")
def analyze_cunningham_chain(request: CunninghamChainRequest) -> dict:
    try:
        result = cunningham_chain(
            request.start_prime, request.length, request.kind, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "cunningham-chain", "Cunningham-chain analysis", result
    )


@app.post("/api/number-theory/ntt-primes")
def find_ntt_primes(request: NttPrimeRequest) -> dict:
    try:
        result = ntt_primes(
            request.bits,
            request.power_two,
            request.count,
            request.candidate_limit,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("ntt-primes", "NTT-friendly prime search", result)


@app.post("/api/number-theory/tonelli-shanks")
def calculate_tonelli_shanks(request: TonelliShanksRequest) -> dict:
    try:
        result = tonelli_shanks(
            request.value, request.prime, request.trace_limit, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("tonelli-shanks", "Tonelli–Shanks trace", result)


@app.post("/api/number-theory/hensel-roots")
def calculate_hensel_roots(request: HenselRootsRequest) -> dict:
    try:
        result = hensel_roots(
            request.coefficients,
            request.prime,
            request.exponent,
            request.limit,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("hensel-roots", "Hensel-lifted roots", result)


@app.post("/api/number-theory/order-distribution")
def calculate_order_distribution(request: DistributionRequest) -> dict:
    try:
        result = order_distribution(
            request.modulus, request.limit, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "order-distribution", "Multiplicative-order distribution", result
    )


@app.post("/api/number-theory/power-residues")
def calculate_power_residues(request: PowerResidueRequest) -> dict:
    try:
        result = power_residue_distribution(
            request.modulus,
            request.exponent,
            request.limit,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "power-residues", "Finite-field power-residue distribution", result
    )


@app.post("/api/number-theory/valuation")
def calculate_p_adic_valuation(request: ValuationRequest) -> dict:
    try:
        result = p_adic_valuation(
            request.number, request.prime, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("p-adic-valuation", "p-adic valuation", result)


@app.post("/api/number-theory/cyclotomic")
def calculate_cyclotomic(request: CyclotomicRequest) -> dict:
    try:
        result = cyclotomic_polynomial(
            request.index, request.prime, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "cyclotomic-polynomial", "Cyclotomic-polynomial factorization", result
    )


@app.post("/api/number-theory/aliquot")
def calculate_aliquot_sequence(request: AliquotRequest) -> dict:
    try:
        result = aliquot_sequence(
            request.number, request.max_steps, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report("aliquot-sequence", "Aliquot sequence", result)


@app.post("/api/number-theory/divisor-classification")
def calculate_divisor_classification(request: DivisorClassificationRequest) -> dict:
    try:
        result = divisor_classification(request.number, request.timeout_seconds)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "divisor-classification", "Divisor-sum classification", result
    )


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


@app.post("/api/zeta/hardy")
def calculate_hardy_z(request: ZetaHardyRequest) -> dict[str, object]:
    try:
        result = evaluate_hardy_z(request.ordinate, request.precision, request.timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "hardy-z", f"Riemann–Siegel Z at t={result['input']}",
        [f"Real enclosure: {result['real']}", f"Imaginary enclosure: {result['imaginary']}", str(result["note"])],
    )
    return {**result, "output_file": path.name}


@app.post("/api/zeta/xi-eta")
def calculate_xi_eta(request: ZetaXiEtaRequest) -> dict[str, object]:
    try:
        result = evaluate_xi_eta(
            request.kind, request.sigma, request.ordinate,
            request.precision, request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        f"zeta-{request.kind}", f"{result['function']} evaluation",
        [f"s = {result['sigma']} + {result['ordinate']}i", f"Real: {result['real']}", f"Imaginary: {result['imaginary']}"],
    )
    return {**result, "output_file": path.name}


@app.post("/api/zeta/stieltjes")
def calculate_stieltjes_constant(request: ZetaIndexedRequest) -> dict[str, object]:
    try:
        result = stieltjes_constant(request.index, request.precision, request.timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "stieltjes-constant", f"Stieltjes constant gamma_{result['index']}",
        [f"Real: {result['real']}", f"Imaginary: {result['imaginary']}"],
    )
    return {**result, "output_file": path.name}


@app.post("/api/zeta/gram")
def calculate_gram_point(request: ZetaIndexedRequest) -> dict[str, object]:
    try:
        result = gram_point(request.index, request.precision, request.timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "gram-point", f"Gram point g_{result['index']}", [f"Enclosure: {result['value']}"],
    )
    return {**result, "label": f"g({result['index']})", "output_file": path.name}


@app.post("/api/zeta/functional-equation")
def calculate_functional_equation(request: ZetaEvaluateRequest) -> dict[str, object]:
    try:
        result = verify_functional_equation(
            request.sigma, request.ordinate, request.precision, request.timeout_seconds
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "zeta-functional-equation", "Riemann zeta functional-equation verification",
        [
            f"s = {result['sigma']} + {result['ordinate']}i",
            f"Verified by overlapping enclosures: {'yes' if result['verified'] else 'no'}",
            f"Left: {result['left_real']} + ({result['left_imaginary']})i",
            f"Right: {result['right_real']} + ({result['right_imaginary']})i",
            f"Residual: {result['residual_real']} + ({result['residual_imaginary']})i",
        ],
    )
    return {**result, "output_file": path.name}


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


@app.post("/api/zeta/explicit-prime-count")
def calculate_explicit_prime_count(request: ZetaExplicitPrimeCountRequest) -> dict[str, object]:
    """Riemann's explicit formula for π(x) from certified zeros (FLINT/Arb)."""

    try:
        result = explicit_prime_count(
            request.bound, request.zeros, request.precision, request.threads,
            request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "zeta-explicit-prime-count",
        f"Riemann explicit formula for pi({result['bound']})",
        [
            f"Exact pi(x) from primecount: {result['exact']}",
            f"Moebius terms: {result['moebius_terms']}",
            *(
                f"N={row['zeros']}: estimate={row['estimate']}; error={row['error']}"
                for row in result["terms"]
            ),
            str(result["note"]),
        ],
    )
    return {**result, "output_file": path.name}


@app.post("/api/zeta/chebyshev-psi")
def calculate_chebyshev_psi(request: ZetaChebyshevPsiRequest) -> dict[str, object]:
    """Chebyshev ψ(x) reconstructed from certified zeros (FLINT/Arb)."""

    try:
        result = chebyshev_psi_formula(
            request.bound, request.zeros, request.precision, request.threads,
            request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "zeta-chebyshev-psi",
        f"Chebyshev psi({result['bound']}) from the explicit formula",
        [
            f"Exact psi(x): {result['exact']}",
            *(
                f"N={row['zeros']}: estimate={row['estimate']}; error={row['error']}"
                for row in result["terms"]
            ),
            str(result["note"]),
        ],
    )
    return {**result, "output_file": path.name}


@app.post("/api/zeta/riemann-siegel")
def calculate_riemann_siegel(request: ZetaRiemannSiegelRequest) -> dict[str, object]:
    """Riemann–Siegel main sum with K corrections against acb_dirichlet_zeta."""

    try:
        result = riemann_siegel_remainder(
            request.sigma, request.ordinate, request.terms, request.precision,
            request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "zeta-riemann-siegel",
        f"Riemann-Siegel remainder analysis at {result['sigma']} + {result['ordinate']}i",
        [
            f"Reference: {result['reference_real']} + ({result['reference_imaginary']})i",
            *(
                f"K={row['terms']}: value={row['real']} + ({row['imaginary']})i; "
                f"deviation={row['deviation']}; bound={row['bound']}"
                for row in result["rows"]
            ),
            str(result["note"]),
        ],
    )
    return {**result, "output_file": path.name}


@app.post("/api/zeta/euler-product")
def calculate_euler_product(request: ZetaEulerProductRequest) -> dict[str, object]:
    """Truncated Euler products against ζ(s) with a rigorous tail bound."""

    try:
        result = euler_product_comparison(
            request.sigma, request.ordinate, request.primes, request.precision,
            request.threads, request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "zeta-euler-product",
        f"Euler-product comparison at {result['sigma']} + {result['ordinate']}i",
        [
            f"Reference: {result['reference_real']} + ({result['reference_imaginary']})i",
            f"FLINT certified Euler product: {result['certified_euler'] or 'not applicable'}",
            *(
                f"{row['primes']} primes (through {row['largest_prime']}): "
                f"{row['real']} + ({row['imaginary']})i; deviation={row['deviation']}; "
                f"truncation bound={row['truncation_bound']}"
                for row in result["rows"]
            ),
            str(result["note"]),
        ],
    )
    return {**result, "output_file": path.name}


@app.post("/api/zeta/zero-spacing")
def calculate_zero_spacing(request: ZetaSpacingRequest) -> dict[str, object]:
    """Normalized nearest-neighbour spacing histogram of certified zeros."""

    try:
        result = zero_spacing_histogram(
            request.start_index, request.count, request.bins, request.precision,
            request.threads, request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "zeta-zero-spacing",
        f"Normalized zero spacings from index {result['start_index']}",
        [
            f"Samples: {result['samples']}; mean={result['mean']}; variance={result['variance']}",
            f"Minimum={result['minimum']}; maximum={result['maximum']}; "
            f"outside window={result['overflow']}",
            *(
                f"[{row['lower']:.6g}, {row['upper']:.6g}): count={row['count']}; "
                f"observed={row['observed']:.6g}; GUE={row['predicted']:.6g}"
                for row in result["bins"]
            ),
            str(result["note"]),
        ],
    )
    return {**result, "output_file": path.name}


@app.post("/api/zeta/pair-correlation")
def calculate_pair_correlation(request: ZetaPairCorrelationRequest) -> dict[str, object]:
    """Pair correlation of certified zeros against the GUE prediction."""

    try:
        result = zero_pair_correlation(
            request.start_index, request.count, request.bins, request.window,
            request.precision, request.threads, request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "zeta-pair-correlation",
        f"Zero pair correlation from index {result['start_index']}",
        [
            f"Zeros: {result['samples']}; pairs inside the window: {result['pairs']}",
            *(
                f"[{row['lower']:.6g}, {row['upper']:.6g}): count={row['count']}; "
                f"observed={row['observed']:.6g}; GUE={row['predicted']:.6g}"
                for row in result["bins"]
            ),
            str(result["note"]),
        ],
    )
    return {**result, "output_file": path.name}


@app.post("/api/zeta/gram-blocks")
def calculate_gram_blocks(request: ZetaGramBlockRequest) -> dict[str, object]:
    """Gram's-law verdicts, exceptions and Gram blocks over an index range."""

    try:
        result = gram_block_structure(
            request.start_index, request.count, request.precision, request.threads,
            request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "zeta-gram-blocks",
        f"Gram's law from index {result['start_index']} over {result['count']} points",
        [
            f"Exceptions: {len(result['exceptions'])}; blocks: {len(result['blocks'])}; "
            f"inconclusive: {result['inconclusive']}",
            *(
                f"n={row['index']}: g={row['gram_point']:.12g}; Z={row['hardy_z']:.12g}; "
                f"{row['status']}"
                for row in result["points"]
            ),
            *(
                f"Gram block at n={block['start_index']} of length {block['length']} "
                f"({block['pattern']})"
                for block in result["blocks"]
            ),
            str(result["note"]),
        ],
    )
    return {**result, "output_file": path.name}


@app.post("/api/zeta/backlund-s")
def calculate_backlund_s(request: ZetaBacklundRequest) -> dict[str, object]:
    """Certified S(T) with an exploratory plot across an ordinate range."""

    try:
        result = backlund_remainder(
            request.lower, request.upper, request.samples, request.precision,
            request.threads, request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "zeta-backlund-s",
        f"Zero-counting remainder S(T) through T={result['upper']}",
        [
            f"S({result['upper']}) = {result['remainder']}",
            f"Rigorous |S(T)| bound: {result['remainder_bound']}",
            f"theta({result['upper']}) = {result['theta']}",
            f"Certified N({result['upper']}) = {result['zero_count']} "
            f"(enclosure {result['zero_count_interval']})",
            *(f"t={point['t']:.17g}\tS={point['s']:.17g}" for point in result["points"]),
            str(result["note"]),
        ],
    )
    return {**result, "output_file": path.name}


@app.post("/api/zeta/characters")
def calculate_dirichlet_characters(request: ZetaCharacterRequest) -> dict[str, object]:
    """Dirichlet character table modulo q with conductor, parity and order."""

    try:
        result = dirichlet_characters(request.modulus, request.limit, request.timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "dirichlet-characters",
        f"Dirichlet characters modulo {result['modulus']}",
        [
            f"Group order: {result['group_order']}; primitive characters: "
            f"{result['primitive_total']}",
            *(
                f"chi_{result['modulus']}({row['number']}): conductor={row['conductor']}; "
                f"{row['parity']}; order={row['order']}; "
                f"{'primitive' if row['primitive'] else 'imprimitive'}; "
                f"{'real' if row['real'] else 'complex'}"
                for row in result["characters"]
            ),
            str(result["note"]),
        ],
    )
    return {**result, "output_file": path.name}


@app.post("/api/zeta/l-function")
def calculate_dirichlet_l(request: ZetaLFunctionRequest) -> dict[str, object]:
    """Rigorous L(s, χ) enclosure with an independent Hurwitz cross-check."""

    try:
        result = dirichlet_l_value(
            request.modulus, request.number, request.sigma, request.ordinate,
            request.precision, request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "dirichlet-l-value",
        f"L(s, chi_{result['modulus']}({result['number']})) at "
        f"{result['sigma']} + {result['ordinate']}i",
        [
            f"Conductor: {result['conductor']}; {result['parity']}; order {result['order']}",
            f"Value: {result['real']} + ({result['imaginary']})i",
            f"Hurwitz cross-check: {result['cross_real']} + ({result['cross_imaginary']})i",
            f"Enclosures overlap: {'yes' if result['verified'] else 'no'}",
            str(result["note"]),
        ],
    )
    return {**result, "output_file": path.name}


@app.post("/api/zeta/l-zeros")
def calculate_dirichlet_l_zeros(request: ZetaLZerosRequest) -> dict[str, object]:
    """Certified critical-line sign changes, or exploratory |L| minima."""

    try:
        result = dirichlet_l_zeros(
            request.modulus, request.number, request.lower, request.upper,
            request.samples, request.precision, request.threads, request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "dirichlet-l-zeros",
        f"Critical-line search for L(s, chi_{result['modulus']}({result['number']}))",
        [
            f"Mode: {result['mode']}; range {result['lower']} to {result['upper']}",
            f"Smooth theta(T,chi)/pi count: {result['smooth_count']}",
            *(
                f"Certified sign change #{row['index']} in "
                f"[{row['lower']:.17g}, {row['upper']:.17g}]"
                for row in result["sign_changes"]
            ),
            *(
                f"Exploratory |L| minimum #{row['index']} at t={row['t']:.17g}: "
                f"{row['magnitude']:.6g}"
                for row in result["minima"]
            ),
            str(result["note"]),
        ],
    )
    return {**result, "output_file": path.name}


@app.post("/api/zeta/dedekind")
def calculate_dedekind_zeta(request: ZetaDedekindRequest) -> dict[str, object]:
    """Dedekind zeta of a bounded number field through PARI/GP."""

    try:
        result = dedekind_zeta(
            request.family, request.parameter, request.polynomial, request.sigma,
            request.ordinate, request.zero_height, request.zero_limit,
            request.class_data, request.precision, request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ZetaEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    path = save_prime_output(
        "dedekind-zeta",
        f"Dedekind zeta of the field defined by {result['polynomial']}",
        [
            f"Degree {result['degree']}; signature ({result['real_places']}, "
            f"{result['complex_places']}); discriminant {result['discriminant']}",
            f"lfuncheckfeq: {result['functional_equation_log2_error']}",
            f"zeta_K({result['sigma']} + {result['ordinate']}i) = {result['value_real']} "
            f"+ ({result['value_imaginary']})i",
            *(f"Pole at s={pole['point']} with residue {pole['residue']}"
              for pole in result["poles"]),
            *(
                [
                    f"Class number {result['class_number']}; regulator {result['regulator']}; "
                    f"torsion units {result['torsion_units']}",
                    f"Class-number-formula residue: "
                    f"{result['class_number_formula_residue']} "
                    f"(difference {result.get('residue_difference', 'n/a')})",
                ]
                if "class_number" in result
                else []
            ),
            f"Zeros located through height {result['zero_height']}: {result['zeros_found']}",
            *(f"Zero #{zero['index']}: t={zero['ordinate']}" for zero in result["zeros"]),
            str(result["note"]),
        ],
    )
    return {**result, "output_file": path.name}


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
        job = manager.create(
            expression=request.expression,
            number=number,
            requested_backend=request.backend,
            threads=request.threads,
            pretest_level=request.pretest_level,
            trial_bound=request.trial_bound,
            cado_parameter_size=request.cado_parameter_size,
            ecm_b1=request.ecm_b1,
            ecm_b2=request.ecm_b2,
            ecm_curves=request.ecm_curves,
            ecm_sigma=request.ecm_sigma,
            ecm_param=request.ecm_param,
        )
        return _public_job(job)
    except (ExpressionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/jobs/batch", status_code=202)
def create_job_batch(request: BatchJobRequest) -> dict[str, object]:
    if sum(len(expression) for expression in request.expressions) > 1_000_000:
        raise HTTPException(status_code=422, detail="Batch input is limited to 1,000,000 characters")
    try:
        numbers = [evaluate_integer(expression) for expression in request.expressions]
    except ExpressionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    jobs: list[dict[str, object]] = []
    try:
        for expression, number in zip(request.expressions, numbers, strict=True):
            jobs.append(
                _public_job(
                    manager.create(
                        expression=expression,
                        number=number,
                        requested_backend=request.backend,
                        threads=request.threads,
                        pretest_level=request.pretest_level,
                        trial_bound=request.trial_bound,
                        cado_parameter_size=request.cado_parameter_size,
                    )
                )
            )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "jobs": jobs,
        "count": len(jobs),
        "note": "The validated batch was added to the controlled factorization queue.",
    }


@app.post("/api/jobs/batch-export")
def export_job_batch(request: BatchExportRequest) -> dict[str, object]:
    jobs = [database.get_job(job_id) for job_id in request.job_ids]
    if any(job is None for job in jobs):
        raise HTTPException(status_code=404, detail="One or more batch jobs no longer exist")
    typed_jobs = [job for job in jobs if job is not None]
    incomplete = [job["id"] for job in typed_jobs if job["status"] != "completed"]
    if incomplete:
        raise HTTPException(
            status_code=409,
            detail=f"Wait for all batch jobs to complete ({len(incomplete)} still incomplete)",
        )
    lines: list[str] = []
    for job in typed_jobs:
        signed = f"-{job['number']}" if job["negative"] else job["number"]
        equation = " * ".join(str(item["value"]) for item in job["factors"])
        lines.extend(
            [
                f"Job {job['id']}", f"{signed} = {equation}",
                f"Strategy: {job['selected_backend']}", "",
            ]
        )
    path = save_prime_output("factorization-batch", "Batch factorization results", lines)
    return {
        "output_file": path.name,
        "count": len(typed_jobs),
        "note": f"Consolidated result saved automatically to output/{path.name}.",
    }


@app.get("/api/jobs")
def list_jobs(
    limit: int = Query(default=100, ge=1, le=500),
    q: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None, max_length=40),
    engine: str | None = Query(default=None, max_length=60),
    since: str | None = Query(default=None, max_length=40),
    until: str | None = Query(default=None, max_length=40),
    sort: str = Query(default="created_at", max_length=40),
    order: Literal["asc", "desc"] = "desc",
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, object]]:
    """List jobs, optionally filtered and sorted (roadmap item 135)."""

    if not any([q, status, engine, since, until, offset]) and sort == "created_at" and order == "desc":
        return [_public_job(job) for job in database.list_jobs(limit)]
    try:
        rows = database.search_jobs(
            q=q, status=status, engine=engine, since=since, until=until,
            sort=sort, descending=order == "desc", limit=limit, offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return [_public_job(job) for job in rows]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    job = database.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _public_job(job)


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
    replacements = sorted(
        ((str(STATE_DIR), "<state>"), (str(BASE_DIR), "<application>")),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for local_path, label in replacements:
        content = content.replace(local_path, label)
    return {"text": content, "size": size, "truncated": size > tail}


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, object]:
    try:
        return _public_job(manager.cancel(job_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc


@app.post("/api/jobs/{job_id}/resume", status_code=202)
def resume_job(job_id: str) -> dict[str, object]:
    try:
        return _public_job(manager.resume(job_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/jobs/{job_id}/continue-cofactor", status_code=202)
def continue_composite_cofactor(
    job_id: str, request: ContinueCofactorRequest
) -> dict[str, object]:
    source = database.get_job(job_id)
    if not source:
        raise HTTPException(status_code=404, detail="Job not found")
    factors = source.get("factors") or []
    if request.factor_index >= len(factors):
        raise HTTPException(status_code=422, detail="The selected factor does not exist")
    factor = factors[request.factor_index]
    if factor.get("status") not in {"composite", "unknown"}:
        raise HTTPException(status_code=409, detail="Only an unresolved composite cofactor can be continued")
    value = int(str(factor["value"]))
    try:
        job = manager.create(
            expression=str(value), number=value, requested_backend=request.backend,
            threads=request.threads, pretest_level=request.pretest_level,
            trial_bound=request.trial_bound,
            cado_parameter_size=None, parent_job_id=job_id,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _public_job(job)


# --- Expert factorization laboratory ---------------------------------------------------
# SQUFOF is served by the numerisect-squfof C helper because no installed library
# provides it. Every other operation here is performed by PARI/GP or GMP-ECM.


class SqufofRequest(BaseModel):
    expression: str = Field(..., min_length=1, max_length=MAX_EXPRESSION_CHARACTERS)
    max_iterations: int = Field(4_000_000, ge=1000, le=200_000_000)
    timeout_seconds: int = Field(300, ge=1, le=3600)


class SpecialFormRequest(BaseModel):
    expression: str = Field(..., min_length=1, max_length=200)
    timeout_seconds: int = Field(120, ge=1, le=600)


class StrategyRequest(BaseModel):
    expression: str = Field(..., min_length=1, max_length=200)
    pretest_level: int = Field(0, ge=0, le=80)
    timeout_seconds: int = Field(120, ge=1, le=600)


class TraceRequest(BaseModel):
    expression: str = Field(..., min_length=1, max_length=120)
    algorithm: Literal["rho", "pm1", "ecm"] = "rho"
    steps: int = Field(40, ge=1, le=500)
    timeout_seconds: int = Field(120, ge=1, le=600)


class CertificateBatchRequest(BaseModel):
    factors: list[str] = Field(..., min_length=1, max_length=64)
    timeout_seconds: int = Field(300, ge=1, le=3600)


def _save_factor_lab_report(kind: str, heading: str, result: dict, rows: list[str]) -> dict:
    lines = [str(result.get("note", "")), ""]
    lines.extend(rows)
    path = save_prime_output(kind, heading, lines)
    return {**result, "output_file": path.name}


class RsaChallengeRequest(BaseModel):
    target: str = Field(default="RSA-250", min_length=1, max_length=1_000)
    prove_factors: bool = False
    proof_seconds: int = Field(default=60, ge=1, le=3600)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class MersenneFactorRequest(BaseModel):
    exponent: int = Field(default=1061, ge=3, le=10**9)
    k_limit: int | None = Field(default=None, ge=1, le=50_000_000)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class MersenneHuntRequest(BaseModel):
    exponent: int = Field(default=87083, ge=3, le=1_000_000)
    trial_k_limit: int = Field(default=100_000, ge=1, le=50_000_000)
    trial_seconds: int = Field(default=60, ge=1, le=3600)
    stage_seconds: int = Field(default=60, ge=1, le=3600)
    pm1_b1: int = Field(default=50_000, ge=100, le=10**12)
    pp1_b1: int = Field(default=50_000, ge=100, le=10**12)
    ecm_b1: int = Field(default=50_000, ge=100, le=10**12)
    ecm_curves: int = Field(default=25, ge=1, le=1_000_000)
    proof_seconds: int = Field(default=10, ge=1, le=600)
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)


@app.post("/api/factor-lab/mersenne-factors")
def factor_lab_mersenne_factors(request: MersenneFactorRequest) -> dict:
    """Trial-factor M_p for odd prime p over q = 2kp + 1 without building M_p."""

    try:
        result = mersenne_factors(
            request.exponent, request.k_limit, request.timeout_seconds
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PrimeEngineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "mersenne-factors", f"Mersenne factors of M_{request.exponent}", result
    )


@app.post("/api/factor-lab/mersenne-hunt")
def factor_lab_mersenne_hunt(request: MersenneHuntRequest) -> dict:
    """Run trial factoring, P-1, P+1, ECM, and native cofactor reconciliation."""

    try:
        result = mersenne_factor_hunt(
            request.exponent,
            trial_k_limit=request.trial_k_limit,
            trial_seconds=request.trial_seconds,
            stage_seconds=request.stage_seconds,
            pm1_b1=request.pm1_b1,
            pp1_b1=request.pp1_b1,
            ecm_b1=request.ecm_b1,
            ecm_curves=request.ecm_curves,
            proof_seconds=request.proof_seconds,
            threads=request.threads,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PrimeEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    report_rows = [
        *(f"{key}: {value}" for key, value in result["metrics"].items()),
        "",
        "Stages:",
        *(f"{stage['stage']}: {stage['status']} — {stage['detail']}"
          for stage in result["stages"]),
        "",
        "Discovered divisors:",
        *(f"{factor['value']} ^ {factor['exponent']} "
          f"[{factor['status']}; {factor['engine']}]"
          for factor in result["factors"]),
        "",
        f"Exact remaining cofactor ({result['cofactor_digits']} digits; "
        f"{result['cofactor_status']}):",
        result["cofactor"],
    ]
    return _save_factor_lab_report(
        "mersenne-hunt", f"Staged Mersenne factor hunt for M_{request.exponent}",
        result, report_rows,
    )


@app.get("/api/factor-lab/sievers")
def factor_lab_sievers() -> dict:
    """Report the GGNFS lattice sievers found, whether each runs on this CPU, and which
    directory YAFU will be given for number field sieve work."""

    result = siever_report()
    return _save_manipulation_report(
        "lattice-sievers", "GGNFS lattice sievers", result
    )


@app.get("/api/factor-lab/rsa-catalogue")
def factor_lab_rsa_catalogue() -> dict:
    """List the RSA Factoring Challenge numbers with their sizes and published status."""

    result = rsa_catalogue()
    return _save_manipulation_report(
        "rsa-catalogue", "RSA Factoring Challenge catalogue", result
    )


@app.post("/api/factor-lab/rsa-challenge")
def factor_lab_rsa_challenge(request: RsaChallengeRequest) -> dict:
    """Identify an RSA challenge number, re-verify its published factors, estimate effort."""

    try:
        result = rsa_challenge_report(
            request.target,
            request.prove_factors,
            request.proof_seconds,
            request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PrimeEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _save_manipulation_report(
        "rsa-challenge", f"RSA challenge report: {result['name']}", result
    )


@app.post("/api/factor-lab/squfof")
def factor_lab_squfof(request: SqufofRequest) -> dict:
    """Factor with Shanks' square forms factorization (numerisect-squfof, C/GMP)."""

    try:
        number = evaluate_integer(request.expression)
    except ExpressionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        result = squfof(number, request.max_iterations, request.timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PrimeEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    rows = [
        f"Input: {result['number']}",
        f"Status: {result['status']}",
        f"Multiplier: {result['multiplier']}",
        f"Iterations: {result['iterations']}",
    ]
    if result["factor"]:
        rows.append(f"Factor: {result['factor']} x {result['cofactor']}")
    return _save_factor_lab_report("squfof", "SQUFOF factorization", result, rows)


@app.post("/api/factor-lab/special-form")
def factor_lab_special_form(request: SpecialFormRequest) -> dict:
    """Detect special algebraic forms, algebraic factors, and SNFS suitability."""

    try:
        result = special_form_analysis(request.expression, request.timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PrimeEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    rows = [f"Value: {result['value']} ({result['digits']} digits)"]
    rows.extend(f"Form: {row['kind']} - {row['detail']}" for row in result["forms"])
    rows.extend(
        f"Algebraic factor: {row['factor']} ({row['identity']})"
        for row in result["algebraic_factors"]
    )
    rows.append(f"SNFS suitable: {'yes' if result['snfs_suitable'] else 'no'}")
    if result["snfs_polynomial"]:
        rows.append(f"SNFS polynomial: {result['snfs_polynomial']}")
    return _save_factor_lab_report("special-form", "Special-form analysis", result, rows)


@app.post("/api/factor-lab/strategy")
def factor_lab_strategy(request: StrategyRequest) -> dict:
    """Recommend an engine and estimate the expected remaining factor size."""

    try:
        result = strategy_advice(
            request.expression, request.pretest_level, request.timeout_seconds
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PrimeEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    rows = [f"Value: {result['value']} ({result['digits']} digits)"]
    rows.extend(
        f"{row['question']} -> {row['answer']} ({row['consequence']})"
        for row in result["decision_path"]
    )
    rows.append(f"Recommended engine: {result['recommended_engine']}")
    rows.append(f"Expected factor digits: {result['expected_factor_digits']}")
    return _save_factor_lab_report("strategy", "Factorization strategy advice", result, rows)


@app.post("/api/factor-lab/trace")
def factor_lab_trace(request: TraceRequest) -> dict:
    """Produce a bounded, educational step trace of a factoring algorithm."""

    try:
        result = algorithm_trace(
            request.expression, request.algorithm, request.steps, request.timeout_seconds
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PrimeEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    rows = [f"Value: {result['value']}", f"Algorithm: {result['algorithm']}"]
    rows.extend(
        f"step {row['step']}: {row['state']} | quantity {row['quantity']} | gcd {row['gcd']}"
        for row in result["steps"]
    )
    return _save_factor_lab_report("algorithm-trace", "Algorithm trace", result, rows)


@app.post("/api/factor-lab/certificates")
def factor_lab_certificates(request: CertificateBatchRequest) -> dict:
    """Generate and independently verify a primality certificate per prime factor."""

    try:
        result = batch_certificates(request.factors, request.timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PrimeEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    rows = [
        f"{row['factor']}: prime={row['prime']} certified={row['certified']} "
        f"verified={row['verified']}"
        for row in result["certificates"]
    ]
    return _save_factor_lab_report("certificates", "Batch primality certificates", result, rows)


class TuneRequest(BaseModel):
    threads: int = Field(default=os.cpu_count() or 1, ge=1, le=256)


class DistributedFactorRequest(BaseModel):
    """A distributed CADO-NFS run. Every field maps to a CADO parameter."""

    expression: str = Field(..., min_length=1, max_length=MAX_EXPRESSION_CHARACTERS)
    address: str = Field("127.0.0.1", max_length=255)
    port: int = Field(8790, ge=1024, le=65535)
    whitelist: list[str] = Field(default_factory=lambda: ["127.0.0.1"], max_length=64)
    ssl: bool = True
    clients: int = Field(2, ge=1, le=1024)
    hostnames: list[str] = Field(default_factory=list, max_length=128)
    script_path: str | None = Field(None, max_length=500)
    client_threads: int | None = Field(None, ge=1, le=256)
    threads: int = Field(default_factory=lambda: os.cpu_count() or 1, ge=1, le=256)
    confirm_network: bool = False


# --- Independent cross-engine verification, self-tests, and large-interval sieving ----
# These do what no single engine can do for itself: compare independent
# implementations, check engines against published constants, and enumerate primes
# above primesieve's 2^64 ceiling.


class CrossCheckCountRequest(BaseModel):
    expression: str = Field(..., min_length=1, max_length=200)
    threads: int = Field(1, ge=1, le=256)
    timeout_seconds: int = Field(600, ge=1, le=3600)


class CrossCheckPrimalityRequest(BaseModel):
    expression: str = Field(..., min_length=1, max_length=MAX_EXPRESSION_CHARACTERS)
    timeout_seconds: int = Field(300, ge=1, le=3600)


class SelfTestRequest(BaseModel):
    engines: list[str] | None = Field(None, max_length=16)
    timeout_seconds: int = Field(300, ge=1, le=3600)


class SieveIntervalRequest(BaseModel):
    start: str = Field(..., min_length=1, max_length=400)
    length: int = Field(..., ge=1, le=100_000_000)
    small_prime_bound: int = Field(1_000_000, ge=100, le=100_000_000)
    threads: int = Field(1, ge=1, le=1024)
    extra_rounds: int = Field(0, ge=0, le=64)
    preview: int = Field(1000, ge=1, le=100_000)
    timeout_seconds: int = Field(900, ge=1, le=3600)


@app.post("/api/verify/prime-count")
def verify_prime_count(request: CrossCheckCountRequest) -> dict:
    """Compare every available pi(x) method across as many as three engine implementations."""

    try:
        bound = evaluate_arbitrary_integer(request.expression)
    except ExpressionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        result = cross_check_prime_count(bound, request.threads, request.timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PrimeEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    lines = [result["note"], "", "Engine | Value | Seconds"]
    lines.extend(
        f"{row['engine']} | {row['value'] or row.get('error', '')} | {row['seconds']}"
        for row in result["sources"]
    )
    path = save_prime_output("verify-count", "Independent pi(x) cross-check", lines)
    return {**result, "output_file": path.name}


@app.post("/api/verify/primality")
def verify_primality(request: CrossCheckPrimalityRequest) -> dict:
    """Decide primality with independent implementations and compare them."""

    try:
        number = evaluate_arbitrary_integer(request.expression)
    except ExpressionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        result = cross_check_primality(number, request.timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PrimeEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    lines = [result["note"], "", "Engine | Prime | Proof"]
    lines.extend(
        f"{row['engine']} | {row['prime']} | {'proof' if row['proof'] else 'probable'}"
        for row in result["sources"]
    )
    path = save_prime_output("verify-primality", "Independent primality cross-check", lines)
    return {**result, "output_file": path.name}


@app.post("/api/verify/self-test")
def verify_engines(request: SelfTestRequest) -> dict:
    """Ask each installed engine questions with published answers."""

    try:
        result = self_test(request.engines, request.timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    lines = [result["note"], "", "Engine | Question | Status | Expected | Actual | Source"]
    lines.extend(
        f"{row['engine']} | {row['question']} | {row['status']} | {row['expected']} | "
        f"{row['actual']} | {row['cites']}"
        for row in result["results"]
    )
    path = save_prime_output("engine-self-test", "Engine self-test", lines)
    return {**result, "output_file": path.name}


@app.post("/api/primes/sieve-interval")
def sieve_large_interval(request: SieveIntervalRequest) -> dict:
    """Enumerate primes in an interval of any magnitude.

    Uses the project's own GMP and OpenMP sieve, because primesieve refuses inputs
    at or above 2**64 and PARI's forprime is single-threaded and much slower there.
    """

    try:
        start = evaluate_arbitrary_integer(request.start)
    except ExpressionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        result = sieve_interval(
            start, request.length, request.small_prime_bound, request.threads,
            request.extra_rounds, request.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PrimeEngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    lines = [
        result["note"], "",
        f"Interval: [{result['start']}, {result['start']} + {result['length']})",
        f"Presieve bound: {result['small_prime_bound']}",
        f"Candidates after presieve: {result['candidates']}",
        f"Primes found: {result['count']} ({result['status']})",
        "",
    ]
    lines.extend(result["primes"])
    path = save_prime_output("sieve-interval", "Large-interval prime enumeration", lines)
    # The report holds every prime; the response is capped so a huge run does not
    # travel through JSON and the browser.
    shown = result["primes"][: request.preview]
    return {
        **result,
        "primes": shown,
        "preview_truncated": len(shown) < result["count"],
        "output_file": path.name,
    }


@app.get("/api/distributed/trust-model")
def distributed_trust_model() -> dict:
    """Describe how distributed CADO authenticates clients, and what it does not."""

    return {
        **describe_trust_model(),
        "enabled_by_environment": ALLOW_NETWORK,
        "environment_variable": "NUMERISECT_ALLOW_NETWORK",
        "cado_available": bool(executable_path("cado-nfs.py")),
        "client_script": str(find_client_script() or ""),
    }


@app.post("/api/distributed/preview")
def preview_distributed_configuration(request: DistributedFactorRequest) -> dict:
    """Validate a distributed configuration and report its exposure without running.

    This performs no networking and starts nothing. It exists so the exposure can
    be read before a run is approved.
    """

    try:
        plan = validate_configuration(
            address=request.address, port=request.port, whitelist=request.whitelist,
            ssl=request.ssl, clients=request.clients, hostnames=request.hostnames,
            script_path=request.script_path, client_threads=request.client_threads,
        )
    except DistributedConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "cado_parameters": plan["parameters"],
        "exposure": plan["exposure"],
        "warnings": plan["warnings"],
        "trust_model": describe_trust_model(),
        "worker_command_template": client_command(
            f"{'https' if request.ssl else 'http'}://{request.address}:{request.port}",
            certsha1="<printed by CADO when the server starts>" if request.ssl else None,
            threads=request.client_threads,
        ),
        "note": (
            "Nothing was started and no connection was made. Review the exposure and "
            "warnings, then submit the same configuration to /api/distributed/factor "
            "with confirm_network set."
        ),
    }


@app.post("/api/distributed/factor", status_code=202)
def start_distributed_factorization(request: DistributedFactorRequest) -> dict:
    """Queue a factorization whose sieving is distributed by CADO-NFS.

    Refused unless the process was started with NUMERISECT_ALLOW_NETWORK=1 and the
    request carries confirm_network, matching every other outbound feature.
    """

    if not request.confirm_network:
        raise HTTPException(
            status_code=403,
            detail=(
                "This request did not set confirm_network, so nothing was started. "
                "Read GET /api/distributed/trust-model first: CADO authenticates "
                "clients by IP address only."
            ),
        )
    local_only = request.address in {"127.0.0.1", "localhost", "::1"} and not request.hostnames
    if not local_only and not ALLOW_NETWORK:
        raise HTTPException(
            status_code=403,
            detail=(
                "Distributed runs that leave this machine require "
                "NUMERISECT_ALLOW_NETWORK=1. A loopback-only run with no remote "
                "workers is allowed without it."
            ),
        )
    try:
        number = evaluate_integer(request.expression)
    except ExpressionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        plan = validate_configuration(
            address=request.address, port=request.port, whitelist=request.whitelist,
            ssl=request.ssl, clients=request.clients, hostnames=request.hostnames,
            script_path=request.script_path, client_threads=request.client_threads,
        )
    except DistributedConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        job = manager.create(
            expression=request.expression, number=number, requested_backend="cado",
            threads=request.threads, pretest_level=DEFAULT_PRETEST_LEVEL,
            trial_bound=100_000, cado_parameter_size=None, distributed=plan,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        **_public_job(job),
        "exposure": plan["exposure"],
        "warnings": plan["warnings"],
        "note": (
            "CADO-NFS runs its own work-unit server with these parameters. Watch the "
            "job log for the server URL and certificate hash, then start workers with "
            "cado-nfs-client.py on the machines you listed."
        ),
    }


@app.post("/api/factor-lab/tune", status_code=202)
def start_engine_tuning(request: TuneRequest) -> dict[str, object]:
    """Measure this machine's SIQS/NFS crossover with YAFU's own `tune`.

    The measurement is performed by YAFU. The result is reported as a suggestion;
    Numerisect never rewrites its own configuration.
    """

    if not GGNFS_DIR:
        raise HTTPException(
            status_code=503,
            detail=(
                "Tuning needs the GGNFS lattice sievers. Set NUMERISECT_GGNFS_DIR to the "
                "directory holding gnfs-lasieve4I*e and restart."
            ),
        )
    try:
        job = manager.create(
            expression="tune", number=2, requested_backend="tune",
            threads=request.threads, pretest_level=DEFAULT_PRETEST_LEVEL,
            trial_bound=100_000, cado_parameter_size=None,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        **_public_job(job),
        "note": (
            "Tuning runs YAFU across progressively larger inputs and can take many "
            "minutes. Watch the job log; the measured crossover appears as a warning "
            "on the finished job."
        ),
    }


@app.post("/api/jobs/{job_id}/certificates")
def job_certificates(job_id: str) -> dict:
    """Certify every prime factor of a completed factorization (roadmap item 13)."""

    job = database.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    values = [
        str(factor["value"])
        for factor in (job.get("factors") or [])
        if str(factor.get("status", "")) in {"prime", "probable prime"}
    ]
    if not values:
        raise HTTPException(status_code=409, detail="This job has no prime factors to certify")
    try:
        result = batch_certificates(values)
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    rows = [
        f"{row['factor']}: prime={row['prime']} certified={row['certified']} "
        f"verified={row['verified']}"
        for row in result["certificates"]
    ]
    return _save_factor_lab_report(
        "certificates", f"Certificates for factorization {job_id[:12]}", {**result, "job_id": job_id}, rows
    )


# --- Algebra laboratory: modular, arithmetic, and algebraic workbenches -------
# Roadmap items 45, 48, 50, 57, 61, 68-71, 74, 110-113, and 115.  Every request
# model below is validated into bounded integers before it reaches PARI/GP.


class ReciprocityTraceRequest(BaseModel):
    a: str = Field(default="30", min_length=1, max_length=100_000)
    n: str = Field(default="101", min_length=1, max_length=100_000)
    trace_limit: int = Field(default=1_000, ge=0, le=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class CongruenceRequest(BaseModel):
    coefficients: list[str] = Field(min_length=2, max_length=65)
    modulus: str = Field(min_length=1, max_length=100_000)
    limit: int = Field(default=10_000, ge=1, le=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class DiscreteLogLabRequest(BaseModel):
    target: str = Field(min_length=1, max_length=100_000)
    base: str = Field(min_length=1, max_length=100_000)
    modulus: str = Field(min_length=1, max_length=100_000)
    algorithm: Literal["bsgs", "pohlig_hellman", "pollard_rho", "native"] = "bsgs"
    step_limit: int = Field(default=1_000_000, ge=1, le=100_000_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class FiniteFieldRequest(BaseModel):
    characteristic: str = Field(default="2", min_length=1, max_length=100)
    degree: int = Field(default=3, ge=1, le=16)
    modulus_coefficients: list[str] = Field(default_factory=list, max_length=17)
    a_coefficients: list[str] = Field(min_length=1, max_length=16)
    b_coefficients: list[str] = Field(min_length=1, max_length=16)
    exponent: int = Field(default=2, ge=-1_000_000, le=1_000_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class DivisorLatticeRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    divisor_limit: int = Field(default=10_000, ge=1, le=100_000)
    lattice_cap: int = Field(default=1_000, ge=0, le=20_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class SmoothnessRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    smooth_bound: str = Field(default="100", min_length=1, max_length=100_000)
    rough_bound: str = Field(default="2", min_length=1, max_length=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class RecordNumberRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    bound: str = Field(default="10000", min_length=1, max_length=100_000)
    limit: int = Field(default=200, ge=1, le=10_000)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class WeirdNumberRequest(BaseModel):
    number: str = Field(min_length=1, max_length=100_000)
    subset_cap: int = Field(default=512, ge=1, le=4_096)
    witness_bits: int = Field(default=8_000_000, ge=0, le=2**31)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class SociableCycleRequest(BaseModel):
    start: str = Field(min_length=1, max_length=100_000)
    end: str = Field(min_length=1, max_length=100_000)
    max_length: int = Field(default=10, ge=1, le=1_000)
    term_bound: str = Field(default="1000000000000", min_length=1, max_length=100_000)
    limit: int = Field(default=1_000, ge=1, le=100_000)
    dedupe: bool = True
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class CornacchiaRequest(BaseModel):
    d: str = Field(default="1", min_length=1, max_length=100_000)
    number: str = Field(min_length=1, max_length=100_000)
    trace_limit: int = Field(default=1_000, ge=0, le=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class QuadraticRingRequest(BaseModel):
    radicand: str = Field(default="-1", min_length=1, max_length=100_000)
    a: str = Field(default="1", min_length=1, max_length=100_000)
    b: str = Field(default="1", min_length=1, max_length=100_000)
    prime: str = Field(default="5", min_length=1, max_length=100_000)
    certify_seconds: int = Field(default=10, ge=1, le=3600)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class NumberFieldRequest(BaseModel):
    coefficients: list[str] = Field(min_length=3, max_length=13)
    primes: list[str] = Field(min_length=1, max_length=32)
    element_coefficients: list[str] = Field(default_factory=list, max_length=12)
    class_seconds: int = Field(default=10, ge=1, le=3600)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class ChebotarevRequest(BaseModel):
    coefficients: list[str] = Field(min_length=3, max_length=8)
    bound: str = Field(default="2000", min_length=1, max_length=100)
    group_seconds: int = Field(default=20, ge=1, le=3600)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


@app.post("/api/algebra/reciprocity")
def calculate_reciprocity_trace(request: ReciprocityTraceRequest) -> dict:
    try:
        result = reciprocity_trace(
            request.a, request.n, request.trace_limit, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "reciprocity-trace", "Quadratic-reciprocity reduction trace", result
    )


@app.post("/api/algebra/congruence")
def solve_congruence(request: CongruenceRequest) -> dict:
    try:
        result = congruence_solutions(
            request.coefficients, request.modulus, request.limit, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "congruence-solutions", "Polynomial congruence solutions", result
    )


@app.post("/api/algebra/discrete-log")
def calculate_discrete_logarithm_lab(request: DiscreteLogLabRequest) -> dict:
    try:
        result = discrete_logarithm_lab(
            request.target,
            request.base,
            request.modulus,
            request.algorithm,
            request.step_limit,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "discrete-log-laboratory", "Discrete-logarithm laboratory", result
    )


@app.post("/api/algebra/finite-field")
def calculate_finite_field(request: FiniteFieldRequest) -> dict:
    try:
        result = finite_field_arithmetic(
            request.characteristic,
            request.degree,
            request.modulus_coefficients,
            request.a_coefficients,
            request.b_coefficients,
            request.exponent,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "finite-field-arithmetic", "Finite-field arithmetic", result
    )


@app.post("/api/algebra/divisor-lattice")
def calculate_divisor_lattice(request: DivisorLatticeRequest) -> dict:
    try:
        result = divisor_lattice(
            request.number,
            request.divisor_limit,
            request.lattice_cap,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "divisor-lattice", "Complete divisor enumeration", result
    )


@app.post("/api/algebra/smoothness")
def calculate_smoothness_profile(request: SmoothnessRequest) -> dict:
    try:
        result = smoothness_profile(
            request.number,
            request.smooth_bound,
            request.rough_bound,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "smoothness-profile", "Smoothness and roughness profile", result
    )


@app.post("/api/algebra/record-numbers")
def calculate_record_numbers(request: RecordNumberRequest) -> dict:
    try:
        result = record_divisor_numbers(
            request.number, request.bound, request.limit, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "record-divisor-numbers", "Highly composite and abundance records", result
    )


@app.post("/api/algebra/weird-numbers")
def calculate_weird_numbers(request: WeirdNumberRequest) -> dict:
    try:
        result = weird_number_analysis(
            request.number,
            request.subset_cap,
            request.witness_bits,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "weird-number-analysis", "Abundance and weird-number analysis", result
    )


@app.post("/api/algebra/sociable")
def find_sociable_cycles(request: SociableCycleRequest) -> dict:
    try:
        result = sociable_cycles(
            request.start,
            request.end,
            request.max_length,
            request.term_bound,
            request.limit,
            request.dedupe,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "sociable-cycles", "Amicable and sociable cycles", result
    )


@app.post("/api/algebra/cornacchia")
def calculate_cornacchia(request: CornacchiaRequest) -> dict:
    try:
        result = cornacchia_representations(
            request.d, request.number, request.trace_limit, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "cornacchia-representations", "Cornacchia representations", result
    )


@app.post("/api/algebra/quadratic-ring")
def calculate_quadratic_ring(request: QuadraticRingRequest) -> dict:
    try:
        result = quadratic_ring_analysis(
            request.radicand,
            request.a,
            request.b,
            request.prime,
            request.certify_seconds,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "quadratic-ring", "Quadratic integer ring analysis", result
    )


@app.post("/api/algebra/number-field")
def calculate_number_field(request: NumberFieldRequest) -> dict:
    try:
        result = number_field_analysis(
            request.coefficients,
            request.primes,
            request.element_coefficients,
            request.class_seconds,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "number-field-decomposition", "Number-field prime decomposition", result
    )


@app.post("/api/algebra/chebotarev")
def calculate_chebotarev_density(request: ChebotarevRequest) -> dict:
    try:
        result = chebotarev_density(
            request.coefficients,
            request.bound,
            request.group_seconds,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "chebotarev-density", "Chebotarev density experiment", result
    )


# ---------------------------------------------------------------------------
# Binary quadratic forms, class groups, continued fractions and Pell equations.
# Kept as one contiguous block -- import, request models and routes together --
# so the feature can be reviewed and moved as a unit.
# Computation attribution: numerisect/forms_lab.py and forms_lab.gp, documented
# in docs/FORMS_LAB.md. Nothing below computes mathematics.
# ---------------------------------------------------------------------------
from .forms_lab import (  # noqa: E402
    class_group,
    compose_forms,
    continued_fraction,
    pell_solutions,
    prime_forms,
    reduce_form,
    reduced_forms,
    represent_integer,
)

ContinuedFractionMode = Literal["rational", "quadratic"]


class FormReductionRequest(BaseModel):
    a: str = Field(default="10", min_length=1, max_length=1_000)
    b: str = Field(default="7", min_length=1, max_length=1_000)
    c: str = Field(default="3", min_length=1, max_length=1_000)
    step_limit: int = Field(default=40, ge=0, le=100_000)
    cycle_limit: int = Field(default=10_000, ge=1, le=1_000_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class FormCompositionRequest(BaseModel):
    a1: str = Field(default="2", min_length=1, max_length=1_000)
    b1: str = Field(default="1", min_length=1, max_length=1_000)
    c1: str = Field(default="3", min_length=1, max_length=1_000)
    a2: str = Field(default="2", min_length=1, max_length=1_000)
    b2: str = Field(default="1", min_length=1, max_length=1_000)
    c2: str = Field(default="3", min_length=1, max_length=1_000)
    exponent: int = Field(default=3, ge=-1_000_000, le=1_000_000)
    order_limit: int = Field(default=1_000, ge=1, le=100_000)
    cycle_limit: int = Field(default=10_000, ge=1, le=1_000_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class PrimeFormRequest(BaseModel):
    discriminant: str = Field(default="-23", min_length=1, max_length=64)
    primes: list[str] = Field(default=["2", "3", "5", "7"], min_length=1, max_length=64)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class ClassGroupRequest(BaseModel):
    discriminant: str = Field(default="-23", min_length=1, max_length=64)
    generator_limit: int = Field(default=16, ge=1, le=64)
    timeout_seconds: int = Field(default=120, ge=1, le=3600)


class ReducedFormsRequest(BaseModel):
    discriminant: str = Field(default="-23", min_length=1, max_length=64)
    form_limit: int = Field(default=200, ge=1, le=100_000)
    cycle_limit: int = Field(default=10_000, ge=1, le=1_000_000)
    timeout_seconds: int = Field(default=120, ge=1, le=3600)


class FormRepresentationRequest(BaseModel):
    a: str = Field(default="1", min_length=1, max_length=1_000)
    b: str = Field(default="0", min_length=1, max_length=1_000)
    c: str = Field(default="3", min_length=1, max_length=1_000)
    number: str = Field(default="1729", min_length=1, max_length=1_000)
    solution_limit: int = Field(default=50, ge=1, le=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class ContinuedFractionRequest(BaseModel):
    mode: ContinuedFractionMode = "quadratic"
    numerator: str = Field(default="0", min_length=1, max_length=1_000)
    denominator: str = Field(default="1", min_length=1, max_length=1_000)
    radicand: str = Field(default="13", min_length=1, max_length=1_000)
    quotient_limit: int = Field(default=40, ge=1, le=100_000)
    convergent_limit: int = Field(default=40, ge=1, le=100_000)
    approximation_bound: str = Field(default="1000", min_length=1, max_length=1_000)
    preview_digits: int = Field(default=2_000, ge=1, le=100_000)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)


class PellRequest(BaseModel):
    d: str = Field(default="13", min_length=1, max_length=200)
    solution_count: int = Field(default=3, ge=1, le=100)
    digit_limit: int = Field(default=2_000, ge=1, le=100_000)
    period_limit: int = Field(default=100_000, ge=1, le=100_000)
    unit_seconds: int = Field(default=30, ge=1, le=3600)
    timeout_seconds: int = Field(default=120, ge=1, le=3600)


@app.post("/api/forms/reduce")
def calculate_form_reduction(request: FormReductionRequest) -> dict:
    try:
        result = reduce_form(
            request.a,
            request.b,
            request.c,
            request.step_limit,
            request.cycle_limit,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "form-reduction", "Binary quadratic form reduction", result
    )


@app.post("/api/forms/compose")
def calculate_form_composition(request: FormCompositionRequest) -> dict:
    try:
        result = compose_forms(
            request.a1,
            request.b1,
            request.c1,
            request.a2,
            request.b2,
            request.c2,
            request.exponent,
            request.order_limit,
            request.cycle_limit,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "form-composition", "Binary quadratic form composition", result
    )


@app.post("/api/forms/prime-form")
def calculate_prime_forms(request: PrimeFormRequest) -> dict:
    try:
        result = prime_forms(
            request.discriminant, request.primes, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "prime-forms", "Prime forms of a discriminant", result
    )


@app.post("/api/forms/class-group")
def calculate_form_class_group(request: ClassGroupRequest) -> dict:
    try:
        result = class_group(
            request.discriminant, request.generator_limit, request.timeout_seconds
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "form-class-group", "Form class number and class group", result
    )


@app.post("/api/forms/reduced-forms")
def calculate_reduced_forms(request: ReducedFormsRequest) -> dict:
    try:
        result = reduced_forms(
            request.discriminant,
            request.form_limit,
            request.cycle_limit,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "reduced-forms", "Reduced forms of a discriminant", result
    )


@app.post("/api/forms/represent")
def calculate_form_representation(request: FormRepresentationRequest) -> dict:
    try:
        result = represent_integer(
            request.a,
            request.b,
            request.c,
            request.number,
            request.solution_limit,
            request.timeout_seconds,
        )
    except (ValueError, PrimeEngineError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _save_manipulation_report(
        "form-representation", "Representation by a binary quadratic form", result
    )


@app.post("/api/forms/continued-fraction")
def calculate_continued_fraction(request: ContinuedFractionRequest) -> dict:
    # PARI/GP writes every partial quotient and convergent at full length to its own
    # file. Convergent denominators grow exponentially in the number of terms, so the
    # JSON response carries a bounded preview and this file carries the real answer.
    temporary_path, export_path = native_output_paths("continued-fraction-full")
    try:
        result = continued_fraction(
            request.mode,
            request.numerator,
            request.denominator,
            request.radicand,
            request.quotient_limit,
            request.convergent_limit,
            request.approximation_bound,
            request.preview_digits,
            temporary_path,
            request.timeout_seconds,
        )
        finalize_native_output(temporary_path, export_path)
    except (ValueError, PrimeEngineError) as exc:
        temporary_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        temporary_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    response = _save_manipulation_report(
        "continued-fraction", "Continued-fraction expansion", result
    )
    response["export_file"] = export_path.name
    return response


@app.post("/api/forms/pell")
def calculate_pell_solutions(request: PellRequest) -> dict:
    # Pell solutions grow without bound: for d = 1000099 the fundamental solution
    # already has 1,128 decimal digits. PARI/GP streams every solution at full length
    # to its own file and the JSON response carries an abbreviated preview.
    temporary_path, export_path = native_output_paths("pell-equation-full")
    try:
        result = pell_solutions(
            request.d,
            request.solution_count,
            request.digit_limit,
            request.period_limit,
            request.unit_seconds,
            temporary_path,
            request.timeout_seconds,
        )
        # quadunit can exceed its budget, in which case no solution is claimed and
        # nothing is written. That is an inconclusive result, not an engine failure.
        if result.get("available"):
            finalize_native_output(temporary_path, export_path)
        else:
            temporary_path.unlink(missing_ok=True)
    except (ValueError, PrimeEngineError) as exc:
        temporary_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        temporary_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    response = _save_manipulation_report(
        "pell-equation", "Pell equation solutions", result
    )
    if result.get("available"):
        response["export_file"] = export_path.name
    return response



def run() -> None:
    uvicorn.run("numerisect.main:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    run()
