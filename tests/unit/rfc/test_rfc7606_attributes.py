"""RFC 7606 section 7: the per-attribute table, row by row.

Section 7 is the part of the document with teeth.  For each existing path attribute it says
what counts as malformed and which of the three approaches applies, and almost every
sentence is a MUST or a SHALL.  tests/unit/test_rfc7606_prescribed_action.py pins the
action half of seven of those rows; this file pins the malformation half, the rows that
file does not reach, and the negative side of all of them.

Two rows fail and carry xfail:

  7.2  a Path Segment Length of zero is accepted instead of being treated as malformed
  7.3  a NEXT_HOP path attribute of sixteen bytes is accepted instead of being malformed

Three more rows - the "if received from an external neighbor, discard it" halves of 7.5,
7.9 and 7.10 - are recorded in qa/rfc/rfc7606.toml as gaps rather than tested, because the
ledger does not let a test claim a requirement we have admitted we do not meet.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute import Attribute

from rfc.rfc7606_wire import (
    EMPTY_AS_PATH,
    MANDATORY,
    NEXT_HOP,
    OPTIONAL,
    OPTIONAL_TRANSITIVE,
    ORIGIN_IGP,
    WELL_KNOWN_TRANSITIVE,
    announced,
    attribute,
    internal_session,
    mp_reach_ipv6,
    parse,
    session,
    update,
    withdrawn_routes,
)

CODE = Attribute.CODE
UPDATE_MESSAGE_ERROR = 3

ROUTE = ['10.0.0.0/24']


def withdrawn_by(attributes: bytes, internal: bool = False, asn4: bool = True) -> bool:
    """True when the UPDATE's route was withdrawn rather than advertised."""
    negotiated = internal_session(asn4=asn4) if internal else session(asn4=asn4)
    parsed = parse(update(attributes), negotiated)
    if announced(parsed) == ROUTE:
        return False
    assert withdrawn_routes(parsed) == ROUTE, 'the route was neither advertised nor withdrawn'
    return True


def kept(code: int, attributes: bytes, asn4: bool = True) -> bool:
    """True when the attribute survived the parse and the route is still advertised."""
    parsed = parse(update(attributes), session(asn4=asn4))
    assert announced(parsed) == ROUTE, f'the route was withdrawn, so this says nothing about {code:#x}'
    return code in parsed.attributes


# ------------------------------------------------------------------ 7.1 ORIGIN


@pytest.mark.rfc('rfc7606#7.1-origin-treat-as-withdraw')
@pytest.mark.parametrize('name,value', [('a length of 2', bytes(2)), ('an undefined value of 3', bytes([3]))])
def test_a_malformed_origin_withdraws_the_route(name: str, value: bytes) -> None:
    """Both halves of the malformation rule: the length, and the value."""
    assert withdrawn_by(attribute(WELL_KNOWN_TRANSITIVE, CODE.ORIGIN, value) + EMPTY_AS_PATH + NEXT_HOP), (
        f'an ORIGIN with {name} was accepted'
    )


@pytest.mark.rfc('rfc7606#7.1-origin-treat-as-withdraw', polarity='negative')
@pytest.mark.parametrize('value', [0, 1, 2])
def test_each_defined_origin_value_is_accepted(value: int) -> None:
    """IGP, EGP and INCOMPLETE are all defined, so none of them may be withdrawn."""
    assert not withdrawn_by(attribute(WELL_KNOWN_TRANSITIVE, CODE.ORIGIN, bytes([value])) + EMPTY_AS_PATH + NEXT_HOP)


# ------------------------------------------------------------------ 7.2 AS_PATH


@pytest.mark.rfc('rfc7606#7.2-as-path-treat-as-withdraw')
@pytest.mark.parametrize(
    'name,value',
    [
        ('an unrecognised segment type', bytes([9, 1, 0xFD, 0xE8])),
        ('a segment length past the attribute', bytes([2, 4, 0xFD, 0xE8])),
        ('a single octet where a segment header should be', bytes([2])),
    ],
)
def test_a_malformed_as_path_withdraws_the_route(name: str, value: bytes) -> None:
    assert withdrawn_by(ORIGIN_IGP + attribute(WELL_KNOWN_TRANSITIVE, CODE.AS_PATH, value) + NEXT_HOP), (
        f'an AS_PATH with {name} was accepted'
    )


@pytest.mark.rfc('rfc7606#7.2-as-path-treat-as-withdraw', polarity='negative')
def test_a_well_formed_as_path_is_accepted() -> None:
    """One AS_SEQUENCE of one ASN, in the two octet encoding this session negotiated."""
    as_path = attribute(WELL_KNOWN_TRANSITIVE, CODE.AS_PATH, bytes([2, 1, 0, 0, 0xFD, 0xE8]))
    assert not withdrawn_by(ORIGIN_IGP + as_path + NEXT_HOP), 'a well formed AS_PATH was treated as malformed'


@pytest.mark.rfc('rfc7606#7.2-zero-path-segment-length-is-malformed')
def test_a_path_segment_of_zero_length_withdraws_the_route() -> None:
    as_path = attribute(WELL_KNOWN_TRANSITIVE, CODE.AS_PATH, bytes([2, 0]))
    assert withdrawn_by(ORIGIN_IGP + as_path + NEXT_HOP), 'an AS_SEQUENCE of zero ASNs was accepted'


@pytest.mark.rfc('rfc7606#7.2-zero-path-segment-length-is-malformed', polarity='negative')
def test_a_path_segment_of_one_asn_is_not_malformed() -> None:
    """An AS_PATH attribute of zero LENGTH is legal, and is a different thing entirely."""
    as_path = attribute(WELL_KNOWN_TRANSITIVE, CODE.AS_PATH, bytes([2, 1, 0, 0, 0xFD, 0xE8]))
    assert not withdrawn_by(ORIGIN_IGP + as_path + NEXT_HOP)
    assert not withdrawn_by(MANDATORY), 'an empty AS_PATH attribute, which is legal, was withdrawn'


# ------------------------------------------------------------------ 7.3 NEXT_HOP


@pytest.mark.rfc('rfc7606#7.3-next-hop-treat-as-withdraw')
def test_a_malformed_next_hop_withdraws_the_route() -> None:
    assert withdrawn_by(ORIGIN_IGP + EMPTY_AS_PATH + attribute(WELL_KNOWN_TRANSITIVE, CODE.NEXT_HOP, bytes(3))), (
        'a three byte NEXT_HOP was accepted'
    )


@pytest.mark.rfc('rfc7606#7.3-next-hop-treat-as-withdraw', polarity='negative')
def test_a_four_byte_next_hop_is_accepted() -> None:
    assert not withdrawn_by(MANDATORY), 'a four byte NEXT_HOP was treated as malformed'


@pytest.mark.rfc('rfc7606#7.3-next-hop-malformed-if-not-four')
def test_a_sixteen_byte_next_hop_path_attribute_is_malformed() -> None:
    sixteen = attribute(WELL_KNOWN_TRANSITIVE, CODE.NEXT_HOP, bytes(16))
    assert withdrawn_by(ORIGIN_IGP + EMPTY_AS_PATH + sixteen), 'a sixteen byte NEXT_HOP was accepted'


@pytest.mark.rfc('rfc7606#7.3-next-hop-malformed-if-not-four', polarity='negative')
def test_a_next_hop_of_exactly_four_bytes_is_not_malformed() -> None:
    assert kept(CODE.NEXT_HOP, MANDATORY), 'a four byte NEXT_HOP was dropped'


# ------------------------------------------------------------------ 7.4 MULTI_EXIT_DISC


@pytest.mark.rfc('rfc7606#7.4-med-treat-as-withdraw')
@pytest.mark.parametrize('length', [0, 3, 5])
def test_a_malformed_med_withdraws_the_route(length: int) -> None:
    """MED is optional NON-transitive, so the flag is OPTIONAL alone or the length is never read."""
    assert withdrawn_by(MANDATORY + attribute(OPTIONAL, CODE.MED, bytes(length))), (
        f'a {length} byte MULTI_EXIT_DISC was accepted'
    )


@pytest.mark.rfc('rfc7606#7.4-med-treat-as-withdraw', polarity='negative')
def test_a_four_byte_med_is_accepted() -> None:
    assert kept(CODE.MED, MANDATORY + attribute(OPTIONAL, CODE.MED, bytes(4)))


# ------------------------------------------------------------------ 7.5 LOCAL_PREF


@pytest.mark.rfc('rfc7606#7.5-local-pref-internal-treat-as-withdraw')
@pytest.mark.parametrize('length', [0, 3, 5])
def test_a_malformed_local_pref_from_an_internal_neighbour_withdraws_the_route(length: int) -> None:
    attributes = MANDATORY + attribute(WELL_KNOWN_TRANSITIVE, CODE.LOCAL_PREF, bytes(length))
    assert withdrawn_by(attributes, internal=True), f'a {length} byte LOCAL_PREF from an IBGP peer was accepted'


@pytest.mark.rfc('rfc7606#7.5-local-pref-internal-treat-as-withdraw', polarity='negative')
def test_a_four_byte_local_pref_from_an_internal_neighbour_is_accepted() -> None:
    attributes = MANDATORY + attribute(WELL_KNOWN_TRANSITIVE, CODE.LOCAL_PREF, bytes(4))
    parsed = parse(update(attributes), internal_session())

    assert announced(parsed) == ROUTE
    assert CODE.LOCAL_PREF in parsed.attributes, 'a well formed LOCAL_PREF from an IBGP peer was dropped'


# ------------------------------------------------------------------ 7.6 ATOMIC_AGGREGATE


@pytest.mark.rfc('rfc7606#7.6-atomic-aggregate-malformed-if-not-zero-length')
@pytest.mark.parametrize('length', [1, 4])
def test_an_atomic_aggregate_with_a_length_is_malformed(length: int) -> None:
    attributes = MANDATORY + attribute(WELL_KNOWN_TRANSITIVE, CODE.ATOMIC_AGGREGATE, bytes(length))
    assert not kept(CODE.ATOMIC_AGGREGATE, attributes), f'a {length} byte ATOMIC_AGGREGATE was kept'


@pytest.mark.rfc('rfc7606#7.6-atomic-aggregate-malformed-if-not-zero-length', polarity='negative')
def test_an_empty_atomic_aggregate_is_not_malformed() -> None:
    attributes = MANDATORY + attribute(WELL_KNOWN_TRANSITIVE, CODE.ATOMIC_AGGREGATE, b'')
    assert kept(CODE.ATOMIC_AGGREGATE, attributes), 'a zero length ATOMIC_AGGREGATE, which is correct, was dropped'


@pytest.mark.rfc('rfc7606#7.6-atomic-aggregate-attribute-discard', polarity='negative')
def test_a_malformed_atomic_aggregate_does_not_withdraw_the_route() -> None:
    """Attribute discard, not treat-as-withdraw: telling the two apart is the point."""
    attributes = MANDATORY + attribute(WELL_KNOWN_TRANSITIVE, CODE.ATOMIC_AGGREGATE, bytes(4))
    assert not withdrawn_by(attributes), 'a malformed ATOMIC_AGGREGATE withdrew the route'


# ------------------------------------------------------------------ 7.7 AGGREGATOR


@pytest.mark.rfc('rfc7606#7.7-aggregator-length-six-or-eight')
@pytest.mark.parametrize(
    'asn4,length',
    [(True, 6), (True, 7), (False, 7), (False, 8)],
)
def test_an_aggregator_of_the_wrong_length_for_the_negotiation_is_malformed(asn4: bool, length: int) -> None:
    """Six is right without the four octet AS capability and wrong with it, and the reverse."""
    attributes = MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.AGGREGATOR, bytes(length))
    assert not kept(CODE.AGGREGATOR, attributes, asn4=asn4), (
        f'a {length} byte AGGREGATOR was kept on a session with asn4={asn4}'
    )


@pytest.mark.rfc('rfc7606#7.7-aggregator-length-six-or-eight', polarity='negative')
@pytest.mark.parametrize('asn4,length', [(True, 8), (False, 6)])
def test_an_aggregator_of_the_right_length_for_the_negotiation_is_kept(asn4: bool, length: int) -> None:
    attributes = MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.AGGREGATOR, bytes(length))
    assert kept(CODE.AGGREGATOR, attributes, asn4=asn4), (
        f'a {length} byte AGGREGATOR was discarded on a session with asn4={asn4}'
    )


@pytest.mark.rfc('rfc7606#7.7-aggregator-attribute-discard', polarity='negative')
def test_a_malformed_aggregator_does_not_withdraw_the_route() -> None:
    attributes = MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.AGGREGATOR, bytes(7))
    assert not withdrawn_by(attributes), 'a malformed AGGREGATOR withdrew the route'


# ------------------------------------------------------------------ 7.8 Community


@pytest.mark.rfc('rfc7606#7.8-community-non-zero-multiple-of-four')
@pytest.mark.parametrize('length', [0, 1, 5, 7])
def test_a_community_attribute_of_the_wrong_length_is_malformed(length: int) -> None:
    """Zero is malformed too: the RFC says a NON-ZERO multiple of four."""
    assert withdrawn_by(MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.COMMUNITY, bytes(length))), (
        f'a {length} byte COMMUNITY was accepted'
    )


@pytest.mark.rfc('rfc7606#7.8-community-non-zero-multiple-of-four', polarity='negative')
@pytest.mark.parametrize('length', [4, 8, 12])
def test_a_community_attribute_of_a_legal_length_is_accepted(length: int) -> None:
    assert kept(CODE.COMMUNITY, MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.COMMUNITY, bytes(length)))


@pytest.mark.rfc('rfc7606#7.8-community-treat-as-withdraw', polarity='negative')
def test_a_well_formed_community_attribute_does_not_withdraw_the_route() -> None:
    assert not withdrawn_by(MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.COMMUNITY, bytes(4)))


# ------------------------------------------------------------------ 7.9 ORIGINATOR_ID


@pytest.mark.rfc('rfc7606#7.9-originator-id-internal-treat-as-withdraw')
@pytest.mark.parametrize('length', [0, 3, 5])
def test_a_malformed_originator_id_from_an_internal_neighbour_withdraws_the_route(length: int) -> None:
    attributes = MANDATORY + attribute(OPTIONAL, CODE.ORIGINATOR_ID, bytes(length))
    assert withdrawn_by(attributes, internal=True), f'a {length} byte ORIGINATOR_ID from an IBGP peer was accepted'


@pytest.mark.rfc('rfc7606#7.9-originator-id-internal-treat-as-withdraw', polarity='negative')
def test_a_four_byte_originator_id_from_an_internal_neighbour_is_accepted() -> None:
    attributes = MANDATORY + attribute(OPTIONAL, CODE.ORIGINATOR_ID, bytes(4))
    parsed = parse(update(attributes), internal_session())

    assert announced(parsed) == ROUTE
    assert CODE.ORIGINATOR_ID in parsed.attributes, 'a well formed ORIGINATOR_ID from an IBGP peer was dropped'


# ------------------------------------------------------------------ 7.10 CLUSTER_LIST


@pytest.mark.rfc('rfc7606#7.10-cluster-list-internal-treat-as-withdraw')
@pytest.mark.parametrize('length', [0, 3, 5])
def test_a_malformed_cluster_list_from_an_internal_neighbour_withdraws_the_route(length: int) -> None:
    """Zero is malformed here as well: a non-zero multiple of four, not a multiple of four."""
    attributes = MANDATORY + attribute(OPTIONAL, CODE.CLUSTER_LIST, bytes(length))
    assert withdrawn_by(attributes, internal=True), f'a {length} byte CLUSTER_LIST from an IBGP peer was accepted'


@pytest.mark.rfc('rfc7606#7.10-cluster-list-internal-treat-as-withdraw', polarity='negative')
@pytest.mark.parametrize('length', [4, 8])
def test_a_cluster_list_of_a_legal_length_from_an_internal_neighbour_is_accepted(length: int) -> None:
    attributes = MANDATORY + attribute(OPTIONAL, CODE.CLUSTER_LIST, bytes(length))
    parsed = parse(update(attributes), internal_session())

    assert announced(parsed) == ROUTE
    assert CODE.CLUSTER_LIST in parsed.attributes, f'a {length} byte CLUSTER_LIST was dropped'


# ------------------------------------------------------------------ 7.11 MP_REACH_NLRI


@pytest.mark.rfc('rfc7606#7.11-mp-reach-next-hop-session-reset')
@pytest.mark.parametrize('next_hop_length', [7, 8, 20])
def test_an_unusable_mp_reach_next_hop_length_resets_the_session(next_hop_length: int) -> None:
    """The next hop precedes the NLRI, so a wrong length loses the place in the attribute."""
    payload = update(ORIGIN_IGP + EMPTY_AS_PATH + mp_reach_ipv6(next_hop_length=next_hop_length), nlri=b'')

    with pytest.raises(Notify) as raised:
        parse(payload, session())

    assert raised.value.code == UPDATE_MESSAGE_ERROR, (
        f'a next hop length of {next_hop_length} gave error code {raised.value.code}'
    )


@pytest.mark.rfc('rfc7606#7.11-mp-reach-next-hop-session-reset', polarity='negative')
def test_an_expected_mp_reach_next_hop_length_does_not_reset_the_session() -> None:
    """Sixteen is what an IPv6 unicast next hop is, so this one has to survive."""
    parsed = parse(update(ORIGIN_IGP + EMPTY_AS_PATH + mp_reach_ipv6(next_hop_length=16), nlri=b''), session())

    assert announced(parsed) == ['::/64'], 'a well formed MP_REACH_NLRI was refused'


# ------------------------------------------------------- 7.14 Extended Community


@pytest.mark.rfc('rfc7606#7.14-extended-community-non-zero-multiple-of-eight')
@pytest.mark.parametrize('length', [0, 1, 9, 15])
def test_an_extended_community_of_the_wrong_length_is_malformed(length: int) -> None:
    assert withdrawn_by(MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.EXTENDED_COMMUNITY, bytes(length))), (
        f'a {length} byte EXTENDED_COMMUNITY was accepted'
    )


@pytest.mark.rfc('rfc7606#7.14-extended-community-non-zero-multiple-of-eight', polarity='negative')
@pytest.mark.parametrize('length', [8, 16])
def test_an_extended_community_of_a_legal_length_is_accepted(length: int) -> None:
    attributes = MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.EXTENDED_COMMUNITY, bytes(length))
    assert kept(CODE.EXTENDED_COMMUNITY, attributes)


@pytest.mark.rfc('rfc7606#7.14-extended-community-treat-as-withdraw', polarity='negative')
def test_a_well_formed_extended_community_does_not_withdraw_the_route() -> None:
    assert not withdrawn_by(MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.EXTENDED_COMMUNITY, bytes(8)))


@pytest.mark.rfc('rfc7606#7.14-unrecognised-extended-community-type-not-an-error')
@pytest.mark.parametrize('type_byte,sub_type', [(0x3F, 0x3F), (0x7F, 0x7F)])
def test_an_unrecognised_extended_community_type_is_kept(type_byte: int, sub_type: int) -> None:
    value = bytes([type_byte, sub_type]) + bytes(6)
    attributes = MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.EXTENDED_COMMUNITY, value)

    assert kept(CODE.EXTENDED_COMMUNITY, attributes), (
        f'type {type_byte:#x} sub-type {sub_type:#x} was treated as an error'
    )


@pytest.mark.rfc('rfc7606#7.14-unrecognised-extended-community-type-not-an-error', polarity='negative')
def test_an_unrecognised_extended_community_type_does_not_excuse_a_bad_length() -> None:
    """Accepting the type is not the same as accepting the attribute: the length still binds."""
    value = bytes([0x3F, 0x3F]) + bytes(7)
    assert withdrawn_by(MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.EXTENDED_COMMUNITY, value)), (
        'a nine byte EXTENDED_COMMUNITY was accepted because its type was unrecognised'
    )


# ------------------------- 7.15 IPv6 Address Specific Extended Community


@pytest.mark.rfc('rfc7606#7.15-ipv6-extended-community-non-zero-multiple-of-twenty')
@pytest.mark.parametrize('length', [0, 1, 19, 21])
def test_an_ipv6_extended_community_of_the_wrong_length_is_malformed(length: int) -> None:
    attributes = MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.IPV6_EXTENDED_COMMUNITY, bytes(length))
    assert withdrawn_by(attributes), f'a {length} byte IPv6 extended community was accepted'


@pytest.mark.rfc('rfc7606#7.15-ipv6-extended-community-non-zero-multiple-of-twenty', polarity='negative')
@pytest.mark.parametrize('length', [20, 40])
def test_an_ipv6_extended_community_of_a_legal_length_is_accepted(length: int) -> None:
    attributes = MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.IPV6_EXTENDED_COMMUNITY, bytes(length))
    assert kept(CODE.IPV6_EXTENDED_COMMUNITY, attributes)


@pytest.mark.rfc('rfc7606#7.15-ipv6-extended-community-treat-as-withdraw', polarity='negative')
def test_a_well_formed_ipv6_extended_community_does_not_withdraw_the_route() -> None:
    attributes = MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.IPV6_EXTENDED_COMMUNITY, bytes(20))
    assert not withdrawn_by(attributes)


@pytest.mark.rfc('rfc7606#7.15-unrecognised-ipv6-extended-community-type-not-an-error')
@pytest.mark.parametrize('type_byte,sub_type', [(0x3F, 0x3F), (0x7F, 0x7F)])
def test_an_unrecognised_ipv6_extended_community_type_is_kept(type_byte: int, sub_type: int) -> None:
    value = bytes([type_byte, sub_type]) + bytes(18)
    attributes = MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.IPV6_EXTENDED_COMMUNITY, value)

    assert kept(CODE.IPV6_EXTENDED_COMMUNITY, attributes), (
        f'type {type_byte:#x} sub-type {sub_type:#x} was treated as an error'
    )


@pytest.mark.rfc('rfc7606#7.15-unrecognised-ipv6-extended-community-type-not-an-error', polarity='negative')
def test_an_unrecognised_ipv6_extended_community_type_does_not_excuse_a_bad_length() -> None:
    value = bytes([0x3F, 0x3F]) + bytes(19)
    attributes = MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.IPV6_EXTENDED_COMMUNITY, value)
    assert withdrawn_by(attributes), (
        'a twenty one byte IPv6 extended community was accepted because its type was unrecognised'
    )
