# Python 3.15 in CI

**Status:** ✅ Done 2026-10-12
**Commits:** `6326abe66`, `cbecf6479`, `f27e5f3da` (all green in CI)

## Asked

Python 3.15 was released. Support it, and run every CI matrix on it, before brew updates.

## Done

- `unit-testing.yml`, `functional-testing.yml`: 3.15 added to the matrix
- `wheels.yml`: `cp315-*` added to `CIBW_BUILD` (cibuildwheel builds cp315 by default since
  4.2.0, we pin 4.2.1). mypy 1.20.1 compiles for 3.15: the mypyc wheels pass `test_wheel`
  on Linux x86_64, Linux arm64 and macOS arm64
- `pyproject.toml`: 3.15 classifier; `doc/user/compiled-build.md`, `.claude/CI_TESTING.md`
- left at 3.12 on purpose, the minimum supported: linting, type checking, `.python-version`,
  mypy `python_version`, the one-file binary and the release

## Found on the way

### The matrix had only ever tested 3.12

uv takes its interpreter from `.python-version` (3.12), not from the Python `setup-python`
installs. The run before the change logged, for the 3.13 and 3.14 legs:

```
Using CPython 3.12.3 interpreter at: /usr/bin/python3.12
```

Both matrix workflows now set `UV_PYTHON: ${{ matrix.python-version }}` for the job, and a
step after `uv sync` fails the leg when the interpreter uv runs is not the one it is named
after. 3.13 and 3.14 passed on their first real run. `compat_gate` passes `--python 3.12`
itself, which wins over the variable.

### libcst 1.8.6 can not be installed on 3.15

`mutmut` pulls `libcst` in. 1.8.6 has no cp315 wheel and its PyO3 0.26 refuses to build
for an interpreter newer than 3.14, so every 3.15 job died in `uv sync`. Only `libcst`
moved in the lock, to 1.9.0, which ships cp315 wheels.

### An invalid escape in a test

`tests/unit/test_group_split_commands.py` wrote `'\;'`: a SyntaxWarning in 3.12 to 3.15,
an error in a later Python. Now `'\\;'`, the same string. Everything under `src`, `tests`
and `qa` compiles on 3.15 with warnings as errors.

### API helpers spun when ExaBGP went away

Not a 3.15 bug, it surfaced in the same CI round: the one-file binary job on macOS failed
with `LEFTOVER: ... api-health.run`. The functional runner kills ExaBGP when it retries a
test; the helper's stdin is then at EOF, `readline()` returns `''` for ever, and the loop
waiting for `done` after `status` spins. Five helpers had it (`api-health`, `api-simple`,
`api-check`, `api-blocklist`, `api-ddos-flowspec`); each reads through `read_line()`, which
exits at EOF. `tests/unit/test_api_helpers_stop_at_eof.py` hangs without the fix.

## Not done

- `test_everything` was not run as a whole: a concurrent session's unfinished zipapp work
  (`qa/bin/build_zipapp` not listed as a tool) fails `test_gates_are_wired`. CI covered the
  rest. Locally on brew's 3.15.0: 17002 unit tests passed, functional parsing 112/112,
  encoding 47/47, decoding 24/24.
