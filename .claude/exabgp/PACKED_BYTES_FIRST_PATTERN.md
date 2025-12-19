# Packed-Bytes-First Pattern for NLRI Classes

**When to read:** Before converting NLRI classes to the packed-bytes-first pattern
**Reference implementation:** `src/exabgp/bgp/message/update/nlri/vpls.py`

---

## Overview

The packed-bytes-first pattern optimizes NLRI handling by:
1. **Avoiding `bytes()` allocation** - Wire data stored as-is, not converted
2. **Lazy unpacking** - Fields extracted only when accessed
3. **Zero-copy routing** - Messages forwarded without re-parsing/re-packing

### Critical Rule: Keep the Length Prefix

**The stored `_packed` bytes MUST include the BGP length prefix from the wire format.**

When BGP encodes an NLRI, it typically prepends a length field (usually 2 bytes). This length prefix MUST be stored as part of `_packed`:

```python
# In unpack_nlri():
packed = bytes(data[0 : 2 + length])  # Include length prefix (bytes 0-1)
                                       # NOT data[2 : 2 + length]
```

**Why?** So that `pack_nlri()` can return `_packed` directly without reconstructing the length prefix. This enables true zero-copy forwarding.

### The Problem

Traditional NLRI parsing:
```python
def __init__(self, rd, endpoint, base, offset, size):
    self.rd = rd              # RouteDistinguisher object created
    self.endpoint = endpoint  # int extracted from bytes
    self.base = base          # int extracted from bytes
    # ... every field parsed immediately
```

**Issues:**
- Every received NLRI allocates multiple Python objects
- Fields are unpacked even if never accessed (e.g., route-reflector forwarding)
- Re-packing requires re-computing the wire format

### The Solution

Store the original wire bytes, unpack on demand via `@property` methods:
```python
def __init__(self, packed: bytes | None):
    self._packed = packed  # Store wire bytes directly
    # Fields are NOT stored as instance attributes
    # Instead, create @property methods that unpack from _packed on access
```

**Key insight:** Instead of storing parsed fields as instance attributes, you MUST create `@property` methods for each field. These properties unpack the data from `_packed` only when accessed.

---

## Two Entry Points: unpack vs make

There are exactly two ways to create an NLRI:

### 1. `unpack_nlri()` - From existing wire data
Used when receiving BGP messages. Takes existing `Buffer` data and passes it directly to `__init__`:
```python
@classmethod
def unpack_nlri(cls, afi, safi, data: Buffer, action, addpath, negotiated):
    # data is existing wire bytes - we don't modify it, just store it
    packed = bytes(data[0:total_length])  # Include length prefix!
    return cls(packed), data[total_length:]
```

### 2. `make_xxx()` - From components
Used when creating NLRI from configuration or programmatically. Builds new packed bytes, then passes to `__init__`:
```python
@classmethod
def make_vpls(cls, rd, endpoint, base, offset, size, action=Action.ANNOUNCE):
    # Build NEW packed bytes from components
    packed = (
        b'\x00\x11'  # length prefix
        + rd.pack_rd()
        + pack('!HHH', endpoint, offset, size)
        + pack('!L', (base << 4) | 0x1)[1:]
    )
    instance = cls(packed)
    instance.action = action
    return instance
```

**Both paths end at `__init__(packed: bytes)`** - the constructor always receives complete packed wire data.

---

## Core Principle: Always Require Packed Data

**The `_packed` bytes are ALWAYS required.** There is no "builder mode" - all NLRI instances must be created with packed wire bytes.

This means:
- `__init__` takes `packed: bytes` (NOT `bytes | None`)
- Properties unpack directly from `_packed` without conditional checks
- Factory methods (`make_xxx()`) pack the data immediately
- Configuration parsing uses factory methods, not empty constructors

---

## Required: @property Methods for Field Access

**You MUST create `@property` methods for every field that needs to be accessed.**

This is the core of the pattern - fields are not stored as regular attributes. Instead:

```python
# WRONG - Don't store fields directly in __init__:
def __init__(self, packed):
    self.rd = RouteDistinguisher(packed[2:10])      # Parses immediately!
    self.endpoint = unpack('!H', packed[10:12])[0]  # Parses immediately!

# CORRECT - Store packed bytes, create @property for each field:
def __init__(self, packed: bytes):
    self._packed = packed  # Just store the bytes - ALWAYS required

@property
def rd(self) -> RouteDistinguisher:
    return RouteDistinguisher(self._packed[2:10])  # Parses only when accessed

@property
def endpoint(self) -> int:
    return unpack('!H', self._packed[10:12])[0]  # Parses only when accessed
```

**Every semantic field needs its own `@property`** that unpacks from `_packed` on access. No conditional checks needed since `_packed` is always present.

---

## 🚨 NLRI Immutability Rule

**NLRI instances are IMMUTABLE after creation. NO SETTERS ALLOWED.**

```python
# ❌ WRONG - Never add property setters for NLRI fields
@path_info.setter
def path_info(self, value: PathInfo) -> None:
    self._packed = ...  # FORBIDDEN

# ❌ WRONG - Never assign to NLRI fields after creation
nlri.labels = Labels.make_labels([100])  # FORBIDDEN
nlri.rd = RouteDistinguisher(...)  # FORBIDDEN
nlri.path_info = PathInfo(...)  # FORBIDDEN

# ✅ CORRECT - Use factory methods with all values upfront
nlri = Label.from_cidr(cidr, afi, labels=Labels.make_labels([100]))
nlri = IPVPN.from_settings(settings)  # settings has all values
```

**Why immutability?**
1. **Wire format integrity:** `_packed` is the source of truth; modifications would desync properties
2. **Thread safety:** Immutable objects are inherently thread-safe
3. **Hash stability:** NLRI are used as dict keys; mutable objects break hashing
4. **Simplicity:** No need to handle partial construction states

**Backward compatibility during migration:**
- Existing code that assigns to NLRI fields will break - this is intentional
- Update callers to use factory methods with all values provided upfront
- If code currently does `nlri.labels = X`, change to `from_cidr(..., labels=X)`

---

## Implementation Pattern

### 1. Class Structure

```python
@NLRI.register(AFI.xxx, SAFI.yyy)
class MyNLRI(NLRI):
    """NLRI using packed-bytes-first pattern.

    Stores wire bytes directly, unpacks fields on @property access.
    """

    __slots__ = ()  # No field storage needed - everything is in _packed

    # Wire format length (including any length prefix)
    PACKED_LENGTH = N  # Document the byte breakdown

    def __init__(self, packed: bytes) -> None:
        """Create from packed wire-format bytes.

        Args:
            packed: N bytes wire format (ALWAYS required)
        """
        NLRI.__init__(self, AFI.xxx, SAFI.yyy)
        self.action = Action.ANNOUNCE
        self.nexthop = IP.NoNextHop

        self._packed: bytes = packed  # ALWAYS required, never None
```

### 2. Factory Method

```python
    @classmethod
    def make_nlri(
        cls,
        field1: Type,
        field2: Type,
        # ... all semantic fields
        action: Action = Action.ANNOUNCE,
        addpath: PathInfo = PathInfo.DISABLED,
    ) -> 'MyNLRI':
        """Factory method to create from components.

        Packs fields into wire format immediately.
        Used by configuration parsing.
        """
        packed = (
            pack('!H', length)  # Include length prefix if wire format has one
            + field1.pack()
            + pack('!H', field2)
            # ...
        )
        instance = cls(packed)
        instance.action = action
        instance.addpath = addpath
        return instance
```

**No `make_empty()` needed** - configuration parsing uses `make_nlri()` with all fields.

### 3. Properties with Lazy Unpacking

```python
    @property
    def field1(self) -> Type:
        """Field description - unpacked from wire bytes on access."""
        return Type(self._packed[START:END])

    @property
    def field2(self) -> int:
        """Field description - unpacked from wire bytes on access."""
        return unpack('!H', self._packed[START:END])[0]
```

**Key points:**
- No conditional checks - `_packed` is always present
- No setters needed - NLRI is effectively immutable after creation
- Offsets account for any length prefix stored in `_packed`

### 4. Pack Methods

```python
    def _pack_nlri_simple(self) -> Buffer:
        """Pack NLRI - returns stored wire bytes directly (zero-copy)."""
        return self._packed

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        # Add addpath handling if needed
        return self._pack_nlri_simple()
```

**No conditional logic** - just return `_packed` directly.

### 5. Unpack Method

```python
    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple['MyNLRI', Buffer]:
        # Validate minimum length
        if len(data) < 2:
            raise Notify(3, 10, f'NLRI too short: need at least 2 bytes, got {len(data)}')

        # Read length prefix (bytes 0-1)
        (length,) = unpack('!H', bytes(data[0:2]))
        total_length = 2 + length  # length prefix + payload

        if len(data) < total_length:
            raise Notify(3, 10, 'NLRI length mismatch')

        # CRITICAL: Store COMPLETE wire format INCLUDING length prefix
        # Start from byte 0, not byte 2!
        packed = bytes(data[0:total_length])  # Includes length prefix
        nlri = cls(packed)
        nlri.action = action

        return nlri, data[total_length:]
```

**CRITICAL:** The `packed` bytes MUST start from `data[0]`, not `data[2]`. This includes the length prefix so that `pack_nlri()` can return `_packed` directly without reconstructing it.

```python
# WRONG - strips length prefix, requires reconstruction during pack:
packed = bytes(data[2 : 2 + length])

# CORRECT - keeps length prefix, enables zero-copy pack:
packed = bytes(data[0 : 2 + length])
```

---

## Byte Offset Reference

When the wire format includes a length prefix, all property offsets shift:

```
Wire format: [length(2)] [field1(8)] [field2(2)] [field3(2)]
             ^0          ^2          ^10         ^12

# Property implementations:
@property
def field1(self):
    return Type(self._packed[2:10])   # After length prefix

@property
def field2(self):
    return unpack('!H', self._packed[10:12])[0]
```

---

## VPLS Wire Format Reference

```
VPLS wire format (19 bytes total):
[length(2)] [RD(8)] [endpoint(2)] [offset(2)] [size(2)] [base(3)]
 0:2         2:10    10:12         12:14       14:16     16:19

PACKED_LENGTH = 19
```

**Ideal properties (no conditionals):**
```python
@property
def rd(self) -> RouteDistinguisher:
    return RouteDistinguisher(self._packed[2:10])

@property
def endpoint(self) -> int:
    return unpack('!H', self._packed[10:12])[0]

@property
def offset(self) -> int:
    return unpack('!H', self._packed[12:14])[0]

@property
def size(self) -> int:
    return unpack('!H', self._packed[14:16])[0]

@property
def base(self) -> int:
    return unpack('!L', b'\x00' + self._packed[16:19])[0] >> 4
```

**Note:** The current VPLS implementation in `vpls.py` still has builder mode (conditional checks) because the configuration parsers assign fields incrementally. New NLRI conversions should use this simplified pattern and update their configuration parsers to use `make_xxx()` with all fields collected upfront.

---

## Configuration Parser Refactoring

The current `RouteBuilder` pattern uses `nlri_factory` to create an empty NLRI, then assigns fields via `nlri-set` actions:

```python
# Current pattern (breaks immutability):
nlri_factory=_vpls_factory,  # Returns VPLS.make_empty()
assign={'endpoint': 'endpoint', 'base': 'base', ...}  # Fields set later
```

To support the simplified packed-first pattern, the configuration parser needs **deferred construction**:

1. **Collect values** during parsing into a temporary dict
2. **Call factory** at the end with all collected values

```python
# Desired pattern:
class DeferredRouteBuilder:
    def parse(self, tokeniser):
        values = {}
        # Parse all tokens, collect values
        for token in tokens:
            values[field_name] = parsed_value
        # Create NLRI with all values at once
        nlri = VPLS.make_vpls(
            rd=values['rd'],
            endpoint=values['endpoint'],
            base=values['base'],
            offset=values['offset'],
            size=values['size'],
        )
        return Route(nlri, attributes)
```

This is a larger refactoring task tracked separately. For now, NLRI classes that need configuration parsing support may keep `make_empty()` as a transitional measure.

---

## Conversion Checklist

When converting an NLRI class to packed-bytes-first:

### 1. Analyze Wire Format
- [ ] Document total byte length including any length prefix
- [ ] Map each field to byte offsets
- [ ] Note any variable-length fields (more complex handling needed)

### 2. Update Class Structure
- [ ] Add `PACKED_LENGTH` constant with byte breakdown comment
- [ ] Change `__init__` to accept `packed: bytes` (NOT `bytes | None`)
- [ ] Store `self._packed = packed` (always required)
- [ ] Remove all `_field` storage variables - not needed
- [ ] Update `__slots__` to be empty or minimal

### 3. Add Factory Method
- [ ] `make_xxx()` - creates from components, packs immediately
- [ ] No `make_empty()` needed

### 4. Convert Fields to @property Methods (CRITICAL)
- [ ] **Remove all direct field assignments from `__init__`** (e.g., remove `self.rd = ...`)
- [ ] **Create `@property` getter for EACH field** that unpacks from `_packed`
- [ ] **No setters needed** - NLRI is immutable after creation
- [ ] Properties simply return: `return Type(self._packed[START:END])`

### 5. Update Pack/Unpack
- [ ] `_pack_nlri_simple()`: simply `return self._packed`
- [ ] `unpack_nlri()`: store complete wire bytes including length prefix

### 6. Update Copy Methods
- [ ] `__copy__`: copy `_packed` only
- [ ] `__deepcopy__`: copy `_packed` only (bytes are immutable)

### 7. Update Configuration Parser
- [ ] Use `make_xxx()` factory method with all fields
- [ ] No field assignment after creation

### 8. Run Tests
- [ ] Unit tests for pack/unpack round-trip
- [ ] Functional encoding tests
- [ ] Configuration parsing tests

---

## Benefits Summary

| Scenario | Traditional | Packed-First |
|----------|-------------|--------------|
| Receive & forward | Parse all fields, re-pack | Zero-copy, return `_packed` |
| Receive & inspect one field | Parse all fields | Unpack only that field |
| Memory per NLRI | Multiple objects | Single bytes object |
| Configuration | Direct construction | Factory method packs immediately |
| Code complexity | Conditionals everywhere | Simple `@property` returns |

---

## When NOT to Use

- **Variable-length NLRI** with complex structure (e.g., FlowSpec with rules)
- **NLRI that's always fully inspected** (no benefit from lazy unpacking)
- **NLRI with negotiated-dependent packing** (packed format varies)

For these cases, document why packed-first doesn't apply.

---

## Related Documentation

- `.claude/exabgp/BUFFER_SHARING_AND_CACHING.md` - How buffer sharing and caching complement packed-bytes-first
- `.claude/exabgp/PEP688_BUFFER_PROTOCOL.md` - Python 3.12 Buffer protocol details
- `.claude/exabgp/NLRI_CLASS_HIERARCHY.md` - Class hierarchy and slot inheritance

---

**Updated:** 2025-12-19
