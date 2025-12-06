# Python 3.12+ Migration with Buffer Protocol for BGP Parsing

**Status:** Phase 2.5 - ✅ COMPLETED - Two-buffer architecture applied
**Priority:** Active - Current patch needs fixing
**Created:** 2025-12-04
**Last Updated:** 2025-12-06

---

## Goal

Migrate ExaBGP to Python 3.12+ minimum and leverage the buffer protocol (`memoryview`) to reduce memory consumption during BGP message parsing.

---

## Completed Prerequisite Work (Phase 0)

### ✅ NLRI Buffer-Ready Architecture (2025-12-06)

The following foundational work has been completed, preparing the codebase for buffer protocol adoption:

#### Class-Level AFI/SAFI Pattern
**Files modified:** `family.py`, `nlri.py`, `evpn/nlri.py`, `vpls.py`, `rtc.py`, `label.py`, `ipvpn.py`

| Class | Change | Memory Savings |
|-------|--------|----------------|
| EVPN | Class-level `_class_afi`/`_class_safi` with `@property` | 16 bytes/instance |
| VPLS | Class-level `_class_afi`/`_class_safi` with `@property` | 16 bytes/instance |
| RTC | Class-level `_class_afi`/`_class_safi` with `@property` | 16 bytes/instance |
| BGPLS | Not updated (supports 2 SAFIs) | - |
| Label | Class-level `_class_safi` with `@property` | 8 bytes/instance |
| IPVPN | Class-level `_class_safi` with `@property` | 8 bytes/instance |

#### Unified `_packed` Base Class Storage
**File:** `src/exabgp/bgp/message/update/nlri/nlri.py`

- Added `_packed: bytes` type annotation to NLRI base class
- Initialized to `b''` in `__init__` and singletons
- All NLRI subclasses inherit this unified storage pattern
- Foundation for future memoryview slice storage

#### Wire Container Classes with Lazy Parsing
**File:** `src/exabgp/bgp/message/update/nlri/collection.py`

- `NLRICollection`: Wire container for IPv4 announce/withdraw sections
- `MPNLRICollection`: Wire container for MP_REACH/MP_UNREACH attribute data
- Dual-mode: wire bytes (packed-first) OR semantic NLRI list
- `_UNPARSED` sentinel for lazy parsing (parse only when `.nlris` accessed)
- Roundtrip tested: wire → parse → pack → wire

#### NLRI Singletons Consolidated
**File:** `src/exabgp/bgp/message/update/nlri/nlri.py`

- `_create_singleton()` method for NLRI.INVALID and NLRI.EMPTY
- `__copy__`/`__deepcopy__` preserve singleton identity

#### Configuration Parser NLRI Normalization
**Files:** `static/route.py`, `flow/__init__.py`, `flow/route.py`

- `_normalize_nlri_type()` recreates NLRI with correct type based on data presence
- Enables class-level SAFI by avoiding post-creation mutation

### ✅ Memory Analysis Completed (2025-12-06)

**Benchmark results** (`lab/rib/results-2025-12-05.txt` - BEFORE):
- 100K routes: add_to_rib 331K ops/sec, del_from_rib 67K ops/sec
- **Bottleneck identified:** `deepcopy()` in `del_from_rib()` = 88% of withdrawal time
- Per Route object: 1,035 bytes (no `__slots__`)

**Benchmark results** (`lab/rib/results-2025-12-06.txt` - AFTER):
- 100K routes: add_to_rib 264K ops/sec, del_from_rib **436K ops/sec** ⬆️ **6.5x faster!**
- CPU time for 10K workload: **0.175s** vs 0.736s = **4.2x faster overall**
- No deepcopy in profile - bottleneck eliminated!

**Key finding:** The biggest memory win would be:
1. `__slots__` on NLRI/Route classes (68% per-object reduction)
2. ~~Shallow copy instead of deepcopy in `del_from_rib()`~~ ✅ DONE - `del_from_rib()` now stores withdraws in `_pending_withdraws` dict without copying

**Note:** `Change` class was renamed to `Route` (`src/exabgp/rib/route.py`)

---

### Phase 2.5: Fix Current Buffer Patch (2025-12-06 Analysis)

#### 🚨 Current Patch Problem

The current patch accepts `Buffer` (PEP 688) at API boundaries but **immediately converts to `bytes`**, defeating the zero-copy benefit:

```python
# Current pattern (WRONG - loses zero-copy)
def __init__(self, packed: Buffer = b'') -> None:
    self._packed = bytes(packed)  # ← Copies the data!
```

**Why This Defeats Zero-Copy:**
- `memoryview` slicing is **O(1)** - creates a view, no copy
- `bytes()` conversion is **O(n)** - copies all data
- With 1000 NLRIs per UPDATE: current patch = 1000 copies, fixed = 0 copies

#### Two-Buffer Architecture (RECOMMENDED)

```
┌─────────────────────────────────────────────────────────────────┐
│ NETWORK LAYER (connection.py)                                    │
│   recv_buffer = bytearray(65535)  # Reusable network buffer     │
│   view = memoryview(recv_buffer)                                │
│   recv_into(view)                                               │
│   message_data = view[:message_length]  # Still refs recv_buffer│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ COPY BOUNDARY
┌─────────────────────────────────────────────────────────────────┐
│ MESSAGE LAYER (Message.__init__)                                 │
│   self._buffer = bytearray(packed)  # Copy for lifetime safety  │
│   self._packed = memoryview(self._buffer)  # View of own buffer │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ ZERO-COPY SLICING
┌─────────────────────────────────────────────────────────────────┐
│ PARSING LAYER (split, NLRI, attributes)                          │
│   withdrawn = self._packed[:withdrawn_len]   # No copy          │
│   attributes = self._packed[offset:next]     # No copy          │
│   nlri_data = self._packed[nlri_start:]      # No copy          │
└─────────────────────────────────────────────────────────────────┘
```

**Why Two Buffers?**
- Network buffer can be reused between messages
- Message owns its data for full lifetime (no dangling references)
- Zero-copy slicing within each message

#### Buffer Conversion Points - ✅ COMPLETED (2025-12-06)

**Pattern:** Copy into message-owned buffer, then create memoryview

```python
# In each Message.__init__:
self._buffer = bytearray(packed)  # Copy for lifetime safety
self._packed = memoryview(self._buffer)  # View for zero-copy slicing
```

| File | Status | Change |
|------|--------|--------|
| `keepalive.py` | ✅ Done | Two-buffer pattern applied |
| `notification.py` | ✅ Done | Two-buffer pattern applied |
| `open/__init__.py` | ✅ Done | Two-buffer pattern applied, bytes conversion at unpack boundary |
| `refresh.py` | ✅ Done | Two-buffer pattern applied |
| `unknown.py` | ✅ Done | Two-buffer pattern applied |
| `update/__init__.py` | ✅ Done | Two-buffer pattern, split() returns memoryview |

**Additional Changes:**
- `UpdateCollection.split()` now returns `tuple[memoryview, memoryview, memoryview]`
- `Open.unpack_message()` converts memoryview to bytes at boundary for `Capabilities.unpack()`
- `UpdateCollection._parse_payload()` converts memoryview slices to bytes for NLRI/Attribute parsing
- Fuzz tests updated to accept `memoryview` return type from `split()`

**Type annotations:**
- Add: `_buffer: bytearray`
- Change: `_packed: memoryview` (was `bytes`)

#### Cost Analysis

| Operation | Old (bytes everywhere) | New (two-buffer) |
|-----------|------------------------|------------------|
| Network read | O(n) copy per recv | O(1) recv_into |
| Message creation | O(n) copy | O(n) copy (same) |
| UPDATE split | O(n) copies × 3 | O(1) slices × 3 |
| NLRI parsing (1000) | O(n) copies × 1000 | O(1) slices × 1000 |

**Net gain:** Eliminates O(n) copies in split() and NLRI parsing.

#### Implementation Patterns

**Pattern 1: Two-Buffer at Message.__init__**
```python
def __init__(self, packed: Buffer) -> None:
    self._buffer = bytearray(packed)  # Copy for lifetime safety
    self._packed = memoryview(self._buffer)  # View for zero-copy slicing
```

**Pattern 2: Return memoryview Slices**
```python
def split(data: Buffer) -> tuple[memoryview, memoryview, memoryview]:
    view = memoryview(data) if not isinstance(data, memoryview) else data
    return (view[a:b], view[c:d], view[e:f])

def unpack_nlri(cls, ..., data: Buffer, ...) -> tuple[NLRI, memoryview]:
    view = memoryview(data) if not isinstance(data, memoryview) else data
    return (nlri, view[consumed:])
```

**Pattern 3: struct.unpack works on memoryview**
```python
# Python 3.12+ - no conversion needed
length = unpack('!H', view[0:2])[0]  # No bytes() needed
```

---

## Current State

### Python Version
- **Current minimum:** Python 3.12 ✅
- **Supported:** 3.12, 3.13, 3.14
- **Location:** `pyproject.toml` line 9: `requires-python = ">=3.12"`

### Current Byte Handling
- All parsing uses `bytes` objects with slice operations
- No `memoryview` or buffer protocol usage
- Each slice creates a new bytes object reference
- Pattern: `data = data[offset:]` repeated throughout parsing
- **NEW:** NLRICollection stores packed bytes, lazy parsing to NLRI list

### Memory Pattern Issues
1. **Label padding:** `bytes([0]) + bgp[:3]` creates new 4-byte object per label
2. **Slice reassignment loops:** Each `data = data[n:]` creates intermediate objects
3. **UPDATE concatenation:** Progressive `announced += packed` is O(n) per append
4. **No zero-copy:** Despite CPython slice optimizations, object headers add ~56 bytes overhead each
5. **No `__slots__`:** NLRI and Route classes use `__dict__` (96 bytes overhead each)

---

## Proposed Changes

### Phase 1: Raise Python Minimum to 3.12 ✅ DONE

**Completed 2025-12-06:**
- `pyproject.toml` updated: `requires-python = ">=3.12"`
- Classifiers updated: Python 3.12, 3.13, 3.14 only
- Version bumped to 6.0.0
- mypy `python_version = "3.12"`
- No GitHub CI workflows in repo (external CI)

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

- `plan/nlri-buffer-ready.md` - ✅ COMPLETED - Class-level AFI/SAFI, unified `_packed`
- `plan/nlri-collection.md` - ✅ COMPLETED - Wire containers with lazy parsing
- `plan/nlri-packed-base.md` - ✅ COMPLETED - `_packed` in NLRI base class
- `plan/packed-attribute.md` - Packed-bytes-first pattern
- `plan/todo.md` - Overall quality improvements

---

## Next Steps (Recommended Order)

### Immediate Wins (Before Full Buffer Protocol)

These can be done independently and provide significant benefits:

1. ~~**Add `__slots__` to NLRI and Route classes**~~ ✅ DONE (2025-12-06)
   - Added `__slots__` to: Route, Family, NLRI, INET, Label, IPVPN, VPLS, RTC, Flow, EVPN, BGPLS, MVPN, MUP, PathInfo
   - Single-family types (VPLS, EVPN, RTC, Label, IPVPN) have afi/safi setters that raise AttributeError
   - NLRI `__copy__`/`__deepcopy__` skip property-backed slots via `_PROPERTY_SLOTS` check
   - Files modified: `rib/route.py`, `protocol/family.py`, `nlri/nlri.py`, `nlri/inet.py`, `nlri/label.py`, `nlri/ipvpn.py`, `nlri/vpls.py`, `nlri/rtc.py`, `nlri/flow.py`, `nlri/evpn/nlri.py`, `nlri/bgpls/nlri.py`, `nlri/mvpn/nlri.py`, `nlri/mup/nlri.py`, `nlri/qualifier/path.py`

2. ~~**Replace `deepcopy` with shallow copy in `del_from_rib()`**~~ ✅ DONE
   - `del_from_rib()` now stores `(NLRI, AttributeCollection)` tuples in `_pending_withdraws`
   - No deepcopy needed - withdraws are generated directly from stored data
   - File: `rib/outgoing.py` (lines 39, 260-267)

### Buffer Protocol Implementation

3. ~~**Phase 1: Raise Python minimum to 3.12**~~ ✅ DONE
   - `pyproject.toml` updated to `>=3.12`
   - Version 6.0.0

4. **Phase 2-6: memoryview migration**
   - Network layer → Message splitting → NLRI unpacking → Attributes
   - See detailed phases above

---

## Memory Savings Analysis (2025-12-06)

### Current Refactoring Impact

| Optimization | Status | Per-Instance Savings | At 100K Routes |
|--------------|--------|----------------------|----------------|
| Class-level AFI/SAFI (single-family) | ✅ Done | 16 bytes | 1.5 MB |
| Class-level SAFI (Label/IPVPN) | ✅ Done | 8 bytes | 0.76 MB |
| Lazy NLRI parsing | ✅ Done | Conditional | Varies |
| Unified `_packed` storage | ✅ Done | Foundation | - |

**Total immediate savings: 1-3% memory reduction** for typical workloads.

### Future Optimization Potential

| Optimization | Status | Per-Instance Savings | At 100K Routes |
|--------------|--------|----------------------|----------------|
| `__slots__` on NLRI | ✅ Done | ~104 bytes (68%) | 10 MB |
| `__slots__` on Route | ✅ Done | ~96 bytes | 9.6 MB |
| Avoid deepcopy in del_from_rib | ✅ Done | 81% for withdrawals | ~125 MB |
| memoryview buffer sharing | ❌ Pending | 50-80% for bulk | 50-80 MB |

### Key Research Sources

- memoryview provides **300x speedup** for large buffer slicing vs bytes ([Eli Bendersky](https://eli.thegreenplace.net/2011/11/28/less-copies-in-python-with-the-buffer-protocol-and-memoryviews))
- `__slots__` reduces instance size from **152 bytes to 48 bytes** for 2-attribute class ([Python Wiki](https://wiki.python.org/moin/UsingSlots))
- Property access is **2-3x slower** than direct attribute but negligible in practice ([Stack Overflow](https://stackoverflow.com/questions/21174590/property-speed-overhead-in-python))

---

## References

- [PEP 688 - Buffer Protocol](https://peps.python.org/pep-0688/)
- [Python 3.12 Release Notes](https://docs.python.org/3.12/whatsnew/3.12.html)
- [memoryview documentation](https://docs.python.org/3/library/stdtypes.html#memoryview)
- [Eli Bendersky - Less copies with buffer protocol](https://eli.thegreenplace.net/2011/11/28/less-copies-in-python-with-the-buffer-protocol-and-memoryviews)
- [ArjanCodes - MemoryView for efficient data handling](https://arjancodes.com/blog/using-memoryview-in-python-for-efficient-data-handling/)
- [Oyster.com - Saving 9GB with __slots__](https://tech.oyster.com/save-ram-with-python-slots/)
