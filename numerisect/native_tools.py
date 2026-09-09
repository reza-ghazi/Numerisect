from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from .config import NATIVE_DIR, STATE_DIR, TOOLS_BIN_DIR, TOOLS_DIR

_BUILD_LOCK = threading.Lock()
ZETA_TOOL_NAME = "numerisect-zeta"
SQUFOF_TOOL_NAME = "numerisect-squfof"
BIGSIEVE_TOOL_NAME = "numerisect-bigsieve"
MFACTOR_TOOL_NAME = "numerisect-mfactor"
MFACTOR_CUDA_TOOL_NAME = "numerisect-mfactor-cuda"


def _pkg_config_environment() -> dict[str, str]:
    environment = os.environ.copy()
    candidates = [
        TOOLS_DIR / "prefix" / "lib" / "pkgconfig",
        TOOLS_DIR / "prefix" / "lib64" / "pkgconfig",
    ]
    existing = environment.get("PKG_CONFIG_PATH", "")
    values = [str(path) for path in candidates]
    if existing:
        values.append(existing)
    environment["PKG_CONFIG_PATH"] = os.pathsep.join(values)
    return environment


def flint_available() -> bool:
    pkg_config = shutil.which("pkg-config")
    if pkg_config:
        result = subprocess.run(
            [pkg_config, "--exists", "flint"],
            env=_pkg_config_environment(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode == 0:
            return True
    return (TOOLS_DIR / "prefix" / "include" / "flint" / "flint.h").is_file()


def _ensure_flint_link_flag(flags: list[str]) -> list[str]:
    """Repair pkg-config output that omits FLINT's own linker flag."""

    if "-lflint" in flags:
        return flags
    first_library = next(
        (index for index, flag in enumerate(flags) if flag.startswith("-l")),
        len(flags),
    )
    return [*flags[:first_library], "-lflint", *flags[first_library:]]


def _pkg_config_flags(module: str) -> list[str]:
    """Return compiler and linker flags for a system or managed native library."""

    pkg_config = shutil.which("pkg-config")
    if not pkg_config:
        return []
    query = subprocess.run(
        [pkg_config, "--cflags", "--libs", module],
        env=_pkg_config_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    return shlex.split(query.stdout) if query.returncode == 0 else []


def _managed_library_flags(library: str) -> list[str]:
    """Fallback flags for a library built into Numerisect's managed prefix."""

    prefix = TOOLS_DIR / "prefix"
    return [
        f"-I{prefix / 'include'}",
        f"-L{prefix / 'lib'}",
        f"-L{prefix / 'lib64'}",
        f"-Wl,-rpath,{prefix / 'lib'}",
        f"-Wl,-rpath,{prefix / 'lib64'}",
        f"-l{library}",
    ]


def _darwin_openmp_flags(prefix: Path) -> list[str]:
    """Apple Clang flags for the keg-only Homebrew libomp runtime."""

    return [
        "-Xpreprocessor",
        "-fopenmp",
        f"-I{prefix / 'include'}",
        f"-L{prefix / 'lib'}",
        f"-Wl,-rpath,{prefix / 'lib'}",
        "-lomp",
    ]


def _openmp_flags() -> list[str]:
    """Return the host toolchain's OpenMP compile and link flags."""

    if sys.platform != "darwin":
        return ["-fopenmp"]

    configured = os.environ.get("NUMERISECT_LIBOMP_PREFIX", "").strip()
    candidates = [Path(configured)] if configured else []
    brew = shutil.which("brew")
    if brew:
        query = subprocess.run(
            [brew, "--prefix", "libomp"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        if query.returncode == 0 and query.stdout.strip():
            candidates.append(Path(query.stdout.strip()))
    candidates.extend((Path("/opt/homebrew/opt/libomp"), Path("/usr/local/opt/libomp")))
    prefix = next(
        (
            path
            for path in candidates
            if (path / "include" / "omp.h").is_file()
            and any((path / "lib" / name).is_file() for name in ("libomp.dylib", "libomp.a"))
        ),
        None,
    )
    if prefix is None:
        raise RuntimeError(
            "Homebrew libomp is required to build Numerisect's multithreaded native "
            "helpers on macOS"
        )
    return _darwin_openmp_flags(prefix)


def build_zeta_tool() -> Path:
    destination = TOOLS_BIN_DIR / ZETA_TOOL_NAME
    source = NATIVE_DIR / "numerisect_zeta.c"
    with _BUILD_LOCK:
        if not source.is_file():
            raise RuntimeError("The Numerisect FLINT zeta source file is missing")
        if destination.is_file() and destination.stat().st_mtime >= source.stat().st_mtime:
            return destination
        compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            raise RuntimeError("A C compiler is required to build the FLINT zeta helper")
        environment = _pkg_config_environment()
        flags = _pkg_config_flags("flint")
        if flags:
            flags = _ensure_flint_link_flag(flags)
        if not flags:
            prefix = TOOLS_DIR / "prefix"
            if not (prefix / "include" / "flint" / "flint.h").is_file():
                raise RuntimeError("FLINT development headers and libraries are unavailable")
            flags = [
                f"-I{prefix / 'include'}",
                f"-L{prefix / 'lib'}",
                f"-L{prefix / 'lib64'}",
                f"-Wl,-rpath,{prefix / 'lib'}",
                f"-Wl,-rpath,{prefix / 'lib64'}",
                "-lflint",
                "-lmpfr",
                "-lgmp",
            ]

        TOOLS_BIN_DIR.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        command = [
            compiler,
            "-O3",
            "-std=c11",
            *_openmp_flags(),
            str(source),
            "-o",
            str(temporary),
            *flags,
            f"-Wl,-rpath,{TOOLS_DIR / 'prefix' / 'lib'}",
            f"-Wl,-rpath,{TOOLS_DIR / 'prefix' / 'lib64'}",
            "-lm",
            "-lpthread",
        ]
        result = subprocess.run(
            command,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if result.returncode:
            temporary.unlink(missing_ok=True)
            (STATE_DIR / "zeta-build.log").write_text(
                result.stdout, encoding="utf-8", errors="replace"
            )
            raise RuntimeError(
                "Failed to build the FLINT zeta helper; inspect the local "
                "zeta-build.log in the Numerisect state directory"
            )
        temporary.chmod(0o755)
        temporary.replace(destination)
        return destination


def zeta_tool_path() -> Path:
    discovered = shutil.which(ZETA_TOOL_NAME)
    if discovered:
        path = Path(discovered)
        source = NATIVE_DIR / "numerisect_zeta.c"
        if (
            path != TOOLS_BIN_DIR / ZETA_TOOL_NAME
            or not source.is_file()
            or path.stat().st_mtime >= source.stat().st_mtime
        ):
            return path
    return build_zeta_tool()

def build_squfof_tool() -> Path:
    """Compile the SQUFOF helper, rebuilding when its source is newer.

    SQUFOF is implemented here in C because no installed library provides it: the
    YAFU build exposes no ``squfof`` function, PARI/GP exposes none, Msieve
    implements only QS/NFS, and GMP-ECM only ECM/P-1/P+1. GMP is used for input
    parsing only; the cycle runs in 64-bit registers.

    Returns:
        Path to the built executable.

    Raises:
        RuntimeError: If the source is missing, no compiler is available, or the
            build fails. The compiler output is written to ``squfof-build.log``
            in the Numerisect state directory.
    """

    destination = TOOLS_BIN_DIR / SQUFOF_TOOL_NAME
    source = NATIVE_DIR / "numerisect_squfof.c"
    with _BUILD_LOCK:
        if not source.is_file():
            raise RuntimeError("The Numerisect SQUFOF source file is missing")
        if destination.is_file() and destination.stat().st_mtime >= source.stat().st_mtime:
            return destination
        compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            raise RuntimeError("A C compiler is required to build the SQUFOF helper")
        TOOLS_BIN_DIR.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        flags = _pkg_config_flags("gmp") or _managed_library_flags("gmp")
        command = [
            compiler, "-O3", "-std=c11", str(source), "-o", str(temporary),
            *flags, "-lm",
        ]
        result = subprocess.run(
            command, env=_pkg_config_environment(), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, check=False,
        )
        if result.returncode:
            temporary.unlink(missing_ok=True)
            (STATE_DIR / "squfof-build.log").write_text(
                result.stdout, encoding="utf-8", errors="replace"
            )
            raise RuntimeError(
                "Failed to build the SQUFOF helper; inspect squfof-build.log "
                "in the Numerisect state directory"
            )
        temporary.chmod(0o755)
        temporary.replace(destination)
        return destination


def squfof_tool_path() -> Path:
    """Return the SQUFOF executable, building it on demand."""

    discovered = shutil.which(SQUFOF_TOOL_NAME)
    source = NATIVE_DIR / "numerisect_squfof.c"
    if discovered:
        path = Path(discovered)
        if (
            path != TOOLS_BIN_DIR / SQUFOF_TOOL_NAME
            or not source.is_file()
            or path.stat().st_mtime >= source.stat().st_mtime
        ):
            return path
    return build_squfof_tool()

def build_bigsieve_tool() -> Path:
    """Compile the arbitrary-precision segmented sieve, rebuilding when newer.

    primesieve is a 64-bit tool and refuses inputs at or above 2**64, and PARI's
    forprime is single-threaded and much slower there. This helper fills that gap
    with GMP and OpenMP.

    Returns:
        Path to the built executable.

    Raises:
        RuntimeError: If the source is missing, no compiler is available, or the
            build fails; the compiler output goes to ``bigsieve-build.log``.
    """

    destination = TOOLS_BIN_DIR / BIGSIEVE_TOOL_NAME
    source = NATIVE_DIR / "numerisect_bigsieve.c"
    with _BUILD_LOCK:
        if not source.is_file():
            raise RuntimeError("The Numerisect big-sieve source file is missing")
        if destination.is_file() and destination.stat().st_mtime >= source.stat().st_mtime:
            return destination
        compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            raise RuntimeError("A C compiler is required to build the big sieve")
        TOOLS_BIN_DIR.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        flags = _pkg_config_flags("gmp") or _managed_library_flags("gmp")
        command = [
            compiler, "-O3", "-std=c11", *_openmp_flags(), str(source),
            "-o", str(temporary), *flags, "-lm",
        ]
        result = subprocess.run(
            command, env=_pkg_config_environment(), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, check=False,
        )
        if result.returncode:
            temporary.unlink(missing_ok=True)
            (STATE_DIR / "bigsieve-build.log").write_text(
                result.stdout, encoding="utf-8", errors="replace"
            )
            raise RuntimeError(
                "Failed to build the big sieve; inspect bigsieve-build.log in the "
                "Numerisect state directory"
            )
        temporary.chmod(0o755)
        temporary.replace(destination)
        return destination


def bigsieve_tool_path() -> Path:
    """Return the big-sieve executable, building it on demand."""

    discovered = shutil.which(BIGSIEVE_TOOL_NAME)
    source = NATIVE_DIR / "numerisect_bigsieve.c"
    if discovered:
        path = Path(discovered)
        if (
            path != TOOLS_BIN_DIR / BIGSIEVE_TOOL_NAME
            or not source.is_file()
            or path.stat().st_mtime >= source.stat().st_mtime
        ):
            return path
    return build_bigsieve_tool()


def build_mfactor_tool() -> Path:
    """Compile the Mersenne trial-factoring helper, rebuilding when newer.

    PARI/GP searches the same progression correctly but with generic arbitrary-precision
    arithmetic on one core.  Measured here for p = 999999001, PARI sustained about 1.1
    million k per second against this helper's 1.3 billion, because the helper sieves the
    k range first, uses a 64-bit modular exponentiation below 2**64, and spreads the work
    over every core.  No installed library offers Mersenne trial factoring.

    Returns:
        Path to the built executable.

    Raises:
        RuntimeError: If the source is missing, no compiler is available, or the build
            fails; the compiler output goes to ``mfactor-build.log``.
    """

    destination = TOOLS_BIN_DIR / MFACTOR_TOOL_NAME
    source = NATIVE_DIR / "numerisect_mfactor.c"
    with _BUILD_LOCK:
        if not source.is_file():
            raise RuntimeError("The Numerisect Mersenne factor source file is missing")
        if destination.is_file() and destination.stat().st_mtime >= source.stat().st_mtime:
            return destination
        compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            raise RuntimeError("A C compiler is required to build the Mersenne factorer")
        TOOLS_BIN_DIR.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        flags = _pkg_config_flags("gmp") or _managed_library_flags("gmp")
        command = [
            compiler, "-O3", "-std=c11", *_openmp_flags(), str(source),
            "-o", str(temporary), *flags,
        ]
        result = subprocess.run(
            command, env=_pkg_config_environment(), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, check=False,
        )
        if result.returncode:
            temporary.unlink(missing_ok=True)
            (STATE_DIR / "mfactor-build.log").write_text(
                result.stdout, encoding="utf-8", errors="replace"
            )
            raise RuntimeError(
                "Failed to build the Mersenne factorer; inspect mfactor-build.log in "
                "the Numerisect state directory"
            )
        temporary.chmod(0o755)
        temporary.replace(destination)
        return destination


def mfactor_tool_path() -> Path:
    """Return the Mersenne factor executable, building it on demand."""

    discovered = shutil.which(MFACTOR_TOOL_NAME)
    source = NATIVE_DIR / "numerisect_mfactor.c"
    if discovered:
        path = Path(discovered)
        if (
            path != TOOLS_BIN_DIR / MFACTOR_TOOL_NAME
            or not source.is_file()
            or path.stat().st_mtime >= source.stat().st_mtime
        ):
            return path
    return build_mfactor_tool()


def cuda_compiler() -> str | None:
    """Locate nvcc, or return ``None`` when no CUDA toolkit is installed.

    A GPU driver alone is not enough: the toolkit ships the compiler, and a machine can
    have a working device with no way to build for it.  That is the case on the
    workstation this was written on.
    """

    candidates = [shutil.which(name) for name in ("nvcc", "nvcc-gpp15")]
    toolkit = Path("/usr/local/cuda/bin/nvcc")
    if toolkit.is_file() and os.access(toolkit, os.X_OK):
        candidates.append(str(toolkit))
    for candidate in candidates:
        if not candidate:
            continue
        # Presence on PATH is not enough. A wrapper script can exist while the compiler
        # it execs does not, which is exactly the state of nvcc-gpp15 on a machine with
        # the driver installed but no toolkit. Ask it to identify itself.
        try:
            probe = subprocess.run(
                [candidate, "--version"], stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=30, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if probe.returncode == 0:
            return candidate
    return None


def build_mfactor_cuda_tool() -> Path | None:
    """Compile the optional CUDA accelerator, or return ``None`` when it cannot be built.

    This computes nothing the C helper cannot and is never required.  A missing toolkit
    is not an error: the caller falls back to the CPU helper, which is complete on its
    own.

    Returns:
        Path to the built executable, or ``None`` when no CUDA compiler is available.

    Raises:
        RuntimeError: If a compiler was found but the build failed; the output goes to
            ``mfactor-cuda-build.log``.
    """

    source = NATIVE_DIR / "numerisect_mfactor_cuda.cu"
    if not source.is_file():
        return None
    compiler = cuda_compiler()
    if not compiler:
        return None
    destination = TOOLS_BIN_DIR / MFACTOR_CUDA_TOOL_NAME
    with _BUILD_LOCK:
        if destination.is_file() and destination.stat().st_mtime >= source.stat().st_mtime:
            return destination
        TOOLS_BIN_DIR.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        command = [compiler, "-O3", "-arch=native", str(source), "-o", str(temporary)]
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            check=False,
        )
        if result.returncode:
            temporary.unlink(missing_ok=True)
            (STATE_DIR / "mfactor-cuda-build.log").write_text(
                result.stdout, encoding="utf-8", errors="replace"
            )
            raise RuntimeError(
                "Failed to build the CUDA Mersenne factorer; inspect "
                "mfactor-cuda-build.log in the Numerisect state directory"
            )
        temporary.chmod(0o755)
        temporary.replace(destination)
        return destination
