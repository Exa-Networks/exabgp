"""RFC 8955, Dissemination of Flow Specification Rules.

The ledger these tests are joined to is qa/rfc/rfc8955.toml.

FlowSpec is the most intricate thing exabgp decodes: a length field with two encodings, a
list of components which must arrive in a particular order, and inside most of them a
list of {operator, value} pairs where the operator octet says how many bytes of value
follow it.  Every one of those is a chance for a decoder to read past the end of its
buffer or to accept a filter the sender did not write, so the negative tests here feed
real malformed bytes to the real `Flow.unpack_nlri` and look at what comes back.

Some tests carry no `rfc()` marker.  That is not an oversight: the rule they pin is stated
in RFC 8955 without an RFC 2119 keyword, so it may not be recorded as a requirement, and a
test is the only place left to put it.
"""

from __future__ import annotations

from struct import pack
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open import ASN, HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update import Update, UpdateCollection
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.extended.communities import ExtendedCommunities
from exabgp.bgp.message.update.attribute.community.extended.traffic import (
    TrafficAction,
    TrafficNextHopSimpson,
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
from exabgp.configuration.check import _negotiated
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.protocol.ip import IP
from exabgp.protocol.ip.fragment import Fragment
from exabgp.protocol.ip.tcp.flag import TCPFlag
from exabgp.protocol.resource import NumericValue
from exabgp.reactor.peer.context import PeerContext
from exabgp.reactor.peer.handlers.update import UpdateHandler
from exabgp.rib import RIB
from exabgp.rib.flow_validation import validate_flows
from exabgp.rib.incoming import IncomingRIB

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
    return pack('!HB', int(afi), int(safi)) + bytes([len(nexthop)]) + nexthop + bytes([0]) + payload


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


# ---------------------------------------------- a whole UPDATE from an eBGP peer, section 6

LOCAL_AS = 65001
PEER_AS = 65002  # the neighbouring AS, which section 6 wants at the left of the AS_PATH
OTHER_AS = 65003

WELL_KNOWN = 0x40
OPTIONAL = 0x80
AS_SEQUENCE = 2

# 192.0.2.0/24 as an IPv4 unicast NLRI, the prefix DESTINATION names
UNICAST_PREFIX = bytes([24, 192, 0, 2])


def path_attribute(flag: int, code: int, value: bytes) -> bytes:
    """One path attribute in the short length encoding: flag, type, length, value."""
    assert len(value) <= 0xFF, 'this helper only writes the one octet length'
    return bytes([flag, code, len(value)]) + value


def as_path(*asns: int) -> bytes:
    """An AS_PATH of one AS_SEQUENCE, four octet ASNs as the session below negotiates."""
    segment = bytes([AS_SEQUENCE, len(asns)]) + b''.join(pack('!L', asn) for asn in asns)
    return path_attribute(WELL_KNOWN, Attribute.CODE.AS_PATH, segment)


def flow_announce(components: bytes, path: tuple[int, ...] = (PEER_AS,)) -> bytes:
    """An UPDATE payload announcing one IPv4 flow specification in MP_REACH_NLRI."""
    reach = mp_reach(1, 133, b'', nlri(components))
    attributes = path_attribute(WELL_KNOWN, Attribute.CODE.ORIGIN, bytes([0])) + as_path(*path)
    attributes += path_attribute(OPTIONAL, Attribute.CODE.MP_REACH_NLRI, reach)
    return pack('!H', 0) + pack('!H', len(attributes)) + attributes


def flow_withdraw(components: bytes) -> bytes:
    """An UPDATE payload withdrawing one IPv4 flow specification in MP_UNREACH_NLRI."""
    unreach = pack('!HB', 1, 133) + nlri(components)
    attributes = path_attribute(OPTIONAL, Attribute.CODE.MP_UNREACH_NLRI, unreach)
    return pack('!H', 0) + pack('!H', len(attributes)) + attributes


def unicast_announce(prefix: bytes = UNICAST_PREFIX) -> bytes:
    """An UPDATE payload announcing one IPv4 unicast route, sent by the neighbouring AS."""
    attributes = path_attribute(WELL_KNOWN, Attribute.CODE.ORIGIN, bytes([0])) + as_path(PEER_AS)
    attributes += path_attribute(WELL_KNOWN, Attribute.CODE.NEXT_HOP, bytes([192, 0, 2, 254]))
    return pack('!H', 0) + pack('!H', len(attributes)) + attributes + prefix


def unicast_withdraw(prefix: bytes = UNICAST_PREFIX) -> bytes:
    """An UPDATE payload withdrawing one IPv4 unicast route and carrying nothing else."""
    return pack('!H', len(prefix)) + prefix + pack('!H', 0)


def ebgp_session() -> Negotiated:
    """An eBGP session carrying IPv4 unicast and IPv4 flow specifications."""
    negotiated = Negotiated.make_negotiated(Neighbor(), Direction.IN)
    negotiated.local_as = ASN(LOCAL_AS)
    negotiated.peer_as = ASN(PEER_AS)
    negotiated.asn4 = True
    negotiated.families = [IPV4_UNICAST, IPV4_FLOW]
    assert not negotiated.is_ibgp, 'section 6 is about routes received over eBGP'
    return negotiated


def received_update(payload: bytes, negotiated: Negotiated) -> Update:
    """Decode an UPDATE the way the reactor does, before it reaches the peer's handler."""
    message = Update.unpack_message(payload, negotiated)
    assert isinstance(message, Update), f'expected an UPDATE, got {type(message).__name__}'
    return message


def peer_context(validation: str = 'enable') -> Any:
    """What `UpdateHandler` and the validation read of a peer: its neighbour's incoming RIB,
    its `flow-validation` setting and counters.  Validation is on unless told otherwise:
    the section 6 tests below are about what it does once asked for."""
    ctx = Mock(spec=PeerContext)
    ctx.neighbor = Mock()
    ctx.neighbor.flow_validation = validation
    ctx.neighbor.route_target_filter = False
    ctx.neighbor.prefix_limit = {}
    ctx.neighbor.rib = Mock()
    ctx.neighbor.rib.incoming = IncomingRIB(True, {IPV4_UNICAST, IPV4_FLOW})
    ctx.negotiated = Mock()
    ctx.negotiated.advertised_paths_limit = {}
    ctx.peer_id = 'rfc8955-peer'
    ctx.stats = {'receive-prefixes': 0, 'receive-withdraws': 0}
    return ctx


def ibgp_session() -> Negotiated:
    """The same session inside our AS, where ORIGINATOR_ID and other neighbouring ASes exist."""
    negotiated = ebgp_session()
    negotiated.peer_as = ASN(LOCAL_AS)
    return negotiated


def receive(ctx: Any, *payloads: bytes, negotiated: Negotiated | None = None) -> list[UpdateCollection]:
    """Hand each UPDATE, decoded on an eBGP session, through the validation to the handler,
    in the order `Protocol.read_message` and the peer loop do.  Returns what revalidation
    tells the API."""
    negotiated = negotiated or ebgp_session()
    handler = UpdateHandler()
    changes: list[UpdateCollection] = []
    for payload in payloads:
        update = received_update(payload, negotiated)
        changes.extend(validate_flows(ctx.neighbor, update.data))
        list(handler.handle(ctx, update))
    return changes


def held(ctx: Any, family: FamilyTuple) -> list[str]:
    """The routes of one family the peer's incoming RIB holds, as the API prints them."""
    return sorted(str(route.nlri) for route in ctx.neighbor.rib.incoming.cached_routes([family]))


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
def test_a_next_hop_on_a_flow_route_is_not_put_on_the_wire() -> None:
    """The sentence is unconditional: when advertising, the length is 0.

    exabgp's flow grammar has a `next-hop` keyword, used with the redirect-to-IP drafts;
    without the draft-simpson community which gives it a meaning it is not sent.
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


# ==================================================== section 4.2, combinations which match nothing

FLOW_NEIGHBOR = """
neighbor %s {
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as 65001;
    peer-as 65002;
    family { ipv4 flow; }
    flow {
        route %s {
            match {
                destination 192.0.2.0/24;
                %s
            }
            then { discard; }
        }
    }
}
"""


@pytest.fixture
def isolated_rib(monkeypatch: pytest.MonkeyPatch) -> None:
    """`RIB` keys a process wide cache by neighbour name, and every test here uses one name."""
    monkeypatch.setattr(RIB, '_cache', {})


def propagated(peer: str, name: str, match: str) -> list[str]:
    """The flow routes a configuration puts in the outgoing RIB; none if it is refused.

    Each call names its own peer: the RIB is cached by neighbour, so a second
    configuration of the same one would inherit the routes of the first.
    """
    configuration = Configuration([FLOW_NEIGHBOR % (peer, name, match)], text=True)
    if not configuration.reload():
        return []
    (neighbor,) = configuration.neighbors.values()
    _negotiated(neighbor)
    for _ in neighbor.rib.outgoing.updates(False):
        pass
    return [str(route.nlri) for route in neighbor.rib.outgoing.cached_routes()]


@pytest.mark.rfc('rfc8955#4.2-unmatchable-not-propagated')
def test_a_flow_specification_matching_icmp_type_and_port_is_not_propagated(isolated_rib: None) -> None:
    """ICMP carries no ports, so a packet with an ICMP type never has a port to match.

    The ICMP type alone is a filter which can match, and is propagated.  Adding the port
    turns it into the section's own example of one which cannot.  Refusing it in the
    configuration and leaving it out of the outgoing RIB are both compliant.
    """
    assert propagated('192.0.2.1', 'icmp-alone', 'icmp-type echo-request;') == [
        'flow destination-ipv4 192.0.2.0/24 icmp-type =echo-request'
    ]

    assert propagated('192.0.2.3', 'icmp-and-port', 'icmp-type echo-request; port =80;') == []


def test_a_flow_route_redirecting_to_its_next_hop_keeps_it() -> None:
    """Unmarked: draft-simpson-idr-flowspec-redirect-ip puts the redirect target in the next
    hop, so a route carrying its community (`redirect-simpson`) is the one exception."""
    simpson = ExtendedCommunities().add(TrafficNextHopSimpson.make_traffic_nexthop_simpson(False))
    collection = MPNLRICollection.from_routed(
        [RoutedNLRI(flow_to(), IP.create_ip(bytes([1, 2, 3, 4])))],
        {Attribute.CODE.EXTENDED_COMMUNITY: simpson},
        AFI.ipv4,
        SAFI.flow_ip,
    )
    (attribute,) = collection.packed_reach_attributes(Negotiated.UNSET)

    assert next_hop_length(attribute) == 4


def test_a_configuration_with_an_unmatchable_flow_route_still_loads(isolated_rib: None) -> None:
    """Unmarked: the route is dropped with a warning, the rest of the configuration stands."""
    configuration = Configuration(
        [FLOW_NEIGHBOR % ('192.0.2.5', 'icmp-and-port', 'icmp-type echo-request; port =80;')], text=True
    )

    assert configuration.reload(), str(configuration.error)


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


@pytest.mark.rfc('rfc8955#4.2.2.11-dscp-other-bits-zero', polarity='negative')
def test_the_two_high_bits_of_a_dscp_octet_are_ignored_on_decoding() -> None:
    """The two high bits of the IP header octet are ECN, not part of the DSCP."""
    clean = decoded(AFI.ipv4, bytes([0x0B, EOL | NumericOperator.EQ, 0x3F]))
    dirty = decoded(AFI.ipv4, bytes([0x0B, EOL | NumericOperator.EQ, 0xFF]))

    assert clean is not None and dirty is not None
    assert str(clean) == 'flow dscp =63'
    assert str(dirty) == str(clean)


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
def test_the_reserved_bits_of_a_fragment_bitmask_are_ignored_on_decoding() -> None:
    clean = decoded(AFI.ipv4, bytes([0x0C, EOL | BinaryOperator.MATCH, 0x05]))
    dirty = decoded(AFI.ipv4, bytes([0x0C, EOL | BinaryOperator.MATCH, 0xF5]))

    assert clean is not None and dirty is not None
    assert str(dirty) == str(clean)


# ==================================================== section 4.2.1.1, a value wider than its field

# The operator octet lets a sender announce a value of 1, 2, 4 or 8 octets whatever the
# component, and exabgp reads any of them: refusing a port of 80 sent in four octets once
# dropped a real route.  What it cannot do is keep a value too large for the field it
# matches.  IP protocol is one octet in the packet, a port two, a flow label four, so a
# protocol of 262 can never match anything, cannot be packed again (`bytes([262])`
# raises), and is rendered to the API as a filter the configuration grammar refuses.
# RFC 8955 section 4.2 calls an NLRI "not encoded as specified here" malformed, without a
# keyword, so these tests carry no rfc() marker.
LEN_FOUR = 0x20
LEN_EIGHT = 0x30

WIDER: dict[int, tuple[int, int]] = {  # field octets: the next width up, and its length bits
    1: (2, LEN_TWO),
    2: (4, LEN_FOUR),
    4: (8, LEN_EIGHT),
}

# (family, component type, octets of the field it matches)
FIELD_WIDTHS: list[tuple[AFI, int, int]] = [
    (AFI.ipv4, 0x03, 1),  # protocol
    (AFI.ipv4, 0x04, 2),  # port
    (AFI.ipv4, 0x05, 2),  # destination-port
    (AFI.ipv4, 0x06, 2),  # source-port
    (AFI.ipv4, 0x07, 1),  # icmp-type
    (AFI.ipv4, 0x08, 1),  # icmp-code
    (AFI.ipv4, 0x09, 2),  # tcp-flags
    (AFI.ipv4, 0x0A, 2),  # packet-length
    (AFI.ipv6, 0x03, 1),  # next-header
    (AFI.ipv6, 0x0B, 1),  # traffic-class
    (AFI.ipv6, 0x0D, 4),  # flow-label
]


def widened(what: int, field_octets: int, value: int) -> bytes:
    """One component whose value is sent one width wider than the field it matches."""
    octets, length_bits = WIDER[field_octets]
    return bytes([what, EOL | length_bits | NumericOperator.EQ]) + value.to_bytes(octets, 'big')


@pytest.mark.parametrize(('afi', 'what', 'field_octets'), FIELD_WIDTHS)
def test_a_value_too_large_for_its_field_is_refused(afi: AFI, what: int, field_octets: int) -> None:
    too_large = 1 << (8 * field_octets)

    flow = decoded(afi, widened(what, field_octets, too_large))

    assert flow is None, f'component {what} kept a value of {too_large}: {flow}'


@pytest.mark.parametrize(('afi', 'what', 'field_octets'), FIELD_WIDTHS)
def test_the_largest_value_of_a_field_sent_wide_still_decodes_and_packs(afi: AFI, what: int, field_octets: int) -> None:
    largest = (1 << (8 * field_octets)) - 1

    flow = decoded(afi, widened(what, field_octets, largest))

    assert flow is not None, f'component {what} refused {largest} sent in a wider value'
    [component] = flow.rules[what]
    packed = bytes(component.pack())
    assert int.from_bytes(packed[1:], 'big') == largest


# ==================================================== section 6, validation

UPDATE_MESSAGE_ERROR = 3
MALFORMED_AS_PATH = 11


def announced_flows(payload: bytes) -> list[str]:
    """The flow specifications an UPDATE from the eBGP peer announces once decoded.

    RFC 4271 section 6.3 answers a leftmost AS which is not the peer's with Malformed
    AS_PATH, and treating the route as withdrawn is the RFC 7606 answer to the same
    error, so either counts as nothing announced.  Any other NOTIFICATION is a failure.
    """
    try:
        parsed = received_update(payload, ebgp_session()).data
    except Notify as notify:
        assert (notify.code, notify.subcode) == (UPDATE_MESSAGE_ERROR, MALFORMED_AS_PATH), str(notify)
        return []
    return [str(routed.nlri) for routed in parsed.announces if routed.nlri.family().afi_safi() == IPV4_FLOW]


@pytest.mark.rfc('rfc8955#6-validation-feasible-if-and-only-if', polarity='negative')
def test_a_flow_specification_without_a_unicast_route_for_its_destination_is_not_feasible() -> None:
    """Rule b: the originator of the flow must be the originator of the best unicast match.

    The same flow from two peers.  The first announced 192.0.2.0/24 as unicast and so
    passes; the second never did, so no unicast route exists for the flow to match and
    it must not be held as feasible.
    """
    with_route = peer_context()
    receive(with_route, unicast_announce(), flow_announce(DESTINATION))
    assert held(with_route, IPV4_FLOW) == ['flow destination-ipv4 192.0.2.0/24']

    without_route = peer_context()
    receive(without_route, flow_announce(DESTINATION))

    assert held(without_route, IPV4_UNICAST) == []
    assert held(without_route, IPV4_FLOW) == []


@pytest.mark.rfc('rfc8955#6-rules-b-and-c-disregarded')
def test_rules_b_and_c_are_not_disregarded_without_explicit_configuration() -> None:
    """Rule a, a destination prefix, is only relaxed by explicit configuration.

    Only then may rules b and c be disregarded.  Nothing here configures that, so a flow
    specification with no destination prefix component has no unicast route for rules b
    and c to check it against, and must not be held as feasible.
    """
    ctx = peer_context()
    receive(ctx, unicast_announce(), flow_announce(PROTOCOL_TCP + PORT_25))

    assert held(ctx, IPV4_UNICAST) == ['192.0.2.0/24']
    assert held(ctx, IPV4_FLOW) == []


@pytest.mark.rfc('rfc8955#6-enforce-leftmost-as', polarity='negative')
def test_an_ebgp_route_whose_as_path_does_not_start_with_the_peer_as_is_not_accepted() -> None:
    """The first half is the positive side: the peer's own AS first is accepted."""
    assert announced_flows(flow_announce(DESTINATION, path=(PEER_AS, OTHER_AS))) == [
        'flow destination-ipv4 192.0.2.0/24'
    ]

    assert announced_flows(flow_announce(DESTINATION, path=(OTHER_AS, PEER_AS))) == []


@pytest.mark.rfc('rfc8955#6-revalidate-on-unicast-change')
def test_a_flow_specification_is_no_longer_feasible_once_its_unicast_route_is_withdrawn() -> None:
    ctx = peer_context()
    receive(ctx, unicast_announce(), flow_announce(DESTINATION))
    assert held(ctx, IPV4_FLOW) == ['flow destination-ipv4 192.0.2.0/24']

    receive(ctx, unicast_withdraw())

    assert held(ctx, IPV4_UNICAST) == []
    assert held(ctx, IPV4_FLOW) == []


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


@pytest.mark.rfc('rfc8955#6-enforce-leftmost-as')
@pytest.mark.parametrize('path', [(OTHER_AS,), (OTHER_AS, PEER_AS)], ids=['another-as-alone', 'another-as-first'])
def test_the_leftmost_as_rule_does_not_bind_an_internal_peer(path: tuple[int, ...]) -> None:
    """The rule is for routes received over eBGP: an iBGP path may start anywhere."""
    negotiated = ebgp_session()
    negotiated.peer_as = ASN(LOCAL_AS)
    parsed = received_update(flow_announce(DESTINATION, path=path), negotiated).data

    assert [str(routed.nlri) for routed in parsed.announces] == ['flow destination-ipv4 192.0.2.0/24']


def test_a_route_server_neighbour_can_turn_the_leftmost_as_rule_off() -> None:
    """Unmarked: `enforce-first-as false`, for a route server, which does not prepend."""
    negotiated = ebgp_session()
    negotiated.neighbor.enforce_first_as = False
    parsed = received_update(flow_announce(DESTINATION, path=(OTHER_AS, PEER_AS)), negotiated).data

    assert [str(routed.nlri) for routed in parsed.announces] == ['flow destination-ipv4 192.0.2.0/24']


# the section 6 validation beyond the four sentences above

OTHER_PREFIX = bytes([24, 198, 51, 100])  # 198.51.100.0/24, which covers nothing the flow names
MORE_SPECIFIC = bytes([25, 192, 0, 2, 0])  # 192.0.2.0/25, inside the flow's destination


def unicast_from(asn: int, prefix: bytes = UNICAST_PREFIX, originator: bytes = b'', first: int = PEER_AS) -> bytes:
    """A unicast UPDATE whose AS_PATH starts with `first` and ends with `asn`, with an
    ORIGINATOR_ID when given."""
    attributes = path_attribute(WELL_KNOWN, Attribute.CODE.ORIGIN, bytes([0]))
    attributes += as_path(first, asn) if asn != first else as_path(first)
    attributes += path_attribute(WELL_KNOWN, Attribute.CODE.NEXT_HOP, bytes([192, 0, 2, 254]))
    if originator:
        attributes += path_attribute(OPTIONAL, Attribute.CODE.ORIGINATOR_ID, originator)
    return pack('!H', 0) + pack('!H', len(attributes)) + attributes + prefix


def test_without_flow_validation_a_flow_with_no_unicast_route_is_held() -> None:
    """Unmarked: the default is off, as decided for this release, and nothing changes then."""
    ctx = peer_context('disable')
    receive(ctx, flow_announce(DESTINATION))

    assert held(ctx, IPV4_FLOW) == ['flow destination-ipv4 192.0.2.0/24']


@pytest.mark.rfc('rfc8955#6-rule-a-may-be-relaxed')
def test_relaxed_validation_accepts_a_flow_with_no_destination() -> None:
    ctx = peer_context('relaxed')
    receive(ctx, flow_announce(PROTOCOL_TCP + PORT_25))

    assert held(ctx, IPV4_FLOW) == ['flow protocol =tcp port =25']


@pytest.mark.rfc('rfc8955#6-rules-b-and-c-disregarded', polarity='negative')
def test_relaxed_validation_still_applies_rules_b_and_c_to_a_flow_with_a_destination() -> None:
    """Relaxing rule a is for flows with no destination; one with a destination is still
    judged, and with no unicast route for it is not feasible."""
    ctx = peer_context('relaxed')
    receive(ctx, flow_announce(DESTINATION))

    assert held(ctx, IPV4_FLOW) == []


@pytest.mark.rfc('rfc8955#6-validation-feasible-if-and-only-if')
def test_a_flow_covered_by_a_shorter_unicast_route_is_feasible() -> None:
    """The best match is the longest unicast prefix covering the destination, not only an
    identical one."""
    ctx = peer_context()
    receive(ctx, unicast_announce(bytes([16, 192, 0])), flow_announce(DESTINATION))

    assert held(ctx, IPV4_FLOW) == ['flow destination-ipv4 192.0.2.0/24']


@pytest.mark.rfc('rfc8955#6-validation-feasible-if-and-only-if', polarity='negative')
def test_a_unicast_route_for_another_prefix_does_not_make_a_flow_feasible() -> None:
    ctx = peer_context()
    receive(ctx, unicast_announce(OTHER_PREFIX), flow_announce(DESTINATION))

    assert held(ctx, IPV4_FLOW) == []


@pytest.mark.rfc('rfc8955#6-validation-feasible-if-and-only-if', polarity='negative')
def test_rule_b_a_flow_from_another_originator_than_its_best_match_is_not_feasible() -> None:
    """Behind a route reflector the originator is the ORIGINATOR_ID, not the peer.

    iBGP: RFC 7606 7.9 discards an ORIGINATOR_ID from an external neighbour.
    """
    ctx = peer_context()
    receive(
        ctx,
        unicast_from(PEER_AS, originator=bytes([192, 0, 2, 7])),
        flow_announce(DESTINATION),
        negotiated=ibgp_session(),
    )

    assert held(ctx, IPV4_FLOW) == []


@pytest.mark.rfc('rfc8955#6-validation-feasible-if-and-only-if', polarity='negative')
def test_rule_c_a_more_specific_route_from_another_neighbouring_as_makes_a_flow_infeasible() -> None:
    """iBGP: on one EBGP session every route's neighbouring AS is the peer's, so rule c can
    only fail for routes which entered our AS from different neighbours."""
    ctx = peer_context()
    receive(
        ctx,
        unicast_from(PEER_AS),
        unicast_from(OTHER_AS, MORE_SPECIFIC, first=OTHER_AS),
        flow_announce(DESTINATION, path=(PEER_AS,)),
        negotiated=ibgp_session(),
    )

    assert held(ctx, IPV4_FLOW) == []


@pytest.mark.rfc('rfc8955#6-revalidate-on-unicast-change')
def test_a_flow_held_back_becomes_feasible_when_its_unicast_route_arrives_and_the_api_is_told() -> None:
    ctx = peer_context()
    receive(ctx, flow_announce(DESTINATION))
    assert held(ctx, IPV4_FLOW) == []

    told = receive(ctx, unicast_announce())

    assert held(ctx, IPV4_FLOW) == ['flow destination-ipv4 192.0.2.0/24']
    assert [str(routed.nlri) for change in told for routed in change.announces] == [
        'flow destination-ipv4 192.0.2.0/24'
    ]


@pytest.mark.rfc('rfc8955#6-revalidate-on-unicast-change', polarity='negative')
def test_a_withdrawn_flow_is_not_brought_back_by_a_later_unicast_route() -> None:
    """A flow the peer withdrew while it was held back is gone, not merely pending."""
    ctx = peer_context()
    receive(ctx, flow_announce(DESTINATION), flow_withdraw(DESTINATION))

    told = receive(ctx, unicast_announce())

    assert held(ctx, IPV4_FLOW) == []
    assert told == []


def test_the_api_is_told_when_a_held_flow_is_no_longer_feasible() -> None:
    """Unmarked: the withdraw half of revalidation, as the API sees it."""
    ctx = peer_context()
    receive(ctx, unicast_announce(), flow_announce(DESTINATION))

    told = receive(ctx, unicast_withdraw())

    assert [str(nlri) for change in told for nlri in change.withdraws] == ['flow destination-ipv4 192.0.2.0/24']


def test_rule_c_passes_when_the_more_specific_route_entered_from_the_same_neighbouring_as() -> None:
    """Unmarked: the other side of rule c, so a check which refused every more-specific
    route would fail here."""
    ctx = peer_context()
    receive(
        ctx,
        unicast_from(PEER_AS),
        unicast_from(OTHER_AS, MORE_SPECIFIC),
        flow_announce(DESTINATION),
        negotiated=ibgp_session(),
    )

    assert held(ctx, IPV4_FLOW) == ['flow destination-ipv4 192.0.2.0/24']


@pytest.mark.rfc('rfc8955#6-validation-feasible-if-and-only-if', polarity='negative')
def test_rule_b_is_judged_against_the_longest_covering_route_not_any_covering_route() -> None:
    """The /16 came from another originator, the /24 from the one which sent the flow: the
    /24 is the best match and the flow is feasible; judged against the /16 it would not be."""
    ctx = peer_context()
    receive(
        ctx,
        unicast_from(PEER_AS, bytes([16, 192, 0]), originator=bytes([192, 0, 2, 7])),
        unicast_from(PEER_AS),
        flow_announce(DESTINATION),
        negotiated=ibgp_session(),
    )

    assert held(ctx, IPV4_FLOW) == ['flow destination-ipv4 192.0.2.0/24']
