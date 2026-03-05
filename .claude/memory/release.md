# ExaBGP Release Process

## Branch Structure
- `main` — current development (6.x)
- `5.0` — stable maintenance branch for 5.0.x releases

## Releasing a patch (e.g. 5.0.3)

1. Switch to the `5.0` branch
2. Make/cherry-pick fixes as needed
3. Update `doc/CHANGELOG.rst` — add a `Version 5.0.3` entry
4. Run `./qa/bin/test_everything`
5. Run `./release github` — this reads the version from CHANGELOG.rst and handles:
   - Updating `pyproject.toml`
   - Updating `debian/changelog`
   - Updating `README.md` and `doc/README.rst`
   - Committing, creating a signed tag, pushing to origin + upstream
6. Run `./release pypi` — builds sdist+wheel, uploads via twine

## Key details
- The `release` script reads the target version from `doc/CHANGELOG.rst`
- Tags are created WITHOUT `v` prefix (e.g. `5.0.3` not `v5.0.3`)
- The `.github/workflows/release.yml` triggers on `v*` tags (mismatch — PyPI upload is manual via twine)
- No need to create a new branch from a tag — the `5.0` branch already exists
