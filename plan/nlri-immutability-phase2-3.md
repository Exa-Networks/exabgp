# Plan: NLRI Immutability - Phase 2 & 3

## Status: Phase 2 Complete ✅

Route class is now immutable (no setters). The `with_action()` and `with_nexthop()` methods provide immutable updates.

---

## ⚠️ CRITICAL: Route Class Immutability

**Route instances MUST be immutable after creation.**

- **DO NOT** add setter methods to Route
- All values must be passed to `__init__` or use `with_action()`/`with_nexthop()`
- Fallback to `nlri.action`/`nlri.nexthop` kept during transition (for backward compat)
- nexthop still exists in NLRI for wire format (UpdateCollection reads it)

---

## Phase 2 Complete ✅ (2025-12-09)

### What Was Done

1. **Removed Route setters** - `action` and `nexthop` are now read-only properties
   - File: `src/exabgp/rib/route.py`

2. **Added `Scope.replace_route()`** - For immutable Route updates in config parsing
   - File: `src/exabgp/configuration/core/scope.py`

3. **Refactored section.py** - Uses `with_nexthop()` + `replace_route()` instead of setters
   - File: `src/exabgp/configuration/core/section.py`
   - Changed `nlri-nexthop` and `nexthop-and-attribute` actions

4. **All tests pass** - 13 test suites (3137+ unit tests)

### Architecture Finding

**nexthop must remain in NLRI** for wire format encoding:
- `UpdateCollection.messages()` groups NLRIs by nexthop for MP_REACH_NLRI
- `NLRICollection.packed_reach_attributes()` reads `nlri.nexthop` to build wire format
- Per RFC 4760, nexthop is in MP_REACH_NLRI attribute header (adjacent to NLRI)

**Solution:** Route.nexthop is authoritative for RIB operations. The `with_nexthop()` method syncs to `nlri.nexthop` for wire format encoding.

### Code Changes Summary

| File | Change |
|------|--------|
| `src/exabgp/rib/route.py` | Removed `action.setter` and `nexthop.setter`, updated docstring |
| `src/exabgp/configuration/core/scope.py` | Added `replace_route()` method |
| `src/exabgp/configuration/core/section.py` | Use `with_nexthop()` + `replace_route()` |

---

## Context from Phase 1

Phase 1 moved `action` from NLRI to Route. Key learnings:

### What Worked
1. Adding `action` property to Route with fallback to `nlri.action`
2. Route constructor accepts optional `action` parameter
3. Migrating `route.nlri.action` reads to `route.action`
4. All tests pass (13 test suites, 3046+ unit tests)

### Phase 1 Complete ✅
- Test H bug was fixed separately
- All tests pass with action in Route

---

## Phase 3: Future Work

### Remove Fallbacks (When Ready)

Once all code uses `route.action`/`route.nexthop` instead of `nlri.action`/`nlri.nexthop`:

1. Remove fallback from Route.action getter
2. Remove fallback from Route.nexthop getter
3. Remove sync to `nlri.nexthop` in `with_nexthop()`

**Prerequisite:** Refactor UpdateCollection to accept nexthop separately, or pass Route objects instead of bare NLRIs.

### Enforce NLRI Immutability (Optional)

After removing mutable nexthop/action from NLRI, enforce immutability:

**Option A: Add `__setattr__` guard**
```python
class NLRI(Family):
    def __setattr__(self, name: str, value: Any) -> None:
        if not getattr(self, '_initialized', False):
            object.__setattr__(self, name, value)
            return
        raise AttributeError(f'NLRI is immutable: cannot set {name}')
```

**Option B: Use `__slots__` Without Setter Methods (Simpler)**

Since NLRI uses `__slots__`, we can simply:
1. Not provide setter methods
2. Remove mutable fields from __slots__
3. Document that NLRI should not be mutated

---

## Verification Checklist

- [x] `./qa/bin/test_everything` passes (all 13 test suites) ✅
- [x] No `route.nlri.action =` assignments remain (Phase 1) ✅
- [x] Route has no setters (immutable) ✅
- [ ] No `route.nlri.nexthop =` assignments remain (Phase 2)
- [ ] Route.nexthop has no fallback to nlri.nexthop (Phase 3)
- [ ] NLRI.__slots__ has no nexthop (Phase 3)
- [ ] Memory usage unchanged or reduced
- [ ] Performance unchanged or improved

---

## Files Modified

| File | Changes |
|------|---------|
| `src/exabgp/rib/route.py` | Removed setters, updated docstring (IMMUTABLE) |
| `src/exabgp/configuration/core/scope.py` | Added `replace_route()` |
| `src/exabgp/configuration/core/section.py` | Use `with_nexthop()` + `replace_route()` |
| `src/exabgp/reactor/api/command/announce.py` | Uses `with_action()` (already done) |
| `src/exabgp/rib/outgoing.py` | Uses `with_action()` (already done) |
| `src/exabgp/configuration/neighbor/__init__.py` | Uses `with_action()` (already done) |
| `src/exabgp/configuration/validator.py` | Uses `with_nexthop()` (already done) |

---

**Created:** 2025-12-09
**Updated:** 2025-12-09 - Phase 2 complete, Route immutable
