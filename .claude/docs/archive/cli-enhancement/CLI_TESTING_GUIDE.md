# CLI Interactive Testing Guide

Quick reference for testing the enhanced CLI interactive features.

---

## 🚀 Quick Start Testing

### 1. Start ExaBGP with Test Config

```bash
# Use the API-enabled config
./sbin/exabgp ./etc/exabgp/api-rib.conf
```

### 2. Start Interactive CLI (in another terminal)

```bash
./sbin/clii
```

Or with socket path:
```bash
./sbin/exabgp cli --socket
```

---

## 🧪 Feature Test Cases

### Tab Completion - Base Commands

**Test:** Type partial command and press TAB

```bash
exabgp> s<TAB>
# Should complete to: show

exabgp> sh<TAB>
# Should complete to: show (or shutdown if ambiguous)

exabgp> ann<TAB>
# Should complete to: announce
```

### Tab Completion - Nested Commands

**Test:** Complete subcommands

```bash
exabgp> show <TAB>
# Should show: adj-rib  neighbor

exabgp> show n<TAB>
# Should complete to: neighbor

exabgp> show neighbor <TAB>
# Should show: configuration  extensive  json  summary  [and neighbor IPs if any]
```

### Tab Completion - AFI/SAFI Values

**Test:** Complete AFI and SAFI for eor/route-refresh

```bash
exabgp> announce eor <TAB>
# Should show: bgp-ls  ipv4  ipv6  l2vpn

exabgp> announce eor ipv4 <TAB>
# Should show: flow  flow-vpn  mcast-vpn  mpls-vpn  mup  multicast  nlri-mpls  unicast

exabgp> announce route-refresh <TAB>
# Should show: bgp-ls  ipv4  ipv6  l2vpn

exabgp> announce route-refresh ipv6 <TAB>
# Should show: flow  flow-vpn  mcast-vpn  mpls-vpn  mup  unicast
```

### Tab Completion - Neighbor IPs

**Test:** Complete with dynamic neighbor IPs (requires ExaBGP with configured neighbors)

```bash
exabgp> teardown <TAB>
# Should show configured neighbor IPs

exabgp> neighbor <TAB>
# Should show configured neighbor IPs

exabgp> show neighbor 192<TAB>
# Should complete IP if it exists
```

### Tab Completion - Neighbor Filters

**Test:** Complete filter keywords after neighbor IP

```bash
exabgp> neighbor 192.168.1.1 <TAB>
# Should show: family-allowed  local-as  local-ip  peer-as  router-id

exabgp> neighbor 192.168.1.1 local-<TAB>
# Should show: local-as  local-ip
```

### Tab Completion - Route Keywords

**Test:** Complete route specification keywords

```bash
exabgp> announce route <TAB>
# Should show: aigp  as-path  cluster-list  community  extended-community  label
#              large-community  local-preference  med  next-hop  origin
#              originator-id  path-information  rd  route-distinguisher  split  watchdog  withdraw

exabgp> announce ipv4 <TAB>
# Should show same list as above
```

### Shortcut Expansion - Single Letter

**Test:** Type shortcuts and verify expansion

```bash
exabgp> s n summary
# Should expand to: show neighbor summary

exabgp> h
# Should expand to: help

exabgp> a e ipv4 unicast
# Should expand to: announce eor ipv4 unicast
```

### Shortcut Expansion - Context Aware

**Test:** Same shortcut expands differently based on context

```bash
exabgp> a r 10.0.0.0/24
# 'a' → announce, 'r' → route

exabgp> a a community:65000:1
# First 'a' → announce, second 'a' → attributes

exabgp> s a i
# 's' → show, 'a' → adj-rib, 'i' → in
```

### Shortcut Expansion - Multi-letter

**Test:** Multi-character shortcuts

```bash
exabgp> a rr ipv4 unicast
# 'rr' → route-refresh
# Should expand to: announce route-refresh ipv4 unicast
```

### Shortcut Expansion - Typo Correction

**Test:** Common typos auto-corrected

```bash
exabgp> neighbour 192.168.1.1
# Should expand to: neighbor 192.168.1.1

exabgp> neigbor 192.168.1.1
# Should expand to: neighbor 192.168.1.1
```

---

## 📊 Expected Behavior

### Neighbor IP Completion Behavior

**When ExaBGP has neighbors:**
- Completer queries `show neighbor json` in background
- Parses JSON for peer IPs
- Caches results for 30 seconds
- Shows IPs in completion list

**When ExaBGP has no neighbors or isn't running:**
- Gracefully returns empty list
- No error shown to user
- Other completions still work

### Completion Display Format

Completions appear inline after pressing TAB:
```bash
exabgp> show <TAB>
adj-rib  neighbor

exabgp> show n<TAB>
exabgp> show neighbor █
```

Multiple TABs cycle through matches:
```bash
exabgp> ann<TAB>
exabgp> announce █
(first TAB completes unique match)

exabgp> show adj-rib <TAB>
in  out
(shows both matches)

exabgp> show adj-rib <TAB><TAB>
(cycles through: in → out → in → ...)
```

---

## 🔍 Debugging Failed Tests

### Completion Not Working

**Check 1:** Verify readline is enabled
```python
import readline
print(readline.get_completer())  # Should not be None
```

**Check 2:** Check if ExaBGP socket exists
```bash
ls -la /var/run/exabgp*.sock
# or
ls -la /tmp/exabgp*.sock
```

**Check 3:** Test send_command function
```python
# In interactive session
response = send_command('help')
print(response)
```

### Neighbor IPs Not Showing

**Check 1:** Verify ExaBGP has neighbors configured
```bash
# In interactive CLI
exabgp> show neighbor json
# Should return JSON with neighbor list
```

**Check 2:** Check cache timeout
```python
# In completer code, reduce timeout for testing
self._cache_timeout = 5  # 5 seconds instead of 30
```

**Check 3:** Clear cache and retry
```python
completer.invalidate_cache()
# Then try completion again
```

### Shortcuts Not Expanding

**Check 1:** Verify shortcuts module imported
```python
from exabgp.application.shortcuts import CommandShortcuts
CommandShortcuts.expand_shortcuts('s n')
# Should return: 'show neighbor'
```

**Check 2:** Check token expansion
```python
tokens = ['s', 'n', 'summary']
expanded = CommandShortcuts.expand_token_list(tokens)
print(expanded)
# Should print: ['show', 'neighbor', 'summary']
```

### Command Tree Empty

**Check 1:** Verify registry can discover commands
```python
from exabgp.reactor.api.command.registry import CommandRegistry
registry = CommandRegistry()
print(len(registry.get_all_commands()))
# Should be > 0
```

**Check 2:** Check Command.callback
```python
from exabgp.reactor.api.command.command import Command
print(len(Command.functions))
# Should be > 0
print('show neighbor' in Command.callback['text'])
# Should be True
```

---

## 🧪 Automated Testing

### Unit Tests (to be created)

```bash
# Test shortcuts module
env exabgp_log_enable=false pytest tests/unit/test_shortcuts.py -v

# Test registry module
env exabgp_log_enable=false pytest tests/unit/test_command_registry.py -v

# Test completer logic
env exabgp_log_enable=false pytest tests/unit/test_completer.py -v
```

### Integration Test Script

Create `tests/integration/test_cli_interactive.sh`:

```bash
#!/bin/bash
set -e

echo "Starting ExaBGP..."
./sbin/exabgp ./etc/exabgp/api-rib.conf &
EXABGP_PID=$!
sleep 2

echo "Testing CLI commands..."

# Test 1: Basic help
echo "help" | ./sbin/clii

# Test 2: Show neighbor
echo "show neighbor" | ./sbin/clii

# Test 3: Shortcut expansion
echo "s n" | ./sbin/clii

echo "Stopping ExaBGP..."
kill $EXABGP_PID

echo "All tests passed!"
```

---

## 📈 Performance Testing

### Completion Response Time

**Expected:** < 100ms for first completion, < 10ms for cached

**Test:**
```bash
# Time first completion (cache miss)
time -p bash -c 'echo -e "show\t" | ./sbin/clii'

# Time second completion (cache hit)
time -p bash -c 'echo -e "show\t" | ./sbin/clii'
```

### Neighbor IP Cache Performance

**Expected:** 30-second cache reduces queries

**Test:**
```bash
# Monitor send_command calls
# Add logging to cli_interactive.py:
def send_command(self, cmd):
    print(f"[DEBUG] Sending: {cmd}")
    # ... rest of code

# Then watch for repeated 'show neighbor json' calls
# Should only appear once per 30 seconds
```

---

## 🐛 Known Limitations

1. **No completion for route values**
   - Completes keywords (next-hop) but not values (192.168.1.1)
   - Future enhancement: Could parse typed route spec

2. **No validation before sending**
   - Invalid commands sent to server, rejected there
   - Future enhancement: Add local validation

3. **Neighbor cache doesn't invalidate on topology change**
   - If neighbor goes down, still appears in completion for 30s
   - Workaround: Call `completer.invalidate_cache()`

4. **No fuzzy matching**
   - Must type prefix exactly
   - Future enhancement: Could add fuzzy matching

5. **No inline help**
   - Completion shows matches but not syntax
   - Future enhancement: Show syntax hint after TAB

---

## ✅ Success Criteria

**Core features working:**
- ✅ Tab completion shows available commands
- ✅ Shortcuts expand correctly (s→show, a→announce, etc.)
- ✅ Context-aware shortcuts work (a→announce vs a→attributes)
- ✅ Dynamic command discovery (no hardcoded lists)
- ✅ All unit tests pass (when created)

**Advanced features working:**
- ✅ Neighbor IP completion (when ExaBGP has neighbors)
- ✅ AFI/SAFI completion for eor/route-refresh
- ✅ Route keyword completion
- ✅ Neighbor filter completion
- ✅ Caching prevents excessive queries

**Quality checks:**
- ✅ No linting errors (ruff)
- ✅ No runtime errors in interactive mode
- ✅ Backward compatible (old shortcuts still work)
- ✅ Performance acceptable (< 100ms completion)

---

**Last updated:** 2025-11-20
**Status:** Ready for testing
