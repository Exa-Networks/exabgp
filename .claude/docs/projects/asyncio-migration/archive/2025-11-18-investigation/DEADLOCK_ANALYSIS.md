# Async Mode Deadlock Analysis

**Status:** Root cause identified
**Date:** 2025-11-18
**Severity:** CRITICAL - Blocks 36/108 functional tests (all API tests)

## Executive Summary

The async/await implementation has a **fundamental architectural flaw** that prevents proper interleaving of API and BGP packet processing, causing all API tests to deadlock.

**Root Cause:** `Reactor._async_main_loop()` awaits peer processing before API command processing, but peer tasks block waiting for BGP messages. This prevents the event loop from ever reaching the API processing code.

**Why Generator Mode Works:** Uses `select.poll()` to monitor ALL file descriptors (peers + API) simultaneously, processing whichever becomes ready first.

**Why Async Mode Fails:** Peer tasks block in `await read_message_async()`, preventing event loop from returning to process queued API commands.

---

## The Working Generator Mode

### Control Flow (Reactor.run() - loop.py:425-639)

```python
while True:
    # 1. Handle signals
    if self.signal.received:
        # ... signal handling ...

    # 2. Check for incoming connections
    if self.listener.incoming():
        # ... spawn new peers ...

    # 3. Process active peers (round-robin)
    peers = self.active_peers()
    for key in list(peers):
        peer = self._peers[key]
        action = peer.run()  # Returns ACTION.NOW/LATER/CLOSE

        if action == ACTION.CLOSE:
            del self._peers[key]
        elif action == ACTION.LATER:
            # Register peer socket for polling
            io = peer.socket()
            self._poller.register(io, select.POLLIN | ...)
            workers[io] = key
            peers.discard(key)  # Don't process again this iteration
        elif action == ACTION.NOW:
            sleep = 0  # Process immediately next iteration

    # 4. Process API commands (CRITICAL - runs EVERY iteration)
    for service, command in self.processes.received():
        self.api.process(self, service, command)
        sleep = 0

    # 5. Register API process FDs for polling
    for fd in self.processes.fds:
        self._poller.register(fd, select.POLLIN | ...)
        api_fds.append(fd)

    # 6. Wait for I/O on ANY registered FD (peers OR API)
    for io in self._wait_for_io(sleep):  # Uses select.poll()
        if io not in api_fds:
            peers.add(workers[io])  # Re-activate peer with socket activity
        # If io IS in api_fds, next iteration processes it at step 4
```

### Key Interleaving Mechanism

**`_wait_for_io(sleeptime)` (loop.py:112-129):**

```python
def _wait_for_io(self, sleeptime: int) -> Generator[int, None, None]:
    try:
        # This monitors ALL registered FDs - both peer sockets AND API pipes
        for fd, event in self._poller.poll(sleeptime):
            if event & select.POLLIN or event & select.POLLPRI:
                yield fd  # Return ready FD
```

**Critical properties:**
1. **Monitors all FDs simultaneously** - peers AND API processes
2. **Returns immediately** when ANY FD becomes ready
3. **Yields control** between checking each ready FD
4. **Non-blocking** - returns after `sleeptime` even if no activity

**This enables true interleaving:**
- If BGP peer has data → peer socket FD returned → peer processed
- If API process has data → API pipe FD returned (implicitly) → step 4 processes it
- **Both can happen in same iteration**

---

## The Broken Async Mode

### Control Flow (Reactor._async_main_loop() - loop.py:198-293)

```python
async def _async_main_loop(self) -> None:
    while True:
        # 1. Handle signals
        if self.signal.received:
            # ... signal handling ...

        # 2. Check for incoming connections
        if self.listener.incoming():
            # ... spawn new peers ...

        # 3. Run all peers concurrently (BLOCKS HERE)
        await self._run_async_peers()  # Line 257 - THE DEADLOCK

        # 4. Process API commands (NEVER REACHED)
        for service, command in self.processes.received_async():  # Line 260
            self.api.process(self, service, command)

        # 5. Yield control
        await asyncio.sleep(0)  # Line 268
```

### The Deadlock Mechanism

**Step 3: `await self._run_async_peers()` (loop.py:162-196)**

```python
async def _run_async_peers(self) -> None:
    # Start all active peers as async tasks
    for key in self.active_peers():
        peer = self._peers[key]
        if not hasattr(peer, '_async_task') or peer._async_task is None:
            peer.start_async_task()  # Creates asyncio.Task running run_async()

    # Yield control to tasks
    await asyncio.sleep(0)  # Line 178 - yields but...

    # Check for completed peers
    # ... cleanup code ...
```

**What happens at line 178:**
1. `await asyncio.sleep(0)` yields control to event loop
2. Event loop switches to a peer task
3. Peer task runs `Peer._main_async()` (peer.py:759-908)
4. **Line 816: `message = await self.proto.read_message_async()`**
5. **This await BLOCKS** waiting for BGP data from remote peer
6. Event loop has no other peers ready, so it **stays stuck** in this task
7. Control **NEVER returns** to `_async_main_loop()` line 257
8. Line 260 (API command processing) **NEVER EXECUTES**

**Meanwhile, in the API process callback:**

```python
def _async_reader_callback(self, process_name: str) -> None:
    """Called by event loop when API process has data"""
    # ... read data from API process stdout ...

    # Line 419: Queue command for processing
    self._command_queue.append((process_name, formated(line)))
```

**The callback DOES fire** when API process sends data, but:
- Commands are queued in `_command_queue`
- But `received_async()` (line 260) **never runs** to dequeue them
- So commands pile up but are never processed

### The Blocking Chain

**In `Peer._main_async()` (peer.py:816):**

```python
while not self._teardown:
    # THIS BLOCKS INDEFINITELY waiting for BGP message
    message = await self.proto.read_message_async()

    # ... process message ...

    # Yield control
    await asyncio.sleep(0)  # Only reached AFTER message received
```

**Problem:** The `await self.proto.read_message_async()` blocks until:
1. Remote BGP peer sends a message, OR
2. Keepalive timer expires and generates synthetic message

**But for API tests:**
- Test sends API command expecting response
- ExaBGP needs to process API command to send response
- But ExaBGP is stuck waiting for BGP message at line 816
- **DEADLOCK**

---

## Why API Tests Deadlock

**API test flow:**
1. Test spawns ExaBGP with config + API process
2. ExaBGP enters `_async_main_loop()`
3. Line 257: `await self._run_async_peers()` starts peer tasks
4. Peer task blocks at line 816 waiting for BGP OPEN from remote peer
5. Test sends API command via API process stdin
6. API process receives command, writes to stdout
7. `_async_reader_callback()` fires, queues command in `_command_queue`
8. **But line 260 never runs** because still stuck at line 257
9. Test waits for API response
10. **Timeout - test fails**

**Why config tests pass:**
- Don't require runtime API command/response
- Just validate configuration parsing
- No bidirectional API communication needed

---

## The Architectural Difference

### Generator Mode: Cooperative Multitasking via select.poll()

```
┌─────────────────────────────────────────────┐
│ Reactor.run() Main Loop                     │
├─────────────────────────────────────────────┤
│ 1. Process peers (peer.run() generators)    │
│    - Yield ACTION.NOW/LATER/CLOSE           │
│    - Register sockets with poller           │
│                                             │
│ 2. Process API commands                     │
│    - processes.received() yields commands   │
│    - Register API FDs with poller           │
│                                             │
│ 3. Wait for ANY FD (peers OR API)          │
│    - _wait_for_io() uses select.poll()     │
│    - Returns when ANY FD ready              │
│    - Re-activates ready peers               │
│                                             │
│ 4. Loop back to step 1                      │
└─────────────────────────────────────────────┘

FDs Monitored: [peer1_socket, peer2_socket, api1_pipe, api2_pipe]
               ↓                           ↓
    Whoever becomes ready first is processed next
```

**Key insight:** `select.poll()` provides **true interleaving** because:
- Monitors all FDs in a single system call
- Returns the FDs that are ready
- Main loop processes whichever FD became ready
- **No blocking** - always returns after timeout

### Async Mode: Task-based with Sequential Await

```
┌─────────────────────────────────────────────┐
│ Reactor._async_main_loop()                  │
├─────────────────────────────────────────────┤
│ 1. await _run_async_peers()  ← BLOCKS HERE  │
│    │                                        │
│    ├─ Peer1 Task: await read_message()     │
│    │   └─ BLOCKED waiting for BGP data     │
│    │                                        │
│    ├─ Peer2 Task: await read_message()     │
│    │   └─ BLOCKED waiting for BGP data     │
│    │                                        │
│    └─ await asyncio.sleep(0)               │
│       └─ Yields to peer tasks (stuck)      │
│                                             │
│ 2. Process API commands  ← NEVER REACHED   │
│    - received_async() has queued commands   │
│    - But we're stuck at step 1              │
│                                             │
│ 3. await asyncio.sleep(0)  ← NEVER REACHED │
└─────────────────────────────────────────────┘

Meanwhile, in event loop callbacks:
- API reader callbacks fire and queue commands
- But main loop never dequeues them
```

**Problem:** The `await` at line 257 doesn't return until peer tasks yield, but peer tasks are blocked waiting for I/O.

---

## The Fix: Proper Event Loop Integration

### Current Broken Pattern

```python
async def _async_main_loop(self) -> None:
    while True:
        # WRONG: Sequential processing
        await self._run_async_peers()  # Blocks until peers yield

        for service, command in self.processes.received_async():  # Never reached
            self.api.process(self, service, command)
```

### Solution: Concurrent Task Management

```python
async def _async_main_loop(self) -> None:
    # Start peer tasks ONCE (not every iteration)
    for key in self.active_peers():
        peer = self._peers[key]
        peer.start_async_task()

    while True:
        # Process signals, incoming connections, etc.
        # ...

        # Process API commands (non-blocking - just dequeue)
        for service, command in self.processes.received_async():
            self.api.process(self, service, command)

        # Check for completed peers
        for key in list(self._peers.keys()):
            peer = self._peers[key]
            if hasattr(peer, '_async_task') and peer._async_task.done():
                # Handle completed peer
                del self._peers[key]

        # Yield control to peer tasks
        await asyncio.sleep(0)  # Let peer tasks run
```

**Key changes:**
1. **Don't await `_run_async_peers()`** - just manage tasks
2. **Process API commands every iteration** (non-blocking dequeue)
3. **Peer tasks run independently** in background
4. **Event loop callbacks** feed `_command_queue`
5. **Main loop** dequeues and processes commands

This restores the interleaving property:
- Peer tasks run when they have work
- API commands processed every main loop iteration
- No blocking waits in main loop

---

## Code Locations

### Blocking Call Sites

1. **`Reactor._async_main_loop()` line 257** (loop.py)
   - `await self._run_async_peers()` - blocks waiting for peers

2. **`Reactor._run_async_peers()` line 178** (loop.py)
   - `await asyncio.sleep(0)` - yields to peer tasks that block

3. **`Peer._main_async()` line 816** (peer.py)
   - `message = await self.proto.read_message_async()` - blocks waiting for BGP message

4. **`Peer.run_async()` line 1131** (peer.py)
   - `await self._run_async()` - calls `_main_async()` which blocks

### API Command Processing

1. **Generator mode** (loop.py:592-594)
   - `for service, command in self.processes.received():` - polls and yields

2. **Async mode** (loop.py:260-261)
   - `for service, command in self.processes.received_async():` - NEVER REACHED

3. **Async callback** (processes.py:419)
   - `self._command_queue.append((process_name, formated(line)))` - queues commands

4. **Async dequeue** (processes.py:461-472)
   - `received_async()` generator - dequeues from `_command_queue`

---

## Verification

**Test command:**
```bash
exabgp_reactor_asyncio=true ./qa/bin/functional encoding
```

**Expected before fix:**
- 36/108 tests timeout (all API tests)
- Deadlock at `Peer._main_async()` line 816

**Expected after fix:**
- 108/108 tests pass
- Proper interleaving of API and BGP processing

---

## Next Steps

1. **Refactor `_async_main_loop()`** to not await peers
2. **Move peer task creation** outside main loop
3. **Process API commands** every iteration (non-blocking)
4. **Verify** with functional tests
5. **Update documentation** on async/await semantics

---

**Last Updated:** 2025-11-18
**Author:** Claude Code Analysis
