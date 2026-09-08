# Installation and versioning

Numerisect 0.6.0 is an experimental, source-distributed pre-release. No
official RPM, DEB, AppImage, macOS package, Windows executable, or other binary
installer is published. The repository includes `install.sh` as a convenience
for installing a checked-out source revision into a user-owned directory.

## Verified and expected hosts

The current application, source installer, and complete native test suite are exercised
on Fedora Linux x86-64 and by GitHub Actions on Ubuntu Linux x86-64 and ARM64, Ubuntu
24.04 x86-64 under Windows WSL, and macOS on ARM64 and Intel. The installer also contains
a package-manager path for Arch Linux, but the project has not completed clean-host
verification there.

The application installer accepts Linux/WSL and macOS on x86-64 or ARM64.
However, the automated YAFU and Msieve source recipes currently reject ARM64;
those two recipes are verified only for x86-64 Linux/WSL. Native Windows
outside WSL is unsupported.

The cross-platform workflow checks prerequisite detection, runs the complete native test
suite, installs a versioned user-local copy, and smoke-tests its installed CLI on every
supported CI host.

## Dependency groups

Required Python runtime dependencies:

- Python 3.11 or newer;
- FastAPI;
- Uvicorn.

Development and validation dependencies are available through the `test` and
`dev` extras: pytest, HTTPX, Ruff, and Build.

System build prerequisites used by the full native setup are Git, Make, a C/C++
compiler, CMake, `pkg-config`, Autoconf, Automake, Libtool, GMP, MPFR, and FLINT
development files. On macOS, Homebrew's `glibtoolize` supplies the Libtool
command expected by the source builds.

Optional native engines are YAFU, Msieve, GMP-ECM, CADO-NFS, PARI/GP,
primesieve, primecount, and the FLINT-backed Numerisect zeta helper. Most Prime
Tools require PARI/GP; 64-bit interval sieving and large exact counting use
primesieve and primecount. Zeta Tools require FLINT/Arb and the compiled helper.
Factorization backends require their corresponding executable. Missing
optional engines do not prevent the browser shell from starting.

## Run from a source checkout

```bash
git clone https://github.com/reza-ghazi/Numerisect.git
cd Numerisect
python3 -m venv .venv
.venv/bin/pip install -e '.[test,dev]'
./run.sh
```

The browser opens `http://127.0.0.1:8765/`. The service binds to loopback only.
The browser UI depends on this local FastAPI process and is not a standalone
static site. Calculations, SQLite job state, engine logs, and `output/` reports
remain local unless the user deliberately shares them.

## Install a versioned user-local copy

From the cloned repository:

```bash
./install.sh
```

The script resolves its own directory, so absolute and relative invocations
also work when the current directory is elsewhere. It validates the version,
operating system, architecture, Python, build commands, and native development
libraries. If system packages are missing, it displays the package manager,
the exact package list, and whether administrative access is needed, then asks
for confirmation.

On Linux and WSL, confirmed dependency installation may execute `sudo dnf
install`, `sudo apt-get update` followed by `sudo apt-get install`, or `sudo
pacman -Sy --needed`. On macOS it may execute `brew install` without `sudo`.
The script never runs a general system upgrade command and does not silently
upgrade pip.

Useful options:

```bash
./install.sh --check
./install.sh --no-system-deps
./install.sh --yes
./install.sh --prefix "$HOME/.local/share/numerisect"
./install.sh --force
```

`--check` is read-only. `--no-system-deps` refuses package-manager changes.
`--yes` noninteractively approves only the exact package transaction displayed
by the script and is intended for deliberate automation. `--force` preserves
the existing version directory under a timestamped backup before replacement.
A failed application install retains an `.install-incomplete` marker and never
updates the stable `current` link or reports success.

The default layout is:

```text
~/.local/share/numerisect/
├── bin/numerisect
├── current -> releases/0.6.0
├── releases/0.6.0/
├── state/
└── output/
```

Add `~/.local/share/numerisect/bin` to `PATH` if desired, then run
`numerisect`. The state and output directories remain shared across versioned
application upgrades.

## Optional native-engine builds

Starting Numerisect never downloads, compiles, or installs an engine. It only
reports availability. When engines are missing, the browser displays a review
button and names the affected components. Installation begins only after the
user accepts a confirmation warning that the operation can require substantial
time, CPU, network bandwidth, and disk space.

Approved engine installation clones exact commits into `state/tools/src`,
verifies those commits, compiles locally, and installs under `state/tools`.
Pins, upstream URLs, licenses, interaction types, and platform notes are stored
in `numerisect/engine_manifest.toml`; no mutable latest-release selection is
used. The current implementation uses Git rather than source archives, so no
archive checksum applies. Third-party sources are not committed to this
repository.

The reviewed 0.6.0 manifest pins primesieve 12.15 and primecount 8.5 in
addition to the existing engines. `primecount` is built against the managed
primesieve development tree so a system executable without development files
cannot produce a mismatched build.

To review a proposed upstream pin without modifying the manifest:

```bash
python scripts/update_engine_pins.py --engine YAFU --ref refs/tags/v3.1.9
```

After reviewing the upstream ref and license, rerun with `--write`, inspect the
manifest diff, update `THIRD_PARTY_LICENSES.md`, and validate a clean build.

## Failures and diagnostics

The setup banner reports the component that failed and keeps detailed commands
in the local state log. Full installation logs and executable paths are not
returned by ordinary API status responses. Resolve the named prerequisite or
engine build failure, restart Numerisect, and retry explicitly from the banner.

The **System diagnostics** workspace (`/#diagnostics`) creates a sanitized
local readiness report containing engine status, pinned revision prefixes,
licenses, build-command availability, CPU count, reported memory, and CADO
parameter sizes. It deliberately excludes hostnames, usernames, network
addresses, absolute paths, job inputs, and results. The exact
`output/diagnostics-<id>.txt` path is shown before the user chooses whether to
share it.

See [the localhost security model](SECURITY_MODEL.md) for API authentication
and safe command-line access. See
[third-party licenses](https://github.com/reza-ghazi/Numerisect/blob/main/THIRD_PARTY_LICENSES.md) before redistributing any
built native component.
