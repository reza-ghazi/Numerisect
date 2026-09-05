# Arithmetic and distribution tools

The source-tree audit covered the unfamiliar source code, notebooks, and Markdown
material in the supplied `prime_numbers` tree. Generated plots, cached bytecode,
virtual environments, copied data sets, PDFs, and URL shortcuts were treated as
artifacts rather than implementations. Files already imported in earlier passes
were deliberately not reread.

Most remaining programs were slower duplicates of Numerisect's existing native
primality, sieve, factorization, gap, tuple, reciprocal, and classification
tools. The useful non-duplicate ideas were consolidated into eight PARI/GP-backed
features. Python validates requests and parses tagged output; JavaScript renders
the results and charts. Neither layer performs the number-theory calculation.

## Finding these operations

Use **Arithmetic & factors** for integer profiles (`/#primes/integer-profile`),
coprimes (`/#primes/coprime-profile`), factor counts
(`/#primes/factor-count-distribution`), and the indicator constant
(`/#primes/prime-constant`). **Patterns & distribution** contains prime density
(`/#primes/prime-distribution`); **Prime generation** contains digit constraints
(`/#primes/digit-constrained`); **Advanced explorations** contains polynomials
(`/#primes/prime-polynomial`) and palindrome-derived values
(`/#primes/palindrome-derived`). Each page displays only its own operation.

A subsequent feature audit added batch primality, deterministic residue-class
searches, and prime-modulus arithmetic. See [Prime manipulation](PRIME_MANIPULATION.md)
for those additions and their distinct input and resource limits.

## Integer arithmetic profile

For a nonzero integer `n`, Numerisect factors `|n|` and computes exactly:

- distinct and multiplicity-counted prime factors, `ω(n)` and `Ω(n)`;
- divisor count `τ(n)`, divisor sum `σ(n)`, and aliquot sum `σ(n)-n`;
- Euler's totient `φ(n)` and the Carmichael function `λ(n)`;
- Möbius `μ(n)` and radical `rad(n)`;
- prime and semiprime status; and
- unit, deficient, perfect, or abundant classification.

The complete arithmetic functions are calculated even when the divisor preview
is limited. Up to 100,000 divisors can enter the response and text report.
Factorization can naturally dominate runtime for a difficult large input.

## Coprime navigation

Given modulus `m ≥ 2`, a start, and a count, PARI/GP calculates `φ(m)`, returns
the requested integers strictly after the start whose gcd with `m` is one, and
previews the reduced residue system modulo `m`. Inputs and gcd calculations use
arbitrary-precision integers. The residue and navigation lists are each capped
at 100,000 entries per request.

## Prime distribution

One native prime enumeration over an inclusive interval produces:

- exact counts in 2–500 equal-width integer bins;
- exact counts for every residue modulo `m`, where `2 ≤ m ≤ 360`;
- the number of consecutive twin pairs wholly inside the range; and
- the largest gap between consecutive in-range primes and its left endpoint.

The browser draws the bin and residue charts from these native counts. A single
interactive scan spans at most 10,000,000 integers; this bounds elapsed time and
does not impose a fixed-precision limit on the endpoints.

## Prime-factor-count distribution

For every positive integer in a finite range, PARI/GP performs an exact
factorization and increments two frequency tables: `ω(n)` counts distinct prime
factors, while `Ω(n)` counts them with multiplicity. The unit `1` occupies the
zero-factor bucket. The browser plots both tables for direct comparison. One
request may span 1,000,000 integers; difficult large factors can still make a
much shorter arbitrary-precision interval expensive.

## Digit-constrained primes

The generator walks only decimal numbers formed from the chosen digit alphabet,
never creates a leading-zero representation, and applies PARI's rigorous
`isprime` to every candidate. It supports lengths through 1,000 digits, a result
limit of 100,000, and an internal two-million-candidate budget. The response
distinguishes a result-limit stop from a candidate-budget stop.

## Exact quadratic exploration

The polynomial tool evaluates `F(n)=n²−n+k` over an arbitrary-precision finite
index interval. It returns rigorously proven prime values, the exact total and
longest consecutive prime run, and all residues `r (mod q)` for primes `q` up
to the selected obstruction bound where `F(r) ≡ 0 (mod q)`.

The scan may span 1,000,000 indices, the result display may contain 100,000
values, and modular obstructions may be requested through `q=1000`. The
prototype's heuristic Bateman–Horn calculation was not imported because its
normalization was not mathematically reliable; Numerisect exposes only exact
finite results and exact congruences.

## Palindrome-derived primes

This source sequence maps a positive integer to
`|n−reverse_decimal_digits(n)|+1`. PARI/GP performs the digit reversal and
rigorous primality test. A request may span 10,000,000 integers and return up to
100,000 records containing the input, reversal, and resulting prime.

## Prime-indicator constant

Numerisect computes

```text
C = Σ(n≥1) [n is prime] · 2^(-n).
```

PARI/GP rigorously tests every binary coefficient. It forms exact rational lower
and upper bounds for the uncomputed tail and extends the series until both bounds
round to the same requested decimal string. Thus the displayed value is
certified, not a floating-point guess. Requests may contain 1–100,000 decimal
digits; time and memory increase with precision.

## API routes

```text
POST /api/primes/integer-profile
POST /api/primes/coprimes
POST /api/primes/distribution
POST /api/primes/factor-count-distribution
POST /api/primes/digit-constrained
POST /api/primes/polynomial
POST /api/primes/palindrome-derived
POST /api/primes/indicator-constant
```

Every successful call writes a text report to `output/` and returns its filename.
The interface explicitly confirms the saved path and provides a download link.

Installation and versioned user-local deployment are documented in
[Installation and versioning](INSTALLATION.md). The arithmetic tools remain
available on Linux, WSL, and macOS wherever PARI/GP can be built and run.

## Audit exclusions

Educational AKS, Fermat, Miller–Rabin, trial-division, and hand-written sieve
variants were not duplicated because PARI/GP and the factor engines already
provide stronger implementations. Static prime tables and plots were replaced
by live native calculations. The experimental line-covering solver is an exact
combinatorial-geometry sequence limited to 63 points rather than a generally
useful prime-analysis operation, so it remains outside the application. Ulam
spiral plotting overlaps the existing modular-wheel visualization without
adding a new arithmetic capability. Ancient numeral rendering is outside
Numerisect's factorization and prime-analysis scope.
