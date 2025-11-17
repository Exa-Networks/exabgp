# Phase 2: PoC Integration Plan - Real Component Testing

**Created:** 2025-11-17
**Status:** ACTIVE
**Approach:** Test hybrid async/generator integration with real ExaBGP components
**Risk Level:** MEDIUM (PoC only, not production code)

---

## Objectives

Create a realistic proof-of-concept that:

1. ✅ Uses REAL ExaBGP components (Connection, Protocol, Peer)
2. ✅ Tests async I/O with actual BGP message encoding/decoding
3. ✅ Validates generator→async bridge pattern works in practice
4. ✅ Measures performance vs current implementation
5. ✅ Identifies integration issues BEFORE committing to full migration

---

## PoC Scope

### What We'll Build

**File:** `tests/integration_poc_async_eventloop.py`

A complete integration test that:
- Creates real TCP sockets (loopback)
- Uses actual BGP message classes (Open, Update, KeepAlive)
- Implements hybrid event loop with real Connection/Protocol objects
- Runs both sync and async modes side-by-side
- Compares performance and correctness

### What We'll Test

1. **Socket I/O** - Real TCP connection with async operations
2. **BGP Protocol** - Actual message encoding/decoding
3. **State Machine** - Generator-based FSM with async I/O bridge
4. **Event Loop** - Hybrid asyncio integration
5. **Error Handling** - Connection failures, timeouts, etc.

### What We WON'T Change

- ❌ No changes to production code (src/)
- ❌ No modification of existing tests
- ✅ Only create NEW test file
- ✅ Self-contained PoC

---

## Implementation Plan

### Step 1: Create Integration PoC Structure

**File:** `tests/integration_poc_async_eventloop.py`

**Components:**
```python
# 1. Import REAL ExaBGP components
from exabgp.reactor.network.connection import Connection
from exabgp.bgp.message import Message, Open, KeepAlive, Update
from exabgp.protocol.ip import IP

# 2. Create hybrid event loop class
class HybridEventLoop:
    """Event loop supporting both generator and async I/O"""

    async def run_async(self):
        """Main async event loop"""
        pass

    def run_sync(self):
        """Original generator-based event loop"""
        pass

# 3. Create BGP peer simulation
class MockPeer:
    """Simulates BGP peer using real Connection object"""

    def __init__(self, connection):
        self.connection = connection

    def run_generator(self):
        """Generator-based state machine (current approach)"""
        yield "IDLE"
        yield "CONNECT"
        # ... FSM states

    async def run_async_hybrid(self):
        """Hybrid: generator FSM + async I/O"""
        for state in self.run_generator():
            if state == "READ_OPEN":
                msg = await self.connection.reader_async()
                # Process message
            yield state

# 4. Test harness
def test_sync_vs_async():
    """Compare sync and async implementations"""
    # Run both modes
    # Compare results
    # Measure performance
```

**Verification:**
```bash
ruff format tests/integration_poc_async_eventloop.py
ruff check tests/integration_poc_async_eventloop.py
python3 tests/integration_poc_async_eventloop.py
```

**Expected:** File created, imports work, structure is valid

---

### Step 2: Implement Sync (Baseline) Version

**Action:** Create working sync version using current approach

**Code:**
```python
def test_sync_bgp_connection():
    """Baseline: Current generator-based approach"""

    # Create server socket
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(('127.0.0.1', 0))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    # Create client connection using real Connection class
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_sock.connect(('127.0.0.1', port))

    # Accept server connection
    server_conn_sock, _ = server_sock.accept()

    # Create Connection objects (REAL ExaBGP classes)
    client_conn = Connection(client_sock, '127.0.0.1', port, ...)
    server_conn = Connection(server_conn_sock, '127.0.0.1', port, ...)

    # Test current generator-based I/O
    # Send BGP Open message
    # Read BGP Open message
    # Verify correctness

    return timing_data
```

**Verification:**
```bash
python3 tests/integration_poc_async_eventloop.py --test sync
```

**Expected:**
- BGP messages exchanged successfully
- Baseline performance data collected

---

### Step 3: Implement Async (Hybrid) Version

**Action:** Create async version using new async methods

**Code:**
```python
async def test_async_bgp_connection():
    """Hybrid: Generator FSM + async I/O"""

    # Same socket setup
    # ...

    # Create Connection objects (same as sync)
    client_conn = Connection(client_sock, '127.0.0.1', port, ...)
    server_conn = Connection(server_conn_sock, '127.0.0.1', port, ...)

    # Use NEW async methods from Phase 1
    # Send BGP Open message using writer_async()
    await client_conn.writer_async(open_msg.message())

    # Read BGP Open message using reader_async()
    length, msg_type, header, body, error = await server_conn.reader_async()

    # Verify correctness

    return timing_data
```

**Verification:**
```bash
python3 tests/integration_poc_async_eventloop.py --test async
```

**Expected:**
- BGP messages exchanged successfully using async I/O
- Performance data collected
- Compare with sync baseline

---

### Step 4: Test Generator→Async Bridge

**Action:** Verify generators can call async I/O

**Code:**
```python
def generator_fsm_with_async_io(connection):
    """Generator-based FSM calling async I/O"""

    # State 1: IDLE
    yield "IDLE"

    # State 2: CONNECT
    yield "CONNECT"

    # State 3: SEND_OPEN
    # Need to bridge from generator to async
    open_msg = Open(...)

    # Create async task
    loop = asyncio.get_event_loop()
    task = asyncio.create_task(
        connection.writer_async(open_msg.message())
    )

    # Yield while waiting
    while not task.done():
        yield "WRITING"

    if task.exception():
        raise task.exception()

    yield "OPENSENT"

    # State 4: READ_OPEN
    task = asyncio.create_task(
        connection.reader_async()
    )

    while not task.done():
        yield "READING"

    result = task.result()
    yield "OPENCONFIRM"

    # ... more states
```

**Verification:**
```bash
python3 tests/integration_poc_async_eventloop.py --test bridge
```

**Expected:**
- Generator successfully calls async I/O
- State machine progresses correctly
- No deadlocks or race conditions

---

### Step 5: Test with Real BGP Messages

**Action:** Use actual BGP message encoding/decoding

**Test Cases:**
1. **Open message exchange**
   - Client sends Open
   - Server receives Open
   - Server sends Open
   - Client receives Open

2. **KeepAlive exchange**
   - Bidirectional KeepAlive

3. **Update message**
   - Send route announcement
   - Parse NLRI, attributes
   - Verify encoding/decoding

4. **Error handling**
   - Connection timeout
   - Invalid message
   - Connection reset

**Verification:**
```bash
python3 tests/integration_poc_async_eventloop.py --test messages
```

**Expected:**
- All message types work correctly
- Encoding/decoding identical to current implementation
- Error handling works

---

### Step 6: Performance Benchmarking

**Metrics to Collect:**

1. **Throughput**
   - Messages per second (sync vs async)
   - Bytes per second

2. **Latency**
   - Time to send message
   - Time to receive message
   - Round-trip time

3. **CPU Usage**
   - CPU time (sync vs async)
   - System calls

4. **Memory**
   - Memory usage
   - Object allocations

**Benchmark Code:**
```python
def benchmark():
    """Compare sync vs async performance"""

    # Test 1: Send 1000 Update messages
    sync_time = benchmark_sync(num_messages=1000)
    async_time = benchmark_async(num_messages=1000)

    # Test 2: Concurrent connections
    sync_time_multi = benchmark_sync(num_peers=10)
    async_time_multi = benchmark_async(num_peers=10)

    # Test 3: Large messages
    sync_time_large = benchmark_sync(message_size=4096)
    async_time_large = benchmark_async(message_size=4096)

    # Generate report
    print_comparison(sync_time, async_time)
```

**Verification:**
```bash
python3 tests/integration_poc_async_eventloop.py --benchmark
```

**Expected:**
- Performance data for both approaches
- Clear comparison metrics
- Identify which approach is faster (if any difference)

---

### Step 7: Integration with Real Configuration

**Action:** Test with actual ExaBGP configuration file

**Test:**
```python
def test_with_real_config():
    """Load real BGP configuration and test"""

    # Use existing test configuration
    config_file = './etc/exabgp/conf-ipself6.conf'

    # Parse configuration
    from exabgp.configuration.configuration import Configuration
    config = Configuration([config_file])

    # Extract neighbor config
    neighbor = list(config.neighbors.values())[0]

    # Create connection with real config params
    connection = create_connection_from_config(neighbor)

    # Test async I/O with real parameters
    # ...
```

**Verification:**
```bash
python3 tests/integration_poc_async_eventloop.py --config ./etc/exabgp/conf-ipself6.conf
```

**Expected:**
- Works with real configuration
- All parameters respected
- No configuration compatibility issues

---

### Step 8: Stress Testing

**Tests:**

1. **Connection churn**
   - Rapid connect/disconnect cycles
   - Memory leak detection

2. **Message flood**
   - Send 10,000+ messages rapidly
   - Verify no message loss

3. **Concurrent peers**
   - Simulate 50+ concurrent BGP sessions
   - Check scalability

4. **Error conditions**
   - Network errors
   - Malformed messages
   - Resource exhaustion

**Verification:**
```bash
python3 tests/integration_poc_async_eventloop.py --stress
```

**Expected:**
- No crashes
- No memory leaks
- Graceful error handling
- Performance remains stable

---

## Success Criteria

The PoC is successful if:

### Functional Requirements
- ✅ All BGP message types work correctly
- ✅ Generator→async bridge functions properly
- ✅ No deadlocks or race conditions
- ✅ Error handling equivalent to current implementation
- ✅ Works with real ExaBGP configuration

### Performance Requirements
- ✅ Async is **at least as fast** as sync (no regression)
- ✅ Memory usage comparable (±10%)
- ✅ CPU usage comparable (±10%)
- ✅ Scalability equal or better

### Code Quality Requirements
- ✅ Bridge pattern is clean and maintainable
- ✅ No complex hacks or workarounds
- ✅ Clear path to production integration
- ✅ Well-documented approach

---

## Go/No-Go Decision Criteria

### Proceed with Phase 2 Integration IF:

1. ✅ **All functional tests pass**
2. ✅ **Performance is equal or better**
3. ✅ **Code complexity is acceptable**
4. ✅ **No blocking issues discovered**
5. ✅ **Clear benefit identified** (performance, maintainability, or features)

### STOP if:

1. ❌ Functional tests fail
2. ❌ Performance regression >10%
3. ❌ Code becomes too complex/hacky
4. ❌ Blocking issues discovered
5. ❌ No clear benefit over current approach

---

## Implementation Timeline

**Step 1:** Structure setup - 1 hour
**Step 2:** Sync baseline - 2 hours
**Step 3:** Async implementation - 2 hours
**Step 4:** Bridge testing - 1 hour
**Step 5:** Message testing - 2 hours
**Step 6:** Performance benchmarking - 2 hours
**Step 7:** Config integration - 1 hour
**Step 8:** Stress testing - 2 hours

**Total: 13 hours**

---

## Next Steps

### Immediate Actions:

1. Create `tests/integration_poc_async_eventloop.py`
2. Import real ExaBGP components
3. Build sync baseline version
4. Implement async version
5. Run tests and collect data

### After PoC Completion:

**If GO:**
- Create detailed Phase 2 integration plan (30-40 steps)
- Follow MANDATORY_REFACTORING_PROTOCOL
- Incremental migration with full testing

**If NO-GO:**
- Document findings
- Keep Phase 1 infrastructure
- Focus on other improvements
- Revisit later if needs change

---

## Risk Mitigation

**PoC Risks:**
- ⚠️ May discover integration blockers
  - *Mitigation:* That's the point - find issues early!

- ⚠️ Performance may be worse
  - *Mitigation:* Know this BEFORE wasting 30+ hours

- ⚠️ Code complexity may be high
  - *Mitigation:* Decide not to proceed if too complex

**All risks are CONTAINED to PoC - no production code affected.**

---

## Approval to Proceed

Ready to start PoC implementation?

- [ ] Yes - Begin Step 1 (structure setup)
- [ ] Questions - Need clarification
- [ ] Modify plan - Suggest changes

---

**Awaiting approval to begin PoC integration testing...**
