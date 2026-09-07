# Proven, probable, inconclusive

Numerisect distinguishes the strength of every claim it makes. This page explains the
four labels, why the distinction is enforced rather than left to the reader, and what
each one costs to obtain.

If you read only one page of this documentation, read this one. A result you misread is
worse than no result.

---

## The four labels

<span class="strength proven">proven</span>
**A mathematical proof exists.** PARI's `isprime` returns this. So does a primality
certificate that `primecertisvalid` has re-checked. There is no probability attached: if
Numerisect says an integer is a proven prime, it is prime.

<span class="strength probable">probable</span>
**A strong probabilistic test passed.** Almost always Baillie–PSW, sometimes with extra
Miller–Rabin rounds. The number behaves like a prime under tests that composites rarely
survive. It is not a proof.

<span class="strength inconclusive">inconclusive</span>
**The question was not settled.** A timeout, a documented search bound, an open
mathematical question, or a catalogue with no entry. This is *not* a negative result and
Numerisect never presents it as one.

<span class="strength exploratory">exploratory</span>
**Indicative, not certified.** A plot sample taken as the midpoint of a rigorous
enclosure, a heuristic estimate, or a prediction from a conjecture. Useful for seeing the
shape of something; not a value to quote.

---

## Why probable is not proven

A composite that passes a primality test is called a pseudoprime to that test. Every
practical probabilistic test has them.

**Fermat.** By Fermat's little theorem, \(a^{n-1} \equiv 1 \pmod n\) for prime \(n\) and
\(\gcd(a,n)=1\). Composites satisfying this for a given \(a\) are Fermat pseudoprimes.
Worse, **Carmichael numbers** satisfy it for *every* base coprime to \(n\). The smallest
is \(561 = 3 \cdot 11 \cdot 17\). No amount of base-changing will expose it, so a Fermat
test alone can never be trusted.

**Miller–Rabin.** The strong test is far better: for any odd composite \(n > 9\), at most
a quarter of the bases in \([2, n-2]\) are strong liars. Repeating with \(k\) independent
random bases therefore fails to detect a composite with probability at most \(4^{-k}\).

That bound is about *random* bases. It says nothing about a *fixed* set of bases, and
composites are known that defeat any fixed small set. The smallest strong pseudoprime to
bases 2, 3, 5 and 7 is

\[
3215031751 = 151 \cdot 751 \cdot 28351 .
\]

Numerisect uses this number in its own test suite precisely because it separates a
careless implementation from a careful one.

**Baillie–PSW** combines a base-2 strong test with a Lucas test using Selfridge's
parameters. The two tests fail in different ways, and no composite is known to pass both.
Several authors have searched extensively without finding one, and there is a heuristic
argument that infinitely many should exist. Both statements are true at once:

!!! warning "What BPSW actually gives you"

    No BPSW pseudoprime is known below \(2^{64}\), and exhaustive verification covers
    that range. Above it, "no known counterexample" is a statement about the history of
    searching, not about mathematics. Numerisect labels every BPSW pass above \(2^{64}\)
    as **probable**.

---

## Where each label comes from

| Label | Produced by | Cost |
|---|---|---|
| Proven prime | PARI `isprime` (APR-CL or ECPP) | Seconds to hours, growing sharply with size |
| Proven prime, certified | PARI `primecert` then `primecertisvalid` | As above, plus verification |
| Probable prime | PARI `ispseudoprime`, GMP `mpz_probab_prime_p` | Milliseconds |
| Proven composite | Any test that fails, or an exhibited factor | Usually immediate |
| Inconclusive | A timeout or a bound being reached | Whatever budget you set |

The gap in cost is the reason both exist. Screening a million candidates with BPSW and
then proving only the survivors is the standard approach, and it is what Numerisect's
generation tools do.

---

## Proven does not mean the factorization is complete

A factorization can be fully proven and still not be finished. When Numerisect reports

```text
1000112004278059472142857 = 1000003 · 1000033 · 1000037 · 1000039
```

each factor is separately labelled. A composite cofactor that no engine has split is
reported as composite, not quietly dropped, and can be continued as a linked child job.

Numerisect accepts a factorization only when the returned factors multiply back to the
input. That check is performed by an engine, not in Python, and a run whose factors do
not reconstruct the input fails rather than reporting a partial answer.

---

## Inconclusive is not negative

This is the distinction most often lost in tools of this kind, and it is enforced
throughout Numerisect.

When the 56-class prime classifier tests membership, a class whose defining search
exceeds its budget is reported as **inconclusive**, separately from classes that
definitely do not match. The difference matters for classes like Mills, Wilson,
Wolstenholme and Fortunate primes, where the honest answer is often "not known within any
feasible search".

The same applies elsewhere:

- A SQUFOF run that exhausts its iteration limit is inconclusive. **It does not mean the
  input is prime.**
- An ECM campaign that finishes its curves without splitting the input is inconclusive.
  Raise \(B_1\) or the curve count, or switch to SIQS or NFS.
- A special-form search that times out reports an incomplete search rather than asserting
  no special form exists.
- A catalogue lookup with no entry means the catalogue does not know, nothing more.

!!! note "How to read an inconclusive result"

    Ask what bound was reached, which the response always states, and decide whether to
    raise it. Never treat it as evidence of absence.

---

## Certified versus exploratory in analytic work

The zeta and L-function tools use Arb's ball arithmetic, where every value carries a
rigorous error radius. A result like

```text
[1.6449340668482264364724151666460251892 +/- 3.19e-38]
```

is a *guaranteed enclosure*: the true value of \(\zeta(2)\) lies inside that interval.
This is a proof, not a floating-point approximation.

Three kinds of zeta result are certified:

- **Evaluations** as ball enclosures.
- **Zero locations** as intervals proven to contain a zero of the Hardy Z function.
- **Zero counts** through a height, via the Turing method.

Plot samples are different. Drawing a curve requires a number per pixel, so Numerisect
uses the midpoint of each enclosure. The shape is faithful; the individual values are
not certified. Every plot says so, and Numerisect never presents a heuristic count or a
finite plot as certification.

---

## External claims are unverified until checked

Anything that arrives from outside the machine is an unverified claim, whatever its
source. Catalogue lookups return claimed factors, and Numerisect passes every one to
PARI/GP, which decides divisibility and primality and computes the remaining cofactor.
The response reports what the engine found, not what the catalogue said.

The same principle covers imported primality certificates: a certificate is re-verified
with `primecertisvalid` rather than trusted because it looks well-formed.

---

## How the distinction is enforced

This is a design constraint, not a convention, and three mechanisms hold it in place.

**Completion markers.** Every engine program ends its output with a marker. A missing
marker is an error, never an empty successful result. A run killed by a timeout cannot be
mistaken for a search that found nothing.

**Explicit re-proof.** PARI's prime iterators and generators can return pseudoprimes
above \(2^{64}\). Numerisect applies `isprime` before calling any generated, ranged or
navigated value a proven prime.

**Independent cross-checks.** The verification tools compute the same quantity by several
independent implementations and report whether they agree. On disagreement Numerisect
reports every value and refuses to choose, because a majority of implementations sharing
a bug is exactly what a vote would conceal.

[:octicons-arrow-right-24: Independent verification](../VERIFICATION.md)

---

## References

- R. Baillie and S. S. Wagstaff, Jr., "Lucas pseudoprimes", *Mathematics of Computation*.
- C. Pomerance, J. L. Selfridge and S. S. Wagstaff, Jr., "The pseudoprimes to
  \(25 \cdot 10^9\)", *Mathematics of Computation*.
- R. Crandall and C. Pomerance, *Prime Numbers: A Computational Perspective*, 2nd ed.,
  Springer. Chapters 3 and 4 cover pseudoprimes and primality proving.
- H. Cohen, *A Course in Computational Algebraic Number Theory*, Springer.
- F. Johansson, "Arb: efficient arbitrary-precision midpoint-radius interval arithmetic",
  *IEEE Transactions on Computers*.
