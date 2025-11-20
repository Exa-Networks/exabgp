# Manual Interactive CLI Testing Instructions

**ExaBGP is currently running** with PID shown in terminal.

Socket location: `run/exabgp.sock`
Config: `etc/exabgp/api-rib.conf`
Neighbor: `127.0.0.1`

---

## How to Test Interactive Mode

### 1. Launch Interactive CLI

In a **NEW terminal window**, run:

```bash
cd /Users/thomas/Code/github.com/exa-networks/exabgp/main
./sbin/clii
```

Or using the main CLI command:
```bash
./sbin/exabgp cli --socket
```

### 2. Test Tab Completion

Try these completion scenarios (press TAB where indicated):

#### Base Command Completion
```
exabgp> s<TAB>
# Should complete to: show

exabgp> sh<TAB>
# Should show: show, shutdown (if ambiguous)

exabgp> ann<TAB>
# Should complete to: announce
```

#### Nested Command Completion
```
exabgp> show <TAB>
# Should show: adj-rib  neighbor

exabgp> show n<TAB>
# Should complete to: neighbor

exabgp> show neighbor <TAB>
# Should show: configuration  extensive  json  summary  127.0.0.1
```

#### AFI/SAFI Completion
```
exabgp> announce eor <TAB>
# Should show: bgp-ls  ipv4  ipv6  l2vpn

exabgp> announce eor ipv4 <TAB>
# Should show: flow  flow-vpn  mcast-vpn  mpls-vpn  mup  multicast  nlri-mpls  unicast

exabgp> announce route-refresh ipv6 <TAB>
# Should show: flow  flow-vpn  mcast-vpn  mpls-vpn  mup  unicast
```

#### Neighbor IP Completion
```
exabgp> neighbor <TAB>
# Should show: 127.0.0.1 (from running ExaBGP)

exabgp> neighbor 127.0.0.1 <TAB>
# Should show filters: family-allowed  local-as  local-ip  peer-as  router-id
```

#### Adj-RIB Completion
```
exabgp> show adj-rib <TAB>
# Should show: in  out

exabgp> show adj-rib in <TAB>
# Should show: extensive  json
```

### 3. Test Shortcut Expansion

Try typing these and press ENTER (shortcuts will be shown as expanded):

```
exabgp> s n summary
# Should expand to: show neighbor summary
# Should display neighbor table

exabgp> h
# Should expand to: help
# Should display help text

exabgp> s a i
# 's' -> show, 'a' -> adj-rib, 'i' -> in
# Should expand to: show adj-rib in

exabgp> neighbour 127.0.0.1
# Should expand to: neighbor 127.0.0.1
# (typo correction)
```

### 4. Test Context-Aware Shortcuts

The 'a' shortcut expands differently based on context:

```
exabgp> a
# At start: 'a' -> 'announce'

exabgp> show a
# After 'show': 'a' -> 'adj-rib'

exabgp> announce a
# After 'announce': 'a' -> 'attributes'
```

### 5. Test Actual Commands

Execute some real commands:

```
exabgp> show neighbor summary
# Should show neighbor status table

exabgp> show neighbor 127.0.0.1 configuration
# Should show detailed neighbor config

exabgp> show adj-rib in
# Should show received routes (may be empty)

exabgp> version
# Should show ExaBGP version
```

### 6. Test Command History

Use arrow keys:
- **Up Arrow**: Previous command
- **Down Arrow**: Next command
- **Ctrl+R**: Reverse search history

### 7. Exit Interactive Mode

```
exabgp> exit
```

Or press **Ctrl+D**

---

## Expected Behavior

### ✅ Success Indicators

1. **Tab completion works** - Pressing TAB shows available options
2. **Shortcuts expand** - "s n" displays as "command: show neighbor"
3. **Neighbor IPs appear** - 127.0.0.1 shows up in completions
4. **AFI/SAFI values complete** - ipv4/ipv6 and their SAFI values appear
5. **No errors** - No Python tracebacks or exceptions
6. **Fast response** - Completion appears instantly (< 100ms)

### ❌ Failure Indicators

1. **Tab does nothing** - No completion appears
2. **Shortcuts don't expand** - "s n" stays as "s n"
3. **Python errors** - Tracebacks or import errors
4. **Slow completion** - Takes > 1 second to show options
5. **No neighbor IPs** - 127.0.0.1 doesn't appear in completions

---

## Debugging

If completion doesn't work:

1. **Check readline**:
   ```python
   python3 -c "import readline; print('readline OK')"
   ```

2. **Check socket**:
   ```bash
   ls -la run/exabgp.sock
   # Should exist and be a socket (s-----)
   ```

3. **Check ExaBGP is running**:
   ```bash
   ps aux | grep exabgp
   ```

4. **Test basic command**:
   ```bash
   ./sbin/exabgp cli --socket version
   ```

---

## Stop ExaBGP When Done

Return to the original terminal and kill the background process:

```bash
# Find the PID (shown when ExaBGP started)
# Or use:
pkill -f "exabgp.*api-rib"

# Or kill all python processes:
killall -9 python
```

---

## What Was Tested Automatically

✅ Shortcut expansion works:
- 's n' → 'show neighbor'
- 's n summary' → 'show neighbor summary'
- 's a i' → 'show adj-rib in'
- 'h' → 'help'

✅ CLI connection works:
- Socket created successfully
- Commands execute correctly
- Responses received

---

## What Needs Manual Testing

⏳ Interactive features (cannot be automated):
- Tab completion behavior
- Completion option display
- Neighbor IP fetching from live ExaBGP
- AFI/SAFI completion
- Filter completion after neighbor IP
- History navigation with arrows
- Ctrl+R reverse search

---

**Current Status:** ExaBGP is running, ready for interactive testing
**Next:** Launch `./sbin/clii` in a new terminal and try the test cases above
