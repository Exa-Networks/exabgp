"""RFC 9830: the SR Policy NLRI, and the length byte which decides how wide the endpoint is.

The NLRI is three fixed fields with no internal framing, so everything rests on one octet.
Section 2.1 ties it to the AFI: 96 bits under AFI 1, 192 under AFI 2.  Get that wrong and
four octets of endpoint get read as sixteen, or the other way round, and the address which
reaches the API is not the address the peer sent.  The tests below feed each AFI the other
one's length byte, which is the shape that would do it.
"""

from __future__ import annotations

from struct import pack
from typing import Any

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI, NextHopWithLinkLocal
from exabgp.bgp.message.update.attribute.tunnel_encap import TunnelEncap
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.nlri.collection import MPNLRICollection
from exabgp.bgp.message.update.nlri.sr_policy import SRPolicyNLRI
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.protocol.ip import IP, IPv6
from tests import negotiation

pytestmark = pytest.mark.timeout(10)

TUNNEL_ENCAP = int(Attribute.CODE.TUNNEL_ENCAP)
TREAT_AS_WITHDRAW = Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW
SR_POLICY_TUNNEL = 15

IPV4_BITS = 96
IPV6_BITS = 192


def nlri_bytes(length_bits: int, endpoint: bytes, distinguisher: int = 1, color: int = 2) -> bytes:
    return bytes([length_bits]) + pack('!II', distinguisher, color) + endpoint


def unpack(afi: AFI, wire: bytes) -> SRPolicyNLRI:
    decoded, remaining = SRPolicyNLRI.unpack_nlri(afi, SAFI.sr_policy, wire, Action.ANNOUNCE, False, Negotiated.UNSET)
    assert remaining == b''
    assert isinstance(decoded, SRPolicyNLRI)
    return decoded


@pytest.mark.rfc('rfc9830#2.1-afi-must-be-ipv4-or-ipv6')
def test_the_sr_policy_nlri_is_registered_for_ipv4_and_ipv6() -> None:
    assert NLRI.registered_nlri['ipv4/sr-policy'] is SRPolicyNLRI
    assert NLRI.registered_nlri['ipv6/sr-policy'] is SRPolicyNLRI


@pytest.mark.rfc('rfc9830#2.1-afi-must-be-ipv4-or-ipv6', polarity='negative')
def test_no_other_address_family_resolves_to_the_sr_policy_nlri() -> None:
    families = sorted(key for key in NLRI.registered_nlri if key.endswith('/sr-policy'))
    assert families == ['ipv4/sr-policy', 'ipv6/sr-policy']


@pytest.mark.rfc('rfc9830#2.1-nlri-length-96-or-192')
def test_ninety_six_bits_under_afi_one_decodes_a_four_octet_endpoint() -> None:
    decoded = unpack(AFI.ipv4, nlri_bytes(IPV4_BITS, bytes([10, 0, 0, 1])))
    assert (decoded.distinguisher, decoded.color, decoded.endpoint) == (1, 2, '10.0.0.1')


@pytest.mark.rfc('rfc9830#2.1-nlri-length-96-or-192')
def test_one_hundred_and_ninety_two_bits_under_afi_two_decodes_a_sixteen_octet_endpoint() -> None:
    endpoint = bytes.fromhex('20010db8000000000000000000000001')
    decoded = unpack(AFI.ipv6, nlri_bytes(IPV6_BITS, endpoint))
    assert decoded.endpoint == '2001:db8::1'


@pytest.mark.rfc('rfc9830#2.1-nlri-length-96-or-192', polarity='negative')
def test_an_ipv4_length_byte_under_afi_two_is_refused_rather_than_read_as_ipv6() -> None:
    # 12 bytes of body with the AFI saying 16: the suspicion is that the endpoint property
    # would read past the end of the NLRI and into whatever followed it
    with pytest.raises(Notify) as raised:
        unpack(AFI.ipv6, nlri_bytes(IPV4_BITS, bytes([10, 0, 0, 1])))
    assert (raised.value.code, raised.value.subcode) == (3, 10)


@pytest.mark.rfc('rfc9830#2.1-nlri-length-96-or-192', polarity='negative')
def test_an_ipv6_length_byte_under_afi_one_is_refused() -> None:
    endpoint = bytes.fromhex('20010db8000000000000000000000001')
    with pytest.raises(Notify) as raised:
        unpack(AFI.ipv4, nlri_bytes(IPV6_BITS, endpoint))
    assert (raised.value.code, raised.value.subcode) == (3, 10)


@pytest.mark.rfc('rfc9830#2.1-nlri-length-96-or-192', polarity='negative')
def test_a_length_byte_of_zero_is_refused_and_does_not_yield_an_empty_nlri() -> None:
    with pytest.raises(Notify):
        unpack(AFI.ipv4, nlri_bytes(0, b''))


@pytest.mark.rfc('rfc9830#2.1-nlri-length-96-or-192', polarity='negative')
def test_the_right_length_byte_with_the_bytes_missing_is_refused() -> None:
    with pytest.raises(Notify) as raised:
        unpack(AFI.ipv4, bytes([IPV4_BITS]) + pack('!II', 1, 2))
    assert (raised.value.code, raised.value.subcode) == (3, 10)


@pytest.mark.rfc('rfc9830#2.4-single-sr-policy-tlv')
def test_two_sr_policy_tlvs_in_one_attribute_are_treated_as_withdraw() -> None:
    tlv = pack('!HH', SR_POLICY_TUNNEL, 8) + pack('!BB', 12, 6) + pack('!BBI', 0, 0, 100)
    value = tlv + tlv
    wire = bytes([0xC0, TUNNEL_ENCAP, len(value)]) + value
    collection = AttributeCollection().parse(wire, Negotiated.UNSET)
    assert TREAT_AS_WITHDRAW in collection
    # the route goes: neither TLV may be kept and handed on as if one had been sent
    assert TUNNEL_ENCAP not in collection


@pytest.mark.rfc('rfc9830#2.4-single-sr-policy-tlv', polarity='negative')
def test_a_second_tunnel_tlv_of_another_type_is_not_a_duplicate() -> None:
    # the rule names the SR Policy tunnel type, not tunnel TLVs in general: a route may
    # carry more than one tunnel, and 1 is a type exabgp does not decode
    sr_policy = pack('!HH', SR_POLICY_TUNNEL, 8) + pack('!BB', 12, 6) + pack('!BBI', 0, 0, 100)
    other = pack('!HH', 1, 4) + b'\x01\x02\x03\x04'
    value = sr_policy + other
    wire = bytes([0xC0, TUNNEL_ENCAP, len(value)]) + value
    collection = AttributeCollection().parse(wire, Negotiated.UNSET)
    assert TREAT_AS_WITHDRAW not in collection
    attr = collection[TUNNEL_ENCAP]
    assert isinstance(attr, TunnelEncap)
    assert len(attr.tunnel_tlvs) == 2


@pytest.mark.rfc('rfc9830#2.4-single-sr-policy-tlv', polarity='negative')
def test_one_sr_policy_tlv_in_an_attribute_is_accepted() -> None:
    value = pack('!HH', SR_POLICY_TUNNEL, 8) + pack('!BB', 12, 6) + pack('!BBI', 0, 0, 100)
    wire = bytes([0xC0, TUNNEL_ENCAP, len(value)]) + value
    collection = AttributeCollection().parse(wire, Negotiated.UNSET)
    assert TREAT_AS_WITHDRAW not in collection
    attr = collection[TUNNEL_ENCAP]
    assert isinstance(attr, TunnelEncap)
    assert len(attr.tunnel_tlvs) == 1


# ------------------------------------------------------------------ section 2.1, the next hop

SR_POLICY_V4: FamilyTuple = (AFI.ipv4, SAFI.sr_policy)
SR_POLICY_V6: FamilyTuple = (AFI.ipv6, SAFI.sr_policy)

NEXT_HOP_V4 = bytes([192, 0, 2, 1])
NEXT_HOP_GLOBAL = IPv6.pton('2001:db8::2')
NEXT_HOP_LINK_LOCAL = IPv6.pton('fe80::2')
ENDPOINT = {AFI.ipv4: bytes([10, 0, 0, 1]), AFI.ipv6: IPv6.pton('2001:db8::1')}
NLRI_BITS = {AFI.ipv4: IPV4_BITS, AFI.ipv6: IPV6_BITS}


def sr_policy_session() -> Negotiated:
    return negotiation.negotiated([SR_POLICY_V4, SR_POLICY_V6])


def sr_policy_reach(family: FamilyTuple, next_hop: bytes) -> bytes:
    afi, safi = family
    nlri = nlri_bytes(NLRI_BITS[afi], ENDPOINT[afi])
    return pack('!HB', int(afi), int(safi)) + bytes([len(next_hop)]) + next_hop + bytes([0]) + nlri


def received_next_hop(family: FamilyTuple, next_hop: bytes) -> IP:
    attribute = MPRNLRI.unpack_attribute(sr_policy_reach(family, next_hop), sr_policy_session())
    assert isinstance(attribute, MPRNLRI)
    routed = list(attribute.iter_routed())
    assert len(routed) == 1
    return routed[0].nexthop


@pytest.mark.rfc('rfc9830#2.1-next-hop-independent-of-afi')
@pytest.mark.parametrize('family', [SR_POLICY_V4, SR_POLICY_V6], ids=['afi-1', 'afi-2'])
def test_the_next_hop_length_not_the_afi_says_which_protocol_it_is(family: FamilyTuple) -> None:
    """Each AFI takes 4, 16 and 32: AFI 1 used to take 4 alone and AFI 2 16 alone."""
    assert str(received_next_hop(family, NEXT_HOP_V4)) == '192.0.2.1'
    assert str(received_next_hop(family, NEXT_HOP_GLOBAL)) == '2001:db8::2'

    pair = received_next_hop(family, NEXT_HOP_GLOBAL + NEXT_HOP_LINK_LOCAL)
    assert isinstance(pair, NextHopWithLinkLocal)
    assert (str(pair), str(pair.link_local)) == ('2001:db8::2', 'fe80::2')


@pytest.mark.rfc('rfc9830#2.1-next-hop-independent-of-afi', polarity='negative')
@pytest.mark.parametrize('family', [SR_POLICY_V4, SR_POLICY_V6], ids=['afi-1', 'afi-2'])
@pytest.mark.parametrize('size', [0, 8, 12, 20, 24, 48])
def test_a_next_hop_length_the_section_does_not_name_is_refused(family: FamilyTuple, size: int) -> None:
    """Four, sixteen and thirty-two are the only lengths 2.1 gives: accepting all fails here."""
    with pytest.raises(Notify) as raised:
        MPRNLRI.unpack_attribute(sr_policy_reach(family, bytes(range(1, size + 1))), sr_policy_session())
    assert (raised.value.code, raised.value.subcode) == (3, 9)


def sent_next_hop(afi: AFI, next_hop: str) -> bytes:
    """The Next Hop field of the MP_REACH_NLRI the encoder produces for one SR Policy route."""
    nlri = SRPolicyNLRI.create(afi, 1, 2, str(IP.create_ip(ENDPOINT[afi])))
    collection = MPNLRICollection.from_routed([RoutedNLRI(nlri, IP.from_string(next_hop))], {}, afi, SAFI.sr_policy)
    (attribute,) = collection.packed_reach_attributes(sr_policy_session())
    header = 4 if attribute[0] & 0x10 else 3
    length = attribute[header + 3]
    return bytes(attribute[header + 4 : header + 4 + length])


@pytest.mark.rfc('rfc9830#2.1-next-hop-independent-of-afi')
def test_an_sr_policy_route_is_sent_with_the_next_hop_of_either_protocol_on_either_afi() -> None:
    """Four octets for IPv4, sixteen for IPv6, whatever the AFI: no IPv4-mapped address."""
    assert sent_next_hop(AFI.ipv4, '192.0.2.1') == NEXT_HOP_V4
    assert sent_next_hop(AFI.ipv4, '2001:db8::2') == NEXT_HOP_GLOBAL
    assert sent_next_hop(AFI.ipv6, '192.0.2.1') == NEXT_HOP_V4
    assert sent_next_hop(AFI.ipv6, '2001:db8::2') == NEXT_HOP_GLOBAL


# ------------------------------------- sections 4.2.1 and 5, what an SR Policy update must carry
#
# NO_ADVERTISE or a Route Target in IPv4-address format, and a Tunnel Encapsulation attribute
# with an SR Policy TLV, or the update is malformed and handled by treat-as-withdraw.  Read
# on an iBGP session, where RFC 9012 11 keeps the Tunnel Encapsulation attribute.

NO_ADVERTISE = bytes([0xC0, 8, 4]) + pack('!L', 0xFFFFFF02)
NO_EXPORT = bytes([0xC0, 8, 4]) + pack('!L', 0xFFFFFF01)
# type 0x01 subtype 0x02: a Route Target, IPv4-address format, 192.0.2.1:7
RT_IPV4 = bytes([0xC0, 16, 8, 0x01, 0x02, 192, 0, 2, 1, 0, 7])
# type 0x00 subtype 0x02: a Route Target, two octet AS format, 65000:7
RT_AS = bytes([0xC0, 16, 8, 0x00, 0x02]) + pack('!HI', 65000, 7)
# both in one attribute, the IPv4 one second
RT_AS_THEN_IPV4 = bytes([0xC0, 16, 16]) + RT_AS[3:] + RT_IPV4[3:]
SR_POLICY_TLV = pack('!HH', SR_POLICY_TUNNEL, 8) + pack('!BB', 12, 6) + pack('!BBI', 0, 0, 100)
TUNNEL_SR_POLICY = bytes([0xC0, TUNNEL_ENCAP, len(SR_POLICY_TLV)]) + SR_POLICY_TLV
OTHER_TLV = pack('!HH', 1, 4) + b'\x01\x02\x03\x04'
TUNNEL_OTHER = bytes([0xC0, TUNNEL_ENCAP, len(OTHER_TLV)]) + OTHER_TLV


def sr_policy_update(*attributes: bytes) -> bytes:
    """An iBGP UPDATE announcing one IPv4 SR Policy route with these attributes."""
    reach = sr_policy_reach(SR_POLICY_V4, NEXT_HOP_V4)
    mp_reach = bytes([0x80, 14, len(reach)]) + reach
    body = bytes([0x40, 1, 1, 0]) + bytes([0x40, 2, 0]) + mp_reach + b''.join(attributes)
    return pack('!HH', 0, len(body)) + body


def announced(*attributes: bytes) -> bool:
    from exabgp.bgp.message.update import UpdateCollection

    update = UpdateCollection.unpack_message(sr_policy_update(*attributes), sr_policy_session())
    assert len(update.announces) + len(update.withdraws) == 1, 'the route is neither announced nor withdrawn'
    return bool(update.announces)


@pytest.mark.rfc('rfc9830#4.2.1-no-advertise-or-ipv4-route-target')
@pytest.mark.rfc('rfc9830#5-invalid-update-treat-as-withdraw', polarity='negative')
@pytest.mark.parametrize(
    'communities',
    [(NO_ADVERTISE,), (RT_IPV4,), (NO_ADVERTISE, RT_IPV4), (RT_AS_THEN_IPV4,)],
    ids=['no-advertise', 'ipv4-route-target', 'both', 'ipv4-route-target-second'],
)
def test_an_update_with_no_advertise_or_an_ipv4_route_target_is_announced(communities: tuple[bytes, ...]) -> None:
    assert announced(TUNNEL_SR_POLICY, *communities)


@pytest.mark.rfc('rfc9830#4.2.1-no-advertise-or-ipv4-route-target', polarity='negative')
@pytest.mark.rfc('rfc9830#5-invalid-update-treat-as-withdraw')
@pytest.mark.parametrize('communities', [(), (NO_EXPORT,), (RT_AS,)], ids=['none', 'no-export', 'as-route-target'])
def test_an_update_without_no_advertise_or_an_ipv4_route_target_is_withdrawn(communities: tuple[bytes, ...]) -> None:
    assert not announced(TUNNEL_SR_POLICY, *communities)


@pytest.mark.rfc('rfc9830#4.2.1-tunnel-encapsulation-attached')
def test_an_update_with_an_sr_policy_tunnel_is_announced() -> None:
    assert announced(NO_ADVERTISE, TUNNEL_SR_POLICY)


@pytest.mark.rfc('rfc9830#4.2.1-tunnel-encapsulation-attached', polarity='negative')
@pytest.mark.rfc('rfc9830#5-invalid-update-treat-as-withdraw')
@pytest.mark.parametrize('tunnel', [b'', TUNNEL_OTHER], ids=['no-attribute', 'no-sr-policy-tlv'])
def test_an_update_without_an_sr_policy_tunnel_is_withdrawn(tunnel: bytes) -> None:
    assert not announced(NO_ADVERTISE, tunnel)


# ------------------------------------------ sections 4.1 and 4.2.1, what we refuse to send

SR_POLICY_ROUTE = 'sr-policy distinguisher 0 color 100 endpoint 10.0.0.1 next-hop 192.0.2.1'
SR_POLICY_TUNNEL_WORDS = 'preference 100 segment-list weight 1 segment type-a mpls 16001'


def configured_sr_policy(route: str) -> tuple[bool, str]:
    """Whether a neighbour announcing this SR Policy route loads, and the error when not."""
    from exabgp.configuration.configuration import Configuration

    text = f"""
neighbor 192.0.2.2 {{
    router-id 192.0.2.1;
    local-address 192.0.2.1;
    local-as 65001;
    peer-as 65001;
    family {{ ipv4 sr-policy; }}
    announce {{ ipv4 {{ {route}; }} }}
}}
"""
    configuration = Configuration([text], text=True)
    loaded = configuration.reload()
    return bool(loaded), str(configuration.error)


@pytest.mark.rfc('rfc9830#4.1-no-advertise-without-route-target')
@pytest.mark.parametrize(
    'communities',
    ['community [ no-advertise ]', 'extended-community [ target:192.0.2.1:7 ]', 'community no-advertise'],
)
def test_an_sr_policy_route_with_no_advertise_or_an_ipv4_route_target_is_configured(communities: str) -> None:
    loaded, error = configured_sr_policy(f'{SR_POLICY_ROUTE} {SR_POLICY_TUNNEL_WORDS} {communities}')
    assert loaded, error


@pytest.mark.rfc('rfc9830#4.1-no-advertise-without-route-target', polarity='negative')
@pytest.mark.parametrize('communities', ['', 'community [ no-export ]', 'extended-community [ target:65000:7 ]'])
def test_an_sr_policy_route_without_no_advertise_or_an_ipv4_route_target_is_refused(communities: str) -> None:
    loaded, error = configured_sr_policy(f'{SR_POLICY_ROUTE} {SR_POLICY_TUNNEL_WORDS} {communities}')
    assert not loaded
    assert 'NO_ADVERTISE' in error and 'RFC 9830' in error, error


@pytest.mark.rfc('rfc9830#4.2.1-tunnel-encapsulation-attached', polarity='negative')
def test_an_sr_policy_route_without_a_tunnel_is_refused() -> None:
    loaded, error = configured_sr_policy(f'{SR_POLICY_ROUTE} community [ no-advertise ]')
    assert not loaded
    assert 'Tunnel Encapsulation' in error, error


def test_the_communities_of_an_sr_policy_route_are_kept_and_print_back() -> None:
    """Unmarked: the communities stay with the route, and the route prints as it was read."""
    from exabgp.configuration.configuration import Configuration
    from exabgp.configuration.grammar.tree.sr_policy import sr_policy_words

    def read(line: str) -> Any:
        configuration = Configuration([''], text=True)
        assert configuration.partial('ipv4', line, 'announce'), str(configuration.error)
        (route,) = configuration.pop_routes()
        return route

    communities = 'community [ no-advertise ] extended-community [ target:192.0.2.1:7 ]'
    route = read(f'{SR_POLICY_ROUTE} {SR_POLICY_TUNNEL_WORDS} {communities}')
    assert route.nlri.malformed_with(route.attributes) is None
    assert Attribute.CODE.COMMUNITY in route.attributes
    assert Attribute.CODE.EXTENDED_COMMUNITY in route.attributes
    printed = ' '.join(str(word) for word in sr_policy_words(route))
    again = read(f'sr-policy {printed}')
    assert again.attributes == route.attributes


def test_an_sr_policy_withdrawal_needs_no_community() -> None:
    """Unmarked: the rule is about an update which announces; a withdrawal carries no attribute."""
    from exabgp.configuration.configuration import Configuration

    configuration = Configuration([''], text=True)
    assert configuration.partial('ipv4', SR_POLICY_ROUTE, 'withdraw'), str(configuration.error)


# ---------------------------------------------- sections 2.4.1 to 2.4.8, one of each sub-TLV
#
# Preference, Binding SID, ENLP, Priority, Candidate Path Name and Policy Name each "MUST NOT
# appear more than once in the SR Policy encoding".  The configuration refused a second ENLP
# only; a second of any other was packed and sent.  What a receiver does with a repeat is
# RFC 9012 13's: the first is kept, the rest disregarded, and the route is not malformed.

NO_ADVERTISE_WORDS = 'community [ no-advertise ]'
SEGMENT_LIST = 'segment-list weight 1 segment type-a mpls 16001'
SINGLE_SUBTLVS = {
    'rfc9830#2.4.1-preference-once': ('preference 100', 'preference 200'),
    'rfc9830#2.4.2-binding-sid-once': ('binding-sid mpls 24000', 'binding-sid null'),
    'rfc9830#2.4.5-enlp-once': ('enlp push-ipv4', 'enlp no-push'),
    'rfc9830#2.4.6-priority-once': ('priority 10', 'priority 20'),
    'rfc9830#2.4.7-candidate-path-name-once': ('candidate-path-name first', 'candidate-path-name second'),
    'rfc9830#2.4.8-policy-name-once': ('policy-name first', 'policy-name second'),
}


@pytest.mark.rfc('rfc9830#2.4.1-preference-once')
@pytest.mark.rfc('rfc9830#2.4.2-binding-sid-once')
@pytest.mark.rfc('rfc9830#2.4.5-enlp-once')
@pytest.mark.rfc('rfc9830#2.4.6-priority-once')
@pytest.mark.rfc('rfc9830#2.4.7-candidate-path-name-once')
@pytest.mark.rfc('rfc9830#2.4.8-policy-name-once')
@pytest.mark.parametrize('first, second', list(SINGLE_SUBTLVS.values()))
def test_a_single_instance_sub_tlv_given_once_is_configured(first: str, second: str) -> None:
    loaded, error = configured_sr_policy(f'{SR_POLICY_ROUTE} {first} {SEGMENT_LIST} {NO_ADVERTISE_WORDS}')
    assert loaded, error


@pytest.mark.rfc('rfc9830#2.4.1-preference-once')
@pytest.mark.rfc('rfc9830#2.4.2-binding-sid-once')
@pytest.mark.rfc('rfc9830#2.4.5-enlp-once')
@pytest.mark.rfc('rfc9830#2.4.6-priority-once')
@pytest.mark.rfc('rfc9830#2.4.7-candidate-path-name-once')
@pytest.mark.rfc('rfc9830#2.4.8-policy-name-once')
@pytest.mark.parametrize('first, second', list(SINGLE_SUBTLVS.values()))
def test_a_single_instance_sub_tlv_given_twice_is_refused(first: str, second: str) -> None:
    loaded, error = configured_sr_policy(f'{SR_POLICY_ROUTE} {first} {SEGMENT_LIST} {second} {NO_ADVERTISE_WORDS}')
    assert not loaded
    assert 'only once' in error, error


@pytest.mark.rfc('rfc9830#2.4.1-preference-once', polarity='negative')
@pytest.mark.rfc('rfc9830#2.4.2-binding-sid-once', polarity='negative')
@pytest.mark.rfc('rfc9830#2.4.5-enlp-once', polarity='negative')
@pytest.mark.rfc('rfc9830#2.4.6-priority-once', polarity='negative')
@pytest.mark.rfc('rfc9830#2.4.7-candidate-path-name-once', polarity='negative')
@pytest.mark.rfc('rfc9830#2.4.8-policy-name-once', polarity='negative')
def test_a_repeat_received_is_disregarded_and_the_first_kept() -> None:
    from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy import (
        BindingSIDSubTLV,
        CandidatePathNameSubTLV,
        ENLPSubTLV,
        PolicyNameSubTLV,
        PreferenceSubTLV,
        PrioritySubTLV,
        SRPolicyTunnel,
    )

    pairs = [
        (PreferenceSubTLV(preference=100), PreferenceSubTLV(preference=200)),
        (BindingSIDSubTLV(label=24000), BindingSIDSubTLV(label=None)),
        (ENLPSubTLV(enlp=1), ENLPSubTLV(enlp=4)),
        (PrioritySubTLV(priority=10), PrioritySubTLV(priority=20)),
        (CandidatePathNameSubTLV(name='first'), CandidatePathNameSubTLV(name='second')),
        (PolicyNameSubTLV(name='first'), PolicyNameSubTLV(name='second')),
    ]
    for first, second in pairs:
        once = SRPolicyTunnel(subtlvs=[first])
        twice = SRPolicyTunnel.unpack(SRPolicyTunnel(subtlvs=[first, second]).pack_value())
        assert twice.json() == once.json(), type(first).__name__


# ------------------------------------------------- section 2.4.2, the label of a Binding SID


@pytest.mark.rfc('rfc9830#2.4.2-binding-sid-label-not-reserved')
@pytest.mark.parametrize('label', ['16', '24000', '1048575'])
def test_a_binding_sid_label_outside_the_reserved_range_is_configured(label: str) -> None:
    loaded, error = configured_sr_policy(
        f'{SR_POLICY_ROUTE} binding-sid mpls {label} {SEGMENT_LIST} {NO_ADVERTISE_WORDS}'
    )
    assert loaded, error


@pytest.mark.rfc('rfc9830#2.4.2-binding-sid-label-not-reserved', polarity='negative')
@pytest.mark.parametrize('label', ['0', '3', '15', '1048576'])
def test_a_reserved_or_too_large_binding_sid_label_is_refused(label: str) -> None:
    """A reserved label was sent as given; 1048576 failed with struct.error when packed."""
    loaded, error = configured_sr_policy(
        f'{SR_POLICY_ROUTE} binding-sid mpls {label} {SEGMENT_LIST} {NO_ADVERTISE_WORDS}'
    )
    assert not loaded
    assert 'binding-sid' in error, error


# --------------------------------------------- section 2.4.4.2.4, the structure of an SRv6 SID

SRV6_SEGMENT = 'segment-list weight 1 segment type-b srv6 fc00::1 endpoint-behavior 65 {lengths}'


@pytest.mark.rfc('rfc9830#2.4.4.2.4-sid-structure-at-most-128')
@pytest.mark.parametrize('lengths', ['32 16 16 0', '64 32 16 16', '128 0 0 0'])
def test_an_srv6_sid_structure_of_at_most_128_bits_is_configured(lengths: str) -> None:
    segment = SRV6_SEGMENT.format(lengths=lengths)
    loaded, error = configured_sr_policy(f'{SR_POLICY_ROUTE} {segment} {NO_ADVERTISE_WORDS}')
    assert loaded, error


@pytest.mark.rfc('rfc9830#2.4.4.2.4-sid-structure-at-most-128', polarity='negative')
@pytest.mark.parametrize('lengths', ['64 32 16 17', '129 0 0 0', '255 255 255 255', '256 0 0 0'])
def test_an_srv6_sid_structure_longer_than_128_bits_is_refused(lengths: str) -> None:
    segment = SRV6_SEGMENT.format(lengths=lengths)
    loaded, error = configured_sr_policy(f'{SR_POLICY_ROUTE} {segment} {NO_ADVERTISE_WORDS}')
    assert not loaded
    assert '128' in error, error
