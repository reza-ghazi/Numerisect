# Numerisect

Numerisect is a local workbench for integer factorization, primality, prime exploration
and analytic number theory. It runs on your machine, listens only on loopback, and keeps
every calculation, log and result there.

**It is a user interface over existing number-theory libraries.** PARI/GP, FLINT/Arb,
YAFU, Msieve, CADO-NFS, GMP-ECM, primesieve and primecount perform the mathematics.
Where no library provides a routine, a small compiled C program fills the gap. Python
handles validation, process orchestration and the HTTP API; JavaScript draws the
interface. Neither computes a mathematical result.

That constraint is the reason this documentation exists in the form it does. If you want
to know how a result was obtained, the answer is always a named routine in a named
library, and every page here says which.

---

## Start here

<div class="grid cards" markdown>

-   **New to Numerisect**

    ---

    Install it, factor your first integer, and learn your way around the interface.

    [:octicons-arrow-right-24: Installation](getting-started/installation.md)

-   **Understand the results**

    ---

    What "proven", "probable" and "inconclusive" mean here, and why the distinction is
    enforced everywhere.

    [:octicons-arrow-right-24: Proven and probable](concepts/proven-and-probable.md)

-   **Learn the mathematics**

    ---

    The theory behind every tool: primality, factorization, distribution, modular
    structure, quadratic forms and zeta.

    [:octicons-arrow-right-24: Mathematics](mathematics/index.md)

-   **Look something up**

    ---

    Every HTTP route, the command line, configuration and output formats.

    [:octicons-arrow-right-24: Reference](reference/api.md)

</div>

---

## What it does

| Area | Examples |
|---|---|
| **Factorization** | Automatic YAFU-to-CADO routing, SQUFOF, resumable ECM campaigns, SIQS and NFS with expert parameters, cross-engine verification, distributed CADO-NFS |
| **Primality** | Rigorous proofs, Baillie–PSW, a comparison laboratory across eight tests, deterministic Miller–Rabin witness sets, Pocklington and Pratt certificates |
| **Prime structure** | A 56-class catalogue, reciprocal periods, special families, Cunningham chains, covering sets, constrained generation |
| **Distribution** | Exact \(\pi(x)\) to \(10^{31}\), six independent counting algorithms compared, nth-prime bounds, prime races, maximal gaps, Hardy–Littlewood and Bateman–Horn predictions |
| **Algebra** | Congruences over composite moduli, four discrete-logarithm algorithms, finite fields, number fields with prime-ideal decomposition, Chebotarev experiments |
| **Quadratic forms** | Reduction, composition, class groups, Pell equations, continued fractions of quadratic irrationals |
| **Zeta and L-functions** | Rigorous \(\zeta(s)\) enclosures, certified critical-line zeros, Turing counts, Riemann–Siegel, pair correlation, Dirichlet L-functions, Dedekind zeta |
| **Visualization** | Ulam, Sacks and polar spirals, Eisenstein lattices, modular wheels, residue heatmaps, sieve animations |

---

## How results are labelled

Numerisect never blurs the strength of a claim. Four labels appear throughout the
application and this documentation.

<span class="strength proven">proven</span>
A mathematical proof. PARI's `isprime` returns one; so does a verified primality
certificate. If Numerisect says proven, a proof exists.

<span class="strength probable">probable</span>
A strong probabilistic test passed, most often Baillie–PSW. No counterexample is known.
That is not the same as no counterexample existing.

<span class="strength inconclusive">inconclusive</span>
A timeout, a search bound, or an open question. **This is never reported as a negative
result.** An exhausted search does not mean the thing does not exist.

<span class="strength exploratory">exploratory</span>
A plot sample, a midpoint of a rigorous enclosure, or a heuristic estimate. Useful for
seeing shape; not a certified value.

[:octicons-arrow-right-24: Read more](concepts/proven-and-probable.md)

---

## Honest limits

!!! warning "This is an experimental pre-release"

    Numerisect is source-distributed and has no official binary packages. It has been
    exercised on Fedora Linux x86-64. Windows WSL and macOS paths are implemented but
    have not been verified by the project.

Some things it deliberately does not do:

- **It does not go online during calculations.** Engine installation and the optional
  catalogue lookups are the only outbound paths, both behind explicit confirmation.
- **It is not audited cryptographic software.** The prime-construction laboratory is
  labelled experimental and should not be used to generate keys.
- **It does not claim more than it proves.** Where an engine cannot answer, the gap is
  reported rather than approximated.

---

## Licence and provenance

Numerisect is licensed GPL-3.0-or-later. The native engines it builds are pinned to
immutable upstream commits recorded in `engine_manifest.toml`, and every completed
factorization carries a reproducibility manifest listing the commands, engine revisions
and executable checksums used.

[:octicons-arrow-right-24: Third-party licences](https://github.com/reza-ghazi/Numerisect/blob/main/THIRD_PARTY_LICENSES.md)
