# Configuration

Numerisect is configured entirely by environment variables. There is no configuration
file, and the application never rewrites its own settings.

## Paths

In a source checkout, state lives in `./data` and reports in `./output`. An installed
wheel uses `~/.local/share/numerisect`.

| Variable | Default | Purpose |
|---|---|---|
| `NUMERISECT_STATE_DIR` | `./data` or the user data directory | Database, jobs, engine builds, setup state |
| `NUMERISECT_OUTPUT_DIR` | `./output` or the user data directory | Saved text and JSON reports |

## Factoring

| Variable | Default | Purpose |
|---|---:|---|
| `NUMERISECT_CADO_THRESHOLD` | `95` | Decimal-digit boundary for automatic YAFU-to-CADO routing |
| `NUMERISECT_PRETEST_LEVEL` | `20` | Default YAFU ECM pretest level |
| `NUMERISECT_MAX_PARALLEL_JOBS` | `1` | Simultaneous CPU-heavy jobs |
| `NUMERISECT_GGNFS_DIR` | unset | Directory holding the GGNFS lattice sievers, needed for NFS and engine tuning |

!!! tip "Tuning the threshold"

    `POST /api/factor-lab/tune` runs YAFU's own `tune` to measure where SIQS stops
    beating NFS on your machine, and reports a suggested value. It never changes the
    setting for you.

## Input limits

| Variable | Default | Purpose |
|---|---:|---|
| `NUMERISECT_MAX_EXPRESSION_CHARACTERS` | `100000` | Expression input length |
| `NUMERISECT_MAX_RESULT_DIGITS` | `100000` | Evaluated integer size |
| `NUMERISECT_MAX_BATCH_IMPORT_ITEMS` | `500` | Expanded items per batch import |
| `NUMERISECT_MAX_BATCH_RANGE_SPAN` | `10000` | Integers per imported range |

## Result cache

| Variable | Default | Purpose |
|---|---:|---|
| `NUMERISECT_RESULT_CACHE` | `1` | Enable caching of synchronous results |
| `NUMERISECT_RESULT_CACHE_MAX_ROWS` | `2000` | Maximum cached responses |
| `NUMERISECT_RESULT_CACHE_MAX_BYTES` | `2000000` | Maximum size of a cached response |

Cache keys combine the operation, the canonical parameters and an engine revision derived
from the pinned manifest plus the checksum of the executable and GP program on disk, so
rebuilding an engine invalidates the cache. Errors and inconclusive results are never
cached.

## Network, off by default

| Variable | Default | Purpose |
|---|---|---|
| `NUMERISECT_ALLOW_NETWORK` | `0` | Master switch for outbound lookups |
| `NUMERISECT_NETWORK_TIMEOUT` | `15` | Seconds |
| `NUMERISECT_OEIS_URL` | `https://oeis.org/search` | OEIS endpoint |
| `NUMERISECT_CATALOGUE_URL` | unset | Remote known-factor catalogue |

Setting the master switch is not sufficient on its own. Each request must additionally
carry `confirm_network: true`. Missing either sends nothing.

## Launcher

| Variable | Purpose |
|---|---|
| `NUMERISECT_NO_BROWSER=1` | Stop `run.sh` opening a browser |
| `NUMERISECT_INSTALL_DIR` | Install prefix for `install.sh` |

[:octicons-arrow-right-24: Security model](../SECURITY_MODEL.md)
