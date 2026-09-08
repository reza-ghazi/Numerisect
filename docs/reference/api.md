# HTTP API reference

Every route below is generated from the running application, so this page cannot
drift from the code. Interactive OpenAPI documentation is also served at
`/api/docs` while Numerisect is running.

## Authentication

All `/api/` routes except `/api/session` require the per-launch session token,
supplied either as the `X-Numerisect-Token` header or the `numerisect_session`
cookie. Obtain it from `GET /api/session`. The token changes every time the process
starts.

```bash
curl --cookie-jar jar http://127.0.0.1:8765/api/session
curl --cookie jar --header 'Content-Type: application/json' \
  --data '{"expression":"32416190071","mode":"proven"}' \
  http://127.0.0.1:8765/api/primes/check
```

To avoid tokens entirely, use `numerisect api`, which drives the same application
in-process. See the [command-line reference](cli.md).

## Conventions

- Invalid input returns **422** with a `detail` message naming the problem.
- A missing engine returns **503**.
- A refused network action returns **403**.
- Operations that produce a result save a report and return its exact
  `output/<filename>` path.
- Searches that stop at a bound set a truncation flag and give a continuation point.

## Routes (208)

### Engine adapters

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/adapters` | List built-in and user-declared engine adapters. |

### Algebra laboratory

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/algebra/chebotarev` | Chebotarev density and Frobenius patterns. Factor a monic irreducible polynomial modulo every unramified prime below a bound and compare the observed cycle-type frequencies with the conjugacy-class densities of its Galois group. |
| `POST` | `/api/algebra/congruence` | Solve P(x) ≡ 0 (mod m). Factor the modulus, solve modulo each prime, lift with Hensel's lemma including singular roots, and recombine every branch with the Chinese remainder theorem. |
| `POST` | `/api/algebra/cornacchia` | Solve x² + dy² = n by Cornacchia. Solve r² ≡ −d for every square divisor of n, run the Euclidean descent with a full step trace, and cross-check the complete solution set against PARI's qfbsolve. |
| `POST` | `/api/algebra/discrete-log` | Solve gˣ ≡ h (mod n) by a chosen method. Run baby-step/giant-step, Pohlig–Hellman, Pollard rho, or PARI's native znlog under an explicit budget of group operations. |
| `POST` | `/api/algebra/divisor-lattice` | Enumerate every divisor and factor pair. List each divisor with its cofactor and Ω value, and build the covering relation of the divisor lattice when the divisor count stays inside the configured cap. |
| `POST` | `/api/algebra/finite-field` | Compute in 𝔽ₚ and 𝔽_{pᵐ}. Build the field from a supplied irreducible reduction polynomial or from PARI's ffinit, then add, subtract, multiply, divide, exponentiate, and report orders, minimal polynomials, and Frobenius images. |
| `POST` | `/api/algebra/number-field` | Split rational primes in a number field. Build the maximal order of a monic irreducible polynomial and report splitting, inertia, ramification, ideal norms, an element's ideal factorization, and the class group. |
| `POST` | `/api/algebra/quadratic-ring` | Norms, units, and primes in ℚ(√d). Compute the norm and trace of a + bω, decide whether it is a unit or a prime of the ring, report the fundamental unit, roots of unity, and class group, and split a rational prime with explicit generators. |
| `POST` | `/api/algebra/reciprocity` | Quadratic reciprocity and the Jacobi symbol (a/n). Reduce (a/n) step by step with reciprocity, the supplementary law for 2, and modular reduction, then cross-check the sign against the native Kronecker symbol. |
| `POST` | `/api/algebra/record-numbers` | Highly composite and colossally abundant numbers. Test n for record τ and record σ(n)/n, decide the superior-highly-composite and colossally-abundant properties from their exact ε-intervals, and list all four record sequences. |
| `POST` | `/api/algebra/smoothness` | Bound the prime factors of n. Report the exact least prime factor, largest prime factor, largest prime power, and the B-smooth, B-powersmooth, and R-rough verdicts with the smooth and rough parts. |
| `POST` | `/api/algebra/sociable` | Aliquot cycles: amicable pairs and sociable chains. Iterate s(n) = σ(n) − n over an interval and report every closed cycle. |
| `POST` | `/api/algebra/weird-numbers` | Abundant, perfect, multiperfect &amp; weird. Classify n by its proper-divisor sum and decide semiperfection with an exact subset-sum over the proper divisors, returning a witness subset whenever one exists. |

### Batch import

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/batch/import` | Expand a TXT/CSV/JSON document of integers, ranges, expressions, and families. |

### Result cache

| Method | Path | Purpose |
|---|---|---|
| `DELETE` | `/api/cache` | Discard cached results, optionally for one operation path only. |
| `GET` | `/api/cache` | Report result-cache size and hit counts. |

### Capabilities

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/capabilities` | Report which engines are installed and what the build supports. |

### Optional catalogues

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/catalogues` | Show local catalogue files and the current network permission state. |
| `POST` | `/api/catalogues/factors` | Look up claimed factors locally, or remotely when explicitly permitted. |
| `POST` | `/api/catalogues/oeis` | Search OEIS for a sequence. Disabled unless explicitly permitted. |

### Prime counting

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/counting/algorithm-comparison` | Count π(x) with independent algorithms. primecount ships six independent prime-counting algorithms, and PARI/GP primepi is a seventh implementation that shares no code with them. |
| `POST` | `/api/counting/nth-prime-inverses` | Compare Li⁻¹(n) and R⁻¹(n) with the n-th prime. Both inverse approximations estimate the n-th prime: Li⁻¹ inverts the Eulerian logarithmic integral and R⁻¹ inverts the Riemann R function. |
| `POST` | `/api/counting/phi` | Evaluate Legendre's phi(x, a). φ(x, a) counts the integers in [1, x] divisible by none of the first a primes — the partial sieve inside Legendre's, Meissel's and Lehmer's formulas. |

### Diagnostics

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/diagnostics` | Collect an environment and engine diagnostic bundle for bug reports. |

### Distributed CADO-NFS

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/distributed/factor` | Queue a factorization whose sieving is distributed by CADO-NFS. |
| `POST` | `/api/distributed/preview` | Validate a distributed configuration and report its exposure without running. |
| `GET` | `/api/distributed/trust-model` | Describe how distributed CADO authenticates clients, and what it does not. |

### Analytic distribution

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/distribution/approximation-error` | Chart π(x) approximation error. Plot the absolute and relative error of x/log x, li(x), and R(x) against exact π(x) over a log-spaced grid. |
| `POST` | `/api/distribution/bateman-horn` | Bateman–Horn prediction for polynomials. Prove each polynomial irreducible, count ω(p) with polrootsmod, build the Bateman–Horn constant, and compare the prediction with an exact count over a bounded range. |
| `POST` | `/api/distribution/density-surface` | Map density over position and residue. Bin every prime in a range by block position and reduced residue class modulo q, then draw the normalised density as a heatmap. |
| `POST` | `/api/distribution/maximal-gaps` | Search for maximal gaps. |
| `POST` | `/api/distribution/nth-prime-bounds` | Check Rosser–Schoenfeld and Dusart bounds. Evaluate six published upper and lower bounds for pₙ at high precision and compare each with the exact n-th prime from primecount. |
| `POST` | `/api/distribution/pnt-convergence` | Track π(x)/(x/log x) and π(x)/li(x). Follow both prime-number-theorem ratios and the normalised error term across a log-spaced grid, flagging every sign change of π(x) − li(x) that the grid can see. |
| `POST` | `/api/distribution/prime-race` | Prime races and Chebyshev bias. Count primes in every reduced residue class modulo q at a series of checkpoints, report the leader at each checkpoint, and normalise the bias by log x/√x. |
| `POST` | `/api/distribution/progressions` | Compare π(x; q, a) with li(x)/φ(q). Count primes in every reduced class modulo q and report the observed deviation from the expected li(x)/φ(q), in absolute, relative, and √x-normalised form. |
| `POST` | `/api/distribution/short-interval` | Maier matrix short-interval experiment. Count the primes in each row interval [qk + 1, qk + y] and compare with the naive expectation y/log(qk). |
| `POST` | `/api/distribution/singular-series` | Hardy–Littlewood singular series 𝔖. Check admissibility and evaluate the singular series as a truncated Euler product with a rigorous relative tail bound and an explicit enclosing interval. |
| `POST` | `/api/distribution/tuple-prediction` | Count twin primes and constellations. Compare the Hardy–Littlewood prediction 𝔖·∫ dt/logᵏ t with an exact count. |

### OpenAPI documentation

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/docs` | Serve the interactive OpenAPI documentation for this API. |

### Exports

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/exports/jobs` | Export job search results in any supported interchange format. |
| `GET` | `/api/exports/jobs/{job_id}` | Export one factorization job in any supported interchange format. |
| `GET` | `/api/exports/reports/{filename}` | Re-container a saved text report; the engine-produced body is unchanged. |

### Expert factorization laboratory

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/factor-lab/certificates` | Generate and independently verify a primality certificate per prime factor. |
| `POST` | `/api/factor-lab/special-form` | Detect special algebraic forms, algebraic factors, and SNFS suitability. |
| `POST` | `/api/factor-lab/squfof` | Factor with Shanks' square forms factorization (numerisect-squfof, C/GMP). |
| `POST` | `/api/factor-lab/strategy` | Recommend an engine and estimate the expected remaining factor size. |
| `POST` | `/api/factor-lab/trace` | Produce a bounded, educational step trace of a factoring algorithm. |
| `POST` | `/api/factor-lab/tune` | Measure this machine's SIQS/NFS crossover with YAFU's own `tune`. |

### Quadratic forms and continued fractions

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/forms/class-group` | Class number, group structure, generators and regulator for a discriminant. |
| `POST` | `/api/forms/compose` | Gaussian composition and powers, with and without reduction; principality and order. |
| `POST` | `/api/forms/continued-fraction` | Continued fraction of a rational or a quadratic irrational; partial quotients, convergents, preperiod and period. Values wider than `preview_digits` are abbreviated in the response and written in full to `export_file`. |
| `POST` | `/api/forms/pell` | Pell's equation `x² − dy² = 1`, solved from the fundamental unit and list further solutions. Values wider than `digit_limit` are abbreviated in the response and written in full to `export_file`. |
| `POST` | `/api/forms/prime-form` | `qfbprimeform` for each requested prime. |
| `POST` | `/api/forms/reduce` | Reduce a binary quadratic form, trace the steps, give the SL(2, ℤ) matrix. |
| `POST` | `/api/forms/reduced-forms` | Enumerate the reduced forms of a discriminant; flag ambiguous and square forms. |
| `POST` | `/api/forms/represent` | Represent an integer by a form with `qfbsolve`. |

### Performance history

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/history/performance` | Aggregate completed-job runtimes by engine and decimal-digit bucket. |

### Factorization jobs

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/jobs` | List jobs, optionally filtered and sorted (roadmap item 135). |
| `POST` | `/api/jobs` | Queue a factorization job on a chosen backend and return its identifier. |
| `POST` | `/api/jobs/batch` | Queue multiple factorizations. Enter one integer expression per line or import a TXT, CSV, or JSON array. |
| `POST` | `/api/jobs/batch-export` | Export several factorization jobs at once in a chosen interchange format. |
| `POST` | `/api/jobs/reorder` | Reorder queued jobs; the supplied order becomes the dispatch order. |
| `GET` | `/api/jobs/{job_id}` | Fetch one factorization job's status, phase and result. |
| `POST` | `/api/jobs/{job_id}/cancel` | Cancel a running job by signalling its engine process group. |
| `POST` | `/api/jobs/{job_id}/certificates` | Certify every prime factor of a completed factorization (roadmap item 13). |
| `POST` | `/api/jobs/{job_id}/continue-cofactor` | Start a linked child job on a composite cofactor the parent could not split. |
| `GET` | `/api/jobs/{job_id}/export` | Download one factorization job in a chosen interchange format. |
| `GET` | `/api/jobs/{job_id}/log` | Stream a job's engine log with absolute paths redacted. |
| `POST` | `/api/jobs/{job_id}/pause` | Suspend a running job's process group with SIGSTOP. |
| `POST` | `/api/jobs/{job_id}/priority` | Change one job's scheduling priority; higher runs sooner. |
| `POST` | `/api/jobs/{job_id}/resume` | Continue a paused job's process group with SIGCONT. |
| `POST` | `/api/jobs/{job_id}/resume-paused` | Continue a paused job's process group with SIGCONT. |

### Number theory

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/number-theory/aliquot` | Follow an aliquot sequence. Iterate proper-divisor sums with native factorization, exact termination detection, and repeated-value cycle detection. |
| `POST` | `/api/number-theory/arithmetic-functions` | Analyze divisors, kernels &amp; representations. Compute σₖ, Jordan Jₖ, Dedekind ψ, Liouville, von Mangoldt, smoothness, squarefree structure, and quadratic representations. |
| `POST` | `/api/number-theory/crt` | Chinese remainder theorem for a congruence system. Solve compatible systems even when moduli are not pairwise coprime. |
| `POST` | `/api/number-theory/cunningham-chain` | Verify a prime chain. Follow pₖ₊₁ = 2pₖ + 1 or 2pₖ − 1, proving every term and stopping explicitly at the first composite. |
| `POST` | `/api/number-theory/cyclotomic` | Construct Φₙ(x) and factor modulo p. Build the exact cyclotomic polynomial and inspect its irreducible factorization over a selected finite field. |
| `POST` | `/api/number-theory/discrete-log` | Solve gˣ ≡ a (mod n). Use PARI's native algorithm selection with the exact order of the generated subgroup. |
| `POST` | `/api/number-theory/divisor-classification` | Classify an integer by its divisors. Determine deficiency, abundance, perfection, almost-perfection, multiperfection, and amicable pairing exactly. |
| `POST` | `/api/number-theory/eisenstein` | Eisenstein primes a + bω. Apply exact norm and rational-axis criteria in the triangular integer lattice ℤ[ω]. |
| `POST` | `/api/number-theory/factor-strategy` | Analyze before factoring. Run native perfect-power, probable-prime, special-form, and small-factor checks before selecting YAFU or CADO-NFS. |
| `POST` | `/api/number-theory/hensel-roots` | Lift polynomial roots modulo pᵏ. Enter integer coefficients from constant term upward and compute exact residues from PARI's p-adic roots. |
| `POST` | `/api/number-theory/modular-roots` | Solve xᵏ ≡ a (mod p). Enumerate all roots in a rigorously verified prime field using PARI finite-field arithmetic. |
| `POST` | `/api/number-theory/ntt-primes` | Generate NTT primes. Find proven primes p = k·2ᵐ + 1 of an exact bit length for native number-theoretic transforms. |
| `POST` | `/api/number-theory/order-distribution` | Distribute multiplicative orders. Enumerate every unit modulo n and count elements of each exact multiplicative order. |
| `POST` | `/api/number-theory/perfect-power` | Detect a perfect power. Find the maximal exponent k and exact base a such that n = aᵏ. |
| `POST` | `/api/number-theory/polynomial` | Factor over ℚ and 𝔽ₚ. Enter integer coefficients from constant term upward; PARI factors the polynomial in both domains and finds finite-field roots. |
| `POST` | `/api/number-theory/power-residues` | Count kth-power residues. Evaluate the complete map x ↦ xᵏ over 𝔽ₚ and count every residue's preimages. |
| `POST` | `/api/number-theory/primality-lab` | Compare primality tests. Compare Fermat, Euler–Jacobi, strong Miller–Rabin, BPSW, and a selected rigorous PARI proof on one input. |
| `POST` | `/api/number-theory/prime-approximations` | Compare π(x) approximations. Compare exact parallel primecount output with x/log(x), Li(x), and Riemann R(x), including signed and relative errors. |
| `POST` | `/api/number-theory/quadratic-decomposition` | Decompose a prime in ℚ(√d). Construct the maximal quadratic order and compute splitting, inertia, ramification, and prime-ideal norms. |
| `POST` | `/api/number-theory/special-form-test` | Test Mersenne or Fermat numbers. Use the necessary-and-sufficient Lucas–Lehmer or Pépin criterion without general factorization. |
| `POST` | `/api/number-theory/special-prime-family` | Search structured prime families. Construct candidates in eight classical families and retain only values rigorously proven prime by PARI/GP. |
| `POST` | `/api/number-theory/summatory-functions` | Calculate M(x), L(x), θ(x), ψ(x). Evaluate Mertens, summatory Liouville, and both Chebyshev functions natively over a bounded exact range. |
| `POST` | `/api/number-theory/symbols` | Legendre, Jacobi &amp; Kronecker. Evaluate all applicable quadratic character symbols exactly and distinguish their domains. |
| `POST` | `/api/number-theory/tonelli-shanks` | Trace Tonelli–Shanks. Compute roots of x² ≡ a (mod p), display the native algorithm state, and verify each result. |
| `POST` | `/api/number-theory/unit-group` | Analyze (ℤ/nℤ)×. Compute invariant factors, component generators, cyclicity, and bounded primitive-root enumeration. |
| `POST` | `/api/number-theory/valuation` | Calculate vₚ(n). Decompose a nonzero arbitrary-size integer into its exact p-power and coprime unit part. |

### Report download

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/outputs/{filename}` | Download a saved report from the output directory. |

### /api/primality-lab

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/primality-lab/bitwin-chains` | Search bi-twin chains. Find maximal chains whose members n·2ⁱ − 1 and n·2ⁱ + 1 are all proven prime. |
| `POST` | `/api/primality-lab/carmichael` | Carmichael numbers and Korselt's criterion. Factor n, test squarefreeness and (p − 1) \| (n − 1) for every prime factor, and derive λ(n) and the exact Fermat-liar count. |
| `POST` | `/api/primality-lab/chernick` | Generate Chernick Carmichael numbers. Search k with 6k + 1, 12k + 1 and 18k + 1 simultaneously prime, and re-verify Korselt's criterion for every product. |
| `POST` | `/api/primality-lab/compare` | Compare eight primality tests. Run Fermat, Solovay–Strassen, Miller–Rabin, Lucas, strong Lucas, Frobenius, Baillie–PSW, APR-CL, and ECPP on one integer and keep probable results separate from proofs. |
| `POST` | `/api/primality-lab/constrained-prime` | Generate a proven prime to specification. Construct an exact-bit-length prime with an optional residue condition, safe-prime or Gordon strong-prime structure, and a PARI certificate. |
| `POST` | `/api/primality-lab/covering-set` | Verify a Sierpiński/Riesel covering set. Check exactly that every exponent class modulo the period contributes a fixed prime divisor, which proves k is a Sierpiński or Riesel number. |
| `POST` | `/api/primality-lab/deterministic-witnesses` | Deterministic Miller–Rabin witness sets. Use the published sufficient base sets for bounded ranges, showing every squaring chain and the exact bound that makes the result a proof. |
| `POST` | `/api/primality-lab/ecpp-steps` | Expand an ECPP certificate. Show every Atkin–Morain descent step, its elliptic curve, point, group order, and discriminant, then re-validate the whole certificate. |
| `POST` | `/api/primality-lab/lucas-lehmer-steps` | Show the Lucas–Lehmer iteration. Materialize the residues s₀ = 4, sᵢ = sᵢ₋₁² − 2 modulo Mₚ that decide whether 2ᵖ − 1 is prime. |
| `POST` | `/api/primality-lab/lucas-sequence` | Run Lucas, Frobenius, and Morrison N+1 tests. Select (P, Q) by Selfridge's method A or by hand, then apply the Lucas, strong Lucas, Frobenius, Lucas–Lehmer–Riesel, and Morrison N + 1 criteria. |
| `POST` | `/api/primality-lab/pocklington` | Pocklington N − 1 primality proof. Factor N − 1 far enough for the Pocklington bound, find a witness for every prime divisor of the factored part, and emit a machine-readable certificate. |
| `POST` | `/api/primality-lab/pratt` | Build a recursive Pratt certificate. Certify n from a primitive root and the full factorization of n − 1, then certify every factor recursively down to 2. |
| `POST` | `/api/primality-lab/prime-ladder` | Prime ladders, one digit at a time. Find a shortest path between two equal-width primes in which every intermediate value is a proven prime. |
| `POST` | `/api/primality-lab/proth` | Proth primes k·bⁿ + 1. Apply Proth's necessary-and-sufficient criterion for base 2, or the generalized N − 1 criterion for any other base, and cross-check against PARI isprime. |
| `POST` | `/api/primality-lab/proth-search` | Search k·bⁿ + 1 over an exponent range. Filter candidates with BPSW natively, then settle each survivor with the Proth criterion or PARI isprime, counting expired budgets as inconclusive. |
| `POST` | `/api/primality-lab/repunit` | Generalized repunits (bⁿ − 1)/(b − 1). Skip composite exponents natively, filter with BPSW, and prove every reported repunit prime with PARI isprime. |
| `POST` | `/api/primality-lab/sierpinski` | Sierpiński and Riesel numbers k·2ⁿ ± 1. Find the first proven prime that removes k from the Sierpiński or Riesel candidates; an exhausted bound stays inconclusive. |
| `POST` | `/api/primality-lab/taxonomy` | Classify pseudoprime families. Separate Fermat, Euler–Jacobi, strong, Lucas, strong Lucas, Frobenius, and Baillie–PSW behaviour for one composite and the bases that fool it. |
| `POST` | `/api/primality-lab/verify-certificate` | Verify a Pocklington or Pratt certificate. Re-derive every condition of a certificate from the certificate alone, without consulting the run that produced it. |

### Prime tools

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/primes/absolute` | Find circular primes. Find primes whose every cyclic decimal rotation is also prime, grouped by orbit. |
| `POST` | `/api/primes/after` | List consecutive proven primes after an integer. |
| `POST` | `/api/primes/batch-check` | Check a list of integers. Test up to 1,000 decimal integers together. |
| `POST` | `/api/primes/before` | List consecutive proven primes before an integer. |
| `POST` | `/api/primes/check` | Check a number. Choose a quick probable-prime test or a rigorous proof. |
| `POST` | `/api/primes/classify` | Classify a prime. Rigorously test a prime against 56 structural, digital, sequence, and constellation classes. |
| `POST` | `/api/primes/contiguous-digits` | Find primes inside a number. Test every distinct contiguous decimal substring without changing digit order. |
| `POST` | `/api/primes/coprimes` | Explore relative primality. Compute φ(m), preview the reduced residue system, and find consecutive integers coprime to m after any starting point. |
| `POST` | `/api/primes/count` | Calculate π(x). Count every positive prime less than or equal to x exactly with primecount's parallel Gourdon algorithm. |
| `POST` | `/api/primes/digit-constrained` | Search a digit alphabet. Generate only candidates composed of selected decimal digits, then rigorously prove the primes. |
| `POST` | `/api/primes/distribution` | Measure density and residues. Count proven primes per interval bin and residue class while measuring twin pairs and the largest internal gap. |
| `POST` | `/api/primes/factor-count-distribution` | Compare ω(n) and Ω(n). Factor every integer in a finite range and compare distinct prime-factor counts with counts that include multiplicity. |
| `POST` | `/api/primes/gap-statistics` | Analyze prime-gap statistics. Compute exact frequencies, extrema, rational mean and median, and mode over consecutive prime gaps. |
| `POST` | `/api/primes/gaps` | Measure consecutive prime gaps. Inspect each gap and highlight the largest gap found in an interval. |
| `POST` | `/api/primes/gaussian/check` | Check a + bi. Apply the exact norm and rational-axis criteria in the Gaussian integers. |
| `POST` | `/api/primes/gaussian/range` | Find Gaussian primes. Search the square −B ≤ a,b ≤ B and inspect the prime lattice. |
| `POST` | `/api/primes/generate` | Create fixed-size primes. Generate distinct primes with an exact decimal length. |
| `POST` | `/api/primes/generate-special` | Generate primes with structure. Create rigorously proven safe, Sophie Germain, Blum, or modular primes. |
| `POST` | `/api/primes/goldbach` | Goldbach partitions of an even integer. Find unique proven-prime pairs whose sum is the supplied even integer. |
| `POST` | `/api/primes/indicator-constant` | Encode primality as binary digits. Calculate C = Σ [n is prime]·2⁻ⁿ with a certified tail bound and arbitrary-precision decimal output. |
| `POST` | `/api/primes/integer-profile` | Analyze arithmetic functions. Factor one arbitrary-size integer and calculate its divisor, totient, Carmichael, Möbius, radical, and semiprime data. |
| `POST` | `/api/primes/miller-rabin-witnesses` | Miller–Rabin witness bases. Use the complete strong test—not the incomplete aᵈ = 1 shortcut—to distinguish witnesses and passing bases. |
| `POST` | `/api/primes/modular` | Calculate modulo a prime. Calculate inverses, powers, multiplicative orders, all square roots, or a primitive root. |
| `POST` | `/api/primes/modular-wheel` | Modular wheel of residue structure. Plot native primality and coprimality results around modular rings. |
| `POST` | `/api/primes/nth` | Find the n-th prime. Look up p(n) exactly using parallel primecount, with a PARI/GP fallback. |
| `POST` | `/api/primes/nth-near` | Primes near a number. Find the nth prime or list consecutive primes strictly before or after an arbitrary-size integer. |
| `POST` | `/api/primes/palindrome-derived` | Test \|n − reverse(n)\| + 1. Reproduce the source sequence with exact decimal reversal and rigorous primality tests. |
| `POST` | `/api/primes/paterson` | Paterson primes by base-4 form. Find prime p when its base-4 digits, read as a decimal integer, are also prime. |
| `POST` | `/api/primes/perfect` | Generate even perfect numbers. Use the Euclid–Euler theorem with rigorously proven Mersenne primes. |
| `POST` | `/api/primes/polynomial` | Euler's prime polynomial n² − n + k. Find rigorous prime values, the longest consecutive run, and residue classes forced divisible by small primes. |
| `POST` | `/api/primes/primorials` | Primorials p#. Multiply the first n rigorously generated primes cumulatively with arbitrary precision. |
| `POST` | `/api/primes/problems` | Run exact equation searches. Explore four problems from the source notebook with native factorizations and rigorous primality checks. |
| `POST` | `/api/primes/progression` | Primes in a residue class. Find proven primes p ≡ r (mod m) in an inclusive interval. |
| `POST` | `/api/primes/pyramid` | Construct number pyramids. Recreate the digit-insertion sequence or a multiplication pyramid with native primality flags. |
| `POST` | `/api/primes/random-range` | Sample proven primes. Select distinct random primes inside an arbitrary-precision interval. |
| `POST` | `/api/primes/range` | Primes in an interval. Results are paginated, even when the endpoints are huge. |
| `POST` | `/api/primes/reciprocal` | Analyze 1/p. Find the exact decimal period, test whether 10 is a primitive root modulo p, and export decimal digits. |
| `POST` | `/api/primes/reptend` | Full-reptend primes and maximal decimal periods. Find primes p for which 1/p has the maximum possible period p−1. |
| `POST` | `/api/primes/sieve-interval` | Enumerate primes in an interval of any magnitude. |
| `POST` | `/api/primes/special-numbers` | Explore related sequences. Search finite ranges using corrected exact definitions for pseudoprimes and prime-bearing sequences. |
| `POST` | `/api/primes/tuples` | Prime tuples: twins and constellations. Search by offsets from a prime base. |
| `POST` | `/api/primes/verify-certificate` | Verify a primality certificate. Validate a machine-readable PARI ECPP certificate independently of the result that created it. |

### Job queue

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/queue` | Show queued and running jobs in dispatch order. |

### Saved reports

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/reports` | Search the index of saved report files. |

### Session

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/session` | Issue the per-process request token; the only unauthenticated route. |

### Engine setup

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/setup` | Report which native engines are present, missing or being built. |
| `POST` | `/api/setup/install` | Build the pinned native engines after explicit browser confirmation. |
| `GET` | `/api/setup/log` | Return the native-engine build log. |

### Integer structure

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/structure/factorint-strategies` | Compare PARI factoring strategies. The second argument of factorint is a bitmask of methods to avoid: 1 avoids MPQS, 2 avoids the first-stage ECM, 4 avoids Pollard–Brent rho and Shanks SQUFOF, 8 skips the final ECM. |
| `POST` | `/api/structure/lenstra-divisors` | Search divisors with Lenstra's algorithm. PARI's divisorslenstra finds every divisor d of N with d ≡ r (mod s) without factoring N. |
| `POST` | `/api/structure/predicates` | Test the PARI structure predicates. Run isprimepower (which returns the exponent k of n = pᵏ), ispseudoprimepower, ispowerful, istotient (which returns a witness m with φ(m) = n), isfundamental and ispolygonal on one integer. |

### Independent verification

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/verify/primality` | Decide primality with independent implementations and compare them. |
| `POST` | `/api/verify/prime-count` | Compute pi(x) with every independent method available and compare them. |
| `POST` | `/api/verify/self-test` | Ask each installed engine questions with published answers. |

### Visualization

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/visual/complexity` | Compare asymptotics with measured runs. |
| `POST` | `/api/visual/eisenstein-lattice` | Map Eisenstein primes on the hexagonal lattice. Enumerate every Eisenstein prime a + bω with norm a² − ab + b² up to a bound and separate the split, inert, and ramified cases. |
| `POST` | `/api/visual/gap-timeline` | Prime gaps and maximal record gaps. Plot every consecutive prime gap across a range and mark each record gap with its merit g / ln p. |
| `POST` | `/api/visual/modular-wheel` | Spin a wheel with an arbitrary base. Place consecutive integers on a wheel of any base up to 10,000 from any starting point, with per-spoke prime counts and Euler's totient computed natively. |
| `POST` | `/api/visual/prime-race` | Prime race animation of the residue classes. Animate the running prime counts of every class coprime to m at native checkpoints and replay each exact lead change. |
| `POST` | `/api/visual/residue-heatmap` | Count primes by residue class and interval. Split a range into equal bins and count the primes in every residue class modulo m, exposing the reduced classes predicted by Dirichlet's theorem. |
| `POST` | `/api/visual/sieve-trace` | Replay a sieve step by step. Play back the exact execution trace of the sieve of Eratosthenes, its segmented variant, Sundaram's sieve, or Atkin's sieve. |
| `POST` | `/api/visual/spiral` | Draw a prime spiral. Lay a range of integers on an Ulam square spiral, a Sacks parabolic spiral, or an Archimedean polar spiral, optionally highlighting a residue class or a quadratic family. |

### Workspaces

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/workspaces` | List saved workspaces, newest first. |
| `POST` | `/api/workspaces` | Save a named workspace referencing jobs, reports, and interface state. |
| `DELETE` | `/api/workspaces/{workspace_id}` | Delete one workspace. Jobs and reports are not affected. |
| `GET` | `/api/workspaces/{workspace_id}` | Load one workspace. |
| `POST` | `/api/workspaces/{workspace_id}` | Update selected fields of one workspace. |

### Zeta and L-functions

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/zeta/backlund-s` | Certified S(T) with an exploratory plot across an ordinate range. |
| `POST` | `/api/zeta/characters` | Dirichlet character table modulo q with conductor, parity and order. |
| `POST` | `/api/zeta/chebyshev-psi` | Chebyshev ψ(x) reconstructed from certified zeros (FLINT/Arb). |
| `POST` | `/api/zeta/count` | Count nontrivial zeros. Certify the exact number of zeros from ordinate 0 through T. |
| `POST` | `/api/zeta/dedekind` | Dedekind zeta of a bounded number field through PARI/GP. |
| `POST` | `/api/zeta/euler-product` | Truncated Euler products against ζ(s) with a rigorous tail bound. |
| `POST` | `/api/zeta/evaluate` | Evaluate ζ(s). Compute certified complex enclosures with FLINT/Arb ball arithmetic. |
| `POST` | `/api/zeta/explicit-prime-count` | Riemann's explicit formula for π(x) from certified zeros (FLINT/Arb). |
| `POST` | `/api/zeta/functional-equation` | Verify ζ(s) symmetry. Independently enclose both sides of the functional equation and test rigorous ball overlap. |
| `POST` | `/api/zeta/gram` | Calculate a Gram point. Enclose gₙ defined by the Riemann–Siegel theta equation θ(gₙ)=πn. |
| `POST` | `/api/zeta/gram-blocks` | Gram's-law verdicts, exceptions and Gram blocks over an index range. |
| `POST` | `/api/zeta/hardy` | Evaluate Hardy Z(t). Evaluate the real-valued critical-line function whose real zeros correspond to ζ zeros. |
| `POST` | `/api/zeta/heatmap` | Render a ζ(s) heatmap. Color magnitude and phase across a sampled complex region. |
| `POST` | `/api/zeta/l-function` | Rigorous L(s, χ) enclosure with an independent Hurwitz cross-check. |
| `POST` | `/api/zeta/l-zeros` | GRH experiments on critical-line zeros of `L(s, χ)`: certified sign changes, or exploratory \|L\| minima. |
| `POST` | `/api/zeta/line` | Plot ζ(½ + it). FLINT evaluates every point; select a component or trace the complex values in an Argand plot. |
| `POST` | `/api/zeta/pair-correlation` | Pair correlation of certified zeros against the GUE prediction. |
| `POST` | `/api/zeta/riemann-siegel` | Riemann–Siegel main sum with K corrections against acb_dirichlet_zeta. |
| `POST` | `/api/zeta/stieltjes` | Calculate a Stieltjes constant. Enclose γₙ from the Laurent expansion of ζ(s) around its pole at s=1. |
| `POST` | `/api/zeta/xi-eta` | Evaluate ξ(s) or η(s). Evaluate the completed xi function or Dirichlet eta continuation with rigorous complex balls. |
| `POST` | `/api/zeta/zero-spacing` | Normalized nearest-neighbour spacing histogram of certified zeros. |
| `POST` | `/api/zeta/zeros` | Isolate consecutive critical-line zeros. Return rigorous intervals for consecutive Hardy Z zeros, starting at any positive index. |

