# AddPath Support for Additional NLRI Types

**Status:** 📋 Planning (not started)
**Priority:** Low (feature enhancement)
**See also:** `packed-bytes/` (refactoring may simplify this)

## Goal

Extend ADD-PATH support to NLRI types that currently lack it. ADD-PATH (RFC 7911) allows multiple paths per prefix, useful for path diversity and fast convergence.

## Current State

ADD-PATH already works for:
- ✅ `inet` (IPv4/IPv6 unicast)
- ✅ `label` (labeled unicast)
- ✅ `ipvpn` (VPNv4/VPNv6)

## Scope

NLRI types needing ADD-PATH support:

| File | NLRI Type | Complexity | Notes |
|------|-----------|------------|-------|
| `nlri/bgpls/nlri.py:107` | BGP-LS | Medium | Link-state NLRI |
| `nlri/flow.py:652` | FlowSpec | High | Builder pattern, complex |
| `nlri/vpls.py:89` | VPLS | Low | Simple structure |
| `nlri/evpn/nlri.py:84` | EVPN | Medium | Multiple route types |
| `nlri/mvpn/nlri.py:76` | MVPN | Medium | Multicast VPN |
| `nlri/mup/nlri.py:79` | MUP | Low | Mobile User Plane |
| `nlri/bgpls/srv6sid.py:129` | SRv6 SID | Low | Segment Routing |

## Implementation Pattern

Each NLRI type needs:

1. **Wire format update** - Prepend 4-byte path ID when ADD-PATH enabled
2. **`pack_nlri()` modification** - Include path ID in output
3. **`unpack_nlri()` modification** - Parse path ID from input
4. **PathInfo handling** - Store/retrieve path identifier

### Example (from existing inet implementation):

```python
def pack_nlri(self, negotiated: Negotiated, addpath: PathInfo | None = None) -> bytes:
    addpath_bytes = addpath.pack() if addpath else b''
    return addpath_bytes + self._pack_cidr()

@classmethod
def unpack_nlri(cls, afi, safi, data, action, addpath, negotiated):
    if addpath:
        path_info = PathInfo.unpack(data[:4])
        data = data[4:]
    else:
        path_info = PathInfo.DISABLED
    # ... parse NLRI ...
    return cls(..., path_info=path_info), remaining
```

## Files to Modify

For each NLRI type:
1. The NLRI class file itself
2. Possibly `nlri/nlri.py` if base class changes needed
3. Test files in `tests/unit/`

## Testing

1. Unit tests for pack/unpack with ADD-PATH enabled
2. Round-trip tests: encode → decode → verify path ID preserved
3. Functional tests with ADD-PATH capability negotiated

```bash
# After each NLRI type:
uv run pytest tests/unit/nlri/test_<type>.py -v
./qa/bin/functional encoding
./qa/bin/test_everything
```

## Risks

| Risk | Mitigation |
|------|------------|
| FlowSpec complexity | May need special handling due to builder pattern |
| Wire format errors | Extensive testing with real BGP implementations |
| Backward compatibility | ADD-PATH only used when negotiated |

## Dependencies

- Recommend completing `packed-bytes/` refactoring first
- Consistent `_packed` attribute makes path ID handling cleaner

## Estimated Effort

| NLRI Type | Effort |
|-----------|--------|
| VPLS, MUP, SRv6 SID | Small (1-2 hours each) |
| BGP-LS, EVPN, MVPN | Medium (2-4 hours each) |
| FlowSpec | Large (4-8 hours) |

---

**Last Updated:** 2025-12-04
