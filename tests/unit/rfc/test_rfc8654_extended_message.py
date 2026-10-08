"""RFC 8654: how large a message each end of a session may send.

The two directions are separate. What we may receive depends only on what we advertised:
"An implementation that advertises the BGP Extended Message Capability MUST be capable of
receiving a message with a length up to and including 65,535 octets." What we may send
depends on what the peer advertised: "A BGP speaker MAY send BGP Extended Messages to a
peer only if the BGP Extended Message Capability was received from that peer."

Two findings, each now a regression test:

- the limit on receipt rose only when both sides had advertised the capability, so a peer
  which took our advertisement at its word, without advertising its own, was refused
- a session mirroring the peer's AS (no local-as) copied the limit before its own OPEN was
  sent, and kept 4096 octets for its whole life whatever both sides advertised

The sessions are real: a Peer and its Protocol over one end of a socket pair, the other
end being the peer, which sends its OPEN and KEEPALIVE.

The ledger entries these prove are in qa/rfc/rfc8654.toml.
"""

from __future__ import annotations

import asyncio
import socket
from struct import pack

import pytest

from exabgp.bgp.fsm import FSM
from exabgp.bgp.message import KeepAlive, Message, Notify, Open
from exabgp.bgp.message.open import ASN, Capabilities, HoldTime, RouterID, Version
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability.extended import ExtendedMessage
from exabgp.bgp.neighbor import Neighbor
from exabgp.reactor.peer import Peer
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB
from exabgp.util.enumeration import TriState
from tests import negotiation

STANDARD = 4096
EXTENDED = 65535


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Neighbor takes a RIB out of a process wide cache, so each test gets its own."""
    monkeypatch.setattr(RIB, '_cache', {})


def configured(*, local_as: int = 65001, advertise: bool = True) -> Neighbor:
    neighbor = negotiation.neighbor(local_as=local_as, peer_as=65002, router_id='192.0.2.1')
    neighbor.capability.extended_message = TriState.TRUE if advertise else TriState.FALSE
    return neighbor


def their_open(*, advertise: bool) -> bytes:
    capabilities = Capabilities()
    if advertise:
        capabilities[Capability.CODE.EXTENDED_MESSAGE] = ExtendedMessage()
    sent = Open.make_open(Version(4), ASN(65002), HoldTime(180), RouterID('192.0.2.2'), capabilities)
    return sent.pack_message(negotiation.negotiated())


async def established(neighbor: Neighbor, *, they_advertise: bool) -> tuple[Peer, Protocol, socket.socket]:
    """Run the OPEN exchange of a session to Established, the peer sending what it says."""
    peer, _ = negotiation.peer(neighbor)
    proto = Protocol(peer)
    theirs = negotiation.connect(proto)
    peer.proto = proto
    theirs.sendall(their_open(advertise=they_advertise))
    theirs.sendall(KeepAlive.make_keepalive().pack_message(negotiation.negotiated()))
    await asyncio.wait_for(peer._establish(), timeout=2)
    assert peer.fsm == FSM.ESTABLISHED
    return peer, proto, theirs


@pytest.mark.rfc('rfc8654#4-receive-up-to-65535-when-advertised')
@pytest.mark.parametrize('local_as', [65001, 0], ids=['local-as', 'mirroring-the-peer'])
@pytest.mark.parametrize('they_advertise', [True, False], ids=['both-advertise', 'only-we-advertise'])
@pytest.mark.asyncio
async def test_advertising_the_capability_raises_what_we_receive(local_as: int, they_advertise: bool) -> None:
    peer, proto, theirs = await established(configured(local_as=local_as), they_advertise=they_advertise)
    try:
        assert proto.connection is not None
        assert proto.connection.msg_size == EXTENDED
    finally:
        negotiation.disconnect(proto, theirs)


@pytest.mark.rfc('rfc8654#4-receive-up-to-65535-when-advertised', polarity='negative')
@pytest.mark.rfc('rfc8654#5-not-advertised-not-accepted')
@pytest.mark.asyncio
async def test_not_advertising_the_capability_keeps_what_we_receive_to_4096() -> None:
    peer, proto, theirs = await established(configured(advertise=False), they_advertise=True)
    try:
        assert proto.connection is not None
        assert proto.connection.msg_size == STANDARD
    finally:
        negotiation.disconnect(proto, theirs)


@pytest.mark.rfc('rfc8654#5-not-advertised-not-accepted', polarity='negative')
@pytest.mark.asyncio
async def test_an_extended_message_we_did_not_advertise_for_is_a_bad_message_length() -> None:
    """The peer sends one anyway: RFC 8654 4 has the listener answer Bad Message Length."""
    peer, proto, theirs = await established(configured(advertise=False), they_advertise=True)
    length = STANDARD + 1
    theirs.sendall(Message.MARKER + pack('!H', length) + bytes([2]) + bytes(length - Message.HEADER_LEN))
    try:
        with pytest.raises(Notify) as caught:
            await asyncio.wait_for(proto.read_message(), timeout=1)
    finally:
        negotiation.disconnect(proto, theirs)
    assert (caught.value.code, caught.value.subcode) == (1, 2)


@pytest.mark.rfc('rfc8654#4-send-only-if-received')
@pytest.mark.parametrize(
    'we_advertise,they_advertise,size',
    [(True, True, EXTENDED), (True, False, STANDARD), (False, True, STANDARD)],
    ids=['both', 'only-we', 'only-they'],
)
@pytest.mark.asyncio
async def test_what_we_send_is_extended_only_with_their_capability(
    we_advertise: bool, they_advertise: bool, size: int
) -> None:
    """Sending needs theirs. It also still needs ours: a MAY, declined while we did not offer it."""
    peer, proto, theirs = await established(configured(advertise=we_advertise), they_advertise=they_advertise)
    try:
        assert proto.negotiated.msg_size == size
    finally:
        negotiation.disconnect(proto, theirs)
