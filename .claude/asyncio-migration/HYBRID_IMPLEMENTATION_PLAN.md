# Hybrid Event Loop Implementation Plan

**Status:** DRAFT - Awaiting Final Approval
**Approach:** Hybrid (Generators for state machines + Async for I/O)
**Protocol:** MANDATORY_REFACTORING_PROTOCOL
**Created:** 2025-11-17

---

## CRITICAL RULES (MANDATORY_REFACTORING_PROTOCOL)

1. **ONE function at a time** - No batching
2. **ALL tests MUST ALWAYS PASS** - No exceptions
3. **PASTE proof at every step** - No summaries
4. **STOP if ANY failures** - Debug before proceeding

---

## Overview

**Scope:** Convert I/O layer to async while keeping generator state machines

**Files to modify:**
1. `src/exabgp/reactor/network/connection.py` (3 async functions)
2. `src/exabgp/reactor/loop.py` (1 async wrapper)
3. Helper utilities (minimal)

**Total Steps:** 12 numbered steps
**Estimated Time:** 10-15 hours
**Risk Level:** MEDIUM

---

## Pre-Execution Checklist

Before starting Step 1:

- [x] PoC B proven working
- [x] User approval obtained
- [x] Understanding of MANDATORY_REFACTORING_PROTOCOL
- [ ] Clean git status (no uncommitted changes)
- [ ] Baseline tests passing
- [ ] File descriptor limit checked (`ulimit -n`)

**Run baseline tests NOW before making ANY changes:**

```bash
# 1. Check file descriptor limit
ulimit -n
# Expected: ≥64000 (increase if needed: ulimit -n 64000)

# 2. Linting baseline
ruff format src && ruff check src
# Expected: "All checks passed!"

# 3. Unit tests baseline
env exabgp_log_enable=false pytest ./tests/unit/ -q
# Expected: "1376 passed"

# 4. Configuration validation baseline
./sbin/exabgp validate -nrv ./etc/exabgp/conf-ipself6.conf
# Expected: Success (exit 0)
```

**PASTE OUTPUT of all 4 baseline tests before proceeding to Step 1.**

---

## PHASE 1: I/O Layer Conversion (Steps 1-7)

### Step 1: Add async imports to connection.py

**File:** `src/exabgp/reactor/network/connection.py`

**Changes:**
- Add `import asyncio` at top of file
- Add type hints: `from typing import AsyncIterator`

**Verification:**
```bash
ruff format src && ruff check src
```

**Expected:** "All checks passed!" (linting only, no logic changes)

---

### Step 2: Add async _reader() method

**File:** `src/exabgp/reactor/network/connection.py`

**Action:** Add new `_reader_async()` method ALONGSIDE existing `_reader()` method

**New method to add:**
```python
async def _reader_async(self, number: int) -> bytes:
    """Read exactly 'number' bytes from socket (async version)

    Uses asyncio for I/O operations.
    """
    loop = asyncio.get_event_loop()

    # Wait for socket to be readable
    while not self.reading():
        await asyncio.sleep(0.001)

    data = b''
    while number > 0:
        try:
            # Use asyncio socket operations
            read = await loop.sock_recv(self.io, number)
            if not read:
                raise LostConnection('Socket closed during read')

            data += read
            number -= len(read)
        except BlockingIOError:
            # Socket not ready, yield control
            await asyncio.sleep(0.001)
        except OSError as exc:
            if exc.args[0] not in error.block:
                raise
            await asyncio.sleep(0.001)

    return data
```

**IMPORTANT:** Keep existing `_reader()` method UNCHANGED

**Verification:**
```bash
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/ -q
```

**Expected:**
- Linting: "All checks passed!"
- Tests: "1376 passed"

---

### Step 3: Add async writer() method

**File:** `src/exabgp/reactor/network/connection.py`

**Action:** Add new `writer_async()` method ALONGSIDE existing `writer()` method

**New method to add:**
```python
async def writer_async(self, data: bytes) -> None:
    """Write data to socket (async version)

    Uses asyncio for I/O operations.
    """
    loop = asyncio.get_event_loop()

    # Wait for socket to be writable
    while not self.writing():
        await asyncio.sleep(0.001)

    # sock_sendall handles all data or raises
    try:
        await loop.sock_sendall(self.io, data)
    except BlockingIOError:
        # Retry with small delay
        await asyncio.sleep(0.001)
        await loop.sock_sendall(self.io, data)
    except OSError as exc:
        if exc.args[0] not in error.block:
            raise
        await asyncio.sleep(0.001)
```

**IMPORTANT:** Keep existing `writer()` method UNCHANGED

**Verification:**
```bash
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/ -q
```

**Expected:**
- Linting: "All checks passed!"
- Tests: "1376 passed"

---

### Step 4: Add async reader() method

**File:** `src/exabgp/reactor/network/connection.py`

**Action:** Add new `reader_async()` method ALONGSIDE existing `reader()` method

**New method to add:**
```python
async def reader_async(self) -> tuple[int, int, bytes, bytes, Optional[NotifyError]]:
    """Read BGP message header and body (async version)

    Returns: (length, msg_type, header, body, error)
    """
    # Read 19-byte BGP header
    header = await self._reader_async(19)

    # Parse header
    length = (header[16] << 8) + header[17]
    msg_type = header[18]

    # Validate length
    if length < 19 or length > 4096:
        error = NotifyError(1, 2, header[:2])  # Message Header Error
        return 0, 0, header, b'', error

    # Read body
    if length > 19:
        body = await self._reader_async(length - 19)
    else:
        body = b''

    return length, msg_type, header, body, None
```

**IMPORTANT:** Keep existing `reader()` method UNCHANGED

**Verification:**
```bash
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/ -q
```

**Expected:**
- Linting: "All checks passed!"
- Tests: "1376 passed"

---

### Step 5: Add bridge helper for generators

**File:** `src/exabgp/reactor/network/connection.py`

**Action:** Add helper method to bridge from generators to async I/O

**New method to add:**
```python
def _async_io_bridge(self, coro):
    """Bridge from generator context to async I/O

    Allows generators to call async I/O operations.
    Yields control while waiting for I/O to complete.

    Args:
        coro: Async coroutine to execute

    Yields:
        Intermediate states while waiting

    Returns:
        Final result from coroutine
    """
    loop = asyncio.get_event_loop()

    # Create task for async operation
    task = asyncio.create_task(coro)

    # Yield control while waiting
    while not task.done():
        yield None  # Waiting for I/O

    # Return result
    return task.result()
```

**IMPORTANT:** This is a NEW helper method, does not replace anything

**Verification:**
```bash
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/ -q
```

**Expected:**
- Linting: "All checks passed!"
- Tests: "1376 passed"

---

### Step 6: Verify I/O layer additions

**Action:** Review all changes to connection.py

**Check:**
- [ ] Three new async methods added (_reader_async, writer_async, reader_async)
- [ ] One bridge helper added (_async_io_bridge)
- [ ] All existing methods UNCHANGED
- [ ] Import asyncio added
- [ ] No breaking changes

**Verification:**
```bash
git diff src/exabgp/reactor/network/connection.py
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/ -q
```

**Expected:**
- Diff shows only ADDITIONS (no deletions of existing code)
- Linting: "All checks passed!"
- Tests: "1376 passed"

---

### Step 7: Document I/O layer changes

**Action:** Add docstring at top of connection.py explaining dual approach

**Add after existing module docstring:**
```python
"""
ASYNC I/O MIGRATION (2025-11-17):

This module supports both generator-based and async I/O:
- Original: _reader(), writer(), reader() - generator-based (KEPT)
- New: _reader_async(), writer_async(), reader_async() - async-based (ADDED)

The async methods use asyncio.sock_recv()/sock_sendall() for I/O.
Generators can call async I/O via _async_io_bridge() helper.

Both approaches coexist during migration. State machines remain generators.
"""
```

**Verification:**
```bash
ruff format src && ruff check src
```

**Expected:** "All checks passed!"

---

## PHASE 2: Event Loop Integration (Steps 8-10)

### Step 8: Add async support to loop.py

**File:** `src/exabgp/reactor/loop.py`

**Action:** Add import and prepare for async integration

**Changes:**
- Add `import asyncio` if not present
- No other changes yet

**Verification:**
```bash
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/ -q
```

**Expected:**
- Linting: "All checks passed!"
- Tests: "1376 passed"

---

### Step 9: Add async _wait_for_io() wrapper

**File:** `src/exabgp/reactor/loop.py`

**Action:** Add async version ALONGSIDE existing _wait_for_io()

**New method to add:**
```python
async def _wait_for_io_async(self, sleeptime: int):
    """Wait for I/O using asyncio (async version)

    Replaces select.poll() with asyncio I/O multiplexing.
    """
    # Convert milliseconds to seconds
    sleep_seconds = sleeptime / 1000.0

    try:
        # Use asyncio.sleep for I/O waiting
        await asyncio.sleep(sleep_seconds)

        # Return empty list if no events
        # (In full implementation, would integrate with asyncio I/O)
        return []

    except KeyboardInterrupt:
        self._termination('^C received', self.Exit.normal)
        return []
    except Exception:
        self._prevent_spin()
        return []
```

**NOTE:** This is a simplified version for Phase 1. Full integration comes later.

**IMPORTANT:** Keep existing `_wait_for_io()` UNCHANGED

**Verification:**
```bash
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/ -q
```

**Expected:**
- Linting: "All checks passed!"
- Tests: "1376 passed"

---

### Step 10: Verify event loop additions

**Action:** Review changes to loop.py

**Check:**
- [ ] asyncio imported
- [ ] _wait_for_io_async() added
- [ ] Existing _wait_for_io() UNCHANGED
- [ ] Existing run() UNCHANGED
- [ ] No breaking changes

**Verification:**
```bash
git diff src/exabgp/reactor/loop.py
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/ -q
```

**Expected:**
- Diff shows only ADDITIONS
- Linting: "All checks passed!"
- Tests: "1376 passed"

---

## PHASE 3: Testing & Validation (Steps 11-12)

### Step 11: Run full test suite

**Action:** Comprehensive testing of all changes

**Tests to run:**
```bash
# 1. Linting
ruff format src && ruff check src

# 2. Unit tests
env exabgp_log_enable=false pytest ./tests/unit/ -q

# 3. Configuration validation
./sbin/exabgp validate -nrv ./etc/exabgp/conf-ipself6.conf

# 4. Type checking (if available)
mypy src/exabgp/reactor/network/connection.py src/exabgp/reactor/loop.py --ignore-missing-imports || true
```

**Expected:**
- All tests passing
- No regressions
- Only additions, no changes to existing behavior

**PASTE FULL OUTPUT**

---

### Step 12: Final verification and summary

**Action:** Confirm all changes are correct and complete

**Checklist:**
- [ ] All 1376 unit tests passing
- [ ] Linting clean
- [ ] Configuration validation passing
- [ ] Only async methods ADDED (nothing removed)
- [ ] Existing generator code UNCHANGED
- [ ] Documentation added
- [ ] Git status clean (tracked changes only)

**Summary of changes:**
```bash
git status
git diff --stat
```

**Expected files modified:**
- `src/exabgp/reactor/network/connection.py` (+~80 lines)
- `src/exabgp/reactor/loop.py` (+~15 lines)

**PASTE OUTPUT**

---

## PRE-COMMIT CHECKLIST (Before Any Commit)

**MANDATORY before committing:**

1. **Full Unit Tests:**
```bash
env exabgp_log_enable=false pytest ./tests/unit/ -q
```
**MUST show: "1376 passed" with 0 failures**

2. **Linting:**
```bash
ruff format src && ruff check src
```
**MUST show: "All checks passed!"**

3. **Functional Tests:**
```bash
./qa/bin/functional encoding
```
**MUST show: 100% pass rate (72/72 tests)**

4. **Git Review:**
```bash
git status
git diff
```
**Review all changes carefully**

5. **User Approval:**
- [ ] User has reviewed changes
- [ ] User explicitly approved commit

**IF ANY CHECK FAILS: DO NOT COMMIT**

---

## Success Criteria

**Phase 1 Complete When:**
- ✅ 3 new async I/O methods in connection.py
- ✅ 1 bridge helper in connection.py
- ✅ 1 async event loop wrapper in loop.py
- ✅ All existing code UNCHANGED
- ✅ All 1376 unit tests passing
- ✅ Linting clean
- ✅ Documentation added

**Note:** This completes the FOUNDATION for hybrid approach. Full integration (actually using the async methods) comes in Phase 2 (future work).

---

## Rollback Plan

If anything goes wrong at any step:

1. **STOP immediately**
2. **Do not proceed to next step**
3. **Review the failure**
4. **Decide:**
   - Fix the issue and retest
   - OR revert the change: `git checkout -- <file>`
5. **Only proceed when tests pass**

**Git makes rollback easy:**
```bash
# Revert specific file
git checkout -- src/exabgp/reactor/network/connection.py

# Revert all changes
git checkout -- .
```

---

## Notes

**This plan adds async infrastructure WITHOUT changing existing behavior.**

- Existing generators continue to work
- Async methods available but not yet used
- Zero risk to production code
- Foundation for future integration

**Future work (Phase 2):**
- Actually use async I/O methods
- Integrate with event loop
- Remove old generator I/O (optional)

---

## Approval Required

**Ready to execute this plan?**

Review:
- [ ] Understand all 12 steps
- [ ] Understand MANDATORY_REFACTORING_PROTOCOL
- [ ] Understand rollback plan
- [ ] Ready to paste proof at each step
- [ ] Ready to stop if any failures

**Approval:**
- [ ] Yes - Proceed with Step 1
- [ ] No - Need clarification/changes
- [ ] Questions - Discuss first

---

**Awaiting final approval to begin execution...**
