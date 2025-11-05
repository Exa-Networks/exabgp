# ExaBGP Async/Await Migration Plan

## Executive Summary

This document outlines the plan to modernize ExaBGP's BGP engine from legacy generator-based coroutines to Python's modern async/await syntax. The current implementation predates Python 3.5's async/await and uses a custom scheduler with generator functions and `yield` statements for cooperative multitasking.

## Current Architecture Analysis

### Key Components

1. **Custom ASYNC Scheduler** (`src/exabgp/reactor/asynchronous.py`)
   - Manages a deque of (uid, generator) tuples
   - Calls `next()` on generators up to 50 times per run
   - Manual cooperative multitasking

2. **Main Reactor Loop** (`src/exabgp/reactor/loop.py`)
   - Uses `select.poll()` for I/O multiplexing
   - Schedules generators via ASYNC
   - Single-threaded event loop (546 lines)

3. **Peer State Machine** (`src/exabgp/reactor/peer.py`)
   - 8 generator methods for BGP FSM states
   - Methods: `_run`, `_establish`, `_connect`, `_send_open`, `_read_open`, `_send_ka`, `_read_ka`, `_main`

4. **Protocol Layer** (`src/exabgp/reactor/protocol.py`)
   - 10+ generator methods for message handling
   - Methods: `connect`, `write`, `read_message`, `new_open`, `new_keepalive`, `new_update`, etc.

5. **Network I/O Layer** (`src/exabgp/reactor/network/connection.py`)
   - 3 generator methods: `_reader()`, `writer()`, `reader()`
   - Socket I/O with non-blocking operations

### Generator Patterns Used

```python
# Pattern 1: Yielding control with boolean status
def connect(self):
    for connected in self.connection.establish():
        yield False  # Not ready yet
    yield True       # Ready/connected

# Pattern 2: Yielding without value (give control back)
def _run(self):
    while True:
        # Do some work
        yield  # Give control back to scheduler

# Pattern 3: Generator scheduling
self.asynchronous.schedule(uid, 'description', generator_function())
```

## Python Version Requirements

- **Current**: Python >= 3.8.1, < 3.14 (from pyproject.toml)
- **Target**: Same (no change required)
- **Status**: ✅ Compatible with async/await (introduced in Python 3.5)

## Migration Strategy

### Phase-Based Approach

We'll use a **bottom-up migration strategy**, starting with the lowest-level components (I/O) and working up to the main event loop. This ensures each phase can be tested independently.

### Phases Overview

```
Phase 1: Network I/O Layer (Foundation)
    ↓
Phase 2: Protocol Layer
    ↓
Phase 3: Peer State Machine
    ↓
Phase 4: ASYNC Scheduler → asyncio Tasks
    ↓
Phase 5: Main Reactor Loop → asyncio Event Loop
    ↓
Phase 6: Supporting Components
    ↓
Phase 7: Testing & Validation
```

---

## Detailed Phase Plans

### Phase 1: Network I/O Layer ⚡ START HERE

**Objective**: Convert low-level socket operations to async/await

**Files to Modify**:
- `src/exabgp/reactor/network/connection.py` (265 lines)
- `src/exabgp/reactor/network/outgoing.py`
- `src/exabgp/reactor/network/incoming.py`

**Changes**:

**Before**:
```python
def _reader(self):
    """Generator that yields True when data is available"""
    while True:
        if self.reading():
            yield True
        else:
            yield False
```

**After**:
```python
async def _reader(self):
    """Async function that waits for data availability"""
    loop = asyncio.get_event_loop()
    reader, writer = await asyncio.open_connection(...)
    return reader, writer
```

**Key Transformations**:
- `def func():` → `async def func():`
- `yield False` → `await asyncio.sleep(0)` (yield control)
- `yield True` → `return True`
- `for x in generator: yield status` → `await async_function()`
- Socket polling → `asyncio.StreamReader/StreamWriter`

**Testing**:
- Unit tests for connection establishment
- Test non-blocking reads/writes
- Test connection timeouts

---

### Phase 2: Protocol Layer

**Objective**: Convert BGP message handling to async/await

**Files to Modify**:
- `src/exabgp/reactor/protocol.py` (513 lines)

**Key Methods to Convert** (10+ generators):
- `connect()` - Connection establishment
- `write()` - Message sending
- `read_message()` - Message receiving
- `new_open()`, `new_keepalive()`, `new_update()`, etc.

**Changes**:

**Before**:
```python
def connect(self):
    for connected in self.connection.establish():
        yield False
    yield True

def write(self, message):
    for written in self.connection.writer():
        yield False
    yield True
```

**After**:
```python
async def connect(self):
    await self.connection.establish()
    return True

async def write(self, message):
    await self.connection.writer()
    return True
```

**Testing**:
- Test message serialization/deserialization
- Test OPEN, KEEPALIVE, UPDATE, NOTIFICATION messages
- Test connection error handling

---

### Phase 3: Peer State Machine

**Objective**: Convert BGP FSM to async/await

**Files to Modify**:
- `src/exabgp/reactor/peer.py` (847 lines)
- `src/exabgp/reactor/keepalive.py`

**Key Methods to Convert** (8 generators):
- `_run()` - Main peer loop
- `_establish()` - Establish connection
- `_connect()` - TCP connection
- `_send_open()` - Send OPEN message
- `_read_open()` - Receive OPEN message
- `_send_ka()` - Send KEEPALIVE
- `_read_ka()` - Receive KEEPALIVE
- `_main()` - Established state handler

**Changes**:

**Before**:
```python
def _run(self):
    while self.fsm != FSM.IDLE:
        if self.fsm == FSM.ACTIVE:
            for success in self._connect():
                yield
        elif self.fsm == FSM.CONNECT:
            for success in self._send_open():
                yield
```

**After**:
```python
async def _run(self):
    while self.fsm != FSM.IDLE:
        if self.fsm == FSM.ACTIVE:
            await self._connect()
        elif self.fsm == FSM.CONNECT:
            await self._send_open()
```

**Testing**:
- Test FSM state transitions
- Test connection establishment flow
- Test ESTABLISHED state message handling
- Test error recovery and reconnection

---

### Phase 4: Replace ASYNC Scheduler

**Objective**: Replace custom scheduler with asyncio.create_task()

**Files to Modify**:
- `src/exabgp/reactor/asynchronous.py` (65 lines)

**Changes**:

**Before**:
```python
class ASYNC:
    def schedule(self, uid, command, callback):
        self._async.append((uid, callback))

    def run(self):
        uid, generator = self._async.popleft()
        for _ in range(self.LIMIT):
            try:
                next(generator)
            except StopIteration:
                ...
```

**After**:
```python
class ASYNC:
    def schedule(self, uid, command, callback):
        task = asyncio.create_task(callback)
        self._tasks[uid] = task

    async def run(self):
        # Tasks run automatically, just await any pending
        await asyncio.sleep(0)
```

**Or even simpler**: Remove the ASYNC class entirely and use `asyncio.create_task()` directly in the reactor.

**Testing**:
- Test task creation and execution
- Test task cancellation
- Test error handling in tasks

---

### Phase 5: Main Reactor Loop

**Objective**: Convert reactor to use asyncio event loop

**Files to Modify**:
- `src/exabgp/reactor/loop.py` (546 lines)

**Major Changes**:

**Before**:
```python
def run(self):
    while True:
        # Manual event loop
        peers = self.active_peers()
        for key in peers:
            action = peer.run()  # Call generator

        self.asynchronous.run()

        for io in self._wait_for_io(sleep):
            peers.add(workers[io])
```

**After**:
```python
async def run(self):
    # Create tasks for all peers
    peer_tasks = [
        asyncio.create_task(peer.run())
        for peer in self._peers.values()
    ]

    # Run until stopped
    await asyncio.gather(*peer_tasks, return_exceptions=True)

def start(self):
    asyncio.run(self.run())
```

**Key Changes**:
- Remove `select.poll()` - asyncio handles this
- Remove `_wait_for_io()` - asyncio handles this
- Convert peer management to task-based
- Use `asyncio.gather()` for concurrent peer handling

**Testing**:
- Test with multiple peers
- Test signal handling (SIGTERM, SIGHUP, SIGUSR1, SIGUSR2)
- Test configuration reload
- Test graceful shutdown

---

### Phase 6: Supporting Components

**Objective**: Convert remaining async components

**Files to Modify**:
- `src/exabgp/reactor/listener.py` - Connection listener
- `src/exabgp/reactor/api/processes.py` - API process handling

**Changes**:
- Convert `new_connections()` generator to async
- Convert process I/O to async

**Testing**:
- Test incoming connection handling
- Test API process communication

---

### Phase 7: Testing & Validation

**Objective**: Ensure all functionality works correctly

**Test Categories**:

1. **Unit Tests**
   - Test each converted component independently
   - Mock network I/O where needed

2. **Integration Tests**
   - Test BGP session establishment
   - Test UPDATE message handling
   - Test graceful restart
   - Test configuration reload

3. **Performance Tests**
   - Measure CPU usage
   - Measure memory usage
   - Test with 100+ peers
   - Compare with original implementation

4. **Regression Tests**
   - Run existing test suite
   - Verify no behavioral changes
   - Test edge cases

---

## Implementation Guidelines

### Code Style

1. **Use async/await consistently**
   ```python
   # Good
   async def connect(self):
       await self.connection.establish()

   # Bad - mixing patterns
   async def connect(self):
       for x in self.old_generator():
           await asyncio.sleep(0)
   ```

2. **Proper exception handling**
   ```python
   async def connect(self):
       try:
           await self.connection.establish()
       except ConnectionError as e:
           log.error(f"Connection failed: {e}")
           raise
   ```

3. **Task cancellation**
   ```python
   try:
       await asyncio.wait_for(operation(), timeout=30)
   except asyncio.TimeoutError:
       log.error("Operation timed out")
   ```

### Common Patterns

| Old Pattern | New Pattern |
|-------------|-------------|
| `yield False` | `await asyncio.sleep(0)` |
| `yield True` | `return True` |
| `yield` | `await asyncio.sleep(0)` |
| `next(generator)` | `await async_func()` |
| `select.poll()` | Built into asyncio |
| Manual scheduling | `asyncio.create_task()` |

### Error Handling

1. **CancelledError**: Handle task cancellation gracefully
2. **TimeoutError**: Set appropriate timeouts for operations
3. **NetworkError**: Propagate network errors properly
4. **FSM errors**: Maintain state machine integrity

---

## Backwards Compatibility

### Approach: Big Bang (Recommended)

Given the tight coupling of components, we recommend a **single major version update** rather than maintaining compatibility layers.

**Rationale**:
- Generator-based and async/await patterns are fundamentally incompatible
- Maintaining both would double code complexity
- ExaBGP is a daemon, not a library - users don't import it
- Clean break allows for better long-term maintenance

**Version Strategy**:
- Current: 5.0.0
- Target: 6.0.0 (breaking change)

---

## Risk Assessment

### High Risk Areas

1. **Peer State Machine**: Complex FSM with many edge cases
   - **Mitigation**: Extensive testing of state transitions

2. **Network I/O**: Critical path for BGP communication
   - **Mitigation**: Comprehensive integration tests

3. **Signal Handling**: SIGUSR1/SIGUSR2 for config reload
   - **Mitigation**: Test signal handling in asyncio loop

4. **Performance**: Ensure no regressions
   - **Mitigation**: Benchmark before and after

### Medium Risk Areas

1. **API Process Communication**: External process I/O
   - **Mitigation**: Test with real API scripts

2. **Listener**: Incoming connection handling
   - **Mitigation**: Test passive peer connections

### Low Risk Areas

1. **Configuration**: Not affected by async changes
2. **Message Parsing**: Pure functions, no async needed
3. **RIB Management**: Data structures, no async needed

---

## Timeline Estimate

| Phase | Estimated Time | Complexity |
|-------|---------------|------------|
| Phase 1: Network I/O | 2-3 days | Medium |
| Phase 2: Protocol Layer | 3-4 days | Medium-High |
| Phase 3: Peer State Machine | 4-5 days | High |
| Phase 4: ASYNC Scheduler | 1-2 days | Low |
| Phase 5: Main Reactor | 3-4 days | High |
| Phase 6: Supporting | 2-3 days | Medium |
| Phase 7: Testing | 5-7 days | High |
| **Total** | **20-28 days** | - |

---

## Success Criteria

1. ✅ All generator functions converted to async/await
2. ✅ No usage of custom ASYNC scheduler
3. ✅ Main loop uses asyncio.run()
4. ✅ All existing tests pass
5. ✅ No performance regression (< 5% overhead)
6. ✅ Code is cleaner and more maintainable
7. ✅ Documentation updated

---

## Getting Started

### Recommended Order

1. **Start with Phase 1** (Network I/O Layer)
   - This is the foundation
   - Smallest scope
   - Can be tested independently

2. **Move to Phase 2** (Protocol Layer)
   - Builds on Phase 1
   - Still relatively isolated

3. **Continue sequentially** through remaining phases

### First Steps

1. Create a feature branch: `feature/async-await-migration`
2. Set up testing environment
3. Begin Phase 1 with `connection.py`
4. Write tests as you go
5. Commit after each file/component is converted

---

## Questions to Address

1. **Q**: Should we maintain backward compatibility?
   **A**: No - recommend clean break with version 6.0.0

2. **Q**: Can we do this incrementally?
   **A**: Yes - bottom-up approach allows testing each phase

3. **Q**: What about performance?
   **A**: asyncio should be comparable or better, but needs validation

4. **Q**: What about Python 3.7 support?
   **A**: Current requirement is 3.8.1+, so we're safe

5. **Q**: How do we handle the transition?
   **A**: Thorough testing and documentation

---

## Resources

### Python asyncio Documentation
- https://docs.python.org/3/library/asyncio.html
- https://docs.python.org/3/library/asyncio-task.html
- https://docs.python.org/3/library/asyncio-stream.html

### Migration Guides
- https://docs.python.org/3/library/asyncio-task.html#coroutines
- https://realpython.com/async-io-python/

### ExaBGP Specific
- Architecture documentation: See generated docs in `/tmp/`
- Generator analysis: 29 functions identified
- Current test suite: `pytest` tests

---

## Conclusion

This migration will modernize ExaBGP's async engine, making it more maintainable and aligned with Python best practices. The phase-based approach ensures we can test incrementally while the bottom-up strategy builds a solid foundation.

The estimated 20-28 day timeline accounts for careful implementation, thorough testing, and documentation updates. The result will be a cleaner, more maintainable codebase ready for future development.

**Ready to begin? Start with Phase 1!**
