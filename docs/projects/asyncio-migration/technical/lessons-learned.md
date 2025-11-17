# Lessons Learned - AsyncIO Migration

**Critical mistakes and corrections during migration**

---

## ❌ MISTAKE #1: Removing `yield` without understanding its purpose

**Date:** 2025-11-17
**Session:** First conversion session
**Functions affected:** announce_route(), withdraw_route(), announce_vpls(), withdraw_vpls()

### What I Did Wrong

Initially converted generators to async by:
1. ✅ Changing `def callback():` to `async def callback():`
2. ❌ Removing ALL `yield` statements without replacement
3. ❌ Assumed yielded True/False values were being consumed by caller

**Bad conversion:**
```python
# Original generator
def callback():
    for change in changes:
        reactor.configuration.inject_change(peers, change)
        yield False  # ← REMOVED without replacement
    reactor.processes.answer_done(service)

# My incorrect async version
async def callback():
    for change in changes:
        reactor.configuration.inject_change(peers, change)
        # ← Nothing here! WRONG!
    reactor.processes.answer_done(service)
```

### Why This Was Wrong

**User correctly identified the issue:**
> "yield could be in a loop with blocking code and waiting for the event would cause other part of the async code to not run and miss time critical events"

**The problem:**
1. `inject_change()` contains nested loops over neighbors
2. With many routes × many neighbors = potentially thousands of operations
3. Without yielding control, the coroutine blocks the event loop
4. **Time-critical BGP events** (keepalives, FSM transitions, incoming messages) would be delayed
5. This could cause **BGP session failures** due to keepalive timeout

**Example scenario that would fail:**
```python
# Announce 100 routes to 50 peers
for change in changes:  # 100 iterations
    inject_change(peers, change)  # loops over 50 neighbors each time
    # = 5000 operations WITHOUT yielding control
    # BGP keepalive timeout is typically 90 seconds
    # If these operations take > 90 seconds, peer sessions DROP
```

### The Correct Fix

**Replace `yield False` with `await asyncio.sleep(0)`** in loops:

```python
async def callback():
    for change in changes:
        reactor.configuration.inject_change(peers, change)
        await asyncio.sleep(0)  # ← Yield control to event loop
    reactor.processes.answer_done(service)
```

**What `await asyncio.sleep(0)` does:**
- Pauses the coroutine
- Returns control to the event loop
- Allows other tasks to run (keepalives, FSM, incoming messages)
- Immediately resumes this coroutine on next event loop iteration

### Understanding `yield True` vs `yield False`

After investigation, I learned:

**`yield True`** - Used on error paths with `return` after:
```python
if not peers:
    reactor.processes.answer_error(service)
    yield True  # ← Signal completion (error)
    return      # ← Exit generator
```
**Conversion:** Just `return` (no await needed)

**`yield False`** - Used in loops to yield control:
```python
for change in changes:
    # ... do work ...
    yield False  # ← Yield control, will be resumed
```
**Conversion:** `await asyncio.sleep(0)`

**Key insight:** The yielded True/False values were **never consumed** by the ASYNC scheduler! They were just control flow markers. The scheduler calls `next(generator)` until `StopIteration`, ignoring yielded values.

---

## ✅ CORRECT CONVERSION PATTERN

### Pattern: Nested Generator API Handler

**Original (Generator):**
```python
@Command.register('announce route')
def announce_route(self, reactor, service, line, use_json):
    def callback():  # ← Nested generator
        try:
            # Parse and validate
            if error:
                reactor.processes.answer_error(service)
                yield True   # ← Error exit
                return

            # Process loop
            for change in changes:
                reactor.configuration.inject_change(peers, change)
                yield False  # ← Yield control in loop

            reactor.processes.answer_done(service)
        except Exception:
            reactor.processes.answer_error(service)
            yield True  # ← Error exit

    reactor.asynchronous.schedule(service, line, callback())
    return True
```

**Correct (Async/Await):**
```python
@Command.register('announce route')
def announce_route(self, reactor, service, line, use_json):
    async def callback():  # ← Async coroutine
        try:
            # Parse and validate
            if error:
                reactor.processes.answer_error(service)
                return  # ← Just return (no yield True needed)

            # Process loop
            for change in changes:
                reactor.configuration.inject_change(peers, change)
                await asyncio.sleep(0)  # ← CRITICAL: Yield control

            reactor.processes.answer_done(service)
        except Exception:
            reactor.processes.answer_error(service)
            return  # ← Just return (no yield True needed)

    reactor.asynchronous.schedule(service, line, callback())
    return True
```

### Key Conversion Rules

1. **`def callback():` → `async def callback():`**
   - Change generator to async coroutine

2. **`yield True` followed by `return` → just `return`**
   - These are error exits
   - No await needed

3. **`yield False` in loops → `await asyncio.sleep(0)`**
   - CRITICAL for event loop fairness
   - Prevents blocking time-critical events
   - Must be in same location as original yield

4. **Keep scheduling:** `reactor.asynchronous.schedule(service, line, callback())`
   - ASYNC class supports both generators and coroutines
   - No changes needed to scheduling

---

## 🎯 TESTING VERIFICATION

**All these tests passed after correction:**
- ✅ Linting: `ruff format src && ruff check src`
- ✅ Unit tests: `env exabgp_log_enable=false pytest ./tests/unit/` (1376 passed)
- ✅ Functional tests: Ready to run

**Why tests passed even with mistake:**
- Unit tests don't test actual async scheduling behavior
- Tests use mocked reactors
- Real-world scenario (many routes, many peers) not covered in unit tests

**Lesson:** Tests passing ≠ correct async behavior. Must understand semantics.

---

## 📋 PRE-CONVERSION CHECKLIST

Before converting any generator to async:

- [ ] **Understand what the `yield` statements do**
  - Are they yielding control in loops? → `await asyncio.sleep(0)`
  - Are they error exits? → just `return`
  - Are they yielding data? → Keep as async generator or refactor

- [ ] **Check what the yielded values mean**
  - Are they used by caller? (rare)
  - Are they just control flow markers? (common)

- [ ] **Identify blocking operations in loops**
  - Nested loops
  - Heavy computation
  - I/O operations
  - Any code that could take significant time

- [ ] **Preserve exact yield locations**
  - Don't consolidate yields unless semantically equivalent
  - Don't skip yields in loops

- [ ] **Add required imports**
  - `import asyncio` if using `await asyncio.sleep(0)`

- [ ] **Test with realistic scenarios**
  - Many items in loops
  - Multiple concurrent operations
  - Time-critical events running simultaneously

---

## 🚨 RED FLAGS

Watch for these patterns that need special care:

❌ **Loop without yield → Likely needs `await asyncio.sleep(0)`**
```python
for item in many_items:
    heavy_operation(item)
    # ← Missing yield/await = BLOCKING!
```

❌ **Nested loops → Definitely needs yielding**
```python
for change in changes:
    for neighbor in neighbors:  # ← Nested!
        # Work here
    # ← MUST yield control after each change
```

❌ **Time-critical code → Cannot block**
```python
# BGP keepalives, FSM transitions, message processing
# These MUST run regularly or sessions fail
```

---

## 💡 KEY INSIGHTS

1. **`yield` in generators serves multiple purposes:**
   - Yielding values (data flow)
   - Yielding control (cooperative multitasking) ← Most common in ExaBGP
   - Signaling completion (control flow)

2. **In ExaBGP's custom async framework:**
   - Yielded values are typically ignored
   - `yield` is primarily for cooperative multitasking
   - `yield False` = "pause me, resume later"
   - `yield True` + `return` = "I'm done (error)"

3. **`await asyncio.sleep(0)` is NOT a no-op:**
   - Extremely important for event loop fairness
   - Prevents blocking time-critical operations
   - Allows other coroutines/generators to run
   - Critical for BGP protocol correctness

4. **User review is invaluable:**
   - Tests don't catch all semantic errors
   - Domain knowledge (BGP timing requirements) is critical
   - Always question "why was this yield here?"

---

## 📝 ACTION ITEMS FOR FUTURE CONVERSIONS

1. **Before converting:** Map all `yield` locations and understand purpose
2. **During converting:** Add `await asyncio.sleep(0)` for each `yield False` in loops
3. **After converting:** Verify yield points match original semantics
4. **Before committing:** Ask "could this block time-critical events?"

---

**Last Updated:** 2025-11-17
**Functions Corrected:** 4 (announce_route, withdraw_route, announce_vpls, withdraw_vpls)
**Critical Fix:** Added `await asyncio.sleep(0)` in all route processing loops
