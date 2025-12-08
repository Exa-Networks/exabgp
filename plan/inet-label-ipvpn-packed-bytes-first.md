# Plan: INET/Label/IPVPN Packed-Bytes-First Pattern

**Status:** ✅ All Phases Complete
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

### Phase 2: Label Class - COMPLETE ✅

**Implemented:**
1. ✅ Removed `_labels_packed` slot, added `_has_labels: bool` slot
2. ✅ Updated `__init__` to accept `has_labels` parameter
3. ✅ Added `_label_end_offset` property for BOS scanning
4. ✅ Updated `labels` property to extract from `_packed`
5. ✅ Overrode `cidr` property to extract from after labels
6. ✅ Updated `from_cidr` to build wire format with labels
7. ✅ Updated `from_settings` (delegates to `from_cidr`)
8. ✅ Updated `pack_nlri()` for zero-copy (returns `_packed` directly)
9. ✅ Updated `__hash__`, `__eq__`, `__len__` for new storage
10. ✅ Updated `__copy__` and `__deepcopy__` to copy `_has_labels`
11. ✅ Updated IPVPN class for Label changes
12. ✅ Fixed `_normalize_nlri_type()` to use `_has_labels` (not `_labels_packed`)

**Test Results:**
- ✅ All 2889 unit tests pass (12 new tests added)
- ✅ All 35 test_label.py tests pass
- ✅ All 18 decoding functional tests pass
- ✅ All 36 encoding functional tests pass (including Test Q)

**Bug Fixed:**
`_normalize_nlri_type()` in `src/exabgp/configuration/static/route.py` was checking for
the non-existent `_labels_packed` attribute. The packed-bytes-first Label class uses
`_has_labels` flag instead. This caused Label NLRIs to be incorrectly downgraded to
INET, losing labels.

**Fix:**
Changed line 374 from:
```python
has_label = hasattr(ipvpn_nlri, '_labels_packed') and ipvpn_nlri._labels_packed
```
To:
```python
has_label = hasattr(ipvpn_nlri, '_has_labels') and ipvpn_nlri._has_labels
```

**New Unit Tests Added:**
`tests/unit/configuration/test_normalize_nlri_type.py` (12 tests):
- `TestNormalizeNlriTypeLabel` - Label preservation through normalization
- `TestNormalizeNlriTypeIPVPN` - IPVPN preservation with RD
- `TestNormalizeNlriTypeINET` - INET pass-through
- `TestLabelFromSettings` - Settings pattern label inclusion
- `TestIPVPNFromSettings` - Settings pattern with labels and RD
- `TestLabelHasLabelsAttribute` - Verify `_has_labels` exists (not `_labels_packed`)
- `TestLabelPreservationThroughNormalization` - Full round-trip verification

---

### Phase 3: IPVPN Class - COMPLETE ✅

**Implemented:**
1. ✅ Removed `_rd_packed` slot, added `_has_rd: bool` slot
2. ✅ Updated `__init__` to accept `has_labels` and `has_rd` parameters
3. ✅ Added `_rd_end_offset` property (returns label_end or label_end+8 based on `_has_rd`)
4. ✅ Updated `rd` property to extract from `_packed[label_end:label_end+8]` if `_has_rd`
5. ✅ Overrode `cidr` property to extract from after RD using `_rd_end_offset`
6. ✅ Updated `from_cidr` to build wire format with RD in `_packed`
7. ✅ Updated `pack_nlri()` for zero-copy (returns `_packed` directly)
8. ✅ Updated `unpack_nlri()` to store complete wire format including RD
9. ✅ Updated `__hash__`, `__eq__`, `__len__` for new storage
10. ✅ Updated `__copy__` and `__deepcopy__` to copy `_has_rd`
11. ✅ Updated `index()` and `_internal()` to use `_has_rd` flag
12. ✅ Fixed `_normalize_nlri_type()` to use `_has_rd` (not `_rd_packed`)
13. ✅ Updated unit tests to use `_has_rd` instead of `_rd_packed`

**Test Results:**
- ✅ All 11 test suites pass
- ✅ All 35 test_label.py tests pass
- ✅ All 12 test_normalize_nlri_type.py tests pass
- ✅ All 18 decoding functional tests pass
- ✅ All 36 encoding functional tests pass

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
IPVPN: [addpath:4?][mask:1][labels:3n][rd:8?][prefix:var]
```

Final storage (all phases complete):
- INET: `_packed` = complete wire format ✅ `_has_addpath` flag
- Label: `_packed` = complete wire format including labels ✅ `_has_labels` flag
- IPVPN: `_packed` = complete wire format including labels and RD ✅ `_has_rd` flag

---

## Zero-Copy Benefits

All three classes now support zero-copy `pack_nlri()`:
- INET: Returns `_packed` directly (or strips/prepends AddPath)
- Label: Returns `_packed` directly (or strips/prepends AddPath)
- IPVPN: Returns `_packed` directly (or strips/prepends AddPath)

No more mask recalculation or RD insertion at pack time.

---

## Resume Point

**Session:** 2025-12-08
**Last Action:** Phase 3 complete - IPVPN RD integrated into `_packed`
**Next Action:** None - all phases complete

**Failures:** None - all tests pass

**Blockers:** None

---

## Verification Commands

```bash
# All tests pass
./qa/bin/test_everything

# Unit tests
env exabgp_log_enable=false uv run pytest ./tests/unit/ -x -q

# Functional tests
./qa/bin/functional encoding  # All 36 pass
./qa/bin/functional decoding  # All 18 pass

# New unit tests for NLRI normalization
uv run pytest tests/unit/configuration/test_normalize_nlri_type.py -v
```
