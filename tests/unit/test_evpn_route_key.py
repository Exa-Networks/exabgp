"""The EVPN route key is the fields RFC 7432 section 7 names, not the whole NLRI.

RFC 7432 7.1, 7.2 and 7.4 say which fields "are considered to be part of the prefix in
the NLRI" for BGP route key processing, and that the MPLS labels and, for a MAC/IP route,
the ESI "are to be treated as route attributes as opposed to being part of the route".
The sentences carry no RFC 2119 keyword, so they are not on the ledger.

`index()` was the whole NLRI, so a MAC/IP route re-announced with a new label sat next to
the old one in the RIB instead of replacing it, and a withdraw carrying another label
removed nothing. The Ethernet A-D and Ethernet Segment routes went the other way: their
`__eq__` and `__hash__` left the ESI out, where it is part of their key, so two routes
for two segments compared equal.

The MAC/IP route also lost its MPLS Label2 on the way to JSON and to text, and printed
every MAC with a /48 behind it.
"""

from __future__ import annotations

import json

from exabgp.bgp.message import Action
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.protocol.family import AFI, SAFI

RD = bytes.fromhex('0001c000020104d2')
ESI = bytes.fromhex('01001122334455667788')
ESI_OTHER = bytes.fromhex('03aabbccddeeff010203')
ETAG = bytes.fromhex('0000007b')
MAC_ADDRESS = bytes.fromhex('001122334455')
IPV4 = bytes.fromhex('c0000202')


def label(value: int) -> bytes:
    return ((value << 4) | 1).to_bytes(3, 'big')


def decode(route_type: int, payload: bytes) -> EVPN:
    data = bytes([route_type, len(payload)]) + payload
    nlri, rest = EVPN.unpack_nlri(AFI.l2vpn, SAFI.evpn, data, Action.ANNOUNCE, False, Negotiated.UNSET)
    assert bytes(rest) == b''
    assert isinstance(nlri, EVPN)
    return nlri


def ad(esi: bytes, labels: bytes) -> EVPN:
    return decode(1, RD + esi + ETAG + labels)


def mac(esi: bytes, labels: bytes) -> EVPN:
    return decode(2, RD + esi + ETAG + bytes([48]) + MAC_ADDRESS + bytes([32]) + IPV4 + labels)


def segment(esi: bytes) -> EVPN:
    return decode(4, RD + esi + bytes([32]) + IPV4)


def same_route(first: EVPN, second: EVPN) -> bool:
    together = first.index() == second.index()
    assert together == (first == second), 'index() and __eq__ disagree'
    if together:
        assert hash(first) == hash(second), 'equal routes hash apart'
    return together


def test_a_mac_ip_route_with_another_label_or_esi_is_the_same_route() -> None:
    assert same_route(mac(ESI, label(100)), mac(ESI, label(200)))
    assert same_route(mac(ESI, label(100)), mac(ESI_OTHER, label(100)))
    assert same_route(mac(ESI, label(100)), mac(ESI, label(100) + label(300)))


def test_a_mac_ip_route_for_another_mac_is_another_route() -> None:
    other = decode(2, RD + ESI + ETAG + bytes([48]) + bytes(6) + bytes([32]) + IPV4 + label(100))
    assert not same_route(mac(ESI, label(100)), other)


def test_an_ethernet_ad_route_with_another_label_is_the_same_route() -> None:
    assert same_route(ad(ESI, label(100)), ad(ESI, label(200)))


def test_an_ethernet_ad_route_for_another_segment_is_another_route() -> None:
    assert not same_route(ad(ESI, label(100)), ad(ESI_OTHER, label(100)))


def test_an_ethernet_segment_route_for_another_segment_is_another_route() -> None:
    assert not same_route(segment(ESI), segment(ESI_OTHER))


def test_a_mac_ip_route_shows_both_its_labels() -> None:
    route = mac(ESI, label(100) + label(300))
    assert json.loads(route.json())['label'] == [[100, 1601], [300, 4801]]
    assert '300' in str(route)


def test_a_mac_ip_route_does_not_print_a_prefix_length_on_its_mac() -> None:
    assert '/48' not in str(mac(ESI, label(100)))
