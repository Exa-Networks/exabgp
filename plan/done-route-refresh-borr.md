# Received End-of-RIB, BoRR and EoRR (RFC 7313 section 4)

**Status:** ✅ Completed
**Created:** 2026-09-27
**Follows:** `plan/done-notification-text.md`, commit `cbacb1b61` (RFC 7313 section 5)

## Why

`RouteRefreshHandler` resent our whole Adj-RIB-Out when the peer sent a BoRR or EoRR, as if
it were a refresh request.  A BoRR is the peer telling us it is about to refresh *its*
routes.  Investigating that found something worse.

## Finding: a received End-of-RIB resets the session (main only)

`Update.unpack_message` returns an `EOR` for an End-of-RIB.  Its TYPE is UPDATE, so the
peer loop gives it to `UpdateHandler`, which reads `update.data`, which `EOR` does not
have.  `AttributeError` reaches the catch-all in `Peer._run`, which resets the session
without a NOTIFICATION.  `adj-rib-in` defaults to true, so the default configuration fully
decodes every UPDATE and hits it.

Reproduced against a running daemon (script in `.claude/backups/eor/`): OPEN, KEEPALIVE,
then an IPv4 End-of-RIB from the peer, and exabgp closes the connection:

    async.mainloop.exception error='EOR' object has no attribute 'data'

The functional test server has a `Message.eor()` helper that nothing calls, so no test
ever sent one.  The generator engine on 5.0 does not have `UpdateHandler`; not checked
further.

## Tasks

| # | task | status |
|---|---|---|
| 1 | fix the End-of-RIB crash, with a functional test where the peer sends one | ✅ `qa/encoding/peer-eor.ci` red 0/3 before, 3/3 after; `option:open:send-eor` added to `qa/sbin/bgp` |
| 2 | enrol RFC 7313 section 4 (3 has no keyword) | ✅ |
| 3 | a received BoRR or EoRR no longer triggers a resend | ✅ |
| 4 | BoRR marks the peer's routes for the family stale in the adj-rib-in, EoRR purges what was not re-sent | ✅ `IncomingRIB.mark_stale`, `purge_stale` |
| 5 | Graceful Restart: ignore a BoRR before the peer's End-of-RIB for the family, and never send a BoRR before ours | ✅ `RouteRefreshHandler._begin`, `Peer._borr_held_back` |
| 6 | found: `rib flush out` bracketed with BoRR/EoRR from our configuration, not the peer's capability | ✅ `loop.neighbor_rib_resend` |

## Design notes

- exabgp's only record of received routes is the adj-rib-in (`rib/incoming.py`, a `Cache`).
  The API processes hold their own view and already receive the refresh messages with a
  `subtype` of begin or end, so they can do their own stale handling.  Section 4's "remove
  any routes from the peer" is applied to the adj-rib-in.
- The End-of-RIB received per family is recorded in `IncomingRIB`, which is cleared when
  the session goes down, since task 5 needs it.
- The sending side already brackets a refresh with BoRR and EoRR (`rib/outgoing.py`).

## Recent failures

### 2026-09-27 documentation step: "the API does not accept `rib resend`"

**Cause:** the ledger note named the operator command by its reactor method.  The command
is `rib flush out` (`flush adj-rib out` in v4 syntax).
**Status:** ✅ renamed in the ledger, the test docstring, the changelog and this plan.

A first run was also failed by the leftover-process audit killing my own wrapper shell
(the command had been moved to the background by a timeout).  Not a test failure.

## Decisions

- The stale upper bound (MAY) is declined: exabgp forwards nothing, and the adj-rib-in is
  cleared with the session.
- A refresh asked for before our End-of-RIB (with Graceful Restart) is replayed without
  the markers rather than delayed.
- No functional test for BoRR/EoRR received: the test peer does not negotiate Enhanced
  Route Refresh.  Unit tests drive the handler with a real `IncomingRIB`.

## Resume point

All tasks done.  `test_everything` steps 1 to 24 passed (te7); step 25 (documentation)
failed on the command name above and passes after the fix.  Waiting for review, then two
commits: the End-of-RIB crash, then section 4.
