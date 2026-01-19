# Long-Lived Graceful Restart (LLGR) Implementation

📋 **Status:** Planning
**Issue:** [#292](https://github.com/Exa-Networks/exabgp/issues/292)
**RFC:** [RFC 9494](https://datatracker.ietf.org/doc/html/rfc9494) (Long-Lived Graceful Restart for BGP)
**Created:** 2025-01-16

---

## Overview

LLGR extends RFC 4724 Graceful Restart to allow routes to be retained for much longer periods (hours/days vs seconds/minutes). Critical for FlowSpec resilience during DDoS mitigation where BGP sessions may flap.

### Use Case (from issue #292)
- DDoS attacks shift between vectors (UDP → TCP → ICMP)
- BGP session loss causes FlowSpec rules to be removed
- Routes need to persist beyond normal GR timer
- LLGR allows "timeout until drop announces from disconnected peer"

---

## RFC 9494 Requirements

### 1. New Capability (Code 71 / 0x47)

```
+--------------------------------------------------+
| Long-Lived Graceful Restart Capability           |
+--------------------------------------------------+
| AFI (2) | SAFI (1) | Flags (1) | LLGR Time (3)   |
+--------------------------------------------------+
     ... (repeated for each address family) ...
```

- **Flags (1 byte):** Bit 0 = Forwarding State preserved
- **LLGR Time (3 bytes):** Stale time in seconds (0-16777215, ~194 days max)

### 2. Well-Known Communities

| Community | Value | Purpose |
|-----------|-------|---------|
| LLGR_STALE | 0xFFFF0006 | Mark routes as stale during LLGR |
| NO_LLGR | 0xFFFF0007 | Route should not be retained during LLGR |

### 3. Behavior

**Sender (ExaBGP as route server):**
- Advertise LLGR capability with supported families and timers
- On session restart: mark retained routes with LLGR_STALE community
- Routes with NO_LLGR community are withdrawn immediately

**Receiver (ExaBGP receiving routes):**
- Parse peer's LLGR capability
- On session loss: retain routes for LLGR timer (with LLGR_STALE)
- Prefer non-stale routes over stale routes (lower LOCAL_PREF equivalent)
- Honor NO_LLGR community (withdraw immediately)

---

## Implementation Plan

### Phase 1: Capability Support (Read-Only)

**Files to modify:**

1. `src/exabgp/bgp/message/open/capability/capability.py`
   - Add `LONG_LIVED_GRACEFUL_RESTART = 0x47` to CapabilityCode
   - Add to names dict

2. `src/exabgp/bgp/message/open/capability/llgr.py` (new)
   - Create `LLGR` class similar to `Graceful`
   - Store per-family: flags, LLGR time (3 bytes)
   - Implement `pack()`, `unpack_capability()`, `json()`, `__str__()`

3. `src/exabgp/bgp/message/open/capability/__init__.py`
   - Import LLGR class

**Tests:**
- Unit tests for pack/unpack round-trip
- Test capability negotiation with various family combinations

### Phase 2: Community Support

**Files to modify:**

1. `src/exabgp/bgp/message/update/attribute/community/community.py`
   - Add `LLGR_STALE = 0xFFFF0006`
   - Add `NO_LLGR = 0xFFFF0007`
   - Add to well-known community names

2. `src/exabgp/configuration/static/parser.py` (if needed)
   - Parse `llgr-stale` and `no-llgr` keywords

**Tests:**
- Community encoding/decoding
- Configuration parsing

### Phase 3: Configuration

**Files to modify:**

1. `src/exabgp/bgp/neighbor/capability.py`
   - Add `llgr` capability configuration
   - Per-family LLGR time settings

2. `src/exabgp/configuration/capability.py`
   - Parse LLGR configuration section

**Example configuration:**
```
neighbor 192.0.2.1 {
    capability {
        graceful-restart 120;
        long-lived-graceful-restart {
            ipv4 unicast 3600;      # 1 hour
            ipv4 flow 86400;        # 24 hours for FlowSpec
        }
    }
}
```

### Phase 4: Stale Route Handling

**Files to modify:**

1. `src/exabgp/rib/store.py` or `src/exabgp/rib/rib.py`
   - Track stale state per route
   - Timer management for LLGR expiry

2. `src/exabgp/reactor/peer/peer.py`
   - On session loss: mark routes stale (add LLGR_STALE community)
   - On session restore: remove LLGR_STALE community
   - On LLGR timer expiry: withdraw stale routes

3. `src/exabgp/bgp/fsm.py`
   - Integrate LLGR state into FSM transitions

**Complexity:** Simplified by lazy evaluation - no timer management needed.

### Phase 5: API Integration

**Files to modify:**

1. `src/exabgp/reactor/api/command/` (relevant files)
   - Expose LLGR state in JSON output
   - Allow manual stale marking via API

2. JSON output additions:
   - `"llgr": { "stale": true/false, "expires_in": N }`

---

## File Summary

| File | Action | Phase |
|------|--------|-------|
| `capability/capability.py` | Modify | 1 |
| `capability/llgr.py` | **New** | 1 |
| `capability/__init__.py` | Modify | 1 |
| `community/community.py` | Modify | 2 |
| `neighbor/capability.py` | Modify | 3 |
| `configuration/capability.py` | Modify | 3 |
| `rib/store.py` | Modify | 4 |
| `reactor/peer/peer.py` | Modify | 4 |
| `bgp/fsm.py` | Modify | 4 |
| `reactor/api/command/*.py` | Modify | 5 |

---

## Testing Requirements

### Unit Tests
- [ ] LLGR capability pack/unpack
- [ ] LLGR capability negotiation
- [ ] LLGR_STALE/NO_LLGR community encoding
- [ ] Configuration parsing
- [ ] Timer logic

### Functional Tests
- [ ] LLGR capability exchange with peer
- [ ] Route staling on session loss
- [ ] Route restoration on session restore
- [ ] LLGR timer expiry behavior
- [ ] NO_LLGR community handling

### Integration Tests
- [ ] Test with router supporting LLGR (Cisco XRv, Juniper vMX, FRR)
- [ ] FlowSpec retention during session flap

---

## Design Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Default LLGR time | **0 (disabled)** | Cisco default; must explicitly set per family |
| RIB storage | **In RIB entry** | Add stale flag + expiry timestamp to route |
| Timer implementation | **Lazy evaluation** | Check expiry on route access, no background timers |
| No LLGR peer | **Fall back to GR** | Use regular graceful restart timers only |

### Implications

**Lazy evaluation benefits:**
- No timer management complexity
- No background threads
- Routes naturally expire when accessed (announce/withdraw/lookup)
- Simpler implementation, fewer race conditions

**RIB entry storage:**
- Add `stale: bool` and `llgr_expiry: float | None` to route storage
- Check expiry on access: `if stale and time.time() > llgr_expiry: withdraw()`

---

## References

- [RFC 9494](https://datatracker.ietf.org/doc/html/rfc9494) - Long-Lived Graceful Restart for BGP
- [RFC 4724](https://datatracker.ietf.org/doc/html/rfc4724) - Graceful Restart Mechanism for BGP
- [GitHub Issue #292](https://github.com/Exa-Networks/exabgp/issues/292) - Original feature request
- `src/exabgp/bgp/message/open/capability/graceful.py` - Existing GR implementation

---

## Progress

| Phase | Status | Notes |
|-------|--------|-------|
| 1. Capability | 📋 Not started | |
| 2. Community | 📋 Not started | |
| 3. Configuration | 📋 Not started | |
| 4. Stale Handling | 📋 Not started | Most complex |
| 5. API | 📋 Not started | |

---

**Estimated effort:** Medium (1-2 weeks) - simplified by lazy evaluation
**Priority:** Medium (addresses long-standing feature request)
**Dependencies:** None (builds on existing GR infrastructure)
