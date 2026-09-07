# Primality

This page is the mathematical background for every primality feature in Numerisect:
what each test actually proves, what it merely makes likely, and where the boundary
between the two lies. It is written for a reader who is comfortable with elementary
number theory and modular arithmetic but who has not necessarily read Crandall and
Pomerance cover to cover — a graduate student, a serious hobbyist, or a programmer who
wants to know what the tool is doing before trusting its output. Each section ends by
naming the Numerisect tool that implements the idea and the library routine that
performs the computation; the feature pages
[Primality laboratory](../PRIMALITY_LAB.md),
[Prime classification](../PRIME_CLASSIFICATION.md) and
[Advanced number theory](../ADVANCED_NUMBER_THEORY.md) are the authoritative record of
those bindings, and nothing here contradicts them.

!!! note "The three verdicts"
    Numerisect reports **proven prime / proven composite**, **probable prime**, or
    **inconclusive**, and it never quietly promotes one to another. A probable prime is
    a number that has survived a compositeness test. Surviving is evidence. It is not a
    proof. An inconclusive result — a budget expired, a search bound reached, a
    criterion that simply does not apply — is never presented as a negative one. Keep
    those three words in mind; the rest of this page is largely about which category
    each classical test lands in.

## Trial division, and why it is only a screen

The definition of a prime is directly testable. If \( n > 1 \) has no divisor \( d \)
with \( 1 < d \le \sqrt{n} \), then \( n \) is prime, because a factorisation
\( n = ab \) with \( a \le b \) forces \( a \le \sqrt{n} \). Dividing by the primes
up to \( \sqrt{n} \) is therefore a complete and rigorous primality test.

It is also hopeless beyond small inputs. By the prime number theorem the number of
divisions is

\[
\pi(\sqrt{n}) \sim \frac{\sqrt{n}}{\tfrac12 \log n},
\]

which is exponential in the *bit length* of \( n \). For a 20-digit \( n \) that is
already about \( 4.5 \times 10^{8} \) divisions; for a 200-digit \( n \) it exceeds
the number of atoms in the observable universe. Doubling the length of the input squares
the work.

What trial division is genuinely good for is *screening*. Removing the primes below
\( 10^{6} \) costs about 78,498 divisions regardless of the size of \( n \), and it
disposes of the overwhelming majority of random composites: a random integer has a
factor below \( 10^{6} \) with probability roughly \( 1 - e^{-\gamma}/\log 10^{6} \approx
0.96 \) by Mertens' theorem. Every serious primality routine begins with such a screen,
including PARI's, and so does Numerisect's factoring strategy adviser.

!!! warning "A completed trial division bound is not a primality claim"
    If Numerisect strips factors below \( 10^{6} \) and finds none, the cofactor is
    *not* thereby prime. It is simply free of small factors. The strategy adviser records
    the bound reached and says so explicitly.

**In Numerisect.** Bounded trial division is a job backend (`pari_trial`) and the first
step of the factoring strategy adviser, `POST /api/factor-lab/strategy`; PARI/GP performs
the division. See [Factorization](factorization.md) for how the bound feeds into
algorithm choice.

## Fermat's little theorem and its pseudoprimes

The workhorse of all fast primality testing is Fermat's little theorem: if \( p \) is
prime and \( p \nmid a \), then

\[
a^{p-1} \equiv 1 \pmod p .
\]

The proof is one line. Multiplication by \( a \) permutes the nonzero residues modulo
\( p \), so \( \prod_{x=1}^{p-1} (ax) \equiv \prod_{x=1}^{p-1} x \pmod p \), and
cancelling the (invertible) product gives \( a^{p-1} \equiv 1 \).

Read contrapositively this is a **compositeness test**. If \( a^{n-1} \not\equiv 1
\pmod n \) for some \( a \) coprime to \( n \), then \( n \) is composite, proven,
with no appeal. The witness \( a \) is a certificate of compositeness that anybody can
check with one modular exponentiation — about \( \log_2 n \) squarings by
square-and-multiply, so the test costs \( O(\log n) \) multiplications of
\( \log n \)-bit numbers.

The trouble is the converse, which is false. A composite \( n \) with
\( a^{n-1} \equiv 1 \pmod n \) is a **Fermat pseudoprime to base \( a \)**. The
smallest base-2 example is

\[
341 = 11 \times 31, \qquad 2^{340} \equiv 1 \pmod{341}.
\]

Pseudoprimes are rare — there are 21,853 base-2 Fermat pseudoprimes below
\( 2.5 \times 10^{10} \), against roughly \( 10^{9} \) primes — so a base-2 Fermat
pass is strong evidence for a *random* input. It is worthless against an adversarial one,
and it is not a proof in either case.

**In Numerisect.** The Fermat step of the comparison laboratory
(`POST /api/primality-lab/compare`) and the base-2 Fermat pseudoprime scan in the
special-number range tool. Both are driven in GP over PARI `Mod` powering, because PARI's
own `ispseudoprime` reports only a combined Baillie–PSW verdict and the point of those
pages is to display each individual step.

## Carmichael numbers and Korselt's criterion

Fermat testing does not merely fail occasionally; for some composites it fails for
*every* base. A composite \( n \) with \( a^{n-1} \equiv 1 \pmod n \) for every
\( a \) coprime to \( n \) is a **Carmichael number**. The smallest is
\( 561 = 3 \times 11 \times 17 \); the sequence continues 1105, 1729, 2465, 2821, 6601,
8911. For such an \( n \) the set of Fermat liars is the whole group
\( (\mathbb{Z}/n\mathbb{Z})^{\times} \), so there are \( \varphi(n) \) of them —
\( \varphi(561) = 320 \) — and the only bases that reveal compositeness are those
sharing a factor with \( n \), which trial division would have caught anyway.

**Korselt's criterion.** A composite \( n \) is a Carmichael number if and only if
\( n \) is squarefree and \( p - 1 \mid n - 1 \) for every prime \( p \mid n \).

*Proof of the sufficient direction.* Suppose \( n = p_1 p_2 \cdots p_k \) is squarefree
with \( p_i - 1 \mid n - 1 \) for each \( i \), and let \( a \) be any integer. Fix
\( i \). If \( p_i \mid a \) then \( a^{n} \equiv 0 \equiv a \pmod{p_i} \).
Otherwise Fermat's little theorem gives \( a^{p_i - 1} \equiv 1 \pmod{p_i} \), and since
\( p_i - 1 \mid n - 1 \) we may write \( n - 1 = (p_i - 1)m \) and conclude
\( a^{n-1} = (a^{p_i-1})^{m} \equiv 1 \pmod{p_i} \), hence \( a^{n} \equiv a
\pmod{p_i} \). So \( a^{n} \equiv a \pmod{p_i} \) for every \( i \); as the
\( p_i \) are distinct primes, the Chinese remainder theorem gives \( a^{n} \equiv a
\pmod n \), and for \( \gcd(a,n) = 1 \) we may cancel \( a \) to obtain
\( a^{n-1} \equiv 1 \pmod n \). \( \square \)

The converse direction (a Carmichael number must be squarefree and satisfy the divisibility)
is proved by choosing \( a \) to be a primitive root modulo each prime power in turn;
it is not much longer, but it needs the structure of \( (\mathbb{Z}/p^{k}\mathbb{Z})^{\times} \)
and we omit it.

Two consequences fall straight out of the criterion and are worth doing, because they
explain the shape of every Carmichael number you will ever see.

*A Carmichael number is odd.* If \( n \) were even and squarefree it would have an odd
prime factor \( p \) (a Carmichael number is not a prime power), and then \( p - 1 \)
is even while \( n - 1 \) is odd, so \( p - 1 \nmid n - 1 \).

*A Carmichael number has at least three prime factors.* Suppose \( n = pq \) with
\( p < q \) prime. Then \( n - 1 = pq - 1 = p(q-1) + (p-1) \), so
\( q - 1 \mid n - 1 \) forces \( q - 1 \mid p - 1 \), impossible since
\( 0 < p - 1 < q - 1 \).

Chernick observed that \( (6k+1)(12k+1)(18k+1) \) is a Carmichael number whenever all
three factors are prime — the criterion is immediate, since each factor minus one divides
\( 36k \), which divides the product minus one. \( k = 1 \) gives 1729.

There are infinitely many Carmichael numbers; this was open for most of a century and was
settled by Alford, Granville and Pomerance, who showed that the count below \( x \)
exceeds \( x^{2/7} \) for large \( x \). Fermat testing therefore cannot be repaired
by trying more bases.

**In Numerisect.** The Carmichael analyser (`POST /api/primality-lab/carmichael`) applies
the exact Korselt criterion using PARI `factor`, `znstar` for the Carmichael function
\( \lambda(n) \) (the largest invariant factor of \( (\mathbb{Z}/n\mathbb{Z})^{\times} \)),
`eulerphi` and `gcd`, and counts Fermat liars over a bounded base range. The Chernick page
(`POST /api/primality-lab/chernick`) searches \( k \) with PARI `isprime` on all three
factors. Carmichael membership is also one of the special-number range scans.

## Euler and strong pseudoprimes

Fermat's congruence can be sharpened in two steps, and each step shrinks the set of liars.

### Euler–Jacobi

For an odd prime \( p \) and \( p \nmid a \), Euler's criterion says

\[
a^{(p-1)/2} \equiv \left( \frac{a}{p} \right) \pmod p,
\]

with the Legendre symbol on the right. Extending the symbol to the Jacobi symbol
\( \left( \frac{a}{n} \right) \) for odd \( n \) gives a test: if
\( a^{(n-1)/2} \not\equiv \left( \frac{a}{n} \right) \pmod n \) then \( n \) is
composite. A composite that passes is an **Euler pseudoprime** (or Euler–Jacobi
pseudoprime) to base \( a \). This is the Solovay–Strassen test. Its guarantee is that
for odd composite \( n \) the Euler liars form a proper subgroup of
\( (\mathbb{Z}/n\mathbb{Z})^{\times} \), hence at most \( \varphi(n)/2 \) of the bases
lie, so each round with a uniformly random base has error probability at most
\( 1/2 \).

### Strong (Miller–Rabin)

Write \( n - 1 = 2^{s} d \) with \( d \) odd. If \( n \) is prime then
\( \mathbb{Z}/n\mathbb{Z} \) is a field, so \( x^{2} = 1 \) has only the roots
\( \pm 1 \); walking the chain \( a^{d}, a^{2d}, a^{4d}, \dots, a^{2^{s-1}d} \) up to
\( a^{n-1} = 1 \), the first entry equal to 1 must have been preceded by \( -1 \), if
it was not 1 from the start. So for prime \( n \), either

\[
a^{d} \equiv 1 \pmod n
\qquad\text{or}\qquad
a^{2^{r} d} \equiv -1 \pmod n \text{ for some } 0 \le r < s .
\]

A composite passing this for base \( a \) is a **strong pseudoprime** to base \( a \);
a base for which it fails is a **witness** to compositeness, and a base for which it
passes is a **strong liar**. The implications are strict:

\[
\text{strong pseudoprime} \implies \text{Euler pseudoprime} \implies \text{Fermat pseudoprime},
\]

and neither arrow reverses in general.

### The 1/4 bound and why it is pessimistic

Monier and Rabin independently proved the bound that makes the test usable: for every odd
composite \( n > 9 \), the number of strong liars is at most \( \varphi(n)/4 \), hence
at most \( (n-1)/4 \). A single round with a uniformly random base therefore fails to
detect a composite with probability at most \( 1/4 \), and \( t \) independent rounds
with at most \( 4^{-t} \).

That is a worst case over all composites, and it is close to sharp — there exist
composites for which nearly a quarter of the bases are strong liars. But it is the wrong
number to quote for the situation that actually arises in practice, which is: *a random
odd integer of \( k \) bits has survived trial division and \( t \) Miller–Rabin
rounds; what is the chance it is composite?* That is a different question, because it
conditions on the input being random rather than adversarial, and almost all composites
have almost no strong liars at all.

Damgård, Landrock and Pomerance analysed exactly this quantity. Writing
\( p_{k,t} \) for the probability that a random odd \( k \)-bit number declared prime
after \( t \) rounds is in fact composite, they prove among other bounds

\[
p_{k,1} \le k^{2} \, 4^{\,2-\sqrt{k}} ,
\]

which for \( k = 500 \) is of order \( 10^{-7} \) — from a *single* round, against the
worst-case bound of \( 1/4 \). The gap is four decimal orders of magnitude even before
the second round.

!!! warning "The distinction matters and Numerisect keeps it"
    The Damgård–Landrock–Pomerance estimate applies to numbers drawn at random. It says
    nothing about a number handed to you by someone who wants you to believe it is prime;
    strong pseudoprimes to any fixed finite set of bases can be constructed deliberately.
    Whichever bound applies, the result is still a **probable prime**, and Numerisect
    labels it `probable`.

**In Numerisect.** The comparison laboratory runs Fermat, Euler–Jacobi, Miller–Rabin,
Lucas, strong Lucas and Frobenius steps side by side on one input over PARI `Mod` powering
and `kronecker`, with `isprime` shown separately as the rigorous reference. The
probable-prime taxonomy page (`POST /api/primality-lab/taxonomy`) classifies which of
those pseudoprime classes a given composite belongs to. The Miller–Rabin witness page
(`POST /api/primes/miller-rabin-witnesses`) implements the complete strong chain and, for
\( n \le 10^{6} \), enumerates every base from 2 to \( n-2 \) and reports exact
witness and liar counts.

## Deterministic Miller–Rabin below a bound

Miller's original test was deterministic under the extended Riemann hypothesis: if GRH
holds, every odd composite \( n \) has a strong witness below \( 2 (\log n)^{2} \)
(the explicit constant is Bach's). That is a genuine polynomial-time primality test, but
it is conditional, and Numerisect does not present conditional results as proofs.

Unconditionally, one can do the finite version. Let \( \psi_k \) be the smallest odd
composite that is a strong pseudoprime to all of the first \( k \) primes. For
\( n < \psi_k \), testing exactly those \( k \) bases is a **complete deterministic
test**: passing is a proof of primality, because the only composite that could pass is at
least \( \psi_k \). Computing \( \psi_k \) is hard work, and the published values are
the foundation of every fast 64-bit primality routine in existence.

| \( n \) below | Bases | Source |
|---|---|---|
| 2,047 | 2 | folklore; \( 2047 = 23 \times 89 \) is the smallest base-2 strong pseudoprime |
| 1,373,653 | 2, 3 | Pomerance, Selfridge and Wagstaff |
| 25,326,001 | 2, 3, 5 | Pomerance, Selfridge and Wagstaff |
| 3,215,031,751 | 2, 3, 5, 7 | Jaeschke |
| 2,152,302,898,747 | 2, 3, 5, 7, 11 | Jaeschke |
| 3,474,749,660,383 | 2, 3, 5, 7, 11, 13 | Jaeschke |
| 341,550,071,728,321 | first 7 primes | Jaeschke |
| 3,825,123,056,546,413,051 | first 9 primes | Jiang and Deng |
| 318,665,857,834,031,151,167,461 | first 12 primes | Sorenson and Webster |
| 3,317,044,064,679,887,385,961,981 | first 13 primes | Sorenson and Webster |

!!! example "3,215,031,751"
    This number is the smallest strong pseudoprime to all of 2, 3, 5 and 7 — it is
    \( 151 \times 751 \times 28351 \). It is exactly the reason the fourth row of the
    table has that bound and not a larger one, and it is a good input for the
    deterministic-witness page: four rounds say "probable prime", the fifth base exposes
    it.

Above the last tabulated bound **no sufficient set is known**, and Numerisect refuses to
extrapolate. The page reports `inconclusive` and points at APR-CL or ECPP. It does not
silently downgrade the verdict to `probable`, because the user asked for a proof.

**In Numerisect.** `POST /api/primality-lab/deterministic-witnesses`, over PARI `primes`,
`valuation` and `Mod` powering, cross-checked against `isprime`.

## Lucas sequences and the Lucas test

Fermat-style tests all live in \( (\mathbb{Z}/n\mathbb{Z})^{\times} \), and they all
share the same blind spot: a composite whose prime factors conspire to make orders
divide \( n-1 \). The cure is to work in a quadratic extension instead, so that the
relevant group order is \( n+1 \) rather than \( n-1 \).

Fix integers \( P, Q \) and set \( D = P^{2} - 4Q \). The **Lucas sequences** are

\[
U_{0}=0,\; U_{1}=1,\; U_{k+1}=P\,U_{k}-Q\,U_{k-1},
\qquad
V_{0}=2,\; V_{1}=P,\; V_{k+1}=P\,V_{k}-Q\,V_{k-1}.
\]

With \( P = 1, Q = -1 \) these are the Fibonacci and Lucas numbers. If \( \alpha,
\beta \) are the roots of \( x^{2} - Px + Q \), then \( U_k = (\alpha^k - \beta^k)/
(\alpha - \beta) \) and \( V_k = \alpha^k + \beta^k \); the sequences are the trace and
"norm-normalised difference" of powers in \( \mathbb{Z}[\alpha] \), which is why they
behave like exponentials in a quadratic field.

**The Lucas test.** If \( n \) is prime, \( \gcd(n, 2QD) = 1 \), and the Jacobi symbol
\( \left( \frac{D}{n} \right) = -1 \), then

\[
U_{n+1} \equiv 0 \pmod n .
\]

The reason is that \( \left( \frac{D}{n} \right) = -1 \) means \( x^2 - Px + Q \) is
irreducible modulo \( n \), so \( \alpha \) lives in \( \mathbb{F}_{n^2} \), the
Frobenius \( x \mapsto x^{n} \) swaps \( \alpha \) and \( \beta \), and
\( \alpha^{n+1} = \alpha \cdot \alpha^{n} = \alpha\beta = Q \) is fixed — from which
\( \alpha^{n+1} = \beta^{n+1} \) and hence \( U_{n+1} \equiv 0 \).

A composite passing this is a **Lucas pseudoprime** for \( (P,Q) \). For the Fibonacci
parameters the smallest is \( 323 = 17 \times 19 \), and \( 4181 = 37 \times 113 \) is
another.

**Strong Lucas.** Exactly as with Miller–Rabin, one can use the 2-adic structure. Write
\( n + 1 = 2^{s} d \) with \( d \) odd; the strong Lucas test passes when

\[
U_{d} \equiv 0 \pmod n
\qquad\text{or}\qquad
V_{2^{r} d} \equiv 0 \pmod n \text{ for some } 0 \le r < s .
\]

Strong Lucas pseudoprimes are a proper subset of Lucas pseudoprimes.

**Selfridge's parameter choice (Method A).** The test is only useful when \( D \) is a
non-residue, so \( D \) must be chosen per input. Selfridge's rule takes the first
\( D \) in the sequence

\[
5,\; -7,\; 9,\; -11,\; 13,\; -15,\; \dots
\]

with \( \left( \frac{D}{n} \right) = -1 \), then sets \( P = 1 \) and
\( Q = (1-D)/4 \). Two details matter. First, if \( \left( \frac{D}{n} \right) = 0 \)
for some small \( D \), you have found a factor and \( n \) is composite. Second, if
\( n \) is a perfect square then \( \left( \frac{D}{n} \right) \ne -1 \) for every
\( D \) and the search never terminates, so squareness must be tested first. The
point of the rule is that \( D \) depends on \( n \) in a way that an adversary
constructing a pseudoprime cannot fix in advance.

**In Numerisect.** The Lucas sequence page (`POST /api/primality-lab/lucas-sequence`)
computes \( U_k, V_k \) by PARI matrix powering over `Mod` — PARI 2.18 publishes no
`lucasU`/`lucasV` entry point — together with `kronecker` for the Jacobi symbol, and
`factor` and `isprime` for the \( N+1 \) side. The Lucas and strong-Lucas rows of the
comparison laboratory use the same machinery.

## Baillie–PSW

The Baillie–Pomerance–Selfridge–Wagstaff test combines the two families:

1. trial division by small primes;
2. a base-2 strong probable prime test;
3. a strong Lucas probable prime test with Selfridge's parameters.

Its appeal is structural rather than statistical. The two tests have different failure
modes: the base-2 strong test can be fooled by composites whose factors have order
dividing \( n-1 \), the Lucas test by composites arranged around \( n+1 \), and
Selfridge's rule ties the Lucas parameters to \( n \) so the two conditions cannot be
satisfied by accident in the same number. Empirically the two pseudoprime sets appear to
be nearly independent.

**No counterexample is known.** Feitsma and Galway enumerated all base-2 strong
pseudoprimes below \( 2^{64} \) and checked them against the Lucas condition; none
passes both. So BPSW is, in effect, a *proof* of primality for \( n < 2^{64} \) — and
PARI exploits this, as we will see under certificates.

**That is not a proof in general.** There is no theorem here. Pomerance gave a heuristic
argument that counterexamples not only exist but are infinite in number, the density
argument being that the two conditions, while hard to satisfy simultaneously by
construction, are not logically linked; a standing cash prize for a counterexample has
gone unclaimed for decades. A BPSW pass on a 300-digit number is therefore excellent
evidence and nothing more.

!!! warning
    PARI's `ispseudoprime(n)` is BPSW. PARI's `isprime(n)` is a proof. They are different
    functions and Numerisect never substitutes one for the other. The
    [independent verification page](../VERIFICATION.md) deliberately runs both, plus
    GMP's separate BPSW implementation, and marks which results are proofs and which are
    probable.

**In Numerisect.** `ispseudoprime` in the comparison laboratory and the taxonomy page;
`POST /api/verify/primality` runs PARI `isprime`, PARI `ispseudoprime` and GMP's
independent implementation on the same input and reports all three with their status.

## Proving primality

A compositeness test can only ever fail to find a proof. To *prove* primality you need a
theorem whose hypotheses you can verify and whose conclusion is "\( n \) is prime". The
classical route is to exhibit an element of large order, which forces \( n \) to be
prime by counting.

### Pocklington's \( N-1 \) theorem

Write \( N - 1 = F \cdot R \) with \( F \) **completely factored** and
\( \gcd(F, R) = 1 \). Suppose that for each prime \( q \mid F \) there is an integer
\( a_q \) with

\[
a_q^{\,N-1} \equiv 1 \pmod N
\qquad\text{and}\qquad
\gcd\!\left( a_q^{\,(N-1)/q} - 1,\; N \right) = 1 .
\]

Then every prime factor \( p \) of \( N \) satisfies \( p \equiv 1 \pmod{F} \).

*Why.* Let \( p \mid N \) and let \( e \) be the order of \( a_q \) modulo \( p \).
From the first condition \( e \mid N-1 \). From the second,
\( a_q^{(N-1)/q} \not\equiv 1 \pmod p \) — otherwise \( p \) would divide the gcd —
so \( e \nmid (N-1)/q \). Hence the full power of \( q \) dividing \( N-1 \) also
divides \( e \), and \( e \mid p-1 \) gives \( q^{v_q(N-1)} \mid p - 1 \). Doing this
for every prime \( q \mid F \) yields \( F \mid p-1 \).

The corollary is what you use: if additionally \( F > \sqrt{N} \), then every prime
factor of \( N \) is at least \( F + 1 > \sqrt{N} \), so \( N \) cannot be composite
and is prime. Brillhart, Lehmer and Selfridge pushed the requirement down to
\( F > N^{1/3} \) at the cost of a small extra computation on the cofactor, and gave the
matching \( N+1 \) criterion using Lucas sequences, which is what makes numbers with a
factorable \( N+1 \) provable.

The cost of Pocklington is not the exponentiations — those are cheap — it is the
requirement to factor enough of \( N - 1 \). That is why the method is decisive for
numbers of special form, where \( N-1 \) is factored by construction, and useless for a
random 200-digit prime.

**In Numerisect.** `POST /api/primality-lab/pocklington` performs the search for witnesses
\( a_q \) with PARI `factor`, `gcd` and `Mod` powering, and cross-checks the verdict with
`primecert(n, 1)` and `primecertisvalid`. Exceeding the witness limit or the factoring
budget is reported as **inconclusive**, never as a failure of primality.

### Pratt certificates

Pocklington applied recursively gives a self-contained proof object. A **Pratt
certificate** for \( p \) consists of a primitive root \( g \) modulo \( p \), the
complete factorisation of \( p - 1 \), and — recursively — a Pratt certificate for every
prime factor of \( p - 1 \). Verification checks \( g^{p-1} \equiv 1 \) and
\( g^{(p-1)/q} \not\equiv 1 \) for each \( q \mid p-1 \), which proves \( g \) has
order exactly \( p-1 \) and hence that \( (\mathbb{Z}/p\mathbb{Z})^{\times} \) has
\( p-1 \) elements, i.e. \( p \) is prime. The recursion is what makes the
factorisation of \( p-1 \) trustworthy: each claimed prime factor carries its own proof,
and the recursion bottoms out at 2.

Pratt's theorem is that this object is *succinct*: the tree has \( O(\log p) \) nodes and
verification costs \( O(\log^{2} p) \) modular multiplications. This is the classical
demonstration that primality lies in NP.

The catch is the same as before: constructing the certificate needs \( p-1 \), and each
\( q-1 \) beneath it, completely factored. Numerisect therefore bounds the tree.

**In Numerisect.** `POST /api/primality-lab/pratt`, over PARI `factor`, `znprimroot`,
`ispseudoprime` and `Mod` powering, with a node limit of 1 to 100,000. Reaching the node
limit or a factoring timeout truncates the tree and the verdict is `inconclusive`.
`POST /api/primality-lab/verify-certificate` re-derives the proof from the certificate
alone, using nothing but `isprime` on the leaves, `gcd` and `Mod` powering.

### Proth's theorem

Let \( N = k \cdot 2^{n} + 1 \) with \( k \) odd and \( k < 2^{n} \) (a **Proth
number**). Then \( N \) is prime if and only if there exists \( a \) with

\[
a^{(N-1)/2} \equiv -1 \pmod N .
\]

Both directions are short. If \( N \) is prime, Euler's criterion makes any \( a \)
with \( \left( \frac{a}{N} \right) = -1 \) work, and half of all residues qualify —
so a few small candidate bases suffice in practice. Conversely, the congruence is exactly
Pocklington's hypothesis with \( F = 2^{n} \) and \( q = 2 \): squaring gives
\( a^{N-1} \equiv 1 \), and \( a^{(N-1)/2} \equiv -1 \) means
\( \gcd(a^{(N-1)/2} - 1, N) = 1 \) unless \( N \mid a^{(N-1)/2}-1 \), which it is not.
The condition \( k < 2^{n} \) is what guarantees \( F = 2^{n} > \sqrt{N} \).

!!! note "When Proth says nothing"
    If \( N \) is a perfect square then no base has Jacobi symbol \( -1 \), so no
    \( a \) can satisfy the congruence and the theorem yields no verdict. Numerisect
    reports `inconclusive` in that case and displays the independent `isprime`
    cross-check separately, rather than reporting "not prime".

**In Numerisect.** `POST /api/primality-lab/proth` and the generalized base-\( b \)
variant, over PARI `kronecker`, `factor` and `Mod`, cross-checked against `isprime`;
`POST /api/primality-lab/proth-search` sweeps exponents. Proth membership is also class 38
of the [56-class classifier](../PRIME_CLASSIFICATION.md).

### Lucas–Lehmer for Mersenne numbers

For an odd prime \( p \), let \( M_p = 2^{p} - 1 \) and define
\( s_0 = 4 \), \( s_{i+1} = s_i^{2} - 2 \). Then

\[
M_p \text{ is prime} \iff s_{p-2} \equiv 0 \pmod{M_p}.
\]

This is a necessary *and sufficient* condition — a genuine two-way criterion, not a
probable-prime test — and it is the reason the largest known primes are Mersenne primes.
Its cost is \( p - 2 \) squarings modulo \( M_p \), and reduction modulo
\( 2^{p}-1 \) is a shift-and-add rather than a division, so with FFT multiplication the
whole proof is \( \tilde{O}(p^{2}) \) bit operations — quasi-quadratic in the exponent,
which for a general \( N \) of the same size would be out of reach.

**In Numerisect.** `POST /api/primality-lab/lucas-lehmer-steps` shows the residue trace
step by step. PARI publishes no Lucas–Lehmer routine, so the iteration is written in GP;
the residue trace is the point of the page. `POST /api/number-theory/special-form-test`
gives the verdict. Even perfect numbers are then built by Euclid–Euler as
\( 2^{q-1}(2^{q}-1) \) after \( M_q \) has been proven, in
`POST /api/primes/perfect`.

### Pépin for Fermat numbers

For \( F_n = 2^{2^{n}} + 1 \) with \( n \ge 1 \),

\[
F_n \text{ is prime} \iff 3^{(F_n - 1)/2} \equiv -1 \pmod{F_n}.
\]

This is Proth's theorem with \( k = 1 \) and the base pinned to 3, which works because
\( \left( \frac{3}{F_n} \right) = -1 \) for every \( n \ge 1 \) by quadratic
reciprocity and the fact that \( F_n \equiv 2 \pmod 3 \) and \( F_n \equiv 1 \pmod 4 \).
Like Lucas–Lehmer it is necessary and sufficient, and like Lucas–Lehmer it costs one
squaring chain — but the chain has \( 2^{n}-1 \) steps on numbers of \( 2^{n} \) bits,
so the work doubles in bit length at every index. Numerisect caps the Fermat family search
at index 20 for exactly this reason.

**In Numerisect.** `POST /api/number-theory/special-form-test`, kind `pepin`.

### APR-CL and ECPP

For a number of no special form, the two practical general proof methods are:

**APR-CL** (Adleman, Pomerance and Rumely, made practical by Cohen and Lenstra) works with
Jacobi sums and Gauss sums in cyclotomic rings, testing congruences that a prime must
satisfy in \( \mathbb{Z}[\zeta_p] \) for a set of small primes. Its running time is
\( (\log n)^{O(\log\log\log n)} \) — not polynomial, but the triple logarithm makes the
exponent effectively a small constant for any input you will ever type. It is fast and
robust for a few thousand digits. Its drawback is that it produces **no certificate**: the
only way to check an APR-CL result is to run APR-CL again.

**ECPP** (Goldwasser and Kilian; made practical by Atkin and Morain) replaces the group
\( (\mathbb{Z}/N\mathbb{Z})^{\times} \) with an elliptic curve group, whose order can be
chosen. The core statement is: let \( E \) be an elliptic curve over
\( \mathbb{Z}/N\mathbb{Z} \) with \( m \) points, suppose \( m = k q \) with \( q \)
prime and \( q > (N^{1/4}+1)^{2} \), and suppose there is a point \( P \) on \( E \)
with \( mP = \mathcal{O} \) and \( (m/q)P \ne \mathcal{O} \). Then \( N \) is prime.
Because the curve is chosen (via complex multiplication, from a discriminant \( D \)
whose class polynomial has a root mod \( N \)), one can always find an \( m \) that
factors usefully — which is precisely what \( N-1 \) methods cannot do. The proof then
recurses on \( q \), which is roughly half the size, giving a chain down to a small
prime. Heuristically it runs in \( O((\log N)^{4+\varepsilon}) \).

ECPP's decisive practical advantage is that it **emits a certificate**, and verifying the
certificate is far cheaper than producing it. That is the subject of the next section.

**In Numerisect.** `isprime(n, 2)` is APR-CL and `isprime(n, 3)` is ECPP; both appear in
the comparison laboratory alongside the probabilistic tests, and
`POST /api/primality-lab/ecpp-steps` displays the ECPP descent with `primecert`,
`primecertisvalid` and `coredisc`.

## Certificates and independent verification

A **primality certificate** is data that lets a third party re-derive the primality of
\( N \) with much less work than the original proof, using no trust in the prover. It is
the difference between "my computer said so" and "here is why, check it yourself". This
matters because primality software is complicated: a miscompiled library, a wrong
architecture flag, or a subtle carry bug will happily return `1`.

PARI's routines behave as follows, and it is worth knowing exactly what each one checks.

`primecert(N, 0)` returns an **ECPP certificate**: a list of steps, each giving the
current \( N \), the discriminant \( D \), the curve order \( m \), the prime
\( q \mid m \) to recurse on, the curve \( E \), and a point \( P \). For example,
the first step for \( N = 10^{30}+57 \) is

```text
 N = 1000000000000000000000000000057
 D = -3
 m = 999999999999998058691781125968
 q = 623786892692306107
 E = [0, 1]
 P = [519335238006017621936447751736, 51315546389334118416664791836]
```

`primecert(N, 1)` returns an **\( N-1 \) (Pocklington–Lehmer) certificate**: the number
together with the prime divisors of \( N - 1 \) that the proof rests on.

`primecertisvalid(cert)` re-runs the verification: for an ECPP certificate it checks, at
each step, that \( q \) really divides \( m \), that the size condition
\( q > (N^{1/4}+1)^{2} \) holds, that \( P \) lies on \( E \), and that the two
scalar multiplications behave as the theorem requires — then descends to the next step. It
returns 1 only if the whole chain checks out. This is genuinely independent of how the
certificate was produced.

!!! note "PARI short-circuits below \( 2^{64} \)"
    Ask PARI for a certificate for a prime below \( 2^{64} \) and it returns the number
    itself; `primecertexport` renders it as *"Indeed, `ispseudoprime(N) = 1` and
    \( N < 2^{64} \)."* That is not laziness, it is the Feitsma–Galway enumeration being
    used as a theorem: below \( 2^{64} \), a BPSW pass **is** a proof, because every
    base-2 strong pseudoprime in that range has been enumerated and none passes the Lucas
    test. Above \( 2^{64} \) you get a real certificate.

**In Numerisect.** `POST /api/primality-lab/verify-certificate` and
`POST /api/primes/verify-certificate` validate a supplied certificate from the certificate
alone. `POST /api/factor-lab/certificates` and `POST /api/jobs/{id}/certificates` build a
certificate for every prime factor of a factorisation with `primecert` and re-check each
one with `primecertisvalid`; a composite input is reported as not prime and not certified,
never as an error. A factor reported as *not certified* is **inconclusive**.

## Prime-generating families

Several of Numerisect's search and classification tools target families defined by a
formula. They are worth collecting here because they share a mathematical motive: for each
of them, \( N-1 \) or \( N+1 \) is factored *by construction*, so Pocklington or its
\( N+1 \) counterpart applies and a hit can be **proven**, not merely believed.

| Family | Form | \( N \mp 1 \) structure |
|---|---|---|
| Mersenne | \( 2^{p}-1 \) | \( N+1 = 2^{p} \); Lucas–Lehmer applies |
| Fermat | \( 2^{2^{n}}+1 \) | \( N-1 = 2^{2^{n}} \); Pépin applies |
| Proth | \( k \cdot 2^{n}+1 \), \( k \) odd, \( k < 2^{n} \) | \( N-1 = k \cdot 2^{n} \), and \( 2^n > \sqrt N \) |
| Cullen | \( n \cdot 2^{n}+1 \) | a Proth number when \( n < 2^{n} \), which is always |
| Woodall | \( n \cdot 2^{n}-1 \) | \( N+1 = n \cdot 2^{n} \); \( N+1 \) methods apply |
| Wagstaff | \( (2^{q}+1)/3 \), \( q \) odd prime | neither side is easy; large ones are only probable primes |
| Repunit | \( R_n = (10^{n}-1)/9 \) | \( n \) must be prime; \( N \pm 1 \) is generally hard |
| Factorial | \( n! \pm 1 \) | \( n! \) is factored by construction |
| Primorial | \( p\# \pm 1 \) | \( p\# \) is factored by construction |

Two further families are about *chains* rather than single values.

**Sophie Germain and safe primes.** \( p \) is a Sophie Germain prime when \( 2p+1 \)
is also prime; \( q = 2p+1 \) is then called a safe prime. The name records Germain's
work on the first case of Fermat's last theorem. Safe primes matter computationally
because \( q - 1 = 2p \) has no small factors other than 2, which makes the multiplicative
group modulo \( q \) free of small subgroups — the reason they appear in Diffie–Hellman
parameter generation.

**Cunningham chains.** A chain of the first kind is a sequence with
\( p_{i+1} = 2p_i + 1 \); of the second kind, \( p_{i+1} = 2p_i - 1 \). A chain of the
first kind of length 2 is exactly a Sophie Germain pair. Chains cannot be arbitrarily long
for a fixed starting residue: divisibility by small primes eventually intervenes, which is
what makes long chains rare and interesting.

Their expected densities are governed by the Bateman–Horn conjecture, which predicts the
number of \( n \le x \) at which a fixed set of irreducible polynomials is simultaneously
prime as a product of a singular series over primes and an integral. It is a conjecture,
and Numerisect labels every Bateman–Horn number as a prediction, never as a count.

!!! example "Proven and probable in the same family"
    The repunits \( R_2, R_{19}, R_{23}, R_{317}, R_{1031} \) are proven prime. The next
    several known repunit values that pass BPSW — at indices in the tens of thousands —
    are **probable primes only**. They are listed in reference works as PRPs, and a tool
    that reported them as prime would be wrong. Cullen primes are known at
    \( n = 1, 141, 4713, 5795, 6611, \dots \), Woodall at
    \( n = 2, 3, 6, 30, 75, 81, 115, 123, \dots \), Wagstaff at
    \( q = 3, 5, 7, 11, 13, 17, 19, 23, 31, 43, 61, 79, 101, 127, \dots \).

**In Numerisect.** `POST /api/number-theory/special-prime-family` searches the Mersenne,
Fermat, Cullen, Woodall, Wagstaff, repunit, primorial \( \pm 1 \) and factorial
\( \pm 1 \) families, and every value returned as prime has passed PARI `isprime`.
`POST /api/number-theory/cunningham-chain` walks both recurrences and includes the first
composite term when a requested chain fails.
`POST /api/primes/generate-special` generates safe and Sophie Germain primes at a
requested size. Family membership for a single input is covered by the classifier
(classes 7 Cullen, 13 factorial, 14 Fermat, 23 Mersenne, 37 primorial, 38 Proth, 41
repunit, 43 safe, 45 Sophie Germain, 51 Wagstaff, 56 Woodall). Predicted densities come
from `POST /api/distribution/bateman-horn`.

!!! warning "Constrained prime generation is educational"
    `POST /api/primality-lab/constrained-prime` builds safe primes and Gordon strong
    primes at a requested bit length, with every primality decision made by PARI/GP. It is
    **not audited cryptographic software and must not be used to generate production
    keys**. See [Primality laboratory](../PRIMALITY_LAB.md) for the full statement.

## Where this appears in Numerisect

| Topic | Tool | Engine routine |
|---|---|---|
| Trial-division screen | Strategy adviser, `pari_trial` backend | PARI/GP `factor` with a bound |
| Fermat, Euler–Jacobi, Miller–Rabin, Lucas, strong Lucas, Frobenius | Comparison laboratory, `POST /api/primality-lab/compare` | PARI `Mod` powering, `kronecker`, driven in GP |
| Pseudoprime classification of a composite | Probable-prime taxonomy, `POST /api/primality-lab/taxonomy` | PARI `ispseudoprime`, `kronecker`, `Mod`; `isprime` as reference |
| Strong witnesses and liars, exact counts | `POST /api/primes/miller-rabin-witnesses` | PARI `Mod` powering |
| Deterministic witness sets | `POST /api/primality-lab/deterministic-witnesses` | PARI `primes`, `valuation`, `Mod`; cross-checked with `isprime` |
| Carmichael numbers, Korselt | `POST /api/primality-lab/carmichael` | PARI `factor`, `znstar`, `eulerphi`, `gcd` |
| Chernick \( (6k+1)(12k+1)(18k+1) \) | `POST /api/primality-lab/chernick` | PARI `isprime` |
| Lucas sequences \( U_k, V_k \); \( N\pm1 \) | `POST /api/primality-lab/lucas-sequence` | PARI matrix powering over `Mod`, `kronecker`, `factor`, `isprime` |
| Baillie–PSW | Comparison laboratory; `POST /api/verify/primality` | PARI `ispseudoprime`, plus GMP's independent BPSW |
| Pocklington \( N-1 \) proof | `POST /api/primality-lab/pocklington` | PARI `factor`, `gcd`, `Mod`; `primecert(n,1)` + `primecertisvalid` |
| Pratt certificate tree | `POST /api/primality-lab/pratt` | PARI `factor`, `znprimroot`, `ispseudoprime`, `Mod` |
| Certificate verification | `POST /api/primality-lab/verify-certificate` | PARI `isprime`, `gcd`, `Mod`, re-derived from the certificate alone |
| Proth and generalized Proth | `POST /api/primality-lab/proth`, `/proth-search` | PARI `kronecker`, `factor`, `Mod`; cross-checked with `isprime` |
| Lucas–Lehmer residue trace | `POST /api/primality-lab/lucas-lehmer-steps` | GP iteration (PARI publishes no Lucas–Lehmer routine) |
| Lucas–Lehmer and Pépin verdicts | `POST /api/number-theory/special-form-test` | PARI arbitrary-precision arithmetic |
| APR-CL, ECPP | Comparison laboratory; `POST /api/primality-lab/ecpp-steps` | PARI `isprime(n,2)`, `isprime(n,3)`, `primecert`, `primecertisvalid`, `coredisc` |
| Batch certificates for factors | `POST /api/factor-lab/certificates`, `POST /api/jobs/{id}/certificates` | PARI `isprime`, `primecert`, `primecertisvalid` |
| Special families | `POST /api/number-theory/special-prime-family` | PARI `ispseudoprime`, `isprime` |
| Cunningham chains | `POST /api/number-theory/cunningham-chain` | PARI `isprime` |
| Safe and Sophie Germain generation | `POST /api/primes/generate-special` | PARI `isprime`, `nextprime` |
| Sierpiński/Riesel covering sets | `POST /api/primality-lab/sierpinski`, `/covering-set` | PARI `ispseudoprime`, `isprime`, `factor`, `Mod` |
| 56-class membership | `POST /api/primes/classify` | `numerisect/prime_classifier.gp` over PARI |

## References

- W. R. Alford, A. Granville and C. Pomerance, *There are infinitely many Carmichael
  numbers*, Annals of Mathematics **139** (1994), 703–722.
- L. M. Adleman, C. Pomerance and R. S. Rumely, *On distinguishing prime numbers from
  composite numbers*, Annals of Mathematics **117** (1983), 173–206.
- M. Agrawal, N. Kayal and N. Saxena, *PRIMES is in P*, Annals of Mathematics **160**
  (2004), 781–793.
- A. O. L. Atkin and F. Morain, *Elliptic curves and primality proving*, Mathematics of
  Computation **61** (1993), 29–68.
- E. Bach, *Explicit bounds for primality testing and related problems*, Mathematics of
  Computation **55** (1990), 355–380.
- R. Baillie and S. S. Wagstaff Jr., *Lucas pseudoprimes*, Mathematics of Computation
  **35** (1980), 1391–1417.
- J. Brillhart, D. H. Lehmer and J. L. Selfridge, *New primality criteria and
  factorizations of \( 2^{m} \pm 1 \)*, Mathematics of Computation **29** (1975),
  620–647.
- J. Chernick, *On Fermat's simple theorem*, Bulletin of the American Mathematical Society
  **45** (1939), 269–274.
- H. Cohen, *A Course in Computational Algebraic Number Theory*, Graduate Texts in
  Mathematics 138, Springer, 1993. Chapters 8 and 9.
- H. Cohen and H. W. Lenstra Jr., *Primality testing and Jacobi sums*, Mathematics of
  Computation **42** (1984), 297–330.
- R. Crandall and C. Pomerance, *Prime Numbers: A Computational Perspective*, 2nd edition,
  Springer, 2005. Chapters 3 and 4.
- I. Damgård, P. Landrock and C. Pomerance, *Average case error estimates for the strong
  probable prime test*, Mathematics of Computation **61** (1993), 177–194.
- S. Goldwasser and J. Kilian, *Almost all primes can be quickly certified*, Proceedings of
  the 18th ACM Symposium on Theory of Computing (1986), 316–329.
- G. Jaeschke, *On strong pseudoprimes to several bases*, Mathematics of Computation
  **61** (1993), 915–926.
- Y. Jiang and Y. Deng, *Strong pseudoprimes to the first eight prime bases*, Mathematics
  of Computation **83** (2014), 2915–2924.
- D. E. Knuth, *The Art of Computer Programming, Volume 2: Seminumerical Algorithms*, 3rd
  edition, Addison-Wesley, 1997, §4.5.4.
- D. H. Lehmer, *An extended theory of Lucas' functions*, Annals of Mathematics **31**
  (1930), 419–448.
- G. L. Miller, *Riemann's hypothesis and tests for primality*, Journal of Computer and
  System Sciences **13** (1976), 300–317.
- L. Monier, *Evaluation and comparison of two efficient probabilistic primality testing
  algorithms*, Theoretical Computer Science **12** (1980), 97–108.
- H. C. Pocklington, *The determination of the prime or composite nature of large numbers
  by Fermat's theorem*, Proceedings of the Cambridge Philosophical Society **18**
  (1914–16).
- C. Pomerance, *Are there counterexamples to the Baillie–PSW primality test?*, in *Dopo Le
  Parole aangeboden aan Dr. A. K. Lenstra*, Amsterdam, 1984.
- C. Pomerance, J. L. Selfridge and S. S. Wagstaff Jr., *The pseudoprimes to
  \( 25 \cdot 10^{9} \)*, Mathematics of Computation **35** (1980), 1003–1026.
- V. R. Pratt, *Every prime has a succinct certificate*, SIAM Journal on Computing **4**
  (1975), 214–220.
- M. O. Rabin, *Probabilistic algorithm for testing primality*, Journal of Number Theory
  **12** (1980), 128–138.
- H. Riesel, *Prime Numbers and Computer Methods for Factorization*, 2nd edition,
  Birkhäuser, 1994.
- R. Solovay and V. Strassen, *A fast Monte-Carlo test for primality*, SIAM Journal on
  Computing **6** (1977), 84–85; erratum **7** (1978), 118.
- J. Sorenson and J. Webster, *Strong pseudoprimes to twelve prime bases*, Mathematics of
  Computation **84** (2015), 2483–2498.

The enumeration of base-2 strong pseudoprimes below \( 2^{64} \), on which the
"no BPSW counterexample below \( 2^{64} \)" statement and PARI's short-circuit both rest,
is due to Feitsma and Galway and is distributed as a data set rather than as a paper.
