# ExaBGP Release Process

## Quick Reference

```bash
./release show current   # version from src/exabgp/version.py
./release show release   # version from doc/CHANGELOG.rst
./release github         # full release (tag + push)
./release pypi           # publish to PyPI
./release pypi -t        # publish to test PyPI
./release binary <path>  # create zipapp binary
./release cleanup        # remove build artifacts
DRY=1 ./release github   # dry run (no files written, no git commands)
```

## Step-by-Step Release

### 1. Update CHANGELOG -- MUST DO BEFORE RELEASE

The release script reads the version from `doc/CHANGELOG.rst`. If changes
are not listed under a new version section, the release will fail (version
already tagged) or release without the new notes. Every fix/feature commit
must be added here before running `./release github`.

Edit `doc/CHANGELOG.rst` - add a new version section at the top:

```rst
Version 5.0.2:
 * Fix: description of fix
 * Feature: description of feature

Version 5.0.1:
 ...
```

The format must be `Version X.Y.Z:` (the script skips the explanation
header and finds the first line starting with `version `).

### 2. Check JSON and TEXT API format versions

`Version.JSON` and `Version.TEXT` in the `release` script control the API
format version written to `version.py`. These are NOT the release version.
They only change when the JSON or text output format itself changes.

Review `release` lines with `JSON =` and `TEXT =`. If this release changes
the JSON or text API output format, bump them. Otherwise leave them alone.

Current values and what they mean:
- `JSON`: version included in JSON API responses (`"exabgp": "X.Y.Z"`)
- `TEXT`: version included in text API responses

Do NOT set these to the release version automatically.

### 3. Commit all changes

All code changes, CHANGELOG edits, and any other modifications MUST be
committed before running `./release github`. The release script only
expects to modify version-related files. If it finds other modified
tracked files, it will abort.

### 4. Run tests

```bash
ulimit -n 64000
ruff format && ruff check
env exabgp_log_enable=false pytest --cov --cov-reset tests/
killall -9 python; ./qa/bin/functional encoding
./qa/bin/functional parsing
```

### 5. Release to GitHub

```bash
./release github
```

This command:
- Reads current version from `src/exabgp/version.py`
- Reads next version from `doc/CHANGELOG.rst`
- Validates semver (must be a patch/minor/major bump from latest tag)
- Updates these files automatically:
  - `src/exabgp/version.py` (release, commit hash, json/text from script constants)
  - `debian/changelog` (version + timestamp)
  - `README.md` (version string replacement)
  - `doc/README.rst` (version string replacement)
  - `pyproject.toml` (version string replacement)
  - `sbin/exabgp` (version string replacement)
- Commits: "updating version to X.Y.Z"
- Creates signed tag: `git tag -s -a X.Y.Z -m "release X.Y.Z"`
- Pushes the specific tag and commits to `origin`
- Pushes to `upstream` if that remote exists, skips otherwise

### 6. Publish to PyPI

```bash
./release pypi       # production
./release pypi -t    # test.pypi.org
```

Builds sdist + wheel via `setup.py`, uploads both with `twine`.

### 7. Create binary (optional)

```bash
./release binary ./exabgp-5.0.2
```

## Version Files

| File | Updated by |
|------|-----------|
| `doc/CHANGELOG.rst` | You (manually, step 1) |
| `src/exabgp/version.py` | `./release github` |
| `debian/changelog` | `./release github` |
| `README.md` | `./release github` |
| `doc/README.rst` | `./release github` |
| `pyproject.toml` | `./release github` |
| `sbin/exabgp` | `./release github` |

## Version Validation

Valid bumps from e.g. `5.0.1`:
- `5.0.2` (patch)
- `5.1.0` (minor)
- `6.0.0` (major)

Any other version will be rejected.

## Common Issues

- **"version was already released"**: tag already exists, pick a different version
- **"more than one file is modified"**: commit all non-version changes first (step 3)
- **"invalid new version in CHANGELOG"**: check `Version X.Y.Z:` format
- **"not one of the candidates, aborting"**: version must be a patch/minor/major bump from latest tag
- **Push fails**: verify SSH keys, test `git push` manually
- **No rollback**: if the release partially fails (e.g., push fails after tag is created),
  you will need to manually clean up the local tag and committed version changes
