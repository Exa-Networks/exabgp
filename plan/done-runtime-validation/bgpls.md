# BGP-LS Data Validation Audit - TODO

**Status:** Completed
**Created:** 2025-12-04
**Priority:** Security/Stability

---

## Summary

Audit found **12+ runtime failure vulnerabilities** in BGP-LS parsing code due to missing data validation. Malformed BGP-LS TLVs could crash the daemon with `IndexError`, `struct.error`, or `ValueError`.

**Location:** `src/exabgp/bgp/message/update/attribute/bgpls/`

---

## Root Cause

All issues follow the same anti-pattern - accessing data without length validation:

```python
# VULNERABLE
def unpack_bgpls(cls, data: bytes) -> SomeClass:
    value = data[3]  # IndexError if len(data) < 4
    field = unpack('!H', data[0:2])[0]  # struct.error if len(data) < 2
```

**Fix pattern:**
```python
# SAFE
def unpack_bgpls(cls, data: bytes) -> SomeClass:
    if len(data) < MIN_REQUIRED:
        raise Notify(3, 5, f'{cls.REPR}: data too short, need {MIN_REQUIRED} bytes')
    # ... safe to access data now
```

---

## Phase 1: HIGH RISK - SRv6 Parsing (6 issues)

### 1.1 srv6endx.py - SRv6 End.X SID
- **File:** `link/srv6endx.py:71-77`
- **Min required:** 22 bytes
- **Vulnerable code:**
  ```python
  behavior = unpack('!I', bytes([0, 0]) + data[:2])[0]
  flags = cls.unpack_flags(data[2:3])
  algorithm = data[3]
  weight = data[4]
  sid = IPv6.ntop(data[6:22])
  ```
- **Fix:** Add `if len(data) < 22: raise Notify(3, 5, ...)`

### 1.2 srv6lanendx.py - SRv6 LAN End.X SID
- **File:** `link/srv6lanendx.py:54-80`
- **Min required:** 28 bytes (ISIS) or 22 bytes (OSPF)
- **Vulnerable code:**
  ```python
  behavior = unpack('!I', bytes([0, 0]) + data[:2])[0]
  flags = cls.unpack_flags(data[2:3])
  algorithm = data[3]
  weight = data[4]
  if protocol_type == ISIS:
      neighbor_id = ISO.unpack_sysid(data[6:12])
  else:
      neighbor_id = str(IP.unpack_ip(data[6:10]))
  sid = IPv6.ntop(data[start_offset : start_offset + 16])
  ```
- **Fix:** Add length check based on protocol_type

### 1.3 srv6sidstructure.py - SRv6 SID Structure
- **File:** `link/srv6sidstructure.py:42-53`
- **Min required:** 4 bytes
- **Vulnerable code:**
  ```python
  loc_block_len = data[0]
  loc_node_len = data[1]
  func_len = data[2]
  arg_len = data[3]
  ```
- **Fix:** Add `if len(data) < 4: raise Notify(3, 5, ...)`

### 1.4 srv6locator.py - SRv6 Locator
- **File:** `link/srv6locator.py:47-53`
- **Min required:** 8 bytes
- **Vulnerable code:**
  ```python
  flags = cls.unpack_flags(bytes(data[0:1]))
  algorithm = data[1]
  metric = unpack('!I', data[4:8])[0]
  ```
- **Fix:** Add `if len(data) < 8: raise Notify(3, 5, ...)`

### 1.5 srv6endpointbehavior.py - SRv6 Endpoint Behavior
- **File:** `link/srv6endpointbehavior.py:43-47`
- **Min required:** 4 bytes
- **Vulnerable code:**
  ```python
  algorithm = data[3]
  endpoint_behavior = unpack('!H', data[0:2])[0]
  ```
- **Fix:** Add `if len(data) < 4: raise Notify(3, 5, ...)`

### 1.6 srcap.py - SR Capabilities
- **File:** `node/srcap.py:66-95`
- **Min required:** 2 bytes initial, then 7+ per iteration
- **Vulnerable code:**
  ```python
  flags = cls.unpack_flags(data[0:1])
  data = data[SRCAP_FLAGS_RESERVED_SIZE:]
  while data:
      range_size = unpack('!L', bytes([0]) + data[:3])[0]
      sub_type, length = unpack('!HH', data[3:7])
      # ...
  ```
- **Fix:** Add initial check and per-iteration check in while loop

---

## Phase 2: HIGH RISK - SR Adjacency Parsing (2 issues)

### 2.1 sradjlan.py - SR Adjacency LAN SID
- **File:** `link/sradjlan.py:58-92`
- **Min required:** 10 bytes
- **Vulnerable code:**
  ```python
  flags = cls.unpack_flags(data[0:1])
  weight = data[1]
  system_id = ISO.unpack_sysid(data[4:10])
  data = data[10:]
  ```
- **Fix:** Add `if len(data) < 10: raise Notify(3, 5, ...)`

### 2.2 sradj.py - SR Adjacency SID
- **File:** `link/sradj.py:50-83`
- **Min required:** 4 bytes
- **Vulnerable code:**
  ```python
  flags = cls.unpack_flags(data[0:1])
  weight = data[1]
  data = data[4:]
  ```
- **Fix:** Add `if len(data) < 4: raise Notify(3, 5, ...)`

---

## Phase 3: MEDIUM RISK - Core Parsing (2 issues)

### 3.1 linkstate.py - Main TLV Loop
- **File:** `linkstate.py:86-108`
- **Min required:** 4 bytes per TLV header
- **Vulnerable code:**
  ```python
  while data:
      scode, length = unpack('!HH', data[:4])
      payload = data[4 : length + 4]
      # ...
  ```
- **Fix:** Add `if len(data) < 4: raise Notify(3, 5, ...)`
- **Also:** Validate `length + 4 <= len(data)` before slicing

### 3.2 linkstate.py - Flag Unpacking
- **File:** `linkstate.py:196`
- **Issue:** Empty data causes `int('', 16)` ValueError
- **Vulnerable code:**
  ```python
  hex_rep = int(binascii.b2a_hex(data), 16)
  ```
- **Fix:** Check `if not data: return {}` or raise

---

## Phase 4: MEDIUM RISK - Node Attributes (2 issues)

### 4.1 isisarea.py - ISIS Area
- **File:** `node/isisarea.py:32-33`
- **Issue:** Empty data causes `int('', 16)` ValueError
- **Vulnerable code:**
  ```python
  return cls(int(data.hex(), 16))
  ```
- **Fix:** Check `if not data: raise Notify(3, 5, ...)`

### 4.2 srprefix.py - SR Prefix SID
- **File:** `prefix/srprefix.py:55-91`
- **Min required:** 4 bytes
- **Vulnerable code:**
  ```python
  flags = cls.unpack_flags(data[0:1])
  sr_algo = data[1]
  data = data[4:]
  ```
- **Fix:** Add `if len(data) < 4: raise Notify(3, 5, ...)`

---

## Testing Strategy

After EACH fix:
```bash
./qa/bin/test_everything
```

Consider adding fuzz tests for BGP-LS parsing with:
- Empty data
- 1-byte data
- Truncated TLVs
- Garbage length fields

---

## Progress Log

| Date | Phase | Status |
|------|-------|--------|
| 2025-12-04 | Audit completed | Documented |
| 2025-12-04 | Phase 1 (SRv6) | ✅ All 6 issues fixed |
| 2025-12-04 | Phase 2 (SR Adjacency) | ✅ All 2 issues fixed |
| 2025-12-04 | Phase 3 (Core Parsing) | ✅ All 2 issues fixed |
| 2025-12-04 | Phase 4 (Node Attrs) | ✅ All 2 issues fixed |
| 2025-12-04 | All tests pass | ✅ 9/9 test suites |

---

## References

- BGP-LS: RFC 7752
- SR Extensions: RFC 8667, RFC 9085
- SRv6: RFC 9252, RFC 9514
