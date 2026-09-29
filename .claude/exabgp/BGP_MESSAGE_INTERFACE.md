# BGP message interface

**What it is:** the contract every class under `Message` keeps, and what each message is.
**Enforced by:** `tests/unit/bgp/message/test_message_contract.py`, which walks every
subclass of `Message`, so a message added later is held to it without being listed.
**Code:** `src/exabgp/bgp/message/`

---

## 1. The contract

A message is its bytes. It stores the body it was built from, reads every field from it,
and is built from fields by one factory.

| Member | Kind | Rule |
|---|---|---|
| `ID` | `ClassVar[int]` | the type octet (RFC 4271 4.1); the only thing a subclass must declare |
| `TYPE` | `ClassVar[bytes]` | `bytes([ID])`, derived by `Message.__init_subclass__`; declaring it fails |
| `FIXED_SIZE` | `ClassVar[int]` | the octets of the body every message of the type has |
| `LENGTH_MIN` | `ClassVar[int]` | `HEADER_LEN + FIXED_SIZE`, derived; declaring it fails |
| `LENGTH_MAX` | `ClassVar[int]` | the whole message, header included; 65535 unless the type says less |
| `HEADER_CHECKS_LENGTH` | `ClassVar[bool]` | True: the header answers a length outside the bounds with 1/2. False: the decoder does, for a type whose RFC gives its own error (ROUTE-REFRESH) |
| `_packed` | `Buffer` | the body, the one source of truth |
| `__init__(packed)` | constructor | trusted bytes only: what a factory built or `unpack_message` checked |
| `make_<name>(...)` | classmethod | builds the body from fields |
| `unpack_message(body, negotiated)` | classmethod | peer bytes: checks them, raises `Notify`, returns an instance |
| `pack_body(negotiated)` | method | what a subclass implements: the body to send |
| `pack_message(negotiated)` | `@final` | header + `pack_body()`; never overridden |
| `__eq__` / `__hash__` | base only | on `(ID, bytes(_packed))`: two messages are equal when their bytes are |

`Message.length_valid(code, length)` asks the registered class for its bounds. A type
nobody registered is bounded by the header only: it is refused by its type (1/3).
`Message.header_refuses(code, length)` is what the connection asks: the same, except for a
type with `HEADER_CHECKS_LENGTH` False, whose decoder must then refuse every other length
(the contract test checks it does).

`Message.frame(code, body)` is the framing, for code which builds a body without an
instance (`UpdateCollection.messages()`).

**Ask the object, not its class.** Dispatch on `message.ID`, `update.IS_EOR`, and cast after
the check (`.claude/EXA_STYLE.md`, "Ask the object, not its class").

## 2. The messages

| Class | ID | FIXED_SIZE | LENGTH_MAX | Factory | Fields |
|---|---|---|---|---|---|
| `Open` | 1 | 10 | 4096 (RFC 8654 3) | `make_open(version, asn, hold_time, router_id, capabilities)` | `version`, `asn`, `hold_time`, `router_id`, `capabilities` |
| `Update` | 2 | 4 | 65535 | none: built by `UpdateCollection.messages()` | `payload`, `withdrawn_bytes`, `attribute_bytes`, `nlri_bytes`, `data` after `parse(negotiated)` |
| `EOR(Update)` | 2 | 4 | 65535 | `make_eor(afi, safi)` | `afi`, `safi`, `nlris`, `attributes`, `data` |
| `Notification` | 3 | 2 | 65535 | `make_notification(code, subcode, data)` | `code`, `subcode`, `data` (the Data field), `text` (its display form) |
| `KeepAlive` | 4 | 0 | 19 | `make_keepalive()` | none |
| `RouteRefresh` | 5 | 4 | 23 | `make_route_refresh(afi, safi, reserved)` | `afi`, `safi`, `reserved` (`REQUEST`, `BEGIN`, `END`) |
| `Operational` | 6 | 4 | 65535 | per group, below | `what`, `payload` |

### UPDATE and End-of-RIB

- `Update(packed)` holds the body; `parse(negotiated)` decodes it once, `data` reads the
  decoded `UpdateCollection`. What a body means depends on the session (ADD-PATH, ASN4).
- `EOR` is an `Update` (`IS_EOR` is `True`) whose body is one of the two RFC 4724 forms:
  four zero octets for IPv4 unicast, else an empty MP_UNREACH_NLRI naming the family. An
  End-of-RIB received in another form is stored in the canonical one.
- `UpdateCollection` is not a message: it builds them (`messages()`) and is what `parse()`
  returns. An End-of-RIB collection is marked by a field (`make_eor`, `IS_EOR`).

### NOTIFICATION, and the two exceptions around it

| Class | Is | Raised when |
|---|---|---|
| `Notification` | the message, either way; not an exception | never raised |
| `Notify(Exception)` | an error we tell the peer about; holds `.notification` | anywhere a peer's bytes are wrong |
| `NotificationReceived(Exception)` | a peer told us it closes; holds `.notification` | by the reactor, on reading one |

Neither exception subclasses the other, so handler order does not matter. `Notify(code,
subcode, detail, *, data=None)`: `detail` stays in our log, `data` is a Data field an RFC
defines; without it the detail is sent as text (for 6/2 and 6/4, as an RFC 9003 Shutdown
Communication).

### OPERATIONAL (draft-ietf-idr-operational-message)

The body is `type(2) length(2) payload`. Each class says what it is with class fields:
`SUBTYPE_ID`, `NAME`, `CATEGORY`, `HAS_FAMILY`, `HAS_ROUTERID`, `IS_FAULT`. A class without a
`NAME` is the layout its group shares, and is never sent.

| Group | Classes | Payload | Factory |
|---|---|---|---|
| `Advisory.Advisory` | `ADM` (1), `ASM` (2) | afi(2) safi(1) text | `make_advisory(afi, safi, advisory)` |
| `Query.Query` | `RPCQ` (3), `APCQ` (5), `LPCQ` (7) | afi safi router-id(4) sequence(4) | `make_query(afi, safi, routerid, sequence)` |
| `Response.Counter` | `RPCP` (4), `APCP` (6), `LPCP` (8) | afi safi router-id sequence counter(4) | `make_counter(afi, safi, routerid, sequence, counter)` |
| `NS.NS` | `Malformed` ... `NotFound` (0xFFFF) | afi safi sequence error(2) | `make_ns(afi, safi, sequence)`; sent only, decoded as unknown |
| `UnknownOperational` | any type not registered | as received | `make_unknown(what, data)` |

A router-id or sequence of zero is one not given: `pack_body` fills it for the session, the
router-id of our OPEN and the next sequence for that router-id. The message itself is not
changed by being sent.

`Operational.register_operational` refuses a second class for the same type, as
`Message.register` does.

## 3. What a malformed message is answered with

Checked by the connection, before any decoder (`reactor/network/connection.py`):

| Condition | NOTIFICATION |
|---|---|
| the marker is not all ones | 1/1 |
| length below 19, above the session maximum, or outside the type's bounds (not ROUTE-REFRESH) | 1/2, Data: the length field |
| a type with no decoder | 1/3, Data: the type octet |

Checked by the decoder (`unpack_message`):

| Message | Condition | NOTIFICATION |
|---|---|---|
| OPEN | body shorter than 10 | 1/2 |
| OPEN | version other than 4 | 2/1, Data: 4 |
| OPEN | a malformed optional parameter | from `Capabilities.unpack`, 2/x |
| UPDATE | see `UpdateCollection._parse_payload` and RFC 7606 | 3/x, or treat-as-withdraw |
| NOTIFICATION | never: RFC 4271 6.5 forbids answering one | a short body is read as 0/0 |
| KEEPALIVE | a body | 1/2 (the header check refuses it first) |
| ROUTE-REFRESH | a body other than 4 octets, the peer's OPEN carried Enhanced Route Refresh | 7/1, Data: the whole message (RFC 7313 5) |
| ROUTE-REFRESH | a body other than 4 octets, without that capability | 1/2, Data: the length field |
| OPERATIONAL | shorter than its header or than its length says | 5/0 |
| OPERATIONAL | too short for its group's layout | 5/0 |

## 4. Changing a message

1. Declare `ID`, `FIXED_SIZE`, and `LENGTH_MAX` if the type has one.
2. `__init__(self, packed)`, fields as properties over `_packed`, one `make_<name>`.
3. `unpack_message` checks every read before it makes it and raises `Notify`.
4. `pack_body` returns the body; do not override `pack_message`, `__eq__` or `__hash__`.
5. Add a sample to `test_message_contract.py`: `test_every_class_has_a_sample` fails until you do.
