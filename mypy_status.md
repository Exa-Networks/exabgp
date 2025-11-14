# MyPy Status - Updated Analysis

**Generated:** 2025-11-14
**Previous Errors:** 1,362
**Current Errors:** 558
**Errors Fixed:** 804 (59% reduction)

## Completed Work (Phases 1-11)

✅ **Phase 1:** var-annotated, unused-ignore, name-match, truthy-function (64 errors)
✅ **Phase 2:** AFI/SAFI architectural fix
✅ **Phase 3:** no-any-return fixes
✅ **Phase 4:** Logger type errors
✅ **Phase 5-11:** Additional fixes across arg-type, union-attr, operator, etc.

## Remaining Error Distribution

| Error Type | Count | % of Total | Fixable | Priority |
|-----------|-------|------------|---------|----------|
| [override] | 158 | 28% | Yes | **HIGH** |
| [attr-defined] | 152 | 27% | Partial | Medium |
| [misc] | 140 | 25% | Partial | Medium |
| [assignment] | 107 | 19% | Yes | **HIGH** |
| [int] | 35 | 6% | Partial | Low |
| [str] | 33 | 6% | Partial | Low |
| [bytes] | 31 | 6% | Partial | Low |
| [unused-ignore] | 1 | 0% | Yes | Low |
| [bool] | 1 | 0% | Yes | Low |

**Total:** 558 errors (note: some lines have multiple errors)

## Top Problem Files

| Errors | File | Primary Issue |
|--------|------|---------------|
| 126 | bgp/message/update/attribute/community/extended/traffic.py | [override] unpack() signatures |
| 66 | bgp/message/update/nlri/flow.py | [misc] type inference |
| 42 | bgp/message/update/attribute/pmsi.py | [override] signatures |
| 42 | bgp/message/update/attribute/community/extended/rt.py | [override] signatures |
| 42 | bgp/message/update/attribute/community/extended/origin.py | [override] signatures |
| 34 | bgp/message/update/attribute/nexthop.py | [override] + [misc] |
| 23 | configuration/check.py | [attr-defined] |
| 23 | bgp/message/update/attribute/originatorid.py | [override] signatures |
| 22 | bgp/message/operational.py | [misc] type annotations |
| 20 | bgp/message/update/nlri/mup/nlri.py | [override] signatures |

## Analysis by Error Type

### 1. [override] Errors (158 errors) - **HIGHEST PRIORITY**

**Pattern:** Subclass method signatures incompatible with base class

**Most Common Issue:** `unpack()` method signature mismatches in extended communities

```python
# Base class (ExtendedCommunityBase):
@classmethod
def unpack(cls, data: bytes, direction: Optional[int] = ..., negotiated: Negotiated = ...) -> ExtendedCommunityBase

# Subclass (TrafficRate):
@staticmethod
def unpack(data: bytes) -> TrafficRate  # ❌ Wrong: missing parameters, @staticmethod vs @classmethod
```

**Files Affected:**
- community/extended/traffic.py (60 errors across 21 classes × ~3 errors each)
- community/extended/rt.py (42 errors)
- community/extended/origin.py (42 errors)
- Other extended community types (~14 errors)

**Fix Strategy:**
1. Make subclass `unpack()` methods match base signature:
   ```python
   @classmethod
   def unpack(cls, data: bytes, direction: Optional[int] = None, negotiated: Optional[Negotiated] = None) -> TrafficRate:
       # Implementation can ignore unused parameters
       return cls(...)
   ```
2. Alternative: Refactor base class to use method overloading if parameters truly vary

**Estimated Effort:** 4-6 hours
**Estimated Reduction:** ~158 errors

### 2. [attr-defined] Errors (152 errors) - **MEDIUM PRIORITY**

**Pattern:** Accessing attributes that don't exist or aren't typed

**Common Issues:**
- Platform-specific attributes (AF_NETLINK on macOS)
- Module import issues
- Missing type stubs

**Examples:**
```python
# configuration/check.py - Missing module attributes
Module "exabgp.conf" has no attribute "Config"

# Platform-specific
Module "socket" has no attribute "AF_NETLINK"  # Only on Linux
```

**Fix Strategy:**
1. Add `# type: ignore[attr-defined]` for platform-specific code
2. Fix genuine import errors
3. Create stub files for missing module attributes
4. Add proper type annotations to dynamic attributes

**Estimated Effort:** 3-5 hours
**Estimated Reduction:** ~50 errors (many are platform-specific, need ignores)

### 3. [misc] Errors (140 errors) - **MEDIUM PRIORITY**

**Pattern:** Miscellaneous type issues including:
- Cannot infer type of lambda
- Complex union types
- Type narrowing issues

**Examples:**
```python
# flow.py - Complex union types causing inference issues
value: Union[int, str, bytes, tuple]
# Downstream operations can't narrow the type properly

# reactor/loop.py - Lambda type inference
log.debug(lambda: 'message')  # Cannot infer lambda type
```

**Fix Strategy:**
1. Add explicit type annotations to lambdas: `lambda: str = lambda: 'message'`
2. Add type guards for complex unions: `isinstance()` checks
3. Use `cast()` where type system can't infer correctly
4. Some may need `# type: ignore[misc]` if unavoidable

**Estimated Effort:** 6-8 hours
**Estimated Reduction:** ~70 errors (many are fundamental design issues)

### 4. [assignment] Errors (107 errors) - **HIGH PRIORITY**

**Pattern:** Assigning incompatible types to variables

**Common Issues:**
- Assigning `None` to non-Optional variables
- Type mismatches in attribute assignments
- Return value type mismatches

**Fix Strategy:**
1. Change type annotations to Optional where None is assigned
2. Fix type mismatches by converting values
3. Add proper type guards

**Estimated Effort:** 3-4 hours
**Estimated Reduction:** ~107 errors

### 5. Type Literal Errors ([int], [str], [bytes]) (99 errors) - **LOW PRIORITY**

**Pattern:** Operations expecting compatible types but receiving literals

**Examples:**
```python
value: int = "string"  # [str]
data: bytes = 123  # [int]
```

**Fix Strategy:**
1. Review each case to determine if annotation or assignment is wrong
2. Add proper type conversions where needed

**Estimated Effort:** 2-3 hours
**Estimated Reduction:** ~99 errors

## Recommended Next Steps

### Phase 12: Fix [override] Errors in Extended Communities (HIGH PRIORITY)
**Target:** Fix unpack() signature mismatches in extended community classes

**Approach:**
1. Start with `community/extended/traffic.py` (126 errors)
2. Fix base signature to match subclass needs OR
3. Fix all subclass signatures to match base class
4. Apply pattern to rt.py, origin.py, and others

**Files to fix:**
- traffic.py (21 classes)
- rt.py (7 classes)
- origin.py (7 classes)
- Other extended community files (5 classes)

**Expected reduction:** ~158 errors
**Estimated time:** 4-6 hours
**Impact:** 28% of remaining errors

### Phase 13: Fix [assignment] Errors (HIGH PRIORITY)
**Target:** Fix type mismatches in variable assignments

**Expected reduction:** ~107 errors
**Estimated time:** 3-4 hours
**Impact:** 19% of remaining errors

### Phase 14: Fix [attr-defined] Errors (MEDIUM PRIORITY)
**Target:** Fix or suppress attribute definition errors

**Expected reduction:** ~50-70 errors
**Estimated time:** 3-5 hours
**Impact:** 9-13% of remaining errors

### Phase 15: Fix [misc] Errors (MEDIUM PRIORITY)
**Target:** Add type annotations and guards for complex types

**Expected reduction:** ~70 errors
**Estimated time:** 6-8 hours
**Impact:** 13% of remaining errors

## Success Projection

**Current:** 558 errors
**After Phase 12 (override):** ~400 errors (-158)
**After Phase 13 (assignment):** ~293 errors (-107)
**After Phase 14 (attr-defined):** ~223 errors (-70)
**After Phase 15 (misc):** ~153 errors (-70)

**Total projected reduction:** ~405 errors (73% of remaining)
**Final projected error count:** ~153 errors (89% reduction from original 1,362)

## Notes

- All fixes must maintain Python 3.8+ compatibility
- All fixes must pass: ruff, pytest, functional encoding tests
- Some errors are fundamental design issues and may need `# type: ignore`
- Consider creating a mypy baseline for truly unfixable errors
- Platform-specific errors (AF_NETLINK, etc.) should be marked with conditional type: ignore
