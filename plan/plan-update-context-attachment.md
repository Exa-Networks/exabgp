# Attach OpenContext to Update + Global Update Cache

**Status:** 📋 Planning
**Created:** 2025-12-07
**Updated:** 2025-12-08

## Goal

1. Assign unique IDs to Updates (hash of wire bytes) for API reference
2. Create global shared cache for all Inbound RIBs
3. Track sender context for zero-copy forwarding decisions
4. Prevent sending updates back to original sender

---

## Important Distinction: Update Cache vs AdjRIB Cache

**This plan covers Update caching — NOT AdjRIB caching.**

| Aspect | Update Cache (this plan) | AdjRIB Cache (separate) |
|--------|--------------------------|-------------------------|
| **Purpose** | API reference, zero-copy forwarding | Route-refresh (RFC 2918) |
| **What's cached** | Wire bytes of UPDATE messages | Semantic routes per peer |
| **Key** | SHA256 hash of wire bytes | (prefix, path-id, peer) |
| **Lifetime** | TTL-based (default 1h) | Per-peer session lifetime |
| **Scope** | Global, shared across all peers | Per-peer Adj-RIB-In |
| **Use case** | `announce hash <id>`, forwarding | `route-refresh` capability response |

**AdjRIB caching is a separate feature** for route-refresh support.

---

## Design Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Global UpdateCache                          │
│                                                                 │
│  Key: content_hash (SHA256 of wire bytes)                       │
│  Value: CacheEntry                                              │
│    ├── update: Update (wire bytes + source_context)             │
│    ├── source_context: OpenContext (sender's capabilities)      │
│    ├── senders: set[PeerID] (peers who sent this update)        │
│    ├── expires: datetime (default: now + 1h)                    │
│    └── pinned: bool (True = never expire, for local updates)    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Update ID

**Format:** SHA256 hash of wire bytes (hex string, 64 chars)

```python
import hashlib

def compute_update_id(wire_bytes: bytes) -> str:
    return hashlib.sha256(wire_bytes).hexdigest()
```

**Benefits:**
- Collision-resistant (unlike Python's `hash()`)
- Content-addressable: same wire bytes → same ID
- Natural deduplication: identical updates share cache entry

---

## Cache Behavior

### TTL-based FIFO

- Default TTL: 1 hour
- Configurable via `exabgp_cache_update_ttl` (seconds)
- `pinned=True` → never expires (for local/API-generated updates)

### Sender Tracking

When Update received from Peer A:
1. Compute hash → lookup/create entry
2. Add Peer A to `senders` set
3. Peer A remains in `senders` until entry expires

When forwarding to `neighbor *`:
- Skip all peers in `senders` set (prevents sending back to originator)

### API Commands

| Command | Behavior |
|---------|----------|
| `show update <hash>` | Return update details from cache |
| `neighbor <selector> announce hash <id>` | Announce cached update to neighbor(s) |
| `neighbor * announce hash <id>` | Announce to all except original senders |

**Error handling:** If update not in cache (expired), command fails with error.

### JSON Output

Extend Update JSON representation to include hash:

```json
{
  "update": {
    "hash": "a1b2c3d4e5f6...",
    "attribute": { ... },
    "announce": { ... },
    "withdraw": { ... }
  }
}
```

This allows external processes to:
1. Receive update with hash
2. Store hash for later reference
3. Use `neighbor <selector> announce hash <id>` to re-announce

---

## Source Context

Each Update stores the `OpenContext` of the connection it was received on:

```python
class Update:
    _packed: bytes           # Wire bytes
    _source_context: OpenContext  # Sender's capabilities

    @property
    def id(self) -> str:
        """SHA256 hash of wire bytes."""
        return hashlib.sha256(self._packed).hexdigest()
```

### Zero-Copy Forwarding Decision

```python
def can_forward_zerocopy(update: Update, dest_context: OpenContext) -> bool:
    """Check if update can be forwarded without repacking."""
    return update.source_context.transmission_compatible(dest_context)
```

**Compatible when:**
- Same ASN4 capability (2-byte vs 4-byte AS numbers)
- Same ADD-PATH capability for the family
- Message size >= update size
- Same IBGP/EBGP context (affects AS_PATH handling)

---

## Configuration

```python
# src/exabgp/environment/config.py

class CacheSection(ConfigSection):
    attributes: bool = option(True, 'cache all attributes for faster parsing')
    nexthops: bool = option(True, 'cache routes next-hops (deprecated)')
    updates: bool = option(True, 'cache UPDATE wire format')
    update_ttl: int = option(3600, 'UPDATE cache TTL in seconds (default 1h)')
```

---

## Components

### 1. UpdateCache (new class)

```python
# src/exabgp/rib/cache.py

class CacheEntry:
    __slots__ = ('update', 'source_context', 'senders', 'expires', 'pinned')

    update: Update
    source_context: OpenContext
    senders: set[str]  # Peer IDs
    expires: float     # time.monotonic() timestamp
    pinned: bool       # Never expire

class UpdateCache:
    _entries: dict[str, CacheEntry]  # hash -> entry
    _ttl: int  # seconds

    def store(self, update: Update, source_context: OpenContext,
              sender_id: str, pinned: bool = False) -> str:
        """Store update, return hash ID."""

    def get(self, update_id: str) -> CacheEntry | None:
        """Get entry, returns None if expired/missing."""

    def is_sender(self, update_id: str, peer_id: str) -> bool:
        """Check if peer is in senders set."""

    def prune_expired(self) -> int:
        """Remove expired entries, return count removed."""
```

### 2. Update class changes

```python
class Update:
    _packed: bytes
    _source_context: OpenContext | None  # None for locally-generated

    @cached_property
    def id(self) -> str:
        return hashlib.sha256(self._packed).hexdigest()

    @property
    def source_context(self) -> OpenContext | None:
        return self._source_context
```

### 3. OpenContext extension

Add `transmission_compatible()` method:

```python
class OpenContext:
    def transmission_compatible(self, other: 'OpenContext') -> bool:
        """Check if wire format is compatible for zero-copy forwarding."""
        return (
            self.asn4 == other.asn4 and
            self.addpath == other.addpath and
            self.msg_size <= other.msg_size and
            self.is_ibgp == other.is_ibgp
        )
```

---

## Files to Modify/Create

| File | Change |
|------|--------|
| `src/exabgp/rib/cache.py` | **NEW:** UpdateCache, CacheEntry classes |
| `src/exabgp/bgp/message/update/__init__.py` | Add `id`, `source_context` to Update |
| `src/exabgp/bgp/message/open/capability/negotiated.py` | Add `is_ibgp` to OpenContext, add `transmission_compatible()` |
| `src/exabgp/environment/config.py` | Add `update_ttl` to CacheSection |
| `src/exabgp/reactor/peer.py` | Wire UpdateCache into inbound path |
| `src/exabgp/reactor/api/command/` | Add `announce hash` command handler |
| `src/exabgp/reactor/api/response/` | Add JSON encoder for hash field |
| `tests/unit/rib/test_cache.py` | **NEW:** Cache tests |

---

## Implementation Steps

### Phase 1: Core Infrastructure

- [ ] Add `is_ibgp` to OpenContext
- [ ] Add `transmission_compatible()` to OpenContext
- [ ] Create `UpdateCache` class with TTL-based expiry
- [ ] Add `id` property to Update (SHA256)
- [ ] Add `source_context` to Update

### Phase 2: Integration

- [ ] Wire UpdateCache as singleton in Reactor
- [ ] Store received Updates in cache (inbound path)
- [ ] Track senders in cache entries
- [ ] Add configuration for TTL

### Phase 3: API & JSON

- [ ] Add `hash` field to Update JSON output
- [ ] `show update <hash>` - display cached update details
- [ ] `neighbor <selector> announce hash <id>` - announce cached update
- [ ] `neighbor * announce hash <id>` - announce to all except senders
- [ ] Error handling for expired/missing updates (command fails with message)

### Phase 4: Zero-Copy Forwarding

- [ ] Check `transmission_compatible()` before forwarding
- [ ] Implement wire-bytes reuse path
- [ ] Implement repack fallback path

### Phase 5: Attribute-Level Reuse (requires extensive testing)

When full zero-copy isn't possible, reuse individual attribute packed bytes.

**Three optimization levels:**

| Level | Condition | Reuse |
|-------|-----------|-------|
| Full zero-copy | Contexts fully compatible | Entire Update wire bytes |
| Attribute reuse | Some attributes unchanged | Individual attribute packed bytes |
| Full repack | Everything changes | Nothing reused |

**Attributes safe to reuse (fixed size, unchanged):**
- [ ] ORIGIN (1 byte)
- [ ] MED (4 bytes)
- [ ] LOCAL_PREF (4 bytes)
- [ ] COMMUNITIES
- [ ] EXTENDED_COMMUNITIES
- [ ] LARGE_COMMUNITIES
- [ ] CLUSTER_LIST
- [ ] ORIGINATOR_ID

**Attributes that may change (regenerate):**
- [ ] AS_PATH (prepend for EBGP)
- [ ] NEXT_HOP (may change for EBGP)
- [ ] MP_REACH_NLRI (addpath changes wire format)
- [ ] MP_UNREACH_NLRI (addpath changes wire format)

**Implementation:**
- [ ] Add `Attribute.can_reuse(source_context, dest_context) -> bool`
- [ ] Add `Attribute.reuse_packed() -> bytes` to return cached wire bytes
- [ ] Modify Update packing to check reuse before regenerating
- [ ] Extensive test coverage for each attribute type
- [ ] Benchmark to verify actual performance gain

---

## Success Criteria

- [ ] Updates have stable SHA256-based IDs
- [ ] Global cache stores all received Updates
- [ ] Sender tracking prevents send-back loops
- [ ] API can reference updates by hash
- [ ] Commands fail gracefully for expired updates
- [ ] TTL-based expiry works (default 1h)
- [ ] `pinned=True` prevents expiry for local updates
- [ ] All existing tests pass

### Phase 5 Success Criteria (separate milestone)

- [ ] Each reusable attribute type tested for correct reuse
- [ ] Each non-reusable attribute type tested for correct regeneration
- [ ] IBGP→IBGP forwarding reuses most attributes
- [ ] EBGP→EBGP forwarding regenerates AS_PATH, reuses others
- [ ] Benchmark shows measurable performance improvement

---

## Future Extensions

- LRU eviction in addition to TTL
- Persistent cache across restarts
- Cache statistics API
- Per-peer cache views

---

**Updated:** 2025-12-08
