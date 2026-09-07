# Zeta lab: explicit formulas, zero statistics, and L-functions

Numerisect 0.5.0 extends the Riemann-zeta workspace with twelve operations that
turn certified zeros into explicit-formula experiments, zero statistics, Gram
geometry, Dirichlet L-functions, and Dedekind zeta functions of bounded number
fields. See [Riemann zeta tools](RIEMANN_ZETA.md) for the ten original
operations; both sets share the `#zeta/...` workspace and result panel.

## The computation policy in one line

Numerisect is a user interface over existing number-theory libraries. Nothing
on this page is implemented in Python or JavaScript. Every mathematical value
comes from FLINT/Arb 3.4.0 or PARI/GP; the C helper
`numerisect/native/numerisect_zeta.c` exists only for the loops that no library
provides (explicit-formula sums over zeros, histogram binning, and rigorous
bisection), and it builds every one of those loops from FLINT primitives.
Python validates input, launches the engine, and parses tagged output.
JavaScript formats text and maps numbers to canvas coordinates.

## Which routine performs each computation

| Operation | Route | Engine routine that computes the result |
|---|---|---|
| Riemann's explicit formula: π(x) from the zeros | `POST /api/zeta/explicit-prime-count` | `acb_dirichlet_hardy_z_zeros` (zeros), `acb_hypgeom_ei` (`li(x^ρ)`), `arb_hypgeom_li` (principal term), `n_moebius_mu` (Möbius weights), `primecount` (exact π(x)) |
| Rebuild Chebyshev ψ(x) | `POST /api/zeta/chebyshev-psi` | `acb_dirichlet_hardy_z_zeros`, `acb_exp`/`acb_div` for `x^ρ/ρ`, FLINT `n_primes_t` sieve plus `arb_log_ui` for the exact ψ(x) |
| Riemann–Siegel remainder | `POST /api/zeta/riemann-siegel` | `acb_dirichlet_zeta_rs`, `acb_dirichlet_zeta_rs_bound`, `acb_dirichlet_zeta` |
| Euler-product comparison | `POST /api/zeta/euler-product` | `acb_pow` over FLINT's `n_primes_t` sieve, `acb_dirichlet_zeta`, `_acb_dirichlet_euler_product_real_ui` |
| Zero-spacing histogram | `POST /api/zeta/zero-spacing` | `acb_dirichlet_hardy_z_zeros`, `acb_dirichlet_hardy_theta` (unfolding), `arb_hypgeom_erf` (GUE surmise) |
| Pair correlation | `POST /api/zeta/pair-correlation` | `acb_dirichlet_hardy_z_zeros`, `acb_dirichlet_hardy_theta`, `arb_sin` for `1 − (sin πu/πu)²` |
| Gram blocks and exceptions | `POST /api/zeta/gram-blocks` | `acb_dirichlet_gram_point`, `acb_dirichlet_hardy_z` |
| Zero-counting remainder S(T) | `POST /api/zeta/backlund-s` | `acb_dirichlet_backlund_s`, `acb_dirichlet_backlund_s_bound`, `acb_dirichlet_zeta_nzeros`, `acb_dirichlet_hardy_theta` |
| Dirichlet character table | `POST /api/zeta/characters` | `dirichlet_group_init`, `dirichlet_char_next`, `dirichlet_conductor_char`, `dirichlet_parity_char`, `dirichlet_order_char` |
| Dirichlet L-functions L(s, χ) | `POST /api/zeta/l-function` | `acb_dirichlet_l`, `acb_dirichlet_l_hurwitz`, `acb_dirichlet_root_number`, `acb_dirichlet_gauss_sum` |
| Critical-line zeros of L(s, χ) | `POST /api/zeta/l-zeros` | `acb_dirichlet_hardy_z`, `acb_dirichlet_hardy_theta`, `acb_dirichlet_l` |
| Dedekind zeta of a number field | `POST /api/zeta/dedekind` | PARI/GP `nfinit`, `polcyclo`, `lfuncreate`, `lfuncheckfeq`, `lfun`, `lfunrootres`, `lfunzeros`, `bnfinit` |

FLINT/Arb has no Dedekind zeta implementation, which is why the last row is the
only one that leaves the C helper. It uses `numerisect/zeta_fields.gp` with
`numerisect/zeta_fields.py` as its boundary module.

## Certified versus exploratory

This distinction is enforced in the engine, repeated in the JSON `note`, and
shown in the result panel. Nothing here softens it.

**Certified** — a rigorous Arb ball enclosure or a decision that could only be
reached because an enclosure excluded zero:

- every zero ordinate returned by `acb_dirichlet_hardy_z_zeros`;
- `N(T)` from `acb_dirichlet_zeta_nzeros` (Turing method), reported as
  `inconclusive` rather than as a number when the enclosure fails to isolate a
  unique integer;
- `S(T)`, `θ(T)`, Gram points and `Z(gₙ)`;
- every Gram's-law verdict: a Gram point is called *good* or *bad* only when the
  enclosure of `(−1)ⁿZ(gₙ)` excludes zero, and otherwise *inconclusive*;
- every Riemann–Siegel row, because `acb_dirichlet_zeta_rs` folds its remainder
  bound into the returned ball;
- every Euler-product partial value, deviation, and truncation bound;
- every `L(s, χ)` value, cross-checked against an independent
  `acb_dirichlet_l_hurwitz` evaluation;
- every sign-change bracket for a real primitive character: the enclosures of
  `Z(t, χ)` at both endpoints are strictly of opposite sign, so the bracket
  provably contains a critical-line zero of odd order.

**Exploratory** — useful, but proving nothing:

- every π(x) and ψ(x) estimate, because the sum over zeros is truncated;
- every histogram and pair-correlation bin;
- the plotted `S(T)` trace (enclosure midpoints);
- `|L(½+it, χ)|` minima for complex characters;
- the smooth `θ(T,χ)/π` count, which is the Riemann–von Mangoldt main term, not
  a count;
- **all** PARI/GP output on the Dedekind page. PARI computes at a requested
  `realprecision` and returns floating-point numbers with no rigorous error
  bound. These are high-precision numerics, not Arb balls, and the page says so.

A certified sign-change count is a **lower** bound on the number of zeros in the
range: a coarse grid can step over a closely spaced pair. Raise the grid
resolution to raise the bound; nothing here claims completeness.

## Worked examples

### π(x) from Riemann's explicit formula

```bash
curl -sX POST 127.0.0.1:8765/api/zeta/explicit-prime-count \
  -H 'X-Numerisect-Token: <token>' -H 'content-type: application/json' \
  -d '{"bound":"100","zeros":200,"precision":30,"threads":8}'
```

The response reports the exact `π(100) = 25` from primecount and a convergence
table at N = 1, 2, 4, 8, … zeros. The estimate walks toward 25 as N grows; it
never becomes a certification, because the tail of the sum over zeros is
discarded. The one part of the formula that *is* bounded rigorously is the tail
integral `∫ₓ^∞ dt/(t(t²−1)log t)`, which the helper encloses in
`[0, log(x²/(x²−1))/(2 log x)]`.

### ψ(x) and the jumps at prime powers

`ψ(10) = 3·log 2 + 2·log 3 + log 5 + log 7 = 7.8320141805054689907…`, and the
exact value is a certified enclosure summed over the prime powers FLINT's sieve
enumerates. Increasing the zero count sharpens the oscillation around each
prime-power jump. The 8-digit approximation quoted in some references as
`ψ(10) ≈ 10.578` does not match the standard definition
`ψ(x) = Σ_{p^k ≤ x} log p`; Numerisect reports the engine's value.

### Gram's law and its first exception

Gram's law asserts `(−1)ⁿZ(gₙ) > 0`. It first fails at **n = 126**, where
`g₁₂₆ = 282.4547208234621746…` and `Z(g₁₂₆) = −0.0276294988571999…` although 126
is even. Scanning indices 120–131 reports exactly one exception and one Gram
block, `n = 125` of length 2 with pattern `gbg` — a good Gram point, one bad
interior point, then a good Gram point.

### Zeros of L(s, χ₋₄)

The character `χ_4(3, ·)` is the real primitive odd character of conductor 4.
`L(1, χ₋₄) = π/4 = 0.78539816339744830961566…` and the first critical-line zero
is at `t = 6.020948904697596654…`. Searching `0.5 ≤ t ≤ 30` on a 400-point grid
certifies ten sign changes against a smooth `θ(T,χ)/π` count of 9.497.

For a complex character such as `χ_5(2, ·)`, Hardy's `Z(t, χ)` is not real
valued, so the page switches to `MODE: magnitude-minima` and reports minima of
`|L(½+it, χ)|` as explicitly exploratory indicators.

### Dedekind zeta of ℚ(i)

```bash
curl -sX POST 127.0.0.1:8765/api/zeta/dedekind \
  -H 'X-Numerisect-Token: <token>' -H 'content-type: application/json' \
  -d '{"family":"quadratic","parameter":"-1","sigma":"2","zero_height":30}'
```

PARI reports degree 2, signature (0, 1), discriminant −4,
`ζ_K(2) = 1.50670300992298503088…` and a simple pole at s = 1 with residue
`π/4 = 0.785398163397448309615…`. With `class_data` enabled, `bnfinit` supplies
the class number, regulator, and torsion order, and the page compares the
residue with the analytic class number formula
`2^{r₁}(2π)^{r₂}hR / (w√|d|)`; the two agree to PARI's working precision.
Since `ζ_K = ζ · L(s, χ₋₄)` for this field, `lfunzeros` returns the union of the
zeta ordinates and the `χ₋₄` ordinates: 6.0209…, 10.2437…, 12.9880…, 14.1347…

`lfuncheckfeq` returns the base-2 logarithm of the functional-equation error; a
large negative value (−125 here) means the L-function object is consistent.

## Bounds, limits, and failure modes

| Limit | Value | Where enforced |
|---|---|---|
| Zeros in an explicit-formula sum | 5,000 | C helper |
| x for the exact ψ(x) | 10^7 | C helper (`chebyshev_psi_exact`) |
| x for π(x) | 10^12 | Python, then primecount |
| Riemann–Siegel ordinate | t ≥ 10 | C helper |
| Riemann–Siegel correction terms | 0 ≤ K ≤ 20 | C helper |
| Euler-product primes | 200,000 | C helper |
| Euler-product half-plane | Re(s) > 1, checked as a ball comparison | C helper |
| Zeros in a statistics run | 20,000 | C helper |
| Dirichlet modulus q | 100,000 | C helper |
| L-function zero search | primitive characters only | C helper |
| Number-field degree | 8 | `zeta_fields.MAX_DEGREE` |
| Field discriminant | 10^12 | `zeta_fields.MAX_DISCRIMINANT` |
| `lfunzeros` height | 200 | Python |
| PARI `realprecision` | 20–200 digits | Python |
| PARI wall clock | 1–3,600 s, default 300 s | Python |

Every one of these is a loud failure, never a quiet empty success:

- a FLINT time limit raises `ZetaEngineError` ("FLINT exceeded the selected
  N-second time limit") and the route answers `503`;
- a PARI error or timeout raises `ZetaEngineError` carrying PARI's own message
  (an out-of-range degree, a reducible polynomial, a non-squarefree radicand, or
  `s = 1`, the pole of every Dedekind zeta function);
- a row count that disagrees with the engine's `COUNT:` marker raises
  `ZetaEngineError`, so a partial run can never look like a complete one;
- input that fails validation raises `ValueError` and the route answers `422`.

## Rebuilding the helper

`numerisect/native/numerisect_zeta.c` is rebuilt automatically whenever it is
newer than `data/tools/bin/numerisect-zeta`; a failed build writes
`data/zeta-build.log`. The new subcommands are `explicit-pi`, `psi`,
`riemann-siegel`, `euler-product`, `zero-spacing`, `pair-correlation`,
`gram-blocks`, `backlund`, `characters`, `l-function`, and `l-zeros`. They
follow the existing tagged-output conventions (`REAL:`, `IMAG:`, `POINT:`,
`COUNT:`) and add `TERM:`, `RS:`, `EULER:`, `BIN:`, `GRAM:`, `EXCEPTION:`,
`BLOCK:`, `CHAR:`, `SIGN_CHANGE:`, and `MINIMUM:`.

Tests for this page live in `tests/test_zeta_lab.py` and assert published
constants: π(100) = 25, ψ(10) = 7.8320141805…, ζ(2) = 1.6449340668…, the first
zeta zero 14.134725141…, g₀ = 17.8455995404…, N(100) = 29, the Gram's-law
exception at n = 126, L(1, χ₋₄) = π/4, the first `χ₋₄` zero 6.0209489047…, and
`ζ_{ℚ(i)}(2) = 1.5067030099…`.
