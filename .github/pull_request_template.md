## Summary

Describe the user-visible and architectural changes.

## Native computation

- [ ] Computationally intensive mathematics remains in an approved native engine or optimized C/C++ layer.
- [ ] Engine pins, licenses, and platform notes are updated when applicable.

## Validation

- [ ] `pytest -q`
- [ ] `ruff check .`
- [ ] `shellcheck install.sh run.sh`
- [ ] `node --check numerisect/static/app.js`
- [ ] Documentation and `CHANGELOG.md` updated

List locally available native prerequisites and any checks that could not run.

## Privacy

- [ ] The change contains no secrets, session tokens, personal paths, databases, generated results, or sensitive logs.
