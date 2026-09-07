# Localhost security model

Numerisect is a locally executed application, not a hosted service or static
website. `run.sh` and the Python entry point bind Uvicorn to `127.0.0.1:8765`.
Do not change this to `0.0.0.0` on an untrusted network.

The application applies three request protections:

1. trusted-host validation accepts only `127.0.0.1`, `localhost`, and IPv6
   loopback;
2. the browser obtains a cryptographically random, per-process authorization
   token from `/api/session`, also stored in a `SameSite=Strict`, HTTP-only
   cookie;
3. API requests reject explicit foreign `Origin`/`Referer` values and
   cross-site Fetch Metadata.

All `/api/` routes except the session bootstrap require the launch token. This
includes state-changing operations, installation, logs, and downloads. The
token changes each time the Python process starts and is never committed to
the repository.

## Command-line API use

The browser interface handles authorization automatically. For deliberate
command-line use, first create a local cookie jar:

```bash
curl --cookie-jar numerisect.cookies http://127.0.0.1:8765/api/session
```

Then include that cookie jar in API requests:

```bash
curl --cookie numerisect.cookies \
  --header 'Content-Type: application/json' \
  --data '{"expression":"32416190071","mode":"proven"}' \
  http://127.0.0.1:8765/api/primes/check
```

Treat the cookie file as temporary local authentication material and delete it
when finished. Do not paste session responses, local engine logs, job logs, or
filesystem locations into public issues.

## Data locality

Numerisect makes no application-level outbound request during calculations.
Native-engine installation is the exception: after a visible confirmation, it
connects to the official upstream repositories listed in the pinned engine
manifest. Calculations, SQLite state, engine logs, and text exports remain on
the machine unless the user deliberately shares them.

The diagnostics workspace follows the same rule. Its report excludes
hostnames, usernames, IP addresses, absolute paths, job inputs, and results;
the user must review and share it manually. Factorization JSON manifests are
more detailed and may include the submitted expression and engine command
arguments, so treat them as calculation results rather than anonymized
diagnostics.
