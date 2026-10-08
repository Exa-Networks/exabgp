"""draft-ietf-idr-operational-message-00 3.1: an OPERATIONAL message goes only to a peer which
advertised the capability.

    A BGP speaker may send an OPERATIONAL message to its
    neighbor only if it has received the OPERATIONAL message capability
    from them.

The same defect as RFC 2918 had for ROUTE-REFRESH, on the same three paths: the queue a
Peer sends from checked our own configuration only, the API command queued for any
selected peer, and the ASM kept for a family was replayed on every new session. Each now
asks the negotiation.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from exabgp.bgp.message.open.capability.refresh import REFRESH
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.network.error import NetworkError
from tests.api_daemon import SECOND, Daemon
from tests.unit.test_peer_main_paths import SENDING_ALL, Session, advisory, neighbor

IPV4 = (AFI.ipv4, SAFI.unicast)
SEND_ONLY_IF_RECEIVED = 'draft-ietf-idr-operational-message-00#3.1-send-only-if-received'


async def operational_sent(session: Session) -> list[str]:
    """Run one session until the End-of-RIB, and return the OPERATIONAL messages it sent."""

    async def drive(session: Session) -> None:
        await session.sent('sent eor')

    raised = await session.run(drive)
    assert isinstance(raised, NetworkError)
    return [event for event in session.events if event == 'sent operational']


def queued(peer_received_the_capability: bool) -> Session:
    configured = neighbor(SENDING_ALL)
    configured.messages.append(advisory(AFI.ipv4, 'queued'))
    session = Session(configured)
    session.negotiated.operational = peer_received_the_capability
    return session


@pytest.mark.asyncio
@pytest.mark.rfc(SEND_ONLY_IF_RECEIVED)
async def test_a_queued_message_is_sent_when_the_peer_advertised_the_capability() -> None:
    session = queued(True)
    assert await operational_sent(session) == ['sent operational']


@pytest.mark.asyncio
@pytest.mark.rfc(SEND_ONLY_IF_RECEIVED, polarity='negative')
async def test_a_queued_message_is_not_sent_when_the_peer_did_not_advertise_the_capability() -> None:
    # we configured and advertised operational, the peer did not
    session = queued(False)
    assert await operational_sent(session) == []
    assert list(session.peer.neighbor.messages) == [], 'the queue kept a message it can never send'


@pytest.mark.asyncio
@pytest.mark.rfc(SEND_ONLY_IF_RECEIVED, polarity='negative')
async def test_the_asm_of_a_family_is_not_replayed_to_a_peer_which_did_not_advertise_the_capability() -> None:
    configured = neighbor(SENDING_ALL)
    configured.asm[IPV4] = advisory(AFI.ipv4, 'kept')
    session = Session(configured)
    session.negotiated.operational = False
    assert await operational_sent(session) == []


@pytest.mark.asyncio
@pytest.mark.rfc(SEND_ONLY_IF_RECEIVED)
async def test_the_asm_of_a_family_is_replayed_to_a_peer_which_advertised_the_capability() -> None:
    configured = neighbor(SENDING_ALL)
    configured.asm[IPV4] = advisory(AFI.ipv4, 'kept')
    session = Session(configured)
    session.negotiated.operational = True
    assert await operational_sent(session) == ['sent operational']


@pytest.fixture
def daemon() -> Iterator[Daemon]:
    created = Daemon()
    yield created
    created.close()


ASM = f'peer {SECOND} announce operational asm afi ipv4 safi unicast advisory "hello"'


@pytest.mark.rfc(SEND_ONLY_IF_RECEIVED)
def test_the_api_queues_a_message_for_a_peer_which_advertised_the_capability(daemon: Daemon) -> None:
    daemon.establish(SECOND)
    daemon.negotiate(SECOND, REFRESH.NORMAL, [IPV4], operational=True)
    assert daemon.send(ASM) == ['done']
    assert [message.NAME for message in daemon.neighbor(SECOND).messages] == ['ASM']


@pytest.mark.rfc(SEND_ONLY_IF_RECEIVED, polarity='negative')
def test_the_api_refuses_a_message_for_a_peer_which_did_not_advertise_the_capability(daemon: Daemon) -> None:
    daemon.establish(SECOND)
    daemon.negotiate(SECOND, REFRESH.NORMAL, [IPV4], operational=False)
    assert daemon.send(ASM)[-1] == 'error'
    assert list(daemon.neighbor(SECOND).messages) == []
    assert IPV4 not in daemon.neighbor(SECOND).asm, 'an ASM no session will carry was kept for replay'


@pytest.mark.rfc(SEND_ONLY_IF_RECEIVED, polarity='negative')
def test_the_api_refuses_a_message_for_a_peer_with_no_session(daemon: Daemon) -> None:
    assert daemon.send(ASM)[-1] == 'error'
    assert list(daemon.neighbor(SECOND).messages) == []
