# Plan: Sentinel Watchdog Pattern

## Status: COMPLETED
## Created: 2025-12-06

## Problem

The `AttributeCollection.watchdog()` method currently returns `Attribute | None`:

```python
def watchdog(self) -> Attribute | None:
    return cast(Attribute | None, self.pop(Attribute.CODE.INTERNAL_WATCHDOG, None))
```

This requires callers to check for `None` and doesn't provide type safety for the watchdog name (which is actually a string stored as an internal pseudo-attribute).

## Current Usage

1. **Configuration parsing** (`configuration/static/parser.py`):
   - Creates `Watchdog(str)` subclass with `ID = Attribute.CODE.INTERNAL_WATCHDOG`
   - The watchdog name is stored as a string

2. **RIB outgoing** (`rib/outgoing.py`):
   ```python
   watchdog = route.attributes.watchdog()
   if watchdog:  # Checks if watchdog attribute exists
       self._watchdog.setdefault(watchdog, {})...  # Uses watchdog as dict key (string)
   ```

## Proposed Solution

Create a sentinel pattern with a dedicated `Watchdog` class:

### Option A: Sentinel with NoWatchdog (Recommended)

```python
# In src/exabgp/bgp/message/update/attribute/watchdog.py (new file)

class Watchdog:
    """Sentinel class for watchdog attribute."""
    __slots__ = ('name',)

    def __init__(self, name: str) -> None:
        self.name = name

    def __bool__(self) -> bool:
        return True

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Watchdog):
            return self.name == other.name
        return False

class _NoWatchdog(Watchdog):
    """Sentinel for no watchdog - singleton pattern."""
    __slots__ = ()

    def __init__(self) -> None:
        # Don't call super().__init__() - no name
        pass

    def __bool__(self) -> bool:
        return False  # Falsy when no watchdog

    def __str__(self) -> str:
        return ''

    def __repr__(self) -> str:
        return 'NoWatchdog'

# Singleton
NoWatchdog: Watchdog = _NoWatchdog()
```

### Changes Required

1. **Create `src/exabgp/bgp/message/update/attribute/watchdog.py`**
   - Define `Watchdog` and `NoWatchdog` sentinel classes

2. **Update `src/exabgp/bgp/message/update/attribute/collection.py`**
   ```python
   from exabgp.bgp.message.update.attribute.watchdog import Watchdog, NoWatchdog

   def watchdog(self) -> Watchdog:
       value = self.pop(Attribute.CODE.INTERNAL_WATCHDOG, None)
       if value is None:
           return NoWatchdog
       # value is the Watchdog(str) from parser
       return Watchdog(str(value))
   ```

3. **Update `src/exabgp/configuration/static/parser.py`**
   - Change parser to use `Watchdog` class instead of local `Watchdog(str)` subclass
   - Or keep parser as-is since it just needs `.ID` attribute

4. **Update `src/exabgp/rib/outgoing.py`**
   - Change type hints from `str` to `Watchdog` where appropriate
   - The `if watchdog:` pattern continues to work (NoWatchdog is falsy)
   - Use `watchdog.name` as dict key instead of `watchdog` directly

## Benefits

1. **Type safety**: `watchdog()` always returns `Watchdog`, never `None`
2. **Falsy check preserved**: `if watchdog:` still works via `__bool__`
3. **No cast needed**: Return type is concrete `Watchdog`
4. **Clear semantics**: `NoWatchdog` is explicit sentinel

## Files to Modify

| File | Changes |
|------|---------|
| `attribute/watchdog.py` | NEW: Watchdog and NoWatchdog classes |
| `attribute/collection.py` | Update watchdog() return type |
| `rib/outgoing.py` | Update type hints, use .name for dict keys |
| `configuration/static/parser.py` | Optional: Use new Watchdog class |

## Testing

1. Run unit tests: `env exabgp_log_enable=false uv run pytest ./tests/unit/`
2. Run functional tests: `./qa/bin/functional encoding`
3. Run full suite: `./qa/bin/test_everything`

## Rollback

If issues arise, revert to `Attribute | None` with cast.
