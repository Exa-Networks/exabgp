# MyPy Type Checking Status

**Date:** 2025-11-15
**MyPy Version:** 1.18.2
**Python Target:** 3.9 (code compatible with 3.8.1+)

## Current Status

**Total Errors:** 1,149 across 137 files
**Previous (with type: ignore):** 354 errors
**Type: ignore comments removed:** 698

## Error Distribution by Category

| Rank | Error Code | Count | Description |
|------|------------|-------|-------------|
| 1 | union-attr | 216 | Accessing attributes on Optional types without guards |
| 2 | attr-defined | 167 | Attribute doesn't exist on type |
| 3 | arg-type | 159 | Argument type mismatches |
| 4 | misc | 152 | Lambda type inference, misc issues |
| 5 | assignment | 146 | Type mismatches in assignments |
| 6 | no-any-return | 74 | Functions returning Any instead of specific types |
| 7 | override | 54 | Incompatible method overrides |
| 8 | operator | 50 | Unsupported operand types |
| 9 | return-value | 24 | Incorrect return types |
| 10 | index | 24 | Indexing Optional dicts without guards |

## Most Problematic Files

| Rank | File | Errors | Primary Issues |
|------|------|--------|----------------|
| 1 | reactor/peer.py | 97 | Optional Protocol/Processes/RIB access |
| 2 | bgp/message/update/nlri/flow.py | 84 | Multiple inheritance (IOperation/NumericString) |
| 3 | reactor/protocol.py | 66 | Union types, Optional access |
| 4 | configuration/flow/parser.py | 55 | Flow parsing type issues |
| 5 | logger/__init__.py | 34 | Method assignment, callable issues |
| 6 | bgp/message/operational.py | 31 | Message type hierarchy |
| 7 | reactor/api/transcoder.py | 31 | Type conversions |
| 8 | configuration/check.py | 30 | Configuration validation |
| 9 | reactor/api/processes.py | 29 | Process management |
| 10 | configuration/configuration.py | 28 | Config parsing |

## Key Issues Identified

### 1. Optional Types Without Guards (216 errors - union-attr)

**Problem:** Many Optional types are accessed without None checks.

**Common patterns:**
- `self.proto: Optional[Protocol]` - Protocol is None during initialization, non-None during operation
- `self.reactor.processes: Optional[Processes]` - Initialized in run(), assumed non-None
- `neighbor.rib: Optional[RIB]` - Usually present after initialization

**Root cause:** Types are Optional for initialization, but code assumes they're present during normal operation.

**Proper fix:** Either:
1. Make types non-Optional and use late initialization patterns
2. Add guards everywhere: `if self.proto: self.proto.method()`
3. Use assertions: `assert self.proto is not None`

### 2. Flow Operations Multiple Inheritance (84 errors)

**File:** `bgp/message/update/nlri/flow.py`

**Problem:** Complex multiple inheritance hierarchy:
```python
class DestinationPort(NumericString, IOperation):
    # NumericString defines: value, operations
    # IOperation defines: value, operations (incompatible types)
```

**Error:**
```
Definition of "operations" in base class "IOperation" is incompatible
with definition in base class "NumericString"
```

**Fix required:** Redesign class hierarchy or use composition instead of multiple inheritance.

### 3. Lambda Type Inference (152 errors - misc)

**Problem:** Mypy can't infer lambda return types when using default arguments for closure.

**Pattern:**
```python
log.debug(lambda peer=peer: f'message {peer.name()}', 'source')
```

**Error:** `Cannot infer type of lambda [misc]`

**Fix:** Add explicit return type: `lambda peer=peer: f'...'` → Limited options without type annotations in lambda.

**Previous approach:** Used `# type: ignore[misc]` (now removed)

### 4. Returning Any (74 errors - no-any-return)

**Problem:** Functions declared to return specific types but return Any.

**Example:**
```python
def encode(self, value: Any) -> Tuple[int, bytes]:
    return some_any_value  # Error: Returning Any
```

**Fix:** Add proper type annotations to intermediate values.

### 5. Method Override Incompatibilities (54 errors)

**Problem:** Subclass methods incompatible with parent signatures.

**Examples:**
- `feedback()` in NLRI subclasses has different signature than base
- `unpack_attribute()` signatures vary across hierarchy
- `register()` methods have incompatible signatures

**Fix:** Align method signatures across inheritance hierarchy (may require API changes).

## Fixability Assessment

### Quick Wins (Estimated 200-300 hours)
1. Add Optional guards (216 errors) - Tedious but straightforward
2. Fix simple type annotations (74 no-any-return)
3. Add index guards (24 errors)

### Medium Effort (Estimated 300-500 hours)
4. Fix argument type mismatches (159 errors)
5. Fix assignment type mismatches (146 errors)
6. Lambda type inference (152 errors) - May need structural changes

### Hard/Architectural (Estimated 500+ hours)
7. Flow operations inheritance (84 errors) - Requires redesign
8. Method override issues (54 errors) - API breaking changes
9. attr-defined errors (167) - May indicate design issues

## Recommendations

### Short Term
1. **Accept current state:** 1,149 errors is the baseline
2. **Document known issues:** This file serves as documentation
3. **Focus on critical paths:** Add types to new code, don't fix old
4. **Use mypy for new modules:** Enable `disallow_untyped_defs` per-module as they're annotated

### Medium Term
1. **Fix high-impact files:** Start with reactor/peer.py (97 errors)
2. **Standardize Optional handling:** Decide on pattern (guards vs assertions vs non-Optional)
3. **Fix Flow hierarchy:** Redesign multiple inheritance

### Long Term
1. **Full type coverage:** Fix all 1,149 errors
2. **Enable strict mode:** `--strict` for entire codebase
3. **Type-safe architecture:** Redesign problematic patterns

## Progress Tracking

**Phase 1 (Complete):** Remove all `# type: ignore` comments - ✅ 698 removed
**Phase 2 (Current):** Baseline assessment - ✅ This document
**Phase 3 (Pending):** Systematic fixes by category
**Phase 4 (Pending):** Architectural refactoring

## Testing Status

All tests pass with current type errors (mypy errors don't affect runtime):
- ✅ Unit tests: 1,376 passed
- ✅ Linting: ruff format + ruff check pass
- ✅ Functional tests: (not run in this session)

## Configuration

Current mypy config (`pyproject.toml`):
```toml
[tool.mypy]
python_version = "3.9"
warn_unused_configs = true
warn_return_any = true
warn_redundant_casts = true
warn_unused_ignores = true

# Permissive settings (to be tightened)
disallow_untyped_defs = false
disallow_untyped_calls = false
disallow_incomplete_defs = false

follow_imports = "normal"
ignore_missing_imports = true
exclude = ["src/exabgp/vendoring/"]
```

## Next Steps

1. **Decide on strategy:** Full fix vs. partial vs. acceptance
2. **Prioritize fixes:** Which categories are most valuable?
3. **Resource allocation:** How much time to invest?
4. **Incremental approach:** Fix one file/category at a time
5. **Testing:** Ensure fixes don't break functionality

---

*Generated: 2025-11-15*
*Mypy errors: 1,149 / Files: 137 / Lines of code: ~50,000*
