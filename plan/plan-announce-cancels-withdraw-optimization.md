# Plan: Announce Cancels Withdraw Optimization

**Status:** 📋 Planning
**Priority:** Low
**Depends on:** `plan-remove-action-from-route.md` completion

---

## Background

During the "Remove Action from Route" refactoring, the following optimization was removed from `outgoing.py`:

```python
# Remove any pending withdraw for this NLRI (announce cancels previous withdraw)
if route_family in self._pending_withdraws:
    self._pending_withdraws[route_family].pop(nlri_index, None)
```

This code was in `add_to_rib()` and would cancel a pending withdraw when an announce for the same NLRI arrived before `updates()` was called.

**Why it was removed:**
- The refactoring simplified the data flow: `add_to_rib()` handles announces only, `del_from_rib()` handles withdraws only
- Mixing logic between the two paths complicated testing during the large refactoring
- The old behavior (both withdraw and announce sent as separate messages) is correct, just suboptimal

---

## Goal

Re-implement the "announce cancels withdraw" optimization to reduce unnecessary BGP UPDATE messages.

**Scenario:**
1. `del_from_rib(route)` called → adds NLRI to `_pending_withdraws`
2. `add_to_rib(route)` called for same NLRI → should cancel the pending withdraw
3. `updates()` called → only sends the announce (not withdraw + announce)

**Benefits:**
- Fewer BGP UPDATE messages sent
- Reduced network traffic
- Cleaner state representation (no transient withdraw→announce)

---

## Implementation

### Phase 1: Add Optimization to `add_to_rib()`

**File:** `src/exabgp/rib/outgoing.py`

In `add_to_rib()`, after computing `route_family` and before adding to `_new_attr_af_nlri`:

```python
# Cancel any pending withdraw for this NLRI (announce supersedes withdraw)
nlri_index = route.nlri.index()
if route_family in self._pending_withdraws:
    self._pending_withdraws[route_family].pop(nlri_index, None)
```

### Phase 2: Add Unit Tests

**File:** `tests/unit/test_rib_outgoing.py`

Add tests for:
1. `test_announce_cancels_pending_withdraw()` - verify withdraw is removed when announce arrives
2. `test_announce_does_not_affect_other_nlri_withdraws()` - verify only matching NLRI is cancelled
3. `test_announce_after_withdraw_sends_only_announce()` - verify `updates()` output

### Phase 3: Add Functional Test (Optional)

Consider adding a test case to `qa/encoding/` that verifies:
- Withdraw followed by announce for same NLRI → only announce sent
- Withdraw for NLRI A, announce for NLRI B → both sent

---

## Considerations

### Edge Cases

1. **Same NLRI, different attributes:** Announce with different attributes should still cancel the withdraw (the new announce replaces)

2. **Multiple withdraws then announce:** Only one withdraw entry per NLRI in `_pending_withdraws`, so this is handled

3. **Announce then withdraw:** No issue - withdraw adds to `_pending_withdraws`, previous announce already in `_new_attr_af_nlri`

### Testing Strategy

Run full test suite before and after to ensure no behavioral changes for existing scenarios:
```bash
./qa/bin/test_everything
```

The optimization should be transparent to tests that don't specifically test withdraw→announce sequences.

---

## Progress

- [ ] Phase 1: Add optimization to `add_to_rib()`
- [ ] Phase 2: Add unit tests
- [ ] Phase 3: Add functional test (optional)
- [ ] Run `./qa/bin/test_everything`

---

## Resume Point

This plan should be executed after `plan-remove-action-from-route.md` is complete and merged.

To start:
1. Ensure all tests pass with current code
2. Implement Phase 1
3. Add unit tests (Phase 2)
4. Run full test suite

---

**Created:** 2025-12-15
**Related:** Removed during action-from-route refactoring (commit pending)
