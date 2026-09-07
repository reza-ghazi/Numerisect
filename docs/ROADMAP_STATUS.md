# 150-item roadmap status

The 150-item feature proposal this file tracks is a roadmap, not a claim that every
research system can safely be
delivered in one pre-release. This file is the authoritative scope boundary: it records
what is implemented, what is partial and precisely what is missing from it, and what is
deferred. No deferred item is exposed as a placeholder, and nothing is replaced by
Python or JavaScript mathematics.

Every implemented operation is performed by an existing library routine (PARI/GP,
FLINT/Arb, YAFU, Msieve, CADO-NFS, GMP-ECM, primesieve, primecount) or, where no
library provides it, by an optimized C program in `numerisect/native/`. The governing
policy is stated in `CONTRIBUTING.md`, and `tests/test_native_computation_policy.py`
enforces it.

## Implemented

**Factorization.** 2, 3, 6, 9, 11–13, 15. Item 4 is complete for the algorithms this
YAFU build provides plus SQUFOF; item 5 is the resumable GMP-ECM campaign manager;
items 7 and 8 cover special-form recognition, SNFS suitability, and algebraic and
Aurifeuillean factors verified by division. Item 14 is implemented for 64-bit interval
enumeration and standard k-tuplets. Item 20 supplies headless access to every route.

**Primality and special primes.** 21–30, 31–36, 38–43. Deterministic Miller–Rabin
witness sets, Pocklington and Pratt certificates with independent verification, the
probable-prime taxonomy, the Carmichael analyzer, Sierpiński and Riesel covering sets,
bi-twin chains, and the provable constrained-prime generator.

**Modular arithmetic and structure.** 44–57, 58–60. Reciprocity traces, congruences over
composite moduli by Hensel lifting and CRT, four selectable discrete-logarithm
algorithms, and finite-field arithmetic over F_p and F_{p^m}.

**Arithmetic functions and integer structure.** 61–74. Divisor lattices, smoothness and
roughness, highly composite and colossally abundant families, a proven weird-number
subset check, amicable and sociable cycles, and Cornacchia with a step trace
cross-checked against `qfbcornacchia`.

**Algebraic primes.** 109–115. Quadratic rings with units and class numbers, general
number fields with prime-ideal decomposition, and Chebotarev density experiments.

**Visualization and education.** 117–126, 128, 130, with 116, 127 and 129 as noted below. Ulam, Sacks, and polar spirals, the
Eisenstein lattice, arbitrary-base modular wheels, residue heatmaps, gap timelines, the
prime-race animation, four sieve animations, the complexity dashboard, and the
educational proof viewer.

**Analytic prime distribution.** 75–93. Approximation-error and prime-number-theorem
convergence charts, nth-prime bounds cited with their validity ranges, prime races and
Chebyshev bias, progressions with expected-versus-observed counts, Hardy–Littlewood
singular series with a rigorous tail bound, constellation predictions, Bateman–Horn
estimates, maximal-gap search with merit and the Cramér, Granville and Firoozbakht
comparisons verified against the published table, Maier-matrix experiments, and a
two-parameter density surface.

**Zeta and L-functions.** 94–108, and 80. Explicit-formula prime counting from certified
zeros, Chebyshev psi reconstruction, Riemann–Siegel remainder analysis, Euler-product
comparison, zero-spacing histograms, pair correlation against the GUE prediction, Gram
blocks and Gram's-law exceptions, the Backlund S(T) remainder, Dirichlet characters and
L-functions with independent Hurwitz cross-checks, L-function zeros for GRH experiments,
and Dedekind zeta functions through PARI.

**Application and reproducibility.** 131–142, 144–150. Item 18 adds distributed
CADO-NFS sieving; read `docs/DISTRIBUTED.md` before enabling it, because CADO
authenticates clients by IP address only. Complete CLI/API parity, six
export formats, batch import, workspaces, searchable history, revision-keyed result
caching, job priorities and reordering, per-job resource limits, pause and resume,
desktop notifications, declarative engine adapters, performance history, client examples
in five languages, and notebook integration.

## Partially implemented

- **1 and 116** — the factor view shows the input, every factor with its exponent,
  primality status and discovering engine, and one total elapsed time. It renders as
  a flat root-plus-leaves list, not a hierarchy, and per-factor discovery time is not
  captured. Composite cofactors can be continued as linked child jobs, so the parent
  and child relationship exists in the data but is not drawn as a tree.
- **4** — every algorithm the installed YAFU build exposes is selectable
  (rho, p−1, p+1, ECM, SIQS, NFS, SNFS, Fermat, trial division) with expert parameter
  panels, and SQUFOF is supplied by `numerisect-squfof` because no installed library
  provides it. SQUFOF is limited to inputs below 2^62 by its 64-bit cycle; larger inputs
  are rejected explicitly rather than answered.
- **10** — cross-verification compares YAFU and Msieve factor multisets and rejects a
  disagreement. Comparing cofactors, per-engine primality conclusions, and per-engine
  timings side by side is not yet done.
- **13** — certificates are generated and independently verified for every prime factor
  of a completed job. Certifying a factor that is only a probable prime still depends on
  PARI proving it first.
- **14** — prime ranges and standard k-tuplets of sizes 2, 4 and 6 use primesieve.
  Sizes 3 and 5 stay on PARI: primesieve emits both admissible shapes together, and
  separating them would require offset arithmetic outside the engines.
- **17** — CADO-NFS parameters are exposed and stage progress is parsed from its log.
  Running an individual stage in isolation is not implemented.
- **29, 30, 37** — the taxonomy, Korselt analysis, and covering-set verification are
  complete within documented finite bounds; results beyond those bounds are
  inconclusive rather than negative.
- **69, 71** — record-number families and sociable cycles are enumerated within bounded
  searches; exceeding a bound is reported as inconclusive.
- **112–113** — splitting, inertia, ramification, and prime-ideal decomposition work for
  general number fields of bounded degree, with class-group work gated by a time budget.
- **127** — bounded educational step traces exist for Pollard rho, p−1, and ECM,
  computed by PARI/GP. Stage traces for the quadratic sieve and NFS are read from
  engine logs rather than instrumented.
- **129** — the engine decision tree is computed by PARI/GP and returned as an
  explicit decision path. It is rendered as a list, not yet as a diagram.
- **128** — the complexity table is cited literature and the timings are local
  measurements from this machine's job history, not a benchmark of the engines.
- **135** — job and report search covers text, status, engine, and date. There is no
  saved-query or faceted-search interface.

## Deferred, with no placeholder implementation

None. Every proposal item is now implemented, partial with its gap named, or declined
with the reasoning recorded below.

## Declined, by decision rather than omission

These were considered and deliberately not built. They are recorded here so the choice
is visible and can be revisited.

- **16, autotuning half — delivered in a narrower form.** `POST /api/factor-lab/tune`
  runs YAFU's own `tune`, which measures this machine's SIQS/NFS crossover, and reports
  the result as a suggested `NUMERISECT_CADO_THRESHOLD`. Numerisect never rewrites its
  own configuration. Using the engine's own tuning routine is what the native-computation
  policy requires; writing a separate tuner would have reimplemented it.
- **16, benchmarking half — declined.** Timing YAFU against Msieve, GMP-ECM and CADO on a
  fixed synthetic input set measures one machine on one day with one set of engine
  builds. It reads like a general fact about the engines and is not one, and it goes
  stale the moment an engine is rebuilt. The durable version already exists:
  `GET /api/history/performance` aggregates real job runtimes by engine and digit
  bucket, so the numbers come from work actually done.
- **19, FactorDB integration — declined.** The code would be cheap: the permissioned
  network path, the two-key opt-in and native verification of claimed factors already
  exist for OEIS and local catalogues. The objection is to what it does to the
  application's meaning. Numerisect's claim is that it computes locally and proves what
  it asserts; FactorDB is a database of unverified community claims, and consulting it
  turns "your machine factored this" into "someone once said this factors that way, and
  we checked the division." The submit direction is worse, because it publishes your
  work to a third party, and any such switch will eventually be flipped without thought.
  It also buys little: numbers FactorDB knows are usually ones these engines factor
  quickly anyway, and for numbers it does not know it says nothing. Local catalogue
  files under `STATE_DIR/catalogues` remain the supported way to use known-factor
  tables, entirely offline.
- **143, side-by-side engine comparison — declined.** The correctness half is already
  covered: `cross_verify` runs YAFU and Msieve independently and rejects a factor
  multiset disagreement. The timing half would present a single sample as a comparison,
  when the result is dominated by thread count and ECM luck. Engine choice is better
  served by the strategy adviser, which decides from digit count, algebraic form,
  small factors and completed ECM depth.

## Beyond the proposal

An audit compared what the installed engines expose against what the application calls,
and the following were added because they belong to the subject, not because the
proposal listed them.

**Exposing more of the installed libraries.** A prime-counting algorithm comparison
across Legendre, Meissel, Lehmer, Lagarias–Miller–Odlyzko, Deléglise–Rivat and Gourdon;
Legendre's phi(x, a) and the nth-prime inverse approximations; the integer-structure
predicates `isprimepower`, `ispowerful`, `istotient`, `isfundamental` and `ispolygonal`;
Lenstra's divisors in a residue class, with the hypotheses PARI does not itself check
enforced before the call; `factorint`'s strategy flags as a factoring-method comparison;
and a binary quadratic forms and continued fractions workbench covering reduction,
composition, class groups, reduced-form enumeration, representation, exact expansions of
quadratic irrationals, and Pell equations.

**Things no single engine can do.** Cross-engine verification computes the same quantity
by every independent method available and reports whether they agree: pi(x) from
primecount's six algorithms, primesieve's sieve and PARI's `primepi`; primality from
PARI's proof, PARI's Baillie–PSW and GMP's independent test. On disagreement it reports
every value and refuses to choose, because a majority of implementations sharing a bug is
what a vote would conceal. An engine self-test asks each installed engine questions whose
answers are published constants, each carrying a citation, so a miscompiled build is
caught before its output is trusted.

**A gap no library fills.** `numerisect_bigsieve.c` enumerates primes in an interval of
any magnitude. primesieve refuses inputs at or above 2^64 outright, and PARI's `forprime`
is single-threaded and roughly 130 times slower per window at 10^30. Results at or above
2^64 are labelled probable primes from Baillie–PSW, never proofs.

## Notes on scope and honesty

A search that reaches a documented bound, a test that times out, or a catalogue that has
no entry is reported as **inconclusive**. None of these is presented as a negative
result, and none is presented as a proof of primality.

Results are labelled by their strength. PARI `isprime` gives a proof; `ispseudoprime`
gives a probable prime and is labelled as such. FLINT/Arb ball enclosures, certified
zero intervals, and Turing-method counts are certified; plot samples use enclosure
midpoints and are exploratory. Externally supplied values are unverified until an engine
re-checks them.
