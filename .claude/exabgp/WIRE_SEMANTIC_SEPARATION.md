# Wire vs Semantic Container Separation

**When to read:** Before modifying Update, Attribute, NLRI, or their Collection counterparts
**Related:** `COLLECTION_PATTERN.md`, `PACKED_BYTES_FIRST_PATTERN.md`

---

## Core Principle

ExaBGP separates **Wire Containers** (immutable, bytes-first) from **Semantic Containers** (Collections - mutable, for transformations).

| Aspect | Wire Container | Semantic Container (Collection) |
|--------|---------------|--------------------------------|
| **Examples** | `Update`, `Attribute`, `NLRI` | `UpdateCollection`, `AttributeCollection`, `NLRICollection` |
| **Mutability** | Immutable after creation | Mutable - add/remove/modify |
| **Storage** | `_packed` bytes + `_negotiated` | Parsed objects in dict/list |
| **pack()** | Return `_packed` directly | Factory - creates new Wire Container |
| **Primary use** | Receiving, forwarding, sending | Building, modifying, transforming |

---

## Why This Matters

### Scenario: Route Reflection

When a route reflector receives an UPDATE from Peer A and forwards to Peer B:

**Optimal path (same capabilities):**
```python
update_a = Update(wire_bytes, negotiated_a)
# Peer B has same capabilities - forward directly
socket_b.write(update_a.pack_message())  # Zero-copy, no parsing
```

**Transformation path (different capabilities):**
```python
update_a = Update(wire_bytes, negotiated_a)
collection = update_a.parse()           # Decode with caps_a
update_b = collection.pack(negotiated_b) # Re-encode with caps_b
socket_b.write(update_b.pack_message())
```

The Wire Container enables zero-copy forwarding when no transformation is needed.

---

## Wire Container Requirements

### 1. Immutable After Creation

```python
class Update(Message):
    """Immutable wire-format container."""

    __slots__ = ('_packed', '_negotiated')

    def __init__(self, packed: Buffer, negotiated: Negotiated) -> None:
        self._packed = bytes(packed)      # Canonical wire representation
        self._negotiated = negotiated     # Capabilities that created this
```

### 2. Store Originating Capabilities

The `_negotiated` reference is essential for correct parsing:
- ASN format (2-byte vs 4-byte)
- ADD-PATH support
- Address family capabilities
- Extended message support

```python
def parse(self) -> UpdateCollection:
    """Parse using stored negotiated capabilities."""
    return UpdateCollection._parse_payload(self._packed, self._negotiated)
```

### 3. No Semantic Delegation

Wire containers should NOT expose semantic properties:

```python
# WRONG - Update delegates to cached parsed data
class Update:
    @property
    def announces(self) -> list[NLRI]:
        return self._parsed.announces  # Leaks semantic into wire

# CORRECT - Callers explicitly parse
update = receive_update(...)
collection = update.parse()
for nlri in collection.announces:
    process(nlri)
```

### 4. No Caching of Parsed Data

Each `parse()` call returns a fresh collection:

```python
# WRONG - caches parsed data
def parse(self, negotiated: Negotiated) -> UpdateCollection:
    if self._parsed is None:
        self._parsed = UpdateCollection._parse_payload(...)
    return self._parsed

# CORRECT - returns fresh collection
def parse(self) -> UpdateCollection:
    return UpdateCollection._parse_payload(self._packed, self._negotiated)
```

---

## Semantic Container Requirements

### 1. Mutable

```python
class UpdateCollection:
    """Mutable semantic container."""

    def __init__(self, announces: list[NLRI], withdraws: list[NLRI], attributes: AttributeCollection):
        self._announces = announces    # Can be modified
        self._withdraws = withdraws
        self._attributes = attributes

    def add_announce(self, nlri: NLRI) -> None:
        self._announces.append(nlri)

    def remove_withdraw(self, nlri: NLRI) -> None:
        self._withdraws.remove(nlri)
```

### 2. Factory pack() Method

`pack()` creates a NEW Wire Container, potentially transforming for target capabilities:

```python
def pack(self, negotiated: Negotiated) -> Update:
    """Create wire-format Update for target peer.

    May transform data based on target capabilities:
    - Convert ASN format
    - Add/remove ADD-PATH
    - Fragment if message too large
    """
    wire_bytes = self._serialize(negotiated)
    return Update(wire_bytes, negotiated)
```

### 3. Handles Capability Transformation

The Collection is where capability differences are resolved:

```python
# Received from 4-byte ASN peer
update_from_4byte = Update(data, negotiated_4byte)
collection = update_from_4byte.parse()

# Send to 2-byte ASN peer - Collection handles conversion
update_for_2byte = collection.pack(negotiated_2byte)
# AS_PATH automatically converted to AS4_PATH + AS_PATH format
```

---

## Pattern Summary

```
              RECEIVE                              SEND
                 |                                   ^
                 v                                   |
          +-------------+                    +-------------+
          |   Update    |                    |   Update    |
          | (immutable) |                    | (immutable) |
          |  _packed    |                    |  _packed    |
          | _negotiated |                    | _negotiated |
          +-------------+                    +-------------+
                 |                                   ^
                 | .parse()                          | .pack(negotiated)
                 v                                   |
          +------------------+              +------------------+
          | UpdateCollection | ──────────> | UpdateCollection |
          |    (mutable)     |   modify    |    (mutable)     |
          |   _announces     |             |   _announces     |
          |   _withdraws     |             |   _withdraws     |
          |   _attributes    |             |   _attributes    |
          +------------------+              +------------------+
```

---

## Hierarchy of Containers

The same pattern applies at multiple levels:

```
Update                    UpdateCollection
  |                           |
  +-- Attribute[]            +-- AttributeCollection (dict)
        |                           |
        +-- _packed                +-- Attribute objects
                                        |
                                        +-- _packed
```

Each level follows the same principle:
- Wire level: immutable, bytes + negotiated
- Semantic level: mutable, for building/transforming

---

## Implementation Status

| Wire Container | Semantic Container | Status |
|---------------|-------------------|--------|
| `Update` | `UpdateCollection` | Needs refactoring - has `_parsed` cache |
| `Attribute` subclasses | `AttributeCollection` | Mostly compliant |
| `NLRI` subclasses | `NLRICollection`/`MPNLRICollection` | Mostly compliant |
| `MPRNLRI` | `MPNLRICollection` | Dual-mode, needs review |
| `MPURNLRI` | `MPNLRICollection` | Dual-mode, needs review |

---

## Common Mistakes

### 1. Storing Parsed Data in Wire Container

```python
# WRONG
class Update:
    def __init__(self, packed, negotiated):
        self._packed = packed
        self._parsed = None  # Cache - breaks immutability
```

### 2. Delegation Properties on Wire Container

```python
# WRONG
class Update:
    @property
    def announces(self):
        return self._parsed.announces  # Should not exist
```

### 3. Parsing Without Stored Negotiated

```python
# WRONG
def parse(self, negotiated):  # Caller must provide
    ...

# CORRECT
def parse(self):  # Uses stored _negotiated
    return UpdateCollection._parse_payload(self._packed, self._negotiated)
```

### 4. Modifying Wire Container After Creation

```python
# WRONG
update = Update(data, negotiated)
update.add_nlri(new_nlri)  # Wire containers are immutable

# CORRECT
collection = update.parse()
collection.add_announce(new_nlri)  # Collections are mutable
new_update = collection.pack(negotiated)
```

---

## Related Documentation

- `COLLECTION_PATTERN.md` - Iterator and factory patterns
- `PACKED_BYTES_FIRST_PATTERN.md` - NLRI packed-bytes implementation
- `BUFFER_SHARING_AND_CACHING.md` - Memory optimization patterns

---

**Updated:** 2025-12-19
