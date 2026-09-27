"""RFC 7313 section 4: what a BoRR and an EoRR mean, sent and received.

A received BoRR is the peer about to re-advertise *its* routes for one family, and the EoRR
closes that re-advertisement: whatever it did not repeat is gone.  exabgp treated both as
a refresh request and replayed its own Adj-RIB-Out at the peer, twice per peer refresh.

exabgp's record of what a peer sent is the adj-rib-in.  The API processes keep their own
view and are sent the ROUTE-REFRESH messages themselves, with their subtype, so they can
apply the same rule to it.
"""

from __future__ import annotations

from typing import Iterator
from unittest.mock import Mock, patch

import pytest

from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.reactor.peer.context import PeerContext
from exabgp.reactor.peer.handlers import route_refresh
from exabgp.reactor.peer.handlers.route_refresh import RouteRefreshHandler
from exabgp.rib.incoming import IncomingRIB
from exabgp.rib.route import Route

FAMILY = (AFI.ipv4, SAFI.unicast)
OTHER = (AFI.ipv6, SAFI.unicast)
KEPT = '192.0.2.0/24'
DROPPED = '198.51.100.0/24'


@pytest.fixture(autouse=True)
def _logger() -> Iterator[None]:
    from exabgp.logger.option import option

    logger, formater = option.logger, option.formater
    option.logger = Mock()
    option.formater = Mock(return_value='formatted message')
    yield
    option.logger, option.formater = logger, formater


def route(prefix: str) -> Route:
    address, mask = prefix.split('/')
    nlri = INET.from_cidr(CIDR.create_cidr(IP.pton(address), int(mask)), AFI.ipv4, SAFI.unicast)
    return Route(nlri, AttributeCollection(), nexthop=IP.from_string('192.0.2.1'))


def held(incoming: IncomingRIB) -> list[str]:
    return sorted(str(entry.nlri) for entry in incoming.cached_routes([FAMILY]))


class Session:
    """The handler, a real adj-rib-in, and what was negotiated."""

    def __init__(self, enhanced: bool = True, graceful: bool = False) -> None:
        self.resend = Mock()
        self.incoming = IncomingRIB(True, {FAMILY, OTHER})
        self.ctx = Mock(spec=PeerContext)
        self.ctx.peer_id = 'peer'
        self.ctx.refresh_enhanced = enhanced
        self.ctx.neighbor = Mock()
        self.ctx.neighbor.rib.incoming = self.incoming
        self.ctx.negotiated = Mock()
        self.ctx.negotiated.received_open.capabilities.announced.side_effect = lambda code: (
            graceful and code == Capability.CODE.GRACEFUL_RESTART
        )
        self.handler = RouteRefreshHandler(self.resend)

    def receive(self, subtype: int, family: tuple[AFI, SAFI] = FAMILY) -> None:
        message = RouteRefresh.make_route_refresh(family[0], family[1], subtype)
        list(self.handler.handle(self.ctx, message))

    def announced(self, *prefixes: str) -> None:
        for prefix in prefixes:
            self.incoming.update_cache(route(prefix))


# ------------------------------------------------------------ examining the subtype


@pytest.mark.rfc('rfc7313#4-examine-the-subtype')
def test_a_normal_request_is_answered_with_an_enhanced_refresh() -> None:
    session = Session()
    session.receive(RouteRefresh.request)
    session.resend.assert_called_once_with(True, FAMILY)


@pytest.mark.rfc('rfc7313#4-examine-the-subtype', polarity='negative')
@pytest.mark.parametrize('subtype', [RouteRefresh.start, RouteRefresh.end], ids=['BoRR', 'EoRR'])
def test_a_borr_or_an_eorr_is_not_a_request(subtype: int) -> None:
    """Both were answered by replaying our whole Adj-RIB-Out at the peer."""
    session = Session()
    session.receive(subtype)
    session.resend.assert_not_called()


# ------------------------------------------------------------ BoRR and EoRR received


@pytest.mark.rfc('rfc7313#4-borr-marks-routes-stale')
@pytest.mark.rfc('rfc7313#4-eorr-removes-stale-routes')
def test_what_the_peer_did_not_repeat_is_removed_at_the_eorr() -> None:
    session = Session()
    session.announced(KEPT, DROPPED)
    session.receive(RouteRefresh.start)
    session.announced(KEPT)
    session.receive(RouteRefresh.end)

    assert held(session.incoming) == [KEPT]


@pytest.mark.rfc('rfc7313#4-borr-marks-routes-stale', polarity='negative')
def test_a_route_re_sent_after_the_borr_is_no_longer_stale() -> None:
    session = Session()
    session.announced(KEPT)
    session.receive(RouteRefresh.start)
    session.announced(KEPT)
    session.receive(RouteRefresh.end)

    assert held(session.incoming) == [KEPT]


@pytest.mark.rfc('rfc7313#4-eorr-removes-stale-routes', polarity='negative')
def test_only_the_family_of_the_borr_is_marked() -> None:
    session = Session()
    session.announced(KEPT)
    session.receive(RouteRefresh.start, OTHER)
    session.receive(RouteRefresh.end, OTHER)

    assert held(session.incoming) == [KEPT]


def test_a_route_withdrawn_during_the_refresh_is_not_purged_twice() -> None:
    session = Session()
    session.announced(KEPT, DROPPED)
    session.receive(RouteRefresh.start)
    session.incoming.update_cache_withdraw(route(DROPPED).nlri)
    session.announced(KEPT)
    session.receive(RouteRefresh.end)

    assert held(session.incoming) == [KEPT]


@pytest.mark.rfc('rfc7313#4-purged-routes-may-be-logged')
def test_purged_routes_are_logged() -> None:
    session = Session()
    session.announced(KEPT, DROPPED)
    session.receive(RouteRefresh.start)
    with patch.object(route_refresh.log, 'info') as info:
        session.receive(RouteRefresh.end)
    info.assert_called_once()


@pytest.mark.rfc('rfc7313#4-may-ignore-eorr-without-borr')
def test_an_eorr_without_a_borr_removes_nothing() -> None:
    session = Session()
    session.announced(KEPT)
    session.receive(RouteRefresh.end)

    assert held(session.incoming) == [KEPT]


@pytest.mark.rfc('rfc7313#4-eorr-without-borr-may-be-logged')
def test_an_eorr_without_a_borr_is_logged() -> None:
    session = Session()
    with patch.object(route_refresh.log, 'warning') as warning:
        session.receive(RouteRefresh.end)
    warning.assert_called_once()


def test_without_the_capability_the_octet_is_still_ignored() -> None:
    """RFC 2918: without Enhanced Route Refresh a BoRR's subtype is a Reserved octet."""
    session = Session(enhanced=False)
    session.announced(KEPT)
    session.receive(RouteRefresh.start)
    session.resend.assert_called_once_with(False, FAMILY)
    assert held(session.incoming) == [KEPT]


# ------------------------------------------------------------ Graceful Restart


@pytest.mark.rfc('rfc7313#4-ignore-borr-before-their-eor')
def test_a_borr_before_the_peers_end_of_rib_is_ignored() -> None:
    session = Session(graceful=True)
    session.announced(KEPT, DROPPED)
    session.receive(RouteRefresh.start)
    session.receive(RouteRefresh.end)

    assert held(session.incoming) == sorted([KEPT, DROPPED])


@pytest.mark.rfc('rfc7313#4-ignore-borr-before-their-eor', polarity='negative')
def test_a_borr_after_the_peers_end_of_rib_is_honoured() -> None:
    session = Session(graceful=True)
    session.announced(KEPT, DROPPED)
    session.incoming.record_end_of_rib(FAMILY)
    session.receive(RouteRefresh.start)
    session.announced(KEPT)
    session.receive(RouteRefresh.end)

    assert held(session.incoming) == [KEPT]


@pytest.mark.rfc('rfc7313#4-log-borr-before-eor')
def test_a_borr_before_the_peers_end_of_rib_is_logged() -> None:
    session = Session(graceful=True)
    with patch.object(route_refresh.log, 'warning') as warning:
        session.receive(RouteRefresh.start)
    warning.assert_called_once()


# ------------------------------------------------------------ what we send


def peer(graceful: bool, enhanced_by_the_peer: bool = True) -> Mock:
    from exabgp.reactor.peer import Peer

    neighbor = Mock()
    neighbor.uid = '1'
    neighbor.api = {'neighbor-changes': False, 'fsm': False}
    neighbor.rib.outgoing.families = {FAMILY, OTHER}
    subject = Peer(neighbor, Mock())
    subject.proto = Mock()
    subject.proto.negotiated.sent_open.capabilities.announced.side_effect = lambda code: (
        graceful and code == Capability.CODE.GRACEFUL_RESTART
    )
    return subject


def replays(subject: Mock) -> dict[tuple[AFI, SAFI] | None, bool]:
    return {call.args[1]: call.args[0] for call in subject.neighbor.rib.outgoing.resend.call_args_list}


@pytest.mark.rfc('rfc7313#4-no-borr-before-our-eor')
def test_no_borr_before_our_end_of_rib_when_we_do_graceful_restart() -> None:
    subject = peer(graceful=True)
    subject.resend(True, FAMILY)
    assert replays(subject) == {FAMILY: False}


@pytest.mark.rfc('rfc7313#4-no-borr-before-our-eor', polarity='negative')
def test_a_borr_once_our_end_of_rib_is_out() -> None:
    subject = peer(graceful=True)
    subject._end_of_rib_sent.add(FAMILY)
    subject.resend(True)
    assert replays(subject) == {FAMILY: True, OTHER: False}


def test_without_graceful_restart_the_end_of_rib_does_not_matter() -> None:
    subject = peer(graceful=False)
    subject.resend(True)
    assert replays(subject) == {None: True}


# ------------------------------------------------------------ a refresh we start


def rib_resend(peer_refresh: int) -> Mock:
    """The operator's `rib flush out`, on a peer whose negotiated refresh is given."""
    from exabgp.reactor.loop import Reactor

    reactor = Mock(spec=Reactor)
    reactor._peers = {'peer': Mock()}
    reactor._peers['peer'].neighbor.capability.route_refresh = True
    reactor._peers['peer'].proto.negotiated.refresh = peer_refresh
    Reactor.neighbor_rib_resend(reactor, 'peer')
    return reactor._peers['peer'].resend


@pytest.mark.rfc('rfc7313#4-send-borr-before-a-refresh', polarity='negative')
@pytest.mark.rfc('rfc7313#4-send-eorr-after-a-refresh', polarity='negative')
def test_a_refresh_we_start_is_not_bracketed_unless_the_peer_advertised_the_capability() -> None:
    """Section 4 applies "only if a BGP speaker has received" the capability.

    `rib flush out` decided from our own configuration, so a peer which never advertised
    Enhanced Route Refresh was sent BoRR and EoRR it had not asked to understand.
    """
    from exabgp.bgp.message.open.capability.refresh import REFRESH

    rib_resend(REFRESH.NORMAL).assert_called_once_with(False)


@pytest.mark.rfc('rfc7313#4-send-borr-before-a-refresh')
@pytest.mark.rfc('rfc7313#4-send-eorr-after-a-refresh')
def test_a_refresh_we_start_is_bracketed_when_the_peer_advertised_it() -> None:
    from exabgp.bgp.message.open.capability.refresh import REFRESH

    rib_resend(REFRESH.ENHANCED).assert_called_once_with(True)


@pytest.mark.rfc('rfc7313#4-advertise-the-capability')
def test_route_refresh_enabled_advertises_the_enhanced_capability_too() -> None:
    from exabgp.bgp.message.open.capability.capabilities import Capabilities

    neighbor = Mock()
    neighbor.capability.route_refresh = True
    capabilities = Capabilities()
    capabilities._refresh(neighbor)
    assert Capability.CODE.ENHANCED_ROUTE_REFRESH in capabilities


def test_a_purged_route_no_longer_counts_against_the_prefix_limit() -> None:
    """RFC 4486 prefix-limit counts the routes a peer holds with us, and the EoRR removed some.

    Left counted, a peer refreshing down to fewer routes would still be closed at the limit.
    """
    session = Session()
    for prefix in (KEPT, DROPPED):
        session.announced(prefix)
        session.incoming.count_prefix(route(prefix).nlri)
    session.receive(RouteRefresh.start)
    session.announced(KEPT)
    session.receive(RouteRefresh.end)

    assert session.incoming.count_prefix(route(KEPT).nlri) == 1


def test_the_prefix_limit_is_released_with_adj_rib_in_off() -> None:
    """The prefix-limit counts whether the cache is on or not, so the stale set has to too."""
    session = Session()
    session.incoming = IncomingRIB(False, {FAMILY, OTHER})
    session.ctx.neighbor.rib.incoming = session.incoming
    for prefix in (KEPT, DROPPED):
        session.announced(prefix)
        session.incoming.count_prefix(route(prefix).nlri)
    session.receive(RouteRefresh.start)
    session.announced(KEPT)
    session.receive(RouteRefresh.end)

    assert session.incoming.count_prefix(route(KEPT).nlri) == 1
