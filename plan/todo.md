# ExaBGP Quality Improvement TODO

**Updated:** 2025-11-25

---

## Remaining Work

### Type Safety - Remaining

**436 mypy errors remaining** (down from 660)

- [ ] Continue fixing remaining type errors in high-impact modules
- [ ] Reduce type:ignore baseline (currently 370)

### Security

- [ ] Add input validation layer in configuration parsers
- [ ] Sanitize error messages for external-facing APIs

### AddPath Support (Feature Enhancement)

*These are feature requests, not bugs. AddPath already works for inet, label, ipvpn.*

- [ ] `nlri/bgpls/nlri.py:107` - implement addpath support
- [ ] `nlri/flow.py:652` - implement addpath support
- [ ] `nlri/vpls.py:89` - implement addpath support
- [ ] `nlri/evpn/nlri.py:84` - implement addpath support
- [ ] `nlri/mvpn/nlri.py:76` - implement addpath support
- [ ] `nlri/mup/nlri.py:79` - implement addpath support
- [ ] `nlri/bgpls/srv6sid.py:129` - implement addpath support

### Test Coverage

**See [coverage.md](coverage.md) for full audit report**

Current: 46% coverage (24,771 statements, 13,442 missing)

**Phase 1 - Quick Wins (6 hours, +1.2%)**
- [ ] Add tests for `data/check.py` (174 lines, 0% → 80%)
- [ ] Add tests for `reactor/api/transcoder.py` (122 lines, 0% → 80%)

**Phase 2 - Configuration (8 hours, +1.3%)**
- [ ] Add tests for `configuration/check.py` (334 lines, 0% → 70%)

**Phase 3 - Reactor Refactoring (20 hours, +5%)**
- [ ] Refactor `reactor/peer.py` for testability (27% → 60%)
- [ ] Extract pure FSM from peer.py

**Phase 4 - Protocol Refactoring (16 hours, +3%)**
- [ ] Split `reactor/protocol.py` I/O from logic (57% → 80%)

**Phase 5 - API Commands (24 hours, +4%)**
- [ ] Refactor `reactor/api/command/*.py` (8-15% → 50%)

**Other**
- [ ] Add configuration validation tests for malformed configs
- [ ] Add API response tests for `reactor/api/response/json.py`
- [ ] Add property-based tests using hypothesis

### Architecture

- [ ] Eliminate circular dependencies:
  - [ ] `bgp/fsm.py` ↔ `reactor/peer.py`
  - [ ] `bgp/message/update/__init__.py` (deferred Response import)

### Code Quality (Low Priority)

- [ ] `bgp/message/update/__init__.py:109-111` - Calculate size progressively (complex refactor)
- [ ] `bgp/message/update/__init__.py:288` - NEXTHOP validation
- [ ] `bgp/message/update/attribute/` - Various validation TODOs (6 locations)
- [ ] `data/check.py` - Improve ipv4/ipv6 validators
- [ ] `protocol/ip/__init__.py` - IP/Range/CIDR API improvements

---

## Completed

### Exception Handling ✅
- 31 of 53 `except Exception:` cases replaced with specific exceptions
- 22 appropriately kept for top-level handlers

### Large File Refactoring ✅
- `port.py`: 4,982 → 89 lines (extracted to JSON)
- `cli.py`: 2,595 → 1,940 lines (extracted Colors, PersistentSocketConnection)

### Type Safety Phase 1-3 ✅
- 328 issues fixed
- 31 type:ignore comments removed
- 4 modules locked with strict mypy (util, data, environment, logger)
- CI enforcement added
- `py.typed` marker added

### Security Audit ✅
- No dangerous eval/exec found in target files

### XXX/TODO Comments ✅
- 6 functional issues fixed
- 8 duplicate capability detection TODOs resolved

### Test Coverage ✅
- `reactor/loop.py` - 41 tests added
- `reactor/protocol.py` - 57 tests exist
- `reactor/network/connection.py` - 80 tests exist
