# BGP-LS Packed-Bytes-First Conversion

**Status:** ✅ Completed (Phase 3)
**Created:** 2025-12-11
**Updated:** 2025-12-12

## Goal

Convert BGP-LS attribute classes to packed-bytes-first pattern and refactor MERGE handling to avoid `_packed_list` by moving grouping logic to LinkState level.

## Background

BGP-LS TLV classes previously used `MERGE = True` to combine multiple TLVs of same type into one instance (to avoid duplicate JSON keys). This required storing lists of parsed content or packed bytes.

**Problem:** With packed-bytes-first, we want simple `__init__(packed: bytes)` with `_packed` only - no lists.

**Solution (Option B - chosen):** Move grouping logic from individual TLV classes to `LinkState` level:
- `LinkState`: stores raw attribute bytes, parses TLVs on demand
- `LinkState.json()`: groups same-type TLVs at output time
- Individual TLV classes: simple `_packed`, no MERGE, `content` returns single dict/value

## Progress

### Phase 1: Add factory methods to existing classes (DONE)

Added `make_*` factory methods to enable tests:

- [x] `SrCapabilities.make_sr_capabilities(flags, sids)` - srcap.py
- [x] `SrAlgorithm.make_sr_algorithm(sr_algos)` - sralgo.py
- [x] `IsisArea.make_isis_area(areaid)` - isisarea.py
- [x] `IgpFlags.make_igp_flags(flags)` - igpflags.py
- [x] `Srv6LanEndXISIS.make_srv6_lan_endx_isis(...)` - srv6lanendx.py
- [x] `Srv6LanEndXOSPF.make_srv6_lan_endx_ospf(...)` - srv6lanendx.py

### Phase 2: Refactor MERGE handling (COMPLETED)

**Completed:**
- [x] `LinkState` refactored to store `_packed` raw bytes
- [x] `LinkState.unpack_attribute()` just stores raw bytes
- [x] `LinkState.ls_attrs` property parses TLVs on demand (no merge)
- [x] `LinkState.json()` groups same-type TLVs for valid JSON output (with bytes→hex conversion)
- [x] `Srv6LanEndXISIS` simplified - `JSON` attr, `content` returns dict
- [x] `Srv6LanEndXOSPF` - removed `MERGE`, added `JSON` attr
- [x] `Srv6EndX` - removed `MERGE`, `_content_list`, `merge()`, added `JSON`, `_unpack_data()`, `content` returns dict
- [x] `GenericLSID` - removed `MERGE`, `_content_list`, `merge()`, `JSON` property, `content` returns hex string
- [x] `AdjacencySid` - added `JSON`, `content` properties for grouping support
- [x] Updated test files for new JSON format (single values as scalars, multiple as arrays)
- [x] Updated unit tests for new behavior

### Phase 3: Add remaining factory methods (COMPLETED)

Added factory methods to classes that were missing them:
- [x] `LocalRouterId.make_local_router_id(address)` - localrouterid.py
- [x] `NodeOpaque.make_node_opaque(data)` - opaque.py

Already had factory methods (no changes needed):
- [x] `IgpTags.make_igp_tags(tags)` - igptags.py
- [x] `IgpExTags.make_igp_ex_tags(tags)` - igpextags.py
- [x] `OspfForwardingAddress.make_ospf_forwarding_address(address)` - ospfaddr.py
- [x] `PrefixSid.make_prefix_sid(flags, sids, sr_algo)` - prefixsid.py
- [x] `SourceRouterId.make_source_router_id(address)` - sourcerouterid.py
- [x] `PrefixAttributesFlags.make_prefix_attributes_flags(flags)` - prefixattributesflags.py

Added unit tests for new factory methods in `test_bgpls_packed_bytes_first.py`.

## Files Modified

| File | Change | Status |
|------|--------|--------|
| `linkstate.py` | Store raw bytes, parse on demand, group in json(), bytes→hex | ✅ Done |
| `srv6lanendx.py` | Remove MERGE, add JSON attr, content→dict | ✅ Done |
| `srv6endx.py` | Remove MERGE/_content_list/merge, add JSON/_unpack_data, content→dict | ✅ Done |
| `adjacencysid.py` | Add JSON attr, content property for grouping | ✅ Done |
| `localrouterid.py` | Add `make_local_router_id()` factory | ✅ Done |
| `opaque.py` (node) | Add `make_node_opaque()` factory | ✅ Done |
| `test_bgpls.py` | Update Srv6EndX test - content is dict not list | ✅ Done |
| `test_bgpls_json_validation.py` | Update LinkState test - use wire-format bytes | ✅ Done |
| `test_bgpls_packed_bytes_first.py` | Update GenericLSID tests, add LocalRouterId/NodeOpaque tests | ✅ Done |
| `qa/decoding/bgp-ls-*` | Update expected JSON format (scalars for single, arrays for multiple) | ✅ Done |

## Key Design Changes

### GenericLSID.content
Before: `list[bytes]` (for MERGE support)
After: `str` (hex string - merging done at LinkState level)

### Srv6EndX.content
Before: `list[dict]` (for MERGE support)
After: `dict` (single value - merging done at LinkState level)

### LinkState.json()
Before: Classes with MERGE=True handled their own merging
After: LinkState groups same-type TLVs and:
- Single TLV: outputs directly via `attr.json()`
- Multiple same-type: combines `[a.content for a in attrs]` as JSON array
- Handles bytes→hex conversion for content that's bytes

### Test File JSON Format
Before: Duplicate keys like `"sr-adj": {...}, "sr-adj": {...}` (invalid JSON)
After: Arrays like `"sr-adj": [{...}, {...}]` (valid JSON)

Before: Single values as arrays `"generic-lsid-258": ["0x..."]`
After: Single values as scalars `"generic-lsid-258": "0x..."`

## Tests Passing

All 15 test categories pass:
- ruff-format, ruff-check
- unit (3211 tests - added 5 new tests for LocalRouterId and NodeOpaque)
- config, no-neighbor, encode-decode, parsing, json
- api-encode, cmd-roundtrip
- decoding (18 tests including all BGP-LS)
- encoding (72 tests)
- cli, api, type-ignore

---

**Updated:** 2025-12-12
