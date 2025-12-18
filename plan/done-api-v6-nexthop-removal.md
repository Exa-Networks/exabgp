# API v6: Remove nexthop from NLRI JSON

## Status: Future Work

## Background

As part of the NLRI immutability refactoring (Phase 4), we separated nexthop from NLRI identity.
The nexthop is now stored in `Route` or `RoutedNLRI` containers, not in the NLRI itself.

However, the JSON API still includes `"next-hop"` in NLRI objects for backward compatibility
with API v4 users.

## Current State

- `NLRI.extensive()` methods no longer include nexthop (removed in Phase 4 Step 6)
- `NLRI.json()` methods still include nexthop for backward compatibility
- `Route.extensive()` now includes nexthop from `Route._nexthop`
- Text API responses include nexthop from `RoutedNLRI` context

## Goal

Remove `"next-hop"` from NLRI JSON objects in API v6, since:
1. nexthop is already available in the grouping key (e.g., `"ipv4 flow": {"1.2.3.4": [...]}`)
2. nexthop is not part of NLRI identity
3. Cleaner JSON structure

## Implementation Plan

### Step 1: Add compatibility flag to NLRI.json() methods

Add optional `include_nexthop: bool = True` parameter to all `NLRI.json()` methods:
- `flow.py:json()`
- Any other NLRI types with json() that include nexthop

### Step 2: Pass compatibility flag from API version

The v4 to v6 API conversion layer should pass `include_nexthop=False` when generating v6 JSON.

Files to modify:
- `src/exabgp/reactor/api/response/json.py`
- `src/exabgp/reactor/api/response/v4/json.py`

### Step 3: Update expected JSON in tests

When API v6 is the default, update:
- `qa/encoding/conf-flow.ci` - remove `"next-hop"` from expected JSON
- Any other test files with expected JSON containing NLRI nexthop

### Step 4: Documentation

- Document the API change in release notes
- Update API documentation to reflect v6 structure

### Step 5: Remove nexthop from NLRI.__slots__

This is the final cleanup from Phase 4 Step 7 of the NLRI immutability plan.

Once nexthop is no longer needed in `NLRI.json()` methods, remove it entirely:

1. **Remove `'nexthop'` from `NLRI.__slots__`** (`src/exabgp/bgp/message/update/nlri/nlri.py:43`)

2. **Remove `self.nexthop = ...`** from all NLRI `__init__` methods:
   - `nlri/inet.py` - INET class
   - `nlri/label.py` - Label class
   - `nlri/ipvpn.py` - IPVPN class
   - `nlri/flow.py` - Flow class
   - `nlri/vpls.py` - VPLS class
   - Other NLRI subclasses

3. **Remove from `__copy__`, `__deepcopy__`** methods in NLRI classes

4. **Remove from factory methods** (`from_cidr()`, `make_flow()`, etc.)

5. **Remove from `_copy_nlri_slots()` and `_deepcopy_nlri_slots()`** helper methods

6. **Update any remaining code** that sets `nlri.nexthop`:
   - `mprnlri.py` - currently sets `nlri.nexthop` for backward compat
   - Config parsing code
   - Any other locations

**Estimated scope:** ~50 files, ~100 changes

**Prerequisite:** Steps 1-4 must be complete (nexthop no longer read from NLRI)

## NLRI Types with json() that include nexthop

Currently identified:
- `flow.py` - has `"next-hop": "{}"` in json() output

Need to audit:
- `inet.py`
- `label.py`
- `ipvpn.py`
- `vpls.py`
- Other NLRI types

## Related

- `plan/nlri-immutability-phase3-routednlri.md` - Phase 4 implementation
- `plan/nlri-immutability.md` - Original NLRI immutability plan

## Notes

The `"string"` field in Flow JSON (`"string": "flow destination-ipv4 ..."`) also changed
because `extensive()` no longer includes nexthop. This is consistent with the model that
NLRI identity doesn't include nexthop.
