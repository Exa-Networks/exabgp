# ExaBGP Quality Improvement TODO

**Updated:** 2025-12-04
**Naming convention:** See `plan/README.md`

---

## Active Projects

### 1. Type Safety (Phase 3 - Near Completion)

**Status:** 🔄 Active
**Started:** 2025-11-13
**See:** `plan/type-safety/`

MyPy errors: 89 (92% reduction from 1,149 baseline)

| Phase | Status | Details |
|-------|--------|---------|
| Phase 1: Replace Any types | ✅ Complete | 169 instances fixed, 64 kept intentionally |
| Phase 2: Baseline assessment | ✅ Complete | 1,149 errors identified |
| Phase 3: Systematic fixes | 🔄 92% done | 1,060 errors eliminated |
| Phase 4: Architectural refactoring | ❌ Pending | For remaining complex cases |

**Remaining work:**
- [ ] Fix remaining 89 mypy errors (mostly `cli/completer.py`)
- [ ] Investigate test_route_refresh failures (58 tests)
- [ ] Reduce type:ignore baseline

---

### 2. Packed-Bytes-First Refactoring

**Status:** 🔄 Active
**See:** `plan/packed-bytes/`

| Wave | Status |
|------|--------|
| Wave 1-3: Attributes | ✅ Complete |
| Wave 4: MP/BGP-LS/SR | ❌ Not started |
| Wave 5: Qualifiers | ✅ Complete |
| Wave 6: NLRI Types | 🔄 In progress (Flow pending) |
| Wave 7: EVPN/MUP/MVPN | ✅ Complete |
| Wave 8: Messages | ✅ Complete |

---

### 3. Test Coverage

**Status:** 🔄 Active
**Current:** 59.71% (up from 46%)
**See:** `plan/coverage.md`

| Area | Coverage | Target |
|------|----------|--------|
| Configuration | 76.2% | ✅ |
| BGP Message | 84.0% | ✅ |
| Reactor | 41.3% | 55% |
| Application | 32.2% | 50% |
| CLI | 39.3% | 55% |

---

## Future Projects

### 4. Python 3.12+ Migration

**Status:** 📋 Planning
**See:** `plan/python312-buffer.md`

Migrate to Python 3.12+ and use `memoryview` for zero-copy parsing.
**Prerequisite:** Complete packed-bytes refactoring.

---

## Remaining Work

### Security

**See:** `plan/runtime-validation/`, `plan/security-validation.md`

- [x] BGP-LS data validation ✅
- [ ] Runtime crash analysis audit
  - **See:** `plan/runtime-validation/TODO.md`
- [ ] Config parser input validation
  - **See:** `plan/security-validation.md`
- [ ] Error message sanitization
  - **See:** `plan/security-validation.md`

---

### AddPath Support (Feature Enhancement)

**Status:** 📋 Planning
**See:** `plan/addpath-nlri.md`

| NLRI Type | File | Complexity |
|-----------|------|------------|
| BGP-LS | `nlri/bgpls/nlri.py:107` | Medium |
| FlowSpec | `nlri/flow.py:652` | High |
| VPLS | `nlri/vpls.py:89` | Low |
| EVPN | `nlri/evpn/nlri.py:84` | Medium |
| MVPN | `nlri/mvpn/nlri.py:76` | Medium |
| MUP | `nlri/mup/nlri.py:79` | Low |
| SRv6 SID | `nlri/bgpls/srv6sid.py:129` | Low |

---

### Architecture

**Status:** 📋 Planning
**See:** `plan/architecture.md`

- [ ] `bgp/fsm.py` ↔ `reactor/peer.py` circular dependency
- [ ] `bgp/message/update/__init__.py` deferred Response import

---

### Code Quality (Low Priority)

**Status:** 📋 Planning
**See:** `plan/code-quality.md`, `plan/family-tuple.md`

- [ ] UPDATE size calculation (`update/__init__.py:109-111`)
- [ ] NEXTHOP validation (`update/__init__.py:288`)
- [ ] Attribute validation TODOs (6 locations)
- [ ] IP/CIDR validators (`data/check.py`)
- [ ] IP/Range/CIDR API (`protocol/ip/__init__.py`)
- [ ] FamilyTuple standardization (67 hints, 18 files)

---

### XXX Cleanup (Phases 4-5)

**See:** `plan/xxx-cleanup/`

- [ ] Phase 4: API Design Issues
- [ ] Phase 5: Investigation Required

---

## Plan Index

All plans in `plan/` directory:

| Plan | Status | Description |
|------|--------|-------------|
| `type-safety/` | 🔄 Active | Type annotations project |
| `packed-bytes/` | 🔄 Active | Packed-bytes-first refactoring |
| `coverage.md` | 🔄 Active | Test coverage improvement |
| `python312-buffer.md` | 📋 Planning | Python 3.12 migration |
| `runtime-validation/` | 🔄 Active | Parsing crash prevention |
| `security-validation.md` | 📋 Planning | Config/API validation |
| `addpath-nlri.md` | 📋 Planning | AddPath for more NLRI types |
| `architecture.md` | 📋 Planning | Circular dependency fixes |
| `code-quality.md` | 📋 Planning | Misc improvements |
| `family-tuple.md` | 📋 Planning | FamilyTuple type alias |
| `xxx-cleanup/` | 🔄 Active | XXX comment resolution |

---

## Completed

### Type Safety Phase 1-3 ✅
- 328+ issues fixed
- 31 type:ignore comments removed
- 4 modules locked with strict mypy
- MyPy errors: 1,149 → 89 (92% reduction)

### Exception Handling ✅
- 31 of 53 `except Exception:` replaced with specific exceptions

### Large File Refactoring ✅
- `port.py`: 4,982 → 89 lines
- `cli.py`: 2,595 → 1,940 lines

### Security Audit ✅
- No dangerous eval/exec found

### XXX/TODO Comments (Phases 1-3) ✅
- 6 functional issues fixed
- 8 duplicate capability detection TODOs resolved

### Test Coverage Improvements ✅
- Coverage: 46% → 59.71% (+13.71%)
- Tests: 1,882 → 2,540 (+658)

### BGP-LS Data Validation ✅
- 12 vulnerabilities fixed across 11 files
- **See:** `plan/runtime-validation/bgpls.md`
