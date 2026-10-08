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
from unittest.mock import Mock, patch

import pytest

from exabgp.bgp.message.open.capability.refresh import REFRESH
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.peer.handlers import route_refresh
from exabgp.reactor.peer.handlers.route_refresh import RouteRefreshHandler
from exabgp.rib.incoming import IncomingRIB
from tests import negotiation
from tests.api_daemon import SECOND, Daemon
from tests.unit.rfc.test_rfc7313_operation import route as ipv4_route
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


# ============================================================ receiving


class Received:
    """The handler of received ROUTE-REFRESH messages, over a session negotiating IPV4 alone."""

    def __init__(self, enhanced: bool = False) -> None:
        self.resend = Mock()
        self.ctx, _ = negotiation.context(refresh_enhanced=enhanced)
        self.ctx.negotiated.families = [IPV4]
        self.ctx.negotiated.received_open = negotiation.open_message([])
        self.incoming = IncomingRIB(True, {IPV4, IPV6})
        self.ctx.neighbor.rib.incoming = self.incoming
        self.handler = RouteRefreshHandler(self.resend)

    def receive(self, family: tuple[AFI, SAFI], subtype: int = RouteRefresh.REQUEST) -> None:
        list(self.handler.handle(self.ctx, RouteRefresh.make_route_refresh(family[0], family[1], subtype)))


@pytest.mark.rfc('rfc2918#4-ignore-a-family-not-advertised')
def test_a_request_for_a_family_of_the_session_is_answered() -> None:
    received = Received()
    received.receive(IPV4)
    received.resend.assert_called_once_with(False, IPV4)


@pytest.mark.rfc('rfc2918#4-ignore-a-family-not-advertised', polarity='negative')
@pytest.mark.parametrize('enhanced', [False, True], ids=['normal', 'enhanced'])
def test_a_request_for_a_family_the_session_did_not_negotiate_is_ignored(enhanced: bool) -> None:
    received = Received(enhanced)
    with patch.object(route_refresh.log, 'warning') as warning:
        received.receive(IPV6)
    received.resend.assert_not_called()
    warning.assert_called_once()


@pytest.mark.rfc('rfc2918#4-ignore-a-family-not-advertised', polarity='negative')
def test_a_borr_and_an_eorr_for_a_family_the_session_did_not_negotiate_are_ignored() -> None:
    """They marked and purged stale routes for any <AFI, SAFI> the peer named."""
    received = Received(enhanced=True)
    received.ctx.negotiated.families = [IPV6]
    received.incoming.update_cache(ipv4_route('192.0.2.0/24'))
    received.receive(IPV4, RouteRefresh.BEGIN)
    received.receive(IPV4, RouteRefresh.END)

    held = [str(route.nlri) for route in received.incoming.cached_routes([IPV4])]
    assert held == ['192.0.2.0/24'], 'an EoRR for a family not negotiated removed a route'
