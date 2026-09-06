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
suite. The heavyweight factorization engines are not required for ordinary CI.
See [the installation guide](docs/INSTALLATION.md) for system prerequisites.

## Checks

Run these before opening a pull request:

```bash
pytest -q
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
5. Keep Python and JavaScript as validation, orchestration, persistence, and UI
   layers. Computationally intensive mathematics belongs in a proven native
   engine or optimized C/C++ using GMP/FLINT and appropriate HPC facilities.
6. Update documentation and `CHANGELOG.md` when behavior changes.

Formatting and imports are enforced by Ruff. Shell scripts must pass
ShellCheck. JavaScript should remain dependency-light and must not duplicate
native mathematical algorithms. Strict mypy checking currently covers the
localhost security boundary. Extending the strict baseline across the older
orchestration modules remains follow-up work and should be done incrementally
with real annotations rather than broad ignores.

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
