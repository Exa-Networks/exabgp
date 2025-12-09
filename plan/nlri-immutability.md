# Plan: NLRI Immutability Enforcement

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

**Solution:**
- Remove `nexthop` from NLRI base class
- Store nexthop in Route class (Route = NLRI + Attributes + Nexthop)
- Or store in Update/UpdateCollection (shared by all NLRIs in that UPDATE)

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

## Implementation Plan

### Phase 1: Move `action` Out of NLRI

1. **Add `action` to Route class**
   - Route already has `with_action()` helper
   - Add `action: Action` slot to Route

2. **Update NLRI methods to take action as parameter**
   - `pack_nlri(negotiated, action) -> Buffer`
   - `feedback(action) -> str`
   - `json(action, compact) -> str`

3. **Remove `action` from NLRI.__slots__**

4. **Update all call sites** (grepped: ~50 locations)

### Phase 2: Move `nexthop` Out of Base NLRI

1. **Add `nexthop` to Route class**
   - Route already has `with_nexthop()` helper
   - Add `nexthop: IP` slot to Route

2. **Remove `nexthop` from NLRI base class**

3. **Subclasses that need nexthop for validation** can:
   - Take nexthop as parameter to validation methods
   - Or access via Route container

4. **Update collection.py** - nexthop packing logic moves to Route/Update level

### Phase 3: Enforce Immutability

After action/nexthop removed, NLRI has only identity fields:
- `afi`, `safi` (from Family)
- `addpath` (path ID, set once at creation)
- `_packed` (wire bytes, set once at creation)
- Subclass-specific fields (prefix, RD, labels, etc.)

1. **Add `__setattr__` guard** - block mutation after initial set
2. **Remove `with_action()` / `with_nexthop()`** - no longer needed
3. **Enable safe sharing** - same NLRI instance can be used for announce/withdraw

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/exabgp/rib/route.py` | Add `action`, `nexthop` slots |
| `src/exabgp/bgp/message/update/nlri/nlri.py` | Remove `action`, `nexthop` from slots |
| `src/exabgp/bgp/message/update/nlri/*.py` | Update pack_nlri, feedback, json signatures |
| `src/exabgp/bgp/message/update/collection.py` | Nexthop packing refactor |
| `src/exabgp/reactor/api/command/announce.py` | Set route.action instead of route.nlri.action |
| `src/exabgp/rib/outgoing.py` | Check route.action instead of route.nlri.action |
| `src/exabgp/configuration/*.py` | Build Route with action/nexthop |

---

## Benefits

1. **True immutability** - NLRI identity never changes after creation
2. **Memory savings** - No nexthop slot in every NLRI
3. **Semantic clarity** - Action is operation context, not data
4. **Safe sharing** - Same NLRI usable for announce and withdraw
5. **Simpler RIB** - Routes with identical NLRI can share NLRI reference

---

## Status

- [x] Ultrathink: Action should not be in NLRI
- [x] Ultrathink: Nexthop should not be in base NLRI
- [x] Revert previous session's incorrect changes (saved as backup)
- 🔄 Phase 1: Move action to Route
  - [x] Add action property to Route class with fallback
  - [x] Update Route constructor to accept action parameter
  - [x] Update route.nlri.action assignments to route.action
  - [x] Update cache.py to use route.action
  - [x] Update announce.py command handlers
  - [x] Update neighbor __init__.py
  - [x] Update validator.py Route creation
  - [x] Update vpls.py Route creation
  - [ ] **BLOCKED**: Test H (l2vpn) fails with server crash - needs investigation
- [ ] Phase 2: Move nexthop to Route
- [ ] Phase 3: Enforce immutability

## Current Blockers

### Test H (l2vpn encoding) Failure

**Symptom:** Server crashes (return_code=-1, "peer reset") when client connects

**What works:**
- Configuration validates successfully
- All other tests pass (35/36)
- Unit tests pass (2928)
- Config validation passes

**What fails:**
- Server crashes after KEEPALIVE sent
- Likely crash in RIB iteration or Update generation

**Next steps to investigate:**
1. Check if issue is in outgoing.py's iteration over routes
2. Check if VPLS routes have correct action set during RIB add
3. Add debug logging to find crash location

---

## Previous Session's Incorrect Changes (To Revert)

The previous session added `action` and `addpath` parameters to EVPN constructors and modified unpack_evpn signatures. This was the wrong direction - we should be **removing** action from NLRI, not propagating it further.

Files with incorrect changes:
- `src/exabgp/bgp/message/update/nlri/evpn/*.py` - Constructor changes
- `src/exabgp/bgp/message/update/nlri/nlri.py` - Various changes
- Several other NLRI files

---

**Updated:** 2025-12-09
