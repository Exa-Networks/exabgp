# Type Ignore Elimination Plan

**Status:** In Progress
**Created:** 2025-11-30
**Total ignores:** 201 across 92 files

---

## Summary by Error Code

| Code | Count | % | Description |
|------|-------|---|-------------|
| `arg-type` | 68 | 33% | Type system limitations with unions/conversions |
| `attr-defined` | 28 | 14% | Dynamic attributes not in type stubs |
| `override` | 20 | 10% | Intentional signature changes in subclasses |
| `misc` | 14 | 7% | ClassVar assignments, type aliasing |
| `no-any-return` | 12 | 6% | Functions returning Any |
| `no-code` | 9 | 4% | Generic ignores without specific error |
| Other | 50 | 25% | Various one-off cases |

---

## Root Causes

### 1. Union + Operations (30+ cases)

**Pattern:** Operations on union types lose type information

**Files affected:**
- `bgp/message/update/attribute/aspath.py` (6 ignores)
- `bgp/message/update/attribute/community/extended/communities.py` (3)
- `bgp/message/update/nlri/mvpn/*.py` (9 total)
- `bgp/message/update/nlri/evpn/*.py` (6 total)

**Example:**
```python
def _segment(cls, seg_type: int,
             values: SET | SEQUENCE | CONFED_SEQUENCE | CONFED_SET,
             asn4: bool) -> bytes:
    # Slicing Union loses original type
    values[:MAX_LEN]  # type: ignore[arg-type]
    # Iteration over Union - mypy can't prove all have .pack_asn()
    b''.join(v.pack_asn(asn4) for v in values)  # type: ignore[arg-type]
```

**Why:** Mypy can't prove:
- Slice of `Union[A|B|C|D]` returns same type
- All union members have same methods
- Operations preserve type

**Fix strategy:**
- Use `TypeVar` with bound: `T = TypeVar('T', bound=list[ASN])`
- Replace union parameters with generic `T`
- Mypy can then track type through operations

### 2. List → Tuple Coercion (15+ cases)

**Pattern:** Passing `list` where `tuple` expected

**Files affected:**
- `bgp/message/update/attribute/aspath.py` (2 ignores - Empty constructors)
- `configuration/static/parser.py` (5 ignores)
- `configuration/static/mpls.py` (3 ignores)

**Example:**
```python
# ASPath.__init__ expects: tuple[SET|SEQUENCE|...], gets list
ASPath([])  # type: ignore[arg-type]
ASPath(ASN.from_string(value))  # type: ignore[arg-type]
```

**Why:** Python allows list→tuple coercion, but mypy is strict

**Fix strategy:**
- Change signatures to accept `Sequence[T]` instead of `tuple[T, ...]`
- Or use `tuple()` wrapper: `ASPath(tuple())`
- Or fix call sites to pass tuples

### 3. Nested dict.setdefault() Chains (8+ cases)

**Pattern:** Nested `setdefault()` with complex types

**Files affected:**
- `rib/outgoing.py` (4 ignores)
- `reactor/network/outgoing.py` (4 ignores)

**Example:**
```python
# Type: dict[int, dict[Family, RIBdict]]
attr_af_nlri.setdefault(change_attr_index, {}) \
            .setdefault(change_family, RIBdict({})) \
            [change_index] = change  # type: ignore[arg-type]
```

**Why:** Mypy loses track of types through chained `.setdefault()` calls

**Fix strategy:**
- Add intermediate type annotations:
  ```python
  level1: dict[Family, RIBdict] = attr_af_nlri.setdefault(change_attr_index, {})
  level2: RIBdict = level1.setdefault(change_family, RIBdict({}))
  level2[change_index] = change  # No ignore needed
  ```

### 4. Method Name Collision (1 case - HIGH PRIORITY)

**Pattern:** Multiple inheritance with same method name

**Files affected:**
- `bgp/message/open/capability/asn4.py` (1 ignore)
- `bgp/message/open/asn.py` (defines `extract()`)
- `bgp/message/open/capability/capability.py` (defines `extract()`)

**Example:**
```python
class ASN4(Capability, ASN):
    def extract(self) -> list[bytes]:
        # Both parents define extract()
        return ASN.extract(self)
```

**Why:** ASN4 inherits from both Capability and ASN, both define `extract()`

**Fix strategy:**
- Rename `ASN.extract()` → `extract_asn()` (only 1 usage in ASN4)
- Rename `Capability.extract()` → `extract_capability()` (used in capabilities.py)
- **Recommendation:** Rename `ASN.extract()` (fewer changes)

---

## Action Items

### High Priority

- [ ] Fix method name collision (ASN4.extract)
  - Rename `ASN.extract()` → `extract_asn()`
  - Update ASN4 to call `ASN.extract_asn()`
  - Remove `# type: ignore[assignment]` in asn4.py:38

### Medium Priority

- [ ] Fix list→tuple coercions (15 cases, easy wins)
  - Change `ASPath.__init__` to accept `Sequence`
  - Or add `tuple()` wrappers at call sites
  - Target: Remove 15+ ignores

- [ ] Fix nested dict.setdefault chains (8 cases)
  - Add intermediate variables with type annotations
  - Target: Remove 8+ ignores in rib/outgoing.py

### Low Priority

- [ ] Fix Union + Operations (30 cases, architectural change)
  - Requires generics/TypeVar refactoring
  - Most complex, highest impact
  - Target: Remove 30+ ignores

- [ ] Fix attr-defined (28 cases)
  - Add proper type stubs
  - Or use `@property` decorators
  - Some may be legitimate dynamic behavior

- [ ] Fix override (20 cases)
  - Review each case for Liskov substitution
  - May require signature changes
  - Some may be intentional violations

- [ ] Document legitimate ignores
  - environment/config.py - Generic T narrowing (legitimate)
  - update/__init__.py - Runtime imports (legitimate)
  - Others requiring investigation

---

## Progress Tracking

**Total ignores:** 201
**Fixed:** 0
**Target:** < 150 (remove easy wins)
**Stretch goal:** < 100

---

**Updated:** 2025-11-30
