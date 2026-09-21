"""The optional CUDA scanner, ``numerisect-mfactor-cuda``, built with nvcc.

Every test here skips cleanly without a CUDA toolkit, because the CPU helper is complete
on its own and a machine without a GPU must not fail the suite. The references are the
published factorizations, PARI/GP, and the compiled CPU helper, never a second search
written in Python.
"""

import subprocess

import pytest

from numerisect.native_tools import build_mfactor_cuda_tool, cuda_compiler, mfactor_tool_path
from numerisect.primes import _run_gp

NVCC = cuda_compiler()
needs_nvcc = pytest.mark.skipif(NVCC is None, reason="no CUDA toolkit installed")


def _scan(tool, order: int, k_start: int, k_end: int, bound: int) -> tuple[list[int], str]:
    """Run a scanner and return the divisors it reported, ascending, with its raw output."""

    output = subprocess.run(
        [str(tool), str(order), str(k_start), str(k_end), str(bound)],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "DONE:1" in output
    found = sorted(
        int(line.split(":", 1)[1].split("|")[0])
        for line in output.splitlines() if line.startswith("FACTOR:")
    )
    return found, output


@needs_nvcc
def test_the_nvcc_build_produces_a_working_binary():
    """With a toolkit present the offline build must work and agree with everything else."""

    tool = build_mfactor_cuda_tool()
    assert tool is not None and tool.is_file()
    found, output = _scan(tool, 43, 1, 30000, 100000)
    assert "STATUS:complete" in output
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


@needs_nvcc
@pytest.mark.parametrize("order,k_limit,expected", [
    (11, 20_000, [23, 89]),
    (23, 20_000, [47, 178481]),
    (29, 20_000, [233, 1103, 2089]),
])
def test_the_device_finds_the_published_factors(order, k_limit, expected):
    found, _ = _scan(build_mfactor_cuda_tool(), order, 1, k_limit, 100000)
    assert found == expected


@needs_nvcc
def test_the_sieve_removes_composite_divisors():
    """2047 = 23 * 89 divides 2^11 - 1, but the sieve takes it out before it is tested.

    A hit is still only a divisor; PARI/GP confirms primality in the pipeline.
    """

    found, _ = _scan(build_mfactor_cuda_tool(), 11, 1, 20_000, 100000)
    assert 2047 not in found
    assert {23, 89}.issubset(found)


@needs_nvcc
def test_candidates_beyond_two_limbs_are_deferred_not_skipped():
    """Silently skipping them would turn an untested range into an apparent absence."""

    order = 9223372036854775837           # odd, just above 2**63, so every q exceeds 2**127
    _, output = _scan(build_mfactor_cuda_tool(), order, 2**63, 2**63 + 1000, 1000)
    assert "CANDIDATES:0" in output
    assert "DEFERRED:0" not in output
    assert "STATUS:deferred-wide" in output


@needs_nvcc
def test_an_even_order_is_rejected():
    result = subprocess.run(
        [str(build_mfactor_cuda_tool()), "4", "1", "10", "100"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "DONE:" not in result.stdout


@needs_nvcc
def test_the_device_agrees_with_the_compiled_cpu_helper():
    """Two independent implementations of the same test must not disagree.

    The CPU helper is called directly: the pipeline itself prefers the device when one is
    present, so going through it would compare the device with itself.
    """

    order, k_limit = 2_000_003, 3_000_000
    device, _ = _scan(build_mfactor_cuda_tool(), order, 1, k_limit, 1_000_000)
    cpu, _ = _scan(mfactor_tool_path(), order, 1, k_limit, 1_000_000)
    assert device == cpu


def _prime_divisors_from_engine(order: int, k_limit: int) -> list[int]:
    """Every prime q = 2k*order + 1 in range that divides 2^order - 1, decided by PARI/GP.

    The reference must not be a second implementation of the same search in Python.
    This asks the engine directly, so a shared mistake in my own arithmetic cannot make
    the device look correct.
    """

    program = (
        f"d = {order}; for(k = 1, {k_limit}, my(q = 2*k*d + 1); "
        "if((q % 8 == 1 || q % 8 == 7) && Mod(2, q)^d == 1 && isprime(q), "
        "print(\"Q:\", q))); print(\"DONE:1\");"
    )
    lines = _run_gp(program, timeout=900)
    assert any(line.startswith("DONE:") for line in lines)
    return sorted(int(line[2:]) for line in lines if line.startswith("Q:"))


@needs_nvcc
@pytest.mark.parametrize("order,k_limit", [(11, 20_000), (23, 20_000), (43, 30_000)])
def test_the_device_matches_the_engine(order, k_limit):
    """The device and PARI/GP must return the same prime divisors over the same range.

    Every q here is far below the square of the sieve bound, so a composite divisor could
    not survive the sieve and the two answers must be identical.
    """

    found, _ = _scan(build_mfactor_cuda_tool(), order, 1, k_limit, 100000)
    assert found == _prime_divisors_from_engine(order, k_limit)
