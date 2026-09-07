# Binary quadratic forms, continued fractions and Pell equations

Numerisect is a user interface over existing number-theory libraries. This page
documents the forms and continued-fraction workbench and, for each operation, names the
routine that performs the computation.

The mathematics lives in `numerisect/forms_lab.gp`, a driver over PARI/GP's own
routines. `numerisect/forms_lab.py` validates decimal inputs, renders them into a single
GP call, requires complete tagged output, parses it, and persists a report. Neither
Python nor JavaScript performs arithmetic on a mathematical quantity.

Every operation is reachable from Prime Tools under **Algebraic primes**, has one
`POST /api/forms/*` route, and writes its report to `output/<filename>`, which the
result panel displays.

## Which PARI/GP routine computes what

| Operation | PARI/GP routines |
| --- | --- |
| Reduce a form | `Qfb` (construction, and the discriminant validity check), `qfbred` (full reduction), `qfbred(f, 1)` (a single reduction step, which is what makes the trace and the indefinite cycle walk possible), `qfbredsl2` (the SL(2, ℤ) matrix), `matdet`, `quaddisc`, `isfundamental`, `sqrtint`, `gcd` |
| Compose and exponentiate | `qfbcomp`, `qfbcompraw`, `qfbpow`, `qfbpowraw`, `qfbprimeform(D, 1)` for the principal form, `qfbred` |
| Prime form of a discriminant | `qfbprimeform`, `qfbred`, `kronecker`, `isprime` |
| Class number and class group | `qfbclassno` (Shanks) cross-checked against `quadclassunit` (structure, generators, regulator), `qfbhclassno` (Hurwitz class number, `D < 0`), `quadunit` (norm of the fundamental unit, `D > 0`) |
| Enumerate reduced forms | `quadclassunit` (class-group generators and cyclic structure), `qfbpow` and `qfbcomp` (class representatives), `qfbred` and `qfbred(f, 1)` (the reduced form, or the whole cycle when `D > 0`), `issquare` |
| Represent an integer by a form | `qfbsolve` flag 1 (primitive solutions) and flag 3 (all solutions), `gcd` |
| Continued fractions | `contfrac` (rational expansions, and the floating-point cross-check for quadratic irrationals), `contfracpnqn` (convergents), `bestappr` (best rational approximation), `sqrtint`, `issquare` |
| Pell's equation | `quadunit` (the fundamental unit of the order of discriminant `4d` **is** the fundamental solution), `norm` (which decides whether the negative Pell equation is solvable), `quadregulator`, `quadgen`, `bestappr` (cross-check against the convergent), `issquare` |

Two computations have no library routine and are therefore built from PARI primitives,
exactly as the Hensel lift is in `docs/ALGEBRA_LAB.md`:

* **The exact continued-fraction expansion of a quadratic irrational.** PARI's `contfrac`
  takes a `t_REAL`, so it returns a floating-point expansion whose tail is unreliable —
  at the default 38 digits `contfrac(sqrt(13))` ends in a spurious `7` — and it reports no
  period at all. The classical `(P, Q)` recursion in the GP program is exact integer
  arithmetic with `sqrtint`, it detects the period by state repetition rather than by
  guessing, and its emitted prefix is cross-checked term by term against `contfrac` at
  raised precision. A disagreement is an engine error, never a returned result.
* **Enumeration of the reduced forms of a discriminant.** PARI exposes the class group
  (`quadclassunit`) and the reduction operators (`qfbred`, `qfbred(f, 1)`) but no routine
  that lists reduced forms. The enumeration is therefore driven entirely by those
  routines: class representatives come from the `quadclassunit` generators through
  `qfbpow`/`qfbcomp`, and for a positive discriminant each class is expanded into its
  cycle by repeated single-step `qfbred`.

`contfracinit`, `contfraceval` and `bestapprPade` are deliberately not used here: they
compute continued-fraction *limits* of power series and Padé approximants of rational
functions, which is a different subject from the arithmetic continued fractions on this
page.

## What counts as a discriminant

An integer `D` is a discriminant when `D ≠ 0` and `D ≡ 0` or `1 (mod 4)`. Every other
integer is rejected with that explanation rather than an engine error. A **square**
discriminant is rejected too: the form then factors over ℚ and PARI's `Qfb` refuses it.

Note that `b² − 4ac` is automatically `0` or `1 (mod 4)` for integer coefficients, so the
congruence rejection is reachable only from the tools that take a discriminant directly
— prime forms, class group, reduced forms.

Every report states which case it is in, because definite and indefinite forms behave
differently under reduction:

* **`D < 0` — positive definite forms.** `Qfb(a, b, c)` requires `a > 0`; PARI does not
  implement negative definite forms, and the request is refused with that message.
  Reduction is `|b| ≤ a ≤ c` with `b ≥ 0` at either boundary, and **each class contains
  exactly one reduced form**. Class number, class-group structure, and the Hurwitz class
  number `H(−D)` from `qfbhclassno` are reported.
* **`D > 0` — indefinite forms.** Reduction has no unique fixed point: **each class is a
  periodic cycle of reduced forms**, walked here with single-step `qfbred`. The report
  gives the cycle length, the regulator, and the norm of the fundamental unit. A
  principality test therefore has to search the principal cycle, and an exhausted cycle
  cap reads `inconclusive` rather than `no`.

`quadclassunit` assumes the generalized Riemann hypothesis for the bound on the
generators it uses; the report says so, and the two class numbers from `qfbclassno` and
`quadclassunit` are compared, with a disagreement raised as an engine error.

## Ambiguous forms and the link to SQUFOF

A form is **ambiguous** when `a | b` or `a = c`. In the first case the substitution
`(x, y) ↦ (x − (b/a)y, y)` and in the second `(x, y) ↦ (−y, x)` carries `(a, b, c)` to
`(a, −b, c)`, so the class is its own inverse. The enumeration tool flags every ambiguous
reduced form, and separately flags the forms whose `|a|` is a perfect square.

This is the historical heart of SQUFOF, documented in
[the factorization laboratory](FACTOR_LAB.md). **SQUFOF walks the principal cycle of
forms of discriminant `4kN` looking for an ambiguous form**: the leading coefficient of
an ambiguous form in that cycle exposes a factor of `N`. Running the enumeration on
`D = 4N` shows exactly what the C helper searches.

Worked example, `N = 1817 = 23 × 79`, so `D = 7268`:

```bash
curl --cookie jar --header 'Content-Type: application/json' \
  --data '{"discriminant":"7268"}' \
  http://127.0.0.1:8765/api/forms/reduced-forms
```

The principal cycle has 28 reduced forms and contains `Qfb(23, 46, −56)`. Here `23`
divides `46`, so the form is ambiguous, and `23` is precisely the factor of `1817` that
SQUFOF extracts. Numerisect's forms lab **shows** this cycle; it does not factor with it.
Use `POST /api/factor-lab/squfof` for the factoring implementation itself.

## Continued fractions, Pell, and the link to CFRAC

The continued-fraction tool takes either a rational `p/q` or a quadratic irrational
`(p + √d)/q`, with `d` a positive non-square. It reports the partial quotients, the
convergents `pₙ/qₙ` from `contfracpnqn`, the preperiod and period, and the best rational
approximation below a denominator bound from `bestappr`.

For `√d` itself the period is `[a₁, …, a_{L−1}, 2a₀]` and the head `[a₁, …, a_{L−1}]` is
palindromic; the report carries a flag for that classical structure and marks it
"not applicable" for any other surd. The convergent at the end of the period solves
Pell's equation, which is why `bestappr(sqrt(13), 1000)` returns `649/180`.

Pell's equation `x² − dy² = 1` is solved from the fundamental unit, not by search.
`quadunit(4d)` is the fundamental unit `x + y√d` of the order ℤ[√d] of discriminant
`4d`, so it *is* the fundamental solution of `x² − dy² = norm(u)`:

* `norm(u) = −1` — the negative Pell equation `x² − dy² = −1` is solvable, with `(x, y)`
  the unit's own coordinates, and the fundamental solution of `x² − dy² = 1` is the
  square of the unit. For `d = 13` the unit is `18 + 5√13` of norm `−1`, and squaring it
  gives `(649, 180)`.
* `norm(u) = +1` — the negative equation has **no** solution, and the unit is already the
  fundamental Pell solution. For `d = 3` the unit is `2 + √3` and the fundamental
  solution is `(2, 1)`.

Further solutions are the powers of the fundamental one. Every pair is verified as
`x² − dy² = 1` inside PARI/GP, and `bestappr` independently confirms that the fundamental
solution is the convergent of `√d` at the end of its period. `quadregulator(4d)` is the
logarithm of the same unit.

**CFRAC** builds congruences of squares out of exactly these convergents of `√N`: the
quantity `Qₙ = pₙ² − N qₙ²` is small, and smooth values of it are combined into a
congruence `x² ≡ y² (mod N)`. **Numerisect does not implement CFRAC as a factoring
method.** SIQS supersedes it at every size — the self-initializing quadratic sieve finds
smooth relations far faster than the continued-fraction recursion can supply them — and
Factor Lab routes those inputs to SIQS through YAFU. The tools on this page are
exposition of where the idea came from, not a factoring path.

## Bounds, and what "inconclusive" means

Every operation is bounded, and exceeding a bound is reported as inconclusive: a period
or cycle length reads `inconclusive`, `complete` is `false`, or the row list is marked
truncated. It never degrades into a wrong or silently shortened answer.

| Bound | Value |
| --- | --- |
| Engine timeout | 1 to 3,600 seconds |
| Form coefficients and representation targets | 200 decimal digits |
| Discriminant | 40 decimal digits |
| Reduction-trace steps | 0 to 100,000 |
| Cycle walk | 1 to 1,000,000 single reduction steps |
| Class-group generators listed | 1 to 64 |
| Reduced forms enumerated | 1 to 100,000 |
| Primes per prime-form request | 1 to 64 |
| Composition exponent | \|e\| ≤ 10⁶; the unreduced power is offered only for \|e\| ≤ 1,000 |
| Class-order search | 1 to 100,000 exponentiations |
| Partial quotients | 1 to 100,000 |
| Convergents returned | 1 to 100,000 |
| Pell solutions | 1 to 100, each capped at 100,000 decimal digits |
| `quadunit` budget | 1 to 3,600 seconds |

Concretely: expanding `√13` with a quotient limit of 3 cannot close the period, so the
period reads `inconclusive` and `complete` is `false` — it does not report a shorter
period. Enumerating the reduced forms of `−47` with a form limit of 2 returns a prefix
with `Enumeration complete: no`. Walking the cycle of an indefinite form with too small a
cycle limit reports the cycle length as `inconclusive`. If `quadunit` exceeds its budget
the Pell report says so and claims no solution.

## Routes

```text
POST /api/forms/reduce              reduce a form, trace the steps, give the SL(2, ℤ) matrix
POST /api/forms/compose             qfbcomp / qfbcompraw / qfbpow / qfbpowraw, principality, order
POST /api/forms/prime-form          qfbprimeform for each requested prime
POST /api/forms/class-group         class number, structure, generators, regulator, H(−D)
POST /api/forms/reduced-forms       enumerate reduced forms; flag ambiguous and square forms
POST /api/forms/represent           qfbsolve: represent an integer by the form
POST /api/forms/continued-fraction  expansion, period, convergents, best approximation
POST /api/forms/pell                fundamental solution and further solutions
```

Example:

```bash
curl --cookie jar --header 'Content-Type: application/json' \
  --data '{"d":"61","solution_count":1}' \
  http://127.0.0.1:8765/api/forms/pell
```

## Verified reference values

`tests/test_forms_lab.py` pins these against the literature:

| Value | Result |
| --- | --- |
| `h(−23)` | 3, class group ℤ/3 generated by `Qfb(2, 1, 3)` |
| `h(−163)` | 1, the largest Heegner discriminant |
| `h(−47)` | 5 reduced forms, principal `Qfb(1, 1, 12)` |
| Principal form of `D = −23` | `Qfb(1, 1, 6)`, and `Qfb(2, 1, 3)³` returns it |
| `qfbprimeform(−23, 2)` | `Qfb(2, 1, 3)` |
| `x² + 3y² = 1729` | 8 primitive solutions including `(23, −20)` and `(31, 16)` |
| `√13` | period `[1, 1, 1, 1, 6]`, preperiod 1, palindromic head |
| `x² − 13y² = 1` | `(649, 180)`; the negative equation is solvable with `(18, 5)` |
| `x² − 61y² = 1` | `(1766319049, 226153980)`, period of `√61` is 11 |
| `x² − 3y² = −1` | unsolvable; the unit `2 + √3` has norm `+1` |
| `D = 7268 = 4 · 1817` | principal cycle of 28 forms containing the ambiguous `Qfb(23, 46, −56)` |
