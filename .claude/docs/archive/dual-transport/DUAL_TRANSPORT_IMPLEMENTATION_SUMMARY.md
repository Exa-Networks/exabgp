# Dual Transport API Implementation Summary

**Date:** 2025-11-19
**Status:** ✅ IMPLEMENTED AND TESTED

---

## Overview

Successfully implemented dual-transport CLI API for ExaBGP, allowing both named pipe and Unix socket based communication to run simultaneously. The CLI defaults to Unix socket but can use pipes via explicit flag.

---

## Files Created

### `src/exabgp/application/unixsocket.py` (NEW)
- Unix socket server implementation for CLI control
- Similar architecture to `pipe.py` but using Unix domain sockets
- Supports bidirectional communication over single socket
- Handles stale socket cleanup and single-connection model
- Functions:
  - `unix_socket()` - Socket path discovery
  - `Control` class - Socket server with event loop
  - `main()` - Entry point when `exabgp_cli_socket` is set

---

## Files Modified

### `src/exabgp/configuration/process/__init__.py`
**Modified:** `add_api()` method (lines 73-102)
- Now checks BOTH `exabgp_cli_pipe` AND `exabgp_cli_socket`
- Creates separate process entries for each enabled transport
- Both use same `API_PREFIX` (`api-internal-cli-{uuid}`) for routing

### `src/exabgp/application/main.py`
**Modified:** `main()` function (lines 31-36)
- Added socket mode detection after pipe mode
- Imports and calls `unixsocket.main()` when `exabgp_cli_socket` is set

### `src/exabgp/application/server.py`
**Modified:** `cmdline()` function (lines 207-238)
- Added Unix socket availability check at startup (similar to pipe check)
- Displays warning messages if socket directory not found
- Provides helpful commands to create socket directory
- Shows `mkdir`, `chmod`, `chown` commands
- Informs user socket will be auto-created when API process starts
- Confirms socket path in logs when directory exists

### `src/exabgp/application/cli.py`
**Major refactoring:**
1. **Added imports:**
   - `import socket as sock` (stdlib socket library)
   - `from exabgp.application.unixsocket import unix_socket`

2. **Modified `setargs()` function:**
   - Added `--pipe` flag (force pipe transport)
   - Added `--socket` flag (force socket transport)
   - Flags are mutually exclusive

3. **Added `send_command_socket()` function:**
   - Connects to Unix socket
   - Sends command
   - Receives and displays response
   - Handles timeouts and errors

4. **Modified `cmdline()` function:**
   - Transport selection logic:
     1. Check `exabgp_cli_transport` environment variable
     2. Check `--pipe` / `--socket` command-line flags
     3. Default to socket transport
   - Moved command nickname processing to main function
   - Routes to `cmdline_pipe()` or `cmdline_socket()` based on selection

5. **Created `cmdline_socket()` function:**
   - Discovers Unix socket path
   - Validates socket exists
   - Calls `send_command_socket()`

6. **Created `cmdline_pipe()` function:**
   - Contains original pipe-based CLI logic
   - Unchanged behavior for pipe transport

---

## Environment Variables

### Server-side (Process Spawning)
- `exabgp_cli_pipe` - Enable pipe-based internal CLI process (EXISTING)
- `exabgp_cli_socket` - Enable socket-based internal CLI process (NEW)
- `exabgp_api_socketpath` - Custom Unix socket path override (NEW, optional)

### Client-side (CLI Tool)
- `exabgp_cli_transport` - Override transport: "pipe" or "socket" (NEW)

---

## CLI Command-Line Flags

- `--pipe` - Force named pipe transport
- `--socket` - Force Unix socket transport (default behavior)
- `--pipename` - Custom pipe name (existing, for pipe transport)

---

## Transport Selection Logic

**Priority order (highest to lowest):**
1. **Command-line flags:** `--pipe` or `--socket` (highest priority)
2. **Environment variable:** `exabgp_cli_transport` ("pipe" or "socket")
3. **Default:** Unix socket

This ensures command-line flags always override environment variables, giving users explicit control.

---

## Testing Results

**✅ All tests PASSED:**

### Linting
```bash
ruff format src && ruff check src
```
- **Result:** All checks passed, 339 files processed

### Unit Tests
```bash
env exabgp_log_enable=false pytest ./tests/unit/ -q
```
- **Result:** 1424 passed in 4.25s
- **New tests added:** 20 CLI transport tests (`test_cli_transport.py`)
  - 6 tests for `unix_socket()` path discovery
  - 6 tests for argument parsing (--pipe, --socket flags)
  - 6 tests for transport selection logic
  - 2 tests for command shortcuts

### Functional Encoding Tests
```bash
./qa/bin/functional encoding
```
- **Result:** 72/72 passed (100%)

### Functional Decoding Tests
```bash
./qa/bin/functional decoding
```
- **Result:** 18/18 passed (100%)

### Configuration Validation
```bash
./sbin/exabgp validate -nrv ./etc/exabgp/conf-ipself6.conf
```
- **Result:** PASS

---

## Key Design Decisions

### 1. Module Naming
**Decision:** Renamed `socket.py` → `unixsocket.py`
**Reason:** Avoided name collision with Python stdlib `socket` module

### 2. Process Naming
**Decision:** Use format `api-internal-cli-{transport}-{uuid}` with transport suffix
**Examples:**
- Pipe: `api-internal-cli-pipe-a1b2c3d4`
- Socket: `api-internal-cli-socket-e5f6g7h8`

**Reason:**
- Prevents UUID collision (both spawn in same function)
- Routing uses `startswith(API_PREFIX)` - both still match
- Transport suffix guarantees uniqueness even with identical UUIDs

### 3. Default Transport
**Decision:** Default to Unix socket, not pipe
**Reason:**
- Sockets are bidirectional (simpler than dual FIFOs)
- Better connection semantics (connect/disconnect vs open/close)
- Modern standard for IPC

### 4. Concurrent Support
**Decision:** Both processes can run simultaneously
**Reason:**
- Allows gradual migration
- Supports mixed usage scenarios
- No breaking changes required

### 5. Socket Connection Model
**Decision:** Single connection at a time (like pipe semantics)
**Reason:**
- Matches existing pipe behavior
- Simpler implementation
- Sufficient for current use cases

---

## Architecture Comparison

### Before
```
CLI Tool → Named FIFO → Internal CLI Process → ExaBGP
            (.in/.out)      (pipe.py)
```

### After
```
                ┌─→ Named FIFO → Pipe Process ─┐
CLI Tool (flag) ┤    (.in/.out)    (pipe.py)   ├─→ ExaBGP
                └─→ Unix Socket → Socket Process ┘
                      (.sock)     (unixsocket.py)
```

---

## Socket Path Discovery

Same priority as pipes:
1. `/run/exabgp/`
2. `/run/{uid}/`
3. `/run/`
4. `/var/run/exabgp/`
5. `/var/run/{uid}/`
6. `/var/run/`
7. `{root}/run/exabgp/`
8. (+ more locations)

**Default socket name:** `exabgp.sock`
**Override:** Set `exabgp_api_socketpath` environment variable

---

## Usage Examples

### Starting ExaBGP with both transports

```bash
# Create named pipes
mkdir -p /tmp/exabgp
mkfifo /tmp/exabgp/exabgp.in /tmp/exabgp/exabgp.out

# Start with both enabled
env exabgp_cli_pipe=/tmp/exabgp \
    exabgp_cli_socket=/tmp/exabgp \
    ./sbin/exabgp etc/exabgp/api-rib.conf

# Both processes spawn with names like:
# - api-internal-cli-a1b2c3d4 (pipe)
# - api-internal-cli-e5f6g7h8 (socket)
```

### Using CLI with different transports

```bash
# Default (socket)
./sbin/exabgp cli "show neighbor"

# Explicit socket
./sbin/exabgp cli --socket "show neighbor"

# Force pipe
./sbin/exabgp cli --pipe "show neighbor"

# Environment variable override
env exabgp_cli_transport=pipe ./sbin/exabgp cli "show neighbor"
```

---

## Backward Compatibility

**✅ Fully backward compatible:**
- Existing pipe-based setups work unchanged
- No configuration file changes required
- CLI behavior identical for pipe transport
- `--pipe` flag provides explicit fallback
- Both transports can coexist

---

## Future Enhancements

### Potential Improvements
1. **Multiple simultaneous socket connections** - Currently single connection model
2. **WebSocket transport** - For remote CLI access
3. **Authentication/authorization** - For socket connections
4. **Metrics tracking** - Monitor which transport is used more

### Deprecation Path (Long-term)
1. Monitor usage statistics over time
2. If socket proves superior, consider pipe deprecation (years away)
3. Maintain both for backward compatibility indefinitely

---

## Notes

### Critical Fixes

**1. Module Name Collision**
Initial implementation used `socket.py` which shadowed Python's stdlib `socket` module, causing import errors in other parts of the codebase (specifically `exabgp/util/dns.py`). Renamed to `unixsocket.py` to avoid collision.

**2. Transport Selection Priority**
Initial implementation had incorrect priority (environment variable > flags). Fixed to correct priority:
1. Command-line flags (--pipe, --socket)
2. Environment variable (exabgp_cli_transport)
3. Default (socket)

This ensures users can always override environment settings with explicit flags.

### Process Routing
Both pipe and socket processes use the same `API_PREFIX` (`api-internal-cli-`) with transport-specific suffixes (`-pipe-` and `-socket-`), ensuring they both get matched to all peers automatically via the `startswith(API_PREFIX)` logic in `src/exabgp/reactor/loop.py:329-330`.

**UUID Collision Fix:** Initially both processes used `api-internal-cli-{uuid}` format. Since both UUIDs are generated in quick succession within the same function call, there was a risk of collision if both `uuid.uuid1()` calls happened within the same 100-nanosecond interval. Adding transport suffixes (`-pipe-` and `-socket-`) guarantees uniqueness even if UUIDs collide.

### Socket Management
The socket server automatically:
- **Creates directory** if it doesn't exist (mode `0o700`)
- **Creates socket file** when binding
- Detects and removes stale socket files (from crashes)
- Cleans up socket file on shutdown
- Handles single client connection at a time

**Zero-setup:** Unlike pipes (which require manual `mkfifo`), sockets are fully automatic - no user intervention needed!

### Startup Checks
Similar to named pipes, ExaBGP now checks for Unix socket availability at startup:
- **If socket directory not found:** Displays warning with helpful commands
- **Suggests:** `mkdir -p`, `chmod`, and `chown` commands
- **Informs:** Socket will be created automatically when socket-based API process starts
- **Shows:** How to enable via `exabgp_cli_socket` environment variable
- **If socket directory exists:** Confirms socket path in logs

---

## Documentation Updates Needed

- [ ] Add environment variables to user documentation
- [ ] Document CLI flags in help text/manpage
- [ ] Update examples showing both transports
- [ ] Migration guide from pipe to socket

---

**Last Updated:** 2025-11-19
