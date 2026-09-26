"""The adj-rib-out batches withdrawals the way it batches announcements.

`rib/outgoing.py` used to yield one `UpdateCollection` for every withdrawn NLRI, so a
withdrawn table was one UPDATE per prefix where RFC 4271 4.3 and RFC 4760 3 let hundreds
share one message. 5.0 does not have that problem: there, a withdrawal goes into the same
attribute bucket as an announcement and comes out grouped, so this is a 6.0 regression
rather than a new feature.

What decides whether two withdrawals can share a message is the family and the attribute
set, and nothing else. A withdrawal has no next hop, which is what stops `_announce_updates`
from grouping ipv6 unicast, so no family is excluded here. The attribute set does matter:
`UpdateCollection.messages` sends no path attribute for a unicast or multicast withdrawal
but sends `base_attr` for any other MP family, so merging two attribute sets would change
the bytes rather than only the count.

These tests count messages, because the count is the point, and then check the three things
which must not move with it: no prefix is lost or duplicated, a message never exceeds the
negotiated size, and a withdrawal still leaves before the announcement which replaces it.
"""

from __future__ import annotations

from unittest.mock import Mock

from exabgp.logger.option import option

option.logger = Mock()

from exabgp.bgp.message.direction import Direction  # noqa: E402
from exabgp.bgp.message.open.asn import ASN  # noqa: E402
from exabgp.bgp.message.open.capability.negotiated import Negotiated  # noqa: E402
from exabgp.bgp.message.refresh import RouteRefresh  # noqa: E402
from exabgp.bgp.message.update import Update, UpdateCollection  # noqa: E402
from exabgp.bgp.message.update.attribute import MED, NextHop, Origin  # noqa: E402
from exabgp.bgp.message.update.attribute.collection import AttributeCollection  # noqa: E402
from exabgp.bgp.message.update.nlri.cidr import CIDR  # noqa: E402
from exabgp.bgp.message.update.nlri.inet import INET  # noqa: E402
from exabgp.bgp.neighbor import Neighbor  # noqa: E402
from exabgp.protocol.family import AFI, SAFI  # noqa: E402
from exabgp.protocol.ip import IP  # noqa: E402
from exabgp.rib.outgoing import OutgoingRIB  # noqa: E402
from exabgp.rib.route import Route  # noqa: E402

IPV4_UNICAST = (AFI.ipv4, SAFI.unicast)
IPV6_UNICAST = (AFI.ipv6, SAFI.unicast)

BGP_MESSAGE_HEADER_SIZE = 19
BGP_MESSAGE_TYPE_UPDATE = 2

# Enough /32 to need more than one UPDATE, so the fragmentation of a batch is exercised and
# not only its existence.
WIDE_WITHDRAWAL_COUNT = 2000


def session() -> Negotiated:
    negotiated = Negotiated.make_negotiated(Neighbor(), Direction.IN)
    negotiated.local_as = ASN(65001)
    negotiated.peer_as = ASN(65002)
    negotiated.asn4 = True
    negotiated.families = [IPV4_UNICAST, IPV6_UNICAST]
    return negotiated


def route4(index: int, med: int | None = None) -> Route:
    address = IP.from_string('10.%d.%d.%d' % ((index >> 16) & 0xFF, (index >> 8) & 0xFF, index & 0xFF))
    nlri = INET.from_cidr(CIDR.create_cidr(address.pack_ip(), 32), AFI.ipv4, SAFI.unicast)
    attributes = AttributeCollection()
    attributes.add(Origin.from_int(0))
    attributes.add(NextHop.from_string('192.0.2.1'))
    if med is not None:
        attributes.add(MED.from_int(med))
    return Route(nlri, attributes, nexthop=IP.from_string('192.0.2.1'))


def route6(index: int) -> Route:
    address = IP.from_string('2001:db8:%x::' % index)
    nlri = INET.from_cidr(CIDR.create_cidr(address.pack_ip(), 64), AFI.ipv6, SAFI.unicast)
    attributes = AttributeCollection()
    attributes.add(Origin.from_int(0))
    return Route(nlri, attributes, nexthop=IP.from_string('2001:db8::1'))


def rib() -> OutgoingRIB:
    return OutgoingRIB(cache=True, families={IPV4_UNICAST, IPV6_UNICAST})


def collections(outgoing: OutgoingRIB, grouped: bool) -> list[UpdateCollection]:
    """One reactor flush, the route refreshes dropped: this file counts UPDATEs."""
    return [update for update in outgoing.updates(grouped=grouped) if not isinstance(update, RouteRefresh)]


def messages(updates: list[UpdateCollection], negotiated: Negotiated) -> list[bytes]:
    packed: list[bytes] = []
    for update in updates:
        packed.extend(update.messages(negotiated))
    return packed


def withdrawn(packed: list[bytes], negotiated: Negotiated) -> list[str]:
    """Every prefix the peer is told to drop, read back off the wire."""
    prefixes: list[str] = []
    for message in packed:
        assert message[BGP_MESSAGE_HEADER_SIZE - 1] == BGP_MESSAGE_TYPE_UPDATE, 'not an UPDATE'
        parsed = Update.unpack_message(message[BGP_MESSAGE_HEADER_SIZE:], negotiated).parse(negotiated)
        prefixes.extend(str(nlri) for nlri in parsed.withdraws)
    return prefixes


def announce_then_withdraw(routes: list[Route], grouped: bool) -> tuple[list[UpdateCollection], list[bytes]]:
    negotiated = session()
    outgoing = rib()
    for route in routes:
        outgoing.add_to_rib(route)
    collections(outgoing, grouped)
    for route in routes:
        outgoing.del_from_rib(route)
    updates = collections(outgoing, grouped)
    return updates, messages(updates, negotiated)


class TestWithdrawalsShareAMessage:
    def test_two_hundred_ipv4_withdrawals_are_one_message(self):
        """The measurement this change exists for: 200 UPDATEs became 1."""
        updates, packed = announce_then_withdraw([route4(index) for index in range(200)], grouped=True)
        assert len(updates) == 1, 'the 200 withdrawals shared one family and one attribute set'
        assert len(packed) == 1, '200 /32 fit one UPDATE, so one is what should go out'

    def test_two_hundred_ipv6_withdrawals_are_one_message(self):
        """Grouping a withdrawal has no next hop to agree on, so ipv6 unicast batches too.

        The announce path excludes this family, because one MP_REACH_NLRI carries a single
        next hop for every NLRI in it. MP_UNREACH_NLRI carries none.
        """
        updates, packed = announce_then_withdraw([route6(index) for index in range(200)], grouped=True)
        assert len(updates) == 1
        assert len(packed) == 1

    def test_a_wide_batch_is_split_and_loses_nothing(self):
        routes = [route4(index) for index in range(WIDE_WITHDRAWAL_COUNT)]
        negotiated = session()
        updates, packed = announce_then_withdraw(routes, grouped=True)

        assert len(packed) > 1, 'two thousand /32 do not fit one UPDATE'
        assert max(len(message) for message in packed) <= negotiated.msg_size
        prefixes = withdrawn(packed, negotiated)
        assert len(prefixes) == len(set(prefixes)), 'a prefix was withdrawn twice'
        assert sorted(prefixes) == sorted(str(route.nlri) for route in routes), 'a withdrawal was lost'

    def test_two_attribute_sets_do_not_merge(self):
        """`messages()` sends `base_attr` for an MP family which is not unicast or multicast,
        so two attribute sets are two messages however alike the prefixes are."""
        low = [route4(index, med=100) for index in range(5)]
        high = [route4(100 + index, med=200) for index in range(5)]
        negotiated = session()
        updates, packed = announce_then_withdraw(low + high, grouped=True)

        assert len(updates) == 2, 'the two MED values must not share an UpdateCollection'
        assert len({update.attributes.index() for update in updates}) == 2
        assert sorted(withdrawn(packed, negotiated)) == sorted(str(route.nlri) for route in low + high)

    def test_group_updates_false_still_sends_one_message_each(self):
        """`group-updates false` is the operator asking for one route per UPDATE.

        `qa/api/api-rib.ci` records three separate withdraw-only UPDATEs for a `clear
        adj-rib out` of three prefixes, on a neighbour which sets it.
        """
        updates, packed = announce_then_withdraw([route4(index) for index in range(200)], grouped=False)
        assert len(updates) == 200
        assert len(packed) == 200


class TestWithdrawalsKeepTheirOrder:
    def test_a_withdrawal_leaves_before_the_announcement_replacing_it(self):
        """A batch which withdraws and re-announces the same prefixes must not invert.

        Both collections carry the same family, so a peer which saw the announcement first
        would hold, until the next packet, a route it has been told to drop.
        """
        negotiated = session()
        outgoing = rib()
        before = [route4(index) for index in range(3)]
        for route in before:
            outgoing.add_to_rib(route)
        collections(outgoing, grouped=True)

        for route in before:
            outgoing.del_from_rib(route)
        for route in [route4(index, med=50) for index in range(3)]:
            outgoing.add_to_rib(route)
        updates = collections(outgoing, grouped=True)

        carriers = ['withdraw' if update.withdraws else 'announce' for update in updates]
        assert 'withdraw' in carriers and 'announce' in carriers
        assert carriers.index('withdraw') < carriers.index('announce')
        packed = messages(updates, negotiated)
        assert withdrawn(packed, negotiated) == ['10.0.0.0/32', '10.0.0.1/32', '10.0.0.2/32']

    def test_two_families_stay_in_their_own_messages(self):
        """RFC 7606 5.1 keeps the Withdrawn Routes field and MP_UNREACH_NLRI apart, and the
        RIB already buckets by family, so a mixed batch is two messages and not one."""
        negotiated = session()
        routes = [route4(index) for index in range(4)] + [route6(index) for index in range(4)]
        updates, packed = announce_then_withdraw(routes, grouped=True)

        assert len(updates) == 2, 'one collection per family'
        assert len(packed) == 2
        assert sorted(withdrawn(packed, negotiated)) == sorted(str(route.nlri) for route in routes)
