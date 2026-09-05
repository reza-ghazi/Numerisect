# Numerisect

**Multi-Engine Integer Factorization and Prime Analysis**

Numerisect 0.3.0 is a local web workbench for integer factorization, primality
proofs, prime generation, prime exploration, and rigorous Riemann-zeta analysis. Python handles validation,
process orchestration, persistence, and the HTTP API; plain JavaScript provides
the browser interface. Native number-theory programs perform the expensive
mathematics.

The server listens only on `127.0.0.1` by default. Results stay on the local
machine unless the repository or exported files are shared deliberately.

This is a private, pre-release project run from its source checkout. Release
packages and a packaging workflow have not been published or designed yet.
For Linux, Windows WSL, and macOS installation, see
[Installation and versioning](docs/INSTALLATION.md).
Version history is tracked in [CHANGELOG.md](CHANGELOG.md).

## Highlights

- Automatic YAFU-to-CADO factorization strategy based on decimal length
- Manual YAFU, Msieve, hybrid, and CADO-NFS strategies
- Automatic CADO parameter discovery and next-larger parameter selection
- CPU-thread selector that defaults to every available logical CPU
- Persistent jobs, live engine logs, cancellation, and CADO snapshot resume
- Product verification before a factorization is marked complete
- Fast probable-prime tests, rigorous proofs, and certificate exports
- Native PARI/GP classification across 56 structural and sequence-based prime classes
- Exact reciprocal periods, full-reptend tests, and decimal repetend exports
- Fixed-length, safe, Sophie Germain, Blum, and modular prime generation
- Prime ranges, nearby primes, tuples, gaps, indexed primes, and exact counts
- The nth proven prime strictly before or after an arbitrary-size integer
- Batch primality checks, interval residue-class searches, and exact prime-modulus arithmetic
- 38 individually routed Prime Tools pages with searchable navigation and local results
- Absolute/circular, Gaussian, Paterson, full-reptend, and perfect-number tools
- Prime pyramids, corrected pseudoprime searches, and Miller–Rabin witness analysis
- Native prime-gap statistics, primorials, Goldbach partitions, digit-substring primes, and bounded equation searches
- Exact arithmetic-function profiles, semiprime detection, and coprime navigation
- Prime-density/residue charts, digit-constrained primes, exact polynomial exploration, and certified prime-indicator constants
- Rigorous zeta evaluation, certified critical-line zeros, exact Turing-method zero counts, and native-sampled plots
- Automatic plain-text reports in `output/`
- First-start, user-local source installation for missing native engines

## Start and stop

```bash
cd /home/reza/dev_dir/my_apps/mathematics/Numerisect
./run.sh
```

The launcher prints the exact source and interface directories it serves and
opens a versioned URL in the default browser when `xdg-open` is available. It
prefers `.venv/bin/python` when present and explicitly loads this source tree.
Set `NUMERISECT_NO_BROWSER=1`
if you prefer to open it manually. The main routes are Prime Tools at
<http://127.0.0.1:8765/?ui=20260905-workstation#primes/prime-check> and Riemann Zeta at
<http://127.0.0.1:8765/?ui=20260905-workstation#zeta>.

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

To install a versioned copy outside the source checkout, run:

```bash
./install.sh
```

The installer supports Linux, Windows WSL, and macOS with Homebrew. It checks
the required toolchain and development libraries, installs missing packages
through the host package manager, creates a release-specific Python virtual
environment, and creates a stable user launcher under
`~/.local/share/numerisect/bin/numerisect`. Native number engines are installed
on the first application start under the shared user state directory. See
[Installation and versioning](docs/INSTALLATION.md) for prefixes, upgrades,
package-manager behavior, and troubleshooting.

## Python setup

Numerisect requires Python 3.11 or newer, FastAPI, and Uvicorn. To create an
isolated development environment:

```bash
cd /home/reza/dev_dir/my_apps/mathematics/Numerisect
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
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

The status line at the top of the interface shows which executables are
available. Engine commands are launched as argument arrays rather than through
shell interpolation.

## First-run engine installation

At startup, Numerisect checks for these commands:

```text
yafu  msieve  ecm  cado-nfs.py  gp  numerisect-zeta
```

If any are missing, a background setup task fetches current upstream source,
builds it, and installs it under `data/tools/`. It does not request root access
or overwrite an existing system installation. The managed `bin` and `lib`
directories are added to the Numerisect process environment automatically.

Source builds require network access plus Git, Make, a C/C++ compiler, CMake,
GMP, MPFR, and FLINT development headers, Autoconf, Automake, and Libtool. If
FLINT is unavailable, Numerisect builds its latest source release and then its
small OpenMP-enabled zeta helper. Progress appears in
the setup banner. Detailed output is stored in:

```text
data/engine-setup.log
```

If installation fails, install the missing build prerequisite, restart
Numerisect, and inspect that log. The setup API can also retry installation:

```bash
curl -X POST http://127.0.0.1:8765/api/setup/install
```

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

Each completed factorization receives an equation view, per-factor status, and
a text report. A job is considered successful only when the returned factors
multiply exactly to the input.

## Prime Tools

All prime operations use PARI/GP subprocesses.

Prime Tools has 38 pages with searchable navigation in six groups. Every
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
| N-th prime | Calculates `p(n)` for positive indices through `10^11` |
| Prime counting | Calculates exact `π(x)` for `x` through `10^12` |
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

The `10^12` exact-counting limit protects the workstation because PARI/GP's
`primepi` implementation uses a memory-intensive sieve. The `10^11` indexed
prime limit matches PARI's largest documented checkpoint. These limits do not
restrict primality testing, navigation, generation, tuple searches, or range
endpoints, although work on very large inputs can take a long time.

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
numerisect/prime_manipulation.py  Validation and GP boundary for batches, progressions, and prime-modulus operations
numerisect/zeta.py       FLINT helper process boundary and strict result parsing
native/numerisect_zeta.c  Compiled FLINT/Arb and OpenMP zeta engine
static/                 HTML, CSS, and JavaScript interface
install.sh              Cross-platform user-space installer
tests/                  Regression tests
docs/                   Feature and architecture documentation
data/numerisect.sqlite3 Persistent factorization job history
data/jobs/              Per-job work directories and native-engine logs
data/tools/             User-local native engine sources and installation
output/                 Completed text reports and prime exports
```

`data/` and generated `output/*.txt` files are intentionally ignored by Git.
The placeholder `output/.gitkeep` keeps the output directory in a fresh clone.

## Configuration

| Environment variable | Default | Purpose |
|---|---:|---|
| `NUMERISECT_STATE_DIR` | `./data` | Database, jobs, setup state, and managed engines |
| `NUMERISECT_OUTPUT_DIR` | `./output` | Completed text exports |
| `NUMERISECT_CADO_THRESHOLD` | `95` | Decimal-digit boundary for automatic hybrid routing |
| `NUMERISECT_PRETEST_LEVEL` | `20` | Default YAFU pretest level |
| `NUMERISECT_MAX_PARALLEL_JOBS` | `1` | Simultaneous CPU-heavy factorization workers |
| `NUMERISECT_MAX_EXPRESSION_CHARACTERS` | `100000` | Expression input length limit |
| `NUMERISECT_MAX_RESULT_DIGITS` | `100000` | Evaluated integer size limit |

## HTTP API

Interactive OpenAPI documentation is available at
<http://127.0.0.1:8765/api/docs> while the server is running.

Important routes include:

```text
GET  /api/capabilities
GET  /api/setup
POST /api/setup/install

POST /api/jobs
GET  /api/jobs
GET  /api/jobs/{id}
GET  /api/jobs/{id}/log
POST /api/jobs/{id}/cancel
POST /api/jobs/{id}/resume
GET  /api/jobs/{id}/export

POST /api/primes/check
POST /api/primes/batch-check
POST /api/primes/progression
POST /api/primes/modular
POST /api/primes/classify
POST /api/primes/reciprocal
POST /api/primes/generate
POST /api/primes/generate-special
POST /api/primes/after
POST /api/primes/before
POST /api/primes/range
POST /api/primes/tuples
POST /api/primes/nth
POST /api/primes/nth-near
POST /api/primes/count
POST /api/primes/gaps
POST /api/primes/absolute
POST /api/primes/gaussian/check
POST /api/primes/gaussian/range
POST /api/primes/modular-wheel
POST /api/primes/paterson
POST /api/primes/perfect
POST /api/primes/reptend
POST /api/primes/pyramid
POST /api/primes/special-numbers
POST /api/primes/miller-rabin-witnesses
POST /api/primes/gap-statistics
POST /api/primes/primorials
POST /api/primes/random-range
POST /api/primes/contiguous-digits
POST /api/primes/goldbach
POST /api/primes/problems
POST /api/primes/integer-profile
POST /api/primes/coprimes
POST /api/primes/distribution
POST /api/primes/factor-count-distribution
POST /api/primes/digit-constrained
POST /api/primes/polynomial
POST /api/primes/palindrome-derived
POST /api/primes/indicator-constant

POST /api/zeta/evaluate
POST /api/zeta/zeros
POST /api/zeta/count
POST /api/zeta/line
POST /api/zeta/heatmap
```

## Tests

Run the complete regression suite and the JavaScript syntax check with:

```bash
cd /home/reza/dev_dir/my_apps/mathematics/Numerisect
python3 -m pytest
node --check static/app.js
```

The native integration tests invoke `gp` and compile or run the FLINT zeta
helper. They fail clearly when the corresponding native prerequisites are unavailable.

The current suite contains 126 tests. A separate browser audit verified one
visible form on each of the 38 Prime Tools routes, native submissions from the
three manipulation pages, saved-report notices, and mobile layout widths.

## Documentation

| Guide | Scope |
| --- | --- |
| [Prime classification](docs/PRIME_CLASSIFICATION.md) | 56 classes and inconclusive-result semantics |
| [Prime reciprocals](docs/PRIME_RECIPROCALS.md) | Exact periods and complete streamed decimal reports |
| [Prime structures](docs/PRIME_STRUCTURES.md) | Structural searches, sequences, and witness analysis |
| [Prime exploration](docs/PRIME_EXPLORATION.md) | Gap statistics, primorials, Goldbach, and notebook problems |
| [Arithmetic and distribution](docs/ARITHMETIC_AND_DISTRIBUTION.md) | Arithmetic profiles, distributions, and source audit |
| [Prime manipulation](docs/PRIME_MANIPULATION.md) | Batches, relative-index navigation, residue classes, and modular arithmetic |
| [Riemann zeta](docs/RIEMANN_ZETA.md) | FLINT/Arb computations, threads, and certification boundaries |

## Security notes

- The provided launcher binds only to `127.0.0.1`.
- Do not expose the service to a network without authentication, TLS, and
  stricter operational quotas.
- Integer expressions are parsed through a restricted AST evaluator.
- Result downloads are constrained to Numerisect's output directory.
- Native commands receive validated values through explicit argument arrays or
  controlled standard input.
