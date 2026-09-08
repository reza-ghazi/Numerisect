# Numerisect

**Multi-Engine Integer Factorization and Prime Analysis**

Numerisect 0.6.0 is a local web workbench for integer factorization, primality
proofs, prime generation, prime exploration, analytic prime distribution, and rigorous
Riemann-zeta and L-function analysis.

**Numerisect is a user interface over existing number-theory libraries.** PARI/GP,
FLINT/Arb, YAFU, Msieve, GMP-ECM, CADO-NFS, primesieve and primecount perform the
mathematics. Where no library provides a routine, an optimized C program using GMP or
FLINT fills the gap. Python handles validation, process orchestration, persistence and
the HTTP API; plain JavaScript draws the interface. Neither computes a mathematical
result. See [CONTRIBUTING.md](CONTRIBUTING.md) for the policy and
`tests/test_native_computation_policy.py` for its enforcement.

Numerisect is an experimental, source-distributed pre-release. No official
binary packages or binary installers are published. The FastAPI service runs
locally and listens only on loopback by default. Computation, job state, logs,
and results remain on the local machine unless the user deliberately moves or
shares them. The browser interface requires that local backend; it is not a
standalone static website.

**The project website is [numerisect.com](https://numerisect.com), which redirects to
the canonical documentation site at
[docs.numerisect.com](https://docs.numerisect.com).** It includes the mathematical
background for every tool.

For installation status, supported hosts, and prerequisites, see
[Installation and versioning](docs/INSTALLATION.md).
Version history is tracked in [CHANGELOG.md](CHANGELOG.md).

## Highlights

- Automatic YAFU-to-CADO factorization strategy based on decimal length
- Manual bounded PARI trial division plus YAFU rho, p−1, p+1, ECM, SIQS, and NFS strategies
- Factor trees, independently continuable composite cofactors, batch queues, and cross-engine verification
- Automatic CADO parameter discovery and next-larger parameter selection
- CPU-thread selector that defaults to every available logical CPU
- Persistent jobs, live engine logs, cancellation, and CADO snapshot resume
- Product verification before a factorization is marked complete
- Fast probable-prime tests, rigorous proofs, and certificate exports
- Native PARI/GP classification across 56 structural and sequence-based prime classes
- Exact reciprocal periods, full-reptend tests, and decimal repetend exports
- Fixed-length, safe, Sophie Germain, Blum, and modular prime generation
- Multithreaded `primesieve` intervals and `primecount` exact counts/indexed primes
- The nth proven prime strictly before or after an arbitrary-size integer
- Batch primality checks, interval residue-class searches, and exact prime-modulus arithmetic
- 133 individually routed Prime Tools pages in 11 searchable groups with local results
- Absolute/circular, Gaussian, Paterson, full-reptend, and perfect-number tools
- Prime pyramids, corrected pseudoprime searches, and Miller–Rabin witness analysis
- Native prime-gap statistics, primorials, Goldbach partitions, digit-substring primes, and bounded equation searches
- Exact arithmetic-function profiles, semiprime detection, and coprime navigation
- Prime-density/residue charts, digit-constrained primes, exact polynomial exploration, and certified prime-indicator constants
- Rigorous zeta, Hardy Z, xi, eta, functional-equation, Stieltjes, Gram-point, certified-zero, and native-sampled plot tools
- Special-family, Cunningham-chain, NTT-prime, modular-root, p-adic, cyclotomic, aliquot, and algebraic workbenches
- A sanitized system-diagnostics workspace that never uploads data
- Automatic plain-text reports in `output/`
- Reproducible factorization manifests with commands, engine revisions, executable hashes, parameters, and provenance
- Explicit, confirmed user-local builds of missing native engines from pinned commits

## Start and stop

```bash
git clone https://github.com/reza-ghazi/Numerisect.git
cd Numerisect
python3 -m venv .venv
.venv/bin/pip install -e '.[test,dev]'
./run.sh
```

The launcher prints the exact source and interface directories it serves and
opens a versioned URL in the default browser when `xdg-open` is available. It
prefers `.venv/bin/python` when present and explicitly loads this source tree.
Set `NUMERISECT_NO_BROWSER=1`
if you prefer to open it manually. The main routes are Prime Tools at
<http://127.0.0.1:8765/?ui=20260907-named-tools#primes/prime-check>, Riemann Zeta at
<http://127.0.0.1:8765/?ui=20260907-named-tools#zeta>, and diagnostics at
<http://127.0.0.1:8765/?ui=20260907-named-tools#diagnostics>.

After updating the source, restart the server and reload the browser page.
The application shell and assets send `no-store` headers; restarting a server
does not itself replace a document already loaded in a tab. The current layout
uses an `N` brand mark and blue/graphite colors.

Keep the terminal open while using Numerisect. Press `Ctrl+C` in that terminal
to stop it. If it was started from another terminal, find and stop only its PID:

```bash
pgrep -af 'uvicorn numerisect.main:app'
kill PID_FROM_THE_PREVIOUS_COMMAND
```

## User installation

After cloning the source, the provided source-install helper can create a
versioned user-local copy outside the checkout:

```bash
./install.sh
```

The application installer has been exercised on Fedora Linux x86-64. Windows
WSL and macOS paths are implemented and expected to work, but have not yet been
verified by the Numerisect project. Before any system-package command, the
helper displays the package manager, exact packages, and administrative-access
requirement, then asks for confirmation. It creates a release-specific Python
environment and a stable launcher under
`~/.local/share/numerisect/bin/numerisect`. Optional number engines are never
installed merely by starting the application. See
[Installation and versioning](docs/INSTALLATION.md) for prefixes, upgrades,
package-manager behavior, and troubleshooting.

## Python setup

Numerisect requires Python 3.11 or newer, FastAPI, and Uvicorn. To create an
isolated development environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test,dev]'
.venv/bin/uvicorn numerisect.main:app --host 127.0.0.1 --port 8765
```

Python is not used to replace the native factoring or prime engines.

## Native engines

| Engine | Numerisect responsibility |
|---|---|
| YAFU | Default pipeline for small and medium inputs; small-factor, ECM, and SIQS work |
| Msieve | Optional manually selected general factoring pipeline |
| GMP-ECM | Detected and installed as the standalone ECM utility available to native workflows |
| CADO-NFS | Number field sieve for large residual composites |
| PARI/GP | Primality, classification, reciprocal periods, arithmetic functions, coprimes, prime generation/distribution, polynomial and sequence searches, certificates, `prime(n)`, and `primepi(x)` |
| FLINT/Arb | Rigorous complex zeta evaluation, certified Hardy Z zeros, Turing-method zero counting, and multithreaded plot sampling |
| primesieve | Multithreaded, cache-aware prime enumeration over 64-bit intervals |
| primecount | Parallel exact `π(x)` through `10^31`, indexed primes, and Li/Riemann-R comparisons |

The status line at the top of the interface shows which executables are
available. Engine commands are launched as argument arrays rather than through
shell interpolation.

## Optional native-engine installation

At startup, Numerisect only checks for these commands:

```text
yafu  msieve  ecm  cado-nfs.py  gp  numerisect-zeta  primesieve  primecount
```

If any are missing, the interface displays them and offers an installation
button. Nothing is downloaded or compiled until the user reviews a visible
confirmation. An approved task clones the exact Git commits recorded in
[`numerisect/engine_manifest.toml`](numerisect/engine_manifest.toml), verifies
the checked-out revisions, builds them, and installs them under `data/tools/`.
It does not request root access or overwrite an existing system installation.
The managed `bin` and `lib` directories are added to the Numerisect process
environment automatically.

Source builds require network access plus Git, Make, a C/C++ compiler, CMake,
GMP, MPFR, and FLINT development headers, Autoconf, Automake, and Libtool. If
FLINT is unavailable, Numerisect builds the pinned FLINT revision and then its
small OpenMP-enabled zeta helper. Engine builds can consume substantial time,
CPU, network bandwidth, and disk space. Progress appears in
the setup banner. Detailed output is stored in:

```text
data/engine-setup.log
```

If installation fails, install the missing build prerequisite, restart
Numerisect, inspect that local log, and retry from the setup banner. The setup
API is protected by the per-launch browser authorization token and rejects
untrusted hosts and foreign origins.

## Factorization workflow

Enter a decimal integer or a safe integer expression. Supported operators are
`+`, `-`, `*`, `//`, `%`, `^`, and `**`, with parentheses. In number-theory
expressions, `^` is treated as exponentiation. Function calls, names, floating
point operations, and arbitrary Python code are rejected.

The default automatic strategy is:

1. Below 95 decimal digits, run YAFU.
2. At 95 digits and above, run a YAFU small-factor/ECM pretest.
3. If the residual falls below 95 digits, finish it with YAFU/SIQS.
4. Otherwise, send the residual to CADO-NFS.

Direct CADO mode fills gaps in CADO's default parameter lookup. It chooses the
smallest installed parameter set that is at least as large as the input. For
example, a 55-digit input uses `params.c60` when `params.c55` is unavailable.
The advanced selector allows an explicit installed parameter set.

The thread count defaults to all detected logical CPUs. Only one CPU-heavy job
runs at a time unless `NUMERISECT_MAX_PARALLEL_JOBS` is changed. Very large
factorizations may still take hours, days, or substantially longer; thread count
and digit count alone cannot predict completion time.

Each completed factorization receives an equation view, factor tree,
per-factor engine status, text report, and JSON reproducibility manifest.
Unresolved composite factors can be submitted as linked child jobs. A result
is accepted only when every returned factor divides the input and their product
equals it; cross-check mode additionally requires identical YAFU and Msieve
factor multisets.

## Prime Tools

Prime operations use PARI/GP by default, with `primesieve` for eligible 64-bit
intervals and `primecount` for large exact counts and indexed-prime requests.

Prime Tools has 133 pages with searchable navigation in 11 groups. Every
operation has its own page and direct hash URL, such as
`#primes/prime-check`, `#primes/prime-reciprocal`, or
`#primes/integer-profile`; only the selected operation is displayed. On narrow
screens, a compact operation selector replaces the navigation sidebar.
Results, errors, the automatic `output/<filename>` confirmation, and the
report-download control appear immediately below the operation that produced
them.

### Primality modes

- **Rigorous:** uses `isprime`; a positive result is a mathematical proof.
- **Fast:** uses the BPSW-based `ispseudoprime`; a positive result is labeled
  “probable prime,” not proven prime.
- **Certificate:** rigorous mode can export a human-readable PARI
  primality/ECPP certificate with the result.

PARI candidate generators and iterators may provide pseudoprimes above `2^64`.
Numerisect explicitly applies `isprime` before reporting generated, ranged,
navigated, or tuple members as proven primes.

### Nth prime before or after an integer

Open **Prime Tools → Primality & navigation → Primes near a number**
(`/#primes/prime-nearby`). Choose **Find the nth prime**, the direction, the
starting integer or expression, and position n. For example, the 100th prime
strictly after 1289 is **2039**, and the 50th prime strictly before 98798 is
**98221**. The input itself is always excluded, even when it is prime; n = 1
means the nearest prime in the selected direction.

The same page retains **List consecutive primes**. Indexed searches count and
prove candidates entirely in PARI/GP and return only the requested prime.
The starting integer supports arbitrary precision; n is limited to 100,000
and the existing one-hour engine timeout applies. Backward searches report an
error if too few positive primes exist. Successful results are saved to a text
report in `output/`, with the exact path and download link shown below the form.

### Batch, progression, and prime-modulus tools

Three dedicated pages extend the existing operations:

- **Primality & navigation → Check a list of integers** tests up to 1,000 decimal
  integers in one GP process, preserving order and duplicates. Rigorous and
  probable-prime modes are clearly distinguished; integers below 2 are neither
  prime nor composite.
- **Prime generation → Primes in a residue class** finds proven primes
  `p ≡ r (mod m)` in an inclusive interval. Results include their exact sum and,
  when paginated, the next start. Modulus 1 selects all primes in the interval.
- **Arithmetic & factors → Calculate modulo a prime** supports modular inverses,
  powers (including negative exponents for nonzero residues), multiplicative
  orders, all square roots, and a primitive root. The modulus is rigorously
  proven before calculation.

These operations use decimal integer inputs, native PARI/GP computation, and
automatic text reports. See [Prime manipulation](docs/PRIME_MANIPULATION.md)
for examples, API details, limits, and audit coverage.

### Prime classification

The classifier runs a dedicated PARI/GP program and evaluates all 56 classes
from the classification catalogue. Exact algebraic forms and recurrences replace
finite lookup tables where practical. Each class has a selectable native-engine
time budget; a timed-out test or a definition whose exhaustive search exceeds a
documented safe bound is reported as **inconclusive**, never as a negative result.
This distinction matters for open or computationally extreme classes such as
Mills, Wilson, Wolstenholme, Higgs, cluster, and Fortunate primes.

Enter an integer expression in **Prime Tools → Classify a prime**, select a
one-to-ten-second budget for each class, and run the analysis. PARI/GP first
proves that the input is prime. A prime result is separated into matches,
definite non-matches, and inconclusive tests; a composite input stops before
classification. The same result is saved automatically as a text report in
`output/`.

See [Prime classification](docs/PRIME_CLASSIFICATION.md) for the complete
56-class catalogue, result semantics, computational limits, API example, and
implementation architecture.

### Reciprocals of primes

The reciprocal analyzer rigorously proves the input prime, calculates the
decimal period as the multiplicative order of 10 modulo the prime, and reports
whether 10 is a primitive root. It therefore also identifies base-10
full-reptend primes. Decimal expansion digits are generated with exact native
integer arithmetic, preserving leading zeros. The complete finite expansion or
repetend is streamed directly by PARI/GP into the automatic text export, while
only the requested preview enters the HTTP response and browser. Inputs 2 and 5
are handled as terminating decimals with period zero.

Period calculation supports arbitrary-precision primes. Factoring `p - 1`,
which is required to establish an exact multiplicative order, may be expensive
for very large inputs; the interface provides optional engine timeouts and a
no-time-limit mode. The browser preview is independently capped at 100,000
digits, but the saved report has no application-imposed digit limit. Available
time, memory, and disk space remain practical constraints for enormous periods.

See [Prime reciprocals](docs/PRIME_RECIPROCALS.md) for definitions, API usage,
limits, and implementation details.

### Available operations

| Tool | Behavior |
|---|---|
| Fixed-size generator | Produces up to 500 distinct, proven primes with exactly the requested decimal digits |
| Prime classifier | Rigorously evaluates 56 digital, structural, sequence, and constellation classes with explicit inconclusive results |
| Reciprocal analyzer | Computes the exact period of `1/p`, tests full-reptend status, and exports exact decimal digits |
| Prime navigator | Returns the nth proven prime or a list of primes strictly before/after an integer; position/count up to 100,000 |
| Batch primality | Tests up to 1,000 decimal integers in order, with rigorous/probable modes and explicit neither-prime-nor-composite results below 2 |
| Residue-class search | Finds proven primes in an inclusive interval with `p ≡ r (mod m)`, exact page sum, and continuation start |
| Prime-modulus arithmetic | Computes inverses, powers, multiplicative orders, all square roots, and a primitive root for a proven prime modulus |
| Range search | Lists proven primes in an interval with a result limit and continuation point |
| Prime tuples | Finds twin, cousin, sexy, triplet, quadruplet, or custom offset patterns |
| Special generator | Produces safe, Sophie Germain, Blum, or `p mod m = r` primes |
| N-th prime | Calculates `p(n)` through index `10^29` with parallel primecount; PARI fallback through `10^11` |
| Prime counting | Calculates exact `π(x)` through `10^31` with primecount; PARI fallback through `10^12` |
| Gap analyzer | Measures gaps between consecutive proven primes in an interval |
| Absolute-prime search | Groups circular primes by their complete decimal-rotation orbit |
| Gaussian tools | Applies the exact Gaussian-prime criterion and searches bounded complex lattices |
| Paterson search | Proves both p and the decimal companion formed from p's base-4 digits |
| Perfect numbers | Generates even perfect numbers from rigorously proven Mersenne primes |
| Full-reptend search | Finds primes satisfying exact `ord_p(10) = p - 1` |
| Prime pyramids | Recreates the source digit-insertion sequence and native-tested multiplication pyramid |
| Special-number search | Finds Carmichael numbers, corrected pseudoprimes, lucky primes, and Jacobsthal primes |
| Witness analyzer | Applies the complete strong Miller–Rabin criterion to arbitrary-size odd inputs |
| Gap statistics | Computes exact frequency tables, extrema, rational mean/median, and mode over bounded gap samples |
| Primorials | Generates cumulative products of rigorously generated consecutive primes |
| Random range sampler | Returns distinct rigorously proven random primes from an arbitrary-precision interval |
| Contiguous digits | Finds every distinct prime formed by an unreordered decimal substring |
| Goldbach partitions | Finds all displayed proven-prime partitions of one even integer; it does not claim a proof of the conjecture |
| Bounded prime problems | Searches four exact equation/factor/divisor-sum problems from the imported notebook |
| Integer arithmetic profile | Factors one nonzero integer and computes τ, σ, aliquot sum, φ, Carmichael λ, Möbius μ, radical, ω/Ω, semiprime status, and divisor class |
| Coprime navigator | Computes φ(m), previews the reduced residue system, and finds requested integers coprime to m after an arbitrary-size start |
| Prime distribution | Counts proven primes by equal interval bins and residue class, plus twins and the largest internal gap |
| Prime-factor distribution | Factors every integer in a bounded range and compares exact `ω(n)` and `Ω(n)` frequencies |
| Digit-constrained primes | Generates candidates from a selected decimal alphabet and rigorously proves matching primes |
| Prime polynomial | Evaluates `n²−n+k`, finds prime values and consecutive runs, and identifies exact small-prime modular obstructions |
| Palindrome-derived sequence | Finds prime values of `|n−reverse(n)|+1` over a finite range |
| Prime-indicator constant | Computes certified decimal digits of `Σ [n is prime]·2⁻ⁿ` from rigorously tested binary coefficients |
| Advanced native workbench | Adds special-prime families, NTT primes, Cunningham chains, modular roots/traces, Hensel lifting, group distributions, p-adic valuations, cyclotomic polynomials, divisor classifications, and aliquot sequences |

The lower fallback limits protect systems where the optional high-performance
engines are unavailable. `primecount` extends exact counting through `10^31`
and indexed requests through `10^29`; practical runtime and memory remain
hardware-dependent. These limits do not restrict primality testing,
arbitrary-precision navigation, generation, or PARI-backed algebraic tools.

Arbitrary precision does not mean unlimited input or runtime. Most expression
requests accept at most 100,000 characters, with configured expression-size
limits; individual tools also impose documented result, scan, or time bounds.
Factorization and zeta have thread controls. GP prime tools run individual
subprocesses and do not currently provide general interactive cancellation or
parallel thread selection.

See [Prime structures and related numbers](docs/PRIME_STRUCTURES.md) for the
definitions, corrections made to the imported prototypes, limits, and API
examples.

See [Prime exploration and notebook problems](docs/PRIME_EXPLORATION.md) for
gap distributions, primorials, Goldbach analysis, substring and random-range
tools, and the four bounded problem searches.

See [Arithmetic and distribution tools](docs/ARITHMETIC_AND_DISTRIBUTION.md)
for the final source-tree audit, mathematical definitions, native-engine
architecture, resource limits, and the eight additional API routes.

See [Advanced number theory](docs/ADVANCED_NUMBER_THEORY.md) for the new native
workbenches, strict result contracts, and documented finite-search bounds.

See [Expert factorization laboratory](docs/FACTOR_LAB.md) for SQUFOF, the resumable
GMP-ECM campaign manager, special-form and Aurifeuillean detection, the strategy
adviser, algorithm traces, and batch certificates.

See [Primality laboratory](docs/PRIMALITY_LAB.md) for the primality-test comparison
laboratory, deterministic witness sets, Pocklington and Pratt certificates, the
probable-prime taxonomy, and the constrained-prime generators.

Pell solutions and continued-fraction convergents have no useful bound on their size —
the fundamental solution for `d = 1000099` has 1,128 decimal digits — so neither tool
truncates them. Values too wide for a JSON response are abbreviated on screen with their
exact leading and trailing digits and exact digit count, and every value is written at
full length to a separate export file named in the response.

Mersenne numbers have their own route: trial factoring over q = 2kp + 1 never builds
M_p, so it reaches exponents in the millions where no general method can. See
[Mersenne numbers](docs/MERSENNE.md).

YAFU's number field sieve needs the GGNFS lattice sievers, which Numerisect
discovers, validates against this CPU and passes to YAFU automatically; see
[GGNFS lattice sievers](docs/SIEVERS.md).

Numerisect factors an RSA challenge number through the ordinary pipeline; see
[The RSA Factoring Challenge](docs/RSA_CHALLENGE.md) for the catalogue of all 54
numbers, the engine-verified factorizations, and an effort estimate for the open ones.

See [Quadratic forms and continued fractions](docs/FORMS_LAB.md) for binary quadratic
form reduction and composition, class groups, Pell equations, and the connection between
the principal cycle of forms and SQUFOF.

See [Algebra laboratory](docs/ALGEBRA_LAB.md) for reciprocity traces, congruences over
composite moduli, discrete-logarithm algorithm comparison, finite fields, record-number
families, quadratic rings, general number fields, and Chebotarev experiments.

See [Visualization and education](docs/VISUAL_LAB.md) for the prime spirals, Eisenstein
lattice, modular wheels, residue heatmaps, gap timelines, the prime race, the four sieve
animations, and the complexity dashboard.

See [Analytic prime distribution](docs/DISTRIBUTION_LAB.md) for approximation-error
charts, nth-prime bounds, prime races, singular series, Bateman-Horn predictions and
maximal-gap verification.

See [Zeta and L-functions](docs/ZETA_LAB.md) for explicit-formula prime counting,
Riemann-Siegel remainder analysis, pair correlation, Gram blocks, Dirichlet L-functions
and Dedekind zeta.

See [Independent verification](docs/VERIFICATION.md) for cross-engine agreement
checks, the engine self-test, and prime enumeration above primesieve's 2^64 ceiling.

See [Distributed CADO-NFS](docs/DISTRIBUTED.md) for distributed sieving, the trust
model it inherits from CADO, and the configurations Numerisect refuses.

See [Application infrastructure](docs/APPLICATION.md) for complete command-line parity,
the six export formats, batch import, workspaces, searchable history, result caching,
job priorities and resource limits, engine adapters, and the permissioned catalogue
lookups.

## Riemann Zeta

The Zeta workspace uses a compiled C helper linked to FLINT/Arb. It evaluates
`ζ(σ + it)` as rigorous complex balls, isolates consecutive Hardy Z zeros on
the critical line, and counts all nontrivial zeros through a requested height
with FLINT's Turing-method implementation. Critical-line graphs, Argand traces,
and complex-plane heatmaps are computed point-by-point in native code; JavaScript
only draws the returned samples. Plot coordinates use enclosure midpoints and
are exploratory, while evaluation enclosures, zero intervals, and counts retain
their explicit rigorous semantics.

See [Riemann zeta tools](docs/RIEMANN_ZETA.md) for mathematical scope, API
examples, precision/thread controls, and the distinction between certification
and visualization.

## Files and persistence

```text
numerisect/             Python backend and engine orchestration
numerisect/prime_classifier.gp  Native PARI/GP classification engine
numerisect/prime_reciprocal.gp  Native reciprocal-period and digit engine
numerisect/prime_structures.gp  Native structural, sequence, witness, and related-number engine
numerisect/number_theory.gp  Native modular, algebraic, analytic, and integer-structure workbench
numerisect/number_theory.py  Validation and tagged-protocol boundary for that workbench
numerisect/prime_manipulation.py  Validation and GP boundary for batches, progressions, and prime-modulus operations
numerisect/zeta.py       FLINT helper process boundary and strict result parsing
numerisect/native/numerisect_zeta.c  Compiled FLINT/Arb and OpenMP zeta engine
numerisect/static/       HTML, CSS, and JavaScript interface
numerisect/engine_manifest.toml  Reviewed immutable native-engine pins
numerisect/cli.py      Native-backed command-line entry point
install.sh              Cross-platform user-space installer
tests/                  Regression tests
docs/                   Feature and architecture documentation
data/numerisect.sqlite3 Persistent factorization job history
data/jobs/              Per-job work directories and native-engine logs
data/tools/             User-local native engine sources and installation
output/                 Completed text reports and factorization JSON manifests
```

`data/` and generated `output/*.txt` and `output/*.json` files are intentionally ignored by Git.
The placeholder `output/.gitkeep` keeps the output directory in a fresh clone.

## Configuration

| Environment variable | Default | Purpose |
|---|---:|---|
| `NUMERISECT_STATE_DIR` | `./data` in a source checkout; user data directory in an installed wheel | Database, jobs, setup state, and managed engines |
| `NUMERISECT_OUTPUT_DIR` | `./output` in a source checkout; user data directory in an installed wheel | Completed text exports |
| `NUMERISECT_CADO_THRESHOLD` | `95` | Decimal-digit boundary for automatic hybrid routing |
| `NUMERISECT_PRETEST_LEVEL` | `20` | Default YAFU pretest level |
| `NUMERISECT_MAX_PARALLEL_JOBS` | `1` | Simultaneous CPU-heavy factorization workers |
| `NUMERISECT_MAX_EXPRESSION_CHARACTERS` | `100000` | Expression input length limit |
| `NUMERISECT_MAX_RESULT_DIGITS` | `100000` | Evaluated integer size limit |
| `NUMERISECT_GGNFS_DIR` | unset | Directory holding the GGNFS lattice sievers, needed for NFS and for engine tuning |

## HTTP API

Interactive OpenAPI documentation is available at
<http://127.0.0.1:8765/api/docs> while the server is running.
All API routes except `/api/session` require a cryptographically random
per-launch session token. The browser manages it automatically; command-line
clients should follow [the localhost security model](docs/SECURITY_MODEL.md).

The installed `numerisect` command starts the web application by default
(equivalently `numerisect serve`). Its native-backed headless commands include `factor`, `prime`, `nth-prime`,
`near-prime`, `symbols`, `crt`, and `perfect-power`; add `--json` before the
subcommand for machine-readable output. For example:

```bash
numerisect --json factor 8051 --engine pari_trial --trial-bound 100
numerisect prime 32416190071 --certificate
numerisect near-prime 1289 100 --direction after
```

Important routes include:

```text
DELETE/api/cache
DELETE/api/workspaces/{workspace_id}
GET  /api/adapters
GET  /api/cache
GET  /api/capabilities
GET  /api/catalogues
GET  /api/distributed/trust-model
GET  /api/docs
GET  /api/exports/jobs
GET  /api/exports/jobs/{job_id}
GET  /api/exports/reports/{filename}
GET  /api/history/performance
GET  /api/jobs
GET  /api/jobs/{job_id}
GET  /api/jobs/{job_id}/export
GET  /api/jobs/{job_id}/log
GET  /api/outputs/{filename}
GET  /api/queue
GET  /api/reports
GET  /api/session
GET  /api/setup
GET  /api/setup/log
GET  /api/workspaces
GET  /api/workspaces/{workspace_id}
POST /api/algebra/chebotarev
POST /api/algebra/congruence
POST /api/algebra/cornacchia
POST /api/algebra/discrete-log
POST /api/algebra/divisor-lattice
POST /api/algebra/finite-field
POST /api/algebra/number-field
POST /api/algebra/quadratic-ring
POST /api/algebra/reciprocity
POST /api/algebra/record-numbers
POST /api/algebra/smoothness
POST /api/algebra/sociable
POST /api/algebra/weird-numbers
POST /api/batch/import
POST /api/catalogues/factors
POST /api/catalogues/oeis
POST /api/counting/algorithm-comparison
POST /api/counting/nth-prime-inverses
POST /api/counting/phi
POST /api/diagnostics
POST /api/distributed/factor
POST /api/distributed/preview
POST /api/distribution/approximation-error
POST /api/distribution/bateman-horn
POST /api/distribution/density-surface
POST /api/distribution/maximal-gaps
POST /api/distribution/nth-prime-bounds
POST /api/distribution/pnt-convergence
POST /api/distribution/prime-race
POST /api/distribution/progressions
POST /api/distribution/short-interval
POST /api/distribution/singular-series
POST /api/distribution/tuple-prediction
POST /api/factor-lab/certificates
POST /api/factor-lab/special-form
POST /api/factor-lab/squfof
POST /api/factor-lab/strategy
POST /api/factor-lab/trace
POST /api/factor-lab/tune
POST /api/forms/class-group
POST /api/forms/compose
POST /api/forms/continued-fraction
POST /api/forms/pell
POST /api/forms/prime-form
POST /api/forms/reduce
POST /api/forms/reduced-forms
POST /api/forms/represent
POST /api/jobs
POST /api/jobs/batch
POST /api/jobs/batch-export
POST /api/jobs/reorder
POST /api/jobs/{job_id}/cancel
POST /api/jobs/{job_id}/certificates
POST /api/jobs/{job_id}/continue-cofactor
POST /api/jobs/{job_id}/pause
POST /api/jobs/{job_id}/priority
POST /api/jobs/{job_id}/resume
POST /api/jobs/{job_id}/resume-paused
POST /api/number-theory/aliquot
POST /api/number-theory/arithmetic-functions
POST /api/number-theory/crt
POST /api/number-theory/cunningham-chain
POST /api/number-theory/cyclotomic
POST /api/number-theory/discrete-log
POST /api/number-theory/divisor-classification
POST /api/number-theory/eisenstein
POST /api/number-theory/factor-strategy
POST /api/number-theory/hensel-roots
POST /api/number-theory/modular-roots
POST /api/number-theory/ntt-primes
POST /api/number-theory/order-distribution
POST /api/number-theory/perfect-power
POST /api/number-theory/polynomial
POST /api/number-theory/power-residues
POST /api/number-theory/primality-lab
POST /api/number-theory/prime-approximations
POST /api/number-theory/quadratic-decomposition
POST /api/number-theory/special-form-test
POST /api/number-theory/special-prime-family
POST /api/number-theory/summatory-functions
POST /api/number-theory/symbols
POST /api/number-theory/tonelli-shanks
POST /api/number-theory/unit-group
POST /api/number-theory/valuation
POST /api/primality-lab/bitwin-chains
POST /api/primality-lab/carmichael
POST /api/primality-lab/chernick
POST /api/primality-lab/compare
POST /api/primality-lab/constrained-prime
POST /api/primality-lab/covering-set
POST /api/primality-lab/deterministic-witnesses
POST /api/primality-lab/ecpp-steps
POST /api/primality-lab/lucas-lehmer-steps
POST /api/primality-lab/lucas-sequence
POST /api/primality-lab/pocklington
POST /api/primality-lab/pratt
POST /api/primality-lab/prime-ladder
POST /api/primality-lab/proth
POST /api/primality-lab/proth-search
POST /api/primality-lab/repunit
POST /api/primality-lab/sierpinski
POST /api/primality-lab/taxonomy
POST /api/primality-lab/verify-certificate
POST /api/primes/absolute
POST /api/primes/after
POST /api/primes/batch-check
POST /api/primes/before
POST /api/primes/check
POST /api/primes/classify
POST /api/primes/contiguous-digits
POST /api/primes/coprimes
POST /api/primes/count
POST /api/primes/digit-constrained
POST /api/primes/distribution
POST /api/primes/factor-count-distribution
POST /api/primes/gap-statistics
POST /api/primes/gaps
POST /api/primes/gaussian/check
POST /api/primes/gaussian/range
POST /api/primes/generate
POST /api/primes/generate-special
POST /api/primes/goldbach
POST /api/primes/indicator-constant
POST /api/primes/integer-profile
POST /api/primes/miller-rabin-witnesses
POST /api/primes/modular
POST /api/primes/modular-wheel
POST /api/primes/nth
POST /api/primes/nth-near
POST /api/primes/palindrome-derived
POST /api/primes/paterson
POST /api/primes/perfect
POST /api/primes/polynomial
POST /api/primes/primorials
POST /api/primes/problems
POST /api/primes/progression
POST /api/primes/pyramid
POST /api/primes/random-range
POST /api/primes/range
POST /api/primes/reciprocal
POST /api/primes/reptend
POST /api/primes/sieve-interval
POST /api/primes/special-numbers
POST /api/primes/tuples
POST /api/primes/verify-certificate
POST /api/setup/install
POST /api/structure/factorint-strategies
POST /api/structure/lenstra-divisors
POST /api/structure/predicates
POST /api/verify/primality
POST /api/verify/prime-count
POST /api/verify/self-test
POST /api/visual/complexity
POST /api/visual/eisenstein-lattice
POST /api/visual/gap-timeline
POST /api/visual/modular-wheel
POST /api/visual/prime-race
POST /api/visual/residue-heatmap
POST /api/visual/sieve-trace
POST /api/visual/spiral
POST /api/workspaces
POST /api/workspaces/{workspace_id}
POST /api/zeta/backlund-s
POST /api/zeta/characters
POST /api/zeta/chebyshev-psi
POST /api/zeta/count
POST /api/zeta/dedekind
POST /api/zeta/euler-product
POST /api/zeta/evaluate
POST /api/zeta/explicit-prime-count
POST /api/zeta/functional-equation
POST /api/zeta/gram
POST /api/zeta/gram-blocks
POST /api/zeta/hardy
POST /api/zeta/heatmap
POST /api/zeta/l-function
POST /api/zeta/l-zeros
POST /api/zeta/line
POST /api/zeta/pair-correlation
POST /api/zeta/riemann-siegel
POST /api/zeta/stieltjes
POST /api/zeta/xi-eta
POST /api/zeta/zero-spacing
POST /api/zeta/zeros
```

## Tests

Run the complete regression suite and the JavaScript syntax check with:

```bash
python -m pytest -q
ruff check .
mypy
shellcheck install.sh run.sh
node --check numerisect/static/app.js
python -m build
```

The native integration tests invoke `gp` and compile or run the FLINT zeta
helper. They fail clearly when the corresponding native prerequisites are unavailable.

The suite includes API security, installer-manifest, native-engine, report,
and interface checks. Static navigation coverage verifies one registered form
for each of the 133 Prime Tools pages and all 22 Zeta pages, local result
placement, saved-report notices, diagnostics, and cache-busted assets.

## Documentation

| Guide | Scope |
| --- | --- |
| [Installation and versioning](docs/INSTALLATION.md) | Verified hosts, prerequisites, source installation, and pinned engine builds |
| [Factorization workspace](docs/FACTORIZATION.md) | Routing, manual algorithms, trees, partial jobs, batches, verification, and manifests |
| [Localhost security](docs/SECURITY_MODEL.md) | Host, origin, per-launch token, command-line access, and data locality |
| [Prime classification](docs/PRIME_CLASSIFICATION.md) | 56 classes and inconclusive-result semantics |
| [Prime reciprocals](docs/PRIME_RECIPROCALS.md) | Exact periods and complete streamed decimal reports |
| [Prime structures](docs/PRIME_STRUCTURES.md) | Structural searches, sequences, and witness analysis |
| [Prime exploration](docs/PRIME_EXPLORATION.md) | Gap statistics, primorials, Goldbach, and notebook problems |
| [Arithmetic and distribution](docs/ARITHMETIC_AND_DISTRIBUTION.md) | Arithmetic profiles, distributions, and source audit |
| [Prime manipulation](docs/PRIME_MANIPULATION.md) | Batches, relative-index navigation, residue classes, and modular arithmetic |
| [Riemann zeta](docs/RIEMANN_ZETA.md) | FLINT/Arb computations, threads, and certification boundaries |
| [Advanced number theory](docs/ADVANCED_NUMBER_THEORY.md) | Modular, polynomial, special-prime, analytic, divisor, and algebraic workbenches |
| [Prime counting and integer structure](docs/COUNTING_LAB.md) | Six-algorithm π(x) cross-check, Legendre's phi, inverse approximations, PARI structure predicates, and factorint strategy masks |
| [Roadmap status](docs/ROADMAP_STATUS.md) | Implemented, partial, and deliberately deferred items from the 150-item proposal |

## Security notes

- The launcher and Python entry point bind only to `127.0.0.1` by default.
- Trusted-host validation rejects non-loopback Host headers; API middleware
  rejects foreign browser origins and requests without the per-launch token.
- Engine installation never runs at startup and requires explicit confirmation.
- Do not expose the service to a network without authentication, TLS, and
  stricter operational quotas.
- Integer expressions are parsed through a restricted AST evaluator.
- Result downloads are constrained to Numerisect's output directory.
- Native commands receive validated values through explicit argument arrays or
  controlled standard input.

## How this was built

Numerisect was designed and directed by its author, and much of the code was written
with AI assistance under that direction and review. This section says so plainly, because
the commit history records it and a reader is entitled to know how a piece of software
came to exist.

**What that meant in practice.** The architecture is the part that matters here, and it
is a human decision: Numerisect is a user interface over existing number-theory
libraries, not a reimplementation of them. A computation uses a library routine first, an
optimized C program with GMP or FLINT only where no library provides one, and never
Python or JavaScript. That constraint shaped every feature, was written into
[CONTRIBUTING.md](CONTRIBUTING.md), and is enforced by
`tests/test_native_computation_policy.py` rather than left to good intentions.

The same applies to the project's other commitments: that a result is labelled proven,
probable or inconclusive and never blurred; that an exhausted search is never reported as
a negative answer; that the application stays offline unless explicitly told otherwise;
and that where the engines cannot answer, the gap is reported rather than approximated.

**What the assistance contributed** was throughput and breadth: writing and testing the
compiled helpers, wiring routes and interface, composing PARI/GP programs, and drafting
documentation, all reviewed against the policy above.

**What review means here.** Every mathematical claim in this repository is checked
against a native engine rather than asserted. The test suite cites published constants
with their sources, the documentation names the library routine behind each operation,
and `POST /api/verify/self-test` asks each installed engine questions whose answers are
published values, so a miscompiled build is caught before its output is trusted. Where
independent implementations of the same quantity exist, Numerisect runs several and
reports disagreement rather than choosing between them.

Correctness here does not rest on who or what typed a line. It rests on the engines doing
the mathematics, on results being labelled by their actual strength, and on the checks
being reproducible by anyone who clones the repository.

## Support, security, and contributing

- For installation or usage questions, read [SUPPORT.md](SUPPORT.md) and use
  the **Question or support request** issue form.
- For reproducible defects, use the structured bug-report form.
- Do not report suspected vulnerabilities in public issues. Follow
  [SECURITY.md](SECURITY.md) for private GitHub reporting or the email fallback.
- Contributions should follow [CONTRIBUTING.md](CONTRIBUTING.md) and pass the
  repository quality and secret-scanning workflows.

## Citation

Academic and educational users can cite the software using
[CITATION.cff](CITATION.cff). GitHub renders this metadata through its
**Cite this repository** interface after the repository becomes public.

## License

Numerisect is licensed under [GPL-3.0-or-later](LICENSE). Native engines and
libraries retain their own licenses; see
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
