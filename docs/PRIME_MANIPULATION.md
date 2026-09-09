# Prime manipulation tools

The Prime Tools audit covered the navigation catalogue, forms, API routes,
native implementations, and existing tests. Existing operations already cover
single and indexed primality/navigation, fixed-size and special generation,
intervals, classifications, tuples and gaps, digit and polynomial searches,
reciprocals, Gaussian primes, arithmetic profiles, witnesses, and bounded
explorations. Zeta analysis remains in its own application section.

The additions below fill practical gaps without duplicating those operations.
This is an incremental feature audit, not a claim that every number-theory
operation or arbitrary input has been exhaustively tested.

| Page | Route | What it adds |
| --- | --- | --- |
| Check a list of integers | `/#primes/prime-batch` | One native batch, retaining input order and duplicates |
| Primes in a residue class | `/#primes/prime-progression` | Deterministic interval search for `p ≡ r mod m` with continuation and exact page sum |
| Calculate modulo a prime | `/#primes/prime-modular` | Inverse, power, order, square roots, and a primitive root |

These pages belong to **Primality & navigation**, **Prime generation**, and
**Divisors & arithmetic functions**, respectively. The complete Prime Tools catalogue has
133 pages in 11 groups. On mobile, the operation selector replaces the desktop sidebar.

## Indexed navigation before or after an integer

The existing **Primes near a number** page (`/#primes/prime-nearby`) now has
two output modes: **Find the nth prime** and **List consecutive primes**.
The start is always excluded. The 100th prime after 1289 is 2039; the 50th prime
before 98798 is 98221. Position 1 means the nearest prime in that direction.
If a backward search reaches 2 before finding n primes, it reports that the
requested prime does not exist.

`POST /api/primes/nth-near` accepts:

```json
{"start":"1289", "index":100, "direction":"after"}
```

Unlike the three decimal-only tools below, navigation accepts the existing
restricted integer-expression syntax. Position is limited to 1–100,000 and
the shared one-hour subprocess timeout applies. GP performs the walk and
proves every counted candidate; the interface receives only the selected prime.
Successful responses include `value`, `label`, and `output_file`.

## Input, correctness, and resources

All new mathematical operations live in `numerisect/prime_structures.gp`.
`numerisect/prime_manipulation.py` validates decimal inputs, runs GP, checks
completion tags, and formats output. Python and JavaScript do no mathematical
searches for these additions. PARI/GP's native `isprime`, `ispseudoprime`, modular
arithmetic, `issquare`, `sqrt`, `znorder`, and `znprimroot` provide the computations.
See the [official PARI/GP arithmetic reference](https://pari.math.u-bordeaux.fr/dochtml/html-stable/Arithmetic_functions.html).
Order and generator calculations enable proven factorization.

Each new operation runs a single GP subprocess, with a user-selected time limit
of 1–3,600 seconds (60 by default), and the shared GP 256 MB initial stack.
These tools have no parallel thread control or interactive cancellation;
the process is terminated and reaped when its timeout expires. Large moduli
may be expensive to prove, and orders/generators may require factoring `p−1`.
Timeouts, native errors, and incomplete output fail explicitly and do not
produce successful reports or negative mathematical conclusions.

Inputs are signed decimal integers, up to 100,000 characters each; formulas are
not accepted on these three pages. Mathematical values use arbitrary precision
and travel through JSON as decimal strings. Batch input is limited to 200,000
characters total and 1,000 entries. Spaces, commas, semicolons, and newlines
separate entries. Fast positive results are labeled probable primes; rigorous
positive results are proven. Integers below 2 are neither prime nor composite.

Progression intervals are inclusive. The modulus must be positive; residues
are normalized in GP. A scan can cover at most 1,000,000 progression candidates
and return at most 100,000 primes. If `gcd(r,m)>1`, GP checks the only possible
prime directly. A result-limit boundary supplies the first omitted prime as
`next_start`. Reuse it as the next inclusive start with the other parameters
unchanged. The sum always covers only returned primes, not omitted pages.

Modular zero has no inverse or multiplicative order. Negative powers require
a nonzero residue. Exponent zero uses the GP convention `a^0=1`, including
`a=0`. Square-root results include all distinct nonnegative roots, including
the single root for zero or modulus 2. An empty completed result means no
square root exists. A primitive root is a generator, not necessarily the
smallest generator. Composite, negative, and unit moduli are rejected.

## Examples and API

`POST /api/primes/batch-check`:

```json
{"integers":"13, 561, 1, -7, 13", "mode":"proven", "timeout_seconds":60}
```

The two 13 entries are proven primes; 561 is composite; 1 and −7 are neither.

`POST /api/primes/progression`:

```json
{"start":"1", "end":"30", "modulus":"4", "residue":"1", "limit":2}
```

Returns 5 and 13, exact page sum 18, and continuation start 17. The next page
contains 17 and 29.

`POST /api/primes/modular`:

```json
{"modulus":"7", "value":"2", "operation":"roots"}
```

Returns 3 and 4. Other `operation` values are `inverse`, `power`, `order`, and
`generator`; `power` uses the decimal-string `exponent` field.

## Results and verification

Each page shows its own result table. The browser previews up to 2,000 rows;
the report contains every returned row, input context, notes, and metrics.
The result panel explicitly confirms `output/<filename>` and offers a download.
Failures do not create reports. An empty completed search does save a report.

Regression tests cover examples, values above 64 bits, input validation,
nonpositive integers, duplicate rows, composite moduli, all modular operations,
progression bounds and continuation, non-coprime classes, output completeness,
timeouts, API failures, and downloadable reports.

The application-wide suite currently contains 800 passing tests. A separate
static navigation audit covers all 133 Prime Tools pages and
submitted the three new forms against real GP endpoints, checked local result
placement and saved-path notices, and checked mobile width handling.

For installing a versioned copy on Linux, Windows WSL, or macOS, see
[Installation and versioning](INSTALLATION.md).
