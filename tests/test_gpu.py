"""The optional CUDA accelerator.

Every test here skips cleanly with no device, because the CPU helper is complete on its
own and a machine without a GPU must not fail the suite.
"""

import subprocess

import pytest

from numerisect import gpu
from numerisect.native_tools import build_mfactor_cuda_tool, cuda_compiler
from numerisect.primes import _run_gp

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
def test_the_nvcc_build_tests_wide_candidates_rather_than_deferring_them():
    """The two-limb kernel replaced deferral with an answer.

    q = 18446744073709551697 is prime, exceeds 2**64, and sits at k = 24 of its order's
    progression. This range used to come back deferred; it now comes back solved.
    """

    tool = build_mfactor_cuda_tool()
    output = subprocess.run(
        [str(tool), "384307168202282327", "1", "60", "100000"],
        capture_output=True, text=True,
    ).stdout
    assert "FACTOR:18446744073709551697|24" in output
    assert "DEFERRED:0" in output
    assert "STATUS:complete" in output


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
    # Published factorizations. The device sees the raw progression, so a composite
    # divisor may appear alongside them; only the primes are asserted as a subset.
    (23, 20_000, [47, 178481]),
    (29, 20_000, [233, 1103, 2089]),
    (43, 30_000, [431, 9719, 2099863]),
])
def test_the_device_finds_the_published_factors(order, k_limit, expected):
    found = gpu.test_candidates(order, _candidates(order, k_limit), DEVICE)
    assert set(expected).issubset(found)


@needs_gpu
def test_a_hit_is_a_divisor_and_not_a_claim_of_primality():
    """2047 = 23 * 89 divides 2^11 - 1, so an unsieved scan reports it, correctly.

    This is why the pipeline sieves first and confirms primality in PARI/GP after.
    """

    found = gpu.test_candidates(11, _candidates(11, 20_000), DEVICE)
    assert 2047 in found            # 2047 = 23 * 89, a genuine composite divisor
    assert {23, 89}.issubset(found)
    # PARI/GP, asked the same question over the same range, agrees exactly.
    assert found == _divisors_from_engine(11, 20_000)


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
    device = gpu.test_candidates(order, _candidates(order, k_limit), DEVICE)
    # The C helper sieves and PARI/GP confirms primality, so it reports prime factors
    # only; the device sees the raw progression. Every prime factor must still appear.
    assert set(cpu).issubset(device)


def test_an_even_order_is_rejected():
    with pytest.raises(ValueError):
        gpu.test_candidates(4, [1])


def _divisors_from_engine(order: int, k_limit: int) -> list[int]:
    """Every q = 2k*order + 1 in range that divides 2^order - 1, decided by PARI/GP.

    The reference must not be a second implementation of the same search in Python.
    This asks the engine directly, so a shared mistake in my own arithmetic cannot make
    the device look correct.
    """

    program = (
        f"d = {order}; for(k = 1, {k_limit}, my(q = 2*k*d + 1); "
        "if((q % 8 == 1 || q % 8 == 7) && Mod(2, q)^d == 1, print(\"Q:\", q)));"
        " print(\"DONE:1\");"
    )
    lines = _run_gp(program, timeout=900)
    assert any(line.startswith("DONE:") for line in lines)
    return sorted(int(line[2:]) for line in lines if line.startswith("Q:"))


def _candidates(order: int, k_limit: int) -> list[int]:
    """Every k whose q satisfies the mod-8 condition, unsieved.

    The device is handed the raw progression rather than a Python-sieved subset, so the
    test exercises the kernel rather than a filter written here.
    """

    return [k for k in range(1, k_limit + 1) if (2 * k * order + 1) % 8 in (1, 7)]


@needs_gpu
@pytest.mark.parametrize("order,k_limit", [(11, 20_000), (23, 20_000), (43, 30_000)])
def test_the_device_matches_the_engine(order, k_limit):
    """The device and PARI/GP must return the same divisors over the same range."""

    assert gpu.test_candidates(order, _candidates(order, k_limit), DEVICE) == (
        _divisors_from_engine(order, k_limit)
    )
