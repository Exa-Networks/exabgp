# Implementation Plan: Dual Transport API (Pipe + Unix Socket)

**Created:** 2025-11-19
**Status:** ✅ COMPLETED 2025-11-19 (Updated with socketname fixes)
**Goal:** Run both pipe-based and socket-based internal CLI processes simultaneously. CLI defaults to Unix socket but can use pipe via `--pipe` flag.

**Documentation:** See `docs/projects/cli-dual-transport/` for complete user and technical documentation.

## Implementation Status

**✅ Phase 1-3: COMPLETE** - All code implemented and tested
**✅ Phase 4: COMPLETE** - All tests passing (linting, unit, functional)
**⏳ Phase 5: IN PROGRESS** - Documentation being updated

---

## Architecture Overview

### Current State
```
CLI Tool → Named FIFO → Internal CLI Process (pipe.py) → stdin/stdout → ExaBGP Server
```

### Target State
```
                    ┌─→ Named FIFO → Pipe Process → stdin/stdout ─┐
CLI Tool (--flag) ──┤                                             ├─→ ExaBGP Server
                    └─→ Unix Socket → Socket Process → stdin/stdout ─┘
```

### Requirements Summary
- ✅ Both processes run simultaneously
- ✅ Same `API_PREFIX` for both (process name agnostic to transport)
- ✅ CLI uses command-line flag (`--pipe` vs `--socket`)
- ✅ Unix socket path is configurable
- ✅ Default to socket if no flag specified

---

## Phase 1: Create Unix Socket Server Module

### Step 1: Create `src/exabgp/application/socket.py`
**Files:** `src/exabgp/application/socket.py` (NEW)

**Implementation:**
- Create new module based on `pipe.py` structure
- Implement `Control` class with Unix socket server logic
- Handle single connection at a time (simpler, matches pipe semantics)
- Bidirectional forwarding: socket ↔ stdin/stdout
- Socket cleanup on shutdown (unlink socket file)
- Error handling for stale socket files

**Verification:**
```bash
ruff format src && ruff check src
```
**Expected:** All checks passed

---

### Step 2: Implement socket path discovery function
**Files:** `src/exabgp/application/socket.py`

**Implementation:**
- Add `unix_socket()` function similar to `named_pipe()` in `pipe.py`
- Search priority locations:
  - `/run/exabgp/`
  - `/run/{uid}/`
  - `/run/`
  - `/var/run/exabgp/`
  - `/var/run/`
  - `/usr/var/run/exabgp/`
  - `{tempdir}/exabgp/`
  - `/tmp/exabgp/`
- Default socket name: `exabgp.sock`
- Environment variable: `exabgp_api_socketpath` for explicit path
- Return socket path or None if not found

**Verification:**
```bash
ruff check src
```
**Expected:** All checks passed

---

### Step 3: Implement `main()` function for socket mode
**Files:** `src/exabgp/application/socket.py`

**Implementation:**
- Entry point when `exabgp_cli_socket` environment variable is set
- Create Unix socket server (bind + listen)
- Event loop using `select.poll()` (consistent with `pipe.py`)
- Accept single connection
- Forward messages bidirectionally:
  - Socket read → write to stdout (to ExaBGP)
  - Stdin read → write to socket (from ExaBGP)
- Handle EOF and connection close
- Clean up socket file on exit

**Verification:**
```bash
env exabgp_log_enable=false pytest ./tests/unit/ -q
```
**Expected:** 1376 passed

---

## Phase 2: Modify Configuration to Spawn Both Processes

### Step 4: Add socket process creation in `add_api()`
**Files:** `src/exabgp/configuration/process/__init__.py`

**Current code (lines 73-86):**
```python
def add_api(self):
    if not os.environ.get('exabgp_cli_pipe', ''):
        return
    name = '{}-{:x}'.format(API_PREFIX, uuid.uuid1().fields[0])
    prog = os.path.join(os.environ.get('PWD', ''), sys.argv[0])
    api = {
        name: {
            'run': [sys.executable, prog],
            'encoder': 'text',
            'respawn': True,
        },
    }
    self._processes.append(name)
    self.processes.update(api)
```

**Modification:**
- Check both `exabgp_cli_pipe` AND `exabgp_cli_socket`
- Create separate process entries for each
- Naming pattern: `api-internal-cli-{transport}-{uuid}` (transport = "pipe" or "socket")
- Transport suffix prevents UUID collision when spawned simultaneously
- Set appropriate environment variable for each process
- Both processes get `API_PREFIX` for routing (via `startswith()` check)

**Verification:**
```bash
env exabgp_log_enable=false pytest ./tests/unit/ -q
```
**Expected:** 1376 passed

---

### Step 5: Update application entry point
**Files:** `src/exabgp/application/main.py`

**Current code (lines 24-29):**
```python
cli_named_pipe = os.environ.get('exabgp_cli_pipe', '')
if cli_named_pipe:
    from exabgp.application.pipe import main
    main(cli_named_pipe)
    sys.exit(0)
```

**Modification:**
- Add socket mode detection after pipe mode
- Check `exabgp_cli_socket` environment variable
- Import and call `socket.main()` if set
- Structure:
  ```python
  cli_named_pipe = os.environ.get('exabgp_cli_pipe', '')
  if cli_named_pipe:
      from exabgp.application.pipe import main
      main(cli_named_pipe)
      sys.exit(0)

  cli_unix_socket = os.environ.get('exabgp_cli_socket', '')
  if cli_unix_socket:
      from exabgp.application.socket import main
      main(cli_unix_socket)
      sys.exit(0)
  ```

**Verification:**
```bash
ruff check src && env exabgp_log_enable=false pytest ./tests/unit/ -q
```
**Expected:** All checks passed, 1376 tests passed

---

## Phase 3: Modify CLI to Support Both Transports

### Step 6: Add command-line argument parsing to CLI
**Files:** `src/exabgp/application/cli.py`

**Implementation:**
- Add `--pipe` flag to force pipe transport
- Add `--socket` flag to force socket transport (optional, it's default)
- Flags are mutually exclusive
- Environment variable override: `exabgp_cli_transport` ("pipe" or "socket")
- Default behavior: try socket first, fall back to pipe if `--pipe` specified
- Use `argparse` for argument parsing

**Verification:**
```bash
ruff check src
```
**Expected:** All checks passed

---

### Step 7: Implement socket connection logic in CLI
**Files:** `src/exabgp/application/cli.py`

**Implementation:**
- Add `unix_socket()` discovery function (similar to `named_pipe()`)
- Search same locations as socket server
- Implement socket connection method:
  - Create Unix socket client
  - Connect to discovered socket path
  - Send command
  - Receive response
  - Close connection
- Handle connection errors gracefully (socket not found, connection refused)
- Timeout handling similar to pipe mode

**Verification:**
```bash
env exabgp_log_enable=false pytest ./tests/unit/ -q
```
**Expected:** 1376 passed

---

### Step 8: Update CLI main logic to route to correct transport
**Files:** `src/exabgp/application/cli.py`

**Implementation:**
- Modify `main()` function to:
  1. Parse command-line arguments
  2. Determine transport (flag, env var, or default)
  3. Route to socket or pipe logic
  4. Execute command
  5. Return response
- Socket path: use discovery or explicit path from env var
- Pipe path: existing logic (lines 132-141)
- Clear error messages if transport unavailable

**Verification:**
```bash
env exabgp_log_enable=false pytest ./tests/unit/ -q
```
**Expected:** 1376 passed

---

## Phase 4: Integration Testing

### Step 9: Test both processes spawn correctly
**Verification:**
```bash
# Set both environment variables
export exabgp_cli_pipe=/run/exabgp
export exabgp_cli_socket=/run/exabgp

# Start ExaBGP
./sbin/exabgp etc/exabgp/api-rib.conf

# In another terminal, check processes
ps aux | grep api-internal-cli

# Expected: Two processes, both with api-internal-cli-{uuid} names
```

**Success criteria:**
- Both processes visible in process list
- Both have `API_PREFIX` in name
- Named pipe files exist: `exabgp.in`, `exabgp.out`
- Socket file exists: `exabgp.sock`

---

### Step 10: Test CLI with both transports
**Verification:**
```bash
# Test default (socket)
./sbin/exabgp cli "show neighbor"

# Test explicit socket
./sbin/exabgp cli --socket "show neighbor"

# Test pipe
./sbin/exabgp cli --pipe "show neighbor"

# All should return identical output
```

**Success criteria:**
- All three commands work
- Responses are identical
- No errors or warnings

---

### Step 11: Test concurrent usage
**Verification:**
```bash
# Terminal 1: Socket commands
for i in {1..10}; do ./sbin/exabgp cli "show neighbor"; done

# Terminal 2: Pipe commands
for i in {1..10}; do ./sbin/exabgp cli --pipe "show neighbor"; done

# Terminal 3: Mixed
./sbin/exabgp cli "show neighbor" &
./sbin/exabgp cli --pipe "show neighbor" &
wait
```

**Success criteria:**
- All commands succeed
- No race conditions or deadlocks
- Responses are correct

---

### Step 12: Run full test suite
**Verification:**
```bash
# Linting
ruff format src && ruff check src

# Unit tests
env exabgp_log_enable=false pytest ./tests/unit/ -q

# Functional encoding tests
./qa/bin/functional encoding

# Functional decoding tests
./qa/bin/functional decoding

# Configuration validation
./sbin/exabgp validate -nrv ./etc/exabgp/conf-ipself6.conf
```

**Success criteria:**
- ✅ Linting: All checks passed
- ✅ Unit tests: 1376 passed, 0 failures
- ✅ Encoding: 72/72 passed (100%)
- ✅ Decoding: 18/18 passed (100%)
- ✅ Validation: PASS

---

## Phase 5: Documentation

### Step 13: Add configuration documentation
**Files:** Update relevant documentation

**Document:**
- New environment variables:
  - `exabgp_cli_socket` - Enable socket-based internal CLI process
  - `exabgp_api_socketpath` - Custom Unix socket path (optional)
  - `exabgp_cli_transport` - CLI transport override ("pipe" or "socket")
- CLI flags:
  - `--pipe` - Force pipe transport
  - `--socket` - Force socket transport (default)
- Socket path discovery behavior
- Example configurations

---

## Key Files Modified

| File | Type | Purpose |
|------|------|---------|
| `src/exabgp/application/socket.py` | NEW | Unix socket server implementation |
| `src/exabgp/configuration/process/__init__.py` | MODIFY | Spawn both pipe and socket processes |
| `src/exabgp/application/main.py` | MODIFY | Socket mode detection |
| `src/exabgp/application/cli.py` | MODIFY | Transport selection and socket connection |

---

## Environment Variables

### Server-side (Process Spawning)
- `exabgp_cli_pipe` - Enable pipe-based process (EXISTING)
- `exabgp_cli_socket` - Enable socket-based process (NEW)
- `exabgp_api_socketpath` - Custom socket path (NEW, optional)

### Client-side (CLI Tool)
- `exabgp_cli_transport` - Override transport: "pipe" or "socket" (NEW)

---

## Implementation Details

### Socket Server Architecture
```python
class Control:
    def __init__(self, socket_path):
        # Create Unix socket
        # Bind to path
        # Listen for connections

    def run(self):
        # Event loop with select.poll()
        # Accept single connection
        # Forward: socket → stdout (to ExaBGP)
        # Forward: stdin → socket (from ExaBGP)
        # Handle EOF, close, cleanup
```

### Socket Path Discovery
```python
def unix_socket(root, socketname='exabgp'):
    locations = [
        '/run/exabgp/',
        f'/run/{os.getuid()}/',
        '/run/',
        '/var/run/exabgp/',
        '/var/run/',
        # ... more locations
    ]
    for location in locations:
        socket_path = location + socketname + '.sock'
        if os.path.exists(socket_path):
            return socket_path
    return None
```

### CLI Transport Selection
```python
def main():
    # Parse args (--pipe, --socket)
    # Check environment variable
    # Determine transport

    if use_socket:
        socket_path = unix_socket(root)
        # Connect to socket
        # Send command
        # Receive response
    else:
        # Existing pipe logic
```

---

## Process Naming Strategy

**Format:** `api-internal-cli-{transport}-{uuid}` where transport is "pipe" or "socket"

**Example process names:**
- Pipe process: `api-internal-cli-pipe-a1b2c3d4`
- Socket process: `api-internal-cli-socket-e5f6g7h8`

**Rationale:**
- Routing logic in `loop.py:329-330` uses `startswith(API_PREFIX)`
- Both processes match the prefix `api-internal-cli-`
- Transport suffix prevents UUID collision (both spawn in same function)
- Both processes get same routing treatment (matched to all peers)
- Transport is visible in process name for debugging

---

## Risk Mitigation

### Backward Compatibility
- ✅ Existing `exabgp cli` commands work (defaults to socket)
- ✅ `--pipe` flag provides explicit fallback
- ✅ No changes to process routing logic
- ✅ Both transports can coexist

### Testing Strategy
- ✅ Each step independently tested
- ✅ Unit tests run after each modification
- ✅ Full functional test suite before commit
- ✅ Manual testing of both transports
- ✅ Concurrent usage testing

### Error Handling
- ✅ Socket cleanup on crash (unlink stale files)
- ✅ Graceful fallback if transport unavailable
- ✅ Clear error messages for users
- ✅ Connection timeout handling

---

## Pre-Commit Checklist

**MANDATORY - ALL must pass before commit:**

- [ ] `ruff format src && ruff check src` → All checks passed
- [ ] `env exabgp_log_enable=false pytest ./tests/unit/ -q` → 1376 passed, 0 failures
- [ ] `./qa/bin/functional encoding` → 72/72 passed (100%)
- [ ] `./qa/bin/functional decoding` → 18/18 passed (100%)
- [ ] `./sbin/exabgp validate -nrv ./etc/exabgp/conf-ipself6.conf` → PASS
- [ ] Manual test: Both processes spawn correctly
- [ ] Manual test: Socket transport works
- [ ] Manual test: Pipe transport works (with `--pipe`)
- [ ] Manual test: Concurrent usage succeeds
- [ ] `git status` reviewed
- [ ] User approval obtained

**If ANY box unchecked: DO NOT COMMIT**

---

## Future Enhancements

### Phase 2 (Optional):
- Support multiple simultaneous socket connections
- WebSocket transport for remote CLI
- Authentication/authorization for socket connections
- Metrics: track which transport is used more

### Deprecation Path (Long-term):
- Monitor usage statistics
- If socket proves superior, consider pipe deprecation (years away)
- Maintain both for backward compatibility

---

---

## Post-Implementation Fixes (2025-11-19)

### Socket Name Configuration Consistency

**Issue:** Socket name configuration was inconsistent across components:
- Unlike `pipename`, `socketname` was NOT defined in environment configuration
- CLI and server had defensive `hasattr()` checks with fallbacks
- Environment variable `exabgp_api_socketname` was only set conditionally
- This could lead to mismatches between server and CLI socket names

**Root Cause:**
- `pipename` was defined in `src/exabgp/environment/setup.py` (line 295-300)
- `socketname` was missing from environment configuration

**Fix Applied:**

1. **Added `socketname` to environment configuration** (`setup.py:301-306`):
   ```python
   'socketname': {
       'read': parsing.unquote,
       'write': parsing.quote,
       'value': 'exabgp',
       'help': 'name to be used for the exabgp Unix socket',
   },
   ```

2. **Simplified server.py socket name logic** (line 209):
   ```python
   # Before: Complex conditional with hasattr checks
   socketname = 'exabgp' if not hasattr(env.api, 'socketname') or env.api.socketname is None else env.api.socketname

   # After: Direct access (with None fallback for consistency with pipename)
   socketname = 'exabgp' if env.api.socketname is None else env.api.socketname
   ```

3. **Fixed environment variable propagation** (server.py:239):
   ```python
   # Before: Conditional (only set if hasattr)
   if hasattr(env.api, 'socketname'):
       os.environ['exabgp_api_socketname'] = socketname

   # After: Always set (matching pipename behavior)
   os.environ['exabgp_api_socketname'] = socketname
   ```

4. **Simplified CLI socket name retrieval** (cli.py:224):
   ```python
   # Before: Conditional with fallback
   socketname = getenv().api.socketname if hasattr(getenv().api, 'socketname') else 'exabgp'

   # After: Direct access
   socketname = getenv().api.socketname
   ```

**Result:**
- Socket name configuration now parallel to pipe name
- All components read from same source (`exabgp.api.socketname`)
- Environment variable always propagates to subprocesses
- Users can configure via `exabgp_api_socketname` environment variable
- Consistent behavior across server, socket process, and CLI

**Testing:**
- ✅ Linting: All checks passed
- ✅ Unit tests: 1424 passed in 4.25s
- ✅ Configuration consistency verified

---

---

## Socket Auto-Enable Fix (2025-11-19)

**Issue:** Socket was opt-in (like pipes), requiring directory to exist or explicit environment variable. This defeated the purpose of "zero-setup" sockets.

**Expected Behavior:**
- **Socket**: Auto-enabled (default, modern, zero-setup)
- **Pipe**: Opt-in (legacy, requires manual setup)

**Fix Applied:**

Modified `src/exabgp/application/server.py` (lines 207-224):
- **Before**: Only set `exabgp_cli_socket` if existing directory found
- **After**: Always set `exabgp_cli_socket` to default location (`{ROOT}/run/`)
- Socket process now spawns automatically when `api.cli=true`
- Directory and socket file auto-created by socket process

**Result:**
- ✅ Socket: Auto-enabled, zero setup required
- ✅ Pipe: Opt-in, only when pipes exist
- ✅ Users can start ExaBGP and use CLI immediately
- ✅ No `mkdir`, no environment variables needed for sockets

**Testing:**
- ✅ Linting: All checks passed
- ✅ Unit tests: 1424 passed
- ✅ Socket auto-creates on ExaBGP startup

---

**Last Updated:** 2025-11-19
