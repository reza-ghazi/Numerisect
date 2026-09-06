from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tempfile
import threading
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from .config import PACKAGE_DIR, STATE_DIR, TOOLS_BIN_DIR, TOOLS_DIR, TOOLS_SOURCE_DIR
from .native_tools import build_zeta_tool, flint_available

MANIFEST_PATH = PACKAGE_DIR / "engine_manifest.toml"


@dataclass(frozen=True)
class EngineSource:
    """Reviewed source identity for one optional native engine."""

    name: str
    command: str
    repository: str
    upstream_ref: str
    revision: str
    source_kind: str
    archive_sha256: str
    license: str
    interaction: str
    platforms: str


def load_engine_manifest(path: Path = MANIFEST_PATH) -> dict[str, EngineSource]:
    """Load and strictly validate the pinned native-engine manifest."""

    with path.open("rb") as handle:
        document = tomllib.load(handle)
    entries = document.get("engine")
    if not isinstance(entries, list) or not entries:
        raise ValueError("The engine manifest must contain at least one [[engine]] entry")
    result: dict[str, EngineSource] = {}
    required = set(EngineSource.__dataclass_fields__)
    for raw in entries:
        if not isinstance(raw, dict) or set(raw) != required:
            raise ValueError("Every engine manifest entry must contain exactly the supported fields")
        source = EngineSource(**raw)
        if source.name in result:
            raise ValueError(f"Duplicate engine manifest entry: {source.name}")
        if len(source.revision) != 40 or any(c not in "0123456789abcdef" for c in source.revision):
            raise ValueError(f"Engine revision is not an immutable Git commit: {source.name}")
        if not source.repository.startswith("https://"):
            raise ValueError(f"Engine repository must use HTTPS: {source.name}")
        if source.source_kind != "git" or source.archive_sha256 != "not-applicable":
            raise ValueError(
                f"Unsupported source verification method for engine: {source.name}"
            )
        result[source.name] = source
    return result


ENGINE_SOURCES = load_engine_manifest()
ENGINE_COMMANDS = {name: source.command for name, source in ENGINE_SOURCES.items()}


class EngineInstaller:
    """Explicit, user-local source installer for pinned native engines."""

    def __init__(self) -> None:
        self.status_path = STATE_DIR / "engine-setup.json"
        self.log_path = STATE_DIR / "engine-setup.log"
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    @staticmethod
    def missing() -> list[str]:
        return [name for name, command in ENGINE_COMMANDS.items() if not shutil.which(command)]

    def status(self) -> dict[str, object]:
        if self.status_path.exists():
            try:
                data = json.loads(self.status_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
        else:
            data = {}
        data["missing"] = self.missing()
        return data

    def _write_status(self, **values: object) -> None:
        data = self.status()
        data.update(values)
        data["updated_at"] = datetime.now(UTC).isoformat()
        self.status_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _run(self, command: list[str], cwd: Path | None = None) -> None:
        with self.log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n$ {' '.join(command)}\n")
            log.flush()
            result = subprocess.run(
                command,
                cwd=cwd,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if result.returncode:
            raise RuntimeError(
                f"{Path(command[0]).name} exited with status {result.returncode}; "
                "inspect the local engine setup log for details"
            )

    def _clone(self, name: str) -> Path:
        source = ENGINE_SOURCES[name]
        slug = name.lower().replace("-", "_").replace("/", "_")
        destination = TOOLS_SOURCE_DIR / f"{slug}-{source.revision[:12]}"
        if destination.exists():
            completed = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=destination,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=False,
            )
            if completed.returncode or completed.stdout.strip() != source.revision:
                raise RuntimeError(
                    f"The managed {name} source directory does not match its pinned revision"
                )
        else:
            temporary = Path(
                tempfile.mkdtemp(prefix=f".{slug}-", dir=TOOLS_SOURCE_DIR)
            )
            try:
                self._run(["git", "init"], temporary)
                self._run(
                    ["git", "remote", "add", "origin", source.repository], temporary
                )
                self._run(
                    ["git", "fetch", "--depth", "1", "origin", source.revision],
                    temporary,
                )
                self._run(
                    ["git", "checkout", "--detach", source.revision], temporary
                )
                temporary.replace(destination)
            except Exception:
                shutil.rmtree(temporary, ignore_errors=True)
                raise
        return destination

    @staticmethod
    def _require_x86_64(name: str) -> None:
        architecture = platform.machine().lower()
        if architecture not in {"x86_64", "amd64"}:
            raise RuntimeError(
                f"The automated {name} recipe currently supports x86-64 only; "
                f"detected {architecture or 'unknown architecture'}"
            )

    @staticmethod
    def _copy_executable(source: Path, destination_name: str) -> None:
        destination = TOOLS_BIN_DIR / destination_name
        shutil.copy2(source, destination)
        destination.chmod(0o755)

    def _install_ecm(self) -> None:
        source = self._clone("GMP-ECM")
        if not (source / "configure").exists():
            self._run(["autoreconf", "-i"], source)
        prefix = TOOLS_DIR / "prefix"
        self._run([str(source / "configure"), f"--prefix={prefix}", "--enable-openmp"], source)
        self._run(["make", "-j", str(os.cpu_count() or 1)], source)
        self._run(["make", "install"], source)
        built = prefix / "bin" / "ecm"
        self._copy_executable(built, "ecm")

    def _install_pari(self) -> None:
        source = self._clone("PARI/GP")
        prefix = TOOLS_DIR / "prefix"
        self._run(
            [str(source / "Configure"), f"--prefix={prefix}", "--mt=pthread"],
            source,
        )
        self._run(["make", "-j", str(os.cpu_count() or 1), "gp"], source)
        self._run(["make", "install"], source)
        built = prefix / "bin" / "gp"
        launcher = TOOLS_BIN_DIR / "gp"
        launcher.unlink(missing_ok=True)
        launcher.symlink_to(built)

    def _install_msieve(self) -> None:
        self._require_x86_64("Msieve")
        source = self._clone("Msieve")
        self._run(["make", "-j", str(os.cpu_count() or 1), "x86_64"], source)
        self._copy_executable(source / "msieve", "msieve")

    def _install_yafu(self) -> None:
        self._require_x86_64("YAFU")
        source = self._clone("YAFU")
        self._run(["make", "-j", str(os.cpu_count() or 1)], source)
        self._copy_executable(source / "yafu", "yafu")
        for name in ("yafu.ini", "docfile.txt"):
            if (source / name).exists():
                shutil.copy2(source / name, TOOLS_BIN_DIR / name)

    def _install_cado(self) -> None:
        source = self._clone("CADO-NFS")
        self._run(["make", "-j", str(os.cpu_count() or 1)], source)
        launcher = TOOLS_BIN_DIR / "cado-nfs.py"
        launcher.unlink(missing_ok=True)
        launcher.symlink_to(source / "cado-nfs.py")

    def _install_flint(self) -> None:
        source = self._clone("FLINT/Zeta")
        prefix = TOOLS_DIR / "prefix"
        build = source / "build-numerisect"
        self._run(
            [
                "cmake",
                "-S",
                str(source),
                "-B",
                str(build),
                f"-DCMAKE_INSTALL_PREFIX={prefix}",
                "-DBUILD_SHARED_LIBS=ON",
            ]
        )
        self._run(["cmake", "--build", str(build), "-j", str(os.cpu_count() or 1)])
        self._run(["cmake", "--install", str(build)])

    def _install_flint_zeta(self) -> None:
        if not flint_available():
            self._install_flint()
        build_zeta_tool()

    def _install(self) -> None:
        recipes: dict[str, Callable[[], None]] = {
            "PARI/GP": self._install_pari,
            "GMP-ECM": self._install_ecm,
            "Msieve": self._install_msieve,
            "YAFU": self._install_yafu,
            "CADO-NFS": self._install_cado,
            "FLINT/Zeta": self._install_flint_zeta,
        }
        missing = self.missing()
        if not missing:
            self._write_status(state="ready", message="All engines are available")
            return
        self.log_path.write_text("Numerisect explicit engine setup\n", encoding="utf-8")
        self._write_status(
            state="installing",
            message="Installing missing engines into a user-owned directory",
            requested=missing,
        )
        try:
            for name in missing:
                self._write_status(state="installing", current=name, requested=missing)
                recipes[name]()
            remaining = self.missing()
            if remaining:
                raise RuntimeError(f"Installation finished but these engines remain unavailable: {remaining}")
            self._write_status(state="ready", current=None, message="All engines are available")
        except Exception as exc:
            self._write_status(state="failed", current=None, message=str(exc))

    def start_if_needed(self) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            if not self.missing():
                self._write_status(state="ready", message="All engines are available")
                return False
            self._thread = threading.Thread(
                target=self._install, name="engine-installer", daemon=True
            )
            self._thread.start()
            return True
