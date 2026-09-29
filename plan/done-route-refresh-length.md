# ROUTE-REFRESH Invalid Message Length (RFC 7313 5) reachable from the wire

**Status:** ✅ Completed
**Created:** 2026-09-28

## The problem

`RouteRefresh.unpack_message` answers a body which is not 4 octets with 7/1, Invalid Message
Length, the Data field holding the whole message. No peer can ever get that answer: the
header check in `reactor/network/connection.py` runs first, `Message.length_valid()` bounds
ROUTE-REFRESH to exactly 23 octets (`FIXED_SIZE = 4`, `LENGTH_MAX = 23`), and a message of
another length is refused there with 1/2, Bad Message Length, its Data the length field.

The ledger (`qa/rfc/rfc7313.toml`, `rfc7313#5-invalid-message-length` and `-data`) reads as
met because its tests call the decoder directly. The daemon does not do what they prove.

## Still required (checked 2026-09-29 at f3b58418f)

The 12 commits since 253548b86 touch none of refresh.py, message.py, connection.py, the
handler, the rfc7313 ledger or its tests. Read from the wire through the header check, a
ROUTE-REFRESH body of 3 or 5 octets is still answered 1/2.

ebf84e5d7 lets a gap be demonstrated by a strict xfail test, so step 0 below records it as
one before it is fixed.

## What the RFC asks

RFC 7313 5:

- applies "only when a BGP speaker has received the Enhanced Route Refresh Capability"
- a message "with Message Subtype 1 and 2" whose body is not 4 octets: 7/1, Data the
  complete ROUTE-REFRESH message
- a subtype other than 0, 1, 2: ignored, SHOULD be logged

RFC 4271 6.1 names type-specific lengths only for OPEN, UPDATE, KEEPALIVE and NOTIFICATION.
RFC 2918 defines ROUTE-REFRESH as 4 octets and no error for another length.

## Design

1. **The header does not bound ROUTE-REFRESH beyond 19 to the session maximum.** A class
   field on `Message`, `HEADER_CHECKS_LENGTH: ClassVar[bool] = True`, says whether RFC 4271
   6.1's Bad Message Length applies to the type's own bounds. `RouteRefresh` sets it False:
   its decoder answers. `length_valid()` keeps meaning "a length this type can have";
   the connection asks `Message.header_refuses(code, length)`, which honours the field.
   LENGTH_MIN and LENGTH_MAX stay 23: they are what the message is, and the contract test
   keeps checking every sample against them.
2. **The decoder decides with what the peer sent.** `unpack_message(data, negotiated)`:
   - Enhanced Route Refresh received from the peer (its OPEN, not the negotiated result:
     the RFC says "received") and the body not 4 octets: 7/1, Data the whole message.
   - not received: 1/2, Data the length field, what the header answered until now.
3. **Subtype.** A body shorter than 3 octets has no subtype to read. Decision needed, see
   below.

## Decisions for Thomas

| # | Question | Recommendation |
|---|----------|----------------|
| 1 | Without the capability, a wrong length is answered with | 1/2 as today (RFC 4271 6.1 spirit, RFC 2918 gives none) |
| 2 | With it, a wrong length and subtype 0 (a plain request) | 7/1 too: the ledger note already says every subtype, and the RFC 7313 message is one message |
| 3 | With it, a wrong length and an unknown subtype (3 to 255) | 7/1: the length is checked before the subtype is trusted, as the ledger note says |
| 4 | OPERATIONAL, bounded at the header since the message-interface work (1/2 rather than the decoder's 5/0) | leave it: the draft names no error of its own |

## Steps (tests first)

| # | Step | Files | Verification |
|---|------|-------|--------------|
| 0 | Mark `rfc7313#5-invalid-message-length` and `-data` as `gap` in the ledger, with a strict xfail test through the reader (see `qa/rfc/README.md`) | `qa/rfc/rfc7313.toml`, `tests/unit/rfc/test_rfc7313_route_refresh_errors.py` | `./qa/bin/check_rfc_compliance` |
| 1 | Failing tests through the reader, not the decoder: a 22 and a 24 octet ROUTE-REFRESH read by `Protocol.read_message` with the capability received gives 7/1 and the whole message as Data; without it, 1/2 and the length field | `tests/unit/rfc/test_rfc7313_route_refresh_errors.py` (use the `_read` helper pattern of `test_rfc4271_message_header.py`) | pytest on the file: fails |
| 2 | `HEADER_CHECKS_LENGTH` on `Message`, False on `RouteRefresh`; `Message.header_refuses()`; the connection's two call sites use it | `bgp/message/message.py`, `bgp/message/refresh.py`, `reactor/network/connection.py` | step 1 tests still fail on the decoder half |
| 3 | `RouteRefresh.unpack_message` chooses 7/1 or 1/2 from the peer's OPEN | `bgp/message/refresh.py` | step 1 tests pass |
| 4 | Contract test: `header_refuses` rows beside `length_valid`, and a check that a class with `HEADER_CHECKS_LENGTH = False` raises Notify from its decoder for every length the header lets through | `tests/unit/bgp/message/test_message_contract.py` | pytest |
| 5 | Existing tests which pinned 1/2 at the header for ROUTE-REFRESH | `tests/unit/test_route_refresh.py::test_route_refresh_length_validation_rule`, `tests/fuzz/test_message_header.py`, `tests/fuzz/test_malformed_messages.py` | pytest |
| 6 | Ledger notes say the test goes through the reader; spec table and CHANGELOG | `qa/rfc/rfc7313.toml`, `.claude/exabgp/BGP_MESSAGE_INTERFACE.md`, `doc/CHANGELOG.rst` | `./qa/bin/check_rfc_compliance` |
| 7 | Full suite | | `./qa/bin/test_everything` |

## Break it to prove it

After step 3, revert `HEADER_CHECKS_LENGTH = False` on `RouteRefresh` and require the step 1
tests to fail: the header would answer 1/2 again, which is the bug.

## Progress (2026-09-29)

Thomas: "ok do it", the four recommendations.

- ✅ Step 0: the reader-level tests went in as strict xfail with the ledger at `gap`: 6 xfailed.
  The decoder-level tests lost their rfc markers, they do not prove what a peer is sent.
  The real-socket reader moved to `tests/unit/rfc/message_wire.py`, shared with RFC 4271's.
- ✅ Steps 1 to 3: `Message.HEADER_CHECKS_LENGTH`, `Message.header_refuses()`, the
  connection's two call sites, and `RouteRefresh._wrong_length()` asking the peer's OPEN.
  The 6 went XPASS(strict); xfail removed, ledger back to `required`, note rewritten.
- ✅ Broken to prove it: with `HEADER_CHECKS_LENGTH = True` on RouteRefresh, 6 fail.
- ✅ Step 4: contract test, `header_refuses` rows and every wrong length refused by the decoder.
- ✅ Step 5: `test_route_refresh_unpack_invalid_data_length` assumed 7/1 with no peer OPEN; now both cases.
- ✅ Step 6: spec, CHANGELOG.

## Resume Point

Done: full suite green (25/25), committed.
