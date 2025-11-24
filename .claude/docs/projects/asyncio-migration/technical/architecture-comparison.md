# Current Async Architecture

ExaBGP uses custom generator-based async built before Python's asyncio.

---

## Core: ASYNC Scheduler

**File:** `src/exabgp/reactor/asynchronous.py`

**Status:** ✅ Updated in Phase 1.1 - supports both generators AND coroutines

```python
class ASYNC:
    def schedule(self, uid: str, command: str, callback: Any) -> None:
        """Schedule generator or coroutine for execution"""
        self._async.append((uid, callback))

    async def _run_async(self) -> bool:
        """Execute scheduled callbacks - handles both modes"""
        uid, callback = self._async.popleft()

        for _ in range(self.LIMIT):
            try:
                if inspect.isgenerator(callback):
                    next(callback)  # Old style
                elif inspect.iscoroutine(callback):
                    await callback  # New style
                else:
                    next(callback)
            except StopIteration:
                # Move to next callback
                pass
```

**Key features:**
- Dual-mode: generators + coroutines
- Round-robin scheduling via deque
- Batch processing (50 iterations/cycle)
- Error isolation

---

## Hierarchy (5 Levels)

### Level 1: Main Event Loop
**File:** `src/exabgp/reactor/loop.py` (1 generator)

```python
def run(self) -> int:
    while True:
        # 1. Check signals
        # 2. Check incoming connections
        # 3. Run each peer
        for key in peers:
            peer.run()
        # 4. Process API commands
        # 5. RUN ASYNC SCHEDULER ← critical
        self.asynchronous.run()
        # 6. Wait for I/O
        for fd in self._wait_for_io(sleep):
            # Handle ready sockets
```

### Level 2: Peer State Machine
**File:** `src/exabgp/reactor/peer.py` (9 generators)

BGP FSM: IDLE → ACTIVE → CONNECT → OPENSENT → OPENCONFIRM → ESTABLISHED

```python
def _connect(self) -> Generator[int, None, None]:
    """Establish BGP connection"""
    self.proto = Protocol(self).connect()
    for sent_open in self._send_open():
        yield sent_open
    for received_open in self._read_open():
        yield received_open
    self.fsm = FSM.ESTABLISHED
    yield ACTION.LATER
```

### Level 3: Protocol Handler
**File:** `src/exabgp/reactor/protocol.py` (14 generators)

```python
def read_message(self) -> Generator[Union[Message, NOP], None, None]:
    """Read and parse BGP messages"""
    for length, msg_id, header, body, notify in self.connection.reader():
        if not length:
            yield _NOP
            continue
        message = Message.unpack(msg_id, body, self.negotiated)
        yield message
```

### Level 4: Network I/O
**File:** `src/exabgp/reactor/network/connection.py` (3 generators)

```python
def _reader(self, number: int) -> Iterator[bytes]:
    """Read exactly 'number' bytes from socket"""
    while not self.reading():
        yield b''  # Wait for readable

    data = b''
    while True:
        read = self.io.recv(number)
        data += read
        number -= len(read)
        if not number:
            yield data
            return
        yield b''  # Need more
```

### Level 5: API Command Handlers
**File:** `src/exabgp/reactor/api/command/announce.py` (30 generators)

```python
@Command.register('announce route')
def announce_route(self, reactor, service, line, use_json):
    def callback():  # Nested generator
        try:
            peers = match_neighbors(...)
            changes = self.api_route(command)
            for change in changes:
                reactor.configuration.inject_change(peers, change)
                yield False  # Continue
            reactor.processes.answer_done(service)
        except ValueError:
            reactor.processes.answer_error(service)
            yield True  # Error

    reactor.asynchronous.schedule(service, line, callback())
    return True
```

---

## Data Flow Through `yield`

### Type 1: Control Flow (API)
```python
yield False  # Continue
yield True   # Stop/error
```

### Type 2: Messages (Protocol)
```python
yield Message   # Parsed BGP message
yield _NOP      # Empty message
```

### Type 3: Binary Data (Network)
```python
yield b''     # Not ready
yield bytes   # Data chunk
```

### Type 4: Status (Network)
```python
yield False   # Write incomplete
yield True    # Write complete
```

### Type 5: File Descriptors (Event Loop)
```python
yield fd      # Socket ready (int)
```

---

## Complete Data Flow Example

```
1. API Command: "announce route neighbor 192.0.2.1 10.0.0.0/8"
   ↓
2. announce_route() creates nested generator callback
   ↓
3. reactor.asynchronous.schedule(uid, command, generator)
   ↓
4. Main loop calls asynchronous.run()
   ↓
5. next(generator) - Parse command, inject route
   ↓
6. yield False - Continue processing
   ↓
7. next(generator) - More work
   ↓
8. StopIteration - Generator complete

Meanwhile, in parallel:

1. Peer.run() called by main loop
   ↓
2. for action in self._connect(): # Generator
   ↓
3. Protocol.connect() creates TCP socket
   ↓
4. for msg in self._send_open(): # Generator
   ↓
5. for boolean in proto.write(open_msg): # Generator
   ↓
6. for boolean in connection.writer(raw): # Generator
   ↓
7. io.send(data) - Socket write
   ↓
8. yield False - Not done yet
   ↓
9. Main loop registers socket in poller
   ↓
10. Socket becomes writable
   ↓
11. _wait_for_io() yields fd
   ↓
12. Peer.run() called again
   ↓
13. next(generator) resumes write
   ↓
14. yield True - Write complete
```

---

## Why Generators Were Used

**Historical:** ExaBGP started 2009, asyncio added Python 3.4 (2014)

**Benefits:**
- Lightweight cooperative multitasking
- Manual scheduling control
- Simple implementation (~125 lines)
- No dependencies

**Drawbacks:**
- Non-standard pattern
- Can't use async libraries
- Limited tooling support
- Harder for new contributors

---

## Current State

**Phase 1.1: COMPLETE** ✅
- ASYNC class updated
- Supports both generators and coroutines
- All 1376 tests passing
- Backward compatible

**Next:** Convert simple generators to async/await

---

**Updated:** 2025-11-16
