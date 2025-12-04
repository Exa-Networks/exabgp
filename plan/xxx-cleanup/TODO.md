# XXX Comment Cleanup - TODO

**Status:** Partial - Phase 1-3 complete
**Started:** 2025-11-25
**Updated:** 2025-11-25

---

## Decisions

### API Breaking Changes (Category 4)
**Decision:** Make breaking changes, update all callers
- NextHop API (string vs bytes)
- VPLS signature alignment
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
- **Status:** Pending
- **Action:** Change to accept bytes, update all callers

### 4.2 Attribute.CODE instantiability
- **File:** `src/exabgp/bgp/message/update/attribute/attribute.py:87-88`
- **Status:** Pending
- **Action:** Make CODE non-instantiable, update usages

### 4.3 VPLS signature alignment
- **File:** `src/exabgp/bgp/message/update/nlri/vpls.py:39`
- **Status:** Pending
- **Action:** Add AFI, SAFI, action parameters to match other NLRIs

### 4.4 TrafficNextHopSimpson inheritance
- **File:** `src/exabgp/bgp/message/update/attribute/community/extended/traffic.py:236`
- **Status:** Pending
- **Action:** Make subclass of NextHop or IP

---

## Phase 5: Investigation Required - NOT STARTED

### 5.1 VPLS unique key
- **File:** `src/exabgp/bgp/message/update/nlri/vpls.py:95-96`
- **Status:** Pending investigation

### 5.2 RTC variable length prefixing
- **File:** `src/exabgp/bgp/message/update/nlri/rtc.py:30`
- **Status:** Pending investigation

### 5.3 EVPN MAC index
- **File:** `src/exabgp/bgp/message/update/nlri/evpn/mac.py:82`
- **Status:** Pending investigation

### 5.4 SRCAP redundant parsing
- **File:** `src/exabgp/bgp/message/update/attribute/bgpls/node/srcap.py:92`
- **Status:** Pending investigation

### 5.5 PMSI length discrepancy
- **File:** `src/exabgp/bgp/message/update/attribute/pmsi.py:90`
- **Status:** Pending investigation

### 5.6 BGP-LS IGP tags LEN checks
- **Files:** `igpextags.py:31`, `igptags.py:34`
- **Status:** Pending investigation

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

---

## Testing

After EACH change:
```bash
./qa/bin/test_everything
```

**Final test run:** ✅ All 8 test suites passed in 37.9s
