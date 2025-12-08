# BGP Concepts to Code Map

Mapping BGP protocol specifications to ExaBGP code locations.

---

## Message Types

BGP has 7 message types (RFC 4271 + extensions):

| Message | Code | File | Purpose |
|---------|------|------|---------|
| OPEN | 1 | `bgp/message/open/__init__.py` | Session establishment, capability negotiation |
| UPDATE | 2 | `bgp/message/update/__init__.py` | Route announcements/withdrawals |
| NOTIFICATION | 3 | `bgp/message/notification.py` | Error reporting, session teardown |
| KEEPALIVE | 4 | `bgp/message/keepalive.py` | Session keepalive |
| ROUTE-REFRESH | 5 | `bgp/message/refresh.py` | Request route re-advertisement (RFC 2918) |
| OPERATIONAL | 6 | `bgp/message/operational.py` | Operational messages (draft) |
| NOP | 255 | `bgp/message/nop.py` | Internal: no operation |

**Registry:** `bgp/message/message.py` - `Message.registered` dict

---

## AFI/SAFI (Address Families)

### AFI Values (Address Family Identifier)

**File:** `src/exabgp/protocol/family.py:28`

| AFI | Value | Description |
|-----|-------|-------------|
| IPv4 | 1 | IP version 4 |
| IPv6 | 2 | IP version 6 |
| L2VPN | 25 | Layer 2 VPN |
| BGP-LS | 16396 | BGP Link State |

### SAFI Values (Subsequent AFI)

**File:** `src/exabgp/protocol/family.py:54`

| SAFI | Value | Description |
|------|-------|-------------|
| unicast | 1 | Unicast routing |
| multicast | 2 | Multicast routing |
| nlri_mpls | 4 | MPLS labels |
| vpn | 128 | VPN (L3VPN) |
| flow_ip | 133 | FlowSpec IPv4 |
| flow_vpn | 134 | FlowSpec VPN |
| evpn | 70 | Ethernet VPN |
| bgp_ls | 71 | BGP Link State |
| rtc | 132 | Route Target Constraint |
| vpls | 65 | Virtual Private LAN Service |
| mup | 69 | Mobility User Plane |
| mpls_vpn | 5 | Multicast VPN |

### Supported Families (42 combinations)

**File:** `src/exabgp/protocol/family.py:143`

```python
known_families = [
    (AFI.ipv4, SAFI.unicast),
    (AFI.ipv4, SAFI.multicast),
    (AFI.ipv4, SAFI.nlri_mpls),
    (AFI.ipv4, SAFI.vpn),
    (AFI.ipv4, SAFI.flow_ip),
    (AFI.ipv4, SAFI.flow_vpn),
    (AFI.ipv6, SAFI.unicast),
    (AFI.ipv6, SAFI.multicast),
    (AFI.ipv6, SAFI.nlri_mpls),
    (AFI.ipv6, SAFI.vpn),
    (AFI.ipv6, SAFI.flow_ip),
    (AFI.ipv6, SAFI.flow_vpn),
    (AFI.l2vpn, SAFI.evpn),
    (AFI.l2vpn, SAFI.vpls),
    (AFI.bgpls, SAFI.bgp_ls),
    # ... etc (42 total)
]
```

---

## NLRI Types (9 families)

Network Layer Reachability Information - routes being advertised.

**Base class:** `bgp/message/update/nlri/nlri.py:NLRI`

| Type | AFI/SAFI | File | Description | Complexity |
|------|----------|------|-------------|------------|
| INET | IPv4/IPv6 unicast/multicast | `nlri/inet.py` | Basic IP prefixes | Simple |
| IPVPN | IPv4/IPv6 VPN | `nlri/ipvpn.py` | VPNv4/v6 with RD + label | Medium |
| FLOW | IPv4/IPv6 FlowSpec | `nlri/flow.py` | Traffic filtering (764 lines) | Complex |
| EVPN | L2VPN EVPN | `nlri/evpn/` | Ethernet VPN (5 route types) | Complex |
| BGPLS | BGP-LS | `nlri/bgpls/` | Link-state distribution | Complex |
| VPLS | L2VPN VPLS | `nlri/vpls.py` | Virtual Private LAN | Medium |
| MUP | IPv4/IPv6 MUP | `nlri/mup/` | Mobile User Plane | Medium |
| MVPN | IPv4/IPv6 MVPN | `nlri/mvpn/` | Multicast VPN | Medium |
| RTC | IPv4 RTC | `nlri/rtc.py` | Route Target Constraint | Simple |

### EVPN Route Types

**Directory:** `bgp/message/update/nlri/evpn/`

| Route Type | Code | File | Class | Description |
|------------|------|------|-------|-------------|
| Ethernet Auto-Discovery | 1 | `ethernetad.py` | `EthernetAD` | Auto-discovery |
| MAC/IP Advertisement | 2 | `mac.py` | `MAC` | MAC/IP route |
| Inclusive Multicast | 3 | `multicast.py` | `Multicast` | Multicast tree |
| Ethernet Segment | 4 | `segment.py` | `EthernetSegment` | ES route |
| IP Prefix | 5 | `prefix.py` | `Prefix` | IP prefix route |
| Generic (unknown) | * | `nlri.py` | `GenericEVPN` | Fallback for unknown types |

---

## Path Attributes (23+ types)

**Base class:** `bgp/message/update/attribute/attribute.py:Attribute`

### Well-Known Mandatory (must be present)

| Attribute | Code | File | Description |
|-----------|------|------|-------------|
| ORIGIN | 1 | `origin.py` | Route origin (IGP/EGP/INCOMPLETE) |
| AS_PATH | 2 | `aspath.py` | AS path traversed |
| NEXT_HOP | 3 | `nexthop.py` | Next hop IP address |

### Well-Known Discretionary (optional but recognized)

| Attribute | Code | File | Description |
|-----------|------|------|-------------|
| LOCAL_PREF | 5 | `localpref.py` | Local preference (iBGP only) |
| ATOMIC_AGGREGATE | 6 | `attribute.py` | Route aggregation marker |
| AGGREGATOR | 7 | `aggregator.py` | Aggregating router info |

### Optional Transitive

| Attribute | Code | File | Description |
|-----------|------|------|-------------|
| MULTI_EXIT_DISC | 4 | `med.py` | MED (metric) |
| COMMUNITY | 8 | `community/initial.py` | Standard communities |
| EXTENDED_COMMUNITY | 16 | `community/extended/` | Extended communities |
| LARGE_COMMUNITY | 32 | `community/large.py` | Large communities |
| AS4_PATH | 17 | `aspath.py` | 4-byte AS path |
| AS4_AGGREGATOR | 18 | `aggregator.py` | 4-byte AS aggregator |

### Optional Non-Transitive

| Attribute | Code | File | Description |
|-----------|------|------|-------------|
| ORIGINATOR_ID | 9 | `originatorid.py` | Route reflector originator |
| CLUSTER_LIST | 10 | `clusterlist.py` | Route reflector cluster path |
| MP_REACH_NLRI | 14 | `mprnlri.py` | Multiprotocol reachable NLRI |
| MP_UNREACH_NLRI | 15 | `mpurnlri.py` | Multiprotocol unreachable NLRI |

### Specialized Attributes

| Attribute | Code | File | Description |
|-----------|------|------|-------------|
| PMSI_TUNNEL | 22 | `pmsi.py` | P-Multicast Service Interface |
| AIGP | 26 | `aigp.py` | Accumulated IGP Metric |
| BGP_PREFIX_SID | 40 | `sr/prefixsid.py` | Segment Routing Prefix SID |
| BGP-LS | 29 | `bgpls/` | Link-state attributes |

**Registry:** `bgp/message/update/attribute/__init__.py` - `Attribute.registered` dict

---

## Capabilities (14+ types)

**Base class:** `bgp/message/open/capability/capability.py:Capability`

**Directory:** `bgp/message/open/capability/`

| Capability | Code | File | Description |
|------------|------|------|-------------|
| Multiprotocol | 1 | `mp.py` | AFI/SAFI support |
| Route Refresh | 2 | `refresh.py` | RFC 2918 route refresh |
| Extended Next Hop | 5 | `nexthop.py` | Extended next hop encoding |
| Extended Message | 6 | `extended.py` | Large message support |
| Graceful Restart | 64 | `graceful.py` | Graceful restart (RFC 4724) |
| ASN4 | 65 | `asn4.py` | 4-byte AS numbers |
| AddPath | 69 | `addpath.py` | Multiple paths per prefix |
| Operational | 66 | `operational.py` | Operational messages |
| Multisession | 68 | `multisession.py` | Multiple sessions |
| AIGP | 71 | `aigp.py` | AIGP support |

**Registry:** `bgp/message/open/capability/__init__.py` - `Capability.registered` dict

---

## FSM States (Finite State Machine)

**File:** `bgp/fsm.py`

| State | Value | Description | Valid Messages |
|-------|-------|-------------|----------------|
| IDLE | 1 | Initial state, no connection | None |
| ACTIVE | 2 | Trying to connect | None |
| CONNECT | 3 | TCP connecting | None |
| OPENSENT | 4 | OPEN sent, awaiting OPEN | OPEN, NOTIFICATION |
| OPENCONFIRM | 5 | OPEN received, awaiting KEEPALIVE | KEEPALIVE, NOTIFICATION |
| ESTABLISHED | 6 | Session up, exchanging routes | UPDATE, KEEPALIVE, NOTIFICATION, ROUTE-REFRESH |

**Transitions:** `reactor/peer.py:FSM` class

---

## Notification Error Codes

**File:** `bgp/message/notification.py`

| Error | Code | Subcodes | Description |
|-------|------|----------|-------------|
| Message Header Error | 1 | 1-3 | Malformed message header |
| OPEN Message Error | 2 | 1-8 | OPEN validation failed |
| UPDATE Message Error | 3 | 1-11 | UPDATE validation failed |
| Hold Timer Expired | 4 | - | Keepalive timeout |
| FSM Error | 5 | 1-3 | Invalid state transition |
| Cease | 6 | 1-11 | Administrative shutdown |

---

## Configuration Sections

**Directory:** `src/exabgp/configuration/`

| Section | Directory | Description |
|---------|-----------|-------------|
| Core settings | `core/` | Process, logging, cache |
| Neighbor | `neighbor/` | BGP neighbor definition |
| Static routes | `static/` | Static route announcements |
| Flow routes | `flow/` | FlowSpec rules |
| L2VPN | `l2vpn/` | EVPN/VPLS routes |
| Operational | `operational/` | Operational messages |
| Process | `process/` | API process configuration |
| Template | `template/` | Template system |

**Main parser:** `configuration/configuration.py`

---

## API Command Categories

**Directory:** `src/exabgp/reactor/api/command/`

| Category | File | Example Commands |
|----------|------|------------------|
| Announcements | `announce.py` | `announce route`, `announce flow`, `announce vpls` |
| Withdrawals | `announce.py` | `withdraw route`, `withdraw flow` |
| Neighbor | `neighbor.py` | `show neighbor`, `neighbor <ip> up/down` |
| Peer | `peer.py` | `peer <selector> up/down/disable/enable` |
| RIB | `rib.py` | `flush neighbor`, `flush adj-rib out` |
| Reactor | `reactor.py` | `show reactor`, `teardown`, `reload` |
| Watchdog | `watchdog.py` | `announce watchdog` |

**Registry:** `reactor/api/command/command.py` - `Command.callback` dict

---

## RIB Structure

**Directory:** `src/exabgp/rib/`

| Component | File | Description |
|-----------|------|-------------|
| RIB main | `__init__.py` | Main RIB class |
| Adj-RIB-In | `incoming.py` | Received routes from peers |
| Adj-RIB-Out | `outgoing.py` | Routes to advertise to peers |
| Change | `change.py` | Route change (NLRI + Attributes combo) |
| Cache | `cache.py` | Route caching for performance |

**Data structure:**
```
RIB
├── incoming: Dict[Peer, Dict[Family, Dict[NLRI, Attributes]]]
└── outgoing: Dict[Peer, Dict[Family, Dict[Index, Change]]]
```

---

## Quick Reference Tables

### Finding Code by BGP Concept

| BGP Concept | Search In | Example |
|-------------|-----------|---------|
| Message type | `bgp/message/*.py` | OPEN, UPDATE, KEEPALIVE |
| NLRI family | `bgp/message/update/nlri/` | IPv4 unicast, VPNv4, FlowSpec |
| Path attribute | `bgp/message/update/attribute/` | AS_PATH, COMMUNITY, MED |
| Capability | `bgp/message/open/capability/` | Multiprotocol, ASN4, AddPath |
| AFI/SAFI code | `protocol/family.py` | AFI.ipv4, SAFI.unicast |
| FSM state | `bgp/fsm.py` | ESTABLISHED, OPENSENT |
| Config syntax | `configuration/*/` | neighbor, announce, flow |
| API command | `reactor/api/command/` | show, announce, withdraw |

### RFC to File Mapping

| RFC | Topic | Files |
|-----|-------|-------|
| RFC 4271 | BGP-4 base | `bgp/message/*.py`, `bgp/fsm.py` |
| RFC 4760 | Multiprotocol BGP | `bgp/message/update/attribute/mprnlri.py`, `nlri/*.py` |
| RFC 2918 | Route Refresh | `bgp/message/refresh.py` |
| RFC 4724 | Graceful Restart | `bgp/message/open/capability/graceful.py` |
| RFC 6793 | 4-byte ASN | `bgp/message/open/capability/asn4.py` |
| RFC 7911 | AddPath | `bgp/message/open/capability/addpath.py` |
| RFC 5575 | FlowSpec | `bgp/message/update/nlri/flow.py` |
| RFC 7432 | EVPN | `bgp/message/update/nlri/evpn/` |
| RFC 7752 | BGP-LS | `bgp/message/update/nlri/bgpls/` |
| RFC 4360 | Extended Communities | `bgp/message/update/attribute/community/extended/` |

---

**See also:**
- `CODEBASE_ARCHITECTURE.md` - File locations
- `DATA_FLOW_GUIDE.md` - How BGP messages flow
- `REGISTRY_AND_EXTENSION_PATTERNS.md` - Adding new types
- `CRITICAL_FILES_REFERENCE.md` - Most important files
- `doc/RFC_WIRE_FORMAT_REFERENCE.md` - Detailed wire format diagrams and byte layouts

---

**Updated:** 2025-12-08
