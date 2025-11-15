# API Design Principles

## Critical Rules - ALWAYS FOLLOW

### Rule 1: Production Code Drives API Design - NEVER Test Code

**THE MOST IMPORTANT RULE:**

**NEVER let test code convenience dictate production API design.**

- Production APIs must be designed for correctness and clarity in real-world usage
- If tests need special handling, create test utilities - DO NOT compromise the API
- If a parameter should be mandatory in production, make it mandatory - tests must adapt
- Test code difficulty is a signal to create better test utilities, NOT to weaken the API

**Example - WRONG:**
```python
# Making parameter optional because tests don't have the value
def pack_attribute(self, negotiated: Optional[Negotiated] = None) -> bytes:
    ...

# Test taking the easy way out
packed = attr.pack_attribute()  # WRONG - using default None
```

**Example - CORRECT:**
```python
# Parameter is mandatory because production code always has it
def pack_attribute(self, negotiated: Negotiated) -> bytes:
    ...

# Test creates proper object using utility
negotiated = create_negotiated()
packed = attr.pack_attribute(negotiated)  # CORRECT - explicit object
```

### Rule 2: Always Pass Negotiated Objects - Never None

When a function requires `negotiated`, always pass a proper `Negotiated` object:

- Use `create_negotiated()` utility in tests
- Thread the parameter through callers if needed
- If caller doesn't have it, update caller's signature to accept and pass it through
- NEVER pass `negotiated=None` as a shortcut

**Example - Caller doesn't have negotiated:**
```python
# WRONG - passing None
def setCache(cls):
    packed = obj.pack_attribute(negotiated=None)

# CORRECT - update signature to accept and use negotiated
def setCache(cls, negotiated: Negotiated):
    packed = obj.pack_attribute(negotiated)
```

### Rule 3: Make Required Parameters Mandatory

If a parameter is logically required for correct operation:
- Make it mandatory in the signature (no default value)
- Force callers to explicitly provide it
- This prevents bugs from forgotten parameters

**Example:**
```python
# WRONG - optional with default
def pack_attribute(self, negotiated: Optional[Negotiated] = None) -> bytes:

# CORRECT - mandatory
def pack_attribute(self, negotiated: Negotiated) -> bytes:
```

### Rule 4: API Clarity Over Implementation Convenience

- Explicit is better than implicit
- Type safety and clarity trump ease of implementation
- If the API is awkward to use, that's feedback to improve the design, not lower the standards
- Think about the caller's mental model and correctness

## Test Utilities

When production APIs require certain objects, create test utilities:

- `create_negotiated()` - Creates a minimal valid Negotiated object for tests
- `create_neighbor()` - Creates test neighbor objects
- Add more utilities as needed - NEVER weaken the API instead

## Summary

1. **Production code drives API design** - test code adapts
2. **Always pass proper objects** - never None shortcuts
3. **Make required parameters mandatory** - no optional defaults for required data
4. **Clarity over convenience** - explicit APIs prevent bugs

These principles ensure robust, maintainable code with clear contracts and type safety.
