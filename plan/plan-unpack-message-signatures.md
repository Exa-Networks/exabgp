# Plan: Fix unpack_message Return Signatures

**Status:** 📋 Planning
**Created:** 2025-12-17
**Last Updated:** 2025-12-17

## Problem

The base `Message.unpack_message()` was added with signature:
```python
def unpack_message(cls, data: Buffer, negotiated: Negotiated) -> Message
```

But `operational.py` has incompatible return type:

```
src/exabgp/bgp/message/operational.py:137: error: Return type "Operational | None" of "unpack_message" incompatible with return type "Message"
```

## Related Issues in operational.py

The file also has:
- Line 132: Signature of "register" incompatible with supertype
- Lines 146, 152, 159: "Too many arguments for Operational" / "None not callable"

These suggest deeper type issues in the Operational message implementation.

## Analysis Needed

1. Why does `Operational.unpack_message` return `None`?
2. What happens when caller receives `None`?
3. Should it raise an exception instead?

## Related Plan

See also: `plan-unpack-attribute-signatures.md` - same pattern for Attribute class

## Tasks

- [ ] Investigate operational.py return None case
- [ ] Investigate operational.py register signature issue
- [ ] Investigate "Too many arguments" errors
- [ ] Decide if exceptions should replace None returns
- [ ] Implement fix
- [ ] Run tests
