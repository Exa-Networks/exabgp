"""RFC 4684 sections 5 and 6: the End-of-RIB for RT membership, and output filtering.

"implementations SHOULD generate an End-of-RIB marker ... for the Route Target membership
(afi, safi), regardless of whether graceful-restart is enabled on the BGP session." exabgp sends
one for every negotiated family, so the test is that (1, 132) is one of them, on a session with
graceful restart off, and that the marker is the RFC 4724 form for that family.

Section 5 lets a speaker exchange RT membership without filtering its VPN routes by it,
"although this is discouraged".  That stays exabgp's default (issue #1109, "signal only"),
so nothing changes for a configuration which does not ask; `route-target-filter true` on
the neighbour filters the VPN routes by the membership the peer sent, and offers them again
whenever that membership changes.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update import UpdateCollection
from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetASN2Number
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.rtc import RTC
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.protocol.ip import IP
from exabgp.rib import RIB
from exabgp.rib.route import Route

from rfc import rfc7606_wire

# RFC 4724 2: an End-of-RIB for a family other than IPv4 unicast is an UPDATE holding only an
# empty MP_UNREACH_NLRI for that family
RTC_END_OF_RIB = bytes.fromhex('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF001E0200000007900F0003000184')


@pytest.fixture
def protocol() -> Any:
    from exabgp.reactor.protocol import Protocol

    neighbor = MagicMock()
    neighbor.capability.graceful_restart.is_enabled = Mock(return_value=False)
    peer = Mock()
    peer.neighbor = neighbor
    peer.stats = defaultdict(int)
    proto = Protocol(peer)
    proto.connection = Mock()
    proto.connection.writer_async = AsyncMock()
    proto.connection.session = Mock(return_value='test-session')
    return proto


@pytest.mark.rfc('rfc4684#6-end-of-rib-for-rt-membership')
@pytest.mark.asyncio
async def test_rt_membership_gets_its_end_of_rib_without_graceful_restart(protocol: Any) -> None:
    protocol.negotiated.families = [(AFI.ipv4, SAFI.mpls_vpn), (AFI.ipv4, SAFI.rtc)]

    await protocol.new_eors()

    written = [bytes(call.args[0]) for call in protocol.connection.writer_async.call_args_list]
    assert RTC_END_OF_RIB in written, [w.hex().upper() for w in written]


# ============================================================ 5, output route filtering

IPV4_VPN: FamilyTuple = (AFI.ipv4, SAFI.mpls_vpn)
IPV4_RTC: FamilyTuple = (AFI.ipv4, SAFI.rtc)

PEER_AS = 65002
WANTED_TARGET = 1
UNWANTED_TARGET = 2


def vpn_route(prefix: str, target: int) -> Route:
    """One VPN route, through the parser the API uses, carrying Route Target 65000:<target>."""
    line = f'route {prefix} next-hop 192.0.2.2 rd 65000:{target} label 100 extended-community target:65000:{target}'
    configuration = Configuration([''], text=True)
    assert configuration.partial('static', line, 'announce'), str(configuration.error)
    (route,) = configuration.pop_routes()
    return route


def filtering_session(enabled: bool = True) -> Negotiated:
    """A session which negotiated VPN and RT-Constraint, `route-target-filter` as given."""
    negotiated = rfc7606_wire.session(peer_as=PEER_AS)
    negotiated.families = [IPV4_VPN, IPV4_RTC]
    negotiated.neighbor.route_target_filter = enabled
    return negotiated


def sent_vpn(rib: RIB, negotiated: Negotiated, announced: bool = True) -> list[NLRI]:
    """The VPN NLRI the adj-rib-out would send the peer next, announced or withdrawn."""
    sent: list[NLRI] = []
    for update in rib.outgoing.updates(False, negotiated=negotiated):
        if isinstance(update, UpdateCollection):
            routes = [routed.nlri for routed in update.announces] if announced else list(update.withdraws)
            sent.extend(nlri for nlri in routes if nlri.safi == SAFI.mpls_vpn)
    return sent


def announced_vpn(rib: RIB, enabled: bool = True) -> list[NLRI]:
    """The VPN NLRI the adj-rib-out would send the peer next."""
    return sent_vpn(rib, filtering_session(enabled))


def membership(target: int | None) -> Route:
    """The peer's RT membership NLRI for 65000:<target>, or the default route target."""
    rt = None if target is None else RouteTargetASN2Number.make_route_target(65000, target)
    return Route(RTC.make_rtc(ASN(PEER_AS), rt), AttributeCollection(), IP.from_string('192.0.2.1'))


def vpn_rib(monkeypatch: pytest.MonkeyPatch, member_of: list[int | None]) -> tuple[RIB, Route, Route]:
    """An adj-rib-out holding a route for 65000:1 and one for 65000:2, the peer a member of `member_of`."""
    monkeypatch.setattr(RIB, '_cache', {})
    rib = RIB('rfc4684-output-filtering', True, True, {IPV4_VPN, IPV4_RTC})
    for target in member_of:
        rib.incoming.update_cache(membership(target))
    wanted = vpn_route('10.0.1.0/24', WANTED_TARGET)
    unwanted = vpn_route('10.0.2.0/24', UNWANTED_TARGET)
    rib.outgoing.add_to_rib(wanted)
    rib.outgoing.add_to_rib(unwanted)
    return rib, wanted, unwanted


@pytest.mark.rfc('rfc4684#5-participate-without-output-filtering', polarity='negative')
def test_a_vpn_route_is_sent_only_for_a_route_target_the_peer_is_a_member_of(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not taking the discouraged option: filter the VPN routes by the peer's membership.

    The peer has told us, in an RT membership NLRI we hold in its adj-rib-in, that it
    wants Route Target 65000:1.  Of two VPN routes queued for it, the one carrying 65000:1
    goes out and the one carrying only 65000:2 does not.  The wanted route is asserted
    as well, because a filter which sent nothing would otherwise pass.
    """
    rib, wanted, unwanted = vpn_rib(monkeypatch, [WANTED_TARGET])

    announced = announced_vpn(rib)

    assert wanted.nlri in announced, 'the route the peer asked for was not sent'
    assert unwanted.nlri not in announced, 'a route for a Route Target the peer is not a member of was sent'


@pytest.mark.rfc('rfc4684#5-participate-without-output-filtering')
def test_without_route_target_filter_every_vpn_route_is_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default: membership is exchanged and the VPN routes are not filtered by it."""
    rib, wanted, unwanted = vpn_rib(monkeypatch, [WANTED_TARGET])

    announced = announced_vpn(rib, enabled=False)

    assert wanted.nlri in announced and unwanted.nlri in announced


def test_the_default_route_target_admits_every_vpn_route(monkeypatch: pytest.MonkeyPatch) -> None:
    """RFC 4684 4: a zero length membership NLRI asks for every Route Target."""
    rib, wanted, unwanted = vpn_rib(monkeypatch, [None])

    announced = announced_vpn(rib)

    assert wanted.nlri in announced and unwanted.nlri in announced


def test_a_vpn_route_the_peer_leaves_is_withdrawn_and_one_it_joins_is_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    """A change of membership offers the VPN routes again: admitted, or withdrawn if sent."""
    rib, wanted, unwanted = vpn_rib(monkeypatch, [WANTED_TARGET])
    negotiated = filtering_session()
    assert sent_vpn(rib, negotiated) == [wanted.nlri]

    rib.incoming.update_cache_withdraw(membership(WANTED_TARGET).nlri)
    rib.incoming.update_cache(membership(UNWANTED_TARGET))
    rib.outgoing.membership_changed()
    announced: list[NLRI] = []
    withdrawn: list[NLRI] = []
    for update in rib.outgoing.updates(False, negotiated=negotiated):
        if isinstance(update, UpdateCollection):
            announced.extend(routed.nlri for routed in update.announces)
            withdrawn.extend(update.withdraws)

    assert announced == [unwanted.nlri], 'the route for the Route Target joined was not sent'
    assert withdrawn == [wanted.nlri], 'the route for the Route Target left was not withdrawn'


@pytest.mark.parametrize(
    'length,covered',
    [(32, True), (48, True), (88, True), (94, True), (95, False), (96, False)],
)
def test_a_partial_membership_covers_the_route_targets_its_prefix_matches(length: int, covered: bool) -> None:
    """RFC 4684 4: a membership carries the origin AS and as much of the Route Target as
    its length says, so a shorter one covers every Route Target sharing those bits.

    65000:1 and 65000:2 share the first 62 of their 64 bits, so a prefix of 32+62 bits
    covers both and one reaching into bit 63 tells them apart. The odd lengths are the
    point: they end inside an octet, which is where a mask can go wrong.
    """
    full = RTC.make_rtc(ASN(PEER_AS), RouteTargetASN2Number.make_route_target(65000, 1))
    packed = bytes(full.pack_nlri(Negotiated.UNSET))
    partial = RTC(bytes([length]) + packed[1 : 1 + (length + 7) // 8])
    other = bytes(RouteTargetASN2Number.make_route_target(65000, 2).pack())

    assert partial.admits(other) is covered


def test_route_target_filter_needs_both_adj_ribs() -> None:
    """The membership is read from the adj-rib-in, and a change replays the adj-rib-out."""
    text = """
neighbor 192.0.2.1 {
    router-id 192.0.2.254;
    local-address 192.0.2.254;
    local-as 65001;
    peer-as 65002;
    route-target-filter true;
    adj-rib-in false;
    family { ipv4 mpls-vpn; ipv4 rtc; }
}
"""
    configuration = Configuration([text], text=True)

    assert not configuration.reload()
    assert 'route-target-filter requires adj-rib-in and adj-rib-out' in str(configuration.error)


def test_many_membership_updates_replay_the_vpn_routes_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """A peer sends its membership in as many UPDATEs as it likes: each must not queue the
    VPN table again, or the queue grows with the number of UPDATEs before a batch is built."""
    rib, wanted, unwanted = vpn_rib(monkeypatch, [WANTED_TARGET])
    negotiated = filtering_session()
    sent_vpn(rib, negotiated)
    assert not rib.outgoing.pending()

    for _ in range(100):
        rib.outgoing.membership_changed()

    assert rib.outgoing.pending(), 'a change of membership left nothing to send'
    assert len(rib.outgoing._refresh_routes) == 0, 'the VPN routes were queued before the batch was built'
    assert sent_vpn(rib, negotiated) == [wanted.nlri]
    assert not rib.outgoing.pending()
