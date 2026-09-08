# Factorization

This page is the mathematical background for every factoring feature in Numerisect: what
each algorithm exploits, what determines its cost, and why the right choice depends as
much on the *shape* of the input as on its size. It assumes comfort with modular
arithmetic and a little group theory, but not familiarity with the sieve literature — it
is written for a graduate student, a serious hobbyist, or a programmer who wants to
understand what YAFU, GMP-ECM and CADO-NFS are doing before handing them a number. Each
section names the Numerisect tool that runs the algorithm and the engine that performs the
computation; the feature pages
[Expert factorization laboratory](../FACTOR_LAB.md),
[Factorization workspace](../FACTORIZATION.md) and
[Binary quadratic forms](../FORMS_LAB.md) are the authoritative record of those bindings,
and nothing here contradicts them.

!!! note "Companion page"
    Everything about deciding whether a number is prime — and in particular why
    "no factor found" is never a primality claim — is on
    [Primality](primality.md). The two pages are meant to be read together: a factoring
    run ends by labelling each part prime or composite, and that labelling is a separate
    mathematical act performed by a separate routine.

## Why factoring is hard

Multiplication is easy and inversion is not. Nothing in the definition of a composite
number tells you where its factors are, and the only structure a general integer offers is
its residues — which is why every practical method reaches for some auxiliary algebraic
object (a group, a ring of integers, a lattice of quadratic forms) whose behaviour
modulo an unknown prime \( p \) leaks information about \( p \).

Costs in this subject are quoted with the sub-exponential \( L \)-notation

\[
L_{N}[\alpha, c] = \exp\!\Big( \big(c + o(1)\big) (\ln N)^{\alpha} (\ln\ln N)^{1-\alpha} \Big),
\]

which interpolates between polynomial time (\( \alpha = 0 \)) and exponential time in
the bit length (\( \alpha = 1 \)). Smaller \( \alpha \) is a qualitatively better
algorithm; for equal \( \alpha \), smaller \( c \) is a constant-factor-style
improvement that nevertheless matters enormously at cryptographic sizes.

### The distinction that governs everything

Factoring algorithms split into two families, and confusing them is the most common
practical mistake.

**Factor-size algorithms.** The running time depends on the size of the factor
\( p \) that is found, and only mildly (through the cost of arithmetic modulo \( N \))
on the size of \( N \). Trial division, Pollard rho, Pollard \( p-1 \), Williams
\( p+1 \), SQUFOF and ECM are all of this kind. They are the right tools when you
suspect a small factor hides inside a large number, and they can be run on a 200-digit
input all day without ever "reaching" a 100-digit factor.

**Input-size algorithms.** The running time depends on \( N \) alone and is essentially
the same whether \( N \) is a product of two equal primes or of a hundred. The quadratic
sieve and the number field sieve are of this kind. They are the right tools when the small
factors have already been removed and what remains is a hard semiprime.

| Algorithm | Cost governed by | Complexity |
|---|---|---|
| Trial division | smallest factor \( p \) | \( O(p / \log p) \) divisions |
| Pollard rho | smallest factor \( p \) | \( O(\sqrt{p}) = O(N^{1/4}) \) expected |
| Pollard \( p-1 \), Williams \( p+1 \) | smoothness of \( p \mp 1 \) | \( O(B_1 \log p) \) plus stage two |
| SQUFOF | \( N \) | \( O(N^{1/4}) \), restricted to machine words |
| ECM | size of \( p \) | \( L_{p}[1/2, \sqrt{2}\,] \) |
| QS / SIQS | \( N \) | \( L_{N}[1/2, 1] \) |
| GNFS | \( N \) | \( L_{N}[1/3, (64/9)^{1/3} \approx 1.923] \) |
| SNFS | \( N \) | \( L_{N}[1/3, (32/9)^{1/3} \approx 1.526] \) |

The practical consequence is the standard pipeline: strip small factors, spend a budgeted
amount of effort on ECM in case a medium factor exists, and only then commit to a sieve
whose cost you can predict in advance from the digit count alone.

**In Numerisect.** The strategy adviser `POST /api/factor-lab/strategy` walks exactly this
decision tree in PARI/GP and returns the path it took together with the recommended
engine.

## Trial division

Dividing by \( 2, 3, 5, 7, \dots \) up to a bound \( B \) removes every factor below
\( B \) at a cost of \( \pi(B) \) divisions. It is not a factoring algorithm for
serious inputs, but it is a mandatory first step for two reasons: most composites have a
tiny factor, and every subsequent algorithm's analysis assumes small factors are gone
(rho wastes its cycle on them; the sieves waste factor-base primes on them).

!!! warning
    A completed trial-division bound is a statement about *the absence of small factors*,
    nothing more. Numerisect records the bound with the job and the strategy response
    states it explicitly; it never presents an exhausted bound as a proof of primality.

**In Numerisect.** The `pari_trial` job backend, YAFU's `trial` entry point, and the
bounded pre-pass inside the strategy adviser.

### Trial factoring a Mersenne number

Special forms can make trial factoring much thinner than ordinary trial division. Let
\(p\) be an odd prime and let \(q\) be a prime divisor of \(M_p=2^p-1\). The order of 2
modulo \(q\) is \(p\), so \(p\mid q-1\); since \(q\) is odd,

\[
q=2kp+1.
\]

Moreover, \(2^{(q-1)/2}=(2^p)^k\equiv1\pmod q\), so 2 is a quadratic residue modulo
\(q\). The supplementary law for the Legendre symbol then gives
\(q\equiv\pm1\pmod8\). This retains two of the four possible odd residue classes—one
half of the \(2kp+1\) progression.

A candidate is a divisor exactly when

\[
2^p\equiv1\pmod q.
\]

That modular exponentiation never requires constructing \(M_p\). A completed finite
\(k\)-range proves only that no divisor occurred in the tested range; it says nothing
about primality of \(M_p\). Lucas–Lehmer answers that different question.
The exceptional exponent \(p=2\) gives the already-prime value \(M_2=3\) and does not
belong to the \(2kp+1\) search.

**In Numerisect.** `POST /api/factor-lab/mersenne-factors`, documented in
[Mersenne numbers](../MERSENNE.md). PARI/GP screens candidates with `ispseudoprime` and
performs the exact modular divisibility test. The separately pinned examples are
rechecked with `isprime` in the test suite.

## Fermat's method, and when the factors are close

If \( N = ab \) with \( a \le b \) both odd, then setting
\( x = (a+b)/2 \) and \( y = (b-a)/2 \) gives

\[
N = x^{2} - y^{2} = (x-y)(x+y).
\]

Fermat's method searches for that representation directly: start at
\( x = \lceil \sqrt{N} \rceil \), test whether \( x^{2} - N \) is a perfect square,
increment, repeat. Every step is one squaring and one square test.

Its cost is the distance from \( \sqrt{N} \) to \( (a+b)/2 \), which is

\[
\frac{a+b}{2} - \sqrt{ab} = \frac{(\sqrt{b} - \sqrt{a})^{2}}{2}.
\]

So the method is superb when \( a \) and \( b \) are close and catastrophic otherwise:
for a balanced semiprime it finds the split almost immediately, and for
\( N = 3 \cdot p \) it is worse than trial division. This is not a curiosity. Keys
generated by a faulty routine that draws two primes from a narrow interval are broken by
Fermat's method in milliseconds, and it is worth running for a few thousand steps on any
input whose provenance you do not know.

Lehman turned the idea into a deterministic \( O(N^{1/3}) \) algorithm by applying
Fermat's search to \( kN \) for a range of small multipliers \( k \), which shifts the
effective ratio of the two factors.

**In Numerisect.** YAFU's `fermat` entry point, exposed as the `yafu_fermat` job backend,
with the trial bound `-fmtmax` configurable in the expert parameters.

## Pollard rho

Pollard's rho method is the cheapest algorithm that finds a factor without knowing
anything about it. Fix a polynomial map, conventionally
\( f(x) = x^{2} + c \) with \( c \ne 0, -2 \), and iterate it modulo \( N \):

\[
x_{0} = 2, \qquad x_{i+1} = f(x_{i}) \bmod N .
\]

Now consider the same sequence modulo an unknown prime factor \( p \). Because there are
only \( p \) residues, the sequence \( x_i \bmod p \) must eventually repeat, and it
does so far sooner than the sequence modulo \( N \). When \( x_i \equiv x_j \pmod p \)
but \( x_i \not\equiv x_j \pmod N \), the value \( \gcd(x_i - x_j, N) \) is a proper
factor.

### The birthday heuristic

Model \( f \) as a random map on \( \mathbb{Z}/p\mathbb{Z} \). By the birthday
paradox, a collision among \( k \) values is expected once \( k \approx \sqrt{p} \);
more precisely the expected rho length (tail plus cycle) of a random map on \( p \)
points is \( \sqrt{\pi p / 2} \). So the method finds \( p \) in
\( O(\sqrt{p}) \) iterations, and since the smallest factor of a composite \( N \)
satisfies \( p \le \sqrt{N} \), rho terminates in \( O(N^{1/4}) \) expected steps.

This is a *heuristic*, not a theorem: \( x^2 + c \) is not a random map, and no
unconditional \( O(N^{1/4}) \) bound for rho is known. In practice the heuristic is
accurate.

### Cycle detection

You cannot compare \( x_i \) with every earlier \( x_j \), so you need a cycle
detector that uses \( O(1) \) memory.

**Floyd.** Advance a "tortoise" one step and a "hare" two steps per iteration and test
\( \gcd(x_i - x_{2i}, N) \). Simple, and it costs three function evaluations per
iteration.

**Brent.** Compare against a stored value that is refreshed at powers of two, testing
\( x_i \) against \( x_{2^{k}-1} \) for \( 2^{k} \le i < 2^{k+1} \). This needs only
one function evaluation per step, and Brent's analysis shows roughly a 25 per cent saving
over Floyd overall. Brent's variant also accumulates the differences into a running
product and takes a single gcd every hundred or so steps, since gcd is far more expensive
than a modular multiplication; if the batched gcd equals \( N \), one backtracks and
takes the gcds individually.

!!! warning "Rho can return \( N \) itself"
    If the sequence collides modulo every prime factor at the same step — which happens
    when the factors are equal or the batch was too large — the gcd is \( N \) and the
    run has failed for that polynomial. The remedy is a different \( c \), not a
    conclusion about \( N \). An exhausted rho run is **inconclusive**.

**In Numerisect.** YAFU's `rho` (Pollard–Brent) as the `yafu_rho` backend, with `-rhomax`
in the expert parameters. A bounded, step-by-step trace of the algorithm — showing each
\( x_i \), each difference, and each gcd — is available from
`POST /api/factor-lab/trace` and is computed in PARI/GP. That trace exists to teach the
method and is explicitly **not** the production factoring path.

## Pollard \( p-1 \) and Williams \( p+1 \)

These two methods exploit a different accident: that the *order of a group attached to
\( p \)* may be smooth, i.e. have only small prime factors.

### \( p - 1 \)

Suppose \( p \mid N \) and \( p - 1 \) is \( B_1 \)-powersmooth, meaning every prime
power dividing \( p-1 \) is at most \( B_1 \). Let

\[
M = \prod_{q \le B_{1}} q^{\lfloor \log_{q} B_{1} \rfloor}
\]

be the product of prime powers below the bound. Then \( (p-1) \mid M \), so by Fermat's
little theorem \( a^{M} \equiv 1 \pmod p \) for any \( a \) coprime to \( p \).
Compute \( a^{M} \bmod N \) by repeated exponentiation — never modulo \( p \), which
is unknown — and take

\[
g = \gcd\!\left( a^{M} - 1,\; N \right).
\]

If \( 1 < g < N \) you have a factor. Stage one costs \( O(B_1) \) modular
multiplications by \( \sum_{q \le B_1} \log_q B_1 \approx B_1/\ln B_1 \cdot \ln B_1 \)
bits of exponent.

**Stage two** handles the common case where \( p - 1 = s \cdot q \) with \( s \)
\( B_1 \)-powersmooth and one remaining prime \( q \) between \( B_1 \) and a second
bound \( B_2 \gg B_1 \). Having computed \( b = a^{M} \), one tests
\( \gcd(b^{q} - 1, N) \) for each prime \( q \in (B_1, B_2] \). Done naively that is
one exponentiation per prime; done properly, the primes in that range are enumerated by
their gaps, so consecutive \( b^{q} \) differ by a multiplication by a small
precomputed power, and the gcds are batched into one product. Stage two is therefore
cheap per prime, which is why \( B_2 \) is typically 50 to 100 times \( B_1 \).

### \( p + 1 \)

Williams' method replaces \( (\mathbb{Z}/p\mathbb{Z})^{\times} \), of order
\( p-1 \), with the group of norm-one elements of
\( \mathbb{F}_{p^{2}}^{\times} \), of order \( p+1 \), realised through Lucas
sequences: one computes \( V_{M}(P, 1) \bmod N \) and takes
\( \gcd(V_{M} - 2, N) \). It succeeds when \( p+1 \) is smooth.

There is a catch that is easy to overlook. The construction only lands in the order-\( (p+1) \)
group when \( P^{2} - 4 \) is a quadratic *non*-residue modulo \( p \). Since \( p \)
is unknown, \( P \) is chosen at random; about half the time the symbol is \( +1 \),
the element lies in the order-\( (p-1) \) subgroup, and the method silently degenerates
into a slower Pollard \( p-1 \). This is why \( p+1 \) is run with several values of
\( P \), and why in practice it earns its keep less often than \( p-1 \).

!!! note "Both methods are gambles on a specific structure"
    \( p-1 \) and \( p+1 \) find a factor only if that particular group order happens
    to be smooth. There is nothing to tune your way out of: if \( p-1 \) has two large
    prime factors, no \( B_1 \) you can afford will help. This is exactly the limitation
    ECM removes.

**In Numerisect.** YAFU's `pm1` and `pp1` as the `yafu_pm1` and `yafu_pp1` backends, with
`-B1pm1`/`-B2pm1` and `-B1pp1`/`-B2pp1` exposed in the expert parameters. A bounded PARI/GP
trace of \( p-1 \) stage one is available from `POST /api/factor-lab/trace`. Safe primes
— see [Primality](primality.md) — are precisely the primes engineered to defeat
\( p-1 \).

## The elliptic curve method

ECM is Lenstra's generalisation of \( p-1 \), and the generalisation is the whole point.
In \( p-1 \) you are stuck with one group, \( (\mathbb{Z}/p\mathbb{Z})^{\times} \), of
one fixed order \( p-1 \); if that order is not smooth, the method fails and there is
nothing to retry. ECM replaces it with the group of points on an elliptic curve
\( E \) over \( \mathbb{F}_{p} \), whose order satisfies Hasse's bound

\[
\big| \#E(\mathbb{F}_{p}) - (p+1) \big| \le 2\sqrt{p},
\]

and — crucially — **varies with the curve**. Choosing a new curve draws a new group order
from an interval of width \( 4\sqrt{p} \) around \( p+1 \). Sooner or later one of
those orders is smooth.

### How it runs without knowing \( p \)

All arithmetic is done on a curve over \( \mathbb{Z}/N\mathbb{Z} \), which is not a
field, so the group law is not well defined. That is the mechanism, not a bug: computing
\( M \cdot P \) for the same smooth multiplier \( M \) as in \( p-1 \) requires a
modular inverse at each addition, and the inversion fails — the extended Euclidean
algorithm returns a nontrivial \( \gcd(\cdot, N) \) — exactly when the accumulated point
has become the identity modulo \( p \) but not modulo \( N \). The failed inversion
*is* the factor. (In practice implementations use Montgomery curves and projective
coordinates so that no inversions occur inside the loop, and take a single gcd of the
accumulated \( Z \)-coordinate at the end of the stage.)

### The parameters

| Parameter | Meaning |
|---|---|
| \( B_1 \) | stage-one smoothness bound; the multiplier is \( \prod_{q \le B_1} q^{\lfloor \log_q B_1 \rfloor} \) |
| \( B_2 \) | stage-two bound; allows one prime factor of the group order in \( (B_1, B_2] \) |
| curve count | how many independent curves to try at that \( B_1 \) |
| \( \sigma \) | the seed that determines the curve (Suyama's parametrisation); recording it makes a hit reproducible |

The expected running time to find a factor \( p \) is
\( L_{p}[1/2, \sqrt{2}\,] \), which depends on \( p \), not on \( N \) — the size of
\( N \) enters only through the cost of one modular multiplication. That is what makes
ECM the only method able to pull a 40-digit factor out of a 300-digit number.

### The expected-work table

For each target factor size there is an optimal \( B_1 \), and an expected number of
curves at that \( B_1 \) before a factor of that size is found. The table below was
produced by asking the installed GMP-ECM for its own estimate, not copied from a
secondary source; you can reproduce any row with

```bash
echo 1000000000000000000000000000057 | ecm -v -c 1 <B1>
```

and reading the "Expected number of curves to find a factor of n digits" line.

| \( B_1 \) | 35 digits | 40 digits | 45 digits | 50 digits | 55 digits | 60 digits |
|---|---|---|---|---|---|---|
| 11,000 | 3,967,858 | \( 2.5 \times 10^{8} \) | \( 2 \times 10^{10} \) | — | — | — |
| 50,000 | 88,265 | 2,402,639 | \( 8.1 \times 10^{7} \) | \( 3.3 \times 10^{9} \) | \( 2.3 \times 10^{11} \) | \( 1.5 \times 10^{17} \) |
| 250,000 | 6,022 | 87,544 | 1,534,319 | \( 3.1 \times 10^{7} \) | \( 7.5 \times 10^{8} \) | \( 2 \times 10^{10} \) |
| 1,000,000 | **1,071** | 10,283 | 118,226 | 1,565,171 | \( 2.4 \times 10^{7} \) | \( 3.9 \times 10^{8} \) |
| 3,000,000 | 374 | **2,753** | 24,017 | 241,048 | 2,713,723 | \( 3.4 \times 10^{7} \) |
| 11,000,000 | 138 | 788 | **5,208** | 39,497 | 336,066 | 3,167,410 |
| 43,000,000 | 61 | 278 | 1,459 | **8,704** | 57,844 | 419,970 |

The bold entries are the conventional working points: \( B_1 = 10^{6} \) with about a
thousand curves is a "t35" campaign, \( B_1 = 3 \times 10^{6} \) with about 2,800 curves
is "t40", and so on. Reading a column downwards shows why raising \( B_1 \) past the
optimum wastes time, and reading a row rightwards shows the steep cost of each extra five
digits.

!!! note "What completing a t-level does and does not tell you"
    Finishing a t40 campaign without a hit does not prove that \( N \) has no 40-digit
    factor. The curve counts are *expected* values for a Poisson-like process; the
    probability of having missed an existing factor after the expected number of curves is
    roughly \( 1/e \). What a completed t-level gives you is a *planning* statement: a
    factor of that size is now unlikely, so the remaining cofactor is probably a balanced
    semiprime and a sieve is the right next step.

**In Numerisect.** Two paths. YAFU's `ecm` as the `yafu_ecm` backend for a quick pretest,
with `-B1ecm`, `-B2ecm` and `-sigma` exposed; and the **ECM campaign manager**, a job
backend running GMP-ECM directly with `-B1`, `-B2`, `-c`, `-sigma`, `-param`, `-save` and
`-resume`, so that a cancelled campaign resumes from its stage-one residues rather than
repeating completed curves. GMP-ECM performs the whole computation including the primality
labelling of what it finds. A campaign that finishes its curves without splitting the input
reports an explicit **inconclusive** failure; it never implies the input is prime.

!!! warning "Reconciling GMP-ECM's output"
    GMP-ECM peels factors off across successive curves and prints each as it is found, so
    the raw list can overlap and need not multiply back to \( N \). Numerisect passes
    that list to PARI/GP (`fl_reconcile`), which divides the candidates out, reports the
    prime powers actually present, decides primality, and returns the cofactor. Nothing is
    divided out in Python, and the recorded parts always multiply back to the input.

## SQUFOF

Shanks' **square forms factorization** is a beautiful \( O(N^{1/4}) \) method that is
simultaneously among the fastest ways to split a number that fits in a machine word and
completely useless above that range. Shanks devised it in the mid-1970s and never
published a full description; the standard modern analysis is by Gower and Wagstaff.

The setting is binary quadratic forms. A form \( (a, b, c) \) represents
\( ax^{2} + bxy + cy^{2} \) and has discriminant \( b^{2} - 4ac \). SQUFOF works with
forms of discriminant \( D = 4kN \) for a small multiplier \( k \), and walks the
**principal cycle** — the cycle of reduced forms equivalent to the identity — by repeated
single-step reduction. Since \( D > 0 \) the forms are indefinite, and reduction has no
unique fixed point: each class is a periodic cycle, which is exactly what makes a walk
possible.

The target is an **ambiguous** form, one with \( a \mid b \) or \( a = c \). Such a
form's class is its own inverse: in the first case the substitution
\( (x,y) \mapsto (x - (b/a)y,\, y) \) and in the second \( (x,y) \mapsto (-y, x) \)
carries \( (a, b, c) \) to \( (a, -b, c) \). An ambiguous form in the principal cycle
of discriminant \( 4kN \) exposes a factor of \( N \) in its leading coefficient. The
algorithm finds one by walking forward until it meets a form whose \( a \) is a perfect
square, then walking the "inverse square root" form backwards to the ambiguous form — the
step that gives the method its name.

!!! example "The link is literal, not an analogy"
    For \( N = 1817 = 23 \times 79 \) and \( D = 4N = 7268 \), the principal cycle has
    28 reduced forms and contains \( \mathrm{Qfb}(23, 46, -56) \). Here
    \( 23 \mid 46 \), so the form is ambiguous, and 23 is precisely the factor the
    implementation extracts. [The forms laboratory](../FORMS_LAB.md) enumerates that cycle
    directly and flags every ambiguous form; it shows the object SQUFOF searches without
    factoring with it.

### Why it is a 64-bit method

The coefficients of reduced forms of discriminant \( D \) are of size \( O(\sqrt{D}) \),
and the inner loop is a handful of additions, multiplications and one division per step —
all of which fit in machine registers when \( 4kN \) does. That register arithmetic *is*
the speed of SQUFOF. Once \( 4kN \) exceeds the word size the loop needs
multiprecision arithmetic, the constant factor collapses, and SIQS is faster anyway.
Numerisect's implementation therefore requires \( N < 2^{62} \) and **rejects larger
inputs with an explicit message** rather than answering slowly or incorrectly.

The other honest limit is that SQUFOF can fail. The walk may complete its iteration budget
without meeting a usable ambiguous form, in which case the run reports
`status: exhausted`. That is **inconclusive**: it is not a claim that the input is prime.

**In Numerisect.** `numerisect/native/numerisect_squfof.c`, a C program in this project
using GMP for input parsing and the range check, with the cycle itself running in 64-bit
registers with 128-bit intermediate products. It exists because SQUFOF was verified absent
from every installed engine: YAFU exposes no `squfof` command, PARI implements it inside
`factorint` but publishes no GP entry point (flag 4 of `factorint` disables it only
together with Pollard–Brent rho), Msieve implements MPQS and NFS only, and GMP-ECM
implements ECM, \( p-1 \) and \( p+1 \) only. Reachable as
`POST /api/factor-lab/squfof` and as the `squfof` job backend. Both parts of a split are
labelled prime or composite by PARI/GP's `isprime`; the C helper never labels primality
itself.

## Congruences of squares: QS and SIQS

Every sieve method rests on one observation. If

\[
x^{2} \equiv y^{2} \pmod N \qquad \text{with} \qquad x \not\equiv \pm y \pmod N,
\]

then \( N \mid (x-y)(x+y) \) while \( N \) divides neither factor, so
\( \gcd(x - y, N) \) is a proper divisor. If \( N \) has at least two distinct odd
prime factors, a random such congruence splits \( N \) with probability at least
\( 1/2 \), so a handful of independent congruences suffices.

The problem is manufacturing them. Dixon's method takes random \( x \), factors
\( x^{2} \bmod N \) over a fixed **factor base** of small primes, keeps the ones that
factor completely (the *smooth relations*), and then finds a subset whose product is a
square by solving a linear system modulo 2 over the exponent vectors.

### The quadratic sieve

Pomerance's improvement is to stop choosing \( x \) at random and instead evaluate a
polynomial whose values are small and can be *sieved*. With
\( m = \lceil \sqrt{N} \rceil \), take

\[
Q(t) = (t + m)^{2} - N ,
\]

so that \( Q(t) \equiv (t+m)^{2} \pmod N \) automatically, and \( |Q(t)| \approx
2t\sqrt{N} \) is small for \( t \) in a modest interval. Three things now work in your
favour:

1. **The factor base halves.** A prime \( p \) can divide \( Q(t) \) only if \( N \)
   is a quadratic residue modulo \( p \), so the factor base contains only the primes
   with \( \left( \frac{N}{p} \right) = 1 \), together with \( -1 \) and 2.
2. **Sieving replaces trial division.** For each factor-base prime \( p \), solving
   \( Q(t) \equiv 0 \pmod p \) gives two roots modulo \( p \); the positions divisible
   by \( p \) then form two arithmetic progressions, and you subtract \( \log p \)
   from an array of accumulators at those positions. Positions whose accumulator ends up
   near \( \log|Q(t)| \) are the smooth candidates. No division is performed in the
   inner loop, which is why the method is fast.
3. **The linear algebra is sparse.** Each relation gives an exponent vector modulo 2 over
   the factor base; with one more relation than factor-base elements, a nontrivial kernel
   vector exists and yields a congruence of squares.

Optimising the factor-base size against the smoothness probability gives the running time
\( L_{N}[1/2, 1] \).

**MPQS and SIQS.** A single polynomial's values grow as you move away from the centre of
the interval, so smooth values become rare. Silverman's **multiple polynomial** variant
switches to a fresh polynomial \( (at+b)^{2} - N \) once the values get too large,
keeping \( |Q| \) small everywhere. The **self-initialising** variant (SIQS) chooses
\( a \) as a product of several factor-base primes so that a whole family of \( b \)
values — and hence a whole family of polynomials — shares one expensive initialisation;
switching polynomials then costs almost nothing, and this is the form used by every
current implementation.

**Large primes.** A relation that is smooth except for one leftover prime slightly above
the factor-base bound is not thrown away: two such *partial* relations sharing the same
large prime multiply to a full relation. The single- and double-large-prime variations
raise the yield substantially at the cost of more bookkeeping in the filtering step.

**The linear algebra step.** The matrix has hundreds of thousands to millions of columns
but only a few dozen nonzero entries per column. Gaussian elimination destroys that
sparsity and is used only for small jobs; production implementations use Montgomery's
block Lanczos algorithm or Wiedemann's method, both of which work with the matrix through
matrix–vector products and never form the fill-in.

**In Numerisect.** YAFU's `siqs` as the `yafu_siqs` backend, with `-siqsB` (factor base),
`-siqsTF` (trial-division bound), `-siqsR` (relations), `-siqsT` (timeout), `-siqsNB`
(blocks) and `-siqsM` (multiplier) exposed as expert parameters. Msieve provides an
independent MPQS implementation, used both as a backend and as the second opinion in
cross-check mode. PARI's `factorint` also contains MPQS, and
`POST /api/structure/factorint-strategies` races `factorint` under different strategy masks
so you can watch MPQS being enabled and disabled.

## The number field sieve

The number field sieve is the fastest known general factoring algorithm, and the only one
in the \( L_N[1/3, \cdot] \) class. Its idea is to build the congruence of squares in two
places at once: in \( \mathbb{Z} \), and in the ring of integers of an algebraic number
field.

### The polynomial pair

Choose two irreducible polynomials \( f, g \in \mathbb{Z}[x] \) with a **common root
\( m \) modulo \( N \)**:

\[
f(m) \equiv g(m) \equiv 0 \pmod N .
\]

The classical base-\( m \) construction takes \( g(x) = x - m \) with
\( m \approx N^{1/d} \) and \( f \) the degree-\( d \) polynomial whose coefficients
are the base-\( m \) digits of \( N \). Let \( \alpha \) be a root of \( f \) in
\( \mathbb{C} \); then there is a ring homomorphism
\( \mathbb{Z}[\alpha] \to \mathbb{Z}/N\mathbb{Z} \) sending \( \alpha \mapsto m \),
and that homomorphism is the bridge between the two sides.

Polynomial selection is not a detail. The yield of the sieve depends on the size of the
values \( f \) takes, and a good polynomial can be worth a factor of several in total
run time; modern implementations spend a meaningful fraction of the whole budget searching
for one.

### Sieving

For coprime pairs \( (a, b) \) with \( b > 0 \) over a large region, one asks that
both

\[
a - bm \quad\text{(the \textit{rational} side)}
\qquad\text{and}\qquad
b^{\deg f} f(a/b) \quad\text{(the \textit{algebraic} side; the norm of } a - b\alpha \text{ up to the leading coefficient of } f)
\]

be smooth over their respective factor bases — rational primes on one side, prime ideals
of small norm on the other. As in QS this is done by sieving over the region rather than by
trial division. Line sieving walks one value of \( b \) at a time; lattice sieving (the
"special-\( q \)" method used by the GGNFS sievers and CADO-NFS) restricts attention to
the sublattice of pairs divisible by one chosen large prime, which raises the density of
useful relations enormously. Sieving is the dominant cost and is embarrassingly parallel.

### Filtering, linear algebra, square root

**Filtering** turns tens or hundreds of millions of raw relations into a matrix: it removes
duplicates and *singletons* (relations containing a prime that appears nowhere else, and
which therefore cannot participate in any dependency), then *merges* relations sharing a
prime to reduce the matrix dimension at the cost of increasing its density. This step
decides how big the linear algebra will be.

**Linear algebra** finds a kernel vector modulo 2, using block Lanczos or block Wiedemann.
Unlike sieving it is not embarrassingly parallel — it is a tightly coupled iteration over a
matrix that may not fit on one machine — and it is usually the second largest cost and the
hardest to distribute.

**Square root.** A dependency gives an element of \( \mathbb{Z}[\alpha] \) that is a
square, and you need its actual square root in the number field before mapping it down to
\( \mathbb{Z}/N\mathbb{Z} \). This is a genuinely nontrivial algebraic computation, not a
formality, and is handled by the Couveignes or Montgomery–Nguyen methods. Mapping both
square roots through \( \alpha \mapsto m \) yields \( x^{2} \equiv y^{2} \pmod N \) and
a gcd finishes the job — or fails, with probability about \( 1/2 \), in which case you
use the next dependency.

### Why SNFS is faster

If \( N \) already has an algebraic form — \( N = r^{e} \pm s \) for small \( r \)
and \( s \), or a value of a low-degree polynomial at a small argument — polynomial
selection can exploit that structure instead of deriving a general polynomial only from
the digits of \(N\). For \(N=2^{101}-1\), the identity \(x^{101}-1\) at \(x=2\)
exhibits the structure and its cyclotomic decomposition. Turning a recognized form into
a production SNFS job still belongs to the selected engine's polynomial-selection and
parameter pipeline; displaying a symbolic polynomial is not itself a completed NFS
configuration.

That is the whole difference, and it is decisive. In the base-\( m \) construction the
coefficients of \( f \) are of size \( N^{1/d} \); in the special construction they are
of size \( O(1) \). Smaller coefficients mean smaller norms mean far more smooth
relations, and the complexity drops from \( L_{N}[1/3, (64/9)^{1/3}] \) to
\( L_{N}[1/3, (32/9)^{1/3}] \) — the same \( \alpha \), a constant roughly 20 per cent
smaller, which at 200 digits is orders of magnitude of work. The cost of an SNFS job is
quoted not by the digit count of \( N \) but by its **SNFS difficulty**, essentially the
size of the number the polynomial makes it equivalent to.

**In Numerisect.** YAFU's `nfs` and `snfs` as the `yafu_nfs` and `yafu_snfs` backends, and
CADO-NFS as the `cado` backend and the second half of `hybrid` mode. Automatic routing
sends inputs at or above the configured decimal threshold to a YAFU pretest followed by the
nearest suitable installed CADO parameter set. `POST /api/factor-lab/tune` runs **YAFU's
own `tune`**, which measures where SIQS stops beating NFS on this machine; the result is a
suggestion printed as an environment variable, and Numerisect never rewrites its own
configuration. Tuning needs the GGNFS lattice sievers.

## Algebraic and Aurifeuillean factorizations

Before running any general algorithm on a number of special form, look for the factors that
algebra hands you for free. This is not an optimisation; it can turn an impossible job into
a trivial one.

### Cyclotomic factorization

For any \( n \),

\[
x^{n} - 1 = \prod_{d \mid n} \Phi_{d}(x),
\]

where \( \Phi_d \) is the \( d \)-th cyclotomic polynomial. Substituting an integer
\( b \) factors \( b^{n} - 1 \) completely into the values \( \Phi_{d}(b) \), each of
which is far smaller than \( b^{n}-1 \) and can be attacked separately. The
corresponding identity for \( b^{n}+1 \) follows from
\( b^{n} + 1 = (b^{2n}-1)/(b^{n}-1) \). For a Cunningham-type number this reduces the
problem from one \( n \)-digit input to several much smaller ones — and it is the reason
the Cunningham tables are organised by \( \Phi_d \) rather than by \( b^n \pm 1 \).

### Aurifeuillean factorization

Sometimes \( \Phi_{n}(b) \) itself splits over \( \mathbb{Z} \), even though
\( \Phi_{n}(x) \) is irreducible over \( \mathbb{Q}[x] \). The classical example is

\[
2^{4k+2} + 1 = \left( 2^{2k+1} - 2^{k+1} + 1 \right)\left( 2^{2k+1} + 2^{k+1} + 1 \right),
\]

which you can verify at once as \( (2^{2k+1}+1)^{2} - (2^{k+1})^{2} \). At \( k = 1 \)
it reads \( 65 = 5 \times 13 \); at \( k = 100 \) it splits a 61-digit number for free.
The general phenomenon — first observed by Aurifeuille — is that
\( \Phi_{n}(x) \) admits an identity of the form
\( \Phi_{n}(x) = C_{n}(x)^{2} - n\,x\,D_{n}(x)^{2} \) for suitable integer polynomials
\( C_n, D_n \), so that at arguments where \( nx \) is a perfect square the value
factors as a difference of two squares. The algorithmic treatment is Brent's.

!!! warning "A missed algebraic factor is wasted computing"
    Handing \( 2^{4k+2}+1 \) to a general sieve without noticing the Aurifeuillean split
    means factoring a number twice as long as necessary. Numerisect looks for the special
    form first — and it **verifies that every algebraic factor it reports actually divides
    the input** before showing it, because an unverified algebraic identity is exactly the
    kind of thing that is subtly wrong for one edge case.

**In Numerisect.** `POST /api/factor-lab/special-form` recognises perfect powers via PARI
`ispower`, values \( a^{k} \pm 1 \) with no base scan or base limit, and cyclotomic values
\( \Phi_{k}(a) \) for bases to 200 and \( k \) to 60, obtaining every algebraic factor
by factoring \( \Phi_{n}(b) \) with PARI `factor`. For \( 2^{101}-1 \) it returns the
SNFS polynomial \( x^{101}-1 \), difficulty 30, and the two algebraic factors
7432339208719 and 341117531003194129. A search that exceeds its time budget reports
`complete: false` and is **inconclusive**: it does not assert that no special form exists.
`POST /api/number-theory/cyclotomic` constructs \( \Phi_{n}(x) \) and factors it over a
selected finite field.

## Choosing an algorithm

Three inputs decide the strategy: the digit count of the remaining cofactor, how much ECM
has already been completed, and whether the number has algebraic structure.

1. **Is it prime?** Ask first. `isprime` is cheap compared with any factoring attempt, and
   there is no sense sieving a prime.
2. **Strip the small factors.** Trial division to \( 10^{6} \), then rho, then a short
   \( p-1 \).
3. **Is there algebraic structure?** If the number is \( b^{n} \pm 1 \), a cyclotomic
   value, a perfect power, or Aurifeuillean, split it first and recurse on the parts. A
   special form also means SNFS is available, which changes the size threshold entirely.
4. **Run ECM to a sensible depth.** How deep depends on what comes next: there is no point
   spending a week on t50 if SIQS would finish the whole number in an hour. The rule of
   thumb is to run ECM to roughly the level at which its expected cost equals a fraction —
   conventionally between a quarter and a third — of the expected sieve cost.
5. **Commit to a sieve.** Below the crossover, SIQS; above it, NFS.

Numerisect's adviser encodes this as explicit routing thresholds: below 20 digits SQUFOF or
SIQS, below 60 digits SIQS, below 95 digits an ECM pretest then SIQS, and CADO-NFS above
that. The crossover is machine-dependent — it moves with your core count and with how each
engine was built — which is why the tune route measures it locally rather than trusting a
published number.

!!! note "The expected remaining factor size is a planning estimate"
    With no ECM completed, the adviser estimates the next factor at one third of the
    cofactor's digits — the balanced-semiprime split. With ECM completed to \( t \)
    digits it estimates at least \( t \), because ECM to that depth makes a smaller
    factor unlikely. The response states which basis was used. **Neither number is a
    proven bound**, and neither becomes one by being displayed.

### Verification

Because factoring is the one operation where a wrong answer is easy to check, Numerisect
checks it. Every factor must divide the requested input, and the complete returned multiset
must multiply back to its absolute value; a nonzero exit, a malformed factor line, a
nondividing factor or an incomplete product fails explicitly and preserves the log.
Cross-check mode runs YAFU and Msieve independently and accepts the result only when their
sorted factor multisets are identical. Each part is then labelled prime or composite by
PARI's `isprime`, and a certificate can be built and independently re-verified for every
prime part. See [Independent verification](../VERIFICATION.md) and
[Primality](primality.md).

## Where this appears in Numerisect

| Topic | Tool | Engine routine |
|---|---|---|
| Bounded trial division | `pari_trial` backend; strategy pre-pass | PARI/GP `factor` with a bound; YAFU `trial` |
| Mersenne trial factoring | `POST /api/factor-lab/mersenne-factors` | PARI `ispseudoprime`, `Mod(2,q)^p`; target \(2^p-1\) is not materialized |
| Fermat's method | `yafu_fermat` backend | YAFU `fermat`, bound `-fmtmax` |
| Pollard rho (Brent) | `yafu_rho` backend | YAFU `rho`, bound `-rhomax` |
| Pollard rho step trace | `POST /api/factor-lab/trace` | PARI/GP `Mod`, `gcd` (teaching trace, capped at 500 steps) |
| Pollard \( p-1 \) | `yafu_pm1` backend | YAFU `pm1`, `-B1pm1`, `-B2pm1` |
| Williams \( p+1 \) | `yafu_pp1` backend | YAFU `pp1`, `-B1pp1`, `-B2pp1` |
| \( p-1 \) stage-one trace | `POST /api/factor-lab/trace` | PARI/GP `Mod`, `gcd`, `forprime` |
| ECM pretest | `yafu_ecm` backend | YAFU `ecm`, `-B1ecm`, `-B2ecm`, `-sigma` |
| ECM campaign, resumable | `ecm_campaign` job backend | GMP-ECM with `-B1`, `-B2`, `-c`, `-sigma`, `-param`, `-save`, `-resume` |
| ECM factor reconciliation | ECM campaign job | PARI/GP `fl_reconcile` |
| ECM stage-one trace | `POST /api/factor-lab/trace` | PARI/GP |
| SQUFOF | `POST /api/factor-lab/squfof`, `squfof` backend | `numerisect-squfof`, a C program in this project using GMP; \( N < 2^{62} \) |
| The forms behind SQUFOF | [Forms laboratory](../FORMS_LAB.md) | PARI `Qfb`, `qfbred`, `quadclassunit`, `qfbclassno` |
| SIQS | `yafu_siqs` backend | YAFU `siqs`, `-siqsB`, `-siqsTF`, `-siqsR`, `-siqsT`, `-siqsNB`, `-siqsM` |
| MPQS, second opinion | `msieve` and `cross_verify` backends | Msieve |
| GNFS | `yafu_nfs`, `cado`, `hybrid` backends | YAFU `nfs`; CADO-NFS with an installed parameter set |
| SNFS | `yafu_snfs` backend | YAFU `snfs` |
| GGNFS lattice-siever diagnostics | `GET /api/factor-lab/sievers` | Executable discovery, CPU compatibility probe and SHA-256 provenance for YAFU's external sievers |
| RSA Challenge identification and verification | `GET /api/factor-lab/rsa-catalogue`, `POST /api/factor-lab/rsa-challenge` | PARI exact multiplication, `ispseudoprime`/`isprime`, and a labelled heuristic NFS effort model |
| SIQS/NFS crossover measurement | `POST /api/factor-lab/tune` | YAFU's own `tune` (needs the GGNFS lattice sievers) |
| `factorint` strategy comparison | `POST /api/structure/factorint-strategies` | PARI `factorint(n, flag)`, timed by `gettime`, audited by `isprime` |
| Divisors in a residue class | `POST /api/structure/lenstra-divisors` | PARI `divisorslenstra` (requires \( \gcd(r,s)=1 \) and \( s^{3} > N \)) |
| Special forms, algebraic and Aurifeuillean factors | `POST /api/factor-lab/special-form` | PARI `ispower`, `polcyclo`, `factor` |
| Strategy adviser and decision tree | `POST /api/factor-lab/strategy` | PARI `isprime`, `factor`, `ispower` |
| Certificates for the prime parts | `POST /api/factor-lab/certificates`, `POST /api/jobs/{id}/certificates` | PARI `primecert`, `primecertisvalid`, `primecertexport` |

## References

- R. P. Brent, *An improved Monte Carlo factorization algorithm*, BIT **20** (1980),
  176–184.
- R. P. Brent, *On computing factors of cyclotomic polynomials*, Mathematics of Computation
  **61** (1993), 131–149.
- J. Brillhart, D. H. Lehmer, J. L. Selfridge, B. Tuckerman and S. S. Wagstaff Jr.,
  *Factorizations of \( b^{n} \pm 1 \), \( b = 2, 3, 5, 6, 7, 10, 11, 12 \) up to High
  Powers*, Contemporary Mathematics 22, American Mathematical Society. The Cunningham
  tables, and the standard reference for algebraic and Aurifeuillean factorizations.
- J. P. Buhler, H. W. Lenstra Jr. and C. Pomerance, *Factoring integers with the number
  field sieve*, in A. K. Lenstra and H. W. Lenstra Jr. (eds.), *The Development of the
  Number Field Sieve*, Lecture Notes in Mathematics 1554, Springer, 1993, 50–94.
- H. Cohen, *A Course in Computational Algebraic Number Theory*, Graduate Texts in
  Mathematics 138, Springer, 1993. Chapters 8 and 10.
- S. Contini, *Factoring Integers with the Self-Initializing Quadratic Sieve*, MA thesis,
  University of Georgia, 1997.
- R. Crandall and C. Pomerance, *Prime Numbers: A Computational Perspective*, 2nd edition,
  Springer, 2005. Chapters 5, 6 and 7.
- J. E. Gower and S. S. Wagstaff Jr., *Square form factorization*, Mathematics of
  Computation **77** (2008), 551–588.
- D. E. Knuth, *The Art of Computer Programming, Volume 2: Seminumerical Algorithms*, 3rd
  edition, Addison-Wesley, 1997, §4.5.4.
- R. S. Lehman, *Factoring large integers*, Mathematics of Computation **28** (1974),
  637–646.
- A. K. Lenstra, H. W. Lenstra Jr., M. S. Manasse and J. M. Pollard, *The number field
  sieve*, Proceedings of the 22nd ACM Symposium on Theory of Computing (1990), 564–572.
- H. W. Lenstra Jr., *Factoring integers with elliptic curves*, Annals of Mathematics
  **126** (1987), 649–673.
- P. L. Montgomery, *A block Lanczos algorithm for finding dependencies over
  \( \mathrm{GF}(2) \)*, Advances in Cryptology — EUROCRYPT '95, Lecture Notes in
  Computer Science 921, Springer, 106–120.
- J. M. Pollard, *Theorems on factorization and primality testing*, Proceedings of the
  Cambridge Philosophical Society **76** (1974), 521–528.
- J. M. Pollard, *A Monte Carlo method for factorization*, BIT **15** (1975), 331–334.
- C. Pomerance, *Analysis and comparison of some integer factoring algorithms*, in H. W.
  Lenstra Jr. and R. Tijdeman (eds.), *Computational Methods in Number Theory, Part I*,
  Mathematical Centre Tracts 154, Amsterdam, 1982, 89–139.
- C. Pomerance, *The quadratic sieve factoring algorithm*, Advances in Cryptology —
  EUROCRYPT '84, Lecture Notes in Computer Science 209, Springer, 1985, 169–182.
- H. Riesel, *Prime Numbers and Computer Methods for Factorization*, 2nd edition,
  Birkhäuser, 1994. Chapters 5 and 6, and the account of SQUFOF.
- R. D. Silverman, *The multiple polynomial quadratic sieve*, Mathematics of Computation
  **48** (1987), 329–339.
- D. H. Wiedemann, *Solving sparse linear equations over finite fields*, IEEE Transactions
  on Information Theory **32** (1986), 54–62.
- H. C. Williams, *A \( p+1 \) method of factoring*, Mathematics of Computation **39**
  (1982), 225–234.

Shanks never published a complete description of SQUFOF; the algorithm is documented in
Riesel and analysed in full by Gower and Wagstaff. The ECM expected-curve figures in this
page were produced by the installed GMP-ECM's own `-v` estimate and can be reproduced with
the command shown beside the table.
