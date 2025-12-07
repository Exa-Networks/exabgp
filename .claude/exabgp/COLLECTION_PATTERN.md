# Collection Pattern Reference

**Purpose:** Document the Wire Container vs Semantic Container pattern used in ExaBGP.

---

## Overview

The codebase uses two complementary patterns for data containers:

1. **Wire Container** - stores raw `_packed` bytes, yields objects with buffer slices
2. **Semantic Container (Collection)** - stores parsed objects, used for building/modification

---

## Pattern Definitions

### Wire Container Pattern

**Purpose:** Efficient storage and transmission of wire-format data.

```python
class WireContainer:
    """Stores raw bytes, provides lazy access to semantic values."""

    def __init__(self, packed: bytes, context: Context | None = None) -> None:
        self._packed = packed      # Canonical representation
        self._context = context    # For lazy parsing
        self._parsed = None        # Cache for semantic container

    @property
    def packed(self) -> bytes:
        """Raw wire bytes."""
        return self._packed

    def __iter__(self) -> Iterator[Item]:
        """Iterate over items by parsing _packed lazily.

        Yields Item objects that store buffer slices.
        Each item parses its data dynamically via properties.
        """
        ...

    def to_collection(self) -> SemanticContainer:
        """Convert to semantic container for modification."""
        if self._parsed is None:
            self._parsed = SemanticContainer.from_wire(self._packed, self._context)
        return self._parsed
```

### Collection Pattern (Semantic Container)

**Purpose:** Building, modifying, and generating wire format from semantic data.

```python
class SemanticContainer:
    """Stores semantic objects, provides factory methods for creation."""

    def __init__(self) -> None:
        self._items: dict[int, Item] = {}

    def add(self, item: Item) -> None:
        """Add item to collection."""
        self._items[item.ID] = item

    def pack(self, context: Context) -> bytes:
        """Generate wire format from semantic data.

        This is a FACTORY operation - may generate defaults,
        transform data based on context, fragment messages.
        This is acceptable for Collection pattern.
        """
        result = b''
        for code in sorted(self._items):
            result += self._items[code].pack(context)
        return result

    @classmethod
    def from_wire(cls, data: bytes, context: Context) -> 'SemanticContainer':
        """Parse wire bytes into semantic container."""
        instance = cls()
        # Parse and add items
        return instance
```

---

## Key Distinction

| Aspect | Wire Container | Semantic Container (Collection) |
|--------|---------------|--------------------------------|
| Storage | `_packed` bytes | Dict of objects |
| Primary use | Receiving, forwarding | Building, modifying |
| pack() behavior | Return `_packed` | Factory - may generate/transform |
| Iteration | Parse `_packed` lazily, yield objects with slices | Iterate dict |
| Modification | Create new Collection | Direct add/remove |

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

## Existing Implementations

| Wire Container | Semantic Container | Status |
|---------------|-------------------|--------|
| `Attributes` | `AttributeCollection` | Implemented |
| `Update` | `UpdateCollection` | Implemented |
| `Flow` | `FlowRuleCollection` | TODO - Flow uses Settings, needs Collection |
| `MPRNLRI` (dual-mode) | `MPRNLRI` (dual-mode) | Implemented |
| `MPURNLRI` (dual-mode) | `MPURNLRI` (dual-mode) | Implemented |

---

## Pattern Application Examples

### Attributes / AttributeCollection

```
Wire Format:           Semantic Format:
Attributes             AttributeCollection
(_packed bytes)        (dict of Attribute objects)
    |                        ^
    |                        |
    +---> __iter__() --------+  (yields Attribute with buffer slice)
    |
    +---> to_collection() ---+  (full parse to dict)
    |
from_set() <-----------------+  (pack collection to bytes)
```

**Attributes (Wire Container):**
- `__init__(packed, context)` - stores raw bytes
- `__iter__()` - yields Attribute objects with buffer slices
- `to_collection()` - converts to AttributeCollection for modification
- `packed` property - returns raw bytes

**AttributeCollection (Semantic Container):**
- `add(attribute)` - add attribute to dict
- `pack_attribute(negotiated)` - factory that generates wire format with defaults
- `from_attributes(attrs, negotiated)` - create from wire Attributes

### Update / UpdateCollection

**Update (Wire Container):**
- `__init__(packed)` - stores raw UPDATE payload
- `parse(negotiated)` - lazy parse to UpdateCollection
- `pack_message()` - return packed bytes with header

**UpdateCollection (Semantic Container):**
- `__init__(announces, withdraws, attributes)` - stores semantic data
- `messages(negotiated)` - factory that generates wire format with fragmentation
- `pack_messages()` - yields Update wire containers

### Flow (Needs Collection)

**Current state:**
- `Flow` is dual-mode (stores `_packed` OR builds from rules)
- `FlowSettings` for deferred construction
- `_pack_from_rules()` does factory work (EOL bits, ordering)

**TODO:**
- Create `FlowRuleCollection` for rule preparation
- Move factory logic from `_pack_from_rules()` to Collection

---

## Iterator Pattern

The Wire Container iterator yields objects that store buffer slices:

```python
def __iter__(self) -> Iterator[Attribute]:
    """Iterate over Attribute objects with buffer slices."""
    data = memoryview(self._packed)  # Zero-copy slicing
    while data:
        flag, code = data[0], data[1]
        # ... extract length and offset ...

        value_slice = data[offset:offset + length]

        # Attribute stores slice, parses on property access
        attr = Attribute.unpack(code, flag, value_slice, self._context)
        yield attr

        data = data[offset + length:]
```

**Key principle:** Objects store buffer slices, parse on property access:

```python
class MED(Attribute):
    def __init__(self, packed: Buffer) -> None:
        self._packed = packed  # Stores slice, no parsing

    @property
    def med(self) -> int:
        return unpack('!L', self._packed)[0]  # Parses on access
```

---

## When to Use Each Pattern

**Use Wire Container when:**
- Receiving data from network
- Forwarding data without modification
- Memory efficiency is critical
- Only need to access a few fields

**Use Collection when:**
- Building new messages
- Modifying existing data
- Need to add/remove items
- Generating wire format with defaults/transformation

---

**Updated:** 2025-12-07
