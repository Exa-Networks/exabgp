# Plan: INET/Label/IPVPN Packed-Bytes-First Pattern

**Status:** ✅ Phase 1 Complete (INET)
**Created:** 2025-12-08
**Last Updated:** 2025-12-08

---

## Progress

### Phase 1: INET Class - COMPLETE ✅

**Implemented:**
1. Replaced `path_info` slot with `_has_addpath: bool` slot
2. Updated `__init__` to accept `has_addpath` parameter
3. Added `_mask_offset` property (returns 0 or 4 based on `_has_addpath`)
4. Added `path_info` property (extracts from `_packed[0:4]` if `_has_addpath`)
5. Updated `cidr` property to use `_mask_offset`
6. Updated `pack_nlri()` with proper AddPath handling
7. Updated `__hash__()`, `index()`, `__len__()` to use `_packed` directly
8. Updated factory methods (`from_cidr`) to build wire format with AddPath

**Also completed:**
- Removed `labels` setter from Label class
- Removed `rd` setter from IPVPN class
- Updated Label and IPVPN `__init__`, `from_cidr`, `from_settings` methods
- Updated Label and IPVPN `__copy__` and `__deepcopy__` methods
- Updated configuration parsing to use settings mode for nested route syntax
- Removed legacy mode from configuration parsing (NLRI are now immutable)
- Updated documentation with NLRI immutability rule

**Tests:** All 2877 unit tests pass, all 11 test suites pass

---

## Remaining Work

### Phase 2: Label Class - NOT STARTED

Store labels in `_packed` instead of separate `_labels_packed` slot.

1. Remove `_labels_packed` slot
2. Update `__init__` to accept complete wire format including labels
3. Add `_label_end_offset()` helper for BOS scanning
4. Update `labels` property to extract from `_packed`
5. Override `cidr` property to extract from after labels

### Phase 3: IPVPN Class - NOT STARTED

Store RD in `_packed` instead of separate `_rd_packed` slot.

1. Remove `_rd_packed` slot
2. Update `__init__` to accept complete wire format including labels and RD
3. Add `rd` property to extract from `_packed[label_end:label_end+8]`
4. Override `cidr` property to extract from after RD
5. Update `unpack_nlri()` to store complete wire format

---

## Key Changes Made

### NLRI Immutability

**All INET/Label/IPVPN NLRI are now immutable after creation.**

- No property setters for `path_info`, `labels`, `rd`
- Factory methods (`from_cidr`, `from_settings`) must receive all values upfront
- Configuration parsing uses settings mode (INETSettings) for deferred construction

### Configuration Parsing

**Nested route syntax now uses settings mode:**

```
route 10.0.0.0/24 {
    rd 65000:1;
    label 100;
    next-hop 1.2.3.4;
}
```

- `pre()` creates INETSettings and enters settings mode
- Parsed values populate the settings object
- `post()` creates immutable NLRI from settings

**Flow NLRI kept mutable** - Flow is a separate hierarchy with its own setters.

---

## Wire Format

```
INET:  [addpath:4?][mask:1][prefix:var]
Label: [addpath:4?][mask:1][labels:3n][prefix:var]
IPVPN: [addpath:4?][mask:1][labels:3n][rd:8][prefix:var]
```

Currently:
- INET: `_packed` = `[addpath:4?][mask:1][prefix:var]` ✅
- Label: `_packed` = `[addpath:4?][mask:1][prefix:var]`, `_labels_packed` = labels (still separate)
- IPVPN: `_packed` = `[addpath:4?][mask:1][prefix:var]`, `_labels_packed` = labels, `_rd_packed` = rd (still separate)

---

## Verification

```bash
./qa/bin/test_everything  # All 11 tests pass
```
