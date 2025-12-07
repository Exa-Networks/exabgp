# Collection Pattern Reference

**Purpose:** Document the Wire Container vs Semantic Container pattern used in ExaBGP.
**Related:** `WIRE_SEMANTIC_SEPARATION.md` (comprehensive design), `PACKED_BYTES_FIRST_PATTERN.md`

---

## Overview

ExaBGP uses two complementary container patterns:

1. **Wire Container** - immutable, stores `_packed` bytes + `_negotiated` capabilities
2. **Semantic Container (Collection)** - mutable, stores parsed objects, used for building/modification

---

## Pattern Definitions

### Wire Container Pattern

**Purpose:** Immutable storage of wire-format data for efficient transmission.

```python
class WireContainer:
    """Immutable container for wire-format data."""

    __slots__ = ('_packed', '_negotiated')

    def __init__(self, packed: bytes, negotiated: Negotiated) -> None:
        self._packed = packed          # Canonical wire representation
        self._negotiated = negotiated  # Capabilities that created this

    @property
    def packed(self) -> bytes:
        """Raw wire bytes - read only."""
        return self._packed

    def pack_message(self) -> bytes:
        """Return wire bytes with header - no processing."""
        return self._header + self._packed

    def parse(self) -> SemanticContainer:
        """Convert to semantic container for modification.

        Returns FRESH container each call - no caching.
        Uses stored _negotiated for correct parsing.
        """
        return SemanticContainer._parse(self._packed, self._negotiated)
```

**Key properties:**
- Immutable after creation
- Stores originating capabilities (`_negotiated`)
- `pack()` returns `_packed` directly (zero-copy)
- `parse()` returns fresh collection (no caching)
- No semantic delegation properties

### Semantic Container (Collection) Pattern

**Purpose:** Mutable container for building, modifying, and transforming data.

```python
class SemanticContainer:
    """Mutable container for semantic data."""

    def __init__(self, items: list[Item], attributes: dict) -> None:
        self._items = items        # Mutable list
        self._attributes = attributes  # Mutable dict

    def add(self, item: Item) -> None:
        """Add item to collection."""
        self._items.append(item)

    def remove(self, item: Item) -> None:
        """Remove item from collection."""
        self._items.remove(item)

    def pack(self, negotiated: Negotiated) -> WireContainer:
        """Create wire container for target peer capabilities.

        This is a FACTORY operation - may:
        - Generate defaults (ORIGIN, AS_PATH, LOCAL_PREF)
        - Transform for target capabilities (ASN format)
        - Fragment into multiple messages
        """
        wire_bytes = self._serialize(negotiated)
        return WireContainer(wire_bytes, negotiated)

    @classmethod
    def _parse(cls, data: bytes, negotiated: Negotiated) -> 'SemanticContainer':
        """Parse wire bytes into semantic container."""
        # Parse items from data
        return cls(items, attributes)
```

**Key properties:**
- Mutable - add/remove/modify allowed
- `pack()` is a factory - creates NEW wire container
- Handles capability transformation
- May generate defaults or fragment messages

---

## Key Distinction

| Aspect | Wire Container | Semantic Container (Collection) |
|--------|---------------|--------------------------------|
| **Mutability** | Immutable | Mutable |
| **Storage** | `_packed` bytes + `_negotiated` | Dict/list of objects |
| **Primary use** | Receiving, forwarding, sending | Building, modifying |
| **pack() behavior** | Return `_packed` directly | Factory - create new Wire |
| **parse() behavior** | Return fresh Collection | N/A (is the parsed form) |
| **Caching** | None - no `_parsed` cache | None |

---

## Why Collection.pack() Can Do Data Processing

The Collection pattern is explicitly a **factory pattern**. When packing:

1. **Default generation** - Add missing ORIGIN, AS_PATH, LOCAL_PREF (AttributeCollection)
2. **Context-based transformation** - ASN format conversion based on peer capability
3. **Message fragmentation** - Split into multiple messages based on size limits
4. **Grouping** - Group NLRIs by nexthop (MPRNLRI)

This is acceptable because:
- **Collection is the builder** - it knows how to construct wire format
- **Wire Container just stores/returns bytes** - no transformation
- **Clear separation of concerns**

---

## Transformation Flow

```
Peer A                                    Peer B
(caps_a)                                  (caps_b)
   |                                         ^
   v                                         |
wire_bytes_a                            wire_bytes_b
   |                                         ^
   v                                         |
WireContainer                           WireContainer
(_packed, _negotiated_a)                (_packed, _negotiated_b)
   |                                         ^
   | .parse()                                | .pack(negotiated_b)
   v                                         |
Collection  ─────────────────────────>  Collection
(mutable)         modify if needed      (same or copy)
```

---

## Existing Implementations

| Wire Container | Semantic Container | Status |
|---------------|-------------------|--------|
| `Update` | `UpdateCollection` | **Needs refactoring** - has `_parsed` cache |
| `Attribute` subclasses | `AttributeCollection` | Mostly compliant |
| `NLRI` subclasses | `NLRICollection`/`MPNLRICollection` | Mostly compliant |
| `MPRNLRI` | `MPNLRICollection` | Dual-mode |
| `MPURNLRI` | `MPNLRICollection` | Dual-mode |

See `plan/wire-semantic-separation.md` for refactoring details.

---

## Pattern Application Examples

### Update / UpdateCollection

```
Wire Format:              Semantic Format:
Update                    UpdateCollection
(_packed bytes)           (announces, withdraws, attributes)
(_negotiated)
    |                           ^
    |                           |
    +---> .parse() -------------+  (returns fresh collection)
    |
    +---> .pack_message() -----> bytes (just adds header)

                                |
    <--- .pack(negotiated) -----+  (factory creates new Update)
```

**Update (Wire Container):**
- `__init__(packed, negotiated)` - stores raw bytes + capabilities
- `parse()` - returns fresh UpdateCollection (no caching)
- `pack_message()` - returns packed bytes with header

**UpdateCollection (Semantic Container):**
- `add_announce(nlri)` - add to announces list
- `pack(negotiated)` - factory creates new Update wire container
- `pack_messages(negotiated)` - iterator for fragmented messages

### Attributes / AttributeCollection

**Attribute subclasses (Wire Container):**
- `__init__(packed)` - stores raw bytes
- `@property` methods - parse from `_packed` on access
- `pack()` - returns `_packed`

**AttributeCollection (Semantic Container):**
- `dict` subclass - mutable attribute storage
- `add(attribute)` - add attribute to dict
- `pack_attribute(negotiated)` - factory generates wire format with defaults

---

## Common Mistakes

### 1. Caching Parsed Data in Wire Container

```python
# WRONG - Wire container caches semantic data
class Update:
    def __init__(self, packed, negotiated):
        self._packed = packed
        self._parsed = None  # Violates immutability

    def parse(self, negotiated):
        if self._parsed is None:
            self._parsed = UpdateCollection._parse(...)
        return self._parsed
```

### 2. Delegation Properties on Wire Container

```python
# WRONG - Wire container delegates to parsed data
class Update:
    @property
    def announces(self):
        return self._parsed.announces  # Should not exist on Wire

# CORRECT - Callers explicitly parse
collection = update.parse()
for nlri in collection.announces:
    ...
```

### 3. Missing Negotiated in Wire Container

```python
# WRONG - No way to know how to parse
class Update:
    def __init__(self, packed):
        self._packed = packed

    def parse(self, negotiated):  # Caller must provide
        ...

# CORRECT - Store originating capabilities
class Update:
    def __init__(self, packed, negotiated):
        self._packed = packed
        self._negotiated = negotiated

    def parse(self):  # Uses stored capabilities
        return UpdateCollection._parse(self._packed, self._negotiated)
```

---

## Iterator Pattern for Wire Containers

Wire containers may iterate over items by parsing `_packed` lazily:

```python
class Attributes:
    """Wire container for path attributes."""

    def __init__(self, packed: bytes, negotiated: Negotiated) -> None:
        self._packed = packed
        self._negotiated = negotiated

    def __iter__(self) -> Iterator[Attribute]:
        """Iterate over Attribute objects by parsing _packed."""
        data = memoryview(self._packed)
        while data:
            flag, code = data[0], data[1]
            # Extract length and slice
            attr_slice = data[offset:offset + length]

            # Each Attribute stores its slice
            attr = Attribute.unpack(code, flag, attr_slice, self._negotiated)
            yield attr

            data = data[offset + length:]
```

Each yielded object stores a buffer slice and parses on property access:

```python
class MED(Attribute):
    def __init__(self, packed: Buffer) -> None:
        self._packed = packed  # Stores slice

    @property
    def med(self) -> int:
        return unpack('!L', self._packed)[0]  # Parses on access
```

---

## When to Use Each Pattern

**Use Wire Container when:**
- Receiving data from network
- Forwarding data without modification
- Sending to peer with same capabilities
- Memory efficiency is critical

**Use Collection when:**
- Building new messages
- Modifying existing data
- Need to add/remove items
- Sending to peer with different capabilities
- Generating wire format with defaults/transformation

---

## Related Documentation

- `WIRE_SEMANTIC_SEPARATION.md` - Comprehensive design principles
- `PACKED_BYTES_FIRST_PATTERN.md` - NLRI implementation details
- `BUFFER_SHARING_AND_CACHING.md` - Memory optimization
- `plan/wire-semantic-separation.md` - Refactoring plan

---

**Updated:** 2025-12-07
