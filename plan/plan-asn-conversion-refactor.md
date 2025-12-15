# Plan: ASN Conversion Refactoring

## Overview

ASN handling in AS_PATH and AGGREGATOR attributes has duplicated conversion logic that could be consolidated.

## Current State

### aggregator.py:134
```python
# TODO: REFACTOR - merge with aspath.py ASN4 conversion
```

### aspath.py:267
```python
# TODO: REFACTOR - similar ASN4 handling exists in aggregator.py
```

Both files handle:
- 2-byte to 4-byte ASN conversion
- AS_TRANS (23456) handling for 4-byte ASN capability
- ASN packing/unpacking based on negotiated capabilities

## Proposed Refactoring

1. Create shared ASN utility module or extend existing `bgp/message/open/asn.py`
2. Add methods:
   - `pack_asn(asn, negotiated)` - pack ASN based on capabilities
   - `unpack_asn(data, negotiated)` - unpack ASN based on capabilities
   - `convert_as_trans(asn_list, as4_path)` - merge AS_TRANS with AS4_PATH

## Steps

1. [ ] Audit current ASN handling in aggregator.py and aspath.py
2. [ ] Identify common patterns
3. [ ] Design shared interface
4. [ ] Implement shared utilities
5. [ ] Refactor aggregator.py to use shared code
6. [ ] Refactor aspath.py to use shared code
7. [ ] Add/update unit tests
8. [ ] Verify functional tests pass

## Files Affected

- `bgp/message/open/asn.py` - extend with utilities
- `bgp/message/update/attribute/aggregator.py` - refactor
- `bgp/message/update/attribute/aspath.py` - refactor

## Priority

Low - Current code works correctly, this is code quality improvement.

## References

- RFC 6793: BGP Support for Four-Octet Autonomous System (AS) Number Space
- RFC 4893: BGP Support for Four-octet AS Number Space (obsoleted by 6793)
