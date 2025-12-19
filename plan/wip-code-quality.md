# Code Quality Improvements

**Status:** 🔄 Active (low priority)
**Priority:** Low
**See also:** `type-safety/`, `comment-cleanup/`

## Goal

Address miscellaneous code quality issues that don't warrant their own project. These are small, self-contained improvements.

---

## Items

### ~~1. UPDATE Message Size Calculation~~ (OBSOLETE)

**Status:** ❌ Obsolete (2025-12-18)
**Reason:** Update class was refactored. The size calculation pattern described no longer exists in the codebase.

### ~~2. NEXTHOP Validation in UPDATE~~ (OBSOLETE)

**Status:** ❌ Obsolete (2025-12-18)
**Reason:** XXX comment at line 288 no longer exists. File is now 221 lines. Wire format validation was moved to `UpdateCollection.messages()` per done-wire-format-validation.md.

### ~~3. Attribute Collection Hash FIXME~~ (DONE)

**Status:** ✅ Completed (2025-12-18)

Changed `__hash__` to use `self.index()` instead of `repr(self)`. `index()` already includes nexthop while `repr()` excludes it (NO_GENERATION=True).

### ~~4. IP/CIDR Validators~~ (DONE)

**Status:** ✅ Completed (2025-12-18)

Added bit-width constants (BITS_8/16/32/96), replaced pow() calls, fixed variable shadowing in `ipv4_range()`.

### ~~5. IP/Range/CIDR API~~ (DONE)

**Status:** ✅ Completed (2025-12-18)

Consolidated duplicate logic in `toaf()`/`toafi()` using `_AF_TO_AFI` mapping. Simplified `klass()` to use `toafi()`.

### ~~6. FamilyTuple Type Alias~~ (DONE)

**Status:** ✅ Completed (2025-12-18)

Added `FamilyTuple = tuple[AFI, SAFI]` type alias in `protocol/family.py`. Updated 22 files with 64 occurrences.

Files updated:
- bgp/neighbor/neighbor.py
- bgp/message/open/capability/negotiated.py
- bgp/message/open/capability/capabilities.py
- bgp/message/open/capability/mp.py
- bgp/message/open/capability/graceful.py
- bgp/message/open/capability/addpath.py
- bgp/message/update/collection.py
- bgp/message/update/nlri/nlri.py
- bgp/message/operational.py
- rib/__init__.py, rib/outgoing.py, rib/incoming.py, rib/cache.py, rib/route.py
- reactor/peer/peer.py, reactor/peer/handlers/route_refresh.py
- reactor/api/command/peer.py
- configuration/neighbor/__init__.py, configuration/neighbor/family.py
- configuration/configuration.py, configuration/setup.py

### 7. Command Keyword Validation Audit

**Files:** Various configuration parsers
**Issue:** Audit all command parsers for validation gaps
**Complexity:** Low
**Benefit:** Better error messages for invalid input

Note: `interface-set` parser already validates direction correctly for both formats.
Other parsers should be audited for similar validation patterns.

### ~~8. Consolidate Numeric Validation~~ (DONE)

**Status:** ✅ Completed 2025-12-10

Added validation methods:
- `ASN.validate(value) -> bool` - 16-bit range (0 to 65535)
- `ASN4.validate(value) -> bool` - 32-bit range (0 to 4294967295)
- `InterfaceSet.validate_group_id(value) -> bool` - 14-bit range (0 to 16383)

Updated `interface-set` parser to use these validators instead of inline `pow(2, N)` checks.

---

## Active Items Summary

| # | Item | Complexity | Status |
|---|------|------------|--------|
| 7 | Command Keyword Validation Audit | Low | 📋 Open |

---

## Implementation Notes

These items are intentionally low priority because:
- Code works correctly as-is
- Changes are cosmetic/cleanup
- Risk of regression outweighs benefit

Work on these when:
- Touching the file for other reasons
- Need a small task to fill time
- Building familiarity with a module

---

## Testing

Each change requires:
```bash
./qa/bin/test_everything
```

Most changes are safe refactors that shouldn't break functionality.

---

**Last Updated:** 2025-12-18
