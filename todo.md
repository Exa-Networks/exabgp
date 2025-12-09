# ExaBGP TODO

**Updated:** 2025-12-09
**Plan files:** See `plan/` directory

---

## Quick Items

- [x] Convert FSM.STATE to use `enum.IntEnum` ✅
- [ ] Make async mode the default reactor
  - Current: Requires `exabgp_reactor_asyncio=true` flag
  - Target: Async by default, legacy mode opt-in
  - Status: AsyncIO Phase 2 complete (100% test parity)

---

## 🚨 Critical - Fixed

- [x] **Attribute Cache Size Limit** ✅ - Removed unused dead code, LRU already bounded
- [x] **Blocking Write Deadlock** ✅ - c7b2f94d
- [x] **Race Conditions** ✅ - Config reload (086b3ec1), RIB iterator/cache (48e4405c)
- [x] **Application Layer Tests** ✅ - c97702b9, 112 new tests
- [x] **Type Safety Issues** ✅ - 159db1cd, removed all `type: ignore`
- [x] **Logging dictConfig** ✅ - b389975b

---

## Active Projects

### 1. Memory Optimization

**Status:** 🔄 Active
**See:** `plan/rib-optimisation.md`, `plan/fix-resolve-self-deepcopy.md`

| Phase | Optimization                | Savings  | Complexity | Status |
|-------|-----------------------------|----------|------------|--------|
| 1     | Fix resolve_self() deepcopy | 60-80%   | Low        | 📋 Planning |
| 2     | NLRI interning pool         | 20-40%   | Medium     | 📋 Planning |
| 3     | Attribute interning         | 30-50%   | Medium     | 📋 Planning |
| 4     | NextHop interning           | 10-20%   | Low        | 📋 Planning |
| 5     | Reference-based RIB         | Variable | High       | 📋 Planning |

**Notes:**
- CIDR stores truncated bytes (IPv4 /24 = 4 bytes, IPv6 /64 = 9 bytes)
- No interning for common prefixes (/24, /32, /64, /128)
- Many routes share same next-hop IP - no current caching
- VPN deployments reuse same RDs repeatedly

---

### 2. Type Safety (92% Complete)

**Status:** 🔄 Active
**See:** `plan/type-safety/`

MyPy errors: 89 (92% reduction from 1,149 baseline)
**Remaining:** mostly `cli/completer.py`

---

### 3. Test Coverage

**Status:** 🔄 Active
**Current:** 59.71% (up from 46%)

| Area | Coverage | Target |
|------|----------|--------|
| Configuration | 76.2% | ✅ |
| BGP Message | 84.0% | ✅ |
| Reactor | 41.3% | 55% |
| Application | 32.2% | 50% |
| CLI | 39.3% | 55% |

---

### 4. Runtime Validation

**Status:** 🔄 Active
**See:** `plan/runtime-validation/`

- [x] Phase 1: BGP-LS data validation ✅
- [x] Phase 2A-C: Messages, Capabilities, Attributes ✅
- [ ] Phase 3: NLRI Types
- [ ] Phase 4: Protocol Layer

---

## ⚠️ High Priority

- [ ] **Refactor Giant Methods**
  - `reactor/peer.py:_main()` - 386 lines
  - `configuration/configuration.py:__init__()` - 222 lines
  - `reactor/loop.py:run()` - 213 lines

- [ ] **Add Class/API Documentation**
  - Current: 94.2% of classes lack docstrings
  - Target: 80% class docstring coverage

- [ ] **Per-IP Connection Limits** - DoS protection
  - File: `reactor/listener.py`

- [ ] **Fix Respawn Tracking Dict Leak** - Memory leak
  - File: `reactor/api/processes.py:282-302`

---

## 📋 Medium Priority

- [ ] Configuration System Tests (15% → 50% coverage)
- [ ] Coverage Reporting in CI (Codecov/Coveralls)
- [ ] RIB Size Limits
- [ ] Make Config Reload Async
- [ ] Optimize Peer Lookup (dict for exact matches)
- [ ] Pre-commit Hooks
- [ ] Dependabot
- [ ] Cache Compiled Regexes

---

## 🔧 Low Priority - Technical Debt

- [ ] Refactor NLRI Duplication (186+ lines)
- [ ] Consolidate Test Fixtures
- [ ] Clean Up Legacy Files (`netlink/old.py`, deprecated files)
- [ ] Performance Regression Testing (pytest-benchmark)
- [ ] Address TODO/FIXME Comments (48 comments)

---

## Future Projects

- **Security Validation** - Config parser input validation, error sanitization
- **AddPath Support** - Extend to BGP-LS, FlowSpec, VPLS, EVPN, MVPN, MUP
- **Architecture Cleanup** - `bgp/fsm.py` ↔ `reactor/peer.py` circular dependency

---

## Completed (2025)

### Packed-Bytes-First Pattern ✅
100% complete (~124 classes) - See `plan/packed-bytes/progress.md`

### Buffer/Wire Architecture ✅
- Wire vs Semantic containers (Update/UpdateCollection, Attributes/AttributeCollection)
- `__slots__` on NLRI/Route (68% per-object reduction)
- `deepcopy` eliminated in `del_from_rib()` (6.5x faster)

### Change → Route Refactoring ✅
- Renamed across 36 files
- `Neighbor.rib` made non-Optional

### Python 3.12+ Buffer Protocol ✅
- Zero-copy with `recv_into()`, `memoryview`, `Buffer` type

### Wire vs Semantic Separation ✅
- Phases 1-3 complete
- OpenContext removed
- NextHopSelf mutate-in-place

### Other ✅
- API Dispatch Refactoring
- Run Script Migration (31 scripts)
- XXX Comment Cleanup
- BGP-LS Data Validation
- Sentinel Watchdog Pattern
