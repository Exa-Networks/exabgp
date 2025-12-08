# Wire vs Semantic Container Separation

**Status:** ✅ Phase 3 Complete
**Created:** 2025-12-07
**Updated:** 2025-12-08

## Goal

Enforce strict separation between Wire Containers (immutable, bytes-first) and Semantic Containers (Collections - mutable, for transformations). Clear distinction between encoding context (`OpenContext`) and session state (`Negotiated`).

---

## Key Concepts

### OpenContext vs Negotiated

| Aspect | `OpenContext` | `Negotiated` |
|--------|---------------|--------------|
| **Purpose** | How data WAS/WILL BE encoded on wire | What the session allows & capabilities |
| **Scope** | Per AFI/SAFI encoding | Session-wide |
| **Contains** | Wire format parameters | Session state & capabilities |
| **Mutability** | Immutable, cacheable | Immutable after OPEN exchange |
| **References** | None (value object) | `neighbor`, OPEN messages |
| **Caching** | By parameter tuple | Should use factory (future) |

**`OpenContext`** = Encoding context for a specific AFI/SAFI
- `afi`, `safi` - Address family for this encoding
- `addpath` - Whether AddPath is used in this encoding
- `asn4` - Whether 4-byte ASNs are used
- `msg_size` - Max message size
- `local_as`, `peer_as` - For IBGP vs EBGP attribute handling
- `is_ibgp` - Derived property (`local_as == peer_as`)

**`Negotiated`** = Session-wide immutable state (after OPEN exchange)
- `families` - Allowed AFI/SAFIs for this session
- `neighbor` - Peer session info (for next-hop-self)
- `aigp` - AIGP capability enabled
- `asn4`, `local_as`, `peer_as` - Session-wide values
- `required(afi, safi)` - Query AddPath status per family
- `nlri_context(afi, safi)` - Factory to get cached `OpenContext`
- `is_ibgp` - Derived property (`local_as == peer_as`)

### When to Use Which

| Operation | Use | Reason |
|-----------|-----|--------|
| Decode NLRI bytes | `OpenContext` | Wire format parameters |
| Encode NLRI to bytes | `OpenContext` | Target encoding format |
| Pack attributes | `Negotiated` | Need `aigp` capability |
| Filter NLRIs by allowed families | `Negotiated` | Session policy |
| Next-hop-self replacement | `Negotiated` | Needs `neighbor` |
| Check AIGP capability | `Negotiated` | Session capability |
| Store in MPRNLRI/MPURNLRI | `OpenContext` | Lightweight, per-family |

---

## Design Principles

### Wire Container (Update, MPRNLRI, MPURNLRI, NLRICollection)

- **Immutable** after creation
- Stores `_packed: bytes` (canonical wire representation)
- `MPRNLRI`/`MPURNLRI`/`NLRICollection` store `_context: OpenContext` (encoding params)
- `Update` stores `_negotiated: Negotiated` (needs full session for parsing)
- `pack()` → returns `_packed` (already encoded)
- Parsing yields semantic objects

### Semantic Container (UpdateCollection, AttributeCollection)

- **Mutable** - can add/remove/modify components
- Stores parsed semantic objects
- `pack(negotiated)` → creates wire bytes for target session

### OpenContext Structure

```python
class OpenContext:
    __slots__ = ('afi', 'safi', 'addpath', 'asn4', 'msg_size', 'local_as', 'peer_as')

    _cache: ClassVar[dict[tuple, OpenContext]] = {}

    @property
    def is_ibgp(self) -> bool:
        return self.local_as == self.peer_as

    @classmethod
    def make_open_context(cls, afi, safi, addpath, asn4, msg_size, local_as, peer_as):
        # Factory with caching by parameter tuple
        key = (afi, safi, addpath, asn4, msg_size, local_as, peer_as)
        if key not in cls._cache:
            cls._cache[key] = cls(...)
        return cls._cache[key]
```

### Negotiated Structure

```python
class Negotiated:
    # Set once during OPEN exchange, immutable after
    local_as: ASN
    peer_as: ASN
    asn4: bool
    aigp: bool
    families: list[tuple[AFI, SAFI]]
    neighbor: Neighbor
    # ... other session state

    @property
    def is_ibgp(self) -> bool:
        return self.local_as == self.peer_as

    def nlri_context(self, afi: AFI, safi: SAFI) -> OpenContext:
        # Returns cached OpenContext for this AFI/SAFI
        return OpenContext.make_open_context(
            afi, safi, self.required(afi, safi),
            self.asn4, self.msg_size, self.local_as, self.peer_as
        )
```

---

## Implementation Status

### Phase 1: Update/UpdateCollection Separation ✅ COMPLETE

- Update stores `_negotiated`, no `_parsed` caching
- Callers use `update.data` or `update.parse()`
- All tests pass

### Phase 2: Add ASNs to OpenContext ✅ COMPLETE

Changes made:
1. `OpenContext` has `local_as`, `peer_as` fields
2. `OpenContext` has `is_ibgp` property
3. `Negotiated` has `is_ibgp` property
4. `Negotiated.nlri_context()` passes ASN values to `OpenContext`
5. All tests pass (11/11)

**Not changed:**
- `pack_attribute()` methods still use `Negotiated` (need `aigp` capability)
- `Update` still stores `Negotiated` (needs full session for parsing)

---

## Findings & Design Decisions

### Why `Update` Stores `Negotiated` (not `OpenContext`)

`Update.parse()` → `UpdateCollection._parse_payload()` requires:
1. **`negotiated.families`** - Filter which NLRIs to process
2. **`negotiated.neighbor`** - Next-hop-self feature
3. **`negotiated.required(afi, safi)`** - AddPath status per family

These are session-level concerns, not encoding concerns.

### Why `pack_attribute()` Uses `Negotiated` (not `OpenContext`)

`AIGP.pack_attribute()` needs:
- `negotiated.aigp` - capability flag (not in `OpenContext`)
- `negotiated.is_ibgp` - for IBGP-only attribute handling

Other attributes like `ASPath`, `Aggregator` only need `asn4`, but for consistency all use `Negotiated`.

### Why `MPRNLRI`/`MPURNLRI`/`NLRICollection` Use `OpenContext`

These store per-AFI/SAFI encoding context:
- Lightweight (7 fields vs full Negotiated)
- Cacheable by parameter tuple
- No session references
- Hashable (can be used as cache key)

### Next-Hop Resolution (Future Consideration)

Currently next-hop validation happens during UPDATE parsing, coupling parsing to neighbor session state.

**Better design:** Resolve next-hop at NLRI **creation time**:
- Remove `NextHopSelf` sentinel class
- NLRI contains actual IP address
- Parsing wouldn't need `neighbor` reference

This would enable `Update` to store `OpenContext` instead of `Negotiated`.

### Negotiated Caching (Future Consideration)

`Negotiated` should be created via a factory method (like `OpenContext.make_open_context`) to enable caching. Currently uses `__init__` directly.

---

## Success Criteria

Phase 1:
- [x] Update has no `_parsed` caching
- [x] Update has `_negotiated` stored
- [x] All callers use `update.data` or `update.parse()`
- [x] All tests pass

Phase 2:
- [x] OpenContext has `local_as`, `peer_as` fields
- [x] OpenContext has `is_ibgp` property
- [x] Negotiated has `is_ibgp` property
- [x] `Negotiated.nlri_context()` passes ASN values
- [x] All tests pass (11/11)

---

## Phase 3: Negotiated Factory Method ✅ COMPLETE

**Goal:** Create `Negotiated` via factory method `make_negotiated()` instead of `__init__` directly.

### Why

- Consistency with `OpenContext.make_open_context()` pattern
- Enable future caching if needed
- Cleaner API - factory methods are the standard pattern

### Implementation

```python
class Negotiated:
    @classmethod
    def make_negotiated(cls, neighbor: Neighbor, direction: Direction) -> Negotiated:
        """Factory method to create Negotiated instances."""
        return cls(neighbor, direction)

    def __init__(self, neighbor: Neighbor, direction: Direction) -> None:
        # Internal - use make_negotiated() instead
        ...
```

### Changes Made

1. Added `make_negotiated()` classmethod to `Negotiated`
2. Updated 5 src callers to use factory method
3. Updated 25 test callers to use factory method

### Success Criteria

- [x] `Negotiated.make_negotiated()` factory method exists
- [x] All callers use factory method
- [x] All tests pass (11/11)

---

## Future Considerations

1. **Next-hop resolution refactoring** - Resolve at NLRI creation, remove `neighbor` dependency from parsing
2. **Update caching by OpenContext** - Cache wire-format Updates for zero-copy forwarding

---

**Updated:** 2025-12-08
