# Changelog

Numerisect is an experimental, source-distributed pre-release. No official
binary packages are published.

## Unreleased

- Added strict loopback Host validation, foreign-origin rejection, Fetch
  Metadata checks, and a cryptographically random per-process API session.
- Removed automatic native-engine installation from application startup and
  added explicit browser confirmation for pinned source builds.
- Added an immutable native-engine manifest, deliberate pin-update command,
  sanitized API status/job responses, and safer source-install confirmation.
- Made static assets, GP programs, the engine manifest, and the native zeta
  source wheel resources independent of the original checkout.
- Added public project metadata, third-party notices, community/security files,
  and SHA-pinned GitHub Actions quality checks.

## 0.3.0 — 2026-09-05

- Added a user-space, versioned `install.sh` for Linux, Windows WSL, and macOS.
- Added system prerequisite checks and distro-aware installation for the native
  build toolchain and GMP, MPFR, and FLINT development libraries.
- Added release directories, a shared state/output area, a `current` pointer,
  and a stable user launcher for upgrades.
- Added batch primality checks, arithmetic-progression prime searches, and
  prime-modulus inverses, powers, orders, square roots, and primitive roots.
- Added nth-prime navigation strictly before or after an arbitrary-size integer.
- Added dedicated Prime Tools routes, searchable navigation, mobile selection,
  local result placement, and stale-asset protection.
- Added native FLINT/Arb Riemann-zeta evaluation, zero isolation, Turing counts,
  and exploratory line/heatmap sampling.
- Expanded native-engine, API, report, UI, and installation regression coverage.

## 0.2.0

- Initial Numerisect development baseline with multi-engine
  factorization, PARI/GP prime tools, and the source-based application shell.
