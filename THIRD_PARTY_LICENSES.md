# Third-party software and licenses

Numerisect itself is licensed under `GPL-3.0-or-later`. The canonical GPLv3
text is in [LICENSE](LICENSE). Third-party projects keep their own licenses;
this notice does not relicense them and is not legal advice.

Numerisect does not vendor these projects. An explicit user-approved engine
installation clones a reviewed Git commit into the user's local state
directory and builds it there. The authoritative machine-readable pins are in
[`numerisect/engine_manifest.toml`](numerisect/engine_manifest.toml). Git
revisions are verified after checkout. No archive is currently downloaded, so
archive checksums are not applicable.

| Component | Official project | License identified upstream | Numerisect interaction |
|---|---|---|---|
| YAFU | [bbuhrow/yafu](https://github.com/bbuhrow/yafu) | Public-domain dedication in upstream build files; bundled and reused components may carry separate notices | Cloned at a pinned commit, compiled locally, and invoked as a separate executable |
| Msieve | [upiter/msieve](https://github.com/upiter/msieve) | Public-domain dedication stated in the upstream README | Cloned at a pinned commit, compiled locally, and invoked as a separate executable |
| GGNFS lattice sievers | [radii/ggnfs](https://github.com/radii/ggnfs) | `GPL-2.0-or-later` | Cloned at a pinned commit and compiled locally. Numerisect never invokes these binaries itself; YAFU calls them to perform the number field sieve. The separate lasieve5 line, distributed as prebuilt binaries with recent YAFU releases, is detected and used if already present but is never downloaded. |
| CADO-NFS | [CADO-NFS GitLab](https://gitlab.inria.fr/cado-nfs/cado-nfs) | `LGPL-2.1-only` (`COPYING` at the pinned revision) | Cloned at a pinned commit, compiled locally, and invoked as a separate executable |
| PARI/GP | [PARI/GP](https://pari.math.u-bordeaux.fr/) | `GPL-2.0-or-later` | Cloned at a pinned commit, compiled locally, and invoked through the `gp` executable |
| GMP-ECM | [GMP-ECM GitLab](https://gitlab.inria.fr/zimmerma/ecm) | `GPL-3.0-or-later` (`COPYING` at the pinned revision) | Cloned at a pinned commit, compiled locally, and invoked as a separate executable |
| FLINT | [FLINT](https://flintlib.org/) | `LGPL-3.0-or-later` for the pinned FLINT 3.6 source | Installed as a system or user-local shared library; the Numerisect zeta helper dynamically links to it |
| Arb | [Arb](https://arblib.org/) | Standalone Arb: `LGPL-2.1-or-later`; Arb was merged into FLINT in 2023 | Numerisect uses Arb ball-arithmetic APIs supplied by FLINT 3 rather than downloading standalone Arb |
| primesieve | [kimwalisch/primesieve](https://github.com/kimwalisch/primesieve) | `BSD-2-Clause` | Cloned at the pinned 12.15 commit, compiled locally, and invoked for multithreaded 64-bit interval sieving |
| primecount | [kimwalisch/primecount](https://github.com/kimwalisch/primecount) | `BSD-2-Clause` | Cloned at the pinned 8.5 commit, linked to primesieve, and invoked for exact counting and indexed primes |
| GMP | [GNU MP](https://gmplib.org/) | Dual-licensed `LGPL-3.0-or-later` or `GPL-2.0-or-later` | System or transitive native build dependency |
| MPFR | [GNU MPFR](https://www.mpfr.org/) | `LGPL-3.0-or-later` | System or transitive native build dependency |

## Review warning

Before any binary redistribution, a licensing specialist should review the
exact YAFU source tree and its bundled components, the resulting link graph,
and all notices emitted by each native build. Numerisect currently distributes
source only and publishes no official binaries.
