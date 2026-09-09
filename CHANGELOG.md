# Changelog

Numerisect is an experimental, source-distributed pre-release. No official
binary packages are published.

## Unreleased

- Removed a Python reimplementation of engine mathematics from the test suite. A GPU test
  built its own candidate set with a full sieve of Eratosthenes and Fermat modular
  inverses written in Python, duplicating what the C helper does. Checking an engine
  against a second implementation written here is not an independent check: a mistake
  shared between the two makes both look correct. The reference now comes from PARI/GP.
- Registered `gpu.py` in the native-computation policy's module list. It had been added
  without one, so none of the dispatch or engine-naming checks applied to it. A CUDA
  kernel launch now counts as engine dispatch, and CUDA and NVRTC count as named engines.
- Added a policy test forbidding Python number theory in the package **and in the test
  suite**: three-argument `pow`, which is modular exponentiation, and `math.gcd`,
  `math.isqrt`, `math.factorial`, `math.comb` and `math.perm`. Verified against a planted
  violation rather than assumed to work.

- Fixed engine results above 4,300 decimal digits raising `ValueError` in every boundary
  module. CPython refuses to convert an integer of more than 4,300 digits to or from a
  string, a denial-of-service guard aimed at untrusted input, and engine output is not
  untrusted input. The guard was lifted only as a side effect of importing the expression
  evaluator, so the web application and the CLI worked while importing any of the ten
  boundary modules directly failed on a large result. Lucas-Lehmer on M_19937 returns
  6,002 digits and raised. The guard is now lifted in the module where the conversion
  happens, and a test asserts every boundary module lifts it regardless of import order.

- Extended the CUDA scanner to two-limb Montgomery arithmetic, so the device now tests
  candidates up to 2^127 instead of stopping at 2^63. At a Mersenne exponent near 10^9
  the old ceiling was reached around k = 4.6 billion, past which the range fell back to
  GMP on the CPU at roughly a hundredth the rate per candidate. Measured across that
  boundary the device is now about **nine times** the C helper: 13.9 seconds against
  121.3 for k up to two times 10^10, with both agreeing exactly on the factors and the
  device deferring nothing.
- The arithmetic is CIOS Montgomery multiplication for a two-limb odd modulus, validated
  before it reached the device: 400,000 randomised agreements against 64-bit modular
  exponentiation, thirteen wide negatives and six wide positives above 2^64 checked
  against PARI/GP. One detail cost an hour and is recorded in the source: R mod n must be
  built by doubling 1 exactly 128 times, not by reducing 2^128 with repeated subtraction,
  which runs about 2^128/n times and does not terminate for a small n.
- The public Mersenne search now uses the device across the whole k ceiling rather than
  only inside the single-limb range.
- The standalone GPU binary no longer reports `deferred-wide` for these ranges, because
  it no longer defers them. The honesty guarantee is unchanged: anything it cannot test
  is still counted and reported rather than silently dropped.

- Closed the GPU performance gap. The CUDA scanner now sieves and tests entirely on the
  device, so no candidate crosses the bus, and it measures about **twelve times** the C
  helper's rate: two seconds against twenty-three for four billion candidates at an order
  near 10^9. The public Mersenne search uses it automatically.
- Two corrections were needed to get there, both caught by measurement. Sieving on the
  host and copying survivors was slower than the C helper, because thirty 64-bit
  Montgomery squarings per candidate does not pay for a PCIe transfer. Moving the sieve to
  the device with one thread per prime was slower still: in a 67-million-entry segment the
  thread holding r = 3 performs 22 million serialized writes while a thread near the sieve
  bound performs seventy. Splitting the work by (prime, chunk) instead of by prime fixed
  it, spreading a small prime's work across every chunk.
- The device is used only when every candidate in the requested range stays below 2^63,
  the Montgomery bound. Wider ranges run on the C helper, which tests them with GMP rather
  than deferring them, so speed is never bought by leaving candidates untested. The
  standalone GPU binary reports deferrals explicitly and never counts them as tested.
- Reports name the scanner that actually ran, CPU or device, and a test asserts the engine
  label and the scanner metric agree.
- Both scanners are now checked against each other as well as against the published
  factorizations.

- Built and verified the offline CUDA path now that a toolkit is installed. `nvcc` 13.4
  compiles the helper, it recovers every published Mersenne factorization on an RTX 5090,
  and it defers candidates at or above 2^63 rather than skipping them, so an untested
  range never reads as an absence of factors. Two tests cover it and skip without a
  toolkit.
- Fixed a type error that only an offline build could expose: the kernel takes
  `unsigned long long` while the host code used `uint64_t`, which is `unsigned long` on
  LP64. Same width, distinct type, and nvcc rejects the launch. NVRTC never saw it
  because it compiles the kernel alone.
- **Corrected the GPU performance claim again, downward.** The earlier entry reported
  about 2.2x from the runtime-compiled path. Benchmarked properly as a standalone binary
  against the C helper on the same range, the GPU build is **slower**: 13.5 seconds
  against 11.3 for two billion candidates. The kernel is not at fault. The work per
  candidate is roughly thirty 64-bit Montgomery squarings, and the pipeline must sieve,
  gather survivors and copy them to the device, while the C helper tests each survivor in
  place in the loop that found it.
- Parallelised the GPU build's host-side sieve, which had been single-threaded and made
  that build about half the speed of the pure-CPU helper. It is now about four fifths,
  which locates the remaining cost in data movement rather than arithmetic. Closing the
  gap would mean sieving on the device so candidates are never transferred, which is a
  different program.
- The C helper stays the default. The GPU path is correct, verified and available, and it
  is not an improvement on 24 cores for this workload.

- **Correction: the CUDA path is verified on hardware, and no CUDA toolkit is needed.**
  The previous entry said the device path had never been executed because no machine had
  a toolkit. The toolkit is indeed absent, but that conclusion was wrong: this workstation
  has the full CUDA runtime installed through pip, including NVRTC, the runtime compiler.
  The kernel is now compiled by NVRTC for whichever device is present, so `nvcc` is not
  required at all. On an RTX 5090 it returns the published factorizations for every case
  tested and agrees exactly with the compiled CPU helper on the same sieved candidates.
- Measured what the GPU is actually worth here: about 16.5 million candidates a second
  against the C helper's 7.4 million across 24 cores, a factor of roughly 2.2 rather than
  the order of magnitude the hardware suggests. The kernel is not the limit; host-to-device
  transfer is. The C helper remains the default and the GPU is an option, not the fast path.
- Split the device code into `numerisect_mfactor_kernel.cu`, free of includes and host
  code so one source compiles both under `nvcc` and under NVRTC.
- Candidates at or above 2^63 are refused by the GPU path rather than skipped, since the
  Montgomery bound cannot cover them and dropping them silently would turn an untested
  range into an apparent absence of factors.

- Stopped reports crediting PARI/GP with work it did not do. Both shared report savers
  overwrote the engine label unconditionally, so a Mersenne scan run entirely by the
  compiled helper came back to the caller labelled `PARI/GP`. A result that names its own
  engine now keeps that name, and a test pins both paths.

- Stopped continuous integration depending on apt repositories the project does not use.
  The hosted runner image ships Google Chrome and Microsoft sources, and on 2026-09-09
  the Chrome repository served an index whose hash did not match its Release file, so
  `apt-get update` exited non-zero and failed the Quality workflow on every Python
  version. Every package the build installs comes from the Ubuntu archives, so those
  sources are now removed before the update rather than relied on.

- Added `numerisect_mfactor.c`, a compiled Mersenne trial-factoring scanner, and made it
  the engine for any finite k range. PARI/GP searched the same progression correctly but
  with generic arbitrary-precision arithmetic on one core, measured here at about 1.1
  million candidates a second for p = 999999001; the helper sustains about 1.3 billion.
  It sieves each progression by small primes first, which removes roughly 96% of the
  range with no modular exponentiation, uses 64-bit arithmetic below 2^64, and runs
  across every core. A search of two billion k now takes under twelve seconds end to end
  where the previous ceiling was fifty million.
- Raised the k ceiling from 50,000,000 to 100,000,000,000 to match. The old bound was
  about a minute of PARI's work and is now a fraction of a second.
- Candidates at or above 2^64 fall back to GMP inside the same helper. The path is
  slower but correct, and the report counts how many candidates needed it. This is
  covered by a test built from a constructed factor above 2^64: q = 18446744073709551697
  at k = 24 of its order's progression.
- PARI/GP keeps the mathematics either side of the scan. It factors the exponent and
  enumerates the order divisors first, and afterwards confirms every reported q is prime
  and genuinely divides 2^d - 1. The scanner reports divisors, which is not the same
  claim, so nothing reaches a report on its word alone. Automatic mode, and any machine
  without a C compiler, still run entirely in PARI/GP.
- Added `numerisect_mfactor_cuda.cu`, an **optional** CUDA accelerator using Montgomery
  arithmetic on the device. It computes nothing the C helper cannot. Its arithmetic was
  verified on the host against plain modular exponentiation over three million random
  cases with no disagreement, and it accepts all 21 known Mersenne factors, but **the
  device path has never been executed**: no machine available to the project has a CUDA
  toolkit, only a driver. This is documented rather than glossed. Compiler detection asks
  nvcc to identify itself instead of trusting PATH, because the `nvcc-gpp15` wrapper
  exists on this workstation while the compiler it calls does not.

- Added the Zenodo archival identifiers issued for the first public source release:
  concept DOI `10.5281/zenodo.22679026` for all versions and version DOI
  `10.5281/zenodo.22679027` for the immutable `v0.7.0` snapshot. The README, website,
  installation guides, release history, FAQ, publishing guide, package metadata, and
  `CITATION.cff` now expose the appropriate identifiers. A dedicated citation page
  explains when to cite the version DOI and when to use the concept DOI.

## 0.7.0 — 2026-09-09

- Audited the public documentation after the Mersenne and local-session changes. The
  factorization mathematics now covers odd composite exponents and their order-divisor
  progressions consistently. The README, interface guide, FAQ, API reference, and both
  security guides now explain that already-open tabs can briefly receive HTTP 403 after
  a server restart because the per-process token changed, and distinguish that expected
  stale-session rejection from a native-engine failure.

- Extended both Mersenne tools to odd composite exponents. PARI/GP factors the exponent
  and searches every order-divisor progression `q = 2kd + 1`, so algebraic divisors such
  as `127 | M_1603` are no longer rejected or missed. Results identify the exponent
  factorization and exact order used for each factor.

- Added staged Mersenne factor hunts. PARI/GP now owns exact construction, divisor
  verification, multiplicity removal, and bounded rigorous cofactor classification;
  GMP-ECM supplies P−1, P+1, and ECM discovery stages. The interface distinguishes
  proven factors from the unresolved cofactor, previews large cofactors safely, saves
  every exact cofactor to the report, and claims completion only after every remaining
  part is rigorously prime.

- Added automatic Mersenne trial-factor search: the native PARI/GP loop now chooses the
  effective k range from the first factor, time budget, and safety ceiling, preserves
  factors found before timeout, and reports the largest k actually tested. Manual mode
  remains available for exhaustive finite ranges, and the interface now distinguishes
  factor discovery from complete factorization.

- Made Mersenne trial factoring a visible, dedicated Factor integers page instead of
  nesting it inside the hidden Batch queue page. Composite Lucas–Lehmer results now
  explain that the proof yields no divisor and link directly to the native progression
  factor search with the exponent prefilled.

- Added GitHub Actions compatibility coverage for Linux ARM64, Ubuntu 24.04 under
  Windows WSL, and macOS on ARM64 and Intel. Each platform checks installer detection,
  runs the native-backed test suite, performs a versioned user-local installation, and
  smoke-tests the installed CLI. The clean-host runs also drove portability fixes for
  Homebrew's keg-only GMP/OpenMP libraries, a Darwin system-header collision in the C
  SQUFOF helper, WSL checkout line endings, and a process-group RSS watchdog for
  reliable macOS memory limits.

- Audited the public documentation against the application after making
  `numerisect.com` the entry point. Added a capability index and a mathematical
  prime-structures chapter covering tuples versus Ω-based k-primes, base-dependent
  digital classes, reciprocal periods, Gaussian and Eisenstein primes, perfect numbers,
  and Mersenne divisor congruences. Corrected the API total from 208 to 212, removed stale
  special-form and manual GGNFS instructions, and surfaced the RSA, Mersenne, siever,
  workflow and distributed-network capabilities on the home page. Also corrected two
  mathematical-strength claims: six primecount modes are distinct algorithms in one
  codebase rather than six independent implementations, and the Mersenne mod-8 filter
  removes one half—not three quarters—of the `q = 2kp + 1` progression. The specialized
  Mersenne search now rejects the exceptional `p = 2` case explicitly instead of running
  a progression theorem that only applies to odd prime exponents.

- Updated the pinned GitHub Actions to `actions/checkout` 7.0.1 and
  `actions/setup-python` 7.0.0, and widened the tested compatibility ranges through
  FastAPI 0.141, Starlette 1.x and mypy 2.x. The test client now uses Starlette's
  preferred `httpx2` package instead of its deprecated `httpx` compatibility path. Also
  corrected the documentation workflow's pull-request paths so changes to
  `pyproject.toml` or the workflow itself can satisfy the required documentation-build
  check instead of leaving Dependabot updates permanently blocked.

- Made `https://numerisect.com` the public project entry point while keeping
  `https://docs.numerisect.com` as the canonical GitHub Pages host. The WHC/LiteSpeed
  apex and `www` names now use a path-preserving permanent redirect, whose configuration
  is retained in `hosting/apex/.htaccess`. Updated the site, publishing guide, package
  metadata and citation record to describe the production arrangement consistently.

- Recorded the Mersenne factors the new routine actually produced, each verified in a
  separate PARI/GP session rather than by the routine that found it, and pinned three of
  them as tests. The largest is a factor of M_999999001, a number with 301,029,695
  decimal digits, found in 10.7 seconds. Two known Mersenne prime exponents are searched
  as controls and must continue to yield nothing.

## 0.6.0 — 2026-09-07

- Added Mersenne trial factoring. Every prime factor q of M_p = 2^p − 1, for prime p,
  satisfies q = 2kp + 1 and q ≡ ±1 (mod 8), so only that thin progression is tested and
  membership is one modular exponentiation. M_p is never constructed, which is what makes
  the routine reach exponents in the millions: M_1000151 has 301,076 decimal digits and
  its factor 2000303 is found at k = 1. An exhausted k range is reported as inconclusive,
  meaning no factor of that form exists below the bound searched, and never as evidence
  that M_p is prime.
- Fixed the special-form analyser, which attempted a full integer factorization of the
  input. The Aurifeuillean check called `factor()` on Φ_n(b), and Φ_n(b) is the whole
  input whenever n is prime, so asking for a report on 2^1061 − 1 asked PARI to factor a
  320-digit number inside a metadata routine. It exhausted its budget and returned
  nothing; 10^101 − 1 behaved the same way. The split is now attempted only below a size
  cap and reported as not attempted above it, which is inconclusive rather than a claim
  that no algebraic factor exists. Both inputs now answer in well under a tenth of a
  second, with the correct SNFS polynomial and difficulty.
- Replaced the special-form search over every base up to 1,000 and every exponent below
  it, on the order of a million full-precision exponentiations, with a direct `ispower`
  question. The answer is also strictly better: there is no longer a base limit, so forms
  with a large base are found too.
- Corrected the rendering of a homogeneous form, which read `n = 2^1061 -1 1`.

- Fixed the number field sieve in YAFU, which could not run at all. YAFU has no lattice
  siever of its own and shells out to the GGNFS `gnfs-lasieve4I<index>e` programs, but
  Numerisect launched it without a siever directory, leaving it to whatever `ggnfs_dir`
  the user's own `yafu.ini` happened to contain. When that setting was wrong, YAFU printed
  `possibly bad path to siever` once per worker thread, exited non-zero having found
  nothing, and reported the input as its own factor. Numerisect rejected that result
  because the factors did not reconstruct the input, so nothing wrong was ever published,
  but on a hundred-digit input the failure read as an engine crash rather than a missing
  dependency. Every YAFU run is now given a discovered, validated siever directory.
- Added a lattice siever subsystem. It searches the configured directory, the managed
  tools directory and the conventional install locations; records a SHA-256 for each
  binary; and reports which sieve indices are available, since the largest one present
  bounds the difficulty YAFU can attempt. YAFU still chooses the index for a given
  factorization, and Numerisect does not override it.
- Every discovered siever is executed once before it is offered to YAFU. An AVX-512 build
  on a CPU without AVX-512 dies with an illegal instruction the moment it is asked to
  work, and nothing about the path or the file name reveals that in advance. Such a
  binary is now reported as unusable rather than passed on. A directory whose sievers all
  fail is skipped rather than handed over.
- Pinned the GGNFS lattice sievers in `engine_manifest.toml` so the installer builds
  lasieve4 from source at a fixed commit like every other managed engine. The separate
  lasieve5 line, which ships as prebuilt binaries with recent YAFU releases and includes
  faster AVX-512 builds, is detected and used when already present but is never
  downloaded, because the project builds from pinned source rather than fetching
  unverified binaries. The two lines share file names, so the report names the line from
  the directory it was found in and says that is what it is doing.
- `tune` no longer requires `NUMERISECT_GGNFS_DIR` to be set by hand; it uses the same
  discovery as everything else.

- Added RSA Factoring Challenge support. Numerisect could already factor an RSA number,
  because an RSA number is an ordinary semiprime and the pipeline routes it by size, but
  it could not say which challenge number you were holding, whether the published
  factorization is genuine, or what an unfactored one would cost. All 54 challenge
  numbers, RSA-100 through RSA-2048, now ship as catalogue data that is never trusted on
  its own authority: PARI/GP proves each value composite, recomputes its decimal and bit
  length, multiplies the published factors back together and tests each for primality.
  The test suite re-runs those checks over the whole file, so a mistyped digit fails the
  build rather than reaching a user. An effort estimate from the conjectured number field
  sieve complexity, anchored on the measured 2,700 core-years of RSA-250 and scaled to the
  local core count, is reported as an order of magnitude and labelled a heuristic. An open
  challenge number is reported as unfactored, never as unfactorable.

- Gave every documented endpoint a purpose. The API reference listed 208 routes and left
  151 of them with a blank Purpose column, so the table named routes without saying what
  any of them did. Each one now carries a description, and for the 134 routes with a
  matching page in the application the text is taken from that page's own heading and
  subtitle, so the reference and the interface cannot drift apart in wording.
- Fixed a broken row in the API reference. The `l-zeros` entry contained an unescaped
  `|L|`, which split the row into extra columns and rendered as a malformed table.
- Added contract tests asserting that no documented endpoint has a blank purpose, that no
  table row contains an unescaped pipe, and that the reference uses the same names the
  interface shows.

- Corrected the three places in the documentation that still named a renamed tool page:
  the reciprocals guide called the full-reptend page by its old heading, and two rows of
  the zeta routine table used operation names the interface no longer shows.

- Renamed 33 tool headings so the navigation shows what each tool is called, not only
  what it does. The sidebar button and the tool picker both display a tool's heading, and
  headings such as "Solve x² − dy² = 1", "Analyze witness bases" and "Apply Korselt's
  criterion" never mentioned Pell, Miller–Rabin or Carmichael, so scanning the list for a
  known name found nothing. The names were present only in the small eyebrow text inside
  each card, visible after the tool was already open. Affected, among others: Pell,
  continued fractions, Miller–Rabin, Goldbach, Carmichael, Hardy–Littlewood, Bateman–Horn,
  Maier, Pocklington, Proth, Sierpiński and Riesel, Chebotarev, Eisenstein, Dirichlet,
  Dedekind, the Chinese remainder theorem and SQUFOF.
- Gave the two prime-race tools distinct names. The animated and the analytic tool both
  read "Race the reduced residue classes", so they were indistinguishable in the sidebar
  and in the picker.
- Added contract tests asserting that every navigation label is unique and that the
  recognised name of each subject appears in some label.

- Stopped labelling a rational's continued-fraction expansion "inconclusive" in the
  exported report. A rational expansion terminates, so it has no period; calling that
  inconclusive confuses "not applicable" with "not settled". The export now says which
  it is, and reserves "inconclusive" for a quadratic irrational whose period was not
  closed within the quotient cap.

- Removed the length ceiling from the Pell solver and the continued-fraction expander.
  Both quantities grow without bound — the fundamental Pell solution for `d = 1000099`
  has 1,128 decimal digits and its fourth solution has 4,513, and convergent denominators
  grow at least as fast as the Fibonacci numbers — and the Pell tool used to stop listing
  at the first solution wider than the digit limit, which made a complete answer look like
  an exhausted search. Every requested solution and convergent is now reported. PARI/GP
  writes each one at full length to its own export file, named in the response as
  `export_file`, and the JSON response carries a preview in which a long value is rendered
  as its exact first twelve digits, its exact last twelve digits and its exact digit count.
  A new `abbreviated` flag says whether any value was shortened for display; `truncated`
  now means only what it says, that something was left out, and is no longer set by these
  tools. Tests substitute every exported Pell pair back into `x² − dy² = 1` and every
  exported convergent of `√2` into `pₙ² − 2qₙ² = ±1`, and check the abbreviation against
  the exported value at both ends.
- Filled in the missing endpoint descriptions for the quadratic-forms section of the API
  reference, which shipped with an empty Purpose column for all eight routes.

- Pointed the declared homepage at the documentation site. `pyproject.toml` and
  `CITATION.cff` both advertised `https://numerisect.com`, which serves a 404 from an
  unrelated document root, so the package metadata and the citation record sent readers
  to a dead page. The apex is not part of the project's hosting.

- Fixed every Material icon on the documentation site, which rendered as literal text
  such as `:octicons-arrow-right-24: Installation` on all 35 occurrences across 15 pages.
  Material's icon shortcodes are emoji shortcodes underneath, and `pymdownx.emoji` was
  never configured, so the theme silently passed them through. The strict build did not
  catch it because unrecognised shortcodes are valid Markdown text.
- Added a source-code section to the documentation home page linking the repository,
  releases, issue tracker, contributing guide and citation file, so a reader arriving at
  the site can find the source and report a wrong result without hunting for it.

- Published a documentation site at [docs.numerisect.com](https://docs.numerisect.com),
  built with MkDocs Material from the existing `docs/` tree so there is one source of
  truth rather than a parallel copy. It adds a mathematical background section covering
  primality, factorization, prime distribution, modular arithmetic, quadratic forms and
  the zeta function, each naming the library routine that performs every computation and
  citing sources for every stated bound. Also adds concept pages on result strength and
  the engines, a getting-started path, an API reference generated from the running
  application, a glossary, a bibliography and an FAQ. The site carries no analytics, and
  a test asserts that it stays that way.
- Corrected the prime-counting comparison, which counted `primecount --double-check` as
  an independent source. It reruns the default algorithm with different alpha tuning, so
  it is a self-consistency check rather than a seventh implementation, and it is now
  reported separately so the independence claim is not inflated.
- Corrected `docs/FACTORIZATION.md`, which still said SQUFOF was "not offered" and listed
  resumable ECM campaigns, expert scheduling, symbolic SNFS and Aurifeuillean analysis and
  distributed workers as deferred. All of those ship.
- Documented that PARI's `primecertexport` cannot render an N−1 certificate, and added a
  test asserting no export path passes it one.
- Granted the secret-scan workflow `pull-requests: read`. Gitleaks enumerates a pull
  request's commits, so without it the scan failed with "Resource not accessible by
  integration" on every pull request, including Dependabot's.

- Recorded the work that goes beyond the 150-item proposal in
  `docs/ROADMAP_STATUS.md`, and refreshed the page, group and test counts across the
  README and the documentation pages so they match the application.
- Added a prime-counting algorithm comparison. `POST /api/counting/algorithm-comparison`
  runs primecount's six algorithms, its alternative-tuning double-check, and PARI's
  `primepi` as independent sources and reports whether they agree. Added Legendre's
  phi(x,a) with the identity check, the two nth-prime inverse approximations, the integer
  predicates `isprimepower`, `ispowerful`, `istotient`, `isfundamental` and `ispolygonal`,
  Lenstra's divisors-in-a-residue-class with its hypotheses enforced, and PARI's
  `factorint` strategy flags as a factoring-method comparison.
- Added a binary quadratic forms and continued fractions workbench: reduction,
  composition and exponentiation of forms, prime forms, class groups and reduced-form
  enumeration, representation of integers, the exact continued-fraction expansion of
  quadratic irrationals with period detection, and Pell equations. Documents the concrete
  link to SQUFOF: discriminant 7268 gives a 28-form principal cycle containing the
  ambiguous form Qfb(23, 46, -56), and 23 divides 1817.
- Added independent cross-engine verification. `POST /api/verify/prime-count` computes
  pi(x) with primecount's six algorithms (Legendre, Meissel, Lehmer, Lagarias-Miller-
  Odlyzko, Deleglise-Rivat, Gourdon), primesieve's sieve and PARI's `primepi`, then
  reports whether they agree. `POST /api/verify/primality` does the same with PARI's
  proof, PARI's Baillie-PSW test and GMP's independent implementation. On disagreement
  Numerisect reports every value and refuses to choose, because a majority of
  implementations sharing a bug is exactly what a vote would hide.
- Added an engine self-test. `POST /api/verify/self-test` asks each installed engine
  questions whose answers are published constants, so a miscompiled or mismatched build
  shows up before its output is trusted. Every expected value carries a citation.
- Added `numerisect-bigsieve`, a GMP and OpenMP segmented sieve for intervals of any
  magnitude. primesieve refuses inputs at or above 2^64 and PARI's `forprime` is
  single-threaded there; over a 10^6-wide window near 10^30 this helper takes 40 ms on
  24 threads against PARI's 916 ms on one, and both find 14496 primes. Results at or
  above 2^64 are labelled probable primes from Baillie-PSW, never proofs.

- Added distributed CADO-NFS sieving (roadmap item 18). Numerisect validates CADO's own
  server and client parameters and adds no networking of its own. Configurations CADO
  would accept but that are unsafe are refused: an absent whitelist, `0.0.0.0/0`, broad
  public ranges, binding a public interface, and remote workers without a script path.
  A two-step approval reports the exposure before anything starts, and a run that leaves
  the machine additionally requires `NUMERISECT_ALLOW_NETWORK=1`. `docs/DISTRIBUTED.md`
  states the trust model verified from CADO's own source: clients do not authenticate to
  its work-unit server, and an IP whitelist is the only access control.
- Fixed a bug that made every CADO-NFS job hang. CADO defaults `slaves.hostnames` to
  `localhost` only when using its own default parameter file; Numerisect always passes
  `-p`, so CADO started a bare work-unit server, queued work units and polled for them
  forever with no client running. Both the plain and distributed paths now set it, and
  the integer is kept contiguous with its `key=value` assignments as CADO requires.
  Found by running a distributed factorization by hand.

## 0.5.0 — 2026-09-07

- Stated the governing development policy: Numerisect is a user interface over existing
  number-theory libraries. A computation uses a library routine first, an optimized C or
  C++ program with GMP/FLINT only when no library provides one, and never Python or
  JavaScript. Added `tests/test_native_computation_policy.py` so the policy is enforced
  by the suite rather than by review, and documented it in `CONTRIBUTING.md`.
- Added `numerisect-squfof`, an optimized C implementation of Shanks' square forms
  factorization using GMP. No installed library provides SQUFOF: the YAFU build has no
  such function, PARI/GP exposes none, Msieve implements only QS/NFS, and GMP-ECM only
  ECM/P-1/P+1. Verified against 150 random semiprimes with no incorrect answers; inputs
  at or above 2^62 are rejected explicitly and an exhausted search is inconclusive.
- Added the expert factorization laboratory: SQUFOF, special-form and SNFS suitability
  analysis, algebraic and Aurifeuillean factors verified by division, a strategy adviser
  with an expected-factor-size estimate, an engine decision path, bounded educational
  algorithm traces, and batch primality certificates.
- Added a resumable GMP-ECM campaign manager using the engine's own save and resume
  residue files, with PARI/GP reconciling the factors GMP-ECM peels off across curves
  into a consistent decomposition.
- Added the primality laboratory: a comparison lab across Fermat, Solovay-Strassen,
  Miller-Rabin, Lucas, Frobenius, BPSW, APR-CL and ECPP; deterministic Miller-Rabin
  witness sets; Pocklington and Pratt certificates with independent verification; the
  probable-prime taxonomy; the Carmichael analyzer; Sierpinski and Riesel covering sets;
  bi-twin chains; and provable constrained-prime generation.
- Added the algebra laboratory: reciprocity traces, congruences over composite moduli,
  four selectable discrete-logarithm algorithms, finite fields, divisor lattices,
  smoothness and roughness, record-number families, a proven weird-number check,
  sociable cycles, Cornacchia with a step trace, quadratic rings, general number fields
  with prime-ideal decomposition, and Chebotarev density experiments.
- Added the visualization and education workbench: Ulam, Sacks and polar spirals, the
  Eisenstein hexagonal lattice, arbitrary-base modular wheels, residue heatmaps, gap and
  record-gap timelines, the prime-race animation, step-traced Eratosthenes, segmented
  Eratosthenes, Sundaram and Atkin sieves, and a cited complexity dashboard.
- Added application infrastructure: complete command-line parity through an in-process
  ASGI caller, CSV/JSON/JSON Lines/Markdown/LaTeX/PARI exports, file-based batch import
  with GP-side expansion, saved workspaces, searchable job and report history,
  revision-keyed result caching, job priorities and reordering, per-job CPU, memory and
  wall-clock limits, pause and resume, opt-in desktop notifications, declarative engine
  adapters, a performance-history dashboard, API clients for five languages, and a
  standard-library client for notebooks.
- Added permissioned catalogue lookups (OEIS and local known-factor tables) that are off
  by default and require both `NUMERISECT_ALLOW_NETWORK=1` and a per-request
  confirmation. Only the query is transmitted, and every claimed factor is verified by
  PARI/GP before being reported as a divisor.
- Fixed the wheel smoke test, which asserted six pinned engines after primesieve and
  primecount brought the manifest to eight.
- Added the analytic prime-distribution laboratory: approximation-error and
  prime-number-theorem convergence charts, cited nth-prime bounds, prime races and
  Chebyshev bias, progressions with expected-versus-observed counts, Hardy-Littlewood
  singular series with a rigorous tail bound, constellation predictions,
  Bateman-Horn estimates, maximal-gap search with merit and Cramer, Granville and
  Firoozbakht comparisons verified against the published table, Maier-matrix
  experiments, and a two-parameter density surface.
- Extended the zeta workspace with explicit-formula prime counting from certified
  zeros, Chebyshev psi reconstruction, Riemann-Siegel remainder analysis, Euler-product
  comparison, zero-spacing histograms, pair correlation against the GUE prediction,
  Gram blocks and Gram's-law exceptions, the Backlund S(T) remainder, Dirichlet
  characters and L-functions with independent Hurwitz cross-checks, L-function zeros
  for GRH experiments, and Dedekind zeta functions through PARI.
- Corrected the Prime Tools group count in the README and prime-manipulation guide, the
  README route list, and the stale test count in the prime-manipulation guide.
- Added engine tuning through YAFU's own `tune`: `POST /api/factor-lab/tune` measures
  this machine's SIQS/NFS crossover and reports a suggested `NUMERISECT_CADO_THRESHOLD`.
  Numerisect never rewrites its own configuration. Needs `NUMERISECT_GGNFS_DIR` to point
  at the GGNFS lattice sievers.
- Recorded two declined items in `docs/ROADMAP_STATUS.md` rather than leaving them as
  open gaps: synthetic engine benchmarking, superseded by the performance history built
  from real jobs, and the side-by-side engine timing view, whose correctness half is
  already covered by cross-verification.
- Bumped the interface asset tag to `20260907-libraries-first`.

## 0.4.0 — 2026-09-06

- Added strict loopback Host validation, foreign-origin rejection, Fetch
  Metadata checks, and a cryptographically random per-process API session.
- Removed automatic native-engine installation from application startup and
  added explicit browser confirmation for pinned source builds.
- Added an immutable native-engine manifest, deliberate pin-update command,
  sanitized API status/job responses, and safer source-install confirmation.
- Made static assets, GP programs, the engine manifest, and the native zeta
  source wheel resources independent of the original checkout.
- Added public project metadata, third-party notices, community/security files,
  and SHA-pinned GitHub Actions quality checks.
- Added factor-tree visualization, partial-cofactor continuation, validated
  batch queues, independent YAFU/Msieve verification, and bounded PARI trial
  division in place of YAFU's crashing trial command.
- Added JSON factorization manifests containing factor provenance, full command
  history, parameters, immutable engine revisions, and executable SHA-256 sums.
- Added pinned primesieve 12.15 and primecount 8.5 integrations for parallel
  interval sieving, exact prime counting, indexed primes, and asymptotic
  comparisons.
- Added independent PARI certificate verification and a native primality
  comparison laboratory.
- Added special-family and NTT prime generation, Cunningham chains,
  Lucas–Lehmer and Pépin tests, perfect-power and factor-strategy analysis.
- Added generalized CRT, character symbols, Tonelli–Shanks traces, modular kth
  roots, Hensel lifting, discrete logs, unit groups, order/power-residue
  distributions, p-adic valuation, and polynomial/cyclotomic factorization.
- Added extended arithmetic and divisor classifications, aliquot sequences,
  summatory functions, Eisenstein primes, and quadratic prime-ideal
  decomposition.
- Extended the compiled FLINT/Arb helper with Hardy Z, xi, eta, Stieltjes,
  Gram-point, and rigorous functional-equation operations.
- Expanded the workstation to 65 individually routed Prime Tools pages and 10
  Zeta pages, plus a sanitized local diagnostics workspace.
- Added a cache-busted Numerisect `N` favicon to prevent stale generic branding.
- Added the `numerisect` CLI and bumped the pre-release version to 0.4.0.

## 0.3.0 — 2026-09-05

- Added a user-space, versioned `install.sh` for Linux, Windows WSL, and macOS.
- Added system prerequisite checks and distro-aware installation for the native
  build toolchain and GMP, MPFR, and FLINT development libraries.
- Added release directories, a shared state/output area, a `current` pointer,
  and a stable user launcher for upgrades.
- Added batch primality checks, arithmetic-progression prime searches, and
  prime-modulus inverses, powers, orders, square roots, and primitive roots.
- Added nth-prime navigation strictly before or after an arbitrary-size integer.
- Added dedicated Prime Tools routes, searchable navigation, mobile selection,
  local result placement, and stale-asset protection.
- Added native FLINT/Arb Riemann-zeta evaluation, zero isolation, Turing counts,
  and exploratory line/heatmap sampling.
- Expanded native-engine, API, report, UI, and installation regression coverage.

## 0.2.0

- Initial Numerisect development baseline with multi-engine
  factorization, PARI/GP prime tools, and the source-based application shell.
