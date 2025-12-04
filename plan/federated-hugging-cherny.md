# CLI Multi-Client Connection Issues - Analysis & Fix Plan

**Date:** 2024-12-04
**Status:** ✅ All fixes implemented and tested

---

## Summary

Analysis of ExaBGP's CLI disconnection/reconnection handling revealed several issues with multi-client mode.

---

## Issues Found

### 1. CRITICAL: Race Condition in Multi-Client Response Routing

**File:** `src/exabgp/application/unixsocket.py:515-518`

**Problem:** `active_command_client` is set without synchronization. When two clients send commands close together, responses can be routed to the wrong client.

```python
def make_std_writer_for_client(client_fd: int):
    def writer(line: bytes) -> int:
        self.response_router.active_command_client = client_fd  # NO LOCK!
        return os.write(standard_out, line)
```

**Impact:** Client A's response may be delivered to Client B.

---

### 2. Commands Lost on Daemon Restart

**File:** `src/exabgp/cli/persistent_connection.py:273, 360-366`

**Problem:** If daemon restarts while a command is in-flight:
- Response queue is cleared during reconnection
- User gets "Timeout waiting for response"
- Command is NOT retried

---

### 3. Stale Socket TOCTOU Race

**File:** `src/exabgp/application/unixsocket.py:200-227`

**Problem:** Time-of-check to time-of-use race between checking if socket is stale and binding:
1. Check: socket appears stale
2. Unlink stale socket
3. Another daemon starts and binds ← race window
4. Our daemon tries to bind → EADDRINUSE

---

## What Works Well

- Daemon UUID tracking detects restarts
- Stale socket cleanup removes dead sockets
- Client disconnect notification (`bye` command)
- Health monitor pauses during reconnection
- 15-second stale client timeout

---

## Recommended Fixes

### Fix 1: Add Request ID to Response Routing (addresses issue #1)

Instead of tracking "active client", add a request ID to each command and include it in responses.

**Changes:**
- `ResponseRouter`: Track `pending_requests: dict[str, int]` mapping request_id → client_fd
- Client sends: `ping <uuid> <timestamp> <request_id>`
- Server response: `pong <daemon_uuid> active=true request_id=<id>`
- Route responses by request_id, not active_command_client

### Fix 2: Add Lock Around active_command_client (simpler alternative to Fix 1)

Add `threading.Lock()` around `active_command_client` access.

**Pros:** Simple, minimal change
**Cons:** Doesn't fully solve the problem if commands overlap

### Fix 3: Command Retry on Reconnect (addresses issue #2)

Store last command, retry after successful reconnection.

**Changes:**
- `persistent_connection.py`: Store `last_command` before sending
- After `_reconnect()` succeeds, check if command was in progress
- Retry with deduplication (don't double-announce)

---

## Implementation Complete

All three fixes have been implemented:

### Fix 1: Request ID Response Routing ✅
- Added `pending_requests: dict[str, int]` to `ResponseRouter`
- Added `register_request()` and `_extract_request_id()` methods
- Responses are now routed by request_id first, then fall back to active_command_client
- Supports both text format (`request_id=<id>`) and JSON format (`{"request_id": "<id>"}`)

### Fix 2: Thread-Safe active_command_client ✅
- Added `threading.Lock()` to `ResponseRouter`
- Added `set_active_client()` method for thread-safe access
- Updated `_disconnect_client()` to use lock when clearing active client
- Updated `make_std_writer_for_client()` to use thread-safe setter

### Fix 3: Command Retry on Reconnect ✅
- Added `_last_command`, `_command_needs_retry`, and `_request_id_counter` to `PersistentSocketConnection`
- Added `_generate_request_id()` method
- `send_command()` now stores last command and tracks retry flag
- `_reconnect()` checks for pending commands and retries after successful reconnection

---

## Files Modified

| File | Changes |
|------|---------|
| `src/exabgp/application/unixsocket.py` | Added threading import, ResponseRouter lock, request ID tracking, thread-safe methods |
| `src/exabgp/cli/persistent_connection.py` | Added request ID generation, command retry logic |
| `tests/unit/test_cli_transport.py` | Added TestResponseRouter and TestPersistentConnectionRetry test classes |

---

## Test Results

```
✓ All 9 tests passed (28.1s)
```
