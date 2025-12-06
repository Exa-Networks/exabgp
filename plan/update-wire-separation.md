# Plan: Proper Separation of Update Wire and Collection Classes

## Problem Statement

The current implementation has `Update` and `UpdateCollection` as separate classes, but:
1. `Update` does NOT inherit from `Message` - it's just a plain class
2. `UpdateCollection` inherits from `Message` and is registered as the UPDATE handler
3. `UpdateCollection.unpack_message()` returns `UpdateCollection`, not `Update`
4. The "wire" class (`Update`) is effectively unused - it's just an alias wrapper

**What should happen:**
- `Update(Message)` should be the registered BGP UPDATE message class
- It stores raw payload bytes after the BGP header
- It provides access to raw bytes for: withdrawn routes, attributes, announced NLRI
- Parsing to `AttributeCollection` happens on-demand when needed
- `UpdateCollection` becomes a builder/utility for constructing updates from semantic data

## Current State

```
File: src/exabgp/bgp/message/update/__init__.py

class Update:                    # NOT Message subclass!
    _payload: bytes
    _parsed: UpdateCollection | None

@Message.register
class UpdateCollection(Message): # This is the registered UPDATE handler
    _announces: list[NLRI]
    _withdraws: list[NLRI]
    _attributes: AttributeCollection
```

## Target State

```
@Message.register
class Update(Message):           # Wire container, registered handler
    _payload: bytes              # Raw UPDATE payload (after BGP header)

    # Properties to access raw bytes:
    @property
    def withdrawn_bytes(self) -> bytes: ...
    @property
    def attribute_bytes(self) -> bytes: ...
    @property
    def nlri_bytes(self) -> bytes: ...

    # Returns Attributes wire container (same pattern as Update itself):
    def attributes(self, negotiated) -> Attributes: ...
    # Caller can then do: update.attributes(neg).parse() -> AttributeCollection

class Attributes:                # Wire container for path attributes
    _packed: bytes               # Raw attribute bytes
    _context: Negotiated | None
    _parsed: AttributeCollection | None

    def parse(self, negotiated=None) -> AttributeCollection: ...

class UpdateCollection:          # Semantic builder (NOT Message)
    _announces: list[NLRI]
    _withdraws: list[NLRI]
    _attributes: AttributeCollection

    def messages(self, negotiated) -> Generator[bytes]: ...
    def pack_messages(self, negotiated) -> Generator[Update]: ...
```

**Pattern consistency:**
- `Update` stores raw bytes → returns `Attributes` wire container
- `Attributes` stores raw bytes → returns `AttributeCollection` on `parse()`
- Both follow "bytes-first, parse on demand" pattern

## Implementation Steps

### Step 1: Restructure Update class

**File:** `src/exabgp/bgp/message/update/__init__.py`

1. Make `Update` inherit from `Message`
2. Add `@Message.register` decorator to `Update`
3. Remove `@Message.register` from `UpdateCollection`
4. Add properties to `Update` for accessing raw bytes:
   - `withdrawn_bytes` - raw withdrawn routes section
   - `attribute_bytes` - raw path attributes section
   - `nlri_bytes` - raw announced NLRI section
5. Add `split()` as instance method (currently on `UpdateCollection`)
6. Add `unpack_message(cls, data, negotiated)` to `Update` that returns `Update`
7. Add method to return Attributes wire container: `attributes(negotiated) -> Attributes`

### Step 2: Simplify UpdateCollection

1. Remove `Message` inheritance from `UpdateCollection`
2. Remove `@Message.register` decorator
3. Keep `messages()` and `pack_messages()` for building updates
4. Keep parsing logic as a utility method (renamed from `unpack_message`)

### Step 3: Update callers

Files that call `UpdateCollection.unpack_message()` need to change to `Update.unpack_message()`:
- `src/exabgp/reactor/protocol.py` - message handling
- Tests that parse UPDATE messages

### Step 4: Verify Attributes class

**File:** `src/exabgp/bgp/message/update/attribute/collection.py`

Ensure `Attributes` wire container:
- Stores `_packed: bytes`
- Provides `parse(negotiated) -> AttributeCollection` on demand
- Does NOT eagerly parse

## Files to Modify

| File | Changes |
|------|---------|
| `src/exabgp/bgp/message/update/__init__.py` | Main refactoring |
| `src/exabgp/reactor/protocol.py` | Update message handling |
| `tests/unit/bgp/message/update/test_update_refactor.py` | Update tests |

## Update Class API (Target)

```python
@Message.register
class Update(Message):
    ID = Message.CODE.UPDATE
    TYPE = bytes([Message.CODE.UPDATE])

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    @property
    def payload(self) -> bytes:
        """Raw UPDATE payload bytes."""
        return self._payload

    @property
    def withdrawn_bytes(self) -> bytes:
        """Raw bytes of withdrawn routes section."""
        withdrawn_len = unpack('!H', self._payload[:2])[0]
        return self._payload[2:2+withdrawn_len]

    @property
    def attribute_bytes(self) -> bytes:
        """Raw bytes of path attributes section."""
        withdrawn_len = unpack('!H', self._payload[:2])[0]
        attr_offset = 2 + withdrawn_len
        attr_len = unpack('!H', self._payload[attr_offset:attr_offset+2])[0]
        return self._payload[attr_offset+2:attr_offset+2+attr_len]

    @property
    def nlri_bytes(self) -> bytes:
        """Raw bytes of announced NLRI section."""
        withdrawn_len = unpack('!H', self._payload[:2])[0]
        attr_offset = 2 + withdrawn_len
        attr_len = unpack('!H', self._payload[attr_offset:attr_offset+2])[0]
        nlri_offset = attr_offset + 2 + attr_len
        return self._payload[nlri_offset:]

    def attributes(self, negotiated: Negotiated) -> Attributes:
        """Return Attributes wire container (can parse to AttributeCollection on demand)."""
        return Attributes(self.attribute_bytes, negotiated)

    @classmethod
    def unpack_message(cls, data: bytes, negotiated: Negotiated) -> 'Update':
        """Create Update from raw payload bytes."""
        return cls(data)

    def to_bytes(self) -> bytes:
        """Generate complete BGP message with header."""
        return self._message(self._payload)
```

## Verification

```bash
./qa/bin/test_everything  # All 11 test suites must pass
```

## Progress

- [x] Step 1: Restructure Update class
  - Made `Update` inherit from `Message`
  - Added `@Message.register` decorator to `Update`
  - Added `unpack_message()` classmethod that returns `Update | EOR`
  - Added `parse()` method for lazy parsing to `UpdateCollection`
  - Added `withdrawn_bytes`, `attribute_bytes`, `nlri_bytes` properties
- [x] Step 2: Simplify UpdateCollection
  - Removed `@Message.register` from `UpdateCollection`
  - Kept `Message` inheritance for `_message()` helper
  - Added `_parse_payload()` internal method for parsing
  - Kept backward compat `unpack_message()` that returns `UpdateCollection | EOR`
- [x] Step 3: Update callers
  - Updated `protocol.py` to use `Update(raw).parse()` instead of `UpdateCollection.unpack_message()`
- [x] Step 4: Verify Attributes class already follows same pattern
- [x] Run tests - All 11 test suites pass
