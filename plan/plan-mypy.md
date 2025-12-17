# MyPy Error Reduction Plan

**Status:** 📋 Planning (ultrathink analysis)
**Created:** 2025-12-17
**Last Updated:** 2025-12-17
**Starting Errors:** 1,149 (baseline)
**Current Errors:** 186 (84% reduction achieved)
**Target:** <50 errors

---

## Executive Summary

Current position: **186 errors remaining** after 84% reduction from baseline.

| Category | Count | Difficulty | Strategy |
|----------|-------|------------|----------|
| `[arg-type]` | 44 | Medium | Mixed: pattern fixes + architectural |
| `[no-untyped-def]` | 30 | Easy | Batch annotate config parsers |
| `[attr-defined]` | 29 | Medium | Registry protocols + missing methods |
| `[misc]` | 19 | Hard | ClassVar patterns, property overrides |
| `[no-untyped-call]` | 17 | Easy | Annotate called functions |
| `[assignment]` | 11 | Medium | Type hierarchy fixes |
| `[override]` | 9 | Hard | Signature unification |
| `[type-var]` | 6 | Medium | Buffer/TypeVar fixes |
| Others | 21 | Varies | Case-by-case |

---

## Phase 1: Easy Wins (~60 errors, ~3 hours)

### 1.1 Function Annotations (30 errors) ⏸️ Pending

Add type annotations to configuration parsers. These are mechanical fixes.

**Files (by error count):**
| File | Errors | Functions |
|------|--------|-----------|
| `configuration/l2vpn/parser.py` | 5 | Parser functions |
| `configuration/process/__init__.py` | 5 | ParseProcess methods |
| `configuration/operational/__init__.py` | 4 | ParseOperational methods |
| `configuration/l2vpn/vpls.py` | 4 | ParseVPLS methods |
| `configuration/l2vpn/__init__.py` | 4 | ParseL2VPN methods |
| `configuration/neighbor/family.py` | 1 | Method annotation |
| `reactor/api/dispatch/v4.py` | 2 | Handler functions |
| `cli/schema_bridge.py` | 1 | `__init__` return type |
| `cli/completer.py` | 1 | Function annotation |
| `bgp/message/update/nlri/mvpn/nlri.py` | 1 | unpack method |
| `bgp/message/update/nlri/mup/nlri.py` | 1 | unpack method |
| `bgp/message/update/nlri/evpn/nlri.py` | 1 | unpack method |

**Pattern:** Add return types `-> bool:`, `-> None:`, parameter types `(self, scope: Scope) -> bool:`

### 1.2 Fix no-untyped-call (17 errors) ⏸️ Pending

These are caused by calling untyped functions. Fix by annotating the called functions.

**Cascade effect:** Fixing 1.1 will automatically fix ~9 of these:
- `ParseProcess`, `ParseL2VPN`, `ParseVPLS`, `ParseOperational` calls in `configuration/configuration.py`
- `clear`, `add_api` calls

**Remaining (3 errors) - objgraph library:**
- `application/server.py` calls `show_most_common_types`, `by_type`, `show_backrefs`
- **Fix:** Add stub or type: ignore for vendored library

**Remaining (5 errors) - cli completers:**
- `cli/schema_bridge.py` calls `ValueTypeCompletionEngine`
- `cli/completer.py` calls `FrequencyProvider`, `ValueTypeCompletionEngine`
- **Fix:** Add annotations to prompt_toolkit integration classes

---

## Phase 2: Pattern-Based Fixes (~50 errors, ~4 hours)

### 2.1 Registry Protocol Pattern (15 errors) ⏸️ Pending

Apply the decorator-sets-ClassVar pattern already used for NLRI registries.

**Files with "type[X]" has no attribute errors:**
| File | Attribute | Pattern |
|------|-----------|---------|
| `nlri/evpn/nlri.py:158` | `unpack_evpn` | Registry method |
| `nlri/bgpls/nlri.py:184,189` | `unpack_bgpls_nlri` | Registry method |
| `nlri/flow.py:901,910` | `ID`, `decoder` | IComponent registry |
| `attribute/bgpls/link/srv6*.py` | `TLV`, `unpack_bgpls`, `registered_subsubtlvs` | TLV registries |

**Solution:** Add ClassVar declarations to base classes, use Protocol pattern:
```python
class EVPN(NLRI):
    unpack_evpn: ClassVar[Callable[[Buffer, Negotiated], EVPN]]
```

### 2.2 Missing Method - answer_async (6 errors) ⏸️ Pending

**Issue:** `reactor/api/command/route.py` calls `processes.answer_async()` but only these exist:
- `_answer_async()` (private)
- `answer_done_async()`
- `answer_error_async()`

**Fix:** Either:
1. Add public `answer_async()` method wrapper
2. Change calls to use `_answer_async()` (if appropriate)
3. Use `answer_done_async()` or `answer_error_async()` as appropriate

**Lines:** 158, 235, 237, 293, 331, 333

### 2.3 Attribute Access on Base Types (8 errors) ⏸️ Pending

**Pattern:** Base `Attribute` class accessed where subclass expected
| File | Issue |
|------|-------|
| `collection.py:216` | `Attribute` has no `pack_ip` |
| `collection.py:607` | `Attribute` has no `iter_routed` |
| `mprnlri.py:140` | `Attribute` has no `pack_ip` |
| `__init__.py:198,200` | `Attribute` has no `afi`, `safi` |
| `neighbor.py:366,367` | `Attribute` has no `SELF`, `resolved`, `resolve` |

**Fix:** Cast to specific type or use Protocol:
```python
from typing import Protocol, cast

class HasPackIP(Protocol):
    def pack_ip(self, negotiated: Negotiated) -> bytes: ...

nexthop = cast(HasPackIP, self[Attribute.CODE.NEXT_HOP])
```

### 2.4 Buffer/TypeVar in split() (3 errors) ⏸️ Pending

**Issue:** `split()` TypeVar is `T = TypeVar('T', str, bytes)` but called with `bytes | memoryview`

**Files:**
- `bgpls/prefix/igptags.py:37`
- `bgpls/prefix/igpextags.py:34`
- `bgpls/link/srlg.py:39`

**Fix:** Change split() to accept Buffer:
```python
T = TypeVar('T', str, Buffer)  # or use overloads
```

---

## Phase 3: Type Hierarchy Fixes (~35 errors, ~4 hours)

### 3.1 arg-type: None instead of Negotiated (8 errors) ⏸️ Pending

**Pattern:** `pack_attribute(..., None)` where `Negotiated` required

**Files:**
- `community/large/communities.py:87,100`
- `community/initial/communities.py:78,90`
- `community/extended/rt_record.py:26`
- `community/extended/communities.py:118,129,199,207`

**Fix options:**
1. Create `NullNegotiated` sentinel object
2. Make `negotiated: Negotiated | None` with runtime guard
3. Pass actual Negotiated in these contexts

### 3.2 arg-type: Socket | None (4 errors) ⏸️ Pending

**File:** `reactor/network/outgoing.py:70,102,171,173`

**Pattern:** `connect(socket | None)` where `socket` required

**Fix:** Add assert/guard before calls:
```python
if self.io is None:
    raise ...
# or
assert self.io is not None
```

### 3.3 arg-type: Type hierarchy mismatches (10 errors) ⏸️ Pending

| File | Issue |
|------|-------|
| `collection.py:594` | `Attribute | IP` expected `IP` |
| `collection.py:603` | `Attribute` expected `Iterable[NLRI]` |
| `nlri/ipvpn.py:525` | `Action` expected `PathInfo` |
| `nlri/inet.py:148` | `Action` expected `PathInfo` |
| `configuration/static/parser.py:330,332` | `IP` expected `ClusterID` |
| `configuration/static/route.py:450` | kwargs mismatch |
| `configuration/static/route.py:500` | `Attribute` expected `int` |
| `configuration/static/mpls.py:181,189,191` | Srv6 TLV type hierarchy |

**Fix:** These require careful analysis of actual data types being passed.

### 3.4 assignment: Section dict type (5 errors) ⏸️ Pending

**Pattern:** `dict[str, object]` assigned where `dict[str | tuple[...], Any]` expected

**Files:**
- `configuration/operational/__init__.py:99`
- `configuration/neighbor/nexthop.py:72`
- `configuration/neighbor/api.py:109,110`
- `configuration/static/__init__.py:37`

**Fix:** Use common dict type `dict[str | tuple[Any, ...], Any]` or restructure Section base class

---

## Phase 4: Override Issues (~20 errors, ~5 hours)

### 4.1 Property Override Conflicts (8 errors) ⏸️ Pending

**Pattern:** Read-only property overrides read-write property

| File | Property |
|------|----------|
| `nlri/rtc.py:52,56` | Properties |
| `nlri/label.py:125,177` | Properties |
| `nlri/ipvpn.py:152,186` | Properties |
| `nlri/mvpn/nlri.py:179` | Property |
| `nlri/mup/nlri.py:184,189` | Properties |
| `nlri/evpn/nlri.py:186` | Property |
| `attribute/bgpls/linkstate.py:269` | Property |

**Fix:** Remove setters from base class (INET) - user approved approach from previous session

### 4.2 Method Signature Incompatibilities (5 errors) ⏸️ Pending

| File | Method | Issue |
|------|--------|-------|
| `attribute/generic.py:117` | `unpack_attribute` | Signature incompatible |
| `nlri/ipvpn.py:443` | `unpack_nlri` | Return type incompatible |
| `nlri/inet.py:373` | `json` | Signature incompatible |
| `message/unknown.py:38` | `unpack_message` | Signature incompatible |

**Fix:** Align signatures or use `@overload`

### 4.3 ClassVar Assignment via Instance (4 errors) ⏸️ Pending

**Pattern:** `Cannot assign to class variable "ID" via instance`

| File | ClassVar |
|------|----------|
| `attribute/generic.py:49,50` | `ID`, `FLAG` |
| `message/unknown.py:27,28` | `ID`, `TYPE` |

**Fix:** Use decorator pattern to set ClassVars at class definition time, not instance init

---

## Phase 5: Misc and Edge Cases (~21 errors, ~3 hours)

### 5.1 Flow Parser yield types (6 errors) ⏸️ Pending

**File:** `configuration/flow/parser.py:135,139,144,156,160,165`

**Pattern:** Yield `IPrefix4`/`IPrefix6` where `Flow4Source | Flow6Source` expected

**Fix:** Update generator return type or restructure flow type hierarchy

### 5.2 Route __index slot issue (2 errors) ⏸️ Pending

**File:** `rib/route.py:56,109`

**Pattern:** `Trying to assign name "__index" that is not in "__slots__"`

**Fix:** Add `"__index"` to `__slots__` or rename attribute

### 5.3 Collection type annotation (1 error) ⏸️ Pending

**File:** `nlri/collection.py:79`

**Pattern:** `Type cannot be declared in assignment to non-self attribute`

**Fix:** Move type declaration to class level or use different pattern

### 5.4 Validator attribute (1 error) ⏸️ Pending

**File:** `configuration/validator.py:1380`

**Pattern:** `Validator[Any]` has no attribute `validate_with_afi`

**Fix:** Add method to Validator or use Protocol

### 5.5 TypeVar constraints (3 errors) ⏸️ Pending

**Files:**
- `attribute/aspath.py:255` - SegmentType constraint
- `attribute/sr/srv6/sidinformation.py:45` - SubTlvType constraint
- `attribute/sr/srv6/sidstructure.py:36` - SubSubTlvType constraint

**Fix:** Expand TypeVar bounds or use Union

### 5.6 Abstract class issues (2 errors) ⏸️ Pending

Check specific errors and implement required abstract methods

### 5.7 Comparison overlap (2 errors) ⏸️ Pending

**Files:**
- `reactor/api/command/peer.py:320`
- `configuration/neighbor/__init__.py:547`

**Pattern:** bytes vs str key comparison

**Fix:** Normalize to single type

---

## Implementation Order (Recommended)

| Priority | Phase | Errors | Hours | Dependencies |
|----------|-------|--------|-------|--------------|
| 1 | 1.1 Function annotations | 30 | 1.5 | None |
| 2 | 1.2 no-untyped-call | 17→8 | 0.5 | After 1.1 |
| 3 | 2.4 Buffer TypeVar | 3 | 0.5 | None |
| 4 | 2.2 answer_async | 6 | 0.5 | None |
| 5 | 3.2 Socket guards | 4 | 0.5 | None |
| 6 | 4.3 ClassVar assignment | 4 | 1 | None |
| 7 | 2.1 Registry protocols | 15 | 2 | Research |
| 8 | 2.3 Attribute protocols | 8 | 1.5 | After 2.1 |
| 9 | 4.1 Property overrides | 8 | 2 | User decision |
| 10 | 3.1 Negotiated None | 8 | 1 | Design decision |
| 11 | 3.3 Type hierarchy | 10 | 2 | Analysis |
| 12 | 4.2 Method signatures | 5 | 2 | After 4.1 |
| 13 | 3.4 Section dict | 5 | 1 | Analysis |
| 14 | 5.x Misc | ~12 | 2 | Varies |

**Estimated total:** ~18 hours to reach <50 errors

---

## Quick Wins Today

If starting now, tackle in this order:

1. **Phase 1.1** - Annotate 30 functions (purely mechanical)
2. **Phase 2.4** - Fix `split()` TypeVar (3 errors, 10 min)
3. **Phase 2.2** - Add `answer_async()` method (6 errors, 15 min)
4. **Phase 3.2** - Add socket guards (4 errors, 15 min)

This batch alone: **~43 errors fixed** in ~2 hours.

---

## Blockers and Decisions Needed

| Decision | Options | Impact |
|----------|---------|--------|
| answer_async implementation | Add wrapper vs change callers | 6 errors |
| Negotiated None pattern | Sentinel vs Optional | 8 errors |
| Property override approach | Remove setters vs @property.setter | 8 errors |
| Section dict type | Change base vs change subclasses | 5 errors |

---

## Testing Requirements

After each phase:
```bash
uv run mypy src/exabgp  # Verify error reduction
uv run ruff format src && uv run ruff check src
env exabgp_log_enable=false uv run pytest ./tests/unit/ -x -q
./qa/bin/functional encoding
```

Before declaring complete:
```bash
./qa/bin/test_everything
```

---

## Success Criteria

- [ ] Error count < 100 (Phase 1-2)
- [ ] Error count < 50 (Phase 3-4)
- [ ] All tests pass
- [ ] No new `# type: ignore` added
- [ ] No mypy config changes

---

## Progress Log

### 2025-12-17 - Ultrathink Analysis

- Analyzed 186 errors across 63 files
- Categorized by error type and difficulty
- Identified quick wins (~43 errors in 2 hours)
- Created prioritized implementation plan
- Estimated ~18 hours to reach <50 errors

### 2025-12-17 - Phase 1.1 Complete

- **Start:** 186 errors
- **End:** 141 errors
- **Fixed:** 45 errors (24% reduction)

**Files annotated:**
- `configuration/l2vpn/parser.py` - 5 functions
- `configuration/process/__init__.py` - 5 functions
- `configuration/operational/__init__.py` - 4 functions
- `configuration/l2vpn/vpls.py` - 4 functions
- `configuration/l2vpn/__init__.py` - 4 functions
- `bgp/message/update/nlri/mvpn/nlri.py` - register_mvpn return type
- `bgp/message/update/nlri/mup/nlri.py` - register_mup_route return type
- `bgp/message/update/nlri/evpn/nlri.py` - register_evpn_route return type
- `configuration/neighbor/family.py` - all() method
- `reactor/api/dispatch/v4.py` - dispatch functions with ModuleType
- `cli/schema_bridge.py` - __init__ return type
- `cli/completer.py` - FrequencyProvider class, imports
- `cli/fuzzy.py` - FrequencyLookup Protocol, broader types

**No type: ignore comments added.**

### 2025-12-17 - Phase 2 Complete

- **Start:** 141 errors
- **End:** 128 errors
- **Fixed:** 13 errors

**Changes:**
- `util/__init__.py` - split() with overloads for str and Buffer types
- `reactor/api/processes.py` - Added public `answer_async()` method
- `reactor/network/outgoing.py` - Added socket asserts for type narrowing

### 2025-12-17 - Phase 2b (Registry fixes)

- **Start:** 128 errors
- **End:** 123 errors
- **Fixed:** 5 errors

**Changes:**
- `vendoring/objgraph.py` - Added type annotations for show_most_common_types, by_type, show_backrefs
- `application/server.py` - Fixed show_most_common_types usage (returns None, prints to stdout)
- `nlri/flow.py` - Added ClassVar declarations for ID and decoder to IComponent base class
- `nlri/evpn/nlri.py` - Renamed unpack_evpn_route → unpack_evpn to match subclass implementations

### 2025-12-17 - Phase 2c (More Registry fixes)

- **Start:** 123 errors
- **End:** 120 errors
- **Fixed:** 3 errors

**Changes:**
- `nlri/bgpls/nlri.py` - Added unpack_bgpls_nlri classmethod stub to BGPLS base class
- `attribute/bgpls/link/srv6capabilities.py` - Added HasTLV Protocol for TLV class attribute typing

### 2025-12-17 - Phase 2d (SRv6 Protocol fixes)

- **Start:** 120 errors
- **End:** 120 errors (swapped TLV errors for ClassVar override errors)

**Changes:**
- `attribute/bgpls/link/srv6endx.py` - Added SubSubTLV Protocol combining TLV + unpack_bgpls
- `attribute/bgpls/link/srv6lanendx.py` - Added SubSubTLV Protocol and ClassVar to Srv6 base

**Note:** Fixed TLV attr-defined errors but introduced ClassVar override errors in subclasses.
These require restructuring the class hierarchy or using different patterns.

**Total reduction:** 186 → 120 errors (35% reduction)

---

**Last Updated:** 2025-12-17
