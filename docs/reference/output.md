# Reports and export formats

Every operation that produces a result writes a plain-text report and returns its exact
`output/<filename>` path. The download link is a convenience, not the only record.

## Why reports are automatic

Long computations are expensive, and a result that exists only in a browser tab is one
reload away from being lost. Numerisect writes the report before responding, and the
response tells you where it went. Reports are also indexed, so `GET /api/reports` can
search them later by text or kind.

## Factorization manifests

A completed factorization additionally produces a JSON manifest beside its text report,
under the schema `org.numerisect.factorization-manifest.v1`. It records:

- The submitted expression and the integer it evaluated to.
- Every command run, as argument arrays.
- The pinned revision and the SHA-256 of each engine executable used.
- The parameters, thread count and any resource limits applied.
- The factors, with provenance per factor.

This is what makes a result reproducible and auditable. It contains the submitted
expression and engine arguments, so treat it as a calculation result rather than an
anonymized diagnostic.

## Export formats

| Format | Extension | Notes |
|---|---|---|
| `json` | `.json` | Full record including every factor |
| `jsonl` | `.jsonl` | One object per line, job record first |
| `csv` | `.csv` | RFC 4180; job summary then a factor table |
| `markdown` | `.md` | GitHub-flavoured tables, separators escaped |
| `latex` | `.tex` | `tabular` environments; report bodies use `verbatim` |
| `pari` | `.gp` | An assignable record plus a product check you can rerun |

```bash
curl --cookie jar "http://127.0.0.1:8765/api/exports/jobs/<id>?format=pari"
curl --cookie jar "http://127.0.0.1:8765/api/exports/jobs?format=csv&status=completed"
curl --cookie jar "http://127.0.0.1:8765/api/exports/reports/<file>.txt?format=markdown"
```

The PARI export is deliberately checkable rather than merely readable. Loading it defines
`N`, `factors` and `exponents`, then verifies that the product equals the input inside GP
itself, so the export can be validated without trusting Numerisect.

## Where reports live

`./output` in a source checkout, or `~/.local/share/numerisect/output` for an installed
copy. Override with `NUMERISECT_OUTPUT_DIR`. Generated reports are excluded from version
control.
