# Type Ignore Elimination Plan

**Status:** In Progress
**Created:** 2025-11-30
**Starting total:** 201 across 92 files
**Current total:** 194 (-7, -3.5%)

---

## Summary by Error Code (Current)

| Code | Count | % | Description |
|------|-------|---|-------------|
| `arg-type` | 63 | 32% | Type system limitations with unions/conversions |
| `attr-defined` | 28 | 14% | Dynamic attributes not in type stubs |
| `override` | 20 | 10% | Intentional signature changes in subclasses |
| `misc` | 14 | 7% | ClassVar assignments, type aliasing |
| `no-any-return` | 12 | 6% | Functions returning Any |
| `no-code` | 9 | 5% | Generic ignores without specific error |
| `type-var` | 3 | 2% | TypeVar can't handle Union (NEW - better than arg-type) |
| Other | 45 | 23% | Various one-off cases |

---

## Completed Work

### Session 1 (2025-11-30) - 7 ignores removed

#### 1. Fixed Method Name Collision (Commit: ffba5d21)

**Problem:** ASN4 inherits from both Capability and ASN, both defined `extract()`

**Solution:**
- Renamed `ASN.extract()` → `extract_asn_bytes()`
- Renamed `Capability.extract()` → `extract_capability_bytes()`

**Files changed:** 16
- asn.py, capability.py, asn4.py, capabilities.py
- 11 capability subclasses (addpath, extended, graceful, hostname, mp, ms, nexthop, operational, refresh, software, unknown)
- 2 call sites in capabilities.py updated

**Impact:** Eliminated name collision, improved code clarity

**Ignores removed:** 0 (cleanup, not removal)

---

#### 2. Fixed ASPath list→tuple Coercion (Commit: 360cbb29)

**Problem:** ASPath.__init__ expected strict `tuple`, callers passed `list`

**Solution:**
```python
# Before
def __init__(self, as_path: tuple[SET | SEQUENCE | ...] = (), ...) -> None:
    self.aspath = as_path

# After
def __init__(self, as_path: Sequence[SET | SEQUENCE | ...] = (), ...) -> None:
    self.aspath = tuple(as_path)  # Convert to tuple internally
```

**Files changed:** 3
- aspath.py - Changed signature to accept Sequence
- attributes.py - Removed ignore from ASPath([])
- parser.py - Removed 2 ignores from ASPath construction

**Ignores removed:** 5
- `aspath.py:236` - `ASPath.Empty = ASPath([])`
- `aspath.py:261` - `AS4Path.Empty = AS4Path([])`
- `attributes.py:214` - `ASPath([])` in default dict
- `parser.py:232` - `ASPath([SEQUENCE([ASN.from_string(value)])])`
- `parser.py:253` - `ASPath(as_path)` after filtering segments

---

#### 3. Fixed aspath._segment Slicing with TypeVar (Commit: 75923349)

**Problem:** Slicing Union loses type information

```python
# Before - mypy can't track type through slice
def _segment(cls, seg_type: int,
             values: SET | SEQUENCE | CONFED_SEQUENCE | CONFED_SET,
             asn4: bool) -> bytes:
    # Recursive call with slice
    cls._segment(seg_type, values[:MAX_LEN], asn4)  # type: ignore[arg-type]
```

**Solution:** Use TypeVar with runtime type reconstruction

```python
# After
SegmentType = TypeVar('SegmentType', SET, SEQUENCE, CONFED_SEQUENCE, CONFED_SET)

def _segment(cls, seg_type: int, values: SegmentType, asn4: bool) -> bytes:
    # Cast slices back to original type
    first_half = type(values)(values[:MAX_LEN])
    second_half = type(values)(values[MAX_LEN:])
    return cls._segment(seg_type, first_half, asn4) + cls._segment(seg_type, second_half, asn4)
```

**Files changed:** 1 (aspath.py)

**Ignores removed:** 2
- Line 111 - Slicing `values[:MAX_LEN]`
- Line 114 - Slicing `values[MAX_LEN:]`

**Ignores changed (better error codes):** 3
- Line 119: `arg-type` → `type-var` - pack_asn(bool) expects Negotiated
- Line 126: `arg-type` → `type-var` - TypeVar can't handle Union at call site
- Line 132: `arg-type` → `type-var` - TypeVar can't handle Union at call site

**Net:** Removed 2 slicing ignores, improved 3 others with specific error codes

---

## Attempted But Reverted

### Nested dict.setdefault() Chains (rib/outgoing.py)

**Problem:**
```python
# Mypy loses track through chained setdefault
self._watchdog.setdefault(watchdog, {}).setdefault('-', {})[change.index()] = change
# type: ignore[arg-type]
```

**Attempted solution:**
```python
# Add intermediate annotations
watchdog_dict: dict[str, dict[bytes, Change]] = self._watchdog.setdefault(watchdog, {})
withdraw_dict: dict[bytes, Change] = watchdog_dict.setdefault('-', {})
withdraw_dict[change.index()] = change
```

**Why reverted:**
1. **Type annotation mismatches**
   - `_new_attr_af_nlri` annotated as `dict[bytes, ...]`
   - But used with various key types at runtime (str, bytes, Attribute)

2. **Runtime vs static types diverge**
   - `watchdog()` returns `Attribute | None`
   - Dict key type is `str` (relies on `__str__()` conversion)
   - Mypy can't express "dict key is str representation of Attribute"

3. **Cascading type errors**
   - Fixing one level reveals errors in next level
   - Would need comprehensive module-level type annotation fixes
   - Type system can't express dynamic key type behavior

**Conclusion:** Keep existing ignores, document runtime behavior in comments

---

## Root Causes Analysis

### 1. Union + Operations (30+ remaining cases)

**Pattern:** Operations on union types lose type information

**Files affected:**
- `bgp/message/update/attribute/aspath.py` (3 remaining - call sites)
- `bgp/message/update/attribute/community/extended/communities.py` (3)
- `bgp/message/update/nlri/mvpn/*.py` (9 total)
- `bgp/message/update/nlri/evpn/*.py` (6 total)

**Example:**
```python
def pack_segments(cls, aspath: tuple[SET | SEQUENCE | CONFED_SEQUENCE | CONFED_SET, ...],
                  asn4: bool) -> bytes:
    for content in aspath:
        # TypeVar can't handle Union at call site
        segments += cls._segment(content.ID, content, asn4)  # type: ignore[type-var]
```

**Why:**
- Mypy can't prove slice of `Union[A|B|C|D]` returns same type
- All union members have same methods, but mypy can't verify
- Operations don't preserve specific type in union

**What works:** TypeVar within function (slicing)
**What doesn't:** TypeVar at call site with Union parameter

---

### 2. List → Tuple Coercion (10+ remaining cases)

**Pattern:** Passing `list` where `tuple` expected

**Remaining files:**
- `configuration/static/mpls.py` (3 ignores - PrefixSid)
- `configuration/announce/vpls.py` (1 ignore - wrong types, not coercion)
- Other scattered cases

**Example:**
```python
# PrefixSid expects tuple, gets list
return PrefixSid([Srv6L3Service(subtlvs=subtlvs)])  # type: ignore[arg-type]
```

**What worked:** Changing `tuple[T, ...]` → `Sequence[T]` in signatures

**What didn't:** Cases where wrong types passed (VPLS with None for required ints)

---

### 3. Nested dict.setdefault() Chains (8+ cases - NOT FIXED)

**Pattern:** Nested `setdefault()` with complex types

**Files affected:**
- `rib/outgoing.py` (4 ignores)
- `reactor/network/outgoing.py` (4 ignores)

**Why not fixed:** Type annotations don't match runtime behavior (see "Attempted But Reverted" above)

**Recommendation:** Document runtime types in comments, keep ignores

---

### 4. Method Name Collision (FIXED)

**Pattern:** Multiple inheritance with same method name

**Solution:** Renamed both methods for clarity (see Completed Work #1)

---

## Lessons Learned

### What Worked ✅

1. **TypeVar for preserving types through operations**
   ```python
   T = TypeVar('T', A, B, C, D)
   def func(val: T) -> T:
       sliced = type(val)(val[:10])  # Reconstruct type at runtime
   ```
   - Effective for homogeneous operations (slicing, copying)
   - Runtime type reconstruction with `type(val)(...)`

2. **Sequence instead of tuple for parameters**
   ```python
   # Accept flexible input
   def __init__(self, items: Sequence[T]) -> None:
       self.items = tuple(items)  # Store immutably
   ```
   - Accepts both list and tuple
   - Convert internally for immutability
   - Easy win with no runtime cost

3. **Method renaming for clarity**
   - Eliminates name collisions
   - Improves code readability
   - Better documentation than workarounds
   - One-time cost, permanent benefit

4. **Specific error codes over generic**
   - `type-var` better than `arg-type` (documents exact limitation)
   - Future readers understand WHY ignore is needed
   - Easier to revisit when mypy improves

### What Didn't Work ❌

1. **Intermediate annotations for nested setdefault**
   - Only works when type annotations match runtime behavior
   - Dict key type mismatches can't be fixed with annotations alone
   - Requires comprehensive module-level type fixes
   - Runtime behavior uses duck typing that type system can't express

2. **Fixing everything at once**
   - Some patterns need architectural changes
   - Type system has fundamental limitations
   - Better to document than force incorrect fixes
   - Partial fixes create more noise than value

3. **TypeVar at Union call sites**
   ```python
   T = TypeVar('T', A, B, C, D)
   def func(val: T) -> None: pass

   # Doesn't work
   for item in union_list:  # item is A | B | C | D
       func(item)  # type: ignore[type-var] - T can't bind to Union
   ```
   - TypeVar can't narrow Union at call site
   - Need runtime isinstance checks or overloads

---

## Recommendations

### Quick Wins (Completed ✅)
- ✅ Method renaming (ffba5d21)
- ✅ Sequence instead of tuple (360cbb29)
- ✅ TypeVar for homogeneous operations (75923349)

### Medium Effort (Worthwhile)
- **attr-defined (28 cases):** Add @property decorators or stub files
- **override (20 cases):** Review Liskov violations, fix safe ones
- **misc (14 cases):** Fix ClassVar assignment patterns

### High Effort (Document Instead)
- **Nested dict.setdefault (8 cases):** Type annotations don't match runtime
- **Union call sites (30+ cases):** Need overloads or runtime checks
- **Dynamic type behavior:** Type system can't express, document in comments

### Best Practices Going Forward

1. **For new code:**
   - Use `Sequence[T]` for parameters accepting list or tuple
   - Use `TypeVar` for operations that should preserve type
   - Add specific error codes to ignores (`type-var` not `arg-type`)

2. **For existing ignores:**
   - Document WHY with comments
   - Use specific error codes
   - Link to type system limitations when applicable

3. **For refactoring:**
   - Start with easy wins (list→tuple)
   - Document hard cases, don't force fixes
   - Test runtime behavior isn't changed

---

## Progress Tracking

**Starting total:** 201
**Current total:** 194
**Fixed:** 7 (-3.5%)
**Target:** < 150 (remove easy wins)
**Stretch goal:** < 100

### By Category

| Category | Before | After | Change |
|----------|--------|-------|--------|
| arg-type | 68 | 63 | -5 |
| type-var | 0 | 3 | +3 (better than arg-type) |
| Other | 133 | 128 | -5 |
| **Total** | **201** | **194** | **-7** |

### Commits

1. `ffba5d21` - Rename extract() methods (16 files, 0 ignores removed, clarity improvement)
2. `360cbb29` - Fix ASPath list→tuple (3 files, -5 ignores)
3. `75923349` - Fix aspath slicing TypeVar (1 file, -2 ignores, improved 3)

---

**Updated:** 2025-11-30
