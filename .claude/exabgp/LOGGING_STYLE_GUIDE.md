# ExaBGP Logging Style Guide

This document defines the standards for log messages in ExaBGP.

---

## 1. Message Structure

Every log message should follow this structure:

```
[WHAT happened] [to WHOM/WHAT] [WHY/CONTEXT] [RECOVERY if error]
```

**Examples:**
```python
# Good
log.error(lambda: f'connection refused to {peer_ip}:{port} - check firewall rules', 'network')
log.warning(lambda: f'capability mismatch with {peer_name}: {afi}/{safi} not negotiated', self.session())

# Bad
log.error(lambda: 'connection refused', 'network')  # Missing: to whom? what to do?
log.warning(lambda: 'capability mismatch', 'reactor')  # Missing: which peer? which capability?
```

---

## 2. Message Categories

Use ONLY these standard categories (defined in `option.py`):

| Category | Use For |
|----------|---------|
| `'configuration'` | Config file parsing, validation |
| `'reactor'` | Main loop, signals, reloads |
| `'daemon'` | PID, forking, daemonization |
| `'process'` | External process/API handling |
| `'network'` | TCP/IP, connections |
| `'statistics'` | Packet/route statistics |
| `'wire'` | Raw BGP packets (hex) |
| `'message'` | Route changes on reload |
| `'rib'` | RIB operations |
| `'timer'` | Keepalive timers |
| `'routes'` | Received route details |
| `'parser'` | BGP message parsing |
| `'welcome'` | Startup messages |
| `'cli'` | CLI operations |

**For peer-specific messages:** Use `self.session()` or `self.id()` as source - these are dynamic identifiers that help correlate logs per peer.

**Do NOT invent new ad-hoc categories** - add them to `option.py` first if needed.

---

## 3. Lazy Evaluation Rules

**ALWAYS use lazy evaluation. NEVER pass raw strings.**

```python
# Correct patterns
log.info(lambda: 'simple message', 'reactor')
log.info(lambda: f'message with {variable}', 'reactor')
log.info(lazymsg('template {var}', var=value), 'reactor')

# Wrong patterns - NEVER do this
log.info('raw string', 'reactor')           # Not lazy
log.info(f'eager {variable}', 'reactor')    # Evaluated immediately
log.info(_precomputed_message, 'reactor')   # Variable, not callable
```

---

## 4. Log Level Guidelines

| Level | Use For | Operator Action |
|-------|---------|-----------------|
| `FATAL` | Cannot continue, exiting | Immediate attention required |
| `CRITICAL` | Major failure, degraded operation | Investigate promptly |
| `ERROR` | Operation failed but continuing | Review and fix |
| `WARNING` | Unexpected but handled condition | Monitor |
| `INFO` | Normal operational events | Informational |
| `DEBUG` | Diagnostic detail | Development/troubleshooting |

---

## 5. Formatting Conventions

### 5.1 Capitalization

Lowercase start (log lines don't start sentences):
```python
log.info(lambda: 'performing reload', 'reactor')      # Good
log.info(lambda: 'Performing reload', 'reactor')      # Bad
```

### 5.2 Tense

Use present progressive for actions in progress, past for completed:
```python
log.debug(lambda: 'connecting to peer', 'network')    # In progress
log.info(lambda: 'connected to peer', 'network')      # Completed
log.error(lambda: 'connection failed', 'network')     # Failed
```

### 5.3 Peer Identification

Always include peer identity for peer-specific messages:
```python
log.info(lambda: f'session established with {peer_ip}', self.session())
```

### 5.4 Numeric Values

Include units and context:
```python
log.warning(lambda: f'attribute too large: {size} bytes (max {MAX_SIZE})', 'parser')
```

### 5.5 Error Messages

Include cause and recovery:
```python
log.error(
    lambda: f'cannot bind to {ip}:{port} - port in use. Stop other BGP daemon or change exabgp.tcp.bind',
    'network'
)
```

---

## 6. Multi-line Messages

Avoid decorative separators. Use structured multi-line for related info:
```python
# Bad
log.warning(lambda: '--------------------------------------------', 'reactor')
log.warning(lambda: 'capability mismatch detected', 'reactor')
log.warning(lambda: '--------------------------------------------', 'reactor')

# Good
log.warning(lambda: 'capability mismatch:', self.session())
for reason, (afi, safi) in mismatches:
    log.warning(lambda: f'  {reason}: {afi}/{safi}', self.session())
```

---

## 7. Binary Data

Use `lazyformat()` for hex dumps:
```python
log.debug(lazyformat('received TCP payload', data), self.session())
# Output: received TCP payload (  64) FF FF FF FF...
```

---

## 8. BGP-Specific Conventions

### 8.1 State Transitions

Show before and after:
```python
log.info(lambda: f'state change: {old_state} -> {new_state}', self.session())
```

### 8.2 NLRI/Attributes

Use dedicated formatters:
```python
log.debug(lazynlri(afi, safi, addpath, data), 'parser')
log.debug(lazyattribute(flag, aid, length, data), 'parser')
```

---

## 9. Available Lazy Helpers

| Helper | Use For | Example |
|--------|---------|---------|
| `lambda` | Simple messages | `lambda: f'msg {var}'` |
| `lazymsg()` | Template strings | `lazymsg('msg {x}', x=val)` |
| `lazyformat()` | Binary data | `lazyformat('prefix', data)` |
| `lazyattribute()` | BGP attributes | `lazyattribute(flag, aid, len, data)` |
| `lazynlri()` | NLRI data | `lazynlri(afi, safi, addpath, data)` |

---

**Updated:** 2025-11-27
