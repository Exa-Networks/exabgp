# ExaBGP Generator Migration - Quick Reference Guide

## What You Need to Know

### The Codebase at a Glance
- **Type:** BGP daemon (network routing software)
- **Age:** ~15 years (since 2009)
- **Python:** 3.8+ only (on main branch)
- **Current Architecture:** Custom generator-based async framework

### Generator Usage Summary
- **Total Generator Functions:** ~150
- **Total Generator Expressions:** ~70
- **Files Affected:** 44 (41 production + 3 test)
- **Critical Files:** 3 (announce.py, protocol.py, peer.py = 53 functions)

---

## Architecture Overview

### Current Event Loop Pattern

```python
# reactor/loop.py main loop
while True:
    for key in list(peers):
        peer = self._peers[key]
        action = peer.run()  # Returns ACTION.NOW/LATER/CLOSE
        
    self.asynchronous.run()  # Process all scheduled generators
    
    for io in self._wait_for_io(sleep):
        # Handle I/O events
```

### Current Async Pattern

```python
# reactor/asynchronous.py - ASYNC class
class ASYNC(object):
    def schedule(self, uid, command, callback):
        self._async.append((uid, callback))
        
    def run(self):
        # Resume up to 50 generators per cycle
        for _ in range(50):
            try:
                next(generator)  # Resume generator
            except StopIteration:
                # Get next generator
```

### API Handler Pattern (Most Common)

```python
# Current pattern in reactor/api/command/announce.py
@Command.register('announce route')
def announce_route(self, reactor, service, line, use_json):
    def callback():  # Nested generator
        try:
            yield False  # Continue processing
            yield True   # Stop processing
        except:
            yield True
    reactor.asynchronous.schedule(service, line, callback())
    return True
```

---

## Migration Path

### Phase 1: Infrastructure Update (1-2 hours)
**Goal:** Make ASYNC class work with async/await

**Changes Needed:**
1. Modify `ASYNC.schedule()` to accept both generators and coroutines
2. Update `ASYNC.run()` to use `await` instead of `next()`
3. Convert main loop to async def with asyncio event loop

**File:** `/home/user/exabgp/src/exabgp/reactor/asynchronous.py`

```python
# Before
def run(self):
    for _ in range(50):
        try:
            next(generator)
        except StopIteration:
            pass

# After
async def run(self):
    for _ in range(50):
        try:
            await generator
        except StopIteration:
            pass
```

---

### Phase 2: Critical Conversions (4-6 hours)
**Goal:** Convert highest-impact files

**Priority 1 - API Command Handlers** (30 generators)
- File: `/home/user/exabgp/src/exabgp/reactor/api/command/announce.py`
- Changes: Convert nested generators to async def
- Pattern Change:
  ```python
  # Before: Nested generator
  def announce_route(self, reactor, service, line, use_json):
      def callback():
          yield False
          yield True
      reactor.asynchronous.schedule(service, line, callback())
  
  # After: Async coroutine
  async def announce_route(self, reactor, service, line, use_json):
      await process_route_announcement()
  ```

**Priority 2 - Protocol Handler** (14 generators)
- File: `/home/user/exabgp/src/exabgp/reactor/protocol.py`
- Functions: `read_message()`, `connect()`, `write()`, `send()`
- Pattern: Change `for ... in generator():` to `async for ... in generator():`

**Priority 3 - Peer State Machine** (9 generators)
- File: `/home/user/exabgp/src/exabgp/reactor/peer.py`
- Functions: `_connect()`, `_send_open()`, `_read_open()`, etc.
- Pattern: Convert state transitions to async/await

---

### Phase 3: Supporting Systems (3-4 hours)
**Goal:** Convert remaining high-priority items

**Connection Handler** (3 generators)
- File: `/home/user/exabgp/src/exabgp/reactor/network/connection.py`
- Functions: `reader()`, `writer()`

**RIB Updates** (2 generators)
- File: `/home/user/exabgp/src/exabgp/rib/outgoing.py`
- Function: `updates(grouped)`
- Note: Can likely remain as regular generator (not async)

**Flow Parser** (16 generators)
- File: `/home/user/exabgp/src/exabgp/configuration/flow/parser.py`
- Note: Can likely remain as generators (not async-critical)

---

### Phase 4: Utilities and Testing (2-3 hours)
**Goal:** Convert or refactor remaining generators

**Configuration Parsing** (20+ generators)
- Can largely remain as regular generators
- Focus on removing from async path if possible

**CLI Completion** (9 generators)
- Can likely remain as generators

**Netlink Module** (15 generators)
- Platform-specific, can convert gradually

**Test Fixtures** (25 generators)
- Update mock fixtures as needed

---

## Top 5 Things to Convert First

### 1. API Command Handlers (`announce.py`)
**Why:** Drives all external API operations
**Effort:** High (nested generators, 69 yields)
**Impact:** Critical path for external integrations

### 2. Protocol Handler (`protocol.py`)
**Why:** Core BGP message I/O
**Effort:** Medium-High (14 generators with iteration)
**Impact:** Network I/O bottleneck

### 3. Peer State Machine (`peer.py`)
**Why:** BGP peer connection lifecycle
**Effort:** Medium (9 generators, complex state)
**Impact:** Connection establishment/teardown

### 4. Connection Handler (`network/connection.py`)
**Why:** TCP socket I/O
**Effort:** Low-Medium (3 generators)
**Impact:** Low-level I/O operations

### 5. RIB Generator (`rib/outgoing.py`)
**Why:** Route message generation
**Effort:** Low (2 generators)
**Impact:** Route dissemination

---

## Key Challenges

### Challenge 1: Nested Generators
**Problem:** API handlers have nested generator functions
```python
def announce_route(reactor, service, line):
    def callback():  # <-- This is nested
        yield False
    reactor.asynchronous.schedule(service, line, callback())
```
**Solution:** Flatten to async def or use async generator patterns

### Challenge 2: Multiple for-loops with yields
**Problem:** Protocol.py has complex iteration patterns
```python
for message in self.read_message():  # <-- generator iteration
    for change in message.changes:
        yield change
```
**Solution:** Convert to async iterators and async for loops

### Challenge 3: Integration with select.poll()
**Problem:** Event loop uses select.poll() not asyncio
**Solution:** Create bridge between select and asyncio, or use asyncio with custom event loop

### Challenge 4: Generator Expressions vs Generator Functions
**Problem:** Some code uses generator expressions (lower priority)
```python
items = (x for x in list if condition)  # <-- generator expression
```
**Solution:** Can convert to list comprehensions or keep as-is

---

## Migration Checklist

### Before Starting
- [ ] Create feature branch: `git checkout -b feature/async-migration`
- [ ] Review `TESTING_ROADMAP.md` and `TESTING_ANALYSIS.md`
- [ ] Set up CI/CD testing
- [ ] Run full test suite baseline: `pytest tests/`
- [ ] Document current behavior with functional tests

### Phase 1: Infrastructure
- [ ] Study `asynchronous.py` and `loop.py` thoroughly
- [ ] Design ASYNC class changes
- [ ] Add asyncio event loop integration
- [ ] Update main loop to async
- [ ] Create wrapper for compatibility
- [ ] Test infrastructure changes only

### Phase 2: Critical Path
- [ ] Convert `announce.py` (30 generators)
- [ ] Verify API operations still work
- [ ] Convert `protocol.py` (14 generators)
- [ ] Test BGP message I/O
- [ ] Convert `peer.py` (9 generators)
- [ ] Test peer lifecycle
- [ ] Run full test suite after each file

### Phase 3: Supporting Systems
- [ ] Convert remaining reactor/* files
- [ ] Convert `rib/outgoing.py`
- [ ] Test route operations

### Phase 4: Utilities
- [ ] Convert `configuration/` parsers (optional)
- [ ] Convert `cli/completer.py` (optional)
- [ ] Update test fixtures
- [ ] Final full test suite run

### After Completion
- [ ] Run performance benchmarks
- [ ] Check for regressions
- [ ] Create PR with detailed summary
- [ ] Get code review
- [ ] Merge to main

---

## Testing Strategy

### Unit Tests
```bash
uv run pytest tests/unit/ -v
```

### Fuzz Tests
```bash
uv run pytest tests/fuzz/ -v
```

### Full Test Suite
```bash
uv run pytest tests/ -v --cov=src/exabgp
```

### Functional Tests
```bash
./qa/bin/functional encoding --list
./qa/bin/functional encoding A  # Run specific test
```

---

## File Priority Reference

### MUST CONVERT (Critical Path)
```
/home/user/exabgp/src/exabgp/reactor/api/command/announce.py      (30 gens) [HIGHEST]
/home/user/exabgp/src/exabgp/reactor/protocol.py                  (14 gens)
/home/user/exabgp/src/exabgp/reactor/peer.py                      (9 gens)
/home/user/exabgp/src/exabgp/reactor/network/connection.py         (3 gens)
/home/user/exabgp/src/exabgp/rib/outgoing.py                       (2 gens)
/home/user/exabgp/src/exabgp/reactor/asynchronous.py               (1 - Infrastructure)
```

### SHOULD CONVERT (High Impact)
```
/home/user/exabgp/src/exabgp/configuration/flow/parser.py          (16 gens)
/home/user/exabgp/src/exabgp/bgp/message/update/attribute/attributes.py (4 gens)
/home/user/exabgp/src/exabgp/reactor/api/command/rib.py            (6 gens)
/home/user/exabgp/src/exabgp/reactor/api/command/neighbor.py       (5 gens)
/home/user/exabgp/src/exabgp/reactor/keepalive.py                  (3 gens)
```

### CAN CONVERT LATER (Lower Priority)
```
/home/user/exabgp/src/exabgp/cli/completer.py                      (9 gens)
/home/user/exabgp/src/exabgp/configuration/core/tokeniser.py       (6 gens)
/home/user/exabgp/src/exabgp/netlink/old.py                        (5 gens)
/home/user/exabgp/src/exabgp/environment/environment.py            (3 gens)
```

---

## Estimated Timeline

| Phase | Task | Files | Effort | Risk |
|-------|------|-------|--------|------|
| 1 | Infrastructure | 1 | 1-2h | Medium |
| 2a | API Handlers | 1 | 2-3h | High |
| 2b | Protocol Handler | 1 | 2h | High |
| 2c | Peer State Machine | 1 | 1.5h | High |
| 3a | Connection Handler | 1 | 0.5h | Low |
| 3b | RIB Updates | 1 | 0.5h | Low |
| 3c | Flow Parser | 1 | 1h | Medium |
| 4 | Config/Utilities | 10+ | 1-2h | Low |
| Testing | Full validation | All | 2-3h | Medium |
| **TOTAL** | | | **12-17h** | |

---

## Reference Documentation

### Key Files to Review
1. `/home/user/exabgp/README.md` - Project overview
2. `/home/user/exabgp/TESTING_ROADMAP.md` - Testing strategy
3. `/home/user/exabgp/PROGRESS.md` - Current status
4. `/home/user/exabgp/src/exabgp/reactor/asynchronous.py` - Current ASYNC class
5. `/home/user/exabgp/src/exabgp/reactor/loop.py` - Main event loop

### Useful Python Docs
- https://docs.python.org/3/library/asyncio.html
- https://docs.python.org/3/howto/functional.html#generators
- https://peps.python.org/pep-0492/ - async/await syntax

### Related RFCs (BGP)
- RFC 4271 - BGP-4
- RFC 6793 - 4-Octet ASN
- RFC 7606 - Error Handling for UPDATE

---

## Quick Decision Tree

**Should this generator be converted to async/await?**

1. Is it in the critical path (announce.py, protocol.py, peer.py)?
   - YES → Convert to async def with await/async for
   
2. Is it called from the async event loop?
   - YES → Convert to async def
   
3. Is it just iterating over data (tokenizer, parser)?
   - YES → Can convert to list comprehension or keep as regular generator
   
4. Is it doing I/O operations?
   - YES → Convert to async def with async I/O
   
5. Is it in tests or utilities?
   - YES → Lower priority, can be deferred

