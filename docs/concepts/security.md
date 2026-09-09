# Security and privacy

Numerisect is a local application, not a hosted service. This page states what that means
in practice, what leaves your machine, and what does not.

## Local by default

The server binds `127.0.0.1:8765`. Three protections apply to every request:

1. **Trusted-host validation.** Only `127.0.0.1`, `localhost` and IPv6 loopback are
   accepted. Anything else is refused with HTTP 400.
2. **A per-launch session token.** A cryptographically random token is generated when the
   process starts, delivered by `GET /api/session`, and stored in a `SameSite=Strict`,
   HTTP-only cookie. Every other `/api/` route requires it. The token changes on every
   restart and is never written to the repository.
3. **Origin and Fetch Metadata checks.** Explicit foreign `Origin` or `Referer` values
   and cross-site fetch metadata are rejected.

Because the token is per launch, restarting the server invalidates the session held by
an already-open tab. Its background `/api/jobs` or `/api/setup` polls can briefly appear
as HTTP 403 in the terminal. Reload or close the stale tab; later `200 OK` entries mean
the current page has recovered. This is an authorization rejection, not an engine
failure. The [full security model](../SECURITY_MODEL.md) documents the two 403 messages
and troubleshooting steps.

!!! danger "Do not bind a public interface"

    Changing the bind address to `0.0.0.0` exposes an API that can start processes and
    read local files on your machine. The loopback binding is the security boundary.

## What stays on your machine

Calculations, job state, engine logs, SQLite history and text exports never leave. There
is no telemetry, no analytics, no crash reporting and no update check.

This documentation site follows the same principle: it carries no analytics and no
tracking.

## The outbound paths that exist

Exactly three, all off by default and all requiring explicit action.

**Engine installation.** After a visible confirmation in the browser, Numerisect clones
the exact upstream commits recorded in the pinned manifest and builds them under your
state directory. It never requests root and never overwrites a system installation.

**Catalogue lookups.** OEIS and known-factor catalogues require *both*
`NUMERISECT_ALLOW_NETWORK=1` in the environment *and* `confirm_network: true` in the
individual request. Missing either sends nothing. Only the query itself is transmitted:
an integer sequence, or a single decimal integer. No credentials, identifiers or results.
Every claimed factor that comes back is verified by PARI/GP before being reported as a
divisor.

**Distributed CADO-NFS.** Sieving across machines uses CADO's own work-unit server. This
inherits CADO's trust model, which you should read before enabling it.

!!! warning "Distributed CADO has no client authentication"

    Verified from CADO-NFS's own source: clients do not authenticate to its server at
    all. An IP whitelist is the only access control, and `--certsha1` authenticates the
    server *to* the client rather than the reverse. Anyone reaching the port from a
    whitelisted address can post relations.

    [:octicons-arrow-right-24: Read the trust model](../DISTRIBUTED.md)

## Diagnostics are sanitized

The diagnostics report is designed to be shareable. It excludes hostnames, usernames, IP
addresses, absolute paths, job inputs and results. Job logs served over the API have
absolute paths redacted.

Factorization JSON manifests are different: they contain the submitted expression and the
engine command arguments, because that is what makes a result reproducible. Treat them as
calculation results rather than anonymized diagnostics.

## Command-line API use

The browser handles the token automatically. For deliberate command-line use, obtain a
cookie jar first:

```bash
curl --cookie-jar numerisect.cookies http://127.0.0.1:8765/api/session
curl --cookie numerisect.cookies \
  --header 'Content-Type: application/json' \
  --data '{"expression":"32416190071","mode":"proven"}' \
  http://127.0.0.1:8765/api/primes/check
```

Treat the cookie file as temporary local authentication material and delete it when you
are finished. The `numerisect api` command avoids the issue entirely by driving the
application in-process.

## Reporting a vulnerability

Do not open a public issue. Follow the process in
[SECURITY.md](https://github.com/reza-ghazi/Numerisect/blob/main/SECURITY.md).

[:octicons-arrow-right-24: Full security model](../SECURITY_MODEL.md)
