# Plan: FlowSpec Improvements

## Overview

FlowSpec implementation has two tech debt items in `bgp/message/update/nlri/flow.py`.

## Items

### 1. AFI Reset Behavior (line 871)

```python
# TODO: verify if this is correct - why reset the afi of the NLRI object after initialisation?
if rule.NAME.endswith('ipv6'):
    self.afi = AFI.ipv6
```

**Issue:** When adding a rule, the AFI is changed based on rule name suffix.

**Questions:**
- Is this the intended behavior?
- Should AFI be set at construction and immutable?
- What happens with mixed IPv4/IPv6 rules?

**Action:** Document why this exists or refactor to set AFI at construction.

### 2. EOL Bits Refactoring (line 894)

```python
# TODO: REFACTOR - This method modifies rule operations in-place (EOL bits)
# and does computation in addition to serialization.
```

**Issue:** `_pack_from_rules()` has side effects:
- Modifies rule operations in-place (clears/sets EOL bits)
- Mixes preparation with serialization
- Not idempotent

**Proposed Refactoring:**
1. Create `FlowRuleCollection` class (like `AttributeCollection`)
2. Move EOL bit handling to collection's `prepare()` method
3. Make `_pack_from_rules()` pure serialization
4. Follow the Collection pattern used elsewhere

## Steps

1. [ ] Document AFI reset behavior (add code comment explaining why)
2. [ ] Design FlowRuleCollection class
3. [ ] Implement prepare() for EOL bit handling
4. [ ] Refactor _pack_from_rules() to pure serialization
5. [ ] Update tests

## Priority

Low - Current implementation works correctly.

## References

- RFC 8955: Dissemination of Flow Specification Rules
- RFC 8956: Dissemination of Flow Specification Rules for IPv6
- `.claude/exabgp/COLLECTION_PATTERN.md` - Collection pattern reference
