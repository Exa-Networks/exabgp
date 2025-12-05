# Tiered Byte Interning for Memory-Efficient NLRI Storage

**Status:** 📋 Planning
**Created:** 2025-12-05
**Goal:** Reduce memory usage for bytes storage in NLRI classes using Python 3.12 Buffer protocol concepts

---

## Problem Statement

NLRI classes store `_packed: bytes` with no deduplication. Each identical byte sequence gets a separate allocation:
- Same prefix via multiple peers → separate allocations
- Same label value across 1000s of VPN routes → separate allocations
- Same RD value across 1000s of routes in a VRF → separate allocations

Python bytes object overhead: ~33 bytes header + payload. For small values (3-8 bytes), overhead exceeds payload.

**Example waste:** 100K VPNv4 routes with 10 VRFs and 100 unique labels:
- Labels: 100K × 36 bytes = 3.6 MB (but only 100 unique values!)
- RDs: 100K × 41 bytes = 4.1 MB (but only 10 unique values!)

---

## Solution: Tiered Byte Interning

**Key insight:** Only cache what's reused enough to break even on cache overhead.

| Component | Size | Typical Reuse | Cache? |
|-----------|------|---------------|--------|
| Labels | 3-12 bytes | 100-1000x | **YES** |
| Route Distinguisher | 8 bytes | 1000-10000x | **YES** |
| PathInfo (AddPath ID) | 4 bytes | 10-100x | **YES** |
| Common prefixes (/0-/16) | 1-3 bytes | 10-100x | Maybe |
| Full CIDR | 5-17 bytes | 1-5x | No |

**Break-even analysis:**
- Cache entry overhead: ~260 bytes (dict key + value + entry)
- Labels (3 bytes, 100x reuse): saves 100×36 - 260 = 3340 bytes per unique label
- RD (8 bytes, 1000x reuse): saves 1000×41 - 260 = 40,740 bytes per unique RD

---

## Architecture

### New File: `src/exabgp/util/intern.py`

```python
from collections import OrderedDict
from typing import ClassVar

class ByteIntern:
    """LRU byte interning cache - returns canonical instance of bytes."""

    _cache: ClassVar[OrderedDict[bytes, bytes]]
    _max_size: ClassVar[int]

    @classmethod
    def intern(cls, value: bytes) -> bytes:
        """Return canonical bytes instance, interning if beneficial."""
        if not value:
            return value

        # Check cache (moves to end for LRU)
        if value in cls._cache:
            cls._cache.move_to_end(value)
            return cls._cache[value]

        # Evict oldest if at capacity
        if len(cls._cache) >= cls._max_size:
            cls._cache.popitem(last=False)

        # Store and return
        cls._cache[value] = value
        return value

    @classmethod
    def clear(cls) -> None:
        cls._cache.clear()

    @classmethod
    def stats(cls) -> dict:
        return {'size': len(cls._cache), 'max': cls._max_size}


class LabelIntern(ByteIntern):
    """Intern MPLS labels (3-12 bytes, very high reuse)."""
    _cache: ClassVar[OrderedDict[bytes, bytes]] = OrderedDict()
    _max_size: ClassVar[int] = 1000


class RDIntern(ByteIntern):
    """Intern Route Distinguishers (8 bytes, extreme reuse)."""
    _cache: ClassVar[OrderedDict[bytes, bytes]] = OrderedDict()
    _max_size: ClassVar[int] = 500


class PathInfoIntern(ByteIntern):
    """Intern PathInfo/AddPath IDs (4 bytes, medium-high reuse)."""
    _cache: ClassVar[OrderedDict[bytes, bytes]] = OrderedDict()
    _max_size: ClassVar[int] = 256  # Typically few unique path IDs
```

### Integration Points

**1. Labels (`src/exabgp/bgp/message/update/nlri/qualifier/labels.py:28-31`)**

Current:
```python
def __init__(self, packed: bytes) -> None:
    if len(packed) % 3 != 0:
        raise ValueError(...)
    self._packed = packed
```

Proposed:
```python
from exabgp.util.intern import LabelIntern

def __init__(self, packed: bytes) -> None:
    if len(packed) % 3 != 0:
        raise ValueError(...)
    self._packed = LabelIntern.intern(packed)
```

**2. RouteDistinguisher (`src/exabgp/bgp/message/update/nlri/qualifier/rd.py:30-34`)**

Current:
```python
def __init__(self, packed: bytes) -> None:
    if packed and len(packed) != self.LENGTH:
        raise ValueError(...)
    self._packed = packed
```

Proposed:
```python
from exabgp.util.intern import RDIntern

def __init__(self, packed: bytes) -> None:
    if packed and len(packed) != self.LENGTH:
        raise ValueError(...)
    self._packed = RDIntern.intern(packed) if packed else packed
```

**3. PathInfo (`src/exabgp/bgp/message/update/nlri/qualifier/path.py:21-24`)**

Current:
```python
def __init__(self, packed: bytes) -> None:
    if packed and len(packed) != self.LENGTH:
        raise ValueError(...)
    self._packed = packed
    self._disabled = False
```

Proposed:
```python
from exabgp.util.intern import PathInfoIntern

def __init__(self, packed: bytes) -> None:
    if packed and len(packed) != self.LENGTH:
        raise ValueError(...)
    self._packed = PathInfoIntern.intern(packed) if packed else packed
    self._disabled = False
```

---

## Memory Savings Estimate

### Scenario: 100K VPNv4 Routes, 10 VRFs, 100 Labels

**Current:**
| Component | Count | Bytes Each | Total |
|-----------|-------|------------|-------|
| Label objects | 100,000 | 36 | 3.6 MB |
| RD objects | 100,000 | 41 | 4.1 MB |
| **Total** | | | **7.7 MB** |

**With Interning:**
| Component | Unique | Cache | References | Total |
|-----------|--------|-------|------------|-------|
| Labels | 100 | 26 KB | 800 KB | 826 KB |
| RD | 10 | 2.6 KB | 800 KB | 803 KB |
| **Total** | | | | **1.6 MB** |

**Savings: 6.1 MB (79%)**

---

## Implementation Plan

### Phase 1: Core Implementation
1. Create `src/exabgp/util/intern.py` with `ByteIntern`, `LabelIntern`, `RDIntern`, `PathInfoIntern`
2. Add unit tests in `tests/unit/util/test_intern.py`

### Phase 2: Integration
3. Modify `Labels.__init__()` to use `LabelIntern.intern()`
4. Modify `RouteDistinguisher.__init__()` to use `RDIntern.intern()`
5. Modify `PathInfo.__init__()` to use `PathInfoIntern.intern()`
6. Run functional tests to verify no regressions

### Phase 3: Validation
7. Add memory benchmark to `lab/rib/benchmark_intern.py`
8. Verify positive ROI with realistic workloads
9. Run full test suite: `./qa/bin/test_everything`

---

## Files to Modify

| File | Change |
|------|--------|
| `src/exabgp/util/intern.py` | **NEW** - ByteIntern, LabelIntern, RDIntern, PathInfoIntern |
| `src/exabgp/bgp/message/update/nlri/qualifier/labels.py` | Use LabelIntern in `__init__` |
| `src/exabgp/bgp/message/update/nlri/qualifier/rd.py` | Use RDIntern in `__init__` |
| `src/exabgp/bgp/message/update/nlri/qualifier/path.py` | Use PathInfoIntern in `__init__` |
| `tests/unit/util/test_intern.py` | **NEW** - Unit tests |
| `lab/rib/benchmark_intern.py` | **NEW** - Memory benchmark |

---

## API Compatibility

- **No breaking changes** - interning is internal
- All existing tests should pass unchanged
- Interned bytes are `==` and `is` (same object) for cache hits

---

## Future Extensions (Not in This Plan)

1. **CIDR prefix interning** - only if common prefixes show high reuse
2. **Slab buffer with memoryview** - for extreme memory optimization
3. **Environment variable toggle** - `exabgp_cache_intern=false` to disable
4. **Cache statistics API** - expose hit/miss rates for tuning

---

## Success Criteria

1. All 72 functional tests pass
2. All 1376 unit tests pass
3. Memory benchmark shows positive ROI (savings > overhead)
4. No performance regression in parsing throughput
