# Socket Conflict Prevention - Functional Tests

**Date**: 2025-12-02
**Commit**: a7f5d25c
**Issue**: Parallel functional tests causing socket conflicts

---

## Problem

When running functional tests in parallel, multiple ExaBGP instances tried to use the same Unix socket path, causing:

1. **Socket conflicts**: `error: socket already exists and is active`
2. **Process respawn loops**: `process.respawn.exceeded limit=5`
3. **100% CPU usage**: Stuck processes competing for the same socket
4. **Test failures**: Random failures when tests run simultaneously

### Root Cause

Functional tests allocated unique TCP ports per test but **all used the same socket path**:

```bash
# Test A (port 1790)
run/exabgp.sock  ← Created by test A

# Test B (port 1791)
run/exabgp.sock  ← CONFLICT! Test B tries to create same socket

# Test C (port 1792)
run/exabgp.sock  ← CONFLICT! Test C tries to create same socket
```

---

## Solution

Each test now gets a **unique socket name** based on its TCP port:

```bash
# Test A (port 1790)
run/exabgp-test-1790.sock  ← Unique to test A

# Test B (port 1791)
run/exabgp-test-1791.sock  ← Unique to test B

# Test C (port 1792)
run/exabgp-test-1792.sock  ← Unique to test C
```

### Implementation

**File**: `qa/bin/functional`

**Change 1** - `client_cmd()` method:
```python
env_parts = [
    'exabgp_tcp_port=%d' % actual_port,
    f'exabgp_tcp_connections={tcp_connections}',
    'exabgp_api_cli=false',
    'exabgp_debug_rotate=true',
    'exabgp_debug_configuration=true',
    f'exabgp_api_socketname=exabgp-test-{actual_port}',  # ← NEW: Unique socket
]
```

**Change 2** - `client()` method:
```python
config = {
    'env': ' \\\n  '.join(
        [
            'exabgp_version=5.0.0-0+test',
            f'exabgp_tcp_connections={tcp_connections}',
            'exabgp_api_cli=false',
            'exabgp_debug_rotate=true',
            'exabgp_debug_configuration=true',
            "exabgp_tcp_bind=''",
            'exabgp_tcp_port=%d' % test.conf['port'],
            f'exabgp_api_socketname=exabgp-test-{test.conf["port"]}',  # ← NEW
            'INTERPRETER=%s' % INTERPRETER,
        ]
    ),
    # ...
}
```

---

## Environment Variable

The fix uses the existing **`exabgp_api_socketname`** environment variable:

```bash
# Default behavior (single instance)
# Creates: run/exabgp.sock

# With custom socket name
export exabgp_api_socketname=my-custom-name
# Creates: run/my-custom-name.sock

# Functional tests (automatic)
export exabgp_api_socketname=exabgp-test-1790
# Creates: run/exabgp-test-1790.sock
```

### Full Socket Path Override

You can also use **`exabgp_api_socketpath`** for complete path control:

```bash
export exabgp_api_socketpath=/tmp/my-exabgp.sock
# Creates: /tmp/my-exabgp.sock (exactly as specified)
```

---

## Testing

### Before Fix

```bash
$ ./qa/bin/functional encoding a b c

# Would see errors like:
Exception in callback None()
  File "src/exabgp/reactor/api/processes.py", line 300
    raise ProcessError
exabgp.reactor.api.processes.ProcessError

api.command.received process=api-internal-cli-socket-XXX
  command=error: socket already exists and is active (run/exabgp.sock)

process.respawn.exceeded process=api-internal-cli-socket-XXX limit=5
```

### After Fix

```bash
$ ./qa/bin/functional encoding a b c

[cleanup] Killed 0 stale process(es) from previous run
timeout [ 0/20] daemons  3 clients  3 passed  3 pending  0

============================================================
TEST SUMMARY
============================================================
passed     3
failed     0
timed out  0
============================================================
Total: 3 test(s) run, 100.0% passed
```

✅ **No socket conflicts**
✅ **No process respawn errors**
✅ **Tests pass reliably**

---

## Benefits

1. **Parallel Test Execution**: Tests can run simultaneously without conflicts
2. **Isolation**: Each test instance is completely isolated
3. **Reliability**: Eliminates random test failures from socket conflicts
4. **Cleanup**: Socket files are automatically removed after tests
5. **Debugging**: Unique socket names make it easier to identify test instances

---

## Manual Usage

If you need to run multiple ExaBGP instances manually:

```bash
# Instance 1
export exabgp_api_socketname=instance1
./sbin/exabgp config1.conf &

# Instance 2
export exabgp_api_socketname=instance2
./sbin/exabgp config2.conf &

# Instance 3
export exabgp_api_socketname=instance3
./sbin/exabgp config3.conf &

# Result:
ls run/
# instance1.sock
# instance2.sock
# instance3.sock
```

---

## Related Environment Variables

From `src/exabgp/application/unixsocket.py`:

- **`exabgp_api_socketpath`**: Full path to socket file (overrides all)
  ```bash
  export exabgp_api_socketpath=/custom/path/my.sock
  ```

- **`exabgp_api_socketname`**: Socket filename (location auto-detected)
  ```bash
  export exabgp_api_socketname=custom-name
  # Creates: run/custom-name.sock (or /var/run/custom-name.sock, etc.)
  ```

- **`exabgp_api_cli`**: Enable/disable CLI process
  ```bash
  export exabgp_api_cli=false  # Disable CLI completely
  ```

---

## Troubleshooting

### Still seeing socket conflicts?

1. **Check for stale processes**:
   ```bash
   ps aux | grep exabgp
   killall -9 Python  # macOS uses capital P
   ```

2. **Check for stale sockets**:
   ```bash
   ls -la run/exabgp*.sock
   rm -f run/exabgp*.sock
   ```

3. **Verify environment variable**:
   ```bash
   # Should show unique socket name per test
   env | grep exabgp_api_socketname
   ```

### Multiple instances stuck at 100% CPU?

This was the original problem. Solution:
1. Kill all ExaBGP processes: `killall -9 Python`
2. Remove all sockets: `rm -f run/exabgp*.sock`
3. Upgrade to this fix: commit a7f5d25c or later

---

## Implementation Details

### Socket Location Priority

ExaBGP searches for socket locations in this order:

1. `exabgp_api_socketpath` (if set) - exact path
2. `/run/exabgp/`
3. `/run/{uid}/`
4. `/run/`
5. `/var/run/exabgp/`
6. `/var/run/{uid}/`
7. `/var/run/`
8. `{root}/run/exabgp/`
9. `{root}/run/{uid}/`
10. `{root}/run/`
11. `{root}/var/run/exabgp/`
12. `{root}/var/run/{uid}/`
13. `{root}/var/run/`

Socket filename:
- Default: `exabgp.sock`
- Custom: `${exabgp_api_socketname}.sock`

### Cleanup

Sockets are automatically removed when:
- ExaBGP process exits normally
- Process is killed
- Test completes

No manual cleanup required in normal operation.

---

## See Also

- `.claude/exabgp/UNIX_SOCKET_API.md` - Unix socket API documentation
- `.claude/exabgp/ENVIRONMENT_VARIABLES.md` - All environment variables
- `src/exabgp/application/unixsocket.py` - Socket implementation
- `qa/bin/functional` - Functional test runner
