# Support

Numerisect is an experimental, source-distributed pre-release maintained on a best-effort basis.

## Usage questions

Before opening an issue:

1. Read [README.md](README.md) and [the installation guide](docs/INSTALLATION.md).
2. Search existing issues for the same behavior.
3. Confirm the problem still occurs on the current `main` revision.
4. Record the operating system, Python version, Numerisect revision, and relevant native-engine versions.

If the terminal shows intermittent `403 Forbidden` responses for `/api/jobs` or
`/api/setup` after a restart, first close old Numerisect tabs and reload the active page.
The per-launch session token changes whenever the server starts; subsequent `200 OK`
responses mean the browser recovered normally. Persistent 403 responses from a fresh,
sole tab are covered by the [localhost security model](docs/SECURITY_MODEL.md).

Use the **Question or support request** issue form for installation and usage questions. Use the bug-report form only for reproducible defects.

Do not publish session tokens, credentials, databases, complete engine logs, confidential integer inputs, or personal filesystem paths. Provide the smallest redacted excerpt needed to understand the problem.

## Security reports

Do not use a public issue for a suspected vulnerability. Follow [SECURITY.md](SECURITY.md) to submit a private report through GitHub or by email.

## Scope

Support is not guaranteed for old commits, locally modified engine pins, unverified platforms, or third-party engine defects. Questions involving YAFU, Msieve, CADO-NFS, PARI/GP, GMP-ECM, FLINT, or Arb may need to be referred to the corresponding upstream project.
