"""Wire-level packetization contracts with and without OTC policy."""

from collections import Counter

import pytest

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.open.capability.role import RoleValue
from exabgp.bgp.message.update import Update, UpdateCollection
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection, NextHop
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.neighbor import Neighbor
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP


def negotiated_session(role: RoleValue = RoleValue.NO_ROLE) -> Negotiated:
    negotiated = Negotiated.make_negotiated(Neighbor(), Direction.IN)
    negotiated.local_as = ASN(65001)
    negotiated.peer_as = ASN(65002)
    negotiated.asn4 = True
    negotiated.role = role
    negotiated.role_otc = True
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


@pytest.mark.parametrize('role,count', [(RoleValue.NO_ROLE, 237), (RoleValue.PROVIDER, 236)])
def test_full_mp_reach_does_not_starve_pending_withdrawal(role, count):
    negotiated = negotiated_session(role)
    announces = [routed_prefix(f'2001:db8::{index:x}/128') for index in range(count)]
    withdrawal = routed_prefix('2001:db8:1::1/128').nlri
    decoded = decode_messages(UpdateCollection(announces, [withdrawal], AttributeCollection()), negotiated)
    assert Counter(str(item.nlri.cidr) for update in decoded for item in update.announces) == Counter(
        str(item.nlri.cidr) for item in announces
    )
    assert [str(item.cidr) for update in decoded for item in update.withdraws] == ['2001:db8:1::1/128']


def test_fragmented_withdrawals_keep_reannounced_prefix_after_its_withdrawal():
    negotiated = negotiated_session()
    announced = routed_prefix('2001:db8::12b/128')
    withdrawals = [routed_prefix(f'2001:db8::{index:x}/128').nlri for index in range(300)]
    decoded = decode_messages(UpdateCollection([announced], withdrawals, AttributeCollection()), negotiated)
    assert Counter(str(item.cidr) for update in decoded for item in update.withdraws) == Counter(
        str(item.cidr) for item in withdrawals
    )
    advertised = set()
    for update in decoded:
        advertised.difference_update(str(item.cidr) for item in update.withdraws)
        advertised.update(str(item.nlri.cidr) for item in update.announces)
    assert advertised == {str(announced.nlri.cidr)}


def test_fragmentation_keeps_reannounced_prefix_after_its_withdrawal():
    negotiated = negotiated_session()
    announces = [routed_prefix(f'2001:db8::{index:x}/128') for index in range(300)]
    decoded = decode_messages(UpdateCollection(announces, [announces[0].nlri], AttributeCollection()), negotiated)
    advertised = set()
    for update in decoded:
        advertised.difference_update(str(item.cidr) for item in update.withdraws)
        advertised.update(str(item.nlri.cidr) for item in update.announces)
    assert advertised == {str(item.nlri.cidr) for item in announces}


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


def test_fragmented_withdrawals_do_not_inherit_automatic_otc():
    negotiated = negotiated_session(RoleValue.PROVIDER)
    announced = routed_prefix('2001:db8:1::1/128')
    withdrawals = [routed_prefix(f'2001:db8::{index:x}/128').nlri for index in range(300)]
    decoded = decode_messages(UpdateCollection([announced], withdrawals, AttributeCollection()), negotiated)
    assert Counter(str(item.cidr) for update in decoded for item in update.withdraws) == Counter(
        str(item.cidr) for item in withdrawals
    )
    for update in decoded:
        if update.announces:
            assert update.attributes[Attribute.CODE.OTC].asn == negotiated.local_as
        else:
            assert Attribute.CODE.OTC not in update.attributes
