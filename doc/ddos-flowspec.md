# DDoS Mitigation with FlowSpec

This guide explains how to use ExaBGP as an automated FlowSpec controller
for DDoS mitigation.  A webhook listener receives attack alerts from a
detection system and translates them into BGP FlowSpec rules that upstream
routers enforce at the network edge.

## What is FlowSpec?

BGP FlowSpec (RFC 5575, updated by RFC 8955) extends BGP to distribute
traffic filtering rules alongside routing information.  Instead of
blackholing an entire prefix, FlowSpec lets you describe attack traffic
precisely -- by source, destination, protocol, port, packet length, and
more -- and instruct routers to drop, rate-limit, or redirect only the
matching packets.

This makes FlowSpec ideal for surgical DDoS mitigation: you keep
legitimate traffic flowing while the attack is filtered at the router
level, before it reaches your servers.

## Prerequisites

1. **Router support** -- Your upstream or edge routers must support BGP
   FlowSpec.  Most modern Juniper (MX, PTX), Cisco (IOS-XR), Nokia (SR OS),
   and Arista (EOS) platforms do.  Check your vendor documentation for the
   required license or feature set.

2. **BGP session** -- ExaBGP must have an iBGP or eBGP session to the
   router(s) where you want FlowSpec rules installed.  The session needs
   `ipv4 flow` (and optionally `ipv6 flow`) address families negotiated.

3. **Validation mode** -- Some routers require the FlowSpec originator to
   also be the best-path next-hop for the destination prefix, or they will
   reject the rule.  Check your router's FlowSpec validation settings
   (`validation { ... }` on Juniper, `flowspec validation` on IOS-XR).

4. **Detection system** -- You need something that detects attacks and can
   send HTTP POST webhooks: Flowtriq, Wanguard, a custom sFlow/NetFlow
   analyzer, or a monitoring system with webhook actions.

## Setup walkthrough

### 1. Install ExaBGP

```bash
pip install exabgp
```

Or from source -- see the main ExaBGP README for details.

### 2. Configure the BGP session

Edit `etc/exabgp/api-ddos-flowspec.conf`:

```
process ddos-flowspec {
    run ./run/api-ddos-flowspec.run;
    encoder text;
}

neighbor 10.0.0.1 {
    router-id 10.0.0.17;
    local-address 10.0.0.17;
    local-as 64512;
    peer-as 64512;
    hold-time 180;
    group-updates true;

    capability {
        route-refresh enable;
    }

    family {
        ipv4 flow;
        ipv6 flow;
    }

    api {
        processes [ ddos-flowspec ];
    }
}
```

Adjust `local-as`, `peer-as`, addresses, and hold-time to match your
network.  If you peer with multiple routers, add additional `neighbor`
blocks -- FlowSpec rules are announced to all peers in the process group.

### 3. Set environment variables

| Variable       | Default     | Description                                     |
|----------------|-------------|-------------------------------------------------|
| `WEBHOOK_PORT` | `5000`      | HTTP port for the webhook listener              |
| `WEBHOOK_BIND` | `127.0.0.1` | Bind address (set `0.0.0.0` for remote access)  |
| `API_KEY`      | (none)      | Bearer token for authentication                 |
| `RATE_LIMIT`   | `0`         | FlowSpec rate-limit in bytes/s (0 = drop)       |
| `LOG_LEVEL`    | `INFO`      | Logging verbosity (DEBUG, INFO, WARNING)        |

Example:

```bash
export WEBHOOK_PORT=5000
export WEBHOOK_BIND=0.0.0.0
export API_KEY=$(openssl rand -hex 32)
export RATE_LIMIT=0
```

### 4. Start ExaBGP

```bash
exabgp ./etc/exabgp/api-ddos-flowspec.conf
```

The process script waits for ExaBGP to signal that a BGP session is up
before it starts the HTTP listener.  If no session comes up within 10
seconds, it starts anyway (rules will be queued and sent when the session
establishes).

### 5. Send a test webhook

```bash
curl -X POST http://localhost:5000/ \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <your-api-key>' \
  -d '{
    "action": "mitigate",
    "source": "203.0.113.0/24",
    "destination": "198.51.100.0/24",
    "protocol": "udp",
    "source_port": 53,
    "attack_id": "dns-amp-test"
  }'
```

Verify the rule is active:

```bash
curl http://localhost:5000/
```

Clear the rule:

```bash
curl -X POST http://localhost:5000/ \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <your-api-key>' \
  -d '{
    "action": "clear",
    "source": "203.0.113.0/24",
    "destination": "198.51.100.0/24",
    "protocol": "udp",
    "source_port": 53,
    "attack_id": "dns-amp-test"
  }'
```

## Payload reference

POST a JSON object to the webhook endpoint:

| Field         | Type   | Required | Description                                       |
|---------------|--------|----------|---------------------------------------------------|
| `action`      | string | yes      | `"mitigate"` to announce, `"clear"` to withdraw   |
| `source`      | string | no*      | Source prefix in CIDR notation                     |
| `destination` | string | no*      | Destination prefix in CIDR notation                |
| `protocol`    | string | no       | IP protocol: `tcp`, `udp`, `icmp`, `gre`, etc.    |
| `port`        | int    | no       | Destination port (1-65535)                         |
| `source_port` | int    | no       | Source port (1-65535)                              |
| `attack_id`   | string | no       | Identifier for logging and correlation             |

\* At least one of `source` or `destination` is required.

All inputs are validated:
- Prefixes are checked with Python's `ipaddress` module.
- Protocol is checked against a known set.
- Ports must be integers between 1 and 65535.

Invalid requests receive a 400 response with a descriptive error message.

## Common attack patterns

### DNS amplification

DNS amplification uses open resolvers to reflect large responses toward
the victim.  The reflected packets come FROM source port 53.

```bash
curl -X POST http://localhost:5000/ \
  -H 'Content-Type: application/json' \
  -d '{
    "action": "mitigate",
    "destination": "198.51.100.0/24",
    "protocol": "udp",
    "source_port": 53,
    "attack_id": "dns-amp"
  }'
```

FlowSpec rule: `match { destination 198.51.100.0/24; protocol udp; source-port =53; }`

### NTP amplification

Similar to DNS amplification, but abuses NTP monlist.  Reflected packets
come from source port 123.

```bash
curl -X POST http://localhost:5000/ \
  -H 'Content-Type: application/json' \
  -d '{
    "action": "mitigate",
    "destination": "198.51.100.0/24",
    "protocol": "udp",
    "source_port": 123,
    "attack_id": "ntp-amp"
  }'
```

FlowSpec rule: `match { destination 198.51.100.0/24; protocol udp; source-port =123; }`

### UDP flood

A volumetric UDP flood from a known source prefix:

```bash
curl -X POST http://localhost:5000/ \
  -H 'Content-Type: application/json' \
  -d '{
    "action": "mitigate",
    "source": "192.0.2.0/24",
    "destination": "198.51.100.0/24",
    "protocol": "udp",
    "attack_id": "udp-flood"
  }'
```

FlowSpec rule: `match { source 192.0.2.0/24; destination 198.51.100.0/24; protocol udp; }`

### SYN flood

TCP SYN floods targeting a specific destination port:

```bash
curl -X POST http://localhost:5000/ \
  -H 'Content-Type: application/json' \
  -d '{
    "action": "mitigate",
    "source": "192.0.2.0/24",
    "destination": "198.51.100.0/24",
    "protocol": "tcp",
    "port": 80,
    "attack_id": "syn-flood"
  }'
```

FlowSpec rule: `match { source 192.0.2.0/24; destination 198.51.100.0/24; protocol tcp; destination-port =80; }`

Note: For SYN floods you may want to use `RATE_LIMIT` instead of dropping
all traffic, to allow some legitimate connections through while the attack
is active.

## Authentication

The webhook listener binds to `127.0.0.1` by default.  Only local
processes can reach it, so authentication is optional in that
configuration.

To accept webhooks from a remote detection system:

1. Set `WEBHOOK_BIND=0.0.0.0`
2. Set `API_KEY` to a strong random value
3. Include the header `Authorization: Bearer <key>` in POST requests

When `API_KEY` is set, POST requests without a valid bearer token receive
a 401 response.

## Troubleshooting

**"broken pipe" errors in the log**
ExaBGP exited or restarted.  The process script will be restarted
automatically by ExaBGP.

**Rules announced but not installed on the router**
- Check that the BGP session is established: `exabgpcli show neighbor summary`
- Verify the router's FlowSpec validation policy.  Some routers reject
  FlowSpec rules unless the originator is the best-path next-hop.
- Check the router's FlowSpec table: `show route table inetflow.0` (Juniper)
  or `show flowspec ipv4` (IOS-XR).

**"no session-up received after 10 s" warning**
The BGP peer did not connect within the startup timeout.  The webhook
listener starts anyway.  Check that the neighbor IP and ASN are correct
and that the peer is reachable.

**Webhook returns 400 with validation error**
The request contained invalid input.  Check the error message:
- Source/destination must be valid CIDR (e.g. `198.51.100.0/24`)
- Protocol must be a known name (`tcp`, `udp`, `icmp`, etc.)
- Port must be an integer between 1 and 65535

**Webhook returns 401**
`API_KEY` is set but the request is missing or has an incorrect
`Authorization: Bearer <key>` header.

## References

- [RFC 5575](https://www.rfc-editor.org/rfc/rfc5575) -- Dissemination of
  Flow Specification Rules
- [RFC 8955](https://www.rfc-editor.org/rfc/rfc8955) -- Dissemination of
  Flow Specification Rules (revised)
- [RFC 8956](https://www.rfc-editor.org/rfc/rfc8956) -- Dissemination of
  Flow Specification Rules for IPv6
- [ExaBGP documentation](https://github.com/Exa-Networks/exabgp)
