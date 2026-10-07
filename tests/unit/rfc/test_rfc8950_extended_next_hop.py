"""The MP_REACH_NLRI next hop: which lengths a family allows, received and sent.

RFC 8950 lets an IPv4 or VPN-IPv4 NLRI carry an IPv6 next hop, 16 or 32 octets, 24 or 48
for the VPN SAFIs, once the Extended Next Hop Encoding capability says so for that
<AFI, SAFI>.  The decoder used to switch every family to "the next hop family the length
suggests" as soon as any extended next hop entry was negotiated: EVPN, VPLS and BGP-LS
then looked themselves up under AFI IPv6 and raised KeyError, and a family the capability
was never negotiated for took a 16 octet next hop.

RFC 4659 3.2.1.1 gives a VPN-IPv6 next hop 24 or 48 octets, a route distinguisher in front
of each address, where the table said 40.  RFC 4798 encodes the IPv4 next hop of an IPv6
route as an IPv4-mapped IPv6 address, which the encoder sent as four bare octets, a length
RFC 2545 3 does not allow for an IPv6 next hop.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI, NextHopWithLinkLocal
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.collection import MPNLRICollection
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
from exabgp.bgp.message.update.nlri.qualifier.labels import Labels
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.protocol.ip import IP, IPv6
from tests import negotiation

IPV4_UNICAST: FamilyTuple = (AFI.ipv4, SAFI.unicast)
IPV4_VPN: FamilyTuple = (AFI.ipv4, SAFI.mpls_vpn)
IPV6_UNICAST: FamilyTuple = (AFI.ipv6, SAFI.unicast)
IPV6_VPN: FamilyTuple = (AFI.ipv6, SAFI.mpls_vpn)
EVPN: FamilyTuple = (AFI.l2vpn, SAFI.evpn)
VPLS: FamilyTuple = (AFI.l2vpn, SAFI.vpls)
BGP_LS: FamilyTuple = (AFI.bgpls, SAFI.bgp_ls)
FAMILIES = [IPV4_UNICAST, IPV4_VPN, IPV6_UNICAST, IPV6_VPN, EVPN, VPLS, BGP_LS]

GLOBAL = IPv6.pton('2001:db8::1')
LINK_LOCAL = IPv6.pton('fe80::1')
RD_ZERO = bytes(8)
RD_SET = pack('!HHI', 0, 1, 1)

# 10.0.0.0/24, as unicast and as a VPN route with one label and a route distinguisher
NLRI_V4 = bytes([24, 10, 0, 0])
NLRI_V4_VPN = bytes([24 + 24 + 64]) + bytes([0, 1, 0x41]) + RD_SET + bytes([10, 0, 0])
NLRI_V6_VPN = bytes([24 + 24 + 64]) + bytes([0, 1, 0x41]) + RD_SET + bytes([0x20, 0x01, 0x0D])


def session(*extended: tuple[AFI, SAFI, AFI]) -> Negotiated:
    return negotiation.negotiated(FAMILIES, nexthop=list(extended))


def reach(family: FamilyTuple, next_hop: bytes, nlri: bytes = NLRI_V4) -> bytes:
    afi, safi = family
    return pack('!HB', int(afi), int(safi)) + bytes([len(next_hop)]) + next_hop + bytes([0]) + nlri


def decoded_next_hop(family: FamilyTuple, next_hop: bytes, negotiated: Negotiated, nlri: bytes = NLRI_V4) -> IP:
    attribute = MPRNLRI.unpack_attribute(reach(family, next_hop, nlri), negotiated)
    assert isinstance(attribute, MPRNLRI)
    routed = list(attribute.iter_routed())
    assert len(routed) == 1
    return routed[0].nexthop


def refused(family: FamilyTuple, next_hop: bytes, negotiated: Negotiated) -> Notify:
    with pytest.raises(Notify) as raised:
        MPRNLRI.unpack_attribute(reach(family, next_hop), negotiated)
    assert (raised.value.code, raised.value.subcode) == (3, 9)
    return raised.value


# ------------------------------------------------------------------ receiving


@pytest.mark.rfc('rfc8950#3-length-determines-next-hop-protocol')
@pytest.mark.rfc('rfc7606#7.11-mp-reach-next-hop-session-reset', polarity='negative')
def test_the_length_says_which_protocol_the_next_hop_is() -> None:
    negotiated = session((AFI.ipv4, SAFI.unicast, AFI.ipv6), (AFI.ipv4, SAFI.mpls_vpn, AFI.ipv6))
    assert str(decoded_next_hop(IPV4_UNICAST, bytes([192, 0, 2, 1]), negotiated)) == '192.0.2.1'
    assert str(decoded_next_hop(IPV4_UNICAST, GLOBAL, negotiated)) == '2001:db8::1'
    pair = decoded_next_hop(IPV4_UNICAST, GLOBAL + LINK_LOCAL, negotiated)
    assert isinstance(pair, NextHopWithLinkLocal) and str(pair.link_local) == 'fe80::1'
    vpn = decoded_next_hop(IPV4_VPN, RD_ZERO + GLOBAL, negotiated, NLRI_V4_VPN)
    assert str(vpn) == '2001:db8::1'
    vpn_pair = decoded_next_hop(IPV4_VPN, RD_ZERO + GLOBAL + RD_ZERO + LINK_LOCAL, negotiated, NLRI_V4_VPN)
    assert isinstance(vpn_pair, NextHopWithLinkLocal) and str(vpn_pair.link_local) == 'fe80::1'


@pytest.mark.rfc('rfc8950#3-length-determines-next-hop-protocol', polarity='negative')
@pytest.mark.rfc('rfc7606#7.11-mp-reach-next-hop-session-reset')
def test_an_ipv6_next_hop_needs_the_capability_for_that_family() -> None:
    # negotiated for IPv4 unicast only: the VPN family keeps its RFC 4364 lengths
    negotiated = session((AFI.ipv4, SAFI.unicast, AFI.ipv6))
    refused(IPV4_VPN, RD_ZERO + GLOBAL, negotiated)
    refused(IPV4_UNICAST, GLOBAL, session())
    # and a length RFC 8950 3 does not list is refused with it
    refused(IPV4_UNICAST, bytes(12), negotiated)
    refused(IPV4_UNICAST, bytes(24), negotiated)


@pytest.mark.rfc('rfc7606#7.11-mp-reach-next-hop-session-reset')
@pytest.mark.parametrize('family', [EVPN, VPLS, BGP_LS], ids=['evpn', 'vpls', 'bgp-ls'])
def test_a_family_outside_rfc_8950_is_answered_with_a_notification_not_a_key_error(family: FamilyTuple) -> None:
    negotiated = session((AFI.ipv4, SAFI.unicast, AFI.ipv6))
    refused(family, bytes(32), negotiated)
    refused(family, bytes(12), negotiated)


def test_an_evpn_next_hop_may_be_ipv6() -> None:
    """RFC 7432 7: "the IPv4 or IPv6 address of the advertising PE" (the length says which)."""
    from exabgp.protocol.family import Family

    lengths, _ = Family.size[EVPN]
    assert 16 in lengths and 4 in lengths


@pytest.mark.rfc('rfc4659#3.2.1.1-ipv6-transport-next-hop-rd-zero')
def test_a_vpn_ipv6_next_hop_pair_is_two_route_distinguishers_and_two_addresses() -> None:
    negotiated = session()
    pair = decoded_next_hop(IPV6_VPN, RD_ZERO + GLOBAL + RD_ZERO + LINK_LOCAL, negotiated, NLRI_V6_VPN)
    assert isinstance(pair, NextHopWithLinkLocal)
    assert str(pair) == '2001:db8::1'
    assert str(pair.link_local) == 'fe80::1'


@pytest.mark.rfc('rfc4659#3.2.1.1-ipv6-transport-next-hop-rd-zero', polarity='negative')
@pytest.mark.rfc('rfc7606#7.11-mp-reach-next-hop-session-reset')
def test_a_vpn_ipv6_next_hop_of_forty_octets_or_with_a_second_rd_set_is_refused() -> None:
    negotiated = session()
    refused(IPV6_VPN, RD_ZERO + GLOBAL + LINK_LOCAL, negotiated)
    refused(IPV6_VPN, RD_ZERO + GLOBAL + RD_SET + LINK_LOCAL, negotiated)


@pytest.mark.rfc('rfc2545#3-next-hop-length', polarity='negative')
def test_a_four_octet_next_hop_for_an_ipv6_route_is_refused() -> None:
    refused(IPV6_UNICAST, bytes([192, 0, 2, 1]), session())


def test_a_four_octet_next_hop_for_an_ipv6_route_is_accepted_when_both_sides_agreed_to_it() -> None:
    """Outside RFC 8950, but an explicit agreement: older releases send exactly this."""
    negotiated = session((AFI.ipv6, SAFI.unicast, AFI.ipv4))
    nlri = bytes([32, 0x20, 0x01, 0x0D, 0xB8])
    assert str(decoded_next_hop(IPV6_UNICAST, bytes([192, 0, 2, 1]), negotiated, nlri)) == '192.0.2.1'


# ------------------------------------------------------------------ sending


def sent_next_hops(family: FamilyTuple, nlri: NLRI, next_hop: str, negotiated: Negotiated) -> list[bytes]:
    """The Next Hop field of every MP_REACH_NLRI the encoder produces for this one route."""
    afi, safi = family
    collection = MPNLRICollection.from_routed([RoutedNLRI(nlri, IP.from_string(next_hop))], {}, afi, safi)
    fields = []
    for attribute in collection.packed_reach_attributes(negotiated):
        header = 4 if attribute[0] & 0x10 else 3
        length = attribute[header + 3]
        fields.append(bytes(attribute[header + 4 : header + 4 + length]))
    return fields


def v4_route() -> INET:
    return INET.from_cidr(CIDR.create_cidr(IP.pton('10.0.0.0'), 24), AFI.ipv4, SAFI.unicast)


def v4_vpn_route() -> IPVPN:
    rd = RouteDistinguisher.make_from_elements('65000', 1)
    cidr = CIDR.create_cidr(IP.pton('10.0.0.0'), 24)
    return IPVPN.from_cidr(cidr, AFI.ipv4, labels=Labels.make_labels([100]), rd=rd)


def v6_route(safi: SAFI = SAFI.unicast) -> INET:
    return INET.from_cidr(CIDR.create_cidr(IP.pton('2001:db8::'), 32), AFI.ipv6, safi)


def v6_vpn_route() -> IPVPN:
    rd = RouteDistinguisher.make_from_elements('65000', 1)
    cidr = CIDR.create_cidr(IP.pton('2001:db8::'), 32)
    return IPVPN.from_cidr(cidr, AFI.ipv6, labels=Labels.make_labels([100]), rd=rd)


@pytest.mark.rfc('rfc8950#4-advertise-only-after-capability')
def test_an_ipv4_route_goes_out_with_an_ipv6_next_hop_once_the_capability_allows_it() -> None:
    negotiated = session((AFI.ipv4, SAFI.unicast, AFI.ipv6), (AFI.ipv4, SAFI.mpls_vpn, AFI.ipv6))
    assert sent_next_hops(IPV4_UNICAST, v4_route(), '2001:db8::1', negotiated) == [GLOBAL]
    assert sent_next_hops(IPV4_VPN, v4_vpn_route(), '2001:db8::1', negotiated) == [RD_ZERO + GLOBAL]


@pytest.mark.rfc('rfc8950#4-advertise-only-after-capability', polarity='negative')
def test_an_ipv4_route_with_an_ipv6_next_hop_is_not_sent_without_the_capability() -> None:
    assert sent_next_hops(IPV4_UNICAST, v4_route(), '2001:db8::1', session()) == []
    # negotiated for unicast, which says nothing of the VPN SAFI
    negotiated = session((AFI.ipv4, SAFI.unicast, AFI.ipv6))
    assert sent_next_hops(IPV4_VPN, v4_vpn_route(), '2001:db8::1', negotiated) == []


MAPPED = bytes(10) + b'\xff\xff' + bytes([192, 0, 2, 1])


@pytest.mark.rfc('rfc4798#2-ipv4-mapped-next-hop')
@pytest.mark.rfc('rfc2545#3-next-hop-length')
def test_the_ipv4_next_hop_of_an_ipv6_route_is_sent_ipv4_mapped() -> None:
    negotiated = session()
    assert sent_next_hops(IPV6_UNICAST, v6_route(), '192.0.2.1', negotiated) == [MAPPED]
    assert sent_next_hops(IPV6_VPN, v6_vpn_route(), '192.0.2.1', negotiated) == [RD_ZERO + MAPPED]


@pytest.mark.rfc('rfc4798#2-ipv4-mapped-next-hop', polarity='negative')
def test_the_ipv6_next_hop_of_an_ipv6_route_is_sent_as_it_is() -> None:
    negotiated = session()
    assert sent_next_hops(IPV6_UNICAST, v6_route(), '2001:db8::1', negotiated) == [GLOBAL]
    assert sent_next_hops(IPV6_VPN, v6_vpn_route(), '2001:db8::1', negotiated) == [RD_ZERO + GLOBAL]


@pytest.mark.rfc('rfc4659#3.2.1.1-ipv6-transport-next-hop-rd-zero')
def test_a_vpn_ipv6_route_sent_with_a_link_local_address_carries_two_route_distinguishers() -> None:
    configured = negotiation.neighbor()
    configured.session.local_link_local = IP.from_string('fe80::1')
    negotiated = negotiation.negotiated(FAMILIES, linklocal_nexthop=True, session=configured)
    assert sent_next_hops(IPV6_VPN, v6_vpn_route(), '2001:db8::1', negotiated) == [
        RD_ZERO + GLOBAL + RD_ZERO + LINK_LOCAL
    ]
