# Prime-counting comparison and integer-structure laboratory

Two features share one module pair, `numerisect/counting_lab.py` and
`numerisect/counting_lab.gp`:

1. a **prime-counting algorithm comparison** that runs several independent
   implementations of π(x) on one input and reports any disagreement, and
2. **integer-structure predicates** — the PARI routines that answer structural
   questions about a single integer, plus a comparison of `factorint`'s
   strategy masks.

`counting_lab.py` validates requests, launches the engines, requires complete
tagged output, parses it and persists reports. It does not evaluate a single
mathematical quantity, and neither does the browser layer.

Each operation has one Prime Tools route: the three counting pages in the
**Analytic prime distribution** group and the three structure pages in the
**Arithmetic & factors** group. Every result appears directly below the
submitted form together with the exact `output/<filename>` path of the saved
report.

!!! note "double-check is not a seventh algorithm"

    `primecount --double-check` reruns the **default** algorithm with different alpha
    tuning. It is a self-consistency check on one implementation, not an independent
    one, and the response counts it separately so the independence claim is not
    inflated.

## Which routine computes what

| Page | Route | Computation performed by |
|---|---|---|
| Algorithm cross-check | `POST /api/counting/algorithm-comparison` | `primecount x --legendre`, `--meissel`, `--lehmer`, `--lmo`, `--deleglise-rivat`, `--gourdon`, `--double-check`; PARI/GP `primepi`; PARI `Set`, `vecmin`, `vecmax` for the agreement analysis |
| Legendre partial sieve | `POST /api/counting/phi` | `primecount --phi <x> <a>`; PARI `prime`, `forprime`, `primepi` |
| Inverse approximations | `POST /api/counting/nth-prime-inverses` | `primecount n --nth-prime`, `--Li-inverse`, `--RiemannR-inverse`; PARI for every error term at 60-digit precision |
| Integer structure | `POST /api/structure/predicates` | PARI `isprimepower`, `ispseudoprimepower`, `ispowerful`, `istotient`, `isfundamental`, `ispolygonal` |
| Divisors in a residue class | `POST /api/structure/lenstra-divisors` | PARI `divisorslenstra`, `gcd`, `numdiv`, `isprime` |
| factorint strategy masks | `POST /api/structure/factorint-strategies` | PARI `factorint(n, flag)`, timed by PARI `gettime`, audited by PARI `isprime` |

The extended **Integer arithmetic profile**
(`POST /api/primes/integer-profile`, `prime_structures.gp`,
`ps_integer_profile`) gained four of the same predicates:
`isprimepower`, `ispowerful`, `istotient` and `isfundamental`. They are
computed by the identical PARI routines listed above.

## Feature 1 — the algorithm comparison

### Why agreement is the point

primecount ships six independent prime-counting algorithms. They are not
variations on one implementation: Legendre's formula, Meissel's refinement,
Lehmer's extension, Lagarias–Miller–Odlyzko, Deléglise–Rivat and Gourdon's
method are different mathematics with different code paths, different sieving
structure and different complexity. PARI/GP's `primepi` is a seventh
implementation that shares no code with any of them.

A single algorithm cannot check itself. Running several on one x and finding
that they return the same integer is an independent correctness check — of the
installed binaries, of this machine, and of the request — that no single run can
provide. That is what this page is for; the timings are a by-product.

So the report never resolves a disagreement. If two sources differ, the page
says `NO — SOURCES DISAGREE`, prefixes the note with `DISAGREEMENT:`, prints
every distinct value with the number of sources reporting it, and shows each
source's signed difference from the consensus. The consensus is labelled a
consensus, not an answer.

### What each option does

| Selector | primecount option | Notes |
|---|---|---|
| Legendre's formula | `--legendre` | The original combinatorial method; the slowest of the six |
| Meissel's formula | `--meissel` | Legendre with the second partial sieve function |
| Lehmer's formula | `--lehmer` | Meissel extended one term further |
| Lagarias–Miller–Odlyzko | `--lmo` | The first sub-`x` combinatorial method |
| Deléglise–Rivat | `--deleglise-rivat` | Alpha-tuned refinement of LMO |
| Gourdon | `--gourdon` | primecount's default algorithm |
| Add `--double-check` | `--double-check` | Recomputes π(x) with alternative alpha tuning factors, so the default algorithm verifies its own first result under a different parameterisation |
| Add PARI/GP `primepi` | — | The seventh, engine-independent source |

### Bounds

* `1 ≤ x ≤ 10^31` — primecount's own documented ceiling for exact π(x).
* `x ≤ 10^16` whenever Legendre's, Meissel's or Lehmer's formula is selected.
  They remain interactive to that point; above it a comparison would silently
  become a multi-hour run, so the request is refused instead.
* PARI/GP `primepi` is used only while `x ≤ 10^11` (`PARI_PRIMEPI_LIMIT`).
  `primepi` sieves, and 10^11 costs roughly six seconds on the development
  machine and grows linearly from there. Above that bound the page reports the
  seventh source as *out of range above 10^11* rather than attempting it.
* `1 ≤ threads ≤ 256`, `1 ≤ time limit ≤ 3600` seconds.

### Timings are local measurements

Every elapsed time on these pages is **a single measurement of one run on the
machine that served the request**, taken by primecount's own `--time` option and
by PARI's `gettime`. It reflects that input, that hardware, that thread count
and that build. It is not a benchmark of the algorithms, it is not an average,
and it must not be quoted as a comparison of their asymptotic behaviour. The
column heading, the note attached to every report and the form itself all say
so.

### Legendre's φ(x, a)

φ(x, a) counts the integers in [1, x] divisible by none of the first a primes.
It is the partial sieve at the heart of Legendre's, Meissel's and Lehmer's
formulas, and `primecount --phi <x> <a>` computes it directly.

PARI adds the context that makes the number readable:

* `prime(a)` and `prime(a + 1)`, the a-th and next prime;
* the Legendre product `x · ∏_{p ≤ p_a} (1 − 1/p)`, which φ approximates, via
  `forprime`;
* and, **only when `x < p_(a+1)²`**, the exact identity

      π(x) = φ(x, a) + a − 1

  checked against PARI `primepi`. Inside that window every integer counted by
  φ above 1 is prime, because a composite surviving the sieve would need two
  prime factors greater than `p_a`. Outside it the identity is reported as
  inapplicable; it is never approximated or quietly dropped.

Worked example: φ(900, 10) = 145, p_10 = 29, p_11 = 31 and 900 < 961, so
π(900) = 145 + 10 − 1 = 154, which is what `primepi(900)` returns. By contrast
φ(10^6, 10) = 157939 falls outside the window and only the Legendre product
(157947.223…) is reported beside it.

### Inverse approximations to the n-th prime

`primecount n --nth-prime` gives the exact n-th prime. `--Li-inverse` inverts
the Eulerian logarithmic integral and `--RiemannR-inverse` inverts the Riemann R
function; both estimate the same value. PARI computes every signed and relative
error at 60-digit precision and selects the closer estimate, which is normally
`R⁻¹`.

For n = 10^6 the exact value is 15485863, `Li⁻¹` gives 15479083 (−6780) and
`R⁻¹` gives 15484039 (−1824). Bound: `1 ≤ n ≤ 10^16`.

## Feature 2 — integer structure

### The predicates

| Routine | Question | What the report adds |
|---|---|---|
| `isprimepower(n, &p)` | is n = pᵏ for a prime p? | the exponent k — the routine returns it, so the page shows `n = p^k` rather than a bare yes |
| `ispseudoprimepower(n, &p)` | the same test with a pseudo-prime base | the exponent and base |
| `ispowerful(n)` | is every prime valuation of n at least 2? | — |
| `istotient(n, &m)` | is n = φ(m) solvable? | a witness m |
| `isfundamental(n)` | is n a fundamental discriminant? | applies to the signed n |
| `ispolygonal(n, s, &N)` | is n the N-th s-gonal number? | the index N |

Known values used in the tests: `isprimepower(1024) = 10` (base 2),
`ispowerful(72)` is true (72 = 2³·3²), `istotient(96)` is true,
`isfundamental(−23)` is true, `ispolygonal(36, 3)` is true with index 8 and
`ispolygonal(35, 3)` is false.

Negative and zero inputs are meaningful only for `isfundamental`; the remaining
predicates report *no* for them rather than raising. Bounds:
`|n| < 10^2000` and `3 ≤ s ≤ 1,000,000`.

Four of these — `isprimepower`, `ispowerful`, `istotient` and `isfundamental` —
were also added to the existing **Integer arithmetic profile** page and its
saved report, where they sit naturally beside ω, Ω, τ, σ, φ, λ, μ and rad.

### Divisors in a residue class

`divisorslenstra(N, r, s)` is Lenstra's algorithm for every divisor d of N with
`d ≡ r (mod s)`. It is genuinely factoring-adjacent: it finds divisors without
factoring N.

The algorithm is correct **only** when `gcd(r, s) = 1` and `s³ > N`. PARI does
not enforce either hypothesis — `divisorslenstra(1000, 1, 3)` returns `[1, 1000]`
and omits 10, 25, 40, 100 and 250 — so `counting_lab.gp` checks both and refuses
the request instead of returning a silently incomplete list. A request with
`gcd(r, s) > 1` is refused for the same reason. Bounds:
`1 ≤ N < 10^200`, `2 ≤ s < 10^100`, `0 ≤ r < s`.

### factorint strategy masks

The second argument of PARI's `factorint` is a bitmask of methods to **avoid**:

| Flag | Disables |
|---|---|
| `1` | MPQS, the multiple-polynomial quadratic sieve |
| `2` | the first-stage ECM (PARI may still fall back on ECM later in the run) |
| `4` | Pollard–Brent rho **and** Shanks SQUFOF |
| `8` | the final ECM; after this a huge composite may be **declared prime** |

Flag `0` is the full default strategy: trial division, Pollard–Brent rho,
Shanks SQUFOF, ECM and MPQS. Flags combine, so `3` avoids both MPQS and the
first-stage ECM; the page accepts any mask in `[0, 15]`.

Running one input under several masks is a PARI-side comparison of factoring
methods for free. PARI's own `gettime` measures each run, and `isprime` audits
every returned base — which is the only way to see what flag `8` gave up, since
skipping the final ECM can leave a composite in the "prime" column. The report
therefore carries both a *product equals n* column and an *every base certified
prime* column, and they can disagree.

**On SQUFOF.** PARI implements Shanks' square forms factorization internally,
inside `factorint`, but exposes no standalone entry point for it: there is no
`squfof()` in the GP language. Flag `4` is the only handle on it, and it turns
SQUFOF off together with Pollard–Brent rho, so the two cannot be separated from
GP. This is why `numerisect/native/numerisect_squfof.c` exists as a separate C
program: a standalone SQUFOF is absent from every installed engine.

Bound: `2 ≤ n < 10^80`. A large semiprime under mask `1` can be slow by design —
that is the comparison — so the time limit (default 900 s, maximum 3600 s)
applies to the whole race.

## Reports

Every route saves a plain-text report with `save_prime_output` and returns
`output/<filename>`. The report carries the note, the metrics, the main table
and any extra sections — the distinct π(x) values for the comparison, and the
per-mask factor bases for the strategy race.

## Tests

`tests/test_counting_lab.py` covers each operation against published constants
(π(10^10) = 455052511, π(10^6) = 78498, φ(10^6, 10) = 157939 and the predicate
values listed above), invalid input for every entry point, an engine-missing
path that reports rather than approximates, `requires("primecount")` skips for
the tests that need the optional engine, and a fabricated disagreement injected
at the engine boundary to prove the mismatch is reported rather than outvoted.
