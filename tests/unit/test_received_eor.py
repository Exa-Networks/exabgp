"""A peer's End-of-RIB reset the session.

Update.unpack_message returns an EOR for one.  Its TYPE is UPDATE, so the peer loop gave it
to UpdateHandler, which read `update.data`, an attribute EOR does not have.  The
AttributeError reached the catch-all in Peer._run, which reset the session without a
NOTIFICATION.  adj-rib-in defaults to true, so the default configuration decoded every
UPDATE fully and met it; qa/encoding/peer-eor.ci is the same failure end to end.

The End-of-RIB is recorded per family, which RFC 7313 section 4 needs: a BoRR received
before the peer's End-of-RIB for that family is ignored when the peer does Graceful Restart.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.update.eor import EOR
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.peer.context import PeerContext
from exabgp.reactor.peer.handlers import UpdateHandler
from exabgp.rib.incoming import IncomingRIB
from tests import negotiation

IPV4_UNICAST = (AFI.ipv4, SAFI.unicast)
IPV6_UNICAST = (AFI.ipv6, SAFI.unicast)


def context() -> PeerContext:
    ctx, _ = negotiation.context()
    ctx.neighbor.rib.incoming = IncomingRIB(True, {IPV4_UNICAST, IPV6_UNICAST})
    return ctx


def test_an_end_of_rib_is_handled_and_recorded() -> None:
    ctx = context()
    list(UpdateHandler().handle(ctx, EOR.make_eor(*IPV4_UNICAST)))

    assert ctx.neighbor.rib.incoming.has_end_of_rib(IPV4_UNICAST)
    assert not ctx.neighbor.rib.incoming.has_end_of_rib(IPV6_UNICAST)


@pytest.mark.asyncio
async def test_the_async_path_handles_it_too() -> None:
    ctx = context()
    await UpdateHandler().handle_async(ctx, EOR.make_eor(*IPV6_UNICAST))

    assert ctx.neighbor.rib.incoming.has_end_of_rib(IPV6_UNICAST)


def test_a_new_session_starts_without_any() -> None:
    incoming = IncomingRIB(True, {IPV4_UNICAST})
    incoming.record_end_of_rib(IPV4_UNICAST)
    incoming.clear()

    assert not incoming.has_end_of_rib(IPV4_UNICAST)
