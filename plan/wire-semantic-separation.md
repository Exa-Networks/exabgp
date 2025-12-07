# Wire vs Semantic Container Separation

**Status:** 🔄 Phase 1 Complete
**Created:** 2025-12-07
**Updated:** 2025-12-07

## Goal

Enforce strict separation between Wire Containers (immutable, bytes-first) and Semantic Containers (Collections - mutable, for transformations). Wire objects should be sendable without modification. Semantic containers handle parsing, mutation, and re-encoding for different peer capabilities.

---

## Design Principles

### Wire Container (Update, Attribute, NLRI)

- **Immutable** after creation
- Stores `_packed: bytes` (canonical wire representation)
- Stores `_negotiated: Negotiated` (capabilities that created it)
- `pack_message()` / `pack()` → just return `_packed` with header (no processing)
- `parse()` → returns NEW Semantic Container (no caching)
- **No semantic delegation properties** (no `.announces`, `.attributes` on `Update`)

### Semantic Container (UpdateCollection, AttributeCollection, NLRICollection)

- **Mutable** - can add/remove/modify components
- Stores parsed semantic objects
- `pack(negotiated)` → creates NEW Wire Container for target capabilities
- Factory methods for building from components

### Transformation Flow

```
Peer A (caps_a)                           Peer B (caps_b)
     |                                         ^
     v                                         |
 wire_bytes_a                             wire_bytes_b
     |                                         ^
     v                                         |
Update(packed, negotiated_a)          Update(packed, negotiated_b)
     |                                         ^
     | .parse()                                | .pack(negotiated_b)
     v                                         |
UpdateCollection  ──────────────────────> UpdateCollection
(mutable semantic container - same instance or copy)
```

---

## Current Violations

### Update Class (`src/exabgp/bgp/message/update/__init__.py`)

| Violation | Line | Issue |
|-----------|------|-------|
| Caches `_parsed` | 83-85 | Blurs immutability, stores mutable state |
| No `_negotiated` | 71 | Can't re-encode without knowing original caps |
| Delegation properties | 151-168 | `.announces`, `.withdraws`, `.attributes`, `.nlris` |
| `parse()` caches | 146-148 | Should return fresh collection |

### Attribute Class (`src/exabgp/bgp/message/update/attribute/attribute.py`)

| Violation | Issue |
|-----------|-------|
| No `_negotiated` storage | Individual attributes don't know their context |
| Mixed concerns | Base class handles both wire and semantic aspects |

### AttributeCollection (`src/exabgp/bgp/message/update/attribute/collection.py`)

| Issue | Description |
|-------|-------------|
| Class-level caching | `cached`, `previous` at class level (lines 66-68) |
| Mixed wire/semantic | Both parses and builds in same class |

---

## Implementation Phases

### Phase 1: Update/UpdateCollection Separation

**Goal:** Clean separation, callers use `UpdateCollection` for semantic access.

#### 1.1 Modify Update Class

```python
class Update(Message):
    """Immutable wire-format BGP UPDATE message."""

    __slots__ = ('_packed', '_negotiated')

    def __init__(self, packed: Buffer, negotiated: Negotiated) -> None:
        self._packed = bytes(packed)
        self._negotiated = negotiated

    @property
    def packed(self) -> bytes:
        return self._packed

    @property
    def negotiated(self) -> Negotiated:
        return self._negotiated

    def pack_message(self) -> bytes:
        """Return wire bytes with BGP header."""
        return self._message(self._packed)

    def parse(self) -> UpdateCollection:
        """Parse to semantic container using stored negotiated.

        Returns fresh UpdateCollection each time (no caching).
        """
        return UpdateCollection._parse_payload(self._packed, self._negotiated)

    # REMOVE: _parsed, announces, withdraws, attributes, nlris properties
```

#### 1.2 Modify UpdateCollection Class

```python
class UpdateCollection:
    """Mutable semantic container for UPDATE data."""

    def __init__(
        self,
        announces: list[NLRI],
        withdraws: list[NLRI],
        attributes: AttributeCollection,
    ) -> None:
        self._announces = announces
        self._withdraws = withdraws
        self._attributes = attributes

    def pack(self, negotiated: Negotiated) -> Update:
        """Create wire-format Update for target peer capabilities.

        Args:
            negotiated: Target peer's negotiated capabilities.

        Returns:
            New Update wire container.
        """
        # Use existing messages() logic, return single Update
        # (or iterator for multiple if message fragmentation needed)
        ...

    def pack_messages(self, negotiated: Negotiated) -> Iterator[Update]:
        """Create multiple Updates if fragmentation needed."""
        for msg_bytes in self.messages(negotiated):
            payload = msg_bytes[19:]  # Strip BGP header
            yield Update(payload, negotiated)
```

#### 1.3 Update Callers

| File | Current | Change To |
|------|---------|-----------|
| `reactor/peer/handlers/update.py:47-48` | `update.announces`, `update.attributes` | `collection = update.parse(); collection.announces` |
| `reactor/peer/handlers/update.py:55` | `update.withdraws` | `collection.withdraws` |
| `reactor/peer/handlers/update.py:76-77` | `update.announces`, `update.attributes` | `collection.announces`, `collection.attributes` |
| `reactor/peer/handlers/update.py:84` | `update.withdraws` | `collection.withdraws` |
| `reactor/protocol.py:261-262` | `update.attributes`, `update.nlris` | `collection.attributes`, `collection.nlris` |
| `reactor/api/response/text.py:120-121` | `update.attributes`, `update.nlris` | `collection.attributes`, `collection.nlris` |
| `reactor/api/response/v4/text.py:146-147` | `update.attributes`, `update.nlris` | `collection.attributes`, `collection.nlris` |
| `configuration/check.py:139-141` | `update.nlris`, `update.attributes` | `collection.nlris`, `collection.attributes` |
| `configuration/check.py:462-463` | `update.nlris`, `update.attributes` | `collection.nlris`, `collection.attributes` |

#### 1.4 Update unpack_message

```python
@classmethod
def unpack_message(cls, data: Buffer, negotiated: Negotiated) -> Message:
    """Unpack raw UPDATE payload to Update.

    Returns Update wire container. Caller must call parse()
    to get semantic UpdateCollection.
    """
    # EOR checks...

    # Return wire container - do NOT parse here
    return cls(data, negotiated)
```

**Issue:** Current code parses immediately and checks for EOR. Need to handle EOR detection differently or accept that EOR is a special case.

---

### Phase 2: Attribute/AttributeCollection Separation

**Goal:** Individual Attribute classes are wire-first, AttributeCollection is semantic.

#### 2.1 Attribute Base Class

```python
class Attribute:
    """Base for wire-format attributes."""

    __slots__ = ('_packed', '_negotiated')

    def __init__(self, packed: bytes, negotiated: Negotiated | None = None) -> None:
        self._packed = packed
        self._negotiated = negotiated

    def pack(self) -> bytes:
        """Return wire bytes."""
        return self._packed

    # Properties parse from _packed on access
```

#### 2.2 Individual Attribute Subclasses

Each subclass (Origin, ASPath, NextHop, Communities, etc.):
- Store `_packed` bytes
- `@property` methods parse from `_packed`
- Factory methods (`make_xxx()`) pack immediately

Many attribute classes already follow this pattern. Audit each for compliance.

#### 2.3 AttributeCollection

- Remove class-level caching (`cached`, `previous`)
- Pure semantic container
- `pack_attribute(negotiated)` creates new wire bytes

---

### Phase 3: NLRI/Collection Alignment

**Goal:** Ensure NLRI classes follow packed-bytes-first, Collections are semantic.

#### 3.1 Audit NLRI Classes

Already documented in `PACKED_BYTES_FIRST_PATTERN.md`. Key classes:
- `VPLS` - reference implementation
- `EVPN` variants
- `FlowSpec` - complex, may need special handling
- `BGP-LS` variants

#### 3.2 NLRICollection / MPNLRICollection

- Already semantic containers
- Verify they don't cache wire state

---

### Phase 4: Testing

#### 4.1 Unit Tests

| Test | Description |
|------|-------------|
| `test_update_immutability` | Verify Update doesn't expose mutable state |
| `test_update_parse_returns_fresh` | Each `parse()` call returns new collection |
| `test_update_negotiated_stored` | `_negotiated` is accessible |
| `test_collection_mutation` | Collection allows add/remove |
| `test_collection_pack_creates_new` | `pack()` returns new wire container |
| `test_roundtrip_different_caps` | Parse with caps_a, pack with caps_b |

#### 4.2 Functional Tests

- All existing encoding/decoding tests must pass
- Add tests for capability transformation scenarios

---

## Files to Modify

### Core Changes

| File | Changes |
|------|---------|
| `src/exabgp/bgp/message/update/__init__.py` | Remove `_parsed`, add `_negotiated`, remove delegation properties |
| `src/exabgp/bgp/message/update/attribute/attribute.py` | Add `_negotiated` to base class |
| `src/exabgp/bgp/message/update/attribute/collection.py` | Remove class-level caching |

### Caller Updates

| File | Changes |
|------|---------|
| `src/exabgp/reactor/peer/handlers/update.py` | Use `collection = update.parse()` |
| `src/exabgp/reactor/protocol.py` | Use `collection = update.parse()` |
| `src/exabgp/reactor/api/response/text.py` | Use collection properties |
| `src/exabgp/reactor/api/response/v4/text.py` | Use collection properties |
| `src/exabgp/configuration/check.py` | Use collection properties |

### Documentation

| File | Changes |
|------|---------|
| `.claude/exabgp/COLLECTION_PATTERN.md` | Update with corrected design |
| `.claude/exabgp/WIRE_SEMANTIC_SEPARATION.md` | New - comprehensive design doc |
| `CLAUDE.md` | Add reference to new documentation |

---

## Migration Strategy

### Backward Compatibility

During transition, Update can have deprecated delegation properties that log warnings:

```python
@property
def announces(self) -> list[NLRI]:
    """Deprecated: Use update.parse().announces instead."""
    import warnings
    warnings.warn(
        "update.announces is deprecated, use update.parse().announces",
        DeprecationWarning,
        stacklevel=2
    )
    return self.parse().announces
```

Remove after all callers updated.

### Incremental Approach

1. **Phase 1a:** Add `_negotiated` to Update, keep existing behavior
2. **Phase 1b:** Update callers to use `parse().property`
3. **Phase 1c:** Remove `_parsed` caching and delegation properties
4. **Phase 2:** Apply same pattern to Attribute/AttributeCollection
5. **Phase 3:** Audit NLRI classes
6. **Phase 4:** Full test suite validation

---

## Open Questions

### EOR Detection

Current `unpack_message` parses to detect EOR. Options:
1. **Check wire bytes directly** - EOR has specific byte patterns
2. **Return special EOR subclass** - detected from wire format
3. **Parse minimally for EOR** - only parse if potential EOR

Recommendation: Option 1 - EOR detection from wire bytes (already partially implemented).

### Message Fragmentation

`UpdateCollection.messages()` can generate multiple wire messages. Should `pack()`:
1. Return first message only?
2. Return iterator?
3. Raise if would fragment?

Recommendation: Keep `pack_messages()` as iterator, add `pack()` that raises if fragmentation needed.

### Negotiated Storage Overhead

Every Update/Attribute storing `_negotiated` adds memory. Options:
1. **Store reference** - minimal overhead if same Negotiated reused
2. **Store weakref** - allows GC but may be None when accessed
3. **Store on parse only** - don't store in wire container

Recommendation: Option 1 - store reference, Negotiated is per-peer so limited instances.

---

## Success Criteria

- [x] Update has no `_parsed` caching (lazy init to None)
- [x] Update has `_negotiated` stored
- [x] Update has no semantic delegation properties (removed nlris, announces, withdraws, attributes)
- [x] All callers use `update.data` or `update.parse()`
- [x] UpdateCollection.pack_messages(negotiated) returns Update with negotiated
- [x] All tests pass (unit + functional)
- [ ] Documentation updated

---

## Recent Failures

### 2025-12-07 - Phase 1 Implementation

**Fixed issues during implementation:**

1. **Test mocks needed update** - Tests mocked `update.announces` directly, needed `update.data.announces`
2. **EOR handling in protocol.py** - Both Update and EOR have `TYPE == Update.TYPE`, needed `isinstance()` check
3. **EOR handling in processes.py** - `_update()` receives both Update and EOR, added `.EOR` flag check
4. **EOR class missing `.EOR` flag** - Added `EOR: bool = True` to EOR class (Update has `EOR: bool = False`)

All tests pass after fixes.

---

## Blockers

*(None)*

---

## Resume Point

**Phase 1 COMPLETE** ✅

**Next action:** Phase 2 - Attribute/AttributeCollection Separation (if desired)

---

**Updated:** 2025-12-07
