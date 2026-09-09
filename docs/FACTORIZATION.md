# Factorization workspace

Numerisect 0.7.0 keeps factorization in native engines while Python manages
validation, processes, persistence, cancellation, and result verification.

## Routing and manual strategies

Automatic mode sends inputs below the configured decimal threshold to YAFU.
At or above the threshold it runs a YAFU pretest and sends a sufficiently
large residual to the nearest suitable installed CADO parameter set. Direct
YAFU, Msieve, CADO, and hybrid modes remain available.

The manual laboratory exposes bounded PARI/GP trial division and YAFU Pollard
rho/Brent, Pollard p−1, Williams p+1, ECM, SIQS, and NFS entry points. The
trial bound is recorded with the job. SQUFOF is available as its own backend, served by the project's compiled
`numerisect-squfof` helper because no installed library exposes a standalone
SQUFOF entry point. See [the expert factorization laboratory](FACTOR_LAB.md).

Engine availability does not guarantee that every algorithm is appropriate
for every input or that a particular third-party build is defect-free. A
nonzero exit, crash, malformed factor line, nondividing factor, or incomplete
factor product fails explicitly and preserves the log.

## Trees, partial results, and batches

The result pane groups repeated factors into exponent leaves and displays
status, decimal length, discovery engine, and total elapsed time. Composite or
unknown leaves can be continued as linked child jobs. The parent result remains
unchanged and the child records its parent job ID.

Batch mode accepts newline text, CSV-like values, or a JSON array. Every
expression is validated before any job is queued. The existing controlled
worker count prevents a file import from bypassing CPU concurrency limits. A
consolidated report becomes available only after every selected job reaches a
terminal state.

## Verification and provenance

Every factor must divide the requested input, and the complete returned
multiset must multiply to its absolute value. Cross-check mode runs YAFU and
Msieve independently and accepts the result only when their sorted factor
multisets are identical.

Successful jobs save both:

- `output/factorization-<job>.txt`, the human-readable equation and provenance;
- `output/factorization-<job>.json`, a reproducibility manifest.

The JSON schema identifier is `org.numerisect.factorization-manifest.v1`. It
records input/equation hashes, factors and proof labels, parent ID, requested
and selected strategy, CPU/pretest/trial/CADO parameters, complete native
command history, configured immutable engine revisions, and SHA-256 hashes of
the executables actually resolved on the host. A configured revision describes
Numerisect's reviewed source pin; the executable hash distinguishes a different
pre-existing system build.

## Campaign features

These were once deferred and have since shipped. Each is documented on its own page:

- **SQUFOF**, expert B1/B2/sigma scheduling, symbolic SNFS and Aurifeuillean analysis,
  the strategy adviser and algorithm traces are in
  [the expert factorization laboratory](FACTOR_LAB.md).
- **Resumable GMP-ECM campaigns** use the engine's own save and resume residue files;
  see the same page.
- **Distributed CADO-NFS** across trusted workers is in
  [Distributed CADO-NFS](DISTRIBUTED.md). Read its trust model before enabling it: CADO
  authenticates clients by IP address only.

Separate CADO stage control remains partial: parameters are exposed and stage progress is
parsed from the log, but running an individual stage in isolation is not implemented. See
[Roadmap status](ROADMAP_STATUS.md).
