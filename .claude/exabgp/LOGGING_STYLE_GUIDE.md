# ExaBGP Logging Style Guide

This document defines standards for all log messages in ExaBGP.

---

## 1. Message Structure

Every log message follows structured logging format:

```
<event.name> key1=value1 key2=value2 [hint=recovery_action]
```

**Examples:**
```python
# Good - structured, parseable, complete
log.error(lazymsg('connection.refused ip={ip} port={port} hint=check_firewall', ip=peer_ip, port=port), 'network')
log.warning(lazymsg('capability.mismatch peer={peer} afi={afi} safi={safi}', peer=peer_name, afi=afi, safi=safi), self.session())

# Bad - unstructured prose, missing context
log.error(lazymsg('connection refused'), 'network')  # Missing: to whom? what to do?
log.warning(lazymsg('capability mismatch'), 'reactor')  # Missing: which peer? which capability?
```

---

## 2. Message Categories

Use ONLY these standard categories (defined in `option.py`):

| Category | Use For |
|----------|---------|
| `'configuration'` | Config file parsing, validation |
| `'reactor'` | Main loop, signals, reloads |
| `'daemon'` | PID, forking, daemonization |
| `'processes'` | External process/API handling |
| `'network'` | TCP/IP, connections |
| `'statistics'` | Packet/route statistics |
| `'wire'` | Raw BGP packets (hex) |
| `'message'` | Route changes on reload |
| `'rib'` | RIB operations |
| `'timer'` | Keepalive timers |
| `'routes'` | Received route details |
| `'parser'` | BGP message parsing |
| `'startup'` | Startup banner messages |
| `'cli'` | CLI operations |
| `'api'` | API operations |
| `'pdb'` | Debugger messages |

**For peer-specific messages:** Use `self.session()` or `self.id()` as source - these are dynamic identifiers that help correlate logs per peer.

**Do NOT invent new ad-hoc categories** - add them to `option.py` first.

---

## 3. Lazy Evaluation Rules

**ALWAYS use lazy evaluation via helpers. NEVER pass raw strings.**

```python
# Correct patterns - use lazymsg for all messages
log.info(lazymsg('simple message'), 'reactor')
log.info(lazymsg('message with {var}', var=variable), 'reactor')

# Wrong patterns - NEVER do this
log.info('raw string', 'reactor')           # Not lazy
log.info(f'eager {variable}', 'reactor')    # Evaluated immediately
log.info(_precomputed_message, 'reactor')   # Variable, not callable
```

---

## 4. Available Lazy Helpers

Import from `exabgp.logger`:

```python
from exabgp.logger import log, lazyformat, lazyattribute, lazynlri, lazymsg
```

### 4.1 `lazymsg(template, **kwargs)`

Template-based lazy message. Preferred for messages with multiple variables:
```python
log.debug(lazymsg('duplicate AFI/SAFI: {afi}/{safi}', afi=afi, safi=safi), 'parser')
```

### 4.2 `lazyformat(prefix, message, formater=od)`

For hex dumps of binary data:
```python
log.debug(lazyformat('received TCP payload', data), self.session())
# Output: received TCP payload (  64) FF FF FF FF...
```

### 4.3 `lazyattribute(flag, aid, length, data)`

For BGP attribute logging:
```python
log.debug(lazyattribute(flag, aid, length, data[:length]), 'parser')
# Output: attribute ORIGIN             flag 0x40 type 0x01 len 0x01 payload 00
```

### 4.4 `lazynlri(afi, safi, addpath, data)`

For NLRI logging:
```python
log.debug(lazynlri(afi, safi, addpath, data), 'parser')
# Output: NLRI      ipv4 unicast       without path-information    payload 18 0A 00 01
```

### 4.5 Default Argument Binding

When creating lazy functions in loops, bind loop variables via default arguments:
```python
# Correct - captures current value
for afi, safi in families:
    def _log_msg(afi: AFI = afi, safi: SAFI = safi) -> str:
        return f'processing {afi}/{safi}'
    log.debug(_log_msg, 'parser')

# Wrong - captures final loop value
for afi, safi in families:
    log.debug(lambda: f'processing {afi}/{safi}', 'parser')  # All logs show final value!
```

---

## 5. Structured Logging Format

Log messages should follow structured logging best practices for both human readability and machine parsing.

### 5.1 Event-First Structure

Every message starts with an event/action identifier, followed by key=value pairs:
```
<event> <key>=<value> <key>=<value> ...
```

```python
# Good - event first, then structured key=value pairs
log.info(lazymsg('peer.connected ip={ip} port={port}', ip=peer_ip, port=port), 'network')
log.info(lazymsg('session.established peer={peer} afi={afi} safi={safi}', peer=name, afi=afi, safi=safi), self.session())
log.debug(lazymsg('attribute.parsed type={type} flag=0x{flag:02x} len={len}', type=aid, flag=flag, len=length), 'parser')

# Bad - unstructured prose
log.info(lazymsg('connected to peer {ip} on port {port}', ip=peer_ip, port=port), 'network')
```

### 5.2 Event Naming Convention

Use dot-separated hierarchical event names:
```python
# Good - hierarchical, searchable
'peer.connected'
'peer.disconnected'
'session.established'
'session.closed'
'attribute.parsed'
'attribute.invalid'
'capability.negotiated'
'capability.mismatch'

# Bad - inconsistent naming
'connected to peer'
'peer connection failed'
'Session is now established'
```

### 5.3 Key=Value Pairs

All variable data uses key=value format:
```python
# Good - consistent key=value, easy to parse
log.error(lazymsg('connection.failed ip={ip} port={port} reason={reason}', ip=ip, port=port, reason=err), 'network')
log.debug(lazymsg('nlri.received afi={afi} safi={safi} count={count}', afi=afi, safi=safi, count=len(nlris)), 'parser')

# For state transitions, use from=/to= pattern
log.info(lazymsg('state.changed from={old} to={new}', old=old_state, new=new_state), self.session())
```

### 5.4 Grep/Parse Friendly

Structured format enables easy parsing:
```bash
# Find all peer connections
grep 'peer.connected' exabgp.log

# Extract IPs from connection failures
grep 'connection.failed' exabgp.log | grep -oP 'ip=\K\S+'

# Count events by type
grep -oP '^\S+' exabgp.log | sort | uniq -c
```

### 5.5 Include Debugging Data

Log messages must include sufficient data for debugging. Don't strip useful context:
```python
# Bad - lost debugging data
log.debug(lazymsg('update.message.sending num={num}', num=num), self.session())

# Good - includes the actual message for debugging
log.debug(lazymsg('update.message.sending num={num} msg={msg}', num=num, msg=repr(message)), self.session())

# Bad - no context about what's being processed
log.debug(lazymsg('update.processing'), self.session())

# Good - includes the update data
log.debug(lazymsg('update.processing update={upd}', upd=update), self.session())
```

**Rule:** If a developer would need to add a print() to debug an issue, that data should already be in the log.

### 5.6 Avoid Anti-Patterns

```python
# Bad - decorative noise
log.debug(lazymsg('========================================'), 'parser')
log.debug(lazymsg('[Protocol.method] CALLED'), self.session())

# Bad - prose with embedded values
log.info(lazymsg('The peer at {ip} has connected on port {port}', ip=ip, port=port), 'network')

# Bad - inconsistent separators
log.error(lazymsg('connection failed - reason: {reason}', reason=err), 'network')

# Good - structured
log.debug(lazymsg('protocol.update.called'), self.session())
log.info(lazymsg('peer.connected ip={ip} port={port}', ip=ip, port=port), 'network')
log.error(lazymsg('connection.failed reason={reason}', reason=err), 'network')
```

---

## 6. Log Level Guidelines

| Level | Use For | Operator Action |
|-------|---------|-----------------|
| `FATAL` | Cannot continue, exiting | Immediate attention required |
| `CRITICAL` | Major failure, degraded operation | Investigate promptly |
| `ERROR` | Operation failed but continuing | Review and fix |
| `WARNING` | Unexpected but handled condition | Monitor |
| `INFO` | Normal operational events | Informational |
| `DEBUG` | Diagnostic detail | Development/troubleshooting |

---

## 7. Formatting Conventions

### 7.1 Capitalization

Lowercase for event names and keys:
```python
log.info(lazymsg('config.reload status=started'), 'reactor')      # Good
log.info(lazymsg('Config.Reload status=Started'), 'reactor')      # Bad
```

### 7.2 Event State Suffixes

Use consistent suffixes for event states:
```python
# .started / .completed / .failed pattern
log.debug(lazymsg('peer.connect.started ip={ip}', ip=peer_ip), 'network')
log.info(lazymsg('peer.connect.completed ip={ip}', ip=peer_ip), 'network')
log.error(lazymsg('peer.connect.failed ip={ip} reason={reason}', ip=peer_ip, reason=err), 'network')
```

### 7.3 Peer Identification

Always include peer identity in key=value format:
```python
log.info(lazymsg('session.established peer={peer}', peer=peer_ip), self.session())
```

### 7.4 Numeric Values

Include units in key names:
```python
log.warning(lazymsg('attribute.oversized size_bytes={size} max_bytes={max}', size=size, max=MAX_SIZE), 'parser')
log.debug(lazymsg('keepalive.sent interval_sec={interval}', interval=interval), 'timer')
```

### 7.5 Error Messages

Include recovery hint as separate key:
```python
log.error(lazymsg('bind.failed ip={ip} port={port} reason=in_use hint=stop_other_bgp_or_change_tcp.bind', ip=ip, port=port), 'network')
```

---

## 8. Multi-line Messages

Avoid decorative separators. Use separate structured log entries:
```python
# Bad - decorative noise
log.warning(lazymsg('--------------------------------------------'), 'reactor')
log.warning(lazymsg('capability mismatch detected'), 'reactor')

# Good - one structured event per line
log.warning(lazymsg('capability.mismatch afi={afi} safi={safi} reason={reason}', afi=afi, safi=safi, reason=reason), self.session())

# For multiple items, log each separately with consistent structure
for afi, safi in mismatches:
    log.warning(lazymsg('capability.missing afi={afi} safi={safi}', afi=afi, safi=safi), self.session())
```

---

## 9. Binary Data

Use `lazyformat()` for hex dumps:
```python
log.debug(lazyformat('received TCP payload', data), self.session())
# Output: received TCP payload (  64) FF FF FF FF...
```

---

## 10. BGP-Specific Conventions

### 10.1 State Transitions

Use from=/to= pattern:
```python
log.info(lazymsg('fsm.state.changed from={old} to={new}', old=old_state, new=new_state), self.session())
```

### 10.2 NLRI/Attributes

Use dedicated formatters for binary protocol data:
```python
log.debug(lazynlri(afi, safi, addpath, data), 'parser')
log.debug(lazyattribute(flag, aid, length, data), 'parser')
```

### 10.3 BGP Event Hierarchy

Suggested event prefixes for BGP:
```python
'fsm.'           # State machine: fsm.state.changed, fsm.timer.expired
'peer.'          # Peer lifecycle: peer.connected, peer.disconnected
'session.'       # BGP session: session.established, session.closed
'message.'       # BGP messages: message.open.sent, message.update.received
'capability.'    # Capabilities: capability.negotiated, capability.mismatch
'attribute.'     # Attributes: attribute.parsed, attribute.invalid
'nlri.'          # NLRI: nlri.received, nlri.announced, nlri.withdrawn
'notification.'  # Notifications: notification.sent, notification.received
```

---

## 11. Quick Reference

| Do | Don't |
|----|-------|
| `lazymsg('event.name key={k}', k=v)` | `f'event {v}'` (eager eval) |
| `'peer.connected ip={ip}'` | `'connected to peer {ip}'` |
| `'fsm.state.changed from={} to={}'` | `'state change: {} -> {}'` |
| `self.session()` for peer logs | `'reactor'` for peer logs |
| lowercase `event.name` | Uppercase `Event.Name` |
| `reason={reason}` key=value | `reason: {reason}` prose |
| `'processes'` category | `'process'` (wrong) |

### Event Format Template
```
<noun>.<verb>.<state> key1=value1 key2=value2
```

### Common Patterns
```python
# Lifecycle events
lazymsg('peer.connected ip={ip} port={port}', ip=ip, port=port)
lazymsg('session.established peer={peer}', peer=peer)
lazymsg('session.closed peer={peer} reason={reason}', peer=peer, reason=reason)

# State changes
lazymsg('fsm.state.changed from={old} to={new}', old=old, new=new)

# Operations
lazymsg('config.reload.started')
lazymsg('config.reload.completed')
lazymsg('config.reload.failed reason={reason}', reason=err)

# Errors with hints
lazymsg('bind.failed ip={ip} port={port} reason={r} hint={h}', ip=ip, port=port, r=reason, h=hint)
```

---

**Updated:** 2025-11-27
