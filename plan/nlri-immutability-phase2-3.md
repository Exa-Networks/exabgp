# Plan: NLRI Immutability - Phase 2 & 3

## ⚠️ CRITICAL: Route Class Immutability

**Route instances MUST be immutable after creation.**

- **DO NOT** add setter methods to Route
- **DO NOT** add fallback to `nlri.nexthop` or `nlri.action`
- All values must be passed to `__init__`
- nexthop should NOT exist in NLRI - it belongs in Route only

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

## Phase 2: Move nexthop from NLRI to Route - IN PROGRESS

### Why nexthop Should Move

1. **Per RFC 4760**: nexthop is in MP_REACH_NLRI attribute header, not NLRI itself
2. **Memory waste**: Every NLRI has nexthop slot, even withdraws (which have no nexthop)
3. **Shared nexthop**: All NLRIs in same UPDATE share same nexthop anyway
4. **Semantic confusion**: nexthop is UPDATE-level, not NLRI-level

### Current State (2025-12-09)

Files staged with changes to use `route.nexthop`:
- `src/exabgp/rib/route.py` - Has `_nexthop` slot and property (BUT with wrong fallback/setter)
- `src/exabgp/reactor/api/command/announce.py` - Uses `route.nexthop`
- `src/exabgp/configuration/core/section.py` - Uses `route.nexthop`
- `src/exabgp/configuration/validator.py` - Uses `route.nexthop`
- `src/exabgp/configuration/announce/ip.py` - Uses `route.nexthop` read
- `src/exabgp/rib/cache.py` - Uses `route.nexthop` read
- `src/exabgp/rib/outgoing.py` - Uses `route.nexthop` read

### Problems to Fix

1. **Route.nexthop property has fallback to nlri.nexthop** - WRONG
   - nexthop should NOT be in NLRI at all
   - Remove fallback, just return `self._nexthop`

2. **Route has setters** - WRONG
   - Route is immutable, no setters allowed
   - Current code uses `route.action =` and `route.nexthop =` in many places
   - Need to refactor to create new Route instances instead

3. **Code that mutates routes** - needs refactoring:
   ```
   route.action = Action.ANNOUNCE  # ~12 places in announce.py
   route.action = Action.ANNOUNCE  # 2 places in neighbor/__init__.py
   route.action = Action.ANNOUNCE  # 1 place in outgoing.py
   route.nexthop = NextHop...      # 2 places
   ```

### Required Refactoring

To make Route immutable, code like:
```python
route.action = Action.WITHDRAW
```

Must become:
```python
route = Route(route.nlri, route.attributes, action=Action.WITHDRAW, nexthop=route.nexthop)
```

Or add a `with_action()` method:
```python
route = route.with_action(Action.WITHDRAW)
```

---

## Phase 3: Enforce NLRI Immutability (TODO)

### What NLRI Should Contain (Identity Only)

After Phase 1 & 2, NLRI contains only identity fields:
- `afi`, `safi` (from Family)
- `addpath` (path ID)
- `_packed` (wire bytes)
- Subclass-specific: prefix, RD, labels, EVPN fields, etc.

**NOT nexthop** - nexthop belongs in Route

### Implementation Options

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

Before declaring any phase complete:

- [x] `./qa/bin/test_everything` passes (all 13 test suites)
- [x] No `route.nlri.action =` assignments remain (Phase 1) ✅
- [ ] No `route.nlri.nexthop =` assignments remain (Phase 2)
- [ ] Route has no setters (immutable)
- [ ] Route.nexthop has no fallback to nlri.nexthop
- [ ] NLRI.__slots__ has no nexthop
- [ ] Memory usage unchanged or reduced
- [ ] Performance unchanged or improved

---

## Files Modified (Phase 2 - staged)

| File | Changes |
|------|---------|
| `src/exabgp/rib/route.py` | Added `_nexthop` slot and property (needs setter removal) |
| `src/exabgp/reactor/api/command/announce.py` | Use `route.nexthop` |
| `src/exabgp/configuration/core/section.py` | Use `route.nexthop` |
| `src/exabgp/configuration/validator.py` | Use `route.nexthop` |
| `src/exabgp/configuration/announce/ip.py` | Use `route.nexthop` read |
| `src/exabgp/rib/cache.py` | Use `route.nexthop` read |
| `src/exabgp/rib/outgoing.py` | Use `route.nexthop` read |
| `tests/unit/configuration/test_route_builder_action.py` | Mock sets `route.nexthop` |

---

## Resume Point

**Phase 2 In Progress** - Files staged, but Route class needs:
1. Remove fallback to nlri.nexthop in property getter
2. Remove setters (action and nexthop)
3. Refactor code that mutates routes to create new instances

---

**Created:** 2025-12-09
**Updated:** 2025-12-09 - Noted immutability requirements
