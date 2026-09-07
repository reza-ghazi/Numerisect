# Installation

Numerisect is source-distributed. There are no official binary packages.

!!! info "Verified platform"

    Exercised on Fedora Linux x86-64. Windows WSL and macOS paths are implemented and
    expected to work but have not been verified by the project.

## Prerequisites

| Requirement | Needed for |
|---|---|
| Python 3.11 or newer | The application itself |
| PARI/GP | Almost every mathematical operation |
| FLINT development files | The zeta and L-function tools |
| GMP, MPFR, a C compiler, pkg-config | Building the compiled helpers |
| Git, Make, CMake, Autoconf, Automake, Libtool | Building optional engines from source |

The heavy factoring engines (YAFU, Msieve, GMP-ECM, CADO-NFS) and the counting engines
(primesieve, primecount) are optional. Features that need a missing engine say so.

## Quick start from source

```bash
git clone https://github.com/reza-ghazi/Numerisect.git
cd Numerisect
python3 -m venv .venv
.venv/bin/pip install -e '.[test,dev]'
./run.sh
```

`run.sh` prints the directories it is serving and opens a browser at
<http://127.0.0.1:8765>. Set `NUMERISECT_NO_BROWSER=1` to skip that.

Keep the terminal open while you use it. Press ++ctrl+c++ there to stop. If it was
started elsewhere, stop only its process:

```bash
pgrep -af 'uvicorn numerisect.main:app'
kill PID_FROM_THE_PREVIOUS_COMMAND
```

## User-local install

To install a versioned copy outside the checkout:

```bash
./install.sh
```

Before any system-package command the helper shows you the package manager, the exact
packages and the administrative-access requirement, then asks for confirmation. It
creates a release-specific virtual environment and a stable launcher at
`~/.local/share/numerisect/bin/numerisect`.

Check prerequisites without installing anything:

```bash
./install.sh --check --no-system-deps
```

[:octicons-arrow-right-24: Prefixes, upgrades and troubleshooting](../INSTALLATION.md)

## Optional engines

At startup Numerisect checks for these commands:

```text
yafu  msieve  ecm  cado-nfs.py  gp  numerisect-zeta  primesieve  primecount
```

If any are missing the interface offers to build them. **Nothing is downloaded or
compiled until you confirm.** An approved build clones the exact commits recorded in
`numerisect/engine_manifest.toml`, verifies the checked-out revisions, and installs under
your state directory without requesting root.

Builds can take substantial time, CPU, bandwidth and disk. Progress appears in the setup
banner; detailed output goes to `data/engine-setup.log`.

## Compiled helpers

Three C programs are built on demand and rebuilt automatically whenever their source is
newer than the binary, so editing the C and reloading picks up the change:

- `numerisect-zeta` needs FLINT development files.
- `numerisect-squfof` needs GMP.
- `numerisect-bigsieve` needs GMP and, for parallelism, OpenMP.

Build failures write a log to your state directory naming the problem.

## Verify the installation

Once it is running, ask the engines to prove themselves:

```bash
numerisect --json api post /api/verify/self-test --data '{}'
```

Each installed engine is asked questions whose answers are published constants. A failure
here means an engine build is wrong, and you should not trust its output until you know
why.

[:octicons-arrow-right-24: First steps](first-steps.md)
