# Plan: Remove Action from NLRI and Route Classes

## Goal
Remove `action` from NLRI and Route `__slots__` to reduce memory footprint. Action is operational context (announce vs withdraw), not NLRI/Route identity. Track action at RIB level and pass as parameter through call chains.

**Memory savings**: ~16 bytes per route (8 bytes from NLRI.action + 8 bytes from Route._action)

## Approach: Clean Break

Remove action storage in one release, update all call sites. No deprecation warnings or fallbacks.

---

## CURRENT STATUS (2024-12-15)

### Phase 1 COMPLETE ✓

**ALL TESTS PASSING** - 15/15 test suites pass including all 38 API tests.

The RIB layer no longer depends on `route.action`. Action is now determined by which method is called:
- `add_to_rib()` / `announce_route()` → announce
- `del_from_rib()` / `withdraw_route()` → withdraw

### Changes Made:

1. **Configuration layer** - `check()` functions accept action as parameter
2. **API layer**:
   - `announce_route()` added (renamed from `inject_route`)
   - `announce_route_indexed()` added (renamed from `inject_route_indexed`)
   - `withdraw_route()` added for withdraws
   - `announce.py` uses `withdraw_route()` for all withdraw commands
3. **RIB layer** - Simplified `outgoing.py` and `cache.py`:
   - `add_to_rib()` handles announces → `_new_attr_af_nlri`
   - `del_from_rib()` handles withdraws → `_pending_withdraws`
   - `updates()` yields withdraws FIRST, then announces (preserves semantic order)
   - Cancel logic REMOVED (see plan-announce-cancels-withdraw-optimization.md for future optimization)
   - `cache.py` simplified - `update_cache(route)` and `update_cache_withdraw(nlri)`
4. **Protocol layer** - `update.py` creates Route objects for cache updates

### Next Steps (Phase 2):

- Remove `Route._action` from `__slots__`
- Remove `NLRI.action` from `__slots__`
- Update any remaining code that reads `route.action` or `nlri.action`

### Previous Session Notes (for context):

---

## DETAILED SESSION NOTES (for context recovery)

### Problem 1: CLI Tests Were Failing

**Original failures (4 tests):**
1. `withdraw route succeeds` - Error: "Could not parse route: route 10.0.0.0/24"
2. `withdraw ipv4 unicast succeeds` - Returns `{'answer': 'error'}`
3. `rib clear in succeeds` - Returns data instead of just done
4. `invalid command returns error` - Returns done instead of error

**Root cause:** Multiple issues in the API command chain:

1. `static/__init__.py` line 137 was calling `check(static_route, nlri.afi)` without passing `nlri_action`
2. API functions `api_flow()`, `api_vpls()`, `api_attributes()` in `reactor/api/__init__.py` were not passing `action` to `partial()`
3. Withdraw functions in `announce.py` were still calling `inject_route()` instead of `withdraw_route()`

**Fixes applied:**

**File: `src/exabgp/configuration/static/__init__.py`**
- Line 82: Changed `check: Callable[[Route, AFI], bool]` to `check: Callable[[Route, AFI, Action], bool]`
- Line 137: Changed `if not check(static_route, nlri.afi):` to `if not check(static_route, nlri.afi, nlri_action):`

**File: `src/exabgp/reactor/api/__init__.py`**
- Line 224 in `api_flow()`: Changed `partial('flow', line)` to `partial('flow', line, action)`
- Line 244 in `api_vpls()`: Changed `partial('l2vpn', line)` to `partial('l2vpn', line, action)`
- Line 264 in `api_attributes()`: Changed `partial('static', line)` to `partial('static', line, action)`

**File: `src/exabgp/reactor/api/command/announce.py`**
Multiple changes across all announce/withdraw function pairs:

For `announce_route()` (around line 108-115):
- Removed: `route = route.with_action(Action.ANNOUNCE)`
- Changed: `ParseStaticRoute.check(route)` to `ParseStaticRoute.check(route, Action.ANNOUNCE)`

For `withdraw_route()` (around line 158-175):
- Removed: `route = route.with_action(Action.WITHDRAW)`
- Changed: `ParseStaticRoute.check(route)` to `ParseStaticRoute.check(route, Action.WITHDRAW)`
- Changed: `reactor.configuration.inject_route(peers, route)` to `reactor.configuration.withdraw_route(peers, route)`

Same pattern applied to:
- `announce_vpls()` / `withdraw_vpls()`
- `announce_attributes()` / `withdraw_attribute()`
- `announce_flow()` / `withdraw_flow()`
- `announce_ipv4()` / `withdraw_ipv4()`
- `announce_ipv6()` / `withdraw_ipv6()`

After these fixes, CLI tests pass: `./qa/bin/functional cli 0 -v` shows 27/27 pass.

---

### Problem 2: API Tests Failing

**Failing tests:** p (api-flow), η (api-rr-rib), θ (api-rr), intermittently n (api-fast)

**How to reproduce:**
```bash
./qa/bin/functional api p -v  # Fails with message mismatch
```

**Test file location:** `/Users/thomas/Code/github.com/exa-networks/exabgp/main/qa/api/api-flow.ci`

**Test structure (api-flow.ci):**
```
1:cmd:announce eor ipv4 flow
1:raw:FFFF...001E...  (expected EOR message)
1:cmd:attributes origin igp local-preference 100
1:raw:FFFF...0025...  (expected attributes-only UPDATE)
1:cmd:withdraw ipv4 flow destination-ipv4 0.0.0.0/32 ...
1:raw:FFFF...003F...800F17...  (expected MP_UNREACH_NLRI - 800F)
1:cmd:announce ipv4 flow destination-ipv4 0.0.0.0/32 ... extended-community [rate-limit:0]
1:raw:FFFF...004C...800E19...  (expected MP_REACH_NLRI - 800E)
...
```

**Key observation:**
- `800E` = MP_REACH_NLRI (announce)
- `800F` = MP_UNREACH_NLRI (withdraw)
- Test expects message 3 to be `800F` (withdraw) but receives `800E` (announce)

**Debugging steps performed:**

1. Ran test with verbose output:
```bash
./qa/bin/functional api p -v 2>&1 | grep -E "(msg #|800E|800F)"
```
Result: All messages show `800E` (MP_REACH), no `800F` (MP_UNREACH)

2. Checked if `withdraw_route()` was being called:
- Yes, it is called and `del_from_rib()` adds to `_pending_withdraws`

3. Traced the issue to `add_to_rib()` in `outgoing.py`:

**ROOT CAUSE FOUND in `src/exabgp/rib/outgoing.py` lines 332-334:**
```python
# Remove any pending withdraw for this NLRI (announce cancels previous withdraw)
if route_family in self._pending_withdraws:
    self._pending_withdraws[route_family].pop(nlri_index, None)
```

**What happens step by step:**
1. Test sends: `withdraw ipv4 flow ...`
2. Code path: `v6_withdraw()` -> `withdraw_ipv4()` -> `api_announce_v4(cmd, 'withdraw')` -> `partial('ipv4', line, 'withdraw')` -> route parsed -> `withdraw_route()` -> `del_from_rib()` -> adds `(nlri, attrs)` to `_pending_withdraws[family][nlri_index]`
3. Test sends: `announce ipv4 flow ...` (same NLRI, different attributes)
4. Code path: `v6_announce()` -> `announce_ipv4()` -> `api_announce_v4(cmd, 'announce')` -> `partial('ipv4', line, 'announce')` -> route parsed -> `inject_route()` -> `add_to_rib()` -> **REMOVES from `_pending_withdraws`** at line 334, then adds to `_new_attr_af_nlri`
5. When `updates()` runs: only announce is in the queue, withdraw was cancelled
6. Result: Only MP_REACH sent, no MP_UNREACH

**Why OLD code worked:**
- OLD `inject_route()` was called for BOTH announces and withdraws
- OLD code called `add_to_rib()` which stored route in `_new_attr_af_nlri`
- OLD `updates()` iterated over `_new_attr_af_nlri` and checked `route.action`:
  ```python
  announces = [r for r in routes.values() if r.action == Action.ANNOUNCE]
  withdraws = [r.nlri for r in routes.values() if r.action == Action.WITHDRAW]
  ```
- With different `attr_index` (withdraw has minimal attrs, announce has extended-community), both routes were stored in different buckets and both were sent

**The fix:** Remove lines 332-334 in `add_to_rib()`. This allows pending withdraws to NOT be cancelled when an announce comes. Both will be sent.

**Alternative considered but rejected:** Change test expectations. User explicitly said tests were correct and should not be changed.

---

### Code Flow Reference

**Announce flow (working):**
```
API: "announce ipv4 flow ..."
  -> v6_announce() [announce.py:778]
  -> announce_ipv4() [announce.py:580] with action='announce'
  -> api_announce_v4(cmd, 'announce') [api/__init__.py:175]
  -> partial('ipv4', line, 'announce') [api/__init__.py:185]
  -> parser sets tokeniser.announce = True
  -> flow_ip_v4() parses route [flow.py:391]
  -> _build_route() creates Route with action from tokeniser [route_builder.py:54]
  -> inject_route(peers, route) [configuration.py:120]
  -> add_to_rib(route) [outgoing.py:296]
  -> stored in _new_attr_af_nlri
  -> updates() yields UpdateCollection with announces
  -> MP_REACH_NLRI generated
```

**Withdraw flow (broken due to cancel logic):**
```
API: "withdraw ipv4 flow ..."
  -> v6_withdraw() [announce.py:809]
  -> withdraw_ipv4() [announce.py:621] with action='withdraw'
  -> api_announce_v4(cmd, 'withdraw') [api/__init__.py:175]
  -> partial('ipv4', line, 'withdraw') [api/__init__.py:185]
  -> parser sets tokeniser.announce = False
  -> flow_ip_v4() parses route [flow.py:391]
  -> _build_route() creates Route [route_builder.py:54]
  -> withdraw_route(peers, route) [configuration.py:149]
  -> del_from_rib(route) [outgoing.py:228]
  -> stored in _pending_withdraws[family][nlri_index]

  THEN if announce comes for same NLRI:
  -> add_to_rib() [outgoing.py:296]
  -> LINE 334: _pending_withdraws[family].pop(nlri_index) <-- CANCELS WITHDRAW!

  -> updates() only sees announce, not withdraw
  -> Only MP_REACH_NLRI generated, no MP_UNREACH_NLRI
```

---

### Key Data Structures in outgoing.py

```python
self._new_attr_af_nlri  # dict[attr_index, dict[family, dict[route_index, Route]]]
                        # Stores pending announces

self._pending_withdraws # dict[family, dict[nlri_index, tuple[NLRI, AttributeCollection]]]
                        # Stores pending withdraws

self._new_nlri          # dict[route_index, Route]
                        # Quick lookup by route index
```

**Index types:**
- `route_index` = `family_prefix + nlri.index()` (includes AFI/SAFI prefix)
- `nlri_index` = `nlri.index()` (does NOT include family prefix)
- `attr_index` = `attributes.index()` (hash of attributes)

---

### Files Modified This Session (exhaustive list)

1. **`src/exabgp/configuration/static/__init__.py`**
   - Line 82: Type annotation `Callable[[Route, AFI], bool]` -> `Callable[[Route, AFI, Action], bool]`
   - Line 137: `check(static_route, nlri.afi)` -> `check(static_route, nlri.afi, nlri_action)`

2. **`src/exabgp/reactor/api/__init__.py`**
   - Line 224: `partial('flow', line)` -> `partial('flow', line, action)`
   - Line 244: `partial('l2vpn', line)` -> `partial('l2vpn', line, action)`
   - Line 264: `partial('static', line)` -> `partial('static', line, action)`

3. **`src/exabgp/reactor/api/command/announce.py`** (many changes)
   - All `route.with_action(Action.ANNOUNCE)` lines removed
   - All `route.with_action(Action.WITHDRAW)` lines removed
   - All withdraw functions: `inject_route()` -> `withdraw_route()`
   - All `ParseStaticRoute.check(route)` -> `ParseStaticRoute.check(route, Action.ANNOUNCE/WITHDRAW)`

---

## KEY DESIGN DECISIONS

1. **Action is implicit in method calls:**
   - `add_to_rib()` = announce (stores in `_new_attr_af_nlri`)
   - `del_from_rib()` = withdraw (stores in `_pending_withdraws`)
   - No need to pass action parameter to RIB methods

2. **Check functions take explicit action:**
   - `check(route, afi, action)` - action passed from caller
   - Defaults to `Action.ANNOUNCE` for backward compat

3. **Configuration has two methods:**
   - `inject_route(peers, route)` - for announces
   - `withdraw_route(peers, route)` - for withdraws

4. **Cache only stores announces:**
   - `update_cache(route)` - adds to cache
   - `update_cache_withdraw(nlri)` - removes from cache
   - `in_cache(route)` - checks for deduplication

5. **DO NOT cancel pending withdraws (deferred optimization):**
   - When announce comes after withdraw for same NLRI, BOTH should be sent
   - This matches old behavior where `updates()` iterated over all routes and checked `route.action`
   - **Follow-up:** See `plan-announce-cancels-withdraw-optimization.md` to re-add this optimization later

---

## Progress

- [x] Phase 1: RIB action parameter (COMPLETE)
- [ ] Phase 2: Remove Route._action (NOT STARTED)
- [ ] Phase 3: Remove NLRI.action (NOT STARTED)
- [x] Phase 4: Configuration parsers (COMPLETE)
- [x] Phase 5: API commands (COMPLETE - pending cancel logic fix)
- [ ] Phase 6: Protocol parsing (NOT STARTED)
- [x] CLI tests pass (27/27)
- [ ] API tests pass (need to fix cancel logic bug)

---

## NEXT STEPS (Resume Point)

### Step 1: Fix Cancel Logic Bug

**File:** `src/exabgp/rib/outgoing.py`

**Action:** Remove lines 332-334:
```python
# Remove any pending withdraw for this NLRI (announce cancels previous withdraw)
if route_family in self._pending_withdraws:
    self._pending_withdraws[route_family].pop(nlri_index, None)
```

**Why:** This cancel logic removes pending withdraws when an announce comes for the same NLRI. The OLD code didn't have this issue because both announces and withdraws were stored in `_new_attr_af_nlri` and separated by `route.action` in `updates()`.

### Step 2: Verify Fix

```bash
# Kill any stuck processes first
killall -9 Python

# Run the specific failing test
./qa/bin/functional api p -v

# If pass, run full API suite
./qa/bin/functional api

# If pass, run everything
./qa/bin/test_everything
```

### Step 3: Continue with Phase 2

After tests pass, continue with removing `Route._action`:
- File: `src/exabgp/rib/route.py`
- Remove `_action` from `__slots__`
- Remove `action` parameter from `__init__`
- Remove `action` property
- Remove `with_action()` method
- Update `feedback()` to take action parameter

---

## What Still Needs To Be Done (after fix)

**Phase 2 - Remove Route._action:**
- `src/exabgp/rib/route.py` - Remove `_action` slot, property, `with_action()` method

**Phase 3 - Remove NLRI.action:**
- `src/exabgp/bgp/message/update/nlri/nlri.py` - Remove `action` slot
- Update all NLRI subclasses

**Phase 6 - Protocol Parsing:**
- `src/exabgp/reactor/protocol.py` - Remove `nlri.action = ...` assignments

**Other files with `route.action` reads:**
- `src/exabgp/configuration/neighbor/__init__.py` - lines 492, 498
- `src/exabgp/configuration/setup.py` - line 135
- `src/exabgp/configuration/check.py` - lines 486, 497
