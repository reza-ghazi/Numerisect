# Changelog

Numerisect is an experimental, source-distributed pre-release. No official
binary packages are published.

## Unreleased

- Gave every documented endpoint a purpose. The API reference listed 208 routes and left
  151 of them with a blank Purpose column, so the table named routes without saying what
  any of them did. Each one now carries a description, and for the 134 routes with a
  matching page in the application the text is taken from that page's own heading and
  subtitle, so the reference and the interface cannot drift apart in wording.
- Fixed a broken row in the API reference. The `l-zeros` entry contained an unescaped
  `|L|`, which split the row into extra columns and rendered as a malformed table.
- Added contract tests asserting that no documented endpoint has a blank purpose, that no
  table row contains an unescaped pipe, and that the reference uses the same names the
  interface shows.

- Corrected the three places in the documentation that still named a renamed tool page:
  the reciprocals guide called the full-reptend page by its old heading, and two rows of
  the zeta routine table used operation names the interface no longer shows.

- Renamed 33 tool headings so the navigation shows what each tool is called, not only
  what it does. The sidebar button and the tool picker both display a tool's heading, and
  headings such as "Solve x² − dy² = 1", "Analyze witness bases" and "Apply Korselt's
  criterion" never mentioned Pell, Miller–Rabin or Carmichael, so scanning the list for a
  known name found nothing. The names were present only in the small eyebrow text inside
  each card, visible after the tool was already open. Affected, among others: Pell,
  continued fractions, Miller–Rabin, Goldbach, Carmichael, Hardy–Littlewood, Bateman–Horn,
  Maier, Pocklington, Proth, Sierpiński and Riesel, Chebotarev, Eisenstein, Dirichlet,
  Dedekind, the Chinese remainder theorem and SQUFOF.
- Gave the two prime-race tools distinct names. The animated and the analytic tool both
  read "Race the reduced residue classes", so they were indistinguishable in the sidebar
  and in the picker.
- Added contract tests asserting that every navigation label is unique and that the
  recognised name of each subject appears in some label.

- Stopped labelling a rational's continued-fraction expansion "inconclusive" in the
  exported report. A rational expansion terminates, so it has no period; calling that
  inconclusive confuses "not applicable" with "not settled". The export now says which
  it is, and reserves "inconclusive" for a quadratic irrational whose period was not
  closed within the quotient cap.

- Removed the length ceiling from the Pell solver and the continued-fraction expander.
  Both quantities grow without bound — the fundamental Pell solution for `d = 1000099`
  has 1,128 decimal digits and its fourth solution has 4,513, and convergent denominators
  grow at least as fast as the Fibonacci numbers — and the Pell tool used to stop listing
  at the first solution wider than the digit limit, which made a complete answer look like
  an exhausted search. Every requested solution and convergent is now reported. PARI/GP
  writes each one at full length to its own export file, named in the response as
  `export_file`, and the JSON response carries a preview in which a long value is rendered
  as its exact first twelve digits, its exact last twelve digits and its exact digit count.
  A new `abbreviated` flag says whether any value was shortened for display; `truncated`
  now means only what it says, that something was left out, and is no longer set by these
  tools. Tests substitute every exported Pell pair back into `x² − dy² = 1` and every
  exported convergent of `√2` into `pₙ² − 2qₙ² = ±1`, and check the abbreviation against
  the exported value at both ends.
- Filled in the missing endpoint descriptions for the quadratic-forms section of the API
  reference, which shipped with an empty Purpose column for all eight routes.

- Pointed the declared homepage at the documentation site. `pyproject.toml` and
  `CITATION.cff` both advertised `https://numerisect.com`, which serves a 404 from an
  unrelated document root, so the package metadata and the citation record sent readers
  to a dead page. The apex is not part of the project's hosting.

- Fixed every Material icon on the documentation site, which rendered as literal text
  such as `:octicons-arrow-right-24: Installation` on all 35 occurrences across 15 pages.
  Material's icon shortcodes are emoji shortcodes underneath, and `pymdownx.emoji` was
  never configured, so the theme silently passed them through. The strict build did not
  catch it because unrecognised shortcodes are valid Markdown text.
- Added a source-code section to the documentation home page linking the repository,
  releases, issue tracker, contributing guide and citation file, so a reader arriving at
  the site can find the source and report a wrong result without hunting for it.

- Published a documentation site at [docs.numerisect.com](https://docs.numerisect.com),
  built with MkDocs Material from the existing `docs/` tree so there is one source of
  truth rather than a parallel copy. It adds a mathematical background section covering
  primality, factorization, prime distribution, modular arithmetic, quadratic forms and
  the zeta function, each naming the library routine that performs every computation and
  citing sources for every stated bound. Also adds concept pages on result strength and
  the engines, a getting-started path, an API reference generated from the running
  application, a glossary, a bibliography and an FAQ. The site carries no analytics, and
  a test asserts that it stays that way.
- Corrected the prime-counting comparison, which counted `primecount --double-check` as
  an independent source. It reruns the default algorithm with different alpha tuning, so
  it is a self-consistency check rather than a seventh implementation, and it is now
  reported separately so the independence claim is not inflated.
- Corrected `docs/FACTORIZATION.md`, which still said SQUFOF was "not offered" and listed
  resumable ECM campaigns, expert scheduling, symbolic SNFS and Aurifeuillean analysis and
  distributed workers as deferred. All of those ship.
- Documented that PARI's `primecertexport` cannot render an N−1 certificate, and added a
  test asserting no export path passes it one.
- Granted the secret-scan workflow `pull-requests: read`. Gitleaks enumerates a pull
  request's commits, so without it the scan failed with "Resource not accessible by
  integration" on every pull request, including Dependabot's.

- Recorded the work that goes beyond the 150-item proposal in
  `docs/ROADMAP_STATUS.md`, and refreshed the page, group and test counts across the
  README and the documentation pages so they match the application.
- Added a prime-counting algorithm comparison. `POST /api/counting/algorithm-comparison`
  runs primecount's six algorithms, its alternative-tuning double-check, and PARI's
  `primepi` as independent sources and reports whether they agree. Added Legendre's
  phi(x,a) with the identity check, the two nth-prime inverse approximations, the integer
  predicates `isprimepower`, `ispowerful`, `istotient`, `isfundamental` and `ispolygonal`,
  Lenstra's divisors-in-a-residue-class with its hypotheses enforced, and PARI's
  `factorint` strategy flags as a factoring-method comparison.
- Added a binary quadratic forms and continued fractions workbench: reduction,
  composition and exponentiation of forms, prime forms, class groups and reduced-form
  enumeration, representation of integers, the exact continued-fraction expansion of
  quadratic irrationals with period detection, and Pell equations. Documents the concrete
  link to SQUFOF: discriminant 7268 gives a 28-form principal cycle containing the
  ambiguous form Qfb(23, 46, -56), and 23 divides 1817.
- Added independent cross-engine verification. `POST /api/verify/prime-count` computes
  pi(x) with primecount's six algorithms (Legendre, Meissel, Lehmer, Lagarias-Miller-
  Odlyzko, Deleglise-Rivat, Gourdon), primesieve's sieve and PARI's `primepi`, then
  reports whether they agree. `POST /api/verify/primality` does the same with PARI's
  proof, PARI's Baillie-PSW test and GMP's independent implementation. On disagreement
  Numerisect reports every value and refuses to choose, because a majority of
  implementations sharing a bug is exactly what a vote would hide.
- Added an engine self-test. `POST /api/verify/self-test` asks each installed engine
  questions whose answers are published constants, so a miscompiled or mismatched build
  shows up before its output is trusted. Every expected value carries a citation.
- Added `numerisect-bigsieve`, a GMP and OpenMP segmented sieve for intervals of any
  magnitude. primesieve refuses inputs at or above 2^64 and PARI's `forprime` is
  single-threaded there; over a 10^6-wide window near 10^30 this helper takes 40 ms on
  24 threads against PARI's 916 ms on one, and both find 14496 primes. Results at or
  above 2^64 are labelled probable primes from Baillie-PSW, never proofs.

- Added distributed CADO-NFS sieving (roadmap item 18). Numerisect validates CADO's own
  server and client parameters and adds no networking of its own. Configurations CADO
  would accept but that are unsafe are refused: an absent whitelist, `0.0.0.0/0`, broad
  public ranges, binding a public interface, and remote workers without a script path.
  A two-step approval reports the exposure before anything starts, and a run that leaves
  the machine additionally requires `NUMERISECT_ALLOW_NETWORK=1`. `docs/DISTRIBUTED.md`
  states the trust model verified from CADO's own source: clients do not authenticate to
  its work-unit server, and an IP whitelist is the only access control.
- Fixed a bug that made every CADO-NFS job hang. CADO defaults `slaves.hostnames` to
  `localhost` only when using its own default parameter file; Numerisect always passes
  `-p`, so CADO started a bare work-unit server, queued work units and polled for them
  forever with no client running. Both the plain and distributed paths now set it, and
  the integer is kept contiguous with its `key=value` assignments as CADO requires.
  Found by running a distributed factorization by hand.

## 0.5.0 — 2026-09-07

- Stated the governing development policy: Numerisect is a user interface over existing
  number-theory libraries. A computation uses a library routine first, an optimized C or
  C++ program with GMP/FLINT only when no library provides one, and never Python or
  JavaScript. Added `tests/test_native_computation_policy.py` so the policy is enforced
  by the suite rather than by review, and documented it in `CONTRIBUTING.md`.
- Added `numerisect-squfof`, an optimized C implementation of Shanks' square forms
  factorization using GMP. No installed library provides SQUFOF: the YAFU build has no
  such function, PARI/GP exposes none, Msieve implements only QS/NFS, and GMP-ECM only
  ECM/P-1/P+1. Verified against 150 random semiprimes with no incorrect answers; inputs
  at or above 2^62 are rejected explicitly and an exhausted search is inconclusive.
- Added the expert factorization laboratory: SQUFOF, special-form and SNFS suitability
  analysis, algebraic and Aurifeuillean factors verified by division, a strategy adviser
  with an expected-factor-size estimate, an engine decision path, bounded educational
  algorithm traces, and batch primality certificates.
- Added a resumable GMP-ECM campaign manager using the engine's own save and resume
  residue files, with PARI/GP reconciling the factors GMP-ECM peels off across curves
  into a consistent decomposition.
- Added the primality laboratory: a comparison lab across Fermat, Solovay-Strassen,
  Miller-Rabin, Lucas, Frobenius, BPSW, APR-CL and ECPP; deterministic Miller-Rabin
  witness sets; Pocklington and Pratt certificates with independent verification; the
  probable-prime taxonomy; the Carmichael analyzer; Sierpinski and Riesel covering sets;
  bi-twin chains; and provable constrained-prime generation.
- Added the algebra laboratory: reciprocity traces, congruences over composite moduli,
  four selectable discrete-logarithm algorithms, finite fields, divisor lattices,
  smoothness and roughness, record-number families, a proven weird-number check,
  sociable cycles, Cornacchia with a step trace, quadratic rings, general number fields
  with prime-ideal decomposition, and Chebotarev density experiments.
- Added the visualization and education workbench: Ulam, Sacks and polar spirals, the
  Eisenstein hexagonal lattice, arbitrary-base modular wheels, residue heatmaps, gap and
  record-gap timelines, the prime-race animation, step-traced Eratosthenes, segmented
  Eratosthenes, Sundaram and Atkin sieves, and a cited complexity dashboard.
- Added application infrastructure: complete command-line parity through an in-process
  ASGI caller, CSV/JSON/JSON Lines/Markdown/LaTeX/PARI exports, file-based batch import
  with GP-side expansion, saved workspaces, searchable job and report history,
  revision-keyed result caching, job priorities and reordering, per-job CPU, memory and
  wall-clock limits, pause and resume, opt-in desktop notifications, declarative engine
  adapters, a performance-history dashboard, API clients for five languages, and a
  standard-library client for notebooks.
- Added permissioned catalogue lookups (OEIS and local known-factor tables) that are off
  by default and require both `NUMERISECT_ALLOW_NETWORK=1` and a per-request
  confirmation. Only the query is transmitted, and every claimed factor is verified by
  PARI/GP before being reported as a divisor.
- Fixed the wheel smoke test, which asserted six pinned engines after primesieve and
  primecount brought the manifest to eight.
- Added the analytic prime-distribution laboratory: approximation-error and
  prime-number-theorem convergence charts, cited nth-prime bounds, prime races and
  Chebyshev bias, progressions with expected-versus-observed counts, Hardy-Littlewood
  singular series with a rigorous tail bound, constellation predictions,
  Bateman-Horn estimates, maximal-gap search with merit and Cramer, Granville and
  Firoozbakht comparisons verified against the published table, Maier-matrix
  experiments, and a two-parameter density surface.
- Extended the zeta workspace with explicit-formula prime counting from certified
  zeros, Chebyshev psi reconstruction, Riemann-Siegel remainder analysis, Euler-product
  comparison, zero-spacing histograms, pair correlation against the GUE prediction,
  Gram blocks and Gram's-law exceptions, the Backlund S(T) remainder, Dirichlet
  characters and L-functions with independent Hurwitz cross-checks, L-function zeros
  for GRH experiments, and Dedekind zeta functions through PARI.
- Corrected the Prime Tools group count in the README and prime-manipulation guide, the
  README route list, and the stale test count in the prime-manipulation guide.
- Added engine tuning through YAFU's own `tune`: `POST /api/factor-lab/tune` measures
  this machine's SIQS/NFS crossover and reports a suggested `NUMERISECT_CADO_THRESHOLD`.
  Numerisect never rewrites its own configuration. Needs `NUMERISECT_GGNFS_DIR` to point
  at the GGNFS lattice sievers.
- Recorded two declined items in `docs/ROADMAP_STATUS.md` rather than leaving them as
  open gaps: synthetic engine benchmarking, superseded by the performance history built
  from real jobs, and the side-by-side engine timing view, whose correctness half is
  already covered by cross-verification.
- Bumped the interface asset tag to `20260907-libraries-first`.

## 0.4.0 — 2026-09-06

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
- Added factor-tree visualization, partial-cofactor continuation, validated
  batch queues, independent YAFU/Msieve verification, and bounded PARI trial
  division in place of YAFU's crashing trial command.
- Added JSON factorization manifests containing factor provenance, full command
  history, parameters, immutable engine revisions, and executable SHA-256 sums.
- Added pinned primesieve 12.15 and primecount 8.5 integrations for parallel
  interval sieving, exact prime counting, indexed primes, and asymptotic
  comparisons.
- Added independent PARI certificate verification and a native primality
  comparison laboratory.
- Added special-family and NTT prime generation, Cunningham chains,
  Lucas–Lehmer and Pépin tests, perfect-power and factor-strategy analysis.
- Added generalized CRT, character symbols, Tonelli–Shanks traces, modular kth
  roots, Hensel lifting, discrete logs, unit groups, order/power-residue
  distributions, p-adic valuation, and polynomial/cyclotomic factorization.
- Added extended arithmetic and divisor classifications, aliquot sequences,
  summatory functions, Eisenstein primes, and quadratic prime-ideal
  decomposition.
- Extended the compiled FLINT/Arb helper with Hardy Z, xi, eta, Stieltjes,
  Gram-point, and rigorous functional-equation operations.
- Expanded the workstation to 65 individually routed Prime Tools pages and 10
  Zeta pages, plus a sanitized local diagnostics workspace.
- Added a cache-busted Numerisect `N` favicon to prevent stale generic branding.
- Added the `numerisect` CLI and bumped the pre-release version to 0.4.0.

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
