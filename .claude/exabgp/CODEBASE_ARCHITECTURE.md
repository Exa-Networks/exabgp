# Codebase Architecture

**Quick Summary:** ExaBGP organized into bgp/ (protocol), reactor/ (event loop), rib/ (routing table), configuration/ (parsing). Tests in tests/ (unit) and qa/ (functional).

**Full content:** 15 KB - Read sections on-demand when working in specific modules. Summary included in ESSENTIAL_PROTOCOLS.md.

---

Complete structural map of ExaBGP codebase - what exists where and why.

---

## Directory Structure

```
src/exabgp/
├── bgp/                          # BGP Protocol Implementation (Core)
│   ├── fsm.py                   # State Machine: IDLE → ESTABLISHED
│   ├── neighbor/                # Neighbor package
│   │   └── neighbor.py          # Neighbor config & state (716 lines)
│   ├── timer.py                 # BGP timers (Connect, Hold, Keepalive)
│   └── message/                 # BGP Message Types
│       ├── message.py           # Base Message + registry pattern
│       ├── open/                # OPEN messages
│       │   ├── __init__.py     # OPEN message encoding/decoding
│       │   └── capability/      # BGP Capabilities (14+ types)
│       ├── update/              # UPDATE messages (most complex)
│       │   ├── __init__.py     # UPDATE encoding/decoding
│       │   ├── attribute/       # Path Attributes (23+ types)
│       │   │   ├── __init__.py # Attribute registry
│       │   │   ├── attribute.py # Attribute base class
│       │   │   ├── collection.py# Attributes collection (755 lines)
│       │   │   ├── nexthop.py  # Next-Hop attribute
│       │   │   ├── aspath.py   # AS Path attribute
│       │   │   ├── community/  # Communities (Standard, Extended, Large)
│       │   │   ├── sr/         # Segment Routing attributes
│       │   │   └── bgpls/      # BGP-LS TLVs
│       │   └── nlri/            # Network Layer Reachability Info
│       │       ├── nlri.py     # NLRI base + registry (9 types)
│       │       ├── inet.py     # IPv4/IPv6 Unicast/Multicast
│       │       ├── ipvpn.py    # IP-VPN (VPNv4/VPNv6)
│       │       ├── label.py    # MPLS Labels
│       │       ├── flow.py     # FlowSpec (1162 lines - most complex)
│       │       ├── vpls.py     # VPLS
│       │       ├── evpn/       # EVPN (5 route types)
│       │       ├── bgpls/      # BGP Link State
│       │       ├── mup/        # Mobility User Plane
│       │       └── mvpn/       # Multicast VPN
│       ├── keepalive.py
│       ├── notification.py
│       ├── operational.py       # Operational messages (draft)
│       └── refresh.py           # ROUTE-REFRESH
│
├── reactor/                      # Event Loop & Peer Management (Core)
│   ├── loop.py                  # Main reactor loop (617 lines)
│   ├── peer/                    # Peer protocol handler (package)
│   │   ├── __init__.py         # Re-exports Peer, Stats, etc.
│   │   ├── peer.py             # Main Peer class (989 lines, async-only)
│   │   ├── context.py          # PeerContext dataclass
│   │   └── handlers/           # Message handlers
│   │       ├── base.py         # MessageHandler ABC
│   │       ├── update.py       # UpdateHandler
│   │       └── route_refresh.py# RouteRefreshHandler
│   ├── protocol.py              # Network protocol layer
│   ├── daemon.py                # Daemonization wrapper
│   ├── listener.py              # Listening socket management
│   ├── api/                     # External Process API
│   │   ├── processes.py         # Process spawn/communication (992 lines)
│   │   ├── command/             # API Command Registry
│   │   │   ├── __init__.py     # Command registration
│   │   │   ├── command.py      # @Command.register decorator
│   │   │   ├── announce.py     # Route announcements (656 lines)
│   │   │   ├── neighbor.py     # Neighbor commands
│   │   │   ├── peer.py         # Peer lifecycle commands (407 lines)
│   │   │   ├── rib.py          # RIB operations
│   │   │   ├── reactor.py      # Reactor status
│   │   │   ├── registry.py     # Command metadata
│   │   │   └── watchdog.py     # Health monitoring
│   │   ├── response/            # Response formatters (JSON, text)
│   │   └── transcoder.py        # Message encoding for API
│   └── network/                 # TCP/Socket management
│
├── rib/                         # Routing Information Base (Core)
│   ├── __init__.py             # RIB class
│   ├── cache.py                # Route caching
│   ├── change.py               # Route change (NLRI + Attributes)
│   ├── incoming.py             # Received routes (Adj-RIB-In)
│   └── outgoing.py             # Routes to advertise (Adj-RIB-Out)
│
├── configuration/              # Config Parsing (Core)
│   ├── configuration.py        # Main parser (614 lines)
│   ├── parser.py              # Tokenizer
│   ├── check.py               # Config validation
│   ├── core/                  # Core config sections
│   ├── neighbor/              # Neighbor config syntax
│   ├── announce/              # Route announcement syntax
│   ├── static/                # Static route definitions
│   ├── flow/                  # FlowSpec config
│   ├── l2vpn/                 # L2VPN config
│   ├── process/               # API process config
│   ├── template/              # Template system
│   └── operational/           # Operational syntax
│
├── protocol/                   # Protocol Utilities
│   ├── family.py              # AFI/SAFI definitions (442 lines)
│   ├── ip/                    # IP address utilities
│   └── iso/                   # ISO address utilities
│
├── cli/                       # CLI Module (refactored from application/cli.py)
│   ├── persistent_connection.py  # Socket lifecycle, health monitoring (678 lines)
│   ├── completer.py           # Tab completion (1426 lines)
│   ├── formatter.py           # Output formatting (458 lines)
│   ├── history.py             # Command history (420 lines)
│   └── colors.py              # Terminal colors (59 lines)
│
├── application/               # CLI & Tools (Peripheral)
│   ├── cli.py                 # CLI entry point (uses cli/ module)
│   ├── shell.py               # Interactive shell
│   ├── run.py                 # Main entry point (592 lines)
│   ├── healthcheck.py         # Health monitoring (623 lines)
│   ├── decode.py              # Message decoder tool
│   ├── validate.py            # Config validator
│   └── unixsocket.py          # Unix socket communication
│
├── logger/                    # Logging System (Peripheral)
├── environment/              # Environment config
├── util/                     # Utilities (caching, etc.)
├── debug/                    # Debug utilities
├── data/                     # Data structures
└── vendoring/                # Vendored libraries (profiler, objgraph)
```

---

## Core vs Peripheral Modules

### Core (Touch frequently)
- **bgp/message/update/** - Message encoding/decoding (90% of protocol work)
- **reactor/** - Event loop, peer management, API
- **rib/** - Routing table operations
- **configuration/** - Config parsing for new features
- **protocol/family.py** - AFI/SAFI definitions

### Peripheral (Rarely modify)
- **application/** - CLI tools (except when adding CLI features)
- **logger/** - Logging infrastructure
- **environment/** - Environment variables
- **util/** - Helper utilities
- **vendoring/** - Third-party code

---

## Critical Files by Size & Importance

| File | Lines | Purpose | Modification Frequency |
|------|-------|---------|----------------------|
| `cli/completer.py` | 1426 | Tab completion | Medium (CLI features) |
| `bgp/message/update/nlri/flow.py` | 1162 | FlowSpec NLRI | Low (complex, avoid) |
| `reactor/peer/peer.py` | 989 | Peer protocol handling (async) | Medium (protocol changes) |
| `reactor/api/processes.py` | 992 | External process API | Low (stable) |
| `bgp/message/update/attribute/collection.py` | 755 | Attribute handling | High (new attributes) |
| `bgp/neighbor/neighbor.py` | 716 | Neighbor config/state | Medium |
| `cli/persistent_connection.py` | 678 | Socket lifecycle | Medium |
| `reactor/loop.py` | 617 | Main event loop | Low (stable) |
| `configuration/configuration.py` | 614 | Config parser | High (new syntax) |
| `application/run.py` | 592 | Main entry point | Low (stable) |

**Rule:** Files >500 lines = high complexity, modify carefully

---

## Module Dependencies

### Import Chain (Inbound - Network to API)
```
Network bytes
  ↓
reactor/protocol.py (TCP handling)
  ↓
reactor/peer/peer.py (BGP protocol)
  ↓
bgp/message/message.py (Message dispatcher)
  ↓
bgp/message/update/__init__.py (UPDATE parser)
  ↓
bgp/message/update/nlri/nlri.py (NLRI registry)
bgp/message/update/attribute/attributes.py (Attribute parser)
  ↓
reactor/api/transcoder.py (API encoding)
  ↓
reactor/api/processes.py (Send to external process)
```

### Import Chain (Outbound - Config to Network)
```
Configuration file
  ↓
configuration/configuration.py (Parse config)
  ↓
rib/outgoing.py (Store in RIB)
  ↓
rib/change.py (Create Change object)
  ↓
bgp/message/update/__init__.py (Encode UPDATE)
  ↓
reactor/peer.py (Send to peer)
  ↓
reactor/protocol.py (TCP send)
  ↓
Network
```

### Circular Dependencies
**None found** - Clean layering maintained

---

## File Naming Conventions

- **`__init__.py`** - Module exports + main class (often large)
- **`{type}.py`** - Single class/concept (e.g., `inet.py`, `aspath.py`)
- **`{type}s.py`** - Collection/container (e.g., `attributes.py`)
- **Subdirectories** - Multiple related types (e.g., `evpn/`, `community/`)

---

## Key Statistics

- **Total source files:** ~150+ Python files
- **Largest file:** `cli/completer.py` (1426 lines)
- **Most complex NLRI:** `flow.py` (1162 lines)
- **NLRI types:** 9 distinct address families
- **Attribute types:** 23+ path attributes
- **Message types:** 7 (OPEN, UPDATE, NOTIFICATION, KEEPALIVE, ROUTE_REFRESH, OPERATIONAL, NOP)
- **AFI/SAFI combinations:** 42 registered families
- **API Commands:** 40+ registered commands

---

## Navigation Tips

**Finding code:**
- BGP message type → `bgp/message/{type}.py`
- NLRI family → `bgp/message/update/nlri/{family}.py`
- Path attribute → `bgp/message/update/attribute/{name}.py`
- API command → `reactor/api/command/{category}.py`
- Config syntax → `configuration/{section}/`

**Understanding flow:**
- Inbound → Start at `reactor/protocol.py`
- Outbound → Start at `configuration/configuration.py`
- RIB operations → Start at `rib/outgoing.py`
- API → Start at `reactor/api/processes.py`

---

**See also:**
- `DATA_FLOW_GUIDE.md` - How data moves through system
- `REGISTRY_AND_EXTENSION_PATTERNS.md` - How to add new types
- `BGP_CONCEPTS_TO_CODE_MAP.md` - BGP RFCs to code locations
- `CRITICAL_FILES_REFERENCE.md` - Most frequently modified files

---

**Updated:** 2025-12-19
