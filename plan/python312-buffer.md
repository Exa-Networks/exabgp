# Python 3.12+ Migration with Buffer Protocol for BGP Parsing

**Status:** Planning (not started)
**Priority:** Future optimization
**Created:** 2025-12-04

---

## Goal

Migrate ExaBGP to Python 3.12+ minimum and leverage the buffer protocol (`memoryview`) to reduce memory consumption during BGP message parsing.

---

## Current State

### Python Version
- **Current minimum:** Python 3.10
- **Supported:** 3.10, 3.11, 3.12, 3.13
- **Location:** `pyproject.toml` line 9: `requires-python = ">=3.10,<3.14"`

### Current Byte Handling
- All parsing uses `bytes` objects with slice operations
- No `memoryview` or buffer protocol usage
- Each slice creates a new bytes object reference
- Pattern: `data = data[offset:]` repeated throughout parsing

### Memory Pattern Issues
1. **Label padding:** `bytes([0]) + bgp[:3]` creates new 4-byte object per label
2. **Slice reassignment loops:** Each `data = data[n:]` creates intermediate objects
3. **UPDATE concatenation:** Progressive `announced += packed` is O(n) per append
4. **No zero-copy:** Despite CPython slice optimizations, object headers add ~56 bytes overhead each

---

## Proposed Changes

### Phase 1: Raise Python Minimum to 3.12

**Why 3.12?**
- Better `memoryview` support and performance
- `buffer` protocol improvements
- Type parameter syntax (`class Foo[T]:`)
- Better error messages for debugging
- f-string improvements

**Files to update:**
- `pyproject.toml` - Change `requires-python = ">=3.12,<3.14"`
- `.github/workflows/*.yml` - Update CI matrix
- `CLAUDE.md` - Update Python version references

**Syntax opportunities (optional):**
- Use type parameter syntax where applicable
- Use improved f-strings

---

### Phase 2: Introduce Buffer Protocol in Network Layer

**Target file:** `src/exabgp/reactor/network/connection.py`

**Current pattern:**
```python
def _reader(self, number: int) -> Iterator[bytes]:
    data = b''
    while len(data) < number:
        read = self.io.recv(number - len(data))
        data += read  # Creates new bytes each iteration
    yield data
```

**Proposed pattern:**
```python
def _reader(self, number: int) -> Iterator[memoryview]:
    buffer = bytearray(number)
    view = memoryview(buffer)
    offset = 0
    while offset < number:
        n = self.io.recv_into(view[offset:])
        offset += n
    yield view  # Zero-copy view of buffer
```

**Benefits:**
- `socket.recv_into()` writes directly to buffer (no intermediate allocation)
- Returns `memoryview` that can be sliced without copying
- Single allocation per message read

---

### Phase 3: Update Message Splitting

**Target file:** `src/exabgp/bgp/message/update/__init__.py`

**Current `split()` method (lines 98-126):**
```python
@staticmethod
def split(data: bytes) -> tuple[bytes, bytes, bytes]:
    len_withdrawn = unpack('!H', data[0:2])[0]
    withdrawn = data[2:len_withdrawn+2]  # Slice creates new object
    # ...
```

**Proposed pattern:**
```python
@staticmethod
def split(data: memoryview) -> tuple[memoryview, memoryview, memoryview]:
    len_withdrawn = int.from_bytes(data[0:2], 'big')  # No struct needed
    withdrawn = data[2:len_withdrawn+2]  # Zero-copy slice
    # ...
```

**Key changes:**
- Accept `memoryview` instead of `bytes`
- Use `int.from_bytes()` instead of `struct.unpack()` (cleaner, same performance)
- Return `memoryview` slices (zero-copy)

---

### Phase 4: Update NLRI Unpacking

**Target files:**
- `src/exabgp/bgp/message/update/nlri/inet.py`
- `src/exabgp/bgp/message/update/nlri/label.py`
- `src/exabgp/bgp/message/update/nlri/ipvpn.py`
- All other `nlri/*.py` files

**Current pattern (inet.py lines 273-350):**
```python
@classmethod
def unpack_nlri(cls, ..., bgp: bytes, ...) -> tuple[INET, bytes]:
    mask = bgp[0]
    bgp = bgp[1:]  # Creates new bytes object
    # ... repeated slicing
    return nlri, bgp
```

**Proposed pattern:**
```python
@classmethod
def unpack_nlri(cls, ..., bgp: memoryview, ...) -> tuple[INET, memoryview]:
    mask = bgp[0]
    bgp = bgp[1:]  # Zero-copy memoryview slice
    # ...
    return nlri, bgp
```

**Label optimization (inet.py line 297):**
```python
# Current (allocates 4-byte object per label):
label = int(unpack('!L', bytes([0]) + bgp[:3])[0])

# Proposed (zero allocation):
label = int.from_bytes(b'\x00' + bytes(bgp[:3]), 'big')
# Or better - bit shifting:
label = (bgp[0] << 16) | (bgp[1] << 8) | bgp[2]
```

---

### Phase 5: Update Attribute Parsing

**Target file:** `src/exabgp/bgp/message/update/attribute/attributes.py`

**Current `parse()` method (lines 276-407):**
```python
def parse(self, data: bytes, negotiated: Negotiated) -> Attributes:
    flag = data[0]
    aid = data[1]
    # ...
    attribute = data[:length]
    data = data[length:]
```

**Proposed pattern:**
```python
def parse(self, data: memoryview, negotiated: Negotiated) -> Attributes:
    flag = data[0]
    aid = data[1]
    # ...
    attribute = data[:length]  # Zero-copy slice
    data = data[length:]  # Zero-copy advance
```

---

### Phase 6: Update Packed Storage

**Issue:** NLRI classes store `_packed: bytes` for wire format.

**Options:**

**Option A: Keep bytes for storage, convert at boundaries**
```python
class INET(NLRI):
    def __init__(self, packed: bytes, ...):
        self._packed = packed  # Store as bytes (immutable, hashable)

    @classmethod
    def unpack_nlri(cls, ..., bgp: memoryview, ...) -> tuple[INET, memoryview]:
        # Convert memoryview to bytes only when storing
        nlri = cls(bytes(bgp[:size]), ...)
        return nlri, bgp[size:]
```

**Option B: Store memoryview, convert to bytes lazily**
```python
class INET(NLRI):
    def __init__(self, packed: bytes | memoryview, ...):
        self._packed_view = packed if isinstance(packed, memoryview) else memoryview(packed)
        self._packed_bytes: bytes | None = None

    @property
    def packed(self) -> bytes:
        if self._packed_bytes is None:
            self._packed_bytes = bytes(self._packed_view)
        return self._packed_bytes
```

**Recommendation:** Option A - simpler, maintains immutability guarantees, conversion cost is minimal for stored NLRIs.

---

## Files to Modify

### Core (must change):
| File | Changes |
|------|---------|
| `pyproject.toml` | Raise Python version |
| `connection.py` | Use `recv_into()`, return `memoryview` |
| `protocol.py` | Pass `memoryview` to message unpack |
| `message.py` | Accept `memoryview` in `unpack()` |
| `update/__init__.py` | `split()` and `unpack_message()` use memoryview |
| `attributes.py` | `parse()` uses memoryview |

### NLRI classes (all need signature changes):
| File | Status |
|------|--------|
| `nlri/nlri.py` | Base class signature |
| `nlri/inet.py` | Core IPv4/IPv6 |
| `nlri/label.py` | Labeled routes |
| `nlri/ipvpn.py` | VPNv4/v6 |
| `nlri/vpls.py` | VPLS |
| `nlri/rtc.py` | Route Target Constraint |
| `nlri/flow.py` | FlowSpec |
| `nlri/cidr.py` | CIDR helper |
| `nlri/evpn/*.py` | EVPN types (5 files) |
| `nlri/bgpls/*.py` | BGP-LS types (5 files) |
| `nlri/mup/*.py` | MUP types (4 files) |
| `nlri/mvpn/*.py` | MVPN types (3 files) |

### Attributes (signature changes):
| File | Status |
|------|--------|
| `attribute/attribute.py` | Base class |
| `attribute/mprnlri.py` | MP_REACH_NLRI |
| `attribute/mpurnlri.py` | MP_UNREACH_NLRI |
| `attribute/aspath.py` | AS_PATH parsing |
| `attribute/generic.py` | Unknown attributes |
| All other attribute files | ~20 files |

---

## Type Signature Changes

### Current:
```python
def unpack_nlri(cls, afi: AFI, safi: SAFI, bgp: bytes, ...) -> tuple[NLRI, bytes]:
def unpack_message(cls, data: bytes, negotiated: Negotiated) -> Update:
def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> Attribute:
```

### Proposed:
```python
def unpack_nlri(cls, afi: AFI, safi: SAFI, bgp: memoryview, ...) -> tuple[NLRI, memoryview]:
def unpack_message(cls, data: memoryview, negotiated: Negotiated) -> Update:
def unpack_attribute(cls, data: memoryview, negotiated: Negotiated) -> Attribute:
```

### Type alias (optional):
```python
from collections.abc import Buffer
# or
type BGPData = bytes | memoryview
```

---

## Testing Strategy

1. **Unit tests:** All existing tests should pass with memoryview inputs
2. **Functional tests:** 72 encoding + decoding tests must pass
3. **Memory benchmarks:** Measure before/after with large UPDATE messages
4. **Stress tests:** Process 100k routes, compare memory usage

### Benchmark scenarios:
- Single UPDATE with 1000 IPv4 prefixes
- Single UPDATE with 100 VPNv4 routes (labels + RD)
- Full table (800k routes) memory comparison

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| memoryview not hashable | Convert to bytes when storing in dicts/sets |
| memoryview becomes invalid if buffer reused | Don't reuse network buffer until message fully parsed |
| Performance regression in hot paths | Benchmark before/after, profile |
| Breaking change for external API consumers | Document in release notes |
| Increased code complexity | Good abstractions, clear documentation |

---

## Benefits

1. **Memory reduction:** ~50-70% less memory for large UPDATE messages
2. **Faster parsing:** No intermediate allocations in parsing loops
3. **Modern Python:** Access to 3.12+ features
4. **Better type hints:** Buffer protocol types
5. **Foundation for future:** Enables further optimizations (async buffer pools)

---

## Non-Goals (This Plan)

- Async-only mode (keep dual generator/async support)
- Complete rewrite of message generation (pack methods)
- External API changes beyond type hints
- Support for Python < 3.12

---

## Implementation Order

1. **Raise Python version** (pyproject.toml, CI) - 1 file
2. **Network layer** (connection.py) - 1 file
3. **Protocol dispatch** (protocol.py, message.py) - 2 files
4. **UPDATE splitting** (update/__init__.py) - 1 file
5. **Attribute parsing** (attributes.py + individual) - ~25 files
6. **NLRI unpacking** (all nlri/*.py) - ~25 files
7. **Testing and benchmarks** - verify all tests pass
8. **Documentation** - update CLAUDE.md, release notes

**Estimated scope:** ~55 files, medium complexity refactor

---

## Related Plans

- `plan/packed-attribute.md` - Packed-bytes-first pattern (foundation for this work)
- `plan/todo.md` - Overall quality improvements

---

## References

- [PEP 688 - Buffer Protocol](https://peps.python.org/pep-0688/)
- [Python 3.12 Release Notes](https://docs.python.org/3.12/whatsnew/3.12.html)
- [memoryview documentation](https://docs.python.org/3/library/stdtypes.html#memoryview)
