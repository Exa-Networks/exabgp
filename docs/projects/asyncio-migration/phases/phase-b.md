# Phase B: Full Async Architecture - DETAILED IMPLEMENTATION PLAN

**Date:** 2025-11-17
**Status:** PLANNING - Awaiting User Approval
**Estimated Effort:** 30-40 hours
**Risk Level:** HIGH

---

## MANDATORY REQUIREMENTS

**THIS PLAN MUST FOLLOW `.claude/MANDATORY_REFACTORING_PROTOCOL.md`**

Key requirements:
- ONE function at a time
- ALL tests MUST pass after EVERY step
- PASTE exact test output at every step
- NO batching of changes
- STOP immediately if ANY test fails

---

## Overview

Phase B converts the core event loop and FSM from generator-based to async/await architecture.

**Current Architecture:**
```
Reactor.run() → while loop → peer.run() → next(generator)
  ↓
peer.generator = peer._run() (Generator)
  ↓
_run() → _establish() → _main() (all Generators)
  ↓
Protocol methods (all Generators)
```

**Target Architecture:**
```
Reactor.run() → asyncio.run(main_async())
  ↓
main_async() → gather(peer.run_async() for all peers)
  ↓
peer.run_async() → _run_async() → _establish_async() → _main_async()
  ↓
Protocol async methods (Phase A complete)
```

---

## Phase B Strategy

Given the complexity and high risk, we'll use a **HYBRID COEXISTENCE** approach:

1. Add async versions alongside existing generator versions
2. Keep both implementations working
3. Add a feature flag to switch between them
4. Test extensively with async disabled (default)
5. Test extensively with async enabled
6. Only when 100% confident, make async the default
7. Eventually deprecate generators (future phase)

This allows for:
- Safe rollback at any point
- Gradual testing and validation
- Production can stay on generators while we develop
- Lower risk overall

---

## Step-by-Step Implementation Plan

### PHASE 0: PRE-WORK

#### Step 0: Commit Phase A Changes
```
Action: Commit the Phase A async methods (currently uncommitted)
Files: protocol.py, peer.py
Verification: git status
Expected: Clean working tree after commit
```

#### Step 1: Run Full Baseline Tests
```
Action: Run complete test suite to establish baseline
Files: N/A (testing only)
Verification:
  - ruff format src && ruff check src
  - env exabgp_log_enable=false pytest ./tests/unit/ -q
  - ./sbin/exabgp validate -nrv ./etc/exabgp/conf-ipself6.conf
  - ./qa/bin/functional encoding
Expected:
  - Linting: All checks passed
  - Unit tests: 1376 passed
  - Config validation: Passed
  - Functional: 72/72 (100%)
```

---

### PHASE 1: PROTOCOL LAYER COMPLETION (4 steps)

These methods already have async stubs in Phase A but need protocol support.

#### Step 2: Add Protocol.new_open_async() method
```
Action: Convert Protocol.new_open() to async version
Files: src/exabgp/reactor/protocol.py
Change: Add new_open_async() alongside new_open()
Pattern:
  - Replace "for _ in self.write():" with "await self.write_async()"
  - Replace "yield _NOP" with "continue" or remove
  - Replace "yield sent_open" with "return sent_open"
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 3: Add Protocol.read_open_async() method
```
Action: Convert Protocol.read_open() to async version
Files: src/exabgp/reactor/protocol.py
Change: Add read_open_async() alongside read_open()
Pattern:
  - Replace "for received_open in self.read_message():" with async iteration
  - Use "await self.read_message_async()"
  - Replace yield with direct return
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 4: Add Protocol.new_keepalive_async() method
```
Action: Convert Protocol.new_keepalive() to async version
Files: src/exabgp/reactor/protocol.py
Change: Add new_keepalive_async() alongside new_keepalive()
Pattern:
  - Replace "for _ in self.write():" with "await self.write_async()"
  - Replace yield with return
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 5: Add Protocol.read_keepalive_async() method
```
Action: Convert Protocol.read_keepalive() to async version
Files: src/exabgp/reactor/protocol.py
Change: Add read_keepalive_async() alongside read_keepalive()
Pattern:
  - Replace generator iteration with async/await
  - Use await self.read_message_async()
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

---

### PHASE 2: UPDATE PEER ASYNC STUBS (4 steps)

Now that protocol async methods exist, update the peer stubs to use them.

#### Step 6: Update Peer._send_open_async() to use proto.new_open_async()
```
Action: Replace stub implementation with real async call
Files: src/exabgp/reactor/peer.py
Change: Replace generator loop with "await self.proto.new_open_async()"
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 7: Update Peer._read_open_async() to use proto.read_open_async()
```
Action: Replace stub implementation with real async call
Files: src/exabgp/reactor/peer.py
Change: Replace generator loop with "await self.proto.read_open_async()"
Add async timeout handling for opentimer
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 8: Update Peer._send_ka_async() to use proto.new_keepalive_async()
```
Action: Replace stub implementation with real async call
Files: src/exabgp/reactor/peer.py
Change: Replace generator loop with "await self.proto.new_keepalive_async()"
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 9: Update Peer._read_ka_async() to use proto.read_keepalive_async()
```
Action: Replace stub implementation with real async call
Files: src/exabgp/reactor/peer.py
Change: Replace generator loop with "await self.proto.read_keepalive_async()"
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

---

### PHASE 3: PEER FSM ASYNC METHODS (3 steps)

Convert the three main FSM generator methods to async.

#### Step 10: Add Peer._establish_async() method
```
Action: Create async version of _establish()
Files: src/exabgp/reactor/peer.py
Change: Add _establish_async() alongside _establish()
Pattern:
  - Replace "for action in self._connect():" patterns with await or keep generator bridge
  - Replace "for sent_open in self._send_open():" with "sent_open = await self._send_open_async()"
  - Replace "for received_open in self._read_open():" with "received_open = await self._read_open_async()"
  - Replace "for action in self._send_ka():" with "await self._send_ka_async()"
  - Replace "for action in self._read_ka():" with "await self._read_ka_async()"
  - Replace "yield ACTION.NOW" with "return ACTION.NOW" or remove
  - Keep FSM state changes as-is
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 11: Add Peer._main_async() method
```
Action: Create async version of _main()
Files: src/exabgp/reactor/peer.py
Change: Add _main_async() alongside _main()
Pattern:
  - This is the most complex method (~200 lines)
  - Replace "for message in self.proto.read_message():" with async iteration
  - Use "await self.proto.read_message_async()"
  - Handle all the control flow with async patterns
  - Keep while loops but replace yield with await asyncio.sleep(0) where needed
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 12: Add Peer._run_async() method
```
Action: Create async version of _run()
Files: src/exabgp/reactor/peer.py
Change: Add _run_async() alongside _run()
Pattern:
  - Replace "for action in self._establish():" with "await self._establish_async()"
  - Replace "for action in self._main():" with "await self._main_async()"
  - Keep exception handling
  - Replace generator yields with returns or awaits
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

---

### PHASE 4: PEER ENTRY POINT (2 steps)

Add async entry point for peers.

#### Step 13: Add Peer.run_async() method
```
Action: Create async version of run()
Files: src/exabgp/reactor/peer.py
Change: Add run_async() alongside run()
Pattern:
  - Check for broken processes (same as sync)
  - Instead of generator management, call "return await self._run_async()"
  - Handle exceptions appropriately
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 14: Add Peer async initialization and task management
```
Action: Add async task lifecycle management
Files: src/exabgp/reactor/peer.py
Change: Add methods to manage async peer as asyncio Task
  - _async_task: Optional[asyncio.Task] = None
  - start_async() - creates asyncio.Task for run_async()
  - stop_async() - cancels the task
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

---

### PHASE 5: REACTOR ASYNC EVENT LOOP (4 steps)

Convert the main reactor loop to async.

#### Step 15: Add Reactor._run_async_peers() helper
```
Action: Create async method to run all peers concurrently
Files: src/exabgp/reactor/loop.py
Change: Add _run_async_peers() method
Pattern:
  - Use asyncio.gather() to run all peer tasks
  - Handle peer task completion/failure
  - Return control flow decisions
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 16: Add Reactor._async_main_loop() method
```
Action: Create async version of main event loop
Files: src/exabgp/reactor/loop.py
Change: Add _async_main_loop() alongside existing while loop in run()
Pattern:
  - Convert while True loop to async
  - Use "await self._wait_for_io_async()" instead of generator
  - Call peer.run_async() instead of peer.run()
  - Handle signals, reload, etc. with async patterns
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 17: Add Reactor.run_async() method
```
Action: Create async entry point for reactor
Files: src/exabgp/reactor/loop.py
Change: Add run_async() method
Pattern:
  - Perform same setup as run() (daemon, processes, listeners, etc.)
  - Instead of while loop, call "await self._async_main_loop()"
  - Handle cleanup
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 18: Add async mode feature flag and integration
```
Action: Add configuration flag to choose sync vs async mode
Files: src/exabgp/reactor/loop.py, src/exabgp/environment.py (if needed)
Change:
  - Add environment variable: exabgp.reactor.async (default: false)
  - Modify Reactor.run() to check flag
  - If async mode: asyncio.run(self.run_async())
  - If sync mode: existing generator-based loop
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

---

### PHASE 6: ADDITIONAL PROTOCOL METHODS (8 steps)

Convert remaining protocol methods that FSM uses.

#### Step 19: Add Protocol.new_notification_async()
```
Action: Create async version of new_notification()
Files: src/exabgp/reactor/protocol.py
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 20: Add Protocol.new_update_async()
```
Action: Create async version of new_update()
Files: src/exabgp/reactor/protocol.py
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 21: Add Protocol.new_eor_async()
```
Action: Create async version of new_eor()
Files: src/exabgp/reactor/protocol.py
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 22: Add Protocol.new_operational_async()
```
Action: Create async version of new_operational()
Files: src/exabgp/reactor/protocol.py
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 23: Add Protocol.new_refresh_async()
```
Action: Create async version of new_refresh()
Files: src/exabgp/reactor/protocol.py
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 24: Update _main_async() to use new_update_async()
```
Action: Replace generator calls in _main_async() with async versions
Files: src/exabgp/reactor/peer.py
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 25: Update _main_async() to use new_eor_async()
```
Action: Replace generator calls in _main_async() with async versions
Files: src/exabgp/reactor/peer.py
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 26: Update _main_async() to use new_operational_async() and new_refresh_async()
```
Action: Replace remaining generator calls in _main_async() with async versions
Files: src/exabgp/reactor/peer.py
Verification: env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

---

### PHASE 7: INTEGRATION TESTING (4 steps)

Test the async mode extensively.

#### Step 27: Run unit tests with async mode DISABLED (default)
```
Action: Verify sync mode still works perfectly
Files: N/A (testing only)
Verification:
  - export exabgp_reactor_async=false (or unset)
  - env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 28: Run functional tests with async mode DISABLED
```
Action: Verify sync mode functional tests pass
Files: N/A (testing only)
Verification: ./qa/bin/functional encoding
Expected: 72/72 (100%)
```

#### Step 29: Run unit tests with async mode ENABLED
```
Action: Test async implementation
Files: N/A (testing only)
Verification:
  - export exabgp_reactor_async=true
  - env exabgp_log_enable=false pytest ./tests/unit/ -q
Expected: 1376 passed, 0 failures
```

#### Step 30: Run functional tests with async mode ENABLED
```
Action: Test async implementation with real BGP
Files: N/A (testing only)
Verification:
  - export exabgp_reactor_async=true
  - ./qa/bin/functional encoding
Expected: 72/72 (100%)
```

---

### PHASE 8: FINAL PRE-COMMIT (1 step)

#### Step 31: Complete Pre-Commit Checklist
```
Action: Run full test suite in both modes before commit
Files: N/A (testing only)
Verification:
  1. Linting: ruff format src && ruff check src
  2. Sync mode unit: env exabgp_log_enable=false pytest ./tests/unit/ -q
  3. Sync mode functional: ./qa/bin/functional encoding
  4. Async mode unit: exabgp_reactor_async=true env exabgp_log_enable=false pytest ./tests/unit/ -q
  5. Async mode functional: exabgp_reactor_async=true ./qa/bin/functional encoding
Expected:
  - Linting: All checks passed
  - Sync unit: 1376 passed
  - Sync functional: 72/72 (100%)
  - Async unit: 1376 passed
  - Async functional: 72/72 (100%)
```

---

## Risk Mitigation

### High-Risk Areas

1. **_main_async() conversion** (Step 11)
   - Most complex method (~200 lines)
   - Multiple control flows
   - Many generator calls
   - **Mitigation**: Break into sub-steps if needed, test extensively

2. **Event loop integration** (Steps 15-18)
   - Core infrastructure change
   - Affects all peers
   - **Mitigation**: Feature flag allows fallback to sync

3. **Functional tests with async mode** (Step 30)
   - Real BGP protocol testing
   - 72 different scenarios
   - **Mitigation**: Test one at a time if failures occur

### Rollback Strategy

At any point if tests fail:
1. **STOP immediately**
2. Review the specific change
3. Debug and fix OR
4. Revert the last commit
5. Reassess approach

Feature flag allows production to stay on sync mode even after merge.

---

## Estimated Timeline

- Phase 0 (Pre-work): 1 hour
- Phase 1 (Protocol completion): 3-4 hours
- Phase 2 (Peer stubs): 2-3 hours
- Phase 3 (FSM methods): 8-10 hours (Step 11 is complex)
- Phase 4 (Peer entry): 2-3 hours
- Phase 5 (Reactor loop): 6-8 hours
- Phase 6 (Additional protocol): 4-5 hours
- Phase 7 (Integration testing): 2-3 hours
- Phase 8 (Pre-commit): 1 hour

**Total: 29-38 hours**

---

## Success Criteria

- [ ] All 31 steps completed
- [ ] Every step passed all tests
- [ ] Sync mode: 1376 unit + 72 functional (100%)
- [ ] Async mode: 1376 unit + 72 functional (100%)
- [ ] Linting clean
- [ ] No regressions
- [ ] Feature flag working
- [ ] Code reviewed and committed

---

## Alternative: Simplified Approach

If the full 31-step plan seems too ambitious, we could do a **MINIMAL Phase B**:

- Complete only Steps 2-9 (Protocol methods + Peer stubs)
- Skip the full event loop conversion
- Result: Async methods exist and work, but not integrated
- Effort: ~8-10 hours instead of 30-40
- Risk: LOW instead of HIGH

This would make Phase B similar in scope to Phase A.

---

## Questions for User

Before proceeding, please confirm:

1. **Scope**: Full 31-step plan OR simplified 9-step version?
2. **Timeline**: Do you have 30-40 hours available for full version?
3. **Risk tolerance**: Comfortable with HIGH risk on core event loop?
4. **Feature flag**: Want ability to switch between sync/async modes?
5. **Testing**: Will you test both modes thoroughly?

---

**Status:** Awaiting User Approval

**Recommendation:** Consider simplified approach first (Steps 2-9 only), then evaluate if full conversion is needed.
