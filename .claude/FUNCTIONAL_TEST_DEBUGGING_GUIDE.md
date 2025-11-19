# Functional Test Debugging Guide

**Purpose:** Systematic process for debugging encoding test failures using `--server` and `--client`.

---

## When to Use

- ✅ Functional encoding test fails or times out
- ✅ Need to see WHY test failed (not just that it failed)
- ✅ Want to see actual BGP messages or error output
- ✅ Investigating differences between sync and async modes

---

## Test Architecture

**How encoding tests work:**

Tests spawn TWO processes that communicate via BGP:

1. **Server** (`qa/sbin/bgp`):
   - BGP test daemon that expects specific messages
   - Compares received messages against `.msg` file
   - Reports success/failure based on exact match

2. **Client** (ExaBGP instance):
   - Runs with test configuration from `.ci` file
   - Should send exact messages server expects
   - May execute API commands from `.run` file

**Normal test run:**
```bash
./qa/bin/functional encoding T
# Spawns both, captures output, reports pass/fail only
```

**Debug run:**
```bash
# Terminal 1: ./qa/bin/functional encoding --server T
# Terminal 2: ./qa/bin/functional encoding --client T
# Shows actual output from both processes
```

---

## Step-by-Step Process

### Step 1: Identify Failing Test

```bash
# Run all tests
./qa/bin/functional encoding

# Note which fail (e.g., "T" for api-rib test)
# Or run specific test:
./qa/bin/functional encoding T
```

### Step 2: Open Two Terminals Side-by-Side

**Critical:** You MUST see both terminals simultaneously to observe the interaction.

### Step 3: Start Server (Terminal 1 - FIRST)

```bash
./qa/bin/functional encoding --server <test_id>

# Example:
./qa/bin/functional encoding --server T
```

**What to expect:**
- Prints exact server command being run
- Server starts and listens on specific port
- Shows expected messages it's waiting for
- Displays actual messages as received
- Reports "successful" or error with details

### Step 4: Start Client (Terminal 2 - SECOND)

```bash
./qa/bin/functional encoding --client <test_id>

# Example:
./qa/bin/functional encoding --client T
```

**What to expect:**
- Prints exact ExaBGP command being run
- ExaBGP connects to server on localhost
- Shows any Python exceptions or errors
- May show BGP FSM state transitions
- Exits when done (or hangs if stuck)

### Step 5: Observe Interaction

Watch BOTH terminals simultaneously:

**Success pattern:**
- Server: Shows "successful" or expected messages received
- Client: Exits cleanly without errors
- Both processes terminate

**Failure patterns - see Troubleshooting section below**

### Step 6: Enable Detailed Logging (If Needed)

If you need MORE detail than basic output provides:

**Server (already verbose):**
```bash
# Server shows expected vs actual by default
./qa/bin/functional encoding --server T
```

**Client (logging blocked by test framework):**
```bash
# Run ExaBGP manually with logging enabled

# Method 1: Check configuration file
cat qa/encoding/<test_id>.ci  # Find config file
cat etc/exabgp/<config>.conf  # See full config

# Method 2: Run manually
env exabgp_log_level=DEBUG exabgp_log_enable=true \
    ./sbin/exabgp ./etc/exabgp/<config>.conf
```

### Step 7: Decode BGP Messages (If Needed)

When server shows "unexpected message" with hex payloads, decode them to see what was actually sent:

**Server output example:**
```
unexpected message:
received    FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:0030:02:0000001540010100400200...

counting 1 valid option(s):
option 01   FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:0030:02:0000001540010100400200...
```

**Find the test configuration:**
```bash
# First, identify which config file the test uses
cat qa/encoding/<test_id>.ci

# Example for test T (api-rib):
# cat qa/encoding/api-rib.ci
# Shows: etc/exabgp/api-rib.conf
```

**Decode the received message:**
```bash
# IMPORTANT: Use the same config file as the test for accurate decoding
# This ensures capabilities (like AddPath) match what was negotiated

# Copy the hex payload from "received" line
./sbin/exabgp decode -c etc/exabgp/api-rib.conf "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:0030:02:..."

# Output shows JSON representation:
# {
#   "type": "update",
#   "neighbor": { "address": { "local": "127.0.0.1", "peer": "127.0.0.1" } },
#   "message": {
#     "update": {
#       "attribute": { "origin": "igp", "local-preference": 100 },
#       "announce": { "ipv4 unicast": { "101.1.101.1": [ { "nlri": "1.1.0.0/24" } ] } }
#     }
#   }
# }
```

**Decode the expected message:**
```bash
# Copy hex from "option 01" (expected message)
./sbin/exabgp decode -c etc/exabgp/api-rib.conf "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:0030:02:..."

# Compare JSON output with received message to find differences
```

**Why use -c (configuration file)?**
- Ensures BGP capabilities match test environment (AddPath, ASN4, etc.)
- Proper context for decoding attributes and NLRI
- Matches OPEN message negotiation from the test
- Without config, decode uses default "all families" which may differ

**Decode options:**
- `-c <config>` - Use test's configuration file (**RECOMMENDED**)
- `-f "ipv4 unicast"` - Specify address family explicitly
- `-i` or `--path-information` - Enable AddPath decoding
- `-d` or `--debug` - Verbose debug output
- Accepts hex with spaces, colons, or no separators

**Example workflow:**
```bash
# 1. Get config file
cat qa/encoding/T.ci  # Shows: etc/exabgp/api-rib.conf

# 2. Decode received message (from server output)
./sbin/exabgp decode -c etc/exabgp/api-rib.conf "<received_hex>"

# 3. Decode expected message (from server output)
./sbin/exabgp decode -c etc/exabgp/api-rib.conf "<option_01_hex>"

# 4. Compare outputs to identify encoding difference
```

### Step 8: Compare Working vs Failing (Optional)

If test worked before or works in sync mode:

```bash
# Terminal 1: Server
./qa/bin/functional encoding --server T

# Terminal 2: Client (sync mode)
./qa/bin/functional encoding --client T

# Terminal 2: Client (async mode) - compare output
env exabgp_reactor_asyncio=true ./qa/bin/functional encoding --client T
```

---

## Output Interpretation

### Success Looks Like

**Server terminal:**
```
running: /path/to/qa/sbin/bgp ...
successful
```

**Client terminal:**
```
running: /path/to/sbin/exabgp ...
[BGP session establishes]
[Messages exchanged]
[Process exits cleanly]
```

### Failure Patterns

| Server Output | Client Output | Likely Cause |
|--------------|---------------|--------------|
| Waiting... (timeout after 20s) | No errors visible | Client not sending messages → encoding bug |
| "Expected X, got Y" | No errors | Message format mismatch → encoding difference |
| No connection | "Connection refused" | Server not ready or port conflict |
| "Wrong message type" | Sends message | BGP message type mismatch |
| Server exits early | Exception/traceback | Client error prevents message send |
| Receives partial message | Hangs or loops | Incomplete message encoding |

---

## Troubleshooting

### Port Conflicts

**Symptoms:** "Address already in use" or "Connection refused"

**Solution:**
```bash
# Kill leftover test processes
killall -9 python

# Or check specific port (tests use 1790+)
lsof -i :1790
lsof -i :1791

# Kill specific process
kill -9 <PID>
```

### Test Timeouts

**Symptoms:** Test waits 20 seconds then fails with timeout

**Diagnosis:**
- Server shows "waiting for message" → Client never sent it
- Usually means encoding bug prevents message generation

**Next steps:**
- Check client terminal for Python exceptions
- Enable debug logging to see where it stops
- Compare with working test (sync mode)

### Message Format Mismatches

**Symptoms:** Server shows "unexpected message:" with hex payloads

**Diagnosis:**
- Client sends wrong message type/format
- BGP attribute or NLRI encoding difference

**Next steps:**
1. **Decode the messages** (Step 7 above) - MOST IMPORTANT:
   ```bash
   # Get config file
   cat qa/encoding/<test>.ci

   # Decode received message
   ./sbin/exabgp decode -c etc/exabgp/<config>.conf "<received_hex>"

   # Decode expected message
   ./sbin/exabgp decode -c etc/exabgp/<config>.conf "<expected_hex>"

   # Compare JSON outputs to find exact difference
   ```
2. Check expected messages in raw format: `cat qa/encoding/<test>.msg`
3. Compare sync vs async mode outputs (Step 8)
4. Use packet capture (see Advanced section below)
5. Examine message encoding code

### Connection Issues

**Symptoms:** Client can't connect to server

**Solutions:**
```bash
# Ensure server started first
# Wait 1-2 seconds before starting client

# Check firewall (localhost should work)
# Increase file descriptor limit
ulimit -n 64000
```

---

## Advanced Techniques

### Packet Capture (BGP Wire Format)

For deep protocol debugging:

```bash
# Terminal 1: Start packet capture
sudo tcpdump -i lo0 -w /tmp/test.pcap port 179 &

# Terminal 2: Run server
./qa/bin/functional encoding --server T

# Terminal 3: Run client
./qa/bin/functional encoding --client T

# Stop capture (Ctrl+C in Terminal 1)

# Analyze captured packets
tshark -r /tmp/test.pcap -V | less

# Or convert to text and compare
tshark -r /tmp/test_async.pcap -V > async.txt
tshark -r /tmp/test_sync.pcap -V > sync.txt
diff async.txt sync.txt
```

### Manual Daemon Execution

Bypass test framework for maximum control:

```bash
# Terminal 1: Run ExaBGP manually
env exabgp_log_level=DEBUG exabgp_log_enable=true \
    exabgp_reactor_asyncio=true \
    ./sbin/exabgp ./etc/exabgp/api-rib.conf

# Terminal 2: Send API commands manually (for api-* tests)
cat etc/exabgp/run/api-rib.run
# Copy commands and paste into API socket

# Terminal 3: Monitor with packet capture
sudo tcpdump -i lo0 -n port 179
```

### Examining Test Files

**Configuration (.ci file):**
```bash
cat qa/encoding/<test_id>.ci
# Shows which .conf file is used
```

**Expected messages (.msg file):**
```bash
cat qa/encoding/<test_id>.msg
# Shows exact BGP messages server expects
# Format: hex dump of wire-format BGP messages
```

**ExaBGP config (.conf file):**
```bash
cat etc/exabgp/<config>.conf
# Shows BGP neighbor config, routes to announce
```

**API commands (.run file - for api-* tests only):**
```bash
cat etc/exabgp/run/<test_id>.run
# Shows API commands sent during test
```

---

## Common Test Categories

### conf-* Tests (Configuration Tests)
- Test BGP session establishment
- Route announcements from configuration
- No runtime API commands
- Easier to debug (static configuration)

### api-* Tests (API Tests)
- Test runtime API commands
- Dynamic route announcements/withdrawals
- Require bidirectional API communication
- More complex debugging (timing-sensitive)

---

## Debugging Checklist

Before claiming test is broken:

- [ ] Ran test multiple times (rule out intermittent issues)
- [ ] Killed leftover Python processes (`killall -9 python`)
- [ ] Ran --server and --client in separate terminals
- [ ] Observed both terminals simultaneously
- [ ] Checked for Python exceptions in client
- [ ] Verified server received expected messages
- [ ] Compared with working test (sync mode if debugging async)
- [ ] Checked port availability (lsof)
- [ ] Reviewed test files (.ci, .msg, .conf)

If ALL checked and still failing:

- [ ] Captured packet trace (tcpdump)
- [ ] Enabled debug logging (manual ExaBGP run)
- [ ] Compared sync vs async wire format
- [ ] Identified exact encoding difference
- [ ] Located code responsible for message generation

---

## Quick Reference

**List all tests:**
```bash
./qa/bin/functional encoding --list           # Detailed
./qa/bin/functional encoding --short-list     # Just IDs
```

**Run specific test (both components):**
```bash
./qa/bin/functional encoding <test_id>
```

**Debug specific test (separate components):**
```bash
# Terminal 1:
./qa/bin/functional encoding --server <test_id>

# Terminal 2:
./qa/bin/functional encoding --client <test_id>
```

**Common test IDs:**
- `0-9`, `A-Z`, `a-z`, `α-κ` (72 total tests)
- Examples: `T` (api-rib), `U` (api-rr), `A` (conf-ipself6)

**Clean up:**
```bash
killall -9 python                    # Kill leftover processes
ulimit -n 64000                      # Increase FD limit
```

---

## Related Documentation

- **CLAUDE.md** - Testing requirements overview
- **CI_TESTING.md** - Pre-commit testing checklist
- **docs/projects/testing-improvements/ci-testing-guide.md** - Comprehensive CI guide
- **.claude/asyncio-migration/DEBUG_GUIDE_TESTS_T_U.md** - Example investigation

---

**Last Updated:** 2025-11-18
