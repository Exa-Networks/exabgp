# Plan: Standardize Buffer Handling Across All BGP Message/Attribute/NLRI Classes

**Status:** In Progress
**Created:** 2025-12-06

**Goal:** Ensure all classes in `src/exabgp/bgp/message/` consistently accept `Buffer` (PEP 688) in constructors and parsing methods.

**Scope:** ~80 classes across message, attribute, and NLRI subsystems.

---

## Part 1: Message Classes (Already Mostly Done)

### Consistency Fixes Needed

**File:** `src/exabgp/bgp/message/operational.py`
- `OperationalFamily.__init__`: Change `bytes(data) if isinstance(data, memoryview) else data` → `bytes(data)`

**File:** `src/exabgp/bgp/message/open/__init__.py`
- `Open.unpack_message`: Remove isinstance checks, use direct `bytes(data[...])`

**File:** `src/exabgp/bgp/message/update/__init__.py`
- `UpdateCollection.split`: Change to `memoryview(data)` directly

---

## Part 2: Attribute Classes (~60 classes)

### Current State
All attribute classes accept `bytes` only:
```python
def __init__(self, packed: bytes) -> None:
def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> Attribute:
```

### Required Changes

**Pattern to apply in ALL attribute `__init__` methods:**
```python
# Before:
def __init__(self, packed: bytes) -> None:
    self._packed = packed

# After:
def __init__(self, packed: Buffer) -> None:
    self._packed = packed  # Keep as Buffer (no conversion)
```

**Pattern to apply in ALL `unpack_attribute` methods:**
```python
# Before:
def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> Attr:

# After:
def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> Attr:
```

**Update type annotations:**
```python
# Before:
_packed: bytes

# After:
_packed: Buffer
```

### Files to Modify

#### Core Attributes
| File | Classes |
|------|---------|
| `attribute/origin.py` | Origin |
| `attribute/aspath.py` | ASPath |
| `attribute/nexthop.py` | NextHop |
| `attribute/med.py` | MED |
| `attribute/localpref.py` | LocalPreference |
| `attribute/atomicaggregate.py` | AtomicAggregate |
| `attribute/aggregator.py` | Aggregator |
| `attribute/originatorid.py` | OriginatorID |
| `attribute/clusterlist.py` | ClusterList |
| `attribute/aigp.py` | AIGP |
| `attribute/pmsi.py` | PMSI |
| `attribute/generic.py` | GenericAttribute |

#### Community Attributes
| File | Classes |
|------|---------|
| `attribute/community/initial/communities.py` | Communities |
| `attribute/community/extended/communities.py` | ExtendedCommunities, ExtendedCommunitiesIPv6 |
| `attribute/community/large/communities.py` | LargeCommunities |

#### MP Attributes
| File | Classes |
|------|---------|
| `attribute/mprnlri.py` | MPRNLRI |
| `attribute/mpurnlri.py` | MPURNLRI |

#### Segment Routing Attributes
| File | Classes |
|------|---------|
| `attribute/sr/prefixsid.py` | PrefixSid |
| `attribute/sr/labelindex.py` | LabelIndex |
| `attribute/sr/srgb.py` | SRGB |
| `attribute/sr/srv6/*.py` | SRv6 TLV classes |

#### BGP-LS Attributes
| File | Classes |
|------|---------|
| `attribute/bgpls/linkstate.py` | LinkState, BaseLS |
| `attribute/bgpls/node/*.py` | Node attribute TLVs (~8) |
| `attribute/bgpls/link/*.py` | Link attribute TLVs (~20) |
| `attribute/bgpls/prefix/*.py` | Prefix attribute TLVs (~10) |

#### Collection
| File | Classes |
|------|---------|
| `attribute/collection.py` | AttributeCollection.unpack(), Attributes |

---

## Part 3: NLRI Classes (~14 classes)

### Current State
All NLRI classes accept `bytes` only (except CIDR which already accepts Buffer):
```python
def __init__(self, packed: bytes, ...) -> None:
def unpack_nlri(cls, ..., data: bytes, ...) -> tuple[NLRI, bytes]:
```

### Required Changes

**Pattern to apply in ALL NLRI `__init__` methods:**
```python
# Before:
def __init__(self, packed: bytes, ...) -> None:
    self._packed = packed

# After:
def __init__(self, packed: Buffer, ...) -> None:
    self._packed = packed  # Keep as Buffer (no conversion)
```

**Pattern to apply in ALL `unpack_nlri` methods:**
```python
# Before:
def unpack_nlri(cls, ..., bgp: bytes, ...) -> tuple[NLRI, bytes]:

# After:
def unpack_nlri(cls, ..., bgp: Buffer, ...) -> tuple[NLRI, Buffer]:
```

**Update type annotations:**
```python
# Before:
_packed: bytes

# After:
_packed: Buffer
```

### Files to Modify

| File | Classes |
|------|---------|
| `nlri/nlri.py` | NLRI (base class) |
| `nlri/inet.py` | INET |
| `nlri/label.py` | Label |
| `nlri/ipvpn.py` | IPVPN |
| `nlri/flow.py` | Flow |
| `nlri/cidr.py` | CIDR (already accepts Buffer) |
| `nlri/vpls.py` | VPLS |
| `nlri/rtc.py` | RTC |
| `nlri/evpn/nlri.py` | EVPN + subtypes |
| `nlri/bgpls/nlri.py` | BGPLS + subtypes |
| `nlri/mup/nlri.py` | MUP + subtypes |
| `nlri/mvpn/nlri.py` | MVPN + subtypes |
| `nlri/collection.py` | NLRICollection, MPNLRICollection |

---

## Part 4: Buffer Import

Add to all modified files:
```python
from collections.abc import Buffer
```

---

## Execution Order

1. **Message classes** (4 files) - consistency fixes
2. **Attribute base** (`attribute/attribute.py`) - add Buffer to base signatures
3. **Attribute subclasses** (~25 files) - update type hints
4. **NLRI base** (`nlri/nlri.py`) - add Buffer to base signatures
5. **NLRI subclasses** (~12 files) - update type hints
6. **Run tests** after each batch

## Verification

```bash
./qa/bin/test_everything
```

All 11 test suites must pass.

---

## Progress

- [x] Part 1: Message classes consistency (completed 2025-12-06)
  - `operational.py`: OperationalFamily uses Buffer
  - `open/__init__.py`: Open.unpack_message accepts Buffer
  - `update/__init__.py`: UpdateCollection.split uses memoryview directly
  - `connection.py`: Zero-copy reads with recv_into, returns memoryview
  - `family.py`: AFI/SAFI unpack accepts Buffer

- [x] Part 2: Attribute classes (completed 2025-12-06)
  - Core: origin, aspath, nexthop, med, localpref, atomicaggregate, aggregator, originatorid, clusterlist, aigp, pmsi, generic
  - Communities: initial, extended, large
  - MP: mprnlri, mpurnlri
  - Base: attribute.py `unpack()` accepts Buffer

- [x] Part 3: NLRI classes (completed 2025-12-06)
  - Base: nlri.py `unpack_nlri()` accepts Buffer
  - Core: inet, ipvpn, label (inherits from inet), flow, rtc, vpls
  - Subdirectories: evpn, bgpls, mup, mvpn
  - Pattern: `data = memoryview(bgp) if not isinstance(bgp, memoryview) else bgp`

- [x] Part 4: Verification (completed 2025-12-06)
  - ruff: All checks passed
  - unit tests: 2830 passed
  - encoding: 36/36 passed
  - decoding: 18/18 passed
