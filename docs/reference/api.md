# HTTP API reference

Every route below is generated from the running application, so this page cannot
drift from the code. Interactive OpenAPI documentation is also served at
`/api/docs` while Numerisect is running.

## Authentication

All `/api/` routes except `/api/session` require the per-launch session token,
supplied either as the `X-Numerisect-Token` header or the `numerisect_session`
cookie. Obtain it from `GET /api/session`. The token changes every time the process
starts.

```bash
curl --cookie-jar jar http://127.0.0.1:8765/api/session
curl --cookie jar --header 'Content-Type: application/json' \
  --data '{"expression":"32416190071","mode":"proven"}' \
  http://127.0.0.1:8765/api/primes/check
```

To avoid tokens entirely, use `numerisect api`, which drives the same application
in-process. See the [command-line reference](cli.md).

## Conventions

- Invalid input returns **422** with a `detail` message naming the problem.
- A missing engine returns **503**.
- A refused network action returns **403**.
- Operations that produce a result save a report and return its exact
  `output/<filename>` path.
- Searches that stop at a bound set a truncation flag and give a continuation point.

## Routes (208)

### Engine adapters

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/adapters` | List built-in and user-declared engine adapters. |

### Algebra laboratory

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/algebra/chebotarev` |  |
| `POST` | `/api/algebra/congruence` |  |
| `POST` | `/api/algebra/cornacchia` |  |
| `POST` | `/api/algebra/discrete-log` |  |
| `POST` | `/api/algebra/divisor-lattice` |  |
| `POST` | `/api/algebra/finite-field` |  |
| `POST` | `/api/algebra/number-field` |  |
| `POST` | `/api/algebra/quadratic-ring` |  |
| `POST` | `/api/algebra/reciprocity` |  |
| `POST` | `/api/algebra/record-numbers` |  |
| `POST` | `/api/algebra/smoothness` |  |
| `POST` | `/api/algebra/sociable` |  |
| `POST` | `/api/algebra/weird-numbers` |  |

### Batch import

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/batch/import` | Expand a TXT/CSV/JSON document of integers, ranges, expressions, and families. |

### Result cache

| Method | Path | Purpose |
|---|---|---|
| `DELETE` | `/api/cache` | Discard cached results, optionally for one operation path only. |
| `GET` | `/api/cache` | Report result-cache size and hit counts. |

### Capabilities

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/capabilities` |  |

### Optional catalogues

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/catalogues` | Show local catalogue files and the current network permission state. |
| `POST` | `/api/catalogues/factors` | Look up claimed factors locally, or remotely when explicitly permitted. |
| `POST` | `/api/catalogues/oeis` | Search OEIS for a sequence. Disabled unless explicitly permitted. |

### Prime counting

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/counting/algorithm-comparison` |  |
| `POST` | `/api/counting/nth-prime-inverses` |  |
| `POST` | `/api/counting/phi` |  |

### Diagnostics

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/diagnostics` |  |

### Distributed CADO-NFS

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/distributed/factor` | Queue a factorization whose sieving is distributed by CADO-NFS. |
| `POST` | `/api/distributed/preview` | Validate a distributed configuration and report its exposure without running. |
| `GET` | `/api/distributed/trust-model` | Describe how distributed CADO authenticates clients, and what it does not. |

### Analytic distribution

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/distribution/approximation-error` |  |
| `POST` | `/api/distribution/bateman-horn` |  |
| `POST` | `/api/distribution/density-surface` |  |
| `POST` | `/api/distribution/maximal-gaps` |  |
| `POST` | `/api/distribution/nth-prime-bounds` |  |
| `POST` | `/api/distribution/pnt-convergence` |  |
| `POST` | `/api/distribution/prime-race` |  |
| `POST` | `/api/distribution/progressions` |  |
| `POST` | `/api/distribution/short-interval` |  |
| `POST` | `/api/distribution/singular-series` |  |
| `POST` | `/api/distribution/tuple-prediction` |  |

### OpenAPI documentation

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/docs` |  |

### Exports

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/exports/jobs` | Export job search results in any supported interchange format. |
| `GET` | `/api/exports/jobs/{job_id}` | Export one factorization job in any supported interchange format. |
| `GET` | `/api/exports/reports/{filename}` | Re-container a saved text report; the engine-produced body is unchanged. |

### Expert factorization laboratory

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/factor-lab/certificates` | Generate and independently verify a primality certificate per prime factor. |
| `POST` | `/api/factor-lab/special-form` | Detect special algebraic forms, algebraic factors, and SNFS suitability. |
| `POST` | `/api/factor-lab/squfof` | Factor with Shanks' square forms factorization (numerisect-squfof, C/GMP). |
| `POST` | `/api/factor-lab/strategy` | Recommend an engine and estimate the expected remaining factor size. |
| `POST` | `/api/factor-lab/trace` | Produce a bounded, educational step trace of a factoring algorithm. |
| `POST` | `/api/factor-lab/tune` | Measure this machine's SIQS/NFS crossover with YAFU's own `tune`. |

### Quadratic forms and continued fractions

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/forms/class-group` |  |
| `POST` | `/api/forms/compose` |  |
| `POST` | `/api/forms/continued-fraction` |  |
| `POST` | `/api/forms/pell` |  |
| `POST` | `/api/forms/prime-form` |  |
| `POST` | `/api/forms/reduce` |  |
| `POST` | `/api/forms/reduced-forms` |  |
| `POST` | `/api/forms/represent` |  |

### Performance history

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/history/performance` | Aggregate completed-job runtimes by engine and decimal-digit bucket. |

### Factorization jobs

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/jobs` | List jobs, optionally filtered and sorted (roadmap item 135). |
| `POST` | `/api/jobs` |  |
| `POST` | `/api/jobs/batch` |  |
| `POST` | `/api/jobs/batch-export` |  |
| `POST` | `/api/jobs/reorder` | Reorder queued jobs; the supplied order becomes the dispatch order. |
| `GET` | `/api/jobs/{job_id}` |  |
| `POST` | `/api/jobs/{job_id}/cancel` |  |
| `POST` | `/api/jobs/{job_id}/certificates` | Certify every prime factor of a completed factorization (roadmap item 13). |
| `POST` | `/api/jobs/{job_id}/continue-cofactor` |  |
| `GET` | `/api/jobs/{job_id}/export` |  |
| `GET` | `/api/jobs/{job_id}/log` |  |
| `POST` | `/api/jobs/{job_id}/pause` | Suspend a running job's process group with SIGSTOP. |
| `POST` | `/api/jobs/{job_id}/priority` | Change one job's scheduling priority; higher runs sooner. |
| `POST` | `/api/jobs/{job_id}/resume` |  |
| `POST` | `/api/jobs/{job_id}/resume-paused` | Continue a paused job's process group with SIGCONT. |

### Number theory

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/number-theory/aliquot` |  |
| `POST` | `/api/number-theory/arithmetic-functions` |  |
| `POST` | `/api/number-theory/crt` |  |
| `POST` | `/api/number-theory/cunningham-chain` |  |
| `POST` | `/api/number-theory/cyclotomic` |  |
| `POST` | `/api/number-theory/discrete-log` |  |
| `POST` | `/api/number-theory/divisor-classification` |  |
| `POST` | `/api/number-theory/eisenstein` |  |
| `POST` | `/api/number-theory/factor-strategy` |  |
| `POST` | `/api/number-theory/hensel-roots` |  |
| `POST` | `/api/number-theory/modular-roots` |  |
| `POST` | `/api/number-theory/ntt-primes` |  |
| `POST` | `/api/number-theory/order-distribution` |  |
| `POST` | `/api/number-theory/perfect-power` |  |
| `POST` | `/api/number-theory/polynomial` |  |
| `POST` | `/api/number-theory/power-residues` |  |
| `POST` | `/api/number-theory/primality-lab` |  |
| `POST` | `/api/number-theory/prime-approximations` |  |
| `POST` | `/api/number-theory/quadratic-decomposition` |  |
| `POST` | `/api/number-theory/special-form-test` |  |
| `POST` | `/api/number-theory/special-prime-family` |  |
| `POST` | `/api/number-theory/summatory-functions` |  |
| `POST` | `/api/number-theory/symbols` |  |
| `POST` | `/api/number-theory/tonelli-shanks` |  |
| `POST` | `/api/number-theory/unit-group` |  |
| `POST` | `/api/number-theory/valuation` |  |

### Report download

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/outputs/{filename}` |  |

### /api/primality-lab

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/primality-lab/bitwin-chains` |  |
| `POST` | `/api/primality-lab/carmichael` |  |
| `POST` | `/api/primality-lab/chernick` |  |
| `POST` | `/api/primality-lab/compare` |  |
| `POST` | `/api/primality-lab/constrained-prime` |  |
| `POST` | `/api/primality-lab/covering-set` |  |
| `POST` | `/api/primality-lab/deterministic-witnesses` |  |
| `POST` | `/api/primality-lab/ecpp-steps` |  |
| `POST` | `/api/primality-lab/lucas-lehmer-steps` |  |
| `POST` | `/api/primality-lab/lucas-sequence` |  |
| `POST` | `/api/primality-lab/pocklington` |  |
| `POST` | `/api/primality-lab/pratt` |  |
| `POST` | `/api/primality-lab/prime-ladder` |  |
| `POST` | `/api/primality-lab/proth` |  |
| `POST` | `/api/primality-lab/proth-search` |  |
| `POST` | `/api/primality-lab/repunit` |  |
| `POST` | `/api/primality-lab/sierpinski` |  |
| `POST` | `/api/primality-lab/taxonomy` |  |
| `POST` | `/api/primality-lab/verify-certificate` |  |

### Prime tools

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/primes/absolute` |  |
| `POST` | `/api/primes/after` |  |
| `POST` | `/api/primes/batch-check` |  |
| `POST` | `/api/primes/before` |  |
| `POST` | `/api/primes/check` |  |
| `POST` | `/api/primes/classify` |  |
| `POST` | `/api/primes/contiguous-digits` |  |
| `POST` | `/api/primes/coprimes` |  |
| `POST` | `/api/primes/count` |  |
| `POST` | `/api/primes/digit-constrained` |  |
| `POST` | `/api/primes/distribution` |  |
| `POST` | `/api/primes/factor-count-distribution` |  |
| `POST` | `/api/primes/gap-statistics` |  |
| `POST` | `/api/primes/gaps` |  |
| `POST` | `/api/primes/gaussian/check` |  |
| `POST` | `/api/primes/gaussian/range` |  |
| `POST` | `/api/primes/generate` |  |
| `POST` | `/api/primes/generate-special` |  |
| `POST` | `/api/primes/goldbach` |  |
| `POST` | `/api/primes/indicator-constant` |  |
| `POST` | `/api/primes/integer-profile` |  |
| `POST` | `/api/primes/miller-rabin-witnesses` |  |
| `POST` | `/api/primes/modular` |  |
| `POST` | `/api/primes/modular-wheel` |  |
| `POST` | `/api/primes/nth` |  |
| `POST` | `/api/primes/nth-near` |  |
| `POST` | `/api/primes/palindrome-derived` |  |
| `POST` | `/api/primes/paterson` |  |
| `POST` | `/api/primes/perfect` |  |
| `POST` | `/api/primes/polynomial` |  |
| `POST` | `/api/primes/primorials` |  |
| `POST` | `/api/primes/problems` |  |
| `POST` | `/api/primes/progression` |  |
| `POST` | `/api/primes/pyramid` |  |
| `POST` | `/api/primes/random-range` |  |
| `POST` | `/api/primes/range` |  |
| `POST` | `/api/primes/reciprocal` |  |
| `POST` | `/api/primes/reptend` |  |
| `POST` | `/api/primes/sieve-interval` | Enumerate primes in an interval of any magnitude. |
| `POST` | `/api/primes/special-numbers` |  |
| `POST` | `/api/primes/tuples` |  |
| `POST` | `/api/primes/verify-certificate` |  |

### Job queue

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/queue` | Show queued and running jobs in dispatch order. |

### Saved reports

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/reports` | Search the index of saved report files. |

### Session

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/session` |  |

### Engine setup

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/setup` |  |
| `POST` | `/api/setup/install` |  |
| `GET` | `/api/setup/log` |  |

### Integer structure

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/structure/factorint-strategies` |  |
| `POST` | `/api/structure/lenstra-divisors` |  |
| `POST` | `/api/structure/predicates` |  |

### Independent verification

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/verify/primality` | Decide primality with independent implementations and compare them. |
| `POST` | `/api/verify/prime-count` | Compute pi(x) with every independent method available and compare them. |
| `POST` | `/api/verify/self-test` | Ask each installed engine questions with published answers. |

### Visualization

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/visual/complexity` |  |
| `POST` | `/api/visual/eisenstein-lattice` |  |
| `POST` | `/api/visual/gap-timeline` |  |
| `POST` | `/api/visual/modular-wheel` |  |
| `POST` | `/api/visual/prime-race` |  |
| `POST` | `/api/visual/residue-heatmap` |  |
| `POST` | `/api/visual/sieve-trace` |  |
| `POST` | `/api/visual/spiral` |  |

### Workspaces

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/workspaces` | List saved workspaces, newest first. |
| `POST` | `/api/workspaces` | Save a named workspace referencing jobs, reports, and interface state. |
| `DELETE` | `/api/workspaces/{workspace_id}` | Delete one workspace. Jobs and reports are not affected. |
| `GET` | `/api/workspaces/{workspace_id}` | Load one workspace. |
| `POST` | `/api/workspaces/{workspace_id}` | Update selected fields of one workspace. |

### Zeta and L-functions

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/zeta/backlund-s` | Certified S(T) with an exploratory plot across an ordinate range. |
| `POST` | `/api/zeta/characters` | Dirichlet character table modulo q with conductor, parity and order. |
| `POST` | `/api/zeta/chebyshev-psi` | Chebyshev ψ(x) reconstructed from certified zeros (FLINT/Arb). |
| `POST` | `/api/zeta/count` |  |
| `POST` | `/api/zeta/dedekind` | Dedekind zeta of a bounded number field through PARI/GP. |
| `POST` | `/api/zeta/euler-product` | Truncated Euler products against ζ(s) with a rigorous tail bound. |
| `POST` | `/api/zeta/evaluate` |  |
| `POST` | `/api/zeta/explicit-prime-count` | Riemann's explicit formula for π(x) from certified zeros (FLINT/Arb). |
| `POST` | `/api/zeta/functional-equation` |  |
| `POST` | `/api/zeta/gram` |  |
| `POST` | `/api/zeta/gram-blocks` | Gram's-law verdicts, exceptions and Gram blocks over an index range. |
| `POST` | `/api/zeta/hardy` |  |
| `POST` | `/api/zeta/heatmap` |  |
| `POST` | `/api/zeta/l-function` | Rigorous L(s, χ) enclosure with an independent Hurwitz cross-check. |
| `POST` | `/api/zeta/l-zeros` | Certified critical-line sign changes, or exploratory |L| minima. |
| `POST` | `/api/zeta/line` |  |
| `POST` | `/api/zeta/pair-correlation` | Pair correlation of certified zeros against the GUE prediction. |
| `POST` | `/api/zeta/riemann-siegel` | Riemann–Siegel main sum with K corrections against acb_dirichlet_zeta. |
| `POST` | `/api/zeta/stieltjes` |  |
| `POST` | `/api/zeta/xi-eta` |  |
| `POST` | `/api/zeta/zero-spacing` | Normalized nearest-neighbour spacing histogram of certified zeros. |
| `POST` | `/api/zeta/zeros` |  |

