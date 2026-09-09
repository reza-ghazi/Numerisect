# Algebra laboratory

Numerisect 0.7.0 adds a modular, arithmetic, and algebraic workbench backed by
`numerisect/algebra_lab.gp`. The GP program is a driver over PARI's own routines;
`numerisect/algebra_lab.py` validates decimal inputs, renders them into a single GP
call, requires complete tagged output, parses it, and persists a report. Neither
Python nor JavaScript performs arithmetic on a mathematical quantity.

Every operation is reachable from Prime Tools, has one `POST /api/algebra/*` route,
and writes its report to `output/<filename>`, which the result panel displays.

## Which PARI/GP routine computes what

| Feature (roadmap item) | PARI/GP routines |
| --- | --- |
| Quadratic-reciprocity trace (45) | `kronecker` (cross-check), `valuation`, `gcd`, `isprime` |
| Linear/polynomial congruences (48) | `factor`, `polrootsmod`, `chinese`, `deriv`, `subst` |
| Discrete logarithms (50) | `znlog`, `znorder`, `factor`, `chinese` |
| Finite fields (57) | `ffinit`, `ffgen`, `fforder`, `ffprimroot`, `minpoly`, `polisirreducible` |
| Divisor enumeration and lattice (61) | `factor`, `divisors`, `sigma`, `numdiv`, `bigomega`, `isprime` |
| Smoothness and roughness (68) | `factor` |
| Divisor records (69) | `numdiv`, `sigma`, `nextprime`, `log` at 80 digits |
| Abundance and weird numbers (70) | `sigma`, `divisors`, `shift`/`bitor`/`bitand`/`bittest` |
| Amicable and sociable cycles (71) | `sigma` |
| Cornacchia (74) | `qfbsolve`, `qfbcornacchia`, `polrootsmod`, `issquare`, `sqrtint`, `fordiv` |
| Quadratic integer rings (110–111) | `core`, `quaddisc`, `quadgen`, `norm`, `trace`, `quadunit`, `quadclassunit`, `bnfinit`, `bnfcertify`, `kronecker`, `idealprimedec`, `bnfisprincipal`, `nfbasistoalg` |
| Number fields (112–113) | `nfinit` (`K.zk`, `K.disc`, `K.index`), `idealprimedec`, `idealfactor`, `nfeltnorm`, `polgalois`, `bnfinit`, `bnfcertify` |
| Chebotarev experiments (115) | `factormod`, `polgalois`, `nfsplitting`, `nfgaloisconj`, `permcycles`, `partitions` |

Three features deliberately write out an algorithm's steps, because displaying the
steps *is* the feature: the reciprocity reduction (45), the baby-step/giant-step,
Pohlig–Hellman, and Pollard-rho comparison (50), and the Cornacchia descent (74).
Each is cross-checked against the corresponding native routine — `kronecker`, a
re-exponentiation in the group, and `qfbsolve`/`qfbcornacchia` respectively.

Three computations have no library routine and are therefore built from PARI
primitives: all roots modulo `p^k` (PARI's `polrootspadic` returns only the
`p`-adically liftable roots and misses singular ones such as 3 and 5 for `x²−1`
modulo 8), the highly-composite candidate sieve, and the subset-sum decision behind
weirdness.

## Definitions and result semantics

### Quadratic reciprocity (45)

The trace reduces `(a/n)` by three rules: reduction of `a` modulo `n`, extraction of
the power of 2 through the supplementary law `(2/n) = (−1)^((n²−1)/8)`, and the
reciprocity flip `(a/n) = ±(n/a)` with the sign `−1` exactly when `a ≡ n ≡ 3 (mod 4)`.
`n` must be a positive odd integer. The result is a **Jacobi** symbol; it is also the
**Legendre** symbol, and therefore decides quadratic residuosity, only when `n` is an
odd prime. The response says which. The accumulated sign is compared with
`kronecker(a, n)` and a mismatch is an engine error, never a returned result.

### Congruences modulo a composite (48)

`P(x) ≡ 0 (mod m)` is solved by factoring `m`, finding the roots modulo each prime
with `polrootsmod`, lifting to `p^e` digit by digit (branching over all `p` residues
at a singular root, where `P'(r) ≡ 0`), and recombining with `chinese`. Every
returned residue is substituted back into `P`. If the singular branching exceeds the
result limit the response sets `complete: false` and the solution count reads
`inconclusive` — never `0`.

### Discrete logarithms (50)

Four selectable algorithms solve `g^x ≡ h (mod n)`: `bsgs`, `pohlig_hellman`,
`pollard_rho`, and `native` (PARI `znlog`). `g` and `h` must be units modulo `n`.
The `step_limit` bounds group operations (1 to 100,000,000). The `status` field is
three-way:

- `solved` — the exponent was found and verified by re-exponentiating;
- `no solution` — the search covered the entire cyclic subgroup `⟨g⟩`, so no
  logarithm exists;
- `inconclusive` — the step budget was exhausted first. This is not a proof of
  insolubility.

### Finite fields (57)

The field is `F_p` (`m = 1`) or `F_{p^m}`. Supply a reduction polynomial by ascending
coefficients, or leave it empty to use `ffinit`. A supplied polynomial must be monic
of degree exactly `m` and is checked with `polisirreducible`. Elements are given by
ascending coordinates in the power basis of the reduction polynomial's root, and all
results are reported in the same convention. Orders come from `fforder`, primitivity
means order `p^m − 1`, and the Frobenius column is `x ↦ x^p`. For `m = 1` the root of
the degree-one modulus can be 0, in which case its order is reported as
`not applicable`.

### Divisor enumeration and lattice (61)

Every divisor is listed with its cofactor (the factor pair `d · (n/d) = n`) and `Ω(d)`.
When the divisor count is at most the lattice cap, the covering relation `d ⋖ dp` of
the divisor lattice is enumerated as well; otherwise it is reported as not
enumerated. `τ(n)` and `σ(n)` are exact regardless of the display limit.

### Smoothness and roughness (68)

`|n|` is factored completely, so all four bounds are exact rather than estimated:
least prime factor (the roughness bound), largest prime factor (the smoothness
bound), largest prime power (the powersmoothness bound), and the `B`-smooth,
`B`-powersmooth, and `R`-rough verdicts, plus the `B`-smooth part and the remaining
rough part.

### Divisor records (69)

Four families are tested. Highly composite means a record `τ`; superabundant means a
record `σ(n)/n`; both are decided against an enumeration of all candidates with
non-increasing exponents over consecutive primes, which provably contains every
member of either family. Superior highly composite and colossally abundant are
decided from the feasibility of their defining `ε`-intervals, evaluated at 80 digits;
the answer is three-way (`yes` / `no` / `inconclusive`), and a feasible interval is
reported.

### Abundance and weird numbers (70)

Deficient, perfect, abundant, almost perfect (`s(n) = n − 1`), quasiperfect
(`s(n) = n + 1`), and multiperfect (`σ(n) = kn`) are exact divisor-sum tests. A
number is *semiperfect* when some subset of its proper divisors sums to `n`, and
*weird* when it is abundant but not semiperfect. Semiperfection is decided by an
exact bitset subset-sum over the proper divisors; a positive verdict returns a
witness subset when the reconstruction table fits in the configured bit budget, and
the witness is verified to sum to `n`. If the proper-divisor count exceeds the
subset cap, `semiperfect` and `weird` are `inconclusive`, not `no`.

### Amicable and sociable cycles (71)

The search iterates `s(n) = σ(n) − n` over an interval. A closed cycle of length 1 is
a perfect number, length 2 an amicable pair, and length ≥ 3 a sociable chain. A
trajectory that exceeds the term bound or the length cap is reported as
`inconclusive` and appears in the table with its last term; it is never treated as
evidence that no cycle exists. With `dedupe` on, each cycle is reported once from its
least member.

### Cornacchia (74)

For each square divisor `g²` of `n`, the square roots of `−d` modulo `m = n/g²` are
computed and the Euclidean descent is run down to `√m`; a candidate `(b, y)` is kept
when `m − b² = d·y²`. Every representation is verified to satisfy `x² + dy² = n`.
The complete solution set is then compared with `qfbsolve(Qfb(1,0,d), n, 3)`: both
sides are closed under the automorphism group of the form (`{±1}` in general, and
additionally the coordinate swap when `d = 1`, because `x² + y²` has an extra
symmetry) and compared **as sets**, so the check is independent of ordering and of
which representative either side lists. For prime `n` the primitive representation is
also compared with `qfbcornacchia`. `Total integer solutions` counts the closed-up
set. If the root enumeration exceeds the native cap, the search reports
`complete: false`.

### Quadratic integer rings (110–111)

For a nonsquare radicand `d`, `ω` is the generator of the maximal order (`√d` when
`d ≡ 2, 3 (mod 4)`, otherwise `(1+√d)/2`). The tool reports `N(a + bω)`,
`Tr(a + bω)`, whether the element is a unit (`|N| = 1`), whether it is a prime of the
ring (prime norm, or an associate of an inert rational prime), the roots of unity,
the fundamental unit for real fields, the class group, and the decomposition of a
rational prime `p` as split, inert, or ramified with an explicit generator for each
principal prime ideal. Class numbers are certified with `bnfcertify` inside the
configured budget; an exhausted budget makes the certification `inconclusive`, which
means the class number is conditional on the generalized Riemann hypothesis.

### Number fields (112–113)

A monic irreducible polynomial of degree 2 to 12 defines the field. `nfinit` builds
the maximal order and `idealprimedec` decomposes each requested rational prime, so
the ramification indices `e`, inertia degrees `f`, and ideal norms `p^f` are exact and
satisfy `Σ eᵢfᵢ = n`. Each prime is labelled ramified, inert, totally split, or
partially split by PARI. An optional element is given by ascending coordinates in the
power basis; its norm and ideal factorization come from `nfeltnorm` and `idealfactor`.
The class group is computed with `bnfinit` inside a budget; when the budget is
exhausted the class number reads `inconclusive` and the prime decomposition above it
is unaffected.

### Chebotarev density experiments (115)

For every unramified prime `p` below the bound, `factormod(f, p)` gives the multiset
of factor degrees, which is the cycle type of the Frobenius class. Chebotarev's
density theorem predicts that the proportion of primes with a given cycle type tends
to the relative size of the corresponding union of conjugacy classes in the Galois
group. For `S_n` and `A_n` the class sizes come from the closed-form cycle-type
identity, so no splitting field of degree `n!` is needed; otherwise `nfsplitting` and
`nfgaloisconj` produce the automorphisms and `permcycles` their cycle types, under a
time budget. **Observed densities are a finite experiment, not a proof.** When the
budget is exhausted the predicted columns read `inconclusive` while the observed
counts remain exact.

## Bounds

| Bound | Value |
| --- | --- |
| Engine timeout | 1 – 3,600 seconds |
| Trace and result limits | 0 – 100,000 rows |
| Congruence degree / coefficient size | 64 / 1,000 decimal digits |
| Congruence modulus | ≥ 2 |
| Discrete-log step budget | 1 – 100,000,000 group operations |
| Field characteristic / extension degree | `p < 2^64` / `1 ≤ m ≤ 16` |
| Finite-field exponent | −1,000,000 – 1,000,000 |
| Divisor rows / lattice cap | 1 – 100,000 / 0 – 20,000 |
| Record-sequence bound / rows per family | ≤ 10^18 / 1 – 10,000 |
| Weird subset cap / witness bits | 1 – 4,096 divisors / 0 – 2^31 |
| Sociable interval / cycle length | ≤ 10,000,000 integers / 1 – 1,000 |
| Number-field degree / coefficient size | 2 – 12 / 30 decimal digits |
| Rational primes per number-field request | 1 – 32 |
| Chebotarev degree / prime bound | 2 – 7 / 10 – 10,000,000 |
| Class-group and certification budgets | 1 – 3,600 seconds |

Limits shown in a form are resource controls, not mathematical claims. A display
limit never changes an exact count, and a truncated or budget-exhausted result says
so. Browser tables show at most 2,000 rows; the saved report retains every row the
native operation returned.

## API examples

All routes are loopback-only and require the per-process token from
`GET /api/session` in the `X-Numerisect-Token` header (or its cookie).

```bash
base=http://127.0.0.1:8765
token=$(curl -s $base/api/session | python3 -c 'import json,sys;print(json.load(sys.stdin)["request_token"])')
post() { curl -s -X POST "$base/api/algebra/$1" -H 'Content-Type: application/json' \
  -H "X-Numerisect-Token: $token" -d "$2"; }

# 45 - trace (30/101); the value is +1 and matches kronecker(30, 101)
post reciprocity '{"a": "30", "n": "101", "trace_limit": 1000}'

# 48 - x^2 + 1 = 0 (mod 65) has the four roots 8, 18, 47, 57
post congruence '{"coefficients": ["1", "0", "1"], "modulus": "65"}'

# 50 - 2^24 = 5 (mod 101), by baby-step/giant-step under a step budget
post discrete-log '{"target": "5", "base": "2", "modulus": "101",
                    "algorithm": "bsgs", "step_limit": 1000000}'

# 57 - arithmetic in F_8 = F_2[a]/(a^3 + a^2 + 1)
post finite-field '{"characteristic": "2", "degree": 3, "modulus_coefficients": [],
                    "a_coefficients": ["0", "1"], "b_coefficients": ["1", "1"],
                    "exponent": 5}'

# 61 - all 12 divisors of 60, sigma = 168, 20 covering edges
post divisor-lattice '{"number": "60", "divisor_limit": 10000, "lattice_cap": 1000}'

# 68 - 720 is 5-smooth but not 5-powersmooth (2^4 = 16 > 5)
post smoothness '{"number": "720", "smooth_bound": "5", "rough_bound": "3"}'

# 69 - 60 is highly composite, superabundant, superior highly composite, colossally abundant
post record-numbers '{"number": "60", "bound": "10000", "limit": 200}'

# 70 - 70 is the smallest weird number: abundant and not semiperfect
post weird-numbers '{"number": "70", "subset_cap": 512}'

# 71 - the amicable pair 220 / 284
post sociable '{"start": "200", "end": "300", "max_length": 12, "limit": 1000}'

# 74 - 101 = 10^2 + 1^2, cross-checked against qfbsolve and qfbcornacchia
post cornacchia '{"d": "1", "number": "101", "trace_limit": 1000}'

# 110-111 - 1 + 2i has norm 5 in Z[i], and 5 splits
post quadratic-ring '{"radicand": "-1", "a": "1", "b": "2", "prime": "5",
                      "certify_seconds": 10}'

# 112-113 - x^3 - x - 1: 23 ramifies, 59 splits completely, 2 and 3 are inert
post number-field '{"coefficients": ["-1", "-1", "0", "1"],
                    "primes": ["2", "3", "23", "59"],
                    "element_coefficients": ["1", "1"], "class_seconds": 10}'

# 115 - S3 densities 1/6, 1/2, 1/3 for x^3 - x - 1
post chebotarev '{"coefficients": ["-1", "-1", "0", "1"], "bound": "2000",
                  "group_seconds": 20}'
```

## Citations and references

- H. Cohen, *A Course in Computational Algebraic Number Theory*, Springer GTM 138 —
  Cornacchia (§1.5.2), baby-step/giant-step and Pohlig–Hellman (§5.4), Hensel lifting,
  and prime decomposition in number fields (§4.8, §6.2).
- S. Ramanujan, "Highly composite numbers", *Proc. London Math. Soc.* 14 (1915) —
  highly composite and superior highly composite numbers.
- L. Alaoglu and P. Erdős, "On highly composite and similar numbers",
  *Trans. Amer. Math. Soc.* 56 (1944) — colossally abundant numbers.
- S. J. Benkoski and P. Erdős, "On weird and pseudoperfect numbers",
  *Math. Comp.* 28 (1974) — 70 is the smallest weird number.
- P. Poulet, *La chasse aux nombres* (1918) — the sociable 5-cycle beginning 12496.
- N. Tschebotareff, "Die Bestimmung der Dichtigkeit einer Menge von Primzahlen …",
  *Math. Ann.* 95 (1926) — the density theorem.
- OEIS A002182 (highly composite), A004394 (superabundant), A002201 (superior highly
  composite), A004490 (colossally abundant), A006037 (weird), A063990 (amicable),
  A122726 (sociable).
- [PARI/GP arithmetic functions](https://pari.math.u-bordeaux.fr/dochtml/html-stable/Arithmetic_functions.html),
  [general number fields](https://pari.math.u-bordeaux.fr/dochtml/html-stable/General_number_fields.html),
  and [(Z/NZ)* and Dirichlet characters](https://pari.math.u-bordeaux.fr/dochtml/html/__backslashZslashNbackslashZ__star__and_Dirichlet_characters.html).

See [Roadmap status](ROADMAP_STATUS.md) for features that remain partial or deferred
rather than being represented by placeholder calculations.
