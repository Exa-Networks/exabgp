# NextHopSelf Refactoring Plan

**Status:** ✅ Phase 3 Complete (Mutate-in-place)
**Created:** 2025-12-08
**Updated:** 2025-12-08

---

## Executive Summary

`NextHopSelf` is a sentinel pattern that defers next-hop IP resolution until neighbor session context is known. Currently, resolution happens at **two points**:
1. **Configuration load time** via `neighbor.remove_self()` - PRIMARY (replaces sentinel permanently)
2. **Pack time** via `nlri.nexthop.ton(negotiated)` - SAFETY NET (if sentinel survives to packing)

The current design couples UPDATE parsing to neighbor session state (`Negotiated.neighbor`), preventing `Update` from using lightweight `OpenContext`.

---

## Current Architecture

### Class Hierarchy

```
NextHop (Attribute)
├── SELF: ClassVar[bool] = False
├── _packed: Buffer  # Wire-format IP bytes
├── ton() → self._packed
└── pack_attribute(negotiated) → self._attribute(self._packed)

NextHopSelf(NextHop)
├── SELF: ClassVar[bool] = True
├── _afi: AFI  # Address family (no packed bytes yet)
├── _packed = b''  # Empty placeholder
├── ton(negotiated, afi) → negotiated.nexthopself(afi).ton()
└── pack_attribute(negotiated) → self._attribute(negotiated.nexthopself(self._afi).ton())

IPSelf
├── SELF: ClassVar[bool] = True
├── afi: AFI
├── ton(negotiated, afi) → negotiated.nexthopself(afi).ton()
└── pack(negotiated) → negotiated.nexthopself(self.afi).ton()

IP
├── SELF: ClassVar[bool] = False
├── _packed: Buffer
└── ton() → self._packed
```

### Key Files

| File | Purpose |
|------|---------|
| `src/exabgp/bgp/message/update/attribute/nexthop.py:136-173` | `NextHopSelf` class definition |
| `src/exabgp/protocol/ip/__init__.py:29-50` | `IPSelf` class definition |
| `src/exabgp/bgp/neighbor/neighbor.py:281-289` | `remove_self()` - primary resolution |
| `src/exabgp/bgp/neighbor/session.py:105-127` | `ip_self()` - actual IP lookup |
| `src/exabgp/bgp/message/open/capability/negotiated.py:314-315` | `nexthopself()` - delegate to neighbor |

### Configuration Parsing (Sentinel Creation)

All parsers detect literal string `"self"` and create sentinels:

| Parser | File:Line | Creates |
|--------|-----------|---------|
| Static routes | `configuration/static/parser.py:88-95` | `IPSelf(afi), NextHopSelf(afi)` |
| Flow routes | `configuration/flow/parser.py:298-304` | `NextHopSelf(AFI.ipv4)` |
| L2VPN routes | `configuration/l2vpn/parser.py:51-56` | `NextHopSelf(AFI.ipv4)` |
| Validator | `configuration/validator.py:745-760` | `IPSelf(afi), NextHopSelf(afi)` |

### NLRI Nexthop Assignment

After parsing, nexthop (possibly `NextHopSelf`) is assigned to NLRI:

| File:Line | Context |
|-----------|---------|
| `configuration/static/route.py:511` | `new_nlri.nexthop = nexthop` |
| `configuration/announce/__init__.py:87` | `nlri.nexthop = nexthop` |

### Resolution Flow (Current)

```
Configuration File: "next-hop self"
         ↓
Parser: Creates NextHopSelf(AFI) sentinel
         ↓
Route.nlri.nexthop = NextHopSelf (SENTINEL STORED)
         ↓
neighbor.remove_self(route) called at config load time
         ↓
Checks: route.nlri.nexthop.SELF == True?
    ├── Yes → neighbor.ip_self(afi) → session.ip_self(afi)
    │         Returns: local_address or router_id
    │         Replaces: nlri.nexthop = resolved IP (permanent)
    │         Also: attributes[NEXT_HOP] = NextHop(resolved_ip)
    └── No  → Return route unchanged
         ↓
Route added to RIB (with resolved nexthop)
         ↓
Pack time: nlri.nexthop.ton(negotiated, afi)
    ├── IP.ton() → self._packed (already resolved)
    └── IPSelf.ton() → negotiated.nexthopself(afi).ton() (safety net)
```

### Call Sites for `remove_self()`

```python
# configuration/neighbor/__init__.py
neighbor.routes.append(neighbor.remove_self(route))  # Lines 442, 450, 456
route = neighbor.remove_self(route)                   # Line 462

# configuration/configuration.py
neighbor.rib.outgoing.add_to_rib(neighbor.remove_self(route))  # Line 79
```

### IP Resolution Logic (`session.ip_self()`)

```python
def ip_self(self, afi: AFI) -> IP:
    # Case 1: AFI matches local_address
    if not self.auto_discovery and afi == self.local_address.afi:
        return self.local_address

    # Case 2: IPv4 route with IPv6 session - use router_id
    if afi == AFI.ipv4 and self.router_id is not None:
        return self.router_id

    # Case 3: Cannot resolve - error
    raise TypeError('AFI mismatch...')
```

---

## Problem Statement

### Why This Matters for Wire-Semantic Separation

The `Update` class currently stores `Negotiated` because:
1. `Update.parse()` needs `negotiated.families` to filter NLRIs
2. `Update.parse()` needs `negotiated.neighbor` for next-hop-self resolution

If next-hop-self were resolved at NLRI **creation time** (not parsing time), `Update` could store lightweight `OpenContext` instead.

### Current Coupling

```
Update._negotiated: Negotiated
     │
     ├── families: list[tuple[AFI, SAFI]]  # Needed for NLRI filtering
     ├── neighbor: Neighbor                 # Needed for nexthopself()
     │       └── session.ip_self(afi)      # Resolves "self" to IP
     └── required(afi, safi): bool         # Needed for AddPath
```

### Desired State

```
Update._context: OpenContext  # Lightweight, no neighbor reference
     │
     ├── afi, safi, addpath, asn4, msg_size
     └── local_as, peer_as, is_ibgp

NLRI.nexthop: IP  # Always concrete, never sentinel
```

---

## Design Options

### Option A: Resolve at NLRI Creation Time (Early Resolution)

**Approach:** Pass resolved IP to NLRI constructor, never store sentinel.

**Pros:**
- Cleanest separation - NLRIs are always concrete
- `Update` can use `OpenContext`
- No sentinel classes needed

**Cons:**
- Requires IP at config parse time (neighbor session may not exist)
- Breaks deferred resolution pattern
- API change for all NLRI constructors

**Feasibility:** LOW - neighbor session doesn't exist at config parse time.

### Option B: Resolve at RIB Insertion (Current Pattern, Formalized)

**Approach:** Keep current `remove_self()` pattern but:
1. Make it explicit that RIB insertion is the resolution boundary
2. Assert NLRIs in RIB never have `SELF=True`
3. Remove pack-time safety net (fail fast if sentinel escapes)

**Pros:**
- Minimal code change
- Clear boundary (RIB = concrete data)
- Validates current invariant

**Cons:**
- Doesn't help `Update` use `OpenContext`
- Still need sentinel classes

**Feasibility:** HIGH - formalize existing behavior.

### Option C: Store Local IP in OpenContext

**Approach:** Add `local_ip: IP` field to `OpenContext`.

```python
class OpenContext:
    __slots__ = ('afi', 'safi', 'addpath', 'asn4', 'msg_size',
                 'local_as', 'peer_as', 'local_ip')
```

**Pros:**
- NLRIs can resolve nexthop via context
- `Update` can use `OpenContext`
- Single source of truth

**Cons:**
- `OpenContext` grows (but still lightweight)
- Caching key changes (adds IP to tuple)
- Chicken-and-egg: may not know local_ip at parse time

**Feasibility:** MEDIUM - depends on when local_ip is known.

### Option D: Two-Phase Parsing (Parse → Resolve)

**Approach:**
1. Parse UPDATE into structure with unresolved nexthops
2. Resolve nexthops in a second pass when session context available

```python
class Update:
    _context: OpenContext
    _needs_resolution: bool  # True if any nexthop is sentinel

def resolve_nexthops(self, neighbor: Neighbor) -> None:
    """Second pass: resolve any NextHopSelf sentinels."""
    for nlri in self.nlris:
        if nlri.nexthop.SELF:
            nlri.nexthop = neighbor.ip_self(nlri.afi)
```

**Pros:**
- Clear separation of parsing and resolution
- `Update` can use `OpenContext` for parsing
- Explicit about resolution requirement

**Cons:**
- Two-phase API more complex
- Callers must remember to call resolve
- Still need sentinel during transition

**Feasibility:** MEDIUM - cleaner but more complex.

### Option E: Resolve in `pack()` Only (Remove `remove_self()`)

**Approach:** Remove config-time resolution, always resolve at pack time.

**Pros:**
- Single resolution point
- Simplifies config loading

**Cons:**
- Sentinel persists longer (through RIB)
- Need `Negotiated` for packing (can't use `OpenContext`)
- Breaks current invariant

**Feasibility:** LOW - makes wire-semantic separation harder.

---

## Recommended Approach

**Option B (Formalize Current Pattern)** as Phase 1, **Option D (Two-Phase)** as Phase 2.

### Phase 1: Formalize Current Behavior

1. Add assertion that NLRIs in RIB never have `nexthop.SELF == True`
2. Document that `remove_self()` is the resolution boundary
3. Consider removing pack-time resolution (fail if sentinel escapes)

### Phase 2: Two-Phase Parsing (Future)

1. `Update.parse()` accepts `OpenContext` (no neighbor)
2. New method `Update.resolve_nexthops(neighbor)` resolves sentinels
3. Wire containers (`Update`) hold unresolved data
4. Semantic containers (`UpdateCollection`) hold resolved data

---

## Detailed Analysis

### When is Neighbor Session Available?

| Context | Session Available? | Can Resolve? |
|---------|-------------------|--------------|
| Config file parsing | No | No |
| `neighbor { }` block exit | Yes (Neighbor created) | Yes |
| Route added to neighbor.routes | Yes | Yes (current) |
| Route added to RIB | Yes | Yes (current) |
| UPDATE received from wire | Yes (established session) | Yes |
| UPDATE packed for sending | Yes | Yes (pack-time fallback) |

**Key insight:** Resolution can happen earliest at neighbor block exit.

### What Needs `nexthopself()` at Parse Time?

Currently: Nothing. Parse creates sentinel, resolution happens later.

The coupling is via `Negotiated.nexthopself()` which delegates to `neighbor.ip_self()`.

### What Actually Uses `Negotiated.neighbor` During Parsing?

```python
# collection.py:406-420 - NEXT_HOP validation
neighbor = getattr(negotiated, 'neighbor', None)
if nexthop is not IP.NoNextHop and neighbor is not None:
    local_address = neighbor.session.local_address
    if nexthop_packed == local_packed:
        log.warning('received NEXT_HOP equals our local address...')
```

This is a **validation** (RFC 4271 compliance check), not resolution. Could be deferred.

---

## Test Coverage

### Existing Tests

| Test | File | Coverage |
|------|------|----------|
| NextHopSelf unit tests | `tests/unit/test_path_attributes.py:882-897` | Basic construction |

### Tests Needed

- [ ] `remove_self()` replaces sentinel with concrete IP
- [ ] Sentinel never reaches RIB
- [ ] Pack-time resolution works as fallback
- [ ] AFI mismatch raises TypeError
- [ ] Router-id fallback for IPv4 routes with IPv6 session

---

## Implementation Plan

### Phase 1: Formalize & Document (Low Risk) ✅ COMPLETE

**Goal:** Make current behavior explicit with no functional changes.

1. **Add RIB entry assertion** ✅
   - In `rib.outgoing._update_rib()`, assert `nlri.nexthop.SELF == False`
   - Fast-fail if sentinel escapes to RIB
   - File: `src/exabgp/rib/outgoing.py:310-315`

2. **Add tests** ✅
   - Test `remove_self()` behavior
   - Test AFI resolution paths
   - Test sentinel detection
   - Test RIB rejection of unresolved sentinels
   - File: `tests/unit/test_nexthop_self.py` (26 tests)

3. **Document invariant** ✅
   - NLRIs in RIB always have concrete nexthop
   - `remove_self()` is the resolution boundary
   - Pack-time resolution is safety net (never triggered in practice)

### Phase 2: Remove Pack-Time Resolution ✅ COMPLETE

**Goal:** Remove redundant pack-time resolution - convert to errors.

1. **Verify sentinel never escapes** ✅
   - Phase 1 RIB assertion proves sentinels never reach pack time
   - All 11 test suites pass with assertion

2. **Convert pack-time resolution to errors** ✅
   - `NextHopSelf.pack_attribute()` → raises `RuntimeError`
   - `NextHopSelf.ton()` → raises `RuntimeError`
   - `IPSelf.top()` → raises `RuntimeError`
   - `IPSelf.ton()` → raises `RuntimeError`
   - `IPSelf.pack()` → raises `RuntimeError`
   - Files modified:
     - `src/exabgp/bgp/message/update/attribute/nexthop.py:165-179`
     - `src/exabgp/protocol/ip/__init__.py:39-61`

3. **Add tests for raise behavior** ✅
   - `test_pack_attribute_raises` - NextHopSelf
   - `test_ton_raises` - NextHopSelf
   - `test_top_raises` - IPSelf
   - `test_ton_raises` - IPSelf
   - `test_pack_raises` - IPSelf
   - File: `tests/unit/test_nexthop_self.py` (now 31 tests)

### Phase 3: Mutate-in-place Resolution ✅ COMPLETE

**Goal:** Change `resolve_self()` to mutate sentinels in-place instead of replacing.

**Design:**
- `SELF` stays as ClassVar (always True for sentinel classes)
- Resolution state detected via `_packed == b''` (unresolved) vs non-empty (resolved)
- Added `resolved` property and `resolve()` method

**Changes:**

1. **IPSelf (`src/exabgp/protocol/ip/__init__.py:37-76`)**
   - Added `_packed: Buffer` attribute
   - Added `resolved` property
   - Added `resolve(ip)` method
   - Added `ton()`, `pack_ip()` methods that raise if not resolved
   - Updated `__repr__()` and `index()` to handle resolved state

2. **NextHopSelf (`src/exabgp/bgp/message/update/attribute/nexthop.py:136-184`)**
   - Added `resolved` property
   - Added `resolve(ip)` method
   - Updated `pack_attribute()` to raise if not resolved
   - Updated `__repr__()` to handle resolved state

3. **resolve_self() (`src/exabgp/bgp/neighbor/neighbor.py:281-303`)**
   - Changed to call `nexthop.resolve(neighbor_self)` instead of replacing
   - Checks `nexthop.resolved` to skip already-resolved sentinels

4. **RIB assertion (`src/exabgp/rib/outgoing.py:309-316`)**
   - Changed to check `SELF and not resolved` (allows resolved sentinels)

5. **Tests (`tests/unit/test_nexthop_self.py`)**
   - Updated all tests for new behavior
   - Tests verify SELF stays True after resolution
   - Tests verify resolved transitions to True

**Key Invariants:**
- Before: `SELF=True`, `_packed=b''`, `resolved=False`
- After: `SELF=True`, `_packed=bytes`, `resolved=True`
- Pack methods raise `ValueError` if `not resolved`

### Phase 4: Two-Phase Parsing (Future)

**Goal:** Enable `Update` to use `OpenContext`.

1. **Add `Update.resolve_nexthops(neighbor)`**
2. **Change callers to call resolution explicitly**
3. **Change `Update._negotiated` to `Update._context`**

---

## Dependencies

- Wire-Semantic Separation plan (completed phases 1-3)
- OpenContext has `local_as`, `peer_as` (completed)

---

## Questions to Resolve

1. **Is pack-time resolution ever triggered?**
   - If yes, where?
   - If no, can we remove it?

2. **Should `Update` store sentinel or resolved IP?**
   - Wire container: Could store sentinel (raw wire + context)
   - Semantic container: Should store resolved IP

3. **Can NEXT_HOP validation be deferred?**
   - Currently in `_parse_payload()`, needs `neighbor.session.local_address`
   - Could move to post-parse validation phase

---

**Updated:** 2025-12-08
