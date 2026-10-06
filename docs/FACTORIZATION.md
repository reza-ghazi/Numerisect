# Factorization workspace

Numerisect 0.12.1 keeps factorization in native engines while Python manages
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

### The tree is drawn, not listed

`GET /api/jobs/{job_id}/tree` returns the hierarchy the run actually produced: the
input, each factor in the order the engines printed it, and the cofactor left after
every division. PARI/GP performs each division and runs `isprime` on each part
(`fl_factor_tree`), because dividing a hundred-digit cofactor is arithmetic and does
not belong in the interface, and because a node's label has to come from a proof
rather than from whichever engine happened to print the factor. The browser receives
the chain and places boxes; it computes no number in it. If the chain cannot be
built — a `tune` measurement is a report about the input, not a decomposition — the
flat summary stays and nothing is drawn.

A cofactor that was continued as a child job carries that job's id, so the drawing
spans more than one run: clicking the node opens the child. A chain that does not
reach 1 is reported as the part of the decomposition the engines established, with
the remaining cofactor named, and is never presented as a factorization.

### CADO-NFS one stage at a time

The `cado_stage` backend runs CADO's own workflow up to a stage you choose and stops
there. `GET /api/factor/cado-stages` lists the stages in the order its harness runs
them: size and root optimization of the polynomial, factor base, free relations,
lattice sieving, the two duplicate-removal passes, singleton removal, matrix merging,
linear algebra, quadratic characters and the square root.

This needs no reimplementation of CADO's upstream harness, which is what the roadmap
ledger assumed for a long time. Every CADO task accepts a `run` parameter, so
disabling the task *after* the requested one makes the harness stop at it: it logs
`Stopping at <task>`, exits cleanly, and leaves the finished work in the job's working
directory. `POST /api/jobs/{job_id}/cado-stage` moves the gate forward and runs again;
CADO's own state database knows which tasks have already run, so the next stage
continues from where the last one stopped. Verified here against CADO-NFS 3.0.0 on a
60-digit input: gated at sieving it stopped after polynomial selection, gated at
singleton removal it sieved and removed duplicates, and ungated it finished and
returned both 30-digit primes.

A staged run is a **report**, not a factorization, and is recorded as one: it names the
stages that ran and the figures CADO printed for them — the best Murphy E, the free and
unique relation counts, what singleton removal left, the merged matrix dimensions. Only
the last stage, the square root, yields factors, and then the usual completeness check
applies. A gated run that ends without CADO's own stop marker fails rather than
reporting the stage as finished, because the workflow ended for some other reason. A
stage earlier than the one already finished is refused: that work is done.

### When each factor appeared

Each factor records `first_seen_seconds`: the offset, from the moment the job started
running, at which its value first appeared in the engine's output. The job manager
notes every number of four or more digits as the output streams past and matches the
final factor list against that record.

This is an observation of the engine's own log, not a measurement of the algorithm —
it includes whatever buffering and staging the engine does, and a single number tells
you when the engine announced the factor, not how long finding it cost. Shorter
factors are not timed at all: three digits appear in engine output for every other
reason, from curve counts to line numbers. A factor the engines never printed as a
whole number, or one produced by a helper the manager calls directly rather than as a
subprocess, carries no time, and an absent time means unknown. It is never filled in
with the job's elapsed time, which would read as though that factor took the whole run.
The peeling order of the tree follows these times where every factor has one, and the
response says which ordering it used in `ordered_by`.

Batch mode accepts newline text, CSV-like values, or a JSON array. Every
expression is validated before any job is queued. The existing controlled
worker count prevents a file import from bypassing CPU concurrency limits. A
consolidated report becomes available only after every selected job reaches a
terminal state.

## Verification and provenance

Every factor must divide the requested input, and the complete returned
multiset must multiply to its absolute value. Cross-check mode runs YAFU and
Msieve independently and accepts the result only when their sorted factor
multisets are identical. It also records what each engine answered: its
factors with the primality label **that engine** assigned, the cofactor it
left and its elapsed time. Agreement on the factors with disagreement on
proven versus probable — `P` against `prp` — raises a warning naming the
factor and both labels; see [Verification](VERIFICATION.md#factorization).

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
