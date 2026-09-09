---
description: A local workbench for integer factorization, primality and analytic number theory.
---

# Numerisect

Numerisect is a local workbench for integer factorization, primality, prime exploration
and analytic number theory. It runs on your machine, listens only on loopback, and keeps
every calculation, log and result there.

!!! info "Current release: 0.7.0"

    Numerisect is an experimental, source-distributed pre-release. The current interface
    contains 133 Prime Tools pages, 22 zeta/L-function pages, an expert factorization
    workspace, and 212 documented API operations. Start with the
    [capability index](capabilities.md) when you know the question but not the tool name.

**It is a user interface over existing number-theory libraries.** PARI/GP, FLINT/Arb,
YAFU, Msieve, CADO-NFS, GMP-ECM, primesieve and primecount perform the mathematics.
Where no library provides a routine, a small compiled C program fills the gap. Python
handles validation, process orchestration and the HTTP API; JavaScript draws the
interface. Neither computes a mathematical result.

That constraint is the reason this documentation exists in the form it does. If you want
to know how a result was obtained, the answer is always a named routine in a named
library, and every page here says which.

The public project address is <https://numerisect.com>. It permanently redirects here,
to the canonical documentation site at <https://docs.numerisect.com>, so both addresses
lead visitors to the same maintained content.

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

-   **Survey the whole workbench**

    ---

    A compact, auditable map of the factorization, Prime Tools, zeta, verification and
    workflow capabilities currently shipped in 0.7.0.

    [:octicons-arrow-right-24: Capability index](capabilities.md)

</div>

---

## What it does

| Area | Examples |
|---|---|
| **Factorization** | Automatic YAFU-to-CADO routing, SQUFOF, resumable ECM campaigns, SIQS and NFS with expert parameters, GGNFS siever diagnostics, distributed CADO-NFS, RSA Challenge verification, Mersenne trial factoring without constructing \(2^p-1\), and staged Mersenne cofactor hunts |
| **Primality** | Rigorous proofs, Baillie–PSW, a comparison laboratory across eight tests, deterministic Miller–Rabin witness sets, Pocklington and Pratt certificates |
| **Prime structure** | A 56-class catalogue, exact reciprocal periods, Gaussian and Eisenstein primes, special families, Cunningham chains, covering sets, and constrained generation |
| **Distribution** | Exact \(\pi(x)\) to \(10^{31}\), six mathematically distinct `primecount` algorithms plus independent PARI and primesieve cross-checks, nth-prime bounds, prime races, maximal gaps, and clearly labelled Hardy–Littlewood and Bateman–Horn predictions |
| **Algebra** | Congruences over composite moduli, four discrete-logarithm algorithms, finite fields, number fields with prime-ideal decomposition, Chebotarev experiments |
| **Quadratic forms** | Reduction, composition, class groups, Pell equations and continued fractions at unlimited digit length |
| **Zeta and L-functions** | Rigorous \(\zeta(s)\) enclosures, certified critical-line zeros, Turing counts, Riemann–Siegel, pair correlation, Dirichlet L-functions, Dedekind zeta |
| **Visualization** | Ulam, Sacks and polar spirals, Eisenstein lattices, modular wheels, residue heatmaps, sieve animations |
| **Research workflow** | Batch import, local result cache, saved workspaces, searchable reports and jobs, resource limits, CLI/API parity, export formats, and reproducibility manifests |

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
    exercised on Fedora Linux x86-64 and by GitHub Actions on Ubuntu Linux x86-64 and
    ARM64, Ubuntu 24.04 x86-64 inside Windows WSL, and macOS on ARM64 and Intel. Native
    Windows remains unsupported, and the Arch Linux installer path has not yet received
    clean-host CI verification.

Some things it deliberately does not do:

- **Ordinary calculations stay local.** The three network-capable paths are confirmed
  engine source builds, optional catalogue lookups, and deliberately configured
  distributed CADO-NFS. Each is off by default or requires explicit authorization; there
  is no telemetry, analytics, or update check.
- **It is not audited cryptographic software.** The prime-construction laboratory is
  labelled experimental and should not be used to generate keys.
- **It does not claim more than it proves.** Where an engine cannot answer, the gap is
  reported rather than approximated.

---

## Source code

Numerisect is free software. The complete source, including every PARI/GP program and
C helper described in this documentation, is public.

<div class="grid cards" markdown>

-   :fontawesome-brands-github: **Repository**

    ---

    Read the source, the commit history and the test suite.

    [:octicons-arrow-right-24: reza-ghazi/Numerisect](https://github.com/reza-ghazi/Numerisect)

-   :octicons-tag-24: **Releases**

    ---

    Tagged versions, each with a changelog entry.

    [:octicons-arrow-right-24: Releases](https://github.com/reza-ghazi/Numerisect/releases)

-   :octicons-bug-24: **Report a problem**

    ---

    A wrong answer, a build failure or a gap in these pages.

    [:octicons-arrow-right-24: Issue tracker](https://github.com/reza-ghazi/Numerisect/issues)

-   :octicons-git-pull-request-24: **Contribute**

    ---

    The native-computation policy every change has to satisfy.

    [:octicons-arrow-right-24: Contributing](about/contributing.md)

</div>

If you report a wrong mathematical result, include the exact input, the engine that
produced it and the saved report from your `output/` directory. Those three things make
the result reproducible, which is the only way a disagreement gets settled.

---

## Licence and provenance

Numerisect is licensed GPL-3.0-or-later. The native engines it builds are pinned to
immutable upstream commits recorded in `engine_manifest.toml`, and every completed
factorization carries a reproducibility manifest listing the commands, engine revisions
and executable checksums used.

[:octicons-arrow-right-24: Third-party licences](https://github.com/reza-ghazi/Numerisect/blob/main/THIRD_PARTY_LICENSES.md)

[:octicons-arrow-right-24: Citing Numerisect](https://github.com/reza-ghazi/Numerisect/blob/main/CITATION.cff)
