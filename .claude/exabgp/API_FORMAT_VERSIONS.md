# API Format Versions

Complete specification of ExaBGP API command formats for v4 (legacy) and v6 (current).

**See also:**
- `CLI_COMMANDS.md` - Complete command reference
- `CLI_SHORTCUTS.md` - Command shortcuts
- `UNIX_SOCKET_API.md` - Socket protocol

---

## Overview

ExaBGP supports two API versions:

| Version | Name | Command Style | Response Format | Status |
|---------|------|---------------|-----------------|--------|
| **v4** | Legacy | Action-first | JSON or Text | Deprecated |
| **v6** | Current | Target-first | JSON only | Default |

**Configuration:**
```bash
# Environment variable
exabgp_api_version=4   # Use legacy v4
exabgp_api_version=6   # Use current v6 (default)

# Configuration file
api {
    version 4;   # Use legacy v4
    version 6;   # Use current v6 (default)
}
```

---

## Version Differences

### Command Style

**v4 (Action-first):** Action/verb comes first, target is implicit or follows
```
shutdown                              # Daemon control (implicit target)
announce route 10.0.0.0/24 ...       # To ALL neighbors (implicit)
neighbor 192.168.1.1 announce ...    # To specific neighbor
```

**v6 (Target-first):** Target/category comes first, action follows
```
daemon shutdown                       # Target: daemon, action: shutdown
peer * announce route 10.0.0.0/24 ...        # Target: all peers (explicit)
peer 192.168.1.1 announce ...                # Target: specific peer
```

**Terminology:** v6 uses `peer` instead of `neighbor` for all peer-related commands.

### Selector Syntax

**v4:** Multiple selectors use comma with repeated `neighbor` keyword
```
neighbor 10.0.0.1 router-id 1.2.3.4, neighbor 10.0.0.1 announce route ...
```

**v6:** Multiple selectors use brackets with comma separation
```
peer [10.0.0.1 router-id 1.2.3.4, 10.0.0.1] announce route ...
peer [10.0.0.1, 10.0.0.2] announce route ...
peer 10.0.0.1 announce route ...      # Single peer - no brackets
peer * announce route ...             # Wildcard - no brackets
```

### Response Format

**v4:** Supports both JSON and Text encoders
```bash
exabgp_api_encoder=json   # JSON responses
exabgp_api_encoder=text   # Text responses (deprecated)
```

**v6:** JSON only
```bash
# Text encoder setting is ignored in v6
# All responses are JSON format
```

### Key Principle

**v4 mode exercises v6 code internally:**
1. Receive v4 command
2. Transform to v6 format
3. Parse with v6 parser
4. Generate v6 response
5. Transform to v4 response format

This ensures both APIs share the same core implementation.

---

## v4 Format Specification (Legacy)

v4 uses action-first syntax. Commands start with an action verb.

### Daemon Control

```
shutdown                    # Stop daemon
reload                      # Reload configuration
restart                     # Restart daemon
status                      # Show daemon status
```

### Session Management

```
enable-ack                  # Enable "done" acknowledgments
disable-ack                 # Disable "done" for next command
silence-ack                 # Disable "done" permanently
enable-sync                 # Wait for wire transmission before ACK
disable-sync                # ACK immediately after RIB update
reset                       # Clear async command queue
ping [uuid timestamp]       # Health check / keepalive
bye                         # Disconnect from socket
```

### System Commands

```
help                        # Show available commands
version                     # Show ExaBGP version
crash                       # Crash daemon (debug only)
queue-status                # Show command queue status
api version [4|6]           # Show or set API version
```

### RIB Operations

```
show adj-rib in [<ip>]              # Show received routes
show adj-rib out [<ip>]             # Show advertised routes
flush adj-rib out [<ip>]            # Clear advertised routes
clear adj-rib in [<ip>]             # Clear received routes
clear adj-rib out [<ip>]            # Clear advertised routes
```

### Neighbor Operations

```
show neighbor [<ip>] [summary|extensive]    # Show neighbor info
teardown [<code>]                           # Teardown ALL neighbors
neighbor <ip> teardown [<code>]             # Teardown specific neighbor
```

### Route Announcements (neighbor prefix optional for ALL)

```
# To ALL neighbors (no neighbor prefix)
announce route <prefix> next-hop <ip> [attributes...]
announce ipv4 <safi> <prefix> [attributes...]
announce ipv6 <safi> <prefix> [attributes...]
announce vpls <specification> [attributes...]
announce flow route <match> then <action>
announce attribute [attributes...]
announce attributes [attributes...]
announce eor <afi> <safi>
announce route-refresh <afi> <safi>
announce operational <specification>
announce watchdog <name>

# To SPECIFIC neighbor (neighbor prefix required)
neighbor <ip> announce route <prefix> next-hop <ip> [attributes...]
neighbor <ip> announce eor <afi> <safi>
# ... etc

# Comma-separated selectors (multiple filters combined)
# Each filter repeats 'neighbor' keyword; command applies to neighbors matching ALL filters
neighbor <ip1> <key1> <val1>, neighbor <ip2> announce route <prefix> ...
neighbor 10.0.0.1 router-id 1.2.3.4, neighbor 10.0.0.1 announce route 1.0.0.0/8 next-hop 10.0.0.254
```

### Route Withdrawals (neighbor prefix optional for ALL)

```
# From ALL neighbors (no neighbor prefix)
withdraw route <prefix> [attributes...]
withdraw ipv4 <safi> <prefix> [attributes...]
withdraw ipv6 <safi> <prefix> [attributes...]
withdraw vpls <specification>
withdraw flow route <match>
withdraw attribute [attributes...]
withdraw attributes [attributes...]
withdraw watchdog <name>

# From SPECIFIC neighbor (neighbor prefix required)
neighbor <ip> withdraw route <prefix> [attributes...]
# ... etc
```

### Peer Management (v4 syntax)

```
create neighbor <ip> { <configuration> }    # Create dynamic peer
delete neighbor <ip>                        # Delete dynamic peer
```

### Comments

```
# <comment text>                 # Ignored by API
```

---

## v6 Format Specification (Current)

v6 uses target-first syntax. Commands are organized by target category.
**Note:** v6 uses `peer` instead of `neighbor` for all peer-related commands.

### Daemon Control

```
daemon shutdown             # Stop daemon
daemon reload               # Reload configuration
daemon restart              # Restart daemon
daemon status               # Show daemon status
```

### Session Management

```
session ack enable          # Enable "done" acknowledgments
session ack disable         # Disable "done" for next command
session ack silence         # Disable "done" permanently
session sync enable         # Wait for wire transmission before ACK
session sync disable        # ACK immediately after RIB update
session reset               # Clear async command queue
session ping [uuid timestamp]   # Health check / keepalive
session bye                 # Disconnect from socket
```

### System Commands

```
system help                 # Show available commands
system version              # Show ExaBGP version
system crash                # Crash daemon (debug only)
system queue-status         # Show command queue status
system api version [4|6]    # Show or set API version
```

### RIB Operations

```
rib show in [peer <ip>]             # Show received routes
rib show out [peer <ip>]            # Show advertised routes
rib flush out [peer <ip>]           # Clear advertised routes
rib clear in [peer <ip>]            # Clear received routes
rib clear out [peer <ip>]           # Clear advertised routes
```

### Peer Operations

```
peer show [<ip>] [summary|extensive]        # Show peer info
peer * teardown [<code>]                    # Teardown ALL peers
peer <ip> teardown [<code>]                 # Teardown specific peer
```

### Route Announcements (peer prefix ALWAYS required)

```
# To ALL peers (explicit wildcard)
peer * announce route <prefix> next-hop <ip> [attributes...]
peer * announce ipv4 <safi> <prefix> [attributes...]
peer * announce ipv6 <safi> <prefix> [attributes...]
peer * announce vpls <specification> [attributes...]
peer * announce flow route <match> then <action>
peer * announce attribute [attributes...]
peer * announce attributes [attributes...]
peer * announce eor <afi> <safi>
peer * announce route refresh <afi> <safi>
peer * announce operational <specification>
peer * announce watchdog <name>

# To SPECIFIC peer
peer <ip> announce route <prefix> next-hop <ip> [attributes...]
peer <ip> announce eor <afi> <safi>
# ... etc

# With filters
peer <ip> peer-as <asn> announce route <prefix> ...
peer * local-as <asn> announce route <prefix> ...

# Multiple selectors - use brackets with comma separation
peer [<ip1> <key1> <val1>, <ip2>] announce route <prefix> ...
peer [10.0.0.1 router-id 1.2.3.4, 10.0.0.1] announce route 1.0.0.0/8 next-hop 10.0.0.254
peer [10.0.0.1, 10.0.0.2] announce route 1.0.0.0/8 next-hop 10.0.0.254
```

### Route Withdrawals (peer prefix ALWAYS required)

```
# From ALL peers (explicit wildcard)
peer * withdraw route <prefix> [attributes...]
peer * withdraw ipv4 <safi> <prefix> [attributes...]
peer * withdraw ipv6 <safi> <prefix> [attributes...]
peer * withdraw vpls <specification>
peer * withdraw flow route <match>
peer * withdraw attribute [attributes...]
peer * withdraw attributes [attributes...]
peer * withdraw watchdog <name>

# From SPECIFIC peer
peer <ip> withdraw route <prefix> [attributes...]
# ... etc
```

### Peer Management

```
peer create <ip> { <configuration> }    # Create dynamic peer
peer delete <ip>                        # Delete dynamic peer
```

### Comments

```
# <comment text>                 # Ignored by API
```

---

## Command Mapping Table

### Commands that CHANGE between versions

| v4 (Legacy) | v6 (Current) | Category |
|-------------|--------------|----------|
| `shutdown` | `daemon shutdown` | daemon |
| `reload` | `daemon reload` | daemon |
| `restart` | `daemon restart` | daemon |
| `status` | `daemon status` | daemon |
| `enable-ack` | `session ack enable` | session |
| `disable-ack` | `session ack disable` | session |
| `silence-ack` | `session ack silence` | session |
| `enable-sync` | `session sync enable` | session |
| `disable-sync` | `session sync disable` | session |
| `reset` | `session reset` | session |
| `ping` | `session ping` | session |
| `bye` | `session bye` | session |
| `help` | `system help` | system |
| `version` | `system version` | system |
| `crash` | `system crash` | system |
| `queue-status` | `system queue-status` | system |
| `api version` | `system api version` | system |
| `show adj-rib in` | `rib show in` | rib |
| `show adj-rib out` | `rib show out` | rib |
| `flush adj-rib out` | `rib flush out` | rib |
| `clear adj-rib in` | `rib clear in` | rib |
| `clear adj-rib out` | `rib clear out` | rib |
| `show neighbor` | `peer show` | peer |
| `teardown` | `peer * teardown` | peer |
| `announce route-refresh` | `peer * announce route refresh` | route |
| `announce route ...` | `peer * announce route ...` | route |
| `withdraw route ...` | `peer * withdraw route ...` | route |
| `announce ipv4 ...` | `peer * announce ipv4 ...` | route |
| `withdraw ipv4 ...` | `peer * withdraw ipv4 ...` | route |
| `announce ipv6 ...` | `peer * announce ipv6 ...` | route |
| `withdraw ipv6 ...` | `peer * withdraw ipv6 ...` | route |
| `announce vpls ...` | `peer * announce vpls ...` | route |
| `withdraw vpls ...` | `peer * withdraw vpls ...` | route |
| `announce flow ...` | `peer * announce flow ...` | route |
| `withdraw flow ...` | `peer * withdraw flow ...` | route |
| `announce attribute ...` | `peer * announce attribute ...` | route |
| `announce attributes ...` | `peer * announce attributes ...` | route |
| `withdraw attribute ...` | `peer * withdraw attribute ...` | route |
| `withdraw attributes ...` | `peer * withdraw attributes ...` | route |
| `announce eor ...` | `peer * announce eor ...` | route |
| `announce operational ...` | `peer * announce operational ...` | route |
| `announce watchdog ...` | `peer * announce watchdog ...` | route |
| `withdraw watchdog ...` | `peer * withdraw watchdog ...` | route |
| `create neighbor ...` | `peer create ...` | peer |
| `delete neighbor ...` | `peer delete ...` | peer |

### Commands that TRANSFORM (v4 neighbor → v6 peer)

| v4 Command | v6 Command | Notes |
|------------|------------|-------|
| `neighbor <ip> announce ...` | `peer <ip> announce ...` | neighbor → peer |
| `neighbor <ip> withdraw ...` | `peer <ip> withdraw ...` | neighbor → peer |
| `neighbor <ip> teardown ...` | `peer <ip> teardown ...` | neighbor → peer |
| `#` (comment) | `#` (comment) | Unchanged |

### v6-only Commands (no v4 equivalent)

| v6 Command | Category | Notes |
|------------|----------|-------|
| `peer create ...` | peer | New in v6 |
| `peer delete ...` | peer | New in v6 |

---

## Transformation Rules

### v4 → v6 Transformation (Input Processing)

When API version is v4, incoming commands are transformed to v6 format before parsing.

**Order matters:** Apply longer patterns first to avoid partial matches.

```python
TRANSFORMS = [
    # Daemon control (exact match at start)
    (r'^shutdown\b', 'daemon shutdown'),
    (r'^reload\b', 'daemon reload'),
    (r'^restart\b', 'daemon restart'),
    (r'^status\b', 'daemon status'),

    # Session management (exact match at start)
    (r'^enable-ack\b', 'session ack enable'),
    (r'^disable-ack\b', 'session ack disable'),
    (r'^silence-ack\b', 'session ack silence'),
    (r'^enable-sync\b', 'session sync enable'),
    (r'^disable-sync\b', 'session sync disable'),
    (r'^reset\b', 'session reset'),
    (r'^ping\b', 'session ping'),
    (r'^bye\b', 'session bye'),

    # System commands (exact match at start)
    (r'^help\b', 'system help'),
    (r'^version\b', 'system version'),
    (r'^crash\b', 'system crash'),
    (r'^queue-status\b', 'system queue-status'),
    (r'^api version\b', 'system api version'),

    # RIB operations (multi-word patterns first)
    (r'^show adj-rib in\b', 'rib show in'),
    (r'^show adj-rib out\b', 'rib show out'),
    (r'^flush adj-rib out\b', 'rib flush out'),
    (r'^clear adj-rib in\b', 'rib clear in'),
    (r'^clear adj-rib out\b', 'rib clear out'),

    # Neighbor operations
    (r'^show neighbor\b', 'neighbor show'),
    (r'^teardown\b', 'neighbor * teardown'),

    # Peer management
    (r'^create neighbor\b', 'peer create'),
    (r'^delete neighbor\b', 'peer delete'),

    # Route refresh (before generic announce)
    (r'^announce route-refresh\b', 'neighbor * announce route refresh'),

    # Announce/Withdraw - add 'neighbor *' prefix if not already present
    # These must be LAST to avoid matching commands that already have neighbor prefix
    (r'^announce\b', 'neighbor * announce'),
    (r'^withdraw\b', 'neighbor * withdraw'),
]
```

**Special case:** Commands starting with `neighbor ` are NOT transformed (already have selector).

### v6 → v4 Transformation (Output Processing)

When API version is v4, responses may need format conversion:

1. **JSON responses:** Wrap in v4 compatibility layer
2. **Text responses:** Use v4 text encoder

**Response differences:**
- v4: May include `exabgp` version prefix in messages
- v6: Clean JSON-only output

---

## Implementation Files

### Input Processing (Command Parsing)

| File | Purpose |
|------|---------|
| `src/exabgp/reactor/api/transform.py` | v4→v6 command transformation |
| `src/exabgp/reactor/api/__init__.py` | API entry point, applies transformation |
| `src/exabgp/reactor/api/command/*.py` | Command handlers (v6 format) |

### Output Processing (Response Encoding)

| File | Purpose |
|------|---------|
| `src/exabgp/reactor/api/response/__init__.py` | Response encoder registry |
| `src/exabgp/reactor/api/response/json.py` | v6 JSON encoder |
| `src/exabgp/reactor/api/response/text.py` | v6 Text encoder (deprecated) |
| `src/exabgp/reactor/api/response/v4/json.py` | v4 JSON wrapper |
| `src/exabgp/reactor/api/response/v4/text.py` | v4 Text wrapper |

### Configuration

| File | Purpose |
|------|---------|
| `src/exabgp/environment/config.py` | `ApiSection.version` option |
| `src/exabgp/environment/parsing.py` | `api_version()` parser |

---

## JSON Output Format Differences

Beyond command syntax, v4 and v6 differ in **JSON output format** for certain NLRI types.

### nexthop in NLRI

**v4:** Includes `next-hop` field in NLRI objects for backward compatibility
**v6:** Excludes `next-hop` from NLRI (available in grouping key instead)

**Example - Flow NLRI:**

```json
// v4 format (v4_json)
{
  "string": "flow destination 10.0.0.0/24",
  "next-hop": "1.2.3.4",
  "destination-ipv4": ["10.0.0.0/24"]
}

// v6 format (json)
{
  "string": "flow destination 10.0.0.0/24",
  "destination-ipv4": ["10.0.0.0/24"]
}
// nexthop is in the grouping key: "ipv4 flow": {"1.2.3.4": [...]}
```

**Rationale:** nexthop is not part of NLRI identity (two routes with same prefix but different nexthops are different routes). v6 places nexthop in the JSON grouping structure.

**Affected NLRI types:**
- Flow (FlowSpec)
- BGP-LS (node, prefixv4, prefixv6)

### Implementation Pattern

NLRI classes implement two methods:
- `json()` - v6 format (no nexthop)
- `v4_json(nexthop)` - v4 format (includes nexthop if provided)

The encoder uses `use_v4_json` flag to select which method to call.

---

## Migration Guide

### From v4 to v6

**1. Update command syntax:**
```bash
# Before (v4)
announce route 10.0.0.0/24 next-hop 1.2.3.4

# After (v6)
neighbor * announce route 10.0.0.0/24 next-hop 1.2.3.4
```

**2. Update daemon control:**
```bash
# Before (v4)
shutdown

# After (v6)
daemon shutdown
```

**3. Remove text encoder dependency:**
```bash
# v4 allowed:
exabgp_api_encoder=text

# v6 ignores this, always JSON
```

**4. Update scripts:**
- Parse JSON responses instead of text
- Use structured data instead of regex parsing

### Backward Compatibility

**To maintain v4 compatibility:**
```bash
exabgp_api_version=4
```

This enables:
- v4 command syntax
- Text encoder option
- v4-style responses

**Deprecation warning:** v4 is deprecated and will be removed in a future release.

---

## Examples

### v4 Session Example

```bash
$ echo "version" | exabgp-cli
exabgp 4.0.1

$ echo "show neighbor summary" | exabgp-cli
neighbor 192.168.1.1 up established

$ echo "announce route 10.0.0.0/24 next-hop 1.2.3.4" | exabgp-cli
done
```

### v6 Session Example

```bash
$ echo "system version" | exabgp-cli
{"version": "6.0.0", "api": "6.0.0"}

$ echo "neighbor show summary" | exabgp-cli
{"neighbors": [{"ip": "192.168.1.1", "state": "established"}]}

$ echo "neighbor * announce route 10.0.0.0/24 next-hop 1.2.3.4" | exabgp-cli
{"status": "ok"}
```

---

**Updated:** 2025-12-18
