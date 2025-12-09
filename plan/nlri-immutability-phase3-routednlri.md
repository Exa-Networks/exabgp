# NLRI Immutability Phase 3: RoutedNLRI Implementation

**Status:** 🔄 Active (Phase 3 complete, Phase 4 planned)
**Started:** 2025-12-09
**Last Updated:** 2025-12-09

## Goal

Remove `nexthop` from NLRI storage and use a separate `RoutedNLRI` container for wire format encoding. This enables NLRI immutability by separating the routing nexthop from the NLRI identity.

## Design Decision

Instead of storing `nexthop` in `NLRI.__slots__`, we created a new `RoutedNLRI` dataclass:

```python
@dataclass(frozen=True, slots=True)
class RoutedNLRI:
    """NLRI with associated nexthop for wire format encoding."""
    nlri: NLRI
    nexthop: IP
```

**Rationale:**
- `UpdateCollection` needs nexthop for MP_REACH_NLRI encoding
- Withdraws (MP_UNREACH_NLRI) don't need nexthop
- Separating nexthop from NLRI allows NLRI to be immutable and reusable

## Completed Steps

### 1. Created RoutedNLRI dataclass
- **File:** `src/exabgp/bgp/message/update/collection.py`
- Added frozen dataclass with `nlri` and `nexthop` fields

### 2. Updated UpdateCollection
- **File:** `src/exabgp/bgp/message/update/collection.py`
- Changed `announces` from `list[NLRI]` to `list[RoutedNLRI]`
- Added backward compatibility: accepts both `list[NLRI]` (legacy) and `list[RoutedNLRI]` (new)
- Updated `messages()` to use `routed.nexthop` instead of `nlri.nexthop`
- Changed internal grouping: `mp_announces` (RoutedNLRI) vs `mp_withdraws` (bare NLRI)
- Updated `_parse_payload()` to wrap parsed NLRIs in RoutedNLRI
- Added `get_nexthop()` helper to extract IP from NEXT_HOP attribute

### 3. Updated MPNLRICollection
- **File:** `src/exabgp/bgp/message/update/nlri/collection.py`
- Added `from_routed()` factory method for RoutedNLRI input
- Added `_routed_nlris` storage for reach operations
- Updated `packed_reach_attributes()` to use RoutedNLRI when available (with legacy fallback)

### 4. Updated outgoing.py (RIB)
- **File:** `src/exabgp/rib/outgoing.py`
- Changed announce creation to use `RoutedNLRI(route.nlri, route.nexthop)`
- Withdraws remain as bare NLRIs

### 5. Updated CLI tools
- **File:** `src/exabgp/application/encode.py`
- **File:** `src/exabgp/configuration/check.py`
- Updated to create `RoutedNLRI` when building UpdateCollection

### 6. Updated unit test
- **File:** `tests/unit/bgp/message/update/test_update_refactor.py`
- Updated to use RoutedNLRI for the announce test

### 7. Added fuzz test helper
- **File:** `tests/fuzz/test_update_message_integration.py`
- Added `create_routed_nlri()` helper function to create RoutedNLRI for announce tests
- Existing tests use backward compatibility layer (bare NLRIs auto-wrapped)

### 8. Fixed UpdateHandler for RoutedNLRI
- **File:** `src/exabgp/reactor/peer/handlers/update.py`
- Fixed both `handle()` and `handle_async()` methods to extract bare NLRI from RoutedNLRI
- Issue: `parsed.announces` now returns `list[RoutedNLRI]`, but RIB cache expects bare `NLRI`
- Solution: Extract `nlri` from `routed.nlri` before passing to `update_cache()`

## Test Results

- ✅ All 13 test suites pass
- ✅ Unit tests: passed
- ✅ Functional encoding tests: 36/36 passed
- ✅ Functional decoding tests: 18/18 passed
- ✅ API tests: 38/38 passed (fixed g, l, q, η, θ)

## Remaining Work

### ~~High Priority~~ ✅ COMPLETED

1. ~~**Run full test suite**~~ ✅ All 13 test suites pass
2. ~~**Fix any remaining test failures**~~ ✅ Fixed UpdateHandler

### Medium Priority (Phase 3 Completion)

3. ~~**Remove legacy `nlri.nexthop` mutation during parsing**~~ ✅ COMPLETED
   - ~~Currently `_parse_payload()` still sets `nlri.nexthop = nexthop` for backward compatibility (JSON API reads it)~~
   - Still set for `NLRI.extensive()` which is used by Route/config validation
   - TODO comment updated to reflect this dependency

4. ~~**Update JSON API to use RoutedNLRI**~~ ✅ COMPLETED (commit d136448)
   - Updated `json.py`, `text.py`, `v4/text.py` to use RoutedNLRI for nexthop
   - EOR messages use original `.nlris` path, UpdateCollection uses `.announces`
   - Added 15 unit tests in `tests/unit/reactor/api/response/test_json_update.py`

5. ~~**Remove backward compatibility layer**~~ ✅ COMPLETED
   - Removed auto-wrapping in `UpdateCollection.__init__`
   - Updated all 28 fuzz tests to use `create_routed_nlri()` helper
   - Changed type signature to `announces: list[RoutedNLRI]` (enforced)
   - `protocol.py:41` uses empty lists `[]` - no change needed
   - All 13 test suites pass

### Low Priority (Future) - Phase 4: Remove nexthop from NLRI

6. **Remove nexthop from NLRI.__slots__**

   **Goal:** Make NLRI truly immutable by removing the mutable `nexthop` slot.

   **Current state:** `nexthop` is in `NLRI.__slots__` at `src/exabgp/bgp/message/update/nlri/nlri.py:43`

   **Prerequisites (must complete first):**
   - ✅ RoutedNLRI for UpdateCollection announces
   - ✅ JSON API uses RoutedNLRI for nexthop
   - ❌ Config parsing must create Route with separate nexthop (not set on NLRI)
   - ❌ Route.nexthop must not fall back to nlri.nexthop
   - ❌ All nlri.nexthop reads must be eliminated or replaced

   **Files that SET nlri.nexthop (47 occurrences):**

   | Category | File | Line | Notes |
   |----------|------|------|-------|
   | **NLRI Classes** | `nlri/nlri.py` | 85 | Base class `__init__` - remove slot |
   | | `nlri/nlri.py` | 103, 121 | `__copy__`/`__deepcopy__` - remove |
   | | `nlri/inet.py` | 135, 199, 232, 268 | `__init__`, factories - use Settings only |
   | | `nlri/ipvpn.py` | 275, 314, 338, 534 | Same pattern |
   | | `nlri/label.py` | 262, 300 | Same pattern |
   | | `nlri/flow.py` | 705, 763 | Same pattern |
   | | `nlri/rtc.py` | 64, 109 | Same pattern |
   | | `nlri/vpls.py` | 58, 134 | Same pattern |
   | | `nlri/evpn/nlri.py` | 68 | Same pattern |
   | | `nlri/bgpls/*.py` | various | BGP-LS classes |
   | **Config Parsing** | `configuration/announce/__init__.py` | 78, 87 | Creates Route, sets nlri.nexthop |
   | | `configuration/static/route.py` | 432, 446, 488, 511 | Same pattern |
   | | `configuration/flow/__init__.py` | 117, 132 | Same pattern |
   | | `configuration/flow/route.py` | 115 | Same pattern |
   | **UPDATE Parsing** | `update/collection.py` | 495 | `_parse_payload()` - backward compat |
   | | `update/attribute/mprnlri.py` | 101 | MP_REACH parsing |
   | **Route Class** | `rib/route.py` | 104 | `nexthop.setter` syncs to nlri |

   **Files that READ nlri.nexthop (17 occurrences):**

   | Category | File | Line | Notes |
   |----------|------|------|-------|
   | **Route fallback** | `rib/route.py` | 80, 85, 86 | Falls back to nlri.nexthop |
   | | `rib/outgoing.py` | 314 | Comment mentions fallback |
   | | `rib/cache.py` | 83 | Comment mentions fallback |
   | **Config** | `configuration/announce/__init__.py` | 78 | Reads before copying |
   | | `configuration/static/route.py` | 432, 446, 488 | Reads for validation/copy |
   | | `configuration/flow/__init__.py` | 132 | Copies nexthop |
   | | `configuration/flow/route.py` | 115 | Copies nexthop |
   | **Neighbor** | `bgp/neighbor/neighbor.py` | 282, 293 | Reads for NEXT_HOP_SELF |
   | **Legacy MP** | `nlri/collection.py` | 298, 320, 326, 332 | Legacy mode fallback |
   | **UPDATE** | `update/collection.py` | 513 | Creates RoutedNLRI from nlri.nexthop |

   **NLRI extensive() methods that show nexthop:**
   - `nlri/inet.py:359`
   - `nlri/label.py:309`
   - `nlri/flow.py:959, 1006`
   - `nlri/vpls.py:205`
   - `nlri/bgpls/*.py` (json methods)

   These are used for logging/display - need Route context or RoutedNLRI.

7. **Implementation Plan for Phase 4:**

   **Step 1: Update Route class** (rib/route.py)
   - Remove fallback to `nlri.nexthop` in `Route.nexthop` property
   - Require `_nexthop` to be set explicitly on all Route instances
   - Remove sync to `nlri.nexthop` in setter

   **Step 2: Update config parsing** (create Route with nexthop, not nlri.nexthop)
   - `configuration/announce/__init__.py`
   - `configuration/static/route.py`
   - `configuration/flow/__init__.py`
   - `configuration/flow/route.py`
   - Pattern: Parse nexthop → create NLRI (without nexthop) → create Route(nlri, nexthop=...)

   **Step 3: Update neighbor.py** (NEXT_HOP_SELF handling)
   - `bgp/neighbor/neighbor.py:282, 293`
   - Use `route.nexthop` instead of `route.nlri.nexthop`

   **Step 4: Update UPDATE parsing** (collection.py, mprnlri.py)
   - Remove backward compat `nlri.nexthop = nexthop` in `_parse_payload()`
   - `mprnlri.py:101` - nexthop already goes to RoutedNLRI

   **Step 5: Remove legacy mode from MPNLRICollection**
   - `nlri/collection.py` - remove legacy fallback (lines 320-337)
   - Only use `_routed_nlris` path

   **Step 6: Update NLRI extensive() methods**
   - These need Route or context to show nexthop
   - May need to accept optional nexthop parameter
   - Or change to not show nexthop (it's not part of NLRI identity)

   **Step 7: Remove nexthop from NLRI**
   - Remove `'nexthop'` from `NLRI.__slots__` (nlri.py:43)
   - Remove `self.nexthop = ...` from all NLRI `__init__` methods
   - Remove from `__copy__`, `__deepcopy__`
   - Remove from all NLRI subclass constructors

   **Estimated scope:** ~50 files, ~100 changes

8. **Testing Strategy for Phase 4:**
   - After each step, run `./qa/bin/test_everything`
   - Key tests to watch:
     - Functional encoding/decoding (MP_REACH nexthop)
     - API tests (JSON output)
     - Config validation tests
   - Add unit tests for Route.nexthop without fallback

## Key Files Modified

| File | Changes |
|------|---------|
| `src/exabgp/bgp/message/update/collection.py` | RoutedNLRI dataclass, UpdateCollection refactor, get_nexthop() helper |
| `src/exabgp/bgp/message/update/nlri/collection.py` | MPNLRICollection.from_routed() |
| `src/exabgp/rib/outgoing.py` | Create RoutedNLRI from Route |
| `src/exabgp/application/encode.py` | Use RoutedNLRI |
| `src/exabgp/configuration/check.py` | Use RoutedNLRI |
| `tests/unit/bgp/message/update/test_update_refactor.py` | Use RoutedNLRI |
| `tests/fuzz/test_update_message_integration.py` | Added create_routed_nlri() helper for future test updates |
| `src/exabgp/reactor/peer/handlers/update.py` | Extract bare NLRI from RoutedNLRI for RIB cache |

## Architecture Notes

### Data Flow (Outbound)

```
Route (nlri + nexthop + action + attributes)
    ↓
RoutedNLRI (nlri + nexthop) for announces
    ↓
UpdateCollection (announces: list[RoutedNLRI], withdraws: list[NLRI])
    ↓
MPNLRICollection.from_routed() for MP routes
    ↓
Wire format bytes
```

### Data Flow (Inbound)

```
Wire format bytes
    ↓
UpdateCollection._parse_payload()
    ↓
RoutedNLRI created from parsed NLRI + nexthop
    ↓
(nlri.nexthop still set for backward compat with JSON API)
```

## Resume Point

**Phase 4 In Progress.** Steps 1-3 complete, Steps 4-7 remaining.

## Session 2025-12-09 Progress

### Completed (session 1):
- ✅ Updated JSON/text API handlers to use RoutedNLRI for nexthop
- ✅ Fixed EOR vs UpdateCollection handling (EOR uses `.nlris`, UpdateCollection uses `.announces`)
- ✅ Added 15 unit tests for JSON API response handling

### Completed (session 2):
- ✅ Updated all 28 fuzz tests to use `create_routed_nlri()` helper
- ✅ Removed backward compatibility layer from `UpdateCollection.__init__`
- ✅ Changed type signature to `announces: list[RoutedNLRI]` (enforced)
- ✅ All 13 test suites pass

### Completed (session 3 - Phase 4):
- ✅ **Step 2:** Updated all Route creation sites to pass explicit `nexthop=` parameter
  - `static/__init__.py`, `announce/__init__.py`, `static/route.py`, `flow/__init__.py`, `flow/parser.py`
  - `validator.py`, `l2vpn/vpls.py`, `check.py`, `static/parser.py`, `rib/cache.py`, `rib/outgoing.py`
- ✅ **Step 1:** Removed fallback in `Route.nexthop` property - now returns `_nexthop` directly
- ✅ **Step 3:** Updated `neighbor.py:resolve_self()` to use `route.nexthop` instead of `route.nlri.nexthop`
- ✅ **Step 4:** Added `iter_routed()` method to MPRNLRI that yields RoutedNLRI with nexthop
  - Refactored `_parse_nexthop_and_nlris()` to separate nexthop parsing
  - `__iter__()` now yields NLRIs without setting nexthop (for backward compat)
  - UpdateCollection uses `reach.iter_routed()` for announces
  - **Note:** Still setting `nlri.nexthop` for backward compat with JSON API (NLRI.json() methods read it)
- ✅ Updated tests to pass explicit nexthop: `test_route_action.py`, `test_nexthop_self.py`, etc.
- ✅ All 13 test suites pass

- ✅ **Step 5:** Removed legacy mode from MPNLRICollection.packed_reach_attributes()
  - Updated tests in `test_multiprotocol.py` and `test_collection.py` to use `from_routed()`
  - Legacy mode that read `nlri.nexthop` removed - now only uses `_routed_nlris`

### Remaining (Steps 6-7):
- Step 6: Update NLRI `extensive()` and `json()` methods (stop reading nexthop from self)
- Step 7: Remove `nexthop` from `NLRI.__slots__`

### Key insight (Step 4):
Cannot fully remove `nlri.nexthop` assignment yet because many NLRI types have `json()` methods
that include `"nexthop": "{self.nexthop}"`. Removing this would break the JSON API format.
Steps 6-7 need to be done together with careful API coordination.

## Blockers

None - all tests pass.

## Related Plans

- `plan/nlri-immutability-phase2-3.md` - Previous phases (completed)
- `plan/nlri-immutability.md` - Original plan
