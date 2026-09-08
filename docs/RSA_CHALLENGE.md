# The RSA Factoring Challenge

*Numerisect 0.6.0*

Numerisect could always factor an RSA number. An RSA number is an ordinary semiprime, and
the automatic pipeline routes one to YAFU or CADO-NFS by size like any other input. What it
could not do was tell you **which** number you were holding, whether the published
factorization is genuine, or what attempting an unfactored one would cost on your machine.
This page documents the tool that answers those three questions.

## Which routine performs each computation

| Operation | Engine routine |
| --- | --- |
| Prove the value composite | PARI/GP `ispseudoprime`; a failed Miller–Rabin round is a proof of compositeness |
| Recompute the size | PARI/GP `#Str` and `#binary` |
| Check a published factorization | PARI/GP exact integer multiplication, `p * q == N` |
| Test each factor | PARI/GP `ispseudoprime` (Baillie–PSW) or `isprime` (APR-CL/ECPP proof) |
| Estimate the effort | PARI/GP real arithmetic over the number field sieve cost model |
| Actually factor one | the existing job pipeline: YAFU, or CADO-NFS above the threshold |

## The catalogue is data, not authority

`rsa_challenge.toml` holds all 54 challenge numbers, from RSA-100 at 100 decimal digits to
RSA-2048 at 617. The values were transcribed from the published challenge list, and **a
transcribed constant is an unverified claim**. Numerisect therefore re-derives every claim
in PARI/GP before reporting it:

* the recorded decimal and bit lengths must match the value;
* the value must be composite, proven rather than assumed;
* where factors are published, `p × q` must reproduce the value exactly, and both factors
  must be prime.

A mistyped digit surfaces as a failed check, never as a fact. `tests/test_rsa_challenge.py`
re-runs all of these over the whole file in a single PARI/GP invocation, so a corrupted
entry fails the suite rather than reaching a user.

At the time of writing the catalogue holds **24 factored** and **30 open** numbers.

## Open is not unfactorable

An open challenge number is *unfactored*. That is a statement about the effort spent so
far, not a proof that the number resists factoring. Numerisect never phrases it otherwise,
for the same reason an exhausted SQUFOF search is inconclusive rather than a claim that the
input is prime.

## The effort estimate, and why it is only an estimate

The general number field sieve has conjectured complexity

\[
L_N\!\left[\tfrac13, c\right] = \exp\!\Big( (c + o(1)) (\ln N)^{1/3} (\ln \ln N)^{2/3} \Big),
\qquad c = \sqrt[3]{64/9} \approx 1.9229 .
\]

There is no proof of this running time and the \(o(1)\) is not bounded, so any number
derived from it is a planning figure and not a prediction. Numerisect anchors it on a
published measurement rather than an abstract constant: the RSA-250 factorization, reported
by Boudot, Gaudry, Guillevic, Heninger, Thomé and Zimmermann at CRYPTO 2020 as roughly
**2,700 core-years** on Intel Xeon Gold 6130 cores. The estimate for any other value is that
anchor scaled by the ratio of \(L\) values, then divided by the cores on your machine.

The model deliberately ignores memory, the linear-algebra step and parameter tuning, all of
which matter in practice. **Treat the output as an order of magnitude.**

As a sanity check, the model puts RSA-100 at about thirteen minutes of core time. It was
factored in 108 seconds on 32 server cores in 2025, which is the same order.

## Routes

```text
GET  /api/factor-lab/rsa-catalogue   list all 54 challenge numbers with sizes and status
POST /api/factor-lab/rsa-challenge   report on one, verifying every claim in PARI/GP
```

Example:

```bash
curl --cookie jar --header 'Content-Type: application/json' \
  --data '{"target":"RSA-250"}' \
  http://127.0.0.1:8765/api/factor-lab/rsa-challenge
```

`target` accepts either a challenge name such as `RSA-250` or the decimal value itself, so
pasting a number tells you whether it is a recognised challenge number. A value that is not
in the list is reported honestly as unlisted, with its size and effort estimate still
computed.

`prove_factors` upgrades the factor check from Baillie–PSW to a primality proof. An
exhausted proof budget is reported as inconclusive and never downgraded to the weaker
claim.

## Actually factoring one

This tool does not factor anything. To attempt a challenge number, hand it to the ordinary
factorization pipeline, which selects an engine by size:

```bash
python3 -m numerisect.cli --json factor "$(cat rsa100.txt)" --engine auto --threads 22
```

Anything above RSA-260 is beyond current public capability, and the report will say so in
core-years before you start.
