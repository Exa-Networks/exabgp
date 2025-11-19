# Quick Debug Guide: Tests T & U

**For future investigators who want to fix tests T & U**

---

## Quick Facts

- **Current Status:** 97.2% pass rate (70/72 tests)
- **Failing:** Test T (api-rib), Test U (api-rr)
- **Architecture:** ✅ VALIDATED - All patterns work in isolation
- **Likely Cause:** BGP message encoding differences

---

## What We Already Know Works

✅ RIB state synchronization
✅ Concurrent API callbacks + peer tasks
✅ Multiple flush commands
✅ Generator consumption
✅ Async scheduler
✅ Event loop coordination

**See:** `tests/async_debug/test_rib_updates_realworld.py` - ALL PASS

---

## What We DON'T Know

❌ Why actual test T fails when mock test passes
❌ Difference between real vs mock BGP message encoding
❌ Test daemon's exact expectations

---

## Fastest Path to Fix

### Step 1: Capture BGP Messages

```bash
# Terminal 1: Start daemon with packet capture
tcpdump -i lo0 -w /tmp/test_t_async.pcap port 179 &
env exabgp_reactor_asyncio=true ./sbin/exabgp ./etc/exabgp/api-rib.conf

# Terminal 2: Same for sync mode
tcpdump -i lo0 -w /tmp/test_t_sync.pcap port 179 &
./sbin/exabgp ./etc/exabgp/api-rib.conf
```

### Step 2: Compare Wire Format

```bash
# Convert to text
tshark -r /tmp/test_t_async.pcap -V > async_packets.txt
tshark -r /tmp/test_t_sync.pcap -V > sync_packets.txt

# Compare UPDATE messages
diff async_packets.txt sync_packets.txt
```

### Step 3: Look for Differences in:

- Message ordering
- Attribute encoding
- NLRI format
- Path attributes when route from `_refresh_changes` vs `_new_nlri`

---

## Alternative Approach: Manual Test

Create standalone test without framework:

```python
#!/usr/bin/env python3
"""
Standalone test for flush operations
Run ExaBGP manually, send commands, observe behavior
"""
import socket
import time
import subprocess

# Start ExaBGP daemon
daemon = subprocess.Popen([
    'env', 'exabgp_log_level=DEBUG', 'exabgp_reactor_asyncio=true',
    './sbin/exabgp', './etc/exabgp/api-rib.conf'
])

time.sleep(2)

# Connect to API
# Send commands
# Observe full logging output

daemon.terminate()
```

---

## Logging Infrastructure

All logging is in place but blocked by test framework:

**Files with debug logging:**
- `src/exabgp/rib/outgoing.py` - RIB operations
- `src/exabgp/reactor/protocol.py` - Message sending
- `src/exabgp/reactor/asynchronous.py` - Scheduler
- `src/exabgp/reactor/api/command/rib.py` - Command handlers
- `src/exabgp/reactor/peer.py` - Peer loop

**To enable:**
```bash
# Won't work in test framework:
env exabgp_log_enable=true exabgp_log_level=DEBUG

# Must run daemon manually:
env exabgp_log_level=DEBUG exabgp_reactor_asyncio=true \
    ./sbin/exabgp ./etc/exabgp/api-rib.conf
```

---

## Key Code Locations

### Where flush is called

**File:** `src/exabgp/reactor/api/command/rib.py:148-176`
```python
@Command.register('flush adj-rib out')
def flush_adj_rib_out(self, reactor, service, line, use_json):
    async def callback(self, peers):
        for peer_name in peers:
            reactor.neighbor_rib_resend(peer_name)  # ← KEY CALL
```

### Where routes are cached

**File:** `src/exabgp/rib/cache.py:75-84`
```python
def update_cache(self, change: Change) -> None:
    if not self.cache:
        return  # ← If cache disabled, flush won't work!
    family = change.nlri.family().afi_safi()
    index = change.index()
    if change.nlri.action == Action.ANNOUNCE:
        self._seen.setdefault(family, {})[index] = change  # ← Stored here
```

### Where flush retrieves cached routes

**File:** `src/exabgp/rib/outgoing.py:89-108`
```python
def resend(self, enhanced_refresh: bool, family=None):
    for change in self.cached_changes(list(requested_families)):
        self._refresh_changes.append(change)  # ← Copied here
```

### Where cached routes are sent

**File:** `src/exabgp/rib/outgoing.py:276-280`
```python
def updates(self, grouped: bool):
    # ...
    for change in self._refresh_changes:
        yield Update([change.nlri], change.attributes)  # ← Sent here
    self._refresh_changes = []
```

---

## Check These Potential Issues

### 1. Cache Not Populated

**Verify:** Routes are being cached when announced

```python
# In update_cache():
if not self.cache:
    return  # ← Routes won't be cached!
```

**Test:** Add logging to confirm `self.cache == True`

### 2. Attributes Missing/Different

**Verify:** Cached Change objects have complete attributes

```python
# Compare:
change_from_new = Change(nlri, attributes)  # Direct announcement
change_from_cache = self._seen[family][index]  # Cached route

# Are attributes identical?
```

**Test:** Log `change.attributes.index()` in both paths

### 3. Message Encoding Path

**Verify:** `update.messages()` produces same output for both paths

```python
# In protocol.py new_update_async():
for update in updates:
    for message in update.messages(self.negotiated, include_withdraw):
        # Is message different when update came from _refresh_changes?
```

**Test:** Log `message.raw()` or `message` repr

### 4. Negotiated Capabilities

**Verify:** Same capabilities used for encoding in both modes

```python
# Check:
self.proto.negotiated.families
self.proto.negotiated.asn4
self.proto.negotiated.add_path
```

**Test:** Log negotiated capabilities at peer establishment

---

## Test Expectations

### Test T expects (from api-rib.msg):

```
Line 10: EOR (initial)
Lines 20-21: 192.168.0.1/32 announce + withdraw
Lines 30-31: 192.168.0.2/32 and 0.3/32 announce
Lines 31-32: 192.168.0.2/32 and 0.3/32 RE-SEND (flush)  ← CRITICAL
Line 40: 192.168.0.4/32 announce
Lines 41-43: 0.2/32, 0.3/32, 0.4/32 RE-SEND (flush)     ← CRITICAL
Lines 50-52: 0.2/32, 0.3/32, 0.4/32 withdraw (clear)
Line 60: 192.168.0.5/32 announce
```

**The flush lines (31-32, 41-43) are where test fails.**

### Message Format

From `.msg` file format:
```
<timestamp>:raw:<marker>:<length>:<type>:<data>
```

Example:
```
30:raw:FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:0031:02:00000015400101004002004003040A0000024005040000006420C0A80002
│  │   │                              │    │  │
│  │   │                              │    │  └─ BGP data
│  │   │                              │    └─ Type (02 = UPDATE)
│  │   │                              └─ Length
│  │   └─ Marker (all F's)
│  └─ Format indicator
└─ Timestamp/ordering
```

**Check:** Are flush UPDATEs encoded identically to original UPDATEs?

---

## Useful Test Commands

```bash
# Run just test T
./qa/bin/functional encoding T                    # Sync
env exabgp_reactor_asyncio=true ./qa/bin/functional encoding T  # Async

# List all tests
./qa/bin/functional encoding --list

# Run specific tests
./qa/bin/functional encoding T U

# Run all async tests
env exabgp_reactor_asyncio=true ./qa/bin/functional encoding

# Manual daemon
./sbin/exabgp ./etc/exabgp/api-rib.conf

# With debug
env exabgp_log_level=DEBUG exabgp_reactor_asyncio=true \
    ./sbin/exabgp ./etc/exabgp/api-rib.conf

# Validate config
./sbin/exabgp validate ./etc/exabgp/api-rib.conf
```

---

## Mock Tests (Always Pass)

```bash
# Run diagnostic tests that PROVE async works:
cd tests/async_debug

# Test 1: Generator patterns
python3 test_generator_interleaving.py

# Test 2: ExaBGP RIB simulation (EXACT test T pattern)
python3 test_rib_updates_realworld.py

# Test 3: Real ExaBGP classes
python3 test_real_exabgp_rib.py
```

**All these pass ✅** - Architecture is sound!

---

## Questions to Answer

1. **Is cache populated?**
   - Add logging to `update_cache()`
   - Check `self.cache` flag value

2. **Are cached routes complete?**
   - Compare `Change` object from cache vs new
   - Check all attributes present

3. **Are messages encoded identically?**
   - Capture wire format in both modes
   - Hex dump comparison

4. **Is timing different?**
   - Does async mode send messages faster?
   - Does daemon need time to process?

5. **Are capabilities negotiated the same?**
   - Log negotiated features in both modes
   - Check for differences

---

## If You're Still Stuck

### Contact Points

- **Previous Investigation:** See `INVESTIGATION_TESTS_T_U.md`
- **Session Notes:** `.claude/asyncio-migration/session-2025-11-18-async-continue-fix.md`
- **Architecture Proof:** `tests/async_debug/*.py` (all pass)

### Nuclear Option: Binary Search

Temporarily disable async features one by one:

```python
# In new_update_async(), match sync mode exactly:
for update in updates:
    for message in update.messages():
        await self.send_async(message)
        await asyncio.sleep(0)  # Add yield
        # Does it work now?
```

If adding yields fixes it → timing issue
If still broken → encoding issue

---

## Success Criteria

Test T passes when:
```bash
env exabgp_reactor_asyncio=true ./qa/bin/functional encoding T
# Output: "Total: 1 test(s) run, 100.0% passed"
```

Daemon log should show:
```
[RIB.resend] CALLED
[RIB.resend] AFTER - refresh_changes=2  (or 3)
[RIB.updates] REFRESH - refresh_changes=2  (or 3)
[RIB.updates] YIELD refresh Update [1/2]: ...
[Protocol] Sending message #1
```

Test `.msg` file validation should match expected messages.

---

**Good luck! The architecture is solid - you're just hunting for an encoding difference.**

---

**Document Version:** 1.0
**Last Updated:** 2025-11-18
