# Independent verification and large-interval sieving

Most of Numerisect exposes what one engine can do. The tools on this page do something
no single engine can do for itself.

## Cross-checking a result across independent implementations

An engine cannot tell you it is right. Several independent implementations agreeing can.
Numerisect has enough engines to ask the same question several ways.

### pi(x)

`POST /api/verify/prime-count` computes pi(x) with eight independent sources where all
are installed:

| Source | Method |
|---|---|
| primecount `--legendre` | Legendre's formula, 1830s |
| primecount `--meissel` | Meissel's refinement, 1870 |
| primecount `--lehmer` | Lehmer's method, 1959 |
| primecount `--lmo` | Lagarias, Miller and Odlyzko, 1985 |
| primecount `--deleglise-rivat` | Deléglise and Rivat, 1996 |
| primecount `--gourdon` | Gourdon, 2001 |
| primesieve `--count` | direct sieving |
| PARI/GP `primepi` | a separate implementation, used up to 10^12 |

All eight agreeing on pi(10^8) = 5761455 is meaningful evidence. **A disagreement means
one engine is faulty, and Numerisect will not pick a winner**: it reports every value,
marks the result unreliable, and tells you to run the self-test. It never takes a majority
vote, because a majority of implementations sharing a bug is exactly the case a vote
would hide.

Timings are reported per source. They are local measurements on one machine with one
thread count and one set of builds, not a benchmark of the algorithms.

### Primality

`POST /api/verify/primality` decides primality three ways: PARI's `isprime`, which is a
proof; PARI's `ispseudoprime`, which is Baillie-PSW; and GMP's independent
Baillie-PSW plus Miller-Rabin implementation. The response marks which results are proofs
and which are probable. A disagreement between a proof and a probabilistic test would be
either a genuine discovery or, far more likely, a broken engine build.

## Engine self-test

`POST /api/verify/self-test` asks each installed engine questions whose answers are
published constants: pi(10^6) = 78498, pi(10^7) = 664579, pi(10^10) = 455052511, the
millionth prime 15485863, 8051 = 83 × 97, phi(2310) = 480, and the period of 1/7.

This catches a miscompiled library, a wrong architecture flag, or a subtly broken build
**before** its output is trusted. Every expected value carries a citation in the response
so you can check the constant itself rather than taking Numerisect's word for it.

The mechanism earned its place during development: it immediately caught a wrong
expected constant that had been written into it, which is the same failure mode it exists
to detect.

## Enumerating primes in an interval of any size

`POST /api/primes/sieve-interval` uses `numerisect/native/numerisect_bigsieve.c`, a GMP
and OpenMP program in this project.

### Why it exists

Numerisect uses an existing library wherever one serves, and for prime enumeration that
library is primesieve. But primesieve is strictly a 64-bit tool:

```text
$ primesieve 18446744073709551617 -d 1000 --count
Error: 64-bit unsigned integer overflow detected
```

Above 2^64 the only remaining option in the installed set is PARI's `forprime`, which is
single-threaded and much slower there. Measured on this machine over a 10^6-wide window:

| Interval near | Method | Time |
|---|---|---:|
| 10^12 | PARI `forprime` | 7 ms |
| 10^30 | PARI `forprime` | 916 ms |
| 10^30 | this helper, 1 thread | 350 ms |
| 10^30 | this helper, 24 threads | 40 ms |

Both found 14496 primes, which is itself an independent cross-check.

### Method

The window is presieved by every prime up to a small bound, which removes about 92% of
candidates when that bound is 10^6. Each survivor is then tested with Baillie-PSW through
GMP. Both phases run in parallel: the window is split into contiguous chunks so no two
threads write the same byte, and survivor tests are distributed dynamically because their
cost varies.

### Proven versus probable

**At or above 2^64 the results are probable primes, not proofs.** GMP's test is
Baillie-PSW plus Miller-Rabin rounds. No BPSW pseudoprime is known, but none is proven
not to exist. The response sets `proven: false` and `status: "probable"` and says so in
its note. Below 2^64 the same test is exact and the response says `status: "exact"`.

To prove any individual result, pass it to the primality tools, which use PARI's
`isprime`.

### Limits

| Limit | Value |
|---|---:|
| Interval length | 100,000,000 |
| Start magnitude | 400 decimal digits |
| Presieve bound | 100 to 100,000,000 |
| Threads | 1 to 1024 |
| Extra Miller-Rabin rounds | 0 to 64 |

The interval is **half-open**, `[start, start + length)`. primesieve's `-d` is inclusive,
so comparisons against it need one fewer.

The saved report holds every prime found; the HTTP response is capped by the `preview`
field so a large run does not travel through JSON and the browser.
