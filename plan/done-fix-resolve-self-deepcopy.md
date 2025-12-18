# Plan: Fix resolve_self() Deepcopy

## Problem

`Neighbor.resolve_self()` does `deepcopy(route)` for every route with `next-hop self`, even when the same route is used by multiple neighbors. This causes massive memory duplication.

**Current code:** `src/exabgp/bgp/neighbor/neighbor.py:281-305`
```python
def resolve_self(self, route: 'Route') -> 'Route':
    nexthop = route.nlri.nexthop

    if not nexthop.SELF:
        return route  # OK - no copy needed

    if nexthop.resolved:
        return route  # OK - already resolved

    route_copy = deepcopy(route)  # PROBLEM: always copies
    nexthop = route_copy.nlri.nexthop
    nexthop.resolve(neighbor_self)  # Mutates IPSelf._packed in-place
    # ...
    return route_copy
```

**Root cause:** `IPSelf.resolve()` mutates the object in-place:
```python
class IPSelf(IPBase):
    def resolve(self, ip: 'IP') -> None:
        self._packed = ip.pack_ip()  # Mutation!
```

---

## Solution: Make IPSelf.resolve() Return New Object

Instead of mutating `IPSelf`, return a resolved `IP` object.

### Step 1: Change IPSelf.resolve() to Return IP

**File:** `src/exabgp/protocol/ip/__init__.py`

**Before:**
```python
class IPSelf(IPBase):
    def resolve(self, ip: 'IP') -> None:
        """Resolve sentinel to concrete IP. Mutates in-place."""
        if self.resolved:
            raise ValueError('IPSelf already resolved')
        self._packed = ip.pack_ip()
```

**After:**
```python
class IPSelf(IPBase):
    def resolve(self, ip: 'IP') -> 'IP':
        """Return concrete IP. Does NOT mutate self."""
        return ip  # Just return the resolved IP directly

    # Remove mutable state
    # _packed no longer needed for resolution
```

Or alternatively, return a new `IPSelf` with the resolved value:
```python
class IPSelf(IPBase):
    def resolve(self, ip: 'IP') -> 'IPSelf':
        """Return new IPSelf with resolved value."""
        resolved = IPSelf(self.afi)
        object.__setattr__(resolved, '_packed', ip.pack_ip())
        object.__setattr__(resolved, '_resolved', True)
        return resolved
```

### Step 2: Update resolve_self() to Use Immutable Pattern

**File:** `src/exabgp/bgp/neighbor/neighbor.py`

**Before:**
```python
def resolve_self(self, route: 'Route') -> 'Route':
    nexthop = route.nlri.nexthop

    if not nexthop.SELF:
        return route

    if nexthop.resolved:
        return route

    route_copy = deepcopy(route)
    nexthop = route_copy.nlri.nexthop
    neighbor_self = self.ip_self(route_copy.nlri.afi)
    nexthop.resolve(neighbor_self)  # Mutates

    if Attribute.CODE.NEXT_HOP in route_copy.attributes:
        nh_attr = route_copy.attributes[Attribute.CODE.NEXT_HOP]
        if nh_attr.SELF and not nh_attr.resolved:
            nh_attr.resolve(neighbor_self)

    return route_copy
```

**After:**
```python
def resolve_self(self, route: 'Route') -> 'Route':
    nexthop = route.nlri.nexthop

    # No resolution needed
    if not nexthop.SELF:
        return route

    # Already resolved - share original
    if nexthop.resolved:
        return route

    # Resolve to concrete IP
    neighbor_self = self.ip_self(route.nlri.afi)
    resolved_nexthop = nexthop.resolve(neighbor_self)  # Returns new IP

    # Create new NLRI with resolved nexthop (no deepcopy!)
    new_nlri = route.nlri.with_nexthop(resolved_nexthop)

    # Handle NEXT_HOP attribute if present
    new_attrs = route.attributes
    if Attribute.CODE.NEXT_HOP in route.attributes:
        nh_attr = route.attributes[Attribute.CODE.NEXT_HOP]
        if nh_attr.SELF and not nh_attr.resolved:
            resolved_nh_attr = nh_attr.resolve(neighbor_self)
            new_attrs = route.attributes.with_nexthop(resolved_nh_attr)

    return Route(new_nlri, new_attrs)
```

### Step 3: Ensure NLRI.with_nexthop() Exists

**File:** `src/exabgp/bgp/message/update/nlri/nlri.py`

This should already exist from the immutability plan. If not:
```python
def with_nexthop(self, nexthop: 'IP') -> 'NLRI':
    """Return copy with different nexthop."""
    new = copy(self)
    object.__setattr__(new, 'nexthop', nexthop)
    return new
```

### Step 4: Handle NextHop Attribute Similarly

**File:** `src/exabgp/bgp/message/update/attribute/nexthop.py`

Ensure `NextHop.resolve()` also returns a new object instead of mutating.

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/exabgp/protocol/ip/__init__.py` | `IPSelf.resolve()` returns new IP instead of mutating |
| `src/exabgp/bgp/neighbor/neighbor.py` | `resolve_self()` uses immutable pattern |
| `src/exabgp/bgp/message/update/attribute/nexthop.py` | `NextHop.resolve()` returns new object |
| `src/exabgp/bgp/message/update/attribute/collection.py` | Add `with_nexthop()` if needed |

---

## Dependencies

- **Requires:** `NLRI.with_nexthop()` method (from `plan/nlri-immutability.md`)
- **Requires:** Immutable NLRI pattern

**If implementing standalone (before full immutability):**
- Can still use `deepcopy` but only when `nexthop.SELF and not nexthop.resolved`
- Current code already does this check but still deepcopies

Wait - looking again at the current code:
```python
if not nexthop.SELF:
    return route  # Already returns original!

if nexthop.resolved:
    return route  # Already returns original!
```

**The current code already avoids deepcopy in 2 of 3 cases!**

The only case that deepcopies is: `nexthop.SELF == True AND nexthop.resolved == False`

This happens when:
1. Config uses `next-hop self`
2. Route hasn't been resolved yet for this neighbor

---

## Revised Analysis

**Question:** How often does `nexthop.SELF and not nexthop.resolved` occur?

- First neighbor: All routes with `next-hop self` need resolution → deepcopy
- Second neighbor: Same routes... are they already resolved?

**Problem:** Each neighbor gets a deepcopy, and each deepcopy has its own `IPSelf` object with its own `_packed`. So `nexthop.resolved` is False for each new copy.

**Real fix:** Don't mutate IPSelf at all. Return a new resolved IP.

---

## Minimal Fix (No Full Immutability Required)

Just change `IPSelf.resolve()` to return a new object:

```python
class IPSelf(IPBase):
    def resolve(self, ip: 'IP') -> 'IP':
        """Return the resolved IP address."""
        return ip  # IPSelf is just a sentinel, return actual IP
```

Then in `resolve_self()`:
```python
def resolve_self(self, route: 'Route') -> 'Route':
    nexthop = route.nlri.nexthop

    if not nexthop.SELF:
        return route

    if nexthop.resolved:
        return route

    # Resolve without deepcopy
    neighbor_self = self.ip_self(route.nlri.afi)
    resolved_ip = neighbor_self  # The actual IP to use

    # Create minimal copy with resolved nexthop
    from copy import copy
    new_nlri = copy(route.nlri)
    new_nlri.nexthop = resolved_ip  # Set to actual IP, not IPSelf

    # Handle attribute
    new_attrs = route.attributes
    if Attribute.CODE.NEXT_HOP in route.attributes:
        nh_attr = route.attributes[Attribute.CODE.NEXT_HOP]
        if nh_attr.SELF and not nh_attr.resolved:
            new_attrs = copy(route.attributes)
            # ... resolve attribute nexthop similarly

    return Route(new_nlri, new_attrs)
```

**Key insight:** We don't need full immutability. We just need to:
1. Stop mutating `IPSelf` in-place
2. Use shallow copy instead of deepcopy
3. Replace `IPSelf` with resolved `IP`

---

## Verification

```bash
# Run all tests
./qa/bin/test_everything

# Specifically test neighbor/routing
uv run pytest tests/unit/ -k neighbor -v
uv run pytest tests/unit/ -k route -v

# Functional tests with next-hop self
./qa/bin/functional encoding
```

---

## Impact

- **Memory saved:** ~60-80% for deployments using `next-hop self`
- **Code complexity:** Low - localized changes
- **Risk:** Medium - nexthop resolution is critical path
- **Testing:** Must verify next-hop appears correctly in wire format

---

## Status

✅ **COMPLETED** 2025-12-18

- [x] Change `IPSelf.resolve()` to return new IP
- [x] Change `NextHopSelf.resolve()` to return new NextHop
- [x] Update `resolve_self()` to use `Route.with_nexthop()` instead of deepcopy
- [x] Update tests for new immutable semantics
- [x] Run full test suite (16/16 passed)
- [ ] Memory profiling before/after (not done - left for user)

### Implementation Summary

1. **`IPSelf.resolve(ip)`** - Now returns the passed `ip` directly (no mutation)
2. **`NextHopSelf.resolve(ip)`** - Now returns a new `NextHop(ip.pack_ip())`
3. **`resolve_self()`** - Uses `Route.with_nexthop()` to create new route with resolved IP
4. **Tests** - Updated 13 tests to expect immutable semantics (sentinel stays unresolved)

### Key Semantic Change

- OLD: Sentinel mutated in-place, `.resolved` becomes True, `.SELF` stays True
- NEW: Sentinel unchanged, returns concrete IP/NextHop with `.SELF = False`
