# Proof of Concept Analysis - Event Loop Migration

**Created:** 2025-11-17
**Purpose:** Test both approaches before committing to implementation
**Status:** In Progress

---

## Approach A: Dual-Mode (Generators + Async Coexist)

### Concept

Add async versions of all functions alongside existing generators, controlled by a flag.

### Example Code Pattern

```python
# Current (generator)
def _reader(self, number: int) -> Iterator[bytes]:
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
            yield b''  # Need more
        except OSError as exc:
            if exc.args[0] in error.block:
                yield b''
            else:
                raise

# New (async version)
async def _reader_async(self, number: int) -> bytes:
    loop = asyncio.get_event_loop()

    # Wait for socket readable
    while not self.reading():
        await asyncio.sleep(0.001)

    data = b''
    while number > 0:
        try:
            read = await loop.sock_recv(self.io, number)
            if not read:
                raise LostConnection('Socket closed')
            data += read
            number -= len(read)
        except BlockingIOError:
            await asyncio.sleep(0.001)

    return data

# Caller chooses based on mode
def reader(self):
    if self._use_asyncio:
        return self._reader_async(number)
    else:
        return self._reader(number)
```

### Testing Strategy

1. Create minimal example with one function (connection._reader)
2. Add both versions
3. Test both modes
4. Measure complexity

---

## Approach B: Event Loop Wrapper (Hybrid)

### Concept

Keep generators for state machines, only convert I/O operations and event loop.

### Example Code Pattern

```python
# Keep generator-based state machine
def _run(self) -> Generator[int, None, None]:
    """BGP FSM - stays as generator (elegant for state machine)"""
    try:
        for action in self._establish():
            yield action

        for action in self._main():
            yield action
    except NetworkError as network:
        self._reset('closing connection', network)

# Convert only I/O layer
async def _reader_async(self, number: int) -> bytes:
    """Socket I/O - converted to async"""
    loop = asyncio.get_event_loop()
    data = b''
    while number > 0:
        read = await loop.sock_recv(self.io, number)
        if not read:
            raise LostConnection('Socket closed')
        data += read
        number -= len(read)
    return data

# Bridge: generator calls async I/O
def _reader_bridge(self, number: int) -> Iterator[bytes]:
    """Bridge from generator to async I/O"""
    # Run async I/O operation from generator context
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # Use run_in_executor or create_task
        future = asyncio.ensure_future(self._reader_async(number))
        while not future.done():
            yield b''  # Yield control while waiting
        result = future.result()
        yield result
    else:
        # Fallback to sync version
        result = loop.run_until_complete(self._reader_async(number))
        yield result
```

### Testing Strategy

1. Create minimal example with I/O operation
2. Test generator → async bridge
3. Verify state machines still work
4. Measure complexity

---

## PoC Implementation Plan

### PoC A: Dual-Mode

**Step 1:** Create test file `tests/poc/test_dual_mode.py`
- Implement simple Connection class with both modes
- Test switching between modes
- Verify both work correctly

**Step 2:** Measure complexity
- Count lines of code
- Identify maintenance burden
- Test edge cases

**Expected Time:** 1-2 hours

---

### PoC B: Event Loop Wrapper

**Step 1:** Create test file `tests/poc/test_hybrid_mode.py`
- Implement generator state machine
- Add async I/O operation
- Create bridge mechanism
- Test integration

**Step 2:** Measure complexity
- Count lines of code
- Test performance
- Identify issues

**Expected Time:** 1-2 hours

---

## Success Criteria

For each PoC:
- [ ] Code compiles and runs
- [ ] Tests pass
- [ ] Clear understanding of implementation complexity
- [ ] Identified gotchas and edge cases
- [ ] Performance acceptable
- [ ] Maintenance burden assessed

---

## Decision Matrix

After PoCs complete, evaluate:

| Criterion | Dual-Mode (A) | Hybrid (B) | Winner |
|-----------|---------------|------------|--------|
| Implementation Complexity | ? | ? | ? |
| Code Duplication | ? | ? | ? |
| Maintenance Burden | ? | ? | ? |
| Performance | ? | ? | ? |
| Risk Level | ? | ? | ? |
| Reversibility | ? | ? | ? |
| Future-Proof | ? | ? | ? |
| Elegance | ? | ? | ? |

Score each 1-5 (5 = best)

---

## Next Steps

1. ✅ Create this analysis document
2. ⏳ Implement PoC A (dual-mode)
3. ⏳ Implement PoC B (hybrid)
4. ⏳ Fill in decision matrix
5. ⏳ Make recommendation
6. ⏳ Create detailed implementation plan for chosen approach

---

**Starting PoC implementations...**
