# Plan: Move Route Validation to Wire Format Generation

## Problem

Route validation (nexthop, labels, RD) was being done during parsing via `check()` functions. This is broken because:

1. **Withdrawals don't need these values** - per RFC 4271, MP_UNREACH_NLRI contains only the NLRI, no nexthop/attributes
2. **Announces need these values** - MP_REACH_NLRI requires nexthop, labeled routes need labels, VPN routes need RD
3. **Parsing doesn't know the action** - after removing action from Route/NLRI, check functions can't distinguish announce vs withdraw

Current broken check functions:
- `AnnounceIP.check` - nexthop validation (removed, was broken)
- `AnnounceLabel.check` - labels validation (broken - can't distinguish action)
- `AnnounceVPN.check` - RD validation (broken - can't distinguish action)

## Solution

Move validation to wire format generation time in `UpdateCollection.messages()` where we know:
- Which NLRIs are announces (go into MP_REACH_NLRI)
- Which NLRIs are withdraws (go into MP_UNREACH_NLRI)

## Implementation

### Phase 1: Remove All Check Functions (COMPLETE)

Remove the broken check infrastructure:
- [x] Remove `AnnounceIP.check()`
- [x] Remove `AnnouncePath.check()` (was already removed, no check method)
- [x] Remove `AnnounceLabel.check()`
- [x] Remove `AnnounceVPN.check()`
- [x] Remove `AnnounceVPLS.check()`
- [x] Remove `AnnounceFlow.check()`
- [x] Remove `AnnounceMVPN.check()`
- [x] Remove `AnnounceMUP.check()`
- [x] Remove `ParseStaticRoute.check()` and `_check()`
- [x] Remove `check_func` parameter from `_build_route()` and `_build_type_selector_route()`
- [x] Remove all check calls from API command handlers (announce.py, group.py, route.py)
- [x] Remove check from `static/__init__.py`
- [x] Clean up unused imports (Labels, RouteDistinguisher, cast, etc.)

### Phase 2: Add Wire Format Validation (COMPLETE)

Location: `src/exabgp/bgp/message/update/collection.py` in `messages()` method

Added validation in the announce processing loop (before sorting into v4/mp categories):

```python
# Wire format validation for announces (not needed for withdraws)
# Validates that required fields are present before generating MP_REACH_NLRI

# 1. Nexthop validation - required for unicast/multicast announces
if nlri.safi in (SAFI.unicast, SAFI.multicast):
    if nexthop is IP.NoNextHop:
        raise ValueError(f'announce requires nexthop: {nlri}')

# 2. Labels validation - required for labeled route announces
if nlri.safi.has_label():
    if isinstance(nlri, Label) and nlri.labels is Labels.NOLABEL:
        raise ValueError(f'labeled route announce requires labels: {nlri}')

# 3. RD validation - required for VPN route announces
if nlri.safi.has_rd():
    if isinstance(nlri, IPVPN) and nlri.rd is RouteDistinguisher.NORD:
        raise ValueError(f'VPN route announce requires RD: {nlri}')
```

**For withdraws:** No validation needed - withdraws only need NLRI identity.

**Tests updated:**
- `test_announce_ipv6_undefined_nexthop_raises_valueerror` - expects new error message
- `test_announce_ipv4_undefined_nexthop_raises_valueerror` - expects new error message

### Phase 3: API-Level Validation (COMPLETE)

Added early validation at API level for immediate user feedback.

**Shared validation function** `validate_announce_nlri(nlri, nexthop)` in `collection.py`:
- Single source of truth for validation logic
- Called at wire format generation (required for config file routes)
- Called at API level via `validate_announce()` wrapper (immediate feedback)

API-level wrapper `validate_announce(route)` in `announce.py`:
- Extracts nlri/nexthop from Route and calls shared function
- Used by API handlers for early feedback

Added validation calls in:
- `announce_route()` in `announce.py` - returns error immediately
- `group` command handler in `group.py` - adds to errors list
- `routes add` handler in `route.py` - returns error in result object

**Why both validation points exist:**
- Config file routes bypass API → need wire format validation
- API routes benefit from immediate feedback → call shared function early
- Same logic, no duplication

## Files to Modify

### Phase 1 (Remove check functions):
- `src/exabgp/configuration/announce/ip.py` - remove check method
- `src/exabgp/configuration/announce/path.py` - remove check method
- `src/exabgp/configuration/announce/label.py` - remove check method
- `src/exabgp/configuration/announce/vpn.py` - remove check method
- `src/exabgp/configuration/announce/vpls.py` - remove check method
- `src/exabgp/configuration/announce/flow.py` - remove check method
- `src/exabgp/configuration/announce/mvpn.py` - remove check method
- `src/exabgp/configuration/announce/mup.py` - remove check method
- `src/exabgp/configuration/announce/route_builder.py` - remove check_func parameter
- `src/exabgp/configuration/static/route.py` - remove check method
- `src/exabgp/configuration/static/__init__.py` - remove check call
- `src/exabgp/reactor/api/command/announce.py` - remove check calls
- `src/exabgp/reactor/api/command/group.py` - remove check calls
- `src/exabgp/reactor/api/command/route.py` - remove check calls

### Phase 2 (Add wire format validation):
- `src/exabgp/bgp/message/update/collection.py` - add validation in messages()

## Testing

1. All existing tests should pass (validation moves, doesn't disappear)
2. Test announce without nexthop → should fail at wire generation
3. Test withdraw without nexthop → should succeed
4. Test labeled route announce without labels → should fail
5. Test VPN route announce without RD → should fail

## Benefits

1. **Correct semantics** - validation happens where we know announce vs withdraw
2. **Simpler parsing** - no check functions cluttering the code
3. **Single validation point** - wire format generation is the authority
4. **Better error messages** - can include context about what's being generated
