# CLI Commands Reference

Complete reference for all ExaBGP CLI commands, syntax, and usage patterns.

**See also:**
- `CLI_SHORTCUTS.md` - Command shortcuts reference
- `CLI_IMPLEMENTATION.md` - Internal architecture
- `UNIX_SOCKET_API.md` - Unix socket API protocol
- `NEIGHBOR_SELECTOR_SYNTAX.md` - Neighbor selector syntax

---

## Command Syntax

### General Format

```
[display_mode] <command> [neighbor_selector] [options]
```

**Components:**

- **display_mode** (optional): `json` or `text` - Override display mode for this command
- **command**: Base command (show, announce, withdraw, etc.)
- **neighbor_selector** (optional): Target specific neighbors - see Neighbor Selectors below
- **options**: Command-specific options and parameters

### API Syntax

**The ExaBGP API uses two command patterns:**

#### 1. Commands to ALL neighbors (no filter)

```
<action> <object> <modifiers>
```

**Examples:**
```bash
announce route 10.0.0.0/24 next-hop 192.168.1.1       # To all neighbors
withdraw route 10.0.0.0/24                             # From all neighbors
announce eor ipv4 unicast                              # To all neighbors
```

#### 2. Commands to SPECIFIC neighbors (with filter)

```
neighbor <ip> [qualifiers] <action> <object> <modifiers>
```

**The `neighbor` keyword is a FILTER that limits which peers receive the command.**

**Examples:**
```bash
neighbor 192.168.1.1 announce route 10.0.0.0/24 next-hop self
neighbor 192.168.1.1 withdraw route 10.0.0.0/24
neighbor 192.168.1.1 teardown 6
neighbor * peer-as 65000 announce eor ipv4 unicast    # All neighbors with AS 65000
```

#### 3. Show commands - CLI transformation

**API syntax (action-first):**
```bash
# show neighbor
show neighbor                           # All neighbors
show neighbor 192.168.1.1 summary       # Specific neighbor (IP after command)

# show adj-rib
show adj-rib in                         # All neighbors
show adj-rib in 192.168.1.1             # Specific neighbor (IP after direction)
show adj-rib out 192.168.1.1            # Specific neighbor
```

**CLI-only syntax (filter-first) - TRANSFORMED to API:**
```bash
neighbor 192.168.1.1 show summary       → show neighbor 192.168.1.1 summary
neighbor 192.168.1.1 adj-rib in show    → show adj-rib in 192.168.1.1
adj-rib in show                         → show adj-rib in
```

**Transformation:** `src/exabgp/application/shortcuts.py:transform_cli_to_api()`

**Important differences:**
- **show neighbor/adj-rib** - API accepts IP after command: `show adj-rib in <ip>`
- **announce/withdraw/teardown** - API requires `neighbor <ip>` prefix: `neighbor <ip> announce ...`
- **CLI filter-first syntax** (`neighbor <ip> show`) - Transformed to API syntax

**Summary:**
- **API show commands** - `show <object> [<direction>] [<ip>] <modifiers>`
- **API other commands** - `neighbor <ip> <action> <object> <modifiers>` (filter prefix required)
- **CLI** - Accepts both patterns, transforms filter-first to action-first for `show`

### Display Modes

**Two independent settings:**

1. **API encoding** (`set encoding json|text`) - Controls API response format
2. **Display mode** (`set display json|text`) - Controls CLI output formatting

**Per-command override:**
```bash
json show neighbor      # Display as JSON (overrides setting)
text show neighbor      # Display as text tables (overrides setting)
```

### Neighbor Selectors

Target specific neighbors using qualifiers:

```
neighbor <ip> [qualifier ...]
```

**Qualifiers:**
- `neighbor <ip>` - Specific neighbor IP (required)
- `local-ip <ip>` - Filter by local IP
- `local-as <asn>` - Filter by local AS
- `peer-as <asn>` - Filter by peer AS
- `router-id <ip>` - Filter by router ID
- `family-allowed <afi> <safi>` - Filter by address family

**Examples:**
```bash
show neighbor 192.168.1.1 summary
announce route 10.0.0.0/24 neighbor 192.168.1.1 next-hop 1.1.1.1
teardown neighbor 10.0.0.1 peer-as 65000
```

**Full syntax:** `.claude/docs/reference/NEIGHBOR_SELECTOR_SYNTAX.md`

---

## All Commands (47 Total)

### Control Commands (16)

Commands for daemon control and management.

**File:** `src/exabgp/reactor/api/command/reactor.py`

#### help

Show available commands.

**Syntax:**
```bash
help
```

**Returns:** List of all available commands with descriptions (JSON or text)

**Example:**
```bash
exabgp> help
exabgp> json help    # JSON format
```

---

#### version

Show ExaBGP version.

**Syntax:**
```bash
version
```

**Returns:** Version string and build information

**Example:**
```bash
exabgp> version
```

---

#### shutdown

Shutdown ExaBGP daemon.

**Syntax:**
```bash
shutdown
```

**Returns:** Confirmation message

**Example:**
```bash
exabgp> shutdown
```

---

#### reload

Reload configuration file.

**Syntax:**
```bash
reload
```

**Returns:** Status message

**Example:**
```bash
exabgp> reload
```

---

#### restart

Restart ExaBGP daemon.

**Syntax:**
```bash
restart
```

**Returns:** Status message

**Example:**
```bash
exabgp> restart
```

---

#### reset

Clear async command queue.

**Syntax:**
```bash
reset
```

**Returns:** Status message

**Example:**
```bash
exabgp> reset
```

---

#### ping

Health check / keepalive.

**Syntax:**
```bash
ping [<uuid> <timestamp>]
```

**Parameters:**
- `uuid` (optional) - Client UUID for single-client enforcement
- `timestamp` (optional) - Client timestamp

**Returns:** Pong response with server timestamp

**Example:**
```bash
exabgp> ping
exabgp> ping 550e8400-e29b-41d4-a716-446655440000 1732412345
```

**Note:** CLI automatically sends periodic pings (10-second interval) for health monitoring.

---

#### status

Show daemon status.

**Syntax:**
```bash
status
```

**Returns:** Daemon state information

**Example:**
```bash
exabgp> status
```

---

#### bye

Disconnect from socket (CLI exits).

**Syntax:**
```bash
bye
```

**Returns:** Disconnection confirmation

**Example:**
```bash
exabgp> bye
```

---

#### # (comment)

Comment line (ignored by API).

**Syntax:**
```bash
# <comment text>
```

**Returns:** Nothing (command ignored)

**Example:**
```bash
exabgp> # This is a comment
```

---

#### crash

Crash daemon (debug only).

**Syntax:**
```bash
crash
```

**Returns:** None (daemon crashes)

**Example:**
```bash
exabgp> crash
```

**Warning:** Debug command only. Immediately crashes daemon.

---

#### enable-ack

Enable "done" acknowledgment responses.

**Syntax:**
```bash
enable-ack
```

**Returns:** Confirmation

**Example:**
```bash
exabgp> enable-ack
```

**Note:** When enabled, API sends "done" after completing commands.

---

#### disable-ack

Disable "done" responses for next command only.

**Syntax:**
```bash
disable-ack
```

**Returns:** Nothing

**Example:**
```bash
exabgp> disable-ack
exabgp> announce route 10.0.0.0/24 next-hop 1.1.1.1   # No "done" response
```

---

#### silence-ack

Disable "done" responses immediately and permanently.

**Syntax:**
```bash
silence-ack
```

**Returns:** Nothing (this is the last acknowledgment)

**Example:**
```bash
exabgp> silence-ack
```

**Note:** Disables acknowledgments immediately. Use `enable-ack` to re-enable.

---

#### enable-sync

Enable sync mode - wait for routes to be flushed to wire before ACK.

**Syntax:**
```bash
enable-sync
```

**Returns:** Confirmation

**Example:**
```bash
exabgp> enable-sync
```

**Note:** When sync mode is enabled, `announce`/`withdraw` commands wait until the routes have been sent on the wire to the BGP peer before returning the "done" response. This allows API processes to know when routes have actually been transmitted.

---

#### disable-sync

Disable sync mode - ACK immediately after RIB update (default).

**Syntax:**
```bash
disable-sync
```

**Returns:** Confirmation

**Example:**
```bash
exabgp> disable-sync
```

**Note:** When sync mode is disabled (default), `announce`/`withdraw` commands return "done" immediately after the route is added to the RIB, without waiting for it to be sent on the wire.

---

### Neighbor Commands (4)

Commands for neighbor/peer management.

**Files:**
- `src/exabgp/reactor/api/command/neighbor.py`
- `src/exabgp/reactor/api/command/peer.py`

#### show neighbor

Show neighbor information.

**Syntax:**
```bash
show neighbor [selector] [options]
```

**Options:**
- `summary` - Brief status (default)
- `extensive` - Detailed information
- `configuration` - Show configuration
- `json` - JSON format

**Selectors:** See Neighbor Selectors section above

**Returns:** Neighbor information in requested format

**Examples:**
```bash
exabgp> show neighbor summary
exabgp> show neighbor 192.168.1.1 extensive
exabgp> show neighbor peer-as 65000 summary
exabgp> json show neighbor
```

---

#### teardown

Gracefully shutdown neighbor connection.

**Syntax:**
```bash
teardown [neighbor_selector] [notification_code]
```

**Parameters:**
- `notification_code` (optional) - BGP notification code (default: 6 = Cease)

**Selectors:** See Neighbor Selectors section above

**Returns:** Confirmation

**Examples:**
```bash
# Teardown specific neighbor
exabgp> neighbor 192.168.1.1 teardown

# Teardown with notification code
exabgp> neighbor 10.0.0.1 teardown 6

# Teardown by peer-as selector
exabgp> neighbor * peer-as 65000 teardown
```

**Notification codes:**
- 1 = Message Header Error
- 2 = OPEN Message Error
- 3 = UPDATE Message Error
- 4 = Hold Timer Expired
- 5 = Finite State Machine Error
- 6 = Cease (default)

---

#### create

Create peer dynamically (API-style).

**Syntax:**
```bash
create <peer_definition>
```

**Parameters:**
- `peer_definition` - Full peer configuration in API format

**Returns:** Confirmation or error

**Example:**
```bash
exabgp> create neighbor 192.168.1.1 { router-id 1.1.1.1; local-as 65000; peer-as 65001; }
```

**Note:** API-style command. Requires complete peer configuration syntax.

**File:** `src/exabgp/reactor/api/command/peer.py`

---

#### delete

Delete peer dynamically (API-style).

**Syntax:**
```bash
delete neighbor <ip>
```

**Parameters:**
- `ip` - Neighbor IP address

**Returns:** Confirmation or error

**Example:**
```bash
exabgp> delete neighbor 192.168.1.1
```

**File:** `src/exabgp/reactor/api/command/peer.py`

---

### Route Announcements (10)

Commands for announcing routes and BGP messages.

**File:** `src/exabgp/reactor/api/command/announce.py`

#### announce route

Announce IPv4/IPv6 route.

**Syntax:**
```bash
announce route <prefix> [neighbor_selector] [attributes]
```

**Attributes:**
- `next-hop <ip>` - Next-hop address (required for most cases)
- `as-path [<asn> ...]` - AS path
- `origin [igp|egp|incomplete]` - Origin attribute
- `local-preference <value>` - Local preference
- `med <value>` - Multi-Exit Discriminator
- `community <value>` - BGP community
- `extended-community <value>` - Extended community
- `large-community <value>` - Large community
- `path-information <value>` - Path ID (AddPath)
- `label <value>` - MPLS label
- `rd <value>` - Route distinguisher (VPN)
- Many more (see BGP attribute specs)

**Examples:**
```bash
# Announce to all neighbors
exabgp> announce route 10.0.0.0/24 next-hop 192.168.1.1

# Announce with AS path
exabgp> announce route 10.1.0.0/24 next-hop 1.1.1.1 as-path [65000 65001]

# Announce to specific neighbor
exabgp> neighbor 192.168.1.1 announce route 10.2.0.0/24 next-hop self

# IPv6 route
exabgp> announce route 2001:db8::/32 next-hop 2001:db8::1
```

---

#### announce ipv4

Announce IPv4 route (explicit AFI).

**Syntax:**
```bash
announce ipv4 <safi> <prefix> [neighbor_selector] [attributes]
```

**SAFIs:**
- `unicast` - IPv4 unicast
- `multicast` - IPv4 multicast
- `mpls-vpn` - VPNv4
- `flow` - FlowSpec
- `flow-vpn` - FlowSpec VPN

**Examples:**
```bash
exabgp> announce ipv4 unicast 10.0.0.0/24 next-hop 192.168.1.1
exabgp> announce ipv4 mpls-vpn 10.1.0.0/24 next-hop 1.1.1.1 rd 65000:1 label 100
```

---

#### announce ipv6

Announce IPv6 route (explicit AFI).

**Syntax:**
```bash
announce ipv6 <safi> <prefix> [neighbor_selector] [attributes]
```

**SAFIs:**
- `unicast` - IPv6 unicast
- `multicast` - IPv6 multicast
- `mpls-vpn` - VPNv6
- `flow` - FlowSpec v6
- `flow-vpn` - FlowSpec VPN v6

**Examples:**
```bash
exabgp> announce ipv6 unicast 2001:db8::/32 next-hop 2001:db8::1
exabgp> announce ipv6 mpls-vpn 2001:db8:1::/48 next-hop ::ffff:1.1.1.1 rd 65000:1
```

---

#### announce vpls

Announce VPLS route.

**Syntax:**
```bash
announce vpls <specification> [neighbor_selector] [attributes]
```

**Examples:**
```bash
exabgp> announce vpls endpoint 10 offset 20 size 8 base 203
```

---

#### announce flow

Announce FlowSpec rule.

**Syntax:**
```bash
announce flow route <match_conditions> then <actions>
```

**Match conditions:**
- `destination <prefix>` - Destination prefix
- `source <prefix>` - Source prefix
- `port <value>` - Port number
- `protocol <value>` - IP protocol
- Many more flow match types

**Actions:**
- `discard` - Drop traffic
- `rate-limit <bps>` - Rate limit
- `redirect <target>` - Redirect to VRF
- `mark <dscp>` - Mark DSCP

**Examples:**
```bash
exabgp> announce flow route destination 10.0.0.0/24 protocol tcp port =80 then discard
exabgp> announce flow route source 192.168.0.0/16 then rate-limit 1000000
```

---

#### announce attribute / announce attributes

Announce BGP attributes only (no NLRI).

**Syntax:**
```bash
announce attribute [neighbor_selector] <attributes>
announce attributes [neighbor_selector] <attributes>
```

**Examples:**
```bash
exabgp> announce attribute next-hop 192.168.1.1 as-path [65000 65001]
exabgp> announce attributes neighbor 10.0.0.1 local-preference 200
```

---

#### announce eor

Send End-of-RIB marker.

**Syntax:**
```bash
announce eor <afi> <safi> [neighbor_selector]
```

**AFIs:**
- `ipv4` - IPv4 AFI
- `ipv6` - IPv6 AFI

**SAFIs:**
- `unicast` - Unicast SAFI
- `multicast` - Multicast SAFI
- `mpls-vpn` - MPLS VPN SAFI
- `flow` - FlowSpec SAFI
- `flow-vpn` - FlowSpec VPN SAFI

**Examples:**
```bash
# Send EOR to all neighbors
exabgp> announce eor ipv4 unicast

# Send EOR to specific neighbor
exabgp> neighbor 192.168.1.1 announce eor ipv6 unicast

# Send EOR for VPNv4
exabgp> announce eor ipv4 mpls-vpn
```

**Note:** Signals completion of initial route advertisement for address family.

---

#### announce route-refresh

Request route refresh from peer.

**Syntax:**
```bash
announce route-refresh <afi> <safi> [neighbor_selector]
```

**AFIs/SAFIs:** Same as announce eor

**Examples:**
```bash
exabgp> announce route-refresh ipv4 unicast
exabgp> announce route-refresh ipv6 unicast neighbor 192.168.1.1
```

**Note:** Requests peer to resend all routes for specified address family.

---

#### announce operational

Send operational message.

**Syntax:**
```bash
announce operational <afi> <specification> [neighbor_selector]
```

**Examples:**
```bash
exabgp> announce operational asm 65000:1 query 0xdeadbeef
```

**Note:** Advanced feature for operational messages (ASM, ADM).

---

#### announce watchdog

Announce watchdog (process monitoring).

**Syntax:**
```bash
announce watchdog <name> [neighbor_selector]
```

**Parameters:**
- `name` - Watchdog process name

**Examples:**
```bash
exabgp> announce watchdog healthcheck
exabgp> announce watchdog myapp neighbor 192.168.1.1
```

**File:** `src/exabgp/reactor/api/command/watchdog.py`

---

### Route Withdrawals (7)

Commands for withdrawing routes and BGP messages.

**File:** `src/exabgp/reactor/api/command/announce.py` (same file as announcements)

#### withdraw route

Withdraw IPv4/IPv6 route.

**Syntax:**
```bash
withdraw route <prefix> [neighbor_selector] [path-information <id>]
```

**Examples:**
```bash
# Withdraw from all neighbors
exabgp> withdraw route 10.0.0.0/24

# Withdraw from specific neighbor
exabgp> neighbor 192.168.1.1 withdraw route 10.1.0.0/24

# IPv6 withdraw
exabgp> withdraw route 2001:db8::/32

# Withdraw with AddPath ID
exabgp> withdraw route 10.0.0.0/24 path-information 5
```

---

#### withdraw ipv4

Withdraw IPv4 route (explicit AFI).

**Syntax:**
```bash
withdraw ipv4 <safi> <prefix> [neighbor_selector] [attributes]
```

**Examples:**
```bash
exabgp> withdraw ipv4 unicast 10.0.0.0/24
exabgp> withdraw ipv4 mpls-vpn 10.1.0.0/24 rd 65000:1
```

---

#### withdraw ipv6

Withdraw IPv6 route (explicit AFI).

**Syntax:**
```bash
withdraw ipv6 <safi> <prefix> [neighbor_selector] [attributes]
```

**Examples:**
```bash
exabgp> withdraw ipv6 unicast 2001:db8::/32
```

---

#### withdraw vpls

Withdraw VPLS route.

**Syntax:**
```bash
withdraw vpls <specification> [neighbor_selector]
```

**Examples:**
```bash
exabgp> withdraw vpls endpoint 10 offset 20 size 8 base 203
```

---

#### withdraw flow

Withdraw FlowSpec rule.

**Syntax:**
```bash
withdraw flow route <match_conditions>
```

**Examples:**
```bash
exabgp> withdraw flow route destination 10.0.0.0/24 protocol tcp port =80
```

---

#### withdraw attribute / withdraw attributes

Withdraw BGP attributes.

**Syntax:**
```bash
withdraw attribute [neighbor_selector] <attributes>
withdraw attributes [neighbor_selector] <attributes>
```

**Examples:**
```bash
exabgp> withdraw attribute next-hop 192.168.1.1
```

---

#### withdraw watchdog

Withdraw watchdog.

**Syntax:**
```bash
withdraw watchdog <name> [neighbor_selector]
```

**Examples:**
```bash
exabgp> withdraw watchdog healthcheck
```

**File:** `src/exabgp/reactor/api/command/watchdog.py`

---

### RIB Operations (4)

Commands for Adj-RIB management.

**File:** `src/exabgp/reactor/api/command/rib.py`

#### show adj-rib in

Show Adj-RIB-In (received routes).

**Syntax:**
```bash
show adj-rib in [neighbor_selector] [extensive]
```

**Options:**
- `extensive` - Detailed output

**Examples:**
```bash
exabgp> show adj-rib in
exabgp> show adj-rib in neighbor 192.168.1.1
exabgp> show adj-rib in extensive
exabgp> json show adj-rib in
```

---

#### show adj-rib out

Show Adj-RIB-Out (advertised routes).

**Syntax:**
```bash
show adj-rib out [neighbor_selector] [extensive]
```

**Options:**
- `extensive` - Detailed output

**Examples:**
```bash
exabgp> show adj-rib out
exabgp> show adj-rib out neighbor 192.168.1.1
exabgp> show adj-rib out extensive
```

---

#### flush adj-rib out

Flush Adj-RIB-Out (clear advertised routes).

**Syntax:**
```bash
flush adj-rib out [neighbor_selector]
```

**Examples:**
```bash
exabgp> flush adj-rib out
exabgp> flush adj-rib out neighbor 192.168.1.1
```

**Note:** Clears advertised routes for neighbor(s).

---

#### clear adj-rib

Clear Adj-RIB (in or out).

**Syntax:**
```bash
clear adj-rib [in|out] [neighbor_selector]
```

**Examples:**
```bash
exabgp> clear adj-rib in
exabgp> clear adj-rib out
exabgp> clear adj-rib in neighbor 192.168.1.1
```

---

## Built-In CLI Commands

Commands handled by CLI itself (not sent to API).

**File:** `src/exabgp/application/cli.py`

### exit / quit

Exit CLI.

**Syntax:**
```bash
exit
quit
```

**Example:**
```bash
exabgp> exit
```

---

### clear

Clear screen.

**Syntax:**
```bash
clear
```

**Example:**
```bash
exabgp> clear
```

---

### history

Show command history.

**Syntax:**
```bash
history [<count>]
```

**Parameters:**
- `count` (optional) - Number of recent commands to show (default: all)

**Examples:**
```bash
exabgp> history
exabgp> history 10
```

---

### set

Set CLI options.

**Syntax:**
```bash
set <option> <value>
```

**Options:**

#### set encoding

Set API encoding format.

```bash
set encoding [json|text]
```

**Default:** `json`

**Examples:**
```bash
exabgp> set encoding json
exabgp> set encoding text
```

---

#### set display

Set output display format.

```bash
set display [json|text]
```

**Default:** `text` (auto-converts JSON to tables)

**Examples:**
```bash
exabgp> set display json
exabgp> set display text
```

**Note:** `text` mode auto-converts JSON responses to readable tables.

---

#### set sync

Set sync mode for announce/withdraw commands.

```bash
set sync [on|off]
```

**Default:** `off`

**Examples:**
```bash
exabgp> set sync on     # Wait for routes to be sent on wire before ACK
exabgp> set sync off    # Return ACK immediately (default)
```

**Behavior:**

- **`off` (default):** `announce`/`withdraw` commands return "done" immediately after the route is added to the RIB, without waiting for it to be transmitted to the BGP peer.

- **`on`:** `announce`/`withdraw` commands wait until the route has actually been sent on the wire to the BGP peer before returning "done". This is useful when you need to synchronize external actions with actual route transmission.

**Per-command override:**

You can override the session sync mode for individual commands by adding `sync` or `async` keyword at the end:

```bash
# Force sync for this command (regardless of session setting)
exabgp> announce route 10.0.0.0/24 next-hop 1.2.3.4 sync

# Force async for this command (regardless of session setting)
exabgp> announce route 10.0.0.0/24 next-hop 1.2.3.4 async

# Works with json/text too (order doesn't matter)
exabgp> announce route 10.0.0.0/24 next-hop 1.2.3.4 sync json
exabgp> announce route 10.0.0.0/24 next-hop 1.2.3.4 json sync
```

**Use cases:**

1. **Route verification:** Wait for route to be sent before checking peer's RIB
2. **Scripted deployments:** Ensure routes are transmitted before proceeding
3. **Testing:** Confirm exact timing of route advertisements

**API commands:** `enable-sync`, `disable-sync` (sent automatically by `set sync`)

---

## Command Categories Summary

| Category | Count | File |
|----------|-------|------|
| Control | 16 | reactor.py |
| Neighbor | 4 | neighbor.py, peer.py |
| Route Announcements | 10 | announce.py, watchdog.py |
| Route Withdrawals | 7 | announce.py, watchdog.py |
| RIB Operations | 4 | rib.py |
| Built-in CLI | 6 | cli.py |
| **Total** | **47** | |

---

## Common Workflows

### View neighbor status

```bash
exabgp> show neighbor summary
exabgp> show neighbor 192.168.1.1 extensive
```

### Announce a route

```bash
# To all neighbors
exabgp> announce route 10.0.0.0/24 next-hop 192.168.1.1

# To specific neighbor
exabgp> neighbor 192.168.1.1 announce route 10.1.0.0/24 next-hop self
```

### Withdraw a route

```bash
# From all neighbors
exabgp> withdraw route 10.0.0.0/24

# From specific neighbor
exabgp> neighbor 192.168.1.1 withdraw route 10.0.0.0/24
```

### Check received routes

```bash
# Show for specific neighbor (both syntaxes work)
exabgp> show adj-rib in 192.168.1.1
exabgp> neighbor 192.168.1.1 adj-rib in show

# JSON format
exabgp> json show adj-rib in
```

### Teardown session

```bash
# Teardown specific neighbor
exabgp> neighbor 192.168.1.1 teardown

# Teardown with code 6 = Cease
exabgp> neighbor 192.168.1.1 teardown 6

# Teardown all neighbors with AS 65000
exabgp> neighbor * peer-as 65000 teardown
```

### Send End-of-RIB

```bash
# To all neighbors
exabgp> announce eor ipv4 unicast

# To specific neighbor
exabgp> neighbor 192.168.1.1 announce eor ipv4 unicast
```

### Request route refresh

```bash
# From all neighbors
exabgp> announce route-refresh ipv4 unicast

# From specific neighbor
exabgp> neighbor 192.168.1.1 announce route-refresh ipv4 unicast
```

---

## Implementation References

**Command registration:** `src/exabgp/reactor/api/command/`
- `reactor.py` - Control commands
- `neighbor.py` - Neighbor show/teardown
- `peer.py` - Peer create/delete
- `announce.py` - Route announcements/withdrawals
- `rib.py` - Adj-RIB operations
- `watchdog.py` - Watchdog announcements

**Command metadata:** `src/exabgp/reactor/api/command/registry.py`
- `CommandRegistry` - Introspects registered commands
- `CommandMetadata` - Structured command information

**CLI implementation:** `src/exabgp/application/cli.py`
- `InteractiveCLI` - REPL loop
- `CommandCompleter` - Tab completion
- `OutputFormatter` - Display formatting
- `PersistentSocketConnection` - Socket management

**Shortcut expansion:** `src/exabgp/application/shortcuts.py`
- `CommandShortcuts` - Context-aware expansion

---

**Updated:** 2025-11-27
