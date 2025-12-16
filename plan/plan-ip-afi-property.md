# Plan: Refactor IP.afi to use Property Pattern

**Status:** ✅ Completed
**Created:** 2025-12-16
**Completed:** 2025-12-16

## Problem

The `afi` attribute in the IP class hierarchy has conflicting requirements:
- `IPv4`/`IPv6`: `afi` is a class constant (always `AFI.ipv4`/`AFI.ipv6`)
- `IPSelf`: `afi` is an instance variable (set in `__init__`, can be ipv4 or ipv6)
- `IP.NoNextHop`: `afi` is `AFI.undefined`

Current approach declares `afi: AFI` as instance variable in base class, but subclasses want ClassVar. Mypy doesn't allow overriding instance variable with ClassVar.

## Solution Implemented

**Chose Option 3:** Keep class attribute without ClassVar annotation (attribute shadowing)

This is the same pattern used by `Family` class in the codebase. The key changes:

### 1. IPFactory Protocol
Added a Protocol class for type-safe class-to-callable mapping:
```python
class IPFactory(Protocol):
    def __call__(self, packed: Buffer) -> 'IP': ...
```

### 2. Class Attribute Shadowing
Changed `IPv4` and `IPv6` from:
```python
afi: ClassVar[AFI] = AFI.ipv4  # mypy complains about ClassVar override
```
to:
```python
afi = AFI.ipv4  # Simple class attribute, shadows base class instance variable
```

### 3. Updated Registry Type
Changed `_known` from `dict[AFI, Type[IP]]` to `dict[AFI, IPFactory]` to properly type the callable pattern.

### 4. Base Class resolve() Compatibility
Updated `IPBase.resolve()` to have optional parameter:
```python
def resolve(self, ip: 'IP | None' = None) -> None:
```
This allows subclasses (IPSelf) to require the parameter while keeping base class compatible.

## Files Modified

- `src/exabgp/protocol/ip/__init__.py`

## Test Results

All tests pass:
- ruff-format ✓
- ruff-check ✓
- unit (3404 tests) ✓
- functional encoding (36 tests) ✓
- functional decoding (18 tests) ✓
- All 15 test suites ✓

---

**Last Updated:** 2025-12-16
