# MyPy Error Reduction Plan

**Status:** ✅ Completed
**Created:** 2025-12-17
**Last Updated:** 2025-12-18
**Starting Errors:** 1,149 (baseline)
**Current Errors:** 0 (100% reduction achieved)
**Target:** <25 errors ✅ ACHIEVED → 0 errors ✅ COMPLETE

---

## Executive Summary

After deep analysis (see `plan/mypy-decorator-classvar-pattern.md` for full details), the remaining 50 errors fall into 12 distinct categories with clear fix patterns.

**Key insight from user:** "Many type issues can be fixed by using the base class as return type" - covariant return types and unified base class method signatures are the primary fix patterns.

---

## Current Error Distribution (50 errors)

| Category | Count | Difficulty | Fix Pattern |
|----------|-------|------------|-------------|
| Method signature overrides | 6 | Medium | Add params with defaults / use base return type |
| Read-only property overrides | 4 | Easy | Remove Family setters |
| Flow NLRI (IComponent/BaseValue) | 6 | Medium | Add @classmethod, implement abstract |
| TypeVar bound constraints | 3 | Medium | Expand TypeVar bounds |
| Static route type narrowing | 6 | Medium | Use `type[INET]` union annotation |
| Config misc (arithmetic, dicts) | 11 | Easy | Type guards, casts |
| Srv6 TLV type hierarchy | 3 | Medium | Fix class hierarchy |
| EOR type marker | 1 | Easy | Use TypeAlias |
| Collection attribute access | 2 | Easy | Cast after code check |
| NLRICollection type decl | 1 | Easy | Move to class level |
| Extended communities list | 1 | Easy | Use base class type |
| Announce NextHop | 1 | Easy | Use .ip accessor |
| **Total** | **50** | | |

---

## Implementation Priority (Ordered by Impact)

### Phase 1: Quick Wins (~15 min, -12 errors)

| Fix | File(s) | Errors |
|-----|---------|--------|
| Add `@classmethod` to `IComponent.make()` | flow.py:111 | -4 |
| Remove Family afi/safi setters | family.py | -4 |
| Fix EOR.EOR type usage | eor.py:77 | -1 |
| Fix NLRICollection type decl | collection.py:79 | -1 |
| Fix communities list type | communities.py:218 | -1 |
| Fix NextHop vs IP | announce.py:176 | -1 |

### Phase 2: Signature Alignment (~30 min, -6 errors)

| Fix | File(s) | Errors |
|-----|---------|--------|
| Align `unpack_nlri` return to `tuple[NLRI, Buffer]` | ipvpn.py, inet.py | -1 |
| Add `announced` param to base NLRI.json() | nlri.py | -1 |
| Add `negotiated` to UnknownMessage.unpack_message | unknown.py | -1 |
| Rename GenericAttribute.unpack_attribute | generic.py | -1 |
| Fix ClusterID.from_string signature | clusterlist.py | -1 |
| Fix linkstate.py tlvs property | linkstate.py | -1 |

### Phase 3: Type Guards (~45 min, -11 errors)

| Fix | File(s) | Errors |
|-----|---------|--------|
| Add type guards for attribute arithmetic | announce/__init__.py | -4 |
| Explicit `type[INET]` annotation for nlri_class | static/route.py | -6 |
| Fix dict_keys iteration | api.py, configuration.py | -1 |

### Phase 4: Hierarchy Fixes (~45 min, -9 errors)

| Fix | File(s) | Errors |
|-----|---------|--------|
| BaseValue: add default short() implementation | flow.py | -2 |
| Expand TypeVar bounds | aspath.py, srv6/*.py | -3 |
| Srv6 TLV hierarchy (inheritance or union) | mpls.py | -3 |
| Config misc (neighbor, l2vpn, etc.) | various | -1 |

### Phase 5: Remaining Config (~30 min, -6 errors)

Remaining configuration file fixes.

---

## Detailed Fix Strategies

### IComponent.make() - Missing @classmethod

**Current (line 111-113 in flow.py):**
```python
def make(cls, bgp: Buffer) -> tuple[IComponent, Buffer]:
    raise NotImplementedError(...)
```

**Fix:**
```python
@classmethod
def make(cls, bgp: Buffer) -> tuple[IComponent, Buffer]:
    raise NotImplementedError(...)
```

### Static Route Type Narrowing

**Current (route.py ~348-355):**
```python
if has_rd:
    nlri_class = IPVPN  # mypy infers type[IPVPN]
elif has_labels:
    nlri_class = Label  # Error: incompatible with type[IPVPN]
else:
    nlri_class = INET   # Error: incompatible with type[IPVPN]
```

**Fix:**
```python
nlri_class: type[INET]  # Explicit annotation - INET is base
if has_rd:
    nlri_class = IPVPN
elif has_labels:
    nlri_class = Label
else:
    nlri_class = INET
```

### unpack_nlri Return Type Alignment

**Issue:** INET returns `tuple[INET, Buffer]`, IPVPN returns `tuple[NLRI, Buffer]`
**Fix:** All implementations should return `tuple[NLRI, Buffer]` (base class type)

This follows the user's insight: use base class return types for covariance.

### Announce Attribute Arithmetic

**Current:**
```python
cut = last.attributes[Attribute.CODE.INTERNAL_SPLIT]
if mask >= cut:  # Error: cut is Attribute | None, not int
```

**Fix:**
```python
cut_attr = last.attributes.get(Attribute.CODE.INTERNAL_SPLIT)
if cut_attr is None or not isinstance(cut_attr, InternalSplit):
    yield last
    return
cut = cut_attr.value  # Now properly typed as int
```

---

## Decisions Needed

| Decision | Options | Impact | Recommendation |
|----------|---------|--------|----------------|
| Family afi/safi | Keep settable vs make read-only | 4 errors | Make read-only (packed-bytes-first pattern) |
| GenericAttribute.unpack_attribute | Rename vs type:ignore | 1 error | Rename to unpack_generic |
| Srv6 TLV hierarchy | Inheritance vs union type | 3 errors | Fix inheritance |

---

## Testing Requirements

After each phase:
```bash
uv run mypy src/exabgp 2>&1 | tail -3  # Verify error reduction
uv run ruff format src && uv run ruff check src
env exabgp_log_enable=false uv run pytest ./tests/unit/ -x -q
```

Before declaring complete:
```bash
./qa/bin/test_everything
```

---

## Success Criteria

- [x] Error count < 100 ✅ (97→74→50 achieved)
- [x] Error count < 80 ✅ (74 achieved)
- [x] Error count < 60 ✅ (50 achieved)
- [x] Error count < 50 ✅ (44 achieved)
- [x] Error count < 25 ✅ (24 achieved - TARGET MET!)
- [x] All tests pass ✅ (3404 unit + 54 functional)
- [x] No new `# type: ignore` added ✅ (except 1 unavoidable Container/RouteBuilder mismatch)
- [x] No mypy config changes ✅

---

## Progress Log

### 2025-12-17 - Initial Analysis
- Baseline: 1,149 errors
- After Phase 1-2d: 120 errors (90% reduction)

### 2025-12-17 - First Deep Analysis
- Current: 97 errors (92% reduction from baseline)
- Categorized into 10 major categories

### 2025-12-18 - Phase 1 Implementation
- Commits: Family properties, Negotiated.UNSET, Route/Section fixes
- Current: 74 errors (94% reduction)

### 2025-12-18 - Current Session
- Starting error count: **50 errors** (96% reduction)
- Created deep analysis document: `mypy-decorator-classvar-pattern.md`
- Identified 12 distinct error categories with clear fix patterns
- **Key insight:** Base class return types for covariant methods

**Phase 1 Implementation:**
- Added `@classmethod` to `IComponent.make()` in flow.py
- Renamed `EOR` ClassVar to `IS_EOR` to avoid name shadowing with class
- Fixed NLRICollection type declaration (removed redundant annotation)
- Fixed communities list type (use base class `ExtendedCommunityBase`)
- Fixed NextHop vs IP in announce.py (use `IP.from_string`)
- Updated all tests to use `IS_EOR`

**Result:** 50 → 44 errors (-6)

**Remaining error categories (44 total):**
- Method signature overrides: 6
- Read-only property overrides: 5 (CODE/ARCHTYPE in Generic* classes)
- Flow NLRI (BaseValue abstract): 4
- TypeVar constraints: 3
- Static route types: 6
- Config misc (arithmetic, dicts): 10
- Srv6 TLV types: 3

### 2025-12-18 - Phase 5 Implementation (Config Misc)
- Starting errors: **33**
- **Target achieved: 24 errors (98% reduction from baseline)**

**Fixes applied:**
1. `process/__init__.py:97` - Added isinstance check for str keys in set_value
2. `neighbor/api.py:112` - Removed explicit dict type annotation (inherit from base)
3. `neighbor/api.py:124` - Fixed dict_keys join with isinstance filter
4. `announce/__init__.py:66` - Added assertion for afi.mask() not None
5. `static/__init__.py:37` - Removed explicit action dict type annotation
6. `static/__init__.py:153` - Replaced lambda with inline IPRange parsing
7. `neighbor/__init__.py:314` - Added explicit dict type annotation for return
8. `l2vpn/__init__.py:33` - Added type: ignore for Container/RouteBuilder mismatch
9. `flow/route.py:103` - Made flow() tokeniser param optional

**Result:** 33 → 24 errors (-9)

**Remaining error categories (24 total):**
- Srv6 HasTLV.unpack_attribute: 3
- Collection attribute access: 2
- INET.json signature: 1
- IComponent attr access: 10
- Property overrides (safi/rd): 4
- Srv6 TLV hierarchy: 3
- Misc: 1

---

## Files Reference

**Primary targets (highest error density):**
- `src/exabgp/bgp/message/update/nlri/flow.py` - 10 errors (IComponent attribute access)
- `src/exabgp/bgp/message/update/attribute/sr/srv6/*.py` - 6 errors (HasTLV + hierarchy)
- `src/exabgp/bgp/message/update/nlri/*/nlri.py` - 4 errors (property overrides)

**Supporting documents:**
- `plan/mypy-decorator-classvar-pattern.md` - Full strategic analysis

---

## Deep Analysis: 24 Remaining Errors (Phase 6)

### Category 1: IComponent Attribute Access (10 errors) - HIGHEST PRIORITY

**Files:** `flow.py:915, 949, 987, 989, 1026, 1028, 1032, 1073, 1076, 1136`

**Root Cause:** The `rules` dict is typed as `dict[int, list[IComponent]]` but actual values
are subclasses with additional attributes: `afi`, `operations`, `short()`, `NAME`.

**Error breakdown:**
- Line 915: "Redundant cast" + "Too many arguments for IComponent"
- Lines 949, 1136: `IComponent` has no attribute `afi`
- Lines 987, 989, 1026, 1073: `IComponent` has no attribute `operations`
- Line 1028: `IComponent` has no attribute `short`
- Lines 1032, 1076: `IComponent` has no attribute `NAME`

**Subclass analysis:**
- `IPrefix4/6`: Has `afi` (ClassVar), `operations` (int=0), `NAME`, `short()`
- `IOperation` subclasses: Has `operations`, `short()`, `NAME` but NOT `afi` as ClassVar

**Fix Strategy:**
1. Add abstract/default attributes to `IComponent`:
   ```python
   class IComponent:
       ID: ClassVar[int]
       NAME: ClassVar[str] = ''  # Add default
       operations: int = 0  # Add default for prefix types

       def short(self) -> str:  # Add abstract/default
           raise NotImplementedError()
   ```
2. For `afi` access (lines 949, 1136): Add isinstance check for IPrefix types OR define
   `afi` as Optional ClassVar in IComponent

---

### Category 2: Property Overrides (4 errors)

**Files:** `mvpn/nlri.py:173`, `mup/nlri.py:178, 183`, `evpn/nlri.py:187`

**Root Cause:** Generic* classes have `@property CODE` that extracts from `_packed`,
but base classes define `CODE: ClassVar[int] = -1`.

**Example:**
```python
class MVPN(NLRI):
    CODE: ClassVar[int] = -1  # Writeable class variable

class GenericMVPN(MVPN):
    @property
    def CODE(self) -> int:  # Read-only property - conflicts!
        return self._packed[0]
```

**Fix Options:**
A. Rename property to avoid conflict: `raw_code` or `code_from_wire`
B. Use `# type: ignore[override]` with documentation (deliberate pattern)
C. Make base CODE a property too (but then decorators can't set it)

**Recommendation:** Option A (rename) is cleanest - these are different concepts:
- Base `CODE`: Static class identifier set by decorator
- GenericX `code_from_wire`: Dynamic extraction from packed bytes

---

### Category 3: Srv6 HasTLV.unpack_attribute (3 errors)

**Files:** `l3service.py:86`, `l2service.py:81`, `sidinformation.py:99`

**Error:** `"type[HasTLV]" has no attribute "unpack_attribute"`

**Root Cause:** `HasTLV` Protocol only defines `TLV: ClassVar[int]`, but code calls
`.unpack_attribute()` on registered classes.

**Fix:** Extend Protocol:
```python
class HasTLV(Protocol):
    TLV: ClassVar[int]

    @classmethod
    def unpack_attribute(cls, data: Buffer, length: int) -> Self: ...
```

---

### Category 4: Srv6 TLV Hierarchy (3 errors)

**File:** `mpls.py:181, 189, 191`

**Errors:**
- Line 181: `list[Srv6SidStructure]` vs `list[GenericSrv6ServiceDataSubSubTlv]`
- Lines 189, 191: `list[Srv6SidInformation]` vs `list[GenericSrv6ServiceSubTlv]`

**Root Cause:** Srv6SidInformation/Srv6SidStructure don't inherit from Generic* bases.

**Fix Options:**
A. Fix inheritance: `class Srv6SidStructure(GenericSrv6ServiceDataSubSubTlv)`
B. Use Union types in parameter annotations
C. Use Protocol for structural typing

**Recommendation:** Option A if semantically correct, otherwise B.

---

### Category 5: Collection Attribute Access (2 errors)

**File:** `collection.py:594, 603`

**Errors:**
- Line 594: `nexthop` is `Attribute | IP` but needs `IP`
- Line 603: `unreach` is `Attribute` but needs `Iterable[NLRI]`

**Fix:** Add type narrowing after attribute lookup:
```python
# Line 594
nh_attr = attributes[Attribute.CODE.NEXT_HOP]
if isinstance(nh_attr, IP):
    routed = RoutedNLRI(nlri, nh_attr)

# Line 603 - already has None check, add isinstance
if unreach is not None and isinstance(unreach, MPURNLRI):
    withdraws.extend(unreach)
```

---

### Category 6: INET.json Signature (1 error)

**File:** `inet.py:359`

**Error:** `json(self, announced=True, compact=False)` incompatible with `json(self, compact=False)`

**Fix:** Add `announced` param to base NLRI.json():
```python
class NLRI:
    def json(self, compact: bool = False, announced: bool = True) -> str:
        ...
```

---

## Implementation Plan

| Phase | Category | Errors | Complexity | Time Est |
|-------|----------|--------|------------|----------|
| 6a | IComponent attrs | 10 | Medium | 30 min |
| 6b | Property overrides | 4 | Low | 15 min |
| 6c | HasTLV Protocol | 3 | Low | 10 min |
| 6d | Srv6 hierarchy | 3 | Medium | 20 min |
| 6e | Collection access | 2 | Low | 10 min |
| 6f | INET.json | 1 | Low | 5 min |
| 6g | Flow cast cleanup | 1 | Low | 5 min |
| **Total** | | **24** | | ~1.5h |

---

**Last Updated:** 2025-12-18
