# API Versioning Plan: v4 (Legacy) and v6 (New)

## Goal

Daemon accepts commands based on API version setting (NO overlap):
- **v4 mode**: Only accepts v4 commands → transforms to v6 internally → v6 parser → v4 response
- **v6 mode**: Only accepts v6 commands → v6 parser → v6 response

**No mixing**: v6 commands rejected in v4 mode, v4 commands rejected in v6 mode.

**Key Principle**: v4 exercises v6 code (both input and output).

**Key Terminology Change**: v6 uses `peer` instead of `neighbor` for all peer-related commands.

## Phase 1: Documentation ✅ COMPLETED

**Status:** Documentation created at `.claude/exabgp/API_FORMAT_VERSIONS.md`

## Phase 2: Implementation

### Step 1: Create v4→v6 Transformation Module ✅ COMPLETED

**File:** `src/exabgp/reactor/api/transform.py`

**Features:**
- Hierarchical dispatch tree for efficient O(1) lookup
- Full parsing of `neighbor` commands with selector validation
- Explicit enumeration of all announce/withdraw subcommands
- Transforms v4 `neighbor` to v6 `peer`
- Raises `ValueError` for invalid commands

**Tests:** 70 unit tests in `tests/unit/test_api_transform.py`

### Step 2: Fix Existing Bug ✅ COMPLETED

**File:** `src/exabgp/reactor/api/processes.py`

Fixed per-process encoder selection (was using global setting).

### Step 3: Register v6 Commands in Daemon ✅ COMPLETED

**File:** `src/exabgp/reactor/api/command/v6.py`

Created v6 command alias registration:
- Maps 67 v6 command names to v4 handlers
- Includes both `peer *` and `peer` forms for announce/withdraw
- Registered via `register_v6_commands()` in `command/__init__.py`

### Step 4: Add Transformation Call in API Processing ✅ COMPLETED

**File:** `src/exabgp/reactor/api/__init__.py`

Updated `process()` and `process_async()` methods:
- v4 mode: Transform command using `v4_to_v6()` before dispatch
- v6 mode: Reject v4 commands, accept v6 commands only
- Logging for transformation and rejections

**Additional Fix:** `src/exabgp/reactor/api/command/limit.py`

Updated `extract_neighbors()` and `match_neighbor()` to handle v6 `peer` prefix:
- Accepts both `neighbor` (v4) and `peer` (v6) prefixes
- Converts to `neighbor` internally for consistency

**Additional Fix:** `src/exabgp/reactor/api/command/watchdog.py`

Updated watchdog handlers to parse arguments correctly for both formats:
- v4: `announce watchdog <name>` (name at index 2)
- v6: `peer * announce watchdog <name>` (name after 'watchdog' keyword)
- New `_extract_watchdog_name()` finds 'watchdog' and gets next word

### Handler Compatibility Pattern

When handlers parse command arguments by index, they must handle both formats:

```python
# BAD - assumes v4 format (breaks with v6)
name = line.split(' ')[2]

# GOOD - finds keyword and gets next word
words = line.split()
idx = words.index('watchdog')
name = words[idx + 1] if idx + 1 < len(words) else default
```

## v6 Format (Target-First, uses `peer`)

```
# Daemon control
daemon shutdown
daemon reload
daemon restart
daemon status

# Session management
session ack enable
session ack disable
session ack silence
session sync enable
session sync disable
session reset
session ping
session bye

# System commands
system help
system version
system crash
system queue-status
system api version

# RIB operations
rib show in [peer <ip>]
rib show out [peer <ip>]
rib flush out [peer <ip>]
rib clear in [peer <ip>]
rib clear out [peer <ip>]

# Peer operations (v6 uses 'peer' not 'neighbor')
peer show [<ip>] [summary|extensive]
peer * teardown [<code>]
peer <ip> teardown [<code>]

# Route announcements (ALWAYS require peer prefix in v6)
peer * announce route <prefix> next-hop <ip> [attributes...]
peer <ip> announce route <prefix> next-hop <ip> [attributes...]
peer <ip> <selector-key> <value> announce route <prefix> ...

# Route withdrawals (ALWAYS require peer prefix in v6)
peer * withdraw route <prefix> [attributes...]
peer <ip> withdraw route <prefix> [attributes...]

# Peer management
peer create <ip> { <configuration> }
peer delete <ip>
```

## v4 Format (Action-First, uses `neighbor`)

```
# Daemon control
shutdown
reload
restart
status

# Session management
enable-ack
disable-ack
silence-ack
enable-sync
disable-sync
reset
ping
bye

# System commands
help
version
crash

# RIB operations
show adj-rib in [<ip>]
show adj-rib out [<ip>]
flush adj-rib out [<ip>]
clear adj-rib in [<ip>]
clear adj-rib out [<ip>]

# Neighbor operations (v4 uses 'neighbor')
show neighbor [<ip>] [summary|extensive]
teardown [<code>]                    # to ALL neighbors
neighbor <ip> teardown [<code>]      # to specific neighbor

# Route announcements (neighbor prefix optional in v4)
announce route <prefix> next-hop <ip> [attributes...]          # to ALL
neighbor <ip> announce route <prefix> next-hop <ip> [attributes...]  # specific

# Route withdrawals (neighbor prefix optional in v4)
withdraw route <prefix> [attributes...]          # from ALL
neighbor <ip> withdraw route <prefix> [attributes...]  # specific

# Peer management (v4 uses 'neighbor')
create neighbor <ip> { <configuration> }
delete neighbor <ip>
```

## Command Mapping Table

| v4 (Action-First) | v6 (Target-First) |
|-------------------|-------------------|
| `shutdown` | `daemon shutdown` |
| `reload` | `daemon reload` |
| `enable-ack` | `session ack enable` |
| `show adj-rib in` | `rib show in` |
| `show neighbor` | `peer show` |
| `teardown` | `peer * teardown` |
| `announce route ...` | `peer * announce route ...` |
| `withdraw route ...` | `peer * withdraw route ...` |
| `neighbor <ip> announce ...` | `peer <ip> announce ...` |
| `create neighbor <ip>` | `peer create <ip>` |
| `delete neighbor <ip>` | `peer delete <ip>` |

## Current Implementation Status

**Completed:**
- ✅ Phase 1: Documentation
- ✅ Phase 2 Step 1: v4→v6 transformation module (75 tests)
- ✅ Phase 2 Step 2: Bug fix in processes.py
- ✅ Phase 2 Step 3: Register v6 commands in daemon
- ✅ Phase 2 Step 4: Add transformation call in API processing
- ✅ Output versioning (v4 response wrappers)
- ✅ Phase 3: v6 Bracket Selector Syntax (21 tests)
- ✅ Phase 4: Refactor Command Dispatch (explicit routing)

**All planned phases completed.**

## Phase 3: v6 Bracket Selector Syntax ✅ COMPLETED

### Goal

Use `[ ]` brackets with comma separators for v6 peer selectors, making parsing easier.

### v4 Syntax (repeated keyword)
```
neighbor 10.0.0.1 router-id 1.2.3.4, neighbor 10.0.0.1 announce route ...
```

### v6 Syntax (bracketed list)
```
# Multiple selectors - brackets required
peer [10.0.0.1 router-id 1.2.3.4, 10.0.0.1] announce route ...
peer [10.0.0.1, 10.0.0.2] announce route ...

# Single peer - no brackets
peer 10.0.0.1 announce route ...

# Wildcard - no brackets
peer * announce route ...
```

Rules:
- `peer [...]` - brackets for multiple selectors (comma-separated inside)
- `peer <ip>` - no brackets, single peer
- `peer *` - no brackets, wildcard for all peers

### Steps

1. ✅ Update v6 format documentation (already had bracket syntax)
2. ✅ Update transform to generate bracket syntax for v6
3. ✅ Update `extract_neighbors()` to parse bracket syntax
4. ✅ Add unit tests for bracket syntax (21 tests in `test_api_limit.py`)

---

## Phase 4: Refactor Command Dispatch ✅ COMPLETED

### Goal

Replace decorator-based command registration with explicit dispatch function.

### Implementation

Created `src/exabgp/reactor/api/dispatch.py` with:
- Explicit routing based on v6 command prefixes
- `COMMANDS` metadata list for help command
- `dispatch()` function returns (handler, neighbor_support)
- `UnknownCommand` exception for unknown commands
- `InvalidCommand` exception for invalid commands

### Steps

1. ✅ Create `dispatch.py` with explicit routing
2. ⏸️ Decorators kept (harmless no-ops, can be removed later)
3. ✅ Update `API.response()` to use dispatch function
4. ⏸️ Command.register kept (unused for dispatch)
5. ✅ Delete `v6.py` (aliases no longer needed)

### Architecture

```
Command arrives (v4 or v6 format)
    ↓
api/__init__.py:process()
    ↓ (transforms v4 → v6)
api/__init__.py:response()
    ↓
dispatch.py:dispatch(command)
    ↓ (explicit prefix matching)
Handler function
```

Benefits achieved:
- Single dispatch location (dispatch.py)
- Explicit, readable routing
- No v6 alias duplication
- Faster dispatch (no iteration through all commands)

## Files

| File | Status | Description |
|------|--------|-------------|
| `.claude/exabgp/API_FORMAT_VERSIONS.md` | ✅ | Documentation |
| `src/exabgp/reactor/api/transform.py` | ✅ | v4→v6 transformation (bracket syntax) |
| `src/exabgp/reactor/api/dispatch.py` | ✅ | Explicit command dispatch |
| `tests/unit/test_api_transform.py` | ✅ | 75 unit tests for transformation |
| `tests/unit/test_api_limit.py` | ✅ | 21 unit tests for selector parsing |
| `src/exabgp/reactor/api/processes.py` | ✅ | Bug fix applied |
| `src/exabgp/reactor/api/__init__.py` | ✅ | Uses dispatch module |
| `src/exabgp/reactor/api/command/__init__.py` | ✅ | v6.py removed |
| `src/exabgp/reactor/api/command/limit.py` | ✅ | Bracket syntax + `peer` prefix |
| `src/exabgp/reactor/api/command/reactor.py` | ✅ | help uses dispatch metadata |
| `src/exabgp/reactor/api/command/watchdog.py` | ✅ | Handle v4/v6 arg parsing |
| `etc/exabgp/run/api-no-neighbor.run` | ✅ | Updated to v6 commands |
