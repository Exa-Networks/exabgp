# Plan: Extended Community Type Support

## Overview

RFC 4360 defines Extended Communities with various type codes. Current implementation is incomplete.

## Missing Types

| Type | Subtype | Name | RFC |
|------|---------|------|-----|
| 0x01 | 0x02 | OriginASN4Number (2,2) | RFC 5668 |
| 0x02 | 0x03 | RouteTargetASN4Number (2,3) | RFC 5668 |

## Current Implementation

File: `configuration/static/parser.py`

```python
_HEADER = {
    'target':   bytes([0x00, 0x02]),  # Route Target (2-byte ASN)
    'target4':  bytes([0x02, 0x02]),  # Route Target (4-byte ASN)
    'origin':   bytes([0x00, 0x03]),  # Route Origin (2-byte ASN)
    'origin4':  bytes([0x01, 0x03]),  # Route Origin (4-byte ASN) - MISSING: should be 0x02, 0x02?
    # TODO: RouteTargetASN4Number (2,3) - missing
    ...
}
```

## Steps

1. [ ] Review RFC 5668 for correct type/subtype codes
2. [ ] Add missing extended community types to `_HEADER`
3. [ ] Add corresponding `_ENCODE` entries
4. [ ] Add parsing support in `extendedcommunity()` function
5. [ ] Add unit tests
6. [ ] Add configuration examples

## Validation Improvement

File: `data/check.py:282`

The `extendedcommunity()` validation function is incomplete per RFC 4360:
- Only handles `origin` and `target` keywords
- Should support additional types (flowspec redirect, bandwidth, etc.)

## Priority

Low - Current types cover most use cases.

## References

- RFC 4360: BGP Extended Communities Attribute
- RFC 5668: 4-Octet AS Specific BGP Extended Community
