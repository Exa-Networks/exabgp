# Functional Test Architecture

---

## Components

**Orchestrator:** `qa/bin/functional`
- Spawns server + client pairs
- Ports: 1790, 1791, ... (increments per test)
- Runs 72 tests in parallel

**Server:** `qa/sbin/bgp --view test.msg --port 1790`
- Reads expected messages from `.msg`
- Validates received BGP bytes
- Exits on ALL messages received → exit 0 + `"successful"`
- Exits on FIRST unexpected → exit 1 + diagnostic

**Client:** `env exabgp_tcp_port=1790 ./sbin/exabgp -d -p test.conf`
- Connects to server
- Spawns `.run` script (API via pipe)
- Encodes routes → BGP UPDATE → server

---

## Test Files

| File | Content |
|------|---------|
| `.ci` | Config file name: `api-ipv4.conf` |
| `.msg` | Expected hex: `1:raw:FFFF...:001E:02:...` |
| `.conf` | BGP neighbor + API process setup |
| `.run` | Python script: `print("announce ipv4 unicast ...")` |

---

## Flow

```
Server: bind :1790 → read .msg → wait
Client: read .conf → spawn .run → connect :1790 → BGP OPEN → ESTABLISHED
.run → ExaBGP stdin → BGP UPDATE → server
Server: compare bytes → match? success : fail
```

---

## Debug Test

**Normal:**
```bash
./qa/bin/functional encoding A
```

**Debug (2 terminals):**
```bash
# Terminal 1 (start FIRST)
./qa/bin/functional encoding --server A --port 1790

# Terminal 2 (start SECOND)
./qa/bin/functional encoding --client A --port 1790
```

Shows: expected/received messages, validation, errors, tracebacks.

---

## Message Format

```
1:raw:FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:001E:02:00000007...
↑     ↑                                ↑    ↑
|     Marker (16x FF)                  |    Type (02=UPDATE)
|                                      Length (30 bytes)
Connection A, message 1
```

Multi-connection: `A1:raw:...`, `B1:raw:...`

---

## Decode Messages

When server shows "unexpected message":

```bash
cat qa/encoding/test.ci  # Get config path
./sbin/exabgp decode -c etc/exabgp/config.conf "FFFF..."  # Decode received
./sbin/exabgp decode -c etc/exabgp/config.conf "FFFF..."  # Decode expected
# Compare JSON outputs
```

**CRITICAL:** Use `-c <config>` to match test capabilities.

---

## Failure Patterns

| Server | Client | Cause |
|--------|--------|-------|
| Timeout 20s | No errors | Not sending → encoding bug |
| "unexpected message" | No errors | Wrong bytes → encoding diff |
| No connection | Connection refused | Port conflict |
| Early exit | Traceback | Client crash |

---

## Commands

```bash
./qa/bin/functional encoding --short-list  # List tests
./qa/bin/functional encoding               # Run all
./qa/bin/functional encoding A             # Run test A
killall -9 Python                          # Clean up ports (macOS uses capital P)
```

---

## Remember

- Server validates **raw BGP bytes** (exact match)
- `.msg` = hex dump of wire format
- Tests run **in parallel** (unique ports)
- Use `--server`/`--client` to see actual output
- Decode with `-c <config>` for correct capabilities

---

**Updated:** 2025-11-23
