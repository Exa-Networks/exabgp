# Async Loop Order Fix - Session 2025-11-19

**Status:** Successfully maintained 70/72 (97.2%) test pass rate
**Issue:** Async mode had degraded from 70/72 to 68/72 due to loop ordering issues
**Resolution:** Fixed loop ordering and coroutine batching to match sync mode behavior

---

## Problem Identified

User reported async code breakage with symptoms:
- Tests 7, D, T, U failing (68/72 passing, 94.4%)
- Previously documented state was 70/72 (97.2%)
- Tests 7 and D had regressed

## Root Causes

### 1. Incorrect Main Loop Ordering

**Sync mode order (correct):**
```python
# 1. Run all peers
for key in peers:
    peer.run()

# 2. Process API commands
for service, command in self.processes.received():
    self.api.process(self, service, command)

# 3. Run callbacks once
self.asynchronous.run()
```

**Async mode had:**
```python
# 1. Process API commands (WRONG ORDER!)
for service, command in self.processes.received_async():
    self.api.process(self, service, command)

# 2. Run callbacks
await self.asynchronous._run_async()

# 3. Run peers
await self._run_async_peers()
```

**Issue:** Callbacks were executing BEFORE peers ran, breaking the timing assumptions.

### 2. Coroutine Batching Issue

The `_run_async()` method in `asynchronous.py` was only processing ONE coroutine at a time:

```python
# Old code
uid, callback = self._async.popleft()
for _ in range(LIMIT):
    if inspect.iscoroutine(callback):
        await callback  # Execute coroutine
    # ... but then put it back on queue!
self._async.appendleft((uid, callback))
```

**Issue:** After executing a coroutine, it put it BACK on the queue instead of moving to the next one. This meant only one API command callback executed per reactor loop iteration.

---

## Fixes Applied

### Fix 1: Add Rate Limiting to Async Peer Loop

**File:** `src/exabgp/reactor/loop.py` (lines 176-178)

```python
# Limit the number of message handling per second (matches sync mode)
if self._rate_limited(key, peer.neighbor['rate-limit']):
    continue
```

**Key change:** Async peer loop now checks rate limits before starting peer tasks, matching sync mode line 565.

### Fix 2: Match Sync Loop Order

**File:** `src/exabgp/reactor/loop.py` (lines 256-270)

```python
# Run all peers concurrently (matches sync mode line 563-597)
await self._run_async_peers()

# Process API commands (matches sync mode line 600-602)
# Read at least one message per process if there is some and parse it
for service, command in self.processes.received_async():
    self.api.process(self, service, command)

# Run async scheduled tasks (matches sync mode line 604)
# Must use _run_async() instead of run() since event loop is already running
if self.asynchronous._async:
    await self.asynchronous._run_async()

# Flush API process write queue (send ACKs and responses)
await self.processes.flush_write_queue_async()
```

**Key change:** Peers run FIRST, then API commands, then callbacks - matching sync mode.

### Fix 3: Process ALL Coroutines Atomically

**File:** `src/exabgp/reactor/asynchronous.py` (lines 87-153)

```python
async def _run_async(self) -> bool:
    """Execute scheduled callbacks (supports both generators and coroutines)

    For generators: processes up to LIMIT iterations, then re-queues if not exhausted
    For coroutines: executes ALL pending coroutines until queue is empty
    """
    if not self._async:
        return False

    # Check if we have coroutines or generators
    first_uid, first_callback = self._async[0]

    if inspect.iscoroutine(first_callback) or inspect.iscoroutinefunction(first_callback):
        # Process ALL coroutines in the queue atomically
        # This ensures commands sent together (like "announce\nclear\n") are
        # executed atomically before peers read the RIB
        while self._async:
            uid, callback = self._async.popleft()
            try:
                if inspect.iscoroutine(callback):
                    await callback
                elif inspect.iscoroutinefunction(callback):
                    await callback()
                else:
                    # Mixed queue - put it back and switch to generator processing
                    self._async.appendleft((uid, callback))
                    break
            except Exception as exc:
                log.error(...)
                # Continue to next callback even if one fails
        return False  # All coroutines processed
    else:
        # Original generator processing logic (unchanged)
        # ... generator handling code ...
```

**Key changes:**
1. Detects coroutines vs generators
2. For coroutines: processes ALL pending coroutines in one call
3. For generators: maintains original behavior (process up to LIMIT iterations)
4. Ensures atomic execution of command batches

---

## Results

### Test Results

**Before fixes:**
- Async mode: 68/72 (94.4%)
- Tests failing: 7, D, T, U

**After fixes:**
- Async mode: 70/72 (97.2%) ✅
- Tests failing: T, U only
- Tests fixed: 7 (api-attributes-path), D (api-fast)

**Sync mode:**
- Still 72/72 (100%) - no regressions ✅

### Improvement

- Fixed 2 tests (7 and D)
- Maintained existing pass rate of 70/72
- Restored to documented baseline from previous session

---

## Why These Fixes Work

### Loop Ordering

By matching sync mode's loop order (peers → commands → callbacks), we ensure:

1. **Peers run first**: They read RIB state and send pending updates
2. **Commands queued**: API commands from external processes are read
3. **Callbacks execute**: Commands modify RIB state
4. **Next iteration**: Peers see updated RIB state

This creates the correct timing relationship between peer updates and API commands.

### Coroutine Batching

Processing ALL coroutines atomically ensures:

1. **Command batches execute together**: "announce\nflush\n" executes as one atomic operation
2. **No interleaving**: Peers don't run between individual command callbacks
3. **Flush barrier semantics**: Commands sent in one flush() call execute together

This matches the sync mode behavior where `asynchronous.run()` processes all pending work before returning.

---

## Remaining Issues (Tests T & U)

Tests T (api-rib) and U (api-rr-rib) still fail with the same issue documented in TEST_T_INVESTIGATION_2025-11-19.md:

**Problem:** Routes queued out of order, clear commands don't work as expected

**Root cause:** RIB state management issue where:
- `clear adj-rib out` only clears routes in `_seen` (already sent to peer)
- Doesn't clear routes in `_new_nlri` (pending transmission)
- In async mode, all callbacks execute before peers run
- So "announce + clear" sequence leaves route in `_new_nlri`

**Status:** Deferred - affects only 2.8% of tests, workaround available (use sync mode)

---

## Files Modified

1. **src/exabgp/reactor/loop.py**
   - Reordered async main loop to match sync mode
   - Lines 256-270: peers → API commands → callbacks

2. **src/exabgp/reactor/asynchronous.py**
   - Fixed coroutine batching logic
   - Lines 87-153: Process ALL coroutines atomically

---

## Testing Performed

```bash
# Async mode
env exabgp_reactor_asyncio=true exabgp_log_enable=false ./qa/bin/functional encoding
# Result: 70/72 (97.2%)

# Sync mode
env exabgp_log_enable=false ./qa/bin/functional encoding
# Result: 72/72 (100%)

# Unit tests (both modes)
env exabgp_log_enable=false pytest ./tests/unit/
# Result: 1376/1376 (100%)
```

---

## Key Insight

**User's hint was critical:** "You fixed it in a previous session... it was about how you ensured we matched our old loop closely"

The key realization: **Async mode must mirror sync mode's loop structure exactly**, not just the functionality. The order of operations matters:

- ✅ Sync: peers → commands → callbacks
- ❌ Previous async: commands → callbacks → peers
- ✅ Fixed async: peers → commands → callbacks

---

## Conclusion

Successfully restored async mode to 70/72 (97.2%) test pass rate by:
1. Matching sync loop ordering exactly
2. Processing all coroutines atomically (flush barrier semantics)

Both fixes maintain 100% backward compatibility with sync mode.

Tests T and U remain documented known issues (2.8% of test suite), acceptable for Phase 2 production validation.

---

**Session Date:** 2025-11-19
**Duration:** ~2 hours
**Status:** ✅ Complete - async mode stable at 97.2%
