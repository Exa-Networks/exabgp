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

## Python 3.10+ Compatibility (MANDATORY)

### Type Annotations

ExaBGP 6.0 requires Python 3.10+, enabling modern type annotation syntax:

✅ **CORRECT (Python 3.10+ style - preferred):**
```python
def func(x: int | str) -> bool | None:
    data: dict[str, list[int]] = {}
```

✅ **ALSO CORRECT (legacy style - still works):**
```python
from typing import Union, Optional
def func(x: Union[int, str]) -> Optional[bool]:
    data: dict[str, list[int]] = {}
```

**Prefer modern syntax** (`int | str`) for new code, but don't refactor existing code just for style.

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

## Backport Tracking (MANDATORY for Bug Fixes)

After fixing ANY bug:
1. Add entry to `.claude/BACKPORT.md`
2. Include: date, commit hash, description, target branch

**Why:** Bug fixes often need backporting to stable branches. Track them immediately.

---

## Mypy Strict Locking (MANDATORY)

**Rule:** When a module passes mypy strict mode with 0 errors, lock it in `pyproject.toml` as part of the same commit.

**Check before committing:**
```bash
# Test if module passes strict
mypy --disallow-untyped-defs --disallow-untyped-calls --disallow-incomplete-defs --warn-return-any src/exabgp/<module>/
```

**If output shows "Success: no issues found":**
1. Add strict override to `pyproject.toml`:
```toml
[[tool.mypy.overrides]]
module = "exabgp.<module>.*"
disallow_untyped_defs = true
disallow_untyped_calls = true
disallow_incomplete_defs = true
warn_return_any = true
```
2. Include this change in the same commit

**Why:** Locking prevents regression - once clean, stays clean.

**Currently locked:** `util.*`, `data.*`, `environment.*`, `logger.*`, `rib.*`, `protocol.*`, `debug.*`, `netlink.*`, `cli` (excluding experimental), `conf.*`

---

## Mypy Configuration Changes (PROHIBITED)

**Rule:** DO NOT add code that requires changes to mypy configuration in `pyproject.toml`.

❌ **NEVER:**
- Add `# type: ignore` comments that could be avoided by better code design
- Write code requiring new mypy exclusions, suppressions, or relaxed settings
- Introduce patterns that need mypy configuration changes to pass type checking

✅ **ALWAYS:**
- Write code that passes mypy with CURRENT configuration
- If code fails mypy strict, fix the code (not the config)
- Use proper type annotations that satisfy existing mypy rules

**Why:** Mypy configuration should only become MORE strict over time, never more lenient. Every configuration change is technical debt.

---

## Class Attribute Type Annotations

**Avoid `| None` in class attributes when possible:**

❌ **AVOID:**
```python
class Foo:
    value: int | None = None
```

✅ **PREFER:** Use sentinels, default values, or restructure to avoid None:
```python
class Foo:
    value: int = 0  # Or appropriate default
```

**Why:** Optional class attributes spread None-checking throughout the codebase.

---

## `__eq__` Method Signatures

**Use the class type, not `object`, for `__eq__` parameter:**

❌ **AVOID:**
```python
def __eq__(self, other: object) -> bool:
    if not isinstance(other, MyClass):
        return False
    return self.value == other.value
```

✅ **PREFER:**
```python
def __eq__(self, other: 'MyClass') -> bool:  # type: ignore[override]
    return self.value == other.value
```

**Why:** Using the specific type:
1. Documents the intended usage - only compare same types
2. Makes attribute access type-safe (no isinstance check needed)
3. Prevents silent `False` returns for logic errors

**Note on `# type: ignore[override]`:** Required because we intentionally violate Liskov substitution principle. Python's `object.__eq__` accepts `object`, but we restrict to our type. This is a deliberate design choice.

**Limitation:** Mypy doesn't catch `x == "string"` at call sites because `==` is specially handled. The type annotation documents intent and enables type-safe implementation, but won't catch all misuse.

---

## Refactoring: Fix Root Causes

**When refactoring reveals mypy or type errors:**

❌ **NEVER hide problems:**
```python
x = cast(SomeType, problematic_value)  # Hides real issue
x = value  # type: ignore  # Silences warning without fixing
```

✅ **ALWAYS fix the root cause:**
- Trace back to where the bad type originates
- Fix the source, not the symptom
- If a function returns wrong type, fix the function
- If data structure is wrong, restructure it

**Why:** Casts and ignores hide bugs. Root cause fixes prevent bugs.

---

## Quick Checklist

- [ ] Python 3.10+ syntax (prefer `int | str` over `Union[int, str]`)
- [ ] Avoid `| None` class attributes when possible
- [ ] Fix type errors at root cause, never cast/ignore
- [ ] `ruff format src && ruff check src` passes
- [ ] `./qa/bin/test_everything` passes
- [ ] No asyncio introduced
- [ ] No FIB manipulation
- [ ] User explicitly requested commit/push
- [ ] Bug fix? Added to `.claude/BACKPORT.md`
- [ ] Module passes mypy strict? Lock it in `pyproject.toml`

---

## See Also

- MANDATORY_REFACTORING_PROTOCOL.md - Refactoring workflow
- TESTING_PROTOCOL.md - Test requirements for code changes
- exabgp/REGISTRY_AND_EXTENSION_PATTERNS.md - Extension patterns

---

**Updated:** 2025-11-30
