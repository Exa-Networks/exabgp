"""RFC 6514: the MCAST-VPN NLRI and the PMSI Tunnel attribute, read by a speaker with no PE.

Most of RFC 6514 is a set of procedures for a PE or an ASBR building provider tunnels and
multicast forwarding state.  exabgp builds neither, so qa/rfc/rfc6514.toml records those
as not-applicable and this file does not test them.  What is left is the wire: the NLRI
of section 4, which exabgp decodes for route types 5, 6 and 7 and keeps as opaque bytes
for 1 to 4, and the PMSI Tunnel attribute of section 5.

Only two pairs below carry an `rfc()` marker, and the reason is the same one which makes
this RFC awkward: section 4 contains exactly one RFC 2119 keyword in its entirety, and
section 5's format is described with none.  "The Length field indicates the length in
octets of the Route Type specific field" is prose, not a MUST.  So the NLRI tests here
are unmarked.  They are still worth having - a Length octet which disagrees with the
payload is the classic way a peer walks a parser off the end of a buffer, and the test
which proves exabgp raises Notify rather than IndexError is the test which proves the
session ends politely rather than with a traceback.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.pmsi import PMSI
from exabgp.bgp.message.update.nlri.mvpn import MVPN, SourceAD
from exabgp.protocol.family import AFI, SAFI

# RFC 6514 section 5: the PMSI Tunnel attribute is optional transitive, so 0xC0.
OPTIONAL_TRANSITIVE = 0xC0

PMSI_TUNNEL = int(Attribute.CODE.PMSI_TUNNEL)
TREAT_AS_WITHDRAW = int(Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW)

# RFC 6514 section 5: Flags(1) + Tunnel Type(1) + MPLS Label(3) before the identifier.
PMSI_HEADER_SIZE_BYTES = 5

TUNNEL_TYPE_NO_TUNNEL = 0
TUNNEL_TYPE_PIM_SSM = 3
TUNNEL_TYPE_INGRESS_REPLICATION = 6

# RFC 6514 section 4.5: RD(8) + source length(1) + source(4) + group length(1) + group(4)
SOURCE_ACTIVE_IPV4_PAYLOAD_SIZE_BYTES = 18
ROUTE_TYPE_SOURCE_ACTIVE = 5
IPV4_ADDRESS_LENGTH_BITS = 32


def session() -> Any:
    """A negotiated session with the attribute cache off, so tests cannot answer each other."""
    negotiated = Mock()
    negotiated.asn4 = False
    negotiated.families = []
    negotiated.nexthop = []
    negotiated.msg_size = 4096
    negotiated.direction = Action.ANNOUNCE
    negotiated.attribute_cache = None
    negotiated.attribute_cache_packed = b''
    negotiated.attribute_cache_enabled = False
    return negotiated


def pmsi_attribute(value: bytes) -> bytes:
    return bytes([OPTIONAL_TRANSITIVE, PMSI_TUNNEL, len(value)]) + value


def parse_pmsi(value: bytes) -> AttributeCollection:
    return AttributeCollection().parse(pmsi_attribute(value), session())


def withdrawn(collection: AttributeCollection) -> bool:
    return TREAT_AS_WITHDRAW in collection


def pmsi_value(tunnel_type: int, identifier: bytes, flags: int = 0, label: bytes = b'\x00\x00\x00') -> bytes:
    """The attribute value of section 5, built by hand rather than by make_pmsi()."""
    return bytes([flags, tunnel_type]) + label + identifier


def source_active(source: bytes, group: bytes) -> bytes:
    """A route type 5 MCAST-VPN NLRI, header included, with an honest Length octet."""
    payload = bytes(8) + bytes([len(source) * 8]) + source + bytes([len(group) * 8]) + group
    return bytes([ROUTE_TYPE_SOURCE_ACTIVE, len(payload)]) + payload


def unpack(data: bytes) -> tuple[Any, Any]:
    return MVPN.unpack_nlri(AFI.ipv4, SAFI.mcast_vpn, data, Action.ANNOUNCE, False, session())


# ================ section 5, the P-multicast group is per route and not per MVPN


@pytest.mark.rfc('rfc6514#5-p-multicast-group-not-expected-common')
def test_two_pim_ssm_tunnels_differing_only_in_the_group_both_survive() -> None:
    """Two routes of one MVPN may name two groups, so both identifiers must come back."""
    root = bytes([10, 0, 0, 1])
    first = pmsi_value(TUNNEL_TYPE_PIM_SSM, root + bytes([232, 1, 1, 1]))
    second = pmsi_value(TUNNEL_TYPE_PIM_SSM, root + bytes([232, 2, 2, 2]))

    decoded_first = PMSI.unpack_attribute(first, session())
    decoded_second = PMSI.unpack_attribute(second, session())

    assert isinstance(decoded_first, PMSI)
    assert isinstance(decoded_second, PMSI)
    assert bytes(decoded_first.tunnel) == root + bytes([232, 1, 1, 1])
    assert bytes(decoded_second.tunnel) == root + bytes([232, 2, 2, 2])
    assert decoded_first.pack_attribute(session()) == pmsi_attribute(first)
    assert decoded_second.pack_attribute(session()) == pmsi_attribute(second)


@pytest.mark.rfc('rfc6514#5-p-multicast-group-not-expected-common', polarity='negative')
def test_two_pim_ssm_tunnels_differing_only_in_the_group_are_not_equal() -> None:
    """The failure this forbids: treating the group as noise and collapsing the two."""
    root = bytes([10, 0, 0, 1])
    first = PMSI.unpack_attribute(pmsi_value(TUNNEL_TYPE_PIM_SSM, root + bytes([232, 1, 1, 1])), session())
    second = PMSI.unpack_attribute(pmsi_value(TUNNEL_TYPE_PIM_SSM, root + bytes([232, 2, 2, 2])), session())

    assert first != second
    assert not withdrawn(parse_pmsi(pmsi_value(TUNNEL_TYPE_PIM_SSM, root + bytes([232, 2, 2, 2]))))


# ============================ section 5, a malformed PMSI withdraws rather than resets


@pytest.mark.rfc('rfc6514#5-malformed-pmsi-treat-as-withdraw')
@pytest.mark.parametrize('size', [0, 1, 2, 3, 4])
def test_a_pmsi_too_short_for_its_own_header_withdraws_the_update(size: int) -> None:
    """Five octets of fixed header, so anything shorter cannot be read at all."""
    collection = parse_pmsi(bytes(size))

    assert withdrawn(collection)
    assert PMSI_TUNNEL not in collection


@pytest.mark.rfc('rfc6514#5-malformed-pmsi-treat-as-withdraw', polarity='negative')
@pytest.mark.parametrize(
    'value',
    [
        pmsi_value(TUNNEL_TYPE_NO_TUNNEL, b''),
        pmsi_value(TUNNEL_TYPE_NO_TUNNEL, b'', flags=1),
        pmsi_value(TUNNEL_TYPE_INGRESS_REPLICATION, bytes([10, 0, 0, 1])),
        pmsi_value(TUNNEL_TYPE_PIM_SSM, bytes([10, 0, 0, 1, 232, 1, 1, 1])),
    ],
)
def test_a_well_formed_pmsi_is_not_withdrawn(value: bytes) -> None:
    """A decoder which withdrew on everything would pass the positive test above."""
    collection = parse_pmsi(value)

    assert not withdrawn(collection)
    decoded = collection[PMSI_TUNNEL]
    assert isinstance(decoded, PMSI)
    assert decoded.pack_attribute(session()) == pmsi_attribute(value)


# =========================== section 4, the NLRI header RFC 6514 never made normative
#
# No rfc() marker on anything below: section 4 states the Route Type octet, the Length
# octet and every route type encoding in declarative prose.  These test the decoder
# against the diagrams anyway, because a Length octet which disagrees with the buffer is
# how a parser is walked off the end.


def test_a_source_active_route_decodes_into_its_fields() -> None:
    nlri, rest = unpack(source_active(bytes([10, 0, 0, 1]), bytes([239, 1, 1, 1])))

    assert isinstance(nlri, SourceAD)
    assert rest == b''
    assert str(nlri.source) == '10.0.0.1'
    assert str(nlri.group) == '239.1.1.1'


def test_the_length_octet_bounds_the_route_and_the_next_nlri_follows_it() -> None:
    """Two NLRI in one field: the second is only reachable if the first stopped on time."""
    one = source_active(bytes([10, 0, 0, 1]), bytes([239, 1, 1, 1]))
    two = source_active(bytes([10, 0, 0, 2]), bytes([239, 2, 2, 2]))

    first, rest = unpack(one + two)
    assert len(rest) == len(two)

    second, tail = unpack(bytes(rest))
    assert tail == b''
    assert str(first.source) == '10.0.0.1'
    assert str(second.source) == '10.0.0.2'


@pytest.mark.parametrize(
    'data',
    [
        b'',
        bytes([ROUTE_TYPE_SOURCE_ACTIVE]),
    ],
)
def test_an_nlri_too_short_for_the_two_octet_header_raises_notify(data: bytes) -> None:
    with pytest.raises(Notify):
        unpack(data)


def test_a_length_octet_larger_than_the_payload_raises_notify() -> None:
    """The Length says 18, eighteen octets are not there, and the parser must say so."""
    truncated = source_active(bytes([10, 0, 0, 1]), bytes([239, 1, 1, 1]))[:-1]
    assert truncated[1] == SOURCE_ACTIVE_IPV4_PAYLOAD_SIZE_BYTES

    with pytest.raises(Notify):
        unpack(truncated)


@pytest.mark.parametrize('length', [0, 3, 9, 17])
def test_a_source_active_payload_too_short_for_its_fixed_fields_raises_notify(length: int) -> None:
    with pytest.raises(Notify):
        unpack(bytes([ROUTE_TYPE_SOURCE_ACTIVE, length]) + bytes(length))


def source_active_with_source_length(bits: int) -> bytes:
    """A route type 5 NLRI whose payload is IPv4 sized whatever the length octet claims."""
    payload = bytes(8) + bytes([bits]) + bytes(4) + bytes([IPV4_ADDRESS_LENGTH_BITS]) + bytes(4)
    return bytes([ROUTE_TYPE_SOURCE_ACTIVE, len(payload)]) + payload


@pytest.mark.parametrize('bits', [0, 8, 31, 64, 127, 255])
def test_a_multicast_source_length_which_is_neither_32_nor_128_raises_notify(bits: int) -> None:
    """Section 4.5 gives 32 for IPv4 and 128 for IPv6 and puts everything else out of scope."""
    with pytest.raises(Notify):
        unpack(source_active_with_source_length(bits))


@pytest.mark.parametrize('bits', [33, 39])
def test_a_multicast_source_length_just_above_32_is_not_accepted_as_ipv4(bits: int) -> None:
    """The length octet is compared against 32 and 128, not its quotient by eight.

    A quotient read 33 to 39 as four octets and decoded the route as though the peer had
    written 32, so the address reported to the API was one the peer never sent.
    """
    with pytest.raises(Notify):
        unpack(source_active_with_source_length(bits))


@pytest.mark.parametrize('bits', [129, 135])
def test_a_multicast_source_length_just_above_128_does_not_run_off_the_buffer(bits: int) -> None:
    """The worst of the two: a Python exception where a peer should get a NOTIFICATION.

    `int(129 / 8)` was 16, so the IPv6 arm of the length check passed, the cursor moved
    sixteen octets into an eighteen octet payload and `packed[cursor]` raised IndexError.
    `AttributeCollection` catches Notify and ValueError around NLRI parsing, not
    IndexError, so two octets from a peer left the decoder as an unhandled exception.
    """
    with pytest.raises(Notify):
        unpack(source_active_with_source_length(bits))


ROUTE_TYPE_SHARED_JOIN = 6
ROUTE_TYPE_SOURCE_JOIN = 7
C_MULTICAST_IPV4_PAYLOAD_SIZE_BYTES = 22


def c_multicast_with_source_length(route_type: int, bits: int) -> bytes:
    """A route type 6 or 7 NLRI: RD(8) + Source AS(4) then the two addresses."""
    payload = bytes(12) + bytes([bits]) + bytes(4) + bytes([IPV4_ADDRESS_LENGTH_BITS]) + bytes(4)
    assert len(payload) == C_MULTICAST_IPV4_PAYLOAD_SIZE_BYTES
    return bytes([route_type, len(payload)]) + payload


@pytest.mark.parametrize('route_type', [ROUTE_TYPE_SHARED_JOIN, ROUTE_TYPE_SOURCE_JOIN])
@pytest.mark.parametrize('bits', [33, 39, 129, 135])
def test_the_c_multicast_routes_share_the_source_length_check(route_type: int, bits: int) -> None:
    """The Join route types carry the same two length octets, four bytes further in.

    They had the same quotient comparison, so the same 129 which walked a Source Active
    route off the end of its buffer walked these off theirs.
    """
    with pytest.raises(Notify):
        unpack(c_multicast_with_source_length(route_type, bits))


@pytest.mark.parametrize('route_type', [ROUTE_TYPE_SHARED_JOIN, ROUTE_TYPE_SOURCE_JOIN])
def test_a_well_formed_c_multicast_route_still_decodes(route_type: int) -> None:
    """A check which refused everything would pass the test above and break the family."""
    nlri, rest = unpack(c_multicast_with_source_length(route_type, IPV4_ADDRESS_LENGTH_BITS))

    assert rest == b''
    assert str(nlri.source) == '0.0.0.0'
    assert str(nlri.group) == '0.0.0.0'


@pytest.mark.parametrize('route_type', [1, 2, 3, 4, 8, 127, 255])
def test_an_unimplemented_or_unknown_route_type_is_kept_as_opaque_bytes(route_type: int) -> None:
    """Types 1 to 4 are real and unimplemented, the rest are not allocated: same handling.

    Keeping the bytes is the right answer for both.  A route type exabgp cannot parse is
    not a malformed one, and reporting it as hex lets the operator see what arrived.
    """
    payload = bytes(range(8))
    nlri, rest = unpack(bytes([route_type, len(payload)]) + payload)

    assert rest == b''
    assert nlri.route_code == route_type
    assert payload.hex() in str(nlri).lower()
