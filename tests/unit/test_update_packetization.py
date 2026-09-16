"""Wire-level packetization contracts, independently of OTC policy."""

from collections import Counter

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update import Update, UpdateCollection
from exabgp.bgp.message.update.attribute import AttributeCollection, NextHop
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.neighbor import Neighbor
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP


def negotiated_session() -> Negotiated:
    negotiated = Negotiated.make_negotiated(Neighbor(), Direction.IN)
    negotiated.local_as = ASN(65001)
    negotiated.peer_as = ASN(65002)
    negotiated.asn4 = True
    negotiated.families = [(AFI.ipv4, SAFI.unicast), (AFI.ipv4, SAFI.multicast), (AFI.ipv6, SAFI.unicast)]
    return negotiated


def routed_prefix(prefix: str, safi: SAFI = SAFI.unicast) -> RoutedNLRI:
    address, mask = prefix.split('/')
    ip = IP.from_string(address)
    cidr = CIDR.create_cidr(ip.pack_ip(), int(mask))
    nlri = INET.from_cidr(cidr, ip.afi, safi)
    nexthop = IP.from_string('192.0.2.1' if ip.afi == AFI.ipv4 else '2001:db8::ffff')
    return RoutedNLRI(nlri, nexthop)


def decode_messages(collection: UpdateCollection, negotiated: Negotiated) -> list[UpdateCollection]:
    messages = list(collection.messages(negotiated))
    assert all(len(message) <= negotiated.msg_size for message in messages)
    return [Update.unpack_message(message[19:], negotiated).parse(negotiated) for message in messages]


def test_suppressed_mp_withdrawal_does_not_emit_an_empty_update():
    negotiated = negotiated_session()
    withdrawal = routed_prefix('2001:db8::1/128').nlri
    collection = UpdateCollection([], [withdrawal], AttributeCollection())
    assert list(collection.messages(negotiated, include_withdraw=False)) == []


def test_ipv4_multicast_keeps_its_safi_without_role_policy():
    negotiated = negotiated_session()
    route = routed_prefix('239.1.0.0/16', SAFI.multicast)
    decoded = decode_messages(UpdateCollection([route], [], AttributeCollection()), negotiated)
    assert [
        (item.nlri.family().afi_safi(), str(item.nlri.cidr)) for update in decoded for item in update.announces
    ] == [((AFI.ipv4, SAFI.multicast), '239.1.0.0/16')]
    withdrawn = decode_messages(UpdateCollection([], [route.nlri], AttributeCollection()), negotiated)
    assert [(item.family().afi_safi(), str(item.cidr)) for update in withdrawn for item in update.withdraws] == [
        ((AFI.ipv4, SAFI.multicast), '239.1.0.0/16')
    ]


def test_native_prefix_is_not_repeated_in_the_following_mp_packet():
    negotiated = negotiated_session()
    native = routed_prefix('10.0.0.0/24')
    multiprotocol = routed_prefix('2001:db8::/32')
    attributes = AttributeCollection()
    attributes.add(NextHop.from_string('192.0.2.1'))
    decoded = decode_messages(UpdateCollection([native, multiprotocol], [], attributes), negotiated)
    assert Counter(str(item.nlri.cidr) for update in decoded for item in update.announces) == Counter(
        ['10.0.0.0/24', '2001:db8::/32']
    )
