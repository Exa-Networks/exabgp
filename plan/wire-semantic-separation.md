# Wire vs Semantic Container Separation

**Status:** 🔄 Phase 1 Complete, Phase 2 Revised
**Created:** 2025-12-07
**Updated:** 2025-12-08

## Goal

Enforce strict separation between Wire Containers (immutable, bytes-first) and Semantic Containers (Collections - mutable, for transformations). Use `OpenContext` (not full `Negotiated`) for encoding context.

---

## Design Principles

### Wire Container (Update, Attribute, NLRI)

- **Immutable** after creation
- Stores `_packed: bytes` (canonical wire representation)
- Stores `_context: OpenContext` (encoding parameters)
- `pack_message()` / `pack()` → just return `_packed` with header
- `parse()` → returns NEW Semantic Container

### Semantic Container (UpdateCollection, AttributeCollection, NLRICollection)

- **Mutable** - can add/remove/modify components
- Stores parsed semantic objects
- `pack(context)` → creates NEW Wire Container for target capabilities

### OpenContext (encoding context)

Minimal context for encoding/decoding, replacing full `Negotiated`:

```python
class OpenContext:
    __slots__ = ('afi', 'safi', 'addpath', 'asn4', 'msg_size', 'local_as', 'peer_as')

    # Derived property
    @property
    def is_ibgp(self) -> bool:
        return self.local_as == self.peer_as
```

**Fields:**
- `afi`, `safi` - Address family
- `addpath` - ADD-PATH enabled for this family
- `asn4` - 4-byte ASN mode
- `msg_size` - Max message size (4096 or 65535)
- `local_as`, `peer_as` - For AS_PATH handling (IBGP vs EBGP)

---

## Implementation Phases

### Phase 1: Update/UpdateCollection Separation ✅ COMPLETE

- Update stores `_negotiated`, no `_parsed` caching
- Callers use `update.data` or `update.parse()`
- All tests pass

### Phase 2: Add ASNs to OpenContext and migrate from Negotiated

**Goal:** Replace `Negotiated` with `OpenContext` where only encoding context is needed.

#### 2.1 Extend OpenContext

Add `local_as` and `peer_as` to OpenContext:

```python
class OpenContext:
    __slots__ = ('afi', 'safi', 'addpath', 'asn4', 'msg_size', 'local_as', 'peer_as')

    _cache: ClassVar[dict[tuple[AFI, SAFI, bool, bool, int, ASN, ASN], 'OpenContext']] = {}

    def __init__(self, afi, safi, addpath, asn4, msg_size, local_as, peer_as):
        self.afi = afi
        self.safi = safi
        self.addpath = addpath
        self.asn4 = asn4
        self.msg_size = msg_size
        self.local_as = local_as
        self.peer_as = peer_as

    @property
    def is_ibgp(self) -> bool:
        return self.local_as == self.peer_as

    @classmethod
    def make_open_context(cls, afi, safi, addpath, asn4, msg_size, local_as, peer_as):
        key = (afi, safi, addpath, asn4, msg_size, local_as, peer_as)
        if key not in cls._cache:
            cls._cache[key] = cls(afi, safi, addpath, asn4, msg_size, local_as, peer_as)
        return cls._cache[key]
```

#### 2.2 Update Negotiated.nlri_context()

```python
def nlri_context(self, afi: AFI, safi: SAFI) -> OpenContext:
    return OpenContext.make_open_context(
        afi=afi,
        safi=safi,
        addpath=self.required(afi, safi),
        asn4=self.asn4,
        msg_size=self.msg_size,
        local_as=self.local_as,
        peer_as=self.peer_as,
    )
```

#### 2.3 Update class changes

Change from storing full Negotiated to OpenContext:

```python
class Update(Message):
    def __init__(self, packed: Buffer, context: OpenContext | None = None) -> None:
        self._packed = packed
        self._context = context  # Was: _negotiated: Negotiated
```

#### 2.4 AttributeCollection.pack_attribute() changes

Change signature from `Negotiated` to `OpenContext`:

```python
def pack_attribute(self, context: OpenContext, with_default: bool = True) -> bytes:
    local_asn = context.local_as
    peer_asn = context.peer_as
    # ... rest unchanged
```

#### 2.5 Individual Attribute classes

Update `pack_attribute()` signatures:

| Class | Current | New |
|-------|---------|-----|
| ASPath | `pack_attribute(negotiated: Negotiated)` | `pack_attribute(context: OpenContext)` |
| Aggregator | `pack_attribute(negotiated: Negotiated)` | `pack_attribute(context: OpenContext)` |
| All others | `pack_attribute(negotiated: Negotiated)` | `pack_attribute(context: OpenContext)` |

Most attribute classes only use `negotiated` for the signature - they don't access any fields. These can be changed to accept `OpenContext` with minimal impact.

**Classes that actually use Negotiated fields:**
- `ASPath.pack_attribute()` - uses `asn4` for AS format
- `Aggregator.pack_attribute()` - uses `asn4`
- `AttributeCollection.pack_attribute()` - uses `local_as`, `peer_as`

All these fields will be available in OpenContext.

---

## Files to Modify

### Phase 2

| File | Changes |
|------|---------|
| `src/exabgp/bgp/message/open/capability/negotiated.py` | Add `local_as`, `peer_as` to OpenContext |
| `src/exabgp/bgp/message/update/__init__.py` | Change `_negotiated` to `_context: OpenContext` |
| `src/exabgp/bgp/message/update/attribute/collection.py` | Change `pack_attribute(negotiated)` to `pack_attribute(context)` |
| `src/exabgp/bgp/message/update/attribute/*.py` | Update `pack_attribute()` signatures (25+ files) |
| `src/exabgp/bgp/message/update/collection.py` | Update `messages()` to use OpenContext |

---

## Benefits

1. **Lightweight context** - OpenContext is ~7 fields vs Negotiated with neighbor refs
2. **Cacheable** - Same OpenContext reused for identical parameters
3. **Hashable** - Can be used as cache key for Update wire format caching
4. **Decoupled** - No reference to peer/session state
5. **Zero-copy forwarding** - Compare source/dest OpenContext for compatibility

---

## Success Criteria

Phase 1:
- [x] Update has no `_parsed` caching
- [x] Update has `_negotiated` stored
- [x] All callers use `update.data` or `update.parse()`
- [x] All tests pass

Phase 2:
- [ ] OpenContext has `local_as`, `peer_as` fields
- [ ] OpenContext has `is_ibgp` property
- [ ] Update stores `_context: OpenContext` (not Negotiated)
- [ ] `pack_attribute()` methods accept OpenContext
- [ ] All tests pass

---

## Resume Point

**Phase 1 COMPLETE** ✅

**Next action:** Phase 2.1 - Add `local_as`, `peer_as` to OpenContext

---

**Updated:** 2025-12-08
