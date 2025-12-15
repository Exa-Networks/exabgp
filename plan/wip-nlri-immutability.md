# Plan: NLRI Immutability Enforcement

## Status: 🔄 Phase 3/4 In Progress

- Phase 1 (action → Route): ✅ Complete
- Phase 2 (Route immutability): ✅ Complete
- Phase 3 (RoutedNLRI implementation): ✅ Complete (Steps 1-5)
- Phase 4 (Remove nexthop from NLRI): 🔄 In Progress (Steps 6-7 remaining)

---

## Goal

Make NLRI objects truly immutable by:
1. Removing mutable fields that don't belong in NLRI
2. Enabling safe sharing (no deepcopy needed)
3. Zero memory overhead (no per-instance `_frozen` field)

---

## Critical Design Decisions

### ❌ Problem 1: `action` Should NOT Be in NLRI Class

**Why `action` doesn't belong in NLRI:**

1. **Action is ephemeral context, not NLRI identity** - An NLRI represents a network prefix/route (e.g., "10.0.0.0/24 with label 100"). Whether it's being announced or withdrawn is a **transient operation**, not an intrinsic property.

2. **Same NLRI, different operations** - The identical NLRI should be usable for both announce and withdraw. Storing action forces:
   - Mutating the NLRI (violates immutability)
   - Creating copies just to change action (wasteful)

3. **Action flows through call stack** - Methods like `pack_nlri()`, `feedback()`, `json()` need action, but it should be a **parameter**, not stored state.

4. **RIB operations define action** - When adding/removing from RIB, the operation itself defines the action, not the NLRI.

**Solution:**
- Remove `action` from NLRI.__slots__
- Pass action as parameter: `pack_nlri(negotiated, action)`, `feedback(action)`, `json(action, ...)`
- Store action in Route class (Route = NLRI + Attributes + Action context)

### ❌ Problem 2: `nexthop` Should NOT Be in Base NLRI Class

**Why `nexthop` doesn't belong in base NLRI:**

1. **Not all NLRI types have nexthop** - Every NLRI class sets `self.nexthop = IP.NoNextHop` in __init__, which is wasteful.

2. **Nexthop is an UPDATE attribute, not NLRI property** - Per RFC 4760:
   - MP_REACH_NLRI attribute contains: AFI, SAFI, **Next Hop**, NLRI...
   - Nexthop is part of the **attribute**, not the NLRI itself
   - Withdraws (MP_UNREACH_NLRI) don't have nexthop at all

3. **Wire format vs semantic confusion:**
   - Wire: nexthop is in MP_REACH_NLRI attribute header
   - Current code: nexthop stored in each NLRI instance
   - All NLRIs in same UPDATE share the same nexthop anyway

4. **Memory waste** - Every NLRI carries a nexthop slot, even for withdraws.

**Solution:** Introduced `RoutedNLRI` dataclass to separate nexthop from NLRI:

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

---

## Revised NLRI Design

### What NLRI Should Contain (Identity Fields Only)

```python
class NLRI(Family):
    __slots__ = ('addpath', '_packed')  # Just path ID and wire bytes

    # afi, safi from Family.__slots__ (or class-level for single-family types)
    # Subclasses add: prefix, RD, labels, EVPN-specific fields, etc.
```

### What Route Should Contain

```python
class Route:
    __slots__ = ('nlri', 'attributes', 'action', 'nexthop', '__index')

    # action: Action - ANNOUNCE/WITHDRAW for this operation
    # nexthop: IP - next hop for this route (from MP_REACH_NLRI)
    # nlri: NLRI - the immutable network layer reachability info
    # attributes: AttributeCollection - BGP path attributes
```

---

## Architecture: Data Flow

### Outbound (Route → Wire)

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

### Inbound (Wire → Route)

```
Wire format bytes
    ↓
UpdateCollection._parse_payload()
    ↓
RoutedNLRI created from parsed NLRI + nexthop
    ↓
(nlri.nexthop still set for backward compat with JSON API)
```

---

## Implementation Progress

### Phase 1: Move `action` Out of NLRI ✅

**Completed 2025-12-09**

1. ✅ Added `action` property to Route class with fallback to `nlri.action`
2. ✅ Route constructor accepts optional `action` parameter
3. ✅ Migrated `route.nlri.action` reads to `route.action`
4. ✅ Updated cache.py, announce.py, neighbor/__init__.py, validator.py, vpls.py
5. ✅ All tests pass

### Phase 2: Route Immutability ✅

**Completed 2025-12-09**

1. ✅ Removed Route setters - `action` and `nexthop` are now read-only properties
2. ✅ Added `Scope.replace_route()` for immutable Route updates in config parsing
3. ✅ Refactored section.py to use `with_nexthop()` + `replace_route()` instead of setters
4. ✅ All tests pass (13 test suites, 3137+ unit tests)

### Phase 3: RoutedNLRI Implementation ✅

**Completed 2025-12-09**

1. ✅ Created `RoutedNLRI` dataclass in `collection.py`
2. ✅ Updated `UpdateCollection` - `announces` is now `list[RoutedNLRI]`
3. ✅ Added `MPNLRICollection.from_routed()` factory method
4. ✅ Updated `outgoing.py` to create `RoutedNLRI(route.nlri, route.nexthop)`
5. ✅ Updated CLI tools (`encode.py`, `check.py`) to use RoutedNLRI
6. ✅ Updated unit tests and fuzz tests with `create_routed_nlri()` helper
7. ✅ Fixed `UpdateHandler` to extract bare NLRI from RoutedNLRI for RIB cache
8. ✅ Updated JSON/text API handlers to use RoutedNLRI for nexthop
9. ✅ Removed backward compatibility layer - type signature enforced
10. ✅ All 13 test suites pass

### Phase 4: Remove nexthop from NLRI 🔄

**In Progress - Steps 1-5 complete, Steps 6-7 remaining**

#### Completed Steps:

1. ✅ **Step 1: Update Route class** - Removed fallback in `Route.nexthop` property
2. ✅ **Step 2: Update config parsing** - All Route creation sites pass explicit `nexthop=`
   - `static/__init__.py`, `announce/__init__.py`, `static/route.py`, `flow/__init__.py`, `flow/parser.py`
   - `validator.py`, `l2vpn/vpls.py`, `check.py`, `static/parser.py`, `rib/cache.py`, `rib/outgoing.py`
3. ✅ **Step 3: Update neighbor.py** - `resolve_self()` uses `route.nexthop`
4. ✅ **Step 4: Add iter_routed() to MPRNLRI** - Yields RoutedNLRI with nexthop
   - Refactored `_parse_nexthop_and_nlris()` to separate nexthop parsing
   - UpdateCollection uses `reach.iter_routed()` for announces
   - **Note:** Still setting `nlri.nexthop` for backward compat with JSON API
5. ✅ **Step 5: Remove legacy mode from MPNLRICollection** - Only uses `_routed_nlris` path

#### Remaining Steps:

6. **Step 6: Update NLRI extensive() and json() methods**
   - These read `self.nexthop` for display - need Route context or RoutedNLRI parameter
   - Files: `nlri/inet.py`, `nlri/label.py`, `nlri/flow.py`, `nlri/vpls.py`, `nlri/bgpls/*.py`

7. **Step 7: Remove nexthop from NLRI**
   - Remove `'nexthop'` from `NLRI.__slots__` (nlri.py:43)
   - Remove `self.nexthop = ...` from all NLRI `__init__` methods
   - Remove from `__copy__`, `__deepcopy__`
   - Remove from all NLRI subclass constructors

**Key insight:** Cannot fully remove `nlri.nexthop` assignment yet because many NLRI types have `json()` methods that include `"nexthop": "{self.nexthop}"`. Steps 6-7 need to be done together with careful API coordination.

---

## Detailed nlri.nexthop Usage Analysis

### Files that SET nlri.nexthop (~24 in nlri/, more in config)

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

### Files that READ nlri.nexthop (17 occurrences)

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

### NLRI extensive() methods that show nexthop

- `nlri/inet.py:359`
- `nlri/label.py:309`
- `nlri/flow.py:959, 1006`
- `nlri/vpls.py:205`
- `nlri/bgpls/*.py` (json methods)

These are used for logging/display - need Route context or RoutedNLRI.

---

## Files Modified

### Phase 1-2

| File | Changes |
|------|---------|
| `src/exabgp/rib/route.py` | Added `action`, `nexthop` slots; removed setters (IMMUTABLE) |
| `src/exabgp/configuration/core/scope.py` | Added `replace_route()` method |
| `src/exabgp/configuration/core/section.py` | Use `with_nexthop()` + `replace_route()` |
| `src/exabgp/reactor/api/command/announce.py` | Uses `with_action()` |
| `src/exabgp/rib/outgoing.py` | Uses `with_action()` |
| `src/exabgp/configuration/neighbor/__init__.py` | Uses `with_action()` |
| `src/exabgp/configuration/validator.py` | Uses `with_nexthop()` |
| `src/exabgp/configuration/vpls/vpls.py` | Route creation with action |

### Phase 3-4

| File | Changes |
|------|---------|
| `src/exabgp/bgp/message/update/collection.py` | RoutedNLRI dataclass, UpdateCollection refactor, get_nexthop() helper |
| `src/exabgp/bgp/message/update/nlri/collection.py` | MPNLRICollection.from_routed() |
| `src/exabgp/bgp/message/update/attribute/mprnlri.py` | iter_routed() method, separated nexthop parsing |
| `src/exabgp/rib/outgoing.py` | Create RoutedNLRI from Route |
| `src/exabgp/application/encode.py` | Use RoutedNLRI |
| `src/exabgp/configuration/check.py` | Use RoutedNLRI |
| `src/exabgp/reactor/peer/handlers/update.py` | Extract bare NLRI from RoutedNLRI for RIB cache |
| `src/exabgp/reactor/api/response/json.py` | Use RoutedNLRI for nexthop |
| `src/exabgp/reactor/api/response/text.py` | Use RoutedNLRI for nexthop |
| `src/exabgp/bgp/neighbor/neighbor.py` | Use route.nexthop for NEXT_HOP_SELF |
| `tests/unit/bgp/message/update/test_update_refactor.py` | Use RoutedNLRI |
| `tests/fuzz/test_update_message_integration.py` | Added create_routed_nlri() helper |
| `tests/unit/reactor/api/response/test_json_update.py` | 15 new tests for JSON API |

---

## Verification Checklist

- [x] `./qa/bin/test_everything` passes (all 13 test suites) ✅
- [x] No `route.nlri.action =` assignments remain (Phase 1) ✅
- [x] Route has no setters (immutable) ✅
- [x] RoutedNLRI used for announces in UpdateCollection ✅
- [x] Route.nexthop has no fallback to nlri.nexthop ✅
- [x] Legacy mode removed from MPNLRICollection ✅
- [ ] No `nlri.nexthop =` assignments remain (Phase 4 Step 7)
- [ ] NLRI.__slots__ has no nexthop (Phase 4 Step 7)
- [ ] Memory usage unchanged or reduced
- [ ] Performance unchanged or improved

---

## Test Results

- ✅ All 13 test suites pass
- ✅ Unit tests: passed
- ✅ Functional encoding tests: 36 tests (0-9, A-Z)
- ✅ Functional decoding tests: 18 tests
- ✅ API tests: 38 tests

---

## Benefits

1. **True immutability** - NLRI identity never changes after creation
2. **Memory savings** - (Future) No nexthop slot in every NLRI
3. **Semantic clarity** - Action is operation context, not data
4. **Safe sharing** - Same NLRI usable for announce and withdraw
5. **Simpler RIB** - Routes with identical NLRI can share NLRI reference

---

## Session Progress Log

### Session 2025-12-09 (Phase 3)

**Session 1:**
- ✅ Updated JSON/text API handlers to use RoutedNLRI for nexthop
- ✅ Fixed EOR vs UpdateCollection handling (EOR uses `.nlris`, UpdateCollection uses `.announces`)
- ✅ Added 15 unit tests for JSON API response handling

**Session 2:**
- ✅ Updated all 28 fuzz tests to use `create_routed_nlri()` helper
- ✅ Removed backward compatibility layer from `UpdateCollection.__init__`
- ✅ Changed type signature to `announces: list[RoutedNLRI]` (enforced)
- ✅ All 13 test suites pass

**Session 3 (Phase 4):**
- ✅ **Step 2:** Updated all Route creation sites to pass explicit `nexthop=` parameter
- ✅ **Step 1:** Removed fallback in `Route.nexthop` property
- ✅ **Step 3:** Updated `neighbor.py:resolve_self()` to use `route.nexthop`
- ✅ **Step 4:** Added `iter_routed()` method to MPRNLRI
- ✅ **Step 5:** Removed legacy mode from MPNLRICollection.packed_reach_attributes()
- ✅ All 13 test suites pass

---

## Resume Point

**Phase 4 In Progress.** Steps 1-5 complete, Steps 6-7 remaining.

**Next steps:**
- Step 6: Update NLRI `extensive()` and `json()` methods (stop reading nexthop from self)
- Step 7: Remove `nexthop` from `NLRI.__slots__`

**Estimated scope for remaining work:** ~50 files, ~100 changes

**Testing strategy:**
- After each step, run `./qa/bin/test_everything`
- Key tests to watch: Functional encoding/decoding (MP_REACH nexthop), API tests (JSON output), Config validation tests
- Add unit tests for Route.nexthop without fallback

---

**Created:** 2025-12-09
**Updated:** 2025-12-15 - Consolidated and verified against current code state

**Note:** Line numbers in detailed tables are approximate (code evolves). Use grep to find current locations.
