# Unix Socket Startup Checks

**Date:** 2025-11-19
**Feature:** Added Unix socket availability checks at ExaBGP startup (parallel to existing pipe checks)

---

## Overview

ExaBGP now checks for Unix socket directory availability at startup and provides helpful guidance, similar to the existing named pipe checks.

---

## Implementation

### Modified File
**`src/exabgp/application/server.py`**
- Lines 207-238: Added Unix socket check logic
- Import added: `from exabgp.application.unixsocket import unix_socket`

### Check Logic

When ExaBGP starts with API CLI enabled (`env.api.cli`), it now:

1. **Checks for socket directory** using `unix_socket()` discovery
2. **If directory not found** (returns multiple search locations):
   - Logs **warning** messages (not errors, since socket is auto-created)
   - Lists searched locations
   - Provides helpful commands to create the directory
3. **If directory found**:
   - Sets environment variables
   - Logs info message with socket path

---

## User Experience

### When Socket Directory Not Found

ExaBGP displays:

```
WARNING | could not find the Unix socket (exabgp.sock) for the cli
WARNING | we scanned the following folders (the number is your PID):
WARNING |  - /run/exabgp/
WARNING |  - /run/1000/
WARNING |  - /run/
WARNING |  - /var/run/exabgp/
WARNING |  (... more locations ...)
WARNING | the socket will be created automatically when the socket-based API process starts
WARNING | to enable it, set the environment variable:
WARNING | > export exabgp_cli_socket=/path/to/exabgp/run
WARNING | or create the directory manually:
WARNING | > mkdir -p /path/to/exabgp/run/exabgp
WARNING | > chmod 700 /path/to/exabgp/run/exabgp
WARNING | > chown 1000:1000 /path/to/exabgp/run/exabgp
```

### When Socket Directory Found

ExaBGP displays:

```
INFO | Unix socket for the cli will be:
INFO | socket path: /run/exabgp/exabgp.sock
```

---

## Key Differences from Pipe Checks

### Pipes (named FIFOs)
- **Error level:** Must exist before startup (ERROR messages)
- **User must create:** Both directory AND FIFO files
- **Creation commands:** `mkfifo` required
- **Created by:** User manually
- **When:** Before ExaBGP starts

### Sockets
- **Warning level:** Optional, can be created later (WARNING messages)
- **Auto-created:** Directory AND socket file created automatically
- **Creation mode:** Directory created with `0o700` (rwx------)
- **Created by:** ExaBGP socket process
- **When:** When socket-based API process starts

**Rationale:**
- Socket server automatically creates directory if it doesn't exist
- Socket file is created by the socket server automatically
- No manual `mkdir` or `mkfifo` commands needed
- Warnings (not errors) because it's fully automatic
- More convenient than pipes (zero manual setup required)

---

## Commands Suggested

### Create Directory
```bash
mkdir -p /path/to/exabgp/run/exabgp
```

### Set Permissions
```bash
chmod 700 /path/to/exabgp/run/exabgp
```

### Set Ownership (if not root)
```bash
chown UID:GID /path/to/exabgp/run/exabgp
```

### Enable via Environment Variable
```bash
export exabgp_cli_socket=/path/to/exabgp/run
```

---

## Environment Variables Set

When socket directory is found:

```python
os.environ['exabgp_cli_socket'] = socket_path  # e.g., '/run/exabgp/'
os.environ['exabgp_api_socketname'] = socketname  # e.g., 'exabgp'
```

These are used by:
- Configuration system to spawn socket-based API process
- CLI to discover socket location

---

## Code Flow

```python
# In src/exabgp/application/server.py cmdline()

if env.api.cli:  # If CLI API is enabled
    socketname = 'exabgp'  # Default, or from env.api.socketname
    sockets = unix_socket(ROOT, socketname)  # Search for directory

    if len(sockets) != 1:
        # Not found - show warnings with helpful commands
        log.warning(...)

    else:
        # Found - set environment and log info
        socket_path = sockets[0]
        os.environ['exabgp_cli_socket'] = socket_path
        log.info(f'socket path: {socket_path}{socketname}.sock')
```

---

## Benefits

1. **Consistent UX:** Matches existing pipe check pattern
2. **Helpful Guidance:** Users know exactly what to do
3. **Auto-Creation:** Socket file created automatically by server
4. **Directory Permissions:** Users set up proper permissions
5. **Environment Setup:** Correct env vars set for child processes

---

## Testing

### Verification

```bash
# Test with socket directory missing
rm -rf /tmp/exabgp
./sbin/exabgp validate etc/exabgp/conf-ipself6.conf
# Should see WARNING messages with helpful commands

# Test with socket directory present
mkdir -p /tmp/exabgp
chmod 700 /tmp/exabgp
./sbin/exabgp validate etc/exabgp/conf-ipself6.conf
# Should see INFO message with socket path
```

### All Tests Pass

```bash
✅ Linting: ruff format src && ruff check src - All checks passed
✅ Unit tests: 1424 passed
✅ Validation: Works correctly
```

---

## Related Files

- `src/exabgp/application/server.py` - Startup checks
- `src/exabgp/application/unixsocket.py` - Socket server & discovery
- `src/exabgp/application/pipe.py` - Pipe checks (reference implementation)

---

**Last Updated:** 2025-11-19
