# Plan: the 100 ms read timeout loses partial messages and desynchronizes the session

**Status:** ✅ Implemented
**Created:** 2026-08-22
**Last Updated:** 2026-08-22
**Origin:** workspace review finding F1, verified by reproduction (below)

> **Outcome: fix B was implemented, not fix A.** The recommendation below was made before
> checking how long a `Connection` lives, and that check overturned it. See
> "Decision, revised" at the end. The original reasoning is left in place unchanged.

---

## What is wrong

`Peer._main_loop` reads each message under a 100 ms deadline and, on expiry, keeps the
connection and loops back to read again:

```python
# src/exabgp/reactor/peer/peer.py:722
try:
    message = await asyncio.wait_for(self.proto.read_message(), timeout=0.1)
except asyncio.TimeoutError:
    message = _NOP
    await asyncio.sleep(0)
```

`wait_for` cancels the coroutine it is waiting on when the deadline expires. The read it
cancels holds all of its progress in coroutine locals:

```python
# src/exabgp/reactor/network/connection.py:242-259, inside _reader_async
buffer = bytearray(number)
view = memoryview(buffer)
offset = 0
while offset < number:
    nbytes = await loop.sock_recv_into(self.io, view[offset:])
    offset += nbytes
```

`sock_recv_into` has already removed those bytes from the kernel socket buffer. They cannot
be read again. When `CancelledError` unwinds the frame, `buffer` and `offset` go with it,
and nothing on `Connection` records that a message was half read.

`reader_async` has the same problem one level up: it reads the 19 byte header, then reads
the body in a second call. Cancellation between the two loses the header even when neither
individual `_reader_async` call was interrupted mid-buffer.

The next loop iteration calls `_reader_async(Message.HEADER_LEN)` on the same socket and
reads the *tail* of the previous message as though it were a fresh header. The marker check
at `connection.py:431` fails, and the session is torn down with

    NotifyError(1, 1, 'The packet received does not contain a BGP marker')

which tells the operator, and the peer, something that never happened.

This is a regression from the asyncio migration. The generator reader kept alongside it
(`Connection.reader`, `connection.py:376`) is resumable for free: generator locals persist
across `next()`, so a caller which stops pulling loses nothing.

## Reproduction

Confirmed against a real socket, not by reading the code. A KEEPALIVE whose 19 bytes arrive
either side of the deadline:

```python
b.send(keepalive[:10])          # 10 bytes now
await asyncio.sleep(0.25)       # past the 100 ms deadline
b.send(keepalive[10:])          # the rest
b.send(keepalive)               # and a complete message behind it

# iteration 1 -> TimeoutError, 10 bytes consumed and discarded
# iteration 2 -> NotifyError(1, 1) 'does not contain a BGP marker'
```

The full script is `qa/bin/` material rather than a unit test as written; the test plan
below turns it into one.

**Trigger in production:** any message whose bytes span more than 100 ms. A single dropped
segment gives Linux a ~200 ms retransmit timeout, so one lost packet anywhere on the path
is enough. Table dumps, WAN latency, and extended-message peers all widen the window. The
symptom is an intermittent session reset with a marker error that points at the peer.

**Related:** each spurious reset increments `Peer.connection_attempts`, which is never
cleared on success (finding F12). A deployment with a non-zero `tcp.attempts` therefore
walks toward giving up on a peer permanently.

## Why the obvious fixes are wrong

**Raise the timeout.** Moves the window, does not close it. A large enough message or a
slow enough link still lands astride whatever number is chosen.

**Catch `CancelledError` inside `_reader_async` and stash the buffer.** Two problems. It
does not cover the header/body seam in `reader_async`, and swallowing `CancelledError` to
do work fights the cancellation protocol: the coroutine must re-raise, so the stash has to
happen in a `finally` and be picked up by the *next* call, which is the persistent-state
design below written in the least readable place.

**Drop the timeout and block on the read.** The loop has other work to do each pass:
keepalive timers, outbound updates, refresh, operational messages, API-driven changes. A
blocking read starves all of it.

## The two candidate fixes

### A. Retain the read task across iterations

Let the *wait* expire rather than the *read*.

```python
if self._read_task is None:
    self._read_task = asyncio.ensure_future(self.proto.read_message())
done, _pending = await asyncio.wait({self._read_task}, timeout=0.1)
if self._read_task in done:
    message = self._read_task.result()
    self._read_task = None
else:
    message = _NOP
```

- The read coroutine is never cancelled, so it keeps its own locals and resumes normally.
- No change to `Connection` at all.
- The task must be cancelled and cleared everywhere the session ends: `_reset()`,
  `_stop()`, `proto.close()`. A task left holding a closed socket is a leak with the
  reactor's lifetime.
- Exceptions now surface from `.result()` rather than from the `await`, so the
  `except Notify` / `except NetworkError` handlers around the loop body need to still see
  them at the same place.

### B. Give `Connection` a resumable read

Move header/offset/buffer onto the connection so any caller can be interrupted.

- Fixes the header/body seam as well, because the whole `reader_async` state machine
  becomes explicit rather than living in the await stack.
- Every future caller of `reader_async` inherits the resumability; A only fixes the one
  call site that remembers to hold the task.
- More code in the most safety-critical file in the tree, and the state has to be cleared
  on `close()` or a reconnect resumes into the previous session's half-read message —
  which is the same class of bug as the one being fixed.

**Recommendation: A**, with `_read_task` owned by `Peer` and cleared in the same places the
protocol is. It is the smaller change, it touches no wire parsing, and the failure mode of
getting it wrong (a dangling task) is louder than the failure mode of getting B wrong (a
resumed read across sessions). Revisit B if a second call site ever needs to interrupt a
read.

`peer.py:482` (`_read_open`) is **not** affected and should not be changed: it also uses
`wait_for`, but on timeout it raises `Notify(5, 1, ...)`, which tears the whole connection
down. A desynced socket is never read again there.

## Test plan

Write these first and watch them fail. The bug is invisible to every existing test because
they all deliver whole messages promptly.

1. **The desync itself.** A socketpair, a message delivered either side of the deadline, and
   a second complete message behind it. Assert the second read returns that message, not a
   marker error. Fails today with `NotifyError(1, 1)`.
2. **The header/body seam.** Deliver exactly the 19 byte header, wait past the deadline,
   then the body. Assert the message decodes. This is the case fix A must also cover and
   the one a naive `_reader_async`-only fix would miss.
3. **Nothing is left behind.** After a session reset, assert no read task is still pending
   (fix A) — `asyncio.all_tasks()` is enough. This is the regression the chosen fix risks
   introducing, so it needs a test of its own.
4. **The timeout still expires.** With no data at all, assert the loop still gets `_NOP`
   within the deadline and goes on to service keepalives. Otherwise a fix which simply
   blocks forever passes tests 1 and 2.
5. **Break it to prove it measures.** Before calling any of this green: revert the fix and
   require tests 1 and 2 to go red. TIGER_STYLE §5.

`./qa/bin/functional encoding --stress N` afterwards, once the local pipe-capacity problem
is worked around (see `.claude/memory/functional-tests-8kb-pipe-limit.md`) — this is exactly
the class of intermittent failure stress mode exists to find.

## Files

| File | Change |
|---|---|
| `src/exabgp/reactor/peer/peer.py` | `_read_task` field, the `asyncio.wait` loop at ~722, cancellation in `_reset`/`_stop` |
| `src/exabgp/reactor/network/connection.py` | none under fix A |
| `tests/unit/reactor/` | new test file for the five cases above |

## Risks

- **A dangling task holding a closed socket.** The reason test 3 exists. Every path which
  ends a session has to clear it, and there is more than one.
- **Exception timing moves.** Errors now come out of `.result()`; the handlers around the
  loop need to keep catching them where they do today.
- **Hard to test the real thing.** The unit tests above use a socketpair, which is not a
  peer. The functional suite is where a whole-session version belongs, and it does not run
  cleanly on this workstation yet.

## Out of scope

- F12, the lifetime `connection_attempts` counter, which this bug aggravates. Its own fix.
- The generator reader kept alongside the async one. Whether it still earns its place is a
  separate question from this defect.

## Decision, revised — B, not A

**SUPERSEDES the recommendation of A above.** Two things came out of writing the tests.

**1. The stated risk of B does not exist.** The plan warned that per-connection read state
"has to be cleared on `close()` or a reconnect resumes into the previous session's half-read
message". Checked: every session builds a fresh `Protocol` (`peer.py:416` for an incoming
connection, `:448` for an outgoing one), and `Protocol` builds a fresh `Connection`
(`protocol.py:123`, or the `Incoming` handed to `accept`). `_close()` drops the reference.
State cannot survive into the next session because the object does not. `close()` clears it
anyway, since a closed connection which is read again should not resume onto bytes that are
gone.

**2. A is not testable at this level, and the tests written for it pin B instead.** A leaves
`Connection` unchanged and makes `Peer` hold the read task, so the only honest test drives
`Peer._main_loop` — which needs a Protocol, a neighbor, an FSM, and a RIB to stand up. The
tests in the plan above cancel a read and require the next one to resume, which is a
statement about `Connection`, i.e. about B. Writing a test that matches A means either heavy
Peer scaffolding or an untested concurrency fix in the reactor.

Weighed against A's real risk — a task left holding a closed socket, needing cancellation on
every teardown path — B is the safer change, and it fixes the header/body seam for every
caller rather than for the one call site that remembers to retain its task.

## What was implemented

`src/exabgp/reactor/network/connection.py` only. `peer.py` is untouched: the loop still uses
`wait_for`, and cancelling it is now harmless.

- `Connection.__init__` gains `_read_buffer`, `_read_offset_bytes`, `_read_header`,
  `_read_length_bytes`, `_read_message_type`, and `_forget_partial_read()` to drop them.
- `_reader_async` resumes onto `_read_buffer`/`_read_offset_bytes` instead of allocating per
  call, and releases them on completion so the next read starts clean. An assertion pins the
  invariant that a resumed read asks for the size it was interrupted at.
- `reader_async` stores the validated header, length and type before reading the body, and
  clears them once the body arrives. Every error return happens *before* the header is
  stored: each one ends the session, so there is nothing to resume onto.
- `close()` calls `_forget_partial_read()`.

Note `if not number:` became `if length == Message.HEADER_LEN:` — same condition, but it
says why there is no body, and it now sits alongside an assertion that the stored-header
path always has one.

### The single-reader invariant, enumerated

`_reader_async` asserts that a resumed read asks for the size it was interrupted at, which
holds only if one read is in flight per `Connection`. ExaBGP does not run with `-O`, so a
wrong assumption here is an `AssertionError` in the read path — the escape class
TIGER_STYLE 1.1 exists to prevent. So it was enumerated rather than assumed:

- `reader_async` has exactly one caller, `Protocol.read_message` (`protocol.py:218`).
- `read_message` has three: `read_open` (`protocol.py:332`), `read_keepalive`
  (`protocol.py:349`), and the main loop (`peer.py:722`).
- All three run inside `Peer.run()`, and there is one such task per peer —
  `peer.py:891` creates it under `if self._async_task is None or self._async_task.done()`.
- They are sequential phases of one coroutine: OPEN, then KEEPALIVE, then the loop.
- The `asyncio.gather` calls in `reactor/api/command/` await flush events, not reads.

**The synchronous `Connection.reader()` has no callers at all** on this engine. It keeps its
own locals and knows nothing about the retained state, so had anything driven it against the
same connection the two would have disagreed about read progress. Nothing does.

### Forgetting is tested, not only resuming

`_forget_partial_read()` is the half that makes resuming safe, and it sits before the
`if not self.io` guard in `close()` on purpose: `_reader_async` calls `close()` on a
connection whose socket is already gone, and a clear behind that guard would run or not run
depending on which call came first. Three tests cover it, including that case, and each was
confirmed to go red with the call removed.

## Progress

| Task | Status |
|---|---|
| Reproduce on a real socket | ✅ |
| Decide between A and B | ✅ B, see above — reverses the earlier recommendation |
| Write failing tests | ✅ `tests/unit/reactor/network/test_read_cancellation.py`, 8 cases |
| Implement | ✅ |
| Break-it check | ✅ all three parts neutered separately — buffer resume, header retention, and the clear on close — each turned its own tests red |
| Verify the single-reader invariant | ✅ enumerated, see above |
| Full gate | ✅ ruff, 5165 unit+fuzz, tiger-style, 22/22 decoding, compat_gate 0 regressions |
| Stress run | ✅ 120/120 — tests 5, D, S, 0, F, R at 20 runs each, stddev ≤ 0.06s. The earlier "blocked" claim was too broad: only the 9 pipe-blocked tests cannot stress; the other 31 exercise the same read path (every session reads through it). The 9 become accessible once the runner's pipe handling is fixed (plan-review-findings-remainder.md Task 1). |

## Failures

**Test harness wrong twice, the same way both times.** First, `LoopbackConnection` set its
fields by hand and skipped `Connection.__init__`, so the new read state did not exist and
all five tests failed with `AttributeError`. Then, once the forgetting tests were added,
they failed against a working fix because the harness had stubbed `close()` out to `pass` —
the method whose behaviour they existed to check.

Both are one mistake: a fixture which replaces the thing under test ends up asserting
against itself. The harness now calls `super().__init__()` and overrides no method that any
test makes a claim about, with a comment saying why `close()` is left alone.

## Blockers

`./qa/bin/functional encoding` does not run cleanly on this workstation
(`.claude/memory/functional-tests-8kb-pipe-limit.md`). It reports the same 31 passed / 9
failed before and after this change, so it shows no regression, but the stress verification
is still owed.

## Resume point

Implemented and verified. Outstanding: `./qa/bin/functional encoding --stress N` once the
local pipe-capacity problem is worked around — this is precisely the intermittent class that
stress mode exists to catch, and it is the one check this fix has not had.

## Post-review fix: the same-tick seam (2026-08-22)

A multi-agent review of this change found (and three independent verifiers reproduced, on
Python 3.12.14 and 3.14.7) a residual race INSIDE one sock_recv_into call: the selector
callback moves the bytes out of the kernel and sets the future's result, and the deadline
cancels the task in the same event-loop batch. Task.cancel() finds the future done, marks
the task to cancel anyway, and CancelledError is raised at the await with the byte count
ready and unread — the resumed read then overwrote the consumed bytes.

Fixed with `Connection._recv_with_progress()`: the recv future is created explicitly, and on
CancelledError a completed result is recorded onto `_read_offset_bytes` before the
cancellation continues; a still-pending recv is cancelled cleanly. Two deterministic tests
drive the future by hand (`test_bytes_consumed_in_the_same_tick_as_the_cancellation_are_kept`,
`test_a_recv_cancelled_while_still_pending_is_cancelled_cleanly`) — wall-clock timing cannot
force this interleaving reliably.

### Benchmark (2026-08-22, lab/benchmark_recv_progress.py)

50,000 reads of 19 bytes over a socketpair, data-ready worst case, median of 5:

    bare await (what the fix replaced)   1.09 us/read    918k reads/s
    _recv_with_progress, Task-wrap only  4.71 us/read    212k reads/s   (first version: 4.3x cost)
    _recv_with_progress, final           0.91 us/read  1,100k reads/s   (1.2x FASTER than bare)

The final version takes buffered bytes with a direct non-blocking recv_into first — no
await point, so no cancellation window and no Task on the hot path — and only pays the
Task machinery when the socket would block, where the wait dwarfs it.
