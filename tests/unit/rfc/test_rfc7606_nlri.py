"""RFC 7606 section 5: finding the NLRI in an UPDATE whose attributes cannot be trusted.

Treat-as-withdraw only works if the NLRI can still be read, so section 5 is about keeping
them findable.  It has two halves, and they pull in opposite directions on purpose:

  5.1 constrains what we SEND, so that a receiver with a malformed attribute in its hands
      can locate the NLRI without walking the attribute list, and then says in the very
      next sentence that we MUST accept a peer which ignores all of it.
  5.2, 5.3 and 5.4 constrain what we do with what we RECEIVE.

Three of the requirements here are not met and carry xfail: two on the sending side, where
UpdateCollection.messages puts MP_REACH_NLRI last and packs a withdrawal and an
announcement into one message, and one on the receiving side, where an UPDATE with no
reachable NLRI and a treat-as-withdraw error does not escalate to a session reset.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.notification import Notify
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


def routed(prefix: str) -> RoutedNLRI:
    """One route with a next hop of its own family, ready to be packed."""
    address, mask = prefix.split('/')
    ip = IP.from_string(address)
    nlri = INET.from_cidr(CIDR.create_cidr(ip.pack_ip(), int(mask)), ip.afi, SAFI.unicast)
    return RoutedNLRI(nlri, IP.from_string('192.0.2.1' if ip.afi == AFI.ipv4 else '2001:db8::ffff'))


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
@pytest.mark.xfail(
    strict=True,
    reason='UpdateCollection.messages appends MP_REACH_NLRI after ORIGIN and AS_PATH, so the '
    'attribute RFC 7606 5.1 wants first is emitted last',
)
def test_we_send_the_mp_nlri_attribute_before_any_other() -> None:
    for _, codes, _ in generated([routed('2001:db8::1/128')], []):
        assert codes, 'an UPDATE was generated with no attributes at all'
        assert codes[0] in (CODE.MP_REACH_NLRI, CODE.MP_UNREACH_NLRI), (
            f'the first attribute we sent was {Attribute.CODE.name(codes[0])}, '
            f'and RFC 7606 5.1 says the MP NLRI attribute goes first'
        )


@pytest.mark.rfc('rfc7606#5.1-one-nlri-field-per-update')
@pytest.mark.xfail(
    strict=True,
    reason='UpdateCollection.messages packs an IPv4 withdrawal and an IPv4 announcement into one '
    'UPDATE, which is two of the four fields RFC 7606 5.1 allows only one of',
)
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
@pytest.mark.xfail(
    strict=True,
    reason='an UPDATE with attributes other than MP_UNREACH_NLRI, no reachable NLRI and a '
    'treat-as-withdraw error parses to an empty UpdateCollection: the marker is added, there is '
    'nothing to move into the withdraw set, and no NOTIFICATION is sent',
)
def test_a_treat_as_withdraw_error_with_no_reachable_nlri_resets_the_session() -> None:
    """There are no routes to withdraw, and no proof the NLRI field was read correctly."""
    payload = update(attribute(WELL_KNOWN_TRANSITIVE, CODE.ORIGIN, bytes(2)) + EMPTY_AS_PATH, nlri=b'')

    with pytest.raises(Notify) as raised:
        parse(payload, session())

    assert raised.value.code == UPDATE_MESSAGE_ERROR


@pytest.mark.rfc('rfc7606#5.2-session-reset-when-no-reachable-nlri', polarity='negative')
def test_an_attribute_discard_error_with_no_reachable_nlri_does_not_reset_the_session() -> None:
    """The RFC exempts attribute discard by name, and we get that half right."""
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
@pytest.mark.xfail(
    strict=True,
    reason='MPRNLRI carries neither TREAT_AS_WITHDRAW nor DISCARD, so an MP_REACH with the '
    'transitive bit set falls through AttributeCollection.parse to a debug line and a continue: '
    'the attribute is dropped in silence and the routes it carried vanish',
)
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
