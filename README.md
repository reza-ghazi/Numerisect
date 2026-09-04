# Numerisect

A friendly local number-theory workbench. It routes integer-factorization jobs
across YAFU, Msieve, GMP-ECM pretesting, and CADO-NFS. Arbitrary-precision
prime operations run in PARI/GP; Python and JavaScript are interface and
orchestration layers only.

## Features

- Safe integer-expression input (`+`, `-`, `*`, `//`, `%`, `^`, `**`)
- Automatic engine selection
- YAFU → CADO hybrid mode for large inputs
- Automatic CADO parameter discovery and next-larger selection
- Persistent SQLite job history and per-job work directories
- Live logs, phase indicators, cancellation, and CADO snapshot resume
- Verified factors: a job is complete only if the factors multiply to the input
- Beautiful factor equations and automatic plain-text exports in `output/`
- Adjustable CPU count, defaulting to every available processor
- Fast probable-prime checks, rigorous primality proofs, and certificate exports
- Exact-decimal-digit prime generation with rigorous verification
- Prime ranges, forward/backward navigation, and prime tuples such as twins
- Safe, Sophie Germain, Blum, and modular prime generators
- N-th-prime lookup, exact prime counting, and prime-gap analysis
- Automatic first-run source installation for missing engines
- Local-only HTTP binding by default

## Run

The required Python packages are already installed on this machine:

```bash
cd /home/reza/dev_dir/my_apps/mathematics/numerisect
./run.sh
```

Open <http://127.0.0.1:8765>.

On first start Numerisect checks for `gp`, `ecm`, `msieve`, `yafu`, and
`cado-nfs.py`.
Missing engines are fetched from their official upstream repositories, compiled,
and installed under `data/tools/`, without root access. Setup status is visible in
the web interface and its detailed build log is `data/engine-setup.log`. A compiler,
Git, Make, CMake, GMP development headers, Autoconf, Automake, and Libtool must be
available for source builds.

For a project-specific virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/uvicorn numerisect.main:app --host 127.0.0.1 --port 8765
```

## Strategy

`Automatic` uses YAFU below 95 decimal digits. At 95 digits and above it first
runs YAFU's small-factor/ECM pretest and sends a still-large residual to CADO-NFS.
If pretesting reduces the residual below the threshold, YAFU finishes it with SIQS.

Direct CADO mode accepts inputs outside CADO's normal parameter lookup gaps. It
chooses the smallest installed parameter set at least as large as the input (for
example, c60 for a 55-digit input). The advanced selector can override this.

State is stored in `data/`, which is intentionally ignored by Git. Set
`NUMERISECT_STATE_DIR` to relocate it. The application processes one CPU-heavy job
at a time by default; set `NUMERISECT_MAX_PARALLEL_JOBS` to change that.
Completed text reports and prime lists are stored in `output/`.

## Prime tools

- Check whether an arbitrary-precision integer is prime
- Choose a fast BPSW probable-prime test or a rigorous proof
- Export human-readable PARI primality/ECPP certificates
- Generate up to 500 distinct primes of a requested decimal length per request
- Generate safe, Sophie Germain, Blum, or congruence-constrained primes
- Find up to 100,000 proven primes in a range, before, or after a starting integer
- Find prime tuples using built-in twin, cousin, sexy, triplet, and quadruplet
  patterns, or custom offsets
- Look up p(n), calculate exact π(x), and inspect consecutive prime gaps

Prime checking uses PARI/GP's `isprime`, so a positive result is a proof rather
than only a probable-prime classification. A separate fast mode uses
`ispseudoprime` and is clearly labeled as non-rigorous. Range, navigation,
random-prime, certificate, counting, gap, and prime-tuple operations execute in
PARI/GP subprocesses. Candidate primes above 2^64 are explicitly passed through
`isprime` before Numerisect reports them as proven primes.

Exact prime counting is capped at 10^12 because PARI/GP's `primepi` uses a
memory-intensive sieve. N-th-prime lookup is capped at PARI's largest documented
checkpoint, 10^11. These limits prevent an innocent browser request from
exhausting the workstation.

## API

Interactive API documentation is available at <http://127.0.0.1:8765/api/docs>.

## Security

The server binds only to `127.0.0.1`. Do not expose it on a network without adding
authentication and request limits. Engine commands are launched as argument arrays,
not interpolated shell commands.
