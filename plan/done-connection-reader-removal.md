# Remove the dead synchronous reader from Connection

**Status:** ✅ Completed 2026-09-29 (6b52293c7, 574e7e451)
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

1. [x] For each test on `reader()`, find the `reader_async()` equivalent or write it.
       `tests/unit/reactor/network/test_read_cancellation.py` shows how to drive
       `_reader_async` against a socket pair.
2. [x] Mutation-check the retargeted tests against `reader_async` (`./qa/bin/mutmut_run`),
       so the header checks are defended and not merely run
3. [x] Delete `reader()` and `_reader()`
4. [x] `./qa/bin/test_everything`

## Progress

### 2026-09-29

Work is on branch `connection-reader-removal`, in a worktree at
`$TMPDIR/wt-reader-removal` (/tmp/claude-502/wt-reader-removal). It is kept apart from
`main` because another agent was running `test_everything` on the main tree. Nothing is
committed yet, and no test has been run: the user asked for none while that run is going.

- `tests/wire_reader.py` (new): `read_message()` / `read_messages()` send bytes from a
  socketpair peer (on a thread, so a message larger than the socket buffer cannot block)
  and return what `reader_async()` makes of them. A read wanting more than was sent gets
  `LostConnection`, where the old `_reader` stubs yielded empty forever.
- All six files retargeted. The stubbed `_reader` generators are gone: header tests now
  go through the real socket reader. Mock-socket tests of `_reader` (recv_into chunks,
  ECONNRESET, timeout, errno 999) call `asyncio.run(conn._reader_async(n))`; the EAGAIN and
  "waits for data" tests use a socketpair with `call_later` delivery.
- Tests which asserted the generator stopped after a NotifyError now assert the next
  `reader_async()` call parses the following header, i.e. no half read state survives.
- Bad Message Length tests now also check `error.data` carries the erroneous Length
  (RFC 4271 6.1), where they did not before.
- Found in passing: the old `test_message_exactly_4096_bytes` stub answered the body read
  with `data[:n]` from the start, so the "body" it checked was the header again.
- `Connection.reading()` and `_rpoller` deleted too: `_reader` was their only caller. Its
  tests are deleted; tests which called it only to register a poller now call `writing()`.
- `tests/performance/README.md`: dropped `TestConnectionReaderPerformance`, a class which
  does not exist.
- ruff and mypy clean on the touched files (static only).

### 2026-09-29, tests

- The retargeted files plus `test_read_cancellation.py`: 148 passed. The integration file
  needs local port binding, which the sandbox refuses (EPERM on bind); it passes (16)
  outside it.
- Step 2 was done by hand rather than with `mutmut_run`: six edits to `reader_async`, each
  run against the retargeted files, each required to go red.
  | mutant | result |
  |---|---|
  | marker check removed | killed |
  | `length > msg_size` removed | killed |
  | `header_refuses` removed | killed |
  | Length dropped from the NotifyError data | killed |
  | `_read_header` not cleared after the body | killed |
  | `length < HEADER_LEN` removed | survives, equivalent: `header_refuses` refuses every length under 19 for all 256 types with the same NotifyError |
- `./qa/bin/test_everything` in the worktree: all 25 steps passed, 10m52s.
- `check_exa_style`: long_function 68 -> 67 (`_reader`), baseline lowered in `qa/exa_style.json`.
  ~~SUPERSEDED BY:~~ `main` had meanwhile gone to 67 in 9c889000f, so after the rebase it is 67 -> 66.
- Committed as 6b52293c7 (tests) and 574e7e451 (removal), fast-forwarded onto `main`.

## Failures

## Blockers

None.

## Resume Point

~~Commit the branch, then `git mv` this plan to done.~~ Done.

~~Step 2 and 4: once the other `test_everything` run is done, run the six
retargeted files, then `./qa/bin/mutmut_run` on `exabgp.reactor.network.connection`, then
`./qa/bin/test_everything`. `check_exa_style --update-baseline` may be able to go down
(`_reader` was a long function).~~
