---
name: ci-python-matrix
description: uv ignores setup-python and follows .python-version, so a CI Python matrix must set UV_PYTHON; how to read CI from this sandbox
metadata:
  type: project
---

uv picks its interpreter from `.python-version` (3.12), not from the Python `actions/setup-python`
installed. Until 2026-10-12 every 3.13 and 3.14 CI leg silently ran 3.12.

**Why:** found while adding Python 3.15 (`plan/done-python-315.md`).

**How to apply:**
- any workflow with a `python-version` matrix that runs `uv` needs
  `env: UV_PYTHON: ${{ matrix.python-version }}`; unit and functional testing also check the
  interpreter after `uv sync`, copy that step to a new matrix
- adding a Python: matrices in `unit-testing.yml` and `functional-testing.yml`, `CIBW_BUILD` in
  `wheels.yml`, classifiers in `pyproject.toml`, `doc/user/compiled-build.md`,
  `.claude/CI_TESTING.md`; then check every dependency in `uv.lock` has a wheel for it (`uv sync`
  on that Python, a source build is the warning sign)
- from the Claude sandbox, `gh`, signed `git commit` and `git push` need the sandbox disabled
  (TLS, gpg agent, ssh); `gh run list --commit` returns nothing here, filter on `headSha`
- the test helpers bind ports, so local unit and functional runs fail in the sandbox with
  `PermissionError` on bind; that is the sandbox, not the code
