# XXX/TODO Comment Cleanup

**Status:** 🔄 IN PROGRESS - Phase 6-7 pending
**Started:** 2025-11-25
**Updated:** 2025-12-09

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

## Phase 6: Remaining XXX Comments - 📋 PENDING

**Total:** 31 XXX comments (28 in src/, 3 in vendoring/)

### 6.1 Reactor/API (2 items)

| ID | File | Line | Comment | Status |
|----|------|------|---------|--------|
| 6.1.1 | `reactor/api/command/watchdog.py` | 56 | move into Action | ⏳ Pending |
| 6.1.2 | `reactor/api/command/watchdog.py` | 75 | move into Action | ⏳ Pending |

### 6.2 Data Validation (4 items)

| ID | File | Line | Comment | Status |
|----|------|------|---------|--------|
| 6.2.1 | `data/check.py` | 82 | object redefine | ⏳ Pending |
| 6.2.2 | `data/check.py` | 133 | ipv4 improve | ⏳ Pending |
| 6.2.3 | `data/check.py` | 137 | ipv6 improve | ⏳ Pending |
| 6.2.4 | `data/check.py` | 282 | Label class reference | ⏳ Pending |

### 6.3 Configuration (6 items)

| ID | File | Line | Comment | Status |
|----|------|------|---------|--------|
| 6.3.1 | `configuration/parser.py` | 105 | port check | ⏳ Pending |
| 6.3.2 | `configuration/flow/parser.py` | 222 | rule family check | ⏳ Pending |
| 6.3.3 | `configuration/static/parser.py` | 60 | could raise | ⏳ Pending |
| 6.3.4 | `configuration/static/parser.py` | 98 | Action.UNSET usage | ⏳ Pending |
| 6.3.5 | `configuration/static/parser.py` | 110 | Action.ANNOUNCE usage | ⏳ Pending |
| 6.3.6 | `configuration/static/parser.py` | 331 | Community cache | ⏳ Pending |
| 6.3.7 | `configuration/neighbor/__init__.py` | 527 | memory usage | ⏳ Pending |
| 6.3.8 | `configuration/configuration.py` | 388 | neighbor location | ⏳ Pending |

### 6.4 Protocol/IP (3 items)

| ID | File | Line | Comment | Status |
|----|------|------|---------|--------|
| 6.4.1 | `protocol/ip/__init__.py` | 21 | API broken | ⏳ Pending |
| 6.4.2 | `protocol/ip/__init__.py` | 22 | NLRI constructors | ⏳ Pending |
| 6.4.3 | `protocol/ip/__init__.py` | 150 | ::FFFF handling | ⏳ Pending |

### 6.5 BGP Capabilities (7 items)

| ID | File | Line | Comment | Status |
|----|------|------|---------|--------|
| 6.5.1 | `bgp/message/open/capability/asn4.py` | 36 | two ASN check | ⏳ Pending |
| 6.5.2 | `bgp/message/open/capability/negotiated.py` | 191 | capa not defined | ⏳ Pending |
| 6.5.3 | `bgp/message/open/capability/negotiated.py` | 210 | router id check | ⏳ Pending |
| 6.5.4 | `bgp/message/open/capability/capabilities.py` | 177 | RFC version | ⏳ Pending |
| 6.5.5 | `bgp/message/open/capability/operational.py` | 27 | verbose | ⏳ Pending |
| 6.5.6 | `bgp/message/open/capability/ms.py` | 30 | Capability content | ⏳ Pending |
| 6.5.7 | `bgp/message/open/capability/capability.py` | 138 | cls tidy up | ⏳ Pending |

### 6.6 BGP Messages (3 items)

| ID | File | Line | Comment | Status |
|----|------|------|---------|--------|
| 6.6.1 | `bgp/message/operational.py` | 85 | upper case | ⏳ Pending |
| 6.6.2 | `bgp/message/refresh.py` | 89 | RR data | ⏳ Pending |
| 6.6.3 | `environment/parsing.py` | 105 | incomplete | ⏳ Pending |

### 6.7 BGP Update/NLRI (3 items)

| ID | File | Line | Comment | Status |
|----|------|------|---------|--------|
| 6.7.1 | `bgp/message/update/attribute/collection.py` | 530 | guesswork | ⏳ Pending |
| 6.7.2 | `bgp/message/update/nlri/inet.py` | 366 | API review | ⏳ Pending |
| 6.7.3 | `bgp/message/update/nlri/flow.py` | 826 | bomb | ⏳ Pending |

### 6.8 Vendored Code (3 items) - ⚠️ DO NOT MODIFY

| ID | File | Line | Comment | Status |
|----|------|------|---------|--------|
| 6.8.1 | `vendoring/objgraph.py` | 800 | stderr/log | ⛔ Skip |
| 6.8.2 | `vendoring/objgraph.py` | 943 | find_executable | ⛔ Skip |
| 6.8.3 | `vendoring/profiler.py` | 254 | where is this used | ⛔ Skip |

---

## Phase 7: TODO Comments - 📋 PENDING

**Total:** 21 TODO comments (20 in src/, 1 in vendoring/)

### 7.1 Reactor/API (2 items)

| ID | File | Line | Comment | Status |
|----|------|------|---------|--------|
| 7.1.1 | `reactor/api/command/limit.py` | 179 | convert to generator | ⏳ Pending |
| 7.1.2 | `reactor/api/processes.py` | 274 | ack-format config option | ⏳ Pending |

### 7.2 Data Validation (3 items)

| ID | File | Line | Comment | Status |
|----|------|------|---------|--------|
| 7.2.1 | `data/check.py` | 214 | improve space check | ⏳ Pending |
| 7.2.2 | `data/check.py` | 270 | extendedcommunity improve | ⏳ Pending |
| 7.2.3 | `data/check.py` | 345 | redirect asn check | ⏳ Pending |

### 7.3 Configuration (2 items)

| ID | File | Line | Comment | Status |
|----|------|------|---------|--------|
| 7.3.1 | `configuration/static/parser.py` | 450 | OriginASN4Number (2,2) | ⏳ Pending |
| 7.3.2 | `configuration/static/parser.py` | 453 | RouteTargetASN4Number (2,3) | ⏳ Pending |

### 7.4 NLRI AddPath Support (5 items)

| ID | File | Line | Comment | Status |
|----|------|------|---------|--------|
| 7.4.1 | `bgp/message/update/nlri/vpls.py` | 178 | addpath support | ⏳ Pending |
| 7.4.2 | `bgp/message/update/nlri/mup/nlri.py` | 87 | addpath support | ⏳ Pending |
| 7.4.3 | `bgp/message/update/nlri/bgpls/nlri.py` | 107 | addpath support | ⏳ Pending |
| 7.4.4 | `bgp/message/update/nlri/mvpn/nlri.py` | 84 | addpath support | ⏳ Pending |
| 7.4.5 | `bgp/message/update/nlri/evpn/nlri.py` | 117 | addpath support | ⏳ Pending |

### 7.5 EVPN/Qualifiers (2 items)

| ID | File | Line | Comment | Status |
|----|------|------|---------|--------|
| 7.5.1 | `bgp/message/update/nlri/qualifier/etag.py` | 9 | E-VPN ESI specs | ⏳ Pending |
| 7.5.2 | `bgp/message/update/nlri/qualifier/esi.py` | 13 | E-VPN ESI specs | ⏳ Pending |

### 7.6 Attributes (2 items)

| ID | File | Line | Comment | Status |
|----|------|------|---------|--------|
| 7.6.1 | `bgp/message/update/attribute/aggregator.py` | 134 | REFACTOR ASN conversion | ⏳ Pending |
| 7.6.2 | `bgp/message/update/attribute/aspath.py` | 267 | REFACTOR ASN conversion | ⏳ Pending |

### 7.7 SRv6 (2 items)

| ID | File | Line | Comment | Status |
|----|------|------|---------|--------|
| 7.7.1 | `bgp/message/update/attribute/sr/srv6/generic.py` | 29 | incomplete | ⏳ Pending |
| 7.7.2 | `bgp/message/update/attribute/sr/srv6/generic.py` | 58 | incomplete | ⏳ Pending |

### 7.8 FlowSpec (2 items)

| ID | File | Line | Comment | Status |
|----|------|------|---------|--------|
| 7.8.1 | `bgp/message/update/nlri/flow.py` | 874 | AFI reset verify | ⏳ Pending |
| 7.8.2 | `bgp/message/update/nlri/flow.py` | 897 | REFACTOR EOL bits | ⏳ Pending |
| 7.8.3 | `bgp/message/update/nlri/flow.py` | 930 | addpath support | ⏳ Pending |

### 7.9 Vendored Code (1 item) - ⚠️ DO NOT MODIFY

| ID | File | Line | Comment | Status |
|----|------|------|---------|--------|
| 7.9.1 | `vendoring/profiler.py` | 20 | multiprocessing alternative | ⛔ Skip |

---

## Summary

| Phase | Category | Total | Resolved | Pending | Skipped |
|-------|----------|-------|----------|---------|---------|
| 1-5 | Original XXX cleanup | 20 | 20 | 0 | 0 |
| 6 | Remaining XXX | 31 | 0 | 28 | 3 |
| 7 | TODO comments | 21 | 0 | 20 | 1 |
| **Total** | | **72** | **20** | **48** | **4** |

---

## Testing

After EACH change:
```bash
./qa/bin/test_everything
```

**Phase 1-5 test run:** ✅ All 8 test suites passed in 37.9s

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
| 2025-12-04 | Validation audit | 2 resolved (4.1, 5.5), 4.3 reopened |
| 2025-12-04 | Recheck 4.3 | 4.3 resolved - make_vpls() has action/addpath |
| 2025-12-04 | Investigate 4.4 | 4.4 resolved - current design correct |
| 2025-12-04 | Investigate Phase 5 | All 6 items resolved |
| 2025-12-09 | Scope expansion | Added 31 XXX + 21 TODO to scope (Phase 6-7) |
