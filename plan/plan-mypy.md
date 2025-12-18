# MyPy Error Reduction Plan

**Status:** 🔄 Active
**Created:** 2025-12-17
**Last Updated:** 2025-12-18
**Starting Errors:** 1,149 (baseline)
**Current Errors:** 44 (96% reduction achieved)
**Target:** <25 errors

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
- [ ] Error count < 25 (new target)
- [x] All tests pass ✅ (3404 unit + 169 fuzz)
- [x] No new `# type: ignore` added ✅
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
- Collection attribute access: 2
- Other: 5

**Estimated time to <25 errors:** ~2 hours across remaining phases

---

## Files Reference

**Primary targets (highest error density):**
- `src/exabgp/bgp/message/update/nlri/flow.py` - 6 errors (IComponent, BaseValue)
- `src/exabgp/configuration/static/route.py` - 6 errors (type narrowing)
- `src/exabgp/configuration/announce/__init__.py` - 4 errors (attribute arithmetic)

**Supporting documents:**
- `plan/mypy-decorator-classvar-pattern.md` - Full strategic analysis

---

**Last Updated:** 2025-12-18
