# Factorization workspace

Numerisect 0.5.0 keeps factorization in native engines while Python manages
validation, processes, persistence, cancellation, and result verification.

## Routing and manual strategies

Automatic mode sends inputs below the configured decimal threshold to YAFU.
At or above the threshold it runs a YAFU pretest and sends a sufficiently
large residual to the nearest suitable installed CADO parameter set. Direct
YAFU, Msieve, CADO, and hybrid modes remain available.

The manual laboratory exposes bounded PARI/GP trial division and YAFU Pollard
rho/Brent, Pollard p−1, Williams p+1, ECM, SIQS, and NFS entry points. The
trial bound is recorded with the job. SQUFOF is not offered because the tested
YAFU command set does not expose it; a native C/C++ implementation needs its
own arbitrary-precision and bounded-machine-word contract before inclusion.

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

## Deferred campaign features

Resumable multi-worker GMP-ECM campaigns, expert B1/B2/sigma scheduling,
SQUFOF, symbolic SNFS/Aurifeuillean analysis, separate CADO stage control, and
distributed trusted workers are deliberately not represented by superficial
controls. They require new persistent schemas, native resume validation,
network security design, and clean cancellation tests. See
[Roadmap status](ROADMAP_STATUS.md).
