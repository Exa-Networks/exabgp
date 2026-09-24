"""RFC 7432: the EVPN NLRI, decoded from bytes a peer could actually send.

RFC 7432 describes its own wire format without a single RFC 2119 keyword.  Section 7
says what the Route Type and Length octets mean in flat declarative prose, the four route
type diagrams in sections 7.1 to 7.4 carry no keyword at all, and section 5 introduces
the ten octet ESI the same way.  So the requirements recorded in qa/rfc/rfc7432.toml and
marked below are the ones from sections 8, 9 and 10, which constrain those same fields in
passing and do use a keyword.

The tests that carry no `rfc` marker are here anyway.  They hold the Route Type and
Length octets to what section 7 says, and a decoder which gets those wrong gets every
marked requirement below wrong too - it simply cannot be claimed as compliance with a
sentence the document never wrote as a rule.

Everything drives `EVPN.unpack_nlri`, the real entry point the reactor uses, on bytes
built here rather than on anything the encoder produced: an encoder and a decoder that
agree with each other and disagree with the RFC pass every round-trip test ever written.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.nlri.evpn.ethernetad import EthernetAD
from exabgp.bgp.message.update.nlri.evpn.mac import MAC
from exabgp.bgp.message.update.nlri.evpn.multicast import Multicast
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN, GenericEVPN
from exabgp.bgp.message.update.nlri.evpn.segment import EthernetSegment
from exabgp.protocol.family import AFI, SAFI

# RFC 7432 section 7: "+ 1 - Ethernet Auto-Discovery (A-D) route", and so on.
ETHERNET_AD = 1
MAC_IP_ADVERTISEMENT = 2
INCLUSIVE_MULTICAST = 3
ETHERNET_SEGMENT = 4

# Field widths from the diagrams in sections 7.1 to 7.4, in octets.
RD_SIZE = 8
ESI_SIZE = 10
ETAG_SIZE = 4
MAC_SIZE = 6
LABEL_SIZE = 3

# The lengths sections 9.2.1 and 10 write in bits.
MAC_BITS = 48
IPV4_BITS = 32
IPV6_BITS = 128
NO_IP_BITS = 0

# Values picked so that a decoder reading one octet early or late produces something
# visibly different rather than another plausible value.
RD = bytes.fromhex('0001c000020104d2')
ESI = bytes.fromhex('01001122334455667788')
ESI_OTHER = bytes.fromhex('03aabbccddeeff010203')
ETAG = bytes.fromhex('0000007b')  # 123
MAC_ADDRESS = bytes.fromhex('001122334455')
LABEL = bytes.fromhex('000641')  # label 100, bottom of stack
IPV4 = bytes.fromhex('c0000202')  # 192.0.2.2
IPV6 = bytes.fromhex('20010db8' + '00' * 11 + '01')  # 2001:db8::1


def nlri(route_type: int, payload: bytes) -> bytes:
    """A complete EVPN NLRI: Route Type octet, Length octet, then the payload.

    Section 7: "The Length field indicates the length in octets of the Route Type
    specific field of the EVPN NLRI."  So the Length counts the payload only, and the
    two header octets are not included in it.
    """
    assert len(payload) < 256
    return bytes([route_type, len(payload)]) + payload


def decode(data: bytes) -> tuple[NLRI, bytes]:
    """Run the real decoder, the way the reactor calls it, with ADD-PATH off."""
    decoded, remaining = EVPN.unpack_nlri(AFI.l2vpn, SAFI.evpn, data, Action.ANNOUNCE, False, Negotiated.UNSET)
    return decoded, bytes(remaining)


def mac_route(maclen: int, iplen: int, ip: bytes) -> bytes:
    """A MAC/IP Advertisement route, section 7.2, with the lengths under test."""
    payload = RD + ESI + ETAG + bytes([maclen]) + MAC_ADDRESS + bytes([iplen]) + ip + LABEL
    return nlri(MAC_IP_ADVERTISEMENT, payload)


def segment_route(iplen: int, ip: bytes, esi: bytes = ESI) -> bytes:
    """An Ethernet Segment route, section 7.4."""
    return nlri(ETHERNET_SEGMENT, RD + esi + bytes([iplen]) + ip)


def ad_route(esi: bytes = ESI, etag: bytes = ETAG) -> bytes:
    """An Ethernet A-D route, section 7.1."""
    return nlri(ETHERNET_AD, RD + esi + etag + LABEL)


# ------------------------------------------------------------------ section 9.2.1, MAC


@pytest.mark.rfc('rfc7432#9.2.1-mac-encoding-six-octets')
def test_a_mac_address_length_of_48_reads_the_six_octets_that_follow_it() -> None:
    decoded, remaining = decode(mac_route(MAC_BITS, NO_IP_BITS, b''))
    assert isinstance(decoded, MAC)
    assert remaining == b''
    assert decoded.maclen == MAC_BITS
    # The six octets, and only those six: a decoder off by one here would fold a byte of
    # the IP Address Length or of the ESI into the address.
    assert bytes(decoded.mac.pack_mac()) == MAC_ADDRESS
    assert str(decoded.mac) == '00:11:22:33:44:55'


@pytest.mark.rfc('rfc7432#9.2.1-mac-encoding-six-octets', polarity='negative')
@pytest.mark.parametrize('maclen', [0, 24, 47])
def test_a_mac_address_length_that_is_not_48_is_refused(maclen: int) -> None:
    with pytest.raises(Notify):
        decode(mac_route(maclen, NO_IP_BITS, b''))


def test_a_mac_address_length_above_48_is_refused() -> None:
    """The half of the same check which does fire, kept so the xfail above is precise.

    This carries no `rfc` marker: on its own it does not prove
    rfc7432#9.2.1-mac-encoding-six-octets, because a length of 24 gets through.
    """
    with pytest.raises(Notify) as raised:
        decode(mac_route(49, NO_IP_BITS, b''))
    assert raised.value.code == 3


# ------------------------------------------------------------------- section 9.2.1, IP


@pytest.mark.rfc('rfc7432#9.2.1-ip-encoding-four-or-sixteen')
@pytest.mark.parametrize(
    'iplen, address, expected',
    [
        (NO_IP_BITS, b'', None),
        (IPV4_BITS, IPV4, '192.0.2.2'),
        (IPV6_BITS, IPV6, '2001:db8::1'),
    ],
)
def test_an_ip_address_length_of_0_32_or_128_reads_that_many_octets(
    iplen: int, address: bytes, expected: str | None
) -> None:
    decoded, remaining = decode(mac_route(MAC_BITS, iplen, address))
    assert isinstance(decoded, MAC)
    assert remaining == b''
    # Section 9.2.1: "By default, the IP Address Length field is set to 0, and the IP
    # Address field is omitted from the route."  Omitted is not the same as zero.
    assert (str(decoded.ip) if decoded.ip is not None else None) == expected
    # The label sits behind the address, so it decodes only if the address was the right
    # width: this is what catches four octets read as sixteen.
    assert bytes(decoded.label.pack_labels()) == LABEL


@pytest.mark.rfc('rfc7432#9.2.1-ip-encoding-four-or-sixteen', polarity='negative')
@pytest.mark.parametrize('iplen', [8, 24, 48, 64, 127, 129, 255])
def test_an_ip_address_length_that_is_neither_4_nor_16_octets_is_refused(iplen: int) -> None:
    with pytest.raises(Notify) as raised:
        decode(mac_route(MAC_BITS, iplen, bytes(iplen // 8)))
    assert raised.value.code == 3


@pytest.mark.rfc('rfc7432#9.2.1-ip-encoding-four-or-sixteen', polarity='negative')
def test_an_ip_address_length_of_32_with_sixteen_octets_behind_it_is_refused() -> None:
    """The length octet says IPv4 and the route carries an IPv6 address.

    A decoder which validated only the length octet would take the first four octets of
    the address and then read the next three as the MPLS label.  Section 9.2.1 leans on
    the NLRI Length for exactly this: it "is sufficient to determine whether an IP
    address is encoded in this route and, if so, whether the encoded IP address is IPv4
    or IPv6", so the two have to agree.
    """
    with pytest.raises(Notify):
        decode(mac_route(MAC_BITS, IPV4_BITS, IPV6))


@pytest.mark.rfc('rfc7432#9.2.1-ip-encoding-four-or-sixteen', polarity='negative')
def test_an_ip_address_length_of_128_with_four_octets_behind_it_is_refused() -> None:
    with pytest.raises(Notify):
        decode(mac_route(MAC_BITS, IPV6_BITS, IPV4))


# ----------------------------------------------------------- section 8.1.1, the ES route


@pytest.mark.rfc('rfc7432#8.1.1-esi-ten-octet')
def test_an_ethernet_segment_route_takes_exactly_ten_octets_of_esi() -> None:
    # Two routes back to back.  The second one decodes only if the first consumed ten
    # octets of ESI and not nine or eleven.
    stream = segment_route(IPV4_BITS, IPV4) + segment_route(IPV6_BITS, IPV6, esi=ESI_OTHER)
    first, remaining = decode(stream)
    assert isinstance(first, EthernetSegment)
    assert bytes(first.esi.pack_esi()) == ESI
    assert len(first.esi) == ESI_SIZE
    assert str(first.ip) == '192.0.2.2'

    second, rest = decode(remaining)
    assert isinstance(second, EthernetSegment)
    assert bytes(second.esi.pack_esi()) == ESI_OTHER
    assert str(second.ip) == '2001:db8::1'
    assert rest == b''


@pytest.mark.rfc('rfc7432#8.1.1-esi-ten-octet', polarity='negative')
@pytest.mark.parametrize('kept', [0, 1, 5, 9])
def test_an_ethernet_segment_route_cut_inside_the_esi_is_refused(kept: int) -> None:
    """A type 4 route whose payload stops part-way through the ESI.

    The accessors index into the packed bytes, so without a length check first this
    surfaces as an IndexError out of `ESI.unpack_esi` rather than as a NOTIFICATION.
    """
    with pytest.raises(Notify) as raised:
        decode(nlri(ETHERNET_SEGMENT, RD + ESI[:kept]))
    assert raised.value.code == 3


@pytest.mark.rfc('rfc7432#8.1.1-esi-ten-octet', polarity='negative')
def test_an_ethernet_segment_route_with_the_esi_but_no_ip_length_is_refused() -> None:
    with pytest.raises(Notify):
        decode(nlri(ETHERNET_SEGMENT, RD + ESI))


# ----------------------------------------------------------- section 8.4.1, the A-D route


@pytest.mark.rfc('rfc7432#8.4.1-esi-ten-octet-ad')
def test_an_ethernet_ad_route_takes_exactly_ten_octets_of_esi() -> None:
    decoded, remaining = decode(ad_route())
    assert isinstance(decoded, EthernetAD)
    assert remaining == b''
    assert bytes(decoded.esi.pack_esi()) == ESI
    # The Ethernet Tag ID begins at the octet after the ESI, so reading it back proves
    # the boundary: section 7.1 puts the four octet tag immediately behind the ESI.
    assert decoded.etag.tag == 123
    assert bytes(decoded.label.pack_labels()) == LABEL


@pytest.mark.rfc('rfc7432#8.4.1-esi-ten-octet-ad', polarity='negative')
@pytest.mark.parametrize('kept', [0, 3, 9])
def test_an_ethernet_ad_route_cut_inside_the_esi_is_refused(kept: int) -> None:
    with pytest.raises(Notify) as raised:
        decode(nlri(ETHERNET_AD, RD + ESI[:kept]))
    assert raised.value.code == 3


@pytest.mark.rfc('rfc7432#8.4.1-esi-ten-octet-ad', polarity='negative')
def test_an_ethernet_ad_route_cut_inside_the_ethernet_tag_is_refused() -> None:
    """The A-D route has a variable length label stack and so no total size to check.

    That makes the fixed part its only floor: if the 24 octet minimum is ever relaxed,
    a route which stops inside the Ethernet Tag ID reaches `EthernetTag.unpack_etag`
    with a short slice.
    """
    with pytest.raises(Notify):
        decode(nlri(ETHERNET_AD, RD + ESI + ETAG[:2]))


# --------------------------------------------------- section 7, stated without a keyword
#
# Nothing below is marked against a requirement.  Section 7 describes the Route Type and
# Length octets in plain prose - "The Length field indicates the length in octets of the
# Route Type specific field of the EVPN NLRI" - with no RFC 2119 keyword anywhere in the
# section, so there is no requirement in qa/rfc/rfc7432.toml for these to prove.  They
# still guard the boundary every marked test above stands on.


def test_a_length_octet_larger_than_the_data_is_refused() -> None:
    route = mac_route(MAC_BITS, NO_IP_BITS, b'')
    lying = route[:1] + bytes([route[1] + 5]) + route[2:]
    with pytest.raises(Notify) as raised:
        decode(lying)
    assert raised.value.code == 3


def test_a_length_octet_smaller_than_the_route_needs_is_refused() -> None:
    """The Length octet is what bounds the route, not the size of the buffer.

    Here the buffer holds a whole MAC/IP route but the Length says it is five octets
    shorter.  Trusting the buffer rather than the Length would decode a route the peer
    did not send and leave the rest to be read as the next NLRI's header.
    """
    route = mac_route(MAC_BITS, NO_IP_BITS, b'')
    lying = route[:1] + bytes([route[1] - 5]) + route[2:]
    with pytest.raises(Notify):
        decode(lying)


@pytest.mark.parametrize('data', [b'', b'\x02', b'\x04'])
def test_an_nlri_too_short_for_its_two_header_octets_is_refused(data: bytes) -> None:
    with pytest.raises(Notify) as raised:
        decode(data)
    assert raised.value.code == 3


def test_a_length_octet_of_zero_is_refused_for_a_route_type_with_fixed_fields() -> None:
    for route_type in (ETHERNET_AD, MAC_IP_ADVERTISEMENT, INCLUSIVE_MULTICAST, ETHERNET_SEGMENT):
        with pytest.raises(Notify):
            decode(nlri(route_type, b''))


def test_an_unknown_route_type_is_kept_whole_rather_than_guessed_at() -> None:
    """Section 7 defines route types 1 to 4 and leaves the rest to IANA.

    An unknown type still has a Length octet, so it can be skipped exactly; exabgp keeps
    the bytes and reports them unparsed rather than dropping the session or trying to
    read a payload it has no diagram for.
    """
    body = bytes.fromhex('deadbeef')
    decoded, remaining = decode(nlri(9, body) + segment_route(IPV4_BITS, IPV4))
    assert isinstance(decoded, GenericEVPN)
    assert decoded.route_code == 9
    assert '"parsed": false' in decoded.json()

    following, rest = decode(remaining)
    assert isinstance(following, EthernetSegment)
    assert rest == b''


def test_an_inclusive_multicast_route_checks_its_ip_length_against_its_size() -> None:
    """Route type 3 carries the same Originating Router's IP Address as route type 4."""
    decoded, remaining = decode(nlri(INCLUSIVE_MULTICAST, RD + ETAG + bytes([IPV4_BITS]) + IPV4))
    assert isinstance(decoded, Multicast)
    assert remaining == b''
    assert str(decoded.ip) == '192.0.2.2'

    with pytest.raises(Notify):
        decode(nlri(INCLUSIVE_MULTICAST, RD + ETAG + bytes([IPV4_BITS]) + IPV6))
