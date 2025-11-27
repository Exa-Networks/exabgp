# Functional Test Debugging

Systematic debug process for encoding test failures.

---

## When to Use

- Test fails or times out
- Need to see WHY (not just that it failed)
- Investigating sync vs async differences
- Debugging intermittent failures

---

## Debugging Intermittent Failures

Use `--save` to capture run logs with timing and message hashes:

```bash
# Run test multiple times, saving logs
./qa/bin/functional encoding A --save /tmp/runs/

# Logs are saved as: /tmp/runs/<test>-<timestamp>.log
# Format:
#   [  0.222s] SESSION_START
#   [  0.222s] OPEN_RECV hash=90f464 len=55
#   [  0.223s] MSG #1 hash=7dffeb len=23 MATCH
#   ...

# Compare logs from passing vs failing runs to find:
# - Timing differences (message delays)
# - Message order differences (by hash)
# - Missing messages
```

### Stress Testing

Run a test multiple times to reproduce intermittent failures:

```bash
# Run test 10 times
./qa/bin/functional encoding A --stress 10

# Output:
# === STRESS TEST: 10 runs of test A ===
# Run   1: ✓ PASS (3.54s)
# Run   2: ✓ PASS (3.57s)
# ...
# Run   7: ✗ FAIL (20.00s)
# ...
# ==================================================
# SUMMARY
# ==================================================
# Passed: 9/10 (90.0%)
# Failed: 1 (runs 7)
#
# Timing (all runs):
#   min: 3.54s  avg: 5.18s  max: 20.00s
#   stddev: 5.12s

# Combine with --save to capture logs for analysis
./qa/bin/functional encoding A --stress 10 --save /tmp/runs/
```

---

## Debug Process

### 1. Identify Failing Test

```bash
./qa/bin/functional encoding  # Note which fail
./qa/bin/functional encoding T  # Run specific test
```

### 2. Open Two Terminals Side-by-Side

**CRITICAL:** Must see both terminals simultaneously.

### 3. Start Server (Terminal 1 - FIRST)

```bash
./qa/bin/functional encoding --server <test_id>
```

Shows: expected messages, received messages, validation result.

### 4. Start Client (Terminal 2 - SECOND)

```bash
./qa/bin/functional encoding --client <test_id>
```

Shows: ExaBGP startup, BGP session, API commands, exceptions.

### 5. Observe Both Terminals

**Success:**
- Server: "successful"
- Client: Exits cleanly

**Failure patterns - see table below**

---

## Encode/Decode BGP Messages

### Decode (hex → JSON)

When server shows "unexpected message" with hex:

```bash
# 1. Get config file
cat qa/encoding/<test>.ci  # Shows: etc/exabgp/api-rib.conf

# 2. Decode received message
./sbin/exabgp decode -c etc/exabgp/api-rib.conf "<received_hex>"

# 3. Decode expected message
./sbin/exabgp decode -c etc/exabgp/api-rib.conf "<option_01_hex>"

# 4. Compare JSON outputs to find difference

# Can also pipe from stdin:
echo "<hex>" | ./sbin/exabgp decode
cat messages.txt | ./sbin/exabgp decode  # Multiple lines
```

**CRITICAL:** Use `-c <config>` to match test's BGP capabilities.

**Decode options:**
- `-c <config>` - Use test config (RECOMMENDED)
- `-f "ipv4 unicast"` - Specify address family
- `-i` or `--path-information` - Enable AddPath
- `-d` or `--debug` - Verbose output

### Encode (route config → hex)

Generate hex UPDATE messages from route configuration:

```bash
# Basic IPv4 route
./sbin/exabgp encode "route 10.0.0.0/24 next-hop 1.2.3.4"

# With attributes
./sbin/exabgp encode "route 10.0.0.0/24 next-hop 1.2.3.4 as-path [65000 65001] community [65000:100]"

# IPv6 route
./sbin/exabgp encode -f "ipv6 unicast" "route 2001:db8::/32 next-hop 2001:db8::1"

# NLRI bytes only (no UPDATE wrapper)
./sbin/exabgp encode -n "route 10.0.0.0/24 next-hop 1.2.3.4"

# Without BGP header
./sbin/exabgp encode --no-header "route 10.0.0.0/24 next-hop 1.2.3.4"

# Round-trip verification
./sbin/exabgp encode "route 10.0.0.0/24 next-hop 1.2.3.4" | ./sbin/exabgp decode
```

**Encode options:**
- `-f <family>` - Address family (default: "ipv4 unicast")
- `-a <asn>` - Local AS (default: 65533)
- `-z <asn>` - Peer AS (default: 65533)
- `-i` - Enable add-path
- `-n` - NLRI only (no UPDATE wrapper)
- `--no-header` - Exclude 19-byte BGP header
- `-c <config>` - Use config file instead of route argument

---

## Failure Patterns

| Server | Client | Cause |
|--------|--------|-------|
| Timeout 20s | No errors | Not sending → encoding bug |
| "unexpected message" | No errors | Wrong bytes → encoding diff |
| No connection | "Connection refused" | Port conflict |
| Early exit | Traceback | Client crash |

---

## Troubleshooting

### Port Conflicts

```bash
killall -9 Python  # macOS uses capital P
lsof -i :1790      # Check specific port
```

### Test Timeouts

- Server shows "waiting" → Client never sent
- Check client for Python exceptions
- Compare with sync mode

### Message Mismatches

1. **Decode messages** (see above) - MOST IMPORTANT
2. Check: `cat qa/encoding/<test>.msg`
3. Compare sync vs async outputs

### Connection Issues

```bash
# Ensure server started first
# Wait 1-2 seconds before client
ulimit -n 64000  # Increase FD limit
```

---

## Advanced Techniques

### Packet Capture

```bash
# Terminal 1
sudo tcpdump -i lo0 -w /tmp/test.pcap port 179 &

# Terminal 2
./qa/bin/functional encoding --server T

# Terminal 3
./qa/bin/functional encoding --client T

# Analyze
tshark -r /tmp/test.pcap -V | less
```

### Manual ExaBGP Run

```bash
env exabgp_log_level=DEBUG exabgp_log_enable=true \
    ./sbin/exabgp ./etc/exabgp/api-rib.conf
```

### Examine Test Files

```bash
cat qa/encoding/<test>.ci    # Config file name
cat qa/encoding/<test>.msg   # Expected messages (hex)
cat etc/exabgp/<config>.conf # BGP neighbor setup
cat etc/exabgp/run/<test>.run  # API commands (api-* tests)
```

---

## Test Categories

**conf-* tests:** Static routes, no API, easier debug
**api-* tests:** Dynamic routes via API, timing-sensitive

---

## Debugging Checklist

Before claiming test broken:

- [ ] Ran multiple times
- [ ] Killed leftover processes (`killall -9 Python` on macOS)
- [ ] Ran --server and --client in separate terminals
- [ ] Observed both simultaneously
- [ ] Checked for exceptions in client
- [ ] Verified server received expected messages
- [ ] Compared with sync mode
- [ ] Checked port availability
- [ ] Reviewed test files (.ci, .msg, .conf)

If still failing:

- [ ] Decoded messages (compare JSON)
- [ ] Captured packet trace
- [ ] Enabled debug logging
- [ ] Located encoding code

---

## Quick Reference

```bash
# List tests
./qa/bin/functional encoding --short-list

# Run test
./qa/bin/functional encoding <test_id>

# Debug (2 terminals)
./qa/bin/functional encoding --server <test_id>
./qa/bin/functional encoding --client <test_id>

# Clean up
killall -9 Python  # macOS uses capital P
```

**Test IDs:** 0-9, A-Z, a-z, α-κ (72 total)

---

**See:** `FUNCTIONAL_TEST_ARCHITECTURE.md` for test system overview.
