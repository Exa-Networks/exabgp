"""RFC 7606 section 5: finding the NLRI in an UPDATE whose attributes cannot be trusted.

Treat-as-withdraw only works if the NLRI can still be read, so section 5 is about keeping
them findable.  It has two halves, and they pull in opposite directions on purpose:

  5.1 constrains what we SEND, so that a receiver with a malformed attribute in its hands
      can locate the NLRI without walking the attribute list, and then says in the very
      next sentence that we MUST accept a peer which ignores all of it.
  5.2, 5.3 and 5.4 constrain what we do with what we RECEIVE.

Both receiving side requirements which used to carry xfail are met: an UPDATE with no
reachable NLRI and a treat-as-withdraw error now resets the session, and an announced EVPN
or MVPN route of an unknown type is discarded (and logged) rather than kept as a
GenericEVPN / GenericMVPN.  A withdrawal of one is still decoded and reported.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update import UpdateCollection
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP

from rfc.rfc7606_wire import (
    EMPTY_AS_PATH,
    IPV4_PREFIX,
    MANDATORY,
    NEXT_HOP,
    OPTIONAL,
    OPTIONAL_TRANSITIVE,
    ORIGIN_IGP,
    OTHER_IPV4_PREFIX,
    WELL_KNOWN_TRANSITIVE,
    announced,
    attribute,
    mp_reach_ipv6,
    mp_unreach_ipv6,
    parse,
    session,
    update,
    withdrawn_routes,
)

CODE = Attribute.CODE

UPDATE_MESSAGE_ERROR = 3
MALFORMED_ATTRIBUTE_LIST = 1
OPTIONAL_ATTRIBUTE_ERROR = 9
INVALID_NETWORK_FIELD = 10

BGP_HEADER_SIZE = 19

MALFORMED_MED = attribute(OPTIONAL, CODE.MED, bytes(3))
MALFORMED_ATOMIC = attribute(WELL_KNOWN_TRANSITIVE, CODE.ATOMIC_AGGREGATE, bytes(4))

# a route type neither EVPN (RFC 7432 and successors) nor MVPN (RFC 6514) registers, as the
# type and length octets both families put in front of every route
UNKNOWN_ROUTE_TYPE = 0x7F
UNKNOWN_TYPED_ROUTE = bytes([UNKNOWN_ROUTE_TYPE, 4]) + bytes([1, 2, 3, 4])


def routed(prefix: str) -> RoutedNLRI:
    """One route with a next hop of its own family, ready to be packed."""
    address, mask = prefix.split('/')
    ip = IP.from_string(address)
    nlri = INET.from_cidr(CIDR.create_cidr(ip.pack_ip(), int(mask)), ip.afi, SAFI.unicast)
    return RoutedNLRI(nlri, IP.from_string('192.0.2.1' if ip.afi == AFI.ipv4 else '2001:db8::ffff'))


def typed_session(afi: AFI, safi: SAFI) -> Negotiated:
    """An EBGP session which negotiated the typed family on top of IPv4 and IPv6 unicast."""
    negotiated = session()
    negotiated.families = negotiated.families + [(afi, safi)]
    return negotiated


def mp_reach_typed(afi: AFI, safi: SAFI, routes: bytes) -> bytes:
    """An MP_REACH_NLRI for a typed family, with an IPv4 next hop and the given routes."""
    payload = pack('!HB', int(afi), int(safi)) + bytes([4, 192, 0, 2, 1]) + bytes([0]) + routes
    return attribute(OPTIONAL, CODE.MP_REACH_NLRI, payload)


def sections(message: bytes) -> tuple[int, list[int], int]:
    """Split one generated UPDATE into (withdrawn length, attribute codes, NLRI length)."""
    body = message[BGP_HEADER_SIZE:]
    withdrawn_length = int.from_bytes(body[0:2], 'big')
    attributes_start = 4 + withdrawn_length
    attributes_length = int.from_bytes(body[2 + withdrawn_length : attributes_start], 'big')
    attributes = body[attributes_start : attributes_start + attributes_length]
    nlri = body[attributes_start + attributes_length :]

    codes: list[int] = []
    offset = 0
    while offset < len(attributes):
        flag, code = attributes[offset], attributes[offset + 1]
        if flag & Attribute.Flag.EXTENDED_LENGTH:
            length = int.from_bytes(attributes[offset + 2 : offset + 4], 'big')
            offset += 4
        else:
            length = attributes[offset + 2]
            offset += 3
        codes.append(code)
        offset += length

    return withdrawn_length, codes, len(nlri)


def generated(announces: list[RoutedNLRI], withdraws: list[NLRI]) -> list[tuple[int, list[int], int]]:
    """Every UPDATE UpdateCollection.messages produces for these routes, dissected."""
    collection = UpdateCollection(announces, withdraws, AttributeCollection())
    return [sections(message) for message in collection.messages(session())]


# ------------------------------------------------------------------ 5.1


@pytest.mark.rfc('rfc7606#5.1-mp-nlri-encoded-first')
def test_we_send_the_mp_nlri_attribute_before_any_other() -> None:
    for _, codes, _ in generated([routed('2001:db8::1/128')], []):
        assert codes, 'an UPDATE was generated with no attributes at all'
        assert codes[0] in (CODE.MP_REACH_NLRI, CODE.MP_UNREACH_NLRI), (
            f'the first attribute we sent was {Attribute.CODE.name(codes[0])}, '
            f'and RFC 7606 5.1 says the MP NLRI attribute goes first'
        )


@pytest.mark.rfc('rfc7606#5.1-one-nlri-field-per-update')
def test_we_never_send_two_of_the_four_nlri_carriers_in_one_update() -> None:
    for withdrawn_length, codes, nlri_length in generated([routed('10.0.0.0/24')], [routed('10.0.1.0/24').nlri]):
        carriers = [
            'withdrawn routes' if withdrawn_length else '',
            'NLRI' if nlri_length else '',
            'MP_REACH_NLRI' if CODE.MP_REACH_NLRI in codes else '',
            'MP_UNREACH_NLRI' if CODE.MP_UNREACH_NLRI in codes else '',
        ]
        present = [name for name in carriers if name]
        assert len(present) <= 1, f'one UPDATE carried {" and ".join(present)}'


@pytest.mark.rfc('rfc7606#5.1-one-nlri-field-per-update')
def test_we_never_send_an_mp_reach_and_an_mp_unreach_in_one_update() -> None:
    """The same rule for the two attribute carriers, which used to be packed together."""
    announce = routed('2001:db8::1/128')
    withdraw = routed('2001:db8::2/128').nlri
    produced = generated([announce], [withdraw])

    assert len(produced) == 2, f'an IPv6 announce and an IPv6 withdraw made {len(produced)} messages'
    for _, codes, _ in produced:
        both = CODE.MP_REACH_NLRI in codes and CODE.MP_UNREACH_NLRI in codes
        assert not both, 'one UPDATE carried MP_REACH_NLRI and MP_UNREACH_NLRI'


@pytest.mark.rfc('rfc7606#5.1-one-nlri-field-per-update')
def test_splitting_the_carriers_apart_did_not_stop_us_batching() -> None:
    """One message per carrier, not one message per prefix: a table load depends on it."""
    announces = [routed(f'10.0.{index}.0/24') for index in range(100)]
    withdraws = [routed(f'10.1.{index}.0/24').nlri for index in range(100)]
    produced = generated(announces, withdraws)

    assert len(produced) == 2, f'200 IPv4 prefixes were spread over {len(produced)} messages'
    assert [(bool(withdrawn), bool(nlri)) for withdrawn, _, nlri in produced] == [(True, False), (False, True)], (
        'the withdrawals must be sent before the announcements, each in one message of its own'
    )


@pytest.mark.rfc('rfc7606#5.1-accept-any-position-or-combination')
def test_we_accept_an_mp_reach_which_is_not_the_first_attribute() -> None:
    """A peer which orders its attributes the old way is not in error."""
    parsed = parse(update(ORIGIN_IGP + EMPTY_AS_PATH + mp_reach_ipv6(), nlri=b''), session())

    assert announced(parsed) == ['::/64'], 'an MP_REACH after ORIGIN and AS_PATH was not accepted'


@pytest.mark.rfc('rfc7606#5.1-accept-any-position-or-combination')
def test_we_accept_a_withdrawn_routes_field_and_an_nlri_field_in_one_update() -> None:
    """Two of the four carriers at once, which 5.1 forbids sending and requires accepting."""
    parsed = parse(update(MANDATORY, nlri=OTHER_IPV4_PREFIX, withdrawn=IPV4_PREFIX), session())

    assert announced(parsed) == ['10.0.1.0/24'], 'the NLRI field was lost when a withdrawal shared the message'
    assert withdrawn_routes(parsed) == ['10.0.0.0/24'], 'the withdrawn field was lost when an NLRI shared the message'


@pytest.mark.rfc('rfc7606#5.1-accept-any-position-or-combination')
def test_we_accept_an_mp_reach_and_an_mp_unreach_in_one_update() -> None:
    parsed = parse(update(ORIGIN_IGP + EMPTY_AS_PATH + mp_reach_ipv6() + mp_unreach_ipv6(mask=48), nlri=b''), session())

    assert announced(parsed) == ['::/64']
    assert withdrawn_routes(parsed) == ['::/48']


# ------------------------------------------------------------------ 5.2


@pytest.mark.rfc('rfc7606#5.2-session-reset-when-no-reachable-nlri')
def test_a_treat_as_withdraw_error_with_no_reachable_nlri_resets_the_session() -> None:
    """There are no routes to withdraw, and no proof the NLRI field was read correctly."""
    payload = update(attribute(WELL_KNOWN_TRANSITIVE, CODE.ORIGIN, bytes(2)) + EMPTY_AS_PATH, nlri=b'')

    with pytest.raises(Notify) as raised:
        parse(payload, session())

    assert raised.value.code == UPDATE_MESSAGE_ERROR


@pytest.mark.rfc('rfc7606#5.2-session-reset-when-no-reachable-nlri')
def test_a_treat_as_withdraw_error_beside_only_withdrawn_routes_resets_the_session() -> None:
    """Withdrawn routes are not reachable NLRI, so they do not make the UPDATE safe to process."""
    payload = update(
        attribute(WELL_KNOWN_TRANSITIVE, CODE.ORIGIN, bytes(2)) + EMPTY_AS_PATH, nlri=b'', withdrawn=IPV4_PREFIX
    )

    with pytest.raises(Notify) as raised:
        parse(payload, session())

    assert raised.value.code == UPDATE_MESSAGE_ERROR


@pytest.mark.rfc('rfc7606#5.2-session-reset-when-no-reachable-nlri', polarity='negative')
def test_a_treat_as_withdraw_error_with_reachable_nlri_does_not_reset_the_session() -> None:
    """The reset is for an UPDATE with nothing to withdraw: with a route, the route is withdrawn."""
    parsed = parse(
        update(attribute(WELL_KNOWN_TRANSITIVE, CODE.ORIGIN, bytes(2)) + EMPTY_AS_PATH + NEXT_HOP), session()
    )

    assert announced(parsed) == []
    assert withdrawn_routes(parsed) == ['10.0.0.0/24']


@pytest.mark.rfc('rfc7606#5.2-session-reset-when-no-reachable-nlri', polarity='negative')
def test_an_attribute_discard_error_with_no_reachable_nlri_does_not_reset_the_session() -> None:
    """The RFC exempts attribute discard by name: the UPDATE is processed, no reset."""
    parsed = parse(update(ORIGIN_IGP + EMPTY_AS_PATH + MALFORMED_ATOMIC, nlri=b''), session())

    assert CODE.ATOMIC_AGGREGATE not in parsed.attributes, 'the malformed attribute was kept'
    assert announced(parsed) == []
    assert withdrawn_routes(parsed) == []


# ------------------------------------------------------------------ 5.3


@pytest.mark.rfc('rfc7606#5.3-nlri-field-syntactic-correctness')
@pytest.mark.parametrize(
    'name,nlri',
    [
        ('an IPv4 NLRI with a mask of 33', bytes([33, 10, 0, 0, 0])),
        ('a last NLRI longer than the data left', IPV4_PREFIX + bytes([24, 10, 0])),
    ],
)
def test_a_syntactically_incorrect_nlri_field_is_refused(name: str, nlri: bytes) -> None:
    with pytest.raises(Notify) as raised:
        parse(update(MANDATORY, nlri=nlri), session())

    assert (raised.value.code, raised.value.subcode) == (UPDATE_MESSAGE_ERROR, INVALID_NETWORK_FIELD), (
        f'{name} gave {raised.value.code}/{raised.value.subcode}'
    )


@pytest.mark.rfc('rfc7606#5.3-nlri-field-syntactic-correctness', polarity='negative')
def test_a_syntactically_correct_nlri_field_is_accepted() -> None:
    parsed = parse(update(MANDATORY, nlri=IPV4_PREFIX + OTHER_IPV4_PREFIX), session())

    assert announced(parsed) == ['10.0.0.0/24', '10.0.1.0/24'], 'a well formed pair of NLRI was refused'


@pytest.mark.rfc('rfc7606#5.3-mp-attribute-nlri-lengths')
@pytest.mark.parametrize(
    'name,attributes',
    [
        ('an IPv6 NLRI with a mask of 129', mp_reach_ipv6(mask=129)),
        (
            'a last NLRI longer than the attribute',
            attribute(
                OPTIONAL,
                CODE.MP_REACH_NLRI,
                bytes([0, 2, 1, 16]) + bytes(16) + bytes([0]) + bytes([64]) + bytes(4),
            ),
        ),
    ],
)
def test_an_mp_attribute_with_an_impossible_nlri_length_is_refused(name: str, attributes: bytes) -> None:
    with pytest.raises(Notify) as raised:
        parse(update(ORIGIN_IGP + EMPTY_AS_PATH + attributes, nlri=b''), session())

    assert (raised.value.code, raised.value.subcode) == (UPDATE_MESSAGE_ERROR, INVALID_NETWORK_FIELD), (
        f'{name} gave {raised.value.code}/{raised.value.subcode}'
    )


@pytest.mark.rfc('rfc7606#5.3-mp-attribute-nlri-lengths', polarity='negative')
def test_an_mp_attribute_whose_nlri_lengths_are_consistent_is_accepted() -> None:
    parsed = parse(update(ORIGIN_IGP + EMPTY_AS_PATH + mp_reach_ipv6(mask=48), nlri=b''), session())

    assert announced(parsed) == ['::/48'], 'a well formed MP_REACH was refused'


@pytest.mark.rfc('rfc7606#5.3-mp-attribute-flags-must-match-rfc4760')
def test_an_mp_reach_with_the_wrong_attribute_flags_is_not_silently_dropped() -> None:
    """RFC 4760 makes both MP attributes optional non-transitive; the peer sets transitive."""
    wrong_flags = attribute(
        OPTIONAL_TRANSITIVE,
        CODE.MP_REACH_NLRI,
        bytes([0, 2, 1, 16]) + bytes(16) + bytes([0]) + bytes([64]) + bytes(8),
    )
    payload = update(ORIGIN_IGP + EMPTY_AS_PATH + wrong_flags, nlri=b'')

    with pytest.raises(Notify) as raised:
        parse(payload, session())

    assert raised.value.code == UPDATE_MESSAGE_ERROR


@pytest.mark.rfc('rfc7606#5.3-mp-attribute-flags-must-match-rfc4760', polarity='negative')
def test_an_mp_reach_with_the_flags_rfc4760_specifies_is_accepted() -> None:
    parsed = parse(update(ORIGIN_IGP + EMPTY_AS_PATH + mp_reach_ipv6(), nlri=b''), session())

    assert announced(parsed) == ['::/64'], 'an optional non-transitive MP_REACH was refused'


@pytest.mark.rfc('rfc7606#5.3-mp-minimum-attribute-length')
@pytest.mark.parametrize(
    'name,attributes',
    [
        ('an MP_REACH_NLRI of 4 bytes', attribute(OPTIONAL, CODE.MP_REACH_NLRI, bytes(4))),
        ('an MP_UNREACH_NLRI of 2 bytes', attribute(OPTIONAL, CODE.MP_UNREACH_NLRI, bytes(2))),
    ],
)
def test_an_mp_attribute_shorter_than_its_minimum_is_refused(name: str, attributes: bytes) -> None:
    with pytest.raises(Notify) as raised:
        parse(update(ORIGIN_IGP + EMPTY_AS_PATH + attributes, nlri=b''), session())

    assert (raised.value.code, raised.value.subcode) == (UPDATE_MESSAGE_ERROR, OPTIONAL_ATTRIBUTE_ERROR), (
        f'{name} gave {raised.value.code}/{raised.value.subcode}'
    )


@pytest.mark.rfc('rfc7606#5.3-mp-minimum-attribute-length', polarity='negative')
def test_mp_attributes_at_or_above_their_minimum_are_accepted() -> None:
    parsed = parse(update(ORIGIN_IGP + EMPTY_AS_PATH + mp_unreach_ipv6(), nlri=b''), session())

    assert withdrawn_routes(parsed) == ['::/64'], 'an MP_UNREACH of legal length was refused'


# An empty MP attribute, and one whose Extended Length bit is set over a length of zero.
# Zero is one more length below the minimum, so the answer is the same 3/9 as for four
# octets. It used to be caught first by the zero length rule every attribute shares, which
# made it treat-as-withdraw: beside legacy NLRI the session stayed up, the IPv4 route was
# withdrawn, and whatever the MP attribute was meant to carry was never looked at.
EMPTY_MP_ATTRIBUTES = [
    ('an empty MP_REACH_NLRI', bytes([OPTIONAL, CODE.MP_REACH_NLRI, 0])),
    ('an empty MP_UNREACH_NLRI', bytes([OPTIONAL, CODE.MP_UNREACH_NLRI, 0])),
    (
        'an empty extended length MP_REACH_NLRI',
        bytes([OPTIONAL | Attribute.Flag.EXTENDED_LENGTH, CODE.MP_REACH_NLRI, 0, 0]),
    ),
]


@pytest.mark.rfc('rfc7606#5.3-mp-minimum-attribute-length')
@pytest.mark.rfc('rfc7606#3j-session-reset-when-nlri-cannot-be-parsed')
@pytest.mark.parametrize('nlri', [IPV4_PREFIX, b''], ids=['with-legacy-nlri', 'alone'])
@pytest.mark.parametrize('name,empty', EMPTY_MP_ATTRIBUTES, ids=[_[0] for _ in EMPTY_MP_ATTRIBUTES])
def test_an_empty_mp_attribute_is_an_optional_attribute_error(name: str, empty: bytes, nlri: bytes) -> None:
    """3/9 whatever else the UPDATE holds, with the attribute as the Data field (RFC 4271 6.3)."""
    with pytest.raises(Notify) as raised:
        parse(update(empty + MANDATORY, nlri=nlri), session())

    assert (raised.value.code, raised.value.subcode) == (UPDATE_MESSAGE_ERROR, OPTIONAL_ATTRIBUTE_ERROR), (
        f'{name} gave {raised.value.code}/{raised.value.subcode}'
    )
    assert raised.value.data == empty, f'{name}: the Data field was {raised.value.data.hex()}'


# An MP_REACH_NLRI which claims forty octets where four are left, and one whose header is
# cut after the flag, the type and the first octet of an extended length. Either way the
# NLRI it carries cannot be read, so RFC 7606 3 (j) puts the session reset back, which the
# treat-as-withdraw of section 4 otherwise standing for an overrun does not reach.
OVERRUNNING_MP_REACH = bytes([OPTIONAL, CODE.MP_REACH_NLRI, 40]) + pack('!HB', 2, 1) + bytes([16])
TRUNCATED_MP_REACH_HEADER = bytes([OPTIONAL | Attribute.Flag.EXTENDED_LENGTH, CODE.MP_REACH_NLRI, 0])
CUT_MP_ATTRIBUTES = [
    ('an MP_REACH_NLRI past the end of the attributes', OVERRUNNING_MP_REACH),
    ('an MP_REACH_NLRI with a truncated header', TRUNCATED_MP_REACH_HEADER),
    ('an MP_UNREACH_NLRI past the end of the attributes', bytes([OPTIONAL, CODE.MP_UNREACH_NLRI, 9, 0, 2])),
]


@pytest.mark.rfc('rfc7606#3j-session-reset-when-nlri-cannot-be-parsed')
@pytest.mark.parametrize('name,cut', CUT_MP_ATTRIBUTES, ids=[_[0] for _ in CUT_MP_ATTRIBUTES])
def test_an_mp_attribute_which_cannot_be_framed_resets_the_session(name: str, cut: bytes) -> None:
    """Beside legacy NLRI too: withdrawing only the IPv4 route kept the session on an MP attribute
    nobody could read."""
    with pytest.raises(Notify) as raised:
        parse(update(MANDATORY + cut), session())

    assert (raised.value.code, raised.value.subcode) == (UPDATE_MESSAGE_ERROR, OPTIONAL_ATTRIBUTE_ERROR), (
        f'{name} gave {raised.value.code}/{raised.value.subcode}'
    )
    assert raised.value.data == cut, f'{name}: the Data field was {raised.value.data.hex()}'


# ------------------------------------------------------------------ 5.4


@pytest.mark.rfc('rfc7606#5.4-unrecognised-typed-nlri-discarded')
@pytest.mark.parametrize(
    'afi,safi',
    [(AFI.l2vpn, SAFI.evpn), (AFI.ipv4, SAFI.mcast_vpn)],
    ids=['evpn', 'mvpn'],
)
def test_a_typed_route_of_an_unknown_type_is_discarded(afi: AFI, safi: SAFI) -> None:
    """Discarded alone: the IPv4 route in the same UPDATE is still advertised, nothing is withdrawn."""
    attributes = MANDATORY + mp_reach_typed(afi, safi, UNKNOWN_TYPED_ROUTE)
    parsed = parse(update(attributes), typed_session(afi, safi))

    assert withdrawn_routes(parsed) == [], 'an unknown route type was treated as withdraw instead of discarded'
    assert announced(parsed) == ['10.0.0.0/24'], (
        f'a {afi} {safi} route of unknown type {UNKNOWN_ROUTE_TYPE:#x} was kept: {announced(parsed)}'
    )


# a Source Active A-D route (RFC 6514 4.5, type 5) for the group 239.1.1.1, which MCAST-VPN
# registers and which is outside the SSM range, so nothing but 5.4 could discard it
KNOWN_MVPN_ROUTE = bytes([5, 18]) + bytes(8) + bytes([32, 10, 0, 0, 1]) + bytes([32, 239, 1, 1, 1])


@pytest.mark.rfc('rfc7606#5.4-unrecognised-typed-nlri-discarded', polarity='negative')
def test_a_typed_route_of_a_known_type_beside_an_unknown_one_is_kept() -> None:
    """Discarding the whole attribute passes the test above; only the unknown route may go."""
    routes = UNKNOWN_TYPED_ROUTE + KNOWN_MVPN_ROUTE
    attributes = MANDATORY + mp_reach_typed(AFI.ipv4, SAFI.mcast_vpn, routes)
    parsed = parse(update(attributes, nlri=b''), typed_session(AFI.ipv4, SAFI.mcast_vpn))

    assert withdrawn_routes(parsed) == []
    assert [type(routed.nlri).__name__ for routed in parsed.announces] == ['SourceAD'], announced(parsed)


@pytest.mark.rfc('rfc7606#5.4-unrecognised-typed-nlri-discarded', polarity='negative')
def test_a_withdrawn_typed_route_of_an_unknown_type_is_still_reported() -> None:
    """Only announcements are discarded: a withdrawal removes nothing and shows the operator the peer."""
    payload = pack('!HB', int(AFI.ipv4), int(SAFI.mcast_vpn)) + UNKNOWN_TYPED_ROUTE
    attributes = attribute(OPTIONAL, CODE.MP_UNREACH_NLRI, payload)
    parsed = parse(update(attributes, nlri=b''), typed_session(AFI.ipv4, SAFI.mcast_vpn))

    assert [type(nlri).__name__ for nlri in parsed.withdraws] == ['GenericMVPN']


@pytest.mark.rfc('rfc7606#5.4-unrecognised-typed-nlri-discarded', polarity='negative')
def test_an_mvpn_route_of_a_type_rfc6514_defines_but_we_do_not_decode_is_kept() -> None:
    """Type 1, Intra-AS I-PMSI A-D, is kept as raw bytes: recognised, so not discarded."""
    intra_as_i_pmsi = bytes([1, 12]) + bytes(8) + bytes([10, 0, 0, 1])
    attributes = MANDATORY + mp_reach_typed(AFI.ipv4, SAFI.mcast_vpn, intra_as_i_pmsi)
    parsed = parse(update(attributes, nlri=b''), typed_session(AFI.ipv4, SAFI.mcast_vpn))

    assert [type(routed.nlri).__name__ for routed in parsed.announces] == ['GenericMVPN']
