# Publishing this site

The documentation builds on every push and deploys to
<https://docs.numerisect.com>. The build itself needs nothing beyond the repository;
publishing needs a one-time repository setting.

## Current state

Pages is enabled with GitHub Actions as the source, and the site is live at
<https://reza-ghazi.github.io/Numerisect/>.

The custom domain is **not** set yet, deliberately. Setting it before the DNS record
exists would make GitHub redirect the working URL to a name that does not resolve,
taking the site offline rather than moving it.

## Remaining step: DNS

Add one record at whichever provider serves `numerisect.com`:

```text
docs.numerisect.com.   CNAME   reza-ghazi.github.io.
```

Once `dig +short docs.numerisect.com` returns a GitHub address, set the custom domain:

```bash
gh api -X PUT repos/reza-ghazi/Numerisect/pages -f cname=docs.numerisect.com
```

or use **Settings → Pages → Custom domain**. Then tick **Enforce HTTPS** once the
certificate has been issued, usually within a few minutes.

`docs/CNAME` already contains the domain and ships with every build, so the setting
survives redeploys once it is applied.

!!! warning "Order matters"

    DNS first, custom domain second. The reverse breaks the working URL.

## DNS

Point the subdomain at GitHub Pages:

```text
docs.numerisect.com.   CNAME   reza-ghazi.github.io.
```

If your DNS provider cannot add a CNAME at that name, use the four A records and four
AAAA records GitHub documents for apex-style setups instead. GitHub verifies the domain
before issuing a certificate, so allow time between the DNS change and enabling HTTPS.

## How the workflow behaves

`.github/workflows/docs.yml` has two jobs.

**Build** runs on every push and pull request that touches `docs/`, `mkdocs.yml`, or the
workflow itself. It builds with `mkdocs build --strict`, which turns warnings into
errors, so a broken cross-reference or a page missing from the navigation fails the
build rather than reaching the site.

**Publish** runs only on a push to `main`. Until Pages is enabled it fails with a 404
while the build job still passes, which is the correct signal: the site is fine, the
destination is not configured yet.

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
