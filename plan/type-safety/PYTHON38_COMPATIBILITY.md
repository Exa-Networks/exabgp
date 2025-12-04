# Python 3.8+ Compatibility Requirements

**Target:** Python 3.8.1+ (per ExaBGP requirements in CLAUDE.md)
**CI Testing:** Python 3.8-3.12 (with legacy 3.6 support)

---

## Type Annotation Compatibility Guidelines

When adding or modifying type annotations in ExaBGP, follow these guidelines to ensure Python 3.8.1+ compatibility:

### ✅ REQUIRED: Use `from __future__ import annotations`

**ALL files with type annotations MUST include this at the top:**

```python
from __future__ import annotations
```

**Why:** This enables postponed evaluation of annotations (PEP 563), which:
- Allows forward references without quotes in many cases
- Prevents circular import issues at runtime
- Makes all annotations strings at runtime (zero overhead)
- Available since Python 3.7

**Status:** ✅ All modified files in Phase 1 already have this import

---

## Compatible Type Annotation Patterns

### ✅ TYPE_CHECKING for Circular Dependencies

**Pattern used in Phase 1:**

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.reactor.loop import Reactor
    from exabgp.bgp.neighbor import Neighbor

class Peer:
    def __init__(self, neighbor: 'Neighbor', reactor: 'Reactor') -> None:
        self.neighbor: 'Neighbor' = neighbor
        self.reactor: 'Reactor' = reactor
```

**Compatibility:**
- ✅ `TYPE_CHECKING` - Available since Python 3.5.2
- ✅ Forward references with quotes - Always compatible
- ✅ Type hints in `if TYPE_CHECKING:` block - Never executed at runtime

**Why quotes are still needed:**
Even with `from __future__ import annotations`, quotes are needed for types imported inside `if TYPE_CHECKING:` blocks because those imports don't exist at runtime.

---

### ✅ Optional and Union Types

**Compatible patterns:**

```python
from typing import Optional, Union

def example(
    neighbor: Optional['Neighbor'] = None,
    connection: Union['Incoming', 'Outgoing']
) -> Optional['Neighbor']:
    pass
```

**Compatibility:**
- ✅ `Optional` - Available since Python 3.5
- ✅ `Union` - Available since Python 3.5
- ✅ Works perfectly with forward references

---

### ✅ Tuple, Dict, List with Type Parameters

**Compatible patterns:**

```python
from typing import Tuple, Dict, List

def example(
    family: Tuple[AFI, SAFI],
    data: Dict[str, int],
    items: List['Neighbor']
) -> None:
    pass
```

**Compatibility:**
- ✅ `Tuple`, `Dict`, `List` - Available since Python 3.5
- ✅ Type parameters work in all Python 3.5+

---

### ✅ Generator Types

**Compatible pattern (for Phase 2):**

```python
from typing import Generator, Union

def read_message(self) -> Generator[Union[Message, NOP], None, None]:
    yield message
```

**Compatibility:**
- ✅ `Generator[YieldType, SendType, ReturnType]` - Python 3.5+
- ✅ `Union` in yield types - Python 3.5+

---

## ❌ AVOID: Python 3.9+ Only Features

### ❌ Built-in Generic Types (PEP 585)

**DON'T use (Python 3.9+ only):**

```python
# ❌ WRONG - Requires Python 3.9+
def example(items: list['Neighbor']) -> dict[str, int]:
    pass
```

**DO use instead:**

```python
# ✅ CORRECT - Python 3.8+ compatible
from typing import List, Dict

def example(items: List['Neighbor']) -> Dict[str, int]:
    pass
```

---

### ❌ Union Operator | (PEP 604)

**DON'T use (Python 3.10+ only):**

```python
# ❌ WRONG - Requires Python 3.10+
def example(value: int | str) -> None:
    pass

def example2(neighbor: 'Neighbor' | None) -> None:
    pass
```

**DO use instead:**

```python
# ✅ CORRECT - Python 3.8+ compatible
from typing import Union, Optional

def example(value: Union[int, str]) -> None:
    pass

def example2(neighbor: Optional['Neighbor']) -> None:
    pass
```

---

## Verification Steps

### Before Committing Type Annotation Changes

1. **Check for `from __future__ import annotations`**
   ```bash
   grep -L "from __future__ import annotations" src/exabgp/**/*.py
   ```

2. **Check for Python 3.9+ features**
   ```bash
   # Look for lowercase generic types (should use typing.List etc)
   grep -r "def.*->.*list\[" src/exabgp/
   grep -r "def.*->.*dict\[" src/exabgp/

   # Look for Union operator (should use typing.Union)
   grep -r "def.*|.*:" src/exabgp/
   ```

3. **Always run full test suite**
   ```bash
   uv run ruff format src && uv run ruff check src
   env exabgp_log_enable=false uv run pytest ./tests/unit/
   ./qa/bin/functional encoding
   ```

---

## Type Annotation Checklist for Future Phases

When working on Phases 2-8, ensure:

- [ ] File has `from __future__ import annotations` at top
- [ ] Use `TYPE_CHECKING` for circular dependency imports
- [ ] Use quoted forward references for TYPE_CHECKING imports
- [ ] Use `typing.Optional`, not `| None`
- [ ] Use `typing.Union`, not `|` operator
- [ ] Use `typing.List/Dict/Tuple`, not `list/dict/tuple`
- [ ] Use `typing.Generator`, properly parameterized
- [ ] Test with `ruff check` (catches many compatibility issues)
- [ ] Test with full unit test suite

---

## Why This Matters

**ExaBGP must support:**
- Python 3.8.1+ (stated in CLAUDE.md)
- Python 3.6 for legacy tests
- CI tests run on Python 3.8-3.12

**Breaking compatibility would:**
- Fail CI on older Python versions
- Break production deployments using Python 3.8
- Violate project requirements

**Our approach ensures:**
- ✅ Works on Python 3.8.1+
- ✅ No runtime overhead (annotations are strings)
- ✅ Full type checking support for modern IDEs
- ✅ Backward compatible with existing code

---

## References

- **PEP 484** - Type Hints (Python 3.5+)
- **PEP 563** - Postponed Evaluation of Annotations (Python 3.7+, via `__future__`)
- **PEP 585** - Builtin Generic Types (Python 3.9+ - DON'T USE)
- **PEP 604** - Union Operator (Python 3.10+ - DON'T USE)
- **typing module docs**: https://docs.python.org/3.8/library/typing.html

---

## Phase 1 Compliance

✅ **All Phase 1 changes are Python 3.8.1+ compatible:**

- Used `from __future__ import annotations` (already present)
- Used `TYPE_CHECKING` for circular dependencies (Python 3.5.2+)
- Used `typing.Optional`, `typing.Union` (Python 3.5+)
- Used `typing.Tuple` with type parameters (Python 3.5+)
- Used quoted forward references for TYPE_CHECKING imports
- Avoided Python 3.9+ features (built-in generics, | operator)

**Verified:** All code runs on Python 3.8+ and passes all tests.
