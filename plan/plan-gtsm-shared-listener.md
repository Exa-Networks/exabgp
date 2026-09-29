# GTSM on a listening socket shared by several neighbours

**Status:** 📋 Planning (not started)
**Created:** 2026-09-29
**From:** `done-review-quality-sweep.md`, the follow-up to the item 5 correction

## Problem

The listener opens one socket per local address, port and interface. The loop over
`self._sockets` in `reactor/listener.py` calls `min_ttl`/`min_ttlv6` on that shared socket
for every neighbour configured on it. The option belongs to the socket, not to a peer, so
two neighbours on the same address with different `incoming-ttl` values both get whichever
was configured last, and a neighbour with none inherits another's minimum.

The sending side is already per connection (`set_accepted_ttl`, applied once the neighbour
is known).

## Options

1. Set the minimum on the accepted socket instead, once the peer is known. Segments which
   arrived before that were not checked, which is weaker than RFC 5082 asks.
2. Use the strictest value across the neighbours on the socket.
3. Refuse a configuration where neighbours sharing a socket disagree.

## Steps

1. [ ] Test: two neighbours on one address with different `incoming-ttl`, assert what each gets
2. [ ] Choose an option with Thomas
3. [ ] Implement, `./qa/bin/test_everything`

## Progress

## Failures

## Blockers

Option choice.

## Resume Point

Step 1.
