# BGP Class Refactoring: Packed-Bytes-First Pattern

## Goal

Refactor ALL BGP classes to a new pattern:
- `__init__(self, packed: bytes)` - ONLY takes packed wire-format data, validates size
- `@classmethod def make_TYPE(cls, ...)` - Factory methods for semantic construction
- `@property` decorators for accessing unpacked data (NO caching - unpack every access)

**Scope:** Messages, Attributes, NLRI - complete replacement of existing patterns

---

## Target Pattern

### Attributes (simple case - Origin)

```python
@Attribute.register()
class Origin(Attribute):
    def __init__(self, packed: bytes) -> None:
        if len(packed) != 1:
            raise ValueError(f'Origin requires exactly 1 byte, got {len(packed)}')
        self._packed = packed

    @classmethod
    def make_origin(cls, origin: int) -> 'Origin':
        return cls(bytes([origin]))

    @property
    def origin(self) -> int:
        return self._packed[0]

    def pack_attribute(self, negotiated: Negotiated | None = None) -> bytes:
        return self._attribute(self._packed)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> 'Origin':
        # Validation happens in __init__
        return cls(data)
```

### NLRI (complex case - has metadata not in wire format)

```python
@NLRI.register(AFI.ipv4, SAFI.unicast)
class INET(NLRI):
    def __init__(self, packed: bytes, afi: AFI, safi: SAFI,
                 action: Action = Action.UNSET,
                 path_info: PathInfo = PathInfo.DISABLED) -> None:
        self._packed = packed  # CIDR portion only
        self._afi = afi
        self._safi = safi
        self._action = action
        self._path_info = path_info
        self._nexthop = IP.NoNextHop

    @classmethod
    def make_route(cls, afi: AFI, safi: SAFI, cidr: CIDR,
                   action: Action = Action.ANNOUNCE) -> 'INET':
        return cls(cidr.pack_nlri(), afi, safi, action)

    @property
    def cidr(self) -> CIDR:
        return CIDR.unpack(self._packed)

    @property
    def action(self) -> Action:
        return self._action

    @action.setter
    def action(self, value: Action) -> None:
        self._action = value
```

---

## Progress

### Wave 1: Simple Attributes ✅ COMPLETE

| File | Status | Factory Method |
|------|--------|----------------|
| `origin.py` | ✅ Done | `Origin.make_origin(int)` |
| `med.py` | ✅ Done | `MED.make_med(int)` |
| `localpref.py` | ✅ Done | `LocalPreference.make_localpref(int)` |
| `atomicaggregate.py` | ✅ Done | `AtomicAggregate.make_atomic_aggregate()` |

**Key decisions:**
- Size validation happens in `__init__`, raises `ValueError`
- `Attributes.parse()` catches `ValueError` alongside `IndexError` for TREAT_AS_WITHDRAW

---

## Implementation Order (Remaining)

### Wave 2: Complex Attributes ✅ COMPLETE

| File | Status | Factory Method |
|------|--------|----------------|
| `aspath.py` | ✅ Done | `ASPath.make_aspath(...)` |
| `nexthop.py` | ✅ Done | `NextHop.make_nexthop(...)` |
| `aggregator.py` | ✅ Done | `Aggregator.make_aggregator(...)` |
| `clusterlist.py` | ✅ Done | `ClusterList.make_clusterlist(...)` |
| `originatorid.py` | ✅ Done | `OriginatorId.make_originatorid(...)` |
| `generic.py` | ✅ Done | `GenericAttribute.make_generic(...)` |

**Also converted:** `aigp.py`, `pmsi.py`

### Wave 3: Community Attributes ✅ COMPLETE

| Category | Files | Status |
|----------|-------|--------|
| Initial | `community.py`, `communities.py` | ✅ Done |
| Large | `community.py`, `communities.py` | ✅ Done |
| Extended | 12 files (community, communities, rt, origin, traffic, bandwidth, encapsulation, flowspec_scope, l2info, mac_mobility, mup, chso) | ✅ Done |

### Wave 4: MP Attributes + BGP-LS + SR
21-55. `mprnlri.py`, `mpurnlri.py`, `bgpls/*.py`, `sr/*.py`

### Wave 5: Qualifiers ✅ COMPLETE

| File | Status | Factory Method |
|------|--------|----------------|
| `path.py` | ✅ Done | `PathInfo.make_from_integer(int)`, `PathInfo.make_from_ip(str)` |
| `rd.py` | ✅ Done | `RouteDistinguisher.make_from_elements(prefix, suffix)` |
| `labels.py` | ✅ Done | `Labels.make_labels(list[int], bos)` |
| `esi.py` | ✅ Done | `ESI.make_default()`, `ESI.make_esi(bytes)` |
| `etag.py` | ✅ Done | `EthernetTag.make_etag(int)` |

### Wave 6: NLRI Types 🔄 IN PROGRESS

| File | Status | Notes |
|------|--------|-------|
| `cidr.py` | ✅ Done | `__init__(self, nlri: bytes)` |
| `inet.py` | ✅ Done | `__init__(self, packed: bytes, ...)` |
| `label.py` | ✅ Done | `__init__(self, packed: bytes, ...)` |
| `ipvpn.py` | ✅ Done | `__init__(self, packed: bytes, ...)` |
| `vpls.py` | ✅ Done | `__init__(self, packed: bytes, ...)` |
| `rtc.py` | ✅ Partial | Origin as packed bytes; RT needs `negotiated` for unpacking |
| `flow.py` | 🔄 Pending | Complex builder pattern - needs conversion |
| `flow.py:IPrefix4` | 🔄 Pending | FlowSpec prefix component |
| `flow.py:IPrefix6` | 🔄 Pending | FlowSpec prefix component |

### Wave 7: EVPN + BGP-LS + MUP + MVPN NLRI ✅ COMPLETE

| Category | Files | Status |
|----------|-------|--------|
| EVPN | ethernetad, mac, multicast, prefix, segment | ✅ Done |
| BGP-LS | node, link, prefixv4, prefixv6, srv6sid | ✅ Done |
| MUP | isd, dsd, t1st, t2st | ✅ Done |
| MVPN | sourcead, sourcejoin, sharedjoin | ✅ Done |

**Commit:** 17331d4a

**Note:** Base classes (`evpn/nlri.py`, `bgpls/nlri.py`, `mup/nlri.py`, `mvpn/nlri.py`) are abstract bases that initialize `_packed = b''` as placeholder. Subclasses properly set `_packed` in their `__init__`. Generic* fallback classes accept packed bytes. No changes needed to base classes.

### Wave 8: Messages ✅ COMPLETE

| File | Status | Factory Method |
|------|--------|----------------|
| `keepalive.py` | ✅ Done | `KeepAlive.make_keepalive()` |
| `notification.py` | ✅ Done | `Notification.make_notification(code, subcode, data)` |
| `refresh.py` | ✅ Done | `RouteRefresh.make_route_refresh(afi, safi, reserved)` |
| `open/__init__.py` | ✅ Done | `Open.make_open(version, asn, hold_time, router_id, capabilities)` |
| `update/__init__.py` | ✅ Done | `Update.make_update(nlris, attributes)` - composite container |

**Notes:**
- KeepAlive: Trivial case (empty payload), `_packed = b''`
- RouteRefresh: 4-byte wire format, properties extract AFI/SAFI/reserved
- Notification: 2+ byte wire format, `data` property parses shutdown communication
- Notify subclass: Keeps semantic constructor for backwards compatibility
- Open: Fixed 9-byte header in `_packed`, capabilities stored separately
- Update: Composite container - NLRIs/Attributes already packed-bytes-first, no single `_packed`

---

## Special Cases

### 1. NLRI Metadata (action, path_info, nexthop)

NLRI has metadata NOT in wire format. Solution: accept as `__init__` params alongside packed bytes:

```python
def __init__(self, packed: bytes, afi: AFI, safi: SAFI,
             action: Action = Action.UNSET, ...) -> None:
```

### 2. Singletons (NLRI.INVALID, NLRI.EMPTY, PathInfo.DISABLED)

Keep existing `_create_invalid()` pattern that bypasses `__init__`:
```python
NLRI.INVALID = NLRI._create_invalid()  # Uses object.__new__()
```

### 3. GenericAttribute (dynamic ID/FLAG)

Pass as `__init__` params since not in packed bytes:
```python
def __init__(self, packed: bytes, code: int, flag: int) -> None:
```

### 4. Multiple Inheritance (NextHop extends Attribute + IP)

Delegate IP functionality to composition, not inheritance:
```python
def __init__(self, packed: bytes) -> None:
    self._packed = packed

@property
def string(self) -> str:
    return IP.ntop(self._packed)
```

### 5. Attribute Cache System

Works unchanged - keyed by packed bytes:
```python
@classmethod
def setCache(cls) -> None:
    IGP = cls.make_origin(cls.IGP)
    cls.cache[Attribute.CODE.ORIGIN][IGP._packed] = IGP
```

---

## Per-File Checklist

For EACH file (one at a time per MANDATORY_REFACTORING_PROTOCOL):

1. [ ] Find all call sites: `grep -r "ClassName(" src/`
2. [ ] Change `__init__` to accept only `packed: bytes` (+ metadata for NLRI)
3. [ ] Add size validation in `__init__`, raise `ValueError` if invalid
4. [ ] Add `@classmethod def make_TYPE(...)` factory methods
5. [ ] Convert instance attributes to `@property` (unpack from `_packed`)
6. [ ] Update `unpack_*` to call new `__init__` (validation in __init__)
7. [ ] Update all call sites to use factory methods
8. [ ] Update tests
9. [ ] Run `./qa/bin/test_everything` - MUST PASS

---

## Critical Files

1. **`src/exabgp/bgp/message/update/attribute/origin.py`** - Template case ✅
2. **`src/exabgp/bgp/message/update/attribute/aspath.py`** - Complex segments
3. **`src/exabgp/bgp/message/update/nlri/inet.py`** - Core NLRI with metadata
4. **`src/exabgp/bgp/message/update/nlri/flow.py`** - Most complex (764 lines)
5. **`src/exabgp/bgp/message/open/__init__.py`** - Open message with capabilities

---

## Risks

| Risk | Mitigation |
|------|------------|
| Property access performance | Monitor benchmarks; simple unpacking should be fast |
| Call site updates | grep all usages; update configuration parser |
| NLRI metadata handling | Accept as __init__ params, not in packed bytes |
| Flow NLRI complexity | Defer to late phase; thorough testing |

---

## Testing

After EACH file change:
```bash
./qa/bin/test_everything  # ALL 6 test suites must pass
```

Round-trip verification:
```bash
./qa/bin/functional encoding  # 72 tests
./qa/bin/functional decoding
```
