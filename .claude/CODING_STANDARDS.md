# ExaBGP Coding Standards

---

## 🧠 Code Quality - Think Before You Code

**BEFORE writing ANY code:**
1. Read and understand ALL related existing code
2. Trace through data flows and type signatures
3. Verify assumptions against actual implementation
4. Check for edge cases and error conditions
5. Look for similar patterns already in the codebase

**NEVER:**
- Guess at APIs or function signatures - READ the actual code
- Make assumptions about behavior - VERIFY by reading implementation
- Copy patterns without understanding why they work
- Write code without understanding the full context
- Rush to implementation without analysis

**Thinking checklist (complete BEFORE coding):**
- [ ] What types are expected? (checked actual definitions)
- [ ] What are the edge cases? (empty lists, None, duplicates, invalid input)
- [ ] Is there existing code doing something similar?
- [ ] Have I read the functions this will call?
- [ ] Have I traced through the full data flow?
- [ ] What error conditions need handling?
- [ ] Are there any inconsistencies in naming/types?

**If you find yourself making the same mistake twice, STOP and re-read all relevant code.**

---

## Python 3.8.1+ Compatibility (MANDATORY)

### Type Annotations

| Feature | Python 3.8 ✅ | Python 3.10+ ❌ (DON'T USE) |
|---------|-------------|---------------------------|
| Union | `Union[int, str]` | `int \| str` |
| Optional | `Optional[str]` | `str \| None` |
| Dict (with `__future__`) | `dict[str, int]` | N/A |
| List (with `__future__`) | `list[int]` | N/A |

✅ **CORRECT:**
```python
from typing import Union, Optional, Dict, List
def func(x: Union[int, str]) -> Optional[bool]:
    data: Dict[str, List[int]] = {}
```

❌ **WRONG:**
```python
def func(x: int | str) -> bool | None:  # NO - requires 3.10+
    data: dict[str, list[int]] = {}      # NO - requires 3.9+ without __future__
```

### With `from __future__ import annotations`

Most ExaBGP files have this. When present:
```python
from __future__ import annotations

# ✅ OK - lowercase generics in annotations
def func(x: dict[str, int]) -> list[str]: pass

# ❌ STILL WRONG - pipe requires 3.10+
def func(x: int | str) -> None: pass  # NO
```

---

## Linting

```bash
ruff format src/  # Single quotes, 120 char
ruff check src/   # Must pass
```

---

## Testing (MANDATORY)

Before declaring "fixed"/"ready"/"working"/"complete":

```bash
./qa/bin/test_everything  # Runs all 6 test suites
```

---

## BGP Method APIs (STABLE - DO NOT CHANGE)

### Protocol Elements (Messages, Attributes, NLRIs)

**REQUIRED signatures:**
```python
def pack(self, negotiated: Negotiated) -> bytes: pass

@classmethod
def unpack_X(cls, data: bytes, negotiated: Negotiated) -> SomeType: pass
```

**Unused parameters OK:**
```python
def pack(self, negotiated: Negotiated) -> bytes:
    return self._value.pack()  # negotiated unused - fine
```

**Why:** Uniform API, future-proofing, type safety, registry pattern requires it.

❌ DO NOT: Remove unused `negotiated`, make it Optional, suggest removing.

### Utility Classes (ESI, Labels, TLVs)

Use `pack_X()` / `unpack_X()` - NO negotiated parameter.

---

## Architecture

- **No asyncio** - custom reactor pattern
- **No FIB manipulation** - BGP protocol only

---

## Git Workflow

**NEVER commit without explicit user request:**
- User must say: "commit", "make a commit", "git commit"
- DO NOT commit after completing work
- WAIT for user review

**NEVER push without explicit user request:**
- Each push needs explicit instruction for THAT work
- User must say: "push", "git push", "push now"

**Before ANY git operation:**
1. Run `git status`
2. Run `git log --oneline -5`
3. Verify no unexpected changes
4. Ask if unsure

---

## Quick Checklist

- [ ] Python 3.8.1+ syntax (`Union`, not `|`)
- [ ] `ruff format src && ruff check src` passes
- [ ] `./qa/bin/test_everything` passes
- [ ] No asyncio introduced
- [ ] No FIB manipulation
- [ ] User explicitly requested commit/push
