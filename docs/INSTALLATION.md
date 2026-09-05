# Installation and versioning

Numerisect is currently a private, pre-release source project. It has no public
release package or packaging workflow. `install.sh` installs a checked-out
version into a user-owned directory and does not change repository visibility.

## Supported hosts

The installer and application support:

| Host | Native toolchain | Package manager |
| --- | --- | --- |
| Linux | GCC/Clang, Make, CMake | `dnf`, `apt-get`, or `pacman` |
| Windows WSL | Linux toolchain inside the WSL distribution | `apt-get` (Ubuntu/Debian) or the distribution manager |
| macOS | Apple Clang, Make, CMake | Homebrew |

Windows WSL is the supported Windows path. Run the installer inside WSL and
keep the checkout on the WSL filesystem, such as `~/src/Numerisect`, for better
build and filesystem performance. The engines are native programs for the WSL
Linux environment; they are not Windows `.exe` builds.

macOS support requires Homebrew and a supported Python 3.11 or newer. Homebrew
provides `glibtoolize` in its `libtool` formula; the installer recognizes that
name. The browser is opened with macOS `open`; Linux and WSL use `xdg-open` when
available. Set `NUMERISECT_NO_BROWSER=1` to suppress automatic browser launch.

## Install from the source checkout

From the repository directory:

```bash
./install.sh
```

The installer reads the authoritative application version from
`pyproject.toml`, checks that Python 3.11+, Git, Make, a C/C++ compiler, CMake,
pkg-config, Autoconf, Automake, Libtool, GMP, MPFR, and FLINT are available,
and attempts to install missing system packages through the detected package
manager (using `sudo` on Linux/WSL when needed). It then:

1. creates `~/.local/share/numerisect/releases/<version>`;
2. copies the application, native sources, static interface, and documentation;
3. creates a release-specific `.venv` and installs FastAPI and Uvicorn from the
   copied `pyproject.toml`;
4. writes `VERSION` and `INSTALLATION.txt` metadata;
5. points `~/.local/share/numerisect/current` at that release; and
6. creates `~/.local/share/numerisect/bin/numerisect` as the stable launcher.

The shared state and output directories are outside release directories:

```text
~/.local/share/numerisect/state
~/.local/share/numerisect/output
```

This preserves jobs, engine sources, logs, and reports across application
updates. Add the launcher directory to the shell path if desired:

```bash
export PATH="$HOME/.local/share/numerisect/bin:$PATH"
numerisect
```

The first application start still checks for YAFU, Msieve, GMP-ECM, CADO-NFS,
PARI/GP, and the FLINT/Arb zeta helper. Missing engines are fetched, compiled,
and installed under the shared `state/tools` directory without root access.

## Options

```bash
./install.sh --prefix "$HOME/.local/share/numerisect"
./install.sh --check
./install.sh --no-system-deps
./install.sh --force
```

`--prefix` chooses another user-writable installation root. `--check` performs
version and prerequisite checks without copying files. `--no-system-deps`
disables package-manager commands and fails if required commands or libraries
remain absent. `--force` moves an existing same-version release to a timestamped
backup before installing the new copy; it never removes that backup.

The installer requires a package manager only when prerequisites are missing.
On Debian/Ubuntu WSL it may invoke `sudo apt-get`; on Fedora it may invoke
`sudo dnf`; on Arch it may invoke `sudo pacman`; on macOS it invokes Homebrew.
Review the package-manager prompt and use `--no-system-deps` if dependencies
are managed by an organization or container image.

## Upgrading

Increment `version` in `pyproject.toml` and keep `numerisect/__init__.py` in
sync before making a release commit. Run `./install.sh` again. A new version
gets its own release directory and `current` switches to it atomically; the
shared state and output remain in place. Reinstalling the same version requires
`--force`.

Before publishing any future package, verify the version with:

```bash
./install.sh --check --no-system-deps
python3 -c 'import numerisect; print(numerisect.__version__)'
```

## Troubleshooting

If system packages cannot be installed, run `./install.sh --check --no-system-deps`
to see the missing command or library. Install the corresponding development
packages for the host, then rerun the installer. If an engine fails during
first start, inspect `state/engine-setup.log` and use the setup banner or
`POST /api/setup/install` to retry. Installation does not overwrite existing
system engine commands; Numerisect prefers its managed `state/tools/bin`
directory for its own processes.
