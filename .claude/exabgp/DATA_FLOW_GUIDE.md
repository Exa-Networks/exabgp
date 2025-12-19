# Data Flow Guide

**Quick Summary:** Network → Reactor → Message → NLRI/Attributes → API (inbound). Config → RIB → Update → Protocol → Network (outbound).

**Full content:** 9 KB - Read on-demand when implementing features or debugging message flow.

---

How information flows through ExaBGP - inbound, outbound, and internal routing.

---

## Overview

ExaBGP operates on three main data flows:

1. **Inbound:** Network → Parse → Process → API output
2. **Outbound:** Config/API → RIB → Encode → Network
3. **Internal:** RIB management, route storage, change tracking

---

## Inbound Flow (Receiving BGP Messages)

### Step-by-Step

```
1. Network Socket (TCP 179)
   ↓
2. reactor/protocol.py
   - read_message() reads bytes from socket
   - Checks BGP marker (16 bytes of 0xFF)
   - Extracts length (2 bytes) and type (1 byte)
   ↓
3. reactor/peer/peer.py
   - receive_message() coordinates message handling
   - Validates message in current FSM state
   ↓
4. bgp/message/message.py
   - Message.unpack(msg_type, data, negotiated)
   - Dispatches to registered message handler via registry
   ↓
5. Message Type Specific (e.g., UPDATE)
   bgp/message/update/__init__.py
   - Update.unpack_message(data, negotiated)
   - Splits into: withdrawn routes, attributes, announced routes
   ↓
6a. Parse Withdrawn Routes
   - Length field (2 bytes)
   - NLRI.unpack_nlri() for each withdrawn prefix
   ↓
6b. Parse Path Attributes
   bgp/message/update/attribute/attributes.py
   - Attributes.unpack(data, negotiated)
   - For each attribute:
     - Extract flags (1 byte), code (1 byte), length (1-2 bytes)
     - Dispatch to Attribute.registered[code].unpack()
   - Returns Attributes object (dict-like)
   ↓
6c. Parse Announced Routes (NLRI)
   bgp/message/update/nlri/nlri.py
   - NLRI.unpack_nlri(afi, safi, data, negotiated)
   - Dispatches via registered_nlri[(afi, safi)]
   - Returns list of NLRI objects
   ↓
7. Create Change Objects
   rib/change.py
   - Change(nlri, attributes) for announcements
   - Change(nlri, None) for withdrawals
   ↓
8. Update RIB
   rib/incoming.py
   - Store received routes (Adj-RIB-In)
   - Track per-neighbor
   ↓
9. Send to API Processes
   reactor/api/transcoder.py
   - Encode route as JSON or text
   reactor/api/processes.py
   - Write to external process stdin
   - Format: "neighbor <ip> <family> <nlri> <attributes>"
```

### Key Files (Inbound)
- `reactor/protocol.py` - `read_message()`
- `bgp/message/message.py` - `Message.unpack()`
- `bgp/message/update/__init__.py` - `Update.unpack_message()`
- `bgp/message/update/attribute/collection.py` - `Attributes.unpack()`
- `bgp/message/update/nlri/nlri.py` - `NLRI.unpack_nlri()`

---

## Outbound Flow (Sending BGP Messages)

### Step-by-Step

```
1a. Configuration File
   etc/exabgp/*.conf
   ↓
1b. OR API Command
   "announce route <nlri> <attributes>"
   ↓
2. Configuration Parsing
   configuration/configuration.py
   - parse() reads config file
   - Builds Neighbor objects (dict-like)
   - Parses static routes into Change objects
   ↓
   OR API Command Parsing
   reactor/api/command/announce.py
   - Parses text command into NLRI + Attributes
   - Creates Change object
   ↓
3. Store in RIB
   rib/outgoing.py
   - insert_announced() adds Change to Adj-RIB-Out
   - Indexed by: neighbor, family, nlri.index()
   - Tracks what each neighbor should receive
   ↓
4. Reactor Determines What to Send
   reactor/loop.py + reactor/peer/peer.py
   - Check peer FSM state (must be ESTABLISHED)
   - Check if routes pending for this peer
   - Group changes by family
   ↓
5. Encode UPDATE Message
   bgp/message/update/__init__.py
   - Update(nlri_list, attributes, withdrawn_list)
   - pack_message(negotiated):
     a. Pack withdrawn routes
        - Length (2 bytes)
        - Each NLRI.pack_nlri(negotiated)
     b. Pack attributes
        - For each attribute: Attribute.pack(negotiated)
        - Length prefix (2 bytes)
     c. Pack announced NLRI
        - Each NLRI.pack_nlri(negotiated)
   ↓
6. Add BGP Header
   bgp/message/message.py
   - Marker (16 bytes: 0xFF...)
   - Length (2 bytes: total message length)
   - Type (1 byte: UPDATE = 2)
   ↓
7. Send to Network
   reactor/protocol.py
   - write() sends bytes to TCP socket
   ↓
8. Track Sent Routes
   rib/outgoing.py
   - Mark as sent (for tracking)
   - Used for flush/withdraw operations
```

### Key Files (Outbound)
- `configuration/configuration.py` - `parse()`
- `reactor/api/command/announce.py` - API route parsing
- `rib/outgoing.py` - `insert_announced()`
- `bgp/message/update/__init__.py` - `Update.pack_message()`
- `bgp/message/update/attribute/attribute.py` - `Attribute.pack()`
- `bgp/message/update/nlri/nlri.py` - `NLRI.pack_nlri()`

---

## RIB (Routing Information Base) Operations

### Structure

```
RIB (rib/__init__.py)
├── Incoming (rib/incoming.py)
│   - Adj-RIB-In: Routes received from neighbors
│   - Indexed by: neighbor → family → nlri
│   - Used for: show neighbor adj-rib in
│
└── Outgoing (rib/outgoing.py)
    - Adj-RIB-Out: Routes to advertise to neighbors
    - Indexed by: neighbor → family → nlri.index()
    - Used for: announcements, withdrawals, flush
```

### Change Object (rib/change.py)

Core data structure combining NLRI + Attributes:

```python
Change(nlri, attributes=None)
  - nlri: NLRI object (route prefix/identifier)
  - attributes: Attributes object (path attributes) or None (withdrawal)
  - index(): Unique identifier for deduplication
  - pack(negotiated): Encode as BGP UPDATE
```

### Key Operations

**Insert announced route:**
```
rib.outgoing.insert_announced(peer, change)
  → Stores in: outgoing[peer][family][nlri.index()] = change
```

**Insert withdrawn route:**
```
rib.outgoing.insert_withdrawn(peer, change)
  → Stores in: withdrawn[peer][family][nlri.index()] = change
```

**Get routes to send:**
```
rib.outgoing.queued(peer)
  → Returns: List of Change objects pending for peer
```

**Flush all routes for neighbor:**
```
rib.outgoing.flush(peer)
  → Withdraws all routes advertised to that peer
```

---

## Parsing Pipeline Details

### UPDATE Message Structure (RFC 4271)

```
Bytes:
  0-15:  Marker (0xFF x 16)
  16-17: Length (total message bytes)
  18:    Type (2 = UPDATE)
  19-20: Withdrawn Routes Length (N)
  21-20+N: Withdrawn Routes (NLRI)
  21+N - 22+N: Total Path Attribute Length (M)
  23+N - 22+N+M: Path Attributes
  23+N+M - end: Announced Routes (NLRI)
```

### Attribute Parsing

Each attribute has structure:
```
Byte 0:    Flags (Optional, Transitive, Partial, Extended)
Byte 1:    Type Code (1-255)
Byte 2-3:  Length (1 or 2 bytes depending on Extended flag)
Byte 4+:   Value
```

**Flags:**
- `0x40` - Optional
- `0x80` - Transitive
- `0x20` - Partial
- `0x10` - Extended Length

### NLRI Parsing

Format depends on AFI/SAFI:
- **IPv4 Unicast:** Length (1 byte) + Prefix (variable)
- **IPv6 Unicast:** Length (1 byte) + Prefix (variable)
- **VPNv4:** RD (8 bytes) + Label Stack + Length + Prefix
- **FlowSpec:** Complex TLV structure (see flow.py)
- **EVPN:** Route Type (1 byte) + Type-specific structure

---

## Serialization Pipeline Details

### Pack Order (Critical)

When encoding UPDATE:
1. **Withdrawn NLRI** packed first (bgp/message/update/nlri/*.py)
2. **Attributes** packed second (bgp/message/update/attribute/*.py)
3. **Announced NLRI** packed last

**Why order matters:** BGP wire format has fixed structure

### Negotiated Context

`Negotiated` object passed through pack/unpack:
```python
negotiated.families: Set[(AFI, SAFI)] - Enabled address families
negotiated.addpath: Dict[(AFI, SAFI), AddPath] - AddPath support
negotiated.asn4: bool - 4-byte ASN support
negotiated.extended_message: bool - Extended message length
```

**Used for:**
- Determining if family is enabled
- Encoding ASN (2-byte vs 4-byte)
- Adding Path Identifier for AddPath
- Validation during unpack

---

## State Machine Integration

### FSM States (bgp/fsm.py)

```
IDLE → ACTIVE → CONNECT → OPENSENT → OPENCONFIRM → ESTABLISHED
```

**Message flow by state:**
- `IDLE/ACTIVE/CONNECT`: No messages
- `OPENSENT`: Send OPEN → expect OPEN
- `OPENCONFIRM`: Send KEEPALIVE → expect KEEPALIVE
- `ESTABLISHED`: Send/receive UPDATE, KEEPALIVE, NOTIFICATION, ROUTE-REFRESH

**reactor/peer/peer.py enforces:**
- Can only send UPDATE in ESTABLISHED state
- NOTIFICATION can be sent/received in any state
- Invalid message for state → send NOTIFICATION, reset connection

---

## API Process Communication

### Inbound (ExaBGP → External Process)

Format:
```
neighbor <peer-ip> <update-type> <afi> <safi> <nlri> <attributes>
```

Examples:
```
neighbor 10.0.0.1 announced ipv4 unicast 192.168.1.0/24 next-hop 10.0.0.2
neighbor 10.0.0.1 withdrawn ipv4 unicast 192.168.1.0/24
```

**Encoding:** `reactor/api/transcoder.py`

### Outbound (External Process → ExaBGP)

Commands read from process stdout:
```
announce route 192.168.1.0/24 next-hop 10.0.0.2
withdraw route 192.168.1.0/24
```

**Parsing:** `reactor/api/command/announce.py`

---

## Performance Considerations

### Caching

**NLRI index():** Used for deduplication
```python
def index(self):
    return self.pack_nlri(None)  # Cached hash key
```

**Attribute packing:** Some attributes cache packed form

### Memory

- RIB stores full Change objects (NLRI + Attributes)
- Multiple neighbors = multiple copies per route
- Flush operation clears neighbor's Adj-RIB-Out

---

## Error Handling

### Parsing Errors

```
Network bytes → Unpack fails
  ↓
Notification(error_code, error_subcode, data)
  ↓
Send NOTIFICATION to peer
  ↓
Tear down BGP session (FSM → IDLE)
```

**Common errors:**
- Unsupported AFI/SAFI → No registered handler
- Malformed attribute → Attribute.unpack() raises
- Invalid NLRI → NLRI.unpack_nlri() raises

### Encoding Errors

```
Configuration/API → pack() fails
  ↓
Log error locally
  ↓
Don't send UPDATE (protect session)
```

---

**See also:**
- `CODEBASE_ARCHITECTURE.md` - File locations
- `REGISTRY_AND_EXTENSION_PATTERNS.md` - How pack/unpack methods work
- `BGP_CONCEPTS_TO_CODE_MAP.md` - BGP terms to code
- `FUNCTIONAL_TEST_DEBUGGING_GUIDE.md` - Debugging message flow

---

**Updated:** 2025-12-19
