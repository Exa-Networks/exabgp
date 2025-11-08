# Task 1.1 Findings: Understanding reader() Implementation

**Date**: 2025-11-08
**File Analyzed**: `/home/user/exabgp/src/exabgp/reactor/network/connection.py`
**Method**: `reader()` (lines 229-266)

---

## Questions Answered

### 1. What line validates the marker?
**Line 235**: `if not header.startswith(Message.MARKER):`

The marker validation checks if the first 16 bytes of the header start with `Message.MARKER`.

### 2. What happens if marker is invalid?
**Lines 236-238**:
```python
report = 'The packet received does not contain a BGP marker'
yield 0, 0, header, b'', NotifyError(1, 1, report)
return
```

- A NotifyError is created with error code (1, 1) - BGP Header Error / Connection Not Synchronized
- The function yields a tuple with the error and returns immediately
- The tuple format: `(length=0, msg=0, header, body=b'', error=NotifyError)`

### 3. What are min/max valid lengths?
**Lines 243-253** show two length validation checks:

**First check (line 243)**:
```python
if length < Message.HEADER_LEN or length > self.msg_size:
```
- **Minimum**: `Message.HEADER_LEN` = **19 bytes**
- **Maximum**: `self.msg_size` which is initially `ExtendedMessage.INITIAL_SIZE` = **4096 bytes**
  - Can be increased to `ExtendedMessage.EXTENDED_SIZE` = **65535 bytes** if extended message capability is negotiated

**Second check (lines 248-253)**:
```python
validator = Message.Length.get(msg, lambda _: _ >= 19)
if not validator(length):
```
- Each message type has a specific length validator
- Default validator: `lambda _: _ >= 19` (minimum 19 bytes)
- Message-type-specific validators may have different requirements

### 4. What are valid message types?
**Line 240**: `msg = header[18]`

The message type is extracted from byte 18 (0-indexed) of the header.

From `/home/user/exabgp/src/exabgp/bgp/message/message.py` (lines 15-22):
```python
class _MessageCode(int):
    NOP = 0x00           # 0 - internal use
    OPEN = 0x01          # 1
    UPDATE = 0x02        # 2
    NOTIFICATION = 0x03  # 3
    KEEPALIVE = 0x04     # 4
    ROUTE_REFRESH = 0x05 # 5
    OPERATIONAL = 0x06   # 6 - Not IANA assigned yet
```

**Valid message types**: 0-6 (though 0 is for internal use, and 6 is not IANA assigned)
**Standard BGP types**: 1-5

**Note**: The original task description mentioned "1-5" but the code actually supports 0-6.

### 5. What exception types are raised?
The `reader()` method and its helper `_reader()` can raise/yield several exceptions:

**From `reader()` (yields in tuple)**:
- **NotifyError(1, 1)** - Invalid marker (line 237)
- **NotifyError(1, 2)** - Invalid length (lines 245, 252)

**From `_reader()` (actually raises)**:
- **NotConnected** - When trying to read from closed connection (line 126)
- **LostConnection** - When TCP connection closes (lines 145, 172)
- **TooSlowError** - Socket timeout (line 158)
- **NetworkError** - Other socket errors (lines 176, 217, 223)

---

## Key Implementation Details

### Reader is a Generator Function
The `reader()` method is a **generator** that uses `yield` to return data incrementally. This is critical for testing.

**Yield signature**: `(length, msg_type, header, body, error)`
- **During reading**: yields `(0, 0, b'', b'', None)` when waiting for data
- **On error**: yields `(length, 0, header, b'', NotifyError(...))`
- **On success**: yields `(length, msg, header, body, None)`

### Data Flow
1. **Read header** (19 bytes) via `_reader(Message.HEADER_LEN)` (line 231)
2. **Validate marker** (16 bytes of 0xFF) (line 235)
3. **Extract and validate length** (2 bytes, big-endian) (lines 241, 243-253)
4. **Extract message type** (1 byte) (line 240)
5. **Read body** (length - 19 bytes) via `_reader(number)` (line 261)
6. **Return complete message** (line 265)

### Header Structure (19 bytes)
```
Bytes 0-15:  Marker (16 bytes of 0xFF)
Bytes 16-17: Length (2 bytes, big-endian unsigned short)
Byte 18:     Message Type (1 byte)
```

### Important Constants
- `Message.MARKER` = `b'\xFF' * 16` (16 bytes of 0xFF)
- `Message.HEADER_LEN` = 19
- `ExtendedMessage.INITIAL_SIZE` = 4096
- `ExtendedMessage.EXTENDED_SIZE` = 65535

---

## Testing Implications

### How to Test `reader()`
Since `reader()` is a generator, tests must:
1. Create a generator instance: `gen = connection.reader()`
2. Iterate through yields: `for result in gen:`
3. Check the yielded tuple values
4. Handle the case where multiple yields occur during reading

### Mock Requirements
To test `reader()`, we need to mock:
- The `_reader()` method (which handles actual socket I/O)
- Or create a Connection instance with proper mocking of socket operations

### Test Strategy
A helper function should be created that:
1. Creates test data (raw bytes)
2. Mocks the connection's `_reader()` to return test data
3. Calls `reader()` and collects results
4. Returns parsed header or raises exception

---

## Coverage Targets

### Code Paths to Cover
- ✓ Valid marker path (line 235 - False branch)
- ✓ Invalid marker path (lines 236-238)
- ✓ Length too small (line 243 - True branch)
- ✓ Length too large (line 243 - True branch)
- ✓ Message-specific length validation failure (lines 249-253)
- ✓ Zero-length body (lines 257-259)
- ✓ Non-zero body read (lines 261-265)

### Edge Cases
- Empty data (< 19 bytes)
- Exactly 19 bytes (minimum valid)
- 4096 bytes (maximum standard)
- 4097 bytes (one over standard maximum)
- Invalid marker (any byte != 0xFF)
- All zeros
- All ones (0xFF everywhere)

---

## Next Steps (Task 1.2+)

1. Create `/home/user/exabgp/tests/fuzz/fuzz_message_header.py`
2. Implement helper function to properly invoke `reader()` for testing
3. Add fuzzing tests for each validation path
4. Measure coverage and iterate
