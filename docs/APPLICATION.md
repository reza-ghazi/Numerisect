# Application infrastructure

Numerisect 0.6.0 adds workspace, search, export, scheduling, caching, adapter, and
optional catalogue facilities around the native computation core. Nothing in this
document performs mathematics: every value shown was produced by PARI/GP, FLINT/Arb,
YAFU, Msieve, GMP-ECM, CADO-NFS, primesieve, or primecount and is only stored,
filtered, or reformatted here.

## Command-line and API parity

The installed `numerisect` command reaches every HTTP route without starting a
browser or opening a socket. `numerisect api` drives the same FastAPI application
in-process through a minimal ASGI caller, attaching the per-launch session token
automatically.

```bash
numerisect routes --filter /api/primes        # list matching routes
numerisect --json api post /api/primes/check --data '{"expression":"32416190071","mode":"proven"}'
numerisect --json api get /api/jobs --param limit=5 --param status=completed
numerisect api post /api/batch/import --data-file batch.json
```

`--data` takes an inline JSON body, `--data-file` reads one from disk, and
`--param KEY=VALUE` (repeatable) adds query parameters. A non-2xx response exits
with status 2 and prints the server's `detail`.

## Exports

Completed work is exportable in six formats. The engine-produced content is never
recomputed; only the container changes.

| Format | Extension | Notes |
|---|---|---|
| `json` | `.json` | Full record including every factor |
| `jsonl` | `.jsonl` | One JSON object per line, job record first |
| `csv` | `.csv` | RFC 4180, job summary followed by a factor table |
| `markdown` | `.md` | GitHub-flavoured tables, `|` escaped |
| `latex` | `.tex` | `tabular` environments; report bodies use `verbatim` |
| `pari` | `.gp` | Assignable record plus a product check you can rerun in GP |

```bash
curl --cookie jar "http://127.0.0.1:8765/api/exports/jobs/<job-id>?format=pari"
curl --cookie jar "http://127.0.0.1:8765/api/exports/jobs?format=csv&status=completed"
curl --cookie jar "http://127.0.0.1:8765/api/exports/reports/<file>.txt?format=markdown"
```

The PARI export is deliberately checkable. Loading it defines `N`, `factors`, and
`exponents`, then verifies `prod(factors[i]^exponents[i]) == N` in GP itself.

## Batch import

`POST /api/batch/import` accepts a TXT, CSV, or JSON document containing decimal
integers, inclusive ranges (`10..14`), safe integer expressions, and polynomial
families (`n^2+n+41 for n=1..100`). Ranges and families are expanded by PARI/GP
through `numerisect/workspace.gp`, never in Python.

| Limit | Default | Environment variable |
|---|---:|---|
| Expanded items per import | 500 | `NUMERISECT_MAX_BATCH_IMPORT_ITEMS` |
| Range span | 10000 | `NUMERISECT_MAX_BATCH_RANGE_SPAN` |
| Document size | 2 MB | fixed |
| Family exponent | 64 | fixed |

Set `queue: true` to enqueue every expanded value as a factorization job at the
requested priority.

## Workspaces

A workspace records a name, free-text notes, a list of job identifiers, a list of
saved report filenames, and arbitrary interface state. Workspaces are local rows in
the existing SQLite database; deleting one never deletes the jobs or reports it
references.

```text
POST   /api/workspaces
GET    /api/workspaces
GET    /api/workspaces/{id}
POST   /api/workspaces/{id}
DELETE /api/workspaces/{id}
```

## Search

`GET /api/jobs` accepts `q`, `status`, `engine`, `since`, `until`, `sort`, `order`,
`limit`, and `offset`. `q` matches the expression, the decimal input, and the stored
factor list. Every clause is parameterized SQL; quoting characters in `q` are treated
as data.

`GET /api/reports` searches an index of saved report files by `q` and `kind`. The
index is populated automatically whenever a report is written, through a listener
registered on `numerisect.outputs`; an indexing failure can never prevent a report
from being saved.

## Result caching

Synchronous prime, number-theory, and zeta responses can be cached by
`(operation, canonical parameters, engine revision)`. The engine revision combines the
pinned manifest revision with the SHA-256 of the executable and of the `.gp` program
actually on disk, so rebuilding an engine or editing a GP file invalidates the cache.

Responses carry `cached: true` when served from the cache. Send `use_cache: false` in
any request to bypass it. **Errors and inconclusive results are never cached**: a
payload is rejected if it carries a `detail` key, an inconclusive verdict, or a
truncation flag at any depth.

```text
GET    /api/cache          cache size and hit counts
DELETE /api/cache          clear all, or one operation with ?operation=/api/...
```

| Knob | Default | Environment variable |
|---|---:|---|
| Enabled | on | `NUMERISECT_RESULT_CACHE` |
| Maximum rows | 2000 | `NUMERISECT_RESULT_CACHE_MAX_ROWS` |
| Maximum response bytes | 2000000 | `NUMERISECT_RESULT_CACHE_MAX_BYTES` |

## Scheduling, limits, and lifecycle

Jobs carry a priority from −10 to 10. The dispatcher orders queued work by priority
first and creation time second, still honouring `NUMERISECT_MAX_PARALLEL_JOBS`.

```text
GET  /api/queue                       queued and running jobs in dispatch order
POST /api/jobs/{id}/priority          {"priority": 5}
POST /api/jobs/reorder                {"job_ids": [...]}
POST /api/jobs/{id}/pause             SIGSTOP the process group
POST /api/jobs/{id}/resume-paused     SIGCONT the process group
```

Per-job resource limits are applied to the engine process: `cpu_seconds` becomes
`RLIMIT_CPU`; Linux enforces `memory_mb` with `RLIMIT_AS`; and watchdogs enforce
`wall_seconds` and the aggregate process-group resident-set limit on macOS. Darwin needs
the RSS watchdog because its loader reserves a large virtual address map, `RLIMIT_DATA`
prevents PARI/GP from starting at practical values, and `RLIMIT_RSS` is advisory.
Exceeding a limit fails the job with an explicit `limit_exceeded` reason, and all three
requested values are recorded in the reproducibility manifest.

Pause uses `SIGSTOP`, which every supported engine tolerates because it requires no
cooperation from the process. A paused job holds its worker slot and its scratch
directory. This is independent of CADO-NFS snapshot resume, which restarts a stopped
job from its most recent parameter snapshot.

## Engine adapters

`numerisect/adapters.py` describes each engine declaratively: the command, a version
probe, an argument-array template, and output patterns for factors and phases. The
built-in engines are registered through the same interface they expose to users.

Additional adapters are read from `STATE_DIR/adapters/*.toml`. They are
**declarative only**: command templates are argument arrays with a fixed set of
named placeholders, and output parsing is regular expressions. No adapter file can
execute arbitrary code, interpolate a shell string, or introduce a new placeholder.
`GET /api/adapters` lists what loaded and reports any file that was rejected.

## Performance history

`GET /api/history/performance` groups completed jobs by engine and decimal-digit
bucket and reports counts and runtimes. These are local measurements on one machine;
they depend on hardware, thread count, and the specific input, and they are not
benchmarks of the engines in general.

## Optional external catalogues

Numerisect is offline by default and makes no outbound request during any
calculation. Catalogue lookups are the only exception, and they require **two**
independent approvals:

1. the process must start with `NUMERISECT_ALLOW_NETWORK=1`, and
2. the individual request must carry `confirm_network: true`.

Missing either one returns HTTP 403 and sends nothing. Only the query itself leaves
the machine: an integer sequence for OEIS, or a single decimal integer for a factor
catalogue. No credentials, identifiers, results, or telemetry are ever transmitted.
All requests use `urllib` over https with a timeout and a bounded response size.

```text
GET  /api/catalogues            local catalogue files and the permission state
POST /api/catalogues/oeis       {"terms": ["2","3","5","7"], "confirm_network": true}
POST /api/catalogues/factors    {"expression": "2^101-1", "remote": false}
```

Local catalogue files in `STATE_DIR/catalogues` (`.txt` as `N = p * q` lines, or
`.json`) are read with no network access at all, which is the recommended way to use
Cunningham-project tables.

**Catalogue results are unverified external claims.** Every claimed factor is passed to
PARI/GP (`ws_verify_factors`), which decides divisibility and primality, checks whether
the claimed factors multiply to the input, and returns the remaining cofactor. The
response reports `verified` per claim plus `product_matches` and `cofactor`. No
divisibility or primality decision is made in Python.

| Knob | Default | Environment variable |
|---|---|---|
| Network permitted | off | `NUMERISECT_ALLOW_NETWORK` |
| Request timeout | 15 s | `NUMERISECT_NETWORK_TIMEOUT` |
| OEIS endpoint | `https://oeis.org/search` | `NUMERISECT_OEIS_URL` |
| Factor catalogue endpoint | unset | `NUMERISECT_CATALOGUE_URL` |
| GGNFS siever-directory override | unset; automatic discovery is used | `NUMERISECT_GGNFS_DIR` |

## Client examples and notebooks

`examples/` contains working clients for Python, Node, curl, C++ (libcurl), and
PARI/GP, each showing the session handshake first. `numerisect/client.py` is a
standard-library-only client used by the Python example:

```python
from numerisect.client import NumerisectClient

with NumerisectClient() as client:
    print(client.check_prime("32416190071")["classification"])
    job = client.factor("8051", engine="pari_trial")
    print(client.wait(job["id"])["factors"])
```

The same class works unchanged in Jupyter and SageMath against a running server. For
headless use with no server at all, `numerisect.asgi_client.LocalApiClient` drives the
application in-process, which is what `numerisect api` uses.
