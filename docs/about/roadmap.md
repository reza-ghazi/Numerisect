# Roadmap and scope

Numerisect was built against a 150-item feature proposal. The ledger records exactly what
was implemented, what is partial with the specific gap named, and what was declined with
the reasoning, so a decision can be revisited rather than rediscovered.

[:octicons-arrow-right-24: The full ledger: `docs/ROADMAP_STATUS.md`](../ROADMAP_STATUS.md)

This page holds the summary, the declined items and the 1.0 questions. The ledger holds
every item's status and the precise gap where one remains.

## Summary

| Status | Proposal items | Ledger entries |
|---|---:|---:|
| Implemented with no caveat | 130 | — |
| Working with a named gap | 17 | 12 |
| Declined, with reasoning recorded | 3 | 4 |
| Deferred, with no placeholder | 0 | 0 |
| **Total** | **150** | |

The two columns differ because a ledger entry can cover several proposal items — 29, 30
and 37 share one, as do 112 and 113 — and because item 16 is recorded as two entries, its
autotuning half delivered in a narrower form and its benchmarking half declined. Each
item is counted once above, under the strongest caveat that applies to it: items 4 and 14
appear in the ledger's implemented narrative *and* in the gap list, because part of each
shipped and part did not, and they are counted here as gaps.

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

## What stands between 0.x and 1.0

*This section lives here, in `docs/about/roadmap.md`, not in the
[150-item ledger](../ROADMAP_STATUS.md).*

Numerisect is at 0.x: the minor number carries the weight, and the version text says so.
**The bar for 1.0 has not been set**, and this section does not set it — it records what
is actually left, so that whoever sets it is choosing from facts.

The remaining distance is **not** more mathematics. Of the twelve items that still carry
a named gap, none is a missing computation; they divide into two kinds, and only one kind
can be closed:

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

So whatever 1.0 comes to mean here, it is a decision about the interface and about
stability rather than about capability. Four questions are open, and none has been
answered yet:

- **Does 1.0 promise a stable API?** Route paths and response keys can change today, and
  several have within 0.x. Promising otherwise is the single largest commitment on this
  list, because it binds every future release.
- **Do the closeable presentation gaps have to be built, or is declining them in writing
  enough?** Either settles an item; leaving it "partial" indefinitely does not.
- **Should the permanent limits be restated outside this ledger**, in the capability index,
  so a reader cannot mistake a bounded search for an unfinished one?
- **Does the published artifact need to be installed and exercised on each supported
  platform** from the release archive rather than from a checkout? CI does not do that
  today.

Until someone decides, the practical rule is unchanged and comes from the version text
rather than from this page: a feature release raises the minor number.

## Honest limits

Numerisect is an experimental, source-distributed pre-release with no official binary
packages. It is exercised on Fedora Linux x86-64 and by GitHub Actions on Ubuntu Linux
x86-64 and ARM64, Ubuntu 24.04 x86-64 inside Windows WSL, and macOS on ARM64 and Intel.
Native Windows remains unsupported, and the Arch Linux installer path has not yet
received clean-host CI verification.
