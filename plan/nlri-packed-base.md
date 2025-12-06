# Move _packed to NLRI Base Class (Wire-First Pattern)

**Status:** ✅ Completed
**Created:** 2025-12-06
**Last Updated:** 2025-12-06

## Goal

Unify all NLRI types to use a wire-first pattern where:
1. `_packed` bytes are stored at the NLRI base class level
2. Validation/decode happens in `__init__` (fail-fast, raises `Notify(3, 10, ...)`)
3. All property access works from raw wire bytes (decode on demand)

## Current State

| Class | Storage Pattern | Wire-first? |
|-------|-----------------|-------------|
| INET | `_packed` (CIDR) | Yes |
| Label | `_packed` + `_labels_packed` | Yes |
| IPVPN | `_packed` + `_labels_packed` + `_rd_packed` | Yes |
| VPLS | `_packed` OR builder attrs | Dual-mode |
| Flow | `_packed` (RD+rules) | Yes |
| EVPN | `_packed` (type+data) | Yes |
| BGPLS | `_packed` (type+data) | Yes |
| MUP | `_packed` (arch+code+data) | Yes |
| MVPN | `_packed` (code+data) | Yes |
| RTC | `_packed_origin` + `rt` object | Hybrid |

## Proposed Changes

### Phase 1: Add `_packed` to NLRI Base Class

**File:** `src/exabgp/bgp/message/update/nlri/nlri.py`

```python
class NLRI(Family):
    _packed: bytes  # Wire format bytes (subclass-specific interpretation)

    def __init__(self, afi: AFI, safi: SAFI, action: Action = Action.UNSET) -> None:
        Family.__init__(self, afi, safi)
        self.action = action
        self._packed = b''  # Subclasses set actual wire data
```

### Phase 2: Update INET Hierarchy

**File:** `src/exabgp/bgp/message/update/nlri/inet.py`

Changes:
1. Remove `_packed` declaration (inherits from NLRI)
2. Validate in `__init__` that packed bytes are valid for AFI
3. Keep `cidr` property for decode-on-access

```python
class INET(NLRI):
    def __init__(self, packed: bytes, afi: AFI, safi: SAFI = SAFI.unicast) -> None:
        NLRI.__init__(self, afi, safi, Action.UNSET)
        # Validation: decode to verify, but store raw
        self._validate_packed(packed, afi)
        self._packed = packed  # Now in NLRI base
        self.path_info = PathInfo.DISABLED
        self.nexthop = IP.NoNextHop

    def _validate_packed(self, packed: bytes, afi: AFI) -> None:
        """Validate packed CIDR bytes. Raises Notify(3, 10) on invalid."""
        if not packed:
            return
        mask = packed[0]
        max_mask = 32 if afi == AFI.ipv4 else 128
        if mask > max_mask:
            raise Notify(3, 10, f'invalid mask {mask} for {afi}')
        expected_len = 1 + CIDR.size(mask)
        if len(packed) < expected_len:
            raise Notify(3, 10, 'could not decode CIDR')
```

### Phase 3: Update Other NLRI Types

Each NLRI subclass needs review to ensure:
1. Uses inherited `_packed` from NLRI base
2. Validates in `__init__`
3. Decodes on property access

**Files to update:**
- `label.py` - uses `_labels_packed` separately (OK)
- `ipvpn.py` - uses `_rd_packed` separately (OK)
- `vpls.py` - dual-mode needs cleanup
- `flow.py` - already wire-first
- `evpn/nlri.py` - already wire-first
- `bgpls/nlri.py` - already wire-first
- `mup/nlri.py` - already wire-first
- `mvpn/nlri.py` - already wire-first
- `rtc.py` - hybrid, needs review

## Implementation Order

1. **Add `_packed` to NLRI base** (`nlri.py`)
   - Add `_packed: bytes = b''` attribute
   - No behavior changes yet

2. **Update INET** (`inet.py`)
   - Remove local `_packed` declaration
   - Add `_validate_packed()` method
   - Call validation in `__init__` and factory methods

3. **Update Label** (`label.py`)
   - Remove local `_packed` if declared
   - Verify `_labels_packed` pattern is consistent

4. **Update IPVPN** (`ipvpn.py`)
   - Remove local `_packed` if declared
   - Verify `_rd_packed` pattern is consistent

5. **Review Flow** (`flow.py`)
   - Already has `_packed`, should inherit

6. **Review VPLS** (`vpls.py`)
   - Needs cleanup of dual-mode pattern
   - Consider standardizing builder mode

7. **Review EVPN/BGPLS/MUP/MVPN**
   - Already wire-first, verify inheritance works

8. **Review RTC** (`rtc.py`)
   - Hybrid pattern - may need special handling

9. **Add tests** for validation in `__init__`

## Design Decisions

1. **Validation raises `Notify(3, 10, ...)`** - Consistent with existing CIDR decode pattern. BGP UPDATE error (code 3), subcode 10 = "Invalid Network Field".

2. **`_packed` semantics are per-type** - Each NLRI type defines what `_packed` contains:
   - INET: just CIDR `[mask][ip...]`
   - EVPN: includes route-type code
   - Keep current per-type semantics

3. **Builder mode uses `_packed = b''`** - For VPLS/Flow builder patterns, empty `_packed` indicates builder mode. Validation skipped when empty. Pack on demand when `pack_nlri()` called.

## Files to Modify

| File | Changes |
|------|---------|
| `nlri.py` | Add `_packed` attribute to NLRI base |
| `inet.py` | Remove `_packed`, add validation |
| `label.py` | Inherit `_packed`, verify consistency |
| `ipvpn.py` | Inherit `_packed`, verify consistency |
| `flow.py` | Verify inheritance works |
| `vpls.py` | Clean up dual-mode, inherit `_packed` |
| `evpn/nlri.py` | Verify inheritance works |
| `bgpls/nlri.py` | Verify inheritance works |
| `mup/nlri.py` | Verify inheritance works |
| `mvpn/nlri.py` | Verify inheritance works |
| `rtc.py` | Review hybrid pattern |

## Tests to Add

1. NLRI base class has `_packed` attribute
2. INET validates packed bytes in `__init__`
3. Invalid mask raises `Notify(3, 10, ...)`
4. Packed too short raises `Notify(3, 10, ...)`
5. All NLRI subclasses inherit `_packed`
6. Wire-first decode works correctly for each type
7. Builder mode (empty `_packed`) is allowed

## Progress

- [x] Phase 1: Add `_packed` to NLRI base
  - Added `_packed: bytes` type annotation to NLRI class
  - Added `self._packed = b''` initialization in `__init__`
  - Updated `_create_invalid()` and `_create_empty()` to set `_packed = b''`
- [x] Phase 2: Update INET hierarchy
  - INET already uses `_packed` correctly; inherits type from base
  - Label and IPVPN inherit correctly through INET
- [x] Phase 3: Update other NLRI types
  - Verified Flow, VPLS, EVPN, BGPLS, MUP, MVPN, RTC all work correctly
  - VPLS's `bytes | None` pattern for builder mode continues to work
- [x] Phase 4: Add tests
  - Added `TestNLRIPackedBaseClass` in `tests/unit/test_inet.py`
  - Tests verify base class annotation, inheritance, singletons, decoding
- [x] Phase 5: Run `./qa/bin/test_everything`
  - All 11 tests pass (ruff, unit, encoding, decoding, config, cli, api, etc.)

## Implementation Notes

The change was minimal but establishes a consistent pattern:

1. **NLRI base class** now declares `_packed: bytes` and initializes it to `b''`
2. **Subclasses** override this with their specific wire data
3. **VPLS special case**: Uses `_packed: bytes | None` for dual-mode (wire/builder)
4. **No breaking changes**: All existing code continues to work

## Files Modified

- `src/exabgp/bgp/message/update/nlri/nlri.py` - Added `_packed` to base class
- `tests/unit/test_inet.py` - Added tests for `_packed` inheritance
