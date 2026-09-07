# Primality laboratory

Numerisect 0.5.0 adds a dedicated PARI/GP computational layer in
`numerisect/primality_lab.gp` with the Python boundary
`numerisect/primality_lab.py`. Python validates requests, launches `gp` under a
bounded wall-clock timeout, requires the mandatory `DONE:` completion marker,
parses the tagged protocol, and persists reports. JavaScript renders only. No
mathematics is performed in Python or JavaScript.

Every operation has one Prime Tools route under `/api/primality-lab/*`, and its
result appears directly below the submitted form together with the exact
`output/<filename>` path of the saved report.

!!! note "A limitation in PARI's certificate export"

    `primecertexport` renders ECPP certificates but not N−1 certificates: PARI 2.18
    answers *"sorry, N-1 certificate is not yet implemented"*. Numerisect therefore
    passes N−1 certificates only to `primecertisvalid` for verification, and exports
    only ECPP certificates. A test enforces this.

    For inputs below 2^64, `primecert` returns the number itself and the export reads
    *"Indeed, ispseudoprime(N) = 1 and N < 2^64"*. That is the exhaustive verification
    of the BPSW range being used as a theorem rather than a computed certificate chain.

## Native engines and library routines

| Feature | Roadmap | Library routine performing the computation |
|---|---|---|
| Comparison laboratory | 21 | `ispseudoprime` (Baillie–PSW), `isprime(n, 2)` (APR-CL), `isprime(n, 3)` (ECPP), `kronecker`, PARI `Mod` modular powering. The individual Fermat, Solovay–Strassen, Miller–Rabin, Lucas, strong Lucas and Frobenius steps are driven in GP because PARI reports only a combined verdict and this page exists to show each step. |
| Deterministic witnesses | 22 | `primes`, `valuation`, `Mod` powering; cross-checked against `isprime`. |
| Pocklington proof | 23 | `factor`, `isprime`, `gcd`, `Mod`; cross-checked with `primecert(n, 1)` and `primecertisvalid`. |
| Pratt certificate tree | 24 | `factor`, `znprimroot`, `ispseudoprime`, `Mod` powering. |
| Certificate verification | 23, 24 | `isprime`, `gcd`, `Mod` powering, re-derived from the certificate alone. |
| Proth and generalized Proth | 27, 33 | `kronecker`, `factor`, `Mod`; cross-checked against `isprime`. |
| Lucas sequences, N−1/N+1 | 28 | PARI matrix powering over `Mod` for the Lucas sequences (PARI 2.18 publishes no `lucasU`/`lucasV`), `kronecker`, `factor`, `isprime`. |
| Probable-prime taxonomy | 29 | `ispseudoprime`, `kronecker`, `Mod` powering, `isprime` for the rigorous reference. |
| Carmichael analyzer | 30 | `factor`, `znstar` (λ(n) is the largest invariant factor of (ℤ/nℤ)×), `eulerphi`, `gcd`. |
| Chernick construction | 30 | `isprime`. |
| Generalized repunits | 36 | `ispseudoprime`, `isprime`. |
| Sierpiński/Riesel explorer | 37 | `ispseudoprime`, `isprime`, `factor`, `Mod` powering. |
| Bi-twin chains, prime ladders | 40 | `isprime`, `digits`. |
| Constrained prime construction | 42, 43 | `nextprime`, `ispseudoprime`, `isprime`, `primecert`, `primecertisvalid`, `primecertexport`. |
| Lucas–Lehmer proof viewer | 130 | GP iteration; PARI publishes no Lucas–Lehmer routine and the residue trace is the point of the page. |
| ECPP proof viewer | 130 | `primecert`, `primecertisvalid`, `coredisc`. |
| Prime k-tuplets | 14 | `primesieve --print=<k>` below 2⁶⁴; PARI `forprime`/`isprime` otherwise. |

## Result semantics

Every page reports one of three verdicts, and the distinction is preserved end
to end:

- **proven prime / proven composite** — a rigorous PARI proof (APR-CL, ECPP,
  `primecert`), or a criterion that is necessary and sufficient for the input
  form (Lucas–Lehmer for Mersenne numbers, Proth's theorem for `k·2ⁿ + 1` with
  odd `k < 2ⁿ`, Korselt for Carmichael numbers, a verified Pocklington, Pratt or
  N+1 certificate, or a complete deterministic Miller–Rabin witness set inside
  its published bound).
- **probable prime** — a compositeness test was passed (Fermat, Euler–Jacobi,
  Miller–Rabin, Lucas, strong Lucas, Frobenius, Baillie–PSW). A pass is evidence,
  never a proof, and is labelled `probable` in the result table.
- **inconclusive** — a time budget expired, a search bound or node limit was
  reached, or the applied criterion simply yields no verdict for this input.
  An inconclusive result is never presented as a negative one.

Concrete consequences worth knowing:

- Exhausting the exponent bound in the Sierpiński/Riesel search does **not**
  prove that `k` is a Sierpiński number. Only a verified covering set does.
- Proth's theorem returns no verdict when `N` is a perfect square, because no
  base has Jacobi symbol −1. The page reports inconclusive and shows the
  independent `isprime` cross-check separately.
- A Lucas pseudoprime such as 4181 = 37 × 113 passes the Lucas test for
  `P = 1, Q = −1`; with Jacobi symbol +1 no N+1 proof applies, so the verdict is
  inconclusive rather than prime.
- Reaching the Pratt node limit or a factoring timeout truncates the certificate
  tree and yields inconclusive.

### Deterministic Miller–Rabin witness sets

The engine holds these published sufficient sets of the first *k* primes:

| n below | Bases | Source |
|---|---|---|
| 2,047 | 2 | folklore; 2047 = 23 × 89 is the smallest base-2 strong pseudoprime |
| 1,373,653 | 2, 3 | Pomerance, Selfridge & Wagstaff (1980) |
| 25,326,001 | 2, 3, 5 | Pomerance, Selfridge & Wagstaff (1980) |
| 3,215,031,751 | 2, 3, 5, 7 | Jaeschke (1993) |
| 2,152,302,898,747 | 2, 3, 5, 7, 11 | Jaeschke (1993) |
| 3,474,749,660,383 | 2, 3, 5, 7, 11, 13 | Jaeschke (1993) |
| 341,550,071,728,321 | first 7 primes | Jaeschke (1993) |
| 3,825,123,056,546,413,051 | first 9 primes | Jiang & Deng (2014) |
| 318,665,857,834,031,151,167,461 | first 12 primes | Sorenson & Webster (2015) |
| 3,317,044,064,679,887,385,961,981 | first 13 primes | Sorenson & Webster (2015) |

References: G. Jaeschke, *On strong pseudoprimes to several bases*, Math. Comp.
61 (1993) 915–926; C. Pomerance, J. L. Selfridge and S. S. Wagstaff Jr.,
*The pseudoprimes to 25·10⁹*, Math. Comp. 35 (1980) 1003–1026; Y. Jiang and
Y. Deng, *Strong pseudoprimes to the first eight prime bases*, Math. Comp. 83
(2014) 2915–2924; J. Sorenson and J. Webster, *Strong pseudoprimes to twelve
prime bases*, Math. Comp. 84 (2015) 2483–2498.

Above the largest tabulated bound no sufficient set is known, so the page reports
`inconclusive` and points at APR-CL or ECPP; it never downgrades to "probable".

### Covering sets

`78557·2ⁿ + 1` is divisible by a member of Selfridge's covering set
{3, 5, 7, 13, 19, 37, 73} for every `n`, with period 36; this is the standard
proof that 78557 is a Sierpiński number (J. L. Selfridge, 1962; see also
W. Sierpiński, *Sur un problème concernant les nombres k·2ⁿ + 1*, Elem. Math. 15
(1960) 73–74). The Riesel counterpart is `509203·2ⁿ − 1` with the covering set
{3, 5, 7, 13, 17, 241} and period 24 (H. Riesel, 1956). Leaving the covering
primes empty makes the engine use the prime divisors of `2^period − 1` instead.

The page verifies exactly that every residue class of `n` modulo the period is
covered and that every covering prime has multiplicative order dividing the
period; it does not search for covering sets.

## Bounds and timeouts

Bounds are deliberate resource controls, not mathematical claims. Every route
has both an in-engine PARI `alarm` budget (`budget_seconds`, 1–3,600) and a
wall-clock subprocess limit (`timeout_seconds`, 1–3,600). A missing `DONE:`
marker is an error; a timeout is inconclusive.

| Route | Input bounds | Default budget / timeout |
|---|---|---|
| `POST /api/primality-lab/compare` | `n ≥ 2`, 1–32 bases | 30 s / 300 s |
| `POST /api/primality-lab/deterministic-witnesses` | `n ≥ 2` | — / 300 s |
| `POST /api/primality-lab/pocklington` | `n ≥ 3`, witness limit 2–100,000 | 60 s / 300 s |
| `POST /api/primality-lab/pratt` | `n ≥ 2`, node limit 1–100,000 | 60 s / 300 s |
| `POST /api/primality-lab/verify-certificate` | vector of integers, ≤ 200,000 characters | — / 300 s |
| `POST /api/primality-lab/proth` | `k ≥ 1`, `1 ≤ n ≤ 10⁶`, `2 ≤ b ≤ 10⁶` | 60 s / 300 s |
| `POST /api/primality-lab/proth-search` | exponents 1–100,000, limit 1–10,000 | 60 s / 600 s |
| `POST /api/primality-lab/lucas-sequence` | odd `n ≥ 3`, `|P|, |Q| ≤ 10⁶` | 60 s / 300 s |
| `POST /api/primality-lab/taxonomy` | odd `n ≥ 3`, 1–32 bases | 60 s / 300 s |
| `POST /api/primality-lab/carmichael` | `n ≥ 3`, base scan 2–10⁷ | 60 s / 300 s |
| `POST /api/primality-lab/chernick` | `1 ≤ k ≤ 10⁸`, limit 1–10,000 | — / 300 s |
| `POST /api/primality-lab/repunit` | `2 ≤ b ≤ 10⁶`, exponents 1–100,000 | 60 s / 600 s |
| `POST /api/primality-lab/sierpinski` | `k ≥ 1`, exponent bound 1–100,000 | 30 s / 600 s |
| `POST /api/primality-lab/covering-set` | period 1–1,000, ≤ 64 covering primes | — / 300 s |
| `POST /api/primality-lab/bitwin-chains` | interval ≤ 10⁹ candidates, length 1–32 | — / 600 s |
| `POST /api/primality-lab/prime-ladder` | equal-width primes, ≤ 9 digits, depth 1–100 | — / 300 s |
| `POST /api/primality-lab/constrained-prime` | 8–1,024 bits (≥ 32 for strong), candidates 1–10⁷ | 60 s / 600 s |
| `POST /api/primality-lab/lucas-lehmer-steps` | `2 ≤ p ≤ 100,000`, 0–10,000 displayed steps | — / 600 s |
| `POST /api/primality-lab/ecpp-steps` | `n ≥ 2` | 120 s / 600 s |

Values wider than 20,000 digits (5,000 for Lucas–Lehmer residues) are withheld
from result tables and reported as such; the verdict is unaffected. Browser
tables show at most 2,000 rows while the saved report retains every returned row.

## High-performance k-tuplet sieving

`prime_tuples_in_range` routes standard constellations to `primesieve`
(`--print=2`, `--print=4`, `--print=6`) whenever the whole interval lies below
2⁶⁴. primesieve is exhaustive and exact in that range, so the results stay
proven. Only sizes with a unique admissible pattern take that path: primesieve
emits both admissible triplet shapes ({0,2,6} and {0,4,6}) together and both
quintuplet shapes ({0,2,6,8,12} and {0,4,6,10,12}) together, and separating them
would require offset arithmetic outside the engines, so those sizes and every
custom offset pattern continue to use PARI `forprime`/`isprime`.

## Cryptographic prime construction is experimental

The constrained-prime page is an educational tool. **It is not audited
cryptographic software and must not be used to generate production keys.**
Python's only use of randomness is a `secrets.randbits` draw for the search seed;
PARI/GP places that seed inside the requested bit interval and performs every
primality decision. Supplying an explicit `seed` makes a run reproducible.
Supported structures are unconstrained primes, safe primes `p = 2q + 1` with `q`
proven prime, and Gordon strong primes built from auxiliary primes `s`, `t` and
`r = 2it + 1`. A residue condition `p ≡ r (mod m)` may be combined with any of
them; PARI rejects a residue condition that is incompatible with Gordon's step
`2rs`.

## API examples

All routes are loopback-only and require the per-process token from
`GET /api/session`; the browser uses the `SameSite=Strict` cookie, and curl needs
the `X-Numerisect-Token` header.

```bash
token=$(curl -s http://127.0.0.1:8765/api/session | python3 -c 'import json,sys;print(json.load(sys.stdin)["request_token"])')

# Item 22: 3215031751 is the smallest strong pseudoprime to 2, 3, 5 and 7.
curl -s -X POST http://127.0.0.1:8765/api/primality-lab/deterministic-witnesses \
  -H "X-Numerisect-Token: $token" -H 'Content-Type: application/json' \
  -d '{"number": "3215031751"}'

# Item 21: compare every test on the same input.
curl -s -X POST http://127.0.0.1:8765/api/primality-lab/compare \
  -H "X-Numerisect-Token: $token" -H 'Content-Type: application/json' \
  -d '{"number": "3215031751", "bases": ["2", "3", "5", "7", "11"], "budget_seconds": 30}'

# Item 23: Pocklington proof, then verify its certificate independently.
curl -s -X POST http://127.0.0.1:8765/api/primality-lab/pocklington \
  -H "X-Numerisect-Token: $token" -H 'Content-Type: application/json' \
  -d '{"number": "104729"}'
curl -s -X POST http://127.0.0.1:8765/api/primality-lab/verify-certificate \
  -H "X-Numerisect-Token: $token" -H 'Content-Type: application/json' \
  -d '{"kind": "pocklington", "certificate": "[104729,1007,[[53, 1, 3], [19, 1, 2]]]"}'

# Item 24: Pratt certificate tree.
curl -s -X POST http://127.0.0.1:8765/api/primality-lab/pratt \
  -H "X-Numerisect-Token: $token" -H 'Content-Type: application/json' \
  -d '{"number": "104729", "max_nodes": 500}'

# Item 30: 561 = 3 * 11 * 17, lambda = 80, 320 Fermat liars.
curl -s -X POST http://127.0.0.1:8765/api/primality-lab/carmichael \
  -H "X-Numerisect-Token: $token" -H 'Content-Type: application/json' \
  -d '{"number": "561", "base_limit": 1000}'

# Item 37: Selfridge's covering set proves 78557 is a Sierpinski number.
curl -s -X POST http://127.0.0.1:8765/api/primality-lab/covering-set \
  -H "X-Numerisect-Token: $token" -H 'Content-Type: application/json' \
  -d '{"k": "78557", "kind": "sierpinski", "period": 36,
       "candidates": ["3", "5", "7", "13", "19", "37", "73"]}'

# Items 42/43: a reproducible 32-bit safe prime with a certificate.
curl -s -X POST http://127.0.0.1:8765/api/primality-lab/constrained-prime \
  -H "X-Numerisect-Token: $token" -H 'Content-Type: application/json' \
  -d '{"bits": 32, "kind": "safe", "certificate": true, "seed": "7"}'

# Item 130: the Lucas-Lehmer trace for M13 = 8191.
curl -s -X POST http://127.0.0.1:8765/api/primality-lab/lucas-lehmer-steps \
  -H "X-Numerisect-Token: $token" -H 'Content-Type: application/json' \
  -d '{"exponent": 13, "show_limit": 5}'
```

Each response includes `output_file`; the saved report is downloadable from
`GET /api/outputs/<filename>` and is announced in the result panel.

See [Roadmap status](ROADMAP_STATUS.md) for features that remain partial or
deferred rather than being represented by placeholder calculations.
