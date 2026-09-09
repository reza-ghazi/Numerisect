"""The optional CUDA accelerator.

Every test here skips cleanly with no device, because the CPU helper is complete on its
own and a machine without a GPU must not fail the suite.
"""

import subprocess

import pytest

from numerisect import gpu
from numerisect.native_tools import build_mfactor_cuda_tool, cuda_compiler

DEVICE = gpu.available()
needs_gpu = pytest.mark.skipif(DEVICE is None, reason="no usable CUDA device")


def test_absence_of_a_device_is_reported_not_raised():
    """Detection must never throw. Missing bindings, driver or device are all normal."""

    assert DEVICE is None or isinstance(DEVICE, gpu.Device)


NVCC = cuda_compiler()
needs_nvcc = pytest.mark.skipif(NVCC is None, reason="no CUDA toolkit installed")


@needs_nvcc
def test_the_nvcc_build_produces_a_working_binary():
    """With a toolkit present the offline build must work and agree with everything else."""

    tool = build_mfactor_cuda_tool()
    assert tool is not None and tool.is_file()
    output = subprocess.run(
        [str(tool), "43", "1", "30000", "100000"], capture_output=True, text=True
    ).stdout
    assert "DONE:1" in output
    assert "STATUS:complete" in output
    found = sorted(
        int(line.split(":", 1)[1].split("|")[0])
        for line in output.splitlines() if line.startswith("FACTOR:")
    )
    assert found == [431, 9719, 2099863]


@needs_nvcc
def test_the_nvcc_build_defers_wide_candidates_rather_than_skipping_them():
    """Beyond 2^63 Montgomery cannot run, and an untested range must not read as empty."""

    tool = build_mfactor_cuda_tool()
    output = subprocess.run(
        [str(tool), "384307168202282327", "1", "60", "100000"],
        capture_output=True, text=True,
    ).stdout
    assert "STATUS:deferred-wide" in output
    deferred = int(
        [line for line in output.splitlines() if line.startswith("DEFERRED:")][0][9:]
    )
    assert deferred >= 1
    # It reports nothing found, which is not the same as reporting no factor exists.
    assert "COUNT:0" in output


def test_detection_does_not_require_a_cuda_toolkit(monkeypatch):
    """nvcc is not needed: NVRTC compiles at run time.

    The workstation this was written on has an RTX 5090 and no nvcc anywhere, which is
    the case that motivated the runtime-compilation path.
    """

    from numerisect import native_tools

    monkeypatch.setattr(native_tools, "cuda_compiler", lambda: None)
    # Availability is decided by the driver and NVRTC, not by the offline compiler.
    assert gpu.available() is DEVICE or gpu.available() is not None or DEVICE is None


@needs_gpu
def test_the_kernel_compiles_for_this_device():
    ptx = gpu.compile_kernel(DEVICE)
    assert ptx.strip()
    assert b"numerisect_mfactor_kernel" in ptx


@needs_gpu
@pytest.mark.parametrize("order,k_limit,expected", [
    # Published factorizations, restricted to the sieved progression the pipeline uses.
    (23, 20_000, [47, 178481]),
    (29, 20_000, [233, 1103, 2089]),
    (43, 30_000, [431, 9719, 2099863]),
])
def test_the_device_finds_the_published_factors(order, k_limit, expected):
    ks = _sieved(order, k_limit)
    assert gpu.test_candidates(order, ks, DEVICE) == sorted(expected)


@needs_gpu
def test_a_hit_is_a_divisor_and_not_a_claim_of_primality():
    """2047 = 23 * 89 divides 2^11 - 1, so an unsieved scan reports it, correctly.

    This is why the pipeline sieves first and confirms primality in PARI/GP after.
    """

    unsieved = list(range(1, 20_001))
    assert 2047 in gpu.test_candidates(11, unsieved, DEVICE)
    assert gpu.test_candidates(11, _sieved(11, 20_000), DEVICE) == [23, 89]


@needs_gpu
def test_candidates_beyond_the_montgomery_bound_are_refused_not_skipped():
    """Silently skipping them would turn an untested range into an apparent absence."""

    order = 384307168202282327
    with pytest.raises(RuntimeError, match="2\\*\\*63"):
        gpu.test_candidates(order, [24], DEVICE)


@needs_gpu
def test_the_device_agrees_with_the_compiled_cpu_helper():
    """Two independent implementations of the same test must not disagree."""

    from numerisect.factor_lab import _mersenne_native_scan

    order, k_limit = 2_000_003, 3_000_000
    hits, _ = _mersenne_native_scan([order], k_limit, 600, None)
    cpu = sorted(int(q) for q, _, _ in hits)
    device = gpu.test_candidates(order, _sieved(order, k_limit), DEVICE)
    assert device == cpu


def test_an_even_order_is_rejected():
    with pytest.raises(ValueError):
        gpu.test_candidates(4, [1])


def _sieved(order: int, k_limit: int, bound: int = 100_000) -> list[int]:
    """The same small-prime sieve the C helper applies, for a comparable candidate set."""

    composite = bytearray(bound + 1)
    primes: list[int] = []
    for i in range(3, bound + 1, 2):
        if not composite[i]:
            primes.append(i)
            for j in range(i * i, bound + 1, 2 * i):
                composite[j] = 1
    dead = bytearray(k_limit + 1)
    for r in primes:
        a = (2 * order) % r
        if a == 0:
            continue
        k0 = (r - pow(a, r - 2, r)) % r
        for k in range(k0 or r, k_limit + 1, r):
            if 2 * k * order + 1 != r:
                dead[k] = 1
    return [
        k for k in range(1, k_limit + 1)
        if not dead[k] and (2 * k * order + 1) % 8 in (1, 7)
    ]
