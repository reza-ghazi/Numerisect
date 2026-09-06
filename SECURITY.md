# Security policy

## Supported versions

Numerisect is an experimental source-only pre-release. Until a stable release
exists, security fixes are made on the current `main` branch only. Older
commits and locally modified engine pins are not supported.

## Reporting a vulnerability

Please report suspected vulnerabilities privately to
`contact@brightarcadia.com`. Do not open a public issue until the report has
been assessed and a safe disclosure plan has been agreed.

Include the Numerisect revision, operating system, Python version, affected
route or component, and minimal reproduction steps. Do not attach secrets,
session tokens, full environment dumps, engine or job logs, database files, or
absolute filesystem paths. Redact sensitive integer inputs when they are not
essential to the report.

Numerisect launches external native tools and may compile optional engines from
pinned upstream Git commits after explicit confirmation. Reports involving an
upstream engine may need coordinated disclosure with that project.

No response-time or remediation guarantee is made for this pre-release
project. Please allow reasonable time for assessment before public disclosure.
