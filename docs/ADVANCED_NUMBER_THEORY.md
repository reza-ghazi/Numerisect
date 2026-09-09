# Advanced number-theory workbenches

Numerisect 0.7.0 adds a dedicated PARI/GP computational layer in
`numerisect/number_theory.gp`. Python validates decimal inputs, starts GP,
requires complete tagged output, parses it, and persists reports. It does not
reimplement the mathematics. Each operation has one Prime Tools route, and its
result appears directly below the submitted form.

## Primality and special families

- The primality laboratory compares Fermat, Euler–Jacobi, strong
  Miller–Rabin, BPSW, and a selected rigorous automatic, N−1, APR-CL, or ECPP
  result. Probable passes are never relabeled as proofs.
- Lucas–Lehmer and Pépin pages provide necessary-and-sufficient special-form
  tests for Mersenne and Fermat numbers.
- The family search covers Mersenne, Fermat, Cullen, Woodall, Wagstaff,
  decimal repunit, primorial ± 1, and factorial ± 1 candidates. Every value
  returned as prime passes PARI `isprime`.
  Fermat search is capped at index 20 because candidate size doubles in bits
  at every step; the other family indices are capped at 10,000.
- Cunningham chains support both recurrences and include the first composite
  term when a requested chain fails.
- NTT-friendly search constructs exact-bit-length primes `p = k·2^m + 1`.
  Hitting the candidate limit is reported as incomplete, not as proof that no
  additional values exist.
- A certificate exported by the rigorous primality page includes PARI's
  machine vector and can be imported into the independent verifier.

## Modular and polynomial arithmetic

The workbench evaluates Legendre, Jacobi, and Kronecker symbols with explicit
domain distinctions; generalized CRT systems with non-coprime moduli; kth
roots in a proven prime field; and discrete logarithms with PARI's native
algorithm selection. The unit-group page returns invariant factors,
generators, cyclicity, and bounded primitive-root enumeration.

Additional pages provide:

- a complete Tonelli–Shanks state trace and verified square roots;
- p-adic root lifting from `polrootspadic`, materialized modulo `p^k`;
- multiplicative-order distributions modulo `n`;
- kth-power-residue distributions over `F_p`;
- exact p-adic valuations and unit parts;
- factorization of integer polynomials over the rationals and finite fields;
- construction of `Φ_n(x)` and factorization over a selected finite field.

Enumeration pages retain explicit row and domain bounds. A display limit does
not change an exact count, and a truncated result says so.

## Integer structure

Extended arithmetic factors `|n|` natively and derives generalized divisor
sums, Jordan totients, Dedekind psi, Liouville and von Mangoldt values,
radicals, squarefree kernels, least/largest factors, smoothness,
powersmoothness, divisor previews, representation counts, and selected
quadratic-form representations.

The divisor-classification page reports deficient, perfect, or abundant
status, almost-perfect and multiperfect conditions, and an exact amicable-pair
check. The aliquot page iterates native divisor sums and distinguishes
termination, a proven repeated-value cycle, and exhaustion of the configured
step limit.

## Analytic and algebraic tools

`primecount` supplies exact `π(x)`, Li, and Riemann-R values through its
documented `10^31` input range. PARI computes `x/log(x)` and the signed and
relative errors. A separate bounded page evaluates Mertens `M(x)`, summatory
Liouville `L(x)`, and Chebyshev theta/psi.

The algebraic pages implement the exact Eisenstein-prime criterion and use
PARI number fields plus `idealprimedec` to classify splitting, inertia, and
ramification in a quadratic field.

## Limits and result contract

Limits shown in the form are deliberate resource controls, not mathematical
claims. Timeouts, candidate limits, display limits, and bounded scans remain
visible in the returned status. Every saved Prime Tools report is announced
with its exact `output/<filename>` path. Browser tables show at most 2,000 rows;
the report retains every row returned by the native operation.

See [Roadmap status](ROADMAP_STATUS.md) for features that remain partial or
deferred rather than being represented by placeholder calculations.
