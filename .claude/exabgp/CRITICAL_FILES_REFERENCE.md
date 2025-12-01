# Critical Files Reference

The 20% of files you'll modify 80% of the time - quick navigation guide.

---

## Top 10 Files by Modification Frequency

| Rank | File | Lines | Purpose | When to Modify |
|------|------|-------|---------|----------------|
| 1 | `reactor/api/command/announce.py` | 656 | Route announcements via API | Adding route types, API syntax |
| 2 | `bgp/message/update/__init__.py` | ~400 | UPDATE encoding/decoding | Message format changes |
| 3 | `bgp/message/update/attribute/attributes.py` | 532 | Attribute collection handling | New attributes, parsing logic |
| 4 | `configuration/configuration.py` | 614 | Main config parser | New config syntax |
| 5 | `reactor/peer/peer.py` | 950 | BGP peer protocol handler (async) | Protocol changes, FSM |
| 6 | `bgp/message/update/nlri/nlri.py` | ~300 | NLRI base + registry | New NLRI families |
| 7 | `protocol/family.py` | 442 | AFI/SAFI definitions | New address families |
| 8 | `reactor/loop.py` | 821 | Main reactor event loop | Event handling changes |
| 9 | `rib/outgoing.py` | ~400 | Adj-RIB-Out management | RIB operations |
| 10 | `bgp/neighbor.py` | 653 | Neighbor config/state | Neighbor features |

---

## Files by Change Type

### Adding New NLRI Type

**Must modify:**
1. `protocol/family.py` - Add AFI/SAFI if new (line 28, 54, 143)
2. `bgp/message/update/nlri/{newtype}.py` - Create new file
3. `bgp/message/update/nlri/__init__.py` - Add import
4. `configuration/announce/{newtype}.py` - Add config parser (optional)
5. `tests/unit/bgp/message/update/nlri/test_{newtype}.py` - Add tests
6. `qa/encoding/api-{newtype}.{ci,msg}` - Add functional test

**Example files to reference:**
- Simple: `bgp/message/update/nlri/inet.py`
- Complex: `bgp/message/update/nlri/flow.py`

### Adding New Path Attribute

**Must modify:**
1. `bgp/message/update/attribute/{name}.py` - Create new file
2. `bgp/message/update/attribute/__init__.py` - Add import
3. `bgp/message/update/attribute/attributes.py` - Special handling (optional)
4. `tests/unit/bgp/message/update/attribute/test_{name}.py` - Add tests

**Example files to reference:**
- Simple: `bgp/message/update/attribute/med.py`
- Complex: `bgp/message/update/attribute/aspath.py`

### Adding API Command

**Must modify:**
1. `reactor/api/command/{category}.py` - Add @Command.register function
2. `reactor/api/command/__init__.py` - Import category (if new)
3. `reactor/api/command/registry.py` - Add metadata (optional)
4. `tests/unit/reactor/api/test_command_{name}.py` - Add tests

**Example files to reference:**
- `reactor/api/command/neighbor.py` - Show commands
- `reactor/api/command/announce.py` - Complex parsing

### Modifying Config Syntax

**Must modify:**
1. `configuration/{section}/{subsection}.py` - Parser logic
2. `configuration/configuration.py` - Main parser (if new section)
3. `etc/exabgp/*.conf` - Example configs
4. `tests/unit/configuration/test_{section}.py` - Add tests

**Example files to reference:**
- `configuration/neighbor/parser.py` - Neighbor config
- `configuration/announce/ipvpn.py` - Route announcements

---

## "When You Change X, Update Y" Table

| Change This | Also Update | Reason |
|-------------|-------------|--------|
| `nlri/*.py` pack/unpack signature | All NLRI subclasses | Uniform API |
| `attribute/*.py` pack/unpack signature | All Attribute subclasses | Uniform API |
| `protocol/family.py` add AFI/SAFI | NLRI registration, config parser | New family support |
| `bgp/message/message.py` Message type | FSM validation, peer.py handling | Protocol correctness |
| `bgp/fsm.py` states/transitions | reactor/peer/peer.py state handling | FSM consistency |
| `reactor/api/command/*.py` add command | `registry.py` metadata | Command discovery |
| `bgp/message/open/capability/*.py` | Neighbor negotiation logic | Capability handling |
| `configuration/configuration.py` syntax | Documentation, examples | User-facing |

---

## Stable Interfaces (DO NOT CHANGE)

These signatures are part of the public API - changes break compatibility:

### NLRI Interface
```python
class NLRI:
    def pack_nlri(self, negotiated: Negotiated) -> bytes: pass

    @classmethod
    def unpack_nlri(
        cls, afi, safi, data, action, addpath, negotiated
    ) -> NLRI: pass

    def index(self) -> bytes: pass
```
**Location:** `bgp/message/update/nlri/nlri.py:67, 89`

### Attribute Interface
```python
class Attribute:
    ID = ...  # Attribute code
    FLAG = ...  # Attribute flags

    def pack(self, negotiated: Negotiated) -> bytes: pass

    @classmethod
    def unpack(cls, data: bytes, negotiated: Negotiated) -> Attribute: pass
```
**Location:** `bgp/message/update/attribute/attribute.py:45, 67`

### Message Interface
```python
class Message:
    def pack_message(self, negotiated: Negotiated) -> bytes: pass

    @classmethod
    def unpack_message(cls, data: bytes, negotiated: Negotiated) -> Message: pass
```
**Location:** `bgp/message/message.py:34, 53`

### Configuration File Format
**Location:** `etc/exabgp/*.conf`

Breaking changes require major version bump and migration guide.

---

## Example Files to Understand Deeply

### 1. Simple NLRI Type
**File:** `bgp/message/update/nlri/inet.py` (~150 lines)

**Why:** Demonstrates:
- Multiple AFI/SAFI registrations
- Basic pack/unpack pattern
- IPv4 vs IPv6 handling
- Index calculation

**Read this first** when adding new NLRI.

### 2. Complex NLRI Type
**File:** `bgp/message/update/nlri/flow.py` (764 lines)

**Why:** Demonstrates:
- Complex TLV encoding
- Multiple component types
- Extensive validation
- Sophisticated parsing

**Read this** for advanced NLRI patterns.

### 3. Simple Attribute
**File:** `bgp/message/update/attribute/med.py` (~50 lines)

**Why:** Demonstrates:
- Minimal attribute implementation
- Pack/unpack pattern
- ID and FLAG constants
- Caching pattern

**Read this first** when adding new attribute.

### 4. Complex Attribute
**File:** `bgp/message/update/attribute/aspath.py` (~400 lines)

**Why:** Demonstrates:
- Multiple encoding formats (AS2 vs AS4)
- Validation logic
- Conversion between formats
- Complex unpacking

**Read this** for advanced attribute patterns.

### 5. API Command Pattern
**File:** `reactor/api/command/neighbor.py` (~300 lines)

**Why:** Demonstrates:
- @Command.register usage
- Neighbor filtering
- JSON output support
- Multiple subcommands

**Read this first** when adding API commands.

### 6. Event Loop Integration
**File:** `reactor/loop.py` (821 lines)

**Why:** Demonstrates:
- Reactor pattern
- Peer lifecycle management
- Signal handling
- Async support (generator vs async)

**Read this** to understand event flow.

### 7. BGP Protocol Handler
**File:** `reactor/peer/peer.py` (950 lines, async-only)

**Why:** Demonstrates:
- FSM implementation
- Message sending/receiving
- Capability negotiation
- Error handling

**Read this** to understand protocol flow.

---

## File Size Guidelines

| Size | Category | Action |
|------|----------|--------|
| < 100 lines | Small | Easy to modify |
| 100-300 lines | Medium | Review carefully |
| 300-600 lines | Large | Modify incrementally |
| 600-1000 lines | Very Large | Consider refactoring |
| > 1000 lines | Huge | Modify with extreme care |

**Files > 500 lines = High complexity - test thoroughly after changes**

---

## Import Dependencies (Critical Path)

### Inbound Message Processing
```
reactor/protocol.py (TCP layer)
  ↓
reactor/peer/peer.py (BGP protocol)
  ↓
bgp/message/message.py (Dispatcher)
  ↓
bgp/message/update/__init__.py (UPDATE parser)
  ↓
bgp/message/update/nlri/nlri.py (NLRI registry)
bgp/message/update/attribute/attributes.py (Attr parser)
```

**Change any file → test entire chain**

### Outbound Message Encoding
```
configuration/configuration.py (Config parser)
  ↓
rib/outgoing.py (RIB storage)
  ↓
bgp/message/update/__init__.py (UPDATE encoder)
  ↓
bgp/message/update/nlri/*.py (NLRI.pack_nlri)
bgp/message/update/attribute/*.py (Attribute.pack)
  ↓
reactor/protocol.py (TCP send)
```

**Change any file → test entire chain**

---

## Testing Requirements by File Type

| File Type | Unit Tests | Functional Tests | Integration Tests |
|-----------|------------|------------------|-------------------|
| NLRI | Required | Required | Optional |
| Attribute | Required | Required | Optional |
| Message | Required | Required | Optional |
| Configuration | Required | Optional | Optional |
| API Command | Required | Optional | Required |
| Reactor/Protocol | Optional | Required | Required |

**See:** `TESTING_PROTOCOL.md` for details

---

## Quick Navigation Patterns

### "I need to add support for..."

**...a new route type:**
→ Start: `bgp/message/update/nlri/`
→ Reference: `inet.py` (simple) or `flow.py` (complex)

**...a new path attribute:**
→ Start: `bgp/message/update/attribute/`
→ Reference: `med.py` (simple) or `aspath.py` (complex)

**...a new CLI command:**
→ Start: `reactor/api/command/`
→ Reference: `neighbor.py`

**...new config syntax:**
→ Start: `configuration/`
→ Reference: `configuration.py` (main parser)

**...debugging a protocol issue:**
→ Start: `reactor/peer/peer.py`
→ Tools: Enable debug logging, packet capture

**...debugging message encoding:**
→ Start: `bgp/message/update/__init__.py`
→ Tools: `./sbin/exabgp decode`, hex dumps

---

## Lines of Code by Directory

| Directory | Approx LOC | Complexity | Modification Freq |
|-----------|------------|------------|-------------------|
| `bgp/message/update/nlri/` | ~5000 | High | High |
| `bgp/message/update/attribute/` | ~4000 | Medium-High | High |
| `reactor/` | ~8000 | High | Medium |
| `configuration/` | ~6000 | Medium | Medium |
| `bgp/message/` | ~3000 | Medium | Low |
| `rib/` | ~1500 | Medium | Medium |
| `application/` | ~4000 | Low-Medium | Low |

---

**See also:**
- `CODEBASE_ARCHITECTURE.md` - Complete directory structure
- `DATA_FLOW_GUIDE.md` - How files interact
- `REGISTRY_AND_EXTENSION_PATTERNS.md` - Modification patterns
- `BGP_CONCEPTS_TO_CODE_MAP.md` - Concept to file mapping

---

**Updated:** 2025-11-24
