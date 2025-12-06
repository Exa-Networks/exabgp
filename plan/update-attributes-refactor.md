# Plan: Separate Generation from Container in Update and Attributes

## Problem Statement

The `Update` and `Attributes` classes mix two responsibilities:
1. **Container** - holding data (semantic objects or wire bytes)
2. **Generator** - serializing data to wire format

Individual `Attribute` classes (e.g., `Origin`, `NextHop`) correctly use "packed-bytes-first" pattern:
- Store `_packed: bytes` as canonical representation
- Derive semantic values via properties
- Clear separation of concerns

But their containers (`Update`, `Attributes`) do the opposite:
- Store semantic objects, generate bytes on demand
- `Update.messages()` is a complex generator mixed into data class

## Design Decision

User selected:
- **Full separation**: Add new classes with clear separation
- **Accept one-to-many**: Serializer yields multiple Update objects
- **Canonical names for wire containers**: `Update` and `Attributes` should be the wire-format (bytes-first) classes
- **Keep Change class**: `Change` (1 NLRI + 1 Attributes) remains for RIB storage; `UpdateData` (N NLRIs + 1 Attributes) is for message batching

## New Class Hierarchy

```
Update (Wire Container - NEW)
    _payload: bytes
    Properties: announces, withdraws, attributes (lazy parsed)
    The "real" BGP UPDATE message - bytes-first

UpdateData (Semantic Container - current Update renamed)
    _announces: list[NLRI]
    _withdraws: list[NLRI]
    _attributes: AttributeSet
    Batches multiple routes for message generation

UpdateSerializer (Generator - NEW)
    serialize(UpdateData, Negotiated) -> Iterator[Update]
    One UpdateData can produce multiple Update wire messages

Attributes (Wire Container - NEW)
    _packed: bytes
    parse(Negotiated) -> AttributeSet  # lazy
    The "real" path attributes - bytes-first

AttributeSet (Semantic Container - current Attributes renamed)
    Inherits from dict, stores Attribute objects by code
    Used for building updates from configuration

Change (UNCHANGED - kept for RIB storage)
    nlri: NLRI
    attributes: Attributes
    Single route for RIB storage and deduplication
```

## Implementation Steps

### Phase 1: Rename Existing Classes

**Step 1.1: Rename current Update → UpdateData**
- File: `src/exabgp/bgp/message/update/__init__.py`
- Rename class `Update` to `UpdateData`
- Keep all current functionality
- This is the semantic container (lists of NLRI + attributes)

**Step 1.2: Rename current Attributes → AttributeSet**
- File: `src/exabgp/bgp/message/update/attribute/attributes.py`
- Rename class `Attributes` to `AttributeSet`
- Keep all current functionality (dict of Attribute objects)
- This is the semantic container for building updates

### Phase 2: Create Wire Containers

**Step 2.1: Create new Update (wire container)**
- File: `src/exabgp/bgp/message/update/__init__.py` (same file)
- Wire container for single BGP UPDATE message
- Stores `_payload: bytes` as canonical representation
- Lazy parsing to get semantic data

```python
class Update(Message):
    """Wire-format BGP UPDATE message (bytes-first)."""
    ID = Message.CODE.UPDATE
    TYPE = bytes([Message.CODE.UPDATE])

    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._parsed: UpdateData | None = None

    @property
    def payload(self) -> bytes:
        return self._payload

    def to_bytes(self) -> bytes:
        """Complete BGP message with header."""
        return Message.MARKER + pack('!H', 19 + len(self._payload)) + self.TYPE + self._payload

    @property
    def data(self) -> UpdateData:
        """Lazy-parse to semantic UpdateData."""
        if self._parsed is None:
            self._parsed = UpdateData.unpack(self._payload, ...)
        return self._parsed

    # Properties that delegate to parsed data
    @property
    def announces(self) -> list[NLRI]:
        return self.data.announces

    @property
    def withdraws(self) -> list[NLRI]:
        return self.data.withdraws

    @property
    def attributes(self) -> Attributes:
        return self.data.attributes
```

**Step 2.2: Create new Attributes (wire container)**
- File: `src/exabgp/bgp/message/update/attribute/attributes.py` (same file)
- Wire container for packed path attributes
- Stores `_packed: bytes` as canonical representation

```python
class Attributes:
    """Wire-format path attributes container (bytes-first)."""

    def __init__(self, packed: bytes, context: Negotiated | None = None) -> None:
        self._packed = packed
        self._context = context
        self._parsed: AttributeSet | None = None

    @classmethod
    def from_set(cls, attr_set: AttributeSet, negotiated: Negotiated) -> 'Attributes':
        """Create from semantic AttributeSet."""
        return cls(attr_set.pack_attribute(negotiated), negotiated)

    @property
    def packed(self) -> bytes:
        return self._packed

    def parse(self, negotiated: Negotiated | None = None) -> AttributeSet:
        """Lazy-parse to AttributeSet."""
        if self._parsed is None:
            self._parsed = AttributeSet.unpack(self._packed, negotiated or self._context)
        return self._parsed

    # Delegate common operations to parsed set
    def __getitem__(self, code: int) -> Attribute:
        return self.parse()[code]

    def has(self, code: int) -> bool:
        return self.parse().has(code)
```

### Phase 3: Create Serializer

**Step 3.1: Create UpdateSerializer**
- File: `src/exabgp/bgp/message/update/serializer.py` (new)
- Move logic from current `Update.messages()` here
- Takes `UpdateData`, yields `Update` wire messages

```python
class UpdateSerializer:
    @staticmethod
    def serialize(
        data: UpdateData,
        negotiated: Negotiated,
        include_withdraw: bool = True,
    ) -> Generator[Update, None, None]:
        """Convert UpdateData to wire-format Update messages.

        One UpdateData can produce multiple Update messages due to size limits.
        """
        # Logic moved from current Update.messages()
        # Build payload bytes, yield Update(payload)
        ...

    @staticmethod
    def serialize_bytes(
        data: UpdateData,
        negotiated: Negotiated,
        include_withdraw: bool = True,
    ) -> Generator[bytes, None, None]:
        """Convenience: yield complete message bytes."""
        for update in UpdateSerializer.serialize(data, negotiated, include_withdraw):
            yield update.to_bytes()
```

### Phase 4: Backward Compatibility

**Step 4.1: Add compatibility layer to UpdateData**
```python
class UpdateData:
    # ... existing code ...

    def messages(self, negotiated: Negotiated, include_withdraw: bool = True) -> Generator[bytes, None, None]:
        """DEPRECATED: Use UpdateSerializer.serialize() instead."""
        import warnings
        warnings.warn(
            "UpdateData.messages() is deprecated, use UpdateSerializer.serialize()",
            DeprecationWarning,
            stacklevel=2
        )
        yield from UpdateSerializer.serialize_bytes(self, negotiated, include_withdraw)
```

**Step 4.2: Add type alias for migration**
```python
# Temporary alias for gradual migration
# Old code: Update([nlri], [], attrs) still works via UpdateData
```

### Phase 5: Update Callers

Files that need migration:
- `src/exabgp/reactor/protocol.py` - sends updates via UpdateSerializer
- `src/exabgp/rib/outgoing.py` - creates UpdateData from Changes (unchanged pattern)
- `src/exabgp/application/encode.py` - CLI encode command
- `src/exabgp/configuration/check.py` - validation

**Note**: `Change` class remains for RIB storage. The RIB stores `Change` objects and groups them into `UpdateData` when generating messages.

Migration pattern:
```python
# Before (current)
update = Update([nlri], [], attrs)
for msg in update.messages(negotiated):
    send(msg)

# After (new)
data = UpdateData([nlri], [], attrs)
for update in UpdateSerializer.serialize(data, negotiated):
    send(update.to_bytes())
    # Or access: update.payload, update.announces, etc.
```

## Files to Create

| File | Purpose |
|------|---------|
| `src/exabgp/bgp/message/update/serializer.py` | UpdateSerializer class |

## Files to Modify

| File | Changes |
|------|---------|
| `src/exabgp/bgp/message/update/__init__.py` | Rename Update→UpdateData, add new Update (wire) |
| `src/exabgp/bgp/message/update/attribute/attributes.py` | Rename Attributes→AttributeSet, add new Attributes (wire) |
| `src/exabgp/reactor/protocol.py` | Update to use UpdateSerializer |
| `src/exabgp/rib/outgoing.py` | Update to yield UpdateData (name change only) |

## Tests to Add

| Test File | Coverage |
|-----------|----------|
| `tests/unit/bgp/message/update/test_update_wire.py` | Update wire container |
| `tests/unit/bgp/message/update/test_serializer.py` | Serialize round-trip, size limits |
| `tests/unit/bgp/message/update/attribute/test_attributes_wire.py` | Attributes wire container |

## Verification

After implementation:
```bash
./qa/bin/test_everything  # All 6 test suites must pass
```

Key functional tests to verify:
- `./qa/bin/functional encoding` - all 72 tests
- `./qa/bin/functional decoding` - all tests

## Summary of Name Changes

| Current Name | New Name | Role |
|--------------|----------|------|
| `Update` | `UpdateData` | Semantic container (lists of NLRI + attributes for batching) |
| (new) | `Update` | Wire container (bytes-first) |
| `Attributes` | `AttributeSet` | Semantic container (dict of Attribute objects) |
| (new) | `Attributes` | Wire container (bytes-first) |
| (new) | `UpdateSerializer` | Generation logic |
| `Change` | `Change` | **Unchanged** - remains for RIB storage (1 NLRI + 1 Attributes) |

## Notes

- Wire containers (`Update`, `Attributes`) have the canonical names - they represent "the real thing"
- Semantic containers (`UpdateData`, `AttributeSet`) are for building/manipulating before serialization
- This matches how individual `Attribute` classes work (bytes-first with semantic properties)
- One `UpdateData` can produce multiple `Update` wire messages (due to size limits)
- Backward compatibility via deprecated `messages()` method on `UpdateData`
- `Change` class kept separate - optimized for RIB storage (1 NLRI), different from `UpdateData` (N NLRIs for batching)

## Implementation Progress

**Phase 1 (Incremental - using *Wire suffix):**
- ✅ `UpdateData` alias added (points to current `Update`)
- ✅ `AttributeSet` alias added (points to current `Attributes`)
- ✅ `UpdateWire` class created (wire container, bytes-first)
- ✅ `AttributesWire` class created (wire container, bytes-first)
- ✅ `UpdateSerializer` class created

**Phase 2 (Swap canonical names) - ✅ COMPLETED 2025-12-06:**
- ✅ Rename current `Update` class → `UpdateData`
- ✅ Rename `UpdateWire` → `Update` (now wire container is canonical)
- ✅ Rename current `Attributes` class → `AttributeSet`
- ✅ Rename `AttributesWire` → `Attributes` (now wire container is canonical)
- ✅ Update all imports across codebase
- ✅ Update all tests to use `AttributeSet` for semantic container
- ✅ All 11 test suites pass (ruff, unit, config, functional, cli, api)

**Backward compatibility aliases:**
- `UpdateWire` → `Update` (for any code using old wire container name)
- `AttributesWire` → `Attributes` (for any code using old wire container name)

## Future Considerations

- ✅ Rename `Change` → `Route` for clarity (Change describes action, Route describes what it is) - **COMPLETED** (separate plan: `eliminate-change-class.md`)

---

### Phase 3: Naming Cleanup - 🔄 IN PROGRESS

**Problem:** Current names don't follow consistent conventions:
- `UpdateData` doesn't match `AttributeSet` pattern
- `AttributeSet` implies set semantics but it's a dict
- `UpdateSerializer.serialize()` doesn't match codebase `pack_*` convention

**Step 3.1: Rename semantic containers (via sed)**
- `UpdateData` → `UpdateCollection`
- `AttributeSet` → `AttributeCollection`
- ~502 occurrences across 38 files

```bash
find src tests -name "*.py" -exec sed -i '' 's/UpdateData/UpdateCollection/g; s/AttributeSet/AttributeCollection/g' {} +
```

**Step 3.2: Move serialize logic into UpdateCollection**
- Move `UpdateSerializer.serialize()` → `UpdateCollection.pack_messages()`
- Rename to follow `pack_*` convention
- Delete `UpdateSerializer` class (keep deprecated alias if needed)

**Step 3.3: Update backward compatibility aliases**
- Add `UpdateData = UpdateCollection` alias
- Add `AttributeSet = AttributeCollection` alias

**Final class hierarchy after Phase 3:**
```
Update (Wire Container)
    _payload: bytes
    The "real" BGP UPDATE message - bytes-first

UpdateCollection (Semantic Container)
    _announces: list[NLRI]
    _withdraws: list[NLRI]
    _attributes: AttributeCollection
    pack_messages(negotiated) -> Generator[Update]

Attributes (Wire Container)
    _packed: bytes
    The "real" path attributes - bytes-first

AttributeCollection (Semantic Container)
    Inherits from dict, stores Attribute objects by code
    pack_attribute(negotiated) -> bytes
```

**Phase 3 Progress - ✅ COMPLETED 2025-12-06:**
- ✅ Step 3.1: Rename via sed (502 occurrences across 38 files)
- ✅ Step 3.2: Added `UpdateCollection.pack_messages()`, deprecated `UpdateSerializer`
- ✅ Step 3.3: Added backward compatibility aliases (`UpdateData`, `AttributeSet`)
- ✅ All 11 test suites pass

**Backward compatibility aliases (complete):**
- `UpdateWire` → `Update`
- `UpdateData` → `UpdateCollection`
- `AttributesWire` → `Attributes`
- `AttributeSet` → `AttributeCollection`

---

## Plan Status: ✅ COMPLETE

All phases implemented and verified. Tests passing (11/11 suites, 2025-12-06).
