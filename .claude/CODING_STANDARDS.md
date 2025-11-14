# ExaBGP Coding Standards

**CRITICAL:** All code changes MUST adhere to these standards.

---

## Python Version Compatibility

### ⚠️ MANDATORY: Python 3.8.1+ Compatibility

**ALL code changes MUST be compatible with Python 3.8.1 and above.**

ExaBGP maintains compatibility with Python 3.8.1+ to support enterprise Linux distributions with long-term support cycles.

### Type Annotations - Python 3.8 Syntax Requirements

When adding or modifying type annotations, you MUST use Python 3.8-compatible syntax:

#### ✅ CORRECT (Python 3.8+):
```python
from typing import Union, Optional, Dict, List, Tuple

# Union types
def func(x: Union[int, str]) -> Union[bool, None]:
    pass

# Optional types
def func(x: Optional[str] = None) -> None:
    pass

# Generic collections
data: Dict[str, List[int]] = {}
items: List[Tuple[str, int]] = []
```

#### ❌ INCORRECT (Python 3.10+ only):
```python
# DO NOT USE pipe operator for unions
def func(x: int | str) -> bool | None:  # ❌ Python 3.10+ only
    pass

# DO NOT USE pipe operator for Optional
def func(x: str | None = None) -> None:  # ❌ Python 3.10+ only
    pass

# DO NOT USE lowercase generic types
data: dict[str, list[int]] = {}  # ❌ Python 3.9+ only
items: list[tuple[str, int]] = []  # ❌ Python 3.9+ only
```

#### Exception: PEP 585 in Annotations (Python 3.8+)

**With `from __future__ import annotations`, you CAN use lowercase generics in type annotations:**

```python
from __future__ import annotations

# ✅ CORRECT - lowercase generics work in annotations with __future__ import
def func(x: dict[str, int]) -> list[str]:
    pass

class MyClass:
    items: dict[str, list[int]] = {}  # ✅ OK with __future__ import

# ❌ STILL INCORRECT - pipe operator requires Python 3.10+
def func(x: int | str) -> None:  # ❌ Even with __future__ import
    pass
```

**Most ExaBGP files already have `from __future__ import annotations` at the top, so:**
- ✅ Use `dict[...]`, `list[...]`, `tuple[...]` for type annotations
- ❌ NEVER use `|` for Union types - always use `Union[...]` from typing
- ❌ NEVER use `x | None` for Optional - always use `Optional[x]` from typing

### Quick Reference

| Feature | Python 3.8 Syntax | Python 3.10+ Only (DO NOT USE) |
|---------|-------------------|--------------------------------|
| Union types | `Union[int, str]` | `int \| str` ❌ |
| Optional | `Optional[str]` | `str \| None` ❌ |
| Dict (with `__future__`) | `dict[str, int]` ✅ | N/A |
| List (with `__future__`) | `list[int]` ✅ | N/A |
| Dict (without `__future__`) | `Dict[str, int]` ✅ | `dict[str, int]` ❌ |

---

## Code Quality Standards

### Linting (ruff)

All code MUST pass ruff checks:

```bash
ruff format src/  # Format code (single quotes, 120 char lines)
ruff check src/   # Check for issues
```

**Configuration:** See `pyproject.toml` for ruff settings.

### Code Style

- **Quotes:** Single quotes preferred (`'string'` not `"string"`)
- **Line length:** Maximum 120 characters
- **Formatting:** Use `ruff format` to auto-format

---

## Testing Requirements

### CRITICAL: All Changes Must Pass ALL Tests

Before declaring code "fixed", "ready", "working", or "complete", you MUST:

1. ✅ **Linting:** `ruff format src && ruff check src` - MUST pass with no errors
2. ✅ **Unit tests:** `env exabgp_log_enable=false pytest ./tests/unit/` - ALL tests MUST pass
3. ✅ **Functional tests:** `./qa/bin/functional encoding` - ALL tests MUST pass
   - **CRITICAL:** Set `ulimit -n 64000` before running functional tests
   - **CRITICAL:** Run ALL tests, not just individual tests

**See `.claude/docs/CI_TESTING_GUIDE.md` for complete testing requirements.**

---

## Type Annotation Standards

### Goals
- Replace `Any` with specific types where possible
- Improve IDE support and type checking
- Maintain runtime performance (zero overhead)
- Keep Python 3.8+ compatibility

### When to Use `Any`

`Any` is acceptable when:
1. **Dynamic typing is intentional** - Plugin systems, dynamic registries
2. **External library limitations** - Third-party APIs without type stubs
3. **Complex runtime polymorphism** - When Union types become too complex
4. **Performance-critical paths** - If type narrowing adds overhead

### Type Annotation Patterns

**Use TYPE_CHECKING for circular imports:**
```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.configuration.core.tokeniser import Tokeniser

def func(tokeniser: 'Tokeniser') -> None:  # Forward reference
    pass
```

**Use specific types over Any:**
```python
# ✅ GOOD
def process(data: dict[str, Union[int, str]]) -> list[str]:
    pass

# ❌ BAD
def process(data: Any) -> Any:
    pass
```

---

## Architecture Constraints

### No asyncio (Custom Reactor Pattern)

ExaBGP uses a **custom reactor pattern**, NOT asyncio. Do not introduce asyncio dependencies.

**Rationale:** ExaBGP predates asyncio adoption and has a well-tested custom event loop.

### No FIB Manipulation

ExaBGP is a BGP implementation that does **NOT manipulate the FIB** (Forwarding Information Base).

Focus is on:
- BGP protocol implementation
- External process communication via JSON API
- Route information management

---

## Git Workflow Standards

### Commit Messages

- Clear, descriptive commit messages
- Reference issue numbers when applicable
- Include test results in commit message for major changes

### Testing Before Commit

**NEVER commit code without running all tests.** See Testing Requirements above.

---

## Performance Considerations

### Type Annotations Have Zero Runtime Cost

Type annotations are metadata only - they don't affect runtime performance.

### Registry Pattern Performance

The registry pattern is performance-critical. When modifying:
- Maintain LRU caching where present
- Don't add runtime type checks in hot paths
- Use lazy loading patterns

---

## Documentation Standards

### Docstrings

- All public APIs should have docstrings
- Include type information in docstring when helpful
- Document exceptions raised

### Comments

- Explain **why**, not **what**
- Complex algorithms need explanatory comments
- Mark TODOs/FIXMEs with context

---

## Common Pitfalls to Avoid

### ❌ Using Python 3.10+ Syntax
```python
# WRONG - Python 3.10+ only
def func(x: int | str) -> bool | None:
    pass
```

### ❌ Skipping Tests
```python
# WRONG - Never declare code "fixed" without running ALL tests
# You MUST run: ruff, pytest, AND functional tests
```

### ❌ Breaking Python 3.8 Compatibility
```python
# WRONG - match/case is Python 3.10+
match value:
    case 1:
        return "one"
```

### ❌ Using Modern Type Features
```python
# WRONG - TypeAlias is Python 3.10+
MyType: TypeAlias = Union[int, str]  # Use plain assignment instead
```

---

## Version Support Matrix

| Python Version | Support Status | Notes |
|----------------|---------------|-------|
| 3.6 | Legacy tests only | Deprecated, but CI tests still run |
| 3.8.1+ | **PRIMARY TARGET** | Minimum supported version |
| 3.9, 3.10, 3.11, 3.12 | Fully supported | All CI tests run |

---

## References

- **Main project instructions:** `/CLAUDE.md` (root of repository)
- **Testing guide:** `.claude/docs/CI_TESTING_GUIDE.md`
- **Type annotation project:** `.claude/type-annotations/`
- **ruff configuration:** `pyproject.toml`

---

## Quick Checklist for Code Changes

Before submitting changes:

- [ ] Code uses Python 3.8.1+ compatible syntax
- [ ] Type annotations use `Union[...]` not `|`
- [ ] Type annotations use `Optional[...]` not `| None`
- [ ] `ruff format src && ruff check src` passes
- [ ] `pytest ./tests/unit/` passes (all tests)
- [ ] `./qa/bin/functional encoding` passes (all 71 tests)
- [ ] `ulimit -n 64000` was set before functional tests
- [ ] No asyncio introduced
- [ ] No FIB manipulation code added
- [ ] Docstrings added/updated where appropriate

---

**Last Updated:** 2025-11-14
**Maintainer:** Project team
**Version:** 1.0

---

**STARTUP PROTOCOL:** When reading this file at session start: output "✅ CODING_STANDARDS.md" only. NO summaries. NO thinking. Knowledge retained in context.
