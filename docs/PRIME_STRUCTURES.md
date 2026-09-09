# Prime structures and related numbers

Numerisect 0.7.0 adds companion algebraic pages for Eisenstein primes and
rational-prime decomposition in quadratic number fields. PARI/GP applies the
exact Eisenstein norm/axis criterion and constructs the maximal quadratic
order for `idealprimedec`, returning splitting, ramification, inertia degree,
and ideal norm. See [Advanced number theory](ADVANCED_NUMBER_THEORY.md).

This workspace collects the capabilities imported from the absolute-prime,
Gaussian-prime, modular-wheel, Paterson-prime, perfect-number, prime-pyramid,
safe-prime, full-reptend, special-prime, and witness-number prototypes.
PARI/GP performs every arithmetic, sequence, modular, and primality operation.
Python and JavaScript remain orchestration and presentation layers.

## Navigation and results

Each tool has a dedicated page in the searchable Prime Tools navigation.
**Reciprocals, Gaussian & digits** includes `/#primes/absolute-prime`,
`/#primes/gaussian-check`, `/#primes/gaussian-range`, `/#primes/modular-wheel`,
`/#primes/paterson-prime`, and `/#primes/reptend-prime`.
Perfect numbers are under **Prime generation**, pyramids and related sequences
under **Digit & sequence explorations**, and witnesses under **Divisors & arithmetic functions**.
Results and explicit `output/<filename>` confirmations appear below their form.

The same native GP file also implements the newer batch, residue-class, and
prime-modulus operations documented in [Prime manipulation](PRIME_MANIPULATION.md).

## Prime and sequence tools

| Tool | Exact definition and behavior |
|---|---|
| Absolute primes | A prime whose every cyclic decimal rotation is prime; results are grouped once per rotation orbit. |
| Gaussian prime check | For nonzero `a,b`, tests whether `a²+b²` is rational prime; on an axis, tests whether the absolute component is a rational prime congruent to 3 modulo 4. |
| Gaussian lattice | Applies that criterion to every point in `[-B,B]²`; JavaScript only plots returned points. |
| Modular wheel | PARI/GP computes value, residue, quotient ring, coprimality, and rigorous primality; JavaScript only assigns coordinates. |
| Paterson primes | Both `p` and the decimal integer formed by writing the base-4 digits of `p` must be prime. |
| Even perfect numbers | Uses Euclid–Euler `2^(q-1)(2^q-1)` after rigorously proving the Mersenne number `2^q-1`. |
| Full-reptend primes | Proves `p` prime and calculates exact `ord_p(10)=p-1`. |
| Digit-insertion pyramid | Reproduces the source sequence beginning `11`, `121`, `13231`, `1432341`. |
| Multiplication pyramid | Constructs all `i×j` cells and attaches native `isprime` results. |
| Safe primes | Already covered by the fixed-digit special-prime generator; no duplicate implementation was added. |

The existing 56-class classifier already covers twin, cousin, sexy, Sophie
Germain, safe, balanced, emirp, palindromic, Mersenne, Fermat, Wilson,
circular, Woodall, repunit, Wagstaff, Lucas, Cullen, Fibonacci, and Pell prime
membership. Prime-tuple search already covers the pair/constellation finders.
Those source methods therefore reuse the existing tools instead of creating
parallel Python calculations.

## Corrected related-number searches

The special-number range tool adds capabilities that were not already present:

- Carmichael numbers, using the exact square-free Korselt criterion;
- base-2 Fermat pseudoprimes, requiring compositeness;
- strong pseudoprimes to both bases 2 and 3, requiring compositeness and the
  full strong probable-prime chain;
- lucky primes from the native lucky-number sieve; and
- prime members of the standard Jacobsthal sequence
  `J(0)=0`, `J(1)=1`, `J(n)=J(n-1)+2J(n-2)`.

Several prototype definitions were mathematically incorrect and were not
copied literally. The prototype labeled ordinary primes as pseudoprimes,
implemented a partial strong test, called `2n²+1` a Pell sequence, used a
Mersenne formula for Lucas primes, and called a condition on two consecutive
primes “pronic.” Numerisect uses corrected standard definitions and documents
the distinction.

Special-number scans accept arbitrary-size endpoints but limit a single span
to 10,000,000 integers for interactive safety. The lucky sieve additionally
limits the upper endpoint to 2,000,000 because it materializes the finite sieve.
These bounds do not affect the general primality, classification, or nearby-prime
tools.

## Miller–Rabin witnesses

The source's `is_prime_by_withness` checked only `a^d = 1 (mod n)` after writing
`n-1=2^s d`. That is neither a complete Miller–Rabin pass condition nor a
primality proof. Numerisect uses the correctly spelled term **witness** and the
complete strong test:

1. calculate `x=a^d mod n`;
2. accept the round if `x=1` or `x=n-1`;
3. otherwise square through `a^(2^r d)` for `1 ≤ r < s`, accepting only if
   one value is `n-1`;
4. for a composite `n`, a failing base is a witness and a passing base is a
   strong liar.

The selected-base test supports arbitrary-size odd integers. For `n ≤ 1,000,000`,
Numerisect also enumerates all standard bases from 2 through `n-2`, reports
exact witness/passing counts, and returns bounded previews. For larger inputs,
it avoids an infeasible all-base scan and evaluates only the selected base.

## API routes

```text
POST /api/primes/absolute
POST /api/primes/gaussian/check
POST /api/primes/gaussian/range
POST /api/primes/modular-wheel
POST /api/primes/paterson
POST /api/primes/perfect
POST /api/primes/reptend
POST /api/primes/pyramid
POST /api/primes/special-numbers
POST /api/primes/miller-rabin-witnesses
```

All successful requests write a text report automatically and explicitly show
its exact `output/<filename>.txt` path in the UI.

See [Installation and versioning](INSTALLATION.md) for Linux, Windows WSL, and
macOS deployment and native-engine setup.

## Implementation map

| File | Responsibility |
|---|---|
| `numerisect/prime_structures.gp` | Native algorithms, exact primality tests, sequence construction, and tagged output |
| `numerisect/primes.py` | GP subprocess boundary and strict parser |
| `numerisect/main.py` | Request validation, endpoints, and report persistence |
| `numerisect/static/index.html` | Forms and resource controls |
| `numerisect/static/app.js` | Rendering and canvas geometry only |
| `tests/test_primes.py` | Known sequences, criteria, corrections, and parser regressions |
