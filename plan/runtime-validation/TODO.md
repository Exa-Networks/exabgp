# Runtime Crash Prevention Audit - TODO

**Status:** In Progress
**Created:** 2025-12-04
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

---

## Pending Audits

### BGP Messages (High Priority)

- [ ] `bgp/message/open/__init__.py` - OPEN message parsing
- [ ] `bgp/message/update/__init__.py` - UPDATE message parsing
- [ ] `bgp/message/notification.py` - NOTIFICATION parsing
- [ ] `bgp/message/keepalive.py` - KEEPALIVE parsing
- [ ] `bgp/message/refresh.py` - ROUTE-REFRESH parsing

### Capabilities (High Priority)

- [ ] `bgp/message/open/capability/` - All capability parsers

### Attributes (Medium Priority)

- [ ] `bgp/message/update/attribute/` - All attribute unpack methods
- [ ] Focus on: communities, extended communities, large communities
- [ ] Focus on: AS_PATH, aggregator, cluster list

### NLRI Types (Medium Priority)

- [ ] `bgp/message/update/nlri/inet.py`
- [ ] `bgp/message/update/nlri/label.py`
- [ ] `bgp/message/update/nlri/flow.py`
- [ ] `bgp/message/update/nlri/evpn/`
- [ ] `bgp/message/update/nlri/vpls.py`
- [ ] `bgp/message/update/nlri/mup/`
- [ ] `bgp/message/update/nlri/mvpn/`

### Protocol Layer (Lower Priority)

- [ ] `protocol/ip/` - IP address parsing
- [ ] `protocol/iso.py` - ISO/ISIS identifiers
- [ ] `protocol/family.py` - AFI/SAFI handling

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

---

## References

- BGP: RFC 4271
- BGP-LS: RFC 7752
- SR Extensions: RFC 8667, RFC 9085
- SRv6: RFC 9252, RFC 9514
