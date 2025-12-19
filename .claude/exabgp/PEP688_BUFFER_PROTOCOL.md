# PEP 688: Python 3.12 Buffer Protocol

**Reference:** https://peps.python.org/pep-0688/
**Python Version:** 3.12+
**Status:** Final (March 2023)

---

## Quick Summary

PEP 688 makes the C buffer protocol accessible from Python, providing:
1. `collections.abc.Buffer` - ABC for type annotations and runtime checks
2. `__buffer__` / `__release_buffer__` - Python-level protocol methods
3. `inspect.BufferFlags` - IntFlag enum for buffer flags

---

## Key Usage for ExaBGP

### Type Annotations

```python
from collections.abc import Buffer

def process_data(data: Buffer) -> bytes:
    """Accept any buffer-supporting type."""
    return bytes(data)

# Accepts: bytes, bytearray, memoryview, array.array, etc.
```

### Runtime Checks

```python
from collections.abc import Buffer

isinstance(b"hello", Buffer)      # True
isinstance(memoryview(b"x"), Buffer)  # True
isinstance("hello", Buffer)       # False (str is NOT a buffer)
issubclass(bytes, Buffer)         # True
issubclass(bytearray, Buffer)     # True
```

### Why Buffer Instead of bytes

| Type | Supports Buffer Protocol | Use Case |
|------|-------------------------|----------|
| `bytes` | Yes | Immutable byte sequences |
| `bytearray` | Yes | Mutable byte sequences |
| `memoryview` | Yes | Zero-copy slicing |
| `array.array` | Yes | Typed arrays |
| `str` | **NO** | Text (not bytes!) |

Using `Buffer` in type hints:
- ✅ Accepts all buffer types including `memoryview`
- ✅ Zero-copy operations possible
- ✅ Explicit about intent

Using `bytes` in type hints:
- ❌ Technically only accepts `bytes`
- ❌ Forces callers to convert `memoryview` to `bytes`
- ❌ Loses zero-copy benefits

---

## ExaBGP-Specific Patterns

### Wire Data Handling

```python
from collections.abc import Buffer

class Message:
    @classmethod
    def unpack(cls, data: Buffer, negotiated: Negotiated) -> 'Message':
        # data can be bytes, memoryview, or any buffer
        # Use memoryview for zero-copy slicing
        view = memoryview(data)
        header = view[:4]
        payload = view[4:]
        ...
```

### Converting When Needed

```python
# When you need actual bytes (for hashing, dict keys, etc.)
data_bytes = bytes(data)

# When you need a view (for slicing)
view = memoryview(data)
```

### Length Checking

```python
# len() works on all Buffer types
if len(data) < 4:
    raise ValueError("Too short")

# Indexing works on all Buffer types
first_byte = data[0]
```

---

## Common Operations on Buffer Types

| Operation | Works on Buffer? | Notes |
|-----------|-----------------|-------|
| `len(data)` | ✅ | All buffers support length |
| `data[0]` | ✅ | Indexing returns int |
| `data[0:4]` | ✅ | Slicing returns same type |
| `bytes(data)` | ✅ | Convert to bytes |
| `memoryview(data)` | ✅ | Create view |
| `data + other` | ⚠️ | Only bytes/bytearray |
| `data.decode()` | ⚠️ | Only bytes/bytearray |
| `hash(data)` | ⚠️ | Only bytes (immutable) |

---

## Implementation Pattern for ExaBGP

### Before (bytes only)

```python
def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> Attribute:
    if len(data) < 4:
        raise ValueError("Too short")
    value = struct.unpack('!I', data[:4])[0]
    return cls(data)
```

### After (Buffer-aware)

```python
from exabgp.util.types import Buffer  # ExaBGP compatibility wrapper

def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> Attribute:
    if len(data) < 4:
        raise ValueError("Too short")
    # struct.unpack accepts Buffer directly
    value = struct.unpack('!I', data[:4])[0]
    # Store as bytes if immutability needed
    return cls(bytes(data))
```

### ExaBGP Import Pattern

ExaBGP uses a compatibility wrapper for Buffer:

```python
from exabgp.util.types import Buffer  # Preferred import for ExaBGP code
```

This wrapper handles type checking mode differences and provides consistent behavior.

---

## When to Convert to bytes

Convert Buffer to bytes when:
1. **Hashing required** - `hash()` only works on immutable types
2. **Dict/set key** - Must be hashable
3. **Storing long-term** - memoryview may become invalid
4. **API requires bytes** - External interface expects bytes

Keep as Buffer when:
1. **Passing to struct.unpack** - Accepts Buffer directly
2. **Creating memoryview slices** - Zero-copy
3. **Passing to other Buffer-accepting functions**

---

## Reference

- PEP 688: https://peps.python.org/pep-0688/
- Python 3.12 docs: https://docs.python.org/3.12/library/collections.abc.html#collections.abc.Buffer

---

**Updated:** 2025-12-19
