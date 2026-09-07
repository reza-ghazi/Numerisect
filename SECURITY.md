# Security policy

## Supported versions

Numerisect is an experimental source-only pre-release. Until a stable release
exists, security fixes are made on the current `main` branch only. Older
commits and locally modified engine pins are not supported.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability.

Use either of these private channels:

1. If GitHub displays the private-reporting form, [open a private vulnerability report](https://github.com/reza-ghazi/Numerisect/security/advisories/new).
2. Otherwise, email [contact@brightarcadia.com](mailto:contact@brightarcadia.com) with the subject `Numerisect security report`.

GitHub private vulnerability reporting must be enabled in the repository
security settings before outside reporters can use the first option. Email is
the fallback whenever that form is unavailable.

Include the Numerisect revision, operating system, Python version, affected
route or component, and minimal reproduction steps. Do not attach credentials,
session tokens, full environment dumps, complete engine or job logs, database
files, or absolute filesystem paths. Redact sensitive integer inputs when they
are not essential to the report.

The local diagnostics page is the preferred starting point: review its
sanitized text report before attaching it, because Numerisect never uploads it
automatically.

Numerisect launches external native tools and may compile optional engines from
pinned upstream Git commits after explicit confirmation. Reports involving an
upstream engine may need coordinated disclosure with that project.

No response-time or remediation guarantee is made for this pre-release
project. Please allow reasonable time for assessment and coordinated remediation
before public disclosure.
