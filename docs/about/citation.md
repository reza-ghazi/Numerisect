# Citing Numerisect

Numerisect releases are preserved independently of GitHub by Zenodo. Use the
version-specific DOI when the exact source used for a calculation matters:

> Ghazi, Reza. (2026). *Numerisect: Multi-Engine Integer Factorization and Prime
> Analysis* (Version 0.7.0) [Computer software]. Zenodo.
> <https://doi.org/10.5281/zenodo.22679027>

## Which DOI should I use?

| Purpose | DOI |
|---|---|
| Cite the exact immutable `v0.7.0` source snapshot | [10.5281/zenodo.22679027](https://doi.org/10.5281/zenodo.22679027) |
| Refer to Numerisect as a project across all released versions | [10.5281/zenodo.22679026](https://doi.org/10.5281/zenodo.22679026) |

The first DOI identifies one fixed release. The second is the concept DOI: it remains
the stable project-level identifier as Zenodo adds later versions to the same record.
For reproducible computational work, prefer the version DOI and also record the native
engine versions and executable checksums contained in the saved Numerisect report.

## Machine-readable metadata

The repository-root
[`CITATION.cff`](https://github.com/reza-ghazi/Numerisect/blob/main/CITATION.cff)
contains the title, creator, version, release date, licence, keywords, abstract, and
version DOI in Citation File Format 1.2. GitHub exposes it through **Cite this
repository**, and common reference managers can import the DOI directly.

## Preserved release

Zenodo archived the source-only GitHub release as
`reza-ghazi/Numerisect-v0.7.0.zip`. The public record identifies it as software,
records the GPL-3.0-or-later licence, and links it to the exact Git tag.

- [Zenodo record for version 0.7.0](https://zenodo.org/records/22679027)
- [GitHub release `v0.7.0`](https://github.com/reza-ghazi/Numerisect/releases/tag/v0.7.0)
- [Version history](changelog.md)

No binary package is implied by the DOI. The archived object is the immutable source
snapshot; installation remains source-based as described in the
[installation guide](../getting-started/installation.md).
