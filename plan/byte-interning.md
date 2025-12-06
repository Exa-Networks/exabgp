# Byte Interning for Memory-Efficient Storage

**Status:** 🔄 Partially Complete
**Created:** 2025-12-05
**Updated:** 2025-12-06
**Goal:** Reduce memory usage by caching/interning frequently reused objects

---

## Current State Analysis

### Already Implemented ✅

#### 1. Attribute Caching (LRU)

Attributes with `CACHING = True` are cached via `Attribute.unpack()`:

```python
# attribute/attribute.py:302-315
cache: bool = cls.caching and cls.CACHING
if cache and data in cls.cache.get(cls.ID, {}):
    return cls.cache[cls.ID].retrieve(data)
# ... create instance ...
if cache:
    cls.cache[cls.ID].cache(data, instance)
```

Uses `util/cache.py` `Cache` class - LRU with time-based expiry.

**Cached attributes:** Origin, MED, LocalPreference, AtomicAggregate, Aggregator, NextHop, OriginatorID, ClusterList, AIGP, PMSI, PrefixSid

#### 2. Pre-populated Singletons

**Origin** (`origin.py:115-126`):
- Only 3 possible values (IGP, EGP, INCOMPLETE)
- Pre-built at module load via `setCache()`

**AtomicAggregate** (`atomicaggregate.py:94-99`):
- Only 1 possible value (empty bytes)
- Pre-built at module load via `setCache()`

#### 3. AFI/SAFI Caching

**`protocol/family.py`:**
- `AFI.common`: bytes → AFI instance (for wire lookup)
- `AFI.cache`: int → AFI instance (for semantic lookup)
- `SAFI.common` / `SAFI.cache`: same pattern
- Pre-populated with all known values

---

## Remaining Work

### NLRI Qualifier Classes (Not Cached)

These are stored inside NLRI objects and don't benefit from Attribute caching:

| Class | Size | Typical Reuse | Priority |
|-------|------|---------------|----------|
| **RouteDistinguisher** | 8 bytes | 1000-10000x (per VRF) | HIGH |
| **Labels** | 3-12 bytes | 100-1000x | HIGH |
| **PathInfo** | 4 bytes | 10-100x | MEDIUM |

### Memory Waste Example

100K VPNv4 routes with 10 VRFs and 100 unique labels:

| Component | Instances | Unique | Bytes Each | Wasted |
|-----------|-----------|--------|------------|--------|
| RD | 100,000 | 10 | 41 | 4.0 MB |
| Labels | 100,000 | 100 | 36 | 3.5 MB |
| **Total waste** | | | | **7.5 MB** |

---

## Implementation Plan

### Approach: Use Existing `Cache` Class

The `util/cache.py` `Cache` class already provides LRU semantics. Use class-level caches following the AFI/SAFI pattern.

### Phase 1: RouteDistinguisher Caching

**File:** `src/exabgp/bgp/message/update/nlri/qualifier/rd.py`

```python
from exabgp.util.cache import Cache

class RouteDistinguisher:
    # Class-level LRU cache
    _cache: ClassVar[Cache[bytes, 'RouteDistinguisher']] = Cache(min_items=50, max_items=500)

    def __init__(self, packed: bytes) -> None:
        if packed and len(packed) != self.LENGTH:
            raise ValueError(...)
        self._packed = packed

    @classmethod
    def from_packed(cls, packed: bytes) -> 'RouteDistinguisher':
        """Get or create RD from packed bytes (cached)."""
        if not packed:
            return cls.NORD
        if packed in cls._cache:
            return cls._cache.retrieve(packed)
        instance = cls(packed)
        return cls._cache.cache(packed, instance)
```

### Phase 2: Labels Caching

**File:** `src/exabgp/bgp/message/update/nlri/qualifier/labels.py`

```python
from exabgp.util.cache import Cache

class Labels:
    _cache: ClassVar[Cache[bytes, 'Labels']] = Cache(min_items=100, max_items=1000)

    @classmethod
    def from_packed(cls, packed: bytes) -> 'Labels':
        """Get or create Labels from packed bytes (cached)."""
        if not packed:
            return cls.NOLABEL
        if packed in cls._cache:
            return cls._cache.retrieve(packed)
        instance = cls(packed)
        return cls._cache.cache(packed, instance)
```

### Phase 3: PathInfo Caching

**File:** `src/exabgp/bgp/message/update/nlri/qualifier/path.py`

```python
from exabgp.util.cache import Cache

class PathInfo:
    _cache: ClassVar[Cache[bytes, 'PathInfo']] = Cache(min_items=50, max_items=256)

    @classmethod
    def from_packed(cls, packed: bytes) -> 'PathInfo':
        """Get or create PathInfo from packed bytes (cached)."""
        if not packed:
            return cls.DISABLED
        if packed in cls._cache:
            return cls._cache.retrieve(packed)
        instance = cls(packed)
        return cls._cache.cache(packed, instance)
```

### Phase 4: Update Callers

Update NLRI unpacking to use `from_packed()` factory methods:

**Files to modify:**
- `nlri/inet.py` - PathInfo creation
- `nlri/ipvpn.py` - RD, Labels creation
- `nlri/label.py` - Labels creation
- `nlri/evpn/*.py` - RD, Labels creation
- `nlri/mvpn/*.py` - RD creation

**Pattern:**
```python
# Before
rd = RouteDistinguisher(data[:8])

# After
rd = RouteDistinguisher.from_packed(data[:8])
```

---

## Cache Configuration

| Class | min_items | max_items | Rationale |
|-------|-----------|-----------|-----------|
| RouteDistinguisher | 50 | 500 | Few unique VRFs, extreme reuse |
| Labels | 100 | 1000 | More unique labels, high reuse |
| PathInfo | 50 | 256 | Typically few unique path IDs |

---

## Files to Modify

| File | Change |
|------|--------|
| `nlri/qualifier/rd.py` | Add `_cache`, `from_packed()` |
| `nlri/qualifier/labels.py` | Add `_cache`, `from_packed()` |
| `nlri/qualifier/path.py` | Add `_cache`, `from_packed()` |
| `nlri/inet.py` | Use `PathInfo.from_packed()` |
| `nlri/ipvpn.py` | Use `RD.from_packed()`, `Labels.from_packed()` |
| `nlri/label.py` | Use `Labels.from_packed()` |
| `nlri/evpn/*.py` | Use cached factories |
| `nlri/mvpn/*.py` | Use cached factories |

---

## Verification

```bash
./qa/bin/test_everything  # All 11 test suites must pass
```

### Memory Benchmark

Create `lab/rib/benchmark_caching.py` to measure:
1. Memory usage with/without caching
2. Cache hit rates
3. Any performance impact

---

## Expected Savings

With caching enabled for 100K VPNv4 routes (10 VRFs, 100 labels):

| Component | Before | After | Savings |
|-----------|--------|-------|---------|
| RD objects | 4.1 MB | 20 KB | 99.5% |
| Label objects | 3.6 MB | 100 KB | 97% |
| **Total** | 7.7 MB | 120 KB | **98%** |

---

## Progress

- [x] Attribute caching (existing)
- [x] Origin/AtomicAggregate singletons (existing)
- [x] AFI/SAFI caching (existing)
- [ ] Phase 1: RouteDistinguisher caching
- [ ] Phase 2: Labels caching
- [ ] Phase 3: PathInfo caching
- [ ] Phase 4: Update callers
- [ ] Memory benchmark
