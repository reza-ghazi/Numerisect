# Mersenne numbers

*Numerisect 0.7.0*

\(M_p = 2^p - 1\). This page covers what Numerisect can do with them, and is honest about
where each tool stops.

## The short answer

| Question | Tool | Practical reach |
| --- | --- | --- |
| Is \(M_p\) prime? | Lucas–Lehmer (`number_theory.gp`) | exponents in the thousands |
| Find a small factor of \(M_p\) | **Mersenne trial factoring**, below | exponents in the **millions** |
| Hunt for additional factors | **Staged factor hunt**, below | materialized \(M_p\), currently \(p\le10^6\) |
| Factor \(M_p\) completely | staged hunt or SNFS, when every cofactor can be resolved | strongly input-dependent |
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

If the odd exponent \(p\) is composite, a divisor \(q\) can have
\(d=\operatorname{ord}_q(2)\) equal to any divisor \(d>1\) of \(p\), not necessarily
\(p\) itself. Numerisect therefore asks PARI/GP to factor the exponent, enumerate every
such order divisor, and search

\[
q=2kd+1,\qquad d\mid p,\quad d>1.
\]

This includes the algebraic factors inherited from \(M_d\mid M_p\). For example,
\(1603=7\cdot229\), so \(M_7=127\) divides \(M_{1603}\); the search finds 127 at
\(d=7,k=9\). A prime-exponent-only \(q=2kp+1\) search would miss it.

The exponent \(p=2\) remains the trivial exception: \(M_2=3\). The specialized search
accepts odd prime or composite exponents starting at 3.

Membership is then decided by a single modular exponentiation:

\[
q \mid M_p \iff 2^p \equiv 1 \pmod q .
\]

PARI/GP also completes `isprime(q)` before the application calls a returned candidate a
prime factor; the pseudoprime filter is only a fast rejection step.

**\(M_p\) is never constructed.** Everything happens modulo the candidate. That is the whole
point: \(M_{1000151}\) has **301,076 decimal digits**, and its factor \(2000303\) is found at
\(k = 1\). Materializing that target merely to test a small candidate would waste memory
and arithmetic; modular powering makes the work depend on the candidate size and exponent
instead. This is the same reason a Mersenne search trial-factors an exponent before
committing to a Lucas–Lehmer test.

There is no formula that predicts the smallest factor—and therefore no mathematically
correct fixed value of \(k\) that can be inferred from \(p\). The application's
**Automatic** mode handles this honestly: the native search advances \(k\) until it finds
the first factor, reaches the 50,000,000 safety ceiling, or consumes the selected time
budget. It reports the largest \(k\) actually tested. **Manual** mode instead checks every
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

### How the search is made fast

PARI/GP searched this progression correctly but at about **1.1 million candidates a
second**, using generic arbitrary-precision arithmetic on one core. A compiled helper,
`numerisect-mfactor`, now does the scanning for any finite range and sustains about
**1.3 billion**. Three things account for it:

1. **The progression is sieved first.** \(q = 2kd+1\) is divisible by a small prime \(r\)
   exactly when \(k \equiv -(2d)^{-1} \pmod r\), an arithmetic progression in \(k\), so a
   sieve removes those \(k\) with no modular exponentiation at all. About 96% of the range
   goes this way at the default bound.
2. **Candidates below \(2^{64}\) use 64-bit arithmetic** with a 128-bit intermediate,
   instead of arbitrary precision. This is where nearly all the work lands.
3. **Every core is used.** The surviving tests are independent.

**Above \(2^{64}\) the helper falls back to GMP.** That path is slower but correct, and
the report counts how many candidates needed it, so a caller can see which ran.

**PARI/GP keeps both jobs it should keep.** It factors the exponent and enumerates the
order divisors before the scan, and it confirms afterwards that every reported \(q\) is
prime and genuinely divides \(2^d - 1\). The helper is a scanner, not an authority:
\(2^d \equiv 1 \pmod q\) makes \(q\) a divisor and says nothing about it being prime.
Nothing reaches a report on the scanner's word alone.

Automatic mode, which stops at the first factor and preserves findings when its budget
expires, still runs in PARI/GP. If no C compiler is available the whole search falls back
there too, and the answers are the same.

### The optional GPU accelerator

The modular exponentiations are perfectly independent, which is what a GPU is for.
`numerisect_mfactor_kernel.cu` runs them on the device using Montgomery multiplication,
which replaces a 128-bit division per multiply with two 64-bit multiplies and a shift.
The REDC bound applies, so it handles \(q < 2^{63}\); anything wider is **refused rather
than skipped**, because silently dropping candidates would turn an untested range into an
apparent absence of factors.

**No CUDA toolkit is required.** The kernel is compiled at run time by NVRTC, which ships
with the same packages as the CUDA runtime, for whichever device is actually present. A
machine can have an excellent GPU and no `nvcc` at all, which is exactly the case on the
workstation this was developed on. An `nvcc` build is still available for anyone who has
the toolkit; both compile the same kernel file.

**Verified on hardware.** On an RTX 5090 (compute capability 12.0, NVRTC 13.0) the device
returns the published factorizations for every case tested, and agrees exactly with the
compiled CPU helper on the same sieved candidate set. The suite skips these tests cleanly
where there is no device.

**What it is worth, measured honestly:**

| | candidates tested per second |
|---|---|
| C helper, 24 cores | 7.4 million |
| RTX 5090 through this path | 16.5 million |

About **2.2x**, not the order of magnitude the hardware suggests. The kernel is not the
limit; moving candidate lists from host to device is. A pipeline that generated
candidates on the device would do much better, and this is not that. It is offered as a
real, verified option rather than as the fast path, and the C helper remains the default.

!!! note "A hit is a divisor, not a prime factor"

    \(2^d \equiv 1 \pmod q\) makes \(q\) a divisor of \(2^d - 1\) and says nothing about
    \(q\) being prime. Composite divisors genuinely occur: \(2047 = 23 \cdot 89\) divides
    \(2^{11} - 1\) and the kernel reports it correctly. The pipeline sieves those out
    beforehand and PARI/GP confirms primality afterwards.

### Finding nothing is inconclusive

For prime \(p\), an exhausted \(k\) range means no factor of the form \(2kp+1\) exists
below the bound searched. For composite \(p\), it means every selected
\(q=2kd+1\) order progression was exhausted through that bound. Neither outcome is
evidence that \(M_p\) is prime.

Finding one or several trial factors is still not a complete factorization. Dividing them
out can leave a cofactor almost as large as \(M_p\): for \(M_{87083}\), the displayed
eight-digit factor leaves a cofactor of roughly 26,207 decimal digits. Completely
factoring a cofactor of that size is not currently practical. Numerisect therefore says
**factors found**, never **all factors**, unless an engine has actually resolved and
verified every cofactor.

## Staged factor hunt and factor inventory

The second form on **Factor integers → Mersenne numbers** joins the native operations
that are useful after trial factoring:

1. PARI/GP exhaustively searches the selected finite \(k\) range.
2. PARI/GP constructs \(M_p\), verifies that each reported divisor divides it, removes
   every occurrence, and records exact multiplicities.
3. GMP-ECM runs Pollard \(p-1\), Williams \(p+1\), and an elliptic-curve campaign on the
   exact remaining cofactor, with the selected CPU count exposed to its native OpenMP
   runtime.
4. After every discovery, PARI/GP reconciles the entire inventory again and attempts a
   bounded rigorous primality proof for the cofactor.

The web response shows only a bounded cofactor preview. The automatically saved report
contains the **exact complete cofactor**, even when it has tens of thousands of digits.
The status vocabulary is deliberate:

- `proven_prime` means PARI/GP completed a rigorous proof;
- `composite` means the cofactor is definitely composite;
- `probable_prime` means screening succeeded but the proof budget expired;
- `unknown` means even bounded screening did not finish;
- **complete prime factorization: yes** appears only when all reported divisors and the
  final cofactor are rigorously prime.

P−1, P+1, and ECM are factor-discovery methods, not exhaustive searches. Finishing all
three without a new divisor leaves the result incomplete. For a cofactor of practical
NFS size, it can subsequently be submitted to the ordinary SIQS/NFS/SNFS workflow. A
26,207-digit cofactor such as the one left by the known factor of \(M_{87083}\) is far
beyond a realistic complete NFS factorization.

```bash
curl --cookie jar --header 'Content-Type: application/json' \
  --data '{"exponent":87083,"trial_k_limit":100000,"trial_seconds":60,"stage_seconds":60}' \
  http://127.0.0.1:8765/api/factor-lab/mersenne-hunt
```

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
POST /api/factor-lab/mersenne-factors   trial-factor over every odd order divisor d of p
POST /api/factor-lab/mersenne-hunt      trial, P-1, P+1, ECM, and exact reconciliation
POST /api/factor-lab/special-form       recognise the form, report the SNFS polynomial
POST /api/number-theory/lucas-lehmer    prove primality of M_p
```
