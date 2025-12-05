# ExaBGP Quality Improvement TODO

**Updated:** 2025-12-05
**Naming convention:** See `plan/README.md`

---

## Active Projects

### 1. Type Safety (Phase 3 - Near Completion)

**Status:** 🔄 Active
**See:** `plan/type-safety/`

MyPy errors: 89 (92% reduction from 1,149 baseline)

| Phase | Status | Details |
|-------|--------|---------|
| Phase 1: Replace Any types | ✅ Complete | 169 instances fixed |
| Phase 2: Baseline assessment | ✅ Complete | 1,149 errors identified |
| Phase 3: Systematic fixes | 🔄 92% done | 1,060 errors eliminated |
| Phase 4: Architectural refactoring | ❌ Pending | For remaining complex cases |

**Remaining:** 89 mypy errors (mostly `cli/completer.py`)

---

### 2. Test Coverage

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

### 3. Runtime Validation

**Status:** 🔄 Active
**See:** `plan/runtime-validation/`, `plan/runtime-validation-plan.md`

- [x] Phase 1: BGP-LS data validation ✅ (12 issues fixed)
- [ ] Phase 2A: BGP Messages (open, update, notification, refresh)
- [ ] Phase 2B: Capabilities
- [ ] Phase 2C: Attributes (aspath, communities, etc.)
- [ ] Phase 3: NLRI Types
- [ ] Phase 4: Protocol Layer

---

## Future Projects

### Python 3.12+ Migration

**Status:** 📋 Planning
**See:** `plan/python312-buffer.md`

Migrate to Python 3.12+ and use `memoryview` for zero-copy parsing.
**Prerequisite:** Complete packed-bytes refactoring.

---

### Security Validation

**Status:** 📋 Planning
**See:** `plan/security-validation.md`

- [ ] Config parser input validation
- [ ] Error message sanitization

---

### AddPath Support

**Status:** 📋 Planning
**See:** `plan/addpath-nlri.md`

Extend ADD-PATH to additional NLRI types (BGP-LS, FlowSpec, VPLS, EVPN, MVPN, MUP).

---

### Architecture Cleanup

**Status:** 📋 Planning
**See:** `plan/architecture.md`

- [ ] `bgp/fsm.py` ↔ `reactor/peer.py` circular dependency
- [ ] Deferred Response import cleanup

---

### Code Quality (Low Priority)

**Status:** 📋 Planning
**See:** `plan/code-quality.md`, `plan/family-tuple.md`

- [ ] FamilyTuple standardization (67 hints, 18 files)
- [ ] UPDATE size calculation
- [ ] NEXTHOP validation
- [ ] IP/CIDR validators

---

## Plan Index

| Plan | Status | Description |
|------|--------|-------------|
| `type-safety/` | 🔄 Active | Type annotations project |
| `packed-bytes/` | 🔄 Active | Packed-bytes-first refactoring |
| `coverage.md` | 🔄 Active | Test coverage improvement |
| `runtime-validation/` | 🔄 Active | Parsing crash prevention |
| `python312-buffer.md` | 📋 Planning | Python 3.12 migration |
| `security-validation.md` | 📋 Planning | Config/API validation |
| `addpath-nlri.md` | 📋 Planning | AddPath for more NLRI types |
| `architecture.md` | 📋 Planning | Circular dependency fixes |
| `code-quality.md` | 📋 Planning | Misc improvements |
| `family-tuple.md` | 📋 Planning | FamilyTuple type alias |

---

## Completed (2025)

### API Dispatch Refactoring ✅
- Tree-based dictionary dispatch for v6 API
- v4/v6 API format transformation
- Bracket selector syntax
- Clean format handlers (api_route, api_flow, etc.)
- 27/27 API tests passing

### Run Script Migration ✅
- 31 scripts migrated to exabgp_api library
- Centralized SIGPIPE/ACK handling

### XXX Comment Cleanup ✅
- All phases complete
- 6 functional issues fixed

### Type Safety Phase 1-3 ✅
- 328+ issues fixed, 31 type:ignore removed
- MyPy errors: 1,149 → 89 (92% reduction)

### Test Coverage Improvements ✅
- Coverage: 46% → 59.71% (+13.71%)
- Tests: 1,882 → 2,540 (+658)

### BGP-LS Data Validation ✅
- 12 vulnerabilities fixed across 11 files
