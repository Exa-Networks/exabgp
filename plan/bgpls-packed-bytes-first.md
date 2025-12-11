# BGP-LS Packed-Bytes-First Conversion

**Status:** 🔄 Active
**Created:** 2025-12-11
**Updated:** 2025-12-11

## Goal

Convert BGP-LS attribute classes to packed-bytes-first pattern and refactor MERGE handling to avoid `_packed_list` by moving grouping logic to LinkState level.

## Background

BGP-LS TLV classes currently use `MERGE = True` to combine multiple TLVs of same type into one instance (to avoid duplicate JSON keys). This requires storing lists of parsed content or packed bytes.

**Problem:** With packed-bytes-first, we want simple `__init__(packed: bytes)` with `_packed` only - no lists.

**Solution:** Move grouping logic from individual TLV classes to `LinkState` level:
- Individual TLV classes: simple, single `_packed`, `MERGE = False`
- `LinkState`: groups same-type TLVs at JSON output time
- `LinkState`: stores raw attribute bytes, parses TLVs on demand

## Progress

### Phase 1: Add factory methods to existing classes (DONE)

Added `make_*` factory methods to enable tests:

- [x] `SrCapabilities.make_sr_capabilities(flags, sids)` - srcap.py
- [x] `SrAlgorithm.make_sr_algorithm(sr_algos)` - sralgo.py
- [x] `IsisArea.make_isis_area(areaid)` - isisarea.py
- [x] `IgpFlags.make_igp_flags(flags)` - igpflags.py
- [x] `Srv6LanEndXISIS.make_srv6_lan_endx_isis(...)` - srv6lanendx.py
- [x] `Srv6LanEndXOSPF.make_srv6_lan_endx_ospf(...)` - srv6lanendx.py

### Phase 2: Refactor MERGE handling (TODO)

Current state:
- `Srv6LanEndXISIS` and `Srv6LanEndXOSPF` have `MERGE = True`
- Base class `merge()` does `self.content.extend(other.content)`
- Requires `content` to be a list

#### Option A: Move grouping to LinkState.json()

```python
class LinkState:
    def __init__(self, packed: bytes = b''):
        self._packed = packed  # Store raw attribute data

    @property
    def ls_attrs(self) -> list[BaseLS]:
        """Parse TLVs on demand from _packed"""
        # Returns list - can have multiple same-type TLVs
        ...

    def json(self) -> str:
        """Group by TLV type for valid JSON output"""
        from collections import defaultdict
        by_type: dict[int, list[BaseLS]] = defaultdict(list)
        for attr in self.ls_attrs:
            by_type[attr.TLV].append(attr)

        parts = []
        for tlv, attrs in by_type.items():
            if len(attrs) == 1:
                parts.append(attrs[0].json())
            else:
                # Combine into array
                key = attrs[0].JSON
                values = [json.loads('{' + a.json() + '}')[key] for a in attrs]
                parts.append(f'"{key}": {json.dumps(values)}')
        return '{ ' + ', '.join(parts) + ' }'
```

Then for TLV classes:
- Set `MERGE = False`
- Remove `merge()` method
- Simple `content` property returning single dict (not list)

#### Option B: LinkState stores raw bytes, parses on demand

```python
class LinkState:
    def __init__(self, packed: bytes):
        self._packed = packed

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated) -> LinkState:
        return cls(data)  # Just store raw bytes

    @property
    def ls_attrs(self) -> list[BaseLS]:
        """Parse all TLVs on demand"""
        # Parse self._packed into TLV instances
        ...
```

### Phase 3: Update remaining skipped tests (TODO)

After MERGE refactor, update tests for:
- [ ] `Srv6EndX` - srv6endx.py (also has MERGE)
- [ ] `LocalRouterId` - localrouterid.py
- [ ] `IgpTags` - igptags.py
- [ ] `IgpExTags` - igpextags.py
- [ ] `OspfForwardingAddress` - ospfforwardingaddress.py
- [ ] `PrefixSid` - prefixsid.py
- [ ] `SourceRouterId` - sourcerouterid.py
- [ ] `PrefixAttributesFlags` - prefixattributesflags.py
- [ ] `NodeOpaque` - opaque.py

## Files to Modify

| File | Change |
|------|--------|
| `linkstate.py` | Add JSON grouping logic, store raw bytes |
| `srv6lanendx.py` | Set MERGE=False, simplify content property |
| `srv6endx.py` | Set MERGE=False, simplify content property |
| `test_bgpls_json_validation.py` | Update tests for new JSON format |

## Current Test Status

```
Skipped tests: 12 remaining
- Srv6EndX (has MERGE, needs same refactor)
- LocalRouterId, IgpTags, IgpExTags, OspfForwardingAddress
- PrefixSid, SourceRouterId, PrefixAttributesFlags, NodeOpaque
- Plus edge case tests
```

## Failures

- Decoding test 6 fails: `AttributeError: 'dict' object has no attribute 'extend'`
- Caused by: `Srv6LanEndXISIS.content` returns dict, but `merge()` expects list

## Resume Point

Need to decide: Option A (grouping in LinkState.json) or Option B (LinkState stores raw bytes)?

Then implement chosen approach and fix decoding test 6.

---

**Updated:** 2025-12-11
