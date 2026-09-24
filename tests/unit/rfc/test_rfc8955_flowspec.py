"""RFC 8955, Dissemination of Flow Specification Rules.

The ledger these tests are joined to is qa/rfc/rfc8955.toml.

FlowSpec is the most intricate thing exabgp decodes: a length field with two encodings, a
list of components which must arrive in a particular order, and inside most of them a
list of {operator, value} pairs where the operator octet says how many bytes of value
follow it.  Every one of those is a chance for a decoder to read past the end of its
buffer or to accept a filter the sender did not write, so the negative tests here feed
real malformed bytes to the real `Flow.unpack_nlri` and look at what comes back.

Three tests carry `xfail` without an `rfc()` marker.  That is not an oversight: the rule
they break is stated in RFC 8955 without an RFC 2119 keyword, so it may not be recorded
as a requirement, and a test is the only place left to put it.  The first of them is the
worst bug in this file's subject matter and is at the top for that reason.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open import ASN, HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute.community.extended.traffic import (
    TrafficAction,
    TrafficMark,
    TrafficRate,
    TrafficRatePackets,
)
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.message.update.nlri.collection import MPNLRICollection
from exabgp.bgp.message.update.nlri.flow import (
    BinaryOperator,
    Flow,
    Flow4Destination,
    FlowDestinationPort,
    FlowDSCP,
    FlowFragment,
    FlowTCPFlag,
    NumericOperator,
    dscp_value,
)
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.neighbor import Neighbor
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.protocol.ip import IP
from exabgp.protocol.ip.fragment import Fragment
from exabgp.protocol.ip.tcp.flag import TCPFlag
from exabgp.protocol.resource import NumericValue

IPV4_UNICAST: FamilyTuple = (AFI.ipv4, SAFI.unicast)
IPV4_FLOW: FamilyTuple = (AFI.ipv4, SAFI.flow_ip)

# RFC 8955 section 4.3.1, "all packets to 192.0.2.0/24 and TCP port 25", component by
# component so a test can reorder or duplicate one of them.
DESTINATION = bytes([0x01, 0x18, 0xC0, 0x00, 0x02])
PROTOCOL_TCP = bytes([0x03, 0x81, 0x06])
PORT_25 = bytes([0x04, 0x81, 0x19])

# the operator bits this document names, so a test reads as the RFC's figure does
EOL = 0x80
AND = 0x40
LEN_ONE = 0x00
LEN_TWO = 0x10
NUMERIC_RESERVED = 0x08
BITMASK_RESERVED = 0x0C

MAX_COMPACT_LENGTH = 239  # the largest length the one octet form can hold


def nlri(components: bytes) -> bytes:
    """One FlowSpec NLRI: the one octet length form of section 4.1, then the components."""
    assert len(components) <= MAX_COMPACT_LENGTH, 'this helper only writes the compact length'
    return bytes([len(components)]) + components


def decoded(afi: AFI, components: bytes, safi: SAFI = SAFI.flow_ip) -> Flow | None:
    """The real decoder, with `NLRI.INVALID` reported as None rather than as an object."""
    flow, over = Flow.unpack_nlri(afi, safi, nlri(components), Action.ANNOUNCE, False, Negotiated.UNSET)
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


def mp_reach(afi: int, safi: int, nexthop: bytes, payload: bytes) -> bytes:
    """The MP_REACH_NLRI attribute value, as RFC 4760 section 3 lays it out."""
    return pack('!HB', afi, safi) + bytes([len(nexthop)]) + nexthop + bytes([0]) + payload


def flow_to(destination: bytes = DESTINATION) -> Flow:
    """A Flow built the way the configuration builds one, matching 192.0.2.0/24."""
    built = Flow.make_flow(AFI.ipv4, SAFI.flow_ip)
    built.add(Flow4Destination(destination[1:]))
    return built


def packed_mp_reach(route: RoutedNLRI) -> bytes:
    """The MP_REACH_NLRI attribute exabgp generates for one route, header and all."""
    collection = MPNLRICollection.from_routed([route], {}, AFI.ipv4, SAFI.flow_ip)
    attributes = list(collection.packed_reach_attributes(Negotiated.UNSET))
    assert len(attributes) == 1, f'one route produced {len(attributes)} attributes'
    return attributes[0]


def next_hop_length(attribute: bytes) -> int:
    """The Length of Next-Hop Network Address octet, past the 3 byte attribute header."""
    return attribute[3 + 3]


# ==================================================== the length field, section 4.1


def test_an_nlri_longer_than_255_octets_decodes() -> None:
    """The extended length form of section 4.1, and exabgp cannot read its own output.

    Section 4.1 has no RFC 2119 keyword in it, so this cannot be a ledger entry, but it
    is the most damaging thing in this file.  The nibble is only non-zero above 255, so
    lengths 240 to 255 work and everything from 256 to 4095 does not: the peer's UPDATE
    is well formed, exabgp's own encoder produced those exact bytes, and the Notify
    raised here is outside the try in `unpack_nlri` so it reaches the reactor and takes
    the session down rather than invalidating one NLRI.
    """
    built = Flow.make_flow(AFI.ipv4, SAFI.flow_ip)
    for octet in range(60):
        built.add(Flow4Destination(bytes([24, 10, octet, 0])))
    wire = bytes(built.pack_nlri(Negotiated.UNSET))

    assert wire[0] & 0xF0 == 0xF0, 'this test needs the extended length form'
    assert len(wire) > 256, 'this test needs a length the compact form cannot hold'

    flow, over = Flow.unpack_nlri(AFI.ipv4, SAFI.flow_ip, wire, Action.ANNOUNCE, False, Negotiated.UNSET)

    assert flow is not NLRI.INVALID
    assert over == b''


@pytest.mark.xfail(
    strict=True,
    reason='a zero length FlowSpec NLRI decodes to a Flow with no component, which '
    'matches every packet, rather than being refused as malformed',
)
def test_an_nlri_of_zero_length_is_refused() -> None:
    """Section 4.2 encodes the value as <[component]+>, one or more, with no keyword.

    A flow specification with no component at all matches the intersection of nothing,
    which is everything.  exabgp hands it to the API as the string `flow`, and an API
    consumer which programmed that would rate limit or discard every packet on the box.
    """
    flow, over = Flow.unpack_nlri(AFI.ipv4, SAFI.flow_ip, bytes([0x00]), Action.ANNOUNCE, False, Negotiated.UNSET)

    assert flow is NLRI.INVALID, f'an empty flow specification decoded to {flow}'
    assert over == b''


def test_a_length_longer_than_the_buffer_is_refused() -> None:
    """Not a ledger entry either, but the read which would run off the end."""
    with pytest.raises(Notify):
        Flow.unpack_nlri(AFI.ipv4, SAFI.flow_ip, bytes([0x20]) + DESTINATION, Action.ANNOUNCE, False, Negotiated.UNSET)


# ==================================================== section 4, the next hop


@pytest.mark.rfc('rfc8955#4-next-hop-length-zero')
def test_a_flow_specification_is_advertised_with_a_next_hop_length_of_zero() -> None:
    attribute = packed_mp_reach(RoutedNLRI(flow_to(), IP.NoNextHop))

    assert next_hop_length(attribute) == 0


@pytest.mark.rfc('rfc8955#4-next-hop-length-zero', polarity='negative')
@pytest.mark.xfail(
    strict=True,
    reason='a flow route carrying a next-hop packs it into MP_REACH_NLRI with a length '
    'of 4; MPNLRICollection._encode_nexthop has no flow_ip case and writes whatever the '
    'route was given',
)
def test_a_next_hop_on_a_flow_route_is_not_put_on_the_wire() -> None:
    """The sentence is unconditional: when advertising, the length is 0.

    exabgp's flow grammar has a `next-hop` keyword, used with the redirect-to-IP drafts,
    and a route which carries one emits a four octet next-hop for AFI 1 SAFI 133.
    """
    attribute = packed_mp_reach(RoutedNLRI(flow_to(), IP.create_ip(bytes([1, 2, 3, 4]))))

    assert next_hop_length(attribute) == 0


@pytest.mark.rfc('rfc8955#4-next-hop-ignored')
def test_a_next_hop_sent_by_a_peer_does_not_change_the_flow_specification() -> None:
    negotiated = session([IPV4_FLOW])
    payload = nlri(DESTINATION + PROTOCOL_TCP)

    without = MPRNLRI.unpack_attribute(mp_reach(1, 133, b'', payload), negotiated)
    with_one = MPRNLRI.unpack_attribute(mp_reach(1, 133, bytes([192, 0, 2, 1]), payload), negotiated)

    assert isinstance(without, MPRNLRI) and isinstance(with_one, MPRNLRI)
    assert [str(entry) for entry in without] == [str(entry) for entry in with_one]


@pytest.mark.rfc('rfc8955#4-next-hop-ignored', polarity='negative')
@pytest.mark.parametrize('address', [[0, 0, 0, 0], [224, 0, 0, 1], [127, 0, 0, 1]])
def test_an_unusable_next_hop_does_not_make_a_flow_specification_unusable(address: list[int]) -> None:
    """Ignoring the field means not resolving it, and not rejecting it either.

    For a unicast route each of these next hops is a reason to discard the announcement.
    For a flow specification the field carries no meaning at all, so it must not be given
    one on the way in.
    """
    negotiated = session([IPV4_FLOW])
    payload = nlri(DESTINATION + PORT_25)

    attribute = MPRNLRI.unpack_attribute(mp_reach(1, 133, bytes(address), payload), negotiated)

    assert isinstance(attribute, MPRNLRI)
    assert [str(entry) for entry in attribute] == ['flow destination-ipv4 192.0.2.0/24 port =25']


# ==================================================== section 4, the capability


@pytest.mark.rfc('rfc8955#4-capability-multiprotocol')
def test_the_flow_specification_safis_are_133_and_134() -> None:
    negotiated = session([IPV4_FLOW, (AFI.ipv4, SAFI.flow_vpn)])

    assert int(SAFI.flow_ip) == 133
    assert int(SAFI.flow_vpn) == 134
    assert IPV4_FLOW in negotiated.families
    assert (AFI.ipv4, SAFI.flow_vpn) in negotiated.families


@pytest.mark.rfc('rfc8955#4-capability-multiprotocol', polarity='negative')
def test_a_flow_specification_for_a_family_never_advertised_is_refused() -> None:
    """The capability is a precondition, not a label on the session."""
    negotiated = session([IPV4_UNICAST])
    payload = nlri(DESTINATION)

    with pytest.raises(Notify):
        MPRNLRI.unpack_attribute(mp_reach(1, 133, b'', payload), negotiated)


# ==================================================== section 4.2, component ordering


@pytest.mark.rfc('rfc8955#4.2-strict-type-ordering')
def test_components_in_increasing_type_order_decode() -> None:
    flow = decoded(AFI.ipv4, DESTINATION + PROTOCOL_TCP + PORT_25)

    assert flow is not None
    assert str(flow) == 'flow destination-ipv4 192.0.2.0/24 protocol =tcp port =25'


@pytest.mark.rfc('rfc8955#4.2-strict-type-ordering', polarity='negative')
def test_components_in_decreasing_type_order_are_refused() -> None:
    """A filter which arrives out of order is not the filter which is reported.

    exabgp used to decode type 4 followed by type 1 and print `destination-ipv4 ...
    port =25`, the order the RFC wanted, so the API consumer could not tell the peer had
    broken the rule.
    """
    assert decoded(AFI.ipv4, PORT_25 + DESTINATION) is None


@pytest.mark.rfc('rfc8955#4.2-precede-higher-type')
def test_a_lower_type_before_a_higher_one_decodes() -> None:
    flow = decoded(AFI.ipv4, PROTOCOL_TCP + PORT_25)

    assert flow is not None
    assert str(flow) == 'flow protocol =tcp port =25'


@pytest.mark.rfc('rfc8955#4.2-precede-higher-type', polarity='negative')
def test_a_higher_type_before_a_lower_one_is_refused() -> None:
    """Distinct from the ordering test above: here each type still appears once.

    An implementation could enforce "no duplicates" without enforcing "in order" and
    would pass the duplicate test below while failing this one.
    """
    assert decoded(AFI.ipv4, DESTINATION + PORT_25 + PROTOCOL_TCP) is None


@pytest.mark.rfc('rfc8955#4.2-component-once')
def test_a_component_type_present_once_decodes() -> None:
    flow = decoded(AFI.ipv4, PROTOCOL_TCP)

    assert flow is not None
    assert str(flow) == 'flow protocol =tcp'


@pytest.mark.rfc('rfc8955#4.2-component-once', polarity='negative')
def test_a_component_type_present_twice_is_refused() -> None:
    """The failure here inverts the filter rather than widening it.

    Section 4.2 says a packet matches the intersection of all components present, so two
    protocol components must be ANDed and can never both hold.  exabgp used to merge them
    into one component whose second operator has the AND bit clear, which is an OR, so a
    rule matching nothing became a rule matching both protocols.
    """
    assert decoded(AFI.ipv4, PROTOCOL_TCP + bytes([0x03, 0x81, 0x11])) is None


# ==================================================== section 4.2.1.1, the numeric operator


@pytest.mark.rfc('rfc8955#4.2.1.1-and-bit-first-unset')
def test_the_first_operator_octet_we_encode_has_the_and_bit_clear() -> None:
    built = Flow.make_flow(AFI.ipv4, SAFI.flow_ip)
    built.add(FlowDestinationPort(NumericOperator.EQ, NumericValue(80)))
    built.add(FlowDestinationPort(NumericOperator.EQ, NumericValue(443)))

    wire = bytes(built.pack_nlri(Negotiated.UNSET))
    first_operator = wire[2]  # length, component type, then the operator

    assert not first_operator & AND


@pytest.mark.rfc('rfc8955#4.2.1.1-and-bit-first-unset', polarity='negative')
def test_an_and_bit_in_the_first_operator_octet_is_treated_as_unset() -> None:
    flow = decoded(AFI.ipv4, bytes([0x03, EOL | AND | NumericOperator.EQ, 0x06]))

    assert flow is not None
    assert str(flow) == 'flow protocol =tcp'


@pytest.mark.rfc('rfc8955#4.2.1.1-reserved-bit-zero')
@pytest.mark.parametrize(
    'operator',
    [NumericOperator.EQ, NumericOperator.LT, NumericOperator.GT, NumericOperator.NEQ, NumericOperator.TRUE],
)
def test_no_numeric_operator_we_encode_sets_the_reserved_bit(operator: int) -> None:
    built = Flow.make_flow(AFI.ipv4, SAFI.flow_ip)
    built.add(FlowDestinationPort(operator, NumericValue(80)))

    wire = bytes(built.pack_nlri(Negotiated.UNSET))

    assert not wire[2] & NUMERIC_RESERVED


@pytest.mark.rfc('rfc8955#4.2.1.1-reserved-bit-zero', polarity='negative')
def test_the_reserved_bit_of_a_numeric_operator_is_ignored_on_decoding() -> None:
    clean = decoded(AFI.ipv4, bytes([0x03, EOL | NumericOperator.EQ, 0x06]))
    dirty = decoded(AFI.ipv4, bytes([0x03, EOL | NUMERIC_RESERVED | NumericOperator.EQ, 0x06]))

    assert clean is not None and dirty is not None
    assert str(dirty) == str(clean)


# ==================================================== section 4.2.1.2, the bitmask operator


@pytest.mark.rfc('rfc8955#4.2.1.2-bitmask-reserved-bits-zero')
@pytest.mark.parametrize('operator', [BinaryOperator.INCLUDE, BinaryOperator.MATCH, BinaryOperator.NOT])
def test_no_bitmask_operator_we_encode_sets_the_reserved_bits(operator: int) -> None:
    built = Flow.make_flow(AFI.ipv4, SAFI.flow_ip)
    built.add(FlowTCPFlag(operator, TCPFlag.named('syn')))

    wire = bytes(built.pack_nlri(Negotiated.UNSET))

    assert not wire[2] & BITMASK_RESERVED


@pytest.mark.rfc('rfc8955#4.2.1.2-bitmask-reserved-bits-zero', polarity='negative')
def test_the_reserved_bits_of_a_bitmask_operator_are_ignored_on_decoding() -> None:
    clean = decoded(AFI.ipv4, bytes([0x0C, EOL | BinaryOperator.MATCH, 0x05]))
    dirty = decoded(AFI.ipv4, bytes([0x0C, EOL | BITMASK_RESERVED | BinaryOperator.MATCH, 0x05]))

    assert clean is not None and dirty is not None
    assert str(dirty) == str(clean)


# ==================================================== section 4.2.2, component widths


@pytest.mark.rfc('rfc8955#4.2.2.9-tcp-flags-width')
@pytest.mark.parametrize('name', sorted(TCPFlag.codes))
def test_every_tcp_flag_we_encode_uses_one_or_two_octets(name: str) -> None:
    built = FlowTCPFlag(BinaryOperator.MATCH, TCPFlag.named(name))

    packed = bytes(built.pack())

    assert packed[0] & 0x30 in (LEN_ONE, LEN_TWO), f'{name} packed with a wider bitmask'
    assert len(packed) - 1 in (1, 2)


@pytest.mark.rfc('rfc8955#4.2.2.9-tcp-flags-width', polarity='negative')
def test_no_tcp_flag_value_could_need_a_third_octet() -> None:
    """`FlowTCPFlag` is an `IOperationByteShort`, which would widen above 65535.

    Nothing stops it in the class, so what keeps exabgp inside the rule is that the
    grammar's largest flag is NS at 0x100 and an unknown name is refused outright.
    """
    assert max(TCPFlag.codes.values()) <= 0xFFFF
    with pytest.raises(ValueError):
        TCPFlag.named('quic')


@pytest.mark.rfc('rfc8955#4.2.2.11-dscp-single-octet')
@pytest.mark.parametrize('value', [0, 1, 32, 46, 63])
def test_every_dscp_we_encode_uses_a_single_octet(value: int) -> None:
    packed = bytes(FlowDSCP(NumericOperator.EQ, NumericValue(value)).pack())

    assert packed[0] & 0x30 == LEN_ONE
    assert len(packed) == 2


@pytest.mark.rfc('rfc8955#4.2.2.11-dscp-single-octet', polarity='negative')
@pytest.mark.parametrize('text', ['64', '255', '256', '-1'])
def test_a_dscp_which_would_not_fit_a_single_octet_is_refused_by_the_grammar(text: str) -> None:
    with pytest.raises(ValueError):
        dscp_value(text)


@pytest.mark.rfc('rfc8955#4.2.2.12-fragment-single-octet')
@pytest.mark.parametrize('name', sorted(Fragment.codes))
def test_every_fragment_bitmask_we_encode_uses_a_single_octet(name: str) -> None:
    packed = bytes(FlowFragment(BinaryOperator.MATCH, Fragment.named(name)).pack())

    assert packed[0] & 0x30 == LEN_ONE
    assert len(packed) == 2


@pytest.mark.rfc('rfc8955#4.2.2.12-fragment-single-octet', polarity='negative')
def test_no_fragment_value_could_need_a_second_octet() -> None:
    """`FlowFragment` is an `IOperationByteShort` and would widen at 256.

    The class does not state the single octet rule, so this is the test which pins it:
    the four bits this document defines are the only ones the grammar can produce.
    """
    assert max(Fragment.codes.values()) <= 0x0F
    with pytest.raises(ValueError):
        Fragment.named('reassembled')


@pytest.mark.rfc('rfc8955#4.2.2.12-fragment-reserved-bits-zero')
@pytest.mark.parametrize('name', sorted(Fragment.codes))
def test_no_fragment_bitmask_we_encode_sets_a_reserved_bit(name: str) -> None:
    packed = bytes(FlowFragment(BinaryOperator.MATCH, Fragment.named(name)).pack())

    assert not packed[1] & 0xF0


@pytest.mark.rfc('rfc8955#4.2.2.12-fragment-reserved-bits-zero', polarity='negative')
@pytest.mark.xfail(
    strict=True,
    reason='Fragment.named reports an unrecognised bit instead of dropping it, so 0xF5 '
    'decodes as "dont-fragment+first-fragment+unknown fragment type 245"',
)
def test_the_reserved_bits_of_a_fragment_bitmask_are_ignored_on_decoding() -> None:
    clean = decoded(AFI.ipv4, bytes([0x0C, EOL | BinaryOperator.MATCH, 0x05]))
    dirty = decoded(AFI.ipv4, bytes([0x0C, EOL | BinaryOperator.MATCH, 0xF5]))

    assert clean is not None and dirty is not None
    assert str(dirty) == str(clean)


# ==================================================== section 7.1, traffic-rate-bytes


@pytest.mark.rfc('rfc8955#7.1-id-not-interpreted')
def test_the_two_octet_id_does_not_appear_in_what_we_report() -> None:
    community = TrafficRate.unpack_attribute(pack('!BBHf', 0x80, 0x06, 64496, 1000.0))

    assert repr(community) == 'rate-limit:1000'
    assert community.rate == 1000.0


@pytest.mark.rfc('rfc8955#7.1-id-not-interpreted', polarity='negative')
@pytest.mark.parametrize('identifier', [0, 1, 65535])
def test_an_id_we_would_never_have_chosen_changes_nothing(identifier: int) -> None:
    """AS 0 and AS 65535 are reserved, and this field is informational, so neither is an
    error and neither may change the rate the community carries."""
    community = TrafficRate.unpack_attribute(pack('!BBHf', 0x80, 0x06, identifier, 1000.0))

    assert community.rate == 1000.0
    assert repr(community) == 'rate-limit:1000'


@pytest.mark.rfc('rfc8955#7.1-traffic-rate-not-negative-on-encoding')
@pytest.mark.parametrize('rate', [0.0, 1.0, 1000.0])
def test_a_non_negative_traffic_rate_is_encoded(rate: float) -> None:
    community = TrafficRate.make_traffic_rate(ASN(64496), rate)

    assert community.rate == rate


@pytest.mark.rfc('rfc8955#7.1-traffic-rate-not-negative-on-encoding', polarity='negative')
@pytest.mark.parametrize('rate', [-1.0, -1000.0])
def test_a_negative_traffic_rate_is_not_encoded(rate: float) -> None:
    with pytest.raises(ValueError):
        TrafficRate.make_traffic_rate(ASN(64496), rate)


@pytest.mark.rfc('rfc8955#7.1-negative-rate-treated-as-zero')
@pytest.mark.parametrize('rate', [0.0, 1.0, 1000.0])
def test_a_non_negative_traffic_rate_decodes_unchanged(rate: float) -> None:
    community = TrafficRate.unpack_attribute(pack('!BBHf', 0x80, 0x06, 64496, rate))

    assert community.rate == rate


@pytest.mark.rfc('rfc8955#7.1-negative-rate-treated-as-zero', polarity='negative')
@pytest.mark.parametrize('rate', [-1.0, -100.0])
def test_a_negative_traffic_rate_decodes_as_zero(rate: float) -> None:
    community = TrafficRate.unpack_attribute(pack('!BBHf', 0x80, 0x06, 64496, rate))

    assert community.rate == 0.0
    assert repr(community) == 'rate-limit:0'


# ==================================================== section 7.2, traffic-rate-packets


@pytest.mark.rfc('rfc8955#7.2-traffic-rate-packets-not-negative-on-encoding')
@pytest.mark.parametrize('rate', [0.0, 1.0, 1000.0])
def test_a_non_negative_traffic_rate_packets_is_encoded(rate: float) -> None:
    community = TrafficRatePackets.make_traffic_rate_packets(ASN(64496), rate)

    assert community.rate == rate


@pytest.mark.rfc('rfc8955#7.2-traffic-rate-packets-not-negative-on-encoding', polarity='negative')
@pytest.mark.parametrize('rate', [-1.0, -1e-30, -1000.0])
def test_a_negative_traffic_rate_packets_is_not_encoded(rate: float) -> None:
    """Zero is legal and means discard everything, so the check has to be < and not <=."""
    with pytest.raises(ValueError):
        TrafficRatePackets.make_traffic_rate_packets(ASN(64496), rate)


@pytest.mark.rfc('rfc8955#7.2-negative-rate-packets-treated-as-zero')
@pytest.mark.parametrize('rate', [-1.0, -1000.0])
def test_a_negative_traffic_rate_packets_decodes_as_zero(rate: float) -> None:
    community = TrafficRatePackets.unpack_attribute(pack('!BBHf', 0x80, 0x0C, 64496, rate))

    assert community.rate == 0.0
    assert repr(community) == 'rate-limit:0:packets'


@pytest.mark.rfc('rfc8955#7.2-negative-rate-packets-treated-as-zero', polarity='negative')
@pytest.mark.parametrize('rate', [0.0, 1.0, 1000.0])
def test_a_non_negative_traffic_rate_packets_decodes_unchanged(rate: float) -> None:
    """The clamp is a floor, not a filter: a rate above zero must survive it."""
    community = TrafficRatePackets.unpack_attribute(pack('!BBHf', 0x80, 0x0C, 64496, rate))

    assert community.rate == rate


# ==================================================== section 7.3, traffic-action


@pytest.mark.rfc('rfc8955#7.3-traffic-action-unused-bits-zero')
@pytest.mark.parametrize('sample', [False, True])
@pytest.mark.parametrize('terminal', [False, True])
def test_the_traffic_action_we_encode_has_every_unused_bit_at_zero(sample: bool, terminal: bool) -> None:
    packed = bytes(TrafficAction.make_traffic_action(sample, terminal).pack())

    assert packed[2:7] == bytes(5)
    assert not packed[7] & 0xFC


@pytest.mark.rfc('rfc8955#7.3-traffic-action-unused-bits-zero', polarity='negative')
def test_unused_traffic_action_bits_set_by_a_peer_are_ignored() -> None:
    clean = TrafficAction.unpack_attribute(bytes([0x80, 0x07, 0, 0, 0, 0, 0, 0x03]))
    dirty = TrafficAction.unpack_attribute(bytes([0x80, 0x07, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]))

    assert (dirty.sample, dirty.terminal) == (clean.sample, clean.terminal) == (True, True)
    assert repr(dirty) == repr(clean)


# ==================================================== section 7.5, traffic-marking


@pytest.mark.rfc('rfc8955#7.5-traffic-marking-reserved-zero')
@pytest.mark.parametrize('value', [0, 1, 46, 63])
def test_the_traffic_marking_we_encode_has_its_reserved_bits_at_zero(value: int) -> None:
    packed = bytes(TrafficMark.make_traffic_mark(dscp_value(str(value))).pack())

    assert packed[2:7] == bytes(5)
    assert not packed[7] & 0xC0


@pytest.mark.rfc('rfc8955#7.5-traffic-marking-reserved-zero', polarity='negative')
@pytest.mark.parametrize('octet, expected', [(0xC1, 1), (0x80 | 46, 46), (0xFF, 63)])
def test_the_reserved_bits_of_a_traffic_marking_are_ignored_on_decoding(octet: int, expected: int) -> None:
    community = TrafficMark.unpack_attribute(pack('!BBLBB', 0x80, 0x09, 0, 0, octet))

    assert community.dscp == expected
