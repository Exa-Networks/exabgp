# Code Quality Improvements

**Status:** 📋 Planning (low priority)
**Priority:** Low
**See also:** `type-safety/`, `comment-cleanup/`

## Goal

Address miscellaneous code quality issues that don't warrant their own project. These are small, self-contained improvements.

---

## Items

### 1. UPDATE Message Size Calculation

**File:** `src/exabgp/bgp/message/update/__init__.py:109-111`
**Issue:** Size calculated at end; could calculate progressively
**Complexity:** Low
**Benefit:** Cleaner code, potential for early-exit optimization

```python
# Current: calculate total at end
size = len(withdrawn) + len(attributes) + len(nlri)

# Progressive: track as we build
size = 0
size += len(withdrawn)
size += len(attributes)
# ...could exit early if exceeds MTU
```

### 2. NEXTHOP Validation in UPDATE

**File:** `src/exabgp/bgp/message/update/__init__.py:288`
**Issue:** XXX comment about NEXTHOP validation
**Complexity:** Medium
**Benefit:** Catch invalid routes earlier

Need to investigate what validation is missing and whether it should be:
- In UPDATE construction
- In configuration parsing
- In RIB insertion

### 3. Attribute Validation TODOs

**Files:** `src/exabgp/bgp/message/update/attribute/*.py` (6 locations)
**Issue:** Various XXX/TODO comments about validation
**Complexity:** Low-Medium per item
**Benefit:** Robustness

Audit needed to enumerate specific items.

### 4. IP/CIDR Validators

**File:** `src/exabgp/data/check.py`
**Issue:** ipv4/ipv6 validators could be improved
**Complexity:** Low
**Benefit:** Better error messages, edge case handling

Current validators are functional but could:
- Provide more specific error messages
- Handle edge cases better
- Be more consistent in style

### 5. IP/Range/CIDR API

**File:** `src/exabgp/protocol/ip/__init__.py`
**Issue:** API could be cleaner
**Complexity:** Medium (API change)
**Benefit:** Better developer experience

This is a larger refactor that should be done carefully due to many call sites.

### 6. FamilyTuple Type Alias

**File:** `src/exabgp/protocol/family.py` + 18 files
**Issue:** Inconsistent `tuple[AFI, SAFI]` usage
**Complexity:** Low (mechanical)
**Benefit:** Consistency, documentation

**See:** `plan/family-tuple.md` for detailed plan

### 7. Command Keyword Validation Audit

**Files:** Various configuration parsers
**Issue:** Audit all command parsers for validation gaps
**Complexity:** Low
**Benefit:** Better error messages for invalid input

Note: `interface-set` parser already validates direction correctly for both formats.
Other parsers should be audited for similar validation patterns.

### 8. Consolidate Numeric Validation (DONE)

**Status:** ✅ Completed 2025-12-10

Added validation methods:
- `ASN.validate(value) -> bool` - 16-bit range (0 to 65535)
- `ASN4.validate(value) -> bool` - 32-bit range (0 to 4294967295)
- `InterfaceSet.validate_group_id(value) -> bool` - 14-bit range (0 to 16383)

Updated `interface-set` parser to use these validators instead of inline `pow(2, N)` checks.

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

**Last Updated:** 2025-12-04
