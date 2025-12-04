# Async Mode Deadlock Fix - Refactoring Plan

**Date:** 2025-11-18
**Status:** PARTIAL SUCCESS - 50% improvement achieved
**Goal:** Fix async mode deadlock by restoring proper API/packet interleaving

## Progress Summary
- ✅ Steps 1-2 completed successfully
- ✅ Unit tests: 1376/1376 passing (100%)
- ✅ Encoding tests (async): 36/72 passing (50% - was 0%)
  - All 36 conf-* tests now pass
  - All 36 api-* tests still timeout
- 🔄 Partial success - significant progress but work remains

---

## Problem Statement

The async implementation blocks on `await self._run_async_peers()` at line 257 of `loop.py`, preventing API command processing at line 260. This causes all 36 API tests to deadlock.

**Root cause:** Sequential processing (peers then API) instead of concurrent processing.

**Solution:** Process API commands every iteration while peer tasks run independently in background.

---

## Refactoring Steps

### STEP 1: Refactor `_async_main_loop()` to remove blocking await on peers
**Files:** `src/exabgp/reactor/loop.py`

**Changes:**
1. Remove `await self._run_async_peers()` call (line 257)
2. Add inline peer task management (non-blocking):
   - Start tasks for new peers
   - Check for completed peer tasks
   - Remove completed peers
3. Move API command processing to run EVERY iteration
4. Keep only `await asyncio.sleep(0)` for yielding to peer tasks

**Before (lines 256-268):**
```python
# Run all peers concurrently
await self._run_async_peers()  # BLOCKS HERE

# Process API commands (using async version with event loop integration)
for service, command in self.processes.received_async():
    self.api.process(self, service, command)

# Run async scheduled tasks
self.asynchronous.run()

# Yield control to peer tasks (minimal sleep)
await asyncio.sleep(0)
```

**After:**
```python
# Start async tasks for new peers (non-blocking)
for key in self.active_peers():
    peer = self._peers[key]
    if not hasattr(peer, '_async_task') or peer._async_task is None:
        peer.start_async_task()

# Process API commands (CRITICAL - runs EVERY iteration, non-blocking)
for service, command in self.processes.received_async():
    self.api.process(self, service, command)

# Run async scheduled tasks
self.asynchronous.run()

# Check for completed/failed peer tasks
completed_peers = []
for key in list(self._peers.keys()):
    peer = self._peers[key]
    if hasattr(peer, '_async_task') and peer._async_task is not None:
        if peer._async_task.done():
            try:
                peer._async_task.result()
            except Exception as exc:
                log.error(lambda exc=exc: f'peer {key} task failed: {exc}', 'reactor')
            completed_peers.append(key)

# Remove completed peers
for key in completed_peers:
    if key in self._peers:
        del self._peers[key]

# Yield control to peer tasks (let them run)
await asyncio.sleep(0)
```

**Verification:**
```bash
env exabgp_log_enable=false pytest ./tests/unit/ -q
```
**Expected:** 1376 passed

---

### STEP 2: Remove `_run_async_peers()` method (now unused)
**Files:** `src/exabgp/reactor/loop.py`

**Changes:**
- Delete `_run_async_peers()` method (lines 162-196)

**Verification:**
```bash
env exabgp_log_enable=false pytest ./tests/unit/ -q
```
**Expected:** 1376 passed

---

### STEP 3: Test with async mode functional encoding tests
**Files:** None (verification step)

**Verification:**
```bash
exabgp_reactor_asyncio=true ./qa/bin/functional encoding
```
**Expected:** 72/72 tests passed (100%)

---

### STEP 4: Test with async mode functional decoding tests
**Files:** None (verification step)

**Verification:**
```bash
exabgp_reactor_asyncio=true ./qa/bin/functional decoding
```
**Expected:** 18/18 tests passed (100%)

---

### STEP 5: Run full linting check
**Files:** None (verification step)

**Verification:**
```bash
uv run ruff format src && uv run ruff check src
```
**Expected:** All checks passed

---

### STEP 6: Run complete test suite (both modes)
**Files:** None (verification step)

**Verification:**
```bash
# Generator mode
env exabgp_log_enable=false pytest ./tests/unit/ -q
./qa/bin/functional encoding
./qa/bin/functional decoding

# Async mode
exabgp_reactor_asyncio=true env exabgp_log_enable=false pytest ./tests/unit/ -q
exabgp_reactor_asyncio=true ./qa/bin/functional encoding
exabgp_reactor_asyncio=true ./qa/bin/functional decoding
```

**Expected:**
- Unit tests: 1376 passed (both modes)
- Encoding: 72/72 passed (both modes)
- Decoding: 18/18 passed (both modes)

---

## Technical Analysis

### Why This Fixes The Deadlock

**Generator mode (working):**
- Uses `select.poll()` to monitor all FDs (peers + API)
- Processes whichever becomes ready first
- True interleaving at kernel level

**Async mode (broken):**
- Sequential: `await peers()` then `process_api()`
- Peer tasks block in `await read_message_async()`
- API processing never reached

**Async mode (fixed):**
- API processing runs EVERY iteration (dequeues commands)
- Peer tasks run independently in background
- Event loop callbacks feed command queue
- Main loop dequeues and processes commands
- No blocking waits in main loop

### Flow Comparison

**Before (Sequential):**
```
Main Loop:
  await _run_async_peers()  ← BLOCKS waiting for peers
    ↳ Peer tasks blocked in read_message_async()
  for cmd in received_async():  ← NEVER REACHED
    process(cmd)
```

**After (Concurrent):**
```
Main Loop:
  Start peer tasks (if not running)
  for cmd in received_async():  ← RUNS EVERY ITERATION
    process(cmd)  ← Processes queued commands
  Check completed peers
  await sleep(0)  ← Let peer tasks run

Background:
  Peer Task 1: await read_message_async()
  Peer Task 2: await read_message_async()
  API Callback: Queue commands when data arrives
```

---

## Expected Outcomes

### Before Fix
- ❌ 36/108 functional tests fail (all API tests)
- ❌ Tests timeout after 20 seconds
- ❌ Deadlock at `Peer._main_async()` line 816

### After Fix
- ✅ 108/108 functional tests pass (100%)
- ✅ Async mode achieves parity with generator mode
- ✅ Proper interleaving of API and BGP processing
- ✅ No deadlocks or timeouts

---

## Risk Assessment

**Low Risk:**
- Changes isolated to async mode code path
- Generator mode completely unaffected
- Unit tests cover both modes
- Functional tests verify end-to-end behavior

**Rollback Plan:**
If tests fail, revert changes immediately using git.

---

## Next Steps After This Fix

Once the refactoring is complete and all tests pass:

1. **Update Phase 2 documentation** - Mark deadlock fix complete
2. **Continue Phase 2 validation** - Production testing
3. **Performance comparison** - Async vs generator benchmarks
4. **Documentation updates** - Update async mode usage guide

---

**Approval Status:** ✅ APPROVED
**Ready to Execute:** YES
**Protocol Followed:** MANDATORY_REFACTORING_PROTOCOL.md

---

**Last Updated:** 2025-11-18
