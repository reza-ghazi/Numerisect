# Visualization and education workbench

Numerisect ships eight visual Prime Tools that are backed by a dedicated
PARI/GP program, `numerisect/visual_lab.gp`. Python (`numerisect/visual_lab.py`)
validates every request, launches GP with an argument array, requires the
`DONE:` completion marker, parses the tagged protocol strictly, and persists a
report. JavaScript receives finished integers and flags and does nothing but
map them to canvas coordinates, colours, and animation frames.

Numerisect is a user interface over existing number-theory libraries, so no
tool here re-implements mathematics a library already provides. Every prime,
every count, every classification, and every axis maximum below comes from a
library routine — primesieve, or PARI's `forprime`, `isprime`, `issquare`,
`gcd`, `eulerphi`, `primes`, and `primepi`.

### Which library routine supplies the numbers

| Visualization | Library routine |
| --- | --- |
| Prime spirals (Ulam, Sacks, polar) | **primesieve** enumerates an unhighlighted range inside 2⁶⁴; otherwise PARI `forprime` + `isprime`, with quadratic-family membership decided by PARI `issquare` |
| Eisenstein prime lattice | PARI `isprime`, `sqrtint` |
| Interactive modular wheel | PARI `isprime`, `gcd`, `eulerphi` |
| Residue-class heatmap | PARI `forprime` + `isprime` + `gcd` |
| Prime-gap timeline | PARI `forprime` + `isprime` + `log` |
| Prime race | PARI `forprime` + `isprime` + `gcd` |
| Sieve animations | the four classical sieves executed step by step in GP, verified against PARI `primes(primepi(n))` |
| Complexity dashboard | none — cited literature plus wall-clock job-history bookkeeping |

### The one deliberate exception

The **sieve animations** do not delegate to a library enumeration routine,
because the algorithms themselves are the subject of the feature: an animation
of the sieve of Eratosthenes has to execute the sieve of Eratosthenes. Those
traces are **educational and bounded** — `n` is capped at 5,000, and PARI/GP
refuses to report a trace whose survivors disagree with its own
`primes(primepi(n))` table. **The application's real prime enumeration never
uses them**: every other tool on this page, and every prime-generation and
counting feature in Numerisect, goes through primesieve, primecount, or PARI's
`forprime`/`isprime`.

The **complexity dashboard** is likewise not a computation: its reference table
is cited literature and its timing summary is bookkeeping over the persisted
job history. Both facts are stated in the response note.

Each tool has its own hash route under `#primes/…` and appears in the
**Visualization & education** navigation group. Every result panel names the
`output/<filename>.txt` report that was saved automatically.

## What each visualization shows

| Tool | Route | What the engine decides | What the browser does |
| --- | --- | --- | --- |
| Prime spiral | `POST /api/visual/spiral` | which integers are prime (`isprime`, or primesieve when nothing is highlighted) and which of them belong to the highlighted family | places offset *i* on an Ulam square spiral, a Sacks spiral, or a polar spiral and colours highlighted points |
| Eisenstein lattice | `POST /api/visual/eisenstein-lattice` | every `a + bω` with norm `a² − ab + b² ≤ bound` that is an Eisenstein prime, and its split/inert/ramified kind | draws `(a − b/2, b√3/2)` on the hexagonal lattice, one colour per kind |
| Modular wheel | `POST /api/visual/modular-wheel` | residue, ring index, coprimality, primality, per-spoke prime counts, and `φ(m)` | converts `(residue, ring)` to polar coordinates |
| Residue heatmap | `POST /api/visual/residue-heatmap` | prime counts per residue class per interval bin, the coprimality of each class, and the busiest cell | maps counts to a colour ramp; blocked classes get a flat dark cell |
| Gap timeline | `POST /api/visual/gap-timeline` | every consecutive gap, every record gap, and its merit `g / ln p` | draws one bar per gap and recolours the record bars |
| Prime race | `POST /api/visual/prime-race` | running class counts at equally spaced checkpoints and every exact lead change | replays the checkpoint frames as animated lines |
| Sieve animation | `POST /api/visual/sieve-trace` | the ordered execution trace of the chosen sieve and the verified survivors | replays the recorded steps onto a grid |
| Complexity dashboard | `POST /api/visual/complexity` | (reference table: literature) plus grouped wall-clock timings from `GET /api/jobs` history | draws median seconds per engine and digit bucket |

### Prime spirals (Ulam, Sacks, polar)

The three layouts differ only in the coordinate map applied to the offset
`i = p − start`:

- **Ulam** — the square spiral: `i` walks the integer lattice one unit step at
  a time, so the diagonals correspond to quadratic families.
- **Sacks** — radius `√i`, angle `2π√i`, which places the perfect squares on a
  single ray and bends the polynomial families into smooth curves.
- **Polar** — radius `i`, angle `i` radians, the plot whose apparent spiral
  arms come from the rational approximations of `2π`.

Highlighting is decided in GP, never in the browser:

- `highlight: "residue"` marks the primes `p ≡ residue (mod modulus)`.
- `highlight: "polynomial"` marks the primes that are values of `a·k² + b·k + c`
  for some integer `k`. GP solves the quadratic in `k` exactly by testing
  whether the discriminant `b² − 4a(c − p)` is a perfect square and whether the
  resulting root is an integer, so the answer is exact for every prime in
  range. With `a = b = 1, c = 41` this marks Euler's `k² + k + 41`.
- `highlight: "none"` skips GP and uses primesieve, which is faster; the
  response `engine` field says which engine ran.

### Eisenstein prime lattice

`ω = e^{2πi/3}` and the norm of `a + bω` is `N = a² − ab + b²`. GP applies the
standard criterion:

- `kind 3` — **ramified**: `N = 3`, the associates of `1 − ω`.
- `kind 1` — **split**: `N` is a rational prime (necessarily `≡ 1 mod 3`).
- `kind 2` — **inert**: the element is a unit multiple of a rational prime
  `q ≡ 2 (mod 3)`, so its norm is `q²`.

### Interactive modular wheel

This is a strict extension of the Prime Structures wheel
(`POST /api/primes/modular-wheel`), which always starts at 0 and caps the base
at 360 with at most 20,001 values. The visual wheel accepts **any base up to
10,000**, **any nonnegative start**, and up to **200,000 consecutive values**,
and additionally returns the per-spoke prime counts and `φ(m)` so the browser
never counts anything. Only the `φ(m)` spokes coprime to the base can carry
primes larger than the base, which is Dirichlet's theorem made visible.

### Residue-class heatmap

The range is split into equal-width bins; the engine returns one row per bin
with a count for every residue `0 … m−1`, plus the range totals and a
coprimality flag per class. Rows for classes sharing a factor with the modulus
stay empty except for the modulus's own prime divisors.

### Prime-gap timeline and record gaps

Every consecutive gap is reported in order. A *record* gap is one exceeding
every earlier gap in the scanned range; when the scan starts at 2 these are
exactly the maximal prime gaps (OEIS A002386 / A005250). The merit `g / ln p`
is evaluated by GP. The timeline may be truncated at the requested `limit`;
the record list never is, and truncation is reported explicitly rather than
being presented as "no more gaps".

### Prime race

For each reduced residue class modulo `q`, GP keeps a running count and emits
a frame at each of the requested checkpoints together with every exact lead
change (a tie keeps the previous leader; leader `-1` means no leader yet).
Modulo 4 through 1,000 gives 80 primes `≡ 1` against 87 primes `≡ 3`, with
class 3 leading — the classical Chebyshev bias.

### Sieve animations

Four traces are available, all recorded step by step in GP and **verified
against PARI's own prime table before the trace is reported at all** — a
disagreement is an engine error, never a silently wrong animation.

| `kind` | Sieve |
| --- | --- |
| `eratosthenes` | classical sieve of Eratosthenes |
| `segmented` | segmented Eratosthenes with a base sieve to `√n` |
| `sundaram` | sieve of Sundaram (strikes `i + j + 2ij`) |
| `atkin` | sieve of Atkin (quadratic-form toggles plus square-multiple removal) |

Each step is `[kind, value, a, b, flag]`:

| Step kind | Meaning |
| --- | --- |
| 1 | select prime `value` |
| 2 | strike composite `value` by prime `a` (`flag` = it was already struck) |
| 3 | survivor `value` declared prime |
| 4 | Sundaram strike of `2m + 1 = value` via `i = a`, `j = b` |
| 5 / 6 / 7 | Atkin toggle by `4x² + y²` / `3x² + y²` / `3x² − y²` with `x = a`, `y = b` (`flag` = new state) |
| 8 | Atkin square-multiple elimination of `value` by `r²`, `r = a` |
| 9 | segment boundary `[value, a]` |

## Documented caps and timeouts

| Operation | Bounds | Default engine time limit |
| --- | --- | --- |
| Spiral | start ≥ 1 and at most 60 decimal digits; 1–1,000,000 integers (100,000 above 2⁶⁴); coefficients in ±1,000,000; 2 ≤ modulus ≤ 1,000,000 | 60 s |
| Eisenstein lattice | norm bound 2–200,000; point limit 1–200,000 | 60 s |
| Modular wheel | base 2–10,000; start ≥ 0 (≤ 60 digits); 1–200,000 values | 60 s |
| Residue heatmap | span ≤ 10,000,000 (100,000 above 2⁶⁴); modulus 2–360; bins 1–200 | 120 s |
| Gap timeline | span ≤ 10,000,000 (100,000 above 2⁶⁴); timeline limit 1–200,000 | 120 s |
| Prime race | span ≤ 10,000,000 (100,000 above 2⁶⁴); modulus 2–360; checkpoints 1–1,000; event limit 1–100,000 | 120 s |
| Sieve trace | `n` 2–5,000; segment size 1–`n` (omit it and PARI/GP derives `sqrtint(n) + 1`; Python never computes it) | 60 s |
| Complexity dashboard | job-history depth 1–500 | not applicable (no engine run) |

Every route accepts `timeout_seconds` between 1 and 3,600. A timeout, an
exhausted display limit, and an exhausted bound are **inconclusive**: the API
returns HTTP 422 with the engine message, or sets `truncated` /
`event_truncated`, and never presents a partial scan as a complete answer. A
missing `DONE:` marker is an error, not an empty success.

## API examples

First create the local session cookie described in
[the security model](SECURITY_MODEL.md).

```bash
curl --cookie numerisect.cookies -X POST http://127.0.0.1:8765/api/visual/spiral \
  -H 'Content-Type: application/json' \
  -d '{"start":"1","count":10000,"layout":"ulam","highlight":"polynomial","a":1,"b":1,"c":41}'

curl --cookie numerisect.cookies -X POST http://127.0.0.1:8765/api/visual/eisenstein-lattice \
  -H 'Content-Type: application/json' \
  -d '{"norm_bound":2000,"limit":20000}'

curl --cookie numerisect.cookies -X POST http://127.0.0.1:8765/api/visual/modular-wheel \
  -H 'Content-Type: application/json' \
  -d '{"modulus":2310,"start":0,"count":5000}'

curl --cookie numerisect.cookies -X POST http://127.0.0.1:8765/api/visual/residue-heatmap \
  -H 'Content-Type: application/json' \
  -d '{"start":"1","end":"100000","modulus":30,"bins":50}'

curl --cookie numerisect.cookies -X POST http://127.0.0.1:8765/api/visual/gap-timeline \
  -H 'Content-Type: application/json' \
  -d '{"start":"1","end":"100000","limit":20000}'

curl --cookie numerisect.cookies -X POST http://127.0.0.1:8765/api/visual/prime-race \
  -H 'Content-Type: application/json' \
  -d '{"start":"1","end":"1000","modulus":4,"checkpoints":200}'

curl --cookie numerisect.cookies -X POST http://127.0.0.1:8765/api/visual/sieve-trace \
  -H 'Content-Type: application/json' \
  -d '{"kind":"atkin","n":200}'

curl --cookie numerisect.cookies -X POST http://127.0.0.1:8765/api/visual/complexity \
  -H 'Content-Type: application/json' \
  -d '{"job_limit":500}'
```

## Complexity and memory reference table

`L_n[α, c]` abbreviates `exp((c + o(1)) (ln n)^α (ln ln n)^(1−α))`. Bounds
marked *heuristic* are not proved; they are the standard published estimates.
This table is literature data, not a Numerisect measurement, and the dashboard
labels it as such.

| Algorithm | Category | Time | Memory | Source |
| --- | --- | --- | --- | --- |
| Trial division | factoring (exponential) | `O(n^(1/2))` divisions; `O(p)` to find a factor `p` | `O(1)` (`O(π(√n))` with a stored prime table) | Crandall & Pomerance, *Prime Numbers: A Computational Perspective*, 2nd ed., §3.1 |
| Pollard rho (Brent cycle finding) | factoring (special purpose) | expected `O(√p) ≈ O(n^(1/4))` modular multiplications (heuristic) | `O(1)` | Pollard, *BIT* 15 (1975); Brent, *BIT* 20 (1980) |
| Pollard p − 1 | factoring (special purpose) | `O(B₁ log B₁)` multiplications for stage 1; succeeds when `p − 1` is `B₁`-smooth | `O(1)` for stage 1; stage 2 stores `O(B₂ / log B₂)` residues or a polynomial table | Pollard, *Proc. Cambridge Philos. Soc.* 76 (1974); Montgomery, *Math. Comp.* 48 (1987) |
| Elliptic-curve method (ECM) | factoring (special purpose) | `L_p[1/2, √2]` per factor `p` (heuristic); independent of the size of `n` | `O(log n)` per curve; stage 2 memory grows with `B₂` | H. W. Lenstra Jr., *Annals of Mathematics* 126 (1987); Zimmermann & Dodson, ANTS VII (2006) |
| Self-initializing quadratic sieve (SIQS) | factoring (general purpose) | `L_n[1/2, 1]` (heuristic) | sub-exponential: factor base, sieve block, sparse relation matrix | Pomerance, *Eurocrypt '84* (1985); Contini, M.Sc. thesis, University of Georgia (1997) |
| General number field sieve (GNFS) | factoring (general purpose) | `L_n[1/3, (64/9)^(1/3) ≈ 1.923]` (heuristic) | sub-exponential: sieve regions plus a sparse matrix with millions of rows | Lenstra & Lenstra (eds.), *The Development of the Number Field Sieve*, LNM 1554 (1993) |
| Special number field sieve (SNFS) | factoring (special form) | `L_n[1/3, (32/9)^(1/3) ≈ 1.526]` (heuristic) | sub-exponential, smaller than GNFS at equal size | Lenstra, Lenstra, Manasse & Pollard, *Math. Comp.* 61 (1993) |
| AKS primality test | primality (deterministic, proven) | `Õ(log⁶ n)` (Lenstra–Pomerance variant); original bound `Õ(log^10.5 n)` | polynomial in `log n` | Agrawal, Kayal & Saxena, *Annals of Mathematics* 160 (2004); Lenstra & Pomerance, *J. Eur. Math. Soc.* 21 (2019) |
| Elliptic-curve primality proving (ECPP) | primality (certificate) | `Õ(log⁴ n)` heuristic (fastECPP); certificate verification `Õ(log³ n)` | polynomial in `log n` | Atkin & Morain, *Math. Comp.* 61 (1993); Morain, *Math. Comp.* 76 (2007) |
| APR-CL | primality (deterministic, proven) | `(log n)^(O(log log log n))` — superpolynomial but practically fast | polynomial in `log n` | Adleman, Pomerance & Rumely, *Annals of Mathematics* 117 (1983); Cohen & Lenstra, *Math. Comp.* 42 (1984) |
| Sieve of Eratosthenes | sieve | `O(n log log n)` | `O(n)` bits | Crandall & Pomerance, §3.2; Sorenson, Technical Report 909, U. Wisconsin (1990) |
| Segmented sieve of Eratosthenes | sieve | `O(n log log n)` | `O(√n)` plus one cache-sized segment | Bays & Hudson, *BIT* 17 (1977); Sorenson (1990) |
| Sieve of Sundaram | sieve | `O(n log n)` | `O(n)` bits | Sundaram (1934), as described in Aiyar, *Math. Student* 2 (1934); Crandall & Pomerance, §3.2 |
| Sieve of Atkin | sieve | `O(n / log log n)` | `O(n^(1/2 + o(1)))` | Atkin & Bernstein, *Math. Comp.* 73 (2004) |

### Measured timings

The dashboard groups **completed** factorization jobs from the local job
history by selected engine and 10-digit input-size bucket and reports the run
count together with the minimum, median, mean, and maximum wall-clock seconds
(`finished_at − started_at`). Queued, running, cancelled, and failed jobs are
excluded, as are jobs without both timestamps. These are measurements of this
machine under whatever load it had at the time; they are not benchmarks and
must not be read as a ranking of the algorithms above.

## Native engines used

- **PARI/GP** (`gp`, argument array, 256 MB stack) runs `visual_lab.gp` for
  every spiral highlight, the Eisenstein lattice, the modular wheel, the
  residue heatmap, the gap timeline, the prime race, and all four sieve
  traces. Primality is always `isprime`, so every prime reported here is
  proven, never probable.
- **primesieve** enumerates the primes for an unhighlighted spiral whose range
  fits in 64 bits.
- No network access, no credentials, and no telemetry are involved in any of
  these operations.

## What the browser is allowed to do

JavaScript in this workbench maps engine-supplied integers and flags to canvas
coordinates, colours, and playback frames, and does nothing else. Spiral,
lattice, and grid coordinates are pure layout and are computed in the browser;
which `n` are prime, which belong to a highlighted family, how many points fall
in each Eisenstein class, how many spokes carry primes, the largest gap, and
the prime-race axis maximum are all read from the response, never recomputed.
The sieve animation replays the recorded step codes and sets one colour flag
per cell; it performs no sieving, no divisibility test, and no primality
decision of its own.
