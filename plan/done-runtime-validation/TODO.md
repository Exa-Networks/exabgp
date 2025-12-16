# Runtime Crash Prevention Audit - TODO

**Status:** ✅ Complete
**Created:** 2025-12-04
**Completed:** 2025-12-16
**Priority:** Security/Stability

---

## Summary

Systematic audit of all parsing code to identify and fix missing length/bounds validation that could cause runtime crashes (IndexError, struct.error, ValueError) when processing malformed data.

---

## Audit Methodology

For each parsing module:
1. Identify all `unpack()`, direct byte indexing (`data[n]`), and slice operations
2. Check if length validation exists before access
3. Add `if len(data) < MIN_REQUIRED: raise Notify(3, 5, ...)` checks where missing
4. Run full test suite after each module fix

---

## Completed Audits

### BGP-LS ✅

**Date:** 2025-12-04
**Files:** 11
**Issues Fixed:** 12

| File | Fix |
|------|-----|
| `bgpls/link/srv6endx.py` | 22 byte minimum |
| `bgpls/link/srv6lanendx.py` | 28/26 bytes (ISIS/OSPF) |
| `bgpls/link/srv6sidstructure.py` | 4 byte minimum |
| `bgpls/link/srv6locator.py` | 8 byte minimum |
| `bgpls/link/srv6endpointbehavior.py` | 4 byte minimum |
| `bgpls/node/srcap.py` | Initial + per-iteration |
| `bgpls/link/sradjlan.py` | 10 byte minimum |
| `bgpls/link/sradj.py` | 4 byte minimum |
| `bgpls/linkstate.py` | TLV header + payload + empty flags |
| `bgpls/node/isisarea.py` | Empty data check |
| `bgpls/prefix/srprefix.py` | 4 byte minimum |

**Details:** See `bgpls.md`

### BGP Messages ✅

**Date:** 2025-12-15
**Files:** 5
**Issues Fixed:** 0 (already validated)

All BGP message parsers already have proper length validation:

| File | Validation |
|------|------------|
| `bgp/message/open/__init__.py` | ✅ Line 127-128: `if len(data) < cls.HEADER_SIZE` |
| `bgp/message/update/collection.py` | ✅ Lines 204-220: Multiple checks in `split()` |
| `bgp/message/notification.py` | ✅ Line 103-104: `if len(packed) < 2` |
| `bgp/message/keepalive.py` | ✅ Line 52-53: Validates empty payload |
| `bgp/message/refresh.py` | ✅ Lines 91-94: try/except for struct.unpack |

### Capabilities ✅

**Date:** 2025-12-15
**Files:** 12
**Issues Fixed:** 0 (already validated)

All capability parsers already have proper length validation:

| File | Validation |
|------|------------|
| `capabilities.py` | ✅ Lines 222-293: Multiple checks for param/capability lengths |
| `mp.py` | ✅ Lines 47-48: `if len(data) < 4` |
| `addpath.py` | ✅ Lines 79-80: `if len(data) < 4` per entry |
| `asn4.py` | ✅ Uses ASN.unpack_asn which validates 2/4 bytes |
| `graceful.py` | ✅ Lines 85-86, 94-95: min 2 bytes + 4 per family |
| `nexthop.py` | ✅ Lines 65-66: `if len(data) < 6` per entry |
| `hostname.py` | ✅ Lines 57-65: Multiple length checks |
| `software.py` | ✅ Lines 42-46: Length validation |
| `extended.py` | ✅ No data to parse (empty capability) |
| `refresh.py` | ✅ No data to parse (empty capability) |
| `ms.py` | ✅ No data parsing needed |
| `operational.py` | ✅ No data parsing needed |
| `unknown.py` | ✅ Stores data as-is, no parsing |

### Attributes ✅

**Date:** 2025-12-16
**Files:** 18
**Issues Fixed:** 0 (already validated)

All attribute parsers already have proper length validation:

| File | Validation |
|------|------------|
| `collection.py` | ✅ Lines 349-366, 403-417: try/except for IndexError/ValueError |
| `aspath.py` | ✅ Lines 211-234: try/except for IndexError and struct.error |
| `aggregator.py` | ✅ Lines 70-72: Validates 6 or 8 bytes |
| `aggregator.py (AS4)` | ✅ Lines 188-189: Validates 8 bytes |
| `clusterlist.py` | ✅ Lines 62-63: Validates multiple of 4 bytes |
| `communities.py` | ✅ Lines 61-62: Validates multiple of 4 bytes |
| `extended/communities.py` | ✅ Lines 93-94: Validates multiple of 8 bytes |
| `extended/communities.py (IPv6)` | ✅ Lines 181-182: Validates multiple of 20 bytes |
| `large/communities.py` | ✅ Lines 59-60: Validates multiple of 12 bytes |
| `origin.py` | ✅ Lines 58-61: Validates exactly 1 byte and value <= 2 |
| `med.py` | ✅ Lines 54-55: Validates exactly 4 bytes |
| `localpref.py` | ✅ Lines 55-56: Validates exactly 4 bytes |
| `nexthop.py` | ✅ Lines 63-64: Validates 4 or 16 bytes |
| `mprnlri.py` | ✅ Lines 158-176: Multiple checks (min 5 bytes, NH length, reserved) |
| `mpurnlri.py` | ✅ Lines 104-105: Validates at least 3 bytes |

### NLRI Types ✅

**Date:** 2025-12-16
**Files:** 15+
**Issues Fixed:** 0 (already validated)

All NLRI parsers already have proper length validation:

| File | Validation |
|------|------------|
| `nlri/inet.py` | ✅ Lines 385-386, 425-429, 433-439: AddPath, mask, NLRI length checks |
| `nlri/cidr.py` | ✅ Lines 226-227: `decode()` validates enough data for CIDR |
| `nlri/label.py` | ✅ Inherits from INET, uses parent validation |
| `nlri/vpls.py` | ✅ Lines 217-221: Min 2 bytes + length consistency |
| `nlri/flow.py` | ✅ Lines 1025-1036: Length validation + extended length + truncation |
| `nlri/evpn/nlri.py` | ✅ Lines 138-145: Min 2 bytes + total length validation |
| `nlri/mup/nlri.py` | ✅ Lines 131-140: Min 4 bytes + total length validation |
| `nlri/mvpn/nlri.py` | ✅ Lines 127-134: Min 2 bytes + total length validation |
| `nlri/bgpls/nlri.py` | ✅ Lines 164-174: Min 4 bytes + VPN 12 bytes + truncation |
| `nlri/qualifier/labels.py` | ✅ Lines 29-30: Validates multiple of 3 bytes |
| `nlri/qualifier/rd.py` | ✅ Lines 31-32: Validates exactly 8 bytes |

### Protocol Layer ✅

**Date:** 2025-12-16
**Files:** 7
**Issues Fixed:** 0 (already validated or safe failure modes)

All protocol layer parsers are validated or have safe failure modes:

| File | Validation |
|------|------------|
| `protocol/ip/__init__.py` | ✅ `socket.inet_ntop()` raises ValueError for invalid data; all wire callers pre-validate |
| `protocol/iso/__init__.py` | ✅ `unpack_sysid()` uses `hex()` which handles any Buffer |
| `protocol/family.py (AFI)` | ✅ Lines 86-87: `if len(data) < 2` validation |
| `protocol/family.py (SAFI)` | ✅ Line 246: Safe handling of empty data with conditional |
| `protocol/__init__.py` | ✅ No data parsing - just name/code mappings |
| `protocol/ip/netmask.py` | ✅ `make_netmask()` validates values (lines 89-94) |
| `protocol/resource.py` | ✅ `_value()` validates ranges (lines 62-67) |

---

## 🎉 Audit Complete

All modules have been audited. The codebase is well-protected against malformed message crashes.

**Summary:**
- **BGP-LS:** 12 issues fixed
- **All other modules:** Already properly validated

---

## Fix Pattern

```python
# VULNERABLE
def unpack(cls, data: bytes) -> SomeClass:
    value = data[3]  # IndexError if len(data) < 4
    field = unpack('!H', data[0:2])[0]  # struct.error if len(data) < 2

# SAFE
MIN_LENGTH = 4  # Document what this covers

def unpack(cls, data: bytes) -> SomeClass:
    if len(data) < MIN_LENGTH:
        raise Notify(3, 5, f'{cls.REPR}: data too short, need {MIN_LENGTH} bytes, got {len(data)}')
    value = data[3]
    field = unpack('!H', data[0:2])[0]
```

---

## Progress Log

| Date | Module | Status |
|------|--------|--------|
| 2025-12-04 | BGP-LS | ✅ Complete (12 issues fixed) |
| 2025-12-15 | BGP Messages | ✅ Complete (0 issues - already validated) |
| 2025-12-15 | Capabilities | ✅ Complete (0 issues - already validated) |
| 2025-12-16 | Attributes | ✅ Complete (0 issues - already validated) |
| 2025-12-16 | NLRI Types | ✅ Complete (0 issues - already validated) |
| 2025-12-16 | Protocol Layer | ✅ Complete (0 issues - already validated) |

---

## References

- BGP: RFC 4271
- BGP-LS: RFC 7752
- SR Extensions: RFC 8667, RFC 9085
- SRv6: RFC 9252, RFC 9514
