# Architecture

This page describes how a request becomes an engine invocation, and why the layers are
divided the way they are.

## The governing rule

Every feature is decided in this order:

1. **Use an existing library routine.** Search the installed engines first and prefer the
   routine the library authors optimized.
2. **Only if no library provides it, write optimized C or C++** using GMP and FLINT,
   exposed through a narrow subprocess boundary.
3. **Python and JavaScript are interface, API and orchestration only.** Neither computes
   a mathematical result, ever.

This is enforced by the test suite, not merely documented. `test_native_computation_policy.py`
asserts that no third-party mathematics library is imported, that every mathematical
module dispatches to an engine and names the routine that computes its results, that
transport and formatting layers decide nothing mathematical, that JavaScript never defines
a primality test, and that every `Math.*` call in the browser is canvas geometry.

## The path of a request

```text
browser form
    ↓  fetch with the per-launch session token
FastAPI route            validates input, bounds every parameter
    ↓
Python boundary module   builds the engine call, launches it, parses tagged output
    ↓
native engine            PARI/GP, FLINT/Arb, YAFU, CADO-NFS, or a compiled helper
    ↓
tagged output            TAG:value lines ending in a completion marker
    ↓
Python boundary module   validates completeness, raises on a missing marker
    ↓
outputs.py               writes a plain-text report, returns output/<filename>
    ↓
browser                  renders the returned values; computes nothing
```

## The tagged-output protocol

Engines and Numerisect communicate through lines of the form `TAG:value` or
`TAG:a|b|c`, ending with a completion marker such as `DONE:` that carries a count.

Two rules make this reliable:

- **The completion marker is mandatory.** Its absence is an error, never an empty
  successful result. A run killed by a timeout cannot look like a search that found
  nothing.
- **Counts are checked.** The number of records parsed must equal the count the engine
  reported, or the result is rejected as inconsistent.

Searches that stop at a bound set an explicit truncation flag, so a partial list is never
mistaken for a complete one.

## Why a subprocess boundary

Engines run as separate processes in their own process group, invoked with argument
arrays rather than shell strings. This buys several things at once: a hostile input
cannot reach a shell; a runaway engine can be cancelled by signalling its group; per-job
CPU, memory and wall-clock limits can be applied before `exec`; and a crash in a native
library cannot take the application with it.

Long-running work goes through the job system, which persists state in SQLite, streams
engine logs, supports cancellation and pause, and resumes CADO-NFS from parameter
snapshots.

## What Python is allowed to do

Validation, process launch, tagged-output parsing, persistence, HTTP, and formatting.
Integer expressions are parsed by an audited AST walker that accepts only integer
literals and the operators `+ - * // % **`, with no names, calls or floats, and with
node-count, exponent and bit-length limits.

Bookkeeping such as grouping job runtimes into digit buckets is not a mathematical
result and is permitted. Deciding divisibility, primality or a gcd is not.

## What JavaScript is allowed to do

Render. It may map engine-supplied integers and flags to canvas coordinates and colours,
animate the playback of a step trace an engine produced, and format strings. Spiral
coordinates are layout; which integers are prime is not, and that always arrives from an
engine.

## Persistence and provenance

Every operation that produces a result saves a plain-text report and returns its exact
`output/<filename>` path. Completed factorizations additionally produce a JSON manifest
recording the commands run, the pinned engine revisions, the SHA-256 of each executable
used, the parameters, and the resulting factors, so a result can be reproduced and
audited later.

[:octicons-arrow-right-24: Security model](../SECURITY_MODEL.md)
