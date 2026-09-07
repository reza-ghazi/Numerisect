# The distribution of primes

This page covers what is known, what is conjectured, and what is merely observed
about how the primes are spread through the integers: the prime counting function
and the three classical approximations to it, the combinatorial algorithms that
evaluate \(\pi(x)\) without listing the primes, the sign of \(\pi(x) - \mathrm{li}(x)\),
explicit bounds on the \(n\)th prime, the statistics of prime gaps, primes in
arithmetic progressions, and the Hardy–Littlewood and Bateman–Horn conjectures for
prime patterns. Numerisect's [analytic prime-distribution laboratory](../DISTRIBUTION_LAB.md)
and [prime-counting comparison](../COUNTING_LAB.md) implement most of what follows;
each section ends by naming the tool and the engine routine, and the summary table
at the foot of the page collects them.

Throughout, results are labelled. A **theorem** is proved. A **conjecture** is not,
however much numerical evidence exists for it. An **observation** is a finite
computation, and a finite computation about an asymptotic statement proves nothing
about the asymptotic statement. Numerisect enforces the same three-way distinction
in its result panels and saved reports, and this page does not soften it.

## The prime counting function

\(\pi(x)\) is the number of primes not exceeding \(x\). It is a step function,
increasing by 1 at each prime, and it is the object every result on this page is
about.

Two weighted variants are analytically better behaved, because they weight a prime
by its logarithm and so grow linearly:

\[
\theta(x) = \sum_{p \le x} \log p,
\qquad
\psi(x) = \sum_{p^k \le x} \log p = \sum_{n \le x} \Lambda(n).
\]

\(\Lambda\) is the von Mangoldt function, equal to \(\log p\) when \(n\) is a power
of a prime \(p\) and 0 otherwise. Chebyshev introduced \(\theta\) and \(\psi\) in the
1850s and proved that \(\pi(x)\log x / x\) is bounded between two explicit positive
constants — the first substantial theorem about the density of the primes, and half
a century short of the prime number theorem itself.

!!! note "Why \(\psi\) rather than \(\pi\)"
    \(\psi(x) \sim x\) is equivalent to \(\pi(x) \sim x/\log x\), and \(\psi\) is the
    function that appears directly in the explicit formula of
    [the zeta page](zeta.md). Numerisect computes \(\theta(x)\) and \(\psi(x)\)
    exactly on the summatory-functions page and reconstructs \(\psi(x)\) from zeta
    zeros in the zeta lab.

### The prime number theorem

**Theorem (Hadamard; de la Vallée Poussin, 1896).**

\[
\pi(x) \sim \frac{x}{\log x},
\qquad\text{equivalently}\qquad
\psi(x) \sim x .
\]

Both proofs rested on showing that \(\zeta(s)\) has no zeros on the line
\(\mathrm{Re}\,s = 1\). That is not a coincidence of technique: the size of the error
term in the prime number theorem is exactly a statement about how far to the left of
that line the zeros are kept, which is the subject of [the zeta page](zeta.md).

### Three approximations, and how good each is

\(x/\log x\) is the statement of the theorem, not a good approximation. Its relative
error is of order \(1/\log x\), which decays so slowly that at \(x = 10^{10}\) it is
still about 4.6 %.

The logarithmic integral is much better:

\[
\mathrm{li}(x) = \int_0^x \frac{dt}{\log t}
\]

taken as a Cauchy principal value at \(t = 1\). Integrating by parts gives the
asymptotic expansion \(x/\log x + x/\log^2 x + 2x/\log^3 x + \cdots\), of which
\(x/\log x\) is only the first term — that is the whole reason \(\mathrm{li}\) wins.
Numerisect never approximates it in Python; it is PARI's exponential integral,
\(\mathrm{li}(x) = \mathrm{Re}\,(-\texttt{eint1}(-\log x))\).

Riemann's approximation refines \(\mathrm{li}\) by Möbius inversion:

\[
R(x) = \sum_{n \ge 1} \frac{\mu(n)}{n}\,\mathrm{li}\!\left(x^{1/n}\right)
= 1 + \sum_{k \ge 1} \frac{(\log x)^k}{k \, k! \, \zeta(k+1)} .
\]

The second form is Gram's series. \(R(x)\) removes the systematic contribution of
prime squares, cubes and higher powers, which is why it sits so much closer to
\(\pi(x)\) than \(\mathrm{li}(x)\) does over any range a computer can reach.

| \(x\) | \(\pi(x)\) | \(x/\log x\) | \(\mathrm{li}(x)\) | \(R(x)\) |
|---|---|---|---|---|
| \(10^6\) | 78 498 | 72 382.4 | 78 627.5 | 78 527.4 |
| \(10^7\) | 664 579 | 620 420.7 | 664 918.4 | 664 667.5 |
| \(10^8\) | 5 761 455 | 5 428 681.0 | 5 762 209.4 | 5 761 551.9 |
| \(10^9\) | 50 847 534 | 48 254 942.4 | 50 849 235.0 | 50 847 455.4 |
| \(10^{10}\) | 455 052 511 | 434 294 481.9 | 455 055 614.6 | 455 050 683.3 |

The \(\pi(x)\) column is exact, from `primecount`; the other three are PARI
evaluations. Notice that \(\mathrm{li}(x)\) overshoots at every row and \(R(x)\) does
not consistently do either. Neither pattern is a theorem, and the next section says
why.

!!! warning "A grid is not a proof"
    Numerisect's approximation-error page samples a log-spaced grid of at most 24
    points. An absence of sign changes across that grid is never evidence that
    \(\pi(x) - \mathrm{li}(x)\) keeps its sign, and the result note attached to the
    report says exactly that.

**In Numerisect.** *Approximation error* (`POST /api/distribution/approximation-error`)
and *PNT convergence* (`POST /api/distribution/pnt-convergence`) tabulate all four
columns together with the signed and relative errors, the ratios
\(\pi(x)/(x/\log x)\) and \(\pi(x)/\mathrm{li}(x)\), and the normalised error
\((\pi(x) - \mathrm{li}(x))\log x/\sqrt{x}\). \(\pi(x)\) comes from `primecount x`,
\(R(x)\) from `primecount --RiemannR` (rounded to an integer, so that column is exact
to within one unit), and everything else from PARI's `eint1`, `log` and `sqrt`.
The smaller *Prime-counting approximations* page
(`POST /api/number-theory/prime-approximations`, `nt_prime_approximations`) gives the
same comparison for one \(x\).

## Computing \(\pi(x)\)

### Sieving

The direct method is to enumerate the primes and count them. A segmented sieve of
Eratosthenes with wheel factorisation costs \(O(x \log \log x)\) operations and
\(O(\sqrt{x})\) memory, and is what `primesieve` does; PARI's `primepi` also sieves.
This is unbeatable when the primes themselves are wanted, and hopeless as a way to
reach \(\pi(10^{20})\), because the work is proportional to \(x\).

### Legendre's \(\varphi(x, a)\), the shared building block

Every combinatorial method is built on the partial sieve function

\[
\varphi(x, a) = \#\{\, n \le x : p \mid n \implies p > p_a \,\},
\]

the count of integers in \([1, x]\) divisible by none of the first \(a\) primes. It
satisfies the recurrence \(\varphi(x, a) = \varphi(x, a-1) - \varphi(x/p_a, a-1)\)
with \(\varphi(x, 0) = \lfloor x \rfloor\), which is inclusion–exclusion over the
squarefree products of the first \(a\) primes.

Legendre's identity follows immediately. If \(a = \pi(\sqrt{x})\) then every integer
surviving the sieve above 1 is prime, so

\[
\pi(x) = \varphi(x, a) + a - 1 .
\]

More generally the identity holds whenever \(x < p_{a+1}^2\), because a composite
surviving the sieve would need two prime factors greater than \(p_a\). Outside that
window the identity is simply inapplicable, and Numerisect reports it as such rather
than approximating it.

**In Numerisect.** The *Legendre partial sieve* page (`POST /api/counting/phi`)
evaluates \(\varphi(x, a)\) with `primecount --phi <x> <a>` and, from PARI, gives
\(p_a\), \(p_{a+1}\), the Legendre product \(x \prod_{p \le p_a}(1 - 1/p)\) that
\(\varphi\) approximates, and — only inside the window \(x < p_{a+1}^2\) — the
identity checked against PARI `primepi`. Worked example from
[the counting lab](../COUNTING_LAB.md): \(\varphi(900, 10) = 145\), \(p_{10} = 29\),
\(p_{11} = 31\), and \(900 < 961\), so \(\pi(900) = 145 + 10 - 1 = 154\).

### The historical line

Each method in the sequence rewrites more of the sieve as closed-form terms and
leaves less to the recursion.

| Method | Idea | Published cost |
|---|---|---|
| **Legendre** | \(\pi(x) = \varphi(x, \pi(\sqrt{x})) + \pi(\sqrt{x}) - 1\), evaluated by the recurrence | essentially linear in \(x\) |
| **Meissel** | truncate the sieve at \(a = \pi(x^{1/3})\) and add a correction term counting the surviving semiprimes | \(O(x/\log^3 x)\) |
| **Lehmer** | truncate at \(a = \pi(x^{1/4})\) and carry one further correction term for products of three primes | \(O(x/\log^4 x)\) |
| **Lagarias–Miller–Odlyzko** | split the \(\varphi\) recursion by the size of the leading divisor and evaluate the "easy" part analytically; the first genuinely sub-\(x\) method | \(O(x^{2/3+\varepsilon})\) time, \(O(x^{1/3+\varepsilon})\) space |
| **Deléglise–Rivat** | refine the LMO split with a tuning parameter \(\alpha\) and a better ordinary-leaves treatment | \(O(x^{2/3}/\log^2 x)\) time |
| **Gourdon** | a further reorganisation of the same split, and `primecount`'s default | as Deléglise–Rivat, with better constants |

Lehmer's method took \(\pi(10^{10})\) into reach by hand-scale computation in 1959;
LMO (Lagarias, Miller and Odlyzko, *Math. Comp.* 44, 1985) was the structural break,
and Deléglise–Rivat (*Math. Comp.* 65, 1996) and Gourdon's subsequent refinement are
what make \(\pi(10^{27})\) a routine computation today. The complexities above are
the published statements; treat them as such and not as measurements.

!!! example "Agreement as a correctness check"
    These are six different pieces of mathematics with six different code paths, and
    PARI's `primepi` is a seventh implementation sharing no code with any of them. A
    single algorithm cannot check itself; several agreeing on one \(x\) is an
    independent check of the installed binaries and of this machine. That is exactly
    what Numerisect's *Algorithm cross-check* page
    (`POST /api/counting/algorithm-comparison`) is for. It never resolves a
    disagreement — it prints every distinct value with the number of sources
    reporting it and calls the majority a *consensus*, not an answer.

**In Numerisect.** `primecount x --legendre`, `--meissel`, `--lehmer`, `--lmo`,
`--deleglise-rivat`, `--gourdon`, plus `--double-check` and PARI `primepi`. The
timings shown are single measurements on the machine that served the request and are
not benchmarks of the algorithms. Bounds: \(x \le 10^{31}\) generally,
\(x \le 10^{16}\) when Legendre, Meissel or Lehmer is selected, \(x \le 10^{11}\) for
PARI `primepi`.

## The sign of \(\pi(x) - \mathrm{li}(x)\)

Every \(x\) at which \(\pi(x)\) has ever been evaluated satisfies
\(\pi(x) < \mathrm{li}(x)\). It is tempting to read the table above as evidence that
\(\mathrm{li}\) always overshoots. It is not.

**Theorem (Littlewood, 1914).** \(\pi(x) - \mathrm{li}(x)\) changes sign infinitely
often. More precisely, \((\pi(x) - \mathrm{li}(x))\dfrac{\log x}{\sqrt{x}}\) has
positive limit superior and negative limit inferior; the oscillation is of order
\(\log\log\log x\).

Littlewood's proof is non-effective: it shows crossings exist without locating one.
Skewes then worked on bounding the first. His 1933 argument, **assuming the Riemann
hypothesis**, gave an upper bound of \(e^{e^{e^{79}}}\); his 1955 argument, assuming
nothing, gave a tower one level higher. Those bounds have since come down enormously
— Bays and Hudson located a region near \(1.398 \times 10^{316}\) where a crossing is
expected, and later work has narrowed the analysis further — but no crossing point
has ever been exhibited, and none is within computational reach.

!!! warning "What a finite computation can and cannot say"
    Observing \(\pi(x) < \mathrm{li}(x)\) at every point of a grid up to \(10^{19}\)
    tells you about that grid. It is not evidence about the general case, because the
    theorem that settles the general case says the opposite happens infinitely often,
    starting somewhere far beyond any grid. Numerisect reports the observed sign and
    every sign change *visible on the submitted grid*, and states in the note that
    absence of a change is not evidence.

The normalisation \((\pi(x) - \mathrm{li}(x))\log x/\sqrt{x}\) reported by the
PNT-convergence page is Littlewood's: it is the scale at which the oscillation is
\(O(\log\log\log x)\) rather than vanishing, and the same \(\sqrt{x}\) scaling
reappears in the prime races below.

## Explicit bounds on the \(n\)th prime

Asymptotically \(p_n \sim n \log n\), and the refinement
\(p_n = n(\log n + \log\log n - 1 + o(1))\) follows from the prime number theorem.
For computation, what is wanted is not an asymptotic but an inequality valid from a
stated point onwards. Six such bounds are implemented, each with the range in which
it is proved:

| Bound on \(p_n\) | Side | Valid for | Source |
|---|---|---|---|
| \(n \log n\) | lower | \(n \ge 1\) | Rosser (1939) |
| \(n(\log n + \log\log n - 3/2)\) | lower | \(n \ge 2\) | Rosser and Schoenfeld, *Approximate formulas for some functions of prime numbers*, Illinois J. Math. 6 (1962), (3.12) |
| \(n(\log n + \log\log n - 1/2)\) | upper | \(n \ge 20\) | Rosser and Schoenfeld (1962), (3.13) |
| \(n(\log n + \log\log n - 1)\) | lower | \(n \ge 2\) | Dusart, *The \(k\)-th prime is greater than \(k(\ln k + \ln\ln k - 1)\) for \(k \ge 2\)*, Math. Comp. 68 (1999), Theorem 3 |
| \(n\!\left(\log n + \log\log n - 1 + \frac{\log\log n - 2.1}{\log n}\right)\) | lower | \(n \ge 3\) | Dusart, *Estimates of some functions over primes without R.H.* (2010), Prop. 5.15 |
| \(n\!\left(\log n + \log\log n - 1 + \frac{\log\log n - 2}{\log n}\right)\) | upper | \(n \ge 688383\) | Dusart (2010), Prop. 5.15 |

These are theorems, not heuristics. Inside its stated range each inequality is
rigorous; outside it the inequality may simply be false, which is why a bound
evaluated outside its range must be reported as *outside the published validity
range* and not counted as a failure.

**In Numerisect.** *\(n\)-th prime bounds* (`POST /api/distribution/nth-prime-bounds`)
evaluates all six at 60-digit precision in PARI and compares them with the exact
\(p_n\) from `primecount --nth-prime`; a violation is reported only when it occurs
inside a stated range. The related *Inverse approximations* page
(`POST /api/counting/nth-prime-inverses`) compares the exact \(p_n\) with
`--Li-inverse` and `--RiemannR-inverse`; for \(n = 10^6\) the exact value is
15 485 863, \(\mathrm{li}^{-1}\) gives 15 479 083 and \(R^{-1}\) gives 15 484 039.

## Prime gaps

Write \(g_n = p_{n+1} - p_n\). The prime number theorem gives an average gap of
\(\log p_n\) near \(p_n\), which motivates the **merit**

\[
M_n = \frac{g_n}{\log p_n},
\]

the gap measured in units of the local average. A merit of 1 is unremarkable; merits
above 30 are records.

### Two heuristics, both conjectural

**Cramér's conjecture (1936).** From a probabilistic model in which \(n\) is "prime"
with probability \(1/\log n\), Cramér was led to

\[
\limsup_{n \to \infty} \frac{g_n}{\log^2 p_n} = 1 .
\]

**Granville's correction (1995).** The Cramér model ignores divisibility by small
primes, which biases the spacing. Granville argued that the correct constant is at
least \(2e^{-\gamma} = 1.1229\ldots\), so that gaps somewhat larger than
\(\log^2 p_n\) should be expected infinitely often.

**Firoozbakht's conjecture.** \(p_n^{1/n}\) is strictly decreasing. Kourbatov
(*Verification of the Firoozbakht conjecture for primes up to four quintillion*,
2015) verified it to \(4 \times 10^{18}\) and showed it implies
\(g_n < \log^2 p_n - \log p_n - 1\) for every \(p_n > 29\).

!!! warning
    All three are conjectures. Numerisect reports the corresponding ratios as
    observations; a record gap satisfying the Firoozbakht-implied bound is a
    datum, not a confirmation, and below \(p = 29\) the verdict is reported as
    outside the stated range rather than as a pass.

What *is* proved about gaps is by contrast rather sparse: infinitely many gaps
exceed \(c \log p_n \log\log p_n \log\log\log\log p_n / (\log\log\log p_n)^2\)
(Rankin, subsequently improved by Ford–Green–Konyagin–Tao and independently by
Maynard), and in the other direction \(\liminf g_n \le 246\) unconditionally
(Zhang, *Bounded gaps between primes*, Ann. of Math. 179 (2014); Maynard, *Small
gaps between primes*, Ann. of Math. 181 (2015); Polymath). The twin prime
conjecture \(\liminf g_n = 2\) remains open.

### Maximal gaps

A gap is **maximal** (a first occurrence) when it exceeds every earlier gap. The
sequence of maximal gaps is OEIS **A005250**, indexed by the prime that begins each
one, **A002386**. Numerisect embeds every published maximal gap through
\(4.3 \times 10^9\) — 35 entries — and compares a scan against them.

The comparison is only meaningful when the scan starts at 2 with baseline 0: a
record inside a window that starts higher is a record *of that window*, not a
maximal gap, and Numerisect refuses to conflate the two.

Worked example: the gap of 34 after \(p = 1327\) has merit \(4.7283454\ldots\),
Cramér–Shanks ratio \(g/\log^2 p = 0.6575661\ldots\), Granville ratio
\(g/(2e^{-\gamma}\log^2 p) = 0.5855864\ldots\), and satisfies the
Firoozbakht-implied bound.

**In Numerisect.** *Record prime gaps* (`POST /api/distribution/maximal-gaps`) scans
with PARI `forprime` under two independent bounds — the range \((\text{end} \le 10^{13})\)
and a cap on primes visited. Hitting the cap sets `TRUNCATED`, reports the prime to
resume from, and marks the result incomplete; it never becomes a claim that no larger
gap exists. Distributional statistics for a range — minimum, maximum, mean, median
and the full frequency table of gap values — come from *gap statistics*
(`POST /api/primes/gap-statistics`, `ps_gap_statistics`).

### Gaps in short intervals

Maier's theorem shows that the naive expectation \(\pi(x + (\log x)^\lambda) - \pi(x)
\sim (\log x)^{\lambda - 1}\) is **false** for every fixed \(\lambda > 1\): short
intervals in residue classes coprime to a primorial modulus are systematically richer
or poorer than the average. Numerisect's *Maier matrix* page
(`POST /api/distribution/short-interval`) builds the matrix whose row \(k\) is
\([qk+1,\, qk+y]\), counts primes per row with `forprime`, and reports the per-row
ratio against \(y/\log(qk)\) together with the mean, maximum and minimum. The spread
is observed, not predicted.

## Primes in arithmetic progressions

**Theorem (Dirichlet, 1837).** If \(\gcd(a, q) = 1\) there are infinitely many primes
\(p \equiv a \pmod q\).

**Theorem (prime number theorem for progressions).** For fixed \(\gcd(a,q) = 1\),

\[
\pi(x; q, a) \sim \frac{\mathrm{li}(x)}{\varphi(q)} .
\]

The \(\varphi(q)\) reduced classes therefore share the primes equally in the limit.
Uniformity in \(q\) is the delicate part: Siegel–Walfisz gives it for
\(q \le (\log x)^A\) with an ineffective constant, and Bombieri–Vinogradov gives it
on average over \(q\) up to nearly \(\sqrt{x}\) — which is what makes
Bombieri–Vinogradov a workable substitute for GRH in many arguments.

### Chebyshev's bias and prime races

Chebyshev observed in 1853 that \(\pi(x; 4, 3)\) exceeds \(\pi(x; 4, 1)\) far more
often than not. The explanation is that squares are all \(\equiv 1 \pmod 4\), so the
class of quadratic residues is "used up" by prime squares in \(\psi\) and the count
of primes in it runs slightly behind.

Littlewood proved the lead changes infinitely often, so neither class wins. The
sharper statement is:

**Theorem (Rubinstein and Sarnak, *Chebyshev's bias*, Experimental Math. 3 (1994)).**
Assume the generalised Riemann hypothesis **and** the linear independence over
\(\mathbb{Q}\) of the positive ordinates of the zeros of the relevant Dirichlet
\(L\)-functions. Then the set \(\{x : \pi(x;4,3) > \pi(x;4,1)\}\) has a logarithmic
density, and it equals \(0.9959\ldots\).

Read that carefully. It is conditional on two hypotheses, one of which (linear
independence) is not even widely expected to be provable soon. It is about
*logarithmic* density, a weighting that makes the limit exist where the natural
density is not known to. And it does not say the bias persists — it says the
proportion of the logarithmic scale on which class 3 leads is 99.59 %.

**In Numerisect.** *Prime race* (`POST /api/distribution/prime-race`) counts primes
by reduced class in a single PARI `forprime` pass, reports the leader at
geometrically spaced checkpoints, and reports the number of lead changes visible at
those checkpoints — explicitly a **lower bound**, since the lead can change between
samples. The normalised bias reported is
\((\pi(x;q,a) - \mathrm{li}(x)/\varphi(q))\log x/\sqrt{x}\), the Rubinstein–Sarnak
scaling. *Progression deviation* (`POST /api/distribution/progressions`) tabulates
\(\pi(x;q,a)\) for every reduced class against the expected
\(\mathrm{li}(x)/\varphi(q)\), with absolute, relative and \(\sqrt{x}\)-normalised
deviations. Caps: \(q \le 5040\), \(x \le 10^{10}\), 64 classes for a race and 128
for a progression table; a modulus with more classes is refused, never silently
truncated. The animated race in [the visual lab](../VISUAL_LAB.md)
(`POST /api/visual/prime-race`) draws the same counts.

The *density surface* page (`POST /api/distribution/density-surface`) shows the same
equidistribution two-dimensionally: primes are binned by position and by reduced
class modulo \(q\), and each cell reports
\(\text{count} \cdot \varphi(q) \cdot \log(\text{block start}) / \text{block width}\),
which tends to 1 under the prime number theorem for progressions.

## Prime constellations

### Admissibility and the singular series

A pattern is a set of offsets \(H = \{0 = h_1 < h_2 < \cdots < h_k\}\). Ask how often
\(n + h_1, \ldots, n + h_k\) are simultaneously prime.

For each prime \(p\) let \(w(p) = \#\{h_i \bmod p\}\) be the number of residue classes
modulo \(p\) that the pattern occupies. If \(w(p) = p\) for some \(p\) — the pattern
covers every class mod \(p\) — then one of the \(k\) values is divisible by \(p\) for
every \(n\), and only finitely many translates can be all prime. Such a pattern is
**inadmissible**. The pattern \(\{0, 2, 4\}\) is inadmissible because it covers all
three classes mod 3, which is why \((3,5,7)\) is the only prime triple of that shape.

For an admissible pattern, the **singular series** is

\[
\mathfrak{S}(H) = \prod_{p} \frac{1 - w(p)/p}{(1 - 1/p)^{k}} .
\]

Each factor compares the true density of surviving residues mod \(p\) with what
independence would predict, and the product is the accumulated correction.

**Conjecture (Hardy and Littlewood, *Some problems of 'Partitio Numerorum' III*,
Acta Math. 44, 1923).** For admissible \(H\),

\[
\#\{ n \le x : n + h_1, \ldots, n + h_k \text{ all prime}\} \sim
\mathfrak{S}(H) \int_2^x \frac{dt}{(\log t)^k} .
\]

For \(H = \{0, 2\}\) this is the twin prime conjecture with
\(\mathfrak{S} = 2C_2 = 1.3203236\ldots\), twice the twin prime constant.

!!! note "The truncation bound is rigorous even though the conjecture is not"
    The product over \(p\) must be truncated at some cutoff \(P\). Above the pattern
    diameter the offsets occupy \(k\) distinct classes, so the local factor is
    \((1 - k/p)/(1 - 1/p)^k\), whose logarithm is bounded in absolute value by
    \((k/p)^2\) when \(k/p \le 1/2\); summing over \(p > P\) with
    \(\sum_{n > P} n^{-2} < 1/P\) gives \(|\log(\text{tail})| < k^2/P\). The printed
    value is therefore correct to relative error \(e^{k^2/P} - 1\), and Numerisect
    reports that bound and the enclosing interval. With \(H = \{0,2\}\) and
    \(P = 10^6\) it returns \(\mathfrak{S} = 1.3203237\ldots\), inside the stated
    bound of \(4 \times 10^{-6}\) of \(2C_2\). **The bound on the truncation is
    rigorous; the conjecture the constant appears in is not.**

### Bateman–Horn: the polynomial generalisation

**Conjecture (Bateman and Horn, *A heuristic asymptotic formula concerning the
distribution of prime numbers*, Math. Comp. 16, 1962).** Let \(f_1, \ldots, f_k\) be
distinct irreducible polynomials over \(\mathbb{Z}\) with positive leading
coefficients, and suppose no prime divides \(\prod f_i(n)\) for all \(n\). Then

\[
\#\{ n \le x : \text{all } f_i(n) \text{ prime}\} \sim
\frac{C}{\prod_i \deg f_i} \int_2^x \frac{dt}{(\log t)^k},
\qquad
C = \prod_p \frac{1 - \omega(p)/p}{(1 - 1/p)^{k}},
\]

with \(\omega(p) = \#\{n \bmod p : \prod_i f_i(n) \equiv 0\}\). Taking all \(f_i\)
linear recovers the Hardy–Littlewood \(k\)-tuple conjecture; taking \(k = 1\) and
\(f(n) = n^2 + 1\) gives the conjectural density of primes of that shape, with
\(C = 1.372\ldots\).

!!! warning "No rigorous truncation bound here"
    Unlike the \(k\)-tuple case, the local factors do not settle to
    \(\omega(p) = k\) for large \(p\); they average to 1 only through
    equidistribution of the roots, so the truncation error is conditional and
    Numerisect claims no bound on it. The Bateman–Horn constant is reported as an
    **estimate**, full stop.

**In Numerisect.** *Singular series* (`POST /api/distribution/singular-series`)
computes \(\mathfrak{S}(H)\), decides admissibility from the same product, and
reports the rigorous \(k^2/P\) tail bound. *Constellation counts*
(`POST /api/distribution/tuple-prediction`) puts the prediction beside an **exact**
count: `primesieve --count=k` for the single-pattern constellations it supports
(twins, quadruplets, sextuplets) below \(2^{64}\), otherwise a PARI sliding window
over `forprime`. *Bateman–Horn* (`POST /api/distribution/bateman-horn`) proves each
polynomial irreducible with `polisirreducible` — a reducible input is refused, not
silently accepted — counts \(\omega(p)\) with `polrootsmod`, and tests every value
with `isprime` over a range of at most \(10^6\) integers. Enumeration of actual
constellations in a range is `POST /api/primes/tuples`, which uses primesieve's
\(k\)-tuplet output where the pattern is unambiguous and PARI otherwise.

## Where this appears in Numerisect

| Topic | Tool (route) | Engine routine |
|---|---|---|
| \(x/\log x\), \(\mathrm{li}\), \(R\) against exact \(\pi(x)\) | Approximation error (`/api/distribution/approximation-error`) | `primecount x`, `primecount --RiemannR`, PARI `eint1` |
| Ratios, normalised error, sign tracking | PNT convergence (`/api/distribution/pnt-convergence`) | `primecount x`; PARI `eint1`, `log`, `sqrt` |
| One-shot approximation comparison | Prime-counting approximations (`/api/number-theory/prime-approximations`) | `nt_prime_approximations`, `primecount`, PARI |
| Six \(\pi(x)\) algorithms compared | Algorithm cross-check (`/api/counting/algorithm-comparison`) | `primecount --legendre/--meissel/--lehmer/--lmo/--deleglise-rivat/--gourdon/--double-check`, PARI `primepi` |
| Legendre's \(\varphi(x, a)\) | Legendre partial sieve (`/api/counting/phi`) | `primecount --phi`, PARI `prime`, `forprime`, `primepi` |
| \(p_n\) and its inverse approximations | Inverse approximations (`/api/counting/nth-prime-inverses`) | `primecount --nth-prime`, `--Li-inverse`, `--RiemannR-inverse` |
| Rosser, Rosser–Schoenfeld, Dusart bounds | \(n\)-th prime bounds (`/api/distribution/nth-prime-bounds`) | `primecount --nth-prime`; PARI at 60 digits |
| Merit, Cramér, Granville, Firoozbakht, A002386/A005250 | Record prime gaps (`/api/distribution/maximal-gaps`) | PARI `forprime`, `log`, `exp`, `Euler` |
| Gap minimum, maximum, mean, median, frequencies | Gap statistics (`/api/primes/gap-statistics`) | `ps_gap_statistics` (PARI `forprime`, `vecsort`) |
| \(\pi(x; q, a)\), Chebyshev bias, lead changes | Prime race (`/api/distribution/prime-race`), Progression deviation (`/api/distribution/progressions`) | PARI `forprime`, `gcd`, `eint1` |
| Race animation | Visual prime race (`/api/visual/prime-race`) | `visual_lab.gp` |
| Maier's short intervals | Maier matrix (`/api/distribution/short-interval`) | PARI `forprime`, `log` |
| Equidistribution heat map | Density surface (`/api/distribution/density-surface`) | PARI `forprime`, `gcd`, `log` |
| Admissibility and \(\mathfrak{S}(H)\) | Singular series (`/api/distribution/singular-series`) | PARI `forprime`, `Set` |
| Predicted versus exact constellation counts | Constellation counts (`/api/distribution/tuple-prediction`) | `primesieve --count=k`; PARI `forprime`, `intnum` |
| Bateman–Horn constant and count | Bateman–Horn (`/api/distribution/bateman-horn`) | PARI `polisirreducible`, `polrootsmod`, `intnum`, `isprime` |
| \(\theta(x)\), \(\psi(x)\), \(M(x)\), summatory \(\lambda\) | Summatory functions (`/api/number-theory/summatory-functions`) | `nt_summatory_functions` (PARI `moebius`, `bigomega`, `forprime`, `log`) |
| \(\psi(x)\) and \(\pi(x)\) rebuilt from zeta zeros | Zeta lab (`/api/zeta/chebyshev-psi`, `/api/zeta/explicit-prime-count`) | `acb_dirichlet_hardy_z_zeros`, `arb_hypgeom_li`, `acb_hypgeom_ei` |

## References

- P. T. Bateman and R. A. Horn, "A heuristic asymptotic formula concerning the
  distribution of prime numbers", *Math. Comp.* **16** (1962).
- C. Bays and R. H. Hudson, "A new bound for the smallest \(x\) with
  \(\pi(x) > \mathrm{li}(x)\)", *Math. Comp.* **69** (2000).
- H. Cramér, "On the order of magnitude of the difference between consecutive prime
  numbers", *Acta Arith.* **2** (1936).
- M. Deléglise and J. Rivat, "Computing \(\pi(x)\): the Meissel, Lehmer, Lagarias,
  Miller, Odlyzko method", *Math. Comp.* **65** (1996).
- P. Dusart, "The \(k\)-th prime is greater than \(k(\ln k + \ln\ln k - 1)\) for
  \(k \ge 2\)", *Math. Comp.* **68** (1999); and *Estimates of some functions over
  primes without R.H.* (2010).
- A. Granville, "Harald Cramér and the distribution of prime numbers",
  *Scand. Actuar. J.* (1995).
- G. H. Hardy and J. E. Littlewood, "Some problems of 'Partitio Numerorum' III: On
  the expression of a number as a sum of primes", *Acta Math.* **44** (1923).
- G. H. Hardy and E. M. Wright, *An Introduction to the Theory of Numbers*, 6th ed.,
  Oxford — Chapters 1, 2 and 22.
- H. Iwaniec and E. Kowalski, *Analytic Number Theory*, AMS Colloquium Publications 53
  — Chapters 5, 17 and 22.
- A. Kourbatov, "Verification of the Firoozbakht conjecture for primes up to four
  quintillion" (2015).
- J. C. Lagarias, V. S. Miller and A. M. Odlyzko, "Computing \(\pi(x)\): the
  Meissel–Lehmer method", *Math. Comp.* **44** (1985).
- H. Maier, "Primes in short intervals", *Michigan Math. J.* **32** (1985).
- J. Maynard, "Small gaps between primes", *Ann. of Math.* **181** (2015).
- H. L. Montgomery and R. C. Vaughan, *Multiplicative Number Theory I: Classical
  Theory*, Cambridge — Chapters 6, 7 and 11.
- J. B. Rosser, "The \(n\)-th prime is greater than \(n \log n\)",
  *Proc. London Math. Soc.* (1939); J. B. Rosser and L. Schoenfeld, "Approximate
  formulas for some functions of prime numbers", *Illinois J. Math.* **6** (1962).
- M. Rubinstein and P. Sarnak, "Chebyshev's bias", *Experimental Math.* **3** (1994).
- Y. Zhang, "Bounded gaps between primes", *Ann. of Math.* **179** (2014).
- OEIS **A002386** and **A005250** (maximal prime gaps, after Nicely's
  first-occurrence tables).
- Numerisect: [analytic prime-distribution laboratory](../DISTRIBUTION_LAB.md),
  [prime-counting comparison](../COUNTING_LAB.md),
  [arithmetic and distribution tools](../ARITHMETIC_AND_DISTRIBUTION.md).
