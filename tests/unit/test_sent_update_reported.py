"""What a helper is told about an UPDATE we sent is what we sent.

`Protocol.send()` decodes the UPDATE it has just written to tell the helpers subscribed to
`send { update; }`. It decoded it as if the peer had sent it, so the checks a receiver makes
ran on our own route: on an EBGP session the AS_PATH starts with our AS, not the peer's, the
first-AS check of RFC 4271 6.3 failed, and the route was reported as withdrawn.
"""

from __future__ import annotations

import asyncio

from exabgp.reactor.protocol import Protocol
from tests import negotiation

LOCAL_AS = 65000
PEER_AS = 65001

# 10.0.0.0/24, next-hop 1.2.3.4, origin igp, med 100, as-path [ 65000 ] in two octet ASNs
SENT = bytes.fromhex(
    'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF0036020000001B4001010040020602010000FDE84003040102030440050400000064180A0000'
)


def _ebgp_protocol() -> tuple[Protocol, negotiation.Told]:
    configured = negotiation.neighbor(local_as=LOCAL_AS, peer_as=PEER_AS)
    negotiation.api_asks(configured, 'send-update', 'send-parsed')
    proto, told = negotiation.protocol(configured)
    proto.negotiated = negotiation.negotiated(session=proto.neighbor)
    return proto, told


def test_an_ebgp_announce_we_sent_is_reported_as_an_announce() -> None:
    proto, told = _ebgp_protocol()
    theirs = negotiation.connect(proto)
    try:
        asyncio.run(proto.send(SENT))
    finally:
        negotiation.disconnect(proto, theirs)

    reported = told.called('update')
    assert len(reported) == 1
    _, direction, collection, *_ = reported[0]
    assert direction == 'send'
    assert [str(routed.nlri) for routed in collection.announces] == ['10.0.0.0/24']
    assert collection.withdraws == []
