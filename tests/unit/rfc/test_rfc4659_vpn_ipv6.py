"""RFC 4659: the two things a VPN-IPv6 speaker can get wrong without a forwarding plane.

RFC 4364 states its encoding without a single RFC 2119 keyword (see the header of
qa/rfc/rfc4364.toml).  RFC 4659 does better: it puts a MUST on the AFI/SAFI pair and a
SHALL on the eight zero octets in front of the next hop, and those two are exactly the
parts exabgp owns.  Everything else in the document is a PE tunnelling packets.

The zero RD in the next hop is the one worth a negative test.  It is not a checksum: the
16 octets behind it are the IPv6 address, so a decoder which tolerated a non-zero RD
would not fail loudly, it would read the address eight octets late and hand the operator
a next hop nobody advertised.
"""

from __future__ import annotations

from struct import pack
from typing import cast

import pytest

from exabgp.bgp.message import Action, Open
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open import ASN, HoldTime, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.neighbor import Neighbor
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.nlri.ipvpn import IPVPNBase
from exabgp.bgp.message.update.nlri.label import LabelBase
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

# Section 2: an 8 octet route distinguisher in front of a 16 octet IPv6 address.
RD_OCTETS = 8
ZERO_RD = bytes(RD_OCTETS)
RD = pack('!HHL', 0, 1, 2)

# 2001:db8::/32 and one label, bottom of stack set.
LABEL = bytes([0x00, 0x06, 0x41])
PREFIX = bytes([0x20, 0x01, 0x0D, 0xB8])
PREFIX_BITS = 32

# The global IPv6 address of the advertising speaker, section 3.2.1.1.
NEXT_HOP = bytes([0x20, 0x01, 0x0D, 0xB8] + [0] * 11 + [1])
# The same field for section 3.2.1.2, an IPv4-mapped IPv6 address holding 192.0.2.1.
MAPPED_NEXT_HOP = bytes(10) + bytes([0xFF, 0xFF, 192, 0, 2, 1])


def session() -> Negotiated:
    """A negotiated session which advertised AFI 2 / SAFI 128 in both directions.

    `MPRNLRI.unpack_attribute` refuses a family which was not negotiated before it looks
    at the next hop at all, so without this the tests below would all pass for the wrong
    reason.
    """
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(65001)
    sent, received = Capabilities(), Capabilities()
    for capabilities in (sent, received):
        multiprotocol = MultiProtocol()
        multiprotocol.extend([(AFI.ipv6, SAFI.mpls_vpn)])
        capabilities[Capability.CODE.MULTIPROTOCOL] = multiprotocol
    negotiated = Negotiated(neighbor, Direction.IN)
    negotiated.sent(Open.make_open(Version(4), ASN(65001), HoldTime(90), RouterID('192.0.2.1'), sent))
    negotiated.received(Open.make_open(Version(4), ASN(65002), HoldTime(90), RouterID('192.0.2.2'), received))
    return negotiated


def vpn_nlri(rd: bytes = RD) -> bytes:
    return bytes([len(LABEL) * 8 + RD_OCTETS * 8 + PREFIX_BITS]) + LABEL + rd + PREFIX


def mp_reach(next_hop: bytes, afi: AFI = AFI.ipv6, safi: SAFI = SAFI.mpls_vpn) -> bytes:
    """An MP_REACH_NLRI value: AFI, SAFI, next hop, the reserved octet, then the NLRI."""
    return pack('!HB', afi, safi) + bytes([len(next_hop)]) + next_hop + bytes([0]) + vpn_nlri()


@pytest.mark.rfc('rfc4659#3.2-afi-and-safi-values')
def test_afi_two_safi_one_twenty_eight_decodes_as_a_vpn_ipv6_route() -> None:
    nlri, rest = NLRI.unpack_nlri(AFI.ipv6, SAFI.mpls_vpn, vpn_nlri(), Action.ANNOUNCE, False, Negotiated.UNSET)
    assert rest == b''
    assert isinstance(nlri, IPVPNBase)
    assert nlri.afi == AFI.ipv6
    assert nlri.safi == SAFI.mpls_vpn
    assert str(nlri.cidr) == '2001:db8::/32'
    assert str(nlri.rd) == ' rd 1:2'


@pytest.mark.rfc('rfc4659#3.2-afi-and-safi-values', polarity='negative')
def test_the_neighbouring_safi_carries_no_route_distinguisher() -> None:
    """AFI 2 with SAFI 4 is labelled unicast, and reading an RD there would be wrong."""
    wire = bytes([len(LABEL) * 8 + PREFIX_BITS]) + LABEL + PREFIX
    nlri, rest = NLRI.unpack_nlri(AFI.ipv6, SAFI.nlri_mpls, wire, Action.ANNOUNCE, False, Negotiated.UNSET)
    assert rest == b''
    assert isinstance(nlri, LabelBase)
    assert not isinstance(nlri, IPVPNBase)
    assert str(nlri.cidr) == '2001:db8::/32'


@pytest.mark.rfc('rfc4659#3.2.1.1-ipv6-transport-next-hop-rd-zero')
def test_a_next_hop_whose_route_distinguisher_is_zero_is_accepted() -> None:
    attribute = cast(MPRNLRI, MPRNLRI.unpack_attribute(mp_reach(ZERO_RD + NEXT_HOP), session()))
    routed = list(attribute.iter_routed())
    assert len(routed) == 1
    assert str(routed[0].nexthop) == '2001:db8::1'


@pytest.mark.rfc('rfc4659#3.2.1.1-ipv6-transport-next-hop-rd-zero', polarity='negative')
def test_a_next_hop_whose_route_distinguisher_is_not_zero_is_refused() -> None:
    """Otherwise the IPv6 address would be read eight octets late and look plausible."""
    with pytest.raises(Notify) as raised:
        MPRNLRI.unpack_attribute(mp_reach(RD + NEXT_HOP), session())
    assert raised.value.code == 3
    assert 'route-distinguisher must be zero' in str(raised.value)


@pytest.mark.rfc('rfc4659#3.2.1.2-ipv4-transport-next-hop-rd-zero')
def test_an_ipv4_mapped_next_hop_with_a_zero_route_distinguisher_is_accepted() -> None:
    attribute = cast(MPRNLRI, MPRNLRI.unpack_attribute(mp_reach(ZERO_RD + MAPPED_NEXT_HOP), session()))
    routed = list(attribute.iter_routed())
    assert len(routed) == 1
    assert str(routed[0].nexthop).endswith('192.0.2.1')


@pytest.mark.rfc('rfc4659#3.2.1.2-ipv4-transport-next-hop-rd-zero', polarity='negative')
def test_an_ipv4_mapped_next_hop_with_a_non_zero_route_distinguisher_is_refused() -> None:
    with pytest.raises(Notify) as raised:
        MPRNLRI.unpack_attribute(mp_reach(RD + MAPPED_NEXT_HOP), session())
    assert raised.value.code == 3


@pytest.mark.rfc('rfc4659#3.2.1.1-ipv6-transport-next-hop-rd-zero', polarity='negative')
def test_a_next_hop_of_the_wrong_length_is_refused() -> None:
    """16 octets is a valid IPv6 next hop elsewhere and is not one here."""
    with pytest.raises(Notify) as raised:
        MPRNLRI.unpack_attribute(mp_reach(NEXT_HOP), session())
    assert raised.value.code == 3
