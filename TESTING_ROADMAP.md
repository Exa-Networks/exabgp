# ExaBGP Testing Roadmap - Quick Reference

## Current State: ~850+ Tests, 60-70% Coverage (BGP Core)

```
Tests by Category:
  NLRI Types        ██████████████████ 478+ tests ✅
  Message Types     ████████████████░░ 234+ tests ✅
  Attributes        ████████████████░░ 218+ tests ✅
  SR Extensions     ████████████████░░  80+ tests ✅
  Network Layer     ░░░░░░░░░░░░░░░░░░   0  tests ❌
  Protocol Handler  ██░░░░░░░░░░░░░░░░   7  tests ⚠️
  Utilities         ██░░░░░░░░░░░░░░░░  10  tests ⚠️
  Fuzzing           ██░░░░░░░░░░░░░░░░   5  tests ⚠️
```

## ✅ COMPLETED - HIGH PRIORITY (Previously Critical)

### 1. AS_PATH Parsing (246 lines) ✅ COMPLETE
**Impact: CRITICAL** | **Current Tests: 21** | **Status: 90%+ coverage**
- ✅ 4 segment types (SET, SEQUENCE, CONFED_SEQUENCE, CONFED_SET)
- ✅ ASN4 vs ASN2 compatibility
- ✅ Empty path edge cases
- ✅ Long paths (>255 ASNs)
- ✅ AS_TRANS handling

**File:** `/src/exabgp/bgp/message/update/attribute/aspath.py`
**Test File:** `tests/test_aspath.py` (21 tests)

---

### 2. Community Attributes (19 files, 500+ lines) ✅ COMPLETE
**Impact: CRITICAL** | **Current Tests: 27** | **Status: 90%+ coverage**
- ✅ Standard communities (RFC 1997)
- ✅ Extended communities (Route Target, Bandwidth, etc.) (RFC 4360)
- ✅ Large communities (RFC 8092)
- ✅ All subtypes tested

**Test File:** `tests/test_communities.py` (27 tests)

---

### 3. Path Attribute Framework (514 lines) ✅ COMPLETE
**Impact: CRITICAL** | **Current Tests: 21** | **Status: 85%+ coverage**
- ✅ Flag validation (mandatory, optional, transitive)
- ✅ Length validation
- ✅ Missing mandatory attributes detection
- ✅ Attribute order validation
- ✅ TREAT_AS_WITHDRAW behavior

**File:** `/src/exabgp/bgp/message/update/attribute/attributes.py`
**Test File:** `tests/test_attributes.py` (21 tests)

---

### 4. UPDATE Message Validation (331 lines) ✅ COMPLETE
**Impact: HIGH** | **Current Tests: 20+** | **Status: 85%+ coverage**
- ✅ Withdrawn routes validation
- ✅ NLRI consistency
- ✅ Attribute dependency checks
- ✅ Mandatory attributes verification

**File:** `/src/exabgp/bgp/message/update/__init__.py`
**Test Files:** `tests/test_update_message.py` (20 tests), `tests/fuzz/test_update_message_integration.py` (integration tests)

---

### 5. MPRNLRI/MPURNLRI (313 lines combined) ✅ COMPLETE
**Impact: HIGH** | **Current Tests: 17** | **Status: 90%+ coverage**
- ✅ MP_REACH_NLRI parsing
- ✅ MP_UNREACH_NLRI parsing
- ✅ AFI/SAFI handling

**Test File:** `tests/test_multiprotocol.py` (17 tests)

---

### 6. OPEN Message (95+ lines + capability logic) ✅ COMPLETE
**Impact: MEDIUM** | **Current Tests: 33** | **Status: 90%+ coverage**
- ✅ All capability types
- ✅ Hold time validation
- ✅ ASN validation
- ✅ Router ID validation
- ✅ Capability negotiation

**Test File:** `tests/test_open_capabilities.py` (33 tests)

---

### 7. Individual Path Attributes (400+ lines combined) ✅ COMPLETE
**Impact: MEDIUM** | **Current Tests: 71** | **Status: 90%+ coverage**
- ✅ ORIGIN (3 values: IGP, EGP, INCOMPLETE)
- ✅ NEXT_HOP validation
- ✅ LOCAL_PREF
- ✅ MED
- ✅ AGGREGATOR
- ✅ CLUSTER_LIST
- ✅ ORIGINATOR_ID
- ✅ ATOMIC_AGGREGATE
- ✅ AIGP
- ✅ PMSI

**Test File:** `tests/test_path_attributes.py` (71 tests)

---

### 8. BGP-LS Extensions (1000+ lines) ✅ COMPLETE
**Impact: MEDIUM** | **Current Tests: 57** | **Status: 83% coverage**
- ✅ All NLRI types (NODE, LINK, PREFIXv4, PREFIXv6, SRv6SID)
- ✅ TLV parsing
- ✅ Node/Link/Prefix descriptors
- ⚠️ 5 hash bugs discovered and documented

**Test File:** `tests/test_bgpls.py` (57 tests, 5 skipped due to bugs)

---

### 9. SRv6 Attributes (300+ lines) ✅ COMPLETE
**Impact: MEDIUM** | **Current Tests: 80** | **Status: 95% coverage**
- ✅ SR-MPLS (LabelIndex, PrefixSid, SRGB)
- ✅ SRv6 (L2 Service, L3 Service, SID Information, SID Structure)
- ✅ Generic fallback for unknown TLVs

**Test File:** `tests/test_sr_attributes.py` (80 tests)

---

### 10. FlowSpec (701 lines) ✅ COMPLETE
**Impact: MEDIUM** | **Current Tests: 70** | **Status: 88% coverage**
- ✅ All component types (Destination, Source, Port, Protocol, etc.)
- ✅ IPv4 and IPv6 flows
- ✅ Operator combinations (EQ, GT, LT, AND, OR)
- ✅ Binary operators (MATCH, NOT, INCLUDE)

**Test File:** `tests/test_flowspec.py` (70 tests)

---

### 11. Message Types ✅ COMPLETE
**Current Tests: 181** | **Status: 85-95% coverage**
- ✅ NOTIFICATION (53 tests) - All error codes/subcodes
- ✅ KEEPALIVE (21 tests) - Format validation
- ✅ ROUTE_REFRESH (43 tests) - All types, demarcation, ORF
- ✅ OPERATIONAL (46 tests) - Advisory, Query, Response, Statistics

**Test Files:**
- `tests/test_notification_comprehensive.py` (53 tests)
- `tests/test_keepalive.py` (21 tests)
- `tests/test_route_refresh.py` (43 tests)
- `tests/test_operational_nop.py` (46 tests)

---

### 12. NLRI Types ✅ MOSTLY COMPLETE
**Current Tests: 478+** | **Status: 85-100% coverage**
- ✅ EVPN (47 tests, 92-98%)
- ✅ MUP (44 tests, 90-93%)
- ✅ MVPN (36 tests, 89-95%)
- ✅ RTC (33 tests, 100%)
- ✅ VPLS (34 tests, 100%)
- ✅ IPVPN (30 tests, 100%)
- ✅ Label (35 tests, 100%)
- ✅ INET (22 tests, 85%)

---

## 🔴 REMAINING CRITICAL GAPS

### 1. TCP/Network Layer (540 lines combined) ❌ NOT STARTED
**Impact: CRITICAL** | **Current Tests: 0** | **Recommended: 25-30**
- Socket creation and management (IPv4/IPv6)
- TLS/TCP-MD5 authentication
- Connection state transitions
- Timeout and error handling
- Non-blocking I/O
- Buffer management

**Files:**
- `/src/exabgp/reactor/network/tcp.py` (275 lines)
- `/src/exabgp/reactor/network/connection.py` (265 lines)

**Recommended Test File:** `tests/test_network_tcp.py`

---

### 2. BGP Neighbor State Machine (665 lines) ❌ MINIMAL COVERAGE
**Impact: CRITICAL** | **Current Tests: ~5** | **Recommended: 25-30**
- State transitions (6 BGP states)
- Hold timer handling and expiration
- Keepalive timer management
- Collision detection
- Graceful shutdown and restart
- Error recovery
- Connection retry logic

**File:** `/src/exabgp/bgp/neighbor.py` (665 lines)

**Recommended Test File:** `tests/test_neighbor_state.py`

---

### 3. Protocol Handler Extended (477 lines) ⚠️ PARTIAL COVERAGE
**Impact: HIGH** | **Current Tests: ~7** | **Recommended: 20-25**
- Message routing based on type
- Negotiation state handling
- ADD-PATH processing
- Extended message support (RFC 8654)
- Error handling for malformed messages
- UPDATE aggregation/splitting
- EOR (End-of-RIB) marker handling

**File:** `/src/exabgp/reactor/protocol.py` (477 lines)

**Recommended Test File:** `tests/test_protocol_handler.py`

---

## 🟡 LOWER PRIORITY GAPS

### Configuration and Parser - 0-20% Coverage
**Impact: MEDIUM** | **Complexity: HIGH**
- CLI argument parsing
- Configuration file parsing
- Neighbor configuration validation
- Route policy parsing

**Files:** `src/exabgp/configuration/`, `src/exabgp/application/`

---

### Reactor/Event Loop - 0% Coverage
**Impact: MEDIUM** | **Complexity: VERY HIGH**
- Event dispatching
- Timer management
- Process management
- API communication

**Files:** `src/exabgp/reactor/loop.py`, `src/exabgp/reactor/api/`

---

## Test Implementation Timeline

### Phase 1: Attribute Foundation ✅ COMPLETED
Priority: CRITICAL | Impact: +40% coverage | Files: 4
- [x] `test_aspath.py` (21 tests) ✅
- [x] `test_attributes.py` (21 tests) ✅
- [x] `test_communities.py` (27 tests) ✅
- [x] `test_path_attributes.py` (71 tests) ✅

**Status:** COMPLETE - 140 tests added, 90%+ coverage achieved

### Phase 2: Message Validation ✅ COMPLETED
Priority: HIGH | Impact: +20% coverage | Files: 7
- [x] `test_update_message.py` (20 tests) ✅
- [x] `test_open_capabilities.py` (33 tests) ✅
- [x] `test_multiprotocol.py` (17 tests) ✅
- [x] `test_notification_comprehensive.py` (53 tests) ✅
- [x] `test_keepalive.py` (21 tests) ✅
- [x] `test_route_refresh.py` (43 tests) ✅
- [x] `test_operational_nop.py` (46 tests) ✅

**Status:** COMPLETE - 233+ tests added, 85-95% coverage achieved

### Phase 3: Network Layer ❌ NOT STARTED
Priority: CRITICAL | Impact: +10-15% coverage | Files: 3
- [ ] `test_network_tcp.py` (25-30 tests) ❌
- [ ] `test_neighbor_state.py` (25-30 tests) ❌
- [ ] `test_protocol_handler.py` (20-25 tests) ⚠️

**Status:** NOT STARTED - This is the PRIMARY REMAINING GAP

**Estimated Effort:** 2-3 weeks
**Impact:** Critical for production reliability

### Phase 4: Advanced Features ✅ MOSTLY COMPLETED
Priority: MEDIUM | Impact: +10% coverage | Files: 4
- [x] `test_bgpls.py` (57 tests) ✅
- [x] `test_sr_attributes.py` (80 tests including SRv6) ✅
- [x] `test_flowspec.py` (70 tests) ✅
- [x] Additional NLRI tests (478+ tests) ✅

**Status:** COMPLETE - 685+ tests added, 85-100% coverage achieved

---

## Key Statistics

| Metric | Original | Current | Change |
|--------|----------|---------|--------|
| Total Source Files | 200+ | 200+ | - |
| BGP Message Files | 50+ | 50+ | - |
| Path Attribute Files | 30+ | 30+ | - |
| NLRI Type Files | 50+ | 50+ | - |
| **Test Cases** | **~60** | **~850+** | **+790** ✅ |
| **BGP Core Coverage** | **30-40%** | **60-70%** | **+30%** ✅ |
| **Remaining Gap** | **140-160 tests** | **60-80 tests** | **Network Layer** ⚠️ |

---

## File Priority Matrix

### ✅ Tier 1: CRITICAL - COMPLETED
```
✅ aspath.py           ⭐⭐⭐⭐⭐  Very High Complexity  (21 tests, 90%+)
✅ attributes.py       ⭐⭐⭐⭐⭐  Very High Complexity  (21 tests, 85%+)
✅ communities/        ⭐⭐⭐⭐   High Complexity       (27 tests, 90%+)
```

### ⚠️ Tier 2: HIGH - PARTIALLY COMPLETED
```
✅ update/__init__.py       ⭐⭐⭐⭐   High Complexity  (20 tests, 85%+)
✅ mprnlri.py              ⭐⭐⭐⭐   High Complexity  (17 tests, 90%+)
✅ mpurnlri.py             ⭐⭐⭐    Medium Complexity (17 tests, 90%+)
❌ network/tcp.py          ⭐⭐⭐⭐   High Complexity  (0 tests, 0%) ⚠️
❌ network/connection.py   ⭐⭐⭐⭐   High Complexity  (0 tests, 0%) ⚠️
```

### ✅ Tier 3: MEDIUM - MOSTLY COMPLETED
```
✅ open/__init__.py           ⭐⭐⭐   Medium Complexity  (33 tests, 90%+)
⚠️ neighbor.py                ⭐⭐⭐⭐   High Complexity    (~5 tests, 10%)
✅ bgpls/ (all)               ⭐⭐⭐⭐   High Complexity    (57 tests, 83%)
✅ nlri/flow.py               ⭐⭐⭐⭐   High Complexity    (70 tests, 88%)
```

### 🎯 CURRENT PRIORITY: Network Layer (Tier 2)
The PRIMARY REMAINING GAP is network layer testing:
1. **test_network_tcp.py** - Socket/TLS/TCP-MD5 (25-30 tests needed)
2. **test_neighbor_state.py** - State machine (25-30 tests needed)
3. **test_protocol_handler.py** - Extended protocol tests (20-25 tests needed)

---

## Testing Best Practices for This Codebase

### 1. Binary Protocol Testing
```python
# Use parameterized tests for binary format variations
@pytest.mark.parametrize("asn_type,data", [
    ("2byte", bytes([0x00, 0x01])),
    ("4byte", bytes([0x00, 0x00, 0x00, 0x01])),
])
```

### 2. Edge Case Coverage
- Zero values and maximum values
- Empty containers (paths, communities, etc.)
- Malformed/incomplete data
- Out-of-order fields

### 3. Error Injection
- Invalid flags
- Wrong lengths
- Truncated messages
- Invalid ASN values

### 4. Property-Based Testing
```python
from hypothesis import given
# Generate random valid ASN values, validate parsing
```

### 5. State Machine Testing
- Verify state transitions for neighbor FSM
- Test timer behavior
- Test error recovery

---

## Quick Win Tests ✅ ALL COMPLETED

All quick win tests have been implemented:

1. ✅ **ORIGIN validation** - Completed in test_path_attributes.py
2. ✅ **LOCAL_PREF** - Completed in test_path_attributes.py
3. ✅ **MED** - Completed in test_path_attributes.py
4. ✅ **CLUSTER_LIST** - Completed in test_path_attributes.py
5. ✅ **AS_PATH tests** - Completed in test_aspath.py (21 comprehensive tests)

---

## Resources

- Full analysis: `/TESTING_ANALYSIS.md`
- BGP RFC: RFC 4271
- Community RFCs: RFC 1997 (standard), RFC 4360 (extended), RFC 8092 (large)
- BGP-LS: RFC 7752
- SRv6: RFC 9256
