# Mersenne numbers

*Numerisect 0.6.0*

\(M_p = 2^p - 1\). This page covers what Numerisect can do with them, and is honest about
where each tool stops.

## The short answer

| Question | Tool | Practical reach |
| --- | --- | --- |
| Is \(M_p\) prime? | Lucas–Lehmer (`number_theory.gp`) | exponents in the thousands |
| Find a small factor of \(M_p\) | **Mersenne trial factoring**, below | exponents in the **millions** |
| Factor \(M_p\) completely | SNFS through the ordinary pipeline | roughly \(p \le 1200\) |
| Is this a known Mersenne prime? | the 56-class prime classifier | catalogue lookup |

The middle row is the one that changes what is possible, and it is the reason this page
exists.

## Trial factoring, and why it reaches so far

Every prime factor \(q\) of \(M_p\), for odd prime \(p\), satisfies two classical congruences:

\[
q \equiv 1 \pmod{2p}, \qquad q \equiv \pm 1 \pmod 8 .
\]

The first follows because the order of \(2\) modulo \(q\) is exactly \(p\), so \(p \mid q-1\)
and \(q\) is odd. The second is the condition for \(2\) to be a quadratic residue modulo
\(q\). Together they confine every candidate to \(q = 2kp + 1\) with
\(q \equiv \pm 1 \pmod 8\). The second condition retains two of the four possible odd
residue classes, so it discards one half of that progression before the modular test.

The exponent \(p=2\) is the trivial exception: \(M_2=3\), and 3 is not of the form
\(2kp+1\) for an integer \(k\). The specialized progression search therefore accepts
odd prime exponents starting at 3. The ordinary primality and factorization tools still
handle 3 normally.

Membership is then decided by a single modular exponentiation:

\[
q \mid M_p \iff 2^p \equiv 1 \pmod q .
\]

**\(M_p\) is never constructed.** Everything happens modulo the candidate. That is the whole
point: \(M_{1000151}\) has **301,076 decimal digits**, and its factor \(2000303\) is found at
\(k = 1\). Materializing that target merely to test a small candidate would waste memory
and arithmetic; modular powering makes the work depend on the candidate size and exponent
instead. This is the same reason a Mersenne search trial-factors an exponent before
committing to a Lucas–Lehmer test.

There is no formula that predicts the smallest factor—and therefore no mathematically
correct fixed value of (k) that can be inferred from (p). The application's
**Automatic** mode handles this honestly: the native search advances (k) until it finds
the first factor, reaches the 50,000,000 safety ceiling, or consumes the selected time
budget. It reports the largest (k) actually tested. **Manual** mode instead checks every
candidate through the bound supplied by the user and reports every factor in that finite
range. Factors found before a timeout are retained in either mode.

```bash
curl --cookie jar --header 'Content-Type: application/json' \
  --data '{"exponent":1000151,"k_limit":5}' \
  http://127.0.0.1:8765/api/factor-lab/mersenne-factors
```

### Results this actually produced

Every factor below was found by the route above and then **verified in a separate PARI/GP
session**, not by the routine that found it. For each one: \(q\) is prime, \(k\) is a genuine
integer in \(q = 2kp+1\), \(q \equiv \pm 1 \pmod 8\), and \(2^p \equiv 1 \pmod q\). Where an
exponent has several factors, the product of all of them was also checked to divide
\(M_p\).

| exponent \(p\) | decimal digits of \(M_p\) | factors found |
| --- | --- | --- |
| 2,000,003 | 602,061 | 160000241, 8924785387159 |
| 30,000,001 | 9,030,901 | 1380000047 |
| 50,000,017 | 15,051,505 | 1131900384847, 3615901229407, 355682820932119 |
| 70,000,027 | 21,072,108 | 9520003673 |
| 400,000,009 | 120,412,001 | 10876800244729 |
| 600,000,001 | 180,617,998 | 27600000047, 2418000004031 |
| 999,999,001 | 301,029,695 | 357999642359 |

The last row is the one to look at. \(M_{999999001}\) has **301,029,695 decimal digits**.
Representing such a value is already substantial, while applying a general-purpose
factorization to it is not realistic. Testing twenty million candidates, up to roughly
\(4 \times 10^{16}\), took **10.7 seconds** in the recorded local run because the target
is never built. That timing describes one machine and build, not a portable benchmark.

Two known Mersenne prime exponents, 6,972,593 and 20,996,011, were searched as controls
and correctly yielded nothing.

### Finding nothing is inconclusive

An exhausted \(k\) range means **no factor of the form \(2kp+1\) exists below the bound
searched**. It is not evidence that \(M_p\) is prime, and Numerisect never reports it as
such. For primality, use the Lucas–Lehmer test, which is a proof.

Finding one or several trial factors is still not a complete factorization. Dividing them
out can leave a cofactor almost as large as (M_p): for (M_{87083}), the displayed
eight-digit factor leaves a cofactor of roughly 26,207 decimal digits. Completely
factoring a cofactor of that size is not currently practical. Numerisect therefore says
**factors found**, never **all factors**, unless an engine has actually resolved and
verified every cofactor.

## Complete factorization

A Mersenne number exposes algebraic structure that a special number field sieve can use:
\(M_p = 2^p - 1\) gives the symbolic relation \(x^p-1\) at \(x=2\). The special-form
analyser reports that relation and a difficulty indicator; the selected NFS engine still
owns production polynomial selection and parameters:

```text
2^1061-1  ->  homogeneous, n = 2^1061 - 1
              SNFS suitable: yes
              SNFS polynomial: x^1061 - 1
              SNFS difficulty: 319
```

Hand the number to the ordinary factoring pipeline to actually run it. A displayed
special-form relation is advice, not a claim that the factorization is practical or that
an engine-ready polynomial has already been selected.

!!! warning "The analyser used to hang here"

    Detecting the algebraic split called `factor()` on \(\Phi_n(b)\), and \(\Phi_n(b)\) *is*
    the whole input whenever \(n\) is prime. Asking for a special-form report on
    \(2^{1061}-1\) therefore asked PARI to factor a 320-digit number inside a metadata
    routine, which exhausted its budget and returned nothing at all. The split is now
    attempted only below a size cap, and above it is reported as not attempted, which is
    inconclusive rather than a claim that no algebraic factor exists.

## Primality

`nt_lucas_lehmer` implements the Lucas–Lehmer test: \(M_p\) is prime exactly when
\(s_{p-2} \equiv 0 \pmod{M_p}\) for \(s_0 = 4\), \(s_{i+1} = s_i^2 - 2\). This one **is** a
proof, not a probable-prime test. It constructs \(M_p\), so its reach is governed by memory
and time rather than by the arithmetic, and it is far slower than trial factoring: on a
large exponent, search for a factor first.

`pl_lucas_lehmer_riesel` covers the related \(k \cdot 2^n - 1\) family.

Lucas–Lehmer's nonzero final residue proves that \(M_p\) is composite but does not
identify a divisor. In the application, a composite result therefore links directly to
**Factor integers → Mersenne numbers**, where the separate progression search tests
\(q=2kp+1\) candidates without constructing \(M_p\).

## Routes

```text
POST /api/factor-lab/mersenne-factors   trial-factor M_p over q = 2kp + 1
POST /api/factor-lab/special-form       recognise the form, report the SNFS polynomial
POST /api/number-theory/lucas-lehmer    prove primality of M_p
```
