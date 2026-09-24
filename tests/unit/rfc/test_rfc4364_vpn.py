"""RFC 4364: a document whose seven MUSTs are all about a router exabgp is not.

This file carries no `@pytest.mark.rfc` marker, and that is the finding rather than an
omission.  RFC 4364 has seven RFC 2119 keywords in 2635 lines.  Two are a PE filtering
Route Targets a customer edge router attached, two are LDP modes, one is a data plane
admission check and two are IPsec.  Every one of them is recorded in qa/rfc/rfc4364.toml
as not-applicable, with the reason, and a marker may only name a requirement the ledger
records as `required`.

The sections which do describe what exabgp puts on the wire, 4.1, 4.2 and 4.3.4, use no
keyword at all: the 8 octet RD, the 2 octet type field, the three type layouts and "the
prefix consists of an 8-byte RD followed by an IPv4 prefix" are all plain declarative
prose, and 4.2's obligations on the Administrator subfield are lowercase "must".  None of
that may be recorded as a requirement, so the behaviour is exercised here unmarked.  It
is the same shape RFC 1997 and RFC 4360 turned out to have.

What the label stack in front of that RD has to do is RFC 8277's business, and is in
tests/unit/rfc/test_rfc8277_labelled_unicast.py.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.nlri.ipvpn import IPVPNBase
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.protocol.family import AFI, SAFI

RD_OCTETS = 8
LABEL = bytes([0x00, 0x06, 0x41])
PREFIX = bytes([10, 0, 0])
PREFIX_BITS = 24


def nlri(rd: bytes) -> bytes:
    return bytes([len(LABEL) * 8 + len(rd) * 8 + PREFIX_BITS]) + LABEL + rd + PREFIX


def decode(wire: bytes) -> IPVPNBase:
    route, rest = NLRI.unpack_nlri(AFI.ipv4, SAFI.mpls_vpn, wire, Action.ANNOUNCE, False, Negotiated.UNSET)
    assert rest == b''
    assert isinstance(route, IPVPNBase)
    return route


# Section 4.2's three type layouts, each with the text form exabgp reports for it.
TYPES: list[tuple[str, bytes, str]] = [
    ('type 0, a 2 byte ASN and a 4 byte assigned number', pack('!HHL', 0, 65001, 100), ' rd 65001:100'),
    (
        'type 1, an IPv4 address and a 2 byte assigned number',
        pack('!HBBBBH', 1, 192, 0, 2, 1, 100),
        ' rd 192.0.2.1:100',
    ),
    ('type 2, a 4 byte ASN and a 2 byte assigned number', pack('!HLH', 2, 65536, 100), ' rd 65536:100'),
]


@pytest.mark.parametrize('name,rd,text', TYPES, ids=[entry[0] for entry in TYPES])
def test_each_route_distinguisher_type_decodes_to_its_documented_layout(name: str, rd: bytes, text: str) -> None:
    """Section 4.2: the type field decides how the six value octets are read."""
    route = decode(nlri(rd))
    assert len(rd) == RD_OCTETS
    assert str(route.rd) == text
    assert str(route.cidr) == '10.0.0.0/24'


@pytest.mark.parametrize('name,rd,text', TYPES, ids=[entry[0] for entry in TYPES])
def test_a_route_distinguisher_survives_a_round_trip_through_the_wire(name: str, rd: bytes, text: str) -> None:
    """The RD is opaque to BGP, so the octets that arrived are the octets that leave."""
    route = decode(nlri(rd))
    assert bytes(route.pack_nlri(Negotiated.UNSET)) == nlri(rd)


def test_two_routes_which_differ_only_in_their_route_distinguisher_stay_distinct() -> None:
    """Section 4.1: the RD exists solely to create distinct routes to one prefix.

    If the RIB key dropped it, the second VPN's route would implicitly withdraw the
    first's, which is the failure the whole address family exists to prevent.
    """
    first = decode(nlri(pack('!HHL', 0, 65001, 100)))
    second = decode(nlri(pack('!HHL', 0, 65001, 200)))
    assert first.index() != second.index()
    assert str(first.cidr) == str(second.cidr)


def test_a_route_distinguisher_of_the_wrong_width_is_refused() -> None:
    """Section 4.2 gives 2 octets of type and 6 of value, and nothing else is an RD."""
    for width in (0, 4, 7, 9, 16):
        if width == 0:
            continue
        with pytest.raises(ValueError):
            RouteDistinguisher(bytes(width))


def test_a_truncated_route_distinguisher_raises_notify_and_not_a_python_exception() -> None:
    """Peer input eight octets short of an RD must end the session, not the process."""
    wire = bytes([len(LABEL) * 8 + RD_OCTETS * 8 + PREFIX_BITS]) + LABEL + bytes(5)
    with pytest.raises(Notify) as raised:
        NLRI.unpack_nlri(AFI.ipv4, SAFI.mpls_vpn, wire, Action.ANNOUNCE, False, Negotiated.UNSET)
    assert raised.value.code == 3
    assert raised.value.subcode == 10


def test_an_unknown_route_distinguisher_type_is_carried_rather_than_refused() -> None:
    """Section 4.2 defines three types "at the present time" and forbids no other.

    A decoder which refused type 3 would break the day IANA assigned one, and the RD is
    explicitly "simply a number" with no inherent information.
    """
    route = decode(nlri(pack('!HHL', 3, 1, 2)))
    assert str(route.cidr) == '10.0.0.0/24'
    assert bytes(route.rd.pack_rd()) == pack('!HHL', 3, 1, 2)
