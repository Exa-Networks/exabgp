# Plan: Unify unpack_attribute Signatures

**Status:** 📋 Planning
**Created:** 2025-12-17
**Last Updated:** 2025-12-17

## Problem

The base `Attribute.unpack_attribute()` method was added with signature:
```python
def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> Attribute
```

But several subclasses have incompatible signatures:

### 1. Return `| None` instead of `Attribute`
These methods return `None` in some error cases:

- `aigp.py:128` - `-> AIGP | None` (returns None on line 131)
- `aspath.py:313` - `-> ASPath | None` (returns None on line 315)
- `aspath.py:368` - `-> AS4Path | None` (returns None on line 370)

### 2. Different Parameters
- `generic.py:117` - `unpack_attribute(cls, code: int, flag: int, data: Buffer)` - completely different signature

## Analysis Needed

For each `return None` case, determine:
1. **Why** does it return None? (malformed data? optional attribute?)
2. **What** does the caller do with None? (skip? error?)
3. **Should** it raise an exception instead? (fail-fast)

## Proposed Solutions

### Option A: Raise Exceptions Instead of None
Change the subclasses to raise exceptions (e.g., `Notify` or `ValueError`) instead of returning `None`. This makes errors explicit and keeps the type signature clean.

**Pros:** Clean types, fail-fast behavior, consistent with other unpack methods
**Cons:** May change error handling behavior

### Option B: Base Returns `Attribute | None`
Change base to `-> Attribute | None` and update all callers to handle None.

**Pros:** Matches current behavior
**Cons:** Spreads None-checking to all call sites

### Option C: Keep GenericAttribute Separate
`GenericAttribute.unpack_attribute` has a fundamentally different purpose (factory for unknown attributes). Consider:
- Rename to `unpack_generic_attribute`
- Or use a different pattern (not override)

## Files to Modify

1. `src/exabgp/bgp/message/update/attribute/aigp.py`
2. `src/exabgp/bgp/message/update/attribute/aspath.py`
3. `src/exabgp/bgp/message/update/attribute/generic.py`
4. `src/exabgp/bgp/message/update/attribute/attribute.py` (base class)

## Current Mypy Errors (from this issue)

```
src/exabgp/bgp/message/update/attribute/generic.py:117: error: Signature of "unpack_attribute" incompatible with supertype
src/exabgp/bgp/message/update/attribute/aigp.py:128: error: Return type "AIGP | None" incompatible with "Attribute"
src/exabgp/bgp/message/update/attribute/aspath.py:313: error: Return type "ASPath | None" incompatible with "Attribute"
src/exabgp/bgp/message/update/attribute/aspath.py:368: error: Return type "AS4Path | None" incompatible with "Attribute"
```

## Tasks

- [ ] Investigate aigp.py return None case
- [ ] Investigate aspath.py ASPath return None case
- [ ] Investigate aspath.py AS4Path return None case
- [ ] Decide on Option A vs B
- [ ] Investigate generic.py different signature
- [ ] Implement chosen solution
- [ ] Run tests to verify no regressions

## Notes

- This is blocking mypy from passing cleanly
- The `Message.unpack_message` base method was added successfully (same pattern)
- GenericAttribute is a special case - used for unknown/unrecognized attributes
