# Changelog

Numerisect is an experimental, source-distributed pre-release. No official
binary packages are published.

## Unreleased

- Added the references and glossary entries for the 0.12.0 mathematics: Coppersmith
  (1997) and May's survey of what partial knowledge of a factor buys; Cantor and
  Zassenhaus (1981) and Shoup's chapter on the three stages in the order they must run.
  Glossary entries for Coppersmith's method, the proven validity window, and the
  square-free, distinct-degree and equal-degree stages.
- Removed the two regexes left dead by the `pari_real` refactor, in `counting_lab.py` and
  `distribution_lab.py`. CodeQL flagged both as unused globals, which they were: the
  shared parser replaced them and the definitions stayed behind.
- Recorded the Zenodo version DOI `10.5281/zenodo.23172229` for the `v0.12.0`
  source release across `CITATION.cff`, the README, the installation guides, the
  capability index, the citation page, the FAQ, the publishing guide and the release
  history. Earlier version DOIs stay listed on the citation page.

## 0.12.0 — 2026-10-05

- Added **staged polynomial factorization over F_p** (`POST /api/algebra/factor-stages`),
  using three PARI routines the application never called: `factormodSQF`, `factormodDDF`
  and `factorcantor`. `factormod` answers in one step; the algorithm behind it has three,
  and each asks a different question — square-free decomposition, distinct-degree
  factorization of each square-free part, then equal-degree splitting by
  Cantor-Zassenhaus. The order is enforced in the engine, because the distinct-degree step
  is documented for a square-free argument and is undefined on a polynomial with a
  repeated factor. The engine verifies that the irreducible factors, raised to the
  multiplicities stage 1 found, multiply back to the input; a failed reconstruction
  reports nothing rather than a partial answer. One new Prime Tools page, bringing the
  catalogue to 139.
- Recorded why YAFU's `-np` poly-search switch is **not** exposed: YAFU's own
  documentation says its "multi-threaded polynomial selection is handled via msieve
  library function calls", and its log confirms it. The switch is a second front end to
  the selection already reachable through the `msieve_poly` strategy, so it would add
  neither a capability nor an independent check.

- Added three independent cross-checks, from an audit of what YAFU and primesieve expose
  against what the application called:
  - **YAFU's APR-CL** joins the primality cross-check as a *second proof engine*. PARI's
    `isprime` was the only proof; everything else there is probabilistic. Two independent
    proofs agreeing is a stronger statement, and the response now names the proof engines
    that answered. YAFU documents APR-CL as a proof below 6021 digits and a BPSW test
    above it, so the claim is only made inside that range.
  - **`POST /api/verify/mersenne`** decides `2^p - 1` with PARI/GP's and YAFU's unrelated
    Lucas-Lehmer implementations. The test is deterministic for a prime exponent, so each
    verdict is a proof. A composite exponent is refused rather than answered: `M_p` is
    composite then for an algebraic reason, not a Lucas-Lehmer one, and YAFU returns that
    verdict happily — which would leave one engine's answer looking cross-checked.
  - **`POST /api/verify/nth-prime`** computes it exactly with primecount and primesieve,
    two separate codebases. The pi(x) comparison cannot claim that for its first six
    sources, which are distinct algorithms inside one library. The approximation page also
    gained primesieve's independent `R(x)` beside primecount's.
- Fixed a defect class this uncovered: **four validators rejected PARI/GP's own number
  format.** PARI prints an exponent with a space before it (`1.0000 E-5`,
  `-5.63e-5` as `-5.63 e-5`), and each of `number_theory.py` (twice), `counting_lab.py`
  and `distribution_lab.py` matched `1e-5` instead. The approximation comparison therefore
  failed outright at x = 10^11 although the page advertises 10^31, and the same trap sat
  under every other page that can reach exponential notation. A shared `pari_real` parser
  in `primes.py` now validates and normalises these values in one place.
- Reading YAFU needs care, and the code says so: YAFU prints primality verdicts as English
  prose and returns the *input* in `ans`, so `aprcl(1000003)` prints "Input is prime." and
  sets `ans = 1000003`. Reading `ans` would make every verdict truthy. `llt` is the one
  function whose verdict really is the returned value.
- Two new Prime Tools pages, bringing the catalogue to 138.

- Added **Coppersmith's method** (`POST /api/factor-lab/coppersmith`, PARI/GP
  `zncoppersmith`), which recovers a divisor of `N` from partial knowledge of it. Unlike
  every other method here, its cost depends on how much of the factor is unknown rather
  than on the size of `N`: measured, a 155-digit modulus splits with 100 bits of a
  256-bit factor unknown, and a 309-digit (1024-bit) modulus splits in milliseconds with
  200 bits of its 512-bit factor unknown. Each root is reported with gcd(N, P(x)), its
  cofactor and PARI's primality verdict on both.
  - The proven validity window is computed by the engine and reported. A request outside
    it is refused **before** the engine is called, because PARI raises "bound too large"
    rather than returning nothing, and a search that never ran must not look like one
    that found nothing.
  - A wrong known part yields no proper divisor and says so: within the window that is
    evidence about the polynomial and bound supplied, not about the modulus.
  - The divisor bound may be left at 0, in which case PARI/GP derives it from the known
    part, so no bit length is computed outside an engine.

- Recorded the Zenodo version DOI `10.5281/zenodo.23168705` for the `v0.11.0`
  source release across `CITATION.cff`, the README, the installation guides, the
  capability index, the citation page, the FAQ, the publishing guide and the release
  history. Earlier version DOIs stay listed on the citation page.

## 0.11.0 — 2026-10-05

- Closed roadmap item 10, the last capability gap on the ledger. `cross_verify` already
  required YAFU and Msieve to agree on the factor multiset and rejected anything else;
  the comparison itself was then thrown away. The job now records each engine's factors
  with the primality label **that engine** assigned, the cofactor it left and its elapsed
  time, shown under the factor tree, in the saved report and as `verification` in the job
  API. Two engines agreeing on the factors while disagreeing on proven versus probable —
  `P` against `prp` — raises a warning naming the factor and both labels, which is a
  difference in what each engine undertook to establish rather than a contradiction. The
  times are single measurements of two runs on one machine and are labelled as such.
- Documented **what 1.0 would require**, since the remaining distance is not more
  mathematics: a stable API, the closeable presentation gaps built or declined in writing,
  the permanent bounded-search limits stated as limits, and the published artifact
  exercised on each supported platform. The twelve remaining ledger gaps are separated
  into those that can be closed and those that are the honest shape of the question.

- Recorded the Zenodo version DOI `10.5281/zenodo.23163322` for the `v0.10.0`
  source release across `CITATION.cff`, the README, the installation guides, the
  capability index, the citation page, the FAQ, the publishing guide and the release
  history. Earlier version DOIs stay listed on the citation page.

## 0.10.0 — 2026-10-05

- Added `scripts/build_factor_catalogue.py`, which fills the local known-factor catalogue
  by factoring `b^n ± 1` here rather than importing a published table. The catalogue
  feature always worked and always searched zero files, because nothing is bundled; the
  obvious fix would have been to vendor the Cunningham tables, whose licence and
  provenance would then have to be argued. PARI/GP factors each number, proves every
  factor prime and verifies the product against the input, and each entry records its
  expression and the engine version that produced it, so a locally computed entry is
  distinguishable from an imported one. A number the per-number budget cannot finish is
  listed under `skipped` and absent from the entries rather than stored half-factored.
  `--min-exponent` allows a catalogue to be extended in slices.

- Exposed NFS **polynomial selection**, the audit's last open item. Selection is the first
  phase of the number field sieve and the one whose result is reused, and neither engine's
  controls were reachable: only the choice of CADO `params.cNN` was.
  - A new `msieve_poly` strategy runs Msieve's selection as its own job, whole or one
    stage at a time (`-np`, `-np1`, `-nps`, `-npr`), and reports the polynomial with the
    quality metrics Msieve prints, written in its own field order so it can be pasted into
    a factor-base file. A single stage reports how many candidates it saved and claims no
    polynomial; a full run that ends without one is an error, not an empty success.
  - CADO's `tasks.polyselect.*` keys (`degree`, `P`, `admin`, `admax`, `incr`, `nrkeep`,
    `adrange`, `nq`, `sopteffort`, `ropteffort`) now reach `cado` and `hybrid` runs, with
    ranges taken from the installed `params.cNN` files.
  - Each set is validated against the engine that will receive it, when the job is created
    rather than when a worker starts, so an Msieve-only parameter cannot be queued for a
    CADO job or the reverse. Stored options are validated again on a resume.
- Fixed a defect this work uncovered: **a successful `tune` job was always marked failed.**
  Its result is a measured crossover, which cannot multiply back to the input, but the
  completeness gate was applied anyway, so every run ended as "failed" with "The returned
  factors do not multiply to the input." Backends whose result is a report rather than a
  factorization are now named in `JobManager.REPORTING_BACKENDS` and judged on whether the
  engine delivered its report. The gate stays strict everywhere it applies, which a test
  pins.
- A report-only job's saved file now says `Report for N` instead of `N = <the report>`,
  which was a false statement about the input, and prints the polynomial when there is one.

- Recorded why the prime classifier keeps citing published searches for Wilson and
  Wolstenholme instead of calling the new scanner, having measured both: the literature
  settles Wilson below 2*10^13 and Wolstenholme below 10^9, while the O(p) cost per
  candidate limits computation to 2^32 and 2,642,246 — about ten seconds for one
  candidate near 10^9. Rerouting the classifier would have shrunk its definite range by
  four orders of magnitude. The catalogue rows and the Fermat-quotient page now state
  this, so the question does not get reopened from the wrong premise.
- The summatory-functions page refused x above 10,000,000 without saying where to go.
  Its cap comes from the Liouville sum, which factors every integer up to x; M(x) alone
  reaches 10^13 on the Mertens page. The refusal and the result note now say so.

- Guard tests for the two mistakes the 0.9.0 work made. Every `numerisect/native/*.c`
  must have a `build_<slug>_tool` in `native_tools.py`, must appear in the CodeQL manual
  build, and every library the builders ask pkg-config for must have its development
  package in `quality.yml` and `codeql.yml`. The CodeQL omission is the one worth a test:
  it fails silently, so a helper left out is simply never analysed and no check turns red.
  Both guards were verified by reintroducing yesterday's mistakes and watching them fail.
- Documented the policy where contributors can see it. `CLAUDE.md` is gitignored in this
  repository, so the strengthened native-computation policy was invisible outside this
  machine. `CONTRIBUTING.md` and `docs/about/contributing.md` now carry the step that was
  missing from both — reach a capability through an engine's own flags or a short
  composition before writing C — and a four-point checklist for adding a compiled helper.
- `POST /api/primes/gaps` now reports each gap's **merit**, the gap divided by the natural
  logarithm of its lower prime, computed by PARI/GP. Merit existed only in the maximal-gap
  and gap-timeline tools, although it is what makes gaps at different magnitudes
  comparable, and the main gap page is where it was most missed.

- Recorded the Zenodo version DOI `10.5281/zenodo.23148620` for the `v0.9.0` source
  release across `CITATION.cff`, the README, the installation guides, the capability
  index, the citation page, the FAQ, the publishing guide and the release history. The
  0.8.1, 0.8.0 and 0.7.0 DOIs stay listed on the citation page.

## 0.9.0 — 2026-10-04

- Hardened and tidied what CodeQL flagged in the new code once it was scanned. Every
  numeric command-line argument for the new helpers is now rendered by one `_argument`
  helper that applies `int()` at the point of assembly, so an argv entry is an integer by
  construction rather than by inspection; the helpers were already launched as argument
  arrays with no shell. Renamed a factor-base prime in `numerisect_classic.c` that shadowed
  the continued fraction's `P_i`; the file is clean under `-Wshadow`.

- Added `libprimesieve-dev` to the CI dependency lists and the four new helpers to the
  CodeQL C build, so the new C sources are both buildable and analysed there. The
  workflows installed the `primesieve` CLI but not its headers, which the Brun and
  Fermat-quotient helpers link against.

- Added `numerisect_classic.c` with three classical factoring methods that no installed
  engine exposes: **CFRAC** (Morrison-Brillhart, 1975), **Lehman's** deterministic method
  (1974) and **Hart's** one-line factorization (2012). YAFU and Msieve cover QS and NFS,
  GMP-ECM covers ECM and P-1/P+1, PARI/GP exposes rho and its own `factorint` strategies,
  and SQUFOF already had a helper; none of them offers these. `POST
  /api/factor-lab/classic` and a Factor Lab page serve all three.
  - None is offered as the fast path, because none is: the engines beat them on almost any
    input. Each answers something the engines cannot. CFRAC is the first subexponential
    method and needs no sieving interval, taking its relations from the continued fraction
    of sqrt(N); its dependency is a congruence of squares that can be checked by hand. It
    factors a 26-digit semiprime in 0.05 s and a 32-digit one in 0.27 s. Lehman is
    deterministic with a proven O(N^(1/3)) bound, so exhausting it proves something.
    Hart is strongest exactly where rho and ECM are weakest, splitting 1000003 * 1000033
    on its first iteration.
  - Every divisor is verified by division inside the helper before it is printed, and
    primality of each part is decided afterwards by PARI/GP `isprime`. Exhausting a bound
    is reported as `exhausted` and is explicitly not evidence of primality; a wall-clock
    expiry is `timeout`; a prime input is reported as having no split to find rather than
    searched.
- Corrected the documentation and module comments that stated CFRAC was deliberately not
  implemented. That was true until this release and is now false; the claim appeared in
  `forms_lab.py` twice, `docs/FACTOR_LAB.md`, `docs/FORMS_LAB.md` and
  `docs/mathematics/quadratic-forms.md`. SIQS still supersedes CFRAC at every size, which
  the corrected text says instead.

- Added `numerisect_mertens.c` for the Mertens function `M(x) = sum_{n<=x} mu(n)`. PARI/GP
  has `moebius` but no summatory routine and FLINT has no `M(x)`, so the application had
  only a GP loop inside the combined summatory page: linear, interpreted, and unusable past
  about 10^7. The helper carries **two independent algorithms** — the hyperbola identity
  `sum_{n<=x} M(x/n) = 1` over a segmented Mobius sieve, and the sieve alone — which share
  no code path beyond the sieve, so the optional cross-check genuinely confirms a value. If
  they ever disagree, no value is reported at all.
  - Validated against PARI/GP for 10^1 through 10^6 and against published values at 10^7
    (1037), 10^8 (1928), 10^9 (-222) and 10^12 (62366).
  - Measured: `M(10^7)` took 4.27 s in GP against 0.002 s here; `M(10^9)` 0.041 s against
    21.3 s for the sieve; `M(10^12)` 4.4 s and `M(10^13)` 26.1 s.
  - A sign mode walks every partial sum and reports the sign changes, extrema and the
    largest `|M(n)|/sqrt(n)` for n >= 2 — the quantity the Mertens conjecture was about.
    Every statistic matches PARI/GP over 10^6. The trivial n = 1, where the ratio is 1,
    is excluded so it cannot mask later records.
- Added `numerisect_brun.c` for Brun-type reciprocal sums over twin, cousin, sexy, triplet
  and quadruplet primes, with primesieve supplying the tuples and MPFR the sum. Nothing
  installed computes these: primesieve counts k-tuplets but sums nothing. The repository
  previously mentioned the twin-prime constant only as documentation prose.
  - All five patterns match PARI/GP exactly on both the sum and the tuple count, and the
    counts reproduce the published pi_2(10^6) = 8169 and pi_2(10^8) = 440312.
  - Members need not be consecutive primes, so each offset is sought arithmetically: (3, 7)
    is a cousin pair with 5 between them and would be missed by taking the next prime.
    Both admissible triplet shapes are counted, once each.
  - The result is the exact **truncated** sum and is never called the constant. These sums
    converge like 1/log x — the twin sum is 1.7747 at 10^9 against a published 1.9021 — so
    no reachable bound fixes the constant's digits. Published estimates come from
    extrapolation models the program deliberately does not apply; the estimate is displayed
    beside the computed sum, never blended into it.
- Two new Prime Tools pages, bringing the catalogue to 136, and two routes:
  `POST /api/primes/mertens` and `POST /api/primes/brun`.
- Extended the policy test's C-helper justification check to recognise MPFR and primesieve
  as named libraries, and registered `analytic_sums.py` in its module list.

- Added `numerisect_fermatq.c`, a compiled scanner for four congruences that strengthen a
  theorem true of every prime: **Wieferich** in any base (`a^(p-1) = 1 mod p^2`),
  **Wall-Sun-Sun** (`p^2 | F_{p-(5|p)}`), **Wilson** (`(p-1)! = -1 mod p^2`) and
  **Wolstenholme** (`H_{p-1} = 0 mod p^3`). No installed engine searches for any of them.
  Before this the application answered Wilson and Wolstenholme from a table of three and
  two published values, tested Wieferich for one candidate in base 2 only, and had no
  Wall-Sun-Sun test at all. One route, `POST /api/primes/fermat-quotients`, and one Prime
  Tools page, bringing the catalogue to 134.
  - Validated against the literature: base 2 returns 1093 and 3511, base 3 returns 11 and
    1006003, base 5 returns 2, 20771 and 40487, Wilson returns 5, 13 and 563, and
    Wolstenholme returns 16843. The last is also what validates the criterion
    implemented, since the harmonic form is used rather than the binomial one.
  - Above 2^32 the squared modulus leaves 64 bits and GMP takes over; all 17 Fermat
    quotients in a window there match PARI/GP exactly.
  - Measured against equivalent GP loops: Wieferich to 10^7, 0.38 s in GP against 0.15 s
    on one core and 0.04 s on 24; Wilson to 20,000, 3.72 s against 0.02 s; Wolstenholme to
    20,000, 6.46 s against 0.17 s. Wieferich to 10^9 takes 1.3 s.
  - Wilson and Wolstenholme cost O(p) per candidate, so their moduli have hard ceilings
    (2^32 and 2,642,246). Candidates beyond them are counted as **refused**, never
    skipped, and an expired budget reports `timeout` with the largest prime fully
    searched. Neither can be mistaken for an exhausted range.
- Registered `counting_lab.py` and `distribution_lab.py` in the native-computation
  policy's module list alongside the new `fermat_quotients.py`. Both predate the policy
  test and were never listed, so none of its dispatch or engine-naming checks applied to
  them; both pass.

- Wired the YAFU expert bounds into the job path. `validate_yafu_parameters` and its
  15-flag table were implemented and unit-tested, but nothing ever passed them to YAFU:
  `_run_yafu` sent only `-threads`, `-terse`, `-ggnfs_dir` and `-pretest`. A job now
  carries `yafu_options`, validated when the job is created rather than when the worker
  starts, stored with the job, and re-validated on a resume. The factor page gained a
  **YAFU expert bounds** panel driven by `data-yafu` attributes, so the markup owns the
  field list and a contract test holds it equal to the server's table.
- Offered every API backend in the browser. `ecm_campaign`, `yafu_snfs` and
  `yafu_fermat` were accepted by `POST /api/jobs` and missing from the strategy list, so
  the richest ECM surface in the application had no form. A test now fails if an
  accepted backend has neither an option nor its own lab form.
- Added GMP-ECM's stage-2 and special-form controls to the campaign backend:
  `ecm_maxmem` (`-maxmem`), `ecm_stage2_steps` (`-k`), `ecm_base2` (`-base2`) and
  `ecm_group_order` (`-go`), with a **GMP-ECM campaign parameters** panel covering all
  nine fields. An empty field is omitted rather than sent as zero, because the engine
  owns every default it is not given.
- Taught the staged Mersenne hunt two things it already knew but never said. Every
  cofactor of `M_p` divides `2^p - 1`, so `-base2 -p` now replaces a general division
  with a reduction modulo that form. Every prime factor `q` satisfies `q = 2kp + 1`, so
  `2p` divides `q - 1`, which is precisely the group order P-1 works in: `-go 2*p` is
  passed to the P-1 stage. Measured on the known factor `2000303` of `M_1000151`, whose
  `q - 1` is `2 * 1000151`: plain P-1 at B1=1000 finds nothing, and with the group order
  preloaded the factor appears in stage 1 at the same bound. P+1 is given no group order
  (`q + 1` need not be divisible by `2p`) and ECM is refused one outright, since no
  curve order is known in advance.

- Recorded the Zenodo version DOI `10.5281/zenodo.22883791` for the `v0.8.1` source
  release. `CITATION.cff`, the README, the installation guides, the capability index, the
  citation page, the FAQ and the publishing guide now point at the 0.8.1 snapshot; the
  0.8.0 and 0.7.0 DOIs stay listed on the citation page.

## 0.8.1 — 2026-09-21

- Recorded the Zenodo version DOI `10.5281/zenodo.22882181` for the `v0.8.0` source
  release. `CITATION.cff`, the README, the installation guides, the citation page, the FAQ
  and the publishing guide now point at the 0.8.0 snapshot; the 0.7.0 DOI stays listed
  on the citation page.
- Removed `numerisect/gpu.py`, the runtime-compiled (NVRTC) route to the Mersenne kernel.
  Nothing in the application called it: the scan has run on the `nvcc`-built
  `numerisect-mfactor-cuda` since the device-side sieve and two-limb Montgomery kernels
  arrived, and that binary covers everything the module did, with q up to 2^127 rather
  than 2^63. The single-candidate-list kernel only it launched is gone from
  `numerisect_mfactor_kernel.cu`. Its tests, which skipped whenever the CUDA Python
  bindings were absent, now run against the `nvcc` binary instead. They check it against
  the published factorizations, PARI/GP's prime divisors and the CPU helper, called
  directly, since the pipeline would otherwise compare the device with itself. They also
  check that the sieve removes the composite divisor 2047, that candidates past 2^127
  are counted as deferred, and that an even order is refused.
- Fixed the CUDA scanner's rebuild check. It compared the binary only against the host
  program, so an edit confined to the included kernel file left the stale binary in use.
  Either file being newer now triggers a rebuild, pinned by a test that runs without a
  CUDA toolkit.
- Corrected the GPU documentation, which still described the removed runtime-compile
  path: the Mersenne guide and engine table now say the accelerator is built with `nvcc`
  and reaches q < 2^127, and the kernel and host source comments no longer describe a
  2^63 limit or claim that nothing is ever deferred.

## 0.8.0 — 2026-09-21

- Fixed four defects that the first CodeQL analysis found, each confirmed by
  reproducing it before changing anything and each now pinned by a test that fails on
  the old code:
  - **The "Measure density and residues" tool drew an empty result**, and had since
    0.5.0. It shared the internal result type `distribution` with the analytic
    distribution pages, whose branch came first, so its own renderer was unreachable and
    the page was drawn by code looking for fields the API never returns. It now has its
    own type, and a test rejects any renderer handling the same type twice.
  - **Batch imports were open to quadratic regular-expression backtracking.** The
    family-syntax pattern let a polynomial ending in a space trade characters with the
    whitespace after it: 20,000 spaces took 1.26 s, and at the two-million-character
    request limit a single line would have held the server for about three and a half
    hours. The polynomial must now end on a non-space character and the whitespace runs
    are possessive; two million characters now take 0.05 s.
  - **Report downloads could follow a symbolic link out of the output directory**, and
    accepted the name `..`, which was refused only because it names a directory. Names
    are now resolved and must stay inside the resolved output directory.
  - **An unreadable adapter file exposed its absolute path** through `/api/adapters`,
    contradicting the rule that responses carry no filesystem paths. Only the operating
    system's reason is reported now.
- Also from the same analysis: two tests performed their request inside an `assert`,
    which would vanish under `python -O`; a dead initial assignment in the spiral renderer;
    a redundant self-import; explanatory comments on deliberate empty exception handlers;
    documentation for the five longest zeta commands; and a test harness that stripped
    markup in a single pass.
- Dismissed six findings as false positives after reading each, with the reason recorded
    on the alert: the two command-injection reports, where every argument is a fixed flag
    or an integer already validated as non-negative, passed as an argument list with no
    shell; the SQL-injection report, where every value is a bound parameter and the only
    interpolated identifiers are allowlisted; and the three report-write paths, whose
    names are a literal kind and a server-generated UUID.

- Added CodeQL code scanning. GitHub had never run an analysis of this repository. The
  new workflow covers everything the project writes: the Python orchestration layer, the
  browser interface, and the compiled C helpers, which parse command-line input and
  allocate from caller-supplied sizes and are the most security-relevant code here. The
  helpers are compiled through the project's own build functions from an editable
  install, so the analysed compiler invocations carry the real flags and map to files in
  the checkout. It runs on every push and pull request and weekly, with actions pinned by
  commit like the rest of CI. The security policy now lists the automated checks.

- Redesigned how a tool is found. 133 operations in a scrollable sidebar is more than
  anyone can survey, and the labels were the only thing search could match, so a tool was
  reachable only by guessing the words this project happened to choose. This was not
  theoretical: the author of the interface could not find Pell's equation in it.
- Added a command palette. `Ctrl`/`Cmd`+`K` from anywhere, or `/` when not typing in a
  field, opens a ranked search over every tool and switches views to open the one chosen.
  It works from the factorization and zeta views as well as Prime Tools.
- Added a concept index covering all 133 tools: the notation, alternative names, related
  problems and mathematicians each one relates to. Search matches it alongside the visible
  text, so `diophantine`, `chakravala` and `x^2-dy^2` all find Pell's equation, `cyclic
  number` finds full-reptend primes, `korselt` finds Carmichael numbers, `heegner` finds
  Euler's prime polynomial, and `keygen` finds prime generation. Seventeen such queries
  are asserted in the test suite, which executes the interface's own scoring code rather
  than a copy of it.
- Replaced the substring filter with ranked scoring. A query like `prime` previously
  matched nearly every tool with no ordering. A match in a tool's name now outranks one in
  its description, which outranks one reached only through the concept index, and a
  multi-word query is treated as a phrase first. Terms must begin at a word boundary,
  because a plain substring test matched `artin` inside `starting`.
- Renamed six navigation groups that did not predict their contents. "Advanced
  explorations" is now "Digit & sequence explorations", "Arithmetic & factors" is
  "Divisors & arithmetic functions", and the confusable pair "Patterns & distribution" and
  "Analytic prime distribution" are now "Gaps, tuples & Goldbach" and "Analytic
  distribution & counting". A test rejects the vague names returning.
- The sidebar search now says when nothing matched instead of silently emptying, and
  reports the tool count from the registry rather than a hard-coded number.

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
