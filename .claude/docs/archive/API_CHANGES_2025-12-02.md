# API Changes - 2025-12-02

**Commit**: 739a7d50

Quick reference for new API commands and methods added in this release.

---

## New API Command: queue-status

**Purpose**: Monitor write queue depth for API processes

### Text Mode

```bash
exabgpcli> queue-status
process1: 5 items (1024 bytes)
process2: 150 items (32768 bytes)
```

### JSON Mode

```bash
exabgpcli> queue-status json
{"process1": {"items": 5, "bytes": 1024}, "process2": {"items": 150, "bytes": 32768}}
```

### Via Socket

```python
import socket
import json

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect('/var/run/exabgp.sock')
sock.sendall(b'queue-status json\n')
response = json.loads(sock.recv(4096).decode())
print(response)
# {"process1": {"items": 5, "bytes": 1024}}
```

---

## New API Methods

### `write_with_backpressure()` - Async

**Location**: `reactor.processes.write_with_backpressure(process, string)`

**Purpose**: Write to API process with automatic backpressure

```python
# In async API command
async def callback():
    # Wait if queue is full (>1000 items)
    await reactor.processes.write_with_backpressure(
        service,
        json.dumps(large_data)
    )
```

**Behavior**:
- Queues normally if queue < 1000 items
- Waits and flushes if queue > 1000 items
- Resumes when queue < 100 items
- Timeout after 10 seconds

### `get_queue_size()` - Sync

**Location**: `reactor.processes.get_queue_size(process)`

**Purpose**: Get queue depth for a specific process

```python
size = reactor.processes.get_queue_size('my-process')
print(f"Queue: {size} items")
```

**Returns**: Integer (0 if no queue)

### `get_queue_stats()` - Sync

**Location**: `reactor.processes.get_queue_stats()`

**Purpose**: Get detailed queue statistics for all processes

```python
stats = reactor.processes.get_queue_stats()
# Returns: {"process1": {"items": 5, "bytes": 1024}, ...}

for process, info in stats.items():
    print(f"{process}: {info['items']} items, {info['bytes']} bytes")
```

**Returns**: Dict mapping process name to `{'items': int, 'bytes': int}`

---

## New Error Helper

### `format_api_error()` - Sync

**Location**: `from exabgp.reactor.api.error import format_api_error`

**Purpose**: Standardized error message formatting

```python
from exabgp.reactor.api.error import format_api_error

try:
    result = parse_route(command)
except ValueError as e:
    # Consistent error format
    error_msg = format_api_error('announce route', e)
    # "announce route failed: ValueError: invalid prefix"
    await reactor.processes.answer_error_async(service, error_msg)
```

**Format**: `"{command} failed: {ErrorType}: {message}"`

---

## Backpressure Configuration

### Thresholds

```python
# Default values (can be modified)
reactor.processes.WRITE_QUEUE_HIGH_WATER = 1000  # Pause threshold
reactor.processes.WRITE_QUEUE_LOW_WATER = 100     # Resume threshold
```

### Tuning Example

```python
# For high-throughput scenarios
reactor.processes.WRITE_QUEUE_HIGH_WATER = 5000
reactor.processes.WRITE_QUEUE_LOW_WATER = 500

# For memory-constrained environments
reactor.processes.WRITE_QUEUE_HIGH_WATER = 500
reactor.processes.WRITE_QUEUE_LOW_WATER = 50
```

---

## Monitoring Example

```python
#!/usr/bin/env python3
import socket
import json
import time

def check_queues():
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect('/var/run/exabgp.sock')
    sock.sendall(b'queue-status json\n')
    stats = json.loads(sock.recv(4096).decode())
    sock.close()

    for process, info in stats.items():
        if info['items'] > 100:
            print(f"⚠️ {process}: {info['items']} queued (slow)")

# Check every 5 seconds
while True:
    check_queues()
    time.sleep(5)
```

---

## Breaking Changes

**None** - All changes are backward compatible.

---

## Deprecations

### Leaf.parser and LeafList.parser

**Deprecated**: Direct use of `parser` field in schema definitions

**Replacement**: Use `validator` field instead

**Example**:
```python
# Old (emits DeprecationWarning)
leaf = Leaf(type=ValueType.COMMUNITY, parser=community_func)

# New (recommended)
leaf = Leaf(type=ValueType.COMMUNITY)  # Auto-generates validator
```

**Warning**: Will be removed in future version

---

## Full Documentation

See `.claude/docs/projects/schema-validators-api-backpressure.md` for complete details on:
- RouteDistinguisherValidator
- RouteTargetValidator
- FlagValidator
- ActionType Literal
- Migration guide
- Testing
- Troubleshooting
