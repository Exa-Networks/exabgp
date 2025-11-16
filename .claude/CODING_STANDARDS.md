# ExaBGP Coding Standards

---

## Python 3.8.1+ Compatibility (MANDATORY)

**ALL code MUST work with Python 3.8.1+**

### Type Annotations

✅ **CORRECT (Python 3.8+):**
```python
from typing import Union, Optional, Dict, List, Tuple

def func(x: Union[int, str]) -> Optional[bool]:
    data: Dict[str, List[int]] = {}
```

❌ **WRONG (Python 3.10+ only):**
```python
def func(x: int | str) -> bool | None:  # NO - requires 3.10+
    data: dict[str, list[int]] = {}      # NO - requires 3.9+ without __future__
```

### With `from __future__ import annotations`

Most ExaBGP files have this. When present:
```python
from __future__ import annotations

# ✅ OK - lowercase generics work in annotations
def func(x: dict[str, int]) -> list[str]:
    pass

# ❌ STILL WRONG - pipe requires 3.10+
def func(x: int | str) -> None:  # NO
```

**Quick Reference:**
| Feature | Python 3.8 | Python 3.10+ (DON'T USE) |
|---------|-----------|--------------------------|
| Union | `Union[int, str]` ✅ | `int \| str` ❌ |
| Optional | `Optional[str]` ✅ | `str \| None` ❌ |
| Dict (with `__future__`) | `dict[str, int]` ✅ | N/A |
| List (with `__future__`) | `list[int]` ✅ | N/A |

---

## Linting

```bash
ruff format src/  # Single quotes, 120 char lines
ruff check src/   # Must pass
```

Config in `pyproject.toml`.

---

## Testing (MANDATORY)

Before declaring code "fixed"/"ready"/"working"/"complete":

1. ✅ `ruff format src && ruff check src`
2. ✅ `env exabgp_log_enable=false pytest ./tests/unit/`
3. ✅ `./qa/bin/functional encoding <test_id>`

**See:** `.claude/docs/CI_TESTING_GUIDE.md`

---

## BGP Method APIs (STABLE - DO NOT CHANGE)

### Protocol Elements (Messages, Attributes, NLRIs)

**REQUIRED signatures:**
```python
def pack(self, negotiated: Negotiated) -> bytes:
    pass

@classmethod
def unpack_X(cls, data: bytes, negotiated: Negotiated) -> SomeType:
    pass
```

**Unused parameters are OK and EXPECTED:**
```python
def pack(self, negotiated: Negotiated) -> bytes:
    # negotiated not used - that's fine
    return self._value.pack()
```

**Why:**
- Uniform API for all protocol elements
- Future-proofing
- Type safety
- Registry pattern requires it

❌ **DO NOT:**
- Remove unused `negotiated` parameters
- Make `negotiated` Optional
- Suggest removing it

### Utility Classes (ESI, Labels, TLVs, etc.)

Use `pack_X()` / `unpack_X()` - NO negotiated parameter.

Examples: `pack_esi()`, `pack_labels()`, `pack_tlv()`

---

## Architecture Constraints

- **No asyncio** - Uses custom reactor pattern
- **No FIB manipulation** - BGP protocol only, not routing

---

## Git Workflow

**NEVER commit without explicit user request:**
- User must say: "commit", "make a commit", "git commit"
- DO NOT commit after completing work automatically
- WAIT for user to review changes first

**NEVER push without explicit user request:**
- Each push requires explicit instruction for THAT work
- User must say: "push", "git push", "push now"

**Before ANY git operation:**
1. Run `git status`
2. Run `git log --oneline -5`
3. Verify no unexpected changes
4. Ask user if unsure

---

## Quick Checklist

Before submitting changes:

- [ ] Python 3.8.1+ syntax (`Union`, not `|`)
- [ ] `ruff format src && ruff check src` passes
- [ ] `pytest ./tests/unit/` passes (all tests)
- [ ] `./qa/bin/functional encoding` passes
- [ ] No asyncio introduced
- [ ] No FIB manipulation
- [ ] User explicitly requested commit/push

---

**Updated:** 2025-11-16
