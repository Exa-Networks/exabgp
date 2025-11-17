# ExaBGP AsyncIO Architecture - Technical Guide

**Purpose:** Explain how the async implementation works, not the migration history.
**Audience:** Developers who need to understand or modify the async code.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Dual-Mode Design Pattern](#dual-mode-design-pattern)
3. [Event Loop Integration](#event-loop-integration)
4. [API Process Communication](#api-process-communication)
5. [Connection and I/O Layer](#connection-and-io-layer)
6. [Protocol Layer](#protocol-layer)
7. [Peer State Machine](#peer-state-machine)
8. [Message Flow](#message-flow)
9. [Concurrency Model](#concurrency-model)
10. [Error Handling](#error-handling)

---

## Architecture Overview

### High-Level Architecture

ExaBGP uses a **dual-mode reactor pattern** that supports both traditional select-based and modern asyncio-based event loops:

```
                    ┌─────────────────────┐
                    │   Configuration     │
                    │  (Determines Mode)  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Environment Check  │
                    │ exabgp_asyncio_enable│
                    └──────────┬──────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
        ┌───────▼────────┐           ┌───────▼────────┐
        │   Sync Mode    │           │   Async Mode   │
        │  (Default)     │           │   (Opt-in)     │
        │                │           │                │
        │ select.poll()  │           │ asyncio.run()  │
        │  Generators    │           │  async/await   │
        └───────┬────────┘           └───────┬────────┘
                │                             │
                └──────────────┬──────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  BGP Protocol       │
                    │  (Shared Logic)     │
                    └─────────────────────┘
```

### Core Components

1. **Reactor** (`src/exabgp/reactor/loop.py`)
   - Main event loop coordinator
   - Manages peer connections
   - Handles signals and scheduling
   - Dual-mode entry points: `run()` (sync) and `run_async()` (async)

2. **Peer** (`src/exabgp/reactor/peer.py`)
   - BGP peer state machine (FSM)
   - Connection lifecycle management
   - Message routing
   - Dual-mode FSM: `run()` (sync) and `run_async()` (async)

3. **Protocol** (`src/exabgp/reactor/protocol.py`)
   - BGP message encoding/decoding
   - Message validation
   - Capability negotiation
   - Dual-mode I/O: `read_message()` and `read_message_async()`

4. **Connection** (`src/exabgp/reactor/network/connection.py`)
   - Low-level socket I/O
   - Non-blocking reads/writes
   - Buffer management
   - Dual-mode primitives: `reader()` and `reader_async()`

5. **API Processes** (`src/exabgp/reactor/api/processes.py`)
   - External process management (stdin/stdout)
   - Command parsing and routing
   - **Critical:** Event loop FD integration for async mode

---

## Dual-Mode Design Pattern

### Mode Detection

```python
# src/exabgp/reactor/loop.py

class Reactor:
    def __init__(self, configuration):
        # Detect mode from environment
        self._async_mode = os.environ.get('exabgp_asyncio_enable', '').lower() in ('true', '1', 'yes')

        if self._async_mode:
            logger.info("Async mode: ENABLED")
        else:
            logger.info("Async mode: DISABLED (using sync mode)")
```

### Dual Entry Points

Every major component has parallel sync and async implementations:

```python
class Reactor:
    def run(self):
        """Sync mode - uses select.poll() and generators"""
        # Traditional event loop
        while True:
            events = self._poll.poll(self.timeout)
            for fd, event in events:
                self._handle_event(fd, event)

    async def run_async(self):
        """Async mode - uses asyncio event loop"""
        # Modern async event loop
        await self._async_main_loop()
```

### Shared State, Separate Logic

Both modes share:
- Configuration data
- BGP state (RIB, neighbors, etc.)
- Message data structures
- Validation logic

Only the **control flow** differs:
- Sync: Generators with `yield ACTION.*`
- Async: Async/await with `await asyncio.sleep(0)`

---

## Event Loop Integration

### Async Event Loop Structure

The async event loop coordinates multiple concurrent activities:

```python
# src/exabgp/reactor/loop.py

async def _async_main_loop(self):
    """Main async event loop - coordinates all activities"""

    # Setup signal handlers
    self._setup_signal_handlers()

    # Setup API process readers (critical for async mode!)
    self.processes.setup_async_readers(asyncio.get_running_loop())

    # Start peer tasks
    peer_tasks = {}

    while True:
        # 1. Handle signals (SIGUSR1, SIGHUP, etc.)
        if self._signal_received:
            self._handle_signal()

        # 2. Accept new connections
        self.listener.incoming()

        # 3. Manage peer tasks
        await self._run_async_peers(peer_tasks)

        # 4. Process API commands (from external processes)
        for service, command in self.processes.received_async():
            self.api.process(self, service, command)

        # 5. Run scheduled tasks
        self.asynchronous.run()

        # 6. Yield control to event loop
        await asyncio.sleep(0)
```

### Peer Task Coordination

```python
async def _run_async_peers(self, tasks):
    """Coordinate concurrent peer FSM tasks"""

    # Start tasks for new peers
    for peer_name in self.peers:
        if peer_name not in tasks:
            peer = self.peers[peer_name]
            task = asyncio.create_task(peer.run_async())
            tasks[peer_name] = task

    # Check for completed/failed tasks
    for peer_name in list(tasks.keys()):
        task = tasks[peer_name]
        if task.done():
            try:
                await task  # Propagate exceptions
            except Exception as e:
                logger.error(f"Peer {peer_name} failed: {e}")
            del tasks[peer_name]
```

**Key Points:**
- Each peer runs as independent async task
- Tasks created on-demand for new peers
- Failed tasks logged and removed
- No blocking - all I/O is async

---

## API Process Communication

### The Challenge

External API processes communicate via stdin/stdout using **synchronous I/O**. The async event loop needs to be notified when data is available without blocking.

### The Solution: loop.add_reader()

```python
# src/exabgp/reactor/api/processes.py

class Processes:
    def __init__(self):
        self._async_mode = False
        self._loop = None
        self._command_queue = collections.deque()  # Buffer for commands

    def setup_async_readers(self, loop):
        """Register API process stdout FDs with event loop"""
        self._async_mode = True
        self._loop = loop

        # Register callback for each existing process
        for name, process in self._process.items():
            if process and process.stdout:
                fd = process.stdout.fileno()
                # OS will notify loop when data available
                loop.add_reader(fd, self._async_reader_callback, name)
```

### Event-Driven Callback

```python
def _async_reader_callback(self, process_name):
    """Called by event loop when process stdout has data"""

    process = self._process.get(process_name)
    if not process or not process.stdout:
        return

    try:
        # Non-blocking read (data is available)
        fd = process.stdout.fileno()
        data = os.read(fd, 16384)

        if not data:
            # EOF - process terminated
            self._handle_process_exit(process_name)
            return

        # Accumulate data in buffer
        self._buffer[process_name] += data.decode('utf-8')

        # Parse complete lines (commands are line-delimited)
        while '\n' in self._buffer[process_name]:
            line, _, self._buffer[process_name] = self._buffer[process_name].partition('\n')
            command = line.strip()

            if command:
                # Queue for reactor to process
                self._command_queue.append((process_name, command))

    except (OSError, IOError) as e:
        logger.error(f"Error reading from {process_name}: {e}")
```

### Generator Bridge

```python
def received_async(self):
    """Generator that yields buffered commands"""
    while self._command_queue:
        yield self._command_queue.popleft()
```

**Why This Works:**

1. **OS-level I/O multiplexing:** `loop.add_reader()` uses epoll/kqueue/IOCP
2. **Event-driven:** Callback only runs when data available
3. **Non-blocking:** `os.read()` returns immediately (data ready)
4. **Queue buffering:** Decouples callback (event loop) from processing (reactor)
5. **Generator bridge:** Reactor consumes commands in familiar pattern

### Flow Diagram

```
External Process                Event Loop                  Reactor
      │                              │                         │
      │ write("announce...")         │                         │
      ├─────────────────────────────>│                         │
      │                              │                         │
      │                              │ FD readable             │
      │                              ├──> add_reader callback  │
      │                              │                         │
      │                              │ _async_reader_callback()│
      │                              │   - os.read(fd)         │
      │                              │   - parse lines         │
      │                              │   - queue.append()      │
      │                              │                         │
      │                              │<────────────────────────│
      │                              │  received_async()       │
      │                              │                         │
      │                              │  yield command──────────>│
      │                              │                         │
      │                              │                         │ api.process()
      │                              │                         │
```

---

## Connection and I/O Layer

### Async Socket I/O

```python
# src/exabgp/reactor/network/connection.py

class Connection:
    async def reader_async(self, max_size=65536):
        """Read data from socket asynchronously"""

        if not self.io or self.io.closed:
            raise NetworkError("Socket closed")

        loop = asyncio.get_running_loop()

        try:
            # Non-blocking socket read using asyncio
            data = await loop.sock_recv(self.io, max_size)

            if not data:
                # EOF - connection closed
                raise NetworkError("Connection closed by peer")

            return data

        except BlockingIOError:
            # Would block - yield and retry
            await asyncio.sleep(0)
            return b''

        except Exception as e:
            raise NetworkError(f"Read failed: {e}")

    async def writer_async(self, data):
        """Write data to socket asynchronously"""

        if not self.io or self.io.closed:
            raise NetworkError("Socket closed")

        loop = asyncio.get_running_loop()

        try:
            # Non-blocking socket write using asyncio
            await loop.sock_sendall(self.io, data)

        except Exception as e:
            raise NetworkError(f"Write failed: {e}")
```

**Key Points:**
- Uses `loop.sock_recv()` and `loop.sock_sendall()` (asyncio primitives)
- Sockets are non-blocking (`socket.setblocking(False)`)
- Event loop handles waiting for I/O readiness
- No busy-waiting or polling

### Async Connection Establishment

```python
# src/exabgp/reactor/network/outgoing.py

class Outgoing:
    async def establish_async(self, timeout=30.0, max_attempts=50):
        """Establish TCP connection asynchronously with timeout"""

        loop = asyncio.get_running_loop()
        start_time = loop.time()
        attempt = 0

        while True:
            attempt += 1
            elapsed = loop.time() - start_time

            # Check timeout
            if elapsed >= timeout:
                raise NetworkError(f"Connection timeout after {elapsed:.1f}s")

            # Check max attempts
            if attempt > max_attempts:
                raise NetworkError(f"Max attempts ({max_attempts}) exceeded")

            try:
                # Create non-blocking socket
                sock = socket.socket(self.peer.family, socket.SOCK_STREAM)
                sock.setblocking(False)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

                # Async connect (non-blocking)
                await loop.sock_connect(sock, (self.peer.peer_address, self.peer.peer_port))

                # Success!
                self.io = sock
                return True

            except OSError as e:
                # Connection refused, network unreachable, etc.
                sock.close()

                # Retry with backoff
                await asyncio.sleep(min(1.0, 0.1 * attempt))
                continue
```

**Features:**
- Non-blocking connect with `loop.sock_connect()`
- Configurable timeout (default: 30s)
- Retry logic with exponential backoff
- Max attempt limit prevents infinite loops
- Clean error propagation

---

## Protocol Layer

### Message Reading

```python
# src/exabgp/reactor/protocol.py

class Protocol:
    async def read_message_async(self):
        """Read one BGP message asynchronously"""

        # Read BGP header (19 bytes: marker + length + type)
        header = b''
        while len(header) < 19:
            chunk = await self.connection.reader_async(19 - len(header))
            if not chunk:
                await asyncio.sleep(0.01)  # Brief wait
                continue
            header += chunk

        # Parse header
        if header[:16] != BGP_MARKER:  # 16 bytes of 0xFF
            raise ProtocolError("Invalid BGP marker")

        length = struct.unpack('!H', header[16:18])[0]
        msg_type = header[18]

        # Read message body
        body_len = length - 19
        body = b''

        while len(body) < body_len:
            chunk = await self.connection.reader_async(body_len - len(body))
            if not chunk:
                await asyncio.sleep(0.01)
                continue
            body += chunk

        # Parse message based on type
        raw_message = header + body
        return Message.unpack(msg_type, raw_message, self.negotiated)
```

### Message Writing

```python
async def write_message_async(self, message):
    """Write BGP message asynchronously"""

    # Pack message with negotiated capabilities
    raw = message.pack_message(self.negotiated)

    # Write to socket
    await self.connection.writer_async(raw)

    # Update statistics
    self.stats.sent += 1
    self.stats.sent_bytes += len(raw)
```

### Protocol Message Generators

```python
async def new_update_async(self, updates):
    """Generate UPDATE messages asynchronously"""

    for update in updates:
        # Pack UPDATE message
        message = Update([update.nlri], update.attributes)

        # Send it
        await self.write_message_async(message)

        # Yield control (don't monopolize event loop)
        await asyncio.sleep(0)

async def new_operational_async(self, operational):
    """Send OPERATIONAL message asynchronously"""

    message = Operational(operational.what, operational.data)
    await self.write_message_async(message)

async def new_refresh_async(self, refresh):
    """Send ROUTE-REFRESH message asynchronously"""

    message = RouteRefresh(refresh.afi, refresh.safi)
    await self.write_message_async(message)
```

**Key Patterns:**
- **Async I/O:** All socket operations use `await`
- **Loop yielding:** `await asyncio.sleep(0)` prevents monopolization
- **Error propagation:** Exceptions bubble up to peer FSM
- **No blocking:** Everything is non-blocking

---

## Peer State Machine

### Async FSM Main Loop

```python
# src/exabgp/reactor/peer.py

class Peer:
    async def run_async(self):
        """Main async FSM loop for peer"""

        while True:
            try:
                # Attempt to establish connection
                await self._establish_async()

                # Run main protocol loop
                await self._main_async()

            except NetworkError as e:
                # Connection failed - retry after delay
                logger.error(f"Peer {self.name}: {e}")
                await asyncio.sleep(self.retry_delay)
                continue

            except ProtocolError as e:
                # BGP protocol error - send NOTIFICATION and reconnect
                logger.error(f"Peer {self.name}: {e}")
                await self._send_notification_async(e.notification)
                await asyncio.sleep(self.retry_delay)
                continue

            except Exception as e:
                # Unexpected error - log and retry
                logger.exception(f"Peer {self.name}: Unexpected error")
                await asyncio.sleep(self.retry_delay)
                continue
```

### Connection Establishment

```python
async def _establish_async(self):
    """Establish BGP session asynchronously"""

    # 1. TCP connection
    await self.connection.establish_async(timeout=30.0)

    # 2. Send OPEN message
    open_sent = await self._send_open_async()

    # 3. Receive OPEN message
    open_received = await self._read_open_async()

    # 4. Validate OPEN
    self._validate_open(open_received, open_sent)

    # 5. Send KEEPALIVE (confirms OPEN)
    await self._send_ka_async()

    # 6. Receive KEEPALIVE
    await self._read_ka_async()

    # 7. Session established!
    self.fsm.state = FSM.ESTABLISHED
    logger.info(f"Peer {self.name}: Session established")
```

### Main Protocol Loop

```python
async def _main_async(self):
    """Main BGP protocol loop after ESTABLISHED"""

    last_ka = asyncio.get_running_loop().time()

    while True:
        # Send pending UPDATEs
        if self._updates_pending():
            updates = self._get_pending_updates()
            await self.protocol.new_update_async(updates)
            await asyncio.sleep(0)  # Yield

        # Send OPERATIONAL messages
        if self._operational_pending():
            operational = self._get_pending_operational()
            await self.protocol.new_operational_async(operational)
            await asyncio.sleep(0)

        # Send ROUTE-REFRESH
        if self._refresh_pending():
            refresh = self._get_pending_refresh()
            await self.protocol.new_refresh_async(refresh)
            await asyncio.sleep(0)

        # Send KEEPALIVE (periodic)
        now = asyncio.get_running_loop().time()
        if now - last_ka >= self.hold_time / 3:
            await self._send_ka_async()
            last_ka = now

        # Read incoming messages
        try:
            message = await self.protocol.read_message_async()
            await self._handle_message_async(message)
        except asyncio.TimeoutError:
            # No message yet - continue loop
            pass

        # Yield control
        await asyncio.sleep(0.01)
```

**Key Patterns:**
- **State tracking:** FSM states (IDLE → ACTIVE → CONNECT → ESTABLISHED)
- **Error handling:** Network errors → reconnect, Protocol errors → NOTIFICATION
- **Message batching:** Process all pending updates before yielding
- **Periodic tasks:** KEEPALIVE timer using event loop time
- **Non-blocking:** All I/O operations use `await`

---

## Message Flow

### Outbound Message Flow

```
Application/API Command
         │
         ▼
  ┌──────────────┐
  │ API Process  │
  │ (External)   │
  └──────┬───────┘
         │ JSON command
         ▼
  ┌──────────────┐
  │  Processes   │  received_async()
  │  (Manager)   │◄──────────────── FD callback (loop.add_reader)
  └──────┬───────┘
         │ Parsed command
         ▼
  ┌──────────────┐
  │     API      │  process()
  │  (Handler)   │
  └──────┬───────┘
         │ Route/action
         ▼
  ┌──────────────┐
  │     Peer     │  Queue update
  │    (FSM)     │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │  Protocol    │  new_update_async()
  │              │
  └──────┬───────┘
         │ Packed BGP message
         ▼
  ┌──────────────┐
  │ Connection   │  writer_async()
  │              │
  └──────┬───────┘
         │ Raw bytes
         ▼
    Network (TCP)
```

### Inbound Message Flow

```
    Network (TCP)
         │ Raw bytes
         ▼
  ┌──────────────┐
  │ Connection   │  reader_async()
  │              │
  └──────┬───────┘
         │ Raw bytes
         ▼
  ┌──────────────┐
  │  Protocol    │  read_message_async()
  │              │  Message.unpack()
  └──────┬───────┘
         │ Parsed message
         ▼
  ┌──────────────┐
  │     Peer     │  _handle_message_async()
  │    (FSM)     │  - UPDATE → RIB
  │              │  - KEEPALIVE → reset timer
  │              │  - NOTIFICATION → reconnect
  └──────┬───────┘
         │ Route update
         ▼
  ┌──────────────┐
  │     RIB      │  Store/update routes
  │              │
  └──────┬───────┘
         │ Notification
         ▼
  ┌──────────────┐
  │  Processes   │  Send to API processes
  │  (Manager)   │
  └──────┬───────┘
         │ JSON notification
         ▼
  ┌──────────────┐
  │ API Process  │  Process update
  │ (External)   │
  └──────────────┘
```

---

## Concurrency Model

### Task-Based Concurrency

ExaBGP async mode uses **cooperative multitasking** with asyncio:

```python
# Each peer is an independent task
peer1_task = asyncio.create_task(peer1.run_async())
peer2_task = asyncio.create_task(peer2.run_async())
peer3_task = asyncio.create_task(peer3.run_async())

# Tasks run concurrently on single thread
# Event loop schedules based on I/O readiness
```

**Characteristics:**
- **Single-threaded:** No locks, no race conditions
- **I/O-bound:** Tasks wait on network I/O
- **Cooperative:** Tasks must `await` to yield control
- **Fair scheduling:** Event loop ensures fairness

### Yielding Control

Tasks must explicitly yield control to prevent monopolization:

```python
# Good: Yields control after each update
async def process_updates(updates):
    for update in updates:
        await send_update(update)
        await asyncio.sleep(0)  # Yield to other tasks

# Bad: Monopolizes event loop
async def process_updates_bad(updates):
    for update in updates:
        await send_update(update)
    # No yielding - other tasks starved!
```

### Shared State Management

Since everything runs on one thread, shared state is safe:

```python
class Reactor:
    def __init__(self):
        self.rib = RIB()  # Shared routing table
        self.peers = {}   # Shared peer dict
        # No locks needed - single thread!
```

**But be careful:**
- Don't hold references across `await` points if state can change
- Use immutable data structures where possible
- Be aware of re-entrancy in callbacks

---

## Error Handling

### Exception Hierarchy

```python
NetworkError          # Socket, connection issues
  ├─ ConnectionClosed # Peer closed connection
  ├─ ConnectionRefused # Can't connect
  └─ Timeout          # Operation timed out

ProtocolError         # BGP protocol violations
  ├─ InvalidMarker    # Bad BGP header
  ├─ InvalidLength    # Message length wrong
  └─ InvalidAttribute # Malformed attribute
```

### Error Recovery Strategy

```python
async def run_async(self):
    """Peer main loop with error recovery"""

    while True:
        try:
            await self._establish_async()
            await self._main_async()

        except NetworkError as e:
            # Network issues - log and retry
            logger.error(f"Network error: {e}")
            self._cleanup_connection()
            await asyncio.sleep(self.retry_delay)
            continue

        except ProtocolError as e:
            # Protocol violations - send NOTIFICATION
            logger.error(f"Protocol error: {e}")
            try:
                await self._send_notification_async(e.notification)
            except:
                pass  # Best effort
            self._cleanup_connection()
            await asyncio.sleep(self.retry_delay)
            continue

        except Exception as e:
            # Unexpected errors - log and retry
            logger.exception(f"Unexpected error: {e}")
            self._cleanup_connection()
            await asyncio.sleep(self.retry_delay)
            continue
```

**Recovery Patterns:**
1. **Network errors:** Clean up, wait, retry
2. **Protocol errors:** Send NOTIFICATION, clean up, retry
3. **Unexpected errors:** Log traceback, clean up, retry
4. **Never crash:** Always recover and continue

### Cleanup on Error

```python
def _cleanup_connection(self):
    """Clean up connection state after error"""

    if self.connection.io:
        try:
            self.connection.io.close()
        except:
            pass

    self.connection.io = None
    self.fsm.state = FSM.IDLE
    self.negotiated.clear()
```

---

## Performance Considerations

### Async Advantages

1. **Scalability:** Handle 100+ peers on single thread
2. **Efficiency:** No context switching overhead
3. **I/O optimization:** OS-level I/O multiplexing (epoll/kqueue)
4. **Modern libraries:** Easy integration with async ecosystem

### Potential Bottlenecks

1. **CPU-bound operations:** Message parsing/packing (use async executor if needed)
2. **Large messages:** Batch processing can monopolize loop
3. **API processes:** FD callback overhead for many processes

### Optimization Strategies

```python
# Batch processing with yielding
async def process_large_table(routes):
    batch_size = 100

    for i in range(0, len(routes), batch_size):
        batch = routes[i:i+batch_size]

        for route in batch:
            await send_update(route)

        # Yield after each batch
        await asyncio.sleep(0)
```

```python
# Prioritize critical messages
async def message_loop(self):
    while True:
        # High priority: KEEPALIVE (prevent timeout)
        if self._ka_due():
            await self._send_ka_async()

        # Medium priority: NOTIFICATION (peer errors)
        if self._notifications_pending():
            await self._send_notifications_async()

        # Low priority: UPDATE (route changes)
        if self._updates_pending():
            await self._send_updates_async()

        await asyncio.sleep(0.01)
```

---

## Debugging and Monitoring

### Logging

```python
import logging

logger = logging.getLogger('exabgp.reactor')

# Async context in logs
async def establish_async(self):
    logger.info(f"[ASYNC] Peer {self.name}: Connecting...")

    try:
        await self.connection.connect_async()
        logger.info(f"[ASYNC] Peer {self.name}: Connected")
    except Exception as e:
        logger.error(f"[ASYNC] Peer {self.name}: Failed - {e}")
        raise
```

### Task Monitoring

```python
async def _run_async_peers(self, tasks):
    """Monitor peer tasks for failures"""

    for peer_name, task in list(tasks.items()):
        if task.done():
            try:
                await task  # Check for exceptions
            except Exception as e:
                logger.error(f"Peer {peer_name} task failed: {e}")
                logger.exception("Full traceback:")

            del tasks[peer_name]
```

### Performance Metrics

```python
import time

class Metrics:
    def __init__(self):
        self.messages_sent = 0
        self.messages_received = 0
        self.bytes_sent = 0
        self.bytes_received = 0
        self.start_time = time.time()

    def uptime(self):
        return time.time() - self.start_time

    def throughput(self):
        return self.messages_sent / self.uptime()
```

---

## Summary

### Key Takeaways

1. **Dual-mode design** maintains backward compatibility while enabling async
2. **API FD integration** (`loop.add_reader()`) is critical for async mode
3. **Cooperative multitasking** requires explicit yielding (`await asyncio.sleep(0)`)
4. **Single-threaded** means no locks but be aware of re-entrancy
5. **Error recovery** is essential - always retry, never crash

### Code Patterns Reference

**Async I/O:**
```python
data = await connection.reader_async()
await connection.writer_async(data)
```

**Yielding Control:**
```python
await asyncio.sleep(0)  # Minimal yield
await asyncio.sleep(0.01)  # Brief wait
```

**Task Creation:**
```python
task = asyncio.create_task(peer.run_async())
```

**Error Handling:**
```python
try:
    await operation()
except SpecificError as e:
    # Handle and recover
    await cleanup()
```

---

**For More Information:**
- See `docs/asyncio-migration/README.md` for migration history
- See source code in `src/exabgp/reactor/` for implementation
- See tests in `tests/` for usage examples

**Last Updated:** 2025-11-17
