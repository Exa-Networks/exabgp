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
   # Mitigate: drop UDP traffic from 203.0.113.0/24 to port 53
   curl -X POST http://localhost:5000/ \
     -H 'Content-Type: application/json' \
     -d '{
       "action": "mitigate",
       "source": "203.0.113.0/24",
       "destination": "198.51.100.0/24",
       "protocol": "udp",
       "port": 53,
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
       "port": 53,
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
| `destination`  | string | no*      | Destination prefix                       |
| `protocol`    | string | no       | `"tcp"`, `"udp"`, `"icmp"`, etc.         |
| `port`        | int    | no       | Destination port number                  |
| `attack_id`   | string | no       | Identifier for logging                   |

\* At least one of `source` or `destination` is required.

## Environment variables

| Variable       | Default | Description                          |
|----------------|---------|--------------------------------------|
| `WEBHOOK_PORT` | `5000`  | Port for the HTTP webhook listener   |
| `RATE_LIMIT`   | `0`     | FlowSpec rate-limit (0 = drop)       |
| `LOG_LEVEL`    | `INFO`  | Logging verbosity                    |

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
- For production use, consider adding authentication to the webhook
  endpoint (e.g. an API key header check) and binding to 127.0.0.1
  instead of 0.0.0.0.
