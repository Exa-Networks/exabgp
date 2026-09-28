"""RFC 4684 sections 5 and 6: the End-of-RIB for RT membership, and output filtering.

"implementations SHOULD generate an End-of-RIB marker ... for the Route Target membership
(afi, safi), regardless of whether graceful-restart is enabled on the BGP session." exabgp sends
one for every negotiated family, so the test is that (1, 132) is one of them, on a session with
graceful restart off, and that the marker is the RFC 4724 form for that family.

Section 5 lets a speaker exchange RT membership without filtering its VPN routes by it,
"although this is discouraged", and that is what exabgp does (issue #1109, "signal only").
The ledger records it as a gap, and the xfail at the end shows what the filtering of
section 6 would look like from the adj-rib-out of the peer which sent the membership.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from exabgp.bgp.message.open.asn import ASN
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


def announced_vpn(rib: RIB) -> list[NLRI]:
    """The VPN NLRI the adj-rib-out would send the peer next."""
    negotiated = rfc7606_wire.session(peer_as=PEER_AS)
    negotiated.families = [IPV4_VPN, IPV4_RTC]
    announced: list[NLRI] = []
    for update in rib.outgoing.updates(False, negotiated=negotiated):
        if isinstance(update, UpdateCollection):
            announced.extend(routed.nlri for routed in update.announces if routed.nlri.safi == SAFI.mpls_vpn)
    return announced


@pytest.mark.rfc('rfc4684#5-participate-without-output-filtering', polarity='negative')
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason='signal only (#1109): the membership a peer sends is not consulted when building its adj-rib-out',
)
def test_a_vpn_route_is_sent_only_for_a_route_target_the_peer_is_a_member_of(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not taking the discouraged option: filter the VPN routes by the peer's membership.

    The peer has told us, in an RT membership NLRI we hold in its adj-rib-in, that it
    wants Route Target 65000:1.  Of two VPN routes queued for it, the one carrying 65000:1
    goes out and the one carrying only 65000:2 does not.  The wanted route is asserted
    as well, because a filter which sent nothing would otherwise pass.
    """
    monkeypatch.setattr(RIB, '_cache', {})
    rib = RIB('rfc4684-output-filtering', True, False, {IPV4_VPN, IPV4_RTC})
    target = RouteTargetASN2Number.make_route_target(65000, WANTED_TARGET)
    membership = RTC.make_rtc(ASN(PEER_AS), target)
    rib.incoming.update_cache(Route(membership, AttributeCollection(), IP.from_string('192.0.2.1')))
    wanted = vpn_route('10.0.1.0/24', WANTED_TARGET)
    unwanted = vpn_route('10.0.2.0/24', UNWANTED_TARGET)
    rib.outgoing.add_to_rib(wanted)
    rib.outgoing.add_to_rib(unwanted)

    announced = announced_vpn(rib)

    assert wanted.nlri in announced, 'the route the peer asked for was not sent'
    assert unwanted.nlri not in announced, 'a route for a Route Target the peer is not a member of was sent'
