"""RFC 7313 section 4: what a BoRR and an EoRR mean, sent and received.

A received BoRR is the peer about to re-advertise *its* routes for one family, and the EoRR
closes that re-advertisement: whatever it did not repeat is gone.  exabgp treated both as
a refresh request and replayed its own Adj-RIB-Out at the peer, twice per peer refresh.

exabgp's record of what a peer sent is the adj-rib-in.  The API processes keep their own
view and are sent the ROUTE-REFRESH messages themselves, with their subtype, so they can
apply the same rule to it.
"""

from __future__ import annotations

from typing import Any, Iterator
from unittest.mock import Mock, patch

import pytest

from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.graceful import Graceful
from exabgp.bgp.message.open.capability.refresh import REFRESH
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.reactor.peer import Peer
from exabgp.reactor.peer.handlers import route_refresh
from exabgp.reactor.peer.handlers.route_refresh import RouteRefreshHandler
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB
from exabgp.rib.incoming import IncomingRIB
from exabgp.rib.outgoing import OutgoingRIB
from exabgp.rib.route import Route
from tests import negotiation

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


def graceful_open(graceful: bool) -> Any:
    """An OPEN announcing Graceful Restart for FAMILY, or no capability at all."""
    capabilities = [Graceful().set(0, 120, [(FAMILY[0], FAMILY[1], 0)])] if graceful else []
    return negotiation.open_message(capabilities)


class Session:
    """The handler, a real adj-rib-in, and what was negotiated."""

    def __init__(self, enhanced: bool = True, graceful: bool = False) -> None:
        self.resend = Mock()
        self.incoming = IncomingRIB(True, {FAMILY, OTHER})
        configured = negotiation.api_asks(negotiation.neighbor(), 'receive-update', 'receive-parsed')
        self.ctx, self.told = negotiation.context(configured, refresh_enhanced=enhanced)
        self.ctx.neighbor.rib.incoming = self.incoming
        # the families the session negotiated: both, so a test about one is not about the other
        self.ctx.negotiated.families = [FAMILY, OTHER]
        # the OPEN the peer sent, which says whether it does Graceful Restart
        self.ctx.negotiated.received_open = graceful_open(graceful)
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
    session.receive(RouteRefresh.REQUEST)
    session.resend.assert_called_once_with(True, FAMILY)


@pytest.mark.rfc('rfc7313#4-examine-the-subtype', polarity='negative')
@pytest.mark.parametrize('subtype', [RouteRefresh.BEGIN, RouteRefresh.END], ids=['BoRR', 'EoRR'])
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
    session.receive(RouteRefresh.BEGIN)
    session.announced(KEPT)
    session.receive(RouteRefresh.END)

    assert held(session.incoming) == [KEPT]


@pytest.mark.rfc('rfc7313#4-borr-marks-routes-stale', polarity='negative')
def test_a_route_re_sent_after_the_borr_is_no_longer_stale() -> None:
    session = Session()
    session.announced(KEPT)
    session.receive(RouteRefresh.BEGIN)
    session.announced(KEPT)
    session.receive(RouteRefresh.END)

    assert held(session.incoming) == [KEPT]


@pytest.mark.rfc('rfc7313#4-eorr-removes-stale-routes')
def test_the_api_is_told_the_routes_the_eorr_removed() -> None:
    """The adj-rib-in dropped them, and the API processes, which keep their own view, kept them."""
    session = Session()
    session.announced(KEPT, DROPPED)
    session.receive(RouteRefresh.BEGIN)
    session.announced(KEPT)
    session.receive(RouteRefresh.END)

    told = [str(nlri) for args in session.told.called('update') for nlri in args[2].withdraws]
    assert told == [DROPPED], f'the API was not told the purged route went: {told}'


@pytest.mark.rfc('rfc7313#4-eorr-removes-stale-routes', polarity='negative')
def test_the_api_is_told_nothing_when_the_peer_repeated_every_route() -> None:
    session = Session()
    session.announced(KEPT)
    session.receive(RouteRefresh.BEGIN)
    session.announced(KEPT)
    session.receive(RouteRefresh.END)

    assert session.told.called('update') == []


@pytest.mark.rfc('rfc7313#4-eorr-removes-stale-routes', polarity='negative')
def test_only_the_family_of_the_borr_is_marked() -> None:
    session = Session()
    session.announced(KEPT)
    session.receive(RouteRefresh.BEGIN, OTHER)
    session.receive(RouteRefresh.END, OTHER)

    assert held(session.incoming) == [KEPT]


def test_a_route_withdrawn_during_the_refresh_is_not_purged_twice() -> None:
    session = Session()
    session.announced(KEPT, DROPPED)
    session.receive(RouteRefresh.BEGIN)
    session.incoming.update_cache_withdraw(route(DROPPED).nlri)
    session.announced(KEPT)
    session.receive(RouteRefresh.END)

    assert held(session.incoming) == [KEPT]


@pytest.mark.rfc('rfc7313#4-purged-routes-may-be-logged')
def test_purged_routes_are_logged() -> None:
    session = Session()
    session.announced(KEPT, DROPPED)
    session.receive(RouteRefresh.BEGIN)
    with patch.object(route_refresh.log, 'info') as info:
        session.receive(RouteRefresh.END)
    info.assert_called_once()


@pytest.mark.rfc('rfc7313#4-may-ignore-eorr-without-borr')
def test_an_eorr_without_a_borr_removes_nothing() -> None:
    session = Session()
    session.announced(KEPT)
    session.receive(RouteRefresh.END)

    assert held(session.incoming) == [KEPT]


@pytest.mark.rfc('rfc7313#4-eorr-without-borr-may-be-logged')
def test_an_eorr_without_a_borr_is_logged() -> None:
    session = Session()
    with patch.object(route_refresh.log, 'warning') as warning:
        session.receive(RouteRefresh.END)
    warning.assert_called_once()


def test_without_the_capability_the_octet_is_still_ignored() -> None:
    """RFC 2918: without Enhanced Route Refresh a BoRR's subtype is a Reserved octet."""
    session = Session(enhanced=False)
    session.announced(KEPT)
    session.receive(RouteRefresh.BEGIN)
    session.resend.assert_called_once_with(False, FAMILY)
    assert held(session.incoming) == [KEPT]


# ------------------------------------------------------------ Graceful Restart


@pytest.mark.rfc('rfc7313#4-ignore-borr-before-their-eor')
def test_a_borr_before_the_peers_end_of_rib_is_ignored() -> None:
    session = Session(graceful=True)
    session.announced(KEPT, DROPPED)
    session.receive(RouteRefresh.BEGIN)
    session.receive(RouteRefresh.END)

    assert held(session.incoming) == sorted([KEPT, DROPPED])


@pytest.mark.rfc('rfc7313#4-ignore-borr-before-their-eor', polarity='negative')
def test_a_borr_after_the_peers_end_of_rib_is_honoured() -> None:
    session = Session(graceful=True)
    session.announced(KEPT, DROPPED)
    session.incoming.record_end_of_rib(FAMILY)
    session.receive(RouteRefresh.BEGIN)
    session.announced(KEPT)
    session.receive(RouteRefresh.END)

    assert held(session.incoming) == [KEPT]


@pytest.mark.rfc('rfc7313#4-log-borr-before-eor')
def test_a_borr_before_the_peers_end_of_rib_is_logged() -> None:
    session = Session(graceful=True)
    with patch.object(route_refresh.log, 'warning') as warning:
        session.receive(RouteRefresh.BEGIN)
    warning.assert_called_once()


# ------------------------------------------------------------ what we send


def peer(graceful: bool | None) -> Peer:
    """A real Peer whose adj-rib-out holds FAMILY and OTHER.

    `graceful` says whether the OPEN we sent announced Graceful Restart, None when the
    session has no OPEN of ours.
    """
    subject, _ = negotiation.peer()
    subject.neighbor.rib = RIB('rfc7313', True, IncomingRIB(True, {FAMILY, OTHER}), OutgoingRIB(True, {FAMILY, OTHER}))
    subject.proto = Protocol(subject)
    # the session negotiated both families, so what a test leaves out is its own choice
    subject.proto.negotiated.families = [FAMILY, OTHER]
    if graceful is not None:
        subject.proto.negotiated.sent_open = graceful_open(graceful)
    return subject


def bracketed(subject: Peer) -> set[tuple[AFI, SAFI]]:
    """The families the adj-rib-out will replay between a BoRR and an EoRR."""
    return subject.neighbor.rib.outgoing._refresh_families


@pytest.mark.rfc('rfc7313#4-no-borr-before-our-eor')
def test_no_borr_before_our_end_of_rib_when_we_do_graceful_restart() -> None:
    subject = peer(graceful=True)
    subject.resend(True, FAMILY)
    assert bracketed(subject) == set()


@pytest.mark.rfc('rfc7313#4-no-borr-before-our-eor', polarity='negative')
def test_a_borr_once_our_end_of_rib_is_out() -> None:
    subject = peer(graceful=True)
    subject._end_of_rib_sent.add(FAMILY)
    subject.resend(True)
    assert bracketed(subject) == {FAMILY}


def test_without_graceful_restart_the_end_of_rib_does_not_matter() -> None:
    subject = peer(graceful=False)
    subject.resend(True)
    assert bracketed(subject) == {FAMILY, OTHER}


# ------------------------------------------------------------ a refresh we start


def rib_resend(peer_refresh: REFRESH) -> set[tuple[AFI, SAFI]]:
    """The operator's `rib flush out`, on a peer whose negotiated refresh is given.

    Returns the families replayed between a BoRR and an EoRR.
    """
    reactor, _ = negotiation.reactor()
    subject = peer(graceful=None)
    subject.proto.negotiated.refresh = peer_refresh
    reactor._peers['peer'] = subject
    reactor.neighbor_rib_resend('peer')
    return bracketed(subject)


@pytest.mark.rfc('rfc7313#4-send-borr-before-a-refresh', polarity='negative')
@pytest.mark.rfc('rfc7313#4-send-eorr-after-a-refresh', polarity='negative')
def test_a_refresh_we_start_is_not_bracketed_unless_the_peer_advertised_the_capability() -> None:
    """Section 4 applies "only if a BGP speaker has received" the capability.

    `rib flush out` decided from our own configuration, so a peer which never advertised
    Enhanced Route Refresh was sent BoRR and EoRR it had not asked to understand.
    """
    assert rib_resend(REFRESH.NORMAL) == set()


@pytest.mark.rfc('rfc7313#4-send-borr-before-a-refresh')
@pytest.mark.rfc('rfc7313#4-send-eorr-after-a-refresh')
def test_a_refresh_we_start_is_bracketed_when_the_peer_advertised_it() -> None:
    assert rib_resend(REFRESH.ENHANCED) == {FAMILY, OTHER}


@pytest.mark.rfc('rfc7313#4-advertise-the-capability')
@pytest.mark.parametrize(
    'mode',
    [
        'route-refresh enable;',
        'route-refresh require;',
        'route-refresh enable; route-refresh-normal require;',
        'route-refresh enable; route-refresh-enhanced require;',
    ],
)
def test_route_refresh_enabled_advertises_the_enhanced_capability_too(mode: str) -> None:
    from exabgp.bgp.message.open.capability.capabilities import Capabilities

    capabilities = Capabilities()
    capabilities._refresh(_configured(mode))
    assert Capability.CODE.ROUTE_REFRESH in capabilities
    assert Capability.CODE.ENHANCED_ROUTE_REFRESH in capabilities


def test_enable_normal_advertises_route_refresh_alone() -> None:
    """The SHOULD leaves the operator the choice, for a peer whose enhanced route refresh misbehaves."""
    from exabgp.bgp.message.open.capability.capabilities import Capabilities

    capabilities = Capabilities()
    capabilities._refresh(_configured('route-refresh-normal enable;'))
    assert Capability.CODE.ROUTE_REFRESH in capabilities
    assert Capability.CODE.ENHANCED_ROUTE_REFRESH not in capabilities


def _configured(mode: str) -> Any:
    from exabgp.configuration.configuration import Configuration

    configuration = Configuration(
        [
            'neighbor 192.0.2.1 { router-id 192.0.2.2; local-address 192.0.2.2; local-as 65001; peer-as 65002; '
            f'capability {{ {mode} }} }}'
        ],
        text=True,
    )
    assert configuration.reload(), str(configuration.error)
    (neighbor,) = configuration.neighbors.values()
    return neighbor


def test_a_purged_route_no_longer_counts_against_the_prefix_limit() -> None:
    """RFC 4486 prefix-limit counts the routes a peer holds with us, and the EoRR removed some.

    Left counted, a peer refreshing down to fewer routes would still be closed at the limit.
    """
    session = Session()
    for prefix in (KEPT, DROPPED):
        session.announced(prefix)
        session.incoming.count_prefix(route(prefix).nlri)
    session.receive(RouteRefresh.BEGIN)
    session.announced(KEPT)
    session.receive(RouteRefresh.END)

    assert session.incoming.count_prefix(route(KEPT).nlri) == 1


def test_the_prefix_limit_is_released_with_adj_rib_in_off() -> None:
    """The prefix-limit counts whether the cache is on or not, so the stale set has to too."""
    session = Session()
    session.incoming = IncomingRIB(False, {FAMILY, OTHER})
    session.ctx.neighbor.rib.incoming = session.incoming
    for prefix in (KEPT, DROPPED):
        session.announced(prefix)
        session.incoming.count_prefix(route(prefix).nlri)
    session.receive(RouteRefresh.BEGIN)
    session.announced(KEPT)
    session.receive(RouteRefresh.END)

    assert session.incoming.count_prefix(route(KEPT).nlri) == 1


# ------------------------------------------------------------ nothing to replay, no markers


def refresh_markers(rib: OutgoingRIB) -> list[int]:
    """The subtypes of the ROUTE-REFRESH messages the adj-rib-out would send next."""
    return [int(update.reserved) for update in rib.updates(False) if isinstance(update, RouteRefresh)]


@pytest.mark.rfc('rfc7313#4-send-eorr-after-a-refresh', polarity='negative')
def test_no_borr_nor_eorr_without_an_adj_rib_out_to_replay() -> None:
    """With no adj-rib-out, a BoRR and an EoRR sent back to back purge all our routes.

    The EoRR says the re-advertisement of the entire Adj-RIB-Out is complete; with the
    cache off nothing was re-advertised, and the peer removes everything it held from us.
    The configuration forces the cache on with route refresh, but a reload which turns both
    off swaps the tables of the running session before it is torn down.
    """
    rib = OutgoingRIB(False, {FAMILY})
    rib.add_to_rib(route(KEPT))
    list(rib.updates(False))
    rib.resend(True, FAMILY)
    assert refresh_markers(rib) == []


@pytest.mark.rfc('rfc7313#4-send-eorr-after-a-refresh')
def test_the_adj_rib_out_is_replayed_between_a_borr_and_an_eorr() -> None:
    rib = OutgoingRIB(True, {FAMILY})
    rib.add_to_rib(route(KEPT))
    list(rib.updates(False))
    rib.resend(True, FAMILY)
    assert refresh_markers(rib) == [RouteRefresh.BEGIN, RouteRefresh.END]


@pytest.mark.rfc('rfc2918#4-family-advertised-by-the-peer', polarity='negative')
def test_a_refresh_we_start_is_only_for_the_families_the_session_negotiated() -> None:
    """Configured for FAMILY and OTHER, negotiated FAMILY alone: OTHER is not refreshed.

    The peer never advertised OTHER, so a BoRR and an EoRR for it are messages for a family
    it said it does not have.
    """
    subject = peer(graceful=None)
    subject.proto.negotiated.families = [FAMILY]
    subject.resend(True)
    assert bracketed(subject) == {FAMILY}


@pytest.mark.rfc('rfc2918#4-family-advertised-by-the-peer', polarity='negative')
def test_the_operator_flush_is_only_for_the_families_the_session_negotiated() -> None:
    reactor, _ = negotiation.reactor()
    subject = peer(graceful=None)
    subject.proto.negotiated.refresh = REFRESH.ENHANCED
    subject.proto.negotiated.families = [FAMILY]
    reactor._peers['peer'] = subject
    reactor.neighbor_rib_resend('peer')
    assert bracketed(subject) == {FAMILY}
