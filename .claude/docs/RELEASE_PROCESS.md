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

A release is not done until every step below is: GitHub tag and release, release
name and notes, PyPI, the next changelog version, and the issues waiting on it.
`./release github` does not publish to PyPI, `./release pypi` must be run as well.

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

### 6. Wait for the tag's workflows

The tag push runs `Zipapp` and `Build container`, and the version commit runs
`Unit Testing`. `Zipapp` creates the GitHub release, titled with the bare version
and a changelog link, and attaches `exabgp-X.Y.Z.pyz`, `exabgp.pyz` and `SHA256SUMS`.

```bash
gh run list --repo Exa-Networks/exabgp -L 5
gh run watch <id> --repo Exa-Networks/exabgp --exit-status
```

### 7. Name the GitHub release and write its notes

Ask the user for the release name before proceeding. Each release is named after
an emoji, which also heads its notes:

```bash
gh release edit X.Y.Z --repo Exa-Networks/exabgp \
  --title "ExaBGP X.Y.Z '<name>'" \
  --notes-file notes.md
```

`notes.md` follows the previous release (`gh release view 5.0.14 --json body -q .body`):
`## Version X.Y.Z <emoji>`, a short summary, the changelog link, then **New:**,
**Compatibility:** and **Fixes:**, and the zipapp download commands. A release which
only changes CI or the tests says so, and says ExaBGP itself is unchanged.

The notes go out under Thomas's account: start them with the Claude attribution line,
and show him the draft before posting.

Previous release names: 'Adhesive Bandage' 🩹 (5.0.15), 'Package' 📦 (5.0.14),
'Waving Hand' 👋 (5.0.13), 'Hugging Face' (5.0.12), 'Pinocchio' (5.0.11), 'Pi' (5.0.10).

### 8. Publish to PyPI (MANDATORY)

```bash
./release pypi       # production
./release pypi -t    # test.pypi.org
```

Builds sdist + wheel via `setup.py`, uploads both with `twine` (credentials from the
keyring). Check it is up:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://pypi.org/pypi/exabgp/X.Y.Z/json   # 200
```

The `info.version` of `https://pypi.org/pypi/exabgp/json` can lag for a while.

The Python versions PyPI lists come from the `Programming Language :: Python :: 3.x`
classifiers in `pyproject.toml`. When CI starts testing a new Python, add its
classifier before the release.

### 9. Open the next version in the changelog

```rst
Version X.Y.Z+1:

Version X.Y.Z:
```

Commit as `doc: open the changelog of X.Y.Z+1, X.Y.Z is released` and push.

### 10. Update the issues waiting on the release

Comment on each issue the release fixes with the release link, then close it.

### Binary (built by CI)

The `Zipapp` workflow builds and attaches the zipapp. To build one by hand:

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
