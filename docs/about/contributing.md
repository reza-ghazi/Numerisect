# Contributing

Numerisect accepts small, reviewable changes with tests and precise mathematical claims.

## Setup

```bash
git clone https://github.com/reza-ghazi/Numerisect.git
cd Numerisect
python3 -m venv .venv
.venv/bin/pip install -e '.[test,dev]'
```

## Checks before a pull request

```bash
python -m pytest -q
ruff check .
mypy
shellcheck install.sh run.sh
node --check numerisect/static/app.js
python -m build
```

State which checks you ran locally and which native prerequisites were present. Do not
say GitHub Actions passed until the workflow has actually completed.

## The governing rule

Numerisect is a user interface over existing number-theory libraries. Decide every
feature in this order, without skipping:

1. **Use an existing library routine.** Search PARI/GP, FLINT/Arb, YAFU, Msieve,
   CADO-NFS, GMP-ECM, primesieve and primecount first, and prefer the routine the library
   authors optimized. Check the documentation and installed headers before concluding one
   is missing.
2. **Only if no library provides it, write optimized C or C++** using GMP and FLINT,
   behind a narrow subprocess boundary. This is the fallback, not the default.
3. **Python and JavaScript are interface, API and orchestration only.** Neither computes
   a mathematical result, ever.

`tests/test_native_computation_policy.py` enforces this. A PARI/GP script drives a
library rather than replacing one, and is the right tool for a short composition of PARI
routines or for a feature that deliberately exposes an algorithm's individual steps. It
is the wrong tool when it reimplements a routine PARI already exposes, or when it becomes
a performance-critical inner loop.

Every new mathematical module must name, in its docstring and its documentation page, the
routine that performs the computation.

## What a change should include

- Tests for success, invalid input, engine failure, cancellation or resource limits, and
  arbitrary-precision behaviour where applicable.
- A documentation update on the matching page.
- A `CHANGELOG.md` entry when behaviour changes.
- Type annotations and Google-style docstrings on new public Python.

## Adding or updating an engine

Do not add mutable branches, dynamically selected releases, binary downloads without
SHA-256 verification, or vendored third-party source. Resolve an official upstream ref
deliberately:

```bash
python scripts/update_engine_pins.py --engine YAFU --ref refs/tags/v3.1.9
```

Review the revision, licence, build instructions and dependency changes, then rerun with
`--write`, update `THIRD_PARTY_LICENSES.md`, and test a clean user-local build. A
reviewer must inspect the manifest diff before merge.

## Licensing

Contributions are accepted under GPL-3.0-or-later. Submit only work you have the right to
contribute, identify copied or adapted code and its licence, and do not add incompatible
or unclear third-party material.

[:octicons-arrow-right-24: Full contributing guide](https://github.com/reza-ghazi/Numerisect/blob/main/CONTRIBUTING.md)
