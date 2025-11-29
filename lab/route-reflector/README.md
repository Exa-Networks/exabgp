# BGP Route Reflector Lab - AS-PATH Based Filtering

This lab demonstrates BGP route filtering based on AS-PATH using ExaBGP as a route reflector. Routes from an upstream BGP speaker are filtered and forwarded to specific client BGP speakers based on which AS appears in the AS-PATH.

## Overview

### Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                         127.0.0.1:1790                          │
│                                                                 │
│  ┌──────────────┐                                               │
│  │  Upstream    │                                               │
│  │  BGP Speaker │──┐                                            │
│  │  AS 65001    │  │                                            │
│  └──────────────┘  │                                            │
│                    │         ┌──────────────┐                   │
│  ┌──────────────┐  │  :1790  │   ExaBGP     │                   │
│  │  Client 1    │  ├────────►│   (Passive)  │                   │
│  │  BGP Speaker │  │         │   Listens on │                   │
│  │  AS 65002    │  │         │   Port 1790  │                   │
│  └──────────────┘  │         │   AS 65000   │                   │
│                    │         └──────┬───────┘                   │
│  ┌──────────────┐  │                │                           │
│  │  Client 2    │  │                │ STDIN/STDOUT              │
│  │  BGP Speaker │──┘                │ (JSON API)                │
│  │  AS 65003    │                   ▼                           │
│  └──────────────┘            ┌──────────────┐                   │
│                              │   Filter     │                   │
│                              │   API        │                   │
│                              │   Program    │                   │
│                              └──────┬───────┘                   │
│                                     │                           │
│                      ┌──────────────┴──────────────┐            │
│                      │                             │            │
│                 AS 15169?                     AS 8075?          │
│                      │                             │            │
│                      ▼                             ▼            │
│            Routes to Client1              Routes to Client2     │
│            (127.0.0.2)                    (127.0.0.3)           │
│            Google routes                  Microsoft routes      │
└─────────────────────────────────────────────────────────────────┘
```

### Components

1. **ExaBGP Route Reflector** (AS 65000)
   - Listens on port 1790 for all incoming BGP connections
   - Accepts connections from 3 neighbors (upstream + 2 clients)
   - Forwards routes via API filter program
   - Configuration: `config/exabgp-rr.conf`

2. **Filter API Process** (`scripts/filter_api.py`)
   - Receives routes from ExaBGP as JSON via stdin
   - Parses AS-PATH attribute
   - Filters routes:
     - AS 15169 (Google) → Client1 (127.0.0.2)
     - AS 8075 (Microsoft) → Client2 (127.0.0.3)
     - Other → Dropped
   - Sends announce commands to ExaBGP via stdout

3. **Upstream BGP Speaker** (`scripts/upstream_speaker.py`)
   - AS 65001
   - Connects to ExaBGP on port 1790
   - Sends valid BGP OPEN message
   - Announces 10 routes with various AS-PATHs via BGP UPDATE
   - Sends periodic KEEPALIVE messages

4. **Client BGP Speakers** (`scripts/client_speaker.py`)
   - Client1 (AS 65002) - connects to port 1790
   - Client2 (AS 65003) - connects to port 1790
   - Send valid BGP OPEN messages
   - Receive and parse BGP UPDATE messages using ExaBGP's decoder
   - Display received routes with AS-PATH information
   - Send periodic KEEPALIVE messages

5. **Orchestrator** (`scripts/orchestrator.py`)
   - Starts all components in correct order
   - Multiplexes output with colored prefixes
   - Handles graceful shutdown (Ctrl+C)

### Filtering Logic

The filter API examines the AS-PATH attribute of each route:

- **Google routes** (AS 15169 in path):
  - `8.8.8.0/24`, `8.8.4.0/24`, `142.250.0.0/16`, `172.217.0.0/16`
  - Forwarded to Client1

- **Microsoft routes** (AS 8075 in path):
  - `13.64.0.0/11`, `40.74.0.0/15`, `52.96.0.0/12`, `104.40.0.0/13`
  - Forwarded to Client2

- **Other routes** (AS 13335, 19281):
  - `1.1.1.0/24` (Cloudflare), `9.9.9.0/24` (Quad9)
  - Dropped (logged but not forwarded)

## Quick Start

### Prerequisites

- Python 3.8+
- ExaBGP installed (part of this repository)
- Terminal with ANSI color support (recommended)

### Running the Lab

```bash
# From repository root
cd lab/route-reflector

# Run orchestrator (starts all components)
python3 scripts/orchestrator.py
```

### Expected Output

```
======================================================================
BGP Route Reflector Lab - AS-PATH Based Filtering
======================================================================

Topology:
  Upstream (AS 65001) → ExaBGP (AS 65000) → Clients (AS 65002, 65003)

Filter Rules:
  Google routes (AS 15169)    → Client1
  Microsoft routes (AS 8075)  → Client2
  Other routes                → Dropped

======================================================================

[ORCHESTRATOR] Started exabgp (PID 12345)
[ORCHESTRATOR] Waiting 3s for ExaBGP to initialize...
[ORCHESTRATOR] Started client1 (PID 12346)
[ORCHESTRATOR] Started client2 (PID 12347)
[ORCHESTRATOR] Waiting 2s for clients to connect...
[ORCHESTRATOR] Started upstream (PID 12348)

======================================================================
All processes started - Monitoring output
Press Ctrl+C to shutdown
======================================================================

[EXABGP]        Starting ExaBGP 6.0.0
[FILTER]        Starting AS-PATH filter API
[FILTER]        Filter rules: 2 AS filters configured
[FILTER]          Google (AS15169) → Client1 (127.0.0.2)
[FILTER]          Microsoft (AS8075) → Client2 (127.0.0.3)
[CLIENT1]       Connecting to ExaBGP at 127.0.0.1:1791
[CLIENT1]       BGP session established successfully
[CLIENT2]       Connecting to ExaBGP at 127.0.0.1:1792
[CLIENT2]       BGP session established successfully
[UPSTREAM]      Connecting to ExaBGP at 127.0.0.1:1790
[UPSTREAM]      BGP session established successfully
[UPSTREAM]      Announcing 10 routes...
[UPSTREAM]      ANNOUNCED: 8.8.8.0/24         AS-PATH: AS15169 → AS65001          (Google Public DNS)
[FILTER]        FORWARD: 8.8.8.0/24 (Google) → Client1 (127.0.0.2) - AS-PATH: Google(15169) → Upstream(65001)
[CLIENT1]       RECEIVED #1: 8.8.8.0/24         AS-PATH: AS15169 → AS65001 → AS65000      next-hop: 10.0.0.1
[UPSTREAM]      ANNOUNCED: 13.64.0.0/11       AS-PATH: AS8075 → AS65001           (Microsoft Azure US East)
[FILTER]        FORWARD: 13.64.0.0/11 (Microsoft) → Client2 (127.0.0.3) - AS-PATH: Microsoft(8075) → Upstream(65001)
[CLIENT2]       RECEIVED #1: 13.64.0.0/11       AS-PATH: AS8075 → AS65001 → AS65000       next-hop: 10.0.0.2
[UPSTREAM]      ANNOUNCED: 1.1.1.0/24         AS-PATH: AS13335 → AS65001          (Cloudflare DNS)
[FILTER]        DROPPED: 1.1.1.0/24 - AS-PATH: Cloudflare(13335) → Upstream(65001)
...
```

### Stopping the Lab

Press `Ctrl+C` to gracefully shutdown all processes.

## File Structure

```
lab/route-reflector/
├── config/
│   └── exabgp-rr.conf          # ExaBGP route reflector config
├── scripts/
│   ├── filter_api.py           # AS-PATH filter (ExaBGP API process)
│   ├── upstream_speaker.py     # Fake upstream BGP (sends routes)
│   ├── client_speaker.py       # Fake client BGP (receives routes)
│   └── orchestrator.py         # Process manager
├── lib/
│   └── bgp_helpers.py          # BGP message encoding/decoding
├── data/
│   └── routes.json             # Test routes (Google/MS/other)
├── logs/
│   └── .gitkeep
└── README.md                    # This file
```

## Technical Details

### BGP Session Parameters

- **Hold Time:** 180 seconds (long to avoid keepalive complexity)
- **BGP Version:** 4
- **Capabilities:**
  - ASN4 (RFC 6793) - 4-byte AS numbers
  - Route Refresh (RFC 2918)
  - Multiprotocol Extensions (RFC 4760) - IPv4 Unicast

### BGP Message Handling

**Client Speakers:**
- **OPEN:** Custom BGP helpers (`lib/bgp_helpers.py`)
- **UPDATE Parsing:** ExaBGP's native decoder (`exabgp.bgp.message.update.Update`)
- **KEEPALIVE:** Custom BGP helpers

**Upstream Speaker:**
- **OPEN:** Custom BGP helpers
- **UPDATE Construction:** Custom BGP helpers (simpler than using ExaBGP's encoder)
- **KEEPALIVE:** Custom BGP helpers

This hybrid approach uses ExaBGP's battle-tested UPDATE decoder for parsing
received routes while keeping message construction simple with custom helpers.

### Message Flow

1. **Session Establishment:**
   ```
   Upstream → ExaBGP: OPEN (AS 65001)
   ExaBGP → Upstream: OPEN (AS 65000)
   Upstream → ExaBGP: KEEPALIVE
   ExaBGP → Upstream: KEEPALIVE
   [Session ESTABLISHED]
   ```

2. **Route Announcement:**
   ```
   Upstream → ExaBGP: UPDATE (8.8.8.0/24, AS-PATH [15169, 65001])
   ExaBGP → Filter API: JSON {"type": "update", "nlri": "8.8.8.0/24", "attributes": {"aspath": [{"asns": [15169, 65001]}]}}
   Filter API → ExaBGP: announce route 8.8.8.0/24 next-hop 10.0.0.1 as-path [ 15169 65001 ]
   ExaBGP → Client1: UPDATE (8.8.8.0/24, AS-PATH [15169, 65001, 65000])
   ```

### AS Numbers Used

| AS Number | Organization | Role |
|-----------|-------------|------|
| 15169 | Google | Route source (filtered to Client1) |
| 8075 | Microsoft | Route source (filtered to Client2) |
| 13335 | Cloudflare | Route source (dropped) |
| 19281 | Quad9 | Route source (dropped) |
| 65000 | ExaBGP | Route reflector |
| 65001 | Upstream | Upstream peer |
| 65002 | Client1 | Client peer (Google routes) |
| 65003 | Client2 | Client peer (Microsoft routes) |

## Manual Component Testing

### Test Individual Components

```bash
# Test ExaBGP only (no routes, just listen)
./sbin/exabgp lab/route-reflector/config/exabgp-rr.conf

# Test upstream speaker (in another terminal, after ExaBGP starts)
python3 lab/route-reflector/scripts/upstream_speaker.py

# Test client speaker (in another terminal)
python3 lab/route-reflector/scripts/client_speaker.py --name CLIENT1 --port 1790 --asn 65002
```

### Verify BGP Messages

Use `tcpdump` to inspect BGP messages:

```bash
sudo tcpdump -i lo0 'tcp port 1790' -X
```

## Troubleshooting

### ExaBGP won't start

**Symptoms:** `[ORCHESTRATOR] Started exabgp` but no ExaBGP output

**Solutions:**
- Check port available: `lsof -i :1790`
- Validate config: `./sbin/exabgp --validate lab/route-reflector/config/exabgp-rr.conf`
- Check ExaBGP logs in terminal output

### Clients can't connect

**Symptoms:** `ERROR: Failed to establish BGP session`

**Solutions:**
- Ensure ExaBGP started and is listening: check for "Listening on..." messages
- Wait longer before starting clients (increase delay in orchestrator)
- Check firewall: `sudo pfctl -s rules | grep 179`

### No routes received by clients

**Symptoms:** Clients connected but no "RECEIVED" messages

**Solutions:**
- Check filter API is running: look for `[FILTER]` messages
- Verify upstream announced routes: look for `[UPSTREAM] ANNOUNCED` messages
- Check filter logic: look for `[FILTER] FORWARD` or `[FILTER] DROPPED` messages
- Enable ExaBGP debug: modify config to add `env { exabgp_log_level=DEBUG; }`

### Routes not filtered correctly

**Symptoms:** Wrong client receives routes

**Solutions:**
- Check AS-PATH in filter API logs
- Verify AS_FILTERS mapping in `scripts/filter_api.py`
- Confirm route data in `data/routes.json` has correct AS-PATH
- Check neighbor IPs in `config/exabgp-rr.conf` match filter mappings

## Learning Objectives

This lab demonstrates:

1. **BGP Route Reflection** - How route reflectors forward routes between peers
2. **AS-PATH Attribute** - Understanding AS-PATH structure and parsing
3. **ExaBGP API** - Using ExaBGP's JSON API for route manipulation
4. **Policy-Based Routing** - Implementing custom routing policies via filters
5. **BGP Message Flow** - OPEN/UPDATE/KEEPALIVE message exchange
6. **Multi-Process Architecture** - Orchestrating multiple BGP speakers

## Extensions

Try these enhancements to deepen understanding:

1. **Add More Filters** - Filter by prefix length, community, MED
2. **Implement Aggregation** - Combine multiple /24s into /16
3. **Add Route Modification** - Prepend local AS multiple times
4. **Implement Blackholing** - Drop traffic to specific prefixes
5. **Add Metrics Collection** - Count routes per AS, per client
6. **Web Dashboard** - Visualize route flow in real-time
7. **IPv6 Support** - Extend to IPv6 unicast family
8. **Multiple Upstreams** - Test with competing routes from different upstreams

## References

- [ExaBGP Documentation](https://github.com/Exa-Networks/exabgp)
- [RFC 4271 - BGP-4](https://tools.ietf.org/html/rfc4271)
- [RFC 6793 - BGP Support for 4-Byte ASN](https://tools.ietf.org/html/rfc6793)
- [RFC 4760 - Multiprotocol Extensions for BGP-4](https://tools.ietf.org/html/rfc4760)

---

**Lab Version:** 1.0
**Created:** 2025-11-21
**ExaBGP Version:** 6.0.0
**Python Version:** 3.8+
