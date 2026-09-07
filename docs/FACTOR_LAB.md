# Expert factorization laboratory

Numerisect is a user interface over existing number-theory libraries. This page
documents the expert factorization tools and, for each one, names the routine that
performs the computation.

| Operation | Performed by |
|---|---|
| SQUFOF | `numerisect-squfof`, a C program in this project using GMP |
| Pollard rho, p−1, p+1, ECM, SIQS, NFS, SNFS, Fermat, bounded trial division | YAFU's `rho`, `pm1`, `pp1`, `ecm`, `siqs`, `nfs`, `snfs`, `fermat`, `trial` |
| ECM campaigns | GMP-ECM with `-save`, `-resume`, `-c`, `-sigma`, `-param` |
| Special forms, algebraic and Aurifeuillean factors, SNFS suitability | PARI/GP `ispower`, `polcyclo`, `factor` |
| Strategy advice and the decision tree | PARI/GP `isprime`, `factor`, `ispower` |
| Algorithm traces | PARI/GP `Mod`, `gcd`, `forprime` |
| Primality certificates | PARI/GP `primecert`, `primecertisvalid`, `primecertexport` |
| General factorization | YAFU, Msieve, CADO-NFS |

## Why SQUFOF is written in C here

The project policy is to use an existing library routine, and to write optimized
C or C++ with GMP or FLINT only when no library provides one. SQUFOF is that case.
It was verified absent from every installed engine:

```text
yafu       'squfof' is an unrecognized variable or function in this build
PARI/GP    squfof is not a function in function call
Msieve     implements MPQS and NFS only
GMP-ECM    implements ECM, P-1 and P+1 only
```

`numerisect/native/numerisect_squfof.c` therefore supplies it. GMP is used for input
parsing and the range check; the cycle itself runs in 64-bit registers with 128-bit
intermediate products, which is what makes SQUFOF fast. The helper is compiled on
demand into `data/tools/bin/numerisect-squfof` and rebuilt automatically whenever the
source is newer, exactly like the FLINT zeta helper.

### Scope and honest limits

Inputs must be below 2^62. Above that, the multiplier-scaled discriminant leaves the
64-bit range and SQUFOF stops being competitive with SIQS in any case; such inputs are
**rejected with an explicit message** rather than answered incorrectly. Route them to
YAFU, Msieve, or CADO-NFS.

A run that finds no factor reports `status: exhausted`. **That is inconclusive.** It is
not a claim that the input is prime, and Numerisect never presents it as one. On a
sample of 150 random semiprimes below 2^62, the helper split 146 and was inconclusive
on 4, with no incorrect answers.

```bash
curl --cookie jar --header 'Content-Type: application/json' \
  --data '{"expression":"11111111111"}' \
  http://127.0.0.1:8765/api/factor-lab/squfof
```

SQUFOF is also selectable as the `squfof` job backend. Both parts of the split are
labelled prime or composite by PARI/GP's `isprime`; the C helper never labels primality
itself.

## Strategy adviser and decision tree

PARI/GP tests the input for primality, strips factors below 10^6 by bounded trial
division, checks the cofactor for a perfect power, and returns the full decision path
alongside the recommended engine.

The **expected remaining factor size** is a planning estimate, not a proven bound. With
no ECM completed it is the balanced-semiprime split, one third of the cofactor's digits.
With ECM completed to t digits it is at least t, because ECM to that depth makes a
smaller factor unlikely. The response states which basis was used.

Routing thresholds: below 20 digits SQUFOF or SIQS, below 60 digits SIQS, below 95
digits an ECM pretest then SIQS, and CADO-NFS above that.

## Special forms, algebraic and Aurifeuillean factors

Recognises perfect powers via `ispower`, values a^k ± 1 for bases to 1000, and
cyclotomic values Φ_k(a) for bases to 200 and k to 60. Every algebraic factor reported
is obtained by factoring Φ_n(b) with PARI and is **verified to divide the input** before
it is shown.

For 2^101 − 1 this returns the SNFS polynomial x^101 − 1, difficulty 30, and the two
algebraic factors 7432339208719 and 341117531003194129, which is the known
factorization of M101.

A search that exceeds its time budget reports `complete: false` and is inconclusive: it
does not assert that no special form exists.

## Algorithm traces

Bounded step traces of Pollard rho, Pollard p−1, and ECM stage 1, computed by PARI/GP so
that each step's state, quantity, and gcd can be shown. These exist to teach the
algorithms. **They are not the production factoring path**; Numerisect factors with YAFU,
Msieve, GMP-ECM, and CADO-NFS. Traces are capped at 500 steps and mark truncation
explicitly.

## Batch primality certificates

For each supplied factor, PARI/GP decides primality with `isprime`, builds a certificate
with `primecert`, and re-checks it independently with `primecertisvalid`. A composite
input is reported as not prime and not certified, never as a failure. `POST
/api/jobs/{id}/certificates` does the same for every prime factor of a completed
factorization.

## YAFU expert parameters

Only flags the installed YAFU build accepts are offered, verified against `yafu -h`:

| Field | Flag | Field | Flag |
|---|---|---|---|
| `b1_pm1`, `b2_pm1` | `-B1pm1`, `-B2pm1` | `siqs_factor_base` | `-siqsB` |
| `b1_pp1`, `b2_pp1` | `-B1pp1`, `-B2pp1` | `siqs_trial_bound` | `-siqsTF` |
| `b1_ecm`, `b2_ecm` | `-B1ecm`, `-B2ecm` | `siqs_relations` | `-siqsR` |
| `rho_max` | `-rhomax` | `siqs_timeout` | `-siqsT` |
| `fermat_max` | `-fmtmax` | `siqs_blocks` | `-siqsNB` |
| `sigma` | `-sigma` | `siqs_multiplier` | `-siqsM` |

Every value is range-checked and passed as a separate argv entry. Engine commands are
argument arrays; nothing is ever interpolated into a shell string.

## ECM campaign manager

`ecm_campaign` is a job backend that runs GMP-ECM with explicit parameters and
resumes where it left off. GMP-ECM performs the whole computation, including
deciding whether the factor and cofactor are prime; Numerisect only supplies the
parameters, streams the log, and records the outcome.

| Field | Meaning | Bounds |
|---|---|---|
| `ecm_b1` | stage-1 bound | 100 to 10^12 |
| `ecm_b2` | stage-2 bound or `min-max` interval | GMP-ECM syntax |
| `ecm_curves` | curves to run (`-c`) | 1 to 1,000,000 |
| `ecm_sigma` | curve parameter (`-sigma`), optionally `param:sigma` | GMP-ECM syntax |
| `ecm_param` | parametrization (`-param`) | 0 to 3 |

Stage-1 residues are written to `ecm-residues.txt` inside the job directory with
`-save`. If the job is cancelled and restarted, Numerisect passes `-resume` with that
file so completed curves are not repeated. Progress is recorded as `ecm_curves_done`.

**Reconciliation.** GMP-ECM peels factors off across successive curves and prints each
one as it is found, so the raw list can overlap and need not multiply to the input.
Passing that list to the job unchanged would produce an inconsistent factorization.
PARI/GP therefore reconciles it (`fl_reconcile`): it divides the candidates out,
reports the prime powers actually present, decides primality, and returns the remaining
cofactor. Nothing is divided out in Python. The recorded parts always multiply back to
the input, and a composite cofactor is flagged so it can be continued as a child job.

A campaign that finishes its curves without splitting the input reports an explicit
**inconclusive** failure telling the user to raise B1 or the curve count, or to switch
to SIQS or NFS. It never implies the input is prime.

## Engine tuning

`POST /api/factor-lab/tune` queues a job that runs **YAFU's own `tune`**, which works
through progressively larger inputs and measures where SIQS stops beating NFS on this
machine. Numerisect supplies the thread count and the siever directory, then reads the
`tune_info` line YAFU writes and reports the crossover it found.

**The result is a suggestion.** Numerisect never rewrites its own configuration. The
response tells you the measured crossover, the threshold currently in force, and the
environment variable to set if you agree:

```text
NUMERISECT_CADO_THRESHOLD=98
```

Tuning needs the GGNFS lattice sievers, which YAFU uses for the NFS side of the
measurement. Point `NUMERISECT_GGNFS_DIR` at the directory holding `gnfs-lasieve4I*e`;
without it the route returns 503 with that instruction rather than running a partial
measurement. A run takes many minutes, so it is a cancellable job rather than a
synchronous request, and the measured crossover appears as a warning on the finished job.

The measurement reflects this machine, this thread count and these engine builds. It is
not a general statement about the engines, and it goes stale when an engine is rebuilt.

## API routes

```text
POST /api/factor-lab/squfof
POST /api/factor-lab/special-form
POST /api/factor-lab/strategy
POST /api/factor-lab/trace
POST /api/factor-lab/certificates
POST /api/factor-lab/tune
POST /api/jobs/{id}/certificates
```

Every route saves a plain-text report and returns its exact `output/<filename>` path.
