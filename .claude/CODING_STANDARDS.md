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

## Python 3.12+ Compatibility (MANDATORY)

### Type Annotations

ExaBGP 6.0 requires Python 3.12+, enabling modern type annotation syntax:

✅ **CORRECT (Python 3.12+ style - preferred):**
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
uv run ruff format src/  # Single quotes, 120 char
uv run ruff check src/   # Must pass
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

## Buffer Protocol (PEP 688) - Zero-Copy Optimization 🚨

**Rule:** Use `Buffer` not `bytes` for `unpack` method `data` parameters.

This is a common pattern in Go and other languages with slice semantics, but rare in Python.
Claude tends to write `bytes` by default - **DO NOT** do this in ExaBGP.

✅ **CORRECT:**
```python
from exabgp.util.types import Buffer

@classmethod
def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> Attribute:
    # data can be bytes, memoryview, or any buffer - zero-copy slicing
    view = memoryview(data)
    ...
```

❌ **FORBIDDEN:**
```python
@classmethod
def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> Attribute:
    # Forces callers to convert memoryview to bytes - copies data!
    ...
```

**Why Buffer matters:**
- `memoryview` slicing is zero-copy (no memory allocation)
- `bytes` slicing creates new objects (memory allocation + copy)
- Network code processes many buffers - overhead adds up
- `struct.unpack()` accepts Buffer directly

**When to use `bytes` vs `Buffer`:**

| Use `bytes` when | Use `Buffer` when |
|------------------|-------------------|
| Dict keys (must be hashable) | `_packed` storage |
| Hashing required | Parsing wire data in unpack methods |
| External API requires bytes | Passing to struct.unpack |
| | Creating memoryview slices |

**Note on `_packed: Buffer`:** Store as `Buffer` to keep zero-copy optimization path open.
At runtime, may be `bytes` (after explicit copy) or `memoryview` (zero-copy from wire).
Copy to `bytes()` only when releasing large network buffers is needed.

**Import:** `from exabgp.util.types import Buffer`

**See:** `.claude/exabgp/PEP688_BUFFER_PROTOCOL.md` for full details

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
uv run mypy --disallow-untyped-defs --disallow-untyped-calls --disallow-incomplete-defs --warn-return-any src/exabgp/<module>/
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

## Refactoring: Right Solution, Not Easy Solution

**Core principle:** Always implement the RIGHT solution, not the easiest or lowest-impact one.

**When refactoring reveals mypy or type errors:**

❌ **NEVER hide problems or take shortcuts:**
```python
x = cast(SomeType, problematic_value)  # Hides real issue - no runtime check
x = value  # type: ignore  # Silences warning without fixing
if hasattr(obj, 'attr'):  # Workaround for missing attribute
```

✅ **ALWAYS fix the root cause, even if it means more work:**
- Trace back to where the bad type originates
- Fix the source, not the symptom
- If a function returns wrong type, fix the function's return type
- If a class is missing an attribute, add it to the class
- If data structure is wrong, restructure it
- Touch multiple files if that's where the fix belongs

**The "right" fix may take longer but results in better code quality.**

**Exception: `cast()` with runtime type checks:**
```python
# ✅ Acceptable - cast() preceded by isinstance check
if isinstance(self.default, bool):
    return cast(T, parsing.boolean(value))

# ✅ Acceptable - TypeVar narrowing after hasattr check
if hasattr(obj, 'value'):
    return cast(SomeType, obj.value)

# ✅ Best - assert/raise instead of fallback cast
if isinstance(x, int):
    return cast(T, x)
raise TypeError(f'Expected int, got {type(x)}')  # Not: return cast(T, x)

# ❌ Never - blind cast without verification
return cast(int, untrusted_value)
```

**Why:** Runtime checks prove safety. Blind casts and ignores hide bugs.

---

## Type Identification: Use ClassVar, Not hasattr/isinstance

**Rule:** Use ClassVar boolean flags for type/capability identification, NOT `hasattr()` or `isinstance()`.

❌ **NEVER:**
```python
# Checking for attribute existence - fragile, breaks with refactoring
has_label = hasattr(obj, '_labels_packed') and obj._labels_packed
has_rd = hasattr(obj, '_rd_packed') and obj._rd_packed

# isinstance checks spread throughout codebase - harder to maintain
if isinstance(nlri, Label):
    labels = nlri.labels
```

✅ **ALWAYS:** Use ClassVar flags that declare capability at class level:
```python
class INET:
    has_label: ClassVar[bool] = False  # Declares: this class has no labels
    has_rd: ClassVar[bool] = False     # Declares: this class has no RD

class Label(INET):
    has_label: ClassVar[bool] = True   # Override: this class HAS labels

class IPVPN(Label):
    has_rd: ClassVar[bool] = True      # Override: this class HAS RD

# Usage - check the flag, not the type
if nlri.has_label:
    labels = nlri.labels
if nlri.has_rd:
    rd = nlri.rd
```

**Why:**
1. **Explicit declaration** - Class capabilities are documented in the class itself
2. **Refactoring-safe** - Renaming internal attributes (`_labels_packed` → `_has_labels`) doesn't break checks
3. **Inheritance-friendly** - Subclasses inherit or override flags naturally
4. **Type-safe** - mypy can verify the flag exists (unlike hasattr)
5. **Faster** - ClassVar lookup is O(1), isinstance checks MRO

**Pattern:** For NLRI classes, use existing `has_label()` and `has_rd()` class methods, or add ClassVar flags.

---

## JSON/API Backward Compatibility

**CRITICAL: Do NOT break existing JSON API consumers.**

When modifying JSON output format for NLRI types, attributes, or messages:

1. **API v4 (`v4_json()`)**: ALWAYS maintain existing format for backward compatibility
   - Users have deployed systems parsing API v4 JSON output
   - Changing field names, structure, or values breaks their code
   - Example: MUP API v4 uses CamelCase names like `Type2SessionTransformedRoute`

2. **API v6 (`json()`)**: MAY introduce cleaner RFC-aligned formats
   - Example: MUP API v6 uses kebab-case names like `type-2-st-route`

3. **Implementation pattern** (see `src/exabgp/bgp/message/update/nlri/flow.py` for example):
   - `json()` - Returns API v6 format (default, may use new cleaner formats)
   - `v4_json()` - Returns API v4 format (backward compatible, calls `json()` by default)
   - Override `v4_json()` in subclasses that need different output for API v4

4. **When adding new JSON fields**: Add to both `json()` and `v4_json()` output
   - New fields don't break backward compatibility
   - Removing or renaming fields DOES break compatibility

**Examples of breaking changes (FORBIDDEN for API v4):**
- Renaming `"name": "Type2SessionTransformedRoute"` to `"name": "type-2-st-route"`
- Changing `"rd": "100:100"` format to `"rd": {"asn": 100, "number": 100}`
- Removing any existing field

**See:** `plan/mup-json-name-format.md` for implementation example

---

## Quick Checklist

- [ ] Python 3.12+ syntax (prefer `int | str` over `Union[int, str]`)
- [ ] **Buffer protocol:** `data: Buffer` NOT `data: bytes` in unpack methods
- [ ] Avoid `| None` class attributes when possible
- [ ] Use ClassVar flags for type identification, not hasattr/isinstance
- [ ] Fix type errors at root cause, avoid `# type: ignore`
- [ ] Only use `cast()` when preceded by runtime type check (isinstance/hasattr)
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

**Updated:** 2025-12-15
