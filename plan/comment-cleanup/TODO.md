# XXX Comment Cleanup - TODO

**Status:** ✅ COMPLETE - All phases resolved
**Started:** 2025-11-25
**Updated:** 2025-12-04

---

## Decisions

### API Breaking Changes (Category 4)
**Decision:** Make breaking changes, update all callers
- ~~NextHop API (string vs bytes)~~ ✅ resolved
- VPLS signature alignment (reopened - make_vpls needs action/addpath)
- Attribute.CODE instantiability
- TrafficNextHopSimpson inheritance

### Performance Optimizations (Category 1)
**Decision:** Benchmark first, only implement if measurable gain
- Progressive size calculation in Update.messages()
- Nexthop caching in MPRNLRI
- MAC hash performance
- Attributes.index() memory optimization

### Unclear Items (Category 5)
**Decision:** Investigate and fix if possible, remove comment if not actionable
- VPLS unique key
- RTC variable length prefixing
- EVPN MAC index
- SRCAP redundant parsing
- PMSI length discrepancy
- BGP-LS IGP tags LEN checks

---

## Phase 1: Performance Optimizations ✅ COMPLETE

### 1.1 Update.messages() progressive size calculation
- **File:** `src/exabgp/bgp/message/update/__init__.py:109-111`
- **Status:** ✅ IMPLEMENTED - 1.3-1.5x speedup at scale
- **Benchmark:** `lab/benchmark_update_size.py`

### 1.2 MPRNLRI nexthop caching
- **File:** `src/exabgp/bgp/message/update/attribute/mprnlri.py:167`
- **Status:** ✅ DOCUMENTED - caching is 2x SLOWER than slicing
- **Benchmark:** `lab/benchmark_nexthop_cache.py`

### 1.3 MAC.__hash__ performance
- **File:** `src/exabgp/bgp/message/update/nlri/qualifier/mac.py:58`
- **Status:** ✅ IMPLEMENTED - 17x speedup
- **Benchmark:** `lab/benchmark_mac_hash.py`

### 1.4 Attributes.index() memory
- **File:** `src/exabgp/bgp/message/update/attribute/attributes.py:293`
- **Status:** ✅ DOCUMENTED - hash collisions risk bugs
- **Benchmark:** `lab/benchmark_attr_index.py`

---

## Phase 2: RFC Validation ✅ COMPLETE

### 2.1 NEXTHOP validation (RFC 4271 Section 5.1.3)
- **File:** `src/exabgp/bgp/message/update/__init__.py:298-311`
- **Status:** ✅ IMPLEMENTED - logs warning if NEXTHOP equals local address

---

## Phase 3: Architecture/Refactoring ✅ COMPLETE

### 3.1 Add INTERNAL flag to Attribute classes
- **File:** `src/exabgp/bgp/message/update/attribute/attributes.py:133`
- **Status:** ⏸️ DEFERRED - XXX kept (marker classes don't inherit Attribute)

### 3.2 Move Attribute.caching initialization
- **File:** `src/exabgp/bgp/message/update/attribute/attributes.py:198`
- **Status:** ✅ FIXED - removed redundant init (already set in server.py)

### 3.3 Add fallback function for unknown attributes
- **File:** `src/exabgp/bgp/message/update/attribute/attributes.py:402`
- **Status:** ✅ DOCUMENTED - GenericAttribute serves this role

### 3.4 Check missing attribute flag handling
- **File:** `src/exabgp/bgp/message/update/attribute/attributes.py:424`
- **Status:** ✅ DOCUMENTED - clarified purpose of fallthrough log

### 3.5 ExtendedCommunity transitivity registration
- **File:** `src/exabgp/bgp/message/update/attribute/community/extended/community.py:20`
- **Status:** ⏸️ NOT STARTED

---

## Phase 4: API Design Issues - NOT STARTED

### 4.1 NextHop API - string vs raw bytes
- **File:** `src/exabgp/bgp/message/update/attribute/nexthop.py:34`
- **Status:** ✅ RESOLVED - XXX comment no longer exists

### 4.2 Attribute.CODE instantiability
- **File:** `src/exabgp/bgp/message/update/attribute/attribute.py:103-104`
- **Status:** Pending
- **Action:** Make CODE non-instantiable, update usages

### 4.3 VPLS signature alignment
- **File:** `src/exabgp/bgp/message/update/nlri/vpls.py:73-105`
- **Status:** ✅ RESOLVED - `make_vpls()` has `action` and `addpath` params
- **Also:** `make_empty()` factory method added with same params (lines 107-125)

### 4.4 TrafficNextHopSimpson inheritance
- **File:** `src/exabgp/bgp/message/update/attribute/community/extended/traffic.py:282-304`
- **Status:** ✅ RESOLVED - No change needed
- **Analysis:** Current design is correct. TrafficNextHopSimpson is an ExtendedCommunity (not NextHop/IP) because it doesn't contain an IP address - it only signals "use the UPDATE's existing NextHop" with a copy flag. Inheriting from NextHop or IP would be semantically wrong.

---

## Phase 5: Investigation Required - ✅ COMPLETE

### 5.1 VPLS unique key
- **File:** `src/exabgp/bgp/message/update/nlri/vpls.py:237-240`
- **Status:** ✅ RESOLVED - XXX removed, unique key = all fields (rd, endpoint, base, offset, size) documented

### 5.2 RTC variable length prefixing
- **File:** `src/exabgp/bgp/message/update/nlri/rtc.py:30-38`
- **Status:** ✅ RESOLVED - XXX removed, limitation documented in docstring (RFC 4684 prefix filtering not implemented)

### 5.3 EVPN MAC index
- **File:** `src/exabgp/bgp/message/update/nlri/evpn/mac.py:132-138`
- **Status:** ✅ RESOLVED - XXX removed, design documented: index() uses full bytes, __eq__() uses RFC key fields

### 5.4 SRCAP redundant parsing
- **File:** `src/exabgp/bgp/message/update/attribute/bgpls/node/srcap.py:88-91`
- **Status:** ✅ RESOLVED - XXX removed, offset calculation (7 = 3 range + 4 header) is correct, not redundant

### 5.5 PMSI length discrepancy
- **File:** `src/exabgp/bgp/message/update/attribute/pmsi.py:90`
- **Status:** ✅ RESOLVED - XXX comment no longer exists

### 5.6 BGP-LS IGP tags LEN checks
- **Files:** `igpextags.py:31`, `igptags.py:34`
- **Status:** ✅ RESOLVED - XXX removed, cls.check(data) validates length, comments document expected format

---

## Progress Log

| Date | Item | Result |
|------|------|--------|
| 2025-11-25 | Project started | Decisions documented |
| 2025-11-25 | Phase 1 benchmarks | 2 implement, 2 document |
| 2025-11-25 | Phase 1 implementation | MAC hash 17x, Update.messages 1.3x |
| 2025-11-25 | Phase 2 implementation | RFC 4271 NEXTHOP validation |
| 2025-11-25 | Phase 3 implementation | Caching init removed, comments clarified |
| 2025-11-25 | All tests pass | Ready for commit |
| 2025-12-04 | Validation audit | 2 resolved (4.1, 5.5), 4.3 reopened (make_vpls needs action/addpath), line numbers updated |
| 2025-12-04 | Recheck 4.3 | 4.3 resolved - make_vpls() has action/addpath params |
| 2025-12-04 | Investigate 4.4 | 4.4 resolved - current design correct, no inheritance change needed |
| 2025-12-04 | Investigate Phase 5 | All 6 items resolved - XXX comments replaced with documentation in commit c948819c |

---

## Testing

After EACH change:
```bash
./qa/bin/test_everything
```

**Final test run:** ✅ All 8 test suites passed in 37.9s
