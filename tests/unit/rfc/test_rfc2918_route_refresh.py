"""RFC 2918: a ROUTE-REFRESH goes only to a peer which advertised the capability.

    A BGP speaker may send a ROUTE-REFRESH message to its peer only if it
    has received the Route Refresh Capability from its peer.  The <AFI,
    SAFI> carried in such a message should be one of the <AFI, SAFI> that
    the peer has advertised to the speaker at the session establishment
    time via capability advertisement.

Both paths are covered: the queue a Peer sends from, and the API command which fills it.
They both checked our own configuration only, so a refresh was sent to a peer which never
said it could handle one, and for a family the session had not negotiated.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from exabgp.bgp.message.open.capability.refresh import REFRESH
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.network.error import NetworkError
from tests.api_daemon import SECOND, Daemon
from tests.unit.test_peer_main_paths import SENDING_ALL, Session, neighbor

IPV4 = (AFI.ipv4, SAFI.unicast)
IPV6 = (AFI.ipv6, SAFI.unicast)


async def refreshes_sent(session: Session, family: tuple[AFI, SAFI]) -> list[str]:
    """Queue a refresh for `family`, run one session until the End-of-RIB, and return what was sent."""
    session.peer.neighbor.refresh.append(RouteRefresh.make_route_refresh(*family))

    async def drive(session: Session) -> None:
        await session.sent('sent eor')

    raised = await session.run(drive)
    assert isinstance(raised, NetworkError)
    return [event for event in session.events if event == 'sent refresh']


@pytest.mark.asyncio
@pytest.mark.rfc('rfc2918#4-send-only-if-received')
@pytest.mark.rfc('rfc2918#4-family-advertised-by-the-peer')
async def test_a_refresh_is_sent_when_the_peer_advertised_the_capability() -> None:
    session = Session(neighbor(SENDING_ALL))
    assert session.negotiated.refresh != REFRESH.ABSENT
    assert await refreshes_sent(session, IPV4) == ['sent refresh']


@pytest.mark.asyncio
@pytest.mark.rfc('rfc2918#4-send-only-if-received', polarity='negative')
async def test_no_refresh_is_sent_when_the_peer_did_not_advertise_the_capability() -> None:
    # we configured and advertised route-refresh, the peer did not
    session = Session(neighbor(SENDING_ALL))
    session.negotiated.refresh = REFRESH.ABSENT
    assert await refreshes_sent(session, IPV4) == []
    assert list(session.peer.neighbor.refresh) == []


@pytest.mark.asyncio
@pytest.mark.rfc('rfc2918#4-family-advertised-by-the-peer', polarity='negative')
async def test_no_refresh_is_sent_for_a_family_the_session_did_not_negotiate() -> None:
    session = Session(neighbor(SENDING_ALL))
    assert IPV6 not in session.negotiated.families
    assert await refreshes_sent(session, IPV6) == []


@pytest.fixture
def daemon() -> Iterator[Daemon]:
    created = Daemon()
    yield created
    created.close()


@pytest.mark.rfc('rfc2918#4-send-only-if-received')
def test_the_api_queues_a_refresh_for_a_peer_which_advertised_the_capability(daemon: Daemon) -> None:
    daemon.establish(SECOND)
    daemon.negotiate(SECOND, REFRESH.NORMAL, [IPV4])
    assert daemon.send(f'peer {SECOND} announce route-refresh ipv4 unicast') == ['done']
    assert len(daemon.neighbor(SECOND).refresh) == 1


@pytest.mark.rfc('rfc2918#4-send-only-if-received', polarity='negative')
def test_the_api_refuses_a_refresh_for_a_peer_which_did_not_advertise_the_capability(daemon: Daemon) -> None:
    daemon.establish(SECOND)
    daemon.negotiate(SECOND, REFRESH.ABSENT, [IPV4])
    assert daemon.send(f'peer {SECOND} announce route-refresh ipv4 unicast') == ['error']
    assert list(daemon.neighbor(SECOND).refresh) == []


@pytest.mark.rfc('rfc2918#4-family-advertised-by-the-peer', polarity='negative')
def test_the_api_refuses_a_refresh_for_a_configured_family_the_peer_did_not_advertise(daemon: Daemon) -> None:
    # SECOND is configured for ipv4 unicast, which the session here did not negotiate
    daemon.establish(SECOND)
    daemon.negotiate(SECOND, REFRESH.NORMAL, [])
    assert daemon.send(f'peer {SECOND} announce route-refresh ipv4 unicast') == ['error']
    assert list(daemon.neighbor(SECOND).refresh) == []
