"""GGNFS-family lattice sievers: discovery, capability reporting, and validation.

Why this module exists
----------------------
YAFU performs the number field sieve by shelling out to the GGNFS lattice sievers, the
``gnfs-lasieve4I<index>e`` programs.  Without them YAFU cannot sieve at all: it reports
``possibly bad path to siever`` for every relation file, then exits non-zero having found
nothing.  On a 100-digit input that failure looks like an engine crash rather than a
missing dependency, which is exactly what it was on the machine this module was written
on.

Numerisect ships no sievers.  It locates the ones already present, checks that they will
actually run on this CPU, records what it found, and hands the directory to YAFU.  The
sieving itself, and the choice of which index to use for a given difficulty, remain
YAFU's decisions; nothing here second-guesses them.

lasieve4 and lasieve5
---------------------
Two lines of these sievers are in circulation.  ``lasieve4`` is the long-standing GGNFS
siever.  ``lasieve5`` is a newer line distributed with recent YAFU releases, including
builds targeting AVX-512, which are reported to sieve appreciably faster on hardware that
supports those instructions.  Both use the same ``gnfs-lasieve4I<index>e`` file names, so
the file name alone cannot tell them apart.  This module reports the line from the
directory the binaries were found in and says so, rather than claiming to have identified
the build.

Why the CPU check matters
-------------------------
An AVX-512 siever on a CPU without AVX-512 dies with an illegal instruction the moment it
is asked to work.  A configuration pointing at such a build looks correct on paper and
fails at run time.  Every discovered siever is therefore executed once, with no job file,
and a binary killed by SIGILL is reported as unusable on this machine instead of being
offered to YAFU.
"""

from __future__ import annotations

import hashlib
import os
import re
import signal
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .config import GGNFS_DIR, TOOLS_DIR

#: GGNFS lattice siever file names: gnfs-lasieve4I11e through gnfs-lasieve4I16e.
SIEVER = re.compile(r"^gnfs-lasieve4I(\d{2})e$")

#: Instruction-set extensions a siever build may require, in the order we report them.
FEATURES = ("avx512f", "avx512dq", "avx512bw", "avx2", "sse4_2")

PROBE_SECONDS = 10


@dataclass
class Siever:
    """One discovered lattice siever."""

    path: Path
    index: int
    sha256: str
    runnable: bool
    detail: str


@dataclass
class SieverSet:
    """Every siever found in one directory."""

    directory: Path
    line: str
    sievers: list[Siever] = field(default_factory=list)

    @property
    def usable(self) -> list[Siever]:
        return [s for s in self.sievers if s.runnable]

    @property
    def indices(self) -> list[int]:
        return sorted(s.index for s in self.usable)


def cpu_features() -> list[str]:
    """Instruction-set extensions this CPU advertises, restricted to ones we report."""

    try:
        text = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    flags: set[str] = set()
    for line in text.splitlines():
        if line.startswith("flags") and ":" in line:
            flags.update(line.split(":", 1)[1].split())
    return [feature for feature in FEATURES if feature in flags]


def _line_of(directory: Path) -> str:
    """Which siever line a directory claims, by its own name.

    This is what the path says, not a fingerprint of the binaries. The two lines share
    file names, so a directory that does not say is reported as unidentified.
    """

    lowered = str(directory).lower()
    if "lasieve5" in lowered:
        return "lasieve5 (per the directory name)"
    if "lasieve4" in lowered or "ggnfs" in lowered:
        return "lasieve4 (per the directory name)"
    return "unidentified"


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def probe(path: Path) -> tuple[bool, str]:
    """Run one siever with no job file and decide whether it works on this CPU.

    A siever with nothing to do prints a complaint and exits. One built for instructions
    this CPU lacks is killed by SIGILL instead, which is the case worth catching: the
    path is correct, the file is present, and it still cannot run.
    """

    try:
        completed = subprocess.run(
            [str(path)],
            capture_output=True,
            timeout=PROBE_SECONDS,
            check=False,
        )
    except OSError as exc:
        return False, f"could not be executed: {exc.strerror or exc}"
    except subprocess.TimeoutExpired:
        return False, "did not exit within the probe budget"

    if completed.returncode == -signal.SIGILL:
        return False, "illegal instruction: built for a CPU feature this machine lacks"
    if completed.returncode < 0:
        name = signal.Signals(-completed.returncode).name
        return False, f"killed by {name}"
    return True, "runs on this CPU"


def candidate_directories() -> list[Path]:
    """Directories to search, most explicit first.

    The configured directory wins, then Numerisect's own managed tools, then the
    conventional install locations. Nothing outside this list is searched.
    """

    found: list[Path] = []
    for raw in (
        GGNFS_DIR,
        str(TOOLS_DIR / "bin"),
        os.path.expanduser("~/ggnfs/bin"),
        "/usr/local/bin",
        "/usr/bin",
    ):
        if not raw:
            continue
        path = Path(raw).expanduser()
        if path.is_dir() and path not in found:
            found.append(path)
    return found


def discover(probe_binaries: bool = True) -> list[SieverSet]:
    """Find every directory holding lattice sievers, in search order."""

    results: list[SieverSet] = []
    for directory in candidate_directories():
        try:
            names = sorted(directory.iterdir())
        except OSError:
            continue
        group = SieverSet(directory=directory, line=_line_of(directory))
        for entry in names:
            match = SIEVER.match(entry.name)
            if not match or not entry.is_file() or not os.access(entry, os.X_OK):
                continue
            if probe_binaries:
                runnable, detail = probe(entry)
            else:
                runnable, detail = True, "not probed"
            group.sievers.append(
                Siever(
                    path=entry,
                    index=int(match.group(1)),
                    sha256=_digest(entry),
                    runnable=runnable,
                    detail=detail,
                )
            )
        if group.sievers:
            results.append(group)
    return results


def siever_directory() -> Path | None:
    """The directory Numerisect should hand to YAFU, or ``None`` if there is none.

    The first directory in search order that holds at least one siever this CPU can
    actually run. A directory whose binaries all fail to run is skipped rather than
    passed on, because YAFU would accept it and then fail mid-sieve.
    """

    for group in discover():
        if group.usable:
            return group.directory
    return None


def report() -> dict[str, object]:
    """Everything known about lattice sieving on this machine."""

    groups = discover()
    rows: list[list[str]] = []
    for group in groups:
        for siever in sorted(group.sievers, key=lambda s: s.index):
            rows.append([
                f"I{siever.index}e",
                str(group.directory),
                group.line,
                "yes" if siever.runnable else "no",
                siever.detail,
                siever.sha256[:16],
            ])

    chosen = siever_directory()
    usable = [s for g in groups for s in g.usable]
    features = cpu_features()
    metrics: dict[str, str] = {
        "Directories searched": str(len(candidate_directories())),
        "Directories holding sievers": str(len(groups)),
        "Sievers found": str(sum(len(g.sievers) for g in groups)),
        "Sievers that run on this CPU": str(len(usable)),
        "Selected directory": str(chosen) if chosen else "none",
        "Available sieve indices": (
            ", ".join(f"I{i}e" for i in sorted({s.index for s in usable})) or "none"
        ),
        "CPU features": ", ".join(features) or "none of the reported set",
        "AVX-512": "yes" if any(f.startswith("avx512") for f in features) else "no",
    }
    if chosen:
        note = (
            "YAFU will be given this directory for number field sieve work. YAFU itself "
            "chooses which sieve index to use for a given difficulty; Numerisect does not "
            "override that choice. The largest available index bounds the difficulty YAFU "
            "can attempt."
        )
    else:
        note = (
            "No usable lattice siever was found, so YAFU cannot run the number field "
            "sieve. It will still perform trial division, Pollard rho, P−1, P+1, ECM and "
            "the quadratic sieve. Install the GGNFS sievers, or set NUMERISECT_GGNFS_DIR "
            "to a directory holding gnfs-lasieve4I*e, to enable NFS. CADO-NFS is an "
            "independent alternative and does not need these binaries."
        )
    if groups and not usable:
        note = (
            "Lattice sievers were found but none of them runs on this CPU; the most "
            "common cause is an AVX-512 build on a machine without AVX-512. " + note
        )
    return {
        "columns": ["Index", "Directory", "Line", "Runs here", "Detail", "SHA-256 (first 16)"],
        "rows": rows,
        "metrics": metrics,
        "note": note,
    }
