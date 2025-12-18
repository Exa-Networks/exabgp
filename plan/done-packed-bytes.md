# BGP Class Refactoring: Packed-Bytes-First Pattern

**Status:** ✅ Complete
**Completion:** 100% (~124 classes converted)

---

## Goal

Refactor ALL BGP classes to packed-bytes-first pattern:
- `__init__(self, packed: bytes)` - ONLY takes packed wire-format data
- `@classmethod def make_TYPE(cls, ...)` - Factory methods for semantic construction
- `@property` decorators for accessing unpacked data

---

## Summary Statistics

| Wave | Category | Done | N/A | Total |
|------|----------|------|-----|-------|
| 1 | Simple Attributes | 4 | 0 | 4 |
| 2 | Complex Attributes | 10 | 1 | 11 |
| 3 | Community Attributes | ~20 | 0 | ~20 |
| 4 | MP/SR/BGP-LS Attributes | ~50 | 3 | ~53 |
| 5 | Qualifiers | 5 | 0 | 5 |
| 6 | NLRI Types | 9 | 0 | 9 |
| 7 | EVPN/BGP-LS/MUP/MVPN NLRI | ~20 | 0 | ~20 |
| 8 | Messages | 6 | 0 | 6 |
| **TOTAL** | | **~124** | **4** | **~128** |

---

## Target Pattern

```python
@Attribute.register()
class Origin(Attribute):
    def __init__(self, packed: bytes) -> None:
        if len(packed) != 1:
            raise ValueError(f'Origin requires 1 byte')
        self._packed = packed

    @classmethod
    def make_origin(cls, origin: int) -> 'Origin':
        return cls(bytes([origin]))

    @property
    def origin(self) -> int:
        return self._packed[0]
```

---

## Special Cases Handled

### 1. NLRI Metadata
NLRI has metadata NOT in wire format (action, path_info, nexthop):
```python
def __init__(self, packed: bytes, afi: AFI, safi: SAFI,
             action: Action = Action.UNSET, ...) -> None:
```

### 2. MPRNLRI/MPURNLRI Hybrid Pattern
Container attributes with lazy NLRI parsing:
- `_MODE_PACKED` - Created from wire bytes
- `_MODE_NLRIS` - Created from NLRI list
- `nlris` property parses lazily with caching

### 3. Flow NLRI Builder Pattern
Flow uses builder pattern - rules added via `add()`:
- `_packed_stale` flag marks when recomputation needed
- `_rules_cache` for lazy parsing

### 4. Singletons
Keep existing `_create_invalid()` pattern:
```python
NLRI.INVALID = NLRI._create_invalid()  # Uses object.__new__()
```

---

## Completed Waves

### Wave 1-2: Simple + Complex Attributes ✅
Origin, MED, LocalPreference, AtomicAggregate, ASPath, NextHop, Aggregator, ClusterList, OriginatorId, GenericAttribute, AIGP, PMSI

### Wave 3: Community Attributes ✅
Community, Communities, LargeCommunity, ExtendedCommunity, RouteTarget, Bandwidth, Encapsulation, MacMobility, etc.

### Wave 4: MP/SR/BGP-LS ✅
MPRNLRI, MPURNLRI, PrefixSid, SrLabelIndex, SrGb, all BGP-LS link/node/prefix attributes

### Wave 5: Qualifiers ✅
PathInfo, RouteDistinguisher, Labels, ESI, EthernetTag

### Wave 6: NLRI Types ✅
CIDR, INET, Label, IPVPN, VPLS, RTC, Flow, IPrefix4, IPrefix6

### Wave 7: EVPN/BGP-LS/MUP/MVPN NLRI ✅
All EVPN types, BGP-LS types, MUP types, MVPN types

### Wave 8: Messages ✅
KeepAlive, Notification, RouteRefresh, Open, Update
