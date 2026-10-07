"""RFC 7607, Codification of AS 0 Processing: the OPEN half.

The ledger these tests are joined to is qa/rfc/rfc7607.toml.

A peer claiming AS 0 was refused only when the configured peer-as happened to differ from
it. With `peer-as auto` nothing compared it at all and the session came up, and with
`local-as auto` we mirrored it and sent an OPEN claiming AS 0 ourselves.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message import Notify
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open import ASN, Capabilities, HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.asn import AS_TRANS
from exabgp.bgp.message.open.capability import ASN4, Capability
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.neighbor import Neighbor
from exabgp.protocol.ip import IPv4
from exabgp.rib import RIB
from exabgp.util.enumeration import TriState
from tests import negotiation

OPEN_MESSAGE_ERROR = 2
BAD_PEER_AS = 2
AUTO = 0


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Neighbor takes a RIB out of a process wide cache, so each test gets its own."""
    monkeypatch.setattr(RIB, '_cache', {})


def judgement(my_as: int, capability_as: int | None, configured_peer_as: int = AUTO) -> tuple[int, int, str] | None:
    """What validate() says of a peer whose OPEN carries these, on a session to AS65001."""
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(65001)
    neighbor.session.peer_as = ASN(configured_peer_as)
    neighbor.session.router_id = RouterID('192.0.2.1')
    ours = Capabilities()
    ours[Capability.CODE.FOUR_BYTES_ASN] = ASN4(65001)
    theirs = Capabilities()
    if capability_as is not None:
        theirs[Capability.CODE.FOUR_BYTES_ASN] = ASN4(capability_as)
    negotiated = Negotiated.make_negotiated(neighbor, Direction.IN)
    negotiated.sent(Open.make_open(Version(4), ASN(65001), HoldTime(180), RouterID('192.0.2.1'), ours))
    negotiated.received(Open.make_open(Version(4), ASN(my_as), HoldTime(180), RouterID('192.0.2.2'), theirs))
    return negotiated.validate(neighbor)


@pytest.mark.rfc('rfc7607#2-open-from-as-zero-is-bad-peer-as')
@pytest.mark.parametrize(
    ('my_as', 'capability_as', 'configured_peer_as'),
    [
        (0, None, AUTO),
        (0, None, 65002),
        (int(AS_TRANS), 0, AUTO),
        (65002, 0, AUTO),
    ],
    ids=['my-as-zero-peer-as-auto', 'my-as-zero-peer-as-configured', 'as-trans-capability-zero', 'capability-zero'],
)
def test_a_peer_claiming_as_zero_is_a_bad_peer_as(
    my_as: int, capability_as: int | None, configured_peer_as: int
) -> None:
    error = judgement(my_as, capability_as, configured_peer_as)

    assert error is not None, 'a peer claiming AS 0 was accepted'
    assert (error[0], error[1]) == (OPEN_MESSAGE_ERROR, BAD_PEER_AS)


@pytest.mark.rfc('rfc7607#2-open-from-as-zero-is-bad-peer-as', polarity='negative')
@pytest.mark.parametrize(('my_as', 'capability_as'), [(65002, None), (int(AS_TRANS), 70000)], ids=['two', 'four'])
def test_a_peer_with_a_non_zero_as_is_accepted_by_peer_as_auto(my_as: int, capability_as: int | None) -> None:
    assert judgement(my_as, capability_as) is None


async def first_open_sent(remote_as: int) -> bytes:
    """What a local-as auto session writes after reading an OPEN from `remote_as`."""
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(AUTO)
    neighbor.session.router_id = RouterID('192.0.2.1')
    neighbor.capability.asn4 = TriState.TRUE
    neighbor.session.peer_address = IPv4.from_string('192.0.2.2')
    neighbor.session.local_address = IPv4.from_string('192.0.2.1')
    proto, _ = negotiation.protocol(neighbor)
    theirs = negotiation.connect(proto)
    received = Capabilities()
    received[Capability.CODE.FOUR_BYTES_ASN] = ASN4(remote_as)
    proto.negotiated.received(
        Open.make_open(Version(4), ASN(remote_as).trans(), HoldTime(90), RouterID('192.0.2.2'), received)
    )
    try:
        await proto.new_open()
    finally:
        sent = negotiation.received(theirs)
    return sent


@pytest.mark.asyncio
@pytest.mark.rfc('rfc7607#2-never-claim-as-zero')
async def test_local_as_auto_does_not_mirror_as_zero() -> None:
    with pytest.raises(Notify) as caught:
        await first_open_sent(0)

    assert (caught.value.code, caught.value.subcode) == (OPEN_MESSAGE_ERROR, BAD_PEER_AS)


@pytest.mark.asyncio
@pytest.mark.rfc('rfc7607#2-never-claim-as-zero', polarity='negative')
async def test_local_as_auto_mirrors_any_other_as() -> None:
    """Without this a speaker which refused to mirror anything would pass the test above."""
    [(kind, body)] = negotiation.messages(await first_open_sent(65002))

    assert kind == Open.ID
    assert Open.unpack_message(body, Negotiated.UNSET).asn == ASN(65002)
