# Conversion Patterns

Code examples showing generator → async/await conversions.

---

## Pattern 1: Simple Single-Yield Generator

**Use case:** Function that yields one value and returns

### Before (Generator)
```python
def get_data(self) -> Generator[bytes, None, None]:
    """Fetch data from source"""
    data = self._fetch()
    yield data
```

### After (Async)
```python
async def get_data(self) -> bytes:
    """Fetch data from source"""
    data = await self._fetch_async()
    return data
```

**Changes:**
- Remove `Generator` type hint
- Replace `yield` with `return`
- Add `async` keyword
- Add `await` for async calls

---

## Pattern 2: Loop-Based Generator (Iteration)

**Use case:** Generator that yields multiple values in loop

### Before (Generator)
```python
def wait_for_io(self, sleep: int) -> Generator[int, None, None]:
    """Yield file descriptors ready for I/O"""
    for fd, event in self._poller.poll(sleep):
        if event & select.POLLIN:
            yield fd
```

### After (Async Generator)
```python
async def wait_for_io(self, sleep: int) -> AsyncGenerator[int, None]:
    """Yield file descriptors ready for I/O"""
    for fd, event in self._poller.poll(sleep):
        if event & select.POLLIN:
            yield fd  # Keep yield for async generator
```

**OR (if converting to single return):**
```python
async def wait_for_io(self, sleep: int) -> list[int]:
    """Return file descriptors ready for I/O"""
    ready_fds = []
    for fd, event in self._poller.poll(sleep):
        if event & select.POLLIN:
            ready_fds.append(fd)
    return ready_fds
```

**Changes:**
- Add `async` keyword
- Keep `yield` if still iterating (becomes async generator)
- OR accumulate and `return` list if single result needed
- Import `AsyncGenerator` from typing

---

## Pattern 3: Generator Chain (for-yield)

**Use case:** Generator that yields from another generator

### Before (Generator)
```python
def read_message(self) -> Generator[Message, None, None]:
    """Read BGP message from network"""
    for length, msg_id, header, body in self.connection.reader():
        if not length:
            yield _NOP
            continue
        message = Message.unpack(msg_id, body)
        yield message
```

### After (Async)
```python
async def read_message(self) -> Message:
    """Read BGP message from network"""
    async for length, msg_id, header, body in self.connection.reader():
        if not length:
            return _NOP
        message = Message.unpack(msg_id, body)
        return message
```

**Changes:**
- `for ... in gen()` → `async for ... in gen()`
- `yield` → `return` (if single value expected)
- Called generator must also be async

---

## Pattern 4: Socket I/O with Blocking

**Use case:** Read/write with EAGAIN/EWOULDBLOCK handling

### Before (Generator)
```python
def _reader(self, number: int) -> Iterator[bytes]:
    """Read exactly 'number' bytes from socket"""
    while not self.reading():
        yield b''  # Wait for readable

    data = b''
    while True:
        try:
            read = self.io.recv(number)
            data += read
            number -= len(read)

            if not number:
                yield data
                return

            yield b''  # Need more data
        except OSError as exc:
            if exc.args[0] in error.block:
                yield b''  # EAGAIN
            else:
                raise
```

### After (Async with asyncio)
```python
async def _reader(self, number: int) -> bytes:
    """Read exactly 'number' bytes from socket"""
    # Wait for socket to be readable
    while not self.reading():
        await asyncio.sleep(0.001)

    data = b''
    while number > 0:
        try:
            # Use asyncio socket operations
            read = await self.loop.sock_recv(self.io, number)
            if not read:
                raise LostConnection('Socket closed')

            data += read
            number -= len(read)
        except BlockingIOError:
            await asyncio.sleep(0.001)
        except OSError:
            raise

    return data
```

**Changes:**
- `yield b''` → `await asyncio.sleep(0.001)` (cooperative yield)
- `io.recv()` → `await loop.sock_recv()`
- Remove multiple yields, single return
- Simplified logic (no yield-based state machine)

---

## Pattern 5: Socket Write

**Use case:** Write data to socket, handling partial writes

### Before (Generator)
```python
def writer(self, data: bytes) -> Iterator[bool]:
    """Write data to socket"""
    while not self.writing():
        yield False  # Wait for writable

    while data:
        try:
            sent = self.io.send(data)
            data = data[sent:]
            yield False if data else True
        except OSError as exc:
            if exc.args[0] in error.block:
                yield False
            else:
                raise
```

### After (Async)
```python
async def writer(self, data: bytes) -> None:
    """Write data to socket"""
    # Wait for socket to be writable
    while not self.writing():
        await asyncio.sleep(0.001)

    while data:
        try:
            sent = await self.loop.sock_sendall(self.io, data)
            return  # sock_sendall sends all or raises
        except BlockingIOError:
            await asyncio.sleep(0.001)
        except OSError:
            raise
```

**Changes:**
- `yield False/True` → just return when done
- `await asyncio.sleep(0.001)` for yielding control
- Can use `sock_sendall()` which handles partial writes
- Simpler control flow

---

## Pattern 6: Nested Generator (API Commands)

**Use case:** Outer function schedules inner generator

### Before (Nested Generator)
```python
@Command.register('announce route')
def announce_route(self, reactor, service, line, use_json):
    """API command handler"""

    def callback():  # Inner generator
        try:
            peers = match_neighbors(reactor, service, line)
            if not peers:
                reactor.processes.answer_error(service)
                yield True  # Error
                return

            changes = self.parse_route(line)
            for change in changes:
                reactor.inject_change(peers, change)
                yield False  # Continue

            reactor.processes.answer_done(service)
        except Exception:
            reactor.processes.answer_error(service)
            yield True  # Error

    # Schedule inner generator
    reactor.asynchronous.schedule(service, line, callback())
    return True
```

### After (Direct Async)
```python
@Command.register('announce route')
async def announce_route(self, reactor, service, line, use_json):
    """API command handler"""
    try:
        peers = match_neighbors(reactor, service, line)
        if not peers:
            reactor.processes.answer_error(service)
            return

        changes = self.parse_route(line)
        for change in changes:
            reactor.inject_change(peers, change)
            await asyncio.sleep(0)  # Yield control

        reactor.processes.answer_done(service)
    except Exception:
        reactor.processes.answer_error(service)
```

**Changes:**
- Remove inner `callback()` function - flatten to single async function
- Remove `reactor.asynchronous.schedule()` call
- Remove `yield True/False` control flow
- Add `await asyncio.sleep(0)` in loops to yield control
- Function directly called as coroutine
- Errors handled with try/except, not yield True

---

## Pattern 7: State Machine with Yields

**Use case:** Function that yields at state transitions

### Before (Generator)
```python
def _connect(self) -> Generator[int, None, None]:
    """Establish BGP connection"""
    # Create connection
    self.proto = Protocol(self).connect()

    # Send OPEN
    for sent in self._send_open():
        yield sent

    # Read OPEN response
    for received in self._read_open():
        yield received

    # Transition state
    self.fsm = FSM.ESTABLISHED
    yield ACTION.LATER
```

### After (Async)
```python
async def _connect(self) -> int:
    """Establish BGP connection"""
    # Create connection
    self.proto = Protocol(self).connect()

    # Send OPEN
    await self._send_open()

    # Read OPEN response
    await self._read_open()

    # Transition state
    self.fsm = FSM.ESTABLISHED
    return ACTION.LATER
```

**Changes:**
- `for x in gen(): yield x` → `await async_func()`
- Final `yield` → `return`
- Callees must also be async

---

## Pattern 8: Error Handling with Yields

**Use case:** Generator that yields errors vs. success

### Before (Generator)
```python
def process_command(self) -> Generator[bool, None, None]:
    """Process command, yield True on error"""
    try:
        data = self.parse()
        if not data:
            yield True  # Error
            return

        result = self.execute(data)
        yield False  # Success
    except Exception:
        yield True  # Error
```

### After (Async)
```python
async def process_command(self) -> None:
    """Process command, raise on error"""
    data = self.parse()
    if not data:
        raise ValueError("Parse failed")

    result = await self.execute(data)
    # Implicit success (no exception)
```

**OR (if bool return needed):**
```python
async def process_command(self) -> bool:
    """Process command, return success status"""
    try:
        data = self.parse()
        if not data:
            return False

        result = await self.execute(data)
        return True
    except Exception:
        return False
```

**Changes:**
- `yield True` (error) → `raise Exception` or `return False`
- `yield False` (success) → `return True` or just return
- More Pythonic error handling

---

## Type Hints Reference

```python
from typing import Generator, AsyncGenerator, Iterator
import asyncio

# Old (Generator)
def func() -> Generator[int, None, None]:
    yield 42

def func2() -> Iterator[str]:
    yield "hello"

# New (Async)
async def func() -> int:
    return 42

async def func2() -> str:
    return "hello"

# New (Async Generator - still yields)
async def func3() -> AsyncGenerator[int, None]:
    for i in range(10):
        yield i
```

---

## Common Gotchas

### 1. Forgetting `await`
```python
# ❌ WRONG
async def foo():
    result = bar()  # Missing await!

# ✅ CORRECT
async def foo():
    result = await bar()
```

### 2. Mixing sync and async
```python
# ❌ WRONG - can't await sync function
async def foo():
    result = await sync_function()

# ✅ CORRECT
async def foo():
    result = sync_function()  # No await for sync
```

### 3. Not converting entire call chain
```python
# ❌ WRONG - caller still expects generator
async def reader():
    return data

def protocol():
    for data in self.reader():  # Breaks! reader is now async
        yield data

# ✅ CORRECT - convert caller too
async def reader():
    return data

async def protocol():
    data = await self.reader()
    return data
```

---

## Quick Reference

| Old Pattern | New Pattern |
|-------------|-------------|
| `yield value` | `return value` |
| `yield` (no value) | `await asyncio.sleep(0)` |
| `for x in gen():` | `async for x in gen():` |
| `def func():` | `async def func():` |
| `Generator[T, None, None]` | `T` (return type) |
| `yield True/False` | `return True/False` or raise |
| `next(generator)` | `await coroutine` |

---

**Updated:** 2025-11-16
