"""RFC 6608: the subcodes of a Finite State Machine Error, and what their Data field holds.

Section 4 gives one subcode per state an unexpected message can arrive in, OpenSent,
OpenConfirm and Established, and the same Data field for each: "a 1-octet, unsigned
integer that indicates the type of the unexpected message".

Three findings, each now a regression test:

- OpenSent sent (5, 1) with a sentence describing the message as its Data field
- OpenConfirm sent (5, 2) with an empty Data field
- an OPEN on an established session was dropped without a word, (5, 3) was never sent

The session is a real Protocol over one end of a socket pair, the other end is the peer.

The ledger entries these prove are in qa/rfc/rfc6608.toml.
"""

from __future__ import annotations

import asyncio
import socket
from struct import pack

import pytest

from exabgp.bgp.fsm import FSM
from exabgp.bgp.message import KeepAlive, Message, Notify, Open
from exabgp.bgp.message.open import ASN, Capabilities, HoldTime, RouterID, Version
from exabgp.reactor.peer import Peer
from exabgp.reactor.peer.handlers import RouteRefreshHandler, UpdateHandler
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB
from tests import negotiation

FSM_ERROR = 5
OPENSENT = 1
OPENCONFIRM = 2
ESTABLISHED = 3

OPEN = 1
UPDATE = 2
KEEPALIVE = 4


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Neighbor takes a RIB out of a process wide cache, so each test gets its own."""
    monkeypatch.setattr(RIB, '_cache', {})


def session() -> tuple[Peer, Protocol, socket.socket]:
    configured = negotiation.neighbor(local_as=65001, peer_as=65002, router_id='192.0.2.1')
    peer, _ = negotiation.peer(configured)
    proto = Protocol(peer)
    theirs = negotiation.connect(proto)
    peer.proto = proto
    return peer, proto, theirs


def their_open() -> bytes:
    sent = Open.make_open(Version(4), ASN(65002), HoldTime(180), RouterID('192.0.2.2'), Capabilities())
    return sent.pack_message(negotiation.negotiated())


def their_keepalive() -> bytes:
    return KeepAlive.make_keepalive().pack_message(negotiation.negotiated())


def their_update() -> bytes:
    """The smallest UPDATE there is, the IPv4 unicast End-of-RIB."""
    return Message.MARKER + pack('!H', 23) + bytes([UPDATE]) + bytes(4)


def subcode_and_data(notify: Notify) -> tuple[int, int, bytes]:
    packed = notify.notification.pack_message(negotiation.negotiated())
    return packed[19], packed[20], packed[21:]


# ------------------------------------------------------------------------------- OpenSent


@pytest.mark.rfc('rfc6608#4-opensent-unexpected-message')
@pytest.mark.rfc('rfc6608#4-opensent-data-is-the-message-type')
@pytest.mark.asyncio
async def test_a_keepalive_in_opensent_is_told_with_its_type() -> None:
    _, proto, theirs = session()
    theirs.sendall(their_keepalive())
    try:
        with pytest.raises(Notify) as caught:
            await asyncio.wait_for(proto.read_open('192.0.2.2'), timeout=1)
    finally:
        negotiation.disconnect(proto, theirs)
    assert subcode_and_data(caught.value) == (FSM_ERROR, OPENSENT, bytes([KEEPALIVE]))


@pytest.mark.rfc('rfc6608#4-opensent-unexpected-message', polarity='negative')
@pytest.mark.asyncio
async def test_an_open_in_opensent_is_what_was_expected() -> None:
    _, proto, theirs = session()
    theirs.sendall(their_open())
    try:
        received = await asyncio.wait_for(proto.read_open('192.0.2.2'), timeout=1)
    finally:
        negotiation.disconnect(proto, theirs)
    assert received.ID == Message.CODE.OPEN


# ---------------------------------------------------------------------------- OpenConfirm


@pytest.mark.rfc('rfc6608#4-openconfirm-unexpected-message')
@pytest.mark.parametrize('message,kind', [(their_open(), OPEN), (their_update(), UPDATE)], ids=['open', 'update'])
@pytest.mark.asyncio
async def test_an_unexpected_message_in_openconfirm_is_told_with_its_type(message: bytes, kind: int) -> None:
    _, proto, theirs = session()
    theirs.sendall(message)
    try:
        with pytest.raises(Notify) as caught:
            await asyncio.wait_for(proto.read_keepalive(), timeout=1)
    finally:
        negotiation.disconnect(proto, theirs)
    assert subcode_and_data(caught.value) == (FSM_ERROR, OPENCONFIRM, bytes([kind]))


@pytest.mark.rfc('rfc6608#4-openconfirm-unexpected-message', polarity='negative')
@pytest.mark.asyncio
async def test_a_keepalive_in_openconfirm_is_what_was_expected() -> None:
    _, proto, theirs = session()
    theirs.sendall(their_keepalive())
    try:
        received = await asyncio.wait_for(proto.read_keepalive(), timeout=1)
    finally:
        negotiation.disconnect(proto, theirs)
    assert received.ID == Message.CODE.KEEPALIVE


# ---------------------------------------------------------------------------- Established


async def handle_established(peer: Peer, message: Message) -> None:
    peer.fsm.change(FSM.ESTABLISHED)
    await peer._handle_inbound(peer._session_context(1), message, UpdateHandler(), RouteRefreshHandler(peer.resend))


@pytest.mark.rfc('rfc6608#4-established-unexpected-message')
@pytest.mark.asyncio
async def test_an_open_on_an_established_session_is_told_with_its_type() -> None:
    """It was dropped: neither handler takes an OPEN, and nothing else looked at it."""
    peer, proto, theirs = session()
    received = Open.unpack_message(their_open()[19:], negotiation.negotiated())
    try:
        with pytest.raises(Notify) as caught:
            await handle_established(peer, received)
    finally:
        negotiation.disconnect(proto, theirs)
    assert subcode_and_data(caught.value) == (FSM_ERROR, ESTABLISHED, bytes([OPEN]))


@pytest.mark.rfc('rfc6608#4-established-unexpected-message', polarity='negative')
@pytest.mark.asyncio
async def test_a_keepalive_on_an_established_session_is_not_an_error() -> None:
    peer, proto, theirs = session()
    try:
        await handle_established(peer, KeepAlive.make_keepalive())
    finally:
        negotiation.disconnect(proto, theirs)
