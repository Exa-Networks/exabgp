# ExaBGP Testing Roadmap - Quick Reference

## Current State: ~60 Tests, 30-40% Coverage

```
Tests by Category:
  NLRI Types        ██████████░░░░░░░░ 17 tests
  Message Types     ███░░░░░░░░░░░░░░░  6 tests
  Attributes        ░░░░░░░░░░░░░░░░░░  0 tests
  Network Layer     ░░░░░░░░░░░░░░░░░░  0 tests
  Protocol Handler  ███░░░░░░░░░░░░░░░  7 tests
  Utilities         ██░░░░░░░░░░░░░░░░ 10 tests
  Fuzzing           ░░░░░░░░░░░░░░░░░░  5 tests
```

## 🔴 CRITICAL GAPS - HIGH IMPACT

### 1. AS_PATH Parsing (246 lines)
**Impact: CRITICAL** | **Current Tests: 0** | **Recommended: 20**
- 4 segment types (SET, SEQUENCE, CONFED_SEQUENCE, CONFED_SET)
- ASN4 vs ASN2 compatibility
- Empty path edge cases

**File:** `/src/exabgp/bgp/message/update/attribute/aspath.py`

---

### 2. Community Attributes (19 files, 500+ lines)
**Impact: CRITICAL** | **Current Tests: 2** | **Recommended: 30**
- Standard communities
- Extended communities (Route Target, Bandwidth, etc.)
- Large communities (RFC 8092)

**Files:** 
- `/src/exabgp/bgp/message/update/attribute/community/initial/`
- `/src/exabgp/bgp/message/update/attribute/community/extended/`
- `/src/exabgp/bgp/message/update/attribute/community/large/`

---

### 3. Path Attribute Framework (514 lines)
**Impact: CRITICAL** | **Current Tests: 0** | **Recommended: 25**
- Flag validation (mandatory, optional, transitive)
- Length validation
- Missing mandatory attributes detection
- Attribute order validation

**File:** `/src/exabgp/bgp/message/update/attribute/attributes.py`

---

## 🟠 HIGH IMPACT GAPS

### 4. UPDATE Message Validation (331 lines)
**Impact: HIGH** | **Current Tests: 2** | **Recommended: 20**
- Withdrawn routes validation
- NLRI consistency
- Attribute dependency checks

**File:** `/src/exabgp/bgp/message/update/__init__.py`

---

### 5. MPRNLRI/MPURNLRI (313 lines combined)
**Impact: HIGH** | **Current Tests: 0** | **Recommended: 18**
- MP_REACH_NLRI parsing
- MP_UNREACH_NLRI parsing
- AFI/SAFI handling

**Files:**
- `/src/exabgp/bgp/message/update/attribute/mprnlri.py`
- `/src/exabgp/bgp/message/update/attribute/mpurnlri.py`

---

### 6. TCP/Network Layer (540 lines combined)
**Impact: HIGH** | **Current Tests: 0** | **Recommended: 27**
- Socket creation and management
- TLS/TCP-MD5 authentication
- Connection state transitions
- Error handling

**Files:**
- `/src/exabgp/reactor/network/tcp.py`
- `/src/exabgp/reactor/network/connection.py`

---

## 🟡 MEDIUM IMPACT GAPS

### 7. OPEN Message (95+ lines + capability logic)
**Impact: MEDIUM** | **Current Tests: 2** | **Recommended: 27**
- Capability negotiation
- Hold time validation
- ASN validation
- Router ID validation

**Files:**
- `/src/exabgp/bgp/message/open/__init__.py`
- `/src/exabgp/bgp/message/open/capability/`

---

### 8. Individual Path Attributes (400+ lines combined)
**Impact: MEDIUM** | **Current Tests: 0** | **Recommended: 19**
- ORIGIN (3 values: IGP, EGP, INCOMPLETE)
- NEXT_HOP validation
- LOCAL_PREF
- MED
- AGGREGATOR
- CLUSTER_LIST
- ORIGINATOR_ID

---

### 9. BGP-LS Extensions (1000+ lines)
**Impact: MEDIUM** | **Current Tests: 9** | **Recommended: 30**
- TLV parsing (10+ types)
- Link attributes with SRv6 extensions
- Node attributes
- Prefix attributes

**Files:** `/src/exabgp/bgp/message/update/attribute/bgpls/`

---

### 10. BGP Neighbor State Machine (665 lines)
**Impact: MEDIUM** | **Current Tests: Minimal** | **Recommended: 25**
- State transitions
- Hold timer handling
- Graceful shutdown
- Error recovery

**File:** `/src/exabgp/bgp/neighbor.py`

---

## 🟢 LOWER PRIORITY GAPS

### Additional Components (High complexity, lower frequency)
- **SRv6 Attributes** (300+ lines) - 0 tests, recommend 12
- **FlowSpec** (701 lines) - 4 tests, recommend 15
- **PMSI** (166 lines) - 0 tests, recommend 8
- **NOTIFICATION** (178 lines) - 2 tests, recommend 15
- **MUP NLRI** (5 files) - 0 tests, recommend 10

---

## Test Implementation Timeline

### Phase 1: Attribute Foundation (2-3 weeks)
Priority: CRITICAL | Impact: +40% coverage | Files: 5
- [ ] `test_aspath.py` (20 tests)
- [ ] `test_attributes.py` (25 tests)
- [ ] `test_communities.py` (30 tests)

### Phase 2: Message Validation (2-3 weeks)
Priority: HIGH | Impact: +20% coverage | Files: 3
- [ ] `test_update_validation.py` (20 tests)
- [ ] `test_open_extended.py` (27 tests)
- [ ] `test_multiprotocol.py` (18 tests)

### Phase 3: Network Layer (3-4 weeks)
Priority: HIGH | Impact: +15% coverage | Files: 3
- [ ] `test_network_tcp.py` (27 tests)
- [ ] `test_neighbor_state.py` (25 tests)
- [ ] `test_protocol_handler_extended.py` (20 tests)

### Phase 4: Advanced Features (2-3 weeks)
Priority: MEDIUM | Impact: +10% coverage | Files: 4
- [ ] `test_bgpls_extended.py` (30 tests)
- [ ] `test_srv6.py` (12 tests)
- [ ] `test_flowspec_advanced.py` (15 tests)

---

## Key Statistics

| Metric | Value |
|--------|-------|
| Total Source Files | 200+ |
| BGP Message Files | 50+ |
| Path Attribute Files | 30+ |
| NLRI Type Files | 50+ |
| Current Test Cases | ~60 |
| **Estimated Gap** | **120-150 tests** |
| **Recommended Priority Tests** | **80-90 tests** |
| **Total Recommended** | **140-160 tests** |

---

## File Priority Matrix

### Tier 1: CRITICAL (Do First)
```
aspath.py           ⭐⭐⭐⭐⭐  Very High Complexity
attributes.py       ⭐⭐⭐⭐⭐  Very High Complexity
communities/        ⭐⭐⭐⭐   High Complexity
```

### Tier 2: HIGH (Do Next)
```
update/__init__.py       ⭐⭐⭐⭐   High Complexity
mprnlri.py              ⭐⭐⭐⭐   High Complexity
mpurnlri.py             ⭐⭐⭐    Medium Complexity
network/tcp.py          ⭐⭐⭐⭐   High Complexity
network/connection.py   ⭐⭐⭐⭐   High Complexity
```

### Tier 3: MEDIUM (Do After)
```
open/__init__.py           ⭐⭐⭐   Medium Complexity
neighbor.py                ⭐⭐⭐⭐   High Complexity
bgpls/ (all)               ⭐⭐⭐⭐   High Complexity
nlri/flow.py               ⭐⭐⭐⭐   High Complexity
```

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

## Quick Win Tests (Low Effort, High Value)

These can be implemented quickly to gain 20% coverage:

1. **ORIGIN validation** (4 tests) - Simple 3-value enum
2. **LOCAL_PREF** (3 tests) - Simple 4-byte value
3. **MED** (3 tests) - Simple 4-byte value
4. **CLUSTER_LIST** (4 tests) - Simple list of addresses
5. **Simple AS_PATH tests** (5 tests) - Basic parsing before complex cases

---

## Resources

- Full analysis: `/TESTING_ANALYSIS.md`
- BGP RFC: RFC 4271
- Community RFCs: RFC 1997 (standard), RFC 4360 (extended), RFC 8092 (large)
- BGP-LS: RFC 7752
- SRv6: RFC 9256
