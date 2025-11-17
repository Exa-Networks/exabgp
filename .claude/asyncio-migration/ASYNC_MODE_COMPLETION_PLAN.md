# AsyncIO Mode Completion Plan

**Status:** 50% Functional (36/72 functional tests passing)
**Created:** 2025-11-17
**Goal:** Make async mode production-ready with 100% test pass rate

---

## Current State Analysis

### What Works ✅

**Sync Mode (Generator-based):**
- Unit tests: 1376/1376 (100%)
- Functional tests: 72/72 (100%)
- Configuration validation: ✅ Passing
- Fully production-ready

**Async Mode (AsyncIO-based):**
- Unit tests: 1376/1376 (100%)
- Functional tests: 36/72 (50%)
- Simple BGP sessions work
- Complex scenarios fail

### What's Missing ❌

Comparing sync vs async event loops reveals critical missing functionality:

#### 1. **Socket I/O Polling and Event Management**
**Sync Loop Has:**
```python
workers: dict = {}  # Maps file descriptors → peer keys
for io in self._wait_for_io(sleep):  # Poll sockets
    if io not in api_fds:
        peers.add(workers[io])  # Wake up peers with ready sockets
```

**Async Loop Missing:**
- No socket polling mechanism
- No fd → peer mapping
- No event-driven peer wakeup
- All peers run continuously without waiting for I/O events

**Impact:** Peers busy-spin instead of waiting for network data, causing:
- High CPU usage
- Timeouts in tests that expect event-driven behavior
- No proper coordination between peer I/O and network readiness

#### 2. **Peer Rate Limiting**
**Sync Loop Has:**
```python
if self._rate_limited(key, peer.neighbor['rate-limit']):
    peers.discard(key)
    continue
```

**Async Loop Missing:**
- No `_rate_limited()` check before running peers
- Peers can exceed configured rate limits

**Impact:** Tests with rate-limit configurations may fail

#### 3. **ACTION-Based Peer Scheduling**
**Sync Loop Has:**
```python
action = peer.run()
if action == ACTION.CLOSE:
    del self._peers[key]
elif action == ACTION.LATER:
    # Register socket for polling
    self._poller.register(io, ...)
    workers[io] = key
elif action == ACTION.NOW:
    sleep = 0  # Immediate reschedule
```

**Async Loop Missing:**
- No ACTION enum handling
- Peers run as fire-and-forget tasks
- No coordination based on peer needs

**Impact:** Peers don't properly signal when they need attention

#### 4. **API File Descriptor Management**
**Sync Loop Has:**
```python
api_fds: list = []
if api_fds != self.processes.fds:
    # Register/unregister API process fds with poller
    for fd in self.processes.fds:
        self._poller.register(fd, ...)
```

**Async Loop Missing:**
- No API fd tracking
- No poller registration for API processes
- API commands may not trigger peer wakeups

**Impact:** Tests using API commands may timeout

#### 5. **Worker Cleanup**
**Sync Loop Has:**
```python
for io in list(workers.keys()):
    if io == -1:
        self._poller.unregister(io)
        del workers[io]
```

**Async Loop Missing:**
- No fd cleanup on socket close

**Impact:** Resource leaks on connection close

---

## Root Cause: Architectural Mismatch

### The Core Problem

The async implementation **abandons the event-driven I/O model** that the sync loop relies on:

**Sync Model (Event-Driven):**
1. Poll sockets with `select.poll()`
2. Wake only peers with ready sockets
3. Peers yield after each operation
4. Reactor schedules based on I/O readiness

**Current Async Model (Task-Based):**
1. Start all peers as concurrent tasks
2. Peers run continuously
3. No I/O event coordination
4. No scheduler feedback

**Why This Fails:**
- BGP requires precise I/O timing (KEEPALIVE, timeouts)
- Tests expect event-driven behavior
- Concurrent tasks without I/O coordination cause race conditions

---

## Completion Roadmap

### Phase 1: I/O Event Integration (HIGH PRIORITY)

**Goal:** Integrate asyncio I/O primitives with peer tasks

**Tasks:**

#### 1.1: Replace `_wait_for_io()` with asyncio equivalent
```python
async def _wait_for_io_async(self, sleeptime: int) -> list[int]:
    # Current: Just sleeps
    # Needed: Actually poll sockets using asyncio

    # Option A: Use asyncio.create_task with socket readers
    # Option B: Use asyncio streams
    # Option C: Use add_reader/add_writer callbacks
```

**Recommendation:** Use `loop.add_reader()` for event-driven wakeups

#### 1.2: Implement async peer I/O coordination
```python
async def _run_async_peers(self) -> None:
    # Add fd → peer mapping
    # Add I/O event handling
    # Wake peers only when sockets are ready
```

#### 1.3: Update Connection async methods
Current `reader_async()` and `writer_async()` are simplified.
Need to integrate with asyncio event loop properly.

**Estimated Effort:** 8-12 hours
**Risk:** MEDIUM (requires understanding asyncio I/O primitives)

---

### Phase 2: Peer Lifecycle Management (MEDIUM PRIORITY)

**Goal:** Implement ACTION-based scheduling in async mode

**Tasks:**

#### 2.1: Add ACTION handling to async peer tasks
```python
async def _run_async_peers(self) -> None:
    for key in self.active_peers():
        peer = self._peers[key]
        # How to get ACTION from async task?
        # Need bidirectional communication
```

**Challenge:** Async tasks don't return ACTION like generators do

**Solutions:**
- **Option A:** Add task → reactor communication channel (asyncio.Queue)
- **Option B:** Use task metadata/callbacks
- **Option C:** Rewrite peer tasks to use different pattern

**Recommended:** Option A (asyncio.Queue per peer)

#### 2.2: Implement rate limiting
```python
async def _async_main_loop(self) -> None:
    # Before calling _run_async_peers()
    for key in list(peers):
        if self._rate_limited(key, self._peers[key].neighbor['rate-limit']):
            # Don't wake this peer
            continue
```

**Estimated Effort:** 4-6 hours
**Risk:** LOW

---

### Phase 3: API Process Integration (MEDIUM PRIORITY)

**Goal:** Handle API file descriptor events in async loop

**Tasks:**

#### 3.1: Track API file descriptors
```python
async def _async_main_loop(self) -> None:
    api_fds: list = []
    # Monitor self.processes.fds changes
    # Use add_reader() for API fds
```

#### 3.2: Integrate API commands with async peers
Ensure API commands trigger peer wakeups properly

**Estimated Effort:** 3-4 hours
**Risk:** LOW

---

### Phase 4: Testing and Debugging (HIGH PRIORITY)

**Goal:** Debug the 36 failing functional tests

**Approach:**

#### 4.1: Run individual failing tests
```bash
./qa/bin/functional encoding 0  # Run test 0
./qa/bin/functional encoding --server 0  # Server only
./qa/bin/functional encoding --client 0  # Client only
```

Identify patterns in failures:
- Do all timeouts happen at specific BGP states?
- Are certain message types failing?
- Is it connection establishment or maintenance?

#### 4.2: Add detailed async logging
```python
# In _async_main_loop(), _run_async_peers(), peer async methods
log.debug(lambda: f'[ASYNC] ...')
```

Enable with: `export exabgp_log_enable=true`

#### 4.3: Compare sync vs async traces
Run same test in both modes with logging, compare behavior

#### 4.4: Incremental fixes
Fix one failing test at a time, re-run full suite after each fix

**Estimated Effort:** 12-16 hours
**Risk:** HIGH (debugging is unpredictable)

---

### Phase 5: Performance Optimization (LOW PRIORITY)

**Goal:** Ensure async mode is performant

**Tasks:**

#### 5.1: Benchmark sync vs async
- Latency per BGP message
- CPU usage
- Memory usage
- Concurrent peer capacity

#### 5.2: Optimize sleep times
Currently using fixed `await asyncio.sleep(ms_sleep / 1000.0)`
Should adapt based on peer needs

#### 5.3: Reduce task creation overhead
Consider task pooling if creating/destroying tasks frequently

**Estimated Effort:** 4-6 hours
**Risk:** LOW

---

### Phase 6: Production Readiness (HIGH PRIORITY)

**Goal:** Make async mode safe for production

**Tasks:**

#### 6.1: Exception handling audit
Ensure all async methods handle exceptions properly

#### 6.2: Resource cleanup verification
Test connection close, peer removal, signal handling

#### 6.3: Long-running stability test
Run async mode for extended period (hours/days)
Monitor for memory leaks, deadlocks, etc.

#### 6.4: Documentation
- Update README with async mode usage
- Document performance characteristics
- Add troubleshooting guide

**Estimated Effort:** 6-8 hours
**Risk:** MEDIUM

---

## Total Effort Estimate

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1: I/O Events | 8-12 hours | MEDIUM |
| Phase 2: Lifecycle | 4-6 hours | LOW |
| Phase 3: API Integration | 3-4 hours | LOW |
| Phase 4: Debugging | 12-16 hours | HIGH |
| Phase 5: Performance | 4-6 hours | LOW |
| Phase 6: Production | 6-8 hours | MEDIUM |
| **TOTAL** | **37-52 hours** | **MEDIUM-HIGH** |

---

## Recommended Approach

### Strategy A: Full Completion (37-52 hours)

Complete all phases in order. Best for:
- Production deployment planned
- Want feature parity with sync mode
- Time available for thorough testing

### Strategy B: Iterative (20-30 hours for MVP)

Focus on critical path:
1. Phase 1 (I/O Events)
2. Phase 4 (Debug failing tests)
3. Phase 2 (Lifecycle - partial)

Skip performance optimization and full production hardening initially.

### Strategy C: Hybrid Approach (Recommended)

Keep both modes long-term:
- **Sync mode:** Default, production-ready
- **Async mode:** Experimental, opt-in via `exabgp.reactor.asyncio=true`

Benefits:
- No pressure to rush async completion
- Can migrate gradually
- Easy rollback if issues found
- Users can test async mode in dev/staging

---

## Debugging Quick Start

### Step 1: Identify Which Tests Fail

```bash
export exabgp_reactor_asyncio=true
./qa/bin/functional encoding 2>&1 | tee async-test-results.txt
```

Failed tests: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, A, B, C, D, E, F, G, H, I, J, K, L, M, N, O, P, R, S, T, U, V, W, X, Y, Z, θ]

### Step 2: Pick One Failing Test

```bash
./qa/bin/functional encoding --list | grep "^0:"
```

### Step 3: Run in Debug Mode

```bash
export exabgp_log_enable=true
export exabgp_reactor_asyncio=true
./qa/bin/functional encoding 0 > async-test-0.log 2>&1
```

### Step 4: Compare with Sync Mode

```bash
export exabgp_log_enable=true
unset exabgp_reactor_asyncio
./qa/bin/functional encoding 0 > sync-test-0.log 2>&1
```

### Step 5: Analyze Differences

```bash
diff -u sync-test-0.log async-test-0.log
```

Look for:
- Where async mode diverges
- Missing log entries (indicates code not reached)
- Different timing/ordering
- Exception stack traces

### Step 6: Add Targeted Logging

In `_async_main_loop()`, `_run_async_peers()`, peer async methods:
```python
log.debug(lambda: f'[ASYNC-DEBUG] checkpoint X reached', 'reactor')
```

### Step 7: Iterate

Fix issue, re-run test, verify pass, move to next failing test.

---

## Key Files to Modify

1. **src/exabgp/reactor/loop.py**
   - `_async_main_loop()` - Add I/O polling
   - `_run_async_peers()` - Add fd mapping, ACTION handling

2. **src/exabgp/reactor/network/connection.py**
   - `reader_async()`, `writer_async()` - Integrate with asyncio I/O

3. **src/exabgp/reactor/peer.py**
   - `run_async()` - Add ACTION return mechanism
   - `_run_async()`, `_main_async()` - Add communication with reactor

4. **src/exabgp/reactor/protocol.py**
   - Already has async methods, may need I/O integration updates

---

## Success Criteria

- [ ] Functional tests: 72/72 passing in async mode
- [ ] Unit tests: 1376/1376 passing in async mode
- [ ] Configuration validation passing in async mode
- [ ] No memory leaks over 24-hour run
- [ ] No performance regression vs sync mode
- [ ] All exception paths tested
- [ ] Documentation complete

---

## Risks and Mitigations

### Risk 1: Fundamental Architecture Incompatibility
**Probability:** LOW
**Impact:** CRITICAL
**Mitigation:** PoC already proves async is viable, just needs I/O integration

### Risk 2: Race Conditions in Async Peer Tasks
**Probability:** MEDIUM
**Impact:** HIGH
**Mitigation:** Careful synchronization, use asyncio primitives (Lock, Queue)

### Risk 3: Time Overrun (>52 hours)
**Probability:** MEDIUM
**Impact:** MEDIUM
**Mitigation:** Use iterative approach, stop at MVP if needed

### Risk 4: Unfixable Edge Cases
**Probability:** LOW
**Impact:** HIGH
**Mitigation:** Keep sync mode as fallback, async is experimental

---

## Next Session Action Items

1. **Immediate:** Run individual failing tests to understand patterns
2. **Short-term:** Implement Phase 1.1 (asyncio I/O polling)
3. **Medium-term:** Debug and fix failing tests one by one
4. **Long-term:** Complete all phases for production readiness

---

**Status:** PLANNING COMPLETE
**Next:** Begin Phase 1.1 or debugging individual tests
