# BGP Class Refactoring: Packed-Bytes-First Pattern

## Goal

Refactor ALL BGP classes to a new pattern:
- `__init__(self, packed: bytes)` - ONLY takes packed wire-format data, validates size
- `@classmethod def make_TYPE(cls, ...)` - Factory methods for semantic construction
- `@property` decorators for accessing unpacked data (NO caching - unpack every access)

**Scope:** Messages, Attributes, NLRI - complete replacement of existing patterns

---

## Target Pattern

### Attributes (simple case - Origin)

```python
@Attribute.register()
class Origin(Attribute):
    def __init__(self, packed: bytes) -> None:
        if len(packed) != 1:
            raise ValueError(f'Origin requires exactly 1 byte, got {len(packed)}')
        self._packed = packed

    @classmethod
    def make_origin(cls, origin: int) -> 'Origin':
        return cls(bytes([origin]))

    @property
    def origin(self) -> int:
        return self._packed[0]

    def pack_attribute(self, negotiated: Negotiated | None = None) -> bytes:
        return self._attribute(self._packed)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> 'Origin':
        # Validation happens in __init__
        return cls(data)
```

### NLRI (complex case - has metadata not in wire format)

```python
@NLRI.register(AFI.ipv4, SAFI.unicast)
class INET(NLRI):
    def __init__(self, packed: bytes, afi: AFI, safi: SAFI,
                 action: Action = Action.UNSET,
                 path_info: PathInfo = PathInfo.DISABLED) -> None:
        self._packed = packed  # CIDR portion only
        self._afi = afi
        self._safi = safi
        self._action = action
        self._path_info = path_info
        self._nexthop = IP.NoNextHop

    @classmethod
    def make_route(cls, afi: AFI, safi: SAFI, cidr: CIDR,
                   action: Action = Action.ANNOUNCE) -> 'INET':
        return cls(cidr.pack_nlri(), afi, safi, action)

    @property
    def cidr(self) -> CIDR:
        return CIDR.unpack(self._packed)

    @property
    def action(self) -> Action:
        return self._action

    @action.setter
    def action(self, value: Action) -> None:
        self._action = value
```

---

## Progress Summary

| Wave | Category | Status | Classes |
|------|----------|--------|---------|
| 1 | Simple Attributes | ✅ COMPLETE | 4 |
| 2 | Complex Attributes | ✅ COMPLETE | 10 |
| 3 | Community Attributes | ✅ COMPLETE | ~20 |
| 4 | MP/SR/BGP-LS Attributes | 🔄 PARTIAL | ~50 (~28 done) |
| 5 | Qualifiers | ✅ COMPLETE | 5 |
| 6 | NLRI Types | 🔄 PARTIAL | ~10 |
| 7 | EVPN/BGP-LS/MUP/MVPN NLRI | ✅ COMPLETE | ~20 |
| 8 | Messages | ✅ COMPLETE | 6 |

**See:** [progress.md](progress.md) for detailed tracking of each class.

---

## Special Cases

### 1. NLRI Metadata (action, path_info, nexthop)

NLRI has metadata NOT in wire format. Solution: accept as `__init__` params alongside packed bytes:

```python
def __init__(self, packed: bytes, afi: AFI, safi: SAFI,
             action: Action = Action.UNSET, ...) -> None:
```

### 2. Singletons (NLRI.INVALID, NLRI.EMPTY, PathInfo.DISABLED)

Keep existing `_create_invalid()` pattern that bypasses `__init__`:
```python
NLRI.INVALID = NLRI._create_invalid()  # Uses object.__new__()
```

### 3. GenericAttribute (dynamic ID/FLAG)

Pass as `__init__` params since not in packed bytes:
```python
def __init__(self, packed: bytes, code: int, flag: int) -> None:
```

### 4. Multiple Inheritance (NextHop extends Attribute + IP)

Delegate IP functionality to composition, not inheritance:
```python
def __init__(self, packed: bytes) -> None:
    self._packed = packed

@property
def string(self) -> str:
    return IP.ntop(self._packed)
```

### 5. Attribute Cache System

Works unchanged - keyed by packed bytes:
```python
@classmethod
def setCache(cls) -> None:
    IGP = cls.make_origin(cls.IGP)
    cls.cache[Attribute.CODE.ORIGIN][IGP._packed] = IGP
```

### 6. Flow NLRI (Excluded)

Flow uses builder pattern - rules added via `add()` method, wire format computed dynamically. **Does NOT need conversion.**

---

## 🚨 MANDATORY: Test-Driven Development (TDD) 🚨

**ALL changes MUST follow TDD workflow. Tests are written BEFORE code changes.**

### TDD Workflow

For EACH class conversion:

1. **WRITE TESTS FIRST** (tests MUST fail initially)
   - Unit tests: `tests/unit/` - test new interface
   - Functional tests: `qa/encoding/` or `qa/decoding/` if needed

2. **Verify tests fail** (proves tests are meaningful)
   ```bash
   uv run pytest tests/unit/path/to/test.py -v  # Should FAIL
   ```

3. **Implement the change** to make tests pass

4. **Run full test suite**
   ```bash
   ./qa/bin/test_everything  # ALL must pass
   ```

### Test Requirements

| Change Type | Required Tests |
|-------------|----------------|
| New `__init__(packed)` | Unit test: construct from bytes, verify properties |
| New `make_*()` factory | Unit test: factory creates valid instance |
| Size validation | Unit test: invalid size raises `ValueError` |
| Property access | Unit test: property returns correct unpacked value |

---

## Per-File Checklist

For EACH file (one at a time per MANDATORY_REFACTORING_PROTOCOL):

1. [ ] Find all call sites: `grep -r "ClassName(" src/`
2. [ ] **Write unit tests for new interface** (tests should fail)
3. [ ] **Verify tests fail** before proceeding
4. [ ] Change `__init__` to accept only `packed: bytes` (+ metadata for NLRI)
5. [ ] Add size validation in `__init__`, raise `ValueError` if invalid
6. [ ] Add `@classmethod def make_TYPE(...)` factory methods
7. [ ] Convert instance attributes to `@property` (unpack from `_packed`)
8. [ ] Update `unpack_*` to call new `__init__` (validation in __init__)
9. [ ] Update all call sites to use factory methods
10. [ ] **Verify unit tests now pass**
11. [ ] Run `./qa/bin/test_everything` - ALL MUST PASS

---

## Risks

| Risk | Mitigation |
|------|------------|
| Property access performance | Monitor benchmarks; simple unpacking should be fast |
| Call site updates | grep all usages; update configuration parser |
| NLRI metadata handling | Accept as __init__ params, not in packed bytes |
| BGP-LS hierarchy complexity | Update BaseLS first, then subclasses inherit |

---

## Testing

After EACH file change:
```bash
./qa/bin/test_everything  # ALL 6 test suites must pass
```

Round-trip verification:
```bash
./qa/bin/functional encoding  # 72 tests
./qa/bin/functional decoding
```
