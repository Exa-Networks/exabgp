# Migration Strategy

**Approach:** Exploratory - start with easy wins, build patterns, scale up complexity

**Scope:** ~80 generators (critical path only, skip parsing/config)

**Event Loop:** Full asyncio.run() integration

---

## Overall Strategy

1. **Learn by doing** - convert simple generators first
2. **Build patterns** - document what works
3. **Incremental safety** - test after each function
4. **Progressive complexity** - simple → medium → complex
5. **Keep working code** - all tests pass at every step

---

## Phase 0: Foundation & Easy Wins

**Goal:** Convert 3-5 simple single-yield generators, establish patterns

**Duration:** 1-2 sessions (2-4 hours)

### Targets (Simple Generators)

**Criteria:** Single yield, no nesting, no complex logic

**Candidates:**
- `loop.py::_wait_for_io()` - yields file descriptors
- Simple utility generators in network layer
- Helper functions with single return point

### Steps

1. **Review archived migration docs**
   - Read `.claude/archive/async-migration/`
   - Extract working patterns
   - Note any blockers/learnings

2. **Find simplest generators**
   - Grep for simple `yield` patterns
   - Prioritize by simplicity
   - Create conversion list

3. **Convert first function**
   - Choose absolute simplest
   - Convert generator → async/await
   - Run linting
   - Run all unit tests
   - Commit if passing

4. **Repeat for 2-4 more**
   - Apply learned patterns
   - Document variations
   - Build confidence

5. **Document patterns**
   - Update CONVERSION_PATTERNS.md
   - Note successes and failures
   - Create quick reference

**Success Criteria:**
- ✅ 3-5 functions converted
- ✅ All tests passing (1376 unit tests)
- ✅ Patterns documented
- ✅ Confidence established

---

## Phase 1: Event Loop Integration

**Goal:** Replace select.poll() with asyncio.run()

**Duration:** 2-3 sessions (4-6 hours)

**Approach:** Full asyncio event loop replacement

### Current Event Loop (select.poll())

```python
def run(self) -> int:
    while True:
        # Process peers
        for key in peers:
            peer.run()

        # Run async scheduler
        self.asynchronous.run()

        # Wait for I/O
        for fd in self._wait_for_io(sleep):
            # Handle ready sockets
```

### Target (asyncio.run())

```python
async def run(self) -> int:
    """Main async event loop"""
    # Create asyncio tasks for each peer
    tasks = []
    for key in peers:
        task = asyncio.create_task(peer.run_async())
        tasks.append(task)

    # Wait for I/O and tasks concurrently
    await asyncio.gather(*tasks, self._handle_io())
```

### Challenges

1. **Socket integration** - use `loop.sock_recv()` / `loop.sock_send()`
2. **Peer coordination** - convert peer.run() to async
3. **Signal handling** - asyncio signal handlers
4. **Backward compat** - some generators still exist

### Steps

1. Create async wrapper for main loop
2. Convert socket I/O to asyncio primitives
3. Update peer.run() to async
4. Test thoroughly
5. Commit when stable

**Blockers:** Need Phase 0 patterns first

---

## Phase 2: Medium Complexity Generators

**Goal:** Convert loop-based and chain generators (~60 functions)

**Duration:** 3-5 sessions (6-10 hours)

### Targets

**Files:**
- `reactor/network/connection.py` (3) - socket I/O
- `reactor/network/tcp.py` (4) - TCP connections
- `reactor/network/incoming.py` (5) - accept loop
- `reactor/protocol.py` (14) - message I/O
- `reactor/rib/outgoing.py` (3) - RIB updates
- Network helpers (31) - various utilities

**Patterns:**

#### Loop-based generators
```python
# Current
def reader(self):
    while True:
        data = self.io.recv(1024)
        yield data

# Target
async def reader(self):
    while True:
        data = await self.loop.sock_recv(self.io, 1024)
        return data
```

#### Generator chains
```python
# Current
def read_message(self):
    for length, msg_id, header, body in self.connection.reader():
        yield (length, msg_id, header, body)

# Target
async def read_message(self):
    length, msg_id, header, body = await self.connection.reader()
    return (length, msg_id, header, body)
```

### Steps

1. Group by file/subsystem
2. Convert one file at a time
3. Test after each file
4. Commit when passing
5. Document patterns as we go

**Blockers:** Need event loop integrated first

---

## Phase 3: Complex Nested Generators (API)

**Goal:** Convert API command handlers (~45 functions)

**Duration:** 4-6 sessions (8-12 hours)

### Targets

**File:** `reactor/api/command/announce.py` (30 functions)
**Files:** `reactor/api/*.py` (15 more functions)

**Pattern:** Nested generator → direct async

#### Current (Nested Generator)
```python
@Command.register('announce route')
def announce_route(self, reactor, service, line, use_json):
    def callback():  # Inner generator
        try:
            peers = match_neighbors(...)
            changes = self.api_route(command)
            for change in changes:
                reactor.configuration.inject_change(peers, change)
                yield False  # Continue
            reactor.processes.answer_done(service)
        except ValueError:
            reactor.processes.answer_error(service)
            yield True  # Error

    reactor.asynchronous.schedule(service, line, callback())
    return True
```

#### Target (Direct Async)
```python
@Command.register('announce route')
async def announce_route(self, reactor, service, line, use_json):
    try:
        peers = match_neighbors(...)
        changes = self.api_route(command)
        for change in changes:
            reactor.configuration.inject_change(peers, change)
            await asyncio.sleep(0)  # Yield control
        reactor.processes.answer_done(service)
    except ValueError:
        reactor.processes.answer_error(service)
```

### Refactoring Required

1. **Remove nesting** - inner callback becomes main function
2. **Remove yield True/False** - just return or raise
3. **Add await points** - where control should yield
4. **Update scheduler calls** - schedule coroutine not generator

### Steps

1. Start with simplest API handler
2. Convert, test, commit
3. Apply pattern to similar handlers
4. Document edge cases
5. Handle all 45 functions

**Blockers:** Need Phases 0-2 complete first

---

## Excluded from Migration

**Will NOT convert:**

### Parsing Generators (43 files)
- Work fine as generators
- Not in hot path
- Used during message decode
- Low value, high effort

### Config Generators (35 files)
- Startup-time only
- Not performance critical
- Complex parsing logic
- Low priority

### Test Generators (3 files)
- Stable and working
- Used for testing only
- Do not modify

---

## Testing Strategy

**MANDATORY after each function conversion:**

```bash
# 1. Linting
ruff format src && ruff check src

# 2. Unit tests (ALL must pass)
env exabgp_log_enable=false pytest ./tests/unit/

# 3. Functional tests (for affected functionality)
./qa/bin/functional encoding <test_id>
```

**Per MANDATORY_REFACTORING_PROTOCOL:**
- ONE function at a time
- ALL tests must ALWAYS pass
- PASTE proof at every step
- COMMIT only when passing

---

## Success Criteria

**Phase 0:** ✅ 3-5 simple generators converted, patterns documented
**Phase 1:** ✅ asyncio.run() event loop integrated, all tests passing
**Phase 2:** ✅ Network/protocol generators converted, all tests passing
**Phase 3:** ✅ API handlers converted, all tests passing

**Final State:**
- ~80 generators converted to async/await
- All 1376 unit tests passing
- All 72 functional tests passing
- Modern asyncio-based architecture
- Parsing/config still use generators (acceptable)

---

## Risk Mitigation

1. **Incremental commits** - revert easily if needed
2. **Full test suite** - catch regressions immediately
3. **Exploratory approach** - learn from simple cases first
4. **Document blockers** - clear handoff between sessions
5. **Keep working code** - never commit broken state

---

**Updated:** 2025-11-16
