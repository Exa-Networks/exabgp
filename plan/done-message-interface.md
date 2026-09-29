# BGP message interface: one explicit contract for every message

**Status:** ✅ Completed
**Started:** 2026-09-28
**Last Updated:** 2026-09-29

## Goal

Every class under `Message` follows the same contract, written down and checked by a test,
so the contract can become a spec. Wire output and API output stay byte for byte the same:
the functional encoding and decoding tests are the proof.

## The contract

```
Message
  ID: ClassVar[_MessageCode]          the type octet (RFC 4271 4.1)
  TYPE: ClassVar[bytes]               derived from ID by __init_subclass__, never declared
  LENGTH_MIN / LENGTH_MAX             whole message, header included, replaces Message.Length
  _packed                             the body, the one source of truth
  __init__(packed)                    trusted bytes, asserts invariants
  make_<name>(fields...)              the only way to build from fields
  unpack_message(body, negotiated)    peer bytes, raises Notify, returns cls
  pack_body(negotiated) -> Buffer     what a subclass implements
  pack_message(negotiated) -> bytes   @final: header + pack_body
  __eq__ / __hash__                   on (ID, body), in the base
```

## Decisions

- **Signals are not messages.** NOP, AWAKE, DONE, `Scheduling` and `SCHEDULING` go. Only
  `_NOP` was used, and only to mean "nothing was read": `read_message()` returns
  `Message | None`.
- **EOR is an Update.** `EOR(Update)` is bytes-first, `Update.unpack_message` returns an
  `Update`. `EOR.data` is an `UpdateCollection` marked as an End-of-RIB by a real field,
  not by identity in a cache, so the encoders stop needing `getattr(..., 'IS_EOR')` and
  `processes._update` stops casting.
- **UpdateCollection is not a Message.** It builds UPDATEs; it frames them with the
  module level helper rather than by inheriting `_message`.
- **Notify is composition, not a subclass with another constructor.** (step 6, design
  confirmed when reached)
- **Operational is bytes-first.** Router-id and sequence left at zero mean "fill at send",
  which is what the current code already does with falsy values.
- **No `__slots__`** in this work: Notification is also an Exception, and mypyc is its own
  plan (`plan-mypyc.md`).
- **No commits** without Thomas asking. A patch goes to `.claude/backups/` after each step.

## Steps

| # | Step | Verification | Status |
|---|------|--------------|--------|
| 1 | Contract test `tests/unit/bgp/message/test_message_contract.py`, failing | pytest on it | ✅ fails at collection, as it should |
| 2 | Signals: remove NOP/AWAKE/DONE/Scheduling; `read_message() -> Message \| None`; fix `_UPDATE` fast path | unit + functional | ✅ |
| 3 | Base: TYPE derived, LENGTH_MIN/MAX, `pack_body` + final `pack_message`, eq/hash | unit + functional | ✅ |
| 4 | Open bytes-first (`_packed` is the whole body) | unit + functional | ✅ |
| 5 | EOR(Update), UpdateCollection out of Message, EOR marker as a field | unit + functional | ✅ |
| 6 | Notification / Notify | unit + functional | ✅ |
| 7 | Operational bytes-first, UPPER constants, registry raises on duplicate, sequence bug | unit + functional | ✅ |
| 8 | Spec: `.claude/exabgp/BGP_MESSAGE_INTERFACE.md` table per message, contract test green | `./qa/bin/test_everything` | ✅ |

## Bugs found on the way

- `SequencedOperationalFamily.pack_message`: without a router-id the sequence is read under
  key `None` and written under the sent router-id, so it is always 1.
- `reactor/protocol.py` returns `_UPDATE`, an `UpdateCollection`, from `read_message()` on
  the fast path (no role, no adj-rib-in, no API, no route logging). `UpdateHandler` then
  reads `.data`, which `UpdateCollection` does not have.

## Notes from step 2

- The `_UPDATE` fast path is removed rather than repaired: skipping the decode also skipped
  the prefix limit (RFC 4486), the End-of-RIB record (RFC 7313) and the RFC 7606 checks.
  Regression test: `tests/unit/test_read_update_without_rib_in.py`.
- `Protocol.log_routes` existed only for the fast path, and is gone.
- `new_update()` returns the number of messages sent, `new_eors()` returns None: both used
  to return the `_UPDATE` placeholder, which no caller read.
- 252 (the old NOP code) is no longer in `Message.CODE.MESSAGES`, so the reactor refuses it
  with Bad Message Type at its membership check, the answer `Message.unpack` gave anyway.
- An UPDATE carrying INTERNAL_DISCARD still returns None, so it does not restart the hold
  timer, as before. RFC 4271 says a received UPDATE does restart it: not changed here.
- `tests/unit/test_singleton_copy.py` `MIN_COMPARISONS_FOUND` lowered 18 -> 16: the four
  `Scheduling` comparisons left with the class. Flag it to Thomas.
- `scheduling.py` deleted with Thomas's permission.

## Notes from steps 3 to 5

- `FIXED_SIZE` is the part of the body every message of a type has; `LENGTH_MIN` is derived
  from it like `TYPE` from `ID`. It replaces `Open.HEADER_SIZE`/`MINIMUM_BODY_SIZE` (the pair
  whose confusion was an earlier bug), `Notification.HEADER_SIZE` and `RouteRefresh.LENGTH`.
- `Message.Length` (a table of lambdas) is gone: `Message.length_valid(code, length)` asks the
  registered class. OPERATIONAL now has a minimum (23): a shorter one is refused at the header
  with 1/2 rather than by the decoder with 5/0. OPEN has a maximum of 4096 (RFC 8654 3).
- Found, not changed: the header check refuses a ROUTE-REFRESH which is not 23 octets with 1/2,
  so `RouteRefresh.unpack_message`'s 7/1 (RFC 7313 5) can never be reached from the wire.
- Open keeps its whole body. `make_open` packs the capabilities once, so tests which stored a
  bare list or int in `Capabilities` (never valid, never packed before) now use real
  `MultiProtocol`/`ASN4` objects.
- `Update(packed)` only: `parse(negotiated)` decodes, `data` reads. `EOR(Update)` stores one of
  the two RFC 4724 bodies; a received EOR in another form is stored in the canonical one.
- `UpdateCollection` is not a Message. Its End-of-RIB mark is a field (`make_eor`), not the
  identity of a cached singleton; its `nlris` then holds the `EOR_NLRI`, as `EOR.nlris` does.
- Thomas: "do not use isinstance if you can use another way", "better have interface and
  class fields instead". Written into EXA_STYLE.md ("Ask the object, not its class"),
  CODING_STANDARDS.md, ESSENTIAL_PROTOCOLS.md and CLAUDE.md. Message dispatch uses `ID`,
  `IS_EOR` and a `cast` after the check.

## Notes from step 6 (Thomas chose "composition, fix .data")

- `Notification(Message)` is the message both ways, not an exception. `data` is the Data field
  as on the wire, `text` the display form (the RFC 9003 decoding which `data` used to be).
- `Notify(Exception)` holds `.notification`; `code`, `subcode`, `data`, `detail` answer through
  it. The reactor sends `notify.notification`.
- `NotificationReceived(Exception)` is what the reactor raises for one a peer sent. Neither
  exception subclasses the other: the handler order in `Peer` no longer matters.
- API change: a received notification's JSON `data`/`message`, and text `data`, now show the
  raw Data field (an RFC 9003 length octet included) rather than the display text. Pinned by
  `test_a_received_shutdown_communication_is_reported_as_the_peer_sent_it`.

## Notes from steps 7 and 8

- Base `__eq__`/`__hash__` on `(ID, bytes(_packed))` came last, once every class stored its
  body (it was listed under step 3). `RouteRefresh` lost its own `__eq__`/`__ne__`, and its
  `request/start/end` became `REQUEST/BEGIN/END`, taken from `Reserved`.
- Operational is bytes-first: `make_advisory`, `make_query`, `make_counter`, `make_ns`,
  `make_unknown`, and `from_values` for the configuration. Class constants are UPPER:
  `SUBTYPE` (the table, was `CODE`), `SUBTYPE_ID` (was `code`), `NAME`, `CATEGORY`,
  `HAS_FAMILY`, `HAS_ROUTERID`, `IS_FAULT`. `register_operational` refuses a duplicate.
- Sequence bug fixed, and shown on HEAD: three queries without a sequence went out
  `[1, 1, 1]`. `tests/unit/test_operational_sequence.py`. Packing no longer changes the message.
- A received advisory longer than 2048 octets is kept as received; only `make_advisory` cuts.
- `rpcq ... sequence -1` is refused by the configuration (it crashed the send before):
  `forms_operational.py` and the frozen legacy digests updated, two entries of 5883.
- Thomas asked why `NS._NS` and not `NS.NS`: the groups' shared layouts are now
  `NS.NS`, `Advisory.Advisory`, `Query.Query`, `Response.Counter`; a class with no `NAME`
  is one which is never sent, and the contract test finds them by that field.
- The derived-field guards in `Message.__init_subclass__` raise TypeError, not assert: the
  `optimised` suite (-O) caught it.
- Spec: `.claude/exabgp/BGP_MESSAGE_INTERFACE.md`, referenced from CLAUDE.md (#21).
- CHANGELOG: the API change and the three fixes.

## Flakes which are not this work (both fail at HEAD)

- `tests/unit/test_util.py::TestDNS` under xdist.
- `tests/unit/test_otc_parsing.py::test_inline_encode_literal_otc[ipv4...]` fails whenever
  `tests/unit/configuration/test_configuration_export.py` (or `config_grammar/test_roundtrip.py`)
  ran before it on the same worker. Reproduced on a HEAD worktree: a test isolation bug.

## Recent Failures

### 2026-09-28 baseline: 22 unit failures
**Error:** subprocess tests raised `ImportError: cannot import name '_NOP'`.
**Cause:** the baseline `test_everything` ran while step 2 was half applied.
**Status:** ✅ not a regression; functional suites green after step 2.

## Resume Point

Done. Committed as f2a84e65b..253548b86 (six commits, one per step, each green with
`test_everything`). The ROUTE-REFRESH 7/1 found in step 3 is fixed in 2cacf8d75,
see `done-route-refresh-length.md`.
