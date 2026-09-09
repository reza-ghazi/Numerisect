"""Optional CUDA acceleration for Mersenne trial factoring, compiled at run time.

Why NVRTC rather than nvcc
--------------------------
The obvious way to ship a CUDA kernel is to compile it with ``nvcc`` at install time.
That requires the CUDA toolkit, and a machine can have a perfectly good device without
one: the workstation this was written on has an RTX 5090, the driver, and the whole CUDA
runtime stack installed through pip, but no ``nvcc`` anywhere.  Requiring the toolkit
would have left that machine unable to use its own GPU.

NVRTC is the runtime compiler.  It ships with the same pip packages as the runtime, takes
CUDA C++ source as a string, and returns PTX the driver can load.  So the kernel is
compiled on first use, for the device actually present, with no toolkit involved.  The
``nvcc`` path still exists for anyone who has it; both compile the same kernel file.

What this is worth, measured
----------------------------
Honestly: less than one might hope.  On this machine the device tested about 16.5 million
candidates a second against the C helper's 7.4 million across 24 cores, a factor of about
2.2.  The kernel itself is not the limit; moving candidate lists from host to device is.
A pipeline that generated candidates on the device would do far better, and this is not
that.  It is offered as a real, verified option, not as the fast path.

What a hit means
----------------
The kernel reports q with ``2^order = 1 (mod q)``, which makes q a divisor of
``2^order - 1`` and says nothing about q being prime.  Composite divisors genuinely occur.
Callers must sieve beforehand and confirm primality in PARI/GP afterwards, exactly as the
C helper's pipeline does.
"""

from __future__ import annotations

import ctypes
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Any

KERNEL_SOURCE = Path(__file__).with_name("native") / "numerisect_mfactor_kernel.cu"
KERNEL_NAME = b"numerisect_mfactor_kernel"

#: Montgomery REDC needs the intermediate sum to fit in 64 bits.
MONTGOMERY_LIMIT = 1 << 63

_BLOCK = 256
_MAX_HITS = 4096


@dataclass
class Device:
    """A CUDA device this process can actually compile for and launch on."""

    name: str
    compute_capability: tuple[int, int]
    nvrtc_version: tuple[int, int]


def _bindings() -> Any:
    from cuda.bindings import driver, nvrtc

    return driver, nvrtc


def available() -> Device | None:
    """Report the usable CUDA device, or ``None`` with no exception raised.

    Every failure here is a normal outcome: no bindings installed, no driver, no device.
    None of them is an error, because the CPU helper is complete on its own.
    """

    try:
        driver, nvrtc = _bindings()
    except ImportError:
        return None
    try:
        error, major, minor = nvrtc.nvrtcVersion()
        if int(error) != 0:
            return None
        if int(driver.cuInit(0)[0]) != 0:
            return None
        error, count = driver.cuDeviceGetCount()
        if int(error) != 0 or count < 1:
            return None
        error, device = driver.cuDeviceGet(0)
        if int(error) != 0:
            return None
        _, raw_name = driver.cuDeviceGetName(96, device)
        attribute = driver.CUdevice_attribute
        _, capability_major = driver.cuDeviceGetAttribute(
            attribute.CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MAJOR, device
        )
        _, capability_minor = driver.cuDeviceGetAttribute(
            attribute.CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MINOR, device
        )
    except Exception:  # pragma: no cover - driver-specific failure modes
        return None
    return Device(
        name=raw_name.decode(errors="replace").split("\x00", 1)[0].strip(),
        compute_capability=(int(capability_major), int(capability_minor)),
        nvrtc_version=(int(major), int(minor)),
    )


def _check(error: Any, *rest: Any) -> Any:
    if int(error) != 0:
        raise RuntimeError(f"CUDA call failed: {error}")
    return rest[0] if len(rest) == 1 else rest


def compile_kernel(device: Device) -> bytes:
    """Compile the shared kernel to PTX for this device, raising on a compile error."""

    _, nvrtc = _bindings()
    source = KERNEL_SOURCE.read_text(encoding="utf-8").encode()
    program = _check(*nvrtc.nvrtcCreateProgram(source, b"mfactor.cu", 0, [], []))
    major, minor = device.compute_capability
    options = [f"--gpu-architecture=compute_{major}{minor}".encode(), b"-default-device"]
    (error,) = nvrtc.nvrtcCompileProgram(program, len(options), options)
    if int(error) != 0:
        _, size = nvrtc.nvrtcGetProgramLogSize(program)
        log = b" " * size
        nvrtc.nvrtcGetProgramLog(program, log)
        raise RuntimeError(
            "NVRTC could not compile the Mersenne kernel: "
            + log.decode(errors="replace").strip()
        )
    _, size = nvrtc.nvrtcGetPTXSize(program)
    ptx = b" " * size
    _check(*nvrtc.nvrtcGetPTX(program, ptx))
    return ptx


def test_candidates(order: int, ks: list[int], device: Device | None = None) -> list[int]:
    """Return every q = 2*k*order + 1 in ``ks`` that divides 2^order - 1.

    Args:
        order: The order divisor being searched. Must be odd and at least 3.
        ks: Candidate k values, already sieved by the caller.
        device: A device from :func:`available`; looked up when omitted.

    Returns:
        The divisors found, ascending. **These are divisors, not proven prime factors.**

    Raises:
        RuntimeError: If no device is usable, a candidate exceeds the Montgomery limit,
            or a CUDA call fails.
    """

    if order < 3 or order % 2 == 0:
        raise ValueError("The order must be an odd integer of at least 3")
    device = device or available()
    if device is None:
        raise RuntimeError("No usable CUDA device is available")
    if not ks:
        return []
    widest = 2 * max(ks) * order + 1
    if widest >= MONTGOMERY_LIMIT:
        raise RuntimeError(
            "A candidate reaches or exceeds 2**63, beyond the Montgomery bound; "
            "send that range to the CPU helper, which handles it with GMP"
        )

    driver, _ = _bindings()
    ptx = compile_kernel(device)
    _check(*driver.cuInit(0))
    handle = _check(*driver.cuDeviceGet(0))
    context = _check(*driver.cuCtxCreate(None, 0, handle))
    try:
        module = _check(*driver.cuModuleLoadData(ptx))
        function = _check(*driver.cuModuleGetFunction(module, KERNEL_NAME))
        # Buffers are plain stdlib arrays and ctypes values. Nothing here computes; it
        # only moves bytes, so no numeric library is involved.
        candidates = array("Q", ks)
        candidate_bytes = candidates.buffer_info()[1] * candidates.itemsize
        device_ks = _check(*driver.cuMemAlloc(candidate_bytes))
        device_hits = _check(*driver.cuMemAlloc(_MAX_HITS * 2 * 8))
        device_count = _check(*driver.cuMemAlloc(4))
        try:
            _check(*driver.cuMemcpyHtoD(
                device_ks, candidates.buffer_info()[0], candidate_bytes
            ))
            _check(*driver.cuMemsetD32(device_count, 0, 1))
            holders = [
                ctypes.c_uint64(int(device_ks)),
                ctypes.c_uint32(len(ks)),
                ctypes.c_uint64(order),
                ctypes.c_uint64(int(device_hits)),
                ctypes.c_uint64(int(device_count)),
                ctypes.c_uint32(_MAX_HITS),
            ]
            pointers = (ctypes.c_void_p * len(holders))(
                *[ctypes.cast(ctypes.byref(h), ctypes.c_void_p) for h in holders]
            )
            grid = (len(ks) + _BLOCK - 1) // _BLOCK
            _check(*driver.cuLaunchKernel(
                function, grid, 1, 1, _BLOCK, 1, 1, 0, 0,
                ctypes.addressof(pointers), 0
            ))
            _check(*driver.cuCtxSynchronize())
            found = ctypes.c_uint32(0)
            _check(*driver.cuMemcpyDtoH(ctypes.addressof(found), device_count, 4))
            total = int(found.value)
            if total > _MAX_HITS:
                raise RuntimeError(
                    f"The kernel found {total} divisors, more than the {_MAX_HITS} it "
                    "can return; narrow the k range"
                )
            if not total:
                return []
            out = array("Q", [0]) * (2 * total)
            _check(*driver.cuMemcpyDtoH(
                out.buffer_info()[0], device_hits, total * 2 * 8
            ))
            return sorted(int(out[2 * i]) for i in range(total))
        finally:
            for pointer in (device_ks, device_hits, device_count):
                driver.cuMemFree(pointer)
    finally:
        driver.cuCtxDestroy(context)
