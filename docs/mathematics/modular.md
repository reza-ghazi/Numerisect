# Modular arithmetic and multiplicative structure

This page covers the algebra that sits underneath most of Numerisect's non-analytic
tools: congruences and the Chinese remainder theorem, solving polynomial congruences
by factoring the modulus and lifting, the structure of the unit group
\((\mathbb{Z}/n\mathbb{Z})^\times\), quadratic and higher-power residues with the
Legendre, Jacobi and Kronecker symbols, the discrete logarithm and its four standard
algorithms, finite fields and polynomial factorization over them, and the classical
arithmetic functions with their Dirichlet convolutions and summatory functions.
The implementing tools are in [the algebra laboratory](../ALGEBRA_LAB.md) and
[the advanced number-theory workbenches](../ADVANCED_NUMBER_THEORY.md); the summary
table at the foot of the page maps every topic to a route and an engine routine.

## Congruences and the Chinese remainder theorem

For a modulus \(m \ge 2\), \(a \equiv b \pmod m\) means \(m \mid a - b\). The
residue classes form the ring \(\mathbb{Z}/m\mathbb{Z}\), and the whole subject is
the study of that ring and of its unit group.

**Theorem (Chinese remainder).** If \(m_1, \ldots, m_r\) are pairwise coprime with
product \(M\), the map

\[
\mathbb{Z}/M\mathbb{Z} \longrightarrow
\mathbb{Z}/m_1\mathbb{Z} \times \cdots \times \mathbb{Z}/m_r\mathbb{Z}
\]

is a ring isomorphism. Consequently a system \(x \equiv a_i \pmod{m_i}\) has exactly
one solution modulo \(M\).

Without coprimality the system may be inconsistent. The general criterion is that
\(x \equiv a_i \pmod{m_i}\) and \(x \equiv a_j \pmod{m_j}\) are simultaneously
solvable exactly when

\[
a_i \equiv a_j \pmod{\gcd(m_i, m_j)},
\]

and when every pair is compatible the solution is unique modulo
\(\mathrm{lcm}(m_1, \ldots, m_r)\).

**In Numerisect.** *Generalized CRT* (`POST /api/number-theory/crt`, `nt_crt`)
merges the congruences one at a time, checking the gcd compatibility condition at
each step and reporting `COMPATIBLE:0` for an inconsistent system rather than
returning a wrong residue. The result is stated modulo the lcm, not the product.

### Polynomial congruences

Solving \(P(x) \equiv 0 \pmod m\) decomposes into three steps, and Numerisect
performs exactly these three:

1. **Factor the modulus,** \(m = \prod p_i^{e_i}\) (PARI `factor`). By CRT the
   solution set modulo \(m\) is the product of the solution sets modulo each
   \(p_i^{e_i}\).
2. **Solve modulo each prime,** with PARI `polrootsmod`, which works in the field
   \(\mathbb{F}_p\).
3. **Lift from \(p\) to \(p^e\), then recombine** with PARI `chinese`.

The lifting step is Hensel's lemma.

**Theorem (Hensel).** If \(P(r) \equiv 0 \pmod{p^k}\) and
\(P'(r) \not\equiv 0 \pmod p\), then \(r\) lifts to a **unique** root modulo
\(p^{k+1}\), namely \(r - P(r) \cdot \overline{P'(r)}\) where the bar is inversion
modulo \(p\). This is Newton's method in the \(p\)-adic metric, and it converges for
the same reason.

The hypothesis \(P'(r) \not\equiv 0\) matters. At a **singular** root, where
\(P'(r) \equiv 0 \pmod p\), the lift is not unique: either no lift exists, or all
\(p\) candidates \(r + t p^k\) lift. Both cases occur.

!!! warning "The singular case is where library routines stop"
    PARI's `polrootspadic` returns only the \(p\)-adically liftable roots and misses
    singular ones. For \(x^2 - 1\) modulo 8 every root is singular
    (\(P'(x) = 2x \equiv 0 \bmod 2\)), and the complete root set
    \(\{1, 3, 5, 7\}\) includes 3 and 5, which `polrootspadic` does not report.
    Numerisect therefore builds the lift itself from PARI primitives, branching over
    all \(p\) residues at a singular root. Every returned residue is substituted back
    into \(P\) before it is shown, and if the branching exceeds the result limit the
    response sets `complete: false` and the solution count reads `inconclusive` —
    never `0`.

**In Numerisect.** *Congruences modulo a composite*
(`POST /api/algebra/congruence`) performs the full factor–lift–recombine pipeline;
*p-adic root lifting* (`POST /api/number-theory/hensel-roots`, `nt_hensel_roots`)
shows the lift level by level and materialises the roots modulo \(p^k\). The
worked example \(x^2 + 1 \equiv 0 \pmod{65}\) returns the four roots
\(8, 18, 47, 57\).

## The unit group \((\mathbb{Z}/n\mathbb{Z})^\times\)

A residue class is invertible exactly when it is coprime to \(n\), so the unit group
has order \(\varphi(n)\), Euler's totient. Its structure is completely known:

\[
(\mathbb{Z}/n\mathbb{Z})^\times \;\cong\;
(\mathbb{Z}/2^{e_0}\mathbb{Z})^\times \times
\prod_{i} (\mathbb{Z}/p_i^{e_i}\mathbb{Z})^\times ,
\]

where for odd \(p\) the factor \((\mathbb{Z}/p^{e}\mathbb{Z})^\times\) is cyclic of
order \(p^{e-1}(p-1)\), and the 2-part is trivial for \(e_0 \le 1\), cyclic of order
2 for \(e_0 = 2\), and \(\mathbb{Z}/2 \times \mathbb{Z}/2^{e_0 - 2}\) for
\(e_0 \ge 3\).

### Primitive roots

A **primitive root** modulo \(n\) is a generator of \((\mathbb{Z}/n\mathbb{Z})^\times\),
which therefore exists exactly when that group is cyclic:

\[
n \in \{\,1,\; 2,\; 4,\; p^k,\; 2p^k \,\}, \qquad p \text{ an odd prime}.
\]

When one exists there are \(\varphi(\varphi(n))\) of them — modulo 101 that is
\(\varphi(100) = 40\). No formula gives the smallest one; searching is the method,
and even the assertion that a fixed integer \(a\) is a primitive root for infinitely
many primes is **Artin's conjecture**, still open in general (though known under
GRH, by Hooley).

### Carmichael's \(\lambda\)

The **exponent** of the unit group is Carmichael's function: the least \(\lambda(n)\)
with \(a^{\lambda(n)} \equiv 1\) for every unit \(a\). It is the lcm of the orders of
the cyclic factors above:

\[
\lambda(2) = 1, \quad \lambda(4) = 2, \quad \lambda(2^k) = 2^{k-2}\ (k \ge 3),
\quad \lambda(p^k) = \varphi(p^k) = p^{k-1}(p-1) \ (p \text{ odd}),
\]

and \(\lambda(n)\) is the lcm over prime-power components. Always
\(\lambda(n) \mid \varphi(n)\), with equality exactly when a primitive root exists.
\(\lambda\) is the sharp exponent in Euler's theorem, and it is the right object for
RSA-style key arithmetic and for Carmichael numbers, which are precisely the
composite \(n\) with \(\lambda(n) \mid n - 1\) (Korselt's criterion).

!!! note "Two functions named \(\lambda\)"
    Carmichael's \(\lambda\) here is unrelated to the Liouville function
    \(\lambda(n) = (-1)^{\Omega(n)}\) in the arithmetic-functions section below.
    Numerisect reports Carmichael's \(\lambda\) on the *integer arithmetic profile*
    and Liouville's on the *extended arithmetic* and *summatory functions* pages;
    the labels in the reports distinguish them.

**In Numerisect.** *Unit group* (`POST /api/number-theory/unit-group`,
`nt_unit_group`) uses PARI `znstar` to return the group order, the invariant factors
`G.cyc`, the generators `G.gen`, a cyclicity verdict, and — when the group is
cyclic and small enough — a bounded enumeration of primitive roots with an explicit
`ENUMERATION_COMPLETE` flag. *Multiplicative-order distribution*
(`POST /api/number-theory/order-distribution`, `nt_order_distribution`) tabulates
`znorder` over every unit, so the order spectrum and the count of elements of each
order are exact. Carmichael's \(\lambda\) appears on the *integer arithmetic profile*
(`POST /api/primes/integer-profile`).

## Quadratic and higher-power residues

### The three symbols

\(a\) is a **quadratic residue** modulo \(p\) when \(x^2 \equiv a\) is solvable. For
an odd prime \(p \nmid a\), Euler's criterion says
\(a^{(p-1)/2} \equiv \pm 1 \pmod p\), and the **Legendre symbol** \(\left(\frac{a}{p}\right)\)
is that sign: \(+1\) for a residue, \(-1\) for a non-residue, \(0\) when \(p \mid a\).

The **Jacobi symbol** extends this to odd \(n > 0\) multiplicatively over the prime
factorization of the *denominator*:
\(\left(\frac{a}{n}\right) = \prod_i \left(\frac{a}{p_i}\right)^{e_i}\).

!!! warning "Jacobi \(= 1\) does not mean residue"
    For composite \(n\) the Jacobi symbol can be \(+1\) with two \(-1\) factors
    cancelling, so it decides quadratic residuosity **only** when \(n\) is an odd
    prime. Numerisect's symbol page states which of the three symbols is applicable
    for the given input and says so explicitly rather than letting the reader assume.

The **Kronecker symbol** extends the Jacobi symbol to every nonzero \(n\), including
negative and even ones, by defining \(\left(\frac{a}{-1}\right)\) by the sign of
\(a\) and \(\left(\frac{a}{2}\right) = 0, +1, -1\) according as \(a\) is even,
\(a \equiv \pm 1 \pmod 8\), or \(a \equiv \pm 3 \pmod 8\). This is the version that
matters in [quadratic fields](quadratic-forms.md), where
\(\left(\frac{D_K}{p}\right)\) decides how \(p\) splits.

### Quadratic reciprocity

**Theorem (Gauss).** For distinct odd primes \(p, q\),

\[
\left(\frac{p}{q}\right)\left(\frac{q}{p}\right)
= (-1)^{\frac{p-1}{2}\cdot\frac{q-1}{2}},
\]

with the supplementary laws

\[
\left(\frac{-1}{p}\right) = (-1)^{\frac{p-1}{2}},
\qquad
\left(\frac{2}{p}\right) = (-1)^{\frac{p^2-1}{8}} .
\]

The law holds for Jacobi symbols with odd positive arguments too, and that is what
makes it an *algorithm*: the symbol \(\left(\frac{a}{n}\right)\) can be evaluated by
reducing \(a\) modulo \(n\), pulling out powers of 2 with the second supplement, and
flipping — a Euclidean-style descent costing \(O(\log^2 n)\) bit operations, with no
factorization of \(n\) needed at any point.

**In Numerisect.** *Quadratic-reciprocity trace*
(`POST /api/algebra/reciprocity`) writes out that descent step by step, because
displaying the steps is the feature; the accumulated sign is cross-checked against
PARI `kronecker` and a mismatch is raised as an engine error, never returned as a
result. *Symbols* (`POST /api/number-theory/symbols`, `nt_symbols`) evaluates all
three symbols for one pair with explicit availability flags.

### Square roots: Tonelli–Shanks

Given that \(a\) is a residue modulo \(p\), finding \(x\) with \(x^2 \equiv a\) is a
separate problem. Write \(p - 1 = q \cdot 2^s\) with \(q\) odd.

- If \(s = 1\) (that is, \(p \equiv 3 \pmod 4\)) the root is simply
  \(a^{(p+1)/4} \bmod p\).
- Otherwise Tonelli–Shanks works in the 2-Sylow subgroup: it takes a quadratic
  non-residue \(z\), sets \(c = z^q\), \(t = a^q\), \(R = a^{(q+1)/2}\), \(M = s\),
  and repeatedly finds the least \(i\) with \(t^{2^i} = 1\), then multiplies \(R\)
  by \(b = c^{2^{M-i-1}}\) and updates. Each round strictly decreases \(M\), so it
  terminates in at most \(s\) rounds at \(O(s^2)\) multiplications on top of the
  initial exponentiations.

The one non-deterministic step is finding the non-residue \(z\); a random or
sequential search succeeds in two tries on average. Under GRH the least non-residue
is \(O(\log^2 p)\), which makes the algorithm deterministic-under-GRH but not
unconditionally deterministic. Cipolla's algorithm solves the same problem in a
quadratic extension and is preferable when \(s\) is large.

**In Numerisect.** *Tonelli–Shanks* (`POST /api/number-theory/tonelli-shanks`,
`nt_tonelli_shanks`) emits the full state trace \((R, t, c, M)\) at each step,
reports the Legendre symbol first so a non-residue input is refused rather than
looped on, and returns both roots \(\min(R, p-R)\) and \(\max(R, p-R)\).

### Higher-power residues

For \(x^k \equiv a \pmod p\) with \(p \nmid a\), put \(g = \gcd(k, p-1)\). Since
\(\mathbb{F}_p^\times\) is cyclic of order \(p - 1\), the map \(x \mapsto x^k\) has
image the subgroup of index \(g\), so:

- the congruence is solvable exactly when \(a^{(p-1)/g} \equiv 1 \pmod p\);
- when solvable it has exactly \(g\) solutions, obtained from one root by
  multiplying through the \(g\) \(k\)-th roots of unity.

**In Numerisect.** *\(k\)-th roots in a prime field*
(`POST /api/number-theory/modular-roots`, `nt_modular_roots`) uses PARI `sqrtn`,
which returns a root together with a generator \(z\) of the \(k\)-th roots of unity,
and then enumerates the full set of \(\gcd(k, p-1)\) roots. *Power-residue
distribution* (`POST /api/number-theory/power-residues`, `nt_power_residues`)
tabulates how many \(a\) map to each value of \(a^k\), so the index-\(g\) image is
visible directly. *p-adic valuation* (`POST /api/number-theory/valuation`) reports
\(v_p(n)\) and the unit part.

## The discrete logarithm

Given a cyclic group \(\langle g \rangle\) of order \(N\) and an element \(h\), find
\(x\) with \(g^x = h\). In \((\mathbb{Z}/n\mathbb{Z})^\times\) this is the discrete
logarithm problem, and its presumed hardness is the basis of Diffie–Hellman.

| Algorithm | Idea | Cost |
|---|---|---|
| **Baby-step giant-step** (Shanks) | write \(x = im + j\) with \(m = \lceil\sqrt N\rceil\), tabulate \(g^j\), then match \(h g^{-im}\) | \(O(\sqrt N)\) time **and** \(O(\sqrt N)\) space |
| **Pohlig–Hellman** | with \(N = \prod p_i^{e_i}\), solve modulo each \(p_i^{e_i}\) by descending digit by digit and recombine by CRT | \(O\!\left(\sum_i e_i(\log N + \sqrt{p_i})\right)\) |
| **Pollard rho for logarithms** | a pseudo-random walk on the group with a collision detector; a collision gives a linear relation in the exponent | \(O(\sqrt N)\) expected time, \(O(1)\) space |
| **Index calculus** | build a factor base of small primes, collect smooth relations, solve the linear system, then descend for the target | subexponential; \(L_p(1/2)\) in the classical form, \(L_p(1/3)\) with a number-field sieve |

Two consequences are worth stating plainly. First, Pohlig–Hellman means the
difficulty is governed by the **largest prime factor** of \(N\), not by \(N\): a
group of smooth order is weak regardless of size, which is why cryptographic groups
are chosen with prime or nearly prime order. Second, index calculus is what makes
the multiplicative group of a finite field far weaker at a given bit size than a
generic group, and it is the reason elliptic-curve groups — where no index calculus
is known — are used at much smaller parameters.

**In Numerisect.** *Discrete logarithms* (`POST /api/algebra/discrete-log`) offers
`bsgs`, `pohlig_hellman`, `pollard_rho` and `native` (PARI `znlog`), with a step
budget of 1 to \(10^8\) group operations and a strictly three-way status:
`solved` (verified by re-exponentiating), `no solution` (the search covered the whole
of \(\langle g \rangle\)), or `inconclusive` (the budget was exhausted first — **not**
a proof of insolubility). The simpler `POST /api/number-theory/discrete-log`
(`nt_discrete_log`) hands the problem to PARI `znlog` with the factored group order.

!!! note "Index calculus is described here but not implemented"
    Numerisect implements the three generic algorithms and PARI's native solver.
    Index calculus is not among them, and the discrete-log page does not claim it.

## Finite fields

For each prime \(p\) and each \(m \ge 1\) there is a field with \(p^m\) elements,
unique up to isomorphism, constructed as \(\mathbb{F}_p[x]/(f)\) for any irreducible
\(f\) of degree \(m\). Its additive group is elementary abelian of exponent \(p\);
its multiplicative group is **cyclic** of order \(p^m - 1\), and a generator is
called a primitive element. The number of monic irreducibles of degree \(m\) over
\(\mathbb{F}_p\) is

\[
\frac{1}{m}\sum_{d \mid m} \mu(d)\, p^{m/d},
\]

which is positive for every \(m\) — that is the existence proof.

The Frobenius map \(x \mapsto x^p\) is a field automorphism fixing \(\mathbb{F}_p\)
pointwise, and \(\mathrm{Gal}(\mathbb{F}_{p^m}/\mathbb{F}_p)\) is cyclic of order
\(m\) generated by it. \(\mathbb{F}_{p^d} \subseteq \mathbb{F}_{p^m}\) exactly when
\(d \mid m\).

**In Numerisect.** *Finite fields* (`POST /api/algebra/finite-field`) constructs
\(\mathbb{F}_{p^m}\) with PARI `ffinit` and `ffgen`, or from a user-supplied
reduction polynomial checked with `polisirreducible` — a non-monic polynomial or one
of the wrong degree is refused. Element orders come from `fforder`, primitivity means
order exactly \(p^m - 1\), `ffprimroot` supplies a primitive element, `minpoly` the
minimal polynomial, and the Frobenius column is \(x \mapsto x^p\). Elements are given
and returned in the power basis of the reduction polynomial's root, in ascending
coordinates.

### Factoring polynomials over a finite field

The standard pipeline is three stages, and each stage is separately meaningful:

1. **Squarefree factorization.** Compute \(\gcd(f, f')\). Over a field of
   characteristic \(p\) there is a wrinkle absent in characteristic zero: \(f' = 0\)
   does not force \(f\) constant, because \(f\) may be a \(p\)-th power
   \(g(x)^p = g(x^p)\), and that case is handled by taking \(p\)-th roots of the
   coefficients. Yun's algorithm performs the whole separation in
   \(O(\deg f)\) gcds.
2. **Distinct-degree factorization.** \(x^{q^d} - x\) is the product of all monic
   irreducibles of degree dividing \(d\) over \(\mathbb{F}_q\), so
   \(\gcd(f, x^{q^d} - x)\) — with \(x^{q^d}\) computed by repeated Frobenius modulo
   \(f\) — peels off exactly the degree-\(d\) part.
3. **Equal-degree factorization (Cantor–Zassenhaus).** Splitting a product of
   several irreducibles of the *same* degree \(d\) needs randomness: for odd \(q\),
   take a random \(h\) and compute \(\gcd\!\left(h^{(q^d - 1)/2} - 1,\, f\right)\),
   which is a proper factor with probability at least about \(1/2\) per trial. This
   is a Las Vegas algorithm — the output is always correct, the running time is
   random. No deterministic polynomial-time algorithm is known in general.

**In Numerisect.** *Integer polynomials over \(\mathbb{Q}\) and \(\mathbb{F}_p\)*
(`POST /api/number-theory/polynomial`, `nt_polynomial`) factors over both with PARI
`factor` and `factor(Mod(1,p)*P)` and lists the roots with `polrootsmod`.
*Cyclotomic polynomials* (`POST /api/number-theory/cyclotomic`, `nt_cyclotomic`)
builds \(\Phi_n(x)\) with `polcyclo` and factors it over a selected
\(\mathbb{F}_p\); the factor degrees there are all equal to the order of \(p\)
modulo \(n\), which is a clean illustration of distinct-degree structure. PARI
performs the factorization; Numerisect does not reimplement Cantor–Zassenhaus.

## Arithmetic functions

An arithmetic function is **multiplicative** when \(f(mn) = f(m)f(n)\) for coprime
\(m, n\), and **completely multiplicative** when that holds for all \(m, n\). A
multiplicative function is determined by its values on prime powers, which is why
factoring \(n\) is enough to evaluate every function in the table below exactly.

| Function | Definition | Value at \(p^e\) | Multiplicative? |
|---|---|---|---|
| \(\tau(n) = \sigma_0(n)\) | number of divisors | \(e + 1\) | yes |
| \(\sigma_k(n)\) | \(\sum_{d \mid n} d^k\) | \((p^{k(e+1)} - 1)/(p^k - 1)\) | yes |
| \(\varphi(n)\) | units modulo \(n\) | \(p^e - p^{e-1}\) | yes |
| \(J_k(n)\) | Jordan totient | \(p^{ke} - p^{k(e-1)}\) | yes |
| \(\psi(n)\) | Dedekind psi | \(p^{e-1}(p+1)\) | yes |
| \(\mu(n)\) | Möbius | \(-1\) if \(e = 1\), else 0 | yes |
| \(\lambda(n)\) | Liouville, \((-1)^{\Omega(n)}\) | \((-1)^e\) | completely |
| \(\Lambda(n)\) | von Mangoldt | \(\log p\) | **no** |
| \(\omega(n), \Omega(n)\) | distinct / counted prime factors | \(1\) / \(e\) | additive, not multiplicative |

\(\Lambda\) is the odd one out and deliberately so: it is not multiplicative, it is
the function whose Dirichlet series is \(-\zeta'/\zeta\), and it is the natural
weight in [the explicit formula](zeta.md).

### Dirichlet convolution

\[
(f * g)(n) = \sum_{d \mid n} f(d)\, g(n/d).
\]

Convolution is commutative and associative, its identity is
\(\varepsilon(n) = [n = 1]\), and multiplicative functions are closed under it. The
standard identities are then one-liners, and each is worth recognising:

\[
\mathbf{1} * \mu = \varepsilon, \qquad
\mathbf{1} * \mathbf{1} = \tau, \qquad
\mathbf{1} * \mathrm{Id} = \sigma, \qquad
\mu * \mathrm{Id} = \varphi, \qquad
\mu * \log = \Lambda .
\]

The first is Möbius inversion: \(g = \mathbf{1} * f \iff f = \mu * g\). The last is
why \(\Lambda\) and \(\mu\) appear together everywhere in analytic number theory,
and why Riemann's \(R(x)\) on [the distribution page](distribution.md) carries
Möbius coefficients.

In Dirichlet series, convolution is multiplication:
\(\sum_n (f*g)(n) n^{-s} = F(s) G(s)\). So \(\sum \mu(n) n^{-s} = 1/\zeta(s)\),
\(\sum \tau(n) n^{-s} = \zeta(s)^2\), \(\sum \lambda(n) n^{-s} = \zeta(2s)/\zeta(s)\),
and \(\sum \Lambda(n) n^{-s} = -\zeta'(s)/\zeta(s)\).

### Summatory functions

The partial sums are where the analysis lives.

- **Mertens function** \(M(x) = \sum_{n \le x} \mu(n)\). Trivially
  \(|M(x)| \le x\); the truth is much smaller but not known precisely.
  **\(M(x) = O(x^{1/2 + \varepsilon})\) for every \(\varepsilon > 0\) is equivalent
  to the Riemann hypothesis.** The stronger *Mertens conjecture*
  \(|M(x)| < \sqrt{x}\) was **disproved** by Odlyzko and te Riele in 1985 — a
  reminder that "true for every computed value" and "true" are different claims.
- **Summatory Liouville** \(L(x) = \sum_{n \le x} \lambda(n)\). Pólya conjectured
  \(L(x) \le 0\) for \(x > 1\); this too is false, with the least counterexample at
  \(x = 906\,150\,257\). \(L(x) = O(x^{1/2+\varepsilon})\) is again equivalent to
  RH.
- **Chebyshev's \(\theta\) and \(\psi\)**, defined at the top of
  [the distribution page](distribution.md), with \(\psi(x) \sim x\) equivalent to
  the prime number theorem.

!!! warning "Two disproved conjectures, both with vast numerical support"
    Mertens' and Pólya's conjectures each survived every computation available for
    decades before being refuted. Numerisect prints \(M(x)\) and \(L(x)\) as
    observations of a finite range and never as evidence for a bound.

**In Numerisect.** *Summatory functions*
(`POST /api/number-theory/summatory-functions`, `nt_summatory_functions`) evaluates
\(M(x)\), \(L(x)\), \(\theta(x)\) and \(\psi(x)\) in one pass at 50-digit precision,
with PARI `moebius` and `bigomega` for the first two and `forprime` with `log` for
the Chebyshev functions. The loop is linear in \(x\), so the page is bounded
accordingly. *Extended arithmetic*
(`POST /api/number-theory/arithmetic-functions`, `nt_arithmetic`) computes
\(\sigma_k\), \(J_k\), Dedekind \(\psi\), Liouville and von Mangoldt values, the
radical and squarefree kernel, least and largest prime factors, and the smoothness
and powersmoothness verdicts, all from one exact factorization. The *integer
arithmetic profile* (`POST /api/primes/integer-profile`) reports \(\omega\),
\(\Omega\), \(\tau\), \(\sigma\), \(\varphi\), Carmichael \(\lambda\), \(\mu\) and
\(\mathrm{rad}\) together.

### Divisor structure

The divisor-related tools sit naturally here. *Divisor enumeration and lattice*
(`POST /api/algebra/divisor-lattice`) lists every divisor with its cofactor and
\(\Omega(d)\) and, within a cap, the covering relation \(d \lessdot dp\) of the
divisor lattice. *Smoothness and roughness*
(`POST /api/algebra/smoothness`) factors \(|n|\) completely, so the smoothness,
powersmoothness and roughness bounds are exact rather than estimated — which is
what makes them usable as inputs to factoring strategy. *Divisor records*
(`POST /api/algebra/record-numbers`) decides highly composite (record \(\tau\)) and
superabundant (record \(\sigma(n)/n\)) against a provably complete candidate
enumeration, and gives a three-way verdict for superior highly composite and
colossally abundant. *Abundance and weird numbers*
(`POST /api/algebra/weird-numbers`) and *amicable and sociable cycles*
(`POST /api/algebra/sociable`) iterate the aliquot map \(s(n) = \sigma(n) - n\);
an exhausted subset or step cap reads `inconclusive`, never `no`.

## Where this appears in Numerisect

| Topic | Tool (route) | Engine routine |
|---|---|---|
| CRT with possibly non-coprime moduli | Generalized CRT (`/api/number-theory/crt`) | `nt_crt` (PARI `gcd`, `lcm`, `Mod`) |
| \(P(x) \equiv 0 \pmod m\), full pipeline | Congruences (`/api/algebra/congruence`) | PARI `factor`, `polrootsmod`, `chinese`, `deriv`, `subst` |
| Hensel lifting, singular roots included | p-adic root lifting (`/api/number-theory/hensel-roots`) | `nt_hensel_roots` (PARI `polrootsmod`, `deriv`, `subst`) |
| Group order, invariant factors, primitive roots | Unit group (`/api/number-theory/unit-group`) | `nt_unit_group` (PARI `znstar`, `znorder`, `eulerphi`) |
| Order spectrum modulo \(n\) | Order distribution (`/api/number-theory/order-distribution`) | `nt_order_distribution` (PARI `znorder`) |
| Carmichael \(\lambda\) | Integer arithmetic profile (`/api/primes/integer-profile`) | `ps_integer_profile` (PARI `lcm` over prime powers) |
| Legendre, Jacobi, Kronecker | Symbols (`/api/number-theory/symbols`) | `nt_symbols` (PARI `kronecker`) |
| Reciprocity descent, step by step | Reciprocity trace (`/api/algebra/reciprocity`) | PARI `kronecker` (cross-check), `valuation`, `gcd`, `isprime` |
| Square roots mod \(p\) with full trace | Tonelli–Shanks (`/api/number-theory/tonelli-shanks`) | `nt_tonelli_shanks` (PARI `kronecker`, `Mod`, `valuation`) |
| \(k\)-th roots mod \(p\) | Modular roots (`/api/number-theory/modular-roots`) | `nt_modular_roots` (PARI `sqrtn`) |
| \(k\)-th power residue distribution | Power residues (`/api/number-theory/power-residues`) | `nt_power_residues` |
| \(v_p(n)\) and unit part | Valuation (`/api/number-theory/valuation`) | `nt_valuation` (PARI `valuation`) |
| BSGS, Pohlig–Hellman, Pollard rho, native | Discrete logarithms (`/api/algebra/discrete-log`) | PARI `znlog`, `znorder`, `factor`, `chinese` |
| \(\mathbb{F}_p\) and \(\mathbb{F}_{p^m}\) arithmetic | Finite fields (`/api/algebra/finite-field`) | PARI `ffinit`, `ffgen`, `fforder`, `ffprimroot`, `minpoly`, `polisirreducible` |
| Factoring over \(\mathbb{Q}\) and \(\mathbb{F}_p\) | Polynomials (`/api/number-theory/polynomial`) | `nt_polynomial` (PARI `factor`, `polrootsmod`) |
| \(\Phi_n(x)\) over \(\mathbb{F}_p\) | Cyclotomic (`/api/number-theory/cyclotomic`) | `nt_cyclotomic` (PARI `polcyclo`, `factor`) |
| \(\sigma_k, J_k, \psi, \lambda, \Lambda\), radical, smoothness | Extended arithmetic (`/api/number-theory/arithmetic-functions`) | `nt_arithmetic` (PARI `factor`, `divisors`, `sigma`, `bigomega`) |
| \(M(x)\), \(L(x)\), \(\theta(x)\), \(\psi(x)\) | Summatory functions (`/api/number-theory/summatory-functions`) | `nt_summatory_functions` (PARI `moebius`, `bigomega`, `forprime`) |
| Divisor lattice, records, abundance, aliquot cycles | `/api/algebra/divisor-lattice`, `/record-numbers`, `/weird-numbers`, `/sociable`, `/api/number-theory/aliquot` | PARI `divisors`, `sigma`, `numdiv`, `bigomega` |
| Structural predicates on one integer | Integer structure (`/api/structure/predicates`) | PARI `isprimepower`, `ispowerful`, `istotient`, `isfundamental`, `ispolygonal` |
| Divisors in a residue class without factoring | Lenstra divisors (`/api/structure/lenstra-divisors`) | PARI `divisorslenstra` (guarded by \(\gcd(r,s)=1\) and \(s^3 > N\)) |

## References

- H. Cohen, *A Course in Computational Algebraic Number Theory*, Springer GTM 138 —
  §1.4–1.5 (gcd, symbols, Tonelli–Shanks), §3.4–3.5 (factoring polynomials over
  finite fields), §5.4 (baby-step/giant-step and Pohlig–Hellman).
- R. Crandall and C. Pomerance, *Prime Numbers: A Computational Perspective*, 2nd ed.
  — Chapter 2 (residues, symbols, square roots), Chapter 5 (discrete logarithms).
- G. H. Hardy and E. M. Wright, *An Introduction to the Theory of Numbers*, 6th ed. —
  Chapters 5–8 (congruences, quadratic residues), Chapters 16–17 (arithmetic
  functions and Dirichlet series).
- K. Ireland and M. Rosen, *A Classical Introduction to Modern Number Theory*,
  Springer GTM 84 — reciprocity and higher-power residues.
- H. L. Montgomery and R. C. Vaughan, *Multiplicative Number Theory I: Classical
  Theory*, Cambridge — Chapters 1–4 (arithmetic functions, Dirichlet series,
  characters).
- A. M. Odlyzko and H. J. J. te Riele, "Disproof of the Mertens conjecture",
  *J. reine angew. Math.* **357** (1985).
- D. Shanks, "Class number, a theory of factorization, and genera" (1971) — the
  baby-step/giant-step idea and its use in class groups.
- [PARI/GP arithmetic functions](https://pari.math.u-bordeaux.fr/dochtml/html-stable/Arithmetic_functions.html)
  and [\((\mathbb{Z}/N\mathbb{Z})^\times\) and Dirichlet characters](https://pari.math.u-bordeaux.fr/dochtml/html/__backslashZslashNbackslashZ__star__and_Dirichlet_characters.html).
- Numerisect: [algebra laboratory](../ALGEBRA_LAB.md),
  [advanced number-theory workbenches](../ADVANCED_NUMBER_THEORY.md),
  [arithmetic and distribution tools](../ARITHMETIC_AND_DISTRIBUTION.md).
