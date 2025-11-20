# Health Monitoring Implementation Plan (CORRECTED)

**Created:** 2025-11-20
**Updated:** 2025-11-20
**Status:** In Progress

---

## CORRECTED ARCHITECTURE

**Key correction:** Health monitoring belongs in CLI CLIENT, NOT in unixsocket.py server.

- **unixsocket.py (server/relay):** Pure message relay, NO health monitoring logic
- **cli.py (client):** Persistent connection with background health monitoring

---

## Requirements

1. CLI maintains persistent socket connection (not request-response per command)
2. Background thread sends `ping` command every 10 seconds
3. Parse `pong <UUID>` responses to track daemon identity
4. Detect daemon restart (UUID change) and notify user
5. Detect daemon failure (no response) and terminate after 3 attempts

---

## Current CLI Architecture (BEFORE)

```python
def send_command_socket(command):
    s = socket.socket()
    s.connect(socket_path)      # New connection per command
    s.sendall(command)
    response = s.recv()
    s.close()                   # Close after each command
    return response
```

**Problem:** No persistent connection, can't do background health monitoring.

---

## New CLI Architecture (AFTER)

```python
class PersistentSocketConnection:
    def __init__(self, socket_path):
        self.socket = socket.socket()
        self.socket.connect(socket_path)
        self.daemon_uuid = None
        self.health_thread = threading.Thread(target=self._health_monitor, daemon=True)
        self.health_thread.start()

    def _health_monitor(self):
        """Background thread: send ping every 10s"""
        while True:
            time.sleep(10)
            self.send_ping()
            response = self.wait_for_response()
            self.check_health(response)

    def send_command(self, command):
        """Send user command and wait for response"""
        self.socket.sendall(command)
        return self.read_response()
```

---

## Implementation Steps

### Step 1: Create PersistentSocketConnection Class

**File:** `src/exabgp/application/cli.py`

**Add before main() function:**

```python
import socket as sock
import threading
import time
from queue import Queue, Empty

class PersistentSocketConnection:
    """Persistent Unix socket connection with health monitoring"""

    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.socket = None
        self.daemon_uuid = None
        self.last_ping_time = 0
        self.consecutive_failures = 0
        self.max_failures = 3
        self.health_interval = 10  # seconds
        self.running = True
        self.lock = threading.Lock()

        # Response handling
        self.pending_responses = Queue()
        self.response_buffer = ""

        # Connect
        self._connect()

        # Start background threads
        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.reader_thread.start()

        self.health_thread = threading.Thread(target=self._health_monitor, daemon=True)
        self.health_thread.start()

    def _connect(self):
        """Establish socket connection"""
        self.socket = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
        full_path = self.socket_path if self.socket_path.endswith('.sock') else self.socket_path + 'exabgp.sock'
        self.socket.connect(full_path)
        self.socket.settimeout(0.1)  # Non-blocking reads with short timeout

    def _read_loop(self):
        """Background thread: continuously read from socket"""
        while self.running:
            try:
                data = self.socket.recv(4096)
                if not data:
                    # Socket closed
                    sys.stderr.write('ERROR: Connection to ExaBGP daemon lost\n')
                    sys.stderr.flush()
                    sys.exit(1)

                self.response_buffer += data.decode('utf-8')

                # Parse complete responses (ending with 'done\n')
                while '\ndone\n' in self.response_buffer or self.response_buffer.endswith('done\n'):
                    if '\ndone\n' in self.response_buffer:
                        response, self.response_buffer = self.response_buffer.split('\ndone\n', 1)
                    else:
                        response = self.response_buffer[:-5]  # Remove 'done\n'
                        self.response_buffer = ""

                    response = response.strip()

                    # Check if this is a ping response
                    if response.startswith('pong '):
                        self._handle_ping_response(response)
                    else:
                        # User command response
                        self.pending_responses.put(response)

            except sock.timeout:
                # No data available, continue
                continue
            except Exception as exc:
                if self.running:
                    sys.stderr.write(f'ERROR: Socket read error: {exc}\n')
                    sys.stderr.flush()
                    sys.exit(1)
                break

    def _health_monitor(self):
        """Background thread: send periodic pings"""
        # Initial ping to get UUID
        time.sleep(1)  # Give socket time to establish
        self._send_ping()

        while self.running:
            current_time = time.time()
            if current_time - self.last_ping_time >= self.health_interval:
                self._send_ping()

            time.sleep(1)  # Check every second

    def _send_ping(self):
        """Send ping command (internal, not user-initiated)"""
        with self.lock:
            try:
                self.socket.sendall(b'ping\n')
                self.last_ping_time = time.time()
            except Exception as exc:
                sys.stderr.write(f'ERROR: Failed to send ping: {exc}\n')
                sys.stderr.flush()
                sys.exit(1)

    def _handle_ping_response(self, response: str):
        """Handle pong response from health check"""
        parts = response.split()
        if len(parts) >= 2:
            new_uuid = parts[1]

            if self.daemon_uuid is None:
                # First UUID discovery
                self.daemon_uuid = new_uuid
                sys.stderr.write(f'✓ Connected to ExaBGP daemon (UUID: {new_uuid})\n')
                sys.stderr.flush()
                self.consecutive_failures = 0
            elif new_uuid != self.daemon_uuid:
                # Daemon restarted!
                old_uuid = self.daemon_uuid
                self.daemon_uuid = new_uuid

                warning = (
                    '\n'
                    '╔════════════════════════════════════════════════════════╗\n'
                    '║  WARNING: ExaBGP daemon restarted                      ║\n'
                    '╠════════════════════════════════════════════════════════╣\n'
                    f'║  Previous UUID: {old_uuid:<38} ║\n'
                    f'║  New UUID:      {new_uuid:<38} ║\n'
                    '╚════════════════════════════════════════════════════════╝\n'
                )
                sys.stderr.write(warning)
                sys.stderr.flush()
                self.consecutive_failures = 0
            else:
                # Normal ping response
                self.consecutive_failures = 0
        else:
            # Malformed response
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.max_failures:
                sys.stderr.write(f'ERROR: ExaBGP daemon not responding after {self.max_failures} attempts\n')
                sys.stderr.flush()
                sys.exit(1)

    def send_command(self, command: str) -> str:
        """Send user command and wait for response"""
        with self.lock:
            try:
                self.socket.sendall((command + '\n').encode('utf-8'))
            except Exception as exc:
                return f'Error: {exc}'

        # Wait for response (with timeout)
        try:
            response = self.pending_responses.get(timeout=5.0)
            return response
        except Empty:
            return 'Error: Timeout waiting for response'

    def close(self):
        """Close connection and stop threads"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
```

### Step 2: Refactor main() to Use Persistent Connection

**In main() function, replace the socket send_func creation:**

**OLD (lines 1094-1153):**
```python
else:
    # Use Unix socket transport
    sockets = unix_socket(ROOT, socketname)
    ...
    def send_command_socket(command: str) -> str:
        s = sock.socket(...)  # New connection per command
        ...
    send_func = send_command_socket
```

**NEW:**
```python
else:
    # Use Unix socket transport
    sockets = unix_socket(ROOT, socketname)
    if len(sockets) != 1:
        sys.stderr.write(f"Could not find ExaBGP's Unix socket ({socketname}.sock)\n")
        sys.stderr.write('Available sockets:\n - ')
        sys.stderr.write('\n - '.join(sockets))
        sys.stderr.write('\n')
        sys.stderr.flush()
        return 1

    socket_path = sockets[0]

    # Create persistent connection with health monitoring
    try:
        connection = PersistentSocketConnection(socket_path)
    except Exception as exc:
        sys.stderr.write(f'Error: Could not connect to ExaBGP: {exc}\n')
        sys.stderr.flush()
        return 1

    def send_command_persistent(command: str) -> str:
        """Send command via persistent connection"""
        expanded = CommandShortcuts.expand_shortcuts(command)
        return connection.send_command(expanded)

    send_func = send_command_persistent
```

### Step 3: Update api-health.run Test

**File:** `etc/exabgp/run/api-health.run`

Test should send ping and status commands and verify responses:

```python
#!/usr/bin/env python3

import sys
import time

# Wait for BGP session to establish
time.sleep(2)

# Test ping command
sys.stdout.write('ping\n')
sys.stdout.flush()

# Read response
response = sys.stdin.readline().strip()
if not response.startswith('pong '):
    sys.stderr.write(f'ERROR: ping failed, got: {response}\n')
    sys.exit(1)

uuid = response.split()[1]
sys.stderr.write(f'OK: ping returned UUID {uuid}\n')

# Read done
done = sys.stdin.readline().strip()
if done != 'done':
    sys.stderr.write(f'ERROR: expected done, got: {done}\n')
    sys.exit(1)

# Test status command
sys.stdout.write('status\n')
sys.stdout.flush()

# Read multi-line response
status_lines = []
while True:
    line = sys.stdin.readline().strip()
    if line == 'done':
        break
    status_lines.append(line)

status_text = '\n'.join(status_lines)
if 'UUID' not in status_text and uuid not in status_text:
    sys.stderr.write(f'ERROR: status missing UUID\n')
    sys.exit(1)

if 'PID' not in status_text:
    sys.stderr.write(f'ERROR: status missing PID\n')
    sys.exit(1)

sys.stderr.write(f'OK: status returned complete information\n')
sys.stderr.write(f'SUCCESS: Health monitoring commands working\n')

# Keep process alive for BGP session
while True:
    time.sleep(1)
```

---

## Testing Plan

### Unit Tests

Already written - tests `ping` and `status` API commands (6/6 passing).

### Manual Testing

**Test 1: Normal operation**
```bash
# Terminal 1: Start ExaBGP
./sbin/exabgp etc/exabgp/api-health.conf

# Terminal 2: Start CLI
./bin/exabgpcli

# Verify: Should see "✓ Connected to ExaBGP daemon (UUID: ...)"
# Wait 10+ seconds, verify no errors (background pings working)
```

**Test 2: Daemon restart detection**
```bash
# Terminal 1: ExaBGP running
# Terminal 2: CLI connected
# Terminal 1: Kill and restart ExaBGP
killall -9 python3; sleep 1; ./sbin/exabgp etc/exabgp/api-health.conf

# Verify: CLI shows "WARNING: ExaBGP daemon restarted" with UUIDs
```

**Test 3: Daemon failure**
```bash
# Terminal 1: ExaBGP running
# Terminal 2: CLI connected
# Terminal 1: Kill ExaBGP
killall -9 python3

# Verify: After 3 failed pings (~30s), CLI shows error and exits
```

### Functional Test

```bash
./qa/bin/functional encoding G
```

Should pass after implementing api-health test properly.

---

## Files Changed

1. ✅ `src/exabgp/reactor/api/command/reactor.py` - Removed get-daemon-identity command
2. ✅ `tests/unit/test_reactor_health.py` - Updated tests (6 tests for ping + status)
3. ✅ `src/exabgp/application/unixsocket.py` - NO CHANGES (remains pure relay)
4. ⏳ `src/exabgp/application/cli.py` - Add PersistentSocketConnection class
5. ⏳ `etc/exabgp/run/api-health.run` - Update test script

---

## Verification Checklist

- [ ] Linting passes (ruff format + check)
- [ ] Unit tests pass (6 tests)
- [ ] Manual test: CLI connects and shows UUID
- [ ] Manual test: Background pings work (no errors after 60s)
- [ ] Manual test: Daemon restart detected
- [ ] Manual test: Daemon failure terminates CLI after 3 attempts
- [ ] Functional test G passes
- [ ] No regressions in other tests

---

**Current Status:** Ready to implement PersistentSocketConnection class in cli.py

**Next Step:** Implement Step 1 (PersistentSocketConnection class)
