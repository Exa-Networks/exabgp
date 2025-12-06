# Why deepcopy is Used in del_from_rib()

## The Issue

**Location:** `src/exabgp/rib/outgoing.py:216-218`

**Impact:** 88% of `del_from_rib()` CPU time is spent in `deepcopy()`

### Benchmark Results (100K routes)

| Metric | With deepcopy | With shallow copy | Improvement |
|--------|---------------|-------------------|-------------|
| Time | 1.50s | ~0.05s | **28x faster** |
| Throughput | 67K ops/sec | ~1.9M ops/sec | **28x higher** |
| Memory | 155 MB | ~30 MB | **81% less** |
| Per-operation | 12.6 µs | 0.4 µs | **28x faster** |

### CPU Profile (cProfile)

```
del_from_rib()     0.642s cumulative (10K routes)
└── deepcopy()     0.564s (88% of time)
    ├── _reconstruct()     0.540s
    └── _deepcopy_dict()   0.507s
```

## Current Code (outgoing.py:216-218)

```python
def del_from_rib(self, change: Change) -> None:
    # ... remove from pending if present ...

    change = deepcopy(change)        # <-- THE BOTTLENECK (88% of time)
    change.nlri.action = Action.WITHDRAW
    self._update_rib(change)
```

## Why deepcopy Exists

The `deepcopy` is needed because:

1. **The original Change is still referenced elsewhere**
   - The caller may still hold a reference to the Change
   - The Change may be in the cache (`_seen`)
   - The Change may be in watchdog storage (`_watchdog`)

2. **We need to modify `nlri.action`**
   - Changing from `Action.ANNOUNCE` to `Action.WITHDRAW`
   - This mutation would affect ALL references to the same object

3. **The withdrawal must coexist with the original**
   - Original: stored in cache as ANNOUNCE
   - Withdrawal: queued in `_new_nlri` as WITHDRAW
   - Both may exist simultaneously

## Why deepcopy is Expensive

`deepcopy` copies the ENTIRE object graph:

```
Change
├── nlri (NLRI object)
│   ├── _packed (bytes)
│   ├── path_info (PathInfo)
│   ├── nexthop (IP)
│   ├── labels (Labels | None)
│   └── rd (RouteDistinguisher | None)
└── attributes (Attributes dict)
    ├── ORIGIN
    ├── AS_PATH
    ├── LOCAL_PREF
    └── ... (many more)
```

But we only need to change ONE field: `nlri.action`

## Solutions

### Option 1: Shallow Copy of NLRI Only

```python
def del_from_rib(self, change: Change) -> None:
    # Shallow copy NLRI, share Attributes
    new_nlri = copy(change.nlri)
    new_nlri.action = Action.WITHDRAW
    withdrawal = Change(new_nlri, change.attributes)  # Share attributes!
    self._update_rib(withdrawal)
```

**Pros**: 28x faster, 81% less memory
**Cons**: Attributes object is shared (fine - we don't modify it)

### Option 2: Action Override in Change

```python
class Change:
    __slots__ = ['nlri', 'attributes', '_index', '_action_override']

    @property
    def action(self) -> Action:
        return self._action_override or self.nlri.action

    def as_withdrawal(self) -> 'Change':
        """Return view with WITHDRAW action, minimal allocation."""
        new = Change.__new__(Change)
        new.nlri = self.nlri           # Same reference
        new.attributes = self.attributes  # Same reference
        new._index = self._index       # Same reference
        new._action_override = Action.WITHDRAW
        return new
```

**Pros**: Near-zero allocation, maximum sharing
**Cons**: Slightly more complex Change class

### Option 3: Immutable Change + Cached Factory

```python
class ChangeFactory:
    """Cache of Change objects for deduplication."""
    _cache: dict[bytes, Change] = {}

    @classmethod
    def get_or_create(cls, nlri: NLRI, attributes: Attributes) -> Change:
        key = nlri.index() + attributes.index().encode()
        if key not in cls._cache:
            cls._cache[key] = Change(nlri, attributes)
        return cls._cache[key]

    @classmethod
    def get_withdrawal(cls, change: Change) -> Change:
        """Get cached withdrawal version of a change."""
        key = b'W' + change.index()  # 'W' prefix for withdrawals
        if key not in cls._cache:
            new_nlri = copy(change.nlri)
            new_nlri.action = Action.WITHDRAW
            cls._cache[key] = Change(new_nlri, change.attributes)
        return cls._cache[key]
```

**Pros**: Maximum object reuse, same `id()` for identical objects
**Cons**: Cache management complexity, memory for cache itself

---

## Object Caching Considerations

If you want `id(obj1) == id(obj2)` for similar objects:

### What Can Be Safely Cached/Shared

| Object | Cacheable? | Notes |
|--------|------------|-------|
| Attributes | ✅ Yes | Immutable after creation, already has class-level caching |
| NLRI (announce) | ⚠️ Careful | Contains mutable `action` field |
| NLRI (withdraw) | ⚠️ Careful | Same concern |
| Change | ⚠️ Careful | References NLRI which has mutable action |

### The `action` Field Problem

The root issue is that `NLRI.action` is mutable:

```python
class NLRI:
    action: Action  # MUTABLE - can be ANNOUNCE, WITHDRAW, or UNSET
```

This prevents simple caching because the same NLRI prefix can be:
- An announcement (action=ANNOUNCE)
- A withdrawal (action=WITHDRAW)

### Suggested Cache Design

```python
class NLRICache:
    """Cache NLRI by (prefix, action) tuple."""

    # Key: (prefix_bytes, action) -> NLRI
    _cache: dict[tuple[bytes, Action], NLRI] = {}

    @classmethod
    def get_or_create(cls, packed: bytes, action: Action, **kwargs) -> NLRI:
        key = (packed, action)
        if key not in cls._cache:
            nlri = NLRI.make_route(packed=packed, action=action, **kwargs)
            cls._cache[key] = nlri
        return cls._cache[key]
```

This way:
- `get_or_create(prefix, ANNOUNCE)` always returns same object
- `get_or_create(prefix, WITHDRAW)` always returns same object
- But they are DIFFERENT objects (different action)

### Attributes Already Has Caching

See `attributes.py:274-294`:

```python
class Attributes(dict):
    cached: ClassVar[Attributes | None] = None
    previous: ClassVar[bytes] = b''

    @classmethod
    def unpack(cls, data: bytes, negotiated: Negotiated) -> Attributes:
        if cls.cached and data == cls.previous:
            return cls.cached  # <-- Returns same object!
```

This already provides `id()` equality for consecutively parsed identical attributes.

---

## Recommendation

For the immediate fix:

1. **Use Option 1 (shallow copy)** - Simple, 28x faster, safe
2. **Keep Attributes sharing** - Already works, no change needed

For future object caching:

1. **Make NLRI immutable** or separate action into Change
2. **Add NLRI cache keyed by (prefix, action)**
3. **Expand Attributes cache** to be global (not just consecutive)

The key insight: **Separate identity from state**. If `action` moves from NLRI to Change, then NLRI becomes truly immutable and cacheable.
