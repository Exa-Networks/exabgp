# MyPy Error Reduction - Deep Strategic Analysis

**Status:** 🔄 Active (Analysis Phase)
**Created:** 2025-12-18
**Current Errors:** 50 (down from 1,149 baseline - 96% reduction)
**Target:** <50 errors

---

## Executive Summary

After deep analysis of the remaining 50 mypy errors, they fall into distinct categories with clear fix patterns. The user's insight that "many type issues can be fixed by using the base class as return" is key - covariant return types and unified base class methods are the primary patterns.

---

## Error Distribution by Root Cause

| Category | Count | Fix Complexity | Primary Pattern |
|----------|-------|----------------|-----------------|
| Method signature overrides | 6 | Medium | Add params with defaults / use base return type |
| Read-only property overrides | 4 | Easy | Remove base class setters OR keep writable |
| Flow NLRI (IComponent/BaseValue) | 6 | Hard | Add @classmethod, implement abstract methods |
| TypeVar bound constraints | 3 | Medium | Expand TypeVar bounds |
| Static route type narrowing | 6 | Medium | Use `type[INET]` union for nlri_class |
| Config misc (arithmetic, dicts) | 11 | Easy | Type guards, casts, dict type fixes |
| Srv6 TLV type hierarchy | 3 | Medium | Fix class hierarchy or use unions |
| EOR type marker | 1 | Easy | Use TypeAlias or Literal |
| Collection attribute access | 2 | Easy | Cast after attribute code check |
| NLRICollection type decl | 1 | Easy | Move annotation to class level |
| Extended communities list | 1 | Easy | Use base class in list type |
| Announce NextHop | 1 | Easy | Use .ip accessor or fix Route.with_nexthop |
| **Total** | **50** | | |

---

## Category 1: Method Signature Overrides (6 errors)

### 1.1 `generic.py:127` - unpack_attribute signature
**Error:** `unpack_attribute(cls, code, flag, data)` vs base `unpack_attribute(cls, data, negotiated)`
**Analysis:** GenericAttribute handles unknown attributes where code/flag are needed for reconstruction.
**Fix Options:**
1. **Rename to `unpack_generic`** - Avoids override conflict, GenericAttribute is special case
2. **Add code/flag to base with defaults** - Changes stable API (NOT recommended)
3. **Use `# type: ignore[override]` with documentation** - Acceptable for factory method variants

**Recommended:** Option 1 - Rename since GenericAttribute is not part of normal registry dispatch

### 1.2 `clusterlist.py:26` - from_string signature
**Error:** `from_string(cls, string)` vs base IP `from_string(cls, string, klass=None)`
**Fix:** Add `klass: IPFactory | None = None` parameter (unused but signature-compatible)

### 1.3 `ipvpn.py:439` - unpack_nlri return type
**Error:** Returns `tuple[NLRI, Buffer]` but INET declares `tuple[INET, Buffer]`
**Analysis:** Subclass return types must be covariant (equal or narrower). NLRI is WIDER than INET.
**Fix:** Change return type to `tuple[INET, Buffer]` or `tuple[IPVPN, Buffer]`
**Alternative:** Change INET to return `tuple[NLRI, Buffer]` (matches base class)

**Recommended:** All subclasses should return `tuple[NLRI, Buffer]` (base class type) for consistency

### 1.4 `inet.py:359` - json() extra parameter
**Error:** `json(self, announced=True, compact=False)` vs base `json(self, compact=False)`
**Fix:** Add `announced: bool = True` to base NLRI.json() signature with default

### 1.5 `unknown.py:48` - unpack_message missing negotiated
**Error:** `unpack_message(cls, data)` vs base `unpack_message(cls, data, negotiated)`
**Fix:** Add `negotiated: Negotiated` parameter (unused but signature-compatible)

### 1.6 `linkstate.py:274` - writeable attribute override
**Error:** Read-only property overrides writeable attribute
**Analysis:** Part of Category 2 (property overrides)

---

## Category 2: Read-Only Property Overrides (4 errors)

**Files:**
- `mvpn/nlri.py:173` - safi
- `mup/nlri.py:178, 183` - safi, rd
- `evpn/nlri.py:187` - safi

**Root Cause:** Family base class defines `afi` and `safi` as settable properties, but subclasses override as read-only (ClassVar or read-only property).

**Fix Pattern:** Check if Family setters are actually used anywhere. If not, remove setters from Family to make properties read-only at base level.

**Investigation needed:**
```bash
grep -r "\.afi\s*=" src/exabgp --include="*.py" | grep -v "__init__"
grep -r "\.safi\s*=" src/exabgp --include="*.py" | grep -v "__init__"
```

---

## Category 3: Flow NLRI Issues (6 errors)

### 3.1 BaseValue abstract instantiation (2 errors)
**Lines:** 507, 515 in flow.py
**Error:** `Cannot instantiate abstract class "BaseValue" with abstract attribute "short"`

**Code:**
```python
def converter(...) -> Callable[[str], BaseValue]:
    def _integer(value: str) -> BaseValue:
        return klass(function(value))  # klass is Type[BaseValue]
```

**Analysis:** `klass` parameter is `Type[BaseValue]` but should be a concrete subclass. The abstract method `short()` must be implemented.

**Fix:** Change signature to `klass: Type[NumericValue]` or another concrete class that implements `short()`. Or make BaseValue concrete by adding default `short()` implementation.

### 3.2 IComponent.make() not a classmethod (4 errors)
**Lines:** 901, 902, 911, 912 in flow.py
**Error:** `Missing positional argument "bgp"`, `Too many arguments for IComponent`

**Code (line 111-113):**
```python
def make(cls, bgp: Buffer) -> tuple[IComponent, Buffer]:
    """Pack the component to wire format. Must be overridden by subclasses."""
    raise NotImplementedError(...)
```

**Analysis:** `make` is defined as instance method but used as class method (`klass.make(bgp)`).

**Fix:** Add `@classmethod` decorator to `IComponent.make()`:
```python
@classmethod
def make(cls, bgp: Buffer) -> tuple[IComponent, Buffer]:
    raise NotImplementedError(...)
```

---

## Category 4: TypeVar Bound Constraints (3 errors)

### 4.1 `aspath.py:255` - SegmentType
**Error:** `Value of type variable "SegmentType" cannot be "SET | SEQUENCE | CONFED_SEQUENCE | CONFED_SET"`
**Fix:** Expand TypeVar bound to include all segment types

### 4.2 `sidinformation.py:45` - SubTlvType
### 4.3 `sidstructure.py:36` - SubSubTlvType
**Pattern:** TypeVar bounds don't include the actual concrete types being registered

**Fix:** Review TypeVar definitions and expand bounds, or use `TypeVar('T', bound=BaseType)` pattern

---

## Category 5: Static Route Type Narrowing (6 errors)

**File:** `configuration/static/route.py`
**Lines:** 352, 355, 419, 426, 450, 500

**Root Cause:** Variable `nlri_class` starts as `type[IPVPN]` (first assignment), then conditionally assigned `type[Label]` or `type[INET]` which are not subtypes of IPVPN.

**Fix:**
```python
# Before (mypy infers type[IPVPN] from first assignment)
if has_rd:
    nlri_class = IPVPN
elif has_labels:
    nlri_class = Label  # Error: type[Label] not compatible with type[IPVPN]
else:
    nlri_class = INET   # Error: type[INET] not compatible with type[IPVPN]

# After (explicit union type annotation)
nlri_class: type[INET] | type[Label] | type[IPVPN]
if has_rd:
    nlri_class = IPVPN
...
```

**Line 450 (kwargs spread):**
```python
new_nlri = target_cls.from_cidr(..., **kwargs)
# kwargs: dict[str, object] doesn't match Labels | None, RouteDistinguisher | None
```

**Fix:** Type-narrow kwargs or pass parameters explicitly:
```python
new_nlri = target_cls.from_cidr(
    nlri.cidr, nlri.afi, target_safi, nlri.path_info,
    labels=kwargs.get('labels'),  # type: ignore[arg-type]
    rd=kwargs.get('rd'),
)
```

---

## Category 6: Config Misc Issues (11 errors)

### 6.1 announce/__init__.py:65, 67, 88 - Arithmetic on Attribute
**Error:** `Unsupported operand types for - ("Attribute" and "int")`
**Code:**
```python
cut = last.attributes[Attribute.CODE.INTERNAL_SPLIT]
if mask >= cut:  # cut is Attribute | None, not int
```

**Fix:** Add type guard:
```python
cut = last.attributes[Attribute.CODE.INTERNAL_SPLIT]
if not isinstance(cut, InternalSplit):
    yield last
    return
# Now cut is known to be InternalSplit, use cut.value for int
```

### 6.2 static/__init__.py:37 - dict type mismatch
**Fix:** Align dict value types with base class

### 6.3 process/__init__.py:97, api.py:124, configuration.py:422 - dict_keys issues
**Fix:** Cast `dict_keys` to `list[str]` or use explicit list comprehension

### 6.4 neighbor/__init__.py:314 - returning Any
**Fix:** Add explicit return type annotation

### 6.5 l2vpn/__init__.py:33 - Container vs RouteBuilder
**Fix:** Align inheritance or use Union type

### 6.6 flow/route.py:103 - None vs Tokeniser
**Fix:** Add None check or make parameter Optional

---

## Category 7: Srv6 TLV Type Hierarchy (3 errors)

**File:** `configuration/static/mpls.py`
**Lines:** 181, 189, 191

**Error:** `list[Srv6SidInformation]` incompatible with `list[GenericSrv6ServiceSubTlv]`

**Root Cause:** Srv6SidInformation doesn't inherit from GenericSrv6ServiceSubTlv

**Fix Options:**
1. Make Srv6SidInformation inherit from GenericSrv6ServiceSubTlv
2. Change parameter type to `list[Srv6SidInformation | GenericSrv6ServiceSubTlv]`
3. Use Protocol type for structural typing

---

## Category 8-12: Quick Fixes (6 errors)

### 8. eor.py:77 - EOR.EOR not valid as type
**Fix:** Use `Literal[True]` or define as TypeAlias

### 9. collection.py:594, 603 - Attribute access
**Fix:** Cast after checking attribute code

### 10. collection.py:79 - Type declaration to non-self
**Fix:** Move `_nlris_cache: list[NLRI]` to class level `__slots__` or annotation

### 11. communities.py:218 - List type mismatch
**Fix:** Use base class `list[ExtendedCommunityBase]`

### 12. command/announce.py:176 - NextHop vs IP
**Fix:** Use `nexthop.ip` or check Route.with_nexthop signature

---

## Implementation Priority

### Phase 1: Quick Wins (15 min, -12 errors)
1. Add @classmethod to IComponent.make() (-4 errors in flow.py)
2. Fix property overrides by removing Family setters (-4 errors)
3. Fix EOR.EOR type usage (-1 error)
4. Fix NLRICollection type declaration (-1 error)
5. Fix extended communities list type (-1 error)
6. Fix NextHop vs IP (-1 error)

### Phase 2: Signature Alignment (30 min, -6 errors)
1. Align unpack_nlri return types to `tuple[NLRI, Buffer]` (-1 error)
2. Add announced param to base NLRI.json() (-1 error)
3. Add negotiated param to UnknownMessage.unpack_message (-1 error)
4. Rename GenericAttribute.unpack_attribute to unpack_generic (-1 error)
5. Fix ClusterID.from_string signature (-1 error)
6. Fix linkstate.py property (-1 error)

### Phase 3: Type Guards (45 min, -11 errors)
1. Fix announce arithmetic with type guards (-4 errors)
2. Fix static route type narrowing with explicit annotation (-6 errors)
3. Fix dict_keys issues (-1 error)

### Phase 4: Hierarchy Fixes (45 min, -6 errors)
1. BaseValue: add default short() implementation (-2 errors)
2. TypeVar bound expansions (-3 errors)
3. Srv6 TLV hierarchy fix (-3 errors)

### Phase 5: Remaining Config Issues (30 min, -10 errors)
1. Config misc issues with casts/guards

---

## Success Metrics

- [x] Error count < 100 (achieved: 50)
- [ ] Error count < 50
- [ ] Error count < 25
- [ ] All tests pass after each phase
- [ ] No new `# type: ignore` without user approval
- [ ] No mypy config changes

---

## Testing Protocol

After each phase:
```bash
uv run mypy src/exabgp 2>&1 | tail -3  # Verify error reduction
uv run ruff format src && uv run ruff check src  # Lint
env exabgp_log_enable=false uv run pytest ./tests/unit/ -x -q  # Unit tests
```

Before declaring complete:
```bash
./qa/bin/test_everything
```

---

**Last Updated:** 2025-12-18
