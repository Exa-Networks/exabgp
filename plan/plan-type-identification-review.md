# Plan: Type Identification Codebase Review

**Status:** Not Started
**Created:** 2025-12-08
**Priority:** Low (code quality improvement, no functional issues)

---

## Goal

Review the codebase to ensure compliance with the new coding standard:
**Use ClassVar flags for type/capability identification, NOT hasattr() or isinstance()**.

This standard was added to `.claude/CODING_STANDARDS.md` after discovering that `hasattr()` checks break during refactoring (the `_labels_packed` → `_has_labels` bug).

---

## Scope

### Files to Review

1. **NLRI-related code** (highest priority):
   - `src/exabgp/bgp/message/update/nlri/*.py`
   - `src/exabgp/configuration/static/*.py`
   - `src/exabgp/configuration/announce/*.py`

2. **Message handling**:
   - `src/exabgp/bgp/message/update/*.py`
   - `src/exabgp/reactor/peer/*.py`

3. **RIB operations**:
   - `src/exabgp/rib/*.py`

### Patterns to Find

```bash
# Find hasattr checks (potential violations)
rg "hasattr\(" src/exabgp/

# Find isinstance checks for NLRI types
rg "isinstance\(.*(?:INET|Label|IPVPN|Flow|VPLS|EVPN|MUP|BGPLS)" src/exabgp/

# Find attribute existence checks
rg "_packed|_labels|_rd" src/exabgp/ | grep -E "hasattr|getattr"
```

---

## Review Checklist

For each `hasattr()` or `isinstance()` check found:

1. [ ] Is this checking a type capability? (e.g., "does this NLRI have labels?")
2. [ ] Is there an existing ClassVar or method that can be used instead?
3. [ ] If not, should we add a ClassVar flag to the class?
4. [ ] Document the change needed

---

## Known Issues to Fix

### Already Fixed

1. **`_normalize_nlri_type()` in route.py** - ✅ Fixed
   - Was: `hasattr(ipvpn_nlri, '_labels_packed') and ipvpn_nlri._labels_packed`
   - Now: `isinstance(nlri, Label) and nlri._has_labels`
   - Note: This still uses isinstance, but it's checking the class type (which is stable) rather than attribute existence (which changes during refactoring)

### To Review

1. **`route.py:split()`** - Uses `isinstance(nlri, Label)` and `isinstance(nlri, IPVPN)` - OK as-is per updated standard
2. **SAFI `has_label()` / `has_rd()` methods** - These check SAFI capability, not actual data

---

## Proposed Changes

### Option A: Keep isinstance for class type checks (current approach)

Use `isinstance()` to check class type (stable), then access class-specific attributes.

```python
if isinstance(nlri, Label):
    labels = nlri.labels  # Safe: Label has labels property
```

**Pros:** Minimal changes, works now
**Cons:** isinstance checks can be scattered

### Option B: Add ClassVar capability flags

Add `can_have_labels: ClassVar[bool]` and `can_have_rd: ClassVar[bool]` to classes.

```python
class INET:
    can_have_labels: ClassVar[bool] = False
    can_have_rd: ClassVar[bool] = False

class Label(INET):
    can_have_labels: ClassVar[bool] = True

class IPVPN(Label):
    can_have_rd: ClassVar[bool] = True
```

**Pros:** Self-documenting, no isinstance needed
**Cons:** More code changes, two concepts (can have vs does have)

### Recommendation

**Option A** is sufficient for now. The key insight is:
- `isinstance()` checks class TYPE (stable across refactoring)
- `hasattr()` checks attribute NAMES (break when attributes are renamed)

The coding standard should clarify: isinstance is acceptable for checking class type, but not as a substitute for proper class design.

---

## Implementation Order

1. Search and catalog all `hasattr()` uses
2. For each, determine if it's checking type capability
3. Replace with isinstance or ClassVar as appropriate
4. Run tests after each change

---

## Resume Point

**Session:** Not started
**Next Action:** Run search commands to catalog violations

---

## Verification

```bash
# All tests must pass
./qa/bin/test_everything

# No hasattr on private attributes
rg "hasattr\(.*_" src/exabgp/ --count
# Should return 0 or only legitimate uses
```
