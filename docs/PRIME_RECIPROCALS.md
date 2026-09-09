# Reciprocals of primes

Numerisect 0.7.0 preserves the streamed native-output contract described here:
the 100,000-digit browser ceiling is only a preview limit and does not cap the
complete finite decimal or repetend written directly by PARI/GP to the report.

Numerisect analyzes the base-10 expansion of `1/p` for a rigorously proven
prime `p`. PARI/GP performs the primality test, multiplicative-order
calculation, primitive-root test, and decimal-digit generation. Python and
JavaScript only validate, orchestrate, persist, and present the native result.

## Using the analyzer

1. Start Numerisect with `./run.sh` and open
   <http://127.0.0.1:8765/#primes/prime-reciprocal>.
2. In **Analyze 1/p**, enter a prime or a supported integer expression.
3. Choose how many decimal digits to preview in the browser. Use zero to omit
   the preview; the complete finite expansion or repetend is still saved.
4. Choose a native-engine time limit, or keep the default **No time limit**, and
   select **Analyze reciprocal**.

The source installer and supported hosts are documented in
[Installation and versioning](INSTALLATION.md).

The result shows:

- whether the decimal terminates or repeats;
- the exact repeating-period length;
- whether 10 is a primitive root modulo `p`;
- whether `p` is a full-reptend prime in base 10;
- the requested leading digits in the browser; and
- a downloadable text report in `output/` containing the complete finite
  expansion or full repetend.

After a successful calculation, the result panel displays the exact saved path
as `output/<generated-filename>.txt` as well as the download button.

Composite inputs are rejected after a rigorous PARI/GP `isprime` test.

The **Full-reptend primes and maximal decimal periods** page (`/#primes/reptend-prime`), in the
same **Prime structures** navigation group, searches an interval for
full-reptend primes. It rigorously proves each candidate prime and requires the
exact order `ord_p(10)=p-1`; this replaces the prototype's repeated modular
multiplication loop with PARI/GP's native multiplicative-order implementation.

## Mathematics and native implementation

For primes other than 2 and 5, the length of the repeating block in `1/p` is
the multiplicative order

```text
ord_p(10) = min { k > 0 : 10^k = 1 (mod p) }.
```

The native program calculates this value with PARI/GP's
`znorder(Mod(10,p))`. Since the multiplicative group modulo a prime has order
`p - 1`, 10 is a primitive root precisely when `ord_p(10) = p - 1`. In that
case, `p` is a full-reptend prime in base 10.

The primes 2 and 5 divide the base, so their decimal reciprocals terminate and
have repeating period zero. Numerisect reports `1/2 = 0.5` and `1/5 = 0.2`
instead of treating these valid primes as errors.

Decimal digits are generated with exact PARI integer arithmetic. The native
engine advances the remainder in blocks, pads every block to its exact decimal
width, and writes each block directly through PARI's buffered file interface.
This avoids copying the full repetend through Python, JSON, or the browser and
preserves leading zeros; for example, the six digits of `1/13` are `076923`,
not `76923`.

## Limits and performance

The native prime and period calculations use arbitrary precision. The API
accepts an expression of up to 100,000 characters, subject to configured
expression-size limits; the period result has no fixed-precision ceiling.

Establishing the exact order generally requires factoring `p - 1`. This can be
the dominant cost for a very large prime. The default has no time limit, so the
native operation can continue until completion or an engine/system failure.
Optional time limits from one second through one hour are available when the
user prefers an operational bound. Exceeding a selected bound produces a clear
engine-timeout error rather than a guessed period.

Only the JSON/browser preview is capped at 100,000 digits per request. The
native text export always streams the entire finite expansion or one complete
repetend and has no application-imposed digit-count limit. The practical limits
are the native engine, computation time, available memory, free disk space, and
filesystem limits. A period with billions of digits will require billions of
bytes and may take a very long time even though Numerisect does not truncate it.

For multiplicative orders in other bases, modular inverses, square roots, or
a primitive root, use [Calculate modulo a prime](PRIME_MANIPULATION.md) in the
**Arithmetic & factors** group. This does not change reciprocal export limits.

## API

First create the local session cookie described in
[the security model](SECURITY_MODEL.md).

```bash
curl --cookie numerisect.cookies -X POST http://127.0.0.1:8765/api/primes/reciprocal \
  -H 'Content-Type: application/json' \
  -d '{"expression":"13","digit_limit":3,"timeout_seconds":0}'
```

The response includes:

```json
{
  "number": "13",
  "digits": 2,
  "is_prime": true,
  "terminating": false,
  "period": "6",
  "primitive_root_10": false,
  "full_reptend": false,
  "decimal_digits": "076",
  "digits_generated": 3,
  "digits_complete": false,
  "digit_limit": 3,
  "exported_digits": "6",
  "export_complete": true,
  "engine": "PARI/GP",
  "note": "...",
  "output_file": "prime-reciprocal-....txt"
}
```

`period` and `exported_digits` are serialized as decimal strings so arbitrarily
large exact values cannot lose precision in JavaScript. Here the browser gets
only `076`, while the downloaded report contains the complete `0.076923`.

## Implementation map

| File | Responsibility |
|---|---|
| `numerisect/prime_reciprocal.gp` | Native primality, period, primitive-root, decimal-digit calculations, and unbounded block-streamed report output. |
| `numerisect/primes.py` | GP process boundary and strict tagged-output validation. |
| `numerisect/main.py` | Request model, API endpoint, error handling, and text export. |
| `numerisect/static/index.html` | Reciprocal-analysis controls. |
| `numerisect/static/app.js` | Submission and exact-result rendering. |
| `numerisect/static/styles.css` | Responsive reciprocal summary and decimal presentation. |
| `tests/test_primes.py` | Period, full-reptend, leading-zero, truncation, terminating, and rejection tests. |
