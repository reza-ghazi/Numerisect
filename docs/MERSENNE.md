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

Every prime factor \(q\) of \(M_p\), for prime \(p\), satisfies two classical congruences:

\[
q \equiv 1 \pmod{2p}, \qquad q \equiv \pm 1 \pmod 8 .
\]

The first follows because the order of \(2\) modulo \(q\) is exactly \(p\), so \(p \mid q-1\)
and \(q\) is odd. The second is the condition for \(2\) to be a quadratic residue modulo
\(q\). Together they confine every candidate to \(q = 2kp + 1\) with \(q \equiv \pm 1 \pmod 8\),
which discards three quarters of that progression before any real work happens.

Membership is then decided by a single modular exponentiation:

\[
q \mid M_p \iff 2^p \equiv 1 \pmod q .
\]

**\(M_p\) is never constructed.** Everything happens modulo the candidate. That is the whole
point: \(M_{1000151}\) has **301,076 decimal digits**, and its factor \(2000303\) is found at
\(k = 1\). Building that number in order to divide by it would be pointless, and for larger
exponents impossible. This is the same reason GIMPS trial-factors an exponent before
committing to a Lucas–Lehmer test.

```bash
curl --cookie jar --header 'Content-Type: application/json' \
  --data '{"exponent":1000151,"k_limit":5}' \
  http://127.0.0.1:8765/api/factor-lab/mersenne-factors
```

### Finding nothing is inconclusive

An exhausted \(k\) range means **no factor of the form \(2kp+1\) exists below the bound
searched**. It is not evidence that \(M_p\) is prime, and Numerisect never reports it as
such. For primality, use the Lucas–Lehmer test, which is a proof.

## Complete factorization

A Mersenne number is the ideal special number field sieve target: \(M_p = 2^p - 1\) gives the
polynomial \(x^p - 1\) directly, so SNFS difficulty is the size of the number rather than
anything worse. The special-form analyser reports this:

```text
2^1061-1  ->  homogeneous, n = 2^1061 - 1
              SNFS suitable: yes
              SNFS polynomial: x^1061 - 1
              SNFS difficulty: 319
```

Hand the number to the ordinary factoring pipeline to actually run it. Difficulty around
320 is at the edge of what a workstation will finish; \(M_{1061}\) itself took a large
distributed effort in 2012.

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

## Routes

```text
POST /api/factor-lab/mersenne-factors   trial-factor M_p over q = 2kp + 1
POST /api/factor-lab/special-form       recognise the form, report the SNFS polynomial
POST /api/number-theory/lucas-lehmer    prove primality of M_p
```
