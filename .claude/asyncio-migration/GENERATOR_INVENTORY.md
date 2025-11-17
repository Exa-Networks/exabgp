# Generator Function Inventory

Complete list of all generators in ExaBGP codebase.

**Total:** ~150 generators across 44 files

---

## Critical Path (Converting)

### Event Loop & Core (2 generators)

| File | Function | Complexity | Priority |
|------|----------|-----------|----------|
| `reactor/loop.py` | `_wait_for_io()` | Simple | HIGH |
| `reactor/asynchronous.py` | N/A | ✅ DONE | N/A |

---

### Peer State Machine (9 generators)

| File | Function | Complexity | Priority |
|------|----------|-----------|----------|
| `reactor/peer.py` | `_connect()` | Medium | CRITICAL |
| `reactor/peer.py` | `_send_open()` | Medium | CRITICAL |
| `reactor/peer.py` | `_read_open()` | Medium | CRITICAL |
| `reactor/peer.py` | `_send_keepalive()` | Simple | HIGH |
| `reactor/peer.py` | `_read_keepalive()` | Medium | HIGH |
| `reactor/peer.py` | `_send_update()` | Medium | HIGH |
| `reactor/peer.py` | `_read_update()` | Medium | HIGH |
| `reactor/peer.py` | `_send_notification()` | Simple | HIGH |
| `reactor/peer.py` | `_read_notification()` | Medium | HIGH |

---

### Protocol Handler (14 generators)

| File | Function | Complexity | Priority |
|------|----------|-----------|----------|
| `reactor/protocol.py` | `read_message()` | Medium | CRITICAL |
| `reactor/protocol.py` | `write()` | Medium | CRITICAL |
| `reactor/protocol.py` | `read_open()` | Medium | CRITICAL |
| `reactor/protocol.py` | `write_open()` | Simple | CRITICAL |
| `reactor/protocol.py` | `read_keepalive()` | Simple | HIGH |
| `reactor/protocol.py` | `write_keepalive()` | Simple | HIGH |
| `reactor/protocol.py` | `read_update()` | Complex | HIGH |
| `reactor/protocol.py` | `write_update()` | Medium | HIGH |
| `reactor/protocol.py` | `read_notification()` | Medium | HIGH |
| `reactor/protocol.py` | `write_notification()` | Simple | HIGH |
| `reactor/protocol.py` | `read_operational()` | Medium | MEDIUM |
| `reactor/protocol.py` | `write_operational()` | Simple | MEDIUM |
| `reactor/protocol.py` | `_reader_factory()` | Complex | HIGH |
| `reactor/protocol.py` | `_writer_factory()` | Complex | HIGH |

---

### Network Layer (31 generators)

**connection.py (3):**
| Function | Complexity | Priority |
|----------|-----------|----------|
| `reader()` | Complex | HIGH |
| `_reader()` | Complex | HIGH |
| `writer()` | Medium | HIGH |

**tcp.py (4):**
| Function | Complexity | Priority |
|----------|-----------|----------|
| `connect()` | Medium | HIGH |
| `accept()` | Medium | HIGH |
| `send()` | Medium | HIGH |
| `receive()` | Medium | HIGH |

**incoming.py (5):**
| Function | Complexity | Priority |
|----------|-----------|----------|
| `new_connections()` | Medium | HIGH |
| `_accept_connection()` | Medium | HIGH |
| `_check_listening()` | Simple | MEDIUM |
| `_bind_socket()` | Simple | MEDIUM |
| `_setup_listener()` | Simple | MEDIUM |

**outgoing.py (6):**
| Function | Complexity | Priority |
|----------|-----------|----------|
| `establish()` | Medium | HIGH |
| `_create_socket()` | Simple | MEDIUM |
| `_connect_socket()` | Medium | HIGH |
| `_handshake()` | Medium | HIGH |
| `_setup_connection()` | Simple | MEDIUM |
| `_validate_peer()` | Simple | MEDIUM |

**Various network utilities (13):**
| File | Count | Complexity | Priority |
|------|-------|-----------|----------|
| `network/error.py` | 2 | Simple | LOW |
| `network/check.py` | 3 | Simple | LOW |
| `network/socket.py` | 4 | Medium | MEDIUM |
| `network/poll.py` | 2 | Simple | MEDIUM |
| `network/buffer.py` | 2 | Simple | LOW |

---

### RIB Management (3 generators)

| File | Function | Complexity | Priority |
|------|----------|-----------|----------|
| `rib/outgoing.py` | `updates()` | Medium | MEDIUM |
| `rib/outgoing.py` | `withdraws()` | Medium | MEDIUM |
| `rib/cache.py` | `cached_updates()` | Simple | LOW |

---

### API Commands (45 generators)

**announce.py (30):**

All follow the nested generator pattern. Complexity: Medium-High (nested)

| Command Group | Count | Priority |
|---------------|-------|----------|
| `announce route / withdraw route` | 2 | HIGH |
| `announce vpn / withdraw vpn` | 2 | HIGH |
| `announce flow / withdraw flow` | 2 | HIGH |
| `announce l2vpn / withdraw l2vpn` | 2 | HIGH |
| `announce vpls / withdraw vpls` | 2 | MEDIUM |
| `announce evpn / withdraw evpn` | 2 | MEDIUM |
| `announce operational / withdraw operational` | 2 | MEDIUM |
| Various attribute commands | 16 | MEDIUM |

**Other API handlers (15):**
| File | Function | Complexity | Priority |
|------|----------|-----------|----------|
| `api/rib.py` | `show_rib()` | Medium | MEDIUM |
| `api/neighbor.py` | `show_neighbors()` | Simple | MEDIUM |
| `api/neighbor.py` | `neighbor_action()` | Medium | MEDIUM |
| `api/watchdog.py` | `watchdog()` | Medium | MEDIUM |
| `api/reactor.py` | `reactor_status()` | Simple | LOW |
| `api/processes.py` | `receive_api_commands()` | Complex | HIGH |
| Others | 9 | Various | MEDIUM |

---

## Excluded from Migration (Skip)

### Parsing Generators (43 total)

**BGP UPDATE parsing (16):**
| File | Count | Complexity | Skip? |
|------|-------|-----------|-------|
| `bgp/message/update/attribute/*.py` | 8 | Complex | YES |
| `bgp/message/update/nlri/*.py` | 8 | Complex | YES |

**Configuration parsing (27):**
| File | Count | Complexity | Skip? |
|------|-------|-----------|-------|
| `configuration/tokeniser.py` | 10 | Complex | YES |
| `configuration/format.py` | 5 | Medium | YES |
| `configuration/flow/parser.py` | 8 | Complex | YES |
| `configuration/neighbor.py` | 4 | Medium | YES |

### Utility Generators (35 total)

**CLI/Environment (15):**
| File | Count | Complexity | Skip? |
|------|-------|-----------|-------|
| `application/cli.py` | 3 | Medium | YES |
| `environment.py` | 4 | Simple | YES |
| `application/completer.py` | 5 | Medium | YES |
| `application/healthcheck.py` | 3 | Simple | YES |

**Netlink/System (10):**
| File | Count | Complexity | Skip? |
|------|-------|-----------|-------|
| `reactor/netlink/*.py` | 10 | Complex | YES |

**Other utilities (10):**
| Various files | 10 | Various | YES |

### Test Generators (3 total - DO NOT MODIFY)

| File | Function | Purpose |
|------|----------|---------|
| `tests/unit/test_connection_advanced.py` | 22 functions | Connection testing |
| `tests/fuzz/test_connection_reader.py` | 2 functions | Fuzz testing |
| `tests/unit/test_route_refresh.py` | 1 function | Route refresh |

---

## Summary by Complexity

| Complexity | Count | Convert? |
|-----------|-------|----------|
| Simple (1 yield) | ~40 | ✅ YES (Phase 0) |
| Medium (2-5 yields) | ~60 | ✅ YES (Phase 2) |
| Complex (6+, nested) | ~50 | ✅ YES (Phase 3) |
| Parsing/Config | ~78 | ❌ NO (skip) |
| Tests | ~3 | ❌ NO (stable) |

---

## Conversion Priority

**Phase 0 Targets (Simple):**
- `loop._wait_for_io()` ← Start here
- Network error handlers (2)
- Simple checks (3)
- Buffer helpers (2)
- **Total:** ~8 functions

**Phase 1 Dependencies:**
- Event loop integration required first

**Phase 2 Targets (Medium - Network/Protocol):**
- Connection I/O (3)
- TCP operations (4)
- Protocol message handlers (14)
- Network utilities (13)
- **Total:** ~34 functions

**Phase 3 Targets (Complex - API):**
- API command handlers (45)
- **Total:** ~45 functions

**Grand Total Converting:** ~87 generators
**Grand Total Skipping:** ~81 generators (parsing/config/tests)

---

**Updated:** 2025-11-16
