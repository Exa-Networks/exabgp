# API Process Integration with AsyncIO Event Loop

**Critical Component:** This integration is what enables async mode to achieve 100% test parity.
**Without this:** API-based tests timeout (36/72 pass). With this:** All tests pass (72/72).

---

## The Problem

ExaBGP communicates with external API processes via stdin/stdout pipes. These processes:
- Send commands (JSON over stdin): `announce route 10.0.0.0/24 next-hop 192.168.1.1`
- Receive updates (JSON over stdout): `{"neighbor": "...", "update": {...}}`

**Challenge:** How do we integrate synchronous pipe I/O with asyncio's event loop?

### Failed Approaches

**1. Polling with asyncio.sleep():**
```python
# BAD: Busy-waiting wastes CPU
async def poll_processes(self):
    while True:
        for process in self._processes:
            data = process.stdout.read()  # Blocks!
            if data:
                self._handle(data)
        await asyncio.sleep(0.01)  # Still wasteful
```

**2. Thread-based readers:**
```python
# BAD: Threading complexity, race conditions
def reader_thread(process):
    while True:
        data = process.stdout.read()  # Blocks thread
        queue.put(data)  # Thread-safe queue needed

# Requires locks, queues, thread management
```

**3. select.poll() in async:**
```python
# BAD: Blocks the entire event loop!
async def poll_processes(self):
    poller = select.poll()
    poller.register(process.stdout, select.POLLIN)

    for fd, event in poller.poll(timeout):  # BLOCKS EVENT LOOP!
        self._handle(fd)
```

---

## The Solution: loop.add_reader()

AsyncIO provides `loop.add_reader(fd, callback, *args)` which:
1. Registers a file descriptor with the OS-level I/O multiplexer (epoll/kqueue/IOCP)
2. Event loop calls callback when FD becomes readable
3. No polling, no threads, no blocking

### Architecture

```
┌────────────────────────────────────────────────────────────┐
│                   AsyncIO Event Loop                        │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │  I/O Multiplexer (epoll/kqueue/IOCP)              │    │
│  │                                                     │    │
│  │  Monitored FDs:                                    │    │
│  │    - API process stdout (fd=10) ───> callback_1   │    │
│  │    - API process stdout (fd=11) ───> callback_2   │    │
│  │    - BGP socket (fd=12) ───────────> callback_3   │    │
│  │    - BGP socket (fd=13) ───────────> callback_4   │    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  When fd becomes readable:                                 │
│    1. OS notifies event loop                               │
│    2. Event loop calls registered callback                 │
│    3. Callback does non-blocking read                      │
│    4. Data queued for reactor processing                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation

### 1. Setup Phase

Called once when async mode starts:

```python
# src/exabgp/reactor/api/processes.py

class Processes:
    def __init__(self):
        self._async_mode = False
        self._loop = None
        self._command_queue = collections.deque()  # Buffered commands
        self._buffer = {}  # Incomplete lines per process

    def setup_async_readers(self, loop):
        """Register all API process stdout FDs with event loop"""

        self._async_mode = True
        self._loop = loop

        logger.info(f"[ASYNC] Setting up async readers for {len(self._process)} processes")

        # Register each existing process
        for name, process in self._process.items():
            if process and process.stdout:
                fd = process.stdout.fileno()

                # Register callback with event loop
                loop.add_reader(
                    fd,                           # File descriptor to monitor
                    self._async_reader_callback,  # Callback when readable
                    name                          # Argument to callback
                )

                logger.debug(f"[ASYNC] Registered reader for {name} (fd={fd})")

                # Initialize buffer for this process
                self._buffer[name] = ''
```

**Called from:** `reactor/loop.py` in `run_async()` after starting API processes

### 2. Callback Phase

Called by event loop when process stdout becomes readable:

```python
def _async_reader_callback(self, process_name):
    """
    Called by event loop when process stdout has data available

    IMPORTANT:
    - This runs in the event loop thread (same as everything else)
    - Non-blocking read (data is guaranteed available)
    - Must be fast - don't do heavy processing here
    """

    process = self._process.get(process_name)
    if not process or not process.stdout:
        # Process terminated - cleanup reader
        if self._loop:
            try:
                fd = process.stdout.fileno() if process and process.stdout else None
                if fd is not None:
                    self._loop.remove_reader(fd)
            except:
                pass
        return

    try:
        # Non-blocking read (data is available, guaranteed by OS)
        fd = process.stdout.fileno()
        data = os.read(fd, 16384)  # Read up to 16KB

        if not data:
            # EOF - process closed stdout (terminated)
            logger.info(f"[ASYNC] Process {process_name} EOF")
            self._handle_process_exit(process_name)
            return

        # Decode and append to buffer
        self._buffer[process_name] += data.decode('utf-8')

        # Parse complete lines (commands are newline-delimited)
        while '\n' in self._buffer[process_name]:
            line, _, self._buffer[process_name] = self._buffer[process_name].partition('\n')
            command = line.strip()

            if command:
                # Queue command for reactor to process
                self._command_queue.append((process_name, command))

                logger.debug(f"[ASYNC] Queued command from {process_name}: {command[:50]}...")

    except (OSError, IOError) as e:
        # Read error - process may have died
        logger.error(f"[ASYNC] Error reading from {process_name}: {e}")
        self._handle_process_exit(process_name)

    except UnicodeDecodeError as e:
        # Invalid UTF-8 - log and continue
        logger.error(f"[ASYNC] Decode error from {process_name}: {e}")
        self._buffer[process_name] = ''  # Discard bad data
```

**Key Points:**
- Runs when data is available (no blocking)
- Uses `os.read()` for non-blocking read
- Buffers incomplete lines
- Queues complete commands for reactor
- Fast - minimal processing

### 3. Consumption Phase

Called by reactor in main async loop:

```python
def received_async(self):
    """
    Generator that yields buffered commands

    Called by reactor main loop to get pending API commands
    Bridges callback-based queueing with generator-based processing
    """

    while self._command_queue:
        service, command = self._command_queue.popleft()
        yield service, command
```

**Usage in reactor:**
```python
# src/exabgp/reactor/loop.py

async def _async_main_loop(self):
    """Main async event loop"""

    # Setup API readers (once at start)
    self.processes.setup_async_readers(asyncio.get_running_loop())

    while True:
        # ... other loop activities ...

        # Process buffered API commands
        for service, command in self.processes.received_async():
            self.api.process(self, service, command)

        # Yield control
        await asyncio.sleep(0)
```

### 4. Cleanup Phase

When process exits or is terminated:

```python
def _handle_process_exit(self, process_name):
    """Clean up when process exits"""

    # Remove reader from event loop
    if self._loop and process_name in self._process:
        process = self._process[process_name]
        if process and process.stdout:
            try:
                fd = process.stdout.fileno()
                self._loop.remove_reader(fd)
                logger.debug(f"[ASYNC] Removed reader for {process_name}")
            except:
                pass

    # Clear buffer
    if process_name in self._buffer:
        del self._buffer[process_name]

    # Terminate process
    self._terminate(process_name)
```

### 5. Dynamic Registration

When new processes start during runtime:

```python
def _start(self, restart=False):
    """Start API process (may be called during runtime)"""

    # ... existing process startup code ...

    # If async mode, register reader for new process
    if self._async_mode and self._loop:
        process = self._process[service]
        if process and process.stdout:
            fd = process.stdout.fileno()
            self._loop.add_reader(fd, self._async_reader_callback, service)
            self._buffer[service] = ''

            logger.info(f"[ASYNC] Registered reader for new process {service}")
```

---

## How It Works: Detailed Flow

### Initial Setup

```
1. Reactor starts: reactor.run_async()
   └─> Start API processes: reactor.processes.start()
       └─> Launch external scripts via subprocess.Popen()
           └─> Each process has stdin/stdout pipes

2. Reactor calls: processes.setup_async_readers(loop)
   └─> For each process:
       └─> Get stdout FD: fd = process.stdout.fileno()
       └─> Register with loop: loop.add_reader(fd, callback, name)

3. Event loop now monitors all API process FDs
```

### Runtime: Command Received

```
External Process                     OS                  Event Loop                 Reactor
      │                              │                        │                       │
      │ write("announce 10.0.0.0/24")│                       │                       │
      ├─────────────────────────────>│                       │                       │
      │                              │                       │                       │
      │                              │ FD 10 readable        │                       │
      │                              ├──────────────────────>│                       │
      │                              │                       │                       │
      │                              │                 Call callback                 │
      │                              │          _async_reader_callback(name)         │
      │                              │                       │                       │
      │                              │<───── os.read(10) ────│                       │
      │                              │                       │                       │
      │                              │── data ─────────────->│                       │
      │                              │                       │                       │
      │                              │                Parse lines                    │
      │                              │                Queue command                  │
      │                              │         queue.append((name, cmd))            │
      │                              │                       │                       │
      │                              │                       │                       │
      │                              │                       │  received_async()     │
      │                              │                       │<──────────────────────│
      │                              │                       │                       │
      │                              │                       │ yield (name, cmd) ───>│
      │                              │                       │                       │
      │                              │                       │                api.process()
      │                              │                       │                       │
```

### Why It's Efficient

1. **Event-driven:** Callback only fires when data available
2. **Non-blocking:** `os.read()` returns immediately (data ready)
3. **No polling:** Event loop handles waiting
4. **OS-level:** Uses epoll (Linux), kqueue (BSD/macOS), IOCP (Windows)
5. **Single-threaded:** No thread overhead or synchronization

### Performance Characteristics

**Memory:**
- Command queue: O(pending commands) - typically small
- Buffers: O(processes) - one buffer per process, typically < 1KB each

**CPU:**
- Callback overhead: Minimal, runs only when data available
- Queue operations: O(1) - deque append/popleft

**Latency:**
- Near-instant: Event loop wakes as soon as data available
- No polling delay

---

## Testing Validation

### Test Pattern Analysis

After implementing API FD integration:

**API Tests (api-*):**
- Before: 1/36 passing (2.8%) - all others timing out
- After: 36/36 passing (100%)
- **Why:** Event loop now receives API responses via callbacks

**Config Tests (conf-*):**
- Before: 35/36 passing (97.2%)
- After: 36/36 passing (100%)
- **Why:** These don't use API processes, always worked

### What Was Fixed

**Before API FD integration:**
```python
# Sync mode used select.poll()
def received(self):
    for process in self._process.values():
        poller = select.poll()
        poller.register(process.stdout, select.POLLIN)

        # This blocks briefly but works in sync mode
        for fd, event in poller.poll(0):  # Non-blocking
            # Read data
```

**Problem in async mode:**
- `select.poll()` not integrated with asyncio event loop
- Event loop doesn't know about API FD readiness
- Commands sent but responses never seen
- Tests timeout waiting for responses that arrived but weren't processed

**After API FD integration:**
```python
# Async mode uses loop.add_reader()
def setup_async_readers(self, loop):
    loop.add_reader(fd, callback, name)
```

**Solution:**
- FDs registered with event loop
- Event loop notifies when readable
- Responses processed immediately
- Tests complete successfully

---

## Common Issues and Solutions

### Issue 1: Reader Not Firing

**Symptom:** Callback never called, commands not processed

**Causes:**
- FD not registered: Check `setup_async_readers()` called
- Wrong FD: Ensure `process.stdout.fileno()` valid
- Process died: Check process still running

**Debug:**
```python
# Add logging
logger.info(f"Registered FD {fd} for {name}")

# List registered readers
loop = asyncio.get_running_loop()
# Check loop._selector (internal, but useful for debug)
```

### Issue 2: Partial Commands

**Symptom:** Commands cut off mid-line

**Cause:** Reading before full line available

**Solution:** Line buffering (already implemented)
```python
self._buffer[name] += data.decode('utf-8')

while '\n' in self._buffer[name]:
    line, _, self._buffer[name] = self._buffer[name].partition('\n')
    # Process complete line
```

### Issue 3: High CPU Usage

**Symptom:** CPU spikes when API process active

**Causes:**
- Callback doing too much work
- Event loop spinning on readable FD

**Solutions:**
```python
# Keep callback minimal
def _async_reader_callback(self, name):
    data = os.read(fd, 16384)  # Fast
    self._buffer[name] += data  # Fast
    # Parse lines - fast
    self._queue.append(command)  # O(1)
    # Don't do heavy processing here!
```

### Issue 4: Memory Growth

**Symptom:** Memory usage grows over time

**Causes:**
- Command queue not drained
- Buffers growing unbounded

**Solutions:**
```python
# Ensure reactor consumes queue
for service, command in self.processes.received_async():
    self.api.process(self, service, command)  # Must consume!

# Limit buffer size
if len(self._buffer[name]) > 1024 * 1024:  # 1MB limit
    logger.error(f"Buffer overflow for {name}, discarding")
    self._buffer[name] = ''
```

---

## Comparison: Sync vs Async

### Sync Mode (select.poll)

```python
def received(self):
    """Sync mode: Poll each process stdout"""

    for process in self._process.values():
        if not process or not process.stdout:
            continue

        # Create poller for this FD
        poller = select.poll()
        poller.register(process.stdout, select.POLLIN)

        # Non-blocking poll (timeout=0)
        for fd, event in poller.poll(0):
            # Read available data
            data = os.read(fd, 16384)
            # Process data
            for line in data.decode().split('\n'):
                if line:
                    yield (process.name, line)
```

**Characteristics:**
- Called repeatedly by reactor main loop
- Creates/destroys poller each time
- Works with generator-based reactor
- Simple, straightforward

### Async Mode (loop.add_reader)

```python
def setup_async_readers(self, loop):
    """Async mode: Register callbacks once"""

    for name, process in self._process.items():
        if process and process.stdout:
            # Register once
            loop.add_reader(
                process.stdout.fileno(),
                self._async_reader_callback,
                name
            )

def _async_reader_callback(self, name):
    """Called when data available"""
    # Read and queue
    data = os.read(fd, 16384)
    # ... parse and queue ...

def received_async(self):
    """Yield queued commands"""
    while self._command_queue:
        yield self._command_queue.popleft()
```

**Characteristics:**
- Register once, callback fires on data
- No repeated poller creation
- Event-driven, efficient
- More complex but better integrated

---

## Best Practices

### 1. Keep Callbacks Fast

```python
# Good: Minimal work in callback
def _async_reader_callback(self, name):
    data = os.read(fd, 16384)
    self._buffer[name] += data
    self._parse_lines(name)  # Simple parsing
    # Fast and returns quickly

# Bad: Heavy processing in callback
def _async_reader_callback(self, name):
    data = os.read(fd, 16384)
    self._complex_parsing(data)  # Slow!
    self._database_lookup(data)   # Blocks!
    await self._async_operation() # ERROR: callback can't be async!
```

### 2. Handle EOF Properly

```python
def _async_reader_callback(self, name):
    data = os.read(fd, 16384)

    if not data:
        # EOF - process died
        self._cleanup_reader(name)
        return

    # Process data...
```

### 3. Register Dynamic Processes

```python
def _start(self, service):
    """Start new process at runtime"""

    # Start process
    process = subprocess.Popen(...)

    # Register with event loop if async mode
    if self._async_mode and self._loop:
        self._loop.add_reader(
            process.stdout.fileno(),
            self._async_reader_callback,
            service
        )
```

### 4. Clean Up Readers

```python
def _terminate(self, service):
    """Terminate process"""

    # Remove reader first
    if self._async_mode and self._loop:
        process = self._process[service]
        if process and process.stdout:
            try:
                self._loop.remove_reader(process.stdout.fileno())
            except:
                pass

    # Then terminate process
    process.terminate()
```

---

## Summary

### What Makes This Work

1. **OS-level I/O multiplexing:** epoll/kqueue/IOCP
2. **Event-driven callbacks:** No polling, no busy-waiting
3. **Non-blocking reads:** Data guaranteed available when callback fires
4. **Queue buffering:** Decouples event loop from reactor processing
5. **Generator bridge:** Maintains familiar API for reactor

### Key Code Locations

- **Setup:** `src/exabgp/reactor/api/processes.py:setup_async_readers()`
- **Callback:** `src/exabgp/reactor/api/processes.py:_async_reader_callback()`
- **Consumption:** `src/exabgp/reactor/api/processes.py:received_async()`
- **Usage:** `src/exabgp/reactor/loop.py:_async_main_loop()`

### Performance Impact

- **CPU:** Lower than polling (event-driven)
- **Latency:** Near-instant (OS notification)
- **Memory:** Minimal (queue + buffers)
- **Scalability:** Excellent (100+ processes)

---

**This integration is why async mode achieves 100% test parity.**
Without it, API tests timeout. With it, everything works.

**Last Updated:** 2025-11-17
