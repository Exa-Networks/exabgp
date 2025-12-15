# Plan: Remove Action from NLRI and Route Classes

## Goal
Remove `action` from NLRI and Route `__slots__` to reduce memory footprint. Action is operational context (announce vs withdraw), not NLRI/Route identity. Track action at RIB level and pass as parameter through call chains.

**Memory savings**: ~16 bytes per route (8 bytes from NLRI.action + 8 bytes from Route._action)

## Status: COMPLETE ✓

All phases completed. Action is now fully removed from Route and NLRI storage.

---

## Summary of Changes

### Phase 1: RIB Layer Refactoring (COMPLETE)
- Action determined by which RIB method is called:
  - `add_to_rib()` / `announce_route()` → announce
  - `del_from_rib()` / `withdraw_route()` → withdraw
- Simplified `outgoing.py` and `cache.py`
- All tests passing

### Phase 2: Remove Storage (COMPLETE)
Commit: `d439e59f8` - "feat: Remove action from Route and NLRI __slots__ - Phase 2 complete"

**Route class changes:**
- Removed `_action` from `__slots__`
- Removed `action` property
- Removed `with_action()` method
- Updated `feedback()` to take action as parameter

**NLRI class changes:**
- Removed `action` from `__slots__`
- Removed action parameter from `__init__`
- Updated all NLRI subclasses (INET, Label, IPVPN, VPLS, RTC, Flow, BGP-LS, EVPN, MUP, MVPN)
- Removed action from factory methods (`from_cidr`, `make_vpls`, `make_rtc`, etc.)

**62 files changed**, 270 insertions(+), 786 deletions(-)

### Phase 3: Simplify Check Functions (COMPLETE)
Commit: `467da8c3a` - "refactor: Remove action parameter from check() validation functions"

- Removed `action` parameter from all `check()` validation functions
- Check functions now always validate route structure (nexthop required for unicast/multicast)
- For withdraws, callers set dummy nexthop (0.0.0.0) before validation

**14 files changed**, 64 insertions(+), 78 deletions(-)

---

## Design Decisions

1. **Action is implicit in method calls:**
   - `add_to_rib()` = announce
   - `del_from_rib()` = withdraw

2. **Route validation simplified:**
   - `check(route, afi)` validates route structure
   - No action parameter needed
   - Withdraws set dummy nexthop before validation

3. **Settings classes retain action:**
   - `INETSettings.action`, `FlowSettings.action`, etc. still exist
   - Used during configuration parsing to track announce vs withdraw context
   - Not propagated to NLRI/Route storage

---

## Test Results

- Unit tests: 3174 passed
- Functional encoding: 36/36 passed
- Functional decoding: 18/18 passed
- All configuration files parse correctly

---

## Files Modified (Summary)

**Core changes:**
- `src/exabgp/rib/route.py` - Route class
- `src/exabgp/bgp/message/update/nlri/nlri.py` - Base NLRI class
- `src/exabgp/bgp/message/update/nlri/*.py` - All NLRI subclasses

**Configuration:**
- `src/exabgp/configuration/announce/*.py` - Check functions
- `src/exabgp/configuration/static/*.py` - Route parsing
- `src/exabgp/configuration/validator.py` - Route validation

**API:**
- `src/exabgp/reactor/api/command/announce.py` - API commands
- `src/exabgp/reactor/api/command/route.py` - Route commands
- `src/exabgp/reactor/api/command/group.py` - Group commands

---

## Related Plans

- `plan-announce-cancels-withdraw-optimization.md` - Future optimization to cancel pending withdraws when announce comes for same NLRI

---

## Completion Date

2024-12-15
