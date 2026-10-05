# Roadmap and scope

Numerisect was built against a 150-item feature proposal. The ledger records exactly what
was implemented, what is partial with the specific gap named, and what was declined with
the reasoning, so a decision can be revisited rather than rediscovered.

[:octicons-arrow-right-24: The full ledger](../ROADMAP_STATUS.md)

## Summary

| Status | Count |
|---|---:|
| Fully implemented | 131 |
| Working with a named gap | 12 |
| Declined, with reasoning recorded | 4 |
| Deferred | 0 |

Beyond the proposal, an audit compared what the installed libraries expose against what
the application calls, and closed the gaps that fall within the subject: a prime-counting
algorithm comparison, integer-structure predicates, `factorint` strategy flags, and a
binary quadratic forms and continued fractions workbench.

Several additions are not wrappers around an engine at all. Cross-engine verification,
the engine self-test and prime enumeration above primesieve's \(2^{64}\) ceiling came
first. Since then: Mersenne trial factoring on CPU and GPU; searches for Wieferich,
Wall–Sun–Sun, Wilson and Wolstenholme primes, which replaced tables of published values;
the Mertens function with two independent algorithms that check each other; Brun-type
reciprocal sums; and CFRAC, Lehman and Hart, the classical factoring methods no installed
engine exposes. Each one states in its source header why no library could serve it.

## What was declined, and why

**Synthetic engine benchmarking.** Timing engines on a fixed input set measures one
machine on one day with one set of builds, reads like a general fact about the engines,
and goes stale the moment one is rebuilt. The durable version already exists: performance
history aggregates runtimes from real jobs.

**Side-by-side engine timing.** The correctness half is covered by cross-verification,
which runs YAFU and Msieve independently and rejects a disagreement. The timing half would
present a single sample as a comparison when the result is dominated by thread count and
ECM luck.

**FactorDB integration.** The code would be cheap, since the permissioned network path
already exists. The objection is what it does to the application's meaning: consulting a
database of unverified community claims turns "your machine factored this" into "someone
once said this factors that way, and we checked the division". Local catalogue files
remain the supported offline route.

## What 1.0 would require

Numerisect is deliberately at 0.x: the minor number carries the weight, and the version
text says so. The remaining distance to 1.0 is **not** more mathematics. Of the twelve
items that still carry a named gap, none is a missing computation; they divide into two
kinds, and only one kind can be closed:

**Presentation, and therefore closeable.** The factor view renders as a flat
root-plus-leaves list rather than a tree, although the parent/child relationship already
exists in the data. The engine decision path is returned as a list rather than drawn. Job
search has no saved queries or facets. Per-factor discovery time is not captured. CADO's
own stages cannot be run one at a time, because its workflow is driven by an upstream
Python harness and isolating a stage means reproducing that harness's bookkeeping.

**Bounded searches, and therefore permanent.** The pseudoprime taxonomy, Korselt
analysis, covering-set verification, record-number families, sociable cycles and
number-field work are all complete *within documented finite bounds*, and report
inconclusive beyond them. That is the honest shape of those questions, not a defect
waiting to be fixed, and 1.0 should not pretend otherwise.

So a 1.0 is a commitment about the interface and about stability, which is why it has not
been declared yet. It would mean:

1. **A stable API.** Route paths and response keys would not change without a major
   version. Today they can, and several have within 0.x.
2. **The closeable presentation gaps either built or declined in writing**, so no item
   sits in an indefinite "partial" state.
3. **The permanent limits stated as limits**, in the capability index as well as the
   ledger, so a reader does not mistake a bounded search for an unfinished one.
4. **The published artifact installed and exercised on each supported platform**, from the
   release archive rather than from a checkout, which CI does not currently do.

This section is the author's standing position, not a schedule. Until those four hold, a
feature release raises the minor number.

## Honest limits

Numerisect is an experimental, source-distributed pre-release with no official binary
packages. It is exercised on Fedora Linux x86-64 and by GitHub Actions on Ubuntu Linux
x86-64 and ARM64, Ubuntu 24.04 x86-64 inside Windows WSL, and macOS on ARM64 and Intel.
Native Windows remains unsupported, and the Arch Linux installer path has not yet
received clean-host CI verification.
