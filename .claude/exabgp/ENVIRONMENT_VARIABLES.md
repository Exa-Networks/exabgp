# Environment Variables Reference

Complete reference for all ExaBGP environment variables.

**Format:** `exabgp_<category>_<name>` or `exabgp.<category>.<name>`

**Example:** `exabgp_tcp_attempts=50` or `exabgp.tcp.attempts=50`

---

## Network & Connection (tcp.*)

### tcp.attempts
**Default:** `0`
**Type:** integer

Maximum cumulative connection failures across all peers before reactor exits.

| Value | Behavior |
|-------|----------|
| `0` | **Daemon mode** (default) - reactor runs forever, never exits due to connection failures |
| `N > 0` | **Limited failure mode** - reactor exits after N cumulative connection failures across all peers |

**What counts as a connection failure:**
- A peer exhausts all retry attempts and gives up
- Only counted when peer stops trying (reaches per-peer limit)
- NOT normal session closures, graceful shutdowns, or explicit teardowns

**Example:**
```bash
# Production - daemon mode
exabgp_tcp_attempts=0 ./sbin/exabgp config.conf

# Testing - exit after 50 total peer failures
exabgp_tcp_attempts=50 ./sbin/exabgp config.conf
```

**Implementation:** See tcp.attempts section below for detailed behavior.

### tcp.bind
**Default:** (empty)
**Type:** space-separated IP list

Local IP addresses to bind to when listening for BGP connections. Empty = disable listening.

**Example:**
```bash
exabgp_tcp_bind="127.0.0.1 ::1" ./sbin/exabgp config.conf
```

### tcp.port
**Default:** `179`
**Type:** integer

TCP port to bind on when listening for BGP connections.

### tcp.delay
**Default:** `0`
**Type:** integer

Delay route announcements until the minutes in the hour is a modulo of this number. Used for synchronized startup across multiple instances.

### tcp.once
**Default:** `false`
**Type:** boolean

**DEPRECATED** - Use `tcp.attempts=1` instead.

Only one TCP connection attempt per peer (for debugging scripts).

### tcp.acl
**Default:** (empty)
**Type:** boolean

**EXPERIMENTAL - DO NOT USE** - Unimplemented ACL feature.

---

## BGP Protocol (bgp.*)

### bgp.openwait
**Default:** `60`
**Type:** integer (seconds)

How many seconds to wait for an OPEN message after TCP connection is established.

### bgp.passive
**Default:** `false`
**Type:** boolean

Ignore peer configuration and make all peers passive (only accept incoming connections).

---

## Daemon Control (daemon.*)

### daemon.daemonize
**Default:** `false`
**Type:** boolean

Run ExaBGP in the background as a daemon process.

### daemon.pid
**Default:** (empty)
**Type:** string (path)

Where to save the PID file if ExaBGP manages it.

**Example:**
```bash
exabgp_daemon_pid=/var/run/exabgp.pid ./sbin/exabgp config.conf
```

### daemon.user
**Default:** `nobody`
**Type:** string (username)

User to drop privileges to after binding to ports.

### daemon.drop
**Default:** `true`
**Type:** boolean

Drop privileges before forking API processes.

### daemon.umask
**Default:** `0137`
**Type:** octal

Daemon umask - governs permissions of log files and other created files.

---

## Logging (log.*)

### log.enable
**Default:** `true`
**Type:** boolean

Enable logging to file or syslog.

### log.level
**Default:** `INFO`
**Type:** string

Log message priority level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

### log.destination
**Default:** `stdout`
**Type:** string

Where to send log output:
- `syslog` - local syslog
- `host:<location>` - remote syslog server
- `stdout` - standard output
- `stderr` - standard error
- `<filename>` - file path

**Example:**
```bash
exabgp_log_destination=/var/log/exabgp.log ./sbin/exabgp config.conf
```

### log.short
**Default:** `true`
**Type:** boolean

Use short log format (no timestamp, level, PID, or source prefix).

### log.all
**Default:** `false`
**Type:** boolean

Report debug information for everything (overrides individual log settings).

### Log Categories (log.<category>)

All default to `true` unless noted:

| Variable | Description |
|----------|-------------|
| `log.configuration` | Configuration file parsing |
| `log.reactor` | Signal handling, reloads |
| `log.daemon` | PID changes, forking |
| `log.processes` | Forked process handling |
| `log.network` | TCP/IP, network state |
| `log.statistics` | Packet statistics |
| `log.packets` | BGP packets (default: `false`) |
| `log.rib` | Local route changes (default: `false`) |
| `log.message` | Route announcements on reload (default: `false`) |
| `log.timers` | Keepalive timers (default: `false`) |
| `log.routes` | Received routes (default: `false`) |
| `log.parser` | BGP message parsing (default: `false`) |

---

## API & Processes (api.*)

### api.ack
**Default:** `true`
**Type:** boolean

Acknowledge API commands and report issues.

### api.encoder
**Default:** `json`
**Type:** string (`json` or `text`)

**EXPERIMENTAL** - Default encoder for external API communication.

### api.compact
**Default:** `false`
**Type:** boolean

Use shorter JSON encoding for IPv4/IPv6 Unicast NLRI.

### api.chunk
**Default:** `1`
**Type:** integer

Maximum lines to print before yielding in `show routes` API command.

### api.respawn
**Default:** `true`
**Type:** boolean

Automatically respawn API processes if they die.

### api.terminate
**Default:** `false`
**Type:** boolean

Terminate ExaBGP if any API process dies.

### api.cli
**Default:** `true`
**Type:** boolean

Create a named pipe for CLI access.

### api.pipename
**Default:** `exabgp`
**Type:** string

Name to use for the ExaBGP named pipe (CLI).

### api.socketname
**Default:** `exabgp`
**Type:** string

Name to use for the ExaBGP Unix socket.

---

## Reactor Control (reactor.*)

### reactor.speed
**Default:** `1.0`
**Type:** float

Reactor event loop speed multiplier. **Use only if you understand the code.**

### reactor.legacy
**Default:** `false`
**Type:** boolean

Use legacy generator-based event loop instead of asyncio. Default is asyncio mode.

---

## Caching (cache.*)

### cache.attributes
**Default:** `true`
**Type:** boolean

Cache all BGP attributes (configuration and wire format) for faster parsing.

### cache.nexthops
**Default:** `true`
**Type:** boolean

Cache route next-hops. **Deprecated:** Next-hops are always cached.

---

## Profiling & Debugging (profile.*, pdb.*, debug.*)

### profile.enable
**Default:** `false`
**Type:** boolean

Enable profiling of the code.

### profile.file
**Default:** (empty)
**Type:** string (path)

Profiling result file. Empty means stdout. Does not overwrite.

### pdb.enable
**Default:** `false`
**Type:** boolean

On program fault, start Python interactive debugger (pdb).

### debug.pdb
**Default:** `false`
**Type:** boolean

Enable Python debugger on errors.

### debug.memory
**Default:** `false`
**Type:** boolean

Command line option `--memory` equivalent.

### debug.configuration
**Default:** `false`
**Type:** boolean

Raise exceptions on configuration parsing errors (instead of warnings).

### debug.selfcheck
**Default:** `false`
**Type:** boolean

Perform self-check on the configuration file.

### debug.route
**Default:** (empty)
**Type:** string

Decode a specific route using the configuration.

### debug.defensive
**Default:** `false`
**Type:** boolean

Generate random faults in the code intentionally (for testing fault tolerance).

### debug.rotate
**Default:** `false`
**Type:** boolean

Rotate configuration files on reload (signal).

---

## tcp.attempts - Detailed Behavior

### Connection Failure Tracking

**Reactor-level tracking:**
```python
self._max_connection_failures: int = getenv().tcp.attempts  # 0 = unlimited
self._total_connection_failures: int = 0  # Cumulative counter
```

**Peer-level tracking:**
```python
self.max_connection_attempts: int = getenv().tcp.attempts
self.connection_attempts: int = 0  # Per-peer counter
```

### Failure Recording Flow

1. Peer attempts connection (increments `peer.connection_attempts`)
2. Connection fails (NetworkError, Notify, or Notification exception)
3. Check `peer.can_reconnect()`:
   - If `tcp.attempts=0`: Always returns True (unlimited retries)
   - If `tcp.attempts=N`: Returns `connection_attempts < N`
4. If `can_reconnect()` returns False:
   - Peer gives up permanently
   - Calls `reactor.record_connection_failure()`
   - Reactor increments global failure counter
   - If global counter >= `tcp.attempts`, reactor exits

### Use Cases

**Production (daemon mode):**
```bash
exabgp_tcp_attempts=0 ./sbin/exabgp config.conf
```
- Reactor runs forever
- Each peer retries indefinitely
- Suitable for production deployments
- Requires external monitoring

**Testing (limited failure mode):**
```bash
exabgp_tcp_attempts=50 ./sbin/exabgp config.conf
```
- Each peer can fail up to 50 times
- Reactor exits after 50 total peer failures
- Prevents hung test processes
- Suitable for CI/CD pipelines

**Example scenario (tcp.attempts=50):**
```
Peer A: tries 50 times, all fail → stops (failure #1 recorded)
Peer B: tries 50 times, all fail → stops (failure #2 recorded)
Peer C: tries 10 times, all fail → stops (failure #3 recorded)
...
After 50 peers give up → reactor exits
```

### Implementation Changes (2025-11-24)

Changed connection failure tracking from per-peer only to global cumulative:

**Before:**
- Only per-peer limit enforced
- Each peer could fail `tcp.attempts` times independently
- No global failure tracking across all peers

**After:**
- Global cumulative failure counter added
- When any peer exhausts its retry attempts, global counter increments
- Reactor exits when cumulative failures reach `tcp.attempts`
- Per-peer limit still exists (same value as global limit)

---

## Environment Variable Aliases

Some environment variables have aliases for backward compatibility:

| Primary | Alias |
|---------|-------|
| `tcp.attempts` | `tcp.connections` |
| `tcp.attempts` | `tcp.once` (deprecated, use attempts=1) |

---

**Files:**
- Configuration source: `src/exabgp/environment/setup.py`
- Environment loader: `src/exabgp/environment/environment.py`
- Reactor implementation: `src/exabgp/reactor/loop.py`
- Peer implementation: `src/exabgp/reactor/peer.py`

---

**Updated:** 2025-11-24
