# The interface

Numerisect has five top-level views, each with its own hash route so any page can be
linked or bookmarked.

| View | Route | What it holds |
|---|---|---|
| **Factor integers** | `#factor` | Single and batch factorization, the expert laboratory, SQUFOF, ECM campaigns, distributed sieving |
| **Prime tools** | `#primes/<tool>` | 133 individually routed pages in 11 searchable groups |
| **Riemann zeta** | `#zeta/<tool>` | 22 pages covering rigorous evaluation, zeros, and L-functions |
| **System diagnostics** | `#diagnostics` | Engine availability, versions, prerequisites, and the engine self-test |
| **Workspaces & history** | `#workspaces` | Saved sessions, searchable job and report history, performance history, notifications |

## Prime tools navigation

The 11 groups are: primality and navigation, primality laboratories, prime generation,
patterns and distribution, analytic prime distribution, prime structures, arithmetic and
factors, modular and polynomial algebra, algebraic primes, advanced explorations, and
visualization and education.

Only one operation is visible at a time, and each has a direct hash route such as
`#primes/prime-check` or `#primes/prime-reciprocal`. A search box filters the navigation;
on narrow screens a compact selector replaces the sidebar.

## Reading a result panel

Results appear immediately below the form that produced them, never elsewhere. Each panel
carries:

- The values, with their strength labelled.
- A note stating what was computed, by which engine, and what the result does and does
  not establish.
- The exact `output/<filename>` where the report was saved.
- A download link.

Where a search stopped at a bound, the panel says so and gives the continuation point.

## The status line

The top of the interface shows which engine executables are available. If any are
missing, an installation banner offers to build them from pinned commits after explicit
confirmation.

## Long-running work

Factorizations run as jobs. You get live engine logs, phase and progress reporting,
cancellation, pause and resume, priority and queue reordering, and per-job CPU, memory
and wall-clock limits. CADO-NFS jobs resume from parameter snapshots.

Only one CPU-heavy job runs at a time unless you raise
`NUMERISECT_MAX_PARALLEL_JOBS`.

## After updating

Restart the server and reload the page. The application shell and its assets are served
with `no-store`, but a document already open in a tab is not replaced by restarting the
server behind it.
