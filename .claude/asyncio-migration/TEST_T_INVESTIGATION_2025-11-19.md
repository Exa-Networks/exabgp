# Test T Investigation - 2025-11-19

**Status:** Routes queuing out of order, clear commands not executing
**Async mode:** 70/72 tests pass (97.2%) - Tests T & U fail
**Sync mode:** 72/72 tests pass (100%)

---

## Critical Findings

### Issue 1: Routes Sent in Wrong Order

**Expected order (from api-rib.run):**
1. 192.168.0.0/32 - announced, then immediately cleared (should NOT be sent)
2. 192.168.0.1/32 - announced, sent, then withdrawn
3. 192.168.0.2/32 - announced, sent
4. 192.168.0.3/32 - announced, sent
5. Flush - resend 0.2 and 0.3
6. 192.168.0.4/32 - announced, sent
7. Flush - resend 0.2, 0.3, 0.4
8. Clear all - withdraw 0.2, 0.3, 0.4
9. 192.168.0.5/32 - announced, sent

**Actual order (async mode logs from 00:58:39):**
```
[Protocol.new_update_async] Processing update: 192.168.0.0/32 next-hop 10.0.0.0  ❌ Should be cleared
[Protocol.new_update_async] Processing update: 192.168.0.1/32 next-hop 10.0.0.1  ❌ Should be withdrawn
[Protocol.new_update_async] Processing update: 192.168.0.2/32 next-hop 10.0.0.2  ✅
[Protocol.new_update_async] Processing update: 192.168.0.3/32 next-hop 10.0.0.3  ✅
[Protocol.new_update_async] Processing update: 192.168.0.4/32 next-hop 10.0.0.4  ✅
[Protocol.new_update_async] Processing update: 192.168.0.5/32 next-hop 10.0.0.5  ✅
[Protocol.new_update_async] Sending message #1
sending TCP payload (  49) ...40 0504 0000 0064 20C0 A800 05  ← Route 0.5 sent FIRST
[Protocol.new_update_async] Processing update: 192.168.0.2/32 next-hop 10.0.0.2  ← Flush duplicate
[Protocol.new_update_async] Sending message #2
sending TCP payload (  49) ...40 0504 0000 0064 20C0 A800 02  ← Route 0.2
[Protocol.new_update_async] Processing update: 192.168.0.3/32 next-hop 10.0.0.3  ← Flush duplicate
[Protocol.new_update_async] Sending message #3
sending TCP payload (  49) ...40 0504 0000 0064 20C0 A800 03  ← Route 0.3
[Protocol.new_update_async] Processing update: 192.168.0.2/32 next-hop 10.0.0.2  ← Second flush
[Protocol.new_update_async] Sending message #4
[Protocol.new_update_async] Processing update: 192.168.0.3/32 next-hop 10.0.0.3  ← Second flush
[Protocol.new_update_async] Sending message #5
[Protocol.new_update_async] Processing update: 192.168.0.4/32 next-hop 10.0.0.4  ← Second flush
[Protocol.new_update_async] Sending message #6
>> 6 UPDATE(s)
```

**Problem:** All 6 routes (0.0, 0.1, 0.2, 0.3, 0.4, 0.5) are queued in RIB before ANY are sent.

### Issue 2: Clear Commands Not Executing

**api-rib.run command sequence:**
```python
# Line 77-78: Announce then immediate clear
sys.stdout.write('announce route 192.168.0.0/32 next-hop 10.0.0.0\n')
sys.stdout.write('clear adj-rib out\n')
sys.stdout.flush()
# Expected: Route 0.0 NEVER sent (cleared before transmission)
# Actual: Route 0.0 appears in processing queue

# Line 84-89: Announce, wait, clear
sys.stdout.write('announce route 192.168.0.1/32 next-hop 10.0.0.1\n')
sys.stdout.flush()
if not wait_for_ack(): pass
sys.stdout.write('clear adj-rib out\n')
sys.stdout.flush()
# Expected: Route 0.1 sent, then withdrawn
# Actual: Route 0.1 appears in final queue (not withdrawn)

# Line 118: Clear all before final announce
sys.stdout.write('clear adj-rib out\n')
sys.stdout.flush()
# Expected: Routes 0.2, 0.3, 0.4 withdrawn
# Actual: No visible withdrawals
```

**Evidence clear commands not executing:**
1. Route 0.0 should be cleared before send - but appears in queue
2. Route 0.1 should be withdrawn - but appears in queue
3. Routes 0.2, 0.3, 0.4 should be withdrawn - no withdrawal messages seen
4. Total messages sent: 6 UPDATEs (all announcements, zero withdrawals)

### Issue 3: Test Daemon Response

**Test daemon expectation (from api-rib.msg):**
```
msg recv FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:0031:02:00000015400101004002004003040A0000014005040000006420C0A80001
                                                                                    ^^^^^^^^^^^^^^^^
                                                                                    Route 0.1 expected
```

**Actual first message received:**
```
msg recv FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:0031:02:00000015400101004002004003040A0000054005040000006420C0A80005
                                                                                    ^^^^^^^^^^^^^^^^
                                                                                    Route 0.5 received
```

Test daemon expects route 0.1 first, receives route 0.5 first → **test fails**.

---

## Command Execution Flow Analysis

### Working Sync Mode

```
1. API process writes: announce 0.0
2. Reactor reads command, queues to _command_queue
3. Main loop processes command via api.process()
4. Command handler modifies RIB (_new_nlri['0.0'] = change)
5. API process writes: clear adj-rib out
6. Reactor reads command, queues
7. Main loop processes clear command
8. Clear handler calls neighbor_rib_out_withdraw()
9. RIB.withdraw() removes routes from _new_nlri
10. Peer loop calls new_update() - sees empty RIB
11. Result: Route 0.0 never sent ✅
```

### Broken Async Mode

```
1. API process writes: announce 0.0
2. Event loop callback reads command, queues
3. Main loop processes command via api.process_async()
4. Command handler schedules async callback (NOT executed yet)
5. API process writes: clear adj-rib out
6. Event loop callback reads command, queues
7. Main loop processes clear command
8. Clear handler schedules async callback (NOT executed yet)
9. ... more commands processed and scheduled ...
10. Peer loop calls new_update_async() - reads RIB
11. RIB still has ALL routes (callbacks haven't executed!)
12. THEN callbacks execute (too late)
13. Result: All routes sent in wrong order ❌
```

**Root cause:** Callbacks scheduled but not executed before peer loop reads RIB.

---

## Key Code Locations

### Command Processing
- `loop.py:228-229` - API command processing loop (async mode)
- `loop.py:589-594` - API command processing loop (sync mode)

### Command Handlers
- `announce.py:31-68` - Announce route handler (schedules callback)
- `rib.py:178-210` - Clear adj-rib handler (schedules callback)
- `rib.py:148-176` - Flush adj-rib handler (schedules callback)

### Async Scheduler
- `asynchronous.py:31-41` - Schedule callback (append to queue)
- `asynchronous.py:88-138` - Execute callbacks (_run_async)
- `loop.py:232` - Sync mode: `self.asynchronous.run()`
- `loop.py:225` - Async mode: `await self._run_async_peers()` (peer loop runs BEFORE callbacks)

### RIB Operations
- `outgoing.py:207-221` - Update RIB (_update_rib)
- `outgoing.py:103-110` - Clear RIB (withdraw)
- `outgoing.py:223-296` - Generate updates (read from RIB)

---

## Timeline Comparison

### Sync Mode (Working)
```
T=0: Command "announce 0.0" arrives
T=1: Command processed → callback scheduled
T=2: Callback executes → RIB modified (0.0 added)
T=3: Command "clear" arrives
T=4: Command processed → callback scheduled
T=5: Callback executes → RIB modified (0.0 removed)
T=6: Peer loop calls new_update()
T=7: RIB.updates() returns empty (0.0 was removed)
T=8: Nothing sent ✅
```

### Async Mode (Broken)
```
T=0: Command "announce 0.0" arrives
T=1: Command processed → callback scheduled
T=2: Command "announce 0.1" arrives
T=3: Command processed → callback scheduled
T=4: ... all 9 commands arrive and get scheduled ...
T=5: Peer loop calls new_update_async()
T=6: RIB.updates() returns ALL routes (callbacks not executed yet!)
T=7: All routes sent in order they were added to RIB
T=8: THEN callbacks execute (too late) ❌
```

**The problem:** In async mode, `await self._run_async_peers()` (line 225) runs BEFORE `self.asynchronous.run()` (line 232), so peer loop reads RIB before command callbacks modify it.

---

## Attempted Fixes (Session 2025-11-19)

### Fix 1: One Command Per Iteration
**Change:** `loop.py:238` - Added `break` to process one command per iteration
**Rationale:** Prevent batch processing, ensure atomic execution
**Result:** ❌ Broke sync mode (test T failed)
**Why:** Changed command processing semantics that sync mode relies on

### Fix 2: Remove Yield Points
**Changes:**
- `announce.py:57` - Removed `await asyncio.sleep(0)`
- `rib.py:155` - Removed `await asyncio.sleep(0)` from flush handler
- `rib.py:188` - Removed `await asyncio.sleep(0)` from clear handler

**Rationale:** Prevent callbacks from yielding control mid-execution
**Result:** ❌ No improvement (callbacks still not executing before peer loop)

### Fix 3: Coroutine Completion Tracking
**Change:** `asynchronous.py:100-144` - Don't re-queue completed coroutines
**Rationale:** Coroutines complete in one await, shouldn't be re-queued like generators
**Result:** ❌ Broke sync mode
**Why:** Changed re-queue logic affected generators

**All fixes reverted** - returned to working baseline.

---

## Unit Tests Created

**File:** `tests/unit/test_rib_flush_async.py`
**Tests:** 10 comprehensive tests
**Status:** ✅ All pass

**Test coverage:**
1. `test_command_queue_fifo` - Verify FIFO ordering with popleft()
2. `test_command_queue_lifo_would_fail` - Demonstrate LIFO (pop) gives wrong order
3. `test_async_scheduler_fifo` - Verify async scheduler maintains FIFO
4. `test_clear_completes_atomically` - Verify clear completes before announce
5. `test_no_interleaving_with_one_command_per_iteration` - Verify atomic execution
6. `test_flush_sequence_from_test_t` - Reproduce api-rib.run flush pattern
7. `test_no_yield_in_simple_callbacks` - Verify callbacks execute atomically
8. `test_callback_with_yield_can_interleave` - Demonstrate interleaving issue
9. `test_announce_then_immediate_clear` - Test lines 77-78 pattern
10. `test_announce_wait_then_clear` - Test lines 84-89 pattern

**Purpose:** Catch regressions in command ordering and atomic execution during future fixes.

---

## Verified Correct Behavior

✅ **FIFO ordering** - Commands use `popleft()` correctly (not `pop()`)
✅ **Command queueing** - API commands queued in correct order
✅ **Callback scheduling** - Callbacks scheduled in FIFO order
✅ **Async scheduler** - Uses `popleft()` to dequeue in FIFO order
✅ **Unit tests** - All 1386 unit tests pass (including 10 new RIB tests)
✅ **Sync mode** - 72/72 functional tests pass

---

## Next Investigation Steps

### 1. Verify Callback Execution Timing

Add logging to track when callbacks execute vs when peer loop reads RIB:

```python
# In loop.py async mode
log.debug('BEFORE _run_async_peers()')
await self._run_async_peers()  # Peer loop
log.debug('AFTER _run_async_peers(), BEFORE asynchronous.run()')
self.asynchronous.run()  # Execute callbacks
log.debug('AFTER asynchronous.run()')
```

**Hypothesis:** Peer loop (`_run_async_peers`) executes before callbacks (`asynchronous.run`), reading stale RIB state.

### 2. Test Execution Order Change

Try swapping lines 225 and 232 in `loop.py`:

```python
# Current (broken):
await self._run_async_peers()  # Line 225 - peers run first
self.asynchronous.run()  # Line 232 - callbacks run second

# Test:
self.asynchronous.run()  # Execute callbacks FIRST
await self._run_async_peers()  # THEN run peers
```

**Risk:** May break peer task scheduling.

### 3. Check Async vs Sync Callback Execution

Compare how callbacks execute in both modes:

**Sync mode (line 594):**
```python
for service, command in self.processes.received():
    self.api.process(self, service, command)  # Sync handler
    sleep = 0

self.asynchronous.run()  # Callbacks execute immediately after commands
```

**Async mode (lines 228-232):**
```python
for service, command in self.processes.received_async():
    self.api.process(self, service, command)  # Sync handler (NOT async!)

# ... peer loop runs here ...
self.asynchronous.run()  # Callbacks execute AFTER peer loop
```

**Note:** Line 229 calls `self.api.process` (sync), not `self.api.process_async`!

### 4. Force Callback Execution After Each Command

Modify async mode to match sync mode pattern:

```python
for service, command in self.processes.received_async():
    self.api.process(self, service, command)
    self.asynchronous.run()  # Execute callback immediately (like sync mode)
    break  # Only one command per iteration
```

**This may fix the issue** - callbacks execute before peer loop reads RIB.

### 5. Investigate `api.process` vs `api.process_async`

Line 229 uses `self.api.process` (sync) instead of `await self.api.process_async`.
Check if this affects callback scheduling.

### 6. Add RIB State Logging

Log RIB state before/after command execution:

```python
# In announce_route callback
log.debug(f'BEFORE inject_change: _new_nlri keys = {list(rib._new_nlri.keys())}')
reactor.configuration.inject_change(peers, change)
log.debug(f'AFTER inject_change: _new_nlri keys = {list(rib._new_nlri.keys())}')

# In clear_adj_rib callback
log.debug(f'BEFORE withdraw: _new_nlri keys = {list(rib._new_nlri.keys())}')
reactor.neighbor_rib_out_withdraw(peer_name)
log.debug(f'AFTER withdraw: _new_nlri keys = {list(rib._new_nlri.keys())}')
```

This will show when RIB actually gets modified.

---

## Expected Test Behavior

**Test T should:**
1. Send route 0.1 UPDATE
2. Send route 0.1 WITHDRAW
3. Send routes 0.2, 0.3 UPDATEs
4. Send routes 0.2, 0.3 UPDATEs again (flush #1)
5. Send route 0.4 UPDATE
6. Send routes 0.2, 0.3, 0.4 UPDATEs (flush #2)
7. Send routes 0.2, 0.3, 0.4 WITHDRAWs (clear)
8. Send route 0.5 UPDATE

**Total:** 13 messages (9 UPDATEs + 4 WITHDRAWs)

**Current async mode:** 6 messages (6 UPDATEs, 0 WITHDRAWs)

---

## References

- Test script: `qa/encoding/api-rib.run`
- Expected messages: `qa/encoding/api-rib.msg`
- Configuration: `etc/exabgp/api-rib.conf`
- Main loop: `src/exabgp/reactor/loop.py:198-291` (async), `499-639` (sync)
- RIB: `src/exabgp/rib/outgoing.py`
- Command handlers: `src/exabgp/reactor/api/command/`

---

**Investigation Date:** 2025-11-19
**Investigator:** Claude + Thomas
**Status:** Root cause identified (callback execution timing), fix pending
**Next Session:** Try Step 4 (execute callbacks immediately after each command)
