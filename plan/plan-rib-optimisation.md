# Plan: RIB Memory Optimisation

## Prerequisites

- **NLRI immutability enforced** (see `plan/nlri-immutability.md`)
- Immutable objects can be safely shared without deepcopy

---

## Problem Statement

Current RIB architecture duplicates routes across neighbors:

```
100 neighbors × 1,000 routes = 100,000 NLRI objects (mostly identical)
```

**Root causes:**
1. `resolve_self()` does `deepcopy(route)` for every neighbor
2. Each neighbor has independent `RIB` with full route copies
3. No sharing of identical NLRI/Attribute objects

---

## Optimisation Phases

### Phase 1: Fix resolve_self() Deepcopy — **60-80% savings**

**File:** `src/exabgp/configuration/neighbor/__init__.py`

**Current (always copies):**
```python
def resolve_self(self, route: Route) -> Route:
    if not nexthop.SELF:
        return route
    route_copy = deepcopy(route)  # ALWAYS deepcopy
    # ... resolve nexthop ...
    return route_copy
```

**After (copy only when needed):**
```python
def resolve_self(self, route: Route) -> Route:
    # If nexthop doesn't need resolution, share the original
    if route.nlri.nexthop is not IP.SELF:
        return route  # Share reference - safe because immutable

    # Only copy when we actually need to modify
    return Route(
        route.nlri.with_nexthop(self._resolve_nexthop()),
        route.attributes
    )
```

**Impact:** If 90% of routes don't use `next-hop self`, 90% fewer copies.

---

### Phase 2: NLRI Interning Pool — **20-40% additional savings**

**File:** `src/exabgp/bgp/message/update/nlri/nlri.py` (new)

```python
class NLRIPool:
    """Global pool for interning immutable NLRI objects."""

    _pool: ClassVar[WeakValueDictionary[bytes, NLRI]] = WeakValueDictionary()

    @classmethod
    def intern(cls, nlri: NLRI) -> NLRI:
        """Return cached NLRI or add to pool."""
        key = nlri.index()
        cached = cls._pool.get(key)
        if cached is not None:
            return cached
        cls._pool[key] = nlri
        return nlri

    @classmethod
    def stats(cls) -> dict[str, int]:
        """Return pool statistics for monitoring."""
        return {'size': len(cls._pool)}
```

**Usage in factories:**
```python
@classmethod
def from_cidr(cls, cidr: CIDR, ...) -> INET:
    instance = cls(...)
    return NLRIPool.intern(instance)  # Return shared instance
```

**Benefits:**
- Same prefix from multiple peers → single object
- WeakValueDictionary → automatic cleanup when unused
- Zero risk with immutable objects

---

### Phase 3: Attribute Interning — **30-50% additional savings**

**File:** `src/exabgp/bgp/message/update/attribute/collection.py`

```python
class AttributePool:
    """Global pool for interning immutable AttributeCollection objects."""

    _pool: ClassVar[WeakValueDictionary[bytes, AttributeCollection]] = WeakValueDictionary()

    @classmethod
    def intern(cls, attrs: AttributeCollection) -> AttributeCollection:
        key = attrs.index()
        cached = cls._pool.get(key)
        if cached is not None:
            return cached
        cls._pool[key] = attrs
        return attrs
```

**Impact:** Route reflectors often have identical attributes across many routes.

---

### Phase 4: NextHop Interning — **10-20% additional savings**

**File:** `src/exabgp/protocol/ip/__init__.py`

```python
class IP:
    _intern_cache: ClassVar[dict[bytes, IP]] = {}

    @classmethod
    def intern(cls, packed: bytes) -> IP:
        """Return cached IP or create and cache."""
        cached = cls._intern_cache.get(packed)
        if cached is not None:
            return cached
        instance = cls(packed)
        cls._intern_cache[packed] = instance
        return instance
```

**Usage:** In NLRI factories and `with_nexthop()`:
```python
def with_nexthop(self, nexthop: IP) -> NLRI:
    return self._copy_with(nexthop=IP.intern(nexthop._packed))
```

**Note:** NextHop cache can be bounded (few unique next-hops in typical deployment).

---

### Phase 5: Reference-Based RIB Storage — **Major savings**

**Current:** Each RIB stores full Route objects
**After:** Store references to shared objects

**File:** `src/exabgp/rib/outgoing.py`

```python
class OutgoingRIB:
    # Current: stores Route copies
    _seen: dict[tuple[AFI, SAFI], dict[bytes, Route]]

    # After: stores references to interned objects
    def add_to_rib(self, route: Route) -> bool:
        # Intern both NLRI and attributes
        interned_nlri = NLRIPool.intern(route.nlri)
        interned_attrs = AttributePool.intern(route.attributes)
        interned_route = Route(interned_nlri, interned_attrs)

        # Store reference (not copy)
        family = interned_nlri.family().afi_safi()
        self._seen.setdefault(family, {})[interned_route.index()] = interned_route
        return True
```

---

## Memory Savings Estimate

| Phase | Savings | Cumulative |
|-------|---------|------------|
| 1. Fix resolve_self | 60-80% | 60-80% |
| 2. NLRI interning | 20-40% of remainder | 70-90% |
| 3. Attribute interning | 30-50% of remainder | 80-95% |
| 4. NextHop interning | 10-20% of remainder | 85-96% |
| 5. Reference-based RIB | Variable | 90-98% |

**Example:** 100 neighbors × 10,000 routes
- Before: ~1.28 GB (100M × 128 bytes/NLRI)
- After Phase 1: ~256 MB
- After all phases: ~25-50 MB

---

## Files to Modify

| Phase | Files |
|-------|-------|
| 1 | `src/exabgp/configuration/neighbor/__init__.py` |
| 2 | `src/exabgp/bgp/message/update/nlri/nlri.py`, all NLRI factories |
| 3 | `src/exabgp/bgp/message/update/attribute/collection.py` |
| 4 | `src/exabgp/protocol/ip/__init__.py` |
| 5 | `src/exabgp/rib/outgoing.py`, `src/exabgp/rib/cache.py` |

---

## Verification

```bash
# Run all tests
./qa/bin/test_everything

# Memory profiling (manual)
python -c "
import tracemalloc
tracemalloc.start()
# ... load large config ...
snapshot = tracemalloc.take_snapshot()
for stat in snapshot.statistics('lineno')[:20]:
    print(stat)
"
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| WeakRef cleanup during iteration | Copy keys before iterating |
| Cache memory growth | Use bounded LRU for IP cache |
| Thread safety | Pools are append-only (safe for reads) |
| Attribute mutability | Ensure AttributeCollection is also immutable |
| Hash collisions | Use full index() bytes, not truncated hash |

---

## Dependencies

1. **NLRI immutability** — must be complete before Phase 2+
2. **AttributeCollection immutability** — required for Phase 3
3. **Route immutability** — required for Phase 5

---

## Rollout Strategy

1. **Phase 1 first** — biggest win, lowest risk, no dependencies
2. **Add monitoring** — track pool sizes, hit rates
3. **Phase 2-4 incrementally** — one interning pool at a time
4. **Phase 5 last** — most invasive, requires all prior phases

---

## Status

- [ ] Phase 1: Fix resolve_self() deepcopy
- [ ] Phase 2: NLRI interning pool
- [ ] Phase 3: Attribute interning pool
- [ ] Phase 4: NextHop interning
- [ ] Phase 5: Reference-based RIB storage
- [ ] Monitoring: Add pool statistics to API/healthcheck

---

## Future Considerations

- **Compressed cold routes:** Store inactive routes as wire bytes only
- **Generational storage:** Hot (active) vs cold (stable) route pools
- **Memory-mapped storage:** For very large tables (full Internet)
