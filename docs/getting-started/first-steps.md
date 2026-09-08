# First steps

A short tour by example. Each of these takes seconds and shows a different part of the
application.

## Factor an integer

Enter an integer or a safe expression in **Factor integers** and submit. Supported
operators are `+ - * // % ^ **` with parentheses; function calls, names and floating
point are rejected.

Try `2^101-1`. Numerisect routes it automatically: below 95 decimal digits it runs YAFU,
above that it runs an ECM pretest and then SIQS or CADO-NFS on the residual.

The result gives you an equation view, a factor list with each factor's primality status
and discovering engine, a text report, and a JSON manifest recording the commands, engine
revisions and executable checksums used.

!!! tip "Before starting a hard factorization"

    Ask the strategy adviser first. It screens for small factors, perfect powers and
    special forms, then recommends an engine and estimates the size of any remaining
    factor. For `2^101-1` it will tell you the number has a special form and hand you the
    SNFS polynomial, which is far cheaper than general NFS.

## Test primality

In **Prime tools → Primality & navigation**, enter `32416190071`.

Two modes matter:

- **Rigorous** uses `isprime`. A positive answer is a proof.
- **Fast** uses Baillie–PSW. A positive answer is a *probable* prime.

Rigorous mode can export a certificate, which Numerisect re-verifies independently rather
than trusting.

## Cross-check a result

Independent agreement is stronger evidence than any single answer. Try **Cross-check
π(x)** with `10^10`.

Eight method outputs run: six mathematically distinct algorithms in primecount, plus
primesieve's direct sieve and PARI's own counter. These represent three independent
engine implementations, and all should return 455052511.

If they ever disagree, Numerisect reports every value and refuses to pick a winner. A
majority of implementations sharing a bug is exactly what a vote would hide.

## Enumerate primes above 2⁶⁴

**Primes in a large interval** with start `10^30` and length `100000`.

primesieve cannot answer this at all; it refuses inputs at or above \(2^{64}\). PARI can,
but single-threaded and slowly. The project's own sieve presieves the window by small
primes and tests the survivors with Baillie–PSW in parallel.

Results at this magnitude are labelled **probable**, not proven. Pass any individual one
to the primality tools for a proof.

## Look at something

**Visualization & education** draws the Ulam, Sacks and polar spirals, the Eisenstein
lattice, modular wheels and residue heatmaps, and animates the sieves of Eratosthenes,
Sundaram and Atkin.

Every number in these pictures comes from an engine. The browser maps integers to
coordinates and colours; it never decides which integers are prime.

## Work from the command line

Everything the browser can do is reachable headlessly:

```bash
numerisect prime 32416190071 --certificate
numerisect --json factor 8051 --engine pari_trial --trial-bound 100
numerisect routes --filter /api/primes
numerisect --json api post /api/primes/check --data '{"expression":"2^89-1","mode":"proven"}'
```

`numerisect api` drives the same application in-process, so every route is available
without starting a server.

## Where results go

Every operation saves a plain-text report and tells you its exact `output/<filename>`
path. The download button is a convenience, not the only record. Reports are indexed and
searchable, and can be exported as CSV, JSON, JSON Lines, Markdown, LaTeX or
PARI-compatible syntax.

[:octicons-arrow-right-24: Interface tour](interface.md)
