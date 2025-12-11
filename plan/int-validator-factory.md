# Integer Validator Factory Pattern

**Status:** ✅ Phase 1-4 Complete
**Created:** 2025-12-11
**Updated:** 2025-12-11

## Goal

Replace manual integer validation (min_value/max_value in Leaf schema) with a factory pattern that provides pre-configured validators for specific configuration values.

**Benefits:**
- Validation logic defined once, reused everywhere
- Schema is simpler (no min_value/max_value parameters)
- Named validators are self-documenting
- Easier to add keyword alternatives (e.g., "disable" for graceful-restart)

---

## Current Pattern (to be replaced)

### In capability.py
```python
# Manual parsing function
def gracefulrestart(tokeniser: 'Tokeniser', default: int | bool) -> int | bool:
    state = string(tokeniser)
    if state in ('disable', 'disabled'):
        return False
    try:
        grace = int(state)
    except ValueError:
        raise ValueError(...)
    if grace < 0:
        raise ValueError(...)
    if grace > Graceful.MAX:
        raise ValueError(...)
    return grace

# Schema with min/max
'graceful-restart': Leaf(
    type=ValueType.INTEGER,
    min_value=0,
    max_value=4095,
    ...
)

# Custom parser in known dict
known = {
    'graceful-restart': gracefulrestart,
}
```

### In schema.py Leaf class
```python
@dataclass
class Leaf(SchemaNode):
    min_value: int | None = None
    max_value: int | None = None
```

---

## Target Pattern

### Factory class in validator.py
```python
class IntValidators:
    """Factory for common integer validators with predefined ranges."""

    @staticmethod
    def graceful_restart() -> IntegerOrKeywordValidator:
        """Graceful restart time: 0-4095 seconds or 'disable'."""
        return IntegerOrKeywordValidator(
            keywords={'disable': False, 'disabled': False}
        ).in_range(0, 4095)

    @staticmethod
    def hold_time() -> IntegerValidator:
        """BGP hold time: 0 or 3-65535 seconds."""
        return IntegerValidator().in_range(0, 65535)

    @staticmethod
    def ttl() -> IntegerValidator:
        """TTL value: 0-255."""
        return IntegerValidator().in_range(0, 255)

    @staticmethod
    def port() -> IntegerValidator:
        """TCP/UDP port: 1-65535."""
        return IntegerValidator().in_range(1, 65535)

    @staticmethod
    def label() -> IntegerValidator:
        """MPLS label: 0-1048575."""
        return IntegerValidator().in_range(0, 1048575)

    @staticmethod
    def range(min_val: int, max_val: int) -> IntegerValidator:
        """Create validator for arbitrary range."""
        return IntegerValidator().in_range(min_val, max_val)
```

### Schema using factory
```python
'graceful-restart': Leaf(
    type=ValueType.GRACEFUL_RESTART,  # or use validator= directly
    description='Graceful restart time in seconds (0-4095) or "disable"',
    default=0,
    ...
)
```

### Leaf class without min/max
```python
@dataclass
class Leaf(SchemaNode):
    type: ValueType = ValueType.STRING
    validator: Validator | None = None  # Optional explicit validator
    # REMOVED: min_value, max_value
```

---

## New Validators to Add

### IntegerOrKeywordValidator

For values that accept integers OR specific keywords with custom return values.
Handles all cases including "disable" (no need for specialized subclass).

```python
@dataclass
class IntegerOrKeywordValidator(Validator[int | Any]):
    """Validates integer values with optional keyword alternatives."""

    name: str = 'integer-or-keyword'
    min_value: int | None = None
    max_value: int | None = None
    keywords: dict[str, Any] = field(default_factory=dict)  # keyword -> return value

    def _parse(self, value: str) -> int | Any:
        lower = value.lower()
        if lower in self.keywords:
            return self.keywords[lower]

        try:
            num = int(value)
        except ValueError:
            valid_range = f'{self.min_value}-{self.max_value}' if self.min_value is not None else 'integer'
            valid_keywords = ', '.join(f"'{k}'" for k in self.keywords.keys())
            raise ValueError(
                f"'{value}' is not valid\n  Valid options: {valid_range} or {valid_keywords}"
            ) from None

        if self.min_value is not None and num < self.min_value:
            raise ValueError(f'{num} is below minimum {self.min_value}')
        if self.max_value is not None and num > self.max_value:
            raise ValueError(f'{num} exceeds maximum {self.max_value}')
        return num

    def in_range(self, min_val: int, max_val: int) -> 'IntegerOrKeywordValidator':
        """Return new validator with range constraint."""
        new = deepcopy(self)
        new.min_value = min_val
        new.max_value = max_val
        return new

    def with_keywords(self, keywords: dict[str, Any]) -> 'IntegerOrKeywordValidator':
        """Return new validator with keyword alternatives."""
        new = deepcopy(self)
        new.keywords = keywords
        return new
```

---

## Locations to Update

### Files with min_value/max_value in Leaf

Search pattern: `min_value=|max_value=` in configuration files.

| File | Leaf | Current Range | Factory Method |
|------|------|---------------|----------------|
| `capability.py` | `graceful-restart` | 0-4095 | `IntValidators.graceful_restart()` |
| TBD | TBD | TBD | TBD |

### Files with manual INT + range validation

| File | Function | Description |
|------|----------|-------------|
| `capability.py` | `gracefulrestart()` | Remove after conversion |
| TBD | TBD | TBD |

---

## Implementation Phases

### Phase 1: Add New Validators
- [ ] Add `IntegerOrKeywordValidator` to `validator.py`
- [ ] Add `IntValidators` factory class to `validator.py`
- [ ] Add unit tests for new validators

### Phase 2: Add ValueTypes (if needed)
- [ ] Evaluate: Add `ValueType.GRACEFUL_RESTART` etc. OR use `validator=` parameter
- [ ] Update `_build_validator_factories()` if adding ValueTypes
- [ ] Update `get_validator()` to handle new types

### Phase 3: Update Schema Classes
- [ ] Add `validator: Validator | None = None` to `Leaf` class
- [ ] Update `Leaf.get_validator()` to prefer explicit validator over ValueType lookup
- [ ] Deprecate `min_value`/`max_value` (keep for backward compat initially)

### Phase 4: Convert capability.py
- [ ] Update `graceful-restart` Leaf to use factory validator
- [ ] Remove `gracefulrestart()` function from `known` dict
- [ ] Remove manual parsing function
- [ ] Verify tests pass

### Phase 5: Find and Convert Other Uses
- [ ] Search for `min_value=` and `max_value=` in codebase
- [ ] Search for manual `int()` + range checks in configuration parsing
- [ ] Convert each to use factory pattern
- [ ] Update tests

### Phase 6: Cleanup
- [ ] Remove `min_value`/`max_value` from `Leaf` class (if all uses converted)
- [ ] Update documentation
- [ ] Run `./qa/bin/test_everything`

---

## Files Summary

### Files to Modify
| File | Change |
|------|--------|
| `src/exabgp/configuration/validator.py` | Add `IntegerOrKeywordValidator`, `IntValidators` factory class |
| `src/exabgp/configuration/schema.py` | Add `validator` parameter to `Leaf`, deprecate `min_value`/`max_value` |
| `src/exabgp/configuration/capability.py` | Use `IntValidators.graceful_restart()`, remove manual function |

### New Files
| File | Purpose |
|------|---------|
| `tests/unit/configuration/test_int_validators.py` | Tests for new validators |

---

## Progress

- [x] Phase 1: Add New Validators ✅
- [x] Phase 2: Add ValueTypes - SKIPPED (using direct validator= parameter instead)
- [x] Phase 3: Update Schema Classes ✅ (already supported validator= parameter)
- [x] Phase 4: Convert capability.py ✅
- [ ] Phase 5: Find and Convert Other Uses - PARTIAL (neighbor uses deferred, see notes)
- [ ] Phase 6: Cleanup

---

## Completed Work (2025-12-11)

### Phase 1: New Validators Added

**IntegerOrKeywordValidator** (`validator.py`):
- Validates integers with optional keyword alternatives
- Supports `in_range()`, `with_keywords()`, `with_default()` methods
- Handles empty input when default is set

**IntValidators Factory Class** (`validator.py`):
- `graceful_restart()` - 0-4095 + "disable" keyword, default=0
- `hold_time()` - 0-65535
- `ttl()` - 0-255
- `port()` - 1-65535
- `label()` - 0-1048575
- `asn()` - 0-4294967295
- `med()` - 0-4294967295
- `local_preference()` - 0-4294967295
- `range(min, max)` - generic range factory

### Phase 4: capability.py Converted

- Removed manual `gracefulrestart()` function
- Updated Leaf to use `validator=IntValidators.graceful_restart()`
- Removed entry from `known` dict

### Phase 5: neighbor/__init__.py - Deferred

The following fields have validators set but are OVERRIDDEN by `known` dict entries:
- `hold-time` - custom parser returns `HoldTime` object (RFC validation)
- `outgoing-ttl` - custom parser returns `int | None` (accepts "disable")
- `incoming-ttl` - custom parser returns `int | None` (accepts "disable")

**Reason for deferral:** These parsers return special types (HoldTime, int|None) that
require more sophisticated validator classes to replace. The `known` dict takes
precedence over schema validators, so the current changes have no effect.

**Future work:**
- Create `HoldTimeValidator` that returns `HoldTime` object with RFC 4271 validation
- Create `IntegerOrNoneValidator` for TTL fields

---

## Decisions Made

1. **ValueType vs validator parameter:** Using direct `validator=` parameter
   - More flexible, no need to modify ValueType enum
   - Each Leaf can have its own custom validator configuration

2. **Backward compatibility:** Keep `min_value`/`max_value` in Leaf
   - Still useful for fields that don't have `known` dict overrides
   - Provides documentation of expected ranges

---

## All Tests Pass

```
./qa/bin/test_everything
✓ All 15 tests passed
```
