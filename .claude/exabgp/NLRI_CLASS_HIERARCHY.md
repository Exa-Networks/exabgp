# NLRI Class Hierarchy Reference

This document maps the NLRI class inheritance structure, showing where class variables (ClassVar) and instance variables (__slots__) are defined. Use this when modifying `__init__` methods or refactoring NLRI classes.

---

## 🚨 NLRI Immutability Rule

**NLRI instances are IMMUTABLE after creation. NO SETTERS ALLOWED.**

- Never add property setters for NLRI fields
- Never assign to NLRI fields after creation
- Use factory methods with all values provided upfront

See `PACKED_BYTES_FIRST_PATTERN.md` for full rationale and migration guidance.

---

## Inheritance Diagram

```
Family (protocol/family.py)
  └── NLRI (nlri.py)
        ├── INET (inet.py)
        │     └── Label (label.py)
        │           └── IPVPN (ipvpn.py)
        ├── VPLS (vpls.py)
        ├── Flow (flow.py)
        ├── RTC (rtc.py)
        ├── EVPN (evpn/nlri.py)
        │     ├── MAC (evpn/mac.py)
        │     ├── EthernetAD (evpn/ethernetad.py)
        │     ├── Multicast (evpn/multicast.py)
        │     ├── EthernetSegment (evpn/segment.py)
        │     ├── Prefix (evpn/prefix.py)
        │     └── GenericEVPN (evpn/nlri.py)
        ├── MUP (mup/nlri.py)
        │     ├── InterworkSegmentDiscoveryRoute (mup/isd.py)
        │     ├── DirectSegmentDiscoveryRoute (mup/dsd.py)
        │     ├── Type1SessionTransformedRoute (mup/t1st.py)
        │     ├── Type2SessionTransformedRoute (mup/t2st.py)
        │     └── MalformedType1SessionTransformedRoute (mup/t1st.py, a withdrawal only)
        ├── MVPN (mvpn/nlri.py)
        │     ├── SourceAD (mvpn/sourcead.py)
        │     ├── SharedJoin (mvpn/sharedjoin.py)
        │     ├── SourceJoin (mvpn/sourcejoin.py)
        │     └── GenericMVPN (mvpn/nlri.py)
        └── BGPLS (bgpls/nlri.py)
              ├── NODE (bgpls/node.py)
              ├── LINK (bgpls/link.py)
              ├── PREFIXv4 (bgpls/prefixv4.py)
              ├── PREFIXv6 (bgpls/prefixv6.py)
              ├── SRv6SID (bgpls/srv6sid.py)
              └── GenericBGPLS (bgpls/nlri.py)
```

---

## Helper Classes (Non-NLRI)

```
CIDR (cidr.py)                    # IP prefix representation

NLRICollection (collection.py)    # Collection of NLRI for withdrawn routes
MPNLRICollection (collection.py)  # Collection of NLRI for MP_REACH/MP_UNREACH

Qualifier Classes (qualifier/):
  ├── RouteDistinguisher (rd.py)  # 8-byte RD
  ├── Labels (labels.py)          # MPLS label stack
  ├── PathInfo (path.py)          # ADD-PATH path identifier
  ├── ESI (esi.py)                # Ethernet Segment Identifier
  ├── EthernetTag (etag.py)       # EVPN Ethernet Tag
  └── MAC (mac.py)                # MAC address

Settings Classes (settings.py):
  ├── VPLSSettings                # VPLS configuration holder
  ├── INETSettings                # INET/Label/IPVPN configuration holder
  └── FlowSettings                # FlowSpec configuration holder
```

---

## Base Classes

### Family (`src/exabgp/protocol/family.py`)

```python
class Family:
    __slots__ = ('afi', 'safi')

    def __init__(self, afi: AFI, safi: SAFI):
        self.afi = afi
        self.safi = safi
```

### NLRI (`src/exabgp/bgp/message/update/nlri/nlri.py`)

```python
class NLRI(Family):
    __slots__ = ('addpath', '_packed')

    # Class Variables
    IS_EOR: ClassVar[bool] = False
    registered_nlri: ClassVar[dict[str, Type[NLRI]]] = {}
    registered_families: ClassVar[list[FamilyTuple]] = []
    INVALID: ClassVar[NLRI]  # Singleton
    EMPTY: ClassVar[NLRI]    # Singleton

    def __init__(self, afi: AFI, safi: SAFI, addpath: PathInfo = PathInfo.DISABLED):
        Family.__init__(self, afi, safi)
        self.addpath = addpath
        self._packed = b''  # Wire format bytes
```

**Key Points:**
- `_packed` stores wire format bytes (subclasses use this differently)
- `addpath` is PathInfo for RFC 7911 ADD-PATH
- **action** is NOT stored in NLRI - determined by RIB method (add_to_rib/del_from_rib)
- **nexthop** is NOT stored in NLRI - stored in Route, passed to methods as parameter

---

## INET Hierarchy

### INET (`src/exabgp/bgp/message/update/nlri/inet.py`)

```python
class INET(NLRI):
    __slots__ = ('_has_addpath', '_labels', '_rd')

    # Registered: AFI.ipv4/ipv6, SAFI.unicast/multicast

    def __init__(self, packed: Buffer, afi: AFI, safi: SAFI = SAFI.unicast, *, has_addpath: bool = False):
        NLRI.__init__(self, afi, safi)
        self._packed = packed  # Wire format: [addpath:4?][mask:1][prefix:var]
        self._has_addpath = has_addpath
        self._labels: Labels | None = None
        self._rd: RouteDistinguisher | None = None

    @property
    def path_info(self) -> PathInfo:
        """Extract PathInfo from wire bytes if AddPath present."""
        if not self._has_addpath:
            return PathInfo.DISABLED
        return PathInfo(self._packed[:4])

    @property
    def cidr(self) -> CIDR:
        """Unpack CIDR from stored wire format bytes."""
        offset = 4 if self._has_addpath else 0
        return CIDR.from_ipv4(self._packed[offset:])  # or from_ipv6
```

**Slot Storage:**
| Slot | Source | Description |
|------|--------|-------------|
| `afi` | Family | Address Family Identifier (private: `_afi`) |
| `safi` | Family | Subsequent AFI (private: `_safi`) |
| `addpath` | NLRI | ADD-PATH PathInfo (legacy, see `path_info` property) |
| `_packed` | NLRI | Wire bytes: [addpath?][mask][prefix] |
| `_has_addpath` | INET | Flag: _packed includes AddPath bytes |
| `_labels` | INET | Labels object or None (for subclasses) |
| `_rd` | INET | RouteDistinguisher or None (for subclasses) |

### Label (`src/exabgp/bgp/message/update/nlri/label.py`)

```python
class Label(INET):
    __slots__ = ('_has_labels',)

    # SAFI is fixed via property (always nlri_mpls)
    @property
    def safi(self) -> SAFI:
        return SAFI.nlri_mpls

    # Registered: AFI.ipv4/ipv6, SAFI.nlri_mpls

    def __init__(self, packed: Buffer, afi: AFI, *, has_addpath: bool = False, has_labels: bool = False):
        INET.__init__(self, packed, afi, self.safi, has_addpath=has_addpath)
        self._has_labels = has_labels

    @property
    def labels(self) -> Labels:
        """Get Labels from wire bytes by scanning for BOS bit."""
        if not self._has_labels:
            return Labels.NOLABEL
        # Scan _packed for label bytes, return Labels object
        ...
```

**Additional Slot:**
| Slot | Source | Description |
|------|--------|-------------|
| `_has_labels` | Label | Flag: _packed includes label bytes |

**Wire format:** `[addpath:4?][mask:1][labels:3n][prefix:var]`
Labels extracted lazily via `labels` property scanning for BOS bit.

### IPVPN (`src/exabgp/bgp/message/update/nlri/ipvpn.py`)

```python
class IPVPN(Label):
    __slots__ = ('_has_rd',)

    # SAFI is fixed via property (always mpls_vpn)
    @property
    def safi(self) -> SAFI:
        return SAFI.mpls_vpn

    # Registered: AFI.ipv4/ipv6, SAFI.mpls_vpn

    def __init__(self, packed: Buffer, afi: AFI, *, has_addpath: bool = False,
                 has_labels: bool = False, has_rd: bool = False):
        Label.__init__(self, packed, afi, has_addpath=has_addpath, has_labels=has_labels)
        self._has_rd = has_rd

    @property
    def rd(self) -> RouteDistinguisher:
        """Get Route Distinguisher from wire bytes."""
        if not self._has_rd:
            return RouteDistinguisher.NORD
        # Extract from _packed[label_end:label_end+8]
        ...
```

**Additional Slot:**
| Slot | Source | Description |
|------|--------|-------------|
| `_has_rd` | IPVPN | Flag: _packed includes RD bytes |

**Wire format:** `[addpath:4?][mask:1][labels:3n][rd:8?][prefix:var]`
RD extracted lazily via `rd` property.

---

## Single-Family NLRI Types

### VPLS (`src/exabgp/bgp/message/update/nlri/vpls.py`)

```python
class VPLS(NLRI):
    __slots__ = ()  # No additional slots - all data in _packed

    # Class Variables
    PACKED_LENGTH: int = 19  # Wire format length

    # Registered: AFI.l2vpn, SAFI.vpls (single family)

    def __init__(self, packed: Buffer):
        NLRI.__init__(self, AFI.l2vpn, SAFI.vpls)
        self._packed = bytes(packed)  # 19 bytes: [len(2)][RD(8)][endpoint(2)][offset(2)][size(2)][base(3)]
```

**Slot Storage:**
| Slot | Source | Description |
|------|--------|-------------|
| `afi` | Family | Always AFI.l2vpn (private: `_afi`) |
| `safi` | Family | Always SAFI.vpls (private: `_safi`) |
| `addpath` | NLRI | ADD-PATH PathInfo |
| `_packed` | NLRI | Complete wire format (19 bytes) |

**Properties (unpacked from `_packed`):**
- `rd` → bytes 2-10
- `endpoint` → bytes 10-12
- `offset` → bytes 12-14
- `block_size` → bytes 14-16
- `base` → bytes 16-19 (20-bit label)

### Flow (`src/exabgp/bgp/message/update/nlri/flow.py`)

```python
class Flow(NLRI):
    __slots__ = ('_rules_cache', '_packed_stale', '_rd_override')

    # Registered: AFI.ipv4/ipv6, SAFI.flow_ip/flow_vpn

    def __init__(self, packed: Buffer, afi: AFI, safi: SAFI):
        NLRI.__init__(self, afi, safi)
        self._packed = packed  # RD + rules (flow_vpn) or just rules (flow_ip)
        self._rules_cache = None  # Lazily parsed
        self._packed_stale = False  # True if rules modified
        self._rd_override = None  # Override RD for recomputation
```

**Slot Storage:**
| Slot | Source | Description |
|------|--------|-------------|
| `_rules_cache` | Flow | Lazily parsed rules dict |
| `_packed_stale` | Flow | Flag: rules modified, need repack |
| `_rd_override` | Flow | Override RD for builder mode |

**Two modes:**
- **Packed mode:** created from wire bytes, rules parsed lazily via `rules` property
- **Builder mode:** created empty, rules added via `add()`, _packed computed on pack

### RTC (`src/exabgp/bgp/message/update/nlri/rtc.py`)

```python
class RTC(NLRI):
    __slots__ = ('_packed_origin', 'rt')

    # Class Variables (class-level AFI/SAFI)
    afi: ClassVar[AFI] = AFI.ipv4
    safi: ClassVar[SAFI] = SAFI.rtc

    # Registered: AFI.ipv4, SAFI.rtc

    def __init__(self, packed_origin: bytes | None, rt: RouteTarget | None,
                 action: Action = Action.UNSET):
        NLRI.__init__(self, AFI.ipv4, SAFI.rtc, action)
        self._packed_origin = packed_origin  # 4 bytes ASN or None
        self.rt = rt
```

---

## EVPN Hierarchy

### EVPN Base (`src/exabgp/bgp/message/update/nlri/evpn/nlri.py`)

```python
class EVPN(NLRI):
    __slots__ = ()  # Empty - uses inherited slots

    # Class Variables
    registered_evpn: ClassVar[dict[int, type[EVPN]]] = {}
    HEADER_SIZE: int = 2  # type(1) + length(1)
    CODE: ClassVar[int] = -1  # Route type (override in subclass)
    NAME: ClassVar[str] = ''
    SHORT_NAME: ClassVar[str] = ''

    # Registered: AFI.l2vpn, SAFI.evpn

    def __init__(self, packed: bytes):
        # packed = type(1) + length(1) + payload(variable)
        self._packed = packed
        self.action = Action.UNSET
        self.nexthop = IP.NoNextHop
        self.addpath = PathInfo.DISABLED
```

### EVPN Subtypes

All EVPN subtypes share the same pattern:

```python
@EVPN.register_evpn_route
class MAC(EVPN):
    __slots__ = ()  # Empty
    CODE: ClassVar[int] = 2  # Route Type 2
    NAME: ClassVar[str] = 'MAC'
    SHORT_NAME: ClassVar[str] = 'MAC'

    # No __init__ - uses parent
```

**Properties (unpacked from `_packed`):**
- Each subtype defines properties to unpack specific fields
- MAC: `rd`, `esi`, `ethernet_tag`, `mac`, `ip`, `label`
- Multicast: `rd`, `ethernet_tag`, `ip`
- etc.

---

## MUP Hierarchy

### MUP Base (`src/exabgp/bgp/message/update/nlri/mup/nlri.py`)

```python
class MUP(NLRI):
    __slots__ = ()  # Empty

    # Class Variables
    registered_mup: ClassVar[dict[str, type[MUP]]] = {}  # "archtype:code" -> class
    ARCHTYPE: ClassVar[int] = 0
    CODE: ClassVar[int] = 0
    NAME: ClassVar[str] = ''
    SHORT_NAME: ClassVar[str] = ''

    # Registered: AFI.ipv4/ipv6, SAFI.mup

    def __init__(self, afi: AFI):
        NLRI.__init__(self, afi, SAFI.mup)
```

### MUP Subtypes

```python
@MUP.register_mup_route
class Type1SessionTransformedRoute(MUP):
    __slots__ = ('_packed',)  # Redeclares for subclass
    ARCHTYPE: ClassVar[int] = 1
    CODE: ClassVar[int] = 3
    NAME: ClassVar[str] = 'Type 1 Session Transformed'
    SHORT_NAME: ClassVar[str] = 't1st'

    def __init__(self, packed: bytes, afi: AFI):
        MUP.__init__(self, afi)
        self._packed = packed  # Wire format (no header)
```

### MalformedType1SessionTransformedRoute

A Type 1 ST route whose key (RD, prefix) is intact and whose 3gpp-5g part is malformed.
draft-mpmz-bess-mup-safi-05 3.1.3.1 makes it treat-as-withdraw, so it is only ever a
withdrawal: `withdrawn_on_receipt()` names the reason and UpdateCollection moves it out of
the announcements. Its `index()` is the well formed route's. There is no GenericMUP: a route
type exabgp does not know is ignored on receipt (3.1), as an NLRIDiscard.

---

## MVPN Hierarchy

### MVPN Base (`src/exabgp/bgp/message/update/nlri/mvpn/nlri.py`)

```python
class MVPN(NLRI):
    __slots__ = ()  # Empty

    # Class Variables
    registered_mvpn: ClassVar[dict[int, Type[MVPN]]] = {}
    CODE: ClassVar[int] = -1
    NAME: ClassVar[str] = ''
    SHORT_NAME: ClassVar[str] = ''

    # Registered: AFI.ipv4/ipv6, SAFI.mcast_vpn

    def __init__(self, afi: AFI):
        NLRI.__init__(self, afi, SAFI.mcast_vpn)
```

### MVPN Subtypes

```python
@MVPN.register_mvpn
class SharedJoin(MVPN):
    __slots__ = ()  # Empty
    CODE: ClassVar[int] = 6
    NAME: ClassVar[str] = 'SharedJoin'
    SHORT_NAME: ClassVar[str] = 'sharedjoin'

    def __init__(self, packed: Buffer, afi: AFI):
        MVPN.__init__(self, afi)
        self._packed = bytes(packed)
```

---

## BGP-LS Hierarchy

### BGPLS Base (`src/exabgp/bgp/message/update/nlri/bgpls/nlri.py`)

```python
class BGPLS(NLRI):
    __slots__ = ()  # Empty

    # Class Variables
    registered_bgpls: ClassVar[dict[int, Type[BGPLS]]] = {}
    CODE: ClassVar[int] = -1  # NLRI Type
    NAME: ClassVar[str] = ''
    SHORT_NAME: ClassVar[str] = ''

    # Registered: AFI.bgpls, SAFI.bgp_ls/bgp_ls_vpn
```

### BGPLS Subtypes

| Class | File | CODE | Description |
|-------|------|------|-------------|
| `NODE` | bgpls/node.py | 1 | Node NLRI |
| `LINK` | bgpls/link.py | 2 | Link NLRI |
| `PREFIXv4` | bgpls/prefixv4.py | 3 | IPv4 Prefix NLRI |
| `PREFIXv6` | bgpls/prefixv6.py | 4 | IPv6 Prefix NLRI |
| `SRv6SID` | bgpls/srv6sid.py | 6 | SRv6 SID NLRI |
| `GenericBGPLS` | bgpls/nlri.py | (dynamic) | Fallback for unknown types |

---

## Flow Component Classes

The Flow NLRI uses many component classes for FlowSpec rules (not part of NLRI hierarchy):

```
Flow Component Hierarchy (flow.py):

Base Classes:
  ├── FlowRule (Protocol)         # Typing protocol for flow rules
  ├── CommonOperator              # Base for numeric/binary operators
  │     ├── NumericOperator       # Numeric comparison operators
  │     └── BinaryOperator        # Binary/bitmask operators
  └── IComponent                  # Interface for flow components

Prefix Components:
  ├── IPrefix                     # Base prefix interface
  │     ├── IPrefix4 (+ IPv4)     # IPv4 prefix component
  │     │     ├── Flow4Destination
  │     │     └── Flow4Source
  │     └── IPrefix6 (+ IPv6)     # IPv6 prefix component
  │           ├── Flow6Destination
  │           └── Flow6Source

Operation Components:
  └── IOperation                  # Base operation interface
        ├── IOperationByte        # 1-byte values
        ├── IOperationByteShort   # 1-2 byte values
        └── IOperationByteShortLong  # 1-4 byte values

Concrete Flow Rules:
  ├── FlowIPProtocol (IPv4)       # IP Protocol field
  ├── FlowNextHeader (IPv6)       # Next Header field
  ├── FlowAnyPort                 # Source or Dest port
  ├── FlowDestinationPort         # Destination port
  ├── FlowSourcePort              # Source port
  ├── FlowICMPType                # ICMP type
  ├── FlowICMPCode                # ICMP code
  ├── FlowTCPFlag                 # TCP flags
  ├── FlowPacketLength            # Packet length
  ├── FlowDSCP (IPv4)             # DSCP field
  ├── FlowTrafficClass (IPv6)     # Traffic class
  ├── FlowFragment                # Fragment flags
  └── FlowFlowLabel (IPv6)        # Flow label
```

---

## Design Patterns

### 1. Packed-Bytes-First Pattern

Classes store complete or partial wire format in `_packed` to avoid repeated serialization:

```python
# VPLS: stores complete 19-byte wire format
self._packed = packed  # [len(2)][RD(8)][endpoint(2)][offset(2)][size(2)][base(3)]

# Properties unpack on demand
@property
def rd(self) -> RouteDistinguisher:
    return RouteDistinguisher.from_bytes(self._packed[2:10])
```

### 2. Single-Family with ClassVar AFI/SAFI

Some types define AFI/SAFI as ClassVar to shadow inherited slots:

```python
class Label(INET):
    safi: ClassVar[SAFI] = SAFI.nlri_mpls  # Shadows Family.safi slot
```

This makes `safi` effectively read-only at instance level.

### 3. Subclass Registration

All NLRI types use decorator-based registration:

```python
@NLRI.register(AFI.ipv4, SAFI.unicast)
class INET(NLRI):
    ...

@EVPN.register_evpn_route
class MAC(EVPN):
    CODE: ClassVar[int] = 2
```

### 4. Factory Methods

Preferred creation patterns:

```python
# From wire bytes (unpacking)
nlri = VPLS(packed_bytes)

# From components (encoding)
nlri = VPLS.make_vpls(rd=..., endpoint=..., base=..., offset=..., size=...)

# From validated settings (configuration)
nlri = VPLS.from_settings(settings)
```

### 5. Lazy Parsing

Complex data parsed on first access:

```python
@property
def rules(self) -> dict:
    if self._rules_cache is None:
        self._rules_cache = self._parse_rules(self._packed)
    return self._rules_cache
```

---

## Slot Inheritance Summary

| Class | Inherits Slots From | Adds Slots |
|-------|---------------------|------------|
| Family | - | `_afi`, `_safi` |
| NLRI | Family | `addpath`, `_packed` |
| INET | NLRI | `_has_addpath`, `_labels`, `_rd` |
| Label | INET | `_has_labels` |
| IPVPN | Label | `_has_rd` |
| VPLS | NLRI | (none) |
| Flow | NLRI | `_rules_cache`, `_packed_stale`, `_rd_override` |
| RTC | NLRI | `_packed_origin`, `rt` |
| EVPN | NLRI | (none) |
| EVPN subtypes | EVPN | (none) |
| GenericEVPN | EVPN | (none) - CODE via property |
| MUP | NLRI | (none) |
| MUP subtypes | MUP | (none) |
| MalformedType1SessionTransformedRoute | MUP | `_reason` |
| MVPN | NLRI | (none) |
| MVPN subtypes | MVPN | (none) |
| GenericMVPN | MVPN | (none) - CODE via property |
| BGPLS | NLRI | (none) |
| BGPLS subtypes | BGPLS | (none) |
| GenericBGPLS | BGPLS | `CODE` (instance attr, not slot) |

**Key changes from pre-refactor:**
- `action`/`nexthop` removed from NLRI - action determined by RIB method, nexthop in Route
- INET uses `_has_addpath` flag pattern, `path_info` is now a property
- Label/IPVPN use `_has_labels`/`_has_rd` flags instead of `_labels_packed`/`_rd_packed`
- VPLS no longer has `unique` slot

---

## When Modifying __init__

1. **Check slot inheritance chain** - Know which slots come from which parent
2. **Call parent __init__ or set slots manually** - Some classes skip parent __init__ for efficiency
3. **Initialize all local slots** - Uninitialized slots cause AttributeError
4. **Consider ClassVar shadows** - Some classes shadow slots with ClassVar (e.g., Label.safi)
5. **Handle `_packed` appropriately** - Most classes expect wire format bytes

---

**Updated:** 2025-12-19
