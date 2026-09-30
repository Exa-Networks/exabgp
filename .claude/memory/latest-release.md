# Always reference the latest release

Decided by Thomas, 2026-09-30, after the README still said 5.0.9 when 5.0.13 was out.

Anything which tells a user which release to install, pull, check out, upgrade to or roll
back to names the latest release of that series, in the README, `doc/` and the wiki.

- Find it before writing: `git ls-remote --tags https://github.com/Exa-Networks/exabgp.git`
  (tags have no `v` prefix), or `release` in `../5.0/src/exabgp/version.py`. Latest 4.x is
  4.2.25.
- Container images are on `ghcr.io/exa-networks/exabgp`, never Docker Hub (`exabgp/exabgp`
  does not exist). ghcr has a tag per 5.0 release (no 5.0.4), `5.0` and `5` follow the
  latest 5.0, and there is no 4.x or `main` image.
- A release is released: when a new one comes out, the version it replaces is stale
  everywhere it is given as the one to use. `./release github` updates README.md and
  doc/README.rst; the wiki it does not touch.
- History stays as history: "removed in 5.0.0", "released November 2025" are facts about
  that release. The JSON `"exabgp"` field is the JSON format version (`5.0.0` on 5.0), not
  the release, so JSON examples keep it.
