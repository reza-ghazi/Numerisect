# Numerisect

**Multi-Engine Integer Factorization and Prime Analysis**

Numerisect 0.2.0 is a local web workbench for integer factorization, primality
proofs, prime generation, and prime exploration. Python handles validation,
process orchestration, persistence, and the HTTP API; plain JavaScript provides
the browser interface. Native number-theory programs perform the expensive
mathematics.

The server listens only on `127.0.0.1` by default. Results stay on the local
machine unless the repository or exported files are shared deliberately.

## Highlights

- Automatic YAFU-to-CADO factorization strategy based on decimal length
- Manual YAFU, Msieve, hybrid, and CADO-NFS strategies
- Automatic CADO parameter discovery and next-larger parameter selection
- CPU-thread selector that defaults to every available logical CPU
- Persistent jobs, live engine logs, cancellation, and CADO snapshot resume
- Product verification before a factorization is marked complete
- Fast probable-prime tests, rigorous proofs, and certificate exports
- Fixed-length, safe, Sophie Germain, Blum, and modular prime generation
- Prime ranges, nearby primes, tuples, gaps, indexed primes, and exact counts
- Automatic plain-text reports in `output/`
- First-start, user-local source installation for missing native engines

## Start and stop

```bash
cd /home/reza/dev_dir/my_apps/mathematics/Numerisect
./run.sh
```

Open the main interface at <http://127.0.0.1:8765> or open Prime Tools directly
at <http://127.0.0.1:8765/#primes>.

Keep the terminal open while using Numerisect. Press `Ctrl+C` in that terminal
to stop it. If it was started from another terminal, find and stop only its PID:

```bash
pgrep -af 'uvicorn numerisect.main:app'
kill PID_FROM_THE_PREVIOUS_COMMAND
```

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
| PARI/GP | Primality tests and proofs, certificates, prime generation, navigation, tuples, gaps, `prime(n)`, and `primepi(x)` |

The status line at the top of the interface shows which executables are
available. Engine commands are launched as argument arrays rather than through
shell interpolation.

## First-run engine installation

At startup, Numerisect checks for these commands:

```text
yafu  msieve  ecm  cado-nfs.py  gp
```

If any are missing, a background setup task fetches current upstream source,
builds it, and installs it under `data/tools/`. It does not request root access
or overwrite an existing system installation. The managed `bin` and `lib`
directories are added to the Numerisect process environment automatically.

Source builds require network access plus Git, Make, a C/C++ compiler, CMake,
GMP development headers, Autoconf, Automake, and Libtool. Progress appears in
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

### Primality modes

- **Rigorous:** uses `isprime`; a positive result is a mathematical proof.
- **Fast:** uses the BPSW-based `ispseudoprime`; a positive result is labeled
  “probable prime,” not proven prime.
- **Certificate:** rigorous mode can export a human-readable PARI
  primality/ECPP certificate with the result.

PARI candidate generators and iterators may provide pseudoprimes above `2^64`.
Numerisect explicitly applies `isprime` before reporting generated, ranged,
navigated, or tuple members as proven primes.

### Available operations

| Tool | Behavior |
|---|---|
| Fixed-size generator | Produces up to 500 distinct, proven primes with exactly the requested decimal digits |
| Prime navigator | Finds up to 100,000 proven primes before or after an arbitrary-size integer |
| Range search | Lists proven primes in an interval with a result limit and continuation point |
| Prime tuples | Finds twin, cousin, sexy, triplet, quadruplet, or custom offset patterns |
| Special generator | Produces safe, Sophie Germain, Blum, or `p mod m = r` primes |
| N-th prime | Calculates `p(n)` for positive indices through `10^11` |
| Prime counting | Calculates exact `π(x)` for `x` through `10^12` |
| Gap analyzer | Measures gaps between consecutive proven primes in an interval |

The `10^12` exact-counting limit protects the workstation because PARI/GP's
`primepi` implementation uses a memory-intensive sieve. The `10^11` indexed
prime limit matches PARI's largest documented checkpoint. These limits do not
restrict primality testing, navigation, generation, tuple searches, or range
endpoints, although work on very large inputs can take a long time.

## Files and persistence

```text
numerisect/             Python backend and engine orchestration
static/                 HTML, CSS, and JavaScript interface
tests/                  Regression tests
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
POST /api/primes/generate
POST /api/primes/generate-special
POST /api/primes/after
POST /api/primes/before
POST /api/primes/range
POST /api/primes/tuples
POST /api/primes/nth
POST /api/primes/count
POST /api/primes/gaps
```

## Tests

Run the complete regression suite and the JavaScript syntax check with:

```bash
cd /home/reza/dev_dir/my_apps/mathematics/Numerisect
python3 -m pytest
node --check static/app.js
```

The prime tests invoke the installed `gp` executable. They will fail clearly if
PARI/GP is unavailable.

## Security notes

- The provided launcher binds only to `127.0.0.1`.
- Do not expose the service to a network without authentication, TLS, and
  stricter operational quotas.
- Integer expressions are parsed through a restricted AST evaluator.
- Result downloads are constrained to Numerisect's output directory.
- Native commands receive validated values through explicit argument arrays or
  controlled standard input.
