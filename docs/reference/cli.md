# Command line

The installed `numerisect` command reaches every part of the application without a
browser. `numerisect-web` starts the server.

## Friendly subcommands

```bash
numerisect serve                      # start the web application (also the default)
numerisect prime 32416190071 --certificate
numerisect factor 8051 --engine pari_trial --trial-bound 100
numerisect nth-prime 1000000
numerisect near-prime 1289 100 --direction after
numerisect symbols 1001 9907
numerisect crt 2:3 3:5 2:7
numerisect perfect-power 1073741824
```

Add `--json` **before** the subcommand for machine-readable output:

```bash
numerisect --json factor 8051 --engine pari_trial
```

Exit code 2 signals invalid input or a missing engine.

## Complete API parity

Any HTTP route is reachable directly. This drives the same FastAPI application
in-process through a minimal ASGI caller, handling the session token internally, so no
server needs to be running and no token needs managing.

```bash
numerisect routes                                  # list every route
numerisect routes --filter /api/primes             # filter by path

numerisect --json api post /api/primes/check \
  --data '{"expression":"2^89-1","mode":"proven"}'

numerisect --json api get /api/jobs --param limit=5 --param status=completed

numerisect api post /api/batch/import --data-file batch.json
```

| Flag | Meaning |
|---|---|
| `--data JSON` | Inline JSON request body |
| `--data-file FILE` | Read the JSON body from a file |
| `--param KEY=VALUE` | Query parameter; repeatable |

A non-2xx response exits with status 2 and prints the server's `detail`.

## From Python

```python
from numerisect.client import NumerisectClient

with NumerisectClient() as client:
    print(client.check_prime("32416190071")["classification"])
    job = client.factor("8051", engine="pari_trial")
    print(client.wait(job["id"])["factors"])
```

`numerisect/client.py` uses only the standard library and works unchanged in Jupyter and
SageMath against a running server. For headless use with no server at all,
`numerisect.asgi_client.LocalApiClient` drives the application in-process, which is what
`numerisect api` uses.

Working clients for Python, Node, curl, C++ and PARI/GP are in `examples/`.
