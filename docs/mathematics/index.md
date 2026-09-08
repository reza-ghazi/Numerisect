# Mathematics

These pages explain the theory behind every tool in Numerisect. They are written for a
reader who is mathematically literate but not necessarily a specialist: enough detail to
understand what an algorithm does and why it works, without assuming you already know.

Each page ends with two sections. **Where this appears in Numerisect** maps each topic to
the tool that implements it and the library routine that performs the computation.
**References** gives sources you can check, because a documentation page asserting a
bound is worth less than one telling you where the bound comes from.

<div class="grid cards" markdown>

-   **Primality**

    ---

    Fermat and Carmichael numbers, Miller–Rabin and its error bound, Lucas sequences and
    Baillie–PSW, and the proof methods: Pocklington, Pratt, Proth, Lucas–Lehmer, APR-CL
    and ECPP.

    [:octicons-arrow-right-24: Read](primality.md)

-   **Factorization**

    ---

    Why factoring is hard, rho and p−1 and p+1, ECM, SQUFOF and the forms behind it, the
    quadratic sieve, and the number field sieve in its general and special variants.

    [:octicons-arrow-right-24: Read](factorization.md)

-   **Prime structures**

    ---

    Decimal rotations and truncations, prime constellations, reciprocal periods,
    Gaussian and Eisenstein primes, perfect numbers, and why a bounded search can remain
    inconclusive.

    [:octicons-arrow-right-24: Read](prime-structures.md)

-   **Distribution**

    ---

    The prime number theorem and its approximations, computing \(\pi(x)\) from Legendre
    to Gourdon, gaps and merit, primes in progressions, Chebyshev's bias, and the
    Hardy–Littlewood and Bateman–Horn conjectures.

    [:octicons-arrow-right-24: Read](distribution.md)

-   **Modular arithmetic**

    ---

    Congruences and Hensel lifting, the structure of the unit group, quadratic
    reciprocity, discrete logarithms, finite fields, and the arithmetic functions.

    [:octicons-arrow-right-24: Read](modular.md)

-   **Quadratic forms**

    ---

    Binary quadratic forms and class groups, continued fractions and their periods,
    Pell's equation, representation of integers, and the link back to factoring.

    [:octicons-arrow-right-24: Read](quadratic-forms.md)

-   **Zeta and L-functions**

    ---

    The Euler product and functional equation, the critical line, Hardy's Z function and
    Gram points, the Turing method, the explicit formula, and Dirichlet L-functions.

    [:octicons-arrow-right-24: Read](zeta.md)

</div>

## A note on rigour

Mathematics pages distinguish three kinds of statement, and say which is which:

- **Theorems** are proven. Fermat's little theorem, quadratic reciprocity and the prime
  number theorem are theorems.
- **Conjectures** are not. The Riemann hypothesis, the Hardy–Littlewood k-tuple
  conjecture, Bateman–Horn, Cramér's and Firoozbakht's conjectures are open, and results
  computed from them are predictions rather than facts.
- **Heuristics** are arguments for why something should be true, useful for estimating
  work but not evidence of correctness.

Numerisect applies the same care to its output that these pages apply to their claims.

[:octicons-arrow-right-24: Proven and probable](../concepts/proven-and-probable.md)
