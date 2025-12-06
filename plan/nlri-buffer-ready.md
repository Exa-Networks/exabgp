# NLRI Buffer-Ready Architecture: On-Demand Field Access

**Status:** ✅ Phase 4 Complete
**Last Updated:** 2025-12-06
**Goal:** Prepare NLRI for memory sharing via Python buffer protocol by minimizing per-instance storage
**Approach:** Incremental phases, derive AFI from buffer for multi-family types

## Progress

### ✅ Phase 1: Single-Family NLRI Types (COMPLETED 2025-12-06)

Implemented class-level AFI/SAFI properties for:
- **EVPN** (`evpn/nlri.py`): l2vpn/evpn - uses `_class_afi`, `_class_safi` ClassVars
- **VPLS** (`vpls.py`): l2vpn/vpls - uses `_class_afi`, `_class_safi` ClassVars
- **RTC** (`rtc.py`): ipv4/rtc - uses `_class_afi`, `_class_safi` ClassVars

**Key pattern established:**
```python
class SingleFamilyNLRI(NLRI):
    _class_afi: ClassVar[AFI] = AFI.xxx
    _class_safi: ClassVar[SAFI] = SAFI.xxx

    def __init__(self, ...):
        # Skip Family.__init__ - afi/safi are class-level properties
        self.action = action
        self.addpath = PathInfo.DISABLED
        self._packed = b''
        # ... other init

    @property
    @final
    def afi(self) -> AFI:
        return self._class_afi

    @property
    @final
    def safi(self) -> SAFI:
        return self._class_safi
```

**Note:** BGPLS was NOT updated because it supports TWO SAFIs (bgp_ls and bgp_ls_vpn).

**Tests:** All 11 test suites pass (./qa/bin/test_everything)

### ✅ Phase 2: Family Base Class (COMPLETED 2025-12-06)

Modified `Family.__init__` to support class-level AFI/SAFI:
- Added `_class_afi: ClassVar[AFI | None] = None` and `_class_safi: ClassVar[SAFI | None] = None`
- `__init__` checks these values: if set, skips instance attribute assignment
- No `isinstance` checks - uses simple `None` check

### ✅ Phase 3: NLRI Base Class (COMPLETED 2025-12-06)

- Added documentation explaining the class-level AFI/SAFI pattern
- Consolidated `_create_invalid` + `_create_empty` → single `_create_singleton` method

### ✅ Phase 4: Multi-Family NLRI Types (COMPLETED 2025-12-06)

**Implemented:** Add class-level SAFI to Label and IPVPN

**Problem solved:** The configuration parser was mutating SAFI after NLRI creation.
This was incompatible with class-level SAFI properties.

**Solution implemented:**
1. `static/route.py:_normalize_nlri_type()` - Recreates NLRI with correct type based on
   actual RD/labels presence (IPVPN if RD, Label if labels, INET otherwise)
2. `flow/__init__.py` and `flow/route.py` - Same pattern for Flow NLRI with VPN RD
3. `Label` class has `_class_safi = SAFI.nlri_mpls` with property accessor
4. `IPVPN` class has `_class_safi = SAFI.mpls_vpn` with property accessor
5. Both classes have no-op SAFI setters for compatibility
6. `from_cidr()` ignores SAFI parameter, always uses class-level value

**Key pattern for multi-family types:**
```python
class Label(INET):
    _class_safi: ClassVar[SAFI] = SAFI.nlri_mpls

    @property
    @final
    def safi(self) -> SAFI:
        return self._class_safi

    @safi.setter
    def safi(self, value: SAFI) -> None:
        pass  # Ignore - SAFI is class-level

    @classmethod
    def from_cidr(cls, cidr, afi, safi=SAFI.nlri_mpls, ...):
        # safi parameter ignored - uses cls._class_safi
        instance = object.__new__(cls)
        NLRI.__init__(instance, afi, cls._class_safi, action)
        ...
```

**Configuration parser normalization:**
- Parser creates IPVPN (can hold all data: RD, labels, cidr)
- `_normalize_nlri_type()` checks `_rd_packed` and `_labels_packed`
- Recreates with correct type: IPVPN (has RD), Label (labels only), INET (neither)
- For INET, determines SAFI from IP range (multicast vs unicast via `IP.tosafi()`)

**Tests:** All 11 test suites pass (./qa/bin/test_everything)

### Key Finding: AFI Cannot Be Derived from Wire Data

Analysis showed that for INET and subclasses, AFI cannot be reliably derived from
packed wire data due to the IPv4/32 vs IPv6/32 ambiguity (both have identical wire format).
Multi-family types MUST continue to store AFI as an instance attribute.

## Context

The user wants to eventually use Python's `buffer` protocol for memory sharing across NLRI instances. This requires:
1. Minimal per-instance Python object storage
2. Data stored in contiguous byte buffers that can be shared/sliced
3. Fields computed on-demand from buffer data rather than stored separately

## Current State

**NLRI stores per-instance:**
- `afi: AFI` (4 bytes) - from Family base class
- `safi: SAFI` (4 bytes) - from Family base class
- `action: int` (4 bytes)
- `addpath: PathInfo` (8 bytes reference)
- `_packed: bytes` (8 bytes reference + data)

## Target Architecture

All metadata fields computed on-demand from `_packed` buffer or class-level constants.

## Implementation Phases

### Phase 1: Single-Family NLRI Types (Class-Level AFI/SAFI)

**Target classes** (hardcoded AFI/SAFI, no instance storage needed):

| Class | AFI | SAFI | File |
|-------|-----|------|------|
| EVPN | l2vpn | evpn | `evpn/nlri.py` |
| BGPLS | bgpls | bgp_ls | `bgpls/nlri.py` |
| VPLS | l2vpn | vpls | `vpls.py` |
| RTC | ipv4 | rtc | `rtc.py` |

**Changes:**
1. Add `_class_afi: ClassVar[AFI]` and `_class_safi: ClassVar[SAFI]`
2. Add `afi` and `safi` properties returning class-level values
3. Remove instance storage from `__init__`

### Phase 2: Family Base Class

**File:** `src/exabgp/protocol/family.py`

**Change:** Make `afi`/`safi` abstract properties instead of instance attributes

```python
class Family:
    @property
    def afi(self) -> AFI:
        raise NotImplementedError

    @property
    def safi(self) -> SAFI:
        raise NotImplementedError
```

### Phase 3: NLRI Base Class

**File:** `src/exabgp/bgp/message/update/nlri/nlri.py`

**Changes:**
1. Add class-level AFI/SAFI with property fallback
2. Update singletons (INVALID, EMPTY) to work with properties
3. Modify `@NLRI.register` to set class-level AFI/SAFI

```python
class NLRI(Family):
    _class_afi: ClassVar[AFI | None] = None
    _class_safi: ClassVar[SAFI | None] = None

    @property
    def afi(self) -> AFI:
        if self._class_afi is not None:
            return self._class_afi
        raise NotImplementedError("Multi-family NLRI must override afi")

    @property
    def safi(self) -> SAFI:
        if self._class_safi is not None:
            return self._class_safi
        raise NotImplementedError("Multi-family NLRI must override safi")
```

### Phase 4: Multi-Family NLRI Types (Buffer-Derived)

**Target classes** (multiple AFI/SAFI registrations):

| Class | Combinations | Derivation Strategy |
|-------|--------------|---------------------|
| INET | ipv4/ipv6 × unicast/multicast | AFI from mask (≤32 = ipv4), SAFI stored |
| Label | ipv4/ipv6 × nlri_mpls | AFI from mask, SAFI class-level |
| IPVPN | ipv4/ipv6 × mpls_vpn | AFI from mask, SAFI class-level |
| Flow | ipv4/ipv6 × flow_ip/flow_vpn | AFI from rule structure, SAFI stored |
| MUP | ipv4/ipv6 × mup | AFI derived, SAFI class-level |
| MVPN | ipv4/ipv6 × mcast_vpn | AFI derived, SAFI class-level |

**INET example:**
```python
class INET(NLRI):
    _class_safi: ClassVar[SAFI | None] = None  # Set by registration or stored
    _safi: SAFI | None = None  # Instance override for multicast

    @property
    def afi(self) -> AFI:
        # Derive from CIDR mask in _packed[0]
        mask = self._packed[0] if self._packed else 0
        return AFI.ipv4 if mask <= 32 else AFI.ipv6

    @property
    def safi(self) -> SAFI:
        if self._safi is not None:
            return self._safi
        if self._class_safi is not None:
            return self._class_safi
        return SAFI.unicast  # Default
```

### Phase 5: Action and PathInfo

**Action:** Store in compact form or derive from context
- During unpack: action comes from context (MP_REACH vs MP_UNREACH)
- During pack: action determines which attribute to use

**PathInfo:** Store path_id bytes in `_packed` prefix or separate `_path_id: bytes`

### Phase 6: Singletons

**NLRI.INVALID and NLRI.EMPTY:**
- Override properties to return `AFI.undefined` / `SAFI.undefined`
- Use special marker in `_packed` or check identity

## Files to Modify (in order)

1. `src/exabgp/protocol/family.py` - Abstract properties
2. `src/exabgp/bgp/message/update/nlri/nlri.py` - Base class pattern
3. `src/exabgp/bgp/message/update/nlri/evpn/nlri.py` - Single-family template
4. `src/exabgp/bgp/message/update/nlri/vpls.py` - Single-family
5. `src/exabgp/bgp/message/update/nlri/bgpls/nlri.py` - Single-family
6. `src/exabgp/bgp/message/update/nlri/rtc.py` - Single-family
7. `src/exabgp/bgp/message/update/nlri/inet.py` - Multi-family template
8. `src/exabgp/bgp/message/update/nlri/label.py` - Inherits INET
9. `src/exabgp/bgp/message/update/nlri/ipvpn.py` - Inherits Label
10. `src/exabgp/bgp/message/update/nlri/flow.py` - Multi-family
11. `src/exabgp/bgp/message/update/nlri/mup/nlri.py` - Multi-family
12. `src/exabgp/bgp/message/update/nlri/mvpn/nlri.py` - Multi-family

## Testing Strategy

After each phase:
1. Run `./qa/bin/test_everything`
2. Verify no regressions in encoding/decoding tests
3. Check that `nlri.afi` and `nlri.safi` access works everywhere

## Risks

1. **Performance:** Property access adds overhead on hot paths
   - Mitigation: Benchmark `__hash__` and `index` after Phase 1
2. **INET AFI derivation:** Mask ≤32 heuristic may fail for edge cases
   - Mitigation: Store explicit AFI byte in buffer prefix if needed
