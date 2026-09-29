# Remove the dead synchronous reader from Connection

**Status:** 📋 Planning (not started)
**Created:** 2026-09-29
**From:** `done-review-quality-sweep.md` item 22 (decision already taken: delete, retarget the tests)

## Why

`Connection.reader()` and `Connection._reader()` have no production caller. The daemon
reads only through `reader_async()`. The tests still exercise the dead generators, so the
header checks the daemon actually runs (bad marker: NOTIFY 1/1, bad length: 1/2,
`Message.header_refuses`) are only tested through a copy of them that nothing uses.

mypyc: `reactor/` message framing is phase 7 of `plan-mypyc.md`. Compiling two copies of
the framing, one of them dead, costs build time and hides which one the benchmarks measure.
Do this before phase 7.

## Scope, measured 2026-09-29

68 calls to `.reader()` or `._reader(` across six test files:

| File | Calls | Lines |
|---|---|---|
| `tests/unit/test_connection_advanced.py` | 35 | 1584 |
| `tests/fuzz/test_malformed_messages.py` | 9 | 654 |
| `tests/unit/test_race_conditions.py` | 7 | 612 |
| `tests/integration/test_connection_lifecycle.py` | 7 | 812 |
| `tests/fuzz/test_connection_reader.py` | 7 | 213 |
| `tests/fuzz/test_random_input_validation.py` | 3 | 423 |

`Connection.writer()` is NOT dead: `Incoming.notification()` uses it to refuse an
unconfigured peer. It stays, or moves to `writer_async()` in the same change as its caller.

## Steps

1. [ ] For each test on `reader()`, find the `reader_async()` equivalent or write it.
       `tests/unit/reactor/network/test_read_cancellation.py` shows how to drive
       `_reader_async` against a socket pair.
2. [ ] Mutation-check the retargeted tests against `reader_async` (`./qa/bin/mutmut_run`),
       so the header checks are defended and not merely run
3. [ ] Delete `reader()` and `_reader()`
4. [ ] `./qa/bin/test_everything`

## Progress

## Failures

## Blockers

None.

## Resume Point

Step 1.
