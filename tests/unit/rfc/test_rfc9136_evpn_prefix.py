"""RFC 9136: the EVPN IP Prefix route (route type 5), as a peer sends it.

Everything drives `EVPN.unpack_nlri`, the entry point the reactor uses, on bytes built
here from the section 3.1 diagrams.
"""

from __future__ import annotations

from typing import cast

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message.update.nlri.evpn.prefix import Prefix
from exabgp.protocol.family import AFI, SAFI

IP_PREFIX_ROUTE = 5

RD = bytes.fromhex('0001c000020104d2')
ESI = bytes.fromhex('01001122334455667788')
ESI_OTHER = bytes.fromhex('03aabbccddeeff010203')
ETAG = bytes.fromhex('0000007b')
LABEL = bytes.fromhex('000641')
LABEL_OTHER = bytes.fromhex('000c81')
IPV4 = bytes.fromhex('c0000200')
IPV4_GATEWAY = bytes.fromhex('c0000201')
IPV6 = bytes.fromhex('20010db8' + '00' * 12)
IPV6_GATEWAY = bytes.fromhex('20010db8' + '00' * 11 + '01')


def route(
    iplen: int,
    ip: bytes = IPV4,
    gateway: bytes = IPV4_GATEWAY,
    esi: bytes = ESI,
    label: bytes = LABEL,
) -> bytes:
    payload = RD + esi + ETAG + bytes([iplen]) + ip + gateway + label
    return bytes([IP_PREFIX_ROUTE, len(payload)]) + payload


def decode(data: bytes) -> EVPN:
    nlri, rest = EVPN.unpack_nlri(AFI.l2vpn, SAFI.evpn, data, Action.ANNOUNCE, False, Negotiated.UNSET)
    assert bytes(rest) == b''
    assert isinstance(nlri, EVPN)
    return nlri


@pytest.mark.rfc('rfc9136#3.1-length-34-or-58')
@pytest.mark.parametrize('ip,gateway', [(IPV4, IPV4_GATEWAY), (IPV6, IPV6_GATEWAY)])
def test_an_ip_prefix_route_of_34_or_58_octets_decodes(ip: bytes, gateway: bytes) -> None:
    assert len(route(24, ip, gateway)) - 2 in (34, 58)
    decode(route(24, ip, gateway))


@pytest.mark.rfc('rfc9136#3.1-length-34-or-58', polarity='negative')
def test_an_ip_prefix_route_of_another_length_is_refused() -> None:
    with pytest.raises(Notify):
        decode(route(24, IPV4, IPV4_GATEWAY + b'\x00'))


@pytest.mark.rfc('rfc9136#3.1-prefix-and-gateway-same-family')
def test_the_gateway_of_an_ipv6_route_is_read_as_ipv6() -> None:
    decoded = decode(route(32, IPV6, IPV6_GATEWAY))
    assert str(cast(Prefix, decoded).gwip) == '2001:db8::1'


@pytest.mark.rfc('rfc9136#3.1-prefix-length-not-above-128')
@pytest.mark.parametrize(
    'ip,gateway,iplen', [(IPV4, IPV4_GATEWAY, 0), (IPV4, IPV4_GATEWAY, 32), (IPV6, IPV6_GATEWAY, 128)]
)
def test_a_prefix_length_the_address_holds_is_accepted(ip: bytes, gateway: bytes, iplen: int) -> None:
    assert f'/{iplen}' in str(decode(route(iplen, ip, gateway)))


@pytest.mark.rfc('rfc9136#3.1-prefix-length-not-above-128', polarity='negative')
@pytest.mark.parametrize(
    'ip,gateway,iplen', [(IPV4, IPV4_GATEWAY, 33), (IPV4, IPV4_GATEWAY, 200), (IPV6, IPV6_GATEWAY, 129)]
)
def test_a_prefix_length_longer_than_the_address_is_refused(ip: bytes, gateway: bytes, iplen: int) -> None:
    with pytest.raises(Notify):
        decode(route(iplen, ip, gateway))


def test_the_esi_gateway_and_label_are_not_part_of_the_route_key() -> None:
    """Section 3.1: "The rest of the fields are not part of the route key"."""
    first = decode(route(24))
    for other in (
        decode(route(24, esi=ESI_OTHER)),
        decode(route(24, gateway=bytes(4))),
        decode(route(24, label=LABEL_OTHER)),
    ):
        assert other.index() == first.index()
        assert other == first
        assert hash(other) == hash(first)


def test_the_prefix_and_its_length_are_part_of_the_route_key() -> None:
    assert decode(route(24)).index() != decode(route(25)).index()
    assert decode(route(24)) != decode(route(24, ip=bytes.fromhex('c0000300')))
