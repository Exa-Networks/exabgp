"""RFC 4760, Multiprotocol Extensions for BGP-4.

The ledger these tests are joined to is qa/rfc/rfc4760.toml. Each test names the
requirement it proves, and the checker fails when a requirement we claim is no longer
proven or when a test names one that is not in the document.

Everything here drives the real decoders and the real capability negotiation: wire bytes
in, MPRNLRI.unpack_attribute or Capabilities.unpack out. Nothing is mocked, because a
mock would answer whatever the test expects and prove nothing about the bytes a peer
sends.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open import ASN, HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update import Update, UpdateCollection
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.neighbor import Neighbor
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.protocol.ip import IP
from exabgp.rib.incoming import IncomingRIB
from exabgp.rib.route import Route
from exabgp.util.enumeration import TriState

IPV4_UNICAST: FamilyTuple = (AFI.ipv4, SAFI.unicast)
IPV4_MULTICAST: FamilyTuple = (AFI.ipv4, SAFI.multicast)
IPV6_UNICAST: FamilyTuple = (AFI.ipv6, SAFI.unicast)
IPV4_VPN: FamilyTuple = (AFI.ipv4, SAFI.mpls_vpn)

# One well formed NLRI per family, so the tests below are about the next hop and the
# header in front of it rather than about prefix parsing.
NLRI_V4 = bytes([24, 10, 0, 0])  # 10.0.0.0/24
NLRI_V6 = bytes([32, 0x20, 0x01, 0x0D, 0xB8])  # 2001:db8::/32


def session(families: list[FamilyTuple], direction: Direction = Direction.IN) -> Negotiated:
    """A negotiated session where both ends advertised exactly these families."""
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(65001)
    sent = Capabilities()
    received = Capabilities()
    for capabilities in (sent, received):
        multiprotocol = MultiProtocol()
        multiprotocol.extend(families)
        capabilities[Capability.CODE.MULTIPROTOCOL] = multiprotocol
    negotiated = Negotiated(neighbor, direction)
    negotiated.sent(Open.make_open(Version(4), ASN(65001), HoldTime(90), RouterID('192.0.2.1'), sent))
    negotiated.received(Open.make_open(Version(4), ASN(65002), HoldTime(90), RouterID('192.0.2.2'), received))
    return negotiated


def mp_reach(afi: int, safi: int, nexthop: bytes, nlri: bytes, reserved: int = 0) -> bytes:
    """The MP_REACH_NLRI attribute value, as section 3 lays it out."""
    return pack('!HB', afi, safi) + bytes([len(nexthop)]) + nexthop + bytes([reserved]) + nlri


def decoded_mp_reach(payload: bytes, negotiated: Negotiated) -> MPRNLRI:
    """MPRNLRI.unpack_attribute, with the return narrowed to what it promises."""
    attribute = MPRNLRI.unpack_attribute(payload, negotiated)
    assert isinstance(attribute, MPRNLRI), f'the MP_REACH_NLRI decoded to {type(attribute).__name__}'
    return attribute


def generated_updates(routed: RoutedNLRI, negotiated: Negotiated) -> list[Update]:
    """Every UPDATE exabgp generates for one route, decoded back off its own wire bytes."""
    updates: list[Update] = []
    for message in UpdateCollection([routed], [], AttributeCollection()).messages(negotiated):
        decoded = Update.unpack_message(message[19:], negotiated)
        assert isinstance(decoded, Update), 'what we generated did not decode as an UPDATE'
        updates.append(decoded)
    assert updates, 'no UPDATE was generated, so there is nothing to look at'
    return updates


def ipv6_route() -> RoutedNLRI:
    address = IP.from_string('2001:db8::1')
    nlri = INET.from_cidr(CIDR.create_cidr(address.pack_ip(), 128), AFI.ipv6, SAFI.unicast)
    return RoutedNLRI(nlri, IP.from_string('2001:db8::ffff'))


def families_of(capabilities: Capabilities) -> list[FamilyTuple]:
    """The families a multiprotocol capability advertises, narrowed for the type checker."""
    advertised = capabilities[Capability.CODE.MULTIPROTOCOL]
    assert isinstance(advertised, MultiProtocol), 'the multiprotocol capability decoded to something else'
    return list(advertised)


# =========================================================== 3, next hop protocol


@pytest.mark.rfc('rfc4760#3-nexthop-protocol-determinable')
@pytest.mark.parametrize(
    'family,afi,safi,nexthop,nlri',
    [
        ('ipv4 unicast, 4 octets', 1, 1, bytes([192, 0, 2, 1]), NLRI_V4),
        ('ipv6 unicast, 16 octets', 2, 1, bytes(15) + bytes([1]), NLRI_V6),
        ('ipv6 unicast, 16 plus link local', 2, 1, bytes(31) + bytes([1]), NLRI_V6),
        ('ipv4 vpn, route distinguisher then 4 octets', 1, 128, bytes(8) + bytes([192, 0, 2, 1]), bytes([0])),
    ],
    ids=['ipv4-4', 'ipv6-16', 'ipv6-32', 'vpnv4-12'],
)
def test_a_next_hop_whose_length_names_its_protocol_is_accepted(
    family: str, afi: int, safi: int, nexthop: bytes, nlri: bytes
) -> None:
    """Each <AFI, SAFI> has a set of next-hop lengths, and each names one protocol."""
    negotiated = session([IPV4_UNICAST, IPV6_UNICAST, IPV4_VPN])

    attribute = MPRNLRI.unpack_attribute(mp_reach(afi, safi, nexthop, nlri), negotiated)

    assert isinstance(attribute, MPRNLRI), f'{family} did not decode to an MP_REACH_NLRI'


@pytest.mark.rfc('rfc4760#3-nexthop-protocol-determinable', polarity='negative')
@pytest.mark.parametrize(
    'family,afi,safi,nexthop,nlri',
    [
        ('ipv4 unicast with an IPv6 sized next hop', 1, 1, bytes(16), NLRI_V4),
        ('ipv6 unicast with an IPv4 sized next hop', 2, 1, bytes(4), NLRI_V6),
        ('ipv6 unicast with a length no protocol uses', 2, 1, bytes(5), NLRI_V6),
        ('ipv4 vpn without its route distinguisher', 1, 128, bytes(4), bytes([0])),
    ],
    ids=['ipv4-16', 'ipv6-4', 'ipv6-5', 'vpnv4-4'],
)
def test_a_next_hop_whose_length_names_no_protocol_is_refused(
    family: str, afi: int, safi: int, nexthop: bytes, nlri: bytes
) -> None:
    """A decoder which guessed here would hand the RIB an address of the wrong family."""
    negotiated = session([IPV4_UNICAST, IPV6_UNICAST, IPV4_VPN])

    with pytest.raises(Notify):
        MPRNLRI.unpack_attribute(mp_reach(afi, safi, nexthop, nlri), negotiated)


# =========================================================== 3, the reserved octet


@pytest.mark.rfc('rfc4760#3-reserved-must-be-zero')
def test_the_reserved_octet_we_send_is_zero() -> None:
    """Read it back off an UPDATE exabgp generated, not off the constant that wrote it."""
    negotiated = session([IPV6_UNICAST], Direction.OUT)

    for update in generated_updates(ipv6_route(), negotiated):
        attributes = AttributeCollection.unpack(update.attribute_bytes, negotiated)
        mp = attributes[Attribute.CODE.MP_REACH_NLRI]
        assert isinstance(mp, MPRNLRI), 'the generated UPDATE carried no MP_REACH_NLRI'
        packed = mp.packed
        length_of_next_hop = packed[3]
        reserved = packed[4 + length_of_next_hop]
        assert reserved == 0, f'we sent {reserved} in the reserved octet'


@pytest.mark.rfc('rfc4760#3-reserved-ignored-on-receipt')
def test_a_non_zero_reserved_octet_is_ignored_on_receipt() -> None:
    """The sentence says to ignore the byte, so the NLRI behind it must still decode."""
    negotiated = session([IPV4_UNICAST])

    attribute = decoded_mp_reach(mp_reach(1, 1, bytes([192, 0, 2, 1]), NLRI_V4, reserved=0xFF), negotiated)

    assert [str(nlri) for nlri in attribute] == ['10.0.0.0/24']


# =========================================================== 3, companion attributes


@pytest.mark.rfc('rfc4760#3-mp-reach-requires-origin-and-aspath')
@pytest.mark.parametrize('peer_as,expected', [(65002, []), (65001, [Attribute.CODE.LOCAL_PREF])], ids=['ebgp', 'ibgp'])
def test_an_update_we_generate_with_mp_reach_carries_origin_and_as_path(peer_as: int, expected: list[int]) -> None:
    """And LOCAL_PREF too when the session is IBGP, which is the second half of the MUST."""
    negotiated = session([IPV6_UNICAST], Direction.OUT)
    negotiated.local_as = ASN(65001)
    negotiated.peer_as = ASN(peer_as)

    for update in generated_updates(ipv6_route(), negotiated):
        attributes = AttributeCollection.unpack(update.attribute_bytes, negotiated)
        for code in [Attribute.CODE.ORIGIN, Attribute.CODE.AS_PATH, Attribute.CODE.MP_REACH_NLRI] + expected:
            assert code in attributes, f'{Attribute.CODE.name(code)} was missing from an MP_REACH UPDATE'


@pytest.mark.rfc('rfc4760#3-no-next-hop-attribute')
def test_an_update_carrying_only_mp_reach_has_no_next_hop_attribute() -> None:
    """The next hop belongs inside the attribute, and saying it twice invites disagreement."""
    negotiated = session([IPV6_UNICAST], Direction.OUT)

    for update in generated_updates(ipv6_route(), negotiated):
        attributes = AttributeCollection.unpack(update.attribute_bytes, negotiated)
        assert Attribute.CODE.NEXT_HOP not in attributes, 'we sent NEXT_HOP beside an MP_REACH_NLRI'
        assert not bytes(update.nlri_bytes), 'the message carried IPv4 NLRI as well, so the rule does not apply'


@pytest.mark.rfc('rfc4760#3-no-next-hop-attribute', polarity='negative')
def test_a_next_hop_attribute_beside_mp_reach_does_not_reach_the_mp_nlri() -> None:
    """A peer which sends both must not have its NEXT_HOP used for the MP_REACH routes."""
    negotiated = session([IPV6_UNICAST])
    attributes = (
        bytes([Attribute.Flag.TRANSITIVE, Attribute.CODE.NEXT_HOP, 4])
        + bytes([192, 0, 2, 9])
        + bytes([Attribute.Flag.OPTIONAL, Attribute.CODE.MP_REACH_NLRI])
        + bytes([len(mp_reach(2, 1, bytes(15) + bytes([1]), NLRI_V6))])
        + mp_reach(2, 1, bytes(15) + bytes([1]), NLRI_V6)
    )

    decoded = AttributeCollection.unpack(attributes, negotiated)
    mp = decoded[Attribute.CODE.MP_REACH_NLRI]
    assert isinstance(mp, MPRNLRI), 'the MP_REACH_NLRI did not decode'
    nexthops = {str(routed.nexthop) for routed in mp.iter_routed()}

    assert nexthops == {'::1'}, f'the NEXT_HOP attribute leaked into the MP_REACH routes: {nexthops}'


# =========================================================== 6, which SAFI we support


@pytest.mark.rfc('rfc4760#6-safi-support-is-optional')
@pytest.mark.parametrize('safi,family', [(1, IPV4_UNICAST), (2, IPV4_MULTICAST)], ids=['unicast', 'multicast'])
def test_both_safi_values_this_document_defines_are_supported(safi: int, family: FamilyTuple) -> None:
    """We took "all" of the permission, so both SAFI 1 and SAFI 2 decode."""
    negotiated = session([family])

    attribute = decoded_mp_reach(mp_reach(1, safi, bytes([192, 0, 2, 1]), NLRI_V4), negotiated)

    assert [str(nlri) for nlri in attribute] == ['10.0.0.0/24']


# =========================================================== 7, error handling


def incorrect_mp_attributes() -> list[tuple[str, bytes]]:
    """Every shape of incorrect MP_REACH_NLRI the decoder knows how to reject.

    A non-zero reserved octet is deliberately not on this list. Section 3 says to ignore
    that byte, so an attribute carrying one is not incorrect, and the test above pins
    that it decodes.
    """
    return [
        ('truncated before the reserved octet', pack('!HB', 1, 1) + bytes([4]) + bytes(4)),
        ('a next-hop length the family never uses', mp_reach(1, 1, bytes(16), NLRI_V4)),
        ('a family neither end advertised', mp_reach(1, 2, bytes([192, 0, 2, 1]), NLRI_V4)),
        ('no NLRI at all, and not an EOR', mp_reach(1, 1, bytes([192, 0, 2, 1]), b'')),
    ]


@pytest.mark.rfc('rfc4760#7-delete-routes-of-that-family')
@pytest.mark.parametrize(
    'what,attribute', incorrect_mp_attributes(), ids=lambda value: value if isinstance(value, str) else ''
)
def test_an_incorrect_mp_attribute_is_found_incorrect(what: str, attribute: bytes) -> None:
    """Half one of the requirement: we have to notice before we can delete anything."""
    negotiated = session([IPV4_UNICAST])

    with pytest.raises(Notify):
        MPRNLRI.unpack_attribute(attribute, negotiated)


@pytest.mark.rfc('rfc4760#7-delete-routes-of-that-family')
def test_clearing_the_incoming_rib_removes_the_routes_of_that_family() -> None:
    """Half two: what Peer._main does on the way back up after the session went down."""
    rib = IncomingRIB(True, {IPV4_UNICAST})
    address = IP.from_string('10.0.0.0')
    nlri = INET.from_cidr(CIDR.create_cidr(address.pack_ip(), 24), AFI.ipv4, SAFI.unicast)
    rib.update_cache(Route(nlri, AttributeCollection(), IP.from_string('192.0.2.1')))
    assert list(rib.cached_routes([IPV4_UNICAST])), 'the route was never cached, so the clear proves nothing'

    rib.clear()

    assert not list(rib.cached_routes([IPV4_UNICAST])), 'a route of that family survived the clear'


@pytest.mark.rfc('rfc4760#7-delete-routes-of-that-family', polarity='negative')
def test_a_correct_mp_attribute_costs_the_peer_nothing() -> None:
    """The deletion is for an incorrect attribute. A well formed one must not trigger it."""
    negotiated = session([IPV4_UNICAST, IPV6_UNICAST])

    for afi, nexthop, nlri in ((1, bytes([192, 0, 2, 1]), NLRI_V4), (2, bytes(15) + bytes([1]), NLRI_V6)):
        MPRNLRI.unpack_attribute(mp_reach(afi, 1, nexthop, nlri), negotiated)
        MPURNLRI.unpack_attribute(pack('!HB', afi, 1) + nlri, negotiated)


@pytest.mark.rfc('rfc4760#7-terminate-with-optional-attribute-error')
def test_an_incorrect_mp_attribute_terminates_with_optional_attribute_error() -> None:
    """One test over every case, because the subcode has to be right for all of them."""
    negotiated = session([IPV4_UNICAST])
    wrong: list[str] = []

    for what, attribute in incorrect_mp_attributes():
        with pytest.raises(Notify) as raised:
            MPRNLRI.unpack_attribute(attribute, negotiated)
        if (raised.value.code, raised.value.subcode) != (3, 9):
            wrong.append(f'{what}: {raised.value.code}/{raised.value.subcode}')

    assert not wrong, 'terminated with the wrong code/subcode for ' + '; '.join(wrong)


@pytest.mark.rfc('rfc4760#7-terminate-with-optional-attribute-error')
@pytest.mark.parametrize(
    'what,attribute',
    [
        ('truncated before the SAFI', pack('!H', 1)),
        ('a family neither end advertised', pack('!HB', 1, 2) + NLRI_V4),
    ],
    ids=['truncated', 'not-negotiated'],
)
def test_an_incorrect_mp_unreach_terminates_with_optional_attribute_error(what: str, attribute: bytes) -> None:
    """The sentence names the attribute pair, so MP_UNREACH_NLRI answers the same subcode."""
    negotiated = session([IPV4_UNICAST])

    with pytest.raises(Notify) as raised:
        MPURNLRI.unpack_attribute(attribute, negotiated)

    assert (raised.value.code, raised.value.subcode) == (3, 9), (
        f'{what} terminated with {raised.value.code}/{raised.value.subcode}'
    )


# =========================================================== 8, capability advertisement


@pytest.mark.rfc('rfc4760#8-should-use-capability-advertisement')
def test_our_open_advertises_the_multiprotocol_capability() -> None:
    """We ask rather than assume: the families we want are in the OPEN we send."""
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(65001)
    neighbor.add_family(IPV6_UNICAST)

    capabilities = Capabilities().new(neighbor, False)
    decoded = Capabilities.unpack(capabilities.pack_capabilities())

    assert IPV6_UNICAST in families_of(decoded), 'a configured family was not advertised'


@pytest.mark.rfc('rfc4760#8-should-use-capability-advertisement', polarity='negative')
def test_a_family_we_want_is_not_used_until_the_peer_answers() -> None:
    """Configuration is not negotiation. With the peer silent, nothing is agreed."""
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(65001)
    sent = Capabilities()
    multiprotocol = MultiProtocol()
    multiprotocol.extend([IPV6_UNICAST])
    sent[Capability.CODE.MULTIPROTOCOL] = multiprotocol
    negotiated = Negotiated(neighbor, Direction.IN)
    negotiated.sent(Open.make_open(Version(4), ASN(65001), HoldTime(90), RouterID('192.0.2.1'), sent))
    negotiated.received(Open.make_open(Version(4), ASN(65002), HoldTime(90), RouterID('192.0.2.2'), Capabilities()))

    assert negotiated.families == [], 'a family was negotiated on our word alone'
    with pytest.raises(Notify):
        MPRNLRI.unpack_attribute(mp_reach(2, 1, bytes(15) + bytes([1]), NLRI_V6), negotiated)


@pytest.mark.rfc('rfc4760#8-reserved-field-zero-and-ignored')
def test_the_reserved_octet_of_the_capability_we_send_is_zero() -> None:
    """AFI, then a zero octet, then SAFI: four octets, as section 8 draws them."""
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(65001)
    neighbor.add_family(IPV6_UNICAST)

    capabilities = Capabilities().new(neighbor, False)
    values = capabilities[Capability.CODE.MULTIPROTOCOL].extract_capability_bytes()

    assert values, 'the multiprotocol capability carried no value'
    for value in values:
        assert len(value) == 4, f'the capability value is {len(value)} octets, not 4'
        assert value[2] == 0, f'we sent {value[2]} in the reserved octet of the capability'


@pytest.mark.rfc('rfc4760#8-reserved-field-zero-and-ignored', polarity='negative')
def test_a_non_zero_reserved_octet_in_the_capability_changes_nothing() -> None:
    """A peer which sets the field must still be understood to mean the same family."""
    ignored = Capabilities.unpack(capabilities_parameter([(Capability.CODE.MULTIPROTOCOL, pack('!HBB', 1, 0xFF, 1))]))
    clean = Capabilities.unpack(capabilities_parameter([(Capability.CODE.MULTIPROTOCOL, pack('!HBB', 1, 0x00, 1))]))

    assert families_of(ignored) == [IPV4_UNICAST]
    assert families_of(ignored) == families_of(clean)


def capabilities_parameter(capabilities: list[tuple[int, bytes]]) -> bytes:
    """One OPEN Capabilities Optional Parameter holding these TLVs, with its length byte."""
    body = b''
    for code, value in capabilities:
        body += bytes([code, len(value)]) + value
    parameter = bytes([2, len(body)]) + body
    return bytes([len(parameter)]) + parameter


@pytest.mark.rfc('rfc4760#8-bidirectional-needs-both-to-advertise')
def test_a_family_both_ends_advertised_is_negotiated() -> None:
    negotiated = session([IPV4_UNICAST, IPV6_UNICAST])

    assert negotiated.families == [IPV4_UNICAST, IPV6_UNICAST]
    MPRNLRI.unpack_attribute(mp_reach(2, 1, bytes(15) + bytes([1]), NLRI_V6), negotiated)


@pytest.mark.rfc('rfc4760#8-bidirectional-needs-both-to-advertise', polarity='negative')
def test_a_family_only_the_peer_advertised_is_not_negotiated() -> None:
    """One side is not both sides, and an UPDATE for that family is refused."""
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(65001)
    sent = Capabilities()
    ours = MultiProtocol()
    ours.extend([IPV4_UNICAST])
    sent[Capability.CODE.MULTIPROTOCOL] = ours
    received = Capabilities()
    theirs = MultiProtocol()
    theirs.extend([IPV4_UNICAST, IPV6_UNICAST])
    received[Capability.CODE.MULTIPROTOCOL] = theirs
    negotiated = Negotiated(neighbor, Direction.IN)
    negotiated.sent(Open.make_open(Version(4), ASN(65001), HoldTime(90), RouterID('192.0.2.1'), sent))
    negotiated.received(Open.make_open(Version(4), ASN(65002), HoldTime(90), RouterID('192.0.2.2'), received))

    assert negotiated.families == [IPV4_UNICAST], 'a family only the peer offered was negotiated'
    with pytest.raises(Notify):
        MPRNLRI.unpack_attribute(mp_reach(2, 1, bytes(15) + bytes([1]), NLRI_V6), negotiated)


def test_the_neighbour_helper_used_above_really_configures_a_family() -> None:
    """Guard on the fixtures: a neighbour with no family would make the tests vacuous."""
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(65001)
    neighbor.capability.asn4 = TriState.TRUE
    neighbor.add_family(IPV6_UNICAST)

    assert IPV6_UNICAST in neighbor.families()
