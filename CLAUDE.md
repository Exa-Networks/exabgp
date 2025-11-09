# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Testing:**
- **Check file descriptor limit before running tests:** `ulimit -n` (should be ≥64000)
- **If needed, increase limit:** `ulimit -n 64000`
- `./qa/bin/functional encoding` - Run all functional tests (spawns client and server pairs)
- `./qa/bin/functional encoding --list` - List available tests with unique letter identifiers
- `./qa/bin/functional encoding <letter>` - Run specific test using letter from --list (e.g., `A`, `B`)
- `./qa/bin/functional encoding --server <letter>` - Run only the server component for a specific test
- `./qa/bin/functional encoding --client <letter>` - Run only the client component for a specific test
- Each test spawns both an ExaBGP client and a dummy test server to verify expected client behavior
- `env exabgp_log_enable=false pytest --cov --cov-reset ./tests/*_test.py` - Unit tests with coverage
- `./qa/bin/parsing` - Configuration parsing tests

**Build:**
- `python3 setup.py sdist bdist_wheel` - Build distribution packages
- `./release binary <target>` - Create self-contained zipapp binary

**Linting:**
- Uses `ruff` for linting and formatting (configured in pyproject.toml)
- `ruff format` - Format code (single quotes, 120 char lines)

## Architecture Overview

**ExaBGP is a BGP implementation that does NOT manipulate the FIB (Forwarding Information Base).** Instead, it focuses on BGP protocol implementation and external process communication via JSON API.

**Core Components:**

1. **BGP Protocol Stack** (`src/exabgp/bgp/`):
   - `fsm.py` - BGP finite state machine (IDLE → ACTIVE → CONNECT → OPENSENT → OPENCONFIRM → ESTABLISHED)
   - `message/` - BGP message types (OPEN, UPDATE, NOTIFICATION, KEEPALIVE)
   - `message/open/capability/` - BGP capabilities (ASN4, MP-BGP, graceful restart, AddPath)
   - `message/update/attribute/` - Path attributes (AS_PATH, communities, AIGP, BGP-LS, SR)
   - `message/update/nlri/` - Network Layer Reachability Info for various address families

2. **Reactor Pattern** (`src/exabgp/reactor/`):
   - Event-driven architecture (NOT asyncio-based, custom implementation)
   - `peer.py` - BGP peer state and protocol handling
   - `network/` - TCP connection management
   - `api/` - External process communication via JSON

3. **Configuration System** (`src/exabgp/configuration/`):
   - Flexible parser supporting templates and neighbor inheritance
   - Built-in validation
   - YANG model support (`conf/yang/`)

4. **RIB Management** (`src/exabgp/rib/`):
   - Maintains routing information base
   - Tracks route changes and updates

## Key NLRI Support

ExaBGP supports extensive BGP address families:
- IPv4/IPv6 Unicast and Multicast
- VPNv4/VPNv6 (MPLS L3VPN)
- EVPN (Ethernet VPN)
- BGP-LS (Link State)
- FlowSpec (Traffic filtering)
- VPLS (Virtual Private LAN Service)
- MUP (Mobile User Plane)
- SRv6 (Segment Routing over IPv6)

## Testing Strategy

**Functional Tests** (`qa/`):
- Encoding/decoding validation using `.ci`/`.msg` file pairs
- Tests BGP message construction and parsing
- Configuration file validation against examples in `etc/exabgp/`

**Unit Tests** (`tests/`):
- pytest-based with coverage reporting
- Component-specific tests (BGP-LS, flow, NLRI parsing)

## Class Hierarchy and Architecture

**Core Design Patterns:**

1. **Registry/Factory Pattern** - The most pervasive pattern enabling dynamic object creation:
   - Messages: `@Message.register` with TYPE field identification
   - NLRI: `@NLRI.register(AFI.ipv4, SAFI.unicast)` for address families
   - Attributes: `@Attribute.register` with unique ID system
   - Capabilities: `@Capability.register` for BGP capability negotiation

2. **Template Method Pattern** - Base classes define algorithmic structure:
   - `Message.message()` interface with specialized implementations
   - `NLRI.pack_nlri()`/`unpack_nlri()` for route encoding/decoding
   - `Attribute` processing with common flag handling

3. **State Machine Pattern** - `FSM` class implements BGP finite state machine:
   - States: `IDLE → ACTIVE → CONNECT → OPENSENT → OPENCONFIRM → ESTABLISHED`
   - Event-driven state transitions with API notifications

4. **Observer Pattern** - Reactor coordinates peer states and external processes
5. **Strategy Pattern** - Different processing based on capabilities, address families, error types

**Key Class Hierarchies:**

```
Message (base, inherits from Exception)
├── Open (session establishment)
├── Update (route announcements/withdrawals)
├── Notification/Notify (error handling)
├── KeepAlive (session maintenance)
└── Operational (ExaBGP extensions)

NLRI (base) ← Family ← AFI/SAFI handling
├── INET (IPv4/IPv6 unicast/multicast)
├── Flow (Flowspec traffic filtering)
├── EVPN (Ethernet VPN)
├── VPN/MVPN (L3VPN routes)
└── BGPLS (Link State information)

Attribute (base with LRU caching)
├── Well-known mandatory (Origin, ASPath, NextHop)
├── Optional transitive (Community, ExtendedCommunity)
└── Multiprotocol extensions (MPRNLRI, MPURNLRI)
```

**Data Flow Architecture:**
- **Inbound**: Network → Reactor → Protocol → Message → NLRI/Attributes → API Processes
- **Outbound**: Configuration → RIB → Update Generation → Protocol → Network

**Extensibility Points:**
- New NLRI types: Inherit from `NLRI` and register with AFI/SAFI
- New attributes: Inherit from `Attribute` with unique ID
- New capabilities: Register with capability code
- API extensions: External processes extend functionality

**Error Handling Strategy:**
- `Message` inherits from `Exception` for error propagation
- Treat-as-withdraw for invalid attributes
- Connection reset for protocol violations
- Graceful restart mechanisms

## Development Notes

- **Python 3.8.1+ required** - maintains compatibility with older Python versions
- **No async/await** - uses custom reactor pattern predating asyncio adoption
- **External Process Model** - communicates with external applications via JSON API
- **Stateful BGP** - maintains full BGP state machine and RIB (unlike some route servers)
- **Extensive RFC Support** - implements modern BGP extensions (ASN4, IPv6, MPLS, SRv6, etc.)
- **Registry-based Plugin Architecture** - Clean extensibility through decorator registration
- **Performance Optimized** - LRU caching, lazy loading, event-driven I/O

## Configuration Examples

Example configurations in `etc/exabgp/` demonstrate:
- API integration (`api-*.conf`)
- Protocol features (`conf-*.conf`) 
- Parsing validation (`parse-*.conf`)

The QA functional tests use these configurations to validate both parsing and BGP message generation.