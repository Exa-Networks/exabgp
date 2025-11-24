# Functional Test --edit Feature

Quick reference for inspecting functional test configurations.

## Usage

```bash
# View all files for a test using cat as editor
env EDITOR=cat ./qa/bin/functional encoding --edit <test-letter>

# Example: View test T (api-peer-lifecycle)
env EDITOR=cat ./qa/bin/functional encoding --edit T

# Example: View test D (api-fast)
env EDITOR=cat ./qa/bin/functional encoding --edit D
```

## What --edit Shows

The `--edit` flag with `EDITOR=cat` displays all components of a functional test:

1. **`.conf`** - ExaBGP configuration file
   - Defines neighbors, processes, capabilities
   - Located in `etc/exabgp/`

2. **`.ci`** - Configuration index file
   - Points to the .conf file to use
   - Located in `qa/encoding/`

3. **`.msg`** - Expected BGP messages file
   - Defines expected message sequence from ExaBGP
   - Format: `<step>:raw:<hex-encoded-bgp-message>`
   - Can include options like `option:tcp_connections:0`
   - Located in `qa/encoding/`

4. **`.run`** - API test script
   - Python script that drives the test via ExaBGP API
   - Sends commands like `announce route`, `create neighbor`
   - Located in `etc/exabgp/run/`

## Message File (.msg) Format

**Structure:**
```
# Comments start with #
option:key:value               # Test options
<step>:raw:<hex-message>       # Expected BGP messages
```

**Common options:**
- `option:tcp_connections:0` - Prevents ExaBGP exit when no initial peers configured
- `option:tcp_connections:3` - Allows 3 connection attempts before giving up

**Message format:**
- `1:raw:FFFF...` - First expected message
- `2:raw:FFFF...` - Second expected message
- Can have multiple messages per step (e.g., `A1:raw:...`, `A1:raw:...`)

**Example:**
```
option:tcp_connections:0
# EOR (End-of-RIB marker)
1:raw:FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:0017:02:00000000
# UPDATE with route 1.1.0.0/24
2:raw:FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:0030:02:0000001540010100400200400304656565654005040000006418010100
```

## Test Types

### Static Neighbor Tests
**Example: Test D (api-fast)**
- Neighbor pre-configured in .conf file
- ExaBGP connects on startup
- API script announces/withdraws routes
- Tests normal BGP message flow

### Dynamic Neighbor Tests
**Example: Test T (api-peer-lifecycle)**
- NO neighbors in .conf file
- Requires `option:tcp_connections:0` to prevent exit
- API script creates neighbor with `create neighbor` command
- Tests dynamic peer management

### Teardown/Reconnection Tests
**Example: Test Z (api-teardown)**
- Tests peer teardown and reconnection cycles
- Uses `option:tcp_connections:N` for multiple attempts
- Sends NOTIFY messages to trigger reconnection
- Tests BGP session resilience

## Listing Tests

```bash
# List all test files
./qa/bin/functional encoding --list

# List only test codes (letters)
./qa/bin/functional encoding --short-list

# Output: A B C D E F G H I J K L M N O P Q R S T U V W X Y Z ...
```

## Running Individual Tests

```bash
# Run single test
./qa/bin/functional encoding T

# Run server only (for manual client testing)
./qa/bin/functional encoding --server T --port 1819

# Run client only (for manual server testing)
./qa/bin/functional encoding --client T --port 1819
```

## Common Test Patterns

### EOR (End-of-RIB) Messages
**Hex:** `FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:0017:02:00000000`
- Marker indicating all initial routes sent
- Should be sent after session establishment
- Required for proper RIB convergence

### Test Execution Flow
1. Test harness starts server (`qa/sbin/bgp --view`)
2. Test harness starts client (ExaBGP with test config)
3. Client connects to server
4. API script (.run) sends commands to ExaBGP
5. Server validates received BGP messages against .msg expectations
6. Test passes if all expected messages received in order

## Debugging Test Failures

```bash
# Run with debug output
env exabgp_log_level=DEBUG ./qa/bin/functional encoding T

# Check what test expects
env EDITOR=cat ./qa/bin/functional encoding --edit T

# Decode BGP message hex
./sbin/exabgp decode -c <config> "<hex>"
```

## Tips

- Use `EDITOR=cat` to view without opening editor
- Use `EDITOR=vim` or `EDITOR=code` to edit test files
- Test letters are alphabetically sorted by test name
- Pre-existing tests should not be modified without good reason
- New tests should follow existing naming patterns

---

**Updated:** 2025-11-24
