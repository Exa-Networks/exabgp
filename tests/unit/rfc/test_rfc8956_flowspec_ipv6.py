"""RFC 8956, Dissemination of Flow Specification Rules for IPv6.

The ledger these tests are joined to is qa/rfc/rfc8956.toml.  The operators, the error
handling and the component types RFC 8956 does not redefine belong to RFC 8955 and are
tested in tests/unit/rfc/test_rfc8955_flowspec.py.

What is new here is the offset octet in the type 1 and type 2 prefix components, and it
is where exabgp is furthest from the document.  The two tests at the top carry `xfail`
with no `rfc()` marker because the sentence they break, that the pattern holds
length-minus-offset bits, is stated without an RFC 2119 keyword and so may not be
recorded as a requirement.  They are first anyway: they are the reason an IPv6 flow
specification from a conforming router does not decode.
"""

from __future__ import annotations

from socket import AF_INET6, inet_pton
from struct import pack

import pytest

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open import ASN, HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.nlri.flow import (
    BinaryOperator,
    Flow,
    Flow6Destination,
    Flow6Source,
    FlowFragment,
    FlowICMPCode,
    FlowICMPType,
    FlowNextHeader,
    NumericOperator,
)
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.neighbor import Neighbor
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.protocol.ip.fragment import Fragment
from exabgp.protocol.resource import NumericValue

IPV4_FLOW: FamilyTuple = (AFI.ipv4, SAFI.flow_ip)
IPV6_FLOW: FamilyTuple = (AFI.ipv6, SAFI.flow_ip)

EOL = 0x80
LEN_ONE = 0x00

# RFC 8956 section 3.8.1, Example 1: from ::1234:5678:9a00:0/64-104 to 2001:db8::/32 and
# upper-layer protocol tcp.  Copied out of Table 1 of the document.
EXAMPLE_ONE_DESTINATION = bytes([0x01, 0x20, 0x00, 0x20, 0x01, 0x0D, 0xB8])
EXAMPLE_ONE_SOURCE = bytes([0x02, 0x68, 0x40, 0x12, 0x34, 0x56, 0x78, 0x9A])
EXAMPLE_ONE_PROTOCOL = bytes([0x03, 0x81, 0x06])


def decoded(components: bytes, afi: AFI = AFI.ipv6) -> Flow | None:
    """The real decoder, with `NLRI.INVALID` reported as None rather than as an object."""
    payload = bytes([len(components)]) + components
    flow, over = Flow.unpack_nlri(afi, SAFI.flow_ip, payload, Action.ANNOUNCE, False, Negotiated.UNSET)
    assert over == b'', 'the whole NLRI should have been consumed'
    if flow is NLRI.INVALID:
        return None
    assert isinstance(flow, Flow), f'the decoder returned a {type(flow).__name__}'
    return flow


def session(families: list[FamilyTuple]) -> Negotiated:
    """A negotiated session where both ends advertised exactly these families."""
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(65001)
    sent = Capabilities()
    received = Capabilities()
    for capabilities in (sent, received):
        multiprotocol = MultiProtocol()
        multiprotocol.extend(families)
        capabilities[Capability.CODE.MULTIPROTOCOL] = multiprotocol
    negotiated = Negotiated(neighbor, Direction.IN)
    negotiated.sent(Open.make_open(Version(4), ASN(65001), HoldTime(90), RouterID('192.0.2.1'), sent))
    negotiated.received(Open.make_open(Version(4), ASN(65002), HoldTime(90), RouterID('192.0.2.2'), received))
    return negotiated


def mp_reach(afi: int, safi: int, payload: bytes) -> bytes:
    """The MP_REACH_NLRI attribute value with the zero length next hop section 4 wants."""
    return pack('!HB', afi, safi) + bytes([0]) + bytes([0]) + payload


def prefix_component(component_id: int, length: int, offset: int, pattern: bytes) -> bytes:
    """A type 1 or type 2 component written the way section 3.1 lays it out."""
    return bytes([component_id, length, offset]) + pattern


# ==================================================== the offset, section 3.1


@pytest.mark.xfail(
    strict=True,
    reason='IPrefix6.make hands bgp[0:1] + bgp[2:] to CIDR.from_ipv6, which sizes the '
    'pattern from the mask alone: it reads ceil(length / 8) octets where RFC 8956 writes '
    'ceil((length - offset) / 8), runs off the end of the NLRI and returns NLRI.INVALID',
)
def test_the_rfcs_own_first_example_decodes() -> None:
    """Section 3.8.1, copied byte for byte out of Table 1 of the document.

    The source component says length 104, offset 64, so the pattern is the 40 bits
    between them: five octets, `12 34 56 78 9a`.  exabgp reads thirteen, which is
    ceil(104 / 8), eats the type 3 component behind it and then runs out of NLRI.  Any
    IPv6 flow specification with a non-zero offset is unreadable, and since
    `IPrefix6.pack` writes the pattern back the same way, the ones exabgp sends are
    unreadable to everyone else.
    """
    flow = decoded(EXAMPLE_ONE_DESTINATION + EXAMPLE_ONE_SOURCE + EXAMPLE_ONE_PROTOCOL)

    assert flow is not None


@pytest.mark.xfail(
    strict=True,
    reason='IPrefix6.pack writes cidr.pack_ip(), which is ceil(length / 8) octets of the '
    'unshifted address, so a /64-104 goes out as thirteen pattern octets where RFC 8956 '
    'section 3.8.1 writes five',
)
def test_a_prefix_with_an_offset_is_encoded_with_length_minus_offset_bits() -> None:
    """The encoder half of the same fault, checked against the RFC's own Table 1."""
    raw = inet_pton(AF_INET6, '::1234:5678:9a00:0')

    packed = bytes(Flow6Source.make_prefix6(raw, 104, 64).pack())

    assert packed == EXAMPLE_ONE_SOURCE


def test_a_prefix_with_no_offset_decodes() -> None:
    """The case which does work, so the two xfails above are about the offset and
    nothing else."""
    flow = decoded(EXAMPLE_ONE_DESTINATION)

    assert flow is not None
    assert str(flow) == 'flow destination-ipv6 2001:db8::/32/0'


# ==================================================== section 2, the capability


@pytest.mark.rfc('rfc8956#2-capability-multiprotocol')
def test_the_ipv6_flow_specification_families_negotiate() -> None:
    negotiated = session([IPV6_FLOW, (AFI.ipv6, SAFI.flow_vpn)])

    assert int(AFI.ipv6) == 2
    assert int(SAFI.flow_ip) == 133
    assert int(SAFI.flow_vpn) == 134
    assert IPV6_FLOW in negotiated.families
    assert (AFI.ipv6, SAFI.flow_vpn) in negotiated.families


@pytest.mark.rfc('rfc8956#2-capability-multiprotocol', polarity='negative')
def test_an_ipv4_flow_session_does_not_carry_ipv6_flow_specifications() -> None:
    """The capability is per (AFI, SAFI), so 1/133 does not let 2/133 through."""
    negotiated = session([IPV4_FLOW])
    payload = bytes([len(EXAMPLE_ONE_DESTINATION)]) + EXAMPLE_ONE_DESTINATION

    with pytest.raises(Notify):
        MPRNLRI.unpack_attribute(mp_reach(2, 133, payload), negotiated)


# ==================================================== section 3.1, padding and length


@pytest.mark.rfc('rfc8956#3.1-padding-bits-zero')
@pytest.mark.parametrize('length', [33, 34, 47, 65])
def test_the_padding_of_a_prefix_we_encode_is_zero(length: int) -> None:
    """A length which is not a multiple of eight leaves padding in the last octet."""
    raw = inet_pton(AF_INET6, '2001:db8::')

    packed = bytes(Flow6Destination.make_prefix6(raw, length, 0).pack())
    last = packed[-1]
    spare = 8 - (length % 8)

    assert not last & ((1 << spare) - 1), f'/{length} left {last:#04x} in its last octet'


@pytest.mark.rfc('rfc8956#3.1-padding-bits-zero', polarity='negative')
@pytest.mark.xfail(
    strict=True,
    reason='CIDR.decode keeps the last octet exactly as it arrived, so the padding is '
    'published rather than ignored: a /33 padded with 0xFF is reported as '
    '2001:db8:ff00::/33 instead of 2001:db8:8000::/33',
)
def test_padding_set_by_a_peer_is_ignored_on_decoding() -> None:
    """Two components describing the same match must decode to the same thing.

    They do not: the padding reaches the CIDR, so the NLRI exabgp reports, and the index
    it hashes into the RIB, both depend on bits the sender was told to leave alone.
    """
    clean = decoded(prefix_component(1, 33, 0, bytes([0x20, 0x01, 0x0D, 0xB8, 0x80])))
    padded = decoded(prefix_component(1, 33, 0, bytes([0x20, 0x01, 0x0D, 0xB8, 0xFF])))

    assert clean is not None and padded is not None
    assert str(padded) == str(clean)


@pytest.mark.rfc('rfc8956#3.1-length-range')
def test_a_length_of_zero_with_an_offset_of_zero_matches_every_address() -> None:
    flow = decoded(prefix_component(1, 0, 0, b''))

    assert flow is not None
    assert str(flow) == 'flow destination-ipv6 ::/0/0'


@pytest.mark.rfc('rfc8956#3.1-length-range', polarity='negative')
@pytest.mark.xfail(
    strict=True,
    reason='the length < 129 end is enforced by CIDR.decode, but nothing compares the '
    'offset to the length: IPrefix6.make reads the offset octet and stores it, so '
    'length 32 with offset 64 is accepted and rendered as 2001:db8::/32/64',
)
def test_a_length_outside_the_range_the_offset_allows_is_refused() -> None:
    """Both ends of "offset < length < 129" in one test, because only one end holds.

    Splitting them would let the half exabgp does enforce report the requirement as
    proven while a component describing a match on bits 64 through 32, which do not
    exist, is still accepted from any peer.
    """
    assert decoded(prefix_component(1, 129, 0, bytes(17))) is None
    assert decoded(prefix_component(1, 32, 64, bytes([0x20, 0x01, 0x0D, 0xB8]))) is None


# ==================================================== section 3.3 to 3.5, component widths


@pytest.mark.rfc('rfc8956#3.3-upper-layer-protocol-single-octet')
@pytest.mark.parametrize('value', [0, 6, 17, 58, 255])
def test_every_upper_layer_protocol_we_encode_uses_a_single_octet(value: int) -> None:
    packed = bytes(FlowNextHeader(NumericOperator.EQ, NumericValue(value)).pack())

    assert packed[0] & 0x30 == LEN_ONE
    assert len(packed) == 2


@pytest.mark.rfc('rfc8956#3.3-upper-layer-protocol-single-octet', polarity='negative')
def test_an_upper_layer_protocol_which_would_not_fit_one_octet_cannot_be_encoded() -> None:
    """`IOperationByte.encode` is `bytes([value])`, which has no wider branch to take."""
    with pytest.raises(ValueError):
        FlowNextHeader(NumericOperator.EQ, NumericValue(256)).pack()


@pytest.mark.rfc('rfc8956#3.4-icmpv6-type-single-octet')
@pytest.mark.parametrize('value', [1, 128, 135, 255])
def test_every_icmpv6_type_we_encode_uses_a_single_octet(value: int) -> None:
    packed = bytes(FlowICMPType(NumericOperator.EQ, NumericValue(value)).pack())

    assert packed[0] & 0x30 == LEN_ONE
    assert len(packed) == 2


@pytest.mark.rfc('rfc8956#3.4-icmpv6-type-single-octet', polarity='negative')
def test_an_icmpv6_type_which_would_not_fit_one_octet_cannot_be_encoded() -> None:
    with pytest.raises(ValueError):
        FlowICMPType(NumericOperator.EQ, NumericValue(256)).pack()


@pytest.mark.rfc('rfc8956#3.5-icmpv6-code-single-octet')
@pytest.mark.parametrize('value', [0, 3, 255])
def test_every_icmpv6_code_we_encode_uses_a_single_octet(value: int) -> None:
    packed = bytes(FlowICMPCode(NumericOperator.EQ, NumericValue(value)).pack())

    assert packed[0] & 0x30 == LEN_ONE
    assert len(packed) == 2


@pytest.mark.rfc('rfc8956#3.5-icmpv6-code-single-octet', polarity='negative')
def test_an_icmpv6_code_which_would_not_fit_one_octet_cannot_be_encoded() -> None:
    with pytest.raises(ValueError):
        FlowICMPCode(NumericOperator.EQ, NumericValue(256)).pack()


# ==================================================== section 3.6, the fragment bitmask


@pytest.mark.rfc('rfc8956#3.6-fragment-single-octet')
@pytest.mark.parametrize('name', sorted(Fragment.codes))
def test_every_ipv6_fragment_bitmask_we_encode_uses_a_single_octet(name: str) -> None:
    packed = bytes(FlowFragment(BinaryOperator.MATCH, Fragment.named(name)).pack())

    assert packed[0] & 0x30 == LEN_ONE
    assert len(packed) == 2


@pytest.mark.rfc('rfc8956#3.6-fragment-single-octet', polarity='negative')
def test_an_ipv6_fragment_component_of_two_octets_is_not_what_we_generate() -> None:
    """`FlowFragment` is an `IOperationByteShort` and would widen above 255.

    The class does not state the single octet rule, so what keeps exabgp inside it is
    that every name `Fragment` defines is 0x0F or below.
    """
    assert max(Fragment.codes.values()) <= 0x0F
    with pytest.raises(ValueError):
        Fragment.named('reassembled')


@pytest.mark.rfc('rfc8956#3.6-fragment-reserved-bits-zero')
@pytest.mark.parametrize('name', sorted(Fragment.codes))
def test_the_four_high_bits_of_an_ipv6_fragment_bitmask_we_encode_are_zero(name: str) -> None:
    """The four bits both families reserve.  Bit 7 is the one only IPv6 reserves and it
    is checked by the test below, which fails."""
    packed = bytes(FlowFragment(BinaryOperator.MATCH, Fragment.named(name)).pack())

    assert not packed[1] & 0xF0


@pytest.mark.rfc('rfc8956#3.6-fragment-reserved-bits-zero', polarity='negative')
@pytest.mark.xfail(
    strict=True,
    reason='one Fragment class serves both families and defines dont-fragment at 0x01 '
    'unconditionally, so the bit RFC 8956 reserves is decoded for AFI 2 as a match on a '
    'header field IPv6 does not have and is reported as "fragment =dont-fragment"',
)
def test_the_reserved_bits_of_an_ipv6_fragment_bitmask_are_ignored_on_decoding() -> None:
    """RFC 8955 gives bit 7 to Don't Fragment; RFC 8956 figure 1 makes it a reserved 0.

    IPv6 has no DF bit, so a peer setting it has said nothing, and exabgp must report
    nothing.  It reports a filter instead.
    """
    nothing = decoded(bytes([0x0C, EOL | BinaryOperator.MATCH, 0x00]))
    reserved = decoded(bytes([0x0C, EOL | BinaryOperator.MATCH, 0x01]))

    assert nothing is not None and reserved is not None
    assert str(reserved) == str(nothing)
