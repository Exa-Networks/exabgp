# Phase 1: Event Loop Integration - Detailed Plan

**Created:** 2025-11-17
**Status:** DRAFT - Awaiting User Approval
**Risk Level:** HIGH - Architectural change affecting core event loop

---

## CRITICAL: This Plan Follows MANDATORY_REFACTORING_PROTOCOL

- ONE function at a time
- ALL tests MUST ALWAYS PASS
- PASTE proof at every step
- NO exceptions

---

## Executive Summary

**Goal:** Replace select.poll() event loop with asyncio.run()

**Scope:** ~25 generator functions across 6 files

**Estimated Time:** 10-15 hours over multiple sessions

**Risk:** HIGH - Core architecture change, affects all BGP operations

**Dependencies:** Phase 0 complete (24 API handlers converted) ✅

---

## Problem Analysis

### Current Architecture (select.poll based)

```
loop.py::run()  ← Main event loop (select.poll)
  ↓
  ├─→ peer.run() → self.generator (peer._run())
  │     ↓
  │     ├─→ _establish() → _connect(), _send_open(), _read_open()
  │     │     ↓
  │     │     └─→ protocol.connect(), protocol.read_open(), protocol.write()
  │     │           ↓
  │     │           └─→ connection.reader(), connection.writer()
  │     │                 ↓
  │     │                 └─→ io.recv(), io.send() [blocking I/O]
  │     │
  │     └─→ _main() → protocol.read_message(), protocol.new_update()
  │
  ├─→ processes.received() → external process IPC
  │
  ├─→ asynchronous.run() → execute scheduled callbacks (DONE ✅)
  │
  └─→ _wait_for_io() → select.poll().poll()
        ↓
        yields ready file descriptors
```

### Target Architecture (asyncio based)

```
async def run()  ← Main async event loop
  ↓
  await asyncio.gather(
    ├─→ async for peer in manage_peers()
    │     ↓
    │     await peer.run_async()
    │           ↓
    │           await _establish_async()
    │                 ↓
    │                 await protocol.read_open_async()
    │                       ↓
    │                       await connection.reader_async()
    │                             ↓
    │                             await loop.sock_recv()
    │
    ├─→ async for process, cmd in processes.received_async()
    │
    ├─→ asynchronous.run()  # Already supports async ✅
    │
    └─→ Built-in asyncio I/O multiplexing (no manual poll needed)
  )
```

---

## Dependency Graph

**Bottom-Up Conversion Order (leaves to root):**

```
Level 5 (Lowest - No dependencies):
  └─→ connection._reader()    ← socket read
  └─→ connection.writer()      ← socket write
  └─→ connection.reader()      ← BGP message read

Level 4:
  └─→ protocol.send()          ← uses connection.writer()
  └─→ protocol.read_message()  ← uses connection.reader()
  └─→ protocol.read_open()     ← uses connection.reader()
  └─→ protocol.read_keepalive() ← uses connection.reader()
  └─→ protocol.write()         ← uses connection.writer()
  └─→ protocol.new_* methods   ← use write()

Level 3:
  └─→ peer._send_open()        ← uses protocol.write()
  └─→ peer._read_open()        ← uses protocol.read_open()
  └─→ peer._send_ka()          ← uses protocol.new_keepalive()
  └─→ peer._read_ka()          ← uses protocol.read_keepalive()
  └─→ peer._connect()          ← uses protocol.connect()

Level 2:
  └─→ peer._establish()        ← uses _connect, _send_open, _read_open
  └─→ peer._main()             ← uses protocol.read_message, new_update
  └─→ peer._run()              ← uses _establish, _main

Level 1:
  └─→ processes.received()     ← external process I/O
  └─→ listener.new_connections() ← accept new connections
  └─→ listener._connected()    ← process accepted connections

Level 0 (Root):
  └─→ loop._wait_for_io()      ← REPLACE with asyncio I/O
  └─→ loop.run()               ← CONVERT to async def run()
```

---

## CRITICAL REALIZATION

After analyzing dependencies, **Phase 1 cannot be done incrementally** with the current approach.

### Why:

1. **loop.run() calls peer.run()** which uses generators
2. **peer.run() cannot be async** until loop.run() is async
3. **loop.run() cannot be async** until peer.run() and all callees are async
4. **Circular dependency**: Need everything converted at once

### This Violates MANDATORY_REFACTORING_PROTOCOL

"ONE FUNCTION AT A TIME" is **impossible** with circular dependencies.

---

## PROPOSED SOLUTION: Dual-Mode Bridge

Instead of converting everything at once, create a **transitional bridge**:

### Step 1: Add async versions alongside sync versions

- Keep existing generators working
- Add `_async` suffix versions that use async/await
- Both versions coexist

### Step 2: Add mode flag to control which version is used

- `self._use_asyncio = False` (default - use generators)
- When True, use async versions

### Step 3: Convert one subsystem at a time

- Start with connection (bottom of stack)
- Then protocol
- Then peer
- Then loop
- Finally remove old generator versions

### Step 4: Test at each stage

- Tests pass with `_use_asyncio = False` (generators)
- Tests pass with `_use_asyncio = True` (async)
- Both modes work

---

## ALTERNATIVE: Event Loop Wrapper (RECOMMENDED)

**Better approach:** Keep generator-based code, wrap event loop only

### Key Insight

The ASYNC class already supports both generators AND coroutines. We don't need to convert ALL generators - just the I/O layer.

### Plan:

1. **Keep peer/protocol as generators** (they work fine)
2. **Convert only I/O operations** (connection.reader/writer) to async
3. **Wrap main loop** with asyncio for I/O multiplexing
4. **Use asyncio for socket operations** while keeping generator state machines

### Benefits:

- ✅ Smaller scope (only I/O layer, not state machines)
- ✅ Can be done incrementally
- ✅ Less risk
- ✅ Generators remain for state machines (actually elegant!)
- ✅ Get asyncio benefits (stdlib integration, debugging, etc.)

---

## QUESTION FOR USER

Before I create the detailed step-by-step plan, I need your decision:

### Option A: Dual-Mode Bridge (Complex, 50+ steps)
- Convert all generators to have async equivalents
- Add mode flag
- Gradually migrate
- Eventually remove old code
- **Time:** 15-20 hours
- **Risk:** VERY HIGH
- **Reversibility:** Good (flag-based)

### Option B: Event Loop Wrapper Only (Simpler, 15-20 steps)
- Keep generators for state machines
- Convert only I/O layer (connection.py)
- Wrap loop.run() with asyncio
- Hybrid approach: generators + asyncio I/O
- **Time:** 6-8 hours
- **Risk:** HIGH (but contained)
- **Reversibility:** Good

### Option C: Abandon Full Event Loop Migration
- Keep current select.poll() architecture
- Only convert standalone async functions (like Phase 0)
- Continue with simpler utility conversions
- **Time:** 2-4 hours
- **Risk:** LOW
- **Reversibility:** N/A

### Option D: Deep Analysis First
- Spend more time analyzing trade-offs
- Create proof-of-concept for each approach
- Make data-driven decision
- **Time:** 3-4 hours planning
- **Risk:** None (planning only)

---

## My Recommendation

**Option D** followed by **Option B**

**Reasoning:**
1. This is a critical architectural decision
2. We should prototype both approaches first
3. Once we see what works, commit to one path
4. Option B (hybrid) seems most pragmatic

**Option B is likely best because:**
- Generators are actually GOOD for state machines
- We get asyncio benefits for I/O
- Smaller scope = less risk
- Matches how modern async works (async I/O, sync state)

---

## Next Steps (Pending Your Decision)

1. You choose an option (A, B, C, or D)
2. I create detailed numbered steps following MANDATORY_REFACTORING_PROTOCOL
3. You approve the plan
4. We execute ONE step at a time with full test verification

---

**Awaiting your decision...**
