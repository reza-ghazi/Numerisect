# Roadmap and scope

Numerisect was built against a 150-item feature proposal. The ledger records exactly what
was implemented, what is partial with the specific gap named, and what was declined with
the reasoning, so a decision can be revisited rather than rediscovered.

[:octicons-arrow-right-24: The full ledger](../ROADMAP_STATUS.md)

## Summary

| Status | Count |
|---|---:|
| Fully implemented | 130 |
| Working with a named gap | 13 |
| Declined, with reasoning recorded | 4 |
| Deferred | 0 |

Beyond the proposal, an audit compared what the installed libraries expose against what
the application calls, and closed the gaps that fall within the subject: a prime-counting
algorithm comparison, integer-structure predicates, `factorint` strategy flags, and a
binary quadratic forms and continued fractions workbench.

Three additions are not wrappers around an engine at all: cross-engine verification, the
engine self-test, and prime enumeration above primesieve's \(2^{64}\) ceiling.

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

## Honest limits

Numerisect is an experimental, source-distributed pre-release with no official binary
packages, exercised on Fedora Linux x86-64. Windows WSL and macOS paths are implemented
but unverified by the project.
