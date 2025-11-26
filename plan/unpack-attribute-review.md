# Plan: Review unpack_attribute Signature Changes

**Status:** Pending Review
**Priority:** 🟡 Medium

## Overview

During mypy fixes, `unpack_attribute` methods were modified. These changes need review to ensure correctness.

## Changes Made

Several `unpack_attribute` methods had signatures changed:

1. **Added `cls` parameter** - Changed from `@staticmethod` to `@classmethod`
2. **Made `negotiated` optional** - Changed `negotiated: Negotiated` to `negotiated: Negotiated | None = None`

### Files Affected

- `src/exabgp/bgp/message/update/attribute/community/extended/bandwidth.py`
- `src/exabgp/bgp/message/update/attribute/community/extended/chso.py`
- `src/exabgp/bgp/message/update/attribute/community/extended/encapsulation.py`
- `src/exabgp/bgp/message/update/attribute/community/extended/l2info.py`
- `src/exabgp/bgp/message/update/attribute/community/extended/mac_mobility.py`
- `src/exabgp/bgp/message/update/attribute/community/extended/mup.py`

### Example Change

```python
# Before
@staticmethod
def unpack_attribute(data: bytes, negotiated: Negotiated) -> Bandwidth:

# After
@classmethod
def unpack_attribute(cls, data: bytes, negotiated: Negotiated | None = None) -> Bandwidth:
```

## Review Questions

1. **Is `@classmethod` correct?** - Do these methods need access to `cls`?
2. **Should `negotiated` be optional?** - The original API required it. Making it optional may hide bugs where callers forget to pass it.
3. **Are callers updated?** - If signature changed, callers may need updates.

## Recommendation

Review whether `negotiated` should remain required (not optional) to maintain API consistency with other `unpack_*` methods. The `negotiated` parameter is part of the stable BGP API pattern.

## Related

- `.claude/CODING_STANDARDS.md` - Documents stable BGP method APIs
- Commit `ca284e03` - Type annotation changes

---

**Created:** 2025-11-26
