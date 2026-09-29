# AddPath Support for Additional NLRI Types

**Status:** 📋 Planning (not started)
**Priority:** Low (feature enhancement)
**See also:** `packed-bytes/` (refactoring may simplify this)

## Goal

Extend ADD-PATH support to NLRI types that currently lack it. ADD-PATH (RFC 7911) allows multiple paths per prefix, useful for path diversity and fast convergence.

## Current State, 2026-09-29

Decoding: every family consumes the path identifier since `2142b4cc1` (EVPN, BGP-LS,
MVPN, MUP, SR-Policy) and `038e9a6f8` (FlowSpec, VPLS, RTC).

Encoding: only the families in `Capabilities._ADD_PATH` write one, and that list is what
we offer, so a peer is never told to expect an identifier we do not send.
`tests/unit/test_addpath_families_encode_path_id.py` holds the list to the encoders.

| Family | Encodes | In `_ADD_PATH` |
|---|---|---|
| `inet`, `label`, `ipvpn` | ✅ | ✅ |
| FlowSpec (issue #1140) | ✅ | ✅ |
| EVPN | ❌ TODO in `pack_nlri` | ❌ |
| BGP-LS | ❌ TODO in `pack_nlri` | ❌ |
| MVPN | ❌ TODO in `pack_nlri` | ❌ |
| VPLS | ❌ TODO in `pack_nlri` | ❌ |
| MUP | ❌ (removed from `_ADD_PATH` because it did not encode) | ❌ |
| SR-Policy | ❌ | ❌ |
| RTC | ❌ | ❌ |

Found by the 2026-09-24 quality sweep (item 33 of `done-review-quality-sweep.md`).

## Scope

Per family: `pack_nlri` writes the identifier when `negotiated.addpath.send()` says so,
a round-trip test, and the family added to `_ADD_PATH` **in the same change**.

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

**Last Updated:** 2026-09-29
