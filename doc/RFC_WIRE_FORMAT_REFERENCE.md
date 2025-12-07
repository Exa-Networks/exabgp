# RFC Wire Format Reference for NLRI Implementation

Quick reference for wire format details needed when working on NLRI classes.

---

## Common Building Blocks

### Route Distinguisher (RFC 4364 Section 4.2)

**Size:** 8 bytes (2-byte type + 6-byte value)

```
+-----------------------------------+
|    Type (2 octets)                |
+-----------------------------------+
|    Value (6 octets)               |
+-----------------------------------+
```

**Types:**
| Type | Administrator | Assigned Number | Example |
|------|---------------|-----------------|---------|
| 0 | 2-byte ASN | 4-byte number | `0:65000:12345` |
| 1 | 4-byte IPv4 | 2-byte number | `1:192.0.2.1:100` |
| 2 | 4-byte ASN | 2-byte number | `2:4200000001:100` |

**Code location:** `nlri/qualifier/rd.py`

---

### Path Identifier / ADD-PATH (RFC 7911)

**Size:** 4 bytes, prepended to NLRI

```
+-----------------------------------+
|    Path Identifier (4 octets)     |
+-----------------------------------+
|    Length (1 octet)               |
+-----------------------------------+
|    Prefix (variable)              |
+-----------------------------------+
```

**Rules:**
- Path ID is locally assigned, no semantic meaning
- (Prefix, Path ID) must be unique per neighbor
- Capability code 69, negotiated per AFI/SAFI

**Code location:** `nlri/qualifier/path.py`

---

### MPLS Labels (RFC 3107, RFC 8277)

**Size:** 3 bytes per label

```
+-----------------------------------+
|    Label (20 bits)                |
+-----------------------------------+
|    TC (3 bits) | S (1) | TTL (8)  |
+-----------------------------------+
```

**Encoding:**
- Label value in top 20 bits
- S (Bottom of Stack) bit: 1 = last label
- When encoding: `(label << 4) | (bos ? 1 : 0)`

**Code location:** `nlri/qualifier/labels.py`

---

### Ethernet Segment Identifier (RFC 7432 Section 5)

**Size:** 10 bytes

```
+-----------------------------------+
|    ESI Type (1 octet)             |
+-----------------------------------+
|    ESI Value (9 octets)           |
+-----------------------------------+
```

**ESI Types:**
| Type | Description |
|------|-------------|
| 0 | Arbitrary (operator configured) |
| 1 | LACP-based |
| 2 | L2 bridge protocol based |
| 3 | MAC-based |
| 4 | Router-ID based |
| 5 | AS-based |

**Special values:**
- `00:00:00:00:00:00:00:00:00:00` = Single-homed (MAX-ET)

**Code location:** `nlri/qualifier/esi.py`

---

## EVPN (RFC 7432)

**AFI/SAFI:** 25 (L2VPN) / 70 (EVPN)

### NLRI Header
```
+-----------------------------------+
|    Route Type (1 octet)           |
+-----------------------------------+
|    Length (1 octet)               |
+-----------------------------------+
|    Route Type specific (variable) |
+-----------------------------------+
```

### Type 1: Ethernet Auto-Discovery
```
+-----------------------------------+
|    RD (8 octets)                  |
+-----------------------------------+
|    ESI (10 octets)                |
+-----------------------------------+
|    Ethernet Tag ID (4 octets)     |
+-----------------------------------+
|    MPLS Label (3 octets)          |
+-----------------------------------+
```
**Length:** 25 bytes (without label) or 28 bytes (with label)
**Code:** `evpn/ethernetad.py`

### Type 2: MAC/IP Advertisement
```
+-----------------------------------+
|    RD (8 octets)                  |
+-----------------------------------+
|    ESI (10 octets)                |
+-----------------------------------+
|    Ethernet Tag ID (4 octets)     |
+-----------------------------------+
|    MAC Address Length (1 octet)   |  Always 48 (bits)
+-----------------------------------+
|    MAC Address (6 octets)         |
+-----------------------------------+
|    IP Address Length (1 octet)    |  0, 32, or 128 (bits)
+-----------------------------------+
|    IP Address (0, 4, or 16 oct)   |
+-----------------------------------+
|    MPLS Label 1 (3 octets)        |
+-----------------------------------+
|    MPLS Label 2 (0 or 3 octets)   |  Optional, for IP-VRF
+-----------------------------------+
```
**Length:** Variable (33-59 bytes depending on IP and labels)
**Code:** `evpn/mac.py`

### Type 3: Inclusive Multicast Ethernet Tag
```
+-----------------------------------+
|    RD (8 octets)                  |
+-----------------------------------+
|    Ethernet Tag ID (4 octets)     |
+-----------------------------------+
|    IP Address Length (1 octet)    |  32 or 128 (bits)
+-----------------------------------+
|    Originating Router IP (4/16)   |
+-----------------------------------+
```
**Length:** 17 (IPv4) or 29 (IPv6) bytes
**Code:** `evpn/multicast.py`

### Type 4: Ethernet Segment
```
+-----------------------------------+
|    RD (8 octets)                  |
+-----------------------------------+
|    ESI (10 octets)                |
+-----------------------------------+
|    IP Address Length (1 octet)    |  32 or 128 (bits)
+-----------------------------------+
|    Originating Router IP (4/16)   |
+-----------------------------------+
```
**Length:** 23 (IPv4) or 35 (IPv6) bytes
**Code:** `evpn/segment.py`

### Type 5: IP Prefix (RFC 9136)
```
+-----------------------------------+
|    RD (8 octets)                  |
+-----------------------------------+
|    ESI (10 octets)                |
+-----------------------------------+
|    Ethernet Tag ID (4 octets)     |
+-----------------------------------+
|    IP Prefix Length (1 octet)     |  In bits
+-----------------------------------+
|    IP Prefix (4 or 16 octets)     |
+-----------------------------------+
|    GW IP Address (4 or 16 octets) |
+-----------------------------------+
|    MPLS Label (3 octets)          |
+-----------------------------------+
```
**Code:** `evpn/prefix.py`

---

## MVPN (RFC 6514)

**AFI/SAFI:** 1 (IPv4) or 2 (IPv6) / 5 (MCAST-VPN)

### NLRI Header
```
+-----------------------------------+
|    Route Type (1 octet)           |
+-----------------------------------+
|    Length (1 octet)               |
+-----------------------------------+
|    Route Type specific (variable) |
+-----------------------------------+
```

### Type 1: Intra-AS I-PMSI A-D (not implemented)
```
+-----------------------------------+
|    RD (8 octets)                  |
+-----------------------------------+
|    Originating Router IP (4/16)   |
+-----------------------------------+
```

### Type 3: S-PMSI A-D (SourceAD)
```
+-----------------------------------+
|    RD (8 octets)                  |
+-----------------------------------+
|    Multicast Source Length (1)    |  In bits (32 or 128)
+-----------------------------------+
|    Multicast Source (4 or 16)     |
+-----------------------------------+
|    Multicast Group Length (1)     |  In bits (32 or 128)
+-----------------------------------+
|    Multicast Group (4 or 16)      |
+-----------------------------------+
|    Originating Router IP (4/16)   |
+-----------------------------------+
```
**Code:** `mvpn/sourcead.py`

### Type 6: Shared Tree Join (SharedJoin)
```
+-----------------------------------+
|    RD (8 octets)                  |
+-----------------------------------+
|    Source AS (4 octets)           |
+-----------------------------------+
|    Multicast Group Length (1)     |  In bits
+-----------------------------------+
|    Multicast Group (4 or 16)      |
+-----------------------------------+
```
**Length:** 17 (IPv4) or 29 (IPv6) bytes
**Code:** `mvpn/sharedjoin.py`

### Type 7: Source Tree Join (SourceJoin)
```
+-----------------------------------+
|    RD (8 octets)                  |
+-----------------------------------+
|    Source AS (4 octets)           |
+-----------------------------------+
|    Multicast Source Length (1)    |  In bits
+-----------------------------------+
|    Multicast Source (4 or 16)     |
+-----------------------------------+
|    Multicast Group Length (1)     |  In bits
+-----------------------------------+
|    Multicast Group (4 or 16)      |
+-----------------------------------+
```
**Length:** 22 (IPv4) or 46 (IPv6) bytes
**Code:** `mvpn/sourcejoin.py`

---

## BGP-LS (RFC 7752 / RFC 9552)

**AFI/SAFI:** 16388 (BGP-LS) / 71 (BGP-LS) or 72 (BGP-LS-VPN)

### NLRI Header
```
+-----------------------------------+
|    NLRI Type (2 octets)           |
+-----------------------------------+
|    Total NLRI Length (2 octets)   |
+-----------------------------------+
|    NLRI Value (variable)          |
+-----------------------------------+
```

**NLRI Types:**
| Type | Description | Code |
|------|-------------|------|
| 1 | Node NLRI | `bgpls/node.py` |
| 2 | Link NLRI | `bgpls/link.py` |
| 3 | IPv4 Topology Prefix | `bgpls/prefixv4.py` |
| 4 | IPv6 Topology Prefix | `bgpls/prefixv6.py` |
| 6 | SRv6 SID NLRI | `bgpls/srv6sid.py` |

### Type 1: Node NLRI
```
+-----------------------------------+
|    Protocol-ID (1 octet)          |
+-----------------------------------+
|    Identifier (8 octets)          |
+-----------------------------------+
|    Local Node Descriptors (var)   |
+-----------------------------------+
```

**Protocol-ID Values:**
| ID | Protocol |
|----|----------|
| 1 | IS-IS Level 1 |
| 2 | IS-IS Level 2 |
| 3 | OSPFv2 |
| 4 | Direct |
| 5 | Static |
| 6 | OSPFv3 |
| 7 | BGP |

### Type 2: Link NLRI
```
+-----------------------------------+
|    Protocol-ID (1 octet)          |
+-----------------------------------+
|    Identifier (8 octets)          |
+-----------------------------------+
|    Local Node Descriptors (var)   |
+-----------------------------------+
|    Remote Node Descriptors (var)  |
+-----------------------------------+
|    Link Descriptors (var)         |
+-----------------------------------+
```

### TLV Format (used throughout BGP-LS)
```
+-----------------------------------+
|    Type (2 octets)                |
+-----------------------------------+
|    Length (2 octets)              |
+-----------------------------------+
|    Value (variable)               |
+-----------------------------------+
```

**Key TLV Types:**
| Type | Name | Used In |
|------|------|---------|
| 256 | Local Node Descriptor | Node, Link, Prefix |
| 257 | Remote Node Descriptor | Link |
| 258 | Link Local/Remote ID | Link |
| 259 | IPv4 Interface Address | Link |
| 260 | IPv4 Neighbor Address | Link |
| 261 | IPv6 Interface Address | Link |
| 262 | IPv6 Neighbor Address | Link |
| 264 | Multi-Topology ID | Link, Prefix |
| 265 | OSPF Route Type | Prefix |
| 266 | IP Reachability Info | Prefix |
| 512 | Autonomous System | Node Descriptor |
| 513 | BGP-LS Identifier | Node Descriptor |
| 514 | OSPF Area-ID | Node Descriptor |
| 515 | IGP Router-ID | Node Descriptor |

**Code location:** `bgpls/tlvs/`

---

## MUP (draft-mpmz-bess-mup-safi)

**AFI/SAFI:** 1 (IPv4) or 2 (IPv6) / 69 (MUP)

### NLRI Header
```
+-----------------------------------+
|    Architecture Type (1 octet)    |
+-----------------------------------+
|    Route Type (2 octets)          |
+-----------------------------------+
|    Length (1 octet)               |
+-----------------------------------+
|    Route Type specific (variable) |
+-----------------------------------+
```

**Architecture Type 1 = 3GPP-5G**

**Route Types:**
| Type | Name | Code |
|------|------|------|
| 1 | Interwork Segment Discovery (ISD) | `mup/isd.py` |
| 2 | Direct Segment Discovery (DSD) | `mup/dsd.py` |
| 3 | Type 1 Session Transformed (T1ST) | `mup/t1st.py` |
| 4 | Type 2 Session Transformed (T2ST) | `mup/t2st.py` |

**Note:** MPLS labels for MUP are NOT in NLRI. Use MUP Extended Community (type 0x0c).

---

## VPLS (RFC 4761)

**AFI/SAFI:** 25 (L2VPN) / 65 (VPLS)

### NLRI Format
```
+-----------------------------------+
|    Length (2 octets)              |  Always 17
+-----------------------------------+
|    RD (8 octets)                  |
+-----------------------------------+
|    VE ID (2 octets)               |
+-----------------------------------+
|    Label Block Offset (2 octets)  |
+-----------------------------------+
|    Label Block Size (2 octets)    |
+-----------------------------------+
|    Label Base (3 octets)          |
+-----------------------------------+
```

**Total size:** 19 bytes (2 length + 17 content)
**Code:** `nlri/vpls.py`

---

## FlowSpec (RFC 5575, RFC 8955)

**AFI/SAFI:**
- IPv4: 1/133 (FlowSpec) or 1/134 (FlowSpec VPN)
- IPv6: 2/133 or 2/134

### NLRI Format
```
+-----------------------------------+
|    Length (1-2 octets)            |  1 if <240, 2 if >=240
+-----------------------------------+
|    FlowSpec Components (variable) |
+-----------------------------------+
```

**Component Types:**
| Type | Name | Matches |
|------|------|---------|
| 1 | Destination Prefix | dst IP |
| 2 | Source Prefix | src IP |
| 3 | IP Protocol | protocol field |
| 4 | Port | src or dst port |
| 5 | Destination Port | dst port |
| 6 | Source Port | src port |
| 7 | ICMP Type | ICMP type |
| 8 | ICMP Code | ICMP code |
| 9 | TCP Flags | TCP flags |
| 10 | Packet Length | total length |
| 11 | DSCP | DSCP field |
| 12 | Fragment | fragment flags |

**Code:** `nlri/flow.py`

---

## RTC - Route Target Constraint (RFC 4684)

**AFI/SAFI:** 1 (IPv4) / 132 (RTC)

### NLRI Format
```
+-----------------------------------+
|    Origin AS (4 octets)           |
+-----------------------------------+
|    Route Target (8 octets)        |
+-----------------------------------+
```

**Total size:** 12 bytes
**Code:** `nlri/rtc.py`

---

## Path Attributes (RFC 4271)

Path attributes are carried in UPDATE messages. Each attribute has a header followed by value.

### Attribute Header Format
```
+-----------------------------------+
|    Attr. Flags (1 octet)          |
+-----------------------------------+
|    Attr. Type Code (1 octet)      |
+-----------------------------------+
|    Attr. Length (1 or 2 octets)   |  2 if Extended Length flag set
+-----------------------------------+
|    Attr. Value (variable)         |
+-----------------------------------+
```

**Attribute Flags (bit positions):**
| Bit | Name | Meaning when set |
|-----|------|------------------|
| 0 (0x80) | Optional | Attribute is optional (vs well-known) |
| 1 (0x40) | Transitive | Should be passed to other BGP peers |
| 2 (0x20) | Partial | Incomplete (optional transitive not recognized) |
| 3 (0x10) | Extended Length | Length field is 2 octets |

### Well-Known Mandatory Attributes

| Code | Name | Length | Format | RFC |
|------|------|--------|--------|-----|
| 1 | ORIGIN | 1 | 0=IGP, 1=EGP, 2=INCOMPLETE | RFC 4271 |
| 2 | AS_PATH | var | Segments of AS numbers | RFC 4271 |
| 3 | NEXT_HOP | 4 | IPv4 address | RFC 4271 |

**Code:** `attribute/origin.py`, `attribute/aspath.py`, `attribute/nexthop.py`

### Well-Known Discretionary

| Code | Name | Length | Format | RFC |
|------|------|--------|--------|-----|
| 4 | MULTI_EXIT_DISC | 4 | 32-bit metric | RFC 4271 |
| 5 | LOCAL_PREF | 4 | 32-bit preference | RFC 4271 |
| 6 | ATOMIC_AGGREGATE | 0 | Flag only (no value) | RFC 4271 |
| 7 | AGGREGATOR | 6/8 | ASN (2/4) + IPv4 | RFC 4271 |

**Code:** `attribute/med.py`, `attribute/localpref.py`, `attribute/aggregator.py`

### Optional Transitive

| Code | Name | Length | Format | RFC |
|------|------|--------|--------|-----|
| 8 | COMMUNITY | 4*n | List of 4-byte communities | RFC 1997 |
| 9 | ORIGINATOR_ID | 4 | Router ID (route reflector) | RFC 4456 |
| 10 | CLUSTER_LIST | 4*n | List of cluster IDs | RFC 4456 |
| 16 | EXTENDED_COMMUNITY | 8*n | List of ext communities | RFC 4360 |
| 17 | AS4_PATH | var | 4-byte AS path | RFC 6793 |
| 18 | AS4_AGGREGATOR | 8 | 4-byte ASN + IPv4 | RFC 6793 |
| 32 | LARGE_COMMUNITY | 12*n | List of large communities | RFC 8092 |

**Code:** `attribute/community/`, `attribute/originatorid.py`, `attribute/clusterlist.py`

### Optional Non-Transitive

| Code | Name | Length | Format | RFC |
|------|------|--------|--------|-----|
| 14 | MP_REACH_NLRI | var | AFI/SAFI + Next Hop + NLRI | RFC 4760 |
| 15 | MP_UNREACH_NLRI | var | AFI/SAFI + Withdrawn NLRI | RFC 4760 |
| 22 | PMSI_TUNNEL | var | Tunnel type + label + ID | RFC 6514 |
| 26 | AIGP | var | AIGP TLVs | RFC 7311 |
| 29 | BGP-LS | var | Link-state TLVs | RFC 7752 |
| 40 | PREFIX_SID | var | SR Prefix SID TLVs | RFC 8669 |

**Code:** `attribute/mprnlri.py`, `attribute/mpurnlri.py`, `attribute/pmsi.py`, `attribute/aigp.py`

---

## Community Types

### Standard Community (RFC 1997)

**Size:** 4 bytes

```
+-----------------------------------+
|    High (2 octets)                |  Typically ASN
+-----------------------------------+
|    Low (2 octets)                 |  Value
+-----------------------------------+
```

**Well-known communities:**
| Value | Name |
|-------|------|
| 0xFFFFFF01 | NO_EXPORT |
| 0xFFFFFF02 | NO_ADVERTISE |
| 0xFFFFFF03 | NO_EXPORT_SUBCONFED |
| 0xFFFFFF04 | NOPEER |

**Code:** `attribute/community/initial/`

### Extended Community (RFC 4360)

**Size:** 8 bytes

```
+-----------------------------------+
|    Type (1 octet)                 |  High bit = IANA/transitive
+-----------------------------------+
|    Sub-Type (1 octet)             |
+-----------------------------------+
|    Value (6 octets)               |
+-----------------------------------+
```

**Common Types:**
| Type | Sub-Type | Name | Code |
|------|----------|------|------|
| 0x00 | 0x02 | Route Target (2-byte ASN) | `extended/rt.py` |
| 0x01 | 0x02 | Route Target (IPv4) | `extended/rt.py` |
| 0x02 | 0x02 | Route Target (4-byte ASN) | `extended/rt.py` |
| 0x00 | 0x03 | Route Origin | `extended/origin.py` |
| 0x03 | 0x0c | Encapsulation | `extended/encapsulation.py` |
| 0x06 | 0x00 | MAC Mobility | `extended/mac_mobility.py` |
| 0x80 | 0x06 | FlowSpec Traffic Rate | `extended/traffic.py` |
| 0x80 | 0x07 | FlowSpec Traffic Action | `extended/traffic.py` |
| 0x80 | 0x08 | FlowSpec Redirect | `extended/traffic.py` |
| 0x80 | 0x09 | FlowSpec Traffic Mark | `extended/traffic.py` |

**Code:** `attribute/community/extended/`

### Large Community (RFC 8092)

**Size:** 12 bytes

```
+-----------------------------------+
|    Global Administrator (4 oct)   |  Typically 4-byte ASN
+-----------------------------------+
|    Local Data Part 1 (4 octets)   |
+-----------------------------------+
|    Local Data Part 2 (4 octets)   |
+-----------------------------------+
```

**Code:** `attribute/community/large/`

---

## Segment Routing Attributes

### Prefix-SID Attribute (RFC 8669)

**Attribute Code:** 40

```
+-----------------------------------+
|    TLV Type (1 octet)             |
+-----------------------------------+
|    TLV Length (2 octets)          |
+-----------------------------------+
|    TLV Value (variable)           |
+-----------------------------------+
```

**TLV Types:**
| Type | Name | Code |
|------|------|------|
| 1 | Label-Index | `sr/labelindex.py` |
| 3 | Originator SRGB | `sr/srgb.py` |
| 5 | SRv6 L3 Service | `sr/srv6/l3service.py` |
| 6 | SRv6 L2 Service | `sr/srv6/l2service.py` |

**Code:** `attribute/sr/`

### SRv6 SID Information Sub-TLV

```
+-----------------------------------+
|    SRv6 SID (16 octets)           |
+-----------------------------------+
|    SID Flags (1 octet)            |
+-----------------------------------+
|    Endpoint Behavior (2 octets)   |
+-----------------------------------+
|    Sub-Sub-TLVs (variable)        |
+-----------------------------------+
```

**Code:** `attribute/sr/srv6/`

---

## BGP-LS Attribute TLVs (RFC 7752)

**Attribute Code:** 29

BGP-LS uses the same TLV format as NLRI (2-byte type, 2-byte length).

### Node Attribute TLVs

| TLV | Name | Length | Code |
|-----|------|--------|------|
| 263 | Multi-Topology ID | var | - |
| 1024 | Node Flags | 1 | `bgpls/node/nodeflags.py` |
| 1025 | Opaque Node Attribute | var | `bgpls/node/opaque.py` |
| 1026 | Node Name | var | `bgpls/node/nodename.py` |
| 1027 | IS-IS Area ID | var | `bgpls/node/isisarea.py` |
| 1028 | IPv4 Router-ID Local | 4 | `bgpls/node/lterid.py` |
| 1029 | IPv6 Router-ID Local | 16 | `bgpls/node/lterid.py` |
| 1034 | SR Capabilities | var | `bgpls/node/srcap.py` |
| 1035 | SR Algorithm | var | `bgpls/node/sralgo.py` |

### Link Attribute TLVs

| TLV | Name | Length | Code |
|-----|------|--------|------|
| 1028 | IPv4 Router-ID Local | 4 | - |
| 1030 | IPv4 Router-ID Remote | 4 | `bgpls/link/rterid.py` |
| 1088 | Admin Group | 4 | `bgpls/link/admingroup.py` |
| 1089 | Max Link Bandwidth | 4 | `bgpls/link/maxbw.py` |
| 1090 | Max Reservable BW | 4 | `bgpls/link/rsvpbw.py` |
| 1091 | Unreserved BW | 32 | `bgpls/link/unrsvpbw.py` |
| 1092 | TE Default Metric | 4 | `bgpls/link/temetric.py` |
| 1093 | Link Protection Type | 2 | `bgpls/link/protection.py` |
| 1094 | MPLS Protocol Mask | 1 | `bgpls/link/mplsmask.py` |
| 1095 | IGP Metric | var | `bgpls/link/igpmetric.py` |
| 1096 | SRLG | var | `bgpls/link/srlg.py` |
| 1098 | Link Name | var | `bgpls/link/linkname.py` |
| 1099 | SR Adjacency SID | var | `bgpls/link/sradj.py` |
| 1100 | SR LAN Adjacency SID | var | `bgpls/link/sradjlan.py` |

### Prefix Attribute TLVs

| TLV | Name | Length | Code |
|-----|------|--------|------|
| 1152 | IGP Flags | 1 | `bgpls/prefix/igpflags.py` |
| 1153 | IGP Route Tag | 4*n | `bgpls/prefix/igptags.py` |
| 1154 | IGP Extended Route Tag | 8*n | `bgpls/prefix/igpextags.py` |
| 1155 | Prefix Metric | 4 | `bgpls/prefix/prefixmetric.py` |
| 1156 | OSPF Forwarding Addr | 4 | `bgpls/prefix/ospfaddr.py` |
| 1157 | Opaque Prefix Attribute | var | `bgpls/prefix/opaque.py` |
| 1158 | SR Prefix SID | var | `bgpls/prefix/srprefix.py` |
| 1170 | SR IGP Prefix Attributes | var | `bgpls/prefix/srigpprefixattr.py` |
| 1171 | SR Source Router-ID | var | `bgpls/prefix/srrid.py` |

---

## Quick Validation Rules

### Length Fields
- **EVPN/MVPN Length:** In bytes, excludes Route Type and Length fields
- **IP Address Length:** Always in **bits** (32=IPv4, 128=IPv6)
- **Prefix Length:** Always in **bits**
- **MAC Address Length:** Always 48 (bits) = 6 bytes

### Byte Order
- All multi-byte fields are **big-endian** (network byte order)
- Use `struct.pack('!...')` for encoding

### Common Mistakes
1. Forgetting IP length is in bits, not bytes
2. Wrong label encoding (remember S bit)
3. Missing ESI for single-homed (should be all zeros)
4. Incorrect RD type byte order

---

## Sources

**Core BGP:**
- [RFC 4271 - BGP-4](https://datatracker.ietf.org/doc/html/rfc4271)
- [RFC 4760 - Multiprotocol BGP](https://datatracker.ietf.org/doc/html/rfc4760)
- [RFC 7911 - ADD-PATH](https://datatracker.ietf.org/doc/html/rfc7911)

**VPN/MPLS:**
- [RFC 4364 - BGP/MPLS IP VPNs](https://datatracker.ietf.org/doc/html/rfc4364)
- [RFC 4761 - VPLS using BGP](https://datatracker.ietf.org/doc/html/rfc4761)
- [RFC 6514 - MVPN](https://datatracker.ietf.org/doc/html/rfc6514)
- [RFC 7432 - EVPN](https://datatracker.ietf.org/doc/html/rfc7432)
- [RFC 9136 - EVPN IP Prefix](https://datatracker.ietf.org/doc/html/rfc9136)

**Communities:**
- [RFC 1997 - BGP Communities](https://datatracker.ietf.org/doc/html/rfc1997)
- [RFC 4360 - Extended Communities](https://datatracker.ietf.org/doc/html/rfc4360)
- [RFC 8092 - Large Communities](https://datatracker.ietf.org/doc/html/rfc8092)

**Link-State/SR:**
- [RFC 7752 - BGP-LS](https://datatracker.ietf.org/doc/html/rfc7752)
- [RFC 9552 - BGP-LS (obsoletes 7752)](https://datatracker.ietf.org/doc/html/rfc9552)
- [RFC 8669 - Segment Routing Prefix-SID](https://datatracker.ietf.org/doc/html/rfc8669)
- [RFC 9514 - BGP-LS for SRv6](https://datatracker.ietf.org/doc/html/rfc9514)

**FlowSpec/Other:**
- [RFC 5575 - FlowSpec](https://datatracker.ietf.org/doc/html/rfc5575)
- [RFC 7311 - AIGP](https://datatracker.ietf.org/doc/html/rfc7311)
- [draft-mpmz-bess-mup-safi - MUP](https://datatracker.ietf.org/doc/draft-mpmz-bess-mup-safi/)

---

**Updated:** 2025-12-07
