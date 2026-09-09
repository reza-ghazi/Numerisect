# The engines

Numerisect computes nothing itself. Every mathematical result comes from one of the
programs below, and each page of this documentation names the routine responsible.

## What is installed

| Engine | Role in Numerisect | Licence |
|---|---|---|
| **PARI/GP** | The workhorse. Primality and proofs, factorization of moderate inputs, arithmetic functions, modular and algebraic structure, number fields, polynomial work, certificates, and most prime-structure searches. | GPL |
| **FLINT / Arb** | Rigorous complex analysis. Zeta and L-function evaluation as ball enclosures, certified critical-line zeros, Turing-method zero counts, multithreaded plot sampling. | LGPL |
| **YAFU** | Default factoring pipeline for small and medium inputs; small-factor work, ECM, SIQS, and its own strategies for rho, p−1, p+1, Fermat and NFS. | Public domain / MIT |
| **Msieve** | An independent general factoring pipeline, used on request and for cross-verification against YAFU. | Public domain |
| **GMP-ECM** | The elliptic-curve method as a standalone campaign engine, with resumable stage-one residues. | GPL |
| **CADO-NFS** | The number field sieve for large residual composites, including distributed sieving. | LGPL |
| **primesieve** | Multithreaded, cache-aware prime enumeration and k-tuplet counting over 64-bit intervals. | BSD |
| **primecount** | Exact \(\pi(x)\) to \(10^{31}\) and indexed primes to \(10^{29}\), with six mathematically distinct algorithm modes in one codebase. | BSD |

Engine sources are pinned to immutable upstream commits recorded in
`numerisect/engine_manifest.toml`. Nothing is downloaded or built until you confirm it.

## Programs written for this project

Three C programs exist because no installed library provides what they do. Each states
that justification in its own source header.

| Program | Why it exists |
|---|---|
| `numerisect_zeta.c` | Drives FLINT/Arb for zeta, Hardy Z, Gram points, Turing counts, Dirichlet L-functions and plot sampling, with OpenMP parallelism. |
| `numerisect_squfof.c` | Shanks' square forms factorization. Absent from every installed engine: YAFU has no `squfof` function, PARI implements it internally but exposes no standalone entry point, Msieve is QS/NFS only, and GMP-ECM is ECM/P−1/P+1 only. |
| `numerisect_bigsieve.c` | Prime enumeration above \(2^{64}\). primesieve refuses such inputs outright, and PARI's `forprime` is single-threaded and far slower there. |
| `numerisect_mfactor.c` | Mersenne trial factoring over \(q = 2kd + 1\). PARI/GP searches the same progression correctly, but with generic arbitrary-precision arithmetic on one core; measured here at about 1.1 million candidates a second against this helper's 1.3 billion. It sieves the progression by small primes, uses a 64-bit modular exponentiation below \(2^{64}\) with a GMP fallback above, and runs across every core. |
| `numerisect_mfactor_kernel.cu` | **Optional** CUDA kernel for the same scan, using Montgomery arithmetic. Compiled at run time by NVRTC, so no CUDA toolkit is needed, and verified on an RTX 5090 against both the published factorizations and the C helper. It computes nothing the C helper cannot, and measured only about 2.2x its rate because host-to-device transfer dominates. |

## Which engine answers which question

**Is this prime?** PARI `isprime` for a proof, `ispseudoprime` for Baillie–PSW. GMP's
independent test is available as a cross-check.

**Factor this.** Below the CADO threshold, YAFU. Above it, a YAFU ECM pretest and then
SIQS or CADO-NFS depending on the residual. SQUFOF, Msieve, GMP-ECM campaigns and the
individual YAFU strategies are all selectable directly.

**How many primes below x?** primecount, which is exact and enormously faster than
sieving at large \(x\). primesieve when you need the primes themselves rather than the
count. PARI as an independent check at small \(x\).

**List primes in an interval.** primesieve below \(2^{64}\); the project's own sieve above
it; PARI for arbitrary-offset tuple patterns.

**Anything analytic.** FLINT/Arb, with PARI for Dedekind zeta and general L-functions
where PARI's `lfun` machinery is the better fit.

## Engine health

Because results depend entirely on these programs, a miscompiled or mismatched build
would produce wrong answers silently. Two facilities guard against that.

The **self-test** asks each installed engine questions whose answers are published
constants, each carrying a citation, and reports any mismatch.

**Cross-checks** compute the same quantity by several independent implementations and
report whether they agree. On disagreement Numerisect reports every value and refuses to
choose.

[:octicons-arrow-right-24: Independent verification](../VERIFICATION.md)

## Optional engines

Only PARI/GP and FLINT are needed for most of the application. The heavier factoring
engines are optional; features that require a missing engine say so and return a clear
error rather than silently substituting a weaker method.

The status line at the top of the interface shows what is available, and the diagnostics
page reports engine versions, pinned revisions and build prerequisites in a sanitized
report that never includes hostnames, usernames or paths.
