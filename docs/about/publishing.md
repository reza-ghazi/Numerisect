# Publishing this site

The documentation builds on every push and deploys to
<https://docs.numerisect.com>. The build itself needs nothing beyond the repository;
publishing needs a one-time repository setting.

## Current state

Pages uses GitHub Actions as its source and serves the canonical site at
<https://docs.numerisect.com>. The repository Pages setting names that custom domain,
HTTPS enforcement is enabled, and `docs/CNAME` ships the same name with every build.

The public entry point <https://numerisect.com> and its `www` name terminate at the WHC
host. LiteSpeed returns a path-preserving HTTP 301 from both names to the canonical
`docs` host. The deployed rule is kept under `hosting/apex/.htaccess` in the repository
so the small piece of hosting configuration remains reviewable and reproducible.

This separation is deliberate: GitHub Pages owns and certificates the documentation
host, while WHC owns only the redirect. Do not change the Pages custom domain to the
apex; doing so would reverse the canonical direction.

## DNS

The relevant records are:

```text
docs.numerisect.com.   CNAME   reza-ghazi.github.io.
numerisect.com.        A       <WHC hosting address>
www.numerisect.com.    CNAME   numerisect.com.
```

DNS does not perform the redirect. The apex A record reaches WHC; the LiteSpeed rule
returns the HTTP 301. The `docs` CNAME reaches GitHub Pages directly.

## Verifying production

Check all three layers after a DNS, redirect, or Pages change:

```bash
dig +short docs.numerisect.com CNAME
curl -I https://numerisect.com/
curl -I https://docs.numerisect.com/
```

The expected results are the GitHub Pages CNAME, a `301` whose `Location` starts with
`https://docs.numerisect.com/`, and a final `200`, respectively. Also test an arbitrary
path with a query string: the redirect must preserve both.

## How the workflow behaves

`.github/workflows/docs.yml` has two jobs.

**Build** runs on every push and pull request that touches `docs/`, `mkdocs.yml`, or the
workflow itself. It builds with `mkdocs build --strict`, which turns warnings into
errors, so a broken cross-reference or a page missing from the navigation fails the
build rather than reaching the site.

**Publish** runs only on a push to `main` or a manual dispatch from `main`. It deploys the
artifact to the already configured GitHub Pages environment; the environment URL records
the resulting canonical site address.

## Building locally

```bash
pip install '.[docs]'
mkdocs serve          # live reload at http://127.0.0.1:8000
mkdocs build --strict # exactly what CI runs
```

Without installing anything permanently:

```bash
uvx --with mkdocs-material --from mkdocs mkdocs serve
```

## Conventions

- The site is built from `docs/`, the same directory the repository serves on GitHub, so
  there is one source of truth. Links between pages are sibling-relative and work in both
  places.
- Links to files outside `docs/` use absolute GitHub URLs, because a relative path out of
  the documentation root does not resolve on the site.
- Mathematics uses `\( … \)` and `\[ … \]` with `pymdownx.arithmatex` in generic mode.
  **Display blocks need a blank line above and below**, or Python-Markdown consumes the
  backslash and the expression disappears silently.
- Every page in `docs/` must appear in the `nav` in `mkdocs.yml`. A test enforces this,
  because an unlisted page is published but unreachable.
- The site carries no analytics or tracking, and a test enforces that too.
