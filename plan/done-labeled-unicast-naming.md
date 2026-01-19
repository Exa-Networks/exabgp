# Plan: labeled-unicast naming for IPv6

**Goal:** Use `labeled-unicast` as the preferred term for SAFI 4 in IPv6 contexts while maintaining `nlri-mpls` for IPv4 backward compatibility.

## Current State

### SAFI 4 Name Mapping
- `SAFI._names[4]` = `'nlri-mpls'` (single name, used everywhere)
- `SAFI.codes['nlri-mpls']` = `SAFI.nlri_mpls` (parsing lookup)
- `AFI.implemented_safi('ipv6')` returns `['unicast', 'mpls-vpn', ...]` (missing nlri-mpls for v6!)

### Usage Points
1. **JSON output** (`reactor/api/response/json.py:398`):
   - Uses `f'"{family[0]} {family[1]}"'` → `"ipv6 nlri-mpls"`
   - Calls `__str__` → `name()` → `_names[4]`

2. **Config parsing** (`configuration/neighbor/family.py`):
   - `convert['ipv6']['nlri-mpls']` = `(AFI.ipv6, SAFI.nlri_mpls)`
   - Schema choices: `['unicast', 'nlri-mpls', 'mpls-vpn', ...]`

3. **CLI/API commands** (`reactor/api/command/registry.py:74-75`):
   - `'ipv4': [..., 'nlri-mpls', ...]`
   - `'ipv6': [...]` (no nlri-mpls currently listed!)

4. **Capability negotiation/display**:
   - Uses `afi.name()` and `safi.name()` directly

---

## Design Decision

### Approach: AFI-aware SAFI naming

Add a method to get the display name for a SAFI in context of its AFI:

```python
# In Family class or as standalone function
def safi_display_name(afi: AFI, safi: SAFI) -> str:
    """Return display name for SAFI, using preferred terminology per AFI."""
    if safi == SAFI.nlri_mpls:
        if afi == AFI.ipv6:
            return 'labeled-unicast'
        return 'nlri-mpls'  # IPv4 backward compat
    return safi.name()
```

**Why this approach:**
- Minimal code changes
- Single point of truth for naming logic
- Easy to extend for other AFI-specific naming needs
- Doesn't break SAFI enum/constants

---

## Implementation Steps

### 1. Add alias support in configuration parser

**File:** `src/exabgp/configuration/neighbor/family.py`

Add `'labeled-unicast'` as alias in `convert['ipv6']`:
```python
'ipv6': {
    'unicast': (AFI.ipv6, SAFI.unicast),
    'nlri-mpls': (AFI.ipv6, SAFI.nlri_mpls),
    'labeled-unicast': (AFI.ipv6, SAFI.nlri_mpls),  # ADD
    ...
}
```

Also update schema choices to include both:
```python
choices=['unicast', 'nlri-mpls', 'labeled-unicast', ...]
```

### 2. Add display name method to Family class

**File:** `src/exabgp/protocol/family.py`

Add method to Family class:
```python
def safi_display_name(self) -> str:
    """Return display name for SAFI, using preferred terminology per AFI.

    IPv6 SAFI 4: 'labeled-unicast' (preferred)
    IPv4 SAFI 4: 'nlri-mpls' (backward compat)
    """
    if self.safi == SAFI.nlri_mpls and self.afi == AFI.ipv6:
        return 'labeled-unicast'
    return self.safi.name()
```

### 3. Update JSON output to use AFI-aware naming

**File:** `src/exabgp/reactor/api/response/json.py`

Change line 398 from:
```python
s = f'"{family[0]} {family[1]}": {{ '
```
to:
```python
# For SAFI display, use AFI-aware naming
from exabgp.protocol.family import Family
fam = Family(family[0], family[1])
s = f'"{family[0]} {fam.safi_display_name()}": {{ '
```

Similarly for line 412 (withdraws).

### 4. Update AFI.implemented_safi()

**File:** `src/exabgp/protocol/family.py:97-106`

Add `'labeled-unicast'` and `'nlri-mpls'` to IPv6 list:
```python
if afi == 'ipv6':
    return ['unicast', 'nlri-mpls', 'labeled-unicast', 'mpls-vpn', 'mcast-vpn', 'flow', 'flow-vpn', 'mup']
```

### 5. Update API command registry

**File:** `src/exabgp/reactor/api/command/registry.py`

Add both terms to ipv6:
```python
'ipv6': ['unicast', 'nlri-mpls', 'labeled-unicast', 'mpls-vpn', ...]
```

### 6. Update documentation/syntax strings

**Files:**
- `src/exabgp/configuration/neighbor/family.py` - syntax string
- `src/exabgp/configuration/neighbor/nexthop.py` - syntax string

---

## Testing Plan

1. **Unit tests:**
   - `Family.safi_display_name()` returns correct values
   - Config parser accepts both `nlri-mpls` and `labeled-unicast` for IPv6

2. **Functional tests:**
   - Existing encoding tests should still pass
   - JSON output for IPv6 labeled routes shows `labeled-unicast`
   - JSON output for IPv4 labeled routes shows `nlri-mpls`

3. **Round-trip:**
   - Config with `ipv6 labeled-unicast` parses correctly
   - JSON output matches expected format

---

## Alternatives Considered

### A. Add second entry to SAFI._names with AFI context
- **Rejected:** `_names` is keyed by SAFI value only, no AFI context

### B. Override `__str__` with AFI parameter
- **Rejected:** Would break existing usage patterns

### C. Create SAFIv6 subclass
- **Rejected:** Over-engineering for single case

---

## Risks

1. **API compatibility:** JSON output changes for IPv6 labeled routes
   - Mitigation: Document in changelog, could add env var to opt-out

2. **Config parsing ambiguity:** Both terms work for IPv6
   - Mitigation: Documentation shows preferred term

---

## Progress

- [x] Step 1: Config parser alias
- [x] Step 2: Family.safi_display_name() method
- [x] Step 3: JSON output update
- [x] Step 4: AFI.implemented_safi() update
- [x] Step 5: API registry update
- [x] Step 6: Documentation update
- [x] Testing: All 16 tests pass

## Failures

(none)

## Blockers

(none)

## Status

✅ **COMPLETE** - All changes implemented and tested
