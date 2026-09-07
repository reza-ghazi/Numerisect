from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import threading
from pathlib import Path

from .config import NATIVE_DIR, STATE_DIR, TOOLS_BIN_DIR, TOOLS_DIR

_BUILD_LOCK = threading.Lock()
ZETA_TOOL_NAME = "numerisect-zeta"
SQUFOF_TOOL_NAME = "numerisect-squfof"


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
        pkg_config = shutil.which("pkg-config")
        flags: list[str] = []
        if pkg_config:
            query = subprocess.run(
                [pkg_config, "--cflags", "--libs", "flint"],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if query.returncode == 0:
                flags = _ensure_flint_link_flag(shlex.split(query.stdout))
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
            "-fopenmp",
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
        command = [
            compiler, "-O3", "-std=c11", str(source), "-o", str(temporary),
            f"-I{TOOLS_DIR / 'prefix' / 'include'}",
            f"-L{TOOLS_DIR / 'prefix' / 'lib'}",
            f"-L{TOOLS_DIR / 'prefix' / 'lib64'}",
            f"-Wl,-rpath,{TOOLS_DIR / 'prefix' / 'lib'}",
            f"-Wl,-rpath,{TOOLS_DIR / 'prefix' / 'lib64'}",
            "-lgmp", "-lm",
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

