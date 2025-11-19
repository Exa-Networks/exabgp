# Async Mode Deadlock Fix - Progress Report

**Date:** 2025-11-18
**Status:** PARTIAL SUCCESS - 50% improvement achieved

---

## Refactoring Completed

### Changes Made

**Step 1: Refactored `_async_main_loop()` (loop.py:162-260)**
- ✅ Removed blocking `await self._run_async_peers()`
- ✅ Added inline peer task management (non-blocking)
- ✅ Moved API command processing to run EVERY iteration
- ✅ Peer tasks now run independently in background
- ✅ Unit tests pass (1376/1376)

**Step 2: Removed unused code**
- ✅ Deleted `_run_async_peers()` method (lines 162-196)
- ✅ Unit tests still pass (1376/1376)

---

## Test Results

### Before Fix
- **Encoding tests (async mode):** 0/72 passed (0%)
  - All tests deadlocked
  - Root cause: `await self._run_async_peers()` blocked API processing

### After Fix
- **Encoding tests (async mode):** 36/72 passed (50%)
  - ✅ Tests 'a'-'κ' (36 conf tests): **ALL PASS**
  - ❌ Tests '0'-'Z' (36 api tests): **ALL TIMEOUT**

**Progress:** 0% → 50% pass rate

---

## Analysis: Partial Success

### What Works Now
**Configuration tests (conf-*):**
- Don't require runtime API bidirectional communication
- Test configuration parsing and BGP message generation
- Peers establish sessions and exchange messages
- ✅ **All 36 pass**

### What Still Fails
**API tests (api-*):**
- Require runtime API command/response cycles
- Test sends command → ExaBGP processes → Test expects response
- ❌ **All 36 timeout after 20 seconds**

---

## Remaining Issue: Peer Task Blocking

### The Problem

Even with API commands processed every iteration, API tests still timeout. Analysis:

**Current flow:**
```python
async def _async_main_loop():
    while True:
        # Start peer tasks (background)
        for peer in active_peers():
            peer.start_async_task()

        # Process API commands (NON-BLOCKING dequeue)
        for service, command in self.processes.received_async():
            self.api.process(self, service, command)  # ← Runs every iteration

        # Yield
        await asyncio.sleep(0.001)  # ← Returns to main loop
```

**Peer task:**
```python
async def _main_async():
    while not self._teardown:
        message = await self.proto.read_message_async()  # ← BLOCKS HERE
        # ... process message ...
        await asyncio.sleep(0)  # Only reached after message
```

**Problem:** Peer tasks block at `read_message_async()` waiting for BGP data.

**Why conf tests work:**
- BGP peers send messages (OPEN, KEEPALIVE, UPDATE)
- `read_message_async()` receives them
- Loop continues, test completes

**Why API tests fail:**
- BGP session establishes (OPEN exchange works)
- But then peer blocks waiting for next BGP message
- Meanwhile, test sends API command via API process
- API callback fires, queues command
- Main loop dequeues and processes command (THIS WORKS!)
- Command processing likely succeeds
- **But response might not be sent back to test?**

### Theory: Response Path Broken

The issue might not be command reading (that works now), but response writing.

When ExaBGP processes an API command:
1. Main loop dequeues command
2. `self.api.process(self, service, command)` called
3. This should write response to API process stdin
4. API process forwards to test

**Hypothesis:** The response write might be blocking or failing in async mode?

---

## Next Steps

### Option 1: Debug Response Path
1. Add logging to see if API commands are actually being processed
2. Check if responses are being written
3. Verify API process is receiving responses

### Option 2: Fix Peer Task Design
The fundamental issue is that peer tasks run forever and block. Two approaches:

**A. Keep peer tasks, fix blocking:**
- Make `read_message_async()` timeout and yield periodically
- Even if no BGP message, return NOP and let loop continue
- This matches generator mode behavior (ACTION.LATER)

**B. Don't use peer tasks:**
- Call `peer.run_async()` directly from main loop (like generator mode)
- Use `asyncio.wait_for()` with timeout to prevent blocking
- More similar to generator mode architecture

### Option 3: Hybrid Approach
- Keep background peer tasks for BGP protocol
- But add explicit yield points every N ms
- Ensure main loop runs at high frequency

---

## Code Quality

All changes follow protocol:
- ✅ Every step verified with unit tests
- ✅ All unit tests pass (1376/1376)
- ✅ No regressions in generator mode
- ✅ Incremental improvement (0% → 50%)
- ✅ Changes well-documented

---

## Decision Needed

**Before continuing, need to:**
1. Understand WHY API tests timeout
   - Is it command reading? (likely fixed)
   - Is it command processing? (need to verify)
   - Is it response writing? (possible issue)

2. Choose fix strategy
   - Debug current approach
   - OR redesign peer task model

**Recommendation:** Add debug logging to understand where API tests hang.

---

**Last Updated:** 2025-11-18
**Next Session:** Debug API command/response flow in async mode
