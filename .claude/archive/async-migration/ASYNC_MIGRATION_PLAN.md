# ExaBGP Generator to Async/Await Migration Plan

**Version:** 1.0
**Date:** 2025-11-08
**Branch:** `claude/convert-generators-to-async-011CUwFUB42rVxbv6Uf6XFQw`

---

## Executive Summary

This plan outlines the progressive conversion of ExaBGP's generator-based asynchronous framework to Python's native async/await and asyncio. The migration will be executed through **28 separate PRs**, allowing incremental testing and validation at each step.

### Key Constraints

1. **No test program modifications during migration** - Test files using generators remain stable
2. **One PR per generator file/component** - Each change is isolated and testable
3. **Progressive implementation** - Each PR builds on previous work without breaking existing functionality
4. **Multi-session capable** - Clear checkpoints allow work to span multiple sessions

### Scope

- **Production Files:** 41 files with ~150 generator functions
- **Test Files:** 3 files (will NOT be modified - kept stable for testing)
- **Critical Path:** 5 high-priority files containing 58 generator functions (37% of total)
- **Timeline:** 28 PRs across 4 phases, estimated 40-60 hours total

---

## Migration Architecture

### Current State

```python
# Custom generator-based async framework
class ASYNC:
    def schedule(self, uid, command, callback):
        self._async.append((uid, callback))  # callback is a generator

    def run(self):
        # Resume generators manually with next()
        for _ in range(50):
            next(generator)
```

### Target State

```python
# Modern asyncio-based framework
class ASYNC:
    def schedule(self, uid, command, callback):
        self._async.append((uid, callback))  # callback is a coroutine

    async def run(self):
        # Await coroutines naturally
        for _ in range(50):
            await coroutine
```

### Compatibility Strategy

During migration, the ASYNC framework will support BOTH generators and coroutines simultaneously, allowing incremental conversion:

```python
async def run(self):
    if inspect.isgenerator(callback):
        next(callback)  # Old style
    elif inspect.iscoroutine(callback):
        await callback  # New style
```

---

## Phase 1: Infrastructure Foundation (PRs 1-3)

### Goal
Establish dual-mode ASYNC framework that supports both generators and async/await

### PR #1: Add Async/Await Infrastructure
**Files:** `src/exabgp/reactor/asynchronous.py`
**Generators:** 0 (infrastructure only)
**Estimated Time:** 2-3 hours
**Risk:** Medium

**Changes:**
1. Import `asyncio`, `inspect` modules
2. Add `_is_coroutine()` helper method
3. Modify `schedule()` to accept both generators and coroutines
4. Update `run()` to handle both types:
   ```python
   async def run(self):
       if inspect.isgenerator(callback):
           next(callback)
       elif inspect.iscoroutine(callback):
           await callback
   ```
5. Add backward compatibility flags

**Testing:**
- Verify existing generator-based code still works
- Add unit tests for coroutine scheduling
- Test mixed generator/coroutine workloads

**Acceptance Criteria:**
- [ ] All existing tests pass
- [ ] Can schedule and run both generators and coroutines
- [ ] No performance regression

---

### PR #2: Update Main Event Loop for Asyncio
**Files:** `src/exabgp/reactor/loop.py`
**Generators:** 1 (`_wait_for_io()`)
**Estimated Time:** 2-3 hours
**Risk:** High

**Changes:**
1. Convert `run()` method to `async def run()`
2. Update `self.asynchronous.run()` to `await self.asynchronous.run()`
3. Integrate asyncio event loop with existing `select.poll()`:
   ```python
   async def run(self):
       loop = asyncio.get_event_loop()
       # Bridge select.poll() with asyncio
   ```
4. Keep `_wait_for_io()` as generator initially (convert in Phase 3)

**Testing:**
- Verify event loop still processes I/O correctly
- Test with multiple peers
- Benchmark performance

**Acceptance Criteria:**
- [ ] Event loop runs without errors
- [ ] All I/O operations function correctly
- [ ] Existing tests pass

---

### PR #3: Add Async Testing Utilities
**Files:** `tests/helpers/async_utils.py` (new file)
**Generators:** 0
**Estimated Time:** 1-2 hours
**Risk:** Low

**Changes:**
1. Create async test helpers:
   ```python
   async def run_async_test(coro):
       loop = asyncio.get_event_loop()
       return await loop.run_until_complete(coro)
   ```
2. Add mock async generators for testing
3. Create compatibility wrappers for existing test fixtures

**Testing:**
- Unit tests for helper functions
- Integration with pytest-asyncio

**Acceptance Criteria:**
- [ ] Async test utilities work correctly
- [ ] Can test both old and new code styles

---

## Phase 2: Critical Path Conversion (PRs 4-8)

### Goal
Convert the 5 most critical files that drive core BGP functionality

---

### PR #4: Convert API Command Handlers - Part 1 (Route Operations)
**Files:** `src/exabgp/reactor/api/command/announce.py`
**Generators:** 10 of 30 (route announce/withdraw only)
**Estimated Time:** 3-4 hours
**Risk:** High

**Changes:**
Convert these 10 generator functions to async def:
1. `announce_route()` → `async def announce_route()`
2. `withdraw_route()` → `async def withdraw_route()`
3. `announce_vpls()` → `async def announce_vpls()`
4. `withdraw_vpls()` → `async def withdraw_vpls()`
5. `announce_flow()` → `async def announce_flow()`
6. `withdraw_flow()` → `async def withdraw_flow()`
7. `announce_l2vpn()` → `async def announce_l2vpn()`
8. `withdraw_l2vpn()` → `async def withdraw_l2vpn()`
9. `announce_operational()` → `async def announce_operational()`
10. `withdraw_operational()` → `async def withdraw_operational()`

**Pattern Conversion:**
```python
# BEFORE
def announce_route(self, reactor, service, line, use_json):
    def callback():
        try:
            # work
            yield False
        except:
            yield True
    reactor.asynchronous.schedule(service, line, callback())

# AFTER
async def announce_route(self, reactor, service, line, use_json):
    try:
        # work
        await asyncio.sleep(0)  # Yield control
    except:
        pass
    # Schedule as coroutine
```

**Testing:**
- Test each converted command independently
- Verify API responses are identical
- Run functional tests for route operations

**Acceptance Criteria:**
- [ ] All 10 functions converted to async def
- [ ] API tests pass for converted commands
- [ ] Remaining 20 generators still work (backward compatibility)

---

### PR #5: Convert API Command Handlers - Part 2 (Attribute Operations)
**Files:** `src/exabgp/reactor/api/command/announce.py`
**Generators:** 10 of remaining 20
**Estimated Time:** 2-3 hours
**Risk:** Medium

**Changes:**
Convert attribute-related generators:
1. `announce_attributes()` → async
2. `withdraw_attributes()` → async
3. And 8 more attribute operations

**Testing:**
- Test attribute announcement/withdrawal
- Verify BGP UPDATE message generation

**Acceptance Criteria:**
- [ ] 20 of 30 functions now async
- [ ] Attribute operations work correctly

---

### PR #6: Convert API Command Handlers - Part 3 (Remaining)
**Files:** `src/exabgp/reactor/api/command/announce.py`
**Generators:** Final 10 of 30
**Estimated Time:** 2-3 hours
**Risk:** Medium

**Changes:**
Complete conversion of `announce.py`:
- All remaining command handlers converted to async def
- Remove compatibility shims
- Update all `reactor.asynchronous.schedule()` calls

**Testing:**
- Full API command test suite
- Integration tests with external processes

**Acceptance Criteria:**
- [ ] All 30 generators in announce.py converted
- [ ] 100% async/await in this file
- [ ] All API tests pass

---

### PR #7: Convert Protocol Handler
**Files:** `src/exabgp/reactor/protocol.py`
**Generators:** 14
**Estimated Time:** 3-4 hours
**Risk:** High

**Changes:**
Convert all 14 protocol generators to async:
1. `connect()` → `async def connect()`
2. `write()` → `async def write()`
3. `send()` → `async def send()`
4. `read_message()` → `async def read_message()`
5. `read_open()` → `async def read_open()`
6. And 9 more protocol methods

**Key Challenge:** Convert nested loops with yields:
```python
# BEFORE
def read_message(self):
    for length, msg_id, header, body, notify in self.connection.reader():
        yield message

# AFTER
async def read_message(self):
    async for length, msg_id, header, body, notify in self.connection.reader():
        return message
```

**Testing:**
- Test BGP OPEN, UPDATE, KEEPALIVE, NOTIFICATION messages
- Verify message parsing integrity
- Test connection establishment

**Acceptance Criteria:**
- [ ] All 14 generators converted
- [ ] BGP protocol operations work correctly
- [ ] No message parsing errors

---

### PR #8: Convert Peer State Machine
**Files:** `src/exabgp/reactor/peer.py`
**Generators:** 9
**Estimated Time:** 2-3 hours
**Risk:** High

**Changes:**
Convert peer lifecycle generators:
1. `changed_statistics()` → async
2. `_connect()` → async
3. `_send_open()` → async
4. `_read_open()` → async
5. `_send_ka()` → async
6. And 4 more state machine methods

**Testing:**
- Test full peer connection lifecycle
- Test keepalive handling
- Test error scenarios and reconnection

**Acceptance Criteria:**
- [ ] All 9 generators converted
- [ ] Peer state transitions work correctly
- [ ] Connection lifecycle tests pass

---

## Phase 3: Supporting Systems (PRs 9-18)

### Goal
Convert remaining high-priority reactor and API components

---

### PR #9: Convert Connection Handler
**Files:** `src/exabgp/reactor/network/connection.py`
**Generators:** 3
**Estimated Time:** 1-2 hours
**Risk:** Medium

**Changes:**
1. `reader()` → `async def reader()`
2. `writer()` → `async def writer()`
3. `_reader()` → `async def _reader()`

**Testing:**
- Test TCP read/write operations
- Test socket error handling

---

### PR #10: Convert RIB Outgoing
**Files:** `src/exabgp/rib/outgoing.py`
**Generators:** 2
**Estimated Time:** 1-2 hours
**Risk:** Low

**Changes:**
1. `updates()` → async generator with `async def` and `yield`
2. Helper generator → async

**Note:** May keep as regular generator if not in async path

---

### PR #11: Convert API RIB Commands
**Files:** `src/exabgp/reactor/api/command/rib.py`
**Generators:** 6
**Estimated Time:** 1-2 hours
**Risk:** Low

---

### PR #12: Convert API Neighbor Commands
**Files:** `src/exabgp/reactor/api/command/neighbor.py`
**Generators:** 5
**Estimated Time:** 1-2 hours
**Risk:** Low

---

### PR #13: Convert API Watchdog Commands
**Files:** `src/exabgp/reactor/api/command/watchdog.py`
**Generators:** 4
**Estimated Time:** 1 hour
**Risk:** Low

---

### PR #14: Convert Keepalive Handler
**Files:** `src/exabgp/reactor/keepalive.py`
**Generators:** 3
**Estimated Time:** 1 hour
**Risk:** Low

---

### PR #15: Convert TCP Network Handlers
**Files:** `src/exabgp/reactor/network/tcp.py`
**Generators:** 6
**Estimated Time:** 1-2 hours
**Risk:** Medium

---

### PR #16: Convert Outgoing Connections
**Files:** `src/exabgp/reactor/network/outgoing.py`
**Generators:** 4
**Estimated Time:** 1 hour
**Risk:** Low

---

### PR #17: Convert Incoming Connections
**Files:** `src/exabgp/reactor/network/incoming.py`
**Generators:** 4
**Estimated Time:** 1 hour
**Risk:** Low

---

### PR #18: Convert Listener
**Files:** `src/exabgp/reactor/listener.py`
**Generators:** 1
**Estimated Time:** 1 hour
**Risk:** Low

---

## Phase 4: BGP Message Parsing (PRs 19-23)

### Goal
Convert binary protocol parsing generators

---

### PR #19: Convert UPDATE Message Parser
**Files:** `src/exabgp/bgp/message/update/__init__.py`
**Generators:** 4
**Estimated Time:** 1-2 hours
**Risk:** Medium

---

### PR #20: Convert Attributes Parser
**Files:** `src/exabgp/bgp/message/update/attribute/attributes.py`
**Generators:** 4
**Estimated Time:** 1-2 hours
**Risk:** Medium

---

### PR #21: Convert MP_REACH_NLRI Parser
**Files:** `src/exabgp/bgp/message/update/attribute/mprnlri.py`
**Generators:** 3
**Estimated Time:** 1 hour
**Risk:** Low

---

### PR #22: Convert MP_UNREACH_NLRI Parser
**Files:** `src/exabgp/bgp/message/update/attribute/mpurnlri.py`
**Generators:** 3
**Estimated Time:** 1 hour
**Risk:** Low

---

### PR #23: Convert AIGP Parser
**Files:** `src/exabgp/bgp/message/update/attribute/aigp.py`
**Generators:** 2
**Estimated Time:** 1 hour
**Risk:** Low

---

## Phase 5: Configuration & Utilities (PRs 24-28)

### Goal
Convert remaining parsers and utilities (optional - can defer)

---

### PR #24: Convert Flow Parser
**Files:** `src/exabgp/configuration/flow/parser.py`
**Generators:** 16
**Estimated Time:** 2-3 hours
**Risk:** Low
**Priority:** Optional

**Note:** This parser is used during configuration loading, not in hot path. Could remain as generators.

---

### PR #25: Convert Tokenizer
**Files:** `src/exabgp/configuration/core/tokeniser.py`
**Generators:** 6
**Estimated Time:** 1-2 hours
**Risk:** Low
**Priority:** Optional

---

### PR #26: Convert CLI Completer
**Files:** `src/exabgp/cli/completer.py`
**Generators:** 9
**Estimated Time:** 1-2 hours
**Risk:** Low
**Priority:** Optional

---

### PR #27: Convert Netlink Parsers
**Files:** `src/exabgp/netlink/old.py`, `netlink/message.py`, `netlink/netlink.py`, `netlink/attributes.py`
**Generators:** 15
**Estimated Time:** 2-3 hours
**Risk:** Low
**Priority:** Optional (Linux-specific)

---

### PR #28: Convert Remaining Utilities
**Files:** Multiple utility files
**Generators:** ~10
**Estimated Time:** 2-3 hours
**Risk:** Low
**Priority:** Optional

---

## Testing Strategy

### Test File Stability Requirement

**CRITICAL:** The following test files use generators and must NOT be modified during migration:

1. `tests/unit/test_connection_advanced.py` (22 generators)
2. `tests/fuzz/test_connection_reader.py` (2 generators)
3. `tests/unit/test_route_refresh.py` (1 generator)

These files serve as stable test fixtures to validate that our async conversions maintain backward compatibility.

### Testing Approach Per PR

Each PR must pass:

1. **Unit Tests**
   ```bash
   PYTHONPATH=src python -m pytest tests/unit/ -v
   ```

2. **Fuzz Tests**
   ```bash
   PYTHONPATH=src python -m pytest tests/fuzz/ -v
   ```

3. **Integration Tests**
   ```bash
   ./qa/bin/functional encoding --list
   ./qa/bin/functional encoding A
   ```

4. **Coverage Check**
   ```bash
   PYTHONPATH=src python -m pytest tests/ --cov=src/exabgp --cov-report=term-missing
   ```

5. **Regression Tests**
   - Compare behavior before/after conversion
   - Verify API responses identical
   - Check BGP message wire format unchanged

### Continuous Integration

All PRs must pass CI checks:
- pytest (all tests)
- pre-commit hooks
- Code coverage >= baseline
- No performance regressions

---

## Dependency Graph

```
PR #1 (Async Infrastructure)
  │
  ├──> PR #2 (Event Loop)
  │      │
  │      └──> PR #3 (Test Utilities)
  │             │
  │             ├──> Phase 2 (PRs 4-8) - Critical Path
  │             │      ├──> PR #4 (Announce Part 1)
  │             │      ├──> PR #5 (Announce Part 2)
  │             │      ├──> PR #6 (Announce Part 3)
  │             │      ├──> PR #7 (Protocol)
  │             │      └──> PR #8 (Peer)
  │             │
  │             ├──> Phase 3 (PRs 9-18) - Supporting
  │             │      └──> Can work in parallel after Phase 2
  │             │
  │             ├──> Phase 4 (PRs 19-23) - Parsing
  │             │      └──> Can work in parallel with Phase 3
  │             │
  │             └──> Phase 5 (PRs 24-28) - Optional
  │                    └──> Can be deferred
```

### Critical Path

Must be completed in order:
1. PR #1 → PR #2 → PR #3 (Infrastructure)
2. PR #4 → PR #5 → PR #6 (API Handlers)
3. PR #7 (Protocol)
4. PR #8 (Peer)

After critical path, PRs can be parallelized or done in any order.

---

## Progress Tracking

### Phase Completion Checklist

#### Phase 1: Infrastructure
- [ ] PR #1: Async Infrastructure merged
- [ ] PR #2: Event Loop merged
- [ ] PR #3: Test Utilities merged

#### Phase 2: Critical Path
- [ ] PR #4: Announce Part 1 merged
- [ ] PR #5: Announce Part 2 merged
- [ ] PR #6: Announce Part 3 merged
- [ ] PR #7: Protocol merged
- [ ] PR #8: Peer merged

#### Phase 3: Supporting Systems
- [ ] PR #9-18: All supporting PRs merged

#### Phase 4: BGP Parsing
- [ ] PR #19-23: All parser PRs merged

#### Phase 5: Utilities (Optional)
- [ ] PR #24-28: Utility PRs merged (if doing)

### Metrics Dashboard

Track after each PR:
- Total generators remaining: 150 → 0
- Test pass rate: 100%
- Code coverage: baseline → target
- Performance: baseline → target
- PRs completed: 0 → 28

---

## Risk Mitigation

### High-Risk PRs

1. **PR #2 (Event Loop)** - Core infrastructure change
   - Mitigation: Extensive testing, feature flag for rollback

2. **PR #4-6 (Announce)** - Heavy API usage
   - Mitigation: Split into 3 PRs, incremental testing

3. **PR #7 (Protocol)** - Critical BGP I/O
   - Mitigation: Comprehensive BGP message tests, wire format validation

4. **PR #8 (Peer)** - State machine complexity
   - Mitigation: State transition tests, error scenario coverage

### Rollback Plan

Each PR includes:
- Feature flag to enable/disable async mode
- Backward compatibility layer
- Revert commit prepared
- Database/state migration (if applicable)

### Session Handoff Protocol

If work spans multiple sessions, document:
1. Last completed PR number
2. Current PR in progress
3. Any blockers or issues
4. Next steps

Example handoff note:
```
HANDOFF SESSION X → SESSION Y
- Completed: PR #1-5 merged
- In Progress: PR #6 (50% complete, 5 of 10 functions converted)
- Blockers: None
- Next: Complete PR #6, then start PR #7
- Notes: Test coverage at 87%, target 90%
```

---

## Timeline Estimates

### Minimum (Aggressive)
- Phase 1: 5-7 hours
- Phase 2: 12-15 hours
- Phase 3: 10-12 hours
- Phase 4: 5-7 hours
- Phase 5: 8-10 hours (optional)
- **Total: 40-51 hours**

### Maximum (Conservative)
- Phase 1: 7-10 hours
- Phase 2: 18-22 hours
- Phase 3: 15-18 hours
- Phase 4: 8-10 hours
- Phase 5: 12-15 hours (optional)
- **Total: 60-75 hours**

### Per-Session Estimates
Assuming 2-4 hour sessions:
- **Minimum:** 10-20 sessions
- **Maximum:** 15-30 sessions

---

## Success Criteria

### Phase 1 Complete
- [ ] ASYNC class supports both generators and coroutines
- [ ] Event loop integrated with asyncio
- [ ] All existing tests pass
- [ ] Test utilities for async code available

### Phase 2 Complete
- [ ] All critical path generators converted (58 functions)
- [ ] API commands fully async
- [ ] BGP protocol handler fully async
- [ ] Peer state machine fully async
- [ ] Core functionality stable

### Phase 3 Complete
- [ ] All reactor components async
- [ ] All API commands async
- [ ] Network layer fully async
- [ ] 90%+ of async path converted

### Phase 4 Complete
- [ ] BGP message parsing async (or confirmed non-async is fine)
- [ ] Protocol compliance maintained

### Phase 5 Complete (Optional)
- [ ] 100% generator elimination
- [ ] All parsers async or refactored

### Final Success
- [ ] All 150 generator functions converted or deprecated
- [ ] 100% test pass rate maintained throughout
- [ ] No performance regression (< 5% acceptable)
- [ ] Code coverage >= 85%
- [ ] Zero backward-incompatible changes to external API
- [ ] Documentation updated
- [ ] Migration guide published

---

## Appendix A: File Reference

### Critical Files (Must Convert)
```
src/exabgp/reactor/api/command/announce.py      - 30 generators [HIGHEST PRIORITY]
src/exabgp/reactor/protocol.py                  - 14 generators
src/exabgp/reactor/peer.py                      - 9 generators
src/exabgp/reactor/network/connection.py        - 3 generators
src/exabgp/rib/outgoing.py                      - 2 generators
```

### Infrastructure Files
```
src/exabgp/reactor/asynchronous.py              - ASYNC class (0 generators, but critical)
src/exabgp/reactor/loop.py                      - Main event loop (1 generator)
```

### Test Files (DO NOT MODIFY)
```
tests/unit/test_connection_advanced.py          - 22 generators [KEEP STABLE]
tests/fuzz/test_connection_reader.py            - 2 generators [KEEP STABLE]
tests/unit/test_route_refresh.py                - 1 generator [KEEP STABLE]
```

---

## Appendix B: Common Conversion Patterns

### Pattern 1: Simple Generator to Async
```python
# BEFORE
def my_function():
    result = do_work()
    yield result

# AFTER
async def my_function():
    result = do_work()
    return result
```

### Pattern 2: Generator with Multiple Yields
```python
# BEFORE
def my_function():
    yield step1()
    yield step2()
    yield step3()

# AFTER
async def my_function():
    await async_step1()
    await async_step2()
    await async_step3()
```

### Pattern 3: Nested Generator (API Pattern)
```python
# BEFORE
def command_handler(reactor, service, line):
    def callback():
        try:
            work()
            yield False  # Continue
        except:
            yield True   # Stop
    reactor.asynchronous.schedule(service, line, callback())

# AFTER
async def command_handler(reactor, service, line):
    try:
        await work_async()
    except:
        pass
```

### Pattern 4: Generator Expression (Keep or Convert)
```python
# BEFORE
items = (x for x in collection if condition)

# AFTER (Option 1: Keep as-is)
items = (x for x in collection if condition)

# AFTER (Option 2: List comprehension)
items = [x for x in collection if condition]

# AFTER (Option 3: Async generator - if needed)
async def items():
    for x in collection:
        if condition:
            yield x
```

### Pattern 5: For Loop with Yields
```python
# BEFORE
def reader(self):
    for chunk in self.connection.read():
        parsed = parse(chunk)
        yield parsed

# AFTER
async def reader(self):
    async for chunk in self.connection.read():
        parsed = parse(chunk)
        yield parsed  # Keep as async generator
```

---

## Appendix C: Questions & Answers

### Q: Why 28 PRs? Isn't that too many?
A: Each PR represents a cohesive unit of work that can be independently tested and validated. This aligns with your requirement for progressive implementation and stability.

### Q: Can we combine some PRs?
A: Yes, particularly in Phase 3-5. The split is conservative. You could combine:
- PRs 9-18 into 2-3 larger PRs
- PRs 19-23 into 1-2 PRs
- PRs 24-28 into 1 PR

### Q: What if a PR breaks tests?
A: Each PR has a rollback plan and backward compatibility layer. The ASYNC class supports both modes simultaneously during transition.

### Q: Can we skip Phase 5?
A: Yes! Phase 5 is marked optional. The generators in config parsing, CLI, and utilities don't need to be async if they're not in the critical path.

### Q: How do we handle generator expressions?
A: Most can remain as-is. Only convert to async generators if they're in an async iteration context.

### Q: What about the test files with generators?
A: **DO NOT MODIFY THEM.** They remain stable to validate our changes. We create new async test utilities instead.

---

## Appendix D: Session Checkpoint Template

Use this template for session handoffs:

```markdown
## SESSION CHECKPOINT: [Date]

### Completed Work
- PRs Merged: #1, #2, #3
- PRs In Review: #4
- PRs In Progress: None

### Current State
- Generators Converted: 15/150 (10%)
- Test Pass Rate: 100%
- Code Coverage: 85%
- Blockers: None

### Next Steps
1. Complete PR #4 review comments
2. Start PR #5 (Announce Part 2)
3. Begin drafting PR #6

### Notes
- Performance testing shows no regression
- All critical path tests passing
- Documentation needs update after PR #4 merges

### Questions for Next Session
- Should we combine PRs 9-10?
- Consider adding more async test coverage?
```

---

## Appendix E: Git Workflow

### Branch Strategy
- Main development branch: `claude/convert-generators-to-async-011CUwFUB42rVxbv6Uf6XFQw`
- PR branches: `async-pr-01-infrastructure`, `async-pr-02-event-loop`, etc.

### Commit Message Format
```
[async-migration] PR #X: Brief description

- Detailed change 1
- Detailed change 2
- Detailed change 3

Testing: Describe testing performed
Risk: Low/Medium/High
Generators converted: N
```

### PR Description Template
```markdown
## PR #X: [Title]

### Summary
Brief description of changes.

### Generators Converted
- `file.py:function_name()` → `async def function_name()`
- [List all converted functions]

### Testing
- [ ] Unit tests pass
- [ ] Fuzz tests pass
- [ ] Integration tests pass
- [ ] Coverage >= baseline

### Risk Assessment
[Low/Medium/High] - Justification

### Dependencies
Requires: PR #Y
Blocks: PR #Z

### Rollback Plan
[How to rollback if needed]
```

---

**END OF MIGRATION PLAN**
