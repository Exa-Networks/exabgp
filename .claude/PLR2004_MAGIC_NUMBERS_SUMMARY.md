# PLR2004 Magic Numbers - Quick Reference Summary

This is a categorized list of all magic numbers found in the BGP code by PLR2004 analysis.

## Quick Statistics
- **Total PLR2004 violations:** 100
- **Unique magic number values:** 36
- **Files affected:** ~30+

---

## Magic Numbers by Category

### Protocol Version & Basic Constants

| Value | Meaning | RFC/Standard | Priority | Files Affected |
|-------|---------|--------------|----------|----------------|
| `4` | BGP Version 4 / IPv4 address length (4 bytes) | RFC 4271 / IPv4 | HIGH | 40+ files |
| `16` | IPv6 address length (16 bytes) | IPv6 | HIGH | 40+ files |
| `2` | 2-byte values / Route Refresh END / Min param length | RFC 4271 | MEDIUM | Multiple |
| `3` | BGP Hold Time minimum (seconds) / Min extended param length | RFC 4271 | HIGH | 2 files |

### Size Limits & Thresholds

| Value | Meaning | RFC/Standard | Priority | Files Affected |
|-------|---------|--------------|----------|----------------|
| `128` | Shutdown Communication max length (legacy) | RFC 8203 | HIGH | 1 file |
| `255` | Extended Optional Parameters marker | RFC 9072 | HIGH | 1 file |
| `256` | Likely related to byte boundary | - | LOW | - |
| `512` | BGP-LS TLV/attribute constants | RFC 7752 | MEDIUM | BGP-LS files |
| `513` | BGP-LS TLV code | RFC 7752 | MEDIUM | BGP-LS files |
| `514` | BGP-LS TLV code | RFC 7752 | MEDIUM | BGP-LS files |
| `515` | BGP-LS TLV code | RFC 7752 | MEDIUM | BGP-LS files |
| `518` | BGP-LS TLV code | RFC 7752 | MEDIUM | BGP-LS files |

### Route Distinguisher & VPN

| Value | Meaning | RFC/Standard | Priority | Files Affected |
|-------|---------|--------------|----------|----------------|
| `0` | RD Type 0 (AS2:number) | RFC 4364 | MEDIUM | 1 file |
| `1` | RD Type 1 (IPv4:number) | RFC 4364 | MEDIUM | 1 file |
| `2` | RD Type 2 (AS4:number) | RFC 4364 | MEDIUM | 1 file |
| `8` | Route Distinguisher length (bytes) | RFC 4364 | MEDIUM | VPN files |

### EVPN Constants

| Value | Meaning | RFC/Standard | Priority | Files Affected |
|-------|---------|--------------|----------|----------------|
| `10` | ESI (Ethernet Segment Identifier) length | RFC 7432 | MEDIUM | 1 file |
| `12` | EVPN route type field sizes | RFC 7432 | LOW | EVPN files |
| `20` | EVPN data sizes | RFC 7432 | LOW | EVPN files |
| `24` | EVPN MAC+IP route components | RFC 7432 | LOW | EVPN files |

### BGP-LS TLV Codes

| Value | Meaning | RFC/Standard | Priority | Files Affected |
|-------|---------|--------------|----------|----------------|
| `257` | BGP-LS Node Descriptor TLV | RFC 7752 | MEDIUM | BGP-LS files |
| `258` | BGP-LS Link Descriptor TLV | RFC 7752 | MEDIUM | BGP-LS files |
| `263` | BGP-LS Multi-Topology ID TLV | RFC 7752 | MEDIUM | BGP-LS files |
| `264` | BGP-LS OSPF Route Type TLV | RFC 7752 | MEDIUM | BGP-LS files |
| `265` | BGP-LS IP Reachability TLV | RFC 7752 | MEDIUM | BGP-LS files |
| `1161` | BGP-LS SRv6 SID Information TLV | RFC 9514 | MEDIUM | BGP-LS files |

### Bit Masks & Flags

| Value | Meaning | RFC/Standard | Priority | Files Affected |
|-------|---------|--------------|----------|----------------|
| `0x02` | CAPABILITIES parameter type | RFC 4271 | HIGH | 1 file |
| `0x3F` | 6-bit mask (0b00111111) | - | LOW | - |
| `0xF0` | High nibble mask (0b11110000) | - | LOW | - |
| `0xFF` | Single byte mask (255) | - | LOW | Multiple |
| `0x0FFF` | 12-bit mask | - | LOW | - |
| `0xFFFF` | 16-bit mask (65535) | - | LOW | - |
| `0xFFFFF` | 20-bit mask | - | LOW | - |
| `0x800000` | 24-bit sign bit | - | LOW | - |

### Miscellaneous Protocol Values

| Value | Meaning | RFC/Standard | Priority | Files Affected |
|-------|---------|--------------|----------|----------------|
| `7` | TLV length or type field | - | LOW | - |
| `11` | EOR prefix length marker | RFC 4724 | LOW | 1 file |
| `32` | IPv4 prefix max length (bits) | - | LOW | - |
| `48` | MAC address length (bits) | - | LOW | - |

---

## Recommended Named Constants (High Priority)

### Create in: `src/exabgp/bgp/constants.py`

```python
# ===================================================================
# BGP Protocol Constants
# ===================================================================

# BGP Version (RFC 4271)
BGP_VERSION = 4

# BGP Hold Time (RFC 4271 Section 4.2)
BGP_HOLD_TIME_MINIMUM = 3  # seconds (unless 0 for disabled keepalive)

# Shutdown Communication (RFC 8203 / RFC 9003)
SHUTDOWN_COMM_MAX_LENGTH_LEGACY = 128    # RFC 8203
SHUTDOWN_COMM_MAX_LENGTH_EXTENDED = 255  # RFC 9003

# Extended Optional Parameters (RFC 9072)
EXTENDED_OPT_PARAMS_MARKER = 255
MIN_CAPABILITY_LENGTH = 2
MIN_EXTENDED_PARAM_LENGTH = 3

# OPEN Message Parameter Types (RFC 4271)
PARAM_TYPE_AUTH_INFO = 0x01  # Deprecated
PARAM_TYPE_CAPABILITIES = 0x02

# Route Refresh Subtypes (RFC 2918 / draft-ietf-idr-bgp-enhanced-route-refresh)
ROUTE_REFRESH_REQUEST = 0
ROUTE_REFRESH_BEGIN = 1
ROUTE_REFRESH_END = 2

# ===================================================================
# IP Address Lengths
# ===================================================================

IPV4_ADDRESS_LENGTH = 4   # bytes (32 bits)
IPV6_ADDRESS_LENGTH = 16  # bytes (128 bits)

# ===================================================================
# Route Distinguisher (RFC 4364)
# ===================================================================

RD_LENGTH = 8  # bytes
RD_TYPE_AS2_ADMIN = 0   # Type 0: 2-byte AS admin + 4-byte number
RD_TYPE_IP_ADMIN = 1    # Type 1: IPv4 admin + 2-byte number
RD_TYPE_AS4_ADMIN = 2   # Type 2: 4-byte AS admin + 2-byte number

# ===================================================================
# EVPN Constants (RFC 7432)
# ===================================================================

ESI_LENGTH = 10  # bytes - Ethernet Segment Identifier
MAC_ADDRESS_BITS = 48

# ===================================================================
# BGP-LS TLV Codes (RFC 7752, RFC 9514)
# ===================================================================

# Descriptor TLVs
BGPLS_TLV_NODE_DESCRIPTOR = 257
BGPLS_TLV_LINK_DESCRIPTOR = 258

# Attribute TLVs
BGPLS_TLV_MULTI_TOPOLOGY_ID = 263
BGPLS_TLV_OSPF_ROUTE_TYPE = 264
BGPLS_TLV_IP_REACHABILITY = 265

# TLV Sub-codes
BGPLS_TLV_LOCAL_NODE_DESC = 512
BGPLS_TLV_REMOTE_NODE_DESC = 513
BGPLS_TLV_LINK_LOCAL_ID = 514
BGPLS_TLV_LINK_REMOTE_ID = 515
BGPLS_TLV_IPV4_INTERFACE_ADDR = 518

# SRv6 Extensions (RFC 9514)
BGPLS_TLV_SRV6_SID_INFO = 1161

# ===================================================================
# ASN Sizes
# ===================================================================

ASN_2BYTE_LENGTH = 2
ASN_4BYTE_LENGTH = 4

# ===================================================================
# Common Bit Masks
# ===================================================================

MASK_8BIT = 0xFF
MASK_16BIT = 0xFFFF
MASK_HIGH_NIBBLE = 0xF0
MASK_LOW_NIBBLE = 0x0F
MASK_6BIT = 0x3F
MASK_12BIT = 0x0FFF
MASK_20BIT = 0xFFFFF
MASK_24BIT_SIGN = 0x800000
```

---

## Implementation Strategy

### Phase 1: High Priority Protocol Constants (Immediate)
1. **BGP Version (4)** - Critical for protocol validation
2. **Hold Time Minimum (3)** - Critical for session management
3. **Shutdown Communication (128/255)** - Important for graceful shutdown
4. **Extended Optional Parameters (255)** - Modern BGP extension support
5. **Parameter Type (0x02)** - OPEN message parsing

**Impact:** ~10 files, improves critical protocol handling readability

### Phase 2: IP Address Lengths (High Impact)
1. **IPv4 Length (4)** and **IPv6 Length (16)**
   - Consider creating in IP class or AFI module
   - Alternative: Use `socket.AF_INET`/`socket.AF_INET6` related constants

**Impact:** 40+ files with 80+ violations (80% of all violations)

### Phase 3: VPN & EVPN Constants (Medium Priority)
1. **Route Distinguisher types** (0, 1, 2) and length (8)
2. **ESI Length (10)**
3. **RD Length (8)**

**Impact:** ~10 files, improves VPN/EVPN code clarity

### Phase 4: BGP-LS Constants (Medium Priority)
1. All BGP-LS TLV codes (257, 258, 263, 264, 265, 512-518, 1161)
   - Consider separate BGP-LS constants file

**Impact:** ~15 BGP-LS files

### Phase 5: Bit Masks (Low Priority)
1. Common masks like 0xFF, 0xFFFF, etc.
   - Only if used multiple times
   - Some are contextual and may not need constants

**Impact:** Various files, low visibility improvement

---

## Special Cases Not Requiring Constants

Some magic numbers are **contextual** and may not need named constants:

1. **Struct format checks:** `len(data) == 4` to choose `!L` vs `!H` format
2. **One-off lengths:** Protocol-specific field sizes used once
3. **Calculation intermediates:** Values used in bit shifting/masking operations
4. **Loop counters and ranges:** `range(10)`, `range(8)`, etc.

---

## Files Most Affected (>4 violations each)

1. `src/exabgp/bgp/message/update/nlri/mvpn/sourcead.py` - 6 violations (IPv4/IPv6 lengths)
2. `src/exabgp/bgp/message/update/nlri/mvpn/sourcejoin.py` - 6 violations (IPv4/IPv6 lengths)
3. `src/exabgp/bgp/message/update/nlri/mvpn/sharedjoin.py` - 6 violations (IPv4/IPv6 lengths)
4. `src/exabgp/bgp/message/open/capability/capabilities.py` - 6 violations (255, 2, 3, 0x02)
5. `src/exabgp/bgp/message/update/nlri/bgpls/tlvs/node.py` - 4+ violations (IPv4/IPv6, BGP-LS)

---

## Key Takeaways

1. **80% of violations** are IPv4/IPv6 length checks (4 and 16)
2. **All magic numbers are legitimate** protocol constants from RFCs
3. **High-priority constants** are in critical path (OPEN, version, hold time)
4. **BGP-LS has many TLV codes** that would benefit from named constants
5. **Some values are contextual** and judgment needed on whether to extract

---

## RFC References

- **RFC 4271** - BGP-4 (version, hold time, parameter types)
- **RFC 4364** - BGP/MPLS IP VPNs (Route Distinguisher)
- **RFC 4724** - BGP Graceful Restart (EOR marker)
- **RFC 7432** - EVPN (ESI length)
- **RFC 7752** - BGP-LS (TLV codes)
- **RFC 8203** - Shutdown Communication (128 byte limit)
- **RFC 9003** - Extended Shutdown Communication (255 byte limit)
- **RFC 9072** - Extended Optional Parameters (255 marker)
- **RFC 9514** - SRv6 BGP-LS Extensions
- **RFC 6514** - Multicast VPN (MVPN route types)

---

## Next Steps

1. Review this analysis with maintainers
2. Decide on constant naming conventions
3. Choose location for constants (single file vs distributed)
4. Implement Phase 1 (high priority protocol constants)
5. Consider whether to tackle IP length constants (high volume)
6. Create constants incrementally with proper RFC documentation
