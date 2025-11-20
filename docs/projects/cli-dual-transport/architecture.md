# CLI Dual Transport: Technical Architecture

Internal implementation details for developers and maintainers.

---

## System Overview

ExaBGP's CLI uses a **subprocess-based architecture** where the daemon spawns internal processes that act as bridges between the CLI tool and the main ExaBGP reactor.

```
┌─────────────────────────────────────────────────────────────────┐
│                         ExaBGP Daemon                            │
│                                                                  │
│  ┌──────────────┐      ┌─────────────┐      ┌─────────────┐   │
│  │   Reactor    │◄─────│ Pipe Process│◄─────│Named Pipes  │   │
│  │   (Main      │      │  (pipe.py)  │      │ .in / .out  │───┼─► CLI
│  │   Event Loop)│◄─────│ Socket Proc │◄─────│   .sock     │   │
│  └──────────────┘      └─────────────┘      └─────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. CLI Client (`src/exabgp/application/cli.py`)

**Responsibilities:**
- Parse command-line arguments (`--pipe`, `--socket`, etc.)
- Discover transport file locations
- Connect to appropriate transport
- Send commands and receive responses
- Handle errors and timeouts

**Key Functions:**

**`main()`** - Entry point
- Parses arguments with `argparse`
- Calls `cmdline()`

**`cmdline(cmdarg)`** - Transport selection and routing
- Determines transport based on:
  1. Command-line flags (`--pipe`, `--socket`)
  2. Environment variable (`exabgp_cli_transport`)
  3. Default (socket)
- Routes to `cmdline_pipe()` or `cmdline_socket()`

**`cmdline_socket(socketname, sending)`** - Socket transport handler
- Discovers socket path using `unix_socket()`
- Validates socket file exists
- Calls `send_command_socket()`

**`cmdline_pipe(pipename, sending)`** - Pipe transport handler
- Discovers pipe paths using `named_pipe()`
- Validates FIFO files exist
- Opens pipes with timeout handling
- Sends command and reads response

**`send_command_socket(socket_path, command_str)`** - Socket communication
- Creates Unix socket client
- Connects with timeout
- Sends command + newline
- Receives response line-by-line
- Detects `done`, `error`, `shutdown` markers
- Closes connection

**Transport Selection Logic:**
```python
# Priority: CLI flags > env var > default
if cmdarg.use_pipe:
    use_pipe_transport = True
elif cmdarg.use_socket:
    use_pipe_transport = False
else:
    env_transport = os.environ.get('exabgp_cli_transport', '').lower()
    if env_transport == 'pipe':
        use_pipe_transport = True
    elif env_transport == 'socket':
        use_pipe_transport = False
    else:
        use_pipe_transport = False  # Default to socket
```

---

### 2. Pipe Process (`src/exabgp/application/pipe.py`)

**Responsibilities:**
- Listen on named pipes (FIFOs)
- Forward commands from pipes to ExaBGP (via stdout)
- Forward responses from ExaBGP (via stdin) to pipes
- Handle EOF and connection close

**Key Components:**

**`Control` class** - Main controller
- Opens FIFOs in non-blocking mode
- Uses `select.poll()` for event-driven I/O
- Maintains separate buffers for each direction
- Handles backpressure and flow control

**Event Loop:**
```python
while True:
    ready = poll()  # Wait for readable fds

    # Read from FIFO.in (CLI commands)
    if fifo_in in ready:
        data = os.read(fifo_in, 4096)
        write_to_stdout(data)  # → ExaBGP

    # Read from stdin (ExaBGP responses)
    if stdin in ready:
        data = os.read(stdin, 4096)
        write_to_fifo_out(data)  # → CLI
```

**FIFO Characteristics:**
- Unidirectional (need 2 FIFOs: `.in` and `.out`)
- Block on open until both sides connected
- Multiple writers possible (but ExaBGP uses single)
- Must exist before process starts

---

### 3. Socket Process (`src/exabgp/application/unixsocket.py`)

**Responsibilities:**
- Create and bind Unix socket
- Accept single client connection
- Forward commands from socket to ExaBGP (via stdout)
- Forward responses from ExaBGP (via stdin) to socket
- Clean up socket file on exit

**Key Components:**

**`Control` class** - Main controller
- Creates Unix domain socket (AF_UNIX, SOCK_STREAM)
- Binds to socket path
- Listens for connections (backlog=1)
- Accepts single connection at a time
- Uses `select.poll()` for event-driven I/O

**Initialization (`init()`):**
```python
def init(self):
    # Remove stale socket file
    if os.path.exists(self.socket_path):
        if is_stale():  # Not actively listening
            os.unlink(self.socket_path)

    # Create directory if needed
    os.makedirs(socket_dir, mode=0o700, exist_ok=True)

    # Create and bind socket
    self.server_socket = socket.socket(AF_UNIX, SOCK_STREAM)
    self.server_socket.bind(self.socket_path)
    self.server_socket.listen(1)
    self.server_socket.setblocking(False)
```

**Event Loop:**
```python
while True:
    ready = poll([stdin, server_socket, client_socket])

    # Accept new connection
    if server_socket in ready and not client_socket:
        client_socket, _ = server_socket.accept()
        client_socket.setblocking(False)

    # Read from client socket (CLI commands)
    if client_socket in ready:
        data = client_socket.recv(4096)
        write_to_stdout(data)  # → ExaBGP

    # Read from stdin (ExaBGP responses)
    if stdin in ready:
        data = os.read(stdin, 4096)
        client_socket.send(data)  # → CLI
```

**Socket Characteristics:**
- Bidirectional (single socket for both directions)
- Connection-oriented (connect/disconnect semantics)
- Single client at a time (sequential)
- Auto-created by server process
- Auto-cleaned on shutdown

**Stale Socket Detection:**
```python
# Test if socket is actually listening
test_sock = socket.socket(AF_UNIX, SOCK_STREAM)
try:
    test_sock.connect(socket_path)
    # Success = socket is active, error out
    return False
except socket.error:
    # Connection refused = stale, safe to remove
    os.unlink(socket_path)
```

---

### 4. Configuration System (`src/exabgp/configuration/process/__init__.py`)

**Responsibilities:**
- Spawn internal CLI processes based on environment
- Set up process metadata (name, command, environment)
- Configure respawn behavior

**Process Spawning (`add_api()`):**
```python
def add_api(self):
    # Pipe process
    cli_pipe = os.environ.get('exabgp_cli_pipe', '')
    if cli_pipe:
        name = f'api-internal-cli-pipe-{uuid.uuid1().fields[0]:x}'
        api = {
            name: {
                'run': [sys.executable, sys.argv[0]],
                'encoder': 'text',
                'respawn': True,
            },
        }
        os.environ['exabgp_cli_pipe'] = cli_pipe  # Pass to child
        self.processes.update(api)

    # Socket process
    cli_socket = os.environ.get('exabgp_cli_socket', '')
    if cli_socket:
        name = f'api-internal-cli-socket-{uuid.uuid1().fields[0]:x}'
        api = {
            name: {
                'run': [sys.executable, sys.argv[0]],
                'encoder': 'text',
                'respawn': True,
            },
        }
        os.environ['exabgp_cli_socket'] = cli_socket  # Pass to child
        self.processes.update(api)
```

**Process Naming:**
- Format: `api-internal-cli-{transport}-{uuid}`
- Transport: `pipe` or `socket`
- UUID: Generated with `uuid.uuid1()`
- Both match `API_PREFIX` for routing

---

### 5. Application Entry Point (`src/exabgp/application/main.py`)

**Responsibilities:**
- Detect if running as internal process
- Route to appropriate subprocess handler

**Entry Point Logic:**
```python
# Check for pipe process mode
cli_named_pipe = os.environ.get('exabgp_cli_pipe', '')
if cli_named_pipe:
    from exabgp.application.pipe import main
    main(cli_named_pipe)
    sys.exit(0)

# Check for socket process mode
cli_unix_socket = os.environ.get('exabgp_cli_socket', '')
if cli_unix_socket:
    from exabgp.application.unixsocket import main
    main(cli_unix_socket)
    sys.exit(0)

# Normal daemon mode
# ... continue with daemon startup
```

---

### 6. Server Startup Checks (`src/exabgp/application/server.py`)

**Responsibilities:**
- Verify transport file availability at startup
- Provide helpful error messages
- Set environment variables for child processes

**Pipe Check:**
```python
if env.api.cli:
    pipename = 'exabgp' if env.api.pipename is None else env.api.pipename
    pipes = named_pipe(ROOT, pipename)

    if len(pipes) != 1:
        env.api.cli = False  # Disable CLI
        log.error(f'could not find named pipes ({pipename}.in/.out)')
        log.error('please create them: mkfifo /path/to/{pipename}.{{in,out}}')
    else:
        os.environ['exabgp_cli_pipe'] = pipes[0]
        os.environ['exabgp_api_pipename'] = pipename
        log.info(f'named pipes: {pipes[0]}{pipename}.in/.out')
```

**Socket Check:**
```python
if env.api.cli:
    socketname = 'exabgp' if env.api.socketname is None else env.api.socketname
    sockets = unix_socket(ROOT, socketname)

    if len(sockets) != 1:
        # WARNING (not error) - socket auto-creates
        log.warning(f'could not find Unix socket ({socketname}.sock)')
        log.warning('socket will be created automatically')
        log.warning('to enable: export exabgp_cli_socket=/path')
    else:
        os.environ['exabgp_cli_socket'] = sockets[0]
        os.environ['exabgp_api_socketname'] = socketname
        log.info(f'Unix socket: {sockets[0]}{socketname}.sock')
```

**Key Difference:**
- Pipes: **ERROR** level (required, must exist)
- Sockets: **WARNING** level (optional, auto-created)

---

## Path Discovery

Both transports use similar discovery logic to locate files.

### Named Pipe Discovery (`named_pipe()` in `pipe.py`)

```python
def named_pipe(root, pipename='exabgp'):
    locations = [
        '/run/exabgp/',
        f'/run/{os.getuid()}/',
        '/run/',
        '/var/run/exabgp/',
        f'/var/run/{os.getuid()}/',
        '/var/run/',
        root + '/run/exabgp/',
        root + '/run/',
        root + '/var/run/exabgp/',
        root + '/var/run/',
    ]

    for location in locations:
        fifo_in = location + pipename + '.in'
        fifo_out = location + pipename + '.out'
        if check_fifo(fifo_in) and check_fifo(fifo_out):
            return [location]  # Found!

    return locations  # Not found, return search list
```

### Unix Socket Discovery (`unix_socket()` in `unixsocket.py`)

```python
def unix_socket(root, socketname='exabgp'):
    # Check for explicit path override
    explicit_path = os.environ.get('exabgp_api_socketpath', '')
    if explicit_path and os.path.exists(explicit_path):
        if stat.S_ISSOCK(os.stat(explicit_path).st_mode):
            return [os.path.dirname(explicit_path) + '/']

    locations = [
        '/run/exabgp/',
        f'/run/{os.getuid()}/',
        '/run/',
        '/var/run/exabgp/',
        f'/var/run/{os.getuid()}/',
        '/var/run/',
        root + '/run/exabgp/',
        root + '/run/',
        root + '/var/run/exabgp/',
        root + '/var/run/',
    ]

    for location in locations:
        socket_path = location + socketname + '.sock'
        if os.path.exists(socket_path):
            if stat.S_ISSOCK(os.stat(socket_path).st_mode):
                return [location]  # Found!

    return locations  # Not found, return search list
```

**Return Value Semantics:**
- **Single-element list** `[path]` → Found, path is valid
- **Multi-element list** `[loc1, loc2, ...]` → Not found, these are search locations

---

## Environment Configuration

### Configuration Definition (`src/exabgp/environment/setup.py`)

```python
'api': {
    'cli': {
        'read': parsing.boolean,
        'write': parsing.lower,
        'value': 'true',
        'help': 'should we create a named pipe for the cli',
    },
    'pipename': {
        'read': parsing.unquote,
        'write': parsing.quote,
        'value': 'exabgp',
        'help': 'name to be used for the exabgp pipe',
    },
    'socketname': {
        'read': parsing.unquote,
        'write': parsing.quote,
        'value': 'exabgp',
        'help': 'name to be used for the exabgp Unix socket',
    },
}
```

**Environment Variable Mapping:**
- `exabgp.api.cli` ← `exabgp_api_cli` (boolean)
- `exabgp.api.pipename` ← `exabgp_api_pipename` (string)
- `exabgp.api.socketname` ← `exabgp_api_socketname` (string)

**Access via `getenv()`:**
```python
from exabgp.environment import getenv

env = getenv()
cli_enabled = env.api.cli        # true/false
pipe_name = env.api.pipename     # 'exabgp' (default)
socket_name = env.api.socketname # 'exabgp' (default)
```

---

## Data Flow

### Command Execution Flow (Socket)

```
1. User runs: ./sbin/exabgp run "show neighbor"
   ↓
2. CLI client (cli.py):
   - Parses args: command="show neighbor", transport=socket
   - Discovers socket: /run/exabgp/exabgp.sock
   - Connects to socket
   ↓
3. Socket process (unixsocket.py):
   - Accepts connection
   - Receives: "show neighbor\n"
   - Writes to stdout: "show neighbor\n"
   ↓
4. ExaBGP reactor (loop.py):
   - Reads from socket process stdin
   - Executes command
   - Generates response
   - Writes to socket process stdout
   ↓
5. Socket process:
   - Reads from stdin (ExaBGP output)
   - Sends to client socket
   ↓
6. CLI client:
   - Receives response lines
   - Prints to user's terminal
   - Detects "done" marker
   - Closes connection
   ↓
7. Socket process:
   - Detects client disconnect
   - Closes client socket
   - Waits for next connection
```

### Command Execution Flow (Pipe)

```
1. User runs: ./sbin/exabgp run --pipe "show neighbor"
   ↓
2. CLI client (cli.py):
   - Parses args: command="show neighbor", transport=pipe
   - Discovers pipes: /run/exabgp/exabgp.in, /run/exabgp/exabgp.out
   - Opens .out for reading (blocks until pipe process opens)
   - Opens .in for writing (blocks until pipe process opens)
   ↓
3. Pipe process (pipe.py):
   - Opens .in for reading (non-blocking)
   - Opens .out for writing (non-blocking)
   - Poll loop waits for data
   ↓
4. CLI client:
   - Writes: "show neighbor\n" to .in
   - Closes .in writer
   ↓
5. Pipe process:
   - Reads from .in FIFO
   - Writes to stdout: "show neighbor\n"
   ↓
6. ExaBGP reactor:
   - Reads from pipe process stdin
   - Executes command
   - Generates response
   - Writes to pipe process stdout
   ↓
7. Pipe process:
   - Reads from stdin (ExaBGP output)
   - Writes to .out FIFO
   ↓
8. CLI client:
   - Reads from .out FIFO
   - Prints to user's terminal
   - Detects "done" marker
   - Closes .out reader
```

---

## Process Lifecycle

### Daemon Startup

```
1. User runs: ./sbin/exabgp config.conf
   ↓
2. main.py entry point:
   - NOT running as subprocess (no exabgp_cli_* env vars)
   - Continues to daemon startup
   ↓
3. server.py cmdline():
   - Checks env.api.cli (default: true)
   - Discovers pipe locations (if exabgp_cli_pipe set)
   - Discovers socket locations (always, for info)
   - Sets environment variables for subprocesses
   ↓
4. Configuration().load():
   - Parses config file
   - Calls configuration.process.add_api()
   ↓
5. add_api():
   - Checks exabgp_cli_pipe env var
   - If set: Creates pipe process entry
   - Checks exabgp_cli_socket env var
   - If set (or default): Creates socket process entry
   ↓
6. Reactor().run():
   - Spawns subprocess for each process entry
   - Subprocess inherits environment (exabgp_cli_*)
   ↓
7. Subprocess starts (same executable):
   - main.py entry point
   - Detects exabgp_cli_pipe env var
   - Routes to pipe.main() → exits
   - OR detects exabgp_cli_socket env var
   - Routes to unixsocket.main() → exits
```

### Subprocess Lifecycle (Socket)

```
1. Subprocess starts with exabgp_cli_socket set
   ↓
2. unixsocket.main():
   - Creates Control(location)
   ↓
3. Control.__init__():
   - Determines socket path
   - Sets up signal handlers
   ↓
4. Control.init():
   - Removes stale socket file
   - Creates directory if needed
   - Creates Unix socket
   - Binds to socket path
   - Listens (backlog=1)
   ↓
5. Control.loop():
   - Sends "enable-ack\n" to ExaBGP
   - Waits for "done\n" response
   - Enters main event loop
   - Polls: stdin, server_socket, client_socket
   ↓
6. When client connects:
   - Accepts connection
   - Sets non-blocking mode
   - Adds to poll list
   ↓
7. Event loop:
   - Forwards client → stdout (ExaBGP)
   - Forwards stdin (ExaBGP) → client
   ↓
8. When client disconnects:
   - Closes client socket
   - Removes from poll list
   - Waits for next connection
   ↓
9. On shutdown (SIGTERM/SIGINT):
   - Closes client socket
   - Closes server socket
   - Removes socket file
   - Exits
```

---

## API Communication Protocol

### Message Format

**Commands** (CLI → ExaBGP):
```
<command>\n
```

Example:
```
show neighbor\n
```

**Responses** (ExaBGP → CLI):
```
<response-line-1>\n
<response-line-2>\n
...
<response-line-n>\n
<marker>\n
```

**Markers:**
- `done` (text mode) or `{ "done": true }` (JSON mode) - Success
- `error` (text mode) or `{ "error": true }` (JSON mode) - Error
- `shutdown` (text mode) or `{ "shutdown": true }` (JSON mode) - Daemon shutting down

**Example Response (text mode):**
```
neighbor 192.0.2.1 state established
neighbor 192.0.2.2 state active
done
```

**Example Response (JSON mode):**
```json
{ "neighbor": { "address": "192.0.2.1", "state": "established" } }
{ "neighbor": { "address": "192.0.2.2", "state": "active" } }
{ "done": true }
```

### ACK Mechanism

When API process starts, it enables ACK mode:

```
Process → ExaBGP: enable-ack\n
ExaBGP → Process: done\n
```

This ensures ExaBGP sends `done`/`error` markers after each command, allowing CLI to detect command completion.

**Without ACK:**
- Commands succeed but no confirmation
- CLI must timeout or guess completion

**With ACK:**
- Commands always send `done`/`error`
- CLI waits for explicit marker
- Better reliability

---

## Error Handling

### Socket Process Error Handling

**Stale Socket File:**
```python
# Test if socket is active
test_sock = socket.socket(AF_UNIX, SOCK_STREAM)
try:
    test_sock.connect(socket_path)
    # Connected → socket is active, fail
    sys.stdout.write('error: socket already in use\n')
    return False
except socket.error:
    # Connection refused → stale socket, remove
    os.unlink(socket_path)
```

**Non-Socket File at Path:**
```python
if os.path.exists(socket_path):
    if not stat.S_ISSOCK(os.stat(socket_path).st_mode):
        sys.stdout.write('error: file exists but is not a socket\n')
        return False
```

**Directory Creation Failure:**
```python
try:
    os.makedirs(socket_dir, mode=0o700, exist_ok=True)
except OSError as exc:
    sys.stdout.write(f'error: could not create directory: {exc}\n')
    return False
```

**Client Connection Errors:**
```python
# Client disconnects unexpectedly
try:
    data = client_socket.recv(4096)
    if not data:
        # EOF → clean disconnect
        cleanup_client()
except OSError as exc:
    if exc.errno in error.block:
        # EAGAIN/EWOULDBLOCK → try later
        return
    # Other error → client disconnected
    cleanup_client()
```

### CLI Client Error Handling

**Socket Not Found:**
```python
if len(sockets) != 1:
    sys.stdout.write(f"could not find Unix socket ({socketname}.sock)\n")
    sys.stdout.write("we scanned:\n - " + "\n - ".join(sockets))
    sys.exit(1)
```

**Connection Refused:**
```python
try:
    client.connect(socket_path)
except socket.error as exc:
    if exc.errno == errno.ECONNREFUSED:
        sys.stdout.write('ExaBGP is not accepting connections\n')
    elif exc.errno == errno.ENOENT:
        sys.stdout.write('Socket file not found\n')
    sys.exit(1)
```

**Command Timeout:**
```python
client.settimeout(COMMAND_RESPONSE_TIMEOUT)  # 5 seconds
try:
    chunk = client.recv(4096)
except socket.timeout:
    sys.stderr.write('warning: no end of command message received\n')
    sys.stderr.write('normal if exabgp.api.ack is set to false\n')
    break
```

---

## Security Considerations

### File Permissions

**Socket File:**
- Created by socket process (server)
- Inherits directory permissions
- Typically `700` (owner-only) directory → socket has same restrictions
- No explicit `chmod` on socket file (not needed)

**Named Pipes:**
- Created manually by user
- Must be set to `600` (owner read/write only)
- ExaBGP does NOT create or modify permissions

**Directory Permissions:**
```bash
# Recommended setup
mkdir -p /run/exabgp
chmod 700 /run/exabgp
chown exabgp:exabgp /run/exabgp
```

### Process Isolation

**Subprocess Security:**
- Inherits parent's user/group
- No privilege escalation
- Uses stdin/stdout (no network exposure)
- Limited attack surface

**Environment Isolation:**
- Subprocesses inherit environment
- No additional secrets passed
- Use standard environment variable security

### Denial of Service

**Single Connection Model:**
- Socket accepts one client at a time
- New connections block until current disconnects
- Prevents connection exhaustion
- Simple to reason about

**No Authentication:**
- Unix socket security relies on file permissions
- No username/password needed
- Kernel enforces access control

**Rate Limiting:**
- CLI commands processed sequentially
- ExaBGP reactor controls command execution rate
- No explicit rate limiting in transport layer

---

## Performance Considerations

### Socket vs Pipe Performance

**Theoretical:**
- Sockets: Bidirectional, single syscall per direction
- Pipes: Unidirectional, two files, more complex

**Measured:**
- Both use same event loop architecture
- Negligible performance difference for CLI use case
- CLI commands are infrequent (human-initiated)

**Recommendation:**
- Use sockets for simplicity
- Performance difference is irrelevant for CLI

### Memory Usage

**Buffers:**
- Each transport maintains separate buffers for stdin/stdout
- Default: 1KB chunks, 100MB max backlog
- Backlog cleared on client disconnect

**Connection Overhead:**
- Socket: Single fd per client + server fd
- Pipe: Two fds (in + out)
- Minimal difference

### Concurrency

**Current Model:**
- Single client at a time (both transports)
- Sequential command processing
- Simple and predictable

**Future:**
- Could support multiple simultaneous socket connections
- Would require multiplexing logic in socket process
- Not needed for current use case

---

## Testing Strategy

### Unit Tests (`tests/unit/test_cli_transport.py`)

**Path Discovery:**
- Test `unix_socket()` with various paths
- Test `named_pipe()` with various paths
- Test explicit path override (`exabgp_api_socketpath`)

**Argument Parsing:**
- Test `--pipe` flag
- Test `--socket` flag
- Test mutual exclusivity

**Transport Selection:**
- Test flag priority
- Test environment variable priority
- Test default behavior

**Command Shortcuts:**
- Test nickname expansion
- Test context-aware shortcuts

### Functional Tests

**Encoding Tests** (`./qa/bin/functional encoding`):
- 72 tests spawn client/server ExaBGP instances
- Both use CLI API internally
- Tests work with both transports

**Decoding Tests** (`./qa/bin/functional decoding`):
- 18 tests validate message parsing
- Indirectly test CLI API

**Manual Testing:**
- Concurrent usage (both transports)
- Custom names and paths
- Error conditions (missing files, permissions)
- Migration scenarios

---

## Debugging

### Enable Logging

**ExaBGP Daemon:**
```bash
env exabgp_log_enable=true \
    exabgp_log_level=DEBUG \
    ./sbin/exabgp config.conf
```

**Subprocess (Pipe/Socket):**
```bash
# Subprocess inherits logging settings
# Check daemon logs for subprocess output
```

### Trace System Calls

**Socket Process:**
```bash
# Find socket process PID
ps aux | grep api-internal-cli-socket

# Trace syscalls
sudo strace -p <PID> -e trace=network,desc
```

**Pipe Process:**
```bash
# Find pipe process PID
ps aux | grep api-internal-cli-pipe

# Trace syscalls
sudo strace -p <PID> -e trace=desc,file
```

### Check File Descriptors

**Socket Process:**
```bash
# List open fds
lsof -p <PID>

# Expected:
# - stdin (fd 0)
# - stdout (fd 1)
# - stderr (fd 2)
# - server socket (fd 3)
# - client socket (fd 4, if connected)
```

**Pipe Process:**
```bash
# List open fds
lsof -p <PID>

# Expected:
# - stdin (fd 0)
# - stdout (fd 1)
# - stderr (fd 2)
# - FIFO.in (fd 3)
# - FIFO.out (fd 4)
```

### Test Transport Manually

**Socket:**
```bash
# Terminal 1: Start ExaBGP
./sbin/exabgp config.conf

# Terminal 2: Connect manually
nc -U /run/exabgp/exabgp.sock
show neighbor
<Ctrl+D>
```

**Pipe:**
```bash
# Terminal 1: Start ExaBGP
env exabgp_cli_pipe=/tmp/exabgp ./sbin/exabgp config.conf

# Terminal 2: Send command
echo "show neighbor" > /tmp/exabgp/exabgp.in

# Terminal 3: Read response
cat /tmp/exabgp/exabgp.out
```

---

## Future Enhancements

### Multiple Simultaneous Connections (Socket)

**Current:** Single connection at a time
**Proposed:** Multiple concurrent connections

**Changes needed:**
- Track multiple client sockets
- Multiplex stdin to all clients (broadcast)
- Queue commands from multiple clients
- Add connection ID to commands

**Benefits:**
- Multiple CLI sessions simultaneously
- Monitoring while running commands

**Challenges:**
- Command ordering
- Response routing
- Complexity increase

### WebSocket Transport

**Proposal:** Add WebSocket transport for remote access

**Benefits:**
- Remote CLI over HTTP/HTTPS
- Browser-based CLI
- Firewall-friendly

**Challenges:**
- Authentication/authorization
- TLS certificate management
- Security implications

### Authentication/Authorization

**Current:** File permissions only
**Proposed:** Username/password or token auth

**Benefits:**
- Granular access control
- Audit logging
- Multi-user support

**Challenges:**
- Credential management
- Backward compatibility
- Performance impact

---

**Last Updated:** 2025-11-19
