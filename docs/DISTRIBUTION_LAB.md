# Analytic prime-distribution laboratory

Numerisect 0.7.0 adds eleven analytic prime-distribution pages backed by
`numerisect/distribution_lab.gp` and the `primecount` and `primesieve` engines.
`numerisect/distribution_lab.py` validates requests, starts the engines,
requires complete tagged output, parses it, and persists reports. It does not
evaluate a single mathematical quantity, and neither does the browser layer:
JavaScript converts the returned strings to canvas coordinates and colours and
nothing else.

Each operation has one Prime Tools route in the **Analytic prime distribution**
group, and its result appears directly below the submitted form together with
the exact `output/<filename>` path of the saved report.

## Which engine computes what

| Page | Route | Computation performed by |
|---|---|---|
| Approximation error (item 76) | `POST /api/distribution/approximation-error` | `primecount x` (exact π), `primecount --RiemannR`; PARI `eint1` for li(x), PARI for `x/log x` and every error term |
| PNT convergence (item 82) | `POST /api/distribution/pnt-convergence` | `primecount x`; PARI `eint1`, `log`, `sqrt` for ratios, error terms and sign tracking |
| n-th prime bounds (item 81) | `POST /api/distribution/nth-prime-bounds` | `primecount --nth-prime`; PARI evaluates the six published bounds at 60-digit precision |
| Prime race (item 83) | `POST /api/distribution/prime-race` | PARI `forprime` residue counting, `gcd`, `eint1` |
| Progression deviation (item 84) | `POST /api/distribution/progressions` | PARI `forprime`, `gcd`, `eint1` |
| Singular series (item 85) | `POST /api/distribution/singular-series` | PARI `forprime` and `Set` for the Euler product and admissibility |
| Constellation counts (item 86) | `POST /api/distribution/tuple-prediction` | `primesieve --count=k` for single-pattern constellations below 2⁶⁴; PARI `forprime` sliding window otherwise; PARI `intnum` for the prediction |
| Bateman–Horn (item 87) | `POST /api/distribution/bateman-horn` | PARI `polisirreducible`, `polrootsmod`, `intnum`, `isprime` |
| Record prime gaps (items 88–91) | `POST /api/distribution/maximal-gaps` | PARI `forprime`, `log`, `exp`, `Euler` |
| Maier matrix (item 92) | `POST /api/distribution/short-interval` | PARI `forprime`, `log` |
| Density surface (item 93) | `POST /api/distribution/density-surface` | PARI `forprime`, `gcd`, `log` |

`li(x)` is PARI's exponential integral: `li(x) = real(-eint1(-log x))`, the
Cauchy principal value of `∫₀ˣ dt/log t`. It is never approximated in Python.

## Approximation error and convergence (items 76 and 82)

Both pages take a log-spaced integer grid, described by two decimal exponents
and a point count (2–24 points, exponents 1–19). PARI generates the grid so
that Python never computes a grid point. `primecount` then returns exact `π(x)`
at each point, and PARI computes:

- `x/log x`, `li(x)`, and the signed and relative error of each against `π(x)`;
- `π(x)/(x/log x)` and `π(x)/li(x)`;
- the normalised error `(π(x) − li(x))·log x/√x`;
- the sign of `π(x) − li(x)` and every sign change visible on the grid.

`R(x)` is `primecount --RiemannR`, which returns a rounded integer, so the
`R(x)` error column is exact to within one unit. A grid samples finitely many
points: an absence of sign changes is never evidence that `π(x) − li(x)` keeps
its sign, and the result note says so. Littlewood proved the difference changes
sign infinitely often.

## Explicit n-th prime bounds (item 81)

Six published bounds are evaluated at 60-digit precision and compared with the
exact `p_n` from `primecount --nth-prime`. Each is reported with its own
validity range; a bound evaluated outside its range is marked *outside the
published validity range* rather than counted as a failure.

| Bound | Side | Valid for | Source |
|---|---|---|---|
| `n log n` | lower | `n ≥ 1` | Rosser (1939) |
| `n(log n + log log n − 3/2)` | lower | `n ≥ 2` | Rosser and Schoenfeld, *Approximate formulas for some functions of prime numbers*, Illinois J. Math. 6 (1962), (3.12) |
| `n(log n + log log n − 1/2)` | upper | `n ≥ 20` | Rosser and Schoenfeld (1962), (3.13) |
| `n(log n + log log n − 1)` | lower | `n ≥ 2` | Dusart, *The k-th prime is greater than k(ln k + ln ln k − 1) for k ≥ 2*, Math. Comp. 68 (1999), Theorem 3 |
| `n(log n + log log n − 1 + (log log n − 2.1)/log n)` | lower | `n ≥ 3` | Dusart, *Estimates of some functions over primes without R.H.* (2010), Proposition 5.15 |
| `n(log n + log log n − 1 + (log log n − 2)/log n)` | upper | `n ≥ 688383` | Dusart (2010), Proposition 5.15 |

These are theorems, not heuristics: within its stated range each inequality is
rigorous, and the page reports a violation only when one occurs inside a stated
range.

## Prime races and progressions (items 83 and 84)

One `forprime` pass counts every prime up to `x` by reduced residue class
modulo `q`. The race page reports counts at geometrically spaced checkpoints,
the leader at each checkpoint, and the number of lead changes visible at those
checkpoints — a lower bound, because the lead can change between samples. The
normalised bias is `(π(x; q, a) − li(x)/φ(q))·log x/√x`, the Rubinstein–Sarnak
scaling under which the Chebyshev bias is visible.

The progression page reports `π(x; q, a)` for every reduced class, the expected
`li(x)/φ(q)`, and the absolute, relative and `√x`-normalised deviation. The
expectation is the prime-number theorem for arithmetic progressions; the
deviations are observed, never predicted.

Documented caps: `q ≤ 5040`, `x ≤ 10^10`, at most 64 reduced residue classes
for a race and 128 for a progression table. A modulus with more classes is
refused as an engine error, never silently truncated.

## Hardy–Littlewood singular series (item 85)

For a pattern `H = {0 = h₁ < … < h_k}` the page computes

```
𝔖(H) = ∏_p (1 − w(p)/p) / (1 − 1/p)^k,   w(p) = #{h_i mod p}
```

truncated at a user-chosen cutoff `P` (100 … 10⁸). Admissibility is decided by
the same product: if `w(p) = p` for some prime, the pattern covers every residue
class modulo `p`, only finitely many translates can be all-prime, and `𝔖 = 0`.

**The truncation bound is rigorous.** For every prime above the pattern
diameter the offsets occupy `k` distinct residues, so the local factor is
`(1 − k/p)/(1 − 1/p)^k` and its logarithm is bounded in absolute value by
`(k/p)²` whenever `k/p ≤ 1/2`. Summing over `p > P` and using
`Σ_{n>P} 1/n² < 1/P` gives `|log tail| < k²/P`, so the printed value is correct
to the relative bound `exp(k²/P) − 1`. The page reports that bound and the
resulting enclosing interval. The value itself is labelled an **estimate**.

With `H = {0, 2}` and `P = 10⁶` the page returns `𝔖 = 1.3203237…`, which
matches twice the twin-prime constant `2·C₂ = 1.3203236316…` well inside the
stated bound of `4·10⁻⁶`.

## Predicted versus observed constellations (item 86)

The prediction is `𝔖(H)` times PARI's `intnum` evaluation of `∫ dt/(log t)^k`
over the requested range, and is an estimate. The observation is exact:

- `primesieve --count=k` counts the pattern when it is one of primesieve's
  single-pattern constellations — twins `(0,2)`, quadruplets `(0,2,6,8)`, and
  sextuplets `(0,4,6,10,12,16)` — and the range stays below `2⁶⁴`;
- otherwise PARI counts with a sliding window over `forprime` that visits each
  prime once and repeats no primality test. (primesieve's `-c3` and `-c5` mix
  two patterns each, so they cannot be compared with a single singular series.)

Both engines use the same convention: a constellation is counted when the whole
pattern lies inside the range. Below `10⁶` the page reports 8169 twin pairs and
1393 triplets of shape `(p, p+2, p+6)`.

## Bateman–Horn (item 87)

Given up to eight polynomials with ascending integer coefficients, PARI proves
each irreducible over `ℚ` with `polisirreducible` (a reducible polynomial is
refused, not silently accepted), counts `ω(p) = #{n mod p : ∏f_i(n) ≡ 0}` with
`polrootsmod` for every prime up to the cutoff, forms

```
C = (1/∏ deg f_i) · ∏_p (1 − ω(p)/p) / (1 − 1/p)^k
```

and predicts `C·∫ dt/(log t)^k`. The observed count tests every value with
`isprime` over a range of at most 10⁶ integers.

**The Bateman–Horn constant is an estimate with no rigorous truncation bound.**
Unlike the k-tuple singular series its local factors do not have `ω(p) = k` for
large `p`; they average to 1 only through equidistribution, so the truncation
error is conditional and no bound is claimed. Primes that divide every value of
the product are reported explicitly, because the prediction is then zero.

For `f(n) = n² + 1` the local product converges to `1.372…`, the Hardy–Littlewood
constant for `n² + 1`, and 6656 values of `n ≤ 10⁵` give a prime.

## Record prime gaps (items 88–91)

The search scans `[start, end]` with `forprime` and records every gap larger
than all earlier ones. It is bounded twice: by the range (`end ≤ 10^13`) and by
an explicit cap on the number of primes visited (100 … 10¹⁰). Reaching the cap
sets `TRUNCATED`, reports the prime to resume from, and marks the result
incomplete — never a proof that no larger gap exists. Progress checkpoints are
emitted during the scan and returned in the report.

For every record the page reports:

- the merit `g/log p`;
- the normalised Cramér–Shanks ratio `g/log²p`. Cramér (1936) conjectured
  `limsup g/log²p = 1`;
- the Granville comparison `g/(2e^{−γ} log²p)`. Granville (1995) argued the
  limsup is at least `2e^{−γ} = 1.1229…`;
- the Firoozbakht-implied bound `log²p − log p − 1`. Kourbatov (2015),
  *Verification of the Firoozbakht conjecture for primes up to four
  quintillion*, showed Firoozbakht's conjecture implies `g < log²p − log p − 1`
  for every `p > 29`; below that threshold the verdict is reported as outside
  the stated range.

The record gap of 34 after 1327 therefore has merit `4.7283454…`,
Cramér–Shanks ratio `0.6575661…`, Granville ratio `0.5855864…`, and satisfies
the Firoozbakht-implied bound.

### Published maximal-gap table (item 90)

`distribution_lab.gp` embeds every published maximal prime gap through
`4.3·10⁹` — 35 entries, comfortably beyond the `10⁹` verification target. The
source is OEIS **A002386** (the prime that begins each maximal gap) paired with
**A005250** (the gap itself), after Thomas R. Nicely's first-occurrence
prime-gap tables. GP performs the comparison and reports agreements and
mismatches; Python only relabels the verdicts.

Verification runs only when the scan starts at 2 with baseline 0, because
records inside a window that starts higher are records of that window and not
maximal gaps. Entries whose gap ends beyond the scanned prefix are skipped
rather than reported as mismatches. A scan to `10⁷` confirms all 22 published
entries in range.

## Maier-matrix short intervals (item 92)

Row `k` of the matrix is the interval `[qk + 1, qk + y]`. PARI counts the primes
in each row and compares them with the naive expectation `y/log(qk)`; the page
reports the per-row ratio and the mean, maximum and minimum across the matrix.
Choosing `q` as a primorial reproduces Maier's construction, in which short
intervals in rows coprime to `q` are systematically richer or poorer than
`y/log x` — the phenomenon behind Maier's theorem that
`π(x + (log x)^λ) − π(x) ∼ (log x)^{λ−1}` fails. The spread reported is
observed, not predicted. Caps: at most 512 rows of at most 10⁶ integers.

## Prime-density surface (item 93)

Every prime in `[start, end]` is binned by block position (up to 64 blocks) and
reduced residue class modulo `q` (`q ≤ 256`) in one `forprime` pass. The cell
value is the normalised density

```
count · φ(q) · log(block start) / block width
```

which tends to 1 under the prime-number theorem for arithmetic progressions.
JavaScript maps those numbers to a blue-to-amber heatmap in the same style as
the zeta heatmap and computes nothing else. The scan spans at most 10⁹
integers.

## Bounds, caps, and honesty rules

- Every search is bounded by documented caps and an engine time limit of at
  most 3,600 seconds. Exceeding a cap or timing out raises `PrimeEngineError`,
  which the API returns as HTTP 422 with no report written. It is never an
  empty successful result.
- Every GP call ends with a mandatory `DONE:` marker whose count must match the
  parsed rows; a partial run cannot look like a complete one.
- Figures that are estimates say so: the singular series, the Bateman–Horn
  constant, and every predicted count. Figures that are rigorous say what makes
  them rigorous: exact counts from `primecount`/`primesieve`/`forprime`, the
  `k²/P` singular-series tail bound, and the published `n`-th prime bounds
  inside their stated validity ranges.
