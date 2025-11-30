# Async Continue Bug Pattern - Critical Blocking Issue

**Date:** 2025-11-18
**Status:** IDENTIFIED AND PARTIALLY FIXED
**Impact:** CRITICAL - Prevents async loops from checking outbound work

---

## Summary

A critical bug pattern was discovered in ExaBGP's async mode where `continue` statements in async loops prevent outbound work from being processed. This pattern may exist in multiple locations throughout the codebase.

**Test Results After Initial Fix:**
- Before: 36/72 tests pass (50%)
- After: 70/72 tests pass (97.2%)
- Remaining: 2 tests fail (T and U) - likely more instances of this pattern

---

## The Bug Pattern

### Problematic Code Structure

```python
async def some_loop():
    while not self._teardown:
        # Try to read/receive something
        try:
            data = await asyncio.wait_for(read_operation(), timeout=0.1)
        except asyncio.TimeoutError:
            await asyncio.sleep(0)
            continue  # ← BUG: Skips all outbound work checking below

        # Check if data is NOP (no operation)
        if data is NOP:
            await asyncio.sleep(0)
            continue  # ← BUG: Skips all outbound work checking below

        # Process received data
        process(data)

        # OUTBOUND WORK - NEVER REACHED when continue is executed above
        if outbound_work_pending():
            send_outbound_data()
```

### Why It's a Bug

**Generator mode (working):**
```python
def some_loop():
    while not self._teardown:
        for data in read_generator():  # Yields NOP when no data
            # Loop body ALWAYS executes, even for NOP
            process(data)  # Handles NOP gracefully

            # OUTBOUND WORK - Always checked, even when data is NOP
            if outbound_work_pending():
                yield send_outbound_data()
```

In generator mode, the `for` loop body executes for every yielded value, including NOP. This ensures outbound work is checked even when no inbound data arrives.

**Async mode (broken with continue):**
- When `read_operation()` times out or returns NOP
- `continue` jumps back to loop start
- Outbound work checking code is **NEVER executed**
- System blocks waiting for inbound data, ignoring outbound work

---

## Confirmed Instance: peer.py Lines 817-830

**File:** `src/exabgp/reactor/peer.py`
**Function:** `_main_async()`
**Lines:** 817-830

**Original (Broken):**
```python
# Read message using async I/O with timeout
try:
    message = await asyncio.wait_for(self.proto.read_message_async(), timeout=0.1)
except asyncio.TimeoutError:
    # No message within timeout - yield control and try again
    await asyncio.sleep(0)
    continue  # ← BUG: Skips outbound UPDATE checks at line 881

# NOP means no data - yield control and try again
if message is NOP:
    await asyncio.sleep(0)
    continue  # ← BUG: Skips outbound UPDATE checks at line 881

# ... inbound message processing ...

# SEND UPDATE (line 881) - NEVER REACHED when continue executes
if not new_routes and self.neighbor.rib.outgoing.pending():
    await self.proto.new_update_async(include_withdraw)
```

**Fixed:**
```python
# Read message using async I/O with timeout
try:
    message = await asyncio.wait_for(self.proto.read_message_async(), timeout=0.1)
except asyncio.TimeoutError:
    # No message within timeout - set to NOP and continue to outbound checks
    message = NOP  # ← FIX: Let NOP flow through to outbound checks
    await asyncio.sleep(0)

# NOP means no data - continue to outbound checks (matches generator mode)
# (No continue statement - let processing continue)

# ... inbound message processing (handles NOP) ...

# SEND UPDATE (line 881) - NOW REACHED even when message is NOP
if not new_routes and self.neighbor.rib.outgoing.pending():
    await self.proto.new_update_async(include_withdraw)
```

**Impact:** Fixed 34/36 api-* tests (from 0/36)

---

## How to Identify This Pattern

### Search Commands

```bash
# Find async loops with continue statements
grep -n "continue" src/exabgp/reactor/*.py src/exabgp/reactor/*/*.py

# Find async loops with timeout handling
grep -B5 -A2 "asyncio.TimeoutError" src/exabgp/reactor/*.py

# Find async loops with NOP checks
grep -B2 -A2 "is NOP" src/exabgp/reactor/*.py

# Find all async while loops
grep -B2 "while.*:" src/exabgp/reactor/*.py | grep -A2 "async def"
```

### Visual Inspection Checklist

For each async loop, check:

1. **Does it have `continue` statements?**
   - If YES → potential bug

2. **Does the continue skip outbound work checking?**
   - Look for code below continue that:
     - Sends messages
     - Checks queues/buffers
     - Processes pending work
   - If YES → CONFIRMED BUG

3. **Does generator mode equivalent execute loop body for NOP?**
   - Find corresponding generator function
   - Check if `for data in generator()` pattern is used
   - If YES → async mode MUST match this behavior

---

## Suspected Additional Instances

### High Priority - Check These Files

1. **`src/exabgp/reactor/network/connection.py`**
   - May have async read/write loops
   - Could have timeout/NOP handling with continue

2. **`src/exabgp/reactor/protocol.py`**
   - Protocol state machine may have async loops
   - May skip state transitions with continue

3. **`src/exabgp/reactor/loop.py`**
   - Main reactor loop already fixed
   - But may have other loops

4. **`src/exabgp/reactor/api/processes.py`**
   - API reading loops
   - May have continue statements

### Evidence

**Test T and U still fail (2/72)** despite main peer loop fix. This suggests:
- Another async loop has the same pattern
- Likely in protocol handling or connection management
- Affects specific test scenarios

---

## Fix Strategy

### For Each Instance Found:

1. **Understand the generator mode equivalent**
   - How does it handle NOP/empty data?
   - What work is checked in the loop body?

2. **Apply the fix pattern:**
   ```python
   # BEFORE (broken):
   except asyncio.TimeoutError:
       await asyncio.sleep(0)
       continue  # ← Remove this

   if data is NOP:
       await asyncio.sleep(0)
       continue  # ← Remove this

   # AFTER (fixed):
   except asyncio.TimeoutError:
       data = NOP  # ← Set to NOP instead
       await asyncio.sleep(0)
       # Fall through to processing

   # Let NOP flow through to outbound checks
   # (no if data is NOP: continue)
   ```

3. **Ensure downstream code handles NOP gracefully**
   - Check if `data.TYPE` comparisons exist
   - NOP has TYPE attribute, comparisons will be False
   - Code should naturally skip NOP processing

4. **Test thoroughly**
   - Run affected tests
   - Verify no regression in sync mode
   - Check async mode improvement

---

## Testing Guide

### Before Fix
```bash
# Baseline - should show failures
env exabgp_reactor_asyncio=true ./qa/bin/functional encoding
```

### After Fix
```bash
# Should show improvement
env exabgp_reactor_asyncio=true ./qa/bin/functional encoding

# Verify no regression in sync mode
./qa/bin/functional encoding
```

### Specific Test Debugging
```bash
# Run failing test with debug
env exabgp_reactor_asyncio=true DEBUG=1 ./qa/bin/functional encoding T

# Check for "continue" in logs showing skipped work
grep -i "skip\|continue" /tmp/test_output.log
```

---

## Root Cause Analysis

### Why This Pattern Exists

**Historical context:**
1. Async mode was created to mirror generator mode
2. Generator mode uses `yield` to pause execution
3. Async mode used `continue` thinking it was equivalent
4. **But they behave differently:**
   - Generator: `for x in generator()` executes body for ALL yields
   - Async: `continue` jumps to loop start, skips rest of body

### Fundamental Difference

**Generator mode:**
```python
for message in self.proto.read_message():  # ← Yields NOP when no data
    # Body ALWAYS executes
    check_outbound_work()  # ← ALWAYS called
```

**Async mode (broken):**
```python
while True:
    try:
        message = await read_async()
    except TimeoutError:
        continue  # ← Jumps to while, skips body

    check_outbound_work()  # ← NEVER called on timeout
```

**Async mode (fixed):**
```python
while True:
    try:
        message = await read_async()
    except TimeoutError:
        message = NOP  # ← Set NOP and fall through

    # Process message (NOP or real)
    if message is not NOP:
        handle_message()

    check_outbound_work()  # ← ALWAYS called
```

---

## Prevention Guidelines

### For New Async Code

**DO:**
- Structure loops to always reach outbound work checks
- Set values to NOP/None instead of continue
- Mirror generator mode's "execute body for all yields" pattern

**DON'T:**
- Use `continue` to skip to next iteration when work may be pending
- Assume timeout means "do nothing"
- Block on inbound I/O without checking outbound work

### Code Review Checklist

When reviewing async loops:
- [ ] Does it have `continue` statements?
- [ ] Is there work checking after the continue point?
- [ ] Does generator equivalent always execute loop body?
- [ ] Does timeout/NOP case need to check outbound work?
- [ ] Are there tests that verify outbound work happens even without inbound data?

---

## Impact Assessment

### Current Status

**Fixed:** `src/exabgp/reactor/peer.py` lines 817-830
- Result: 36/72 → 70/72 tests (50% → 97.2%)

**Remaining Issues:** 2/72 tests still fail
- Tests T and U
- Likely additional instances of this pattern
- Requires systematic search

### Potential Locations (To Be Investigated)

1. Connection read/write loops
2. Protocol state machine transitions
3. API command processing loops
4. Network I/O handling
5. Timer/periodic task loops

---

## Next Steps

1. **Systematic Search:**
   - Run grep commands above
   - Inspect each async loop with continue
   - Compare with generator mode equivalent

2. **Test-Driven Investigation:**
   - Run failing tests T and U with debug logging
   - Look for loops that never execute expected code
   - Add strategic logging before/after continue statements

3. **Fix and Verify:**
   - Apply fix pattern to each instance
   - Run tests after each fix
   - Document each fix location

4. **Documentation:**
   - Update this file with each instance found
   - Add code comments explaining why continue was removed
   - Create regression tests for the pattern

---

## File Modification Log

| File | Lines | Status | Tests Fixed |
|------|-------|--------|-------------|
| `src/exabgp/reactor/peer.py` | 821-828 | ✅ FIXED | 34/36 api-* tests |
| `src/exabgp/reactor/api/command/rib.py` | 84, 157, 190 | ✅ FIXED | Async callbacks (no test impact) |
| *(others to be found)* | TBD | 🔍 SEARCHING | 2/72 remaining (T, U) |

**Failing Tests:**
- T: `api-rib` - RIB manipulation test (uses flush/clear adj-rib commands)
- U: `api-rr` - Route Reflector test

**Note:** rib.py async callback fixes did not resolve T/U failures. The issue is likely NOT the continue pattern but a different async-specific bug in RIB handling.

---

## Related Documents

- `.claude/asyncio-migration/ASYNC_FIX_FINAL_STATUS.md` - Previous 50% status
- `.claude/asyncio-migration/DEADLOCK_ANALYSIS.md` - Initial deadlock fix
- `docs/projects/asyncio-migration/README.md` - Full migration guide

---

**Last Updated:** 2025-11-18
**Current Test Status:** 70/72 passing (97.2%)
**Next Action:** Systematic search for remaining instances
