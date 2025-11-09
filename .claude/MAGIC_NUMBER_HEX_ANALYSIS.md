# ExaBGP Magic Numbers - Hex vs Decimal Analysis

## ExaBGP Coding Conventions

Based on codebase analysis, ExaBGP uses:

### **Hexadecimal (0x...) for:**
1. **Protocol type codes** - AFI (0x01, 0x02), SAFI, message types
2. **Capability codes** - 0x01 (Multiprotocol), 0x02 (Route Refresh), 0x40 (Graceful Restart)
3. **Parameter types** - 0x01 (Auth), 0x02 (Capabilities)
4. **Bit masks** - 0xFFFF, 0x0FFF, 0xF000, 0x80, 0x08
5. **Flags** - RESTART_STATE = 0x08, FORWARDING_STATE = 0x80

### **Decimal for:**
1. **Counts and quantities** - 3 (keepalive divisor), 10 (ESI length)
2. **Byte lengths** - 4 (IPv4), 16 (IPv6), 8 (RD), 128 (shutdown msg)
3. **Bit lengths** - 32 (IPv4 mask), 128 (IPv6 mask)
4. **Time values** - 3 (min hold time seconds)
5. **TLV codes** - 257, 258, 263 (could be 0x101, 0x102, 0x107 but written as decimal)

---

## Critical Finding: Parameter.CAPABILITIES Already Exists!

**File:** `src/exabgp/bgp/message/open/capability/capabilities.py:36-45`

```python
class Parameter(int):
    AUTHENTIFICATION_INFORMATION = 0x01  # Deprecated
    CAPABILITIES = 0x02

    def __str__(self):
        if self == 0x01:  # ❌ PLR2004 - should use self.AUTHENTIFICATION_INFORMATION
            return 'AUTHENTIFICATION INFORMATION'
        if self == 0x02:  # ❌ PLR2004 - should use self.CAPABILITIES
            return 'OPTIONAL'
        return 'UNKNOWN'
```

**This is a PLR2004 violation WITHIN the file that defines the constants!**

---

## Updated Recommendations by Magic Number

### Protocol Type Codes (Use Hex)

#### `0x02` (CAPABILITIES Parameter Type)
**Status:** ✅ **CONSTANT EXISTS** - `Parameter.CAPABILITIES = 0x02`

**Violations:**
- `src/exabgp/bgp/message/open/capability/capabilities.py:43` - `if self == 0x02:`

**Fix:** Use existing constant
```python
# Before
if self == 0x02:
    return 'OPTIONAL'

# After  
if self == self.CAPABILITIES:
    return 'OPTIONAL'
```

---

### Version Numbers (Context-dependent)

#### `4` (BGP Version)
**Status:** ❌ **CONSTANT MISSING**

**Current:** `src/exabgp/bgp/message/open/__init__.py:87` - `if version != 4:`

**Recommendation:** Create as decimal (version number, not protocol code)
```python
# In src/exabgp/bgp/message/open/version.py
class Version(int):
    BGP_4 = 4  # RFC 4271 - BGP version 4 (use decimal for version numbers)
```

**Note:** Could also be `0x04` to match hex style, but version numbers are typically decimal

---

### Byte Lengths (Use Decimal)

#### `4` (IPv4 Address Byte Length)
**Status:** ⚠️ **PARTIAL** - Bit length exists (32), byte length missing

**Current:** Used in 40+ files for IPv4 address length checks

**Existing:** `AFI._masks = {IPv4: 32, IPv6: 128}` (bit lengths only)

**Recommendation:** Add byte length constants
```python
# In src/exabgp/protocol/family.py
class _AFI(int):
    # ... existing code ...
    
    _masks = {
        IPv4: 32,
        IPv6: 128,
    }
    
    # NEW: Byte lengths
    _bytes = {
        IPv4: 4,   # 4 bytes = 32 bits
        IPv6: 16,  # 16 bytes = 128 bits
    }
    
    def bytes(self):
        """Return address length in bytes."""
        return self._bytes.get(self, 0)
```

**Usage:**
```python
# Before
if sourceiplen != 4 and sourceiplen != 16:

# After
if sourceiplen not in (AFI.ipv4.bytes(), AFI.ipv6.bytes()):
```

---

### Size Limits (Use Decimal)

#### `128` (Shutdown Communication Max Length)
**Status:** ❌ **CONSTANT MISSING**

**Current:** `src/exabgp/bgp/message/notification.py:127` - `if shutdown_length > 128:`

**Recommendation:** Decimal (byte count)
```python
# In src/exabgp/bgp/message/notification.py
class Notification(Message, Exception):
    # RFC 8203 / RFC 9003 - Shutdown Communication length limits
    SHUTDOWN_COMM_MAX_LEGACY = 128      # RFC 8203 (backward compat)
    SHUTDOWN_COMM_MAX_EXTENDED = 255    # RFC 9003 (extended)
```

---

#### `255` (Extended Optional Parameters Marker)
**Status:** ❌ **CONSTANT MISSING**

**Current:** `src/exabgp/bgp/message/open/capability/capabilities.py:239`
```python
if option_len == 255 and option_type == 255:
```

**Recommendation:** Could be hex (0xFF) as it's a protocol marker value
```python
# In src/exabgp/bgp/message/open/capability/capabilities.py
class Capability:
    EXTENDED_PARAMS_MARKER = 0xFF  # RFC 9072 - distinguished value
```

**Or decimal if treating as size:**
```python
EXTENDED_PARAMS_MARKER = 255  # RFC 9072
```

**ExaBGP convention:** Probably 0xFF since it's a special protocol value, not just a size

---

### Time Values (Use Decimal)

#### `3` (Hold Time Minimum / Keepalive Divisor)
**Status:** ⚠️ **INCONSISTENT**

**Current:** 
- `src/exabgp/bgp/message/open/capability/negotiated.py:156` - `if hold_time < 3:`
- `src/exabgp/bgp/message/open/holdtime.py:23` - `return int(self / 3)`

**Existing:** `HoldTime.MAX = 0xFFFF` exists (hex for max value)

**Recommendation:** Decimal for time values
```python
# In src/exabgp/bgp/message/open/holdtime.py
class HoldTime(int):
    MAX = 0xFFFF  # Keep as hex (matches IANA style)
    MIN = 3       # RFC 4271 - minimum hold time in seconds (use decimal for time)
    KEEPALIVE_DIVISOR = 3  # RFC 4271 Section 4.4 - keepalive = hold_time / 3
```

---

### RD Types (Use Decimal)

#### `0`, `1`, `2` (Route Distinguisher Types)
**Status:** ❌ **CONSTANT MISSING**

**Current:** `src/exabgp/bgp/message/update/nlri/qualifier/rd.py:54-58`
```python
t, c1, c2, c3 = unpack('!HHHH', self.rd)
if t == 0:
    rd = '%d:%d' % (c1, (c2 << 16) + c3)
elif t == 1:
    rd = '%d.%d.%d.%d:%d' % (c1 >> 8, c1 & 0xFF, c2 >> 8, c2 & 0xFF, c3)
elif t == 2:
    rd = '%d:%d' % ((c1 << 16) + c2, c3)
```

**Recommendation:** Decimal (type field values)
```python
# In src/exabgp/bgp/message/update/nlri/qualifier/rd.py
class RouteDistinguisher:
    # RFC 4364 - Route Distinguisher Type Field
    TYPE_AS2_ADMIN = 0   # Type 0: 2-byte AS + 4-byte number
    TYPE_IPV4_ADMIN = 1  # Type 1: IPv4 address + 2-byte number  
    TYPE_AS4_ADMIN = 2   # Type 2: 4-byte AS + 2-byte number
    
    LENGTH = 8  # Always 8 bytes
```

---

### ESI Length (Use Decimal)

#### `10` (Ethernet Segment Identifier Length)
**Status:** ❌ **CONSTANT MISSING**

**Current:** `src/exabgp/bgp/message/update/nlri/qualifier/esi.py:21`
```python
class ESI:
    DEFAULT = b''.join(bytes([0]) for _ in range(10))
    MAX = b''.join(bytes([0xFF]) for _ in range(10))

    def __init__(self, esi=None):
        if len(self.esi) != 10:
            raise Exception('incorrect ESI, len %d instead of 10' % len(esi))
```

**Recommendation:** Decimal (byte count)
```python
class ESI:
    LENGTH = 10  # RFC 7432 - ESI is always 10 bytes
    
    DEFAULT = bytes(LENGTH)
    MAX = bytes([0xFF] * LENGTH)
```

---

### BGP-LS TLV Codes (Use Decimal with Hex Comment)

#### `257`, `258`, `263`, `264`, `265`, `512-518`, `1161`
**Status:** ❌ **DECENTRALIZED** - Each class has its own TLV, no central registry

**Current:** Scattered across BGP-LS files

**Recommendation:** Decimal with hex in comments (IANA uses decimal)
```python
# In src/exabgp/bgp/message/update/nlri/bgpls/tlvcodes.py (NEW FILE)
class BGPLS_TLV:
    """BGP-LS TLV Type Codes - RFC 7752, RFC 9514"""
    
    # Descriptor TLVs
    NODE_DESCRIPTOR = 257   # 0x0101
    LINK_DESCRIPTOR = 258   # 0x0102
    
    # Attribute TLVs  
    MULTI_TOPOLOGY_ID = 263  # 0x0107
    OSPF_ROUTE_TYPE = 264    # 0x0108
    IP_REACHABILITY = 265    # 0x0109
    
    # Sub-TLVs
    LOCAL_NODE_DESC = 512    # 0x0200
    REMOTE_NODE_DESC = 513   # 0x0201
    LINK_LOCAL_ID = 514      # 0x0202
    LINK_REMOTE_ID = 515     # 0x0203
    IPV4_INTERFACE_ADDR = 518  # 0x0206
    
    # SRv6 Extensions - RFC 9514
    SRV6_SID_INFO = 1161  # 0x0489
```

**Rationale:** IANA BGP-LS registry lists codes in decimal

---

## Summary: Hex vs Decimal Decision Matrix

| Value Type | Notation | Example |
|-----------|----------|---------|
| Protocol type codes (AFI, SAFI, Capability) | **Hex** | `0x01`, `0x02`, `0x40` |
| Parameter types | **Hex** | `0x02` (CAPABILITIES) |
| Bit masks | **Hex** | `0xFFFF`, `0x80`, `0x08` |
| BGP version | **Decimal** | `4` (version number) |
| Byte lengths | **Decimal** | `4`, `16`, `8`, `10` |
| Time values | **Decimal** | `3` (seconds) |
| Size limits | **Decimal** or **Hex** | `128` or `0xFF` (0xFF for protocol markers) |
| TLV codes | **Decimal** (with hex comment) | `257  # 0x0101` |
| RD types | **Decimal** | `0`, `1`, `2` |

---

## Priority Fixes

### **Phase 1: Use Existing Constants (Easy Wins)**

1. **Parameter.CAPABILITIES = 0x02** (1 fix)
   - File: `capabilities.py:43,45`
   - Change: `if self == 0x02:` → `if self == self.CAPABILITIES:`

2. **Parameter.AUTHENTIFICATION_INFORMATION = 0x01** (1 fix)
   - File: `capabilities.py:41`
   - Change: `if self == 0x01:` → `if self == self.AUTHENTIFICATION_INFORMATION:`

### **Phase 2: Add Missing Constants (High Impact)**

3. **AFI byte lengths** (80+ fixes across 40+ files)
   - Add `_bytes` dict and `.bytes()` method to `_AFI` class
   - Replace all `!= 4 and != 16` checks

4. **HoldTime.MIN and HoldTime.KEEPALIVE_DIVISOR** (23 fixes)
   - Add to existing `HoldTime` class
   - Replace `< 3` and `/ 3` usages

5. **Extended params marker** (4 fixes)
   - Add `EXTENDED_PARAMS_MARKER = 0xFF` to Capability
   - Replace `== 255` checks

6. **Shutdown comm length** (1 fix)
   - Add to Notification class

### **Phase 3: Add Structural Constants**

7. **RD types** (3 fixes)
   - Add to RouteDistinguisher class

8. **ESI length** (4 fixes)
   - Add LENGTH constant to ESI class

9. **BGP version** (1 fix)
   - Add to Version class

10. **BGP-LS TLV codes** (40+ fixes)
    - Create centralized tlvcodes.py module

---

## Conclusion

ExaBGP follows a clear pattern:
- **Hex for protocol/type codes and masks** (following IANA/RFC convention)
- **Decimal for counts, lengths, and times** (human-readable values)

The biggest wins are:
1. Using `Parameter.CAPABILITIES` (already exists!)
2. Adding byte length support to AFI (covers 80+ violations)
3. Adding time constants to HoldTime (covers 23 violations)
