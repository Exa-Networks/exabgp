# Test T (api-rib) RIB Update Ordering Bug in Async Mode

**Date:** 2025-11-19
**Status:** Sync mode FIXED ✅ | Async mode BROKEN ❌
**Test:** `./qa/bin/functional encoding T` (api-rib test)

---

## Summary

Functional test T fails in async mode due to incorrect BGP UPDATE message ordering. The client sends route 192.168.0.5 as the first UPDATE when it should send 192.168.0.1.

**Root cause:** Asyncio event loop callbacks (`loop.add_reader()`) process ALL API commands with higher priority than coroutine `await` points, causing all commands to be batched before any messages are sent. This breaks the interleaved API-command-processing + message-sending behavior that sync mode has.

---

## Test Results

### Sync Mode (Default) ✅
```bash
./qa/bin/functional encoding T
# Result: PASSED (100%)
```

Server receives expected sequence:
1. EOR (End-of-RIB)
2. UPDATE 192.168.0.1 (announce)
3. UPDATE 192.168.0.1 (withdraw)
4. UPDATE 192.168.0.2, 192.168.0.3 (announce)
5. ... (correct sequence)

### Async Mode ❌
```bash
env exabgp_reactor_asyncio=true ./qa/bin/functional encoding T
# Result: FAILED

Server output:
  Expected: UPDATE 192.168.0.1
  Received: UPDATE 192.168.0.5 ❌
```

---

## Technical Analysis

### How Sync Mode Works (Correct Behavior)

**Reactor Loop (loop.py:600-605):**
```python
# Sync version - manual polling
for service, command in self.processes.received():
    self.api.process(self, service, command)  # Process ONE command
    sleep = 0
```

**processes.received() behavior:**
- Uses `select.poll()` to check API process FDs
- Reads available data
- Returns ONE command at a time
- Control returns to reactor loop after each command

**Peer Loop (peer.py:702-713):**
```python
if not new_routes and self.neighbor.rib.outgoing.pending():
    new_routes = self.proto.new_update(include_withdraw)  # Create generator ONCE

if new_routes:
    try:
        for _ in range(routes_per_iteration):  # Send up to 25 messages
            next(new_routes)  # Yields for each send()
    except StopIteration:
        new_routes = None
        include_withdraw = True
```

**Key insight:** Each `yield` in the generator returns control to the reactor loop, which then polls for more API commands. This creates **interleaving**:
1. Process API command → Add route to RIB
2. Send message → Yield
3. Process next API command → Modify RIB
4. Send next message → Yield
5. Repeat...

### How Async Mode Works (Broken Behavior)

**Reactor Loop (loop.py:267-268):**
```python
# Async version - yields from queue
for service, command in self.processes.received_async():
    self.api.process(self, service, command)
```

**processes.received_async() behavior (AFTER FIX):**
```python
def received_async(self) -> Generator[Tuple[str, str], None, None]:
    # Yield only ONE buffered command (matches sync version behavior)
    if self._command_queue:
        yield self._command_queue.popleft()
```

**API Reader Callbacks (processes.py:389-458):**
```python
def _async_reader_callback(self, process_name: str) -> None:
    """Callback invoked by event loop when API process stdout has data"""
    raw_data = os.read(fd, 16384)  # Read up to 16KB

    # Extract complete lines and queue as commands
    while '\n' in raw:
        line, raw = raw.split('\n', 1)
        # Queue command for processing
        self._command_queue.append((process_name, formated(line)))
```

**The Problem:**

1. **Event loop registers readers:** `loop.add_reader(fd, self._async_reader_callback, process_name)`
2. **Callbacks have higher priority** than coroutine `await` points
3. **All data is consumed immediately:** When API process writes commands, asyncio calls the callback repeatedly in a tight loop until ALL data is read
4. **All commands queued before peer loop runs:** By the time `await anext(new_routes)` executes, `_command_queue` contains ALL commands
5. **RIB state is wrong:** When `rib.updates()` is called, it sees the final state (all routes added/modified), not the incremental state

**Timeline:**
```
Time 0: API process writes all commands to pipe
Time 1: Event loop detects data available
Time 2-10: Callback fires repeatedly, reads ALL data, queues ALL commands
Time 11: Reactor loop calls received_async() → processes first command
Time 12: Reactor loop calls received_async() → processes second command
...
Time N: Reactor loop eventually calls peer loop
Time N+1: peer loop calls rib.updates()
Time N+2: RIB returns routes in WRONG order (based on final dictionary state)
```

---

## What Was Fixed

### 1. Created Async Generator Pattern (protocol.py:671-696)

**New method:** `new_update_async_generator()`
```python
async def new_update_async_generator(self, include_withdraw: bool):
    """Async generator version of new_update - yields control between sending messages

    This matches the sync version's behavior where the generator is created once and
    iterated over multiple event loop cycles, preserving RIB state correctly.
    """
    updates = self.neighbor.rib.outgoing.updates(self.neighbor['group-updates'])
    number: int = 0
    for update in updates:
        for message in update.messages(self.negotiated, include_withdraw):
            number += 1
            await self.send_async(message)
            # Yield control after each message (matches sync version yielding _NOP)
            yield
    if number:
        log.debug(lambda: '>> %d UPDATE(s)' % number, self.connection.session())
```

**Why:** The old `new_update_async()` ran to completion, calling `rib.updates()` and sending ALL messages. The new generator version yields after each message, allowing the event loop to process other events.

### 2. Modified Peer Loop to Use Generator (peer.py:879-897)

**Before (BROKEN):**
```python
if not new_routes and self.neighbor.rib.outgoing.pending():
    await self.proto.new_update_async(include_withdraw)  # Runs to completion!
    new_routes = None
    include_withdraw = True
```

**After (FIXED for sync mode):**
```python
routes_per_iteration = 1 if self.neighbor['rate-limit'] > 0 else 25

if not new_routes and self.neighbor.rib.outgoing.pending():
    # Create the updates generator ONCE (matches sync version behavior)
    new_routes = self.proto.new_update_async_generator(include_withdraw)

if new_routes:
    try:
        # Process routes_per_iteration messages from the generator (matches sync version)
        for _ in range(routes_per_iteration):
            await anext(new_routes)
            await asyncio.sleep(0)  # Yield control to event loop
    except StopAsyncIteration:
        new_routes = None
        include_withdraw = True
```

**Why:** Matches sync version's batching behavior - create generator once, iterate over it across multiple loop cycles, send up to 25 messages per iteration.

### 3. Fixed received_async() to Yield One Command (processes.py:499-515)

**Before (BROKEN):**
```python
def received_async(self) -> Generator[Tuple[str, str], None, None]:
    # Yield all buffered commands
    while self._command_queue:
        yield self._command_queue.popleft()
```

**After (PARTIALLY FIXED):**
```python
def received_async(self) -> Generator[Tuple[str, str], None, None]:
    """Only yield ONE command per call to match sync version"""
    # Yield only ONE buffered command (matches sync version behavior)
    if self._command_queue:
        yield self._command_queue.popleft()
```

**Why:** Sync version polls and returns ONE command per reactor loop iteration. This was meant to ensure interleaving but doesn't work because callbacks still batch everything.

---

## Why the Fix Doesn't Work for Async Mode

**The fix addresses symptoms but not the root cause:**

✅ Generator pattern ensures `rib.updates()` is only called ONCE
✅ Batching matches sync version (25 messages per iteration)
✅ `received_async()` yields one command per call

❌ **BUT:** All commands are still read into `_command_queue` BEFORE any peer loop iterations

**The fundamental issue:** Asyncio event loop callback priority

```
Priority 1: Ready callbacks (loop.add_reader fired when FD has data)
Priority 2: Ready tasks (await points that are ready to resume)
Priority 3: Scheduled callbacks (call_later, etc.)
```

When API data arrives:
1. Event loop calls `_async_reader_callback()` immediately (Priority 1)
2. Callback reads 16KB and queues multiple commands
3. Callback returns, but if more data available, it fires AGAIN immediately
4. This repeats until ALL data consumed
5. ONLY THEN does event loop resume coroutines (Priority 2)
6. Peer loop's `await anext()` finally executes
7. But by now, ALL commands are queued and RIB state is final

---

## The Real Fix Required

### Option 1: Remove loop.add_reader() and Use Manual Polling

**Change:** Don't use asyncio's `loop.add_reader()`. Instead, manually poll API FDs in the reactor loop using `select.poll()` even in async mode.

**Implementation:**
```python
# In loop.py async reactor:
async def _run_reactor_async(self):
    while not self._stopping:
        # Don't call processes.setup_async_readers() at all

        # Run peers
        await self._run_async_peers()

        # Manually poll for API data (matches sync version)
        for service, command in self.processes.received():  # Use sync version!
            self.api.process(self, service, command)

        # Yield control
        await asyncio.sleep(0)
```

**Pros:**
- Matches sync mode behavior exactly
- Proper interleaving guaranteed
- No event loop priority issues

**Cons:**
- Mixing async/sync I/O (but we're already doing this for API processes)
- `select.poll()` in async context (but it's non-blocking, so OK)

### Option 2: Rate-Limit the Callback

**Change:** Make `_async_reader_callback()` read only ONE complete line, then reschedule itself.

**Implementation:**
```python
def _async_reader_callback(self, process_name: str) -> None:
    # Read only until first \n
    raw_data = os.read(fd, 1)  # Read 1 byte at a time
    raw = self._buffer.get(process_name, '') + str(raw_data, 'ascii')

    if '\n' in raw:
        line, raw = raw.split('\n', 1)
        self._command_queue.append((process_name, formated(line)))
        self._buffer[process_name] = raw
        # Don't continue reading - let event loop cycle
```

**Pros:**
- Minimal code change
- Uses asyncio properly

**Cons:**
- Inefficient (1 byte per callback invocation)
- Still doesn't guarantee interleaving due to event loop scheduling
- Complex edge cases (partial reads, buffering)

### Option 3: Process Commands in Peer Loop

**Change:** Move API command processing from reactor loop to peer loop.

**Implementation:**
```python
# In peer.py _main_async():
while not self._teardown:
    # Process ONE API command before sending messages
    for service, command in self.reactor.processes.received_async():
        self.reactor.api.process(self.reactor, service, command)
        break  # Only ONE command

    # Send messages
    if new_routes:
        await anext(new_routes)
```

**Pros:**
- Perfect interleaving
- No reactor loop changes

**Cons:**
- Architectural change (API processing in peer loop)
- Requires access to reactor from peer
- Duplicates logic across peers

---

## Recommended Solution

**Option 1** is recommended: Use manual polling even in async mode.

**Rationale:**
1. API process I/O is inherently blocking (subprocess pipes)
2. We're already mixing async (BGP sockets) and sync (API pipes)
3. Matches sync mode behavior exactly (proven correct)
4. Minimal code change
5. No event loop priority issues

**Implementation Plan:**
1. Remove `processes.setup_async_readers()` call from async reactor
2. Use `processes.received()` (sync version) in async reactor loop
3. Add `await asyncio.sleep(0)` after processing each command
4. Remove `_async_reader_callback` and related code (or keep for future use)

---

## Test Case Details

### API Commands Sequence (from etc/exabgp/run/api-rib.run)

```python
# Command 1-2
announce route 192.168.0.0/32 next-hop 10.0.0.0
clear adj-rib out

# Command 3-4
announce route 192.168.0.1/32 next-hop 10.0.0.1
clear adj-rib out

# Command 5-7
announce route 192.168.0.2/32 next-hop 10.0.0.2
announce route 192.168.0.3/32 next-hop 10.0.0.3
flush adj-rib out

# Command 8-9
announce route 192.168.0.4/32 next-hop 10.0.0.4
flush adj-rib out

# Command 10-11
clear adj-rib out
announce route 192.168.0.5/32 next-hop 10.0.0.5
```

### Expected Message Sequence (from qa/encoding/api-rib.msg)

```
01: EOR (End-of-RIB)
02: UPDATE announce 192.168.0.1
03: UPDATE withdraw 192.168.0.1
04: UPDATE announce 192.168.0.2
04: UPDATE announce 192.168.0.3
05: UPDATE announce 192.168.0.2 (flush resend)
05: UPDATE announce 192.168.0.3 (flush resend)
06: UPDATE announce 192.168.0.4
07: UPDATE announce 192.168.0.2 (flush resend)
07: UPDATE announce 192.168.0.3 (flush resend)
07: UPDATE announce 192.168.0.4 (flush resend)
08: UPDATE withdraw 192.168.0.2 (clear)
08: UPDATE withdraw 192.168.0.3 (clear)
08: UPDATE withdraw 192.168.0.4 (clear)
09: UPDATE announce 192.168.0.5
```

### What Async Mode Sends (WRONG)

```
01: EOR (correct)
02: UPDATE announce 192.168.0.5 ❌ (should be 192.168.0.1)
```

Server rejects and closes connection.

---

## Files Modified

### src/exabgp/reactor/protocol.py
- Added `new_update_async_generator()` (lines 671-696)
- Kept `new_update_async()` for backwards compatibility

### src/exabgp/reactor/peer.py
- Added `routes_per_iteration` variable (line 800)
- Modified async update handling to use generator (lines 879-897)

### src/exabgp/reactor/api/processes.py
- Modified `received_async()` to yield one command (lines 499-515)
- Added comments explaining batching issue (lines 414-420, 440-441)

---

## How to Reproduce

```bash
# Sync mode (passes)
./qa/bin/functional encoding T

# Async mode (fails)
env exabgp_reactor_asyncio=true ./qa/bin/functional encoding T

# Debug with separate server/client
# Terminal 1:
./qa/bin/functional encoding --server T

# Terminal 2:
env exabgp_reactor_asyncio=true ./qa/bin/functional encoding --client T
```

---

## Related Issues

- AsyncIO Phase 2 production validation depends on this fix
- All 72 functional tests must pass in both modes before defaulting to async
- This is a blocking issue for async mode becoming default

---

## References

- Test configuration: `qa/encoding/api-rib.ci`
- Expected messages: `qa/encoding/api-rib.msg`
- API commands script: `etc/exabgp/run/api-rib.run`
- Config file: `etc/exabgp/api-rib.conf`
- Debugging guide: `.claude/FUNCTIONAL_TEST_DEBUGGING_GUIDE.md`
- AsyncIO migration: `docs/projects/asyncio-migration/README.md`
- Phase 2 plan: `.claude/asyncio-migration/PHASE2_PRODUCTION_VALIDATION.md`

---

**Last Updated:** 2025-11-19
**Next Steps:** Implement Option 1 (manual polling in async mode)
