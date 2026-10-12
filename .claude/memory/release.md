# ExaBGP Release Process

## Branch Structure
- `main` — current development (6.x), worktree at `../main`
- `5.0` — stable maintenance branch for 5.0.x releases, worktree at `../5.0`

## Releasing a patch (e.g. 5.0.3)

1. Work from the `5.0` worktree at `../5.0` (NOT `git checkout 5.0`)
2. `git pull` to ensure the branch is up to date
3. Make/cherry-pick fixes as needed
4. Update `doc/CHANGELOG.rst` — add a `Version X.Y.Z` entry
5. **Commit the CHANGELOG** — `./release github` requires a clean working tree
6. Run tests (5.0 branch has no `test_everything` — run lint + pytest + functional separately)
   - Tests K and T are known flaky (timing-sensitive, pass individually)
7. Run `./release github` — this reads the version from CHANGELOG.rst and handles:
   - Updating `pyproject.toml`
   - Updating `debian/changelog`
   - Updating `README.md` and `doc/README.rst`
   - Committing, creating a signed tag, pushing to origin + upstream
6. Run `./release pypi` — builds sdist+wheel, uploads via twine

## IMPORTANT: Always use worktrees
- For 5.0 work: `cd ../5.0` — NEVER `git checkout 5.0` from main
- For main work: `cd ../main`
- Cherry-picks, fixes, releases — all done in the correct worktree

## Key details
- The `release` script reads the target version from `doc/CHANGELOG.rst`
- Tags are created WITHOUT `v` prefix (e.g. `5.0.3` not `v5.0.3`)
- The `.github/workflows/release.yml` triggers on `v*` tags (mismatch — PyPI upload is manual via twine)
- No need to create a new branch from a tag — the `5.0` branch already exists
- On main, `./release binary` builds the zipapp (dist/exabgp-<version>.pyz, doc/user/zipapp.md);
  `.github/workflows/zipapp.yml` runs it to attach the zipapp to each 6.x release and to the
  `nightly` pre-release. All release tooling stays in `./release`, no separate scripts
- On 5.0, `./release binary` builds the same zipapp (Python 3.8+), and the 5.0 branch's
  `.github/workflows/zipapp.yml` attaches it to each 5.0.x release (from 5.0.14). Once a 6.x
  release exists, it keeps the newest 6.x as GitHub's "latest": the latest/download URL must
  never serve 5.0. When editing a 5.0 release in the web UI, leave "Set as latest" unticked
