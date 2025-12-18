# MyPy Error Reduction Plan

**Status:** 🔄 Active
**Created:** 2025-12-17
**Last Updated:** 2025-12-18
**Starting Errors:** 1,149 (baseline)
**Current Errors:** 74 (94% reduction achieved)
**Target:** <50 errors

---

## Executive Summary

Current position: **97 errors remaining** across 43 files after 92% reduction from baseline.

| Category | Count | Difficulty | Strategy |
|----------|-------|------------|----------|
| Property overrides (`[misc]`/`[override]`) | 10 | Easy | Remove setters from INET base class |
| Negotiated = None (`[arg-type]`) | 9 | Medium | Sentinel pattern or Optional |
| Attribute access (`[attr-defined]`) | 12 | Medium | Protocol types or cast |
| Static route types (`[arg-type]`/`[assignment]`) | 10 | Medium | Fix type narrowing |
| Flow NLRI registry (`[call-arg]`/`[arg-type]`) | 8 | Hard | Fix IComponent class methods |
| Flow parser yields (`[misc]`) | 6 | Easy | Fix return type annotations |
| Section dict types (`[assignment]`) | 7 | Easy | Unify dict key types |
| Update vs UpdateCollection | 5 | Medium | Type alias or union |
| Method signature overrides (`[override]`) | 4 | Hard | Signature alignment |
| Other misc issues | 26 | Varies | Case-by-case |

---

## Phase 1: Quick Wins (~33 errors)

### 1.1 Property Override Fixes (10 errors) ✅ READY

**Root cause:** INET defines `labels` and `rd` as read-write properties (with setters), but Label/IPVPN override them as read-only properties.

**Files:**
| File | Lines | Properties |
|------|-------|------------|
| `nlri/rtc.py` | 52, 56 | safi, labels |
| `nlri/label.py` | 125, 177 | safi, labels |
| `nlri/ipvpn.py` | 152, 186 | safi, rd |
| `nlri/mvpn/nlri.py` | 179 | safi |
| `nlri/mup/nlri.py` | 184, 189 | safi, rd |
| `nlri/evpn/nlri.py` | 187 | safi |
| `attribute/bgpls/linkstate.py` | 274 | tlvs |

**Fix:** Remove setters from `inet.py` lines 121-123 and 129-131. The packed-bytes-first pattern makes properties read-only by design.

```python
# REMOVE these setter methods from inet.py:
@labels.setter
def labels(self, value: Labels | None) -> None:
    self._labels = value

@rd.setter
def rd(self, value: RouteDistinguisher | None) -> None:
    self._rd = value
```

### 1.2 Flow Parser Yield Types (6 errors) ✅ READY

**Root cause:** Functions return `Generator[Flow4Source | Flow6Source]` but yield `IPrefix4`/`IPrefix6`.

**File:** `configuration/flow/parser.py` lines 135, 139, 144, 156, 160, 165

**Fix:** The `make_prefix4`/`make_prefix6` methods return the correct Flow types. Update the type hints to match actual return types, or verify the methods return Flow4Source/Flow6Source (they should).

### 1.3 Section Dict Types (7 errors) ✅ READY

**Root cause:** Subclasses define `content: dict[str, object]` but base Section uses `dict[str | tuple[Any, ...], Any]`.

**Files:**
- `configuration/operational/__init__.py:106`
- `configuration/neighbor/nexthop.py:72`
- `configuration/neighbor/api.py:109,110,124`
- `configuration/static/__init__.py` (2 errors)
- `configuration/configuration.py` (dict_keys)

**Fix:** Change subclass type annotations to match base class:
```python
content: dict[str | tuple[Any, ...], Any] = {}
```

### 1.4 Route __index Slot (2 errors) ✅ READY

**Root cause:** `__index` not in `__slots__` but `_Route__index` is (Python name mangling).

**File:** `rib/route.py:56,109`

**Fix:** The slot is correctly declared as `_Route__index` (line 36). The assignment `self.__index = b''` uses Python's name mangling and should work. Need to verify mypy understands this - may need explicit cast or rename.

### 1.5 INET Attribute Redefinition (2 errors) ✅ READY

**Root cause:** `_labels` and `_rd` defined in `__slots__` AND as instance attributes.

**File:** `inet.py:151,152`

**Fix:** Remove the redundant instance attribute assignments since they're already in `__slots__`:
```python
# Lines 151-152 can be removed if __slots__ handles it
# Or keep only the type annotation without assignment
```

### 1.6 EOR Valid Type (1 error) ✅ READY

**Root cause:** `EOR.EOR` used as a type but it's a ClassVar bool.

**File:** `eor.py:79`

**Fix:** The `EOR.EOR` is used as a marker. Check context - likely needs different approach.

### 1.7 NLRI Collection Type Declaration (1 error) ✅ READY

**Root cause:** Type declared in assignment to non-self attribute.

**File:** `nlri/collection.py:79`

**Fix:** Move type annotation to class level or use different pattern.

### 1.8 Extended Community List Type (1 error) ✅ READY

**File:** `community/extended/communities.py:217`

**Fix:** Cast or fix the list type annotation.

### 1.9 L2VPN Container Type (1 error) ✅ READY

**File:** `configuration/l2vpn/__init__.py`

**Fix:** Align Container/RouteBuilder types.

### 1.10 Flow Route Tokeniser (1 error) ✅ READY

**File:** `configuration/flow/route.py`

**Fix:** Handle None case for Tokeniser argument.

---

## Phase 2: Medium Complexity (~35 errors)

### 2.1 Negotiated = None Pattern (9 errors)

**Root cause:** Community pack methods call `pack_attribute(None)` where `Negotiated` expected.

**Files:**
- `community/large/communities.py:87,100`
- `community/initial/communities.py:78,90`
- `community/extended/rt_record.py:26`
- `community/extended/communities.py:118,129,199,207`

**Options:**
1. **Sentinel pattern** - Create `NullNegotiated` singleton
2. **Optional parameter** - Make `negotiated: Negotiated | None`
3. **Skip pack_attribute** - Use direct packing for these cases

**Recommended:** Option 2 - Make parameter optional with None default, add runtime guard.

### 2.2 Attribute Access on Base Types (12 errors)

**Root cause:** Code accesses subclass-specific attributes on base `Attribute` type.

| File | Attribute | Solution |
|------|-----------|----------|
| `collection.py:216` | `pack_ip` | Cast to NextHop |
| `collection.py:594` | (Attribute\|IP) → IP | Type guard |
| `collection.py:603` | `extend` with Attribute | Cast to MPRNLRI |
| `collection.py:607` | `iter_routed` | Cast to MPRNLRI |
| `mprnlri.py:140` | `pack_ip` | Cast to NextHop |
| `update/__init__.py:198,200` | `afi`, `safi` | Cast to MPRNLRI |
| `update/__init__.py:210` | UpdateCollection\|None | Type guard |
| `neighbor.py:366,367` | `SELF`, `resolved`, `resolve` | Cast to NextHop |
| `validator.py:1380` | `validate_with_afi` | Add method or Protocol |

**Fix:** Use `cast()` with appropriate types based on the attribute code being accessed.

### 2.3 Update vs UpdateCollection (5 errors)

**Root cause:** Functions return `UpdateCollection` but are typed to return `Update`.

**Files:**
- `reactor/protocol.py:445,464` - return type mismatch
- `reactor/api/processes.py:1320,1324` - assignment/arg mismatch
- `bgp/message/update/__init__.py:210` - None handling

**Fix:** Either:
1. Change return types to `UpdateCollection`
2. Create type alias `UpdateResult = Update | UpdateCollection`
3. Verify the semantic intent and fix appropriately

### 2.4 Static Route Type Mismatches (10 errors)

**Files:**
- `configuration/static/route.py:352,355,419,426` - type[INET/Label] → type[IPVPN]
- `configuration/static/route.py:450` - kwargs spread
- `configuration/static/route.py:500` - Attribute → int
- `configuration/static/parser.py:330,332` - IP → ClusterID
- `configuration/static/mpls.py:138` - missing return
- `configuration/static/mpls.py:181,189,191` - Srv6 TLV types

**Fix:** These require careful analysis of the type narrowing logic. The route creation code assigns different NLRI class types based on conditions.

### 2.5 Announce Config Issues (4 errors)

**File:** `configuration/announce/__init__.py:65,67,88`

**Pattern:** Arithmetic on `int | None` and `Attribute` types.

**Fix:** Add type guards before arithmetic operations.

### 2.6 Announce NextHop (1 error)

**File:** `reactor/api/command/announce.py`

**Pattern:** `NextHop` passed where `IP` expected.

**Fix:** NextHop should be compatible with IP or needs accessor.

### 2.7 Neighbor Return Type (1 error)

**File:** `configuration/neighbor/__init__.py`

**Pattern:** Returning Any from typed function.

**Fix:** Add proper return type annotation.

---

## Phase 3: Complex Fixes (~25 errors)

### 3.1 Flow NLRI Registry Issues (8 errors)

**Root cause:** `IComponent` base class doesn't properly type the registry pattern.

**File:** `nlri/flow.py` lines 902, 903, 912, 913, 508, 516

**Issues:**
1. `klass.make(bgp)` - `make` is not a classmethod but used as one
2. `klass(operator, adding_val)` - IComponent constructor doesn't match
3. `BaseValue` instantiation - abstract class

**Fix:**
1. Make `make` a proper `@classmethod` with correct signature
2. Add ClassVar declarations for factory methods
3. Fix BaseValue to not be abstract or use concrete subclass

### 3.2 Method Signature Overrides (4 errors)

| File | Method | Issue |
|------|--------|-------|
| `attribute/generic.py:127` | `unpack_attribute` | Extra params (code, flag) |
| `nlri/ipvpn.py:443` | `unpack_nlri` | Returns NLRI vs INET |
| `nlri/inet.py:373` | `json` | Extra param (announced) |
| `message/unknown.py:48` | `unpack_message` | Missing negotiated param |

**Fix options:**
1. Use `@overload` decorators
2. Align signatures with base class
3. Use `# type: ignore[override]` with documentation (last resort)

### 3.3 TypeVar Constraints (3 errors)

**Files:**
- `attribute/aspath.py:255` - SegmentType
- `attribute/sr/srv6/sidinformation.py:45` - SubTlvType
- `attribute/sr/srv6/sidstructure.py:36` - SubSubTlvType

**Fix:** Expand TypeVar bounds to include the actual types being used.

---

## Implementation Order

| Priority | Phase | Errors | Effort | Notes |
|----------|-------|--------|--------|-------|
| 1 | 1.1 Property overrides | 10 | 15 min | Just remove setters |
| 2 | 1.2 Flow parser yields | 6 | 15 min | Type annotation fix |
| 3 | 1.3-1.10 Quick misc | 9 | 30 min | Various small fixes |
| 4 | 2.1 Negotiated None | 9 | 30 min | Parameter change |
| 5 | 2.2 Attribute access | 12 | 45 min | Add casts |
| 6 | 2.3 Update types | 5 | 30 min | Return type fixes |
| 7 | 2.4-2.7 Static route | 16 | 1 hr | Type narrowing |
| 8 | 3.1 Flow registry | 8 | 1 hr | Class restructure |
| 9 | 3.2 Method sigs | 4 | 45 min | Signature alignment |
| 10 | 3.3 TypeVars | 3 | 15 min | Bound expansion |

**Estimated total:** ~6 hours to reach <50 errors

---

## Quick Start: First 25 Errors

Run these in order for maximum impact:

```bash
# 1. Remove INET property setters (10 errors)
# Edit src/exabgp/bgp/message/update/nlri/inet.py
# Remove lines 121-123 (@labels.setter) and 129-131 (@rd.setter)

# 2. Fix flow parser return types (6 errors)
# Edit src/exabgp/configuration/flow/parser.py
# Verify make_prefix4/make_prefix6 return correct types

# 3. Fix Section dict types (7 errors)
# Update subclass type annotations to match base

# 4. Fix Route __index and INET redefinitions (4 errors)
# Minor slot/attribute fixes

# Verify:
uv run mypy src/exabgp 2>&1 | tail -3
```

---

## Decisions Needed

| Decision | Options | Impact |
|----------|---------|--------|
| Negotiated None | Sentinel vs Optional param | 9 errors |
| Update vs UpdateCollection | Union type vs separate | 5 errors |
| Method signature overrides | Align vs type:ignore | 4 errors |
| Flow IComponent | Restructure vs Protocol | 8 errors |

---

## Testing Requirements

After each phase:
```bash
uv run mypy src/exabgp  # Verify error reduction
uv run ruff format src && uv run ruff check src
env exabgp_log_enable=false uv run pytest ./tests/unit/ -x -q
```

Before declaring complete:
```bash
./qa/bin/test_everything
```

---

## Success Criteria

- [x] Error count < 100 ✅ (97 achieved)
- [x] Error count < 80 ✅ (74 achieved)
- [ ] Error count < 50
- [ ] All tests pass
- [ ] No new `# type: ignore` added
- [ ] No mypy config changes

---

## Progress Log

### 2025-12-17 - Initial Analysis
- Baseline: 1,149 errors
- After Phase 1-2d: 120 errors (90% reduction)

### 2025-12-17 - Ultrathink Deep Analysis
- Current: **97 errors** (92% reduction from baseline)
- Categorized all 97 errors into 10 major categories
- Identified 33 quick-win errors (Phase 1)
- Property override fix alone removes 10 errors
- Created prioritized implementation plan
- Estimated ~6 hours to reach <50 errors

**Error Distribution by Category:**
- Property overrides: 10
- Negotiated None: 9
- Attribute access: 12
- Static route types: 10
- Flow NLRI: 8
- Flow parser: 6
- Section dict: 7
- Update types: 5
- Method overrides: 4
- TypeVars: 3
- Other: 23

### 2025-12-18 - Phase 1 Implementation

**Commits:**
1. `d0846055e` - Make Family afi/safi properties read-only (97→89, -8 errors)
2. `6ac0e1978` - Use Negotiated.UNSET singleton (89→80, -9 errors)
3. (pending) - Fix Route __index and Section dict types (80→74, -6 errors)

**Current: 74 errors** (94% reduction from baseline)

**Remaining error categories:**
- ClassVar property overrides: 5
- Flow NLRI registry: 6
- Attribute access (cast needed): 6
- Static route types: 6
- Flow parser yields: 4
- Update vs UpdateCollection: 2
- Method signature overrides: 3
- TypeVars: 3
- Other misc: ~40

---

**Last Updated:** 2025-12-18
