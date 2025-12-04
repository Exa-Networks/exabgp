# ExaBGP Quality Improvement TODO

**Updated:** 2025-12-04

---

## Active Projects

### 1. Type Safety (Phase 3 - Near Completion)

**Started:** 2025-11-13
**MyPy errors:** 89 (92% reduction from 1,149 baseline)

| Phase | Status | Details |
|-------|--------|---------|
| Phase 1: Replace Any types | ✅ Complete | 169 instances fixed, 64 kept intentionally |
| Phase 2: Baseline assessment | ✅ Complete | 1,149 errors identified |
| Phase 3: Systematic fixes | 🔄 92% done | 1,060 errors eliminated |
| Phase 4: Architectural refactoring | ❌ Pending | For remaining complex cases |

**Progress Timeline:**

| Date | Errors | Reduction |
|------|--------|-----------|
| 2025-11-15 | 1,149 | baseline |
| 2025-11-16 | 605 | 47% |
| 2025-12-04 | 89 | 92% |

**Remaining work:**
- [ ] Fix remaining 89 mypy errors (mostly `cli/completer.py`)
- [ ] Investigate test_route_refresh failures (58 tests)
- [ ] Reduce type:ignore baseline

**Reference:** `plan/type-annotations/` for detailed plans

---

### 2. Packed-Bytes-First Refactoring

**See:** `plan/packed-attribute.md` for full status

| Wave | Status |
|------|--------|
| Wave 1-3: Attributes | ✅ Complete |
| Wave 4: MP/BGP-LS/SR | ❌ Not started |
| Wave 5: Qualifiers | ✅ Complete |
| Wave 6: NLRI Types | 🔄 In progress (Flow pending) |
| Wave 7: EVPN/MUP/MVPN | ✅ Complete |
| Wave 8: Messages | ❌ Not started |

---

### 3. Test Coverage

**Current:** 59.71% (up from 46%)
**See:** `plan/coverage.md` for full audit

| Area | Coverage | Target |
|------|----------|--------|
| Configuration | 76.2% | ✅ |
| BGP Message | 84.0% | ✅ |
| Reactor | 41.3% | 55% |
| Application | 32.2% | 50% |
| CLI | 39.3% | 55% |

---

## Future Projects

### 4. Python 3.12+ Migration with Buffer Protocol

**Status:** Planning (not started)
**See:** `plan/python312-buffer-protocol.md` for full plan

**Goal:** Migrate to Python 3.12+ minimum and use `memoryview` for zero-copy BGP message parsing.

**Benefits:**
- 50-70% memory reduction for large UPDATE messages
- Zero-copy parsing (no intermediate allocations)
- Access to Python 3.12+ features (type parameter syntax, better f-strings)

**Scope:** ~55 files

| Phase | Files | Description |
|-------|-------|-------------|
| 1 | 1 | Raise Python version (pyproject.toml) |
| 2 | 1 | Network layer (`recv_into()`, return `memoryview`) |
| 3 | 2 | Protocol dispatch (pass `memoryview` to unpack) |
| 4 | 1 | UPDATE splitting (`split()` with memoryview) |
| 5 | ~25 | Attribute parsing (all attribute files) |
| 6 | ~25 | NLRI unpacking (all nlri files) |

**Prerequisite:** Complete packed-bytes-first refactoring (provides foundation)

---

## Remaining Work

### Security

- [x] BGP-LS data validation - malformed TLV crash prevention ✅
- [ ] Runtime crash analysis audit - systematic review of all parsing code for missing length/bounds checks
  - **See:** `plan/runtime-validation/TODO.md`
- [ ] Add input validation layer in configuration parsers
- [ ] Sanitize error messages for external-facing APIs

### AddPath Support (Feature Enhancement)

*Feature requests - AddPath already works for inet, label, ipvpn.*

- [ ] `nlri/bgpls/nlri.py:107` - implement addpath support
- [ ] `nlri/flow.py:652` - implement addpath support
- [ ] `nlri/vpls.py:89` - implement addpath support
- [ ] `nlri/evpn/nlri.py:84` - implement addpath support
- [ ] `nlri/mvpn/nlri.py:76` - implement addpath support
- [ ] `nlri/mup/nlri.py:79` - implement addpath support
- [ ] `nlri/bgpls/srv6sid.py:129` - implement addpath support

### Architecture

- [ ] Eliminate circular dependencies:
  - [ ] `bgp/fsm.py` ↔ `reactor/peer.py`
  - [ ] `bgp/message/update/__init__.py` (deferred Response import)

### Code Quality (Low Priority)

- [ ] `bgp/message/update/__init__.py:109-111` - Calculate size progressively
- [ ] `bgp/message/update/__init__.py:288` - NEXTHOP validation
- [ ] `bgp/message/update/attribute/` - Various validation TODOs (6 locations)
- [ ] `data/check.py` - Improve ipv4/ipv6 validators
- [ ] `protocol/ip/__init__.py` - IP/Range/CIDR API improvements

### XXX Cleanup (Phases 4-5)

**See:** `plan/xxx-cleanup/TODO.md`

- [ ] Phase 4: API Design Issues (NextHop, VPLS, Attribute.CODE)
- [ ] Phase 5: Investigation Required (6 items)

---

## Completed

### Type Safety Phase 1-3 ✅
- 328+ issues fixed
- 31 type:ignore comments removed
- 4 modules locked with strict mypy (util, data, environment, logger)
- CI enforcement added
- `py.typed` marker added
- MyPy errors: 1,149 → 89 (92% reduction)

### Exception Handling ✅
- 31 of 53 `except Exception:` cases replaced with specific exceptions
- 22 appropriately kept for top-level handlers

### Large File Refactoring ✅
- `port.py`: 4,982 → 89 lines (extracted to JSON)
- `cli.py`: 2,595 → 1,940 lines (extracted Colors, PersistentSocketConnection)

### Security Audit ✅
- No dangerous eval/exec found in target files

### XXX/TODO Comments (Phases 1-3) ✅
- 6 functional issues fixed
- 8 duplicate capability detection TODOs resolved
- Performance optimizations benchmarked and implemented

### Test Coverage Improvements ✅
- Coverage: 46% → 59.71% (+13.71%)
- Tests: 1,882 → 2,540 (+658)
- `reactor/loop.py` - 41 tests added
- `reactor/protocol.py` - 57 tests exist
- `reactor/network/connection.py` - 80 tests exist

### BGP-LS Data Validation ✅
- 12 vulnerabilities fixed across 11 files
- Added length validation to prevent IndexError/struct.error/ValueError crashes
- Files: srv6endx, srv6lanendx, srv6sidstructure, srv6locator, srv6endpointbehavior, srcap, sradjlan, sradj, linkstate, isisarea, srprefix
- **See:** `plan/runtime-validation/bgpls.md`
