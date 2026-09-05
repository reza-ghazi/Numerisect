# Prime exploration and notebook problems

Numerisect imports the useful operations from `primes_gap.ipynb` and
`prime_problems.ipynb` without retaining their Python/SymPy calculations or
dependence on a pre-generated prime file. PARI/GP generates and proves primes,
factors integers, and computes statistics. JavaScript only renders the native
results.

## Navigation

Use **Patterns & distribution** for gap statistics (`/#primes/gap-statistics`)
and Goldbach (`/#primes/goldbach`), **Prime generation** for primorials
(`/#primes/primorial`) and random-range sampling (`/#primes/random-range`),
and **Advanced explorations** for contiguous digits (`/#primes/contiguous-digits`)
and bounded problems (`/#primes/prime-problem`). Each operation occupies one
page with its result and saved-report path immediately below the form.

## Prime-gap statistics

The existing gap analyzer lists consecutive prime pairs. The new distribution
tool additionally calculates, inside PARI/GP:

- exact frequencies for every observed gap size;
- minimum and maximum;
- exact rational mean and median; and
- the mode and its frequency.

The browser draws a frequency chart from that table. A result limit bounds the
number of consecutive gaps scanned per request and returns truncation status.
No external `primes_to_1e7_list.txt` file is required.

## Primorials

The primorial generator starts with 2 and repeatedly obtains the next proven
prime, producing `2`, `6`, `30`, `210`, `2310`, and so on. Products use PARI's
arbitrary-precision integers. Up to 500 cumulative products may be requested.

## General prime operations reused

The notebooks' prime range/list/generator cells reuse Numerisect's existing
range endpoint. **Primes near a number** (`/#primes/prime-nearby`) offers
**Find the nth prime** and **List consecutive primes**, in either direction.
It excludes the starting integer and reports exhaustion when a backward search
has too few primes. General k-gap pairs use custom tuple offsets such as `[0,40]`.

For deterministic searches within one modular residue class, including exact
sums and continuation points, see [Prime manipulation](PRIME_MANIPULATION.md).

The random-range tool fills one missing variant: it samples distinct primes
inside arbitrary-precision endpoints and rigorously rechecks every value with
`isprime` before returning it.

## Digit substrings and Goldbach partitions

The contiguous-digit tool tests every distinct substring of the absolute
decimal input, without reordering its digits. Inputs are limited to 1,000
digits because the number of substrings is quadratic.

The Goldbach tool accepts one even integer greater than two and returns unique
pairs `p ≤ q` with `p+q=n`, rigorously proving both members. This is a bounded
verification for the supplied number and is never presented as a proof of the
Goldbach conjecture.

## Four bounded problem searches

| Problem | Native condition |
|---|---|
| Prime-square equation | Find primes `r<q<p` satisfying `p²+1=q²+r²`. |
| Fourth-power sums | Find prime values `a⁴+b⁴` with positive `a≤b`. |
| Three prime factors | Find `n` for which `Ω(n²−1)=3`, counting multiplicity. |
| Square divisor sum | Among the first requested prime candidates, find p for which `σ(p⁴)=p⁴+p³+p²+p+1` is a square. |

The equation search caps `p` at 100,000 per request; the fourth-power result
bound is at most `10^12`; the factor search spans at most 1,000,000 integers;
and the divisor-sum search considers at most the first 1,000,000 primes. Result
limits protect the browser and report size. These are resource controls for
finite searches, not fixed-precision arithmetic limitations.

## API routes

```text
POST /api/primes/gap-statistics
POST /api/primes/primorials
POST /api/primes/random-range
POST /api/primes/contiguous-digits
POST /api/primes/goldbach
POST /api/primes/problems
```

Every successful response includes `output_file`, and the browser explicitly
shows that the report was saved to `output/<filename>`.
