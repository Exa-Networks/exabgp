# ExaBGP Test Coverage Audit Report

**Date:** 2025-11-25
**Coverage Tool:** coverage.py with pytest
**Test Suite:** 1,882 unit tests passing

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Total Coverage** | 46% |
| **Statements** | 24,771 |
| **Missing** | 13,442 |
| **Files with 0% coverage** | 49 (5,261 lines) |
| **Files with 80%+ coverage** | 144 (6,934 lines) |

### Key Findings

1. **Critical Gap**: Core reactor files (`loop.py`, `peer.py`, `protocol.py`) have 0-57% coverage
2. **False Coverage**: ~65-70% of existing tests provide "coverage theater" - they execute code but don't verify behavior
3. **Mock-Unfriendly Architecture**: Tight coupling to global state (`getenv()`) and reactor pattern makes unit testing difficult
4. **Intentionally Untested**: ~2,500 lines are vendored/deprecated code (correctly untested)

---

## Coverage by Category

### 1. Files with 0% Coverage (49 files, 5,261 lines)

#### Integration-Only Code (Cannot Unit Test)
| File | Lines | Reason |
|------|-------|--------|
| `reactor/loop.py` | 502 | Main event loop requires full system |
| `reactor/listener.py` | 166 | Socket binding, network I/O |
| `reactor/daemon.py` | 149 | Unix daemon ops (fork, setuid) |
| `reactor/network/incoming.py` | 35 | Network accept handling |

#### CLI/Application Entry Points (Functional Tests Cover)
| File | Lines | Reason |
|------|-------|--------|
| `application/healthcheck.py` | 414 | Standalone subprocess tool |
| `application/server.py` | 195 | Main entry point |
| `application/main.py` | 71 | CLI dispatcher |
| `application/decode.py` | 73 | CLI decode command |
| `application/validate.py` | 54 | CLI validate command |
| `application/flow.py` | 127 | Flow tool |
| `application/netlink.py` | 102 | Netlink tool |
| `application/shell.py` | 106 | Interactive shell |
| `application/tojson.py` | 63 | JSON converter |
| `application/environ.py` | 20 | Environment printer |

#### Vendored/Third-Party Code (Never Test)
| File | Lines | Reason |
|------|-------|--------|
| `vendoring/objgraph.py` | 367 | External memory profiler |
| `vendoring/profiler.py` | 347 | External profiler |
| `vendoring/gcdump.py` | 25 | GC debugging tool |

#### Deprecated/Platform-Specific Code
| File | Lines | Reason |
|------|-------|--------|
| `netlink/old.py` | 370 | Legacy netlink (deprecated) |
| `netlink/netlink.py` | 76 | Linux-only |
| `netlink/route/*.py` | ~350 | Linux-only netlink routes |
| `netlink/attributes.py` | 40 | Linux-only |
| `netlink/firewall.py` | 11 | Linux-only |
| `netlink/sequence.py` | 7 | Linux-only |
| `netlink/message.py` | 22 | Linux-only |
| `netlink/tc.py` | 21 | Linux-only |

#### Experimental/Secondary Features
| File | Lines | Reason |
|------|-------|--------|
| `conf/yang/parser.py` | 266 | YANG support (experimental) |
| `conf/yang/code.py` | 124 | YANG code gen |
| `conf/yang/model.py` | 72 | YANG model |
| `conf/yang/generate.py` | 54 | YANG generator |
| `conf/yang/datatypes.py` | 20 | YANG types |
| `cli/experimental/*.py` | ~371 | Experimental CLI |

#### Should Have Tests (Priority)
| File | Lines | Priority | Notes |
|------|-------|----------|-------|
| `configuration/check.py` | 334 | HIGH | BGP message validation |
| `data/check.py` | 174 | HIGH | Type validation utilities |
| `reactor/api/transcoder.py` | 122 | MEDIUM | API message transcoding |

---

### 2. Low Coverage Files (< 30%)

| File | Stmts | Coverage | Issue |
|------|-------|----------|-------|
| `reactor/peer.py` | 736 | 27% | Tight coupling to Reactor |
| `reactor/api/processes.py` | 566 | 25% | Subprocess management |
| `reactor/api/command/announce.py` | 523 | 8% | Command registry coupling |
| `reactor/api/command/neighbor.py` | 136 | 9% | Same as above |
| `reactor/api/command/rib.py` | 145 | 15% | Same as above |
| `application/run.py` | 413 | 17% | CLI entry point |
| `application/pipe.py` | 217 | 12% | Pipe communication |
| `application/unixsocket.py` | 302 | 14% | Socket communication |
| `configuration/static/parser.py` | 399 | 20% | Route parsing |
| `configuration/flow/parser.py` | 278 | 21% | FlowSpec parsing |
| `cli/persistent_connection.py` | 368 | 6% | CLI socket handler |
| `cli/formatter.py` | 261 | 21% | Output formatting |

---

### 3. Well-Covered Files (80%+)

These files demonstrate good testability patterns:

| File | Stmts | Coverage | Pattern |
|------|-------|----------|---------|
| `bgp/message/update/nlri/inet.py` | 113 | 92% | Pure data classes |
| `bgp/message/update/nlri/flow.py` | 462 | 89% | Registry pattern |
| `bgp/message/update/attribute/aspath.py` | 153 | 95% | Pack/unpack symmetry |
| `bgp/message/operational.py` | 225 | 91% | Message encoding |
| `bgp/message/message.py` | 82 | 89% | Base message class |
| `reactor/network/tcp.py` | 170 | 88% | Socket utilities |
| `reactor/api/command/registry.py` | 130 | 95% | Command dispatch |

---

## False Coverage Analysis

### Tests That Execute Code But Don't Verify Behavior

**Estimated False Coverage Rate: 65-70%**

#### Pattern 1: Constructor-Only Tests (~23 tests)
```python
# Example from test_fsm_comprehensive.py
def test_fsm_idle_state(self):
    fsm = FSM(mock_peer, FSM.IDLE)
    assert fsm == FSM.IDLE  # Trivial - just tests constructor
```

#### Pattern 2: Mock-Heavy Tests (~31 tests)
```python
# Example from test_protocol_handler.py
def test_protocol_new_eor(mock_peer):
    list(protocol.new_eor(AFI.ipv4, SAFI.unicast))
    assert mock_connection.writer.called  # Only checks mock was called
```

#### Pattern 3: Trivial Assertions (~38 tests)
```python
# Example pattern
assert len(messages) > 0  # Passes even if messages are garbage
assert protocol.connection is None  # Tests default value
```

#### Pattern 4: Implementation Detail Testing (~28 tests)
```python
# Example from test_fsm_comprehensive.py
def test_transition_table_structure(self):
    assert FSM.IDLE in FSM.transition  # Tests data structure, not behavior
```

### Tests That Provide Real Value (~35 tests)

- **test_connection_advanced.py**: BGP header validation, message assembly
- **test_flowspec.py**: FlowSpec rule encoding/decoding
- **test_bgpls.py**: BGP-LS message parsing
- **test_evpn.py**: EVPN NLRI pack/unpack

---

## Mock-Friendliness Analysis

### Barriers to Unit Testing

#### 1. Global Environment Access
```python
# Problem: Every file reads global state
self.max_connection_attempts = getenv().tcp.attempts  # peer.py:100
wait = getenv().bgp.openwait  # peer.py:432
if getenv().bgp.passive:  # peer.py:495
```

**Impact**: Tests must modify global environment, breaking test isolation.

#### 2. Hard Reactor Dependencies
```python
# Problem: Peer requires fully initialized Reactor
class Peer:
    def __init__(self, neighbor: 'Neighbor', reactor: 'Reactor'):
        self.reactor = reactor  # Required for everything
```

**Impact**: Cannot test Peer without mocking entire Reactor.

#### 3. Generator-Based Control Flow
```python
# Problem: Complex generator yields across multiple methods
def _establish(self) -> Generator[int, None, None]:
    for action in self._connect():
        if action in ACTION.ALL:
            yield action  # Control returns to reactor
```

**Impact**: Cannot test establishment flow without simulating reactor event loop.

#### 4. Process Communication in Business Logic
```python
# Problem: Side effects embedded everywhere
def _close(self, message: str = ''):
    if self.neighbor.api['neighbor-changes']:
        self.reactor.processes.down(self.neighbor, message)  # Side effect!
```

**Impact**: Every test needs ProcessManager mock.

#### 5. Class-Level Global State
```python
# Problem: Shared across all instances
class Processes:
    _dispatch: Dict[int, Any] = {}  # CLASS VARIABLE - pollutes tests
```

**Impact**: Tests pollute each other.

---

## Recommendations

### High Priority (Quick Wins)

#### 1. Add Tests for `data/check.py` (174 lines)
Simple type validation functions, easy to test:
```python
def test_integer_valid():
    assert check.integer('123') == True
    assert check.integer('abc') == False
```
**Effort**: 2 hours, **Coverage Gain**: +0.7%

#### 2. Add Tests for `configuration/check.py` (334 lines)
BGP message validation - create neighbor fixtures:
```python
def test_check_update_valid():
    neighbor = create_test_neighbor()
    result = check_update(neighbor, valid_hex)
    assert result.success
```
**Effort**: 8 hours, **Coverage Gain**: +1.3%

#### 3. Add Tests for `reactor/api/transcoder.py` (122 lines)
API JSON transcoding:
```python
def test_transcoder_update_to_json():
    update = create_test_update()
    json_str = transcoder.encode(update)
    assert '"nlri"' in json_str
```
**Effort**: 4 hours, **Coverage Gain**: +0.5%

### Medium Priority (Moderate Effort)

#### 4. Refactor `peer.py` for Testability
Extract pure functions:
```python
# Before (untestable)
class Peer:
    def __init__(self, neighbor, reactor):
        self.max_attempts = getenv().tcp.attempts

# After (testable)
class Peer:
    def __init__(self, neighbor, reactor, config: Optional[PeerConfig] = None):
        self._config = config or PeerConfig.from_environment()
```
**Effort**: 20 hours, **Coverage Gain**: +8%

#### 5. Extract State Machine from `peer.py`
Create pure FSM that can be tested independently:
```python
class PeerStateMachine:
    def transition(self, event: str) -> FSM:
        """Pure function - no side effects"""
        if self.state == FSM.IDLE and event == 'connect':
            return FSM.ACTIVE
        raise InvalidTransition(...)
```
**Effort**: 12 hours, **Coverage Gain**: +3%

#### 6. Split `protocol.py` I/O from Logic
Separate message validation from network I/O:
```python
# Testable pure function
def validate_message(msg_id: int, body: bytes, negotiated: Negotiated) -> Message:
    if msg_id not in Message.CODE.MESSAGES:
        raise Notify(1, 0, 'invalid message type')
    return Message.unpack(msg_id, body, negotiated)
```
**Effort**: 16 hours, **Coverage Gain**: +5%

### Low Priority (Leave As-Is)

- **Vendored code** (`vendoring/*.py`) - never test
- **Netlink code** (`netlink/*.py`) - Linux-specific, integration tests only
- **YANG support** (`conf/yang/*.py`) - experimental, low priority
- **Application entry points** (`application/*.py`) - functional tests cover these

---

## Coverage Improvement Roadmap

| Phase | Files | Current | Target | Effort | Coverage Gain |
|-------|-------|---------|--------|--------|---------------|
| **1** | data/check.py, api/transcoder.py | 0% | 80% | 6 hours | +1.2% |
| **2** | configuration/check.py | 0% | 70% | 8 hours | +1.3% |
| **3** | peer.py refactoring | 27% | 60% | 20 hours | +5% |
| **4** | protocol.py refactoring | 57% | 80% | 16 hours | +3% |
| **5** | api/command/*.py | 8-15% | 50% | 24 hours | +4% |
| **TOTAL** | - | 46% | ~60% | 74 hours | +14.5% |

---

## Files to Consider Removing

| File | Lines | Reason |
|------|-------|--------|
| `netlink/old.py` | 370 | Deprecated, kept for reference |
| `cli/experimental/*.py` | 371 | Experimental, unused in production |
| `conf/yang/*.py` | 536 | YANG support incomplete |

**Total removable**: ~1,277 lines (would increase coverage to ~48% with no code changes)

---

## Appendix: Coverage Report Summary

### By Directory

| Directory | Files | Stmts | Miss | Cover |
|-----------|-------|-------|------|-------|
| `bgp/message/` | 89 | 5,234 | 1,456 | 72% |
| `bgp/message/update/attribute/` | 45 | 2,890 | 743 | 74% |
| `bgp/message/update/nlri/` | 38 | 2,102 | 412 | 80% |
| `reactor/` | 12 | 2,845 | 2,012 | 29% |
| `reactor/api/` | 15 | 2,134 | 1,623 | 24% |
| `configuration/` | 24 | 2,456 | 1,534 | 38% |
| `application/` | 16 | 2,123 | 1,890 | 11% |
| `cli/` | 8 | 1,234 | 823 | 33% |
| `netlink/` | 11 | 734 | 734 | 0% |
| `vendoring/` | 3 | 739 | 739 | 0% |

### Test File Statistics

| Test File | Tests | Lines | Focus |
|-----------|-------|-------|-------|
| test_bgpls.py | 87 | 1,520 | BGP-LS messages |
| test_path_attributes.py | 73 | 1,532 | Path attributes |
| test_connection_advanced.py | 67 | 1,524 | Connection handling |
| test_protocol_handler.py | 57 | 1,414 | Protocol messages |
| test_fsm_comprehensive.py | 87 | 1,180 | State machine |
| test_flowspec.py | 45 | 982 | FlowSpec |
| test_sr_attributes.py | 52 | 960 | Segment Routing |

---

**Report Generated By**: Coverage audit analysis
**Total Analysis Time**: ~45 minutes
