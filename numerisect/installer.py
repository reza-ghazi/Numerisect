from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from .config import STATE_DIR, TOOLS_BIN_DIR, TOOLS_DIR, TOOLS_SOURCE_DIR
from .native_tools import build_zeta_tool, flint_available


ENGINE_COMMANDS = {
    "PARI/GP": "gp",
    "GMP-ECM": "ecm",
    "Msieve": "msieve",
    "YAFU": "yafu",
    "CADO-NFS": "cado-nfs.py",
    "FLINT/Zeta": "numerisect-zeta",
}

REPOSITORIES = {
    "PARI/GP": "https://pari.math.u-bordeaux.fr/git/pari.git",
    "GMP-ECM": "https://gitlab.inria.fr/zimmerma/ecm.git",
    "Msieve": "https://github.com/radii/msieve.git",
    "YAFU": "https://github.com/bbuhrow/yafu.git",
    "CADO-NFS": "https://gitlab.inria.fr/cado-nfs/cado-nfs.git",
    "FLINT": "https://github.com/flintlib/flint.git",
}


class EngineInstaller:
    """Best-effort, user-local source installer for missing factor engines."""

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
        data["log_path"] = str(self.log_path)
        data["managed_bin"] = str(TOOLS_BIN_DIR)
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
            raise RuntimeError(f"Command exited with status {result.returncode}: {' '.join(command)}")

    def _clone(self, name: str) -> Path:
        slug = name.lower().replace("-", "_").replace("/", "_")
        destination = TOOLS_SOURCE_DIR / slug
        if destination.exists():
            self._run(["git", "fetch", "--tags", "--prune", "origin"], destination)
            self._run(["git", "reset", "--hard", "origin/HEAD"], destination)
        else:
            self._run(["git", "clone", "--depth", "1", REPOSITORIES[name], str(destination)])
        if name == "YAFU":
            # YAFU publishes versioned releases; select the newest tag dynamically.
            self._run(["git", "fetch", "--tags", "--depth", "1", "origin"], destination)
            tags = subprocess.check_output(
                ["git", "tag", "--sort=-v:refname"], cwd=destination, text=True
            ).splitlines()
            release = next((tag for tag in tags if tag.startswith("v")), None)
            if release:
                self._run(["git", "checkout", "--force", release], destination)
        return destination

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
        source = self._clone("Msieve")
        self._run(["make", "-j", str(os.cpu_count() or 1), "x86_64"], source)
        self._copy_executable(source / "msieve", "msieve")

    def _install_yafu(self) -> None:
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
        source = self._clone("FLINT")
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
        self.log_path.write_text("Numerisect first-run engine setup\n", encoding="utf-8")
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
