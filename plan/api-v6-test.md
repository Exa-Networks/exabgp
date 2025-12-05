# Comprehensive v6 API Functional Test Plan

**Status:** 🔄 Active
**Last Updated:** 2025-12-05

## Goal

Create a comprehensive functional test for the v6 API that:
1. Tests ALL 43+ v6 API commands
2. Validates JSON responses against expected values
3. Includes error case testing
4. Ends with kill route for clean shutdown
5. Discovers bugs in the current API implementation

## Design Decisions

- **Location:** New `qa/api/` directory
- **Structure:** Single comprehensive test file
- **Validation:** JSON response only (no BGP wire format)
- **Error cases:** Yes, include comprehensive error testing

---

## Progress

| Task | Status |
|------|--------|
| Documentation: `.claude/exabgp/FUNCTIONAL_TEST_RUNNER.md` | ✅ |
| Update CRITICAL_FILES_REFERENCE.md | ✅ |
| Create `qa/api/` directory | ✅ |
| Create `etc/exabgp/api-v6-comprehensive.conf` | ✅ |
| Create `etc/exabgp/run/api-v6-comprehensive.run` | ✅ |
| Create `qa/api/api-v6-comprehensive.ci` | ✅ |
| Extend `qa/bin/functional` with api subcommand | ✅ |
| Run tests and fix bugs | 🔄 18/27 passing (66.7%) |

---

## Files to Create

### 1. `qa/api/README.md`
Documentation for API tests.

### 2. `qa/api/api-v6-comprehensive.ci`
Config reference file (single line pointing to conf).

### 3. `etc/exabgp/api-v6-comprehensive.conf`
ExaBGP configuration with process and neighbor.

### 4. `etc/exabgp/run/api-v6-comprehensive.run`
Main test script (~400 lines) that:
- Sends each v6 API command
- Parses JSON response
- Validates against expected structure
- Logs PASS/FAIL for each test
- Reports summary at end
- Sends kill route to trigger shutdown

---

## Test Execution Phases

### Phase 1: System Commands (no peer required)
```
system version        → {"version": "*", "application": "exabgp"}
system help           → {"description": "*", "commands": [...]}
system api version    → {"api_version": 6, ...}
system queue-status   → {<process>: {"items": N, "bytes": M}}
```

### Phase 2: Session Management (no peer required)
```
session ping          → {"pong": "<uuid>", "active": true}
session ack enable    → {"answer": "done"}
session ack disable   → {"answer": "done"} (then silence)
session ack enable    → {"answer": "done"} (re-enable)
session sync enable   → {"answer": "done"}
session sync disable  → {"answer": "done"}
session reset         → {"status": "asynchronous queue cleared"}
```

### Phase 3: Daemon Status
```
daemon status         → {"version": "*", "uuid": "*", "pid": N, ...}
```

### Phase 4: Peer Operations (peer established)
```
peer list             → [{peer-address, peer-as, state}, ...]
peer 127.0.0.1 show   → {neighbor info}
peer 127.0.0.1 show summary/extensive/configuration
```

### Phase 5: Route Announcements
```
peer 127.0.0.1 announce route 10.0.0.0/24 next-hop 1.2.3.4
peer 127.0.0.1 announce ipv4/ipv6/eor/route-refresh
# All should return {"answer": "done"}
```

### Phase 6: Route Withdrawals
```
peer 127.0.0.1 withdraw route 10.0.0.0/24
peer 127.0.0.1 withdraw ipv4/ipv6
# All should return {"answer": "done"}
```

### Phase 7: RIB Operations
```
rib show in/out       → (async output) + {"answer": "done"}
rib clear in/out      → {"answer": "done"}
rib flush out         → {"answer": "done"}
```

### Phase 8: Error Cases
```
invalid_command_xyz           → {"answer": "error", ...}
peer 999.999.999.999 show     → {"answer": "error", ...}
daemon invalid_action         → {"answer": "error", ...}
```

### Phase 9: Comment
```
# this is a comment   → (no output or {"answer": "done"})
```

### Phase 10: Cleanup
```
peer 127.0.0.1 announce route 255.255.255.255/32 next-hop 255.255.255.255
# Kill route signals test completion
```

---

## Response Validation

### Wildcard Matching
- `"*"` matches any value
- `{"key": "*"}` matches any value for key

### Partial Object Matching
- Expected `{"answer": "done"}` matches `{"answer": "done", "extra": "field"}`

### Error Response
- Expected `{"answer": "error"}` matches any error (don't check message)

---

## Critical Files

| File | Purpose |
|------|---------|
| `src/exabgp/reactor/api/dispatch.py` | All 43 v6 commands defined |
| `src/exabgp/reactor/api/command/reactor.py` | system/session/daemon handlers |
| `src/exabgp/reactor/api/command/neighbor.py` | peer show/list/teardown |
| `src/exabgp/reactor/api/command/announce.py` | announce/withdraw handlers |
| `src/exabgp/reactor/api/command/rib.py` | RIB operations |
| `qa/bin/functional` | Test runner to extend |
| `.claude/exabgp/FUNCTIONAL_TEST_RUNNER.md` | Test runner architecture |

---

## Bug Discovery Areas

1. **JSON response consistency** - Some handlers may not send proper JSON
2. **Answer termination** - Commands might not always send `{"answer": "done"}`
3. **v4 vs v6 format** - Transform logic may have edge cases
4. **Neighbor selector parsing** - Complex selectors may fail
5. **Error messages** - Invalid commands should return helpful errors

---

## Success Criteria

Test passes when:
1. All 43+ v6 commands tested
2. All JSON responses match expected patterns
3. Error cases return proper error responses
4. Test script exits with code 0
5. Output contains "SUCCESS: All tests passed"
6. Kill route triggers clean shutdown

---

## Recent Failures

**Test Run: 2025-12-05**
- Passed: 18/27 (66.7%)
- Failed: 9

### Bugs Found:

1. **`system queue-status` returns error** - `{'error': 'Invalid version: version'}`
   - Location: `src/exabgp/reactor/api/command/reactor.py`

2. **Invalid command returns done instead of error** - `invalid_command_xyz_12345` returns `{'answer': 'done'}`
   - Location: `src/exabgp/reactor/api/dispatch.py`

3. **Response ordering issue** - Commands receiving responses from previous commands due to async queue lag
   - Need to investigate async response handling

4. **`withdraw route` without explicit family fails** - `withdraw route 10.0.0.0/24` returns error
   - But `withdraw ipv4 unicast 10.0.1.0/24` works

5. **`announce route-refresh` returns error** - May need peer in ESTABLISHED state

### Test Script Issues:
- Response ordering needs better handling (drain previous responses)
- Some expected values need adjustment to match actual v6 API format

---

## Resume Point

**For next session:**

1. **Fix `system queue-status` error** - `{'error': 'Invalid version: version'}`
   - Check `src/exabgp/reactor/api/command/reactor.py`
   - The command seems to be misinterpreting "version" as a parameter

2. **Fix invalid command handling** - Should return error, not done
   - Check `src/exabgp/reactor/api/dispatch.py` - dispatch() function
   - Unknown commands should return `answer_error()`

3. **Fix `withdraw route` without family** - Should work like `announce route`
   - Check `src/exabgp/reactor/api/command/announce.py`

4. **Improve test script response handling**
   - Add response draining between commands
   - Adjust expected values to match actual v6 API format

**Run test:** `./qa/bin/functional api 0 -v`

---

**Related:** `.claude/exabgp/FUNCTIONAL_TEST_RUNNER.md`
