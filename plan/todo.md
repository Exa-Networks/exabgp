# ExaBGP Quality Improvement TODO

**Updated:** 2025-12-08
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

### 4. Wire vs Semantic Separation (Phase 1 Complete)

**Status:** 🔄 Active (Phase 2 pending)
**See:** `plan/wire-semantic-separation.md`

Phase 1 complete - Update/UpdateCollection separation:
- Update stores `_negotiated`, has no `_parsed` caching
- Callers use `update.data` or `update.parse()`

Next: Phase 2 - Replace `Negotiated` with `OpenContext`:
- Add `local_as`, `peer_as` to OpenContext
- Update stores `_context: OpenContext` instead of `_negotiated`
- Change `pack_attribute(negotiated)` → `pack_attribute(context)`

---

### 5. Update Context Attachment

**Status:** 📋 Planning
**See:** `plan/update-context-attachment.md`

Global Update cache with SHA256 IDs, sender tracking, API commands.

---

## Future Projects

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

### Type Identification Review (Low Priority)

**Status:** 📋 Planning
**See:** `plan/type-identification-review.md`

Review codebase for hasattr() violations after `_labels_packed` → `_has_labels` bug discovery.

---

## Plan Index

| Plan | Status | Description |
|------|--------|-------------|
| `type-safety/` | 🔄 Active | Type annotations project |
| `coverage.md` | 🔄 Active | Test coverage improvement |
| `runtime-validation/` | 🔄 Active | Parsing crash prevention |
| `wire-semantic-separation.md` | 🔄 Active | Wire vs Semantic container separation |
| `update-context-attachment.md` | 📋 Planning | Global Update cache with IDs |
| `type-identification-review.md` | 📋 Planning | hasattr() → ClassVar review |
| `security-validation.md` | 📋 Planning | Config/API validation |
| `addpath-nlri.md` | 📋 Planning | AddPath for more NLRI types |
| `architecture.md` | 📋 Planning | Circular dependency fixes |
| `code-quality.md` | 📋 Planning | Misc improvements |
| `family-tuple.md` | 📋 Planning | FamilyTuple type alias |

---

## Completed (2025)

### Buffer/Wire Architecture Refactoring ✅ (2025-12-06)

Major refactoring to implement packed-bytes-first pattern across the codebase:

**Update/Attributes Wire Separation:**
- `Update` is now wire container (bytes-first), registered as UPDATE handler
- `UpdateCollection` is semantic container (NLRI lists + attributes)
- `Attributes` is wire container, `AttributeCollection` is semantic container
- Commits: `5c409647`, `26180d8b`, `5981faf1`, `97ab5e52`

**NLRI Buffer-Ready Architecture:**
- Class-level AFI/SAFI for single-family types (EVPN, VPLS, RTC, Label, IPVPN)
- `_packed` attribute in NLRI base class
- `NLRICollection` and `MPNLRICollection` wire containers with lazy parsing
- `_UNPARSED` sentinel for deferred parsing
- Commits: `e0ef3b95`, `89856617`, `4dac25e9`, `ca97b8dc`, `dff7a853`, `52b65211`, `b1b384d1`

**Memory Optimizations:**
- `__slots__` on NLRI and Route classes (68% per-object reduction)
- Eliminated `deepcopy` in `del_from_rib()` (6.5x faster withdrawals)
- Commit: `3808601e`

**Buffer Type Standardization:**
- All message/attribute/NLRI classes accept `Buffer` (PEP 688)
- Two-buffer pattern: message owns buffer, slices are zero-copy
- Removed unnecessary `bytes()` conversions
- Commits: `f111d137`, `45d1ef62`, `89fa615b`

**CIDR/INET Fix:**
- Fixed /32 IPv6 misclassification by requiring explicit AFI
- Commit: `c12dae82`

### Change Class Refactoring ✅ (2025-12-06)

**Renamed Change → Route** (commit `ab2bdb45`):
- Renamed `src/exabgp/rib/change.py` → `route.py`
- Renamed class `Change` → `Route` across 36 files
- Better semantics: represents a BGP route (NLRI + attributes), not a change operation

**RIB Performance Optimization** (phases from `eliminate-change-class.md`):
- Phase 1-3: `UpdateCollection` with announces/withdraws separation
- Phase 4: `del_from_rib()` without deepcopy - **6.5x faster withdrawals**
- Phase 5-6: Overloaded RIB/Cache signatures accept `(nlri, attrs)` directly
- Phase 7: Keep `Route` class for configuration parsing (clean abstraction)

**Neighbor.rib refactor** (commit `6deae33b`):
- Made `Neighbor.rib` non-Optional with enabled flag
- Removed 14 `rib is not None` checks across codebase
- `RIB.enable()` activates with proper settings, reuses cached RIB on reload

---

### Python 3.12+ Buffer Protocol ✅ (2025-12-06)

Full implementation of zero-copy buffer handling:

- **Phase 1:** Python 3.12 minimum (pyproject.toml)
- **Phase 2:** Network layer uses `recv_into()`, returns `memoryview`
- **Phase 2.5:** Two-buffer architecture in Message classes
- **Phase 3:** `UpdateCollection.split()` returns `tuple[memoryview, memoryview, memoryview]`
- **Phase 4:** All NLRI `unpack_nlri()` methods accept `Buffer`, use `memoryview` internally
- **Phase 5:** `AttributeCollection.unpack()` accepts `Buffer`
- **Phase 6:** NLRI stores `bytes` (Option A - convert at boundary)

**Memory optimizations:**
- `__slots__` on NLRI and Route classes (68% per-object reduction)
- Eliminated `deepcopy` in `del_from_rib()` (6.5x faster withdrawals)

---

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
- 12 parsing issues fixed across 11 files (proper exceptions on invalid data)

### INET/Label/IPVPN Packed-Bytes-First ✅ (2025-12-08)
- Converted INET/Label/IPVPN to `_packed` storage with `_has_addpath`/`_has_labels`/`_has_rd` flags
- All three classes immutable after creation, zero-copy `pack_nlri()`
- Fixed `_normalize_nlri_type()` bug, added 12 unit tests

### NLRI Immutability Refactoring ✅ (2025-12-07)
- Settings classes (VPLSSettings, INETSettings, FlowSettings) with `from_settings()` factories
- RouteBuilder/Static routes use deferred construction (no mutation)
- VPLS fully immutable: removed `make_empty()`, `assign()`, builder slots

### Collection Caching by OpenContext ✅ (2025-12-07)
- UpdateCollection caches wire format per OpenContext (is_ibgp, addpath, asn4, msg_size)
- `exabgp_cache_updates` env var to enable/disable

### Pack NLRI Optimization ✅ (2025-12-08)
- All `pack_nlri()` methods do zero-copy returns (inet, rtc, mup, bgpls)

### Sentinel Watchdog Pattern ✅ (2025-12-06)
- `Watchdog`/`NoWatchdog` sentinel replaces `None` returns

### NLRI Packed-Bytes-First Conversion ✅ (2025-12-08)
- Core: VPLS, RTC, INET, Label, IPVPN - all converted with zero-copy pack_nlri()
- EVPN: All 6 types converted
- MUP: All 4 types converted (ISD, DSD, T1ST, T2ST)
- BGP-LS: All 6 types converted (NODE, LINK, PREFIXv4, PREFIXv6, SRv6SID)
- Flow/MVPN not applicable (builder pattern / low priority)
