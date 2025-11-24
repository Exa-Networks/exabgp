# Unix Socket API Protocol

Complete reference for ExaBGP's Unix socket API protocol.

**See also:**
- `CLI_COMMANDS.md` - CLI command reference (uses this API)
- `CLI_SHORTCUTS.md` - CLI shortcuts (CLI-specific, not in API)
- `CLI_IMPLEMENTATION.md` - How CLI uses this API internally
- `NEIGHBOR_SELECTOR_SYNTAX.md` - Neighbor selector syntax

---

## Overview

ExaBGP provides a Unix domain socket API for external control. The CLI uses this API to send commands and receive responses.

**Key characteristics:**
- Single-client mode (one CLI connection at a time)
- Persistent connection with health monitoring
- Text and JSON response formats
- Synchronous request/response pattern
- Line-based protocol with terminators

---

## Socket Location

**Discovery order:**
1. Environment variable: `exabgp_api_socketpath`
2. Default search paths:
   - `/run/exabgp/exabgp.sock`
   - `/run/<uid>/exabgp.sock`
   - `/var/run/exabgp/exabgp.sock`
   - `/var/run/<uid>/exabgp.sock`
   - Root directory (dev/test mode)

**Socket name:** Configurable via `exabgp_api_socketname` (default: 'exabgp')

**Full path example:** `/var/run/exabgp/exabgp.sock`

**Implementation:** `src/exabgp/application/unixsocket.py`

---

## Connection Protocol

### 1. Socket Connection

```python
socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
socket.connect('/var/run/exabgp/exabgp.sock')
```

### 2. Initial Handshake (Ping)

Client must send ping immediately after connecting:

```
ping <client_uuid> <client_timestamp>\n
```

**Example:**
```
ping a1b2c3d4-e5f6-7890-abcd-ef1234567890 1700000000.123456\n
```

**Response (JSON):**
```json
{ "pong": "<daemon_uuid>", "active": true }
{ "answer": "done", "message": "command completed" }
```

**Response (text):**
```
pong <daemon_uuid> active=true
done
```

**If another client already connected:**
```
error: Another CLI client is already connected
error
```

### 3. Command/Response Cycle

**Send command:**
```
<command>\n
```

**Receive response:**
```
<line1>
<line2>
...
<lineN>
done
```

---

## Command Format

### Basic Syntax

```
<command> [arguments] [options]\n
```

**Rules:**
- Commands are newline-terminated (`\n`)
- Whitespace-separated tokens
- Case-sensitive
- JSON mode: append `json` keyword

**Examples:**
```
help
version
show neighbor
show neighbor summary
show neighbor json
announce route 10.0.0.0/24 next-hop 192.168.1.1
```

---

## Response Format

### Text Mode (Default)

**Success:**
```
<output_line_1>
<output_line_2>
...
done
```

**Error:**
```
error: <message>
error
```

**Simple error:**
```
error
```

**Terminator:** Line containing exactly `done` or `error`

### JSON Mode

**Success:**
```json
<json_line_1>
<json_line_2>
...
{ "answer": "done", "message": "command completed" }
```

**Error:**
```json
{ "error": "<message>" }
{ "answer": "error", "message": "..." }
```

**Terminator:** JSON object with `"answer": "done"` or `"answer": "error"`

---

## Available Commands

### Control Commands

| Command | Description | JSON Support |
|---------|-------------|--------------|
| `help` | List available commands | Yes |
| `version` | Show ExaBGP version | No |
| `shutdown` | Shutdown daemon | No |
| `reload` | Reload configuration | No |
| `restart` | Restart daemon | No |
| `reset` | Clear async queue | No |
| `bye` | Disconnect client | No |

### ACK Control

| Command | Description | Behavior |
|---------|-------------|----------|
| `enable-ack` | Enable "done" responses | Default mode |
| `disable-ack` | Disable "done" for next command | This command gets "done" |
| `silence-ack` | Disable "done" immediately | No "done" for this command |

### Health/Status

| Command | Description | JSON Support |
|---------|-------------|--------------|
| `ping [<uuid> <timestamp>]` | Health check | Yes (default) |
| `ping text` | Force text response | No |
| `status` | Daemon status | Yes |

### Neighbor Commands

**Syntax:**
```
[neighbor <selector>] <command>
```

**Selector format:**
```
neighbor <ip> [local-ip <ip>] [local-as <asn>] [peer-as <asn>] [router-id <ip>]
```

**Wildcard:** `neighbor *` matches all neighbors

**Commands:**
- `show neighbor [summary|extensive|configuration] [json]`
- `teardown <code>` - Tear down session with NOTIFICATION code

**Examples:**
```
show neighbor
show neighbor summary
show neighbor json
neighbor 192.0.2.1 teardown 6
neighbor * peer-as 65000 teardown 2
```

### Route Announcements

**IPv4/IPv6 routes:**
```
announce route <prefix> next-hop <ip> [attributes]
announce ipv4 unicast <prefix> next-hop <ip>
announce ipv6 unicast <prefix> next-hop <ip>
```

**FlowSpec:**
```
announce flow route <match-rules> then <actions>
```

**VPLS:**
```
announce vpls <endpoint> <offset> <size> <label>
```

**Other:**
```
announce eor <afi> <safi>
announce route-refresh <afi> <safi>
announce operational <data>
announce watchdog <neighbor>
```

**Attributes:**
- `next-hop <ip>`
- `as-path <asn> <asn> ...`
- `community <community>`
- `extended-community <community>`
- `large-community <community>`
- `local-preference <value>`
- `med <value>`
- `origin <igp|egp|incomplete>`
- `label <value>`
- `rd <route-distinguisher>`

### Route Withdrawals

```
withdraw route <prefix>
withdraw ipv4 unicast <prefix>
withdraw ipv6 unicast <prefix>
withdraw flow route <match-rules>
withdraw vpls <endpoint> <offset> <size>
withdraw watchdog <neighbor>
```

### RIB Operations

**Show RIB:**
```
show adj-rib in [<neighbor>] [extensive] [json]
show adj-rib out [<neighbor>] [extensive] [json]
```

**Clear RIB:**
```
clear adj-rib in [<neighbor>]
clear adj-rib out [<neighbor>]
```

**Flush RIB:**
```
flush adj-rib out [<neighbor>]
```

---

## Neighbor Selector Syntax

### Grammar

```
neighbor <ip> [qualifier]*

Qualifiers:
  local-ip <ip>
  local-as <asn>
  peer-as <asn>
  router-id <ip>
  family-allowed <afi-safi>
```

### Matching Logic

**Rules:**
- Wildcard `*` matches all neighbors
- Multiple qualifiers use AND logic
- Multiple selectors (comma-separated) use OR logic

**Examples:**

| Selector | Matches |
|----------|---------|
| `neighbor *` | All neighbors |
| `neighbor 192.0.2.1` | Specific IP |
| `neighbor * peer-as 65000` | All neighbors with AS 65000 |
| `neighbor 192.0.2.1 local-as 65001` | IP + local AS match |
| `neighbor 192.0.2.1, neighbor 192.0.2.2` | Either neighbor |

### Implementation

**Files:**
- `src/exabgp/reactor/api/command/limit.py` - `extract_neighbors()`, `match_neighbors()`
- All commands use same parsing/matching logic

---

## Response Parsing

### Terminator Detection

**Text mode:**
```python
complete = (
    '\ndone\n' in buffer or
    buffer.endswith('done\n') or
    '\nerror\n' in buffer or
    buffer.endswith('error\n')
)
```

**JSON mode:**
```python
import json
obj = json.loads(line)
complete = obj.get('answer') in ('done', 'error')
```

### Multi-line Responses

Responses may span multiple lines:
```
Neighbor 192.0.2.1
  ASN    65000
  State  established
Neighbor 192.0.2.2
  ASN    65001
  State  idle
done
```

**Parser must:**
1. Buffer incomplete lines until `\n` received
2. Continue until terminator found
3. Extract response content (everything before terminator)

---

## Connection Management

### Single-Client Mode

Only one CLI client can connect at a time.

**Enforcement:**
1. Server tracks active client via UUID
2. Second client receives error on ping
3. First client disconnects → second can connect

**Error message:**
```
error: Another CLI client is already connected. Please close the other client first.
error
```

### Health Monitoring

**Periodic ping:**
- Client sends `ping <uuid> <timestamp>` every 10 seconds
- Tracks consecutive failures (max 3)
- Automatic reconnection after failures

**Ping response:**
```json
{ "pong": "<daemon_uuid>", "active": true }
```

### Reconnection

**Automatic reconnection (client-side):**
1. Detect connection loss (recv returns empty)
2. Close old socket
3. Wait 2 seconds
4. Attempt reconnect (max 5 attempts)
5. Re-send initial ping
6. Resume operation

**User sees:**
```
⚠ Connection to ExaBGP daemon lost, attempting to reconnect...
  Attempt 1/5... ✓ Reconnected successfully!
✓ Reconnected to ExaBGP daemon (UUID: 12345678)
```

---

## Error Handling

### Connection Errors

**Socket not found:**
```
Could not find ExaBGP's Unix socket (exabgp.sock)
Available sockets:
 - <list of sockets>
```

**Another client connected:**
```
ERROR: Another CLI client is already connected
Only one CLI client can be active at a time.
Please close the other client first.
```

**Connection timeout:**
```
ERROR: Connection timeout
ExaBGP daemon is not responding to commands.
Try closing any other CLI clients first.
```

### Command Errors

**Unknown command:**
```
error
```

**Parse error:**
```
error: Could not parse route: invalid syntax
error
```

**JSON not supported:**
```json
{ "answer": "error", "message": "this command does not support json output" }
```

---

## Implementation Files

### Client Side (CLI)

**File:** `src/exabgp/application/cli.py`

**Key classes:**
- `PersistentSocketConnection` - Socket lifecycle, health monitoring
- `CommandCompleter` - Tab completion
- `InteractiveCLI` - REPL loop

**Key methods:**
- `_connect()` - Establish socket connection
- `_initial_ping()` - Handshake protocol
- `send_command()` - Send command, wait for response
- `_read_loop()` - Background thread reading responses
- `_health_monitor()` - Periodic health checks
- `_reconnect()` - Automatic reconnection

### Server Side (Daemon)

**File:** `src/exabgp/application/unixsocket.py`

**Key classes:**
- `Control` - Unix socket server

**Key methods:**
- `init()` - Create and bind socket
- `loop()` - Event loop forwarding messages
- `read_on()` - select.poll() for events

**File:** `src/exabgp/reactor/api/__init__.py`

**Key classes:**
- `API` - Command processing

**Key methods:**
- `process()` - Entry point from reactor
- `response()` - Command dispatch
- `answer_done()` - Send completion marker
- `answer_error()` - Send error marker

---

## Example Sessions

### Session 1: Basic Commands

```
Client: version\n
Server: exabgp 5.1.0\ndone\n

Client: help\n
Server: available API commands are listed here:\n...\ndone\n

Client: show neighbor\n
Server: Neighbor 192.0.2.1\n  State established\ndone\n
```

### Session 2: Route Announcement

```
Client: announce route 10.0.0.0/24 next-hop 192.168.1.1\n
Server: done\n

Client: withdraw route 10.0.0.0/24\n
Server: done\n
```

### Session 3: JSON Mode

```
Client: show neighbor json\n
Server: [{"peer-address":"192.0.2.1","state":"established"}]\n
Server: {"answer":"done","message":"command completed"}\n
```

### Session 4: Error Handling

```
Client: invalid-command\n
Server: error\n

Client: announce route bad-syntax\n
Server: error: Could not parse route: bad-syntax\nerror\n
```

---

## Protocol Constants

**Terminators:**
- Text success: `done\n`
- Text error: `error\n`
- JSON success: `{ "answer": "done", ... }`
- JSON error: `{ "answer": "error", ... }`

**Timeouts:**
- Initial ping: 0.5 seconds
- Command response: 5.0 seconds
- Socket recv: 0.1 seconds (non-blocking loop)
- Health check interval: 10 seconds

**Limits:**
- Max consecutive failures: 3
- Max reconnection attempts: 5
- Reconnection delay: 2 seconds

**Buffer sizes:**
- Socket recv: 4096 bytes
- Max backlog: 100 MB per source

---

**See also:**
- `CLI_INTERFACE.md` - CLI commands and interface
- `CODEBASE_ARCHITECTURE.md` - Overall architecture
- `DATA_FLOW_GUIDE.md` - Message flow

---

**Implementation:** `src/exabgp/application/{cli,unixsocket}.py`, `src/exabgp/reactor/api/`
**Updated:** 2025-11-24
