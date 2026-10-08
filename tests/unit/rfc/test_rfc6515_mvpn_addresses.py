"""RFC 6515: the address family of a PE address in an MCAST-VPN route is its length, not the AFI.

An SP with an IPv4 core may carry IPv6 customer multicast, and the other way round, so
the AFI of an MCAST-VPN route speaks for the customer addresses only.  The one PE address
exabgp reads is the Next Hop of the MP_REACH_NLRI: the route types it decodes (5, 6 and
7) carry no Originating Router's IP Address, and 1 to 4 are kept as opaque bytes.

AFI 2 already took a next hop of 4 or 16.  AFI 1 took 4 alone, so an IPv4 MVPN route
from a PE in an IPv6 core reset the session with 3/9.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.message.update.nlri.collection import MPNLRICollection
from exabgp.bgp.message.update.nlri.mvpn import SourceAD
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.protocol.ip import IP, IPv4, IPv6
from tests import negotiation

pytestmark = pytest.mark.timeout(10)

MVPN_V4: FamilyTuple = (AFI.ipv4, SAFI.mcast_vpn)
MVPN_V6: FamilyTuple = (AFI.ipv6, SAFI.mcast_vpn)

ROUTE_TYPE_SOURCE_ACTIVE = 5
NEXT_HOP_V4 = IPv4.pton('192.0.2.1')
NEXT_HOP_V6 = IPv6.pton('2001:db8::2')

# the customer addresses follow the AFI, the next hop does not
CUSTOMER = {
    AFI.ipv4: (IPv4.pton('10.0.0.1'), IPv4.pton('239.1.1.1')),
    AFI.ipv6: (IPv6.pton('2001:db8::1'), IPv6.pton('ff0e::1')),
}


def session() -> Negotiated:
    return negotiation.negotiated([MVPN_V4, MVPN_V6])


def source_active(afi: AFI) -> bytes:
    """A route type 5 MCAST-VPN NLRI for the customer addresses of this AFI."""
    source, group = CUSTOMER[afi]
    payload = bytes(8) + bytes([len(source) * 8]) + source + bytes([len(group) * 8]) + group
    return bytes([ROUTE_TYPE_SOURCE_ACTIVE, len(payload)]) + payload


def reach(family: FamilyTuple, next_hop: bytes) -> bytes:
    afi, safi = family
    return pack('!HB', int(afi), int(safi)) + bytes([len(next_hop)]) + next_hop + bytes([0]) + source_active(afi)


def received_next_hop(family: FamilyTuple, next_hop: bytes) -> IP:
    attribute = MPRNLRI.unpack_attribute(reach(family, next_hop), session())
    assert isinstance(attribute, MPRNLRI)
    routed = list(attribute.iter_routed())
    assert len(routed) == 1
    assert isinstance(routed[0].nlri, SourceAD)
    return routed[0].nexthop


@pytest.mark.rfc('rfc6515#1.1-pe-address-family-not-from-afi')
@pytest.mark.rfc('rfc6515#2-next-hop-length-4-or-16')
@pytest.mark.parametrize('family', [MVPN_V4, MVPN_V6], ids=['afi-1', 'afi-2'])
def test_either_afi_takes_a_next_hop_of_either_protocol(family: FamilyTuple) -> None:
    assert str(received_next_hop(family, NEXT_HOP_V4)) == '192.0.2.1'
    assert str(received_next_hop(family, NEXT_HOP_V6)) == '2001:db8::2'


@pytest.mark.rfc('rfc6515#2-next-hop-length-4-or-16', polarity='negative')
@pytest.mark.parametrize('family', [MVPN_V4, MVPN_V6], ids=['afi-1', 'afi-2'])
@pytest.mark.parametrize('size', [0, 8, 12, 24, 32])
def test_a_next_hop_neither_4_nor_16_octets_is_an_incorrect_attribute(family: FamilyTuple, size: int) -> None:
    """RFC 4760 7 handles an incorrect MP_REACH_NLRI, which ExaBGP answers with 3/9.

    32 is in the list: RFC 2545's global and link-local pair is not one of the two lengths
    this section allows.
    """
    with pytest.raises(Notify) as raised:
        MPRNLRI.unpack_attribute(reach(family, bytes(range(1, size + 1))), session())
    assert (raised.value.code, raised.value.subcode) == (3, 9)


def sent_next_hop(afi: AFI, next_hop: str) -> bytes:
    """The Next Hop field of the MP_REACH_NLRI the encoder produces for one Source Active route."""
    source, group = CUSTOMER[afi]
    nlri = SourceAD.make_sourcead(RouteDistinguisher(bytes(8)), afi, IP.create_ip(source), IP.create_ip(group))
    collection = MPNLRICollection.from_routed([RoutedNLRI(nlri, IP.from_string(next_hop))], {}, afi, SAFI.mcast_vpn)
    (attribute,) = collection.packed_reach_attributes(session())
    header = 4 if attribute[0] & 0x10 else 3
    length = attribute[header + 3]
    return bytes(attribute[header + 4 : header + 4 + length])


@pytest.mark.rfc('rfc6515#1.1-pe-address-family-not-from-afi')
def test_the_next_hop_is_sent_at_its_own_length_whatever_the_afi() -> None:
    """Four octets for an IPv4 PE under AFI 2: RFC 6515 1.1 refuses the IPv4-mapped form."""
    assert sent_next_hop(AFI.ipv4, '192.0.2.1') == NEXT_HOP_V4
    assert sent_next_hop(AFI.ipv4, '2001:db8::2') == NEXT_HOP_V6
    assert sent_next_hop(AFI.ipv6, '192.0.2.1') == NEXT_HOP_V4
    assert sent_next_hop(AFI.ipv6, '2001:db8::2') == NEXT_HOP_V6


# ------------------------------------------- section 2, items 2 to 4: the Originating Router
#
# Route types 1, 3 and 4 end with the Originating Router's IP Address, whose length is what
# the NLRI length leaves once the fields in front of it are read: 4 or 16, or the
# MP_REACH_NLRI is "incorrect" and RFC 4760 7 applies, which exabgp answers with 3/9.

ROUTE_TYPE_INTRA_AS_IPMSI = 1
ROUTE_TYPE_SPMSI = 3
ROUTE_TYPE_LEAF = 4
RD = bytes(8)
ORIGINATORS = [IPv4.pton('192.0.2.9'), IPv6.pton('2001:db8::9')]
WRONG_SIZES = [0, 1, 3, 5, 8, 15, 17, 20]


def mvpn_route(route_type: int, payload: bytes) -> bytes:
    return bytes([route_type, len(payload)]) + payload


def intra_as_ipmsi(originator: bytes) -> bytes:
    return mvpn_route(ROUTE_TYPE_INTRA_AS_IPMSI, RD + originator)


def spmsi(originator: bytes, source: bytes = CUSTOMER[AFI.ipv4][0], group: bytes = CUSTOMER[AFI.ipv4][1]) -> bytes:
    fields = bytes([len(source) * 8]) + source + bytes([len(group) * 8]) + group
    return mvpn_route(ROUTE_TYPE_SPMSI, RD + fields + originator)


def leaf(originator: bytes) -> bytes:
    """A Leaf A-D route whose Route Key is an S-PMSI A-D route, as RFC 6514 4.4 has it."""
    return mvpn_route(ROUTE_TYPE_LEAF, spmsi(ORIGINATORS[0]) + originator)


def reach_of(family: FamilyTuple, nlri: bytes) -> list[RoutedNLRI]:
    afi, safi = family
    value = pack('!HB', int(afi), int(safi)) + bytes([len(NEXT_HOP_V4)]) + NEXT_HOP_V4 + bytes([0]) + nlri
    attribute = MPRNLRI.unpack_attribute(value, session())
    assert isinstance(attribute, MPRNLRI)
    return list(attribute.iter_routed())


def accepted(wire: bytes) -> None:
    """Every family and both originator sizes decode, and pack back to the same bytes."""
    for family in (MVPN_V4, MVPN_V6):
        (routed,) = reach_of(family, wire)
        assert bytes(routed.nlri.pack_nlri(session())) == wire


def incorrect(wire: bytes) -> None:
    with pytest.raises(Notify) as raised:
        reach_of(MVPN_V4, wire)
    assert (raised.value.code, raised.value.subcode) == (3, 9)


@pytest.mark.rfc('rfc6515#2-intra-as-ipmsi-originator-4-or-16')
@pytest.mark.parametrize('originator', ORIGINATORS, ids=['ipv4', 'ipv6'])
def test_an_intra_as_ipmsi_route_with_a_4_or_16_octet_originator_is_accepted(originator: bytes) -> None:
    accepted(intra_as_ipmsi(originator))


@pytest.mark.rfc('rfc6515#2-intra-as-ipmsi-originator-4-or-16', polarity='negative')
@pytest.mark.parametrize('size', WRONG_SIZES)
def test_an_intra_as_ipmsi_route_with_another_originator_size_is_incorrect(size: int) -> None:
    incorrect(intra_as_ipmsi(bytes(range(1, size + 1))))


@pytest.mark.rfc('rfc6515#2-spmsi-originator-4-or-16')
@pytest.mark.parametrize('originator', ORIGINATORS, ids=['ipv4', 'ipv6'])
def test_an_spmsi_route_with_a_4_or_16_octet_originator_is_accepted(originator: bytes) -> None:
    accepted(spmsi(originator))
    accepted(spmsi(originator, *CUSTOMER[AFI.ipv6]))
    # RFC 6625 wildcards: a source or group length of zero
    accepted(spmsi(originator, b'', b''))


@pytest.mark.rfc('rfc6515#2-spmsi-originator-4-or-16', polarity='negative')
@pytest.mark.parametrize('size', WRONG_SIZES)
def test_an_spmsi_route_with_another_originator_size_is_incorrect(size: int) -> None:
    incorrect(spmsi(bytes(range(1, size + 1))))


@pytest.mark.rfc('rfc6515#2-spmsi-originator-4-or-16', polarity='negative')
def test_an_spmsi_route_whose_source_runs_past_the_route_is_incorrect() -> None:
    """The lengths in front leave no room for an originator: nothing can be computed."""
    incorrect(mvpn_route(ROUTE_TYPE_SPMSI, RD + bytes([128]) + bytes(4)))
    incorrect(mvpn_route(ROUTE_TYPE_SPMSI, RD))


@pytest.mark.rfc('rfc6515#2-leaf-originator-4-or-16')
@pytest.mark.parametrize('originator', ORIGINATORS, ids=['ipv4', 'ipv6'])
def test_a_leaf_route_with_a_4_or_16_octet_originator_is_accepted(originator: bytes) -> None:
    accepted(leaf(originator))


@pytest.mark.rfc('rfc6515#2-leaf-originator-4-or-16', polarity='negative')
@pytest.mark.parametrize('size', WRONG_SIZES)
def test_a_leaf_route_with_another_originator_size_is_incorrect(size: int) -> None:
    incorrect(leaf(bytes(range(1, size + 1))))


@pytest.mark.rfc('rfc6515#2-leaf-originator-4-or-16', polarity='negative')
def test_a_leaf_route_whose_route_key_runs_past_the_route_is_incorrect() -> None:
    incorrect(mvpn_route(ROUTE_TYPE_LEAF, bytes([ROUTE_TYPE_SPMSI, 40]) + bytes(4)))
    incorrect(mvpn_route(ROUTE_TYPE_LEAF, b''))


# ---------------------------------------- section 4.2, the Tunnel Identifier and the next hop

TUNNEL_TYPE_INGRESS_REPLICATION = 6


def update_with_pmsi(identifier: bytes) -> bytes:
    """An iBGP UPDATE: an Intra-AS I-PMSI A-D route behind an IPv4 next hop, and a PMSI."""
    pmsi = bytes([0, TUNNEL_TYPE_INGRESS_REPLICATION, 0, 0, 0]) + identifier
    nlri = intra_as_ipmsi(ORIGINATORS[0])
    reach_value = pack('!HB', int(AFI.ipv4), int(SAFI.mcast_vpn)) + bytes([4]) + NEXT_HOP_V4 + bytes([0]) + nlri
    attributes = (
        bytes([0x40, 1, 1, 0])  # ORIGIN IGP
        + bytes([0x40, 2, 0])  # an empty AS_PATH, iBGP
        + bytes([0x80, 14, len(reach_value)])
        + reach_value
        + bytes([0xC0, 22, len(pmsi)])
        + pmsi
    )
    return pack('!H', 0) + pack('!H', len(attributes)) + attributes


@pytest.mark.rfc('rfc6515#4.2-tunnel-identifier-follows-next-hop')
@pytest.mark.xfail(strict=True, reason='the PMSI decoder cannot see the next hop, see the ledger note')
def test_an_ipv6_tunnel_identifier_behind_an_ipv4_next_hop_is_a_malformed_pmsi() -> None:
    from exabgp.bgp.message.update import UpdateCollection

    update = UpdateCollection.unpack_message(update_with_pmsi(IPv6.pton('2001:db8::9')), session())
    assert update.announces == []
