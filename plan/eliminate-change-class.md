# Plan: Eliminate Change Class - Index by Attributes

**Status:** 🚧 In Progress (Phase 1-4 complete)
**Created:** 2025-12-05
**Goal:** Remove Change class, remove action storage - RIB indexes by Attributes, stores NLRIs directly

---

## Progress (2025-12-05)

### Completed Phases

**Phase 1: Update class with announces/withdraws ✅**
- Added dual-mode `__init__`: legacy `(nlris, attrs)` and new `(announces, withdraws, attrs)`
- Added `.announces` and `.withdraws` properties
- Full backward compatibility with `_legacy_mode` flag

**Phase 2: Update unpack_message() ✅**
- Now creates `Update(announces, withdraws, attributes)` using new signature
- Separates IPv4 withdrawn/announced and MP_REACH/MP_UNREACH

**Phase 3: Update messages() for new mode ✅**
- `messages()` now handles both legacy and new mode
- In new mode: uses `v4_announces`/`v4_withdraws` lists directly
- No reliance on `nlri.action` in new mode

**Phase 4: RIB del_from_rib() without deepcopy ✅**
- Added `_pending_withdraws` dict to `OutgoingRIB`
- `del_from_rib()` now stores NLRI directly in `_pending_withdraws`
- **No deepcopy required!** Eliminated the 88% CPU bottleneck
- Added `update_cache_withdraw()` method to Cache
- `updates()` yields withdraw Updates using new 3-arg signature

### All tests pass ✅
- Unit tests: 2678 passed
- Functional encoding: 36/36 passed
- Functional decoding: 18/18 passed
- API tests: 38/38 passed
- All 11 test suites pass

### Additional Completed Phases (2025-12-05)

**Phase 5: Update incoming RIB handler ✅**
- `UpdateHandler.handle()` and `handle_async()` now call `update_cache(nlri, attributes)`
- No more `Change` object creation in the receive path
- Removed `from exabgp.rib.change import Change` from handler

**Phase 6: Update cache and RIB with overloaded signatures ✅**
- `Cache.update_cache()` now accepts `(change)` or `(nlri, attributes)`
- `Cache.update_cache_withdraw()` now accepts `(change)` or `(nlri)`
- `OutgoingRIB.add_to_rib()` now accepts `(change, force)` or `(nlri, attrs, force)`
- `OutgoingRIB.del_from_rib()` now accepts `(change)` or `(nlri, attrs)`
- Full backward compatibility with existing callers

**Phase 7: Configuration parsers - keeping Change ✅**
- Decision: Keep `Change` class for configuration parsing
- `Change` serves as a clean data container for "route with attributes"
- Not performance critical (only at config load time)
- The new signatures allow callers to pass `(nlri, attrs)` directly where beneficial

### Remaining (Lower Priority)

- **Remove action from NLRI** - Would require significant changes to cache filtering
- **Delete Change class entirely** - Keep for configuration, provides clean abstraction

### Summary

The original performance goal (eliminating deepcopy in del_from_rib) is complete.
Additional phases added overloaded signatures to avoid unnecessary Change creation
in the receive path. The Change class is retained for configuration parsing where
it provides a useful abstraction.

---

## Problem Statement

1. `deepcopy()` in `del_from_rib()` takes 88% of CPU time
2. `action` stored on NLRI but it's not intrinsic to the route
3. `Change` class is just a wrapper around `(NLRI, Attributes)` - adds overhead

---

## Solution: Eliminate Change, Index by Attributes

**Key insight:** If RIB indexes by Attributes first, we don't need Change at all.

```python
# Current: Change wraps (NLRI, Attributes), indexed by change.index()
_new_nlri[change.index()] = change

# New: Store NLRIs directly, grouped by Attributes
_pending_announces: dict[bytes, dict[bytes, NLRI]]  # attr_index -> nlri_index -> NLRI
_pending_withdraws: dict[bytes, dict[bytes, NLRI]]  # attr_index -> nlri_index -> NLRI
_attributes: dict[bytes, Attributes]                 # attr_index -> Attributes
```

---

## Data Structures

### RIB Storage (new)

```python
class OutgoingRIB:
    # Announces: grouped by attributes, then by nlri
    _pending_announces: dict[bytes, dict[bytes, NLRI]]
    # Withdraws: grouped by attributes, then by nlri (attributes may be empty for withdraws)
    _pending_withdraws: dict[bytes, dict[bytes, NLRI]]
    # Attribute lookup
    _attributes: dict[bytes, Attributes]

    # Cache: still need to track what's been sent
    _seen: dict[tuple[AFI, SAFI], dict[bytes, tuple[NLRI, Attributes]]]
```

### Update Class (new)

```python
class Update(Message):
    def __init__(self, announces: list[NLRI], withdraws: list[NLRI], attributes: Attributes) -> None:
        self._announces = announces
        self._withdraws = withdraws
        self._attributes = attributes

    @property
    def announces(self) -> list[NLRI]:
        return self._announces

    @property
    def withdraws(self) -> list[NLRI]:
        return self._withdraws
```

---

## Implementation Plan

### Phase 1: Update Update class

```python
class Update(Message):
    def __init__(self, announces: list[NLRI], withdraws: list[NLRI], attributes: Attributes):
        self._announces = announces
        self._withdraws = withdraws
        self._attributes = attributes

    # Backward compat
    @property
    def nlris(self) -> list[NLRI]:
        return self._announces + self._withdraws

    def messages(self, negotiated, include_withdraw=True) -> Generator[bytes, None, None]:
        # Use self._announces and self._withdraws directly
        # No nlri.action needed
```

### Phase 2: Update unpack_message()

```python
@classmethod
def unpack_message(cls, data: bytes, negotiated: Negotiated) -> Update | EOR:
    # Parse withdrawn -> withdraws list
    # Parse announced -> announces list
    # Parse MP_UNREACH -> add to withdraws
    # Parse MP_REACH -> add to announces
    return Update(announces, withdraws, attributes)
```

### Phase 3: Restructure RIB storage

```python
def add_to_rib(self, nlri: NLRI, attributes: Attributes, force: bool = False) -> None:
    attr_index = attributes.index()
    nlri_index = nlri.index()

    self._pending_announces.setdefault(attr_index, {})[nlri_index] = nlri
    self._attributes[attr_index] = attributes

def del_from_rib(self, nlri: NLRI, attributes: Attributes) -> None:
    # No deepcopy needed! Just add to withdraws
    attr_index = attributes.index()  # May use empty attrs for withdraws
    nlri_index = nlri.index()

    self._pending_withdraws.setdefault(attr_index, {})[nlri_index] = nlri
```

### Phase 4: Update updates() generator

```python
def updates(self, grouped: bool) -> Iterator[Update | RouteRefresh]:
    # Generate Updates from pending announces
    for attr_index, nlri_dict in self._pending_announces.items():
        attrs = self._attributes[attr_index]
        announces = list(nlri_dict.values())
        yield Update(announces, [], attrs)

    # Generate Updates from pending withdraws
    for attr_index, nlri_dict in self._pending_withdraws.items():
        attrs = self._attributes.get(attr_index, Attributes())
        withdraws = list(nlri_dict.values())
        yield Update([], withdraws, attrs)

    # Clear pending
    self._pending_announces = {}
    self._pending_withdraws = {}
```

### Phase 5: Update callers to pass (NLRI, Attributes) instead of Change

All callers that create Change now pass tuple:
```python
# Before
change = Change(nlri, attributes)
rib.add_to_rib(change)

# After
rib.add_to_rib(nlri, attributes)
```

### Phase 6: Remove Change class

Delete `src/exabgp/rib/change.py`

### Phase 7: Remove action from NLRI

- Remove `action` attribute from NLRI
- Remove from `__init__`, `__copy__`, `__deepcopy__`

---

## Key Design Decisions

### Q1: What about withdraws with no attributes?

Withdraws in BGP don't require attributes. Options:
- Use empty `Attributes()` as key
- Use `None` as attr_index for withdraws
- Separate structure for withdraws (no attr grouping)

**Decision:** Withdraws use empty `Attributes()` - simpler, consistent.

### Q2: What about configuration parsing?

Configuration creates Change objects. Replace with:
```python
# Before
change = Change(nlri, Attributes())
scope.append_route(change)

# After - return (NLRI, Attributes) tuple or just NLRI
scope.append_route(nlri, Attributes())
```

Or introduce a lightweight dataclass if needed for configuration:
```python
@dataclass
class Route:
    nlri: NLRI
    attributes: Attributes
```

### Q3: What about cache operations?

Cache stores what's been announced:
```python
# Current
_seen[family][change_index] = change

# New
_seen[family][nlri_index] = (nlri, attributes)
```

### Q4: What about TREAT_AS_WITHDRAW?

```python
update = Update.unpack_message(body, negotiated)
if INTERNAL_TREAT_AS_WITHDRAW in update.attributes:
    update = Update([], update.announces + update.withdraws, update.attributes)
```

---

## Files to Modify

### Core Changes

| File | Changes |
|------|---------|
| `src/exabgp/rib/change.py` | **DELETE** |
| `src/exabgp/rib/outgoing.py` | New storage structure, `add_to_rib(nlri, attrs)`, `del_from_rib(nlri, attrs)` |
| `src/exabgp/rib/cache.py` | Store `(nlri, attrs)` tuples instead of Change |
| `src/exabgp/bgp/message/update/__init__.py` | `Update(announces, withdraws, attrs)` |
| `src/exabgp/bgp/message/update/nlri/nlri.py` | Remove `action` attribute |

### Callers (replace Change with tuple)

| File | Changes |
|------|---------|
| `src/exabgp/reactor/peer/handlers/update.py` | Pass `(nlri, attrs)` to cache |
| `src/exabgp/configuration/flow/parser.py` | Return `(nlri, attrs)` |
| `src/exabgp/configuration/flow/__init__.py` | Use tuple |
| `src/exabgp/configuration/static/parser.py` | Return `(nlri, attrs)` |
| `src/exabgp/configuration/static/route.py` | Return tuples |
| `src/exabgp/configuration/static/__init__.py` | Use tuples |
| `src/exabgp/configuration/validator.py` | Use tuples |
| `src/exabgp/configuration/check.py` | Use `(nlri, attrs)` |
| `src/exabgp/configuration/l2vpn/parser.py` | Return tuple |
| `src/exabgp/configuration/announce/__init__.py` | Return tuples |
| `src/exabgp/configuration/core/scope.py` | `append_route(nlri, attrs)` |
| `src/exabgp/configuration/announce/*.py` | Update check functions |

### API/Response (use Update directly)

| File | Changes |
|------|---------|
| `src/exabgp/reactor/api/command/announce.py` | Create Updates directly |
| `src/exabgp/reactor/api/response/json.py` | Use Update.announces/withdraws |
| `src/exabgp/reactor/api/response/text.py` | Use Update properties |

---

## Expected Outcome

- **No deepcopy:** `del_from_rib()` just adds NLRI to withdraws dict
- **No Change class:** Eliminated ~100 lines, one less abstraction
- **No action field:** Removed from NLRI entirely
- **Simpler RIB:** Direct storage of NLRIs grouped by Attributes
- **Memory savings:** No wrapper object overhead

---

## Implementation Order

1. Update `Update.__init__(announces, withdraws, attrs)` with backward compat
2. Update `Update.messages()` to use two lists
3. Update `unpack_message()` to populate two lists
4. Restructure RIB storage (add separate announce/withdraw dicts)
5. Update `add_to_rib()` / `del_from_rib()` signatures
6. Update all Change creation sites to use tuples
7. Update cache to store tuples
8. Remove action from NLRI
9. Delete Change class
10. Run tests after each phase
