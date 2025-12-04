# Architecture: Circular Dependency Resolution

**Status:** 📋 Planning (not started)
**Priority:** Medium
**See also:** `type-safety/` (TYPE_CHECKING already used as workaround)

## Goal

Eliminate circular imports between modules to improve code organization, reduce coupling, and enable cleaner type checking.

## Current Circular Dependencies

### 1. `bgp/fsm.py` ↔ `reactor/peer/peer.py`

**Current state:**
- `fsm.py` imports `Peer` via `TYPE_CHECKING` (line 14)
- `peer.py` imports `FSM` directly (line 21)
- FSM stores reference to Peer: `self.peer: Peer`

**Why circular:**
- FSM needs Peer reference to call peer methods during state transitions
- Peer needs FSM to track connection state

**File locations:**
```
src/exabgp/bgp/fsm.py:14      → from exabgp.reactor.peer import Peer
src/exabgp/reactor/peer/peer.py:21 → from exabgp.bgp.fsm import FSM
```

### 2. `bgp/message/update/__init__.py` - Deferred Response Import

**Current state:**
- Update module has deferred import of Response (search for pattern)
- This is a workaround for circular dependency

**File location:**
```
src/exabgp/bgp/message/update/__init__.py
```

## Proposed Solutions

### Solution A: Extract Interface/Protocol (Recommended)

Create abstract base classes or protocols that define the interface without implementation:

```python
# src/exabgp/bgp/fsm_interface.py (NEW)
from typing import Protocol

class PeerInterface(Protocol):
    """Interface for Peer as seen by FSM."""
    def handle_state_change(self, old: int, new: int) -> None: ...
    def close(self) -> None: ...
    # ... minimal interface FSM needs

# src/exabgp/bgp/fsm.py
from exabgp.bgp.fsm_interface import PeerInterface

class FSM:
    peer: PeerInterface  # Uses interface, not concrete class
```

**Pros:**
- Clean separation of concerns
- Explicit interface documentation
- No import-time issues

**Cons:**
- Additional file to maintain
- Slight indirection

### Solution B: Dependency Injection

Pass dependencies at runtime rather than import time:

```python
# src/exabgp/bgp/fsm.py
class FSM:
    def __init__(self) -> None:
        self.peer = None  # Set later

    def set_peer(self, peer: 'Peer') -> None:
        self.peer = peer
```

**Pros:**
- Simple, no new files
- Already partially used (TYPE_CHECKING)

**Cons:**
- Delayed initialization can cause None errors
- Less explicit about requirements

### Solution C: Merge Modules

If FSM and Peer are tightly coupled, they may belong together:

```python
# src/exabgp/reactor/peer/peer.py
# Move FSM class into peer.py or peer/__init__.py
```

**Pros:**
- Eliminates the problem entirely
- Reflects actual coupling

**Cons:**
- Larger file
- May not make conceptual sense (FSM is BGP concept, Peer is reactor)

## Recommended Approach

**Solution A (Protocol)** for `fsm.py ↔ peer.py`:

1. Create `src/exabgp/bgp/peer_protocol.py`:
   ```python
   from typing import Protocol

   class PeerProtocol(Protocol):
       """Minimal interface FSM needs from Peer."""
       def close(self) -> None: ...
       # Add only methods FSM actually calls
   ```

2. Update `fsm.py` to use protocol instead of concrete class

3. No changes needed to `peer.py`

**For Update/Response:** Investigate what the actual dependency is before deciding.

## Files to Modify

| File | Change |
|------|--------|
| `src/exabgp/bgp/peer_protocol.py` | NEW - Protocol definition |
| `src/exabgp/bgp/fsm.py` | Use PeerProtocol instead of Peer |
| `src/exabgp/bgp/message/update/__init__.py` | TBD - investigate first |

## Investigation Required

Before implementation:

1. **Audit FSM → Peer calls**: What methods does FSM actually call on Peer?
   ```bash
   grep -n "self.peer\." src/exabgp/bgp/fsm.py
   ```

2. **Audit Update → Response**: Why is Response import deferred?
   ```bash
   grep -n "Response" src/exabgp/bgp/message/update/__init__.py
   ```

3. **Check other TYPE_CHECKING uses**: Are there other hidden circular deps?
   ```bash
   grep -rn "TYPE_CHECKING" src/exabgp/ | wc -l  # Currently 114 files
   ```

## Testing

After changes:
```bash
# Verify no import errors
python -c "from exabgp.bgp.fsm import FSM; from exabgp.reactor.peer import Peer"

# Full test suite
./qa/bin/test_everything
```

## Risks

| Risk | Mitigation |
|------|------------|
| Breaking existing code | TYPE_CHECKING already works; this is cleanup |
| Protocol too narrow | Audit actual usage before defining |
| Performance impact | Protocols have no runtime overhead |

---

**Last Updated:** 2025-12-04
