# Phase 4: Remove OpenContext Class

**Status:** ✅ Completed
**Created:** 2025-12-08
**Completed:** 2025-12-09
**Depends on:** Phase 3 (Mutate-in-place resolution) ✅

---

## Goal

Simplify the codebase by removing the `OpenContext` class entirely and storing the minimal required context directly in classes that need it.

---

## What Was Done

### Removed OpenContext Class

The `OpenContext` class was a lightweight cached subset of `Negotiated` with fields:
- `afi`, `safi` - address family
- `addpath` - whether AddPath is enabled
- `asn4`, `msg_size`, `local_as`, `peer_as` - from Negotiated

Analysis showed that only `addpath` was actually used for NLRI parsing.

### Updated Classes to Store Context Directly

**MPRNLRI / MPURNLRI:**
- Changed from `__init__(packed, context: OpenContext)` to `__init__(packed, addpath: bool)`
- Now stores just `_addpath` instead of full `OpenContext`
- AFI/SAFI already available from wire bytes via `Family` inheritance

**NLRICollection:**
- Changed from `__init__(packed, context, action)` to `__init__(packed, afi, safi, addpath, action)`
- Stores `_afi`, `_safi`, `_addpath` directly
- `make_collection()` updated to take `afi, safi, nlris, action`

**MPNLRICollection:**
- Changed from `__init__(nlris, attributes, context)` to `__init__(nlris, attributes, afi, safi)`
- Stores `_afi`, `_safi` directly
- `from_wire()` updated to take `afi, safi` parameters

### Removed from Negotiated

- Deleted `OpenContext` class (lines 31-99)
- Deleted `nlri_context()` method

---

## Files Modified

| File | Changes |
|------|---------|
| `src/exabgp/bgp/message/open/capability/negotiated.py` | Removed OpenContext class and nlri_context() method (-70 lines) |
| `src/exabgp/bgp/message/update/attribute/mprnlri.py` | Store addpath:bool instead of OpenContext |
| `src/exabgp/bgp/message/update/attribute/mpurnlri.py` | Store addpath:bool instead of OpenContext |
| `src/exabgp/bgp/message/update/nlri/collection.py` | Store afi/safi/addpath directly |
| `src/exabgp/bgp/message/update/collection.py` | Pass afi/safi directly to MPNLRICollection |
| `tests/unit/test_collection.py` | Updated for new API |
| `tests/unit/test_multiprotocol.py` | Updated for new API |
| `tests/fuzz/test_update_message_integration.py` | Removed nlri_context from mock |

---

## Test Results

All 13 test suites pass:
```
✓ All 13 tests passed in 1m41s
```

---

## Benefits Achieved

1. **Simpler:** Removed 70 lines of cached context class
2. **Clearer:** Each class stores only what it needs
3. **No caching overhead:** No OpenContext._cache dictionary
4. **Direct access:** Fields accessed directly, not via context object

---

**Updated:** 2025-12-09
