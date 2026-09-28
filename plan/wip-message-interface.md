# BGP message interface: one explicit contract for every message

**Status:** 🔄 Active
**Started:** 2026-09-28
**Last Updated:** 2026-09-28

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
| 3 | Base: TYPE derived, LENGTH_MIN/MAX, `pack_body` + final `pack_message`, eq/hash | unit + functional | ⏳ |
| 4 | Open bytes-first (`_packed` is the whole body) | unit + functional | ⏳ |
| 5 | EOR(Update), UpdateCollection out of Message, EOR marker as a field | unit + functional | ⏳ |
| 6 | Notification / Notify | unit + functional | ⏳ |
| 7 | Operational bytes-first, UPPER constants, registry raises on duplicate, sequence bug | unit + functional | ⏳ |
| 8 | Spec: `doc/` table per message, contract test green | `./qa/bin/test_everything` | ⏳ |

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

## Recent Failures

### 2026-09-28 baseline: 22 unit failures
**Error:** subprocess tests raised `ImportError: cannot import name '_NOP'`.
**Cause:** the baseline `test_everything` ran while step 2 was half applied.
**Status:** ✅ not a regression; functional suites green after step 2.

## Resume Point

Step 3.
