# DDoS Auto-Mitigation with FlowSpec

This example shows how to use ExaBGP as an automated FlowSpec controller
for DDoS mitigation.  A lightweight HTTP webhook listener receives attack
alerts from a detection system and translates them into FlowSpec
announce/withdraw commands that ExaBGP pushes to upstream routers.

## How it works

```
Detection System                ExaBGP              Upstream Router
(Flowtriq, etc.)               (this example)       (Juniper, Cisco, etc.)
      |                              |                       |
      |-- POST /  {"action":        |                       |
      |    "mitigate", ...}  ------>|                       |
      |                             |-- announce flow       |
      |                             |   route { match ... } |
      |                             |   ------------------>  |
      |                             |                       | (drops/limits
      |                             |                       |  attack traffic)
      |-- POST /  {"action":       |                       |
      |    "clear", ...}  -------->|                       |
      |                             |-- withdraw flow       |
      |                             |   route { match ... } |
      |                             |   ------------------>  |
```

## Quick start

1. Edit `api-ddos-flowspec.conf` with your BGP peering details (ASN,
   addresses, hold-time).

2. Start ExaBGP:

   ```bash
   exabgp ./api-ddos-flowspec.conf
   ```

3. Trigger a mitigation (from your detection system, or manually with
   curl for testing):

   ```bash
   # Mitigate: drop reflected DNS replies from source port 53
   curl -X POST http://localhost:5000/ \
     -H 'Content-Type: application/json' \
     -d '{
       "action": "mitigate",
       "source": "203.0.113.0/24",
       "destination": "198.51.100.0/24",
       "protocol": "udp",
       "source_port": 53,
       "attack_id": "dns-amp-001"
     }'

   # Clear when the attack subsides
   curl -X POST http://localhost:5000/ \
     -H 'Content-Type: application/json' \
     -d '{
       "action": "clear",
       "source": "203.0.113.0/24",
       "destination": "198.51.100.0/24",
       "protocol": "udp",
       "source_port": 53,
       "attack_id": "dns-amp-001"
     }'
   ```

4. List active rules:

   ```bash
   curl http://localhost:5000/
   ```

## Webhook payload

| Field         | Type   | Required | Description                              |
|---------------|--------|----------|------------------------------------------|
| `action`      | string | yes      | `"mitigate"` to announce, `"clear"` to withdraw |
| `source`      | string | no*      | Source prefix (e.g. `"203.0.113.0/24"`)  |
| `destination` | string | no*      | Destination prefix                       |
| `protocol`    | string | no       | `"tcp"`, `"udp"`, `"icmp"`, etc.         |
| `port`        | int    | no       | Destination port number                  |
| `source_port` | int    | no       | Source port number                       |
| `attack_id`   | string | no       | Identifier for logging                   |

\* At least one of `source` or `destination` is required.

All fields are validated before being passed to ExaBGP:
- `source` and `destination` must be valid CIDR prefixes
- `protocol` must be a known IP protocol (tcp, udp, icmp, etc.)
- `port` and `source_port` must be integers between 1 and 65535

## Environment variables

| Variable       | Default     | Description                                     |
|----------------|-------------|-------------------------------------------------|
| `WEBHOOK_PORT` | `5000`      | Port for the HTTP webhook listener              |
| `WEBHOOK_BIND` | `127.0.0.1` | Bind address for the HTTP listener              |
| `API_KEY`      | (none)      | Bearer token for authentication (see below)     |
| `RATE_LIMIT`   | `0`         | FlowSpec rate-limit in bytes/s (0 = drop)       |
| `LOG_LEVEL`    | `INFO`      | Logging verbosity                               |

## Authentication

By default the webhook listener binds to `127.0.0.1`, so only processes on
the same machine can reach it.  This is safe for setups where the detection
system runs locally or sends alerts through a local relay.

To accept webhooks from a remote detection system:

1. Set `WEBHOOK_BIND=0.0.0.0` (or a specific interface address).
2. Set `API_KEY` to a strong random value, e.g.:
   ```bash
   export API_KEY=$(openssl rand -hex 32)
   ```
3. Configure the detection system to include the header:
   ```
   Authorization: Bearer <your-api-key>
   ```

When `API_KEY` is set, all POST requests without a valid
`Authorization: Bearer <key>` header receive a 401 response.
GET requests (listing active rules) are not authenticated.

## Detection systems

This example works with any system that can send HTTP POST requests.
Some platforms that support webhook-based alerting:

- [Flowtriq](https://flowtriq.com) -- DDoS detection with webhook alerts
- Custom sFlow/NetFlow analyzers
- Monitoring systems (Zabbix, Nagios, etc.) with webhook actions

## Notes

- FlowSpec rules require that upstream routers support BGP FlowSpec
  (RFC 5575 / RFC 8955).  Most modern Juniper, Cisco, and Nokia routers
  do.
- The script tracks active rules and deduplicates announcements.
- On ExaBGP shutdown, all announced routes are implicitly withdrawn when
  the BGP session goes down.
- The HTTP server uses `ThreadingHTTPServer` so concurrent webhook calls
  are handled in parallel.
- The server waits for ExaBGP to signal a session-up before accepting
  webhooks (with a 10-second fallback timeout).
- For a more detailed setup guide, see `doc/ddos-flowspec.md`.
