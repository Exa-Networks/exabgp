# PLR2004 Magic Numbers - Fix Examples

This document provides concrete examples of how to fix PLR2004 violations by replacing magic numbers with named constants.

---

## Example 1: BGP Version Check

### Current Code (VIOLATION)
**File:** `src/exabgp/bgp/message/open/__init__.py:87`

```python
@classmethod
def unpack_message(cls, data, direction=None, negotiated=None):
    version = data[0]
    if version != 4:  # PLR2004: Magic value used in comparison
        # Only version 4 is supported nowdays ..
        raise Notify(2, 1, 'version number: %d' % data[0])
```

### Fixed Code
```python
# At the top of the file or in constants.py
BGP_VERSION = 4  # RFC 4271 - BGP version 4

@classmethod
def unpack_message(cls, data, direction=None, negotiated=None):
    version = data[0]
    if version != BGP_VERSION:
        # Only version 4 is supported nowdays ..
        raise Notify(2, 1, 'version number: %d' % data[0])
```

**Benefits:**
- Clear intent: "We're checking for BGP version 4"
- RFC reference in one place
- Easy to update if protocol evolves

---

## Example 2: Hold Time Validation

### Current Code (VIOLATION)
**File:** `src/exabgp/bgp/message/open/capability/negotiated.py:156`

```python
if self.received_open.hold_time and self.received_open.hold_time < 3:  # PLR2004
    return (2, 6, 'Hold Time is invalid (%d)' % self.received_open.hold_time)
```

### Fixed Code
```python
# In constants.py or at module level
BGP_HOLD_TIME_MINIMUM = 3  # RFC 4271 Section 4.2 - minimum hold time in seconds (unless 0)

if self.received_open.hold_time and self.received_open.hold_time < BGP_HOLD_TIME_MINIMUM:
    return (2, 6, 'Hold Time is invalid (%d)' % self.received_open.hold_time)
```

**Benefits:**
- Documents the 3-second minimum requirement
- Links to specific RFC section
- Self-documenting code

---

## Example 3: Shutdown Communication Length

### Current Code (VIOLATION)
**File:** `src/exabgp/bgp/message/notification.py:127`

```python
if shutdown_length > 128:  # PLR2004
    self.data = f'invalid Shutdown Communication (too large) length : {shutdown_length} [{hexstring(data)}]'.encode()
    return
```

### Fixed Code
```python
# In constants.py
SHUTDOWN_COMM_MAX_LENGTH_LEGACY = 128    # RFC 8203 - max length for backward compatibility
SHUTDOWN_COMM_MAX_LENGTH_EXTENDED = 255  # RFC 9003 - extended length for multibyte charsets

# In notification.py
if shutdown_length > SHUTDOWN_COMM_MAX_LENGTH_LEGACY:
    self.data = f'invalid Shutdown Communication (too large) length : {shutdown_length} [{hexstring(data)}]'.encode()
    return
```

**Alternative (if supporting RFC 9003):**
```python
# Could add capability check here
max_length = SHUTDOWN_COMM_MAX_LENGTH_EXTENDED if self.supports_rfc9003 else SHUTDOWN_COMM_MAX_LENGTH_LEGACY
if shutdown_length > max_length:
    self.data = f'invalid Shutdown Communication (too large) length : {shutdown_length} [{hexstring(data)}]'.encode()
    return
```

**Benefits:**
- Clarifies why 128 is the limit
- Documents RFC evolution (8203 → 9003)
- Makes future updates easier

---

## Example 4: Extended Optional Parameters

### Current Code (VIOLATION)
**File:** `src/exabgp/bgp/message/open/capability/capabilities.py:239`

```python
if option_len == 255 and option_type == 255:  # PLR2004 (2 violations)
    option_len = unpack('!H', data[2:4])[0]
    data = data[4 : option_len + 4]
    decoder = _extended_type_length
```

### Fixed Code
```python
# In constants.py
EXTENDED_OPT_PARAMS_MARKER = 255  # RFC 9072 - distinguished value for extended parameters

# In capabilities.py
if option_len == EXTENDED_OPT_PARAMS_MARKER and option_type == EXTENDED_OPT_PARAMS_MARKER:
    option_len = unpack('!H', data[2:4])[0]
    data = data[4 : option_len + 4]
    decoder = _extended_type_length
```

**Benefits:**
- Makes the special meaning of 255 obvious
- Links to RFC 9072 specification
- Reduces duplication

---

## Example 5: Route Refresh Subtypes

### Current Code (VIOLATION)
**File:** `src/exabgp/bgp/message/refresh.py:30`

```python
class Reserved(int):
    def __str__(self):
        if self == 0:
            return 'query'
        if self == 1:
            return 'begin'
        if self == 2:  # PLR2004
            return 'end'
        return 'invalid'
```

### Fixed Code - Option A (Class Constants)
```python
class Reserved(int):
    # RFC 2918 / draft-ietf-idr-bgp-enhanced-route-refresh
    REQUEST = 0
    BEGIN = 1
    END = 2

    def __str__(self):
        if self == self.REQUEST:
            return 'query'
        if self == self.BEGIN:
            return 'begin'
        if self == self.END:
            return 'end'
        return 'invalid'
```

### Fixed Code - Option B (Module Constants)
```python
# At module level
ROUTE_REFRESH_REQUEST = 0
ROUTE_REFRESH_BEGIN = 1
ROUTE_REFRESH_END = 2

class Reserved(int):
    def __str__(self):
        if self == ROUTE_REFRESH_REQUEST:
            return 'query'
        if self == ROUTE_REFRESH_BEGIN:
            return 'begin'
        if self == ROUTE_REFRESH_END:
            return 'end'
        return 'invalid'
```

**Benefits:**
- Clear semantic meaning
- Reusable across module
- Better for testing

---

## Example 6: IPv4/IPv6 Address Lengths (High Volume)

### Current Code (VIOLATION)
**File:** `src/exabgp/bgp/message/update/nlri/mvpn/sourcead.py:78,88`

```python
sourceiplen = int(data[cursor] / 8)
cursor += 1
if sourceiplen != 4 and sourceiplen != 16:  # PLR2004 (2 violations)
    raise Notify(3, 5, f'Expected 32 bits (IPv4) or 128 bits (IPv6).')

# ... later ...
groupiplen = int(data[cursor] / 8)
cursor += 1
if groupiplen != 4 and groupiplen != 16:  # PLR2004 (2 violations)
    raise Notify(3, 5, f'Expected 32 bits (IPv4) or 128 bits (IPv6).')
```

### Fixed Code - Option A (Simple Constants)
```python
# In constants.py or protocol.family module
IPV4_ADDRESS_LENGTH = 4   # bytes (32 bits)
IPV6_ADDRESS_LENGTH = 16  # bytes (128 bits)

# In sourcead.py
sourceiplen = int(data[cursor] / 8)
cursor += 1
if sourceiplen not in (IPV4_ADDRESS_LENGTH, IPV6_ADDRESS_LENGTH):
    raise Notify(3, 5, f'Expected 32 bits (IPv4) or 128 bits (IPv6).')

groupiplen = int(data[cursor] / 8)
cursor += 1
if groupiplen not in (IPV4_ADDRESS_LENGTH, IPV6_ADDRESS_LENGTH):
    raise Notify(3, 5, f'Expected 32 bits (IPv4) or 128 bits (IPv6).')
```

### Fixed Code - Option B (Validation Function)
```python
# In a utilities module
IPV4_ADDRESS_LENGTH = 4
IPV6_ADDRESS_LENGTH = 16
VALID_IP_LENGTHS = (IPV4_ADDRESS_LENGTH, IPV6_ADDRESS_LENGTH)

def validate_ip_length(length: int, field_name: str = "IP address") -> None:
    """Validate that IP address length is either IPv4 (4 bytes) or IPv6 (16 bytes).

    Args:
        length: The length in bytes to validate
        field_name: Name of the field for error messages

    Raises:
        Notify: If length is not valid IPv4 or IPv6 length
    """
    if length not in VALID_IP_LENGTHS:
        raise Notify(
            3, 5,
            f'{field_name} length ({length * 8} bits) invalid. '
            f'Expected 32 bits (IPv4) or 128 bits (IPv6).'
        )

# In sourcead.py
sourceiplen = int(data[cursor] / 8)
cursor += 1
validate_ip_length(sourceiplen, "Multicast Source IP")

groupiplen = int(data[cursor] / 8)
cursor += 1
validate_ip_length(groupiplen, "Multicast Group IP")
```

**Benefits:**
- Reduces duplication across 40+ files
- Centralizes IP validation logic
- Better error messages
- Easier to maintain

---

## Example 7: Route Distinguisher Types

### Current Code (VIOLATION)
**File:** `src/exabgp/bgp/message/update/nlri/qualifier/rd.py:54-58`

```python
def _str(self):
    t, c1, c2, c3 = unpack('!HHHH', self.rd)
    if t == 0:  # PLR2004
        rd = '%d:%d' % (c1, (c2 << 16) + c3)
    elif t == 1:  # PLR2004
        rd = '%d.%d.%d.%d:%d' % (c1 >> 8, c1 & 0xFF, c2 >> 8, c2 & 0xFF, c3)
    elif t == 2:  # PLR2004
        rd = '%d:%d' % ((c1 << 16) + c2, c3)
    else:
        rd = hexstring(self.rd)
    return rd
```

### Fixed Code
```python
# As class constants
class RouteDistinguisher:
    # RFC 4364 - Route Distinguisher Type Field
    TYPE_AS2_ADMIN = 0  # Type 0: 2-byte AS administrator + 4-byte assigned number
    TYPE_IP_ADMIN = 1   # Type 1: IPv4 address administrator + 2-byte assigned number
    TYPE_AS4_ADMIN = 2  # Type 2: 4-byte AS administrator + 2-byte assigned number

    LENGTH = 8  # Route Distinguisher is always 8 bytes

    def _str(self):
        t, c1, c2, c3 = unpack('!HHHH', self.rd)
        if t == self.TYPE_AS2_ADMIN:
            rd = '%d:%d' % (c1, (c2 << 16) + c3)
        elif t == self.TYPE_IP_ADMIN:
            rd = '%d.%d.%d.%d:%d' % (c1 >> 8, c1 & 0xFF, c2 >> 8, c2 & 0xFF, c3)
        elif t == self.TYPE_AS4_ADMIN:
            rd = '%d:%d' % ((c1 << 16) + c2, c3)
        else:
            rd = hexstring(self.rd)
        return rd
```

**Benefits:**
- Documents RD type encodings
- Self-contained in RD class
- Matches RFC 4364 terminology

---

## Example 8: ESI Length Validation

### Current Code (VIOLATION)
**File:** `src/exabgp/bgp/message/update/nlri/qualifier/esi.py:21`

```python
class ESI:
    DEFAULT = b''.join(bytes([0]) for _ in range(10))
    MAX = b''.join(bytes([0xFF]) for _ in range(10))

    def __init__(self, esi=None):
        self.esi = self.DEFAULT if esi is None else esi
        if len(self.esi) != 10:  # PLR2004
            raise Exception('incorrect ESI, len %d instead of 10' % len(esi))
```

### Fixed Code
```python
class ESI:
    LENGTH = 10  # RFC 7432 - Ethernet Segment Identifier is always 10 bytes

    DEFAULT = b''.join(bytes([0]) for _ in range(LENGTH))
    MAX = b''.join(bytes([0xFF]) for _ in range(LENGTH))

    def __init__(self, esi=None):
        self.esi = self.DEFAULT if esi is None else esi
        if len(self.esi) != self.LENGTH:
            raise Exception(f'incorrect ESI, len {len(esi)} instead of {self.LENGTH}')

    def __len__(self):
        return self.LENGTH  # Can now use this constant
```

**Benefits:**
- Single source of truth for ESI length
- Used in multiple places (DEFAULT, MAX, validation)
- Clearer error messages

---

## Example 9: BGP-LS TLV Codes

### Current Code (VIOLATION)
**File:** `src/exabgp/bgp/message/update/nlri/bgpls/tlvs/neighaddr.py` (conceptual)

```python
# Hypothetical example showing TLV code checks
def unpack(cls, data, tlv_code):
    if tlv_code == 257:  # PLR2004
        # Node descriptor
        pass
    elif tlv_code == 258:  # PLR2004
        # Link descriptor
        pass
```

### Fixed Code
```python
# In bgpls/constants.py or as class constants
class BGPLS_TLV:
    """BGP-LS TLV Type Codes - RFC 7752"""
    # Descriptor TLVs
    NODE_DESCRIPTOR = 257
    LINK_DESCRIPTOR = 258

    # Attribute TLVs
    MULTI_TOPOLOGY_ID = 263
    OSPF_ROUTE_TYPE = 264
    IP_REACHABILITY = 265

    # Sub-TLVs
    LOCAL_NODE_DESC = 512
    REMOTE_NODE_DESC = 513
    LINK_LOCAL_ID = 514
    LINK_REMOTE_ID = 515
    IPV4_INTERFACE_ADDR = 518

    # SRv6 Extensions - RFC 9514
    SRV6_SID_INFO = 1161

# Usage
def unpack(cls, data, tlv_code):
    if tlv_code == BGPLS_TLV.NODE_DESCRIPTOR:
        # Node descriptor
        pass
    elif tlv_code == BGPLS_TLV.LINK_DESCRIPTOR:
        # Link descriptor
        pass
```

**Benefits:**
- All BGP-LS codes in one place
- Easy to add new TLV types
- Clear RFC attribution

---

## Example 10: Parameter Type Check

### Current Code (VIOLATION)
**File:** `src/exabgp/bgp/message/open/capability/capabilities.py:43`

```python
class Parameter(int):
    AUTHENTIFICATION_INFORMATION = 0x01  # Depreciated
    CAPABILITIES = 0x02

    def __str__(self):
        if self == 0x01:
            return 'AUTHENTIFICATION INFORMATION'
        if self == 0x02:  # PLR2004
            return 'OPTIONAL'
        return 'UNKNOWN'
```

### Fixed Code
```python
class Parameter(int):
    AUTHENTIFICATION_INFORMATION = 0x01  # Deprecated - RFC 4271
    CAPABILITIES = 0x02                  # RFC 4271

    def __str__(self):
        if self == self.AUTHENTIFICATION_INFORMATION:
            return 'AUTHENTIFICATION INFORMATION'
        if self == self.CAPABILITIES:
            return 'OPTIONAL'
        return 'UNKNOWN'
```

**Benefits:**
- Uses existing class constants
- Self-referential and maintainable
- No new constants needed

---

## General Patterns

### Pattern 1: Simple Comparison
```python
# Before
if value == 4:

# After
EXPECTED_VALUE = 4
if value == EXPECTED_VALUE:
```

### Pattern 2: Multiple Comparisons
```python
# Before
if value != 4 and value != 16:

# After
VALID_VALUES = (4, 16)
if value not in VALID_VALUES:
```

### Pattern 3: Class Constants
```python
# Before
class MyClass:
    def check(self):
        if self.value == 10:
            return True

# After
class MyClass:
    EXPECTED_VALUE = 10

    def check(self):
        if self.value == self.EXPECTED_VALUE:
            return True
```

### Pattern 4: Enum-like Values
```python
# Before
if msg_type == 0:
    return 'request'
elif msg_type == 1:
    return 'begin'
elif msg_type == 2:
    return 'end'

# After
MSG_TYPE_REQUEST = 0
MSG_TYPE_BEGIN = 1
MSG_TYPE_END = 2

if msg_type == MSG_TYPE_REQUEST:
    return 'request'
elif msg_type == MSG_TYPE_BEGIN:
    return 'begin'
elif msg_type == MSG_TYPE_END:
    return 'end'
```

---

## Testing Considerations

When fixing magic numbers, ensure:

1. **No behavioral changes** - constants must equal original values
2. **Tests still pass** - run functional and unit tests
3. **Error messages updated** - if showing constant values
4. **Documentation updated** - if values are documented

Example test:
```python
def test_bgp_version_constant():
    """Ensure BGP_VERSION constant matches expected value."""
    assert BGP_VERSION == 4, "BGP version should be 4 per RFC 4271"

def test_ip_length_constants():
    """Ensure IP length constants are correct."""
    assert IPV4_ADDRESS_LENGTH == 4
    assert IPV6_ADDRESS_LENGTH == 16
```

---

## Migration Strategy

### Step 1: Create Constants File
```python
# src/exabgp/bgp/constants.py
"""
BGP Protocol Constants

This module defines named constants for BGP protocol values
to improve code readability and maintainability.
"""

# Protocol version
BGP_VERSION = 4  # RFC 4271

# ... etc
```

### Step 2: Import in Target Files
```python
from exabgp.bgp.constants import BGP_VERSION, BGP_HOLD_TIME_MINIMUM
```

### Step 3: Replace Magic Numbers
Do one category at a time:
1. High priority (version, hold time)
2. High volume (IP lengths)
3. Specialized (RD types, ESI length)
4. BGP-LS codes

### Step 4: Run Tests
After each change:
```bash
./qa/bin/functional encoding
env exabgp_log_enable=false pytest --cov --cov-reset ./tests/*_test.py
```

### Step 5: Update Documentation
Update CLAUDE.md and other docs with constant locations

---

## Summary

Replacing magic numbers with named constants:
- **Improves readability** - intent is clear
- **Eases maintenance** - change in one place
- **Documents RFCs** - links to specifications
- **Reduces errors** - typos in 128 vs 182 caught at definition
- **Enables IDE features** - jump to definition, find usages
- **No runtime cost** - constants are compile-time substitutions

The key is choosing good names that are:
- **Descriptive** - clear what the value represents
- **Consistent** - follow naming conventions
- **Scoped** - in appropriate module/class
- **Documented** - with RFC references
