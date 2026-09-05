# Prime classification

Numerisect evaluates 56 prime classifications through a native PARI/GP
program. Python validates the request, starts PARI/GP, parses tagged results,
and writes the report; JavaScript presents the result. Neither interface layer
performs the classification mathematics.

## Using the classifier

1. Start Numerisect with `./run.sh` and open
   <http://127.0.0.1:8765/#primes/prime-classify>.
2. In **Classify a prime**, enter a decimal integer or a supported integer
   expression such as `2^127 - 1`.
3. Choose the per-class time budget. The default is two seconds; available
   choices range from one to ten seconds.
4. Select **Classify prime**.

For a versioned user installation on Linux, Windows WSL, or macOS, see
[Installation and versioning](INSTALLATION.md).

PARI/GP rigorously tests the input with `isprime` before classification. A
composite input is reported immediately and the 56 membership tests are not
run. A prime result is rendered as classification cards and saved as a text
file in `output/`. Its result appears beneath the form with the exact saved
path and a download control. The page is in **Primality & navigation**; for
testing a list without classification, use **Check a list of integers** in the
same group (see [Prime manipulation](PRIME_MANIPULATION.md)).

## Result meanings

| Result | Meaning |
|---|---|
| Match | The native test established that the prime belongs to the class. |
| Not matched | The native test established that the prime does not belong to the class. |
| Inconclusive | The test exceeded its time budget or a deliberately documented exact-search/catalogue boundary. It is not a negative result. |

Each matching or inconclusive item includes an identifier, display name,
definition, and, when useful, native-engine detail such as a partner prime,
sequence index, exponent, or limiting reason. The summary also reports the
number of tested, matched, not-matched, and inconclusive classes.

## Classification catalogue

All classifications from the source catalogue are represented exactly once.
“Exact” below means that Numerisect uses an algebraic condition, recurrence,
rigorous primality test, congruence, or exhaustive test for the supplied input.

| # | Identifier | Classification | Native test and scope |
|---:|---|---|---|
| 1 | `balanced` | Balanced | Exact comparison with the nearest proven prime on each side. |
| 2 | `chen` | Chen | Exact test that `p + 2` is prime or has exactly two prime factors with multiplicity. |
| 3 | `circular` | Circular | Rigorously tests every cyclic decimal rotation. |
| 4 | `cluster` | Cluster | Exact prime-difference coverage through `p = 100000`; larger inputs are inconclusive. |
| 5 | `cousin` | Cousin | Rigorously tests partners at distance four. |
| 6 | `cuban` | Cuban | Exact recognition of the two cubic-difference forms. |
| 7 | `cullen` | Cullen | Exact recognition of `n * 2^n + 1`. |
| 8 | `delicate` | Digitally delicate | Rigorously tests every one-digit decimal replacement. |
| 9 | `dihedral` | Dihedral | Rigorously tests the valid seven-segment rotations and reflections. |
| 10 | `double_mersenne` | Double Mersenne | Exact recognition of `2^(2^q - 1) - 1` with prime `q`. |
| 11 | `emirp` | Emirp | Rigorously tests the distinct decimal reversal. |
| 12 | `even` | Even | Exact recognition of the unique even prime. |
| 13 | `factorial` | Factorial | Exact recognition of `n! - 1` and `n! + 1`. |
| 14 | `fermat` | Fermat | Exact recognition of `2^(2^n) + 1`. |
| 15 | `fibonacci` | Fibonacci | Exact square-criterion sequence membership. |
| 16 | `fortunate` | Fortunate | Exact primorial search for candidate values through 1000; larger candidates are inconclusive. |
| 17 | `good` | Good | Exact symmetric-neighbor comparisons through `p = 1000000`; larger inputs are inconclusive. |
| 18 | `happy` | Happy | Exact digit-square orbit with cycle detection. |
| 19 | `higgs` | Higgs | Exact exponent-two sequence construction through `p = 100000`; larger inputs are inconclusive. |
| 20 | `left_and_right_truncatable` | Left-and-right truncatable | Rigorously tests simultaneous outer decimal truncations. |
| 21 | `left_truncatable` | Left-truncatable | Rigorously tests all left truncations and rejects embedded leading-zero cases. |
| 22 | `lucas` | Lucas | Exact square-criterion sequence membership. |
| 23 | `mersenne` | Mersenne | Exact recognition that `p + 1` is a power of two. |
| 24 | `mills` | Mills | Membership in the established Mills-prime sequence; values beyond the established catalogue are inconclusive. |
| 25 | `minimal` | Minimal | Membership in the established minimal-prime catalogue. |
| 26 | `motzkin` | Motzkin | Exact integer-recurrence sequence membership. |
| 27 | `non_insertable` | Non-insertable | Rigorously tests every decimal digit at every insertion position. |
| 28 | `newman_shanks_williams` | Newman–Shanks–Williams | Exact recurrence membership with the required eligible odd index. |
| 29 | `palindromic` | Palindromic | Exact decimal reversal comparison. |
| 30 | `pell` | Pell | Exact integer-recurrence sequence membership. |
| 31 | `pell_lucas` | Pell–Lucas | Exact half-companion Pell recurrence membership. |
| 32 | `permutable` | Permutable | Established non-repunit catalogue plus exact repunit recognition; unresolved range beyond the catalogue is inconclusive. |
| 33 | `pierpont` | Pierpont | Exact recognition of `2^u * 3^v + 1`. |
| 34 | `pillai` | Pillai | Exact factorial-residue search through `p = 200000`; larger inputs are inconclusive. |
| 35 | `prime_quadruplet` | Prime quadruplet | Rigorously tests every constellation position in `{q, q+2, q+6, q+8}`. |
| 36 | `prime_triplet` | Prime triplet | Rigorously tests all three-prime constellations of diameter six. |
| 37 | `primorial` | Primorial | Exact recognition of one more or less than a prime primorial. |
| 38 | `proth` | Proth | Exact recognition of `k * 2^n + 1`, where `k` is odd and `k < 2^n`. |
| 39 | `pythagorean` | Pythagorean | Exact congruence test `p = 1 (mod 4)`. |
| 40 | `quartan` | Quartan | Exact binary-quadratic-form solution followed by fourth-power verification. |
| 41 | `repunit` | Repunit | Exact recognition of an all-ones decimal representation. |
| 42 | `right_truncatable` | Right-truncatable | Rigorously tests every successive right truncation. |
| 43 | `safe` | Safe | Rigorously tests `(p - 1) / 2`. |
| 44 | `sexy` | Sexy | Rigorously tests partners at distance six. |
| 45 | `sophie_germain` | Sophie Germain | Rigorously tests `2p + 1`. |
| 46 | `strobogrammatic` | Strobogrammatic | Exact 180-degree decimal-display transformation. |
| 47 | `strong` | Strong | Exact comparison with the mean of the nearest proven prime neighbors. |
| 48 | `superprime` | Superprime | Exact prime-index test through `p = 10^12`; larger inputs are inconclusive. |
| 49 | `supersingular` | Supersingular | Exact membership in the prime divisors of the Monster group's order. |
| 50 | `twin` | Twin | Rigorously tests partners at distance two. |
| 51 | `wagstaff` | Wagstaff | Exact recognition of `(2^q + 1) / 3` with odd prime `q`. |
| 52 | `wieferich` | Wieferich | Exact base-two congruence modulo `p^2`. |
| 53 | `williams` | Williams | Exact form test for the catalogue's tested bases 3 through 9. |
| 54 | `wilson` | Wilson | Established members and exhaustive non-membership below `2 * 10^13`; larger inputs are inconclusive. |
| 55 | `wolstenholme` | Wolstenholme | Established members and exhaustive non-membership below `10^9`; larger inputs are inconclusive. |
| 56 | `woodall` | Woodall | Exact recognition of `n * 2^n - 1`. |

## API

The endpoint accepts the same restricted integer-expression syntax as the
other Numerisect tools:

```bash
curl -X POST http://127.0.0.1:8765/api/primes/classify \
  -H 'Content-Type: application/json' \
  -d '{"expression":"2^127 - 1","per_test_seconds":2}'
```

The response has this shape:

```json
{
  "number": "170141183460469231731687303715884105727",
  "digits": 39,
  "is_prime": true,
  "classification": "prime",
  "matches": [],
  "inconclusive": [],
  "tested": 56,
  "not_matched": 56,
  "engine": "PARI/GP",
  "note": "...",
  "output_file": "..."
}
```

The contents of `matches` and `inconclusive` depend on the input and budget;
the empty arrays above document the response structure rather than the actual
classification of the example number.

## Time and size behavior

The selected budget applies independently to every guarded classification.
PARI/GP's `alarm` mechanism interrupts a native test that exceeds its budget,
and Numerisect records that class as inconclusive. The overall subprocess has a
larger safety timeout so all 56 tests normally have time to finish.

Arbitrary-precision arithmetic is provided by PARI/GP and GMP. There is no
fixed-precision limit in the native primality and exact algebraic operations,
but API expressions are capped at 100,000 characters and evaluated results
follow the configured expression-size limit. Time and memory grow with input size. Explicit boundaries in
the table protect interactive use where a definition requires an exhaustive
search or where mathematical knowledge is catalogue-based.

PARI's candidate-navigation routines may return pseudoprimes for sufficiently
large inputs. The classifier's neighbor helper therefore rechecks candidates
with rigorous `isprime` before using them in a proof-oriented result.

## Implementation map

| File | Responsibility |
|---|---|
| `numerisect/prime_classifier.gp` | All classification mathematics, rigorous primality checks, time guards, and tagged native output. |
| `numerisect/primes.py` | Catalogue metadata, GP process boundary, tagged-output validation, and response assembly. |
| `numerisect/main.py` | Request validation, HTTP endpoint, error translation, and text-report persistence. |
| `static/index.html` | Classifier form and time-budget controls. |
| `static/app.js` | Request submission and result rendering. |
| `static/styles.css` | Match, non-match summary, and inconclusive presentation. |
| `tests/test_primes.py` | Native integration and response-contract regression coverage. |

When a classification is extended, its identifier must stay synchronized
between the GP dispatcher and the Python metadata catalogue. A mathematical
limit must be exposed as inconclusive unless non-membership is actually proven.
