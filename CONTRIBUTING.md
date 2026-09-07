# Contributing to Numerisect

Numerisect is an experimental computational-number-theory application. Small,
reviewable changes with tests and precise mathematical claims are preferred.

## Development setup

```bash
git clone https://github.com/reza-ghazi/Numerisect.git
cd Numerisect
python3 -m venv .venv
.venv/bin/pip install -e '.[test,dev]'
```

PARI/GP and FLINT development files are required by the full native integration
suite. primesieve and primecount exercise the high-performance range/count
paths when installed. The heavyweight factorization engines are not required for ordinary CI.
See [the installation guide](docs/INSTALLATION.md) for system prerequisites.

## Checks

Run these before opening a pull request:

```bash
python -m pytest -q
ruff check .
mypy
shellcheck install.sh run.sh
node --check numerisect/static/app.js
python -m build
```

State which checks ran locally and which native prerequisites were present. Do
not say GitHub Actions passed until the workflow has completed on GitHub.

## Workflow and conventions

1. Open an issue for substantial features or architecture changes.
2. Create a focused branch and keep unrelated edits out of the change.
3. Add tests for success, invalid input, native-engine failure, cancellation,
   resource limits, and arbitrary-precision behavior where applicable.
4. Add type annotations and Google-style docstrings to new or modified public
   Python APIs.
5. Follow the native-computation policy below. It is the governing rule of this
   project and `tests/test_native_computation_policy.py` enforces it.
6. Update documentation and `CHANGELOG.md` when behavior changes.
7. Register each new Prime Tools form exactly once in `primeSections`, keep its
   hash route unique, and preserve the explicit saved `output/<filename>` notice.

Formatting and imports are enforced by Ruff. Shell scripts must pass
ShellCheck. JavaScript should remain dependency-light and must not duplicate
native mathematical algorithms. Strict mypy checking currently covers the
localhost security boundary. Extending the strict baseline across the older
orchestration modules remains follow-up work and should be done incrementally
with real annotations rather than broad ignores.

## Native-computation policy

Numerisect is a well-designed user interface over existing number-theory libraries. It
gathers, in one place, almost every operation concerning prime numbers and integer
factorization. It is not a place to reimplement mathematics a mature library provides.

Decide every feature in this order, without skipping or stopping early:

1. **Use an existing library routine.** Search the installed engines first: PARI/GP for
   number theory, FLINT/Arb for analytic and ball arithmetic, YAFU, Msieve, CADO-NFS and
   GMP-ECM for factoring, primesieve for enumeration, primecount for counting. Prefer the
   routine the library authors optimized over anything hand-written, and check the
   documentation and installed headers before concluding one is missing.
2. **Only if no library provides it, write an optimized C or C++ program** using GMP,
   FLINT/Arb and appropriate HPC facilities, exposed through a narrow subprocess
   boundary. This is the fallback, not the default. `numerisect/native/numerisect_squfof.c`
   is the worked example: SQUFOF is absent from every installed engine, and the file
   documents that before implementing it.
3. **Python and JavaScript are interface, API, and orchestration only.** Python
   validates input, launches engines, parses tagged output, persists results, and serves
   HTTP. JavaScript renders. Neither computes a mathematical result, ever.

A PARI/GP script drives a library rather than replacing one. It is the right tool for a
short composition of PARI routines, and for features that deliberately expose an
algorithm's individual steps (comparison laboratories, certificate trees, algorithm
traces). It is the wrong tool when it reimplements a routine the library already exposes,
or when it becomes a performance-critical inner loop; escalate those to step 2.

Violations include arithmetic on mathematical quantities in Python or JavaScript
(divisibility, primality, gcd, factoring, modular exponentiation, series summation, prime
counting), reimplementing in GP script what the library exposes as a routine, and
silently substituting a Python or JavaScript fallback when an engine is missing.
Formatting, sorting, bookkeeping and request bounds checking are not violations. If the
engines cannot deliver a requested feature, report the gap explicitly rather than
approximating it.

Every new mathematical module must name, in its docstring and its `docs/*.md` page, the
library routine or C program that performs the computation.

## Adding or updating an engine

Do not add mutable branches, dynamically selected latest releases, binary
downloads without SHA-256 verification, or vendored third-party source.
Resolve an official upstream ref deliberately:

```bash
python scripts/update_engine_pins.py --engine YAFU --ref refs/tags/v3.1.9
```

Review the displayed revision, upstream license, build instructions, platform
support, and dependency changes. Then rerun with `--write`, update
`THIRD_PARTY_LICENSES.md`, and test a clean user-local build. A reviewer must
inspect the manifest diff before merge.

## Licensing

Contributions are accepted under `GPL-3.0-or-later`, the project license. Only
submit work you have the right to contribute. Identify copied or adapted code
and its license; do not add incompatible or unclear third-party material.

## Commit identity and privacy

Git commit author names and email addresses are permanent repository metadata
and become visible when a repository is public. Contributors who prefer not to
publish a personal address should enable GitHub's email-privacy option and
configure Git with their GitHub-provided `users.noreply.github.com` address
before creating commits. Never rewrite shared history or force-push solely to
change commit identity without coordinating with the maintainer.
