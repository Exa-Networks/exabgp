# Buffer Sharing and Caching in ExaBGP

**Purpose:** Memory efficiency for BGP UPDATE message processing
**Strategy:** Two complementary approaches: buffer sharing (zero-copy) + object caching

---

## Overview

ExaBGP processes thousands of BGP routes per second. Without optimization, each route would require multiple memory allocations for parsing. Two strategies minimize this overhead:

1. **Buffer Sharing** - Use Python's buffer protocol to avoid copying wire data during parsing
2. **Object Caching** - Reuse identical objects (like RouteDistinguisher) across routes

---

## Part 1: Python 3.12 Buffer Protocol Integration

### 1.1 The Buffer Type

ExaBGP uses PEP 688's `collections.abc.Buffer` for type annotations:

```python
# src/exabgp/util/types.py
if TYPE_CHECKING:
    Buffer = bytes | memoryview   # For type checkers
else:
    from collections.abc import Buffer  # Runtime: PEP 688
```

This allows all unpack methods to accept any buffer-supporting type without forcing conversions.

### 1.2 Zero-Copy Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     NETWORK I/O LAYER                           │
│  Socket.recv_into(bytearray) → writes directly, no allocation   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MEMORYVIEW WRAP                             │
│  view = memoryview(bytearray) → zero-copy reference             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    view[0:19]      view[19:50]      view[50:]
    (BGP header)    (withdrawn)      (payload)
    zero-copy       zero-copy        zero-copy
```

Key points:
- `recv_into()` writes directly to pre-allocated buffer
- `memoryview` wraps without copying
- Slicing memoryview creates new view, not new bytes
- Conversion to `bytes` only when storing long-term

---

## Part 2: Class Hierarchy Buffer Sharing

### 2.1 NLRI Inheritance and _packed Storage

The NLRI class hierarchy places `_packed` in the base class so all subclasses inherit it:

```
Family (afi, safi slots)
    └── NLRI (action, nexthop, addpath, _packed slots)
          │
          ├── EVPN (_packed = type(1) + length(1) + payload)
          │     ├── MAC (properties unpack from _packed)
          │     ├── Multicast
          │     └── ...
          │
          ├── MVPN (_packed = type(1) + length(1) + payload)
          │     ├── SourceAD
          │     ├── SharedJoin
          │     └── ...
          │
          ├── VPLS (_packed = 19-byte complete wire format)
          │
          └── INET (_packed = CIDR wire bytes)
                ├── Label (_labels_packed added)
                └── IPVPN (_rd_packed added)
```

Each subclass stores wire format in `_packed` and unpacks fields via properties.

### 2.2 How Multiple Classes Share One Buffer

During UPDATE parsing, all NLRIs reference slices from the same underlying buffer:

```
                    ┌─────────────────────────────────────┐
                    │     BGP UPDATE Message Buffer       │
                    │  [withdrawn][attributes][announced] │
                    └───────────┬─────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
   NLRICollection          Attributes            NLRICollection
   (withdrawn)             (shared)              (announced)
        │                       │                       │
        ▼                       ▼                       ▼
   ┌─────────┐           ┌───────────┐           ┌─────────┐
   │ NLRI 1  │           │  Origin   │           │ NLRI 1  │
   │_packed→ │───slice───│  MED      │───slice───│_packed→ │
   └─────────┘           │  NextHop  │           └─────────┘
   ┌─────────┐           └───────────┘           ┌─────────┐
   │ NLRI 2  │                                   │ NLRI 2  │
   │_packed→ │───slice────────────────────slice──│_packed→ │
   └─────────┘                                   └─────────┘
```

All `_packed` references point into the same underlying buffer during parsing.
Only converted to `bytes` when stored long-term (for immutability and hashing).

### 2.3 Unpack Methods: Store Raw Bytes, Don't Parse

**Critical Design Principle:**

`unpack_nlri()` and `unpack()` methods should:
- Store raw wire bytes directly in `_packed`
- NOT parse/decompose fields during unpacking
- Defer ALL parsing to property access

```
unpack_nlri(data: Buffer)
    ↓
self._packed = bytes(data[start:end])  ← STORE RAW BYTES
    ↓
return (instance, remaining_data)

# Later, on property access:
@property
def rd(self) -> RouteDistinguisher:
    return RouteDistinguisher(self._packed[2:10])  ← PARSE ON DEMAND
```

**Why this matters:**
- Zero parsing overhead for routes that are just forwarded
- Route reflectors/servers forward most routes unchanged
- Only pays parsing cost when field is actually accessed
- Buffer can be shared without intermediate object allocations

### 2.4 Property-Based Lazy Unpacking

Properties extract data on-demand from `_packed`:

```python
class VPLS(NLRI):
    @property
    def rd(self) -> RouteDistinguisher:
        return RouteDistinguisher(self._packed[2:10])  # Bytes 2-10

    @property
    def endpoint(self) -> int:
        return unpack('!H', self._packed[10:12])[0]   # Bytes 10-12

    @property
    def base(self) -> int:
        raw = unpack('!L', b'\x00' + self._packed[16:19])[0]
        return raw >> 4  # 20-bit label
```

No intermediate values stored - recalculated on each access.
For frequently accessed fields, caching can be added (see Part 3).

---

## Part 3: Caching When Slicing Isn't Enough

### 3.1 Problem: Repeated Object Creation

Consider 100,000 VPNv4 routes across 10 VRFs:
- Same RouteDistinguisher appears in ~10,000 routes each
- Each `route.rd` property access creates a new `RouteDistinguisher` object
- Without caching: 100K objects × 41 bytes = 4.1 MB wasted

### 3.2 Solution: Object Interning via Cache Class

ExaBGP provides `Cache` class (`util/cache.py`) with LRU + time-based expiry:

```
          ┌─────────────────────────────────────┐
          │     Cache[bytes, RouteDistinguisher] │
          │                                      │
          │  bytes(rd1) ──→ RD instance #1       │
          │  bytes(rd2) ──→ RD instance #2       │
          │  bytes(rd3) ──→ RD instance #3       │
          └─────────────────────────────────────┘
                      ▲
                      │
    Route 1 ─────────┤
    Route 2 ─────────┼──── all return same RD instance #1
    Route 3 ─────────┤
    ...              │
    Route 10000 ─────┘
```

Same bytes → same object instance.

### 3.3 Currently Cached

**Attribute Caching (LRU):**
- Origin, MED, LocalPreference, NextHop
- AtomicAggregate, Aggregator, OriginatorID
- ClusterList, AIGP, PMSI, PrefixSid

**Pre-populated Singletons:**
- `Origin.IGP`, `Origin.EGP`, `Origin.INCOMPLETE` (3 total values)
- `AtomicAggregate` (1 value - empty bytes)

**AFI/SAFI Lookup Tables:**
- `AFI.common`: bytes → AFI instance
- `SAFI.common`: bytes → SAFI instance

### 3.4 Planned Caching (byte-interning)

See: `plan/byte-interning.md`

| Class | Size | Typical Reuse | Expected Savings |
|-------|------|---------------|------------------|
| RouteDistinguisher | 8 bytes | 1000-10000x per VRF | 99.5% |
| Labels | 3-12 bytes | 100-1000x | 97% |
| PathInfo | 4 bytes | 10-100x | 90% |

---

## Part 4: When to Cache vs. Slice

| Data Type | Cardinality | Reuse Pattern | Strategy |
|-----------|-------------|---------------|----------|
| RouteDistinguisher | ~10 unique | Extreme (10K routes/RD) | **CACHE** |
| Labels | ~100 unique | High (1K routes/label) | **CACHE** |
| IP Prefixes | ~100K unique | None (each unique) | **SLICE** |
| AS Paths | ~10K unique | Low (10 routes/path) | **SLICE** |
| Origin | 3 total | Universal | **SINGLETON** |

Decision rule:
- **CACHE**: Low cardinality, high reuse
- **SLICE**: High cardinality, low/no reuse
- **SINGLETON**: Fixed finite domain

---

## Part 5: Memory Savings Summary

### Without Optimization

100K VPNv4 routes:
- 100K × RouteDistinguisher objects = 4.1 MB
- 100K × Labels objects = 3.6 MB
- Parsing overhead during UPDATE processing
- **Total overhead: ~8+ MB**

### With Buffer Sharing + Caching

- Zero-copy parsing: ~0 intermediate allocations during UPDATE processing
- Cached RD (10 unique): 10 × 41 bytes = 410 bytes (vs 4.1 MB)
- Cached Labels (100 unique): 100 × 36 bytes = 3.6 KB (vs 3.6 MB)
- **Total overhead: ~4 KB (99.95% reduction)**

---

## Reference Files

| File | Purpose |
|------|---------|
| `src/exabgp/util/types.py` | Buffer type definition |
| `src/exabgp/util/cache.py` | Cache class (LRU + time expiry) |
| `src/exabgp/bgp/message/update/nlri/nlri.py` | Base NLRI with `_packed` slot |
| `src/exabgp/bgp/message/update/nlri/vpls.py` | Reference packed-bytes-first implementation |
| `src/exabgp/bgp/message/update/attribute/attribute.py` | Attribute caching framework |
| `src/exabgp/protocol/family.py` | AFI/SAFI caching pattern |

---

## Related Documentation

- `.claude/exabgp/PEP688_BUFFER_PROTOCOL.md` - Buffer protocol details
- `.claude/exabgp/PACKED_BYTES_FIRST_PATTERN.md` - Implementation pattern
- `.claude/exabgp/NLRI_CLASS_HIERARCHY.md` - Class hierarchy reference
- `plan/byte-interning.md` - Planned caching improvements

---

**Updated:** 2025-12-07
