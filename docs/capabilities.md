---
description: A complete map of the workspaces, mathematical engines, guarantees and limits in Numerisect 0.6.0.
---

# Capability index

This page answers a practical question: **which part of Numerisect should I use?** It is
an index of the released 0.6.0 interface, not a list of future intentions. The
[roadmap ledger](ROADMAP_STATUS.md) separately records partial, deferred and declined
work.

The current application exposes five top-level workspaces, 133 individually routed
Prime Tools pages, 22 individually routed zeta pages, and 212 HTTP API operations. The
API total is checked against the running FastAPI application by the test suite, so adding
or removing a route without updating the public reference fails validation.

!!! note "A large input is not automatically a conclusive input"

    GMP, PARI/GP and FLINT provide arbitrary-precision arithmetic, but algorithms still
    consume finite time, memory and disk. A timeout, catalogue boundary, candidate cap or
    unfinished exhaustive search is reported as **inconclusive**, never as a negative
    mathematical result.

## Choose a workspace

| If you want to… | Open | Principal engine |
|---|---|---|
| Factor one integer, a batch, an RSA Challenge number or a special form | **Factor integers** | YAFU, Msieve, GMP-ECM, CADO-NFS, GGNFS, PARI/GP, native SQUFOF |
| Prove, generate, classify, count or explore primes and integer structure | **Prime tools** | PARI/GP, primecount, primesieve, GMP, native big-interval sieve |
| Evaluate zeta/L-functions, isolate zeros or explore zero statistics | **Riemann zeta** | FLINT/Arb and PARI/GP |
| Check builds, versions and published reference values | **System diagnostics** | The installed engines themselves |
| Revisit jobs, reports, cached results, measurements or saved sessions | **Workspaces & history** | Local SQLite state and saved output files |

The browser is a presentation layer. Python validates requests, starts native processes,
parses complete tagged output and persists results. JavaScript manages interaction and
draws coordinates and colours. Mathematical decisions remain in the engines named below.

## Factorization workspace

The workspace is organized around a production pipeline and an expert laboratory.

| Capability | What it establishes | Guide |
|---|---|---|
| Automatic routing | YAFU below the configured threshold; YAFU pretest followed by SIQS or CADO-NFS for a large residual | [Factorization](FACTORIZATION.md) |
| Manual strategies | Trial division, Fermat, rho, p−1, p+1, ECM, SIQS, NFS, SNFS, Msieve and direct CADO selection | [Mathematics](mathematics/factorization.md) |
| Result verification | Every reported factor divides the input and the full multiset reconstructs it; optional YAFU/Msieve cross-check | [Verification](VERIFICATION.md) |
| SQUFOF | A bounded factor search for \(N<2^{62}\), implemented in C with GMP because no exposed engine routine supplies it | [Expert laboratory](FACTOR_LAB.md) |
| Resumable ECM | A GMP-ECM campaign with saved stage-one residues and native factor reconciliation | [Expert laboratory](FACTOR_LAB.md) |
| Special-form analysis | Perfect powers and \(a^k\!\pm1\) without a base limit, plus bounded cyclotomic/Aurifeuillean analysis and SNFS advice | [Expert laboratory](FACTOR_LAB.md) |
| Mersenne trial factoring | Searches \(q=2kp+1\) for prime exponents and every \(q=2kd+1\) order progression for odd composite exponents, without materializing \(M_p\) | [Mersenne numbers](MERSENNE.md) |
| Staged Mersenne factor hunt | Reconciles exact multiplicities and the cofactor in PARI/GP after bounded trial, P−1, P+1, and GMP-ECM stages | [Mersenne numbers](MERSENNE.md) |
| RSA Challenge catalogue | Identifies all 54 challenge values and independently checks recorded size, compositeness and published factors | [RSA Challenge](RSA_CHALLENGE.md) |
| GGNFS diagnostics | Discovers lattice sievers, rejects binaries that cannot execute on this CPU, and reports usable indices and hashes | [GGNFS sievers](SIEVERS.md) |
| Distributed sieving | Uses CADO's server/client model with explicit exposure review and a mandatory worker whitelist | [Distributed CADO-NFS](DISTRIBUTED.md) |
| Reproducibility | Saves commands, parameters, engine revisions and executable hashes beside a completed factorization | [Output reference](reference/output.md) |

## Prime Tools

Only one Prime Tools form is visible at a time. Search by a standard name such as
`Pocklington`, `Goldbach`, `Pell`, `Chebotarev`, or `Carmichael`; each operation also has
a bookmarkable `#primes/<tool>` route.

| Group | Pages | Included operations |
|---|---:|---|
| **Primality & navigation** | 10 | Single and batch primality; 56-class classification; nearby, interval, nth and counted primes; cross-checks; arbitrary-offset interval sieving |
| **Primality laboratories** | 15 | Certificate verification; eight-test comparison; deterministic Miller–Rabin bounds; Pocklington, Pratt, Proth, Lucas/Frobenius/Morrison and ECPP; pseudoprime and Carmichael analysis; covering sets; Lucas–Lehmer traces |
| **Prime generation** | 16 | Fixed-digit and structured primes; safe, Sophie Germain, Blum, congruence and NTT primes; progressions and random samples; perfect numbers and primorials; Proth, Chernick, repunit, Sierpiński/Riesel, bi-twin, ladder and constrained searches |
| **Patterns & distribution** | 6 | Consecutive gaps, twin/k-tuple patterns, Cunningham chains, gap statistics, density/residue summaries and Goldbach partitions |
| **Analytic prime distribution** | 16 | \(\pi(x)\) approximations, summatory functions, PNT convergence, nth-prime bounds, prime races, progression deviations, singular series, Hardy–Littlewood and Bateman–Horn predictions, maximal gaps, Maier matrices, density surfaces and algorithm comparisons |
| **Prime structures** | 7 | Exact reciprocal periods, circular/absolute and Paterson primes, full-reptend primes, Gaussian primes and modular wheels |
| **Arithmetic & factors** | 20 | Factor-strategy advice; arithmetic functions; divisor, aliquot, coprime, smoothness, record-number and weird-number structure; perfect powers; modular arithmetic; Miller–Rabin witnesses; Cornacchia; PARI predicates and factoring strategies |
| **Modular & polynomial algebra** | 16 | Legendre/Jacobi/Kronecker symbols, Tonelli–Shanks, CRT, modular and Hensel roots, discrete logarithms, unit groups, orders, power residues, p-adic valuations, polynomial/cyclotomic factorization, congruences and finite fields |
| **Algebraic primes** | 13 | Eisenstein primes; quadratic and general number fields; prime decomposition; Chebotarev experiments; binary quadratic forms and class groups; continued fractions and Pell equations |
| **Advanced explorations** | 6 | Prime pyramids, corrected related-number sequences, digit-substring primes, bounded equation searches, Euler's prime polynomial and palindrome-derived candidates |
| **Visualization & education** | 8 | Ulam/Sacks/polar spirals, Eisenstein lattices, modular wheels, residue heatmaps, gap timelines, prime-race animation, sieve traces and measured complexity views |

The [prime-classification catalogue](PRIME_CLASSIFICATION.md) defines all 56 classifier
results. The [prime-structure mathematics](mathematics/prime-structures.md) explains the
base-dependent, algebraic, reciprocal and constellation concepts that do not fit into a
single primality-test page.

## Zeta and L-function workspace

| Group | Pages | Included operations |
|---|---:|---|
| **Rigorous functions** | 5 | \(\zeta(s)\), Hardy \(Z(t)\), Riemann \(\xi\), Dirichlet \(\eta\), the functional equation and Stieltjes constants |
| **Zeros & Gram geometry** | 5 | Turing counts, certified critical-line zeros, Gram points and blocks, Gram-law exceptions and Backlund's \(S(T)\) remainder |
| **Explicit formulas & zero statistics** | 6 | Explicit-formula \(\pi(x)\), Chebyshev \(\psi(x)\), Riemann–Siegel remainder, Euler products, normalized spacings and pair correlation |
| **Dirichlet & Dedekind functions** | 4 | Dirichlet characters, \(L(s,\chi)\), exploratory L-zero searches and Dedekind zeta functions |
| **Exploratory plots** | 2 | Critical-line sampling and complex-plane heatmaps |

FLINT/Arb returns certified ball enclosures and drives certified zero isolation and
Turing counts. A plotted midpoint, a finite heatmap, pair-correlation data and an
L-function zero scan remain exploratory. See [zeta mathematics](mathematics/zeta.md) and
the [zeta guide](RIEMANN_ZETA.md).

## Workflow and data capabilities

- Import TXT, CSV and JSON batches; validate every item before queuing work.
- Save named workspaces and search factorization jobs and generated reports.
- Cache bounded, conclusive responses by operation, canonical parameters and engine
  revision; never cache a timeout as an answer.
- Set job priority, CPU count, memory and wall-clock limits; cancel, pause and resume
  supported job types.
- Export CSV, JSON, JSON Lines, Markdown, LaTeX and PARI-compatible data.
- Use the browser, the `numerisect` command, the in-process API client, or the HTTP API.
- Add declarative engine adapters without allowing shell interpolation or executable
  code in adapter files.

See [Application infrastructure](APPLICATION.md), the [CLI reference](reference/cli.md),
and the [API reference](reference/api.md).

## Result guarantees

| Label | Meaning |
|---|---|
| **Proven** | A theorem-backed deterministic criterion, a verified certificate, or a rigorous native proof settled the claim. |
| **Probable** | A strong probable-prime test passed; this is evidence, not a proof. |
| **Inconclusive** | The operation stopped without settling the claim. It must not be read as “no”. |
| **Exploratory** | A visualization, heuristic prediction, timing observation or midpoint sample intended for investigation rather than certification. |

Every successful Prime Tools calculation that persists output names its exact
`output/<filename>` path in the local result panel. Large native streams—such as a full
reciprocal repetend—go directly to the report rather than through Python, JSON or the DOM.

## What is deliberately outside scope

- Numerisect is not audited cryptographic software and must not generate production keys.
- It does not turn heuristic complexity estimates or conjectural prime-density formulas
  into predictions with guarantees.
- It does not expose the local process-launching API to a network interface; remote use
  belongs behind an SSH tunnel.
- It does not publish binary installers yet. The current release is installed from source.
- It does not silently substitute Python or JavaScript arithmetic when an engine is
  unavailable.

Those exclusions are part of the capability contract, not missing UI switches.
