# Plan: Migrate .run Scripts to exabgp_api Library

**Status:** ✅ COMPLETE (2025-12-05)
**Scope:** 31 scripts migrated, 9 skipped (test frameworks)

## Summary

Successfully migrated `.run` scripts in `etc/exabgp/run/` to use the shared `exabgp_api.py` library, eliminating duplicated `wait_for_ack()`, `flush()`, and `wait_for_shutdown()` implementations.

**Library location:** `etc/exabgp/run/exabgp_api.py`
**Reference example:** `api-announce.run`

---

## Migration Results

| Phase | Scripts | Status |
|-------|---------|--------|
| Phase 1: Simple | 12 | ✅ Migrated |
| Phase 2: Medium | 17 | ✅ Migrated |
| Phase 3: Complex | 2 | ✅ Migrated |
| **Total Migrated** | **31** | ✅ |
| Skipped (test frameworks) | 9 | N/A |

---

## Migrated Scripts (31)

### Phase 1: Simple Scripts (12)
- `api-ipv4.run`
- `api-ipv6.run`
- `api-eor.run`
- `api-nexthop.run`
- `api-multiple-public.run`
- `api-multiple-private.run`
- `api-vpnv4.run`
- `api-multisession.run`
- `api-no-respawn-1.run`
- `api-no-respawn-2.run`
- `api-fast.run`
- `watchdog.run`

### Phase 2: Medium Scripts (17)
- `api-add-remove.run`
- `api-announce-star.run`
- `api-announcement.run`
- `api-attributes.run`
- `api-attributes-path.run`
- `api-attributes-vpn.run`
- `api-broken-flow.run`
- `api-flow.run`
- `api-flow-merge.run`
- `api-manual-eor.run`
- `api-multi-neighbor.run`
- `api-mvpn.run`
- `api-nexthop-self.run`
- `api-notification.run`
- `api-peer-lifecycle.run`
- `api-reload.run`
- `api-rib.run`
- `api-rr-rib.run`
- `api-teardown.run`
- `api-vpls.run`

### Phase 3: Complex Scripts (2)
- `api-ack-control.run` - ACK control flow testing
- `api-silence-ack.run` - Silence ACK testing

---

## Skipped Scripts (9) - Test Frameworks with Custom I/O

These scripts need custom stdin handling for specific test logic and were intentionally kept as-is:

1. `api-simple.run` - Tests version/ping/status/shutdown commands
2. `api-check.run` - Reads stdin for specific update messages
3. `api-health.run` - Tests ping/status with custom validation
4. `api-no-neighbor.run` - Tests version/shutdown without neighbors
5. `api-open.run` - Expects 'open' JSON message from stdin
6. `api-api.nothing.run` - Reads stdin first line to check for shutdown
7. `api-rr.run` - Reads route-refresh responses from stdin
8. `api-api.receive.run` - Long-running loop processing BGP updates
9. `api-blocklist.run` - Multi-threaded blocklist fetcher with threads + external libs

---

## Test Results

All tests pass after migration:
```
✓ All 9 tests passed in 35.2s
```

---

## Migration Pattern Applied

**Before (110+ lines):**
```python
import json, os, select, signal, sys, time
def wait_for_ack(...): ...  # 40 lines
def flush(...): ...         # 3 lines
def main(): ...
signal.signal(SIGPIPE, SIG_DFL)
```

**After (20-30 lines):**
```python
from exabgp_api import send, wait_for_ack, wait_for_shutdown
def main(): ...
```

Key benefits:
- Reduced code duplication
- Centralized SIGPIPE handling in library
- Consistent ACK handling across all scripts
- Easier maintenance
