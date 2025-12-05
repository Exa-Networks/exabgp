# Plan: Runtime Validation Audit - Phase 2

**Status:** 📋 Planning
**Created:** 2025-12-05
**Priority:** Security/Stability

---

## Goal

Complete the systematic audit of all parsing code to identify and fix missing length/bounds validation that could cause runtime crashes (IndexError, struct.error, ValueError) when processing malformed BGP data.

**Phase 1 (BGP-LS) completed:** 12 issues fixed across 11 files.

---

## Scope

### High Priority (Network-facing, untrusted data)

1. **BGP Messages** - Core message parsing
2. **Capabilities** - OPEN message capabilities
3. **Attributes** - UPDATE message attributes

### Medium Priority (After high priority complete)

4. **NLRI Types** - Route parsing
5. **Protocol Layer** - IP/ISO parsing

---

## Implementation Plan

### Phase 2A: BGP Messages ✅ COMPLETE (2025-12-05)

| File | Status | Fix Applied |
|------|--------|-------------|
| `message/open/__init__.py` | ✅ Fixed | Added HEADER_SIZE check |
| `capability/capabilities.py` | ✅ Fixed | Added extended format validation |
| `message/update/__init__.py` | ✅ Fixed | Added split() length checks |
| `message/notification.py` | ✅ Already valid | N/A |
| `message/keepalive.py` | ✅ N/A | Empty body, no parsing |
| `message/refresh.py` | ✅ Already valid | N/A |

All 11 tests pass.

### Phase 2B: Capabilities ✅ COMPLETE (2025-12-05)

| File | Status | Fix Applied |
|------|--------|-------------|
| `capability/capability.py` | ✅ Safe | Base class, no parsing |
| `capability/addpath.py` | ✅ Fixed | 4-byte loop validation |
| `capability/graceful.py` | ✅ Fixed | 2-byte header + 4-byte loop |
| `capability/mp.py` | ✅ Fixed | 4-byte minimum check |
| `capability/nexthop.py` | ✅ Fixed | 6-byte loop validation |
| `capability/hostname.py` | ✅ Fixed | Progressive length checks |
| `capability/software.py` | ✅ Fixed | Length prefix validation |
| `capability/asn4.py` | ✅ Fixed | ASN size validation |
| `capability/refresh.py` | ✅ Safe | No data access |
| `capability/extended.py` | ✅ Safe | No data access |

All 11 tests pass.

### Phase 2C: Attributes ✅ COMPLETE (2025-12-05)

All attribute parsing already validated - no changes needed!

| File | Status | Notes |
|------|--------|-------|
| `attribute/aspath.py` | ✅ Safe | try/except IndexError/struct.error |
| `attribute/aggregator.py` | ✅ Safe | Length check in from_packet() |
| `attribute/clusterlist.py` | ✅ Safe | Modulo 4 check |
| `attribute/nexthop.py` | ✅ Safe | Length in (4, 16) check |
| `community/initial/` | ✅ Safe | Modulo 4 check |
| `community/large/` | ✅ Safe | Modulo 12 check |
| `community/extended/` | ✅ Safe | Modulo 8 and 20 checks |

### Phase 3: NLRI Types (Medium Priority)

| File | Notes |
|------|-------|
| `nlri/inet.py` | Core IPv4/IPv6 prefixes |
| `nlri/label.py` | Labeled unicast |
| `nlri/ipvpn.py` | VPNv4/v6 |
| `nlri/flow.py` | FlowSpec (complex) |
| `nlri/vpls.py` | VPLS |
| `nlri/evpn/*.py` | EVPN route types |
| `nlri/mup/*.py` | MUP route types |
| `nlri/mvpn/*.py` | MVPN route types |

### Phase 4: Protocol Layer (Lower Priority)

| File | Notes |
|------|-------|
| `protocol/ip/__init__.py` | IP address parsing |
| `protocol/iso.py` | ISIS identifiers |

---

## Fix Pattern

```python
# VULNERABLE
def unpack(cls, data: bytes) -> SomeClass:
    value = data[3]  # IndexError if len(data) < 4
    field = unpack('!H', data[0:2])[0]  # struct.error if len(data) < 2

# SAFE
MIN_LENGTH = 4  # Document minimum requirement

def unpack(cls, data: bytes) -> SomeClass:
    if len(data) < MIN_LENGTH:
        raise Notify(3, 5, f'{cls.__name__}: data too short, need {MIN_LENGTH} bytes, got {len(data)}')
    value = data[3]
    field = unpack('!H', data[0:2])[0]
```

**Error codes:**
- `Notify(3, 5, ...)` = UPDATE Message Error, Attribute Length Error
- `Notify(2, 0, ...)` = OPEN Message Error, Unspecific
- `Notify(1, 2, ...)` = Message Header Error, Bad Message Length

---

## Testing Strategy

After EACH file fix:
```bash
uv run pytest tests/unit/ -v -x  # Quick unit tests
./qa/bin/test_everything         # Full suite before commit
```

Consider adding fuzz tests:
- Empty data
- 1-byte data
- Truncated messages
- Garbage length fields

---

## Success Criteria

- [ ] All high-priority files audited (messages, capabilities)
- [ ] All medium-priority files audited (attributes, NLRI)
- [ ] All tests pass after each fix
- [ ] No IndexError/struct.error possible from malformed input

---

## Resume Point

**Start with:** `message/open/__init__.py` - OPEN message parsing

**Method:**
1. Read the file
2. Search for `unpack(`, `data[`, slice patterns
3. Identify minimum length requirements
4. Add validation before each access
5. Test

---

**Last Updated:** 2025-12-05
