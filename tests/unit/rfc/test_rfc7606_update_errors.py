"""RFC 7606 section 3: the amendments to RFC 4271 section 6.3, item by item.

Section 3 is a list of lettered edits to the base specification, and each letter is a
separate decision about one class of malformed UPDATE.  They are tested here in the order
the RFC lists them, because that is the order a reader checks them in.

Everything below sends real wire bytes through Update.unpack_message and asserts on the
UpdateCollection that came back, or on the Notify that did not.  The distinction the whole
document turns on is only visible from there: a Notify means the adjacency went, and no
amount of "the parser did not crash" can stand in for that.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute import Attribute

from rfc.rfc7606_wire import (
    EMPTY_AS_PATH,
    IPV4_PREFIX,
    MANDATORY,
    NEXT_HOP,
    OPTIONAL,
    OPTIONAL_TRANSITIVE,
    ORIGIN_IGP,
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

# BGP error codes and subcodes (RFC 4271 4.5)
UPDATE_MESSAGE_ERROR = 3
MALFORMED_ATTRIBUTE_LIST = 1
INVALID_NETWORK_FIELD = 10

MALFORMED_MED = attribute(OPTIONAL, CODE.MED, bytes(3))
MALFORMED_ATOMIC = attribute(WELL_KNOWN_TRANSITIVE, CODE.ATOMIC_AGGREGATE, bytes(4))
MALFORMED_AGGREGATOR = attribute(OPTIONAL_TRANSITIVE, CODE.AGGREGATOR, bytes(7))

# an MP_REACH whose Length of Next Hop Network Address is a size no IPv6 unicast next hop
# can have.  RFC 7606 7.11 is the one row in the document which still says session reset.
MP_REACH_WITH_UNUSABLE_NEXT_HOP = mp_reach_ipv6(next_hop_length=7)


# ------------------------------------------------------------------ 3 (a)


@pytest.mark.rfc('rfc7606#3a-session-reset-uses-update-message-error')
def test_a_case_which_specifies_a_session_reset_sends_update_message_error() -> None:
    """An unusable MP_REACH next hop length is one of the few resets the RFC keeps."""
    payload = update(ORIGIN_IGP + EMPTY_AS_PATH + MP_REACH_WITH_UNUSABLE_NEXT_HOP, nlri=b'')

    with pytest.raises(Notify) as raised:
        parse(payload, session())

    assert raised.value.code == UPDATE_MESSAGE_ERROR, (
        f'a session reset was signalled with error code {raised.value.code}, not UPDATE Message Error'
    )


@pytest.mark.rfc('rfc7606#3a-session-reset-uses-update-message-error', polarity='negative')
def test_a_case_which_does_not_specify_a_session_reset_sends_no_notification() -> None:
    """The half that matters: a treat-as-withdraw case must not reach for a NOTIFICATION."""
    parsed = parse(update(MANDATORY + MALFORMED_MED), session())

    assert withdrawn_routes(parsed) == ['10.0.0.0/24'], 'a malformed MULTI_EXIT_DISC did not withdraw the route'


# ------------------------------------------------------------------ 3 (b)


@pytest.mark.rfc('rfc7606#3b-length-too-large-is-malformed-attribute-list')
@pytest.mark.parametrize(
    'name,payload',
    [
        ('withdrawn routes length', pack('!H', 40) + bytes(4)),
        ('total attribute length', pack('!H', 0) + pack('!H', 40) + bytes(4)),
    ],
)
def test_a_length_larger_than_the_message_is_a_malformed_attribute_list(name: str, payload: bytes) -> None:
    """Section 3 (b) is explicit that this case keeps the old behaviour."""
    with pytest.raises(Notify) as raised:
        parse(payload, session())

    assert (raised.value.code, raised.value.subcode) == (UPDATE_MESSAGE_ERROR, MALFORMED_ATTRIBUTE_LIST), (
        f'a {name} past the end of the message gave {raised.value.code}/{raised.value.subcode}, '
        f'not Malformed Attribute List'
    )


@pytest.mark.rfc('rfc7606#3b-length-too-large-is-malformed-attribute-list', polarity='negative')
def test_lengths_which_add_up_are_not_a_malformed_attribute_list() -> None:
    """An implementation which refused every UPDATE would pass the test above."""
    parsed = parse(update(MANDATORY, withdrawn=bytes([24, 10, 0, 2])), session())

    assert announced(parsed) == ['10.0.0.0/24']
    assert withdrawn_routes(parsed) == ['10.0.2.0/24']


# ------------------------------------------------------------------ 3 (c)


@pytest.mark.rfc('rfc7606#3c-flag-conflict-treat-as-withdraw')
@pytest.mark.parametrize(
    'name,attributes',
    [
        # ORIGIN is well-known transitive; the peer marks it optional
        ('origin marked optional', attribute(OPTIONAL, CODE.ORIGIN, bytes([0])) + EMPTY_AS_PATH + NEXT_HOP),
        # COMMUNITY is optional transitive; the peer clears the optional bit
        ('community marked well-known', MANDATORY + attribute(WELL_KNOWN_TRANSITIVE, CODE.COMMUNITY, bytes(4))),
    ],
)
def test_a_conflicting_optional_or_transitive_bit_is_treat_as_withdraw(name: str, attributes: bytes) -> None:
    """The value may be perfectly well formed; the flags alone make the attribute malformed."""
    parsed = parse(update(attributes), session())

    assert announced(parsed) == [], f'{name} left the route advertised'
    assert withdrawn_routes(parsed) == ['10.0.0.0/24'], f'{name} was not treated as withdraw'


@pytest.mark.rfc('rfc7606#3c-flag-conflict-treat-as-withdraw', polarity='negative')
def test_the_specified_flag_values_are_not_a_conflict() -> None:
    """The same two attributes with the flags RFC 4271 and RFC 1997 specify."""
    parsed = parse(update(MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.COMMUNITY, bytes(4))), session())

    assert announced(parsed) == ['10.0.0.0/24'], 'correctly flagged attributes were treated as malformed'
    assert CODE.COMMUNITY in parsed.attributes


# ------------------------------------------------------------------ 3 (d)


@pytest.mark.rfc('rfc7606#3d-missing-well-known-mandatory-treat-as-withdraw')
@pytest.mark.parametrize(
    'missing,attributes',
    [
        ('ORIGIN', EMPTY_AS_PATH + NEXT_HOP),
        ('AS_PATH', ORIGIN_IGP + NEXT_HOP),
        ('NEXT_HOP', ORIGIN_IGP + EMPTY_AS_PATH),
    ],
)
def test_an_absent_well_known_mandatory_attribute_withdraws_the_route(missing: str, attributes: bytes) -> None:
    """RFC 4271 called this an UPDATE error; RFC 7606 3 (d) makes it a withdrawal."""
    parsed = parse(update(attributes), session())

    assert announced(parsed) == [], f'an UPDATE with no {missing} still advertised its route'
    assert withdrawn_routes(parsed) == ['10.0.0.0/24'], f'an UPDATE with no {missing} was not treated as withdraw'


@pytest.mark.rfc('rfc7606#3d-missing-well-known-mandatory-treat-as-withdraw', polarity='negative')
def test_an_update_carrying_all_of_them_is_advertised() -> None:
    parsed = parse(update(MANDATORY), session())

    assert announced(parsed) == ['10.0.0.0/24'], 'an UPDATE with every mandatory attribute was withdrawn'
    assert withdrawn_routes(parsed) == []


# ------------------------------------------------------------------ 3 (e) and 3 (f)


@pytest.mark.rfc('rfc7606#3e-treat-as-withdraw-replaces-session-reset')
@pytest.mark.parametrize(
    'name,attributes',
    [
        ('ORIGIN', attribute(WELL_KNOWN_TRANSITIVE, CODE.ORIGIN, bytes(2)) + EMPTY_AS_PATH + NEXT_HOP),
        ('AS_PATH', ORIGIN_IGP + attribute(WELL_KNOWN_TRANSITIVE, CODE.AS_PATH, bytes([9, 1, 0, 0])) + NEXT_HOP),
        ('NEXT_HOP', ORIGIN_IGP + EMPTY_AS_PATH + attribute(WELL_KNOWN_TRANSITIVE, CODE.NEXT_HOP, bytes(3))),
        ('MULTI_EXIT_DISC', MANDATORY + MALFORMED_MED),
        ('LOCAL_PREF', MANDATORY + attribute(WELL_KNOWN_TRANSITIVE, CODE.LOCAL_PREF, bytes(3))),
    ],
)
def test_the_five_named_attributes_withdraw_instead_of_resetting(name: str, attributes: bytes) -> None:
    """Each of these was a NOTIFICATION under RFC 4271, and is a withdrawal now."""
    parsed = parse(update(attributes), session())

    assert announced(parsed) == [], f'a malformed {name} left the route advertised'
    assert withdrawn_routes(parsed) == ['10.0.0.0/24'], f'a malformed {name} was not treated as withdraw'


@pytest.mark.rfc('rfc7606#3e-treat-as-withdraw-replaces-session-reset', polarity='negative')
def test_the_five_named_attributes_are_kept_when_they_are_well_formed() -> None:
    attributes = MANDATORY
    attributes += attribute(OPTIONAL, CODE.MED, bytes(4))
    attributes += attribute(WELL_KNOWN_TRANSITIVE, CODE.LOCAL_PREF, bytes(4))
    parsed = parse(update(attributes), session())

    assert announced(parsed) == ['10.0.0.0/24']
    for code in (CODE.ORIGIN, CODE.AS_PATH, CODE.NEXT_HOP, CODE.MED, CODE.LOCAL_PREF):
        assert code in parsed.attributes, f'a well formed {Attribute.CODE.name(code)} was dropped'


@pytest.mark.rfc('rfc7606#3f-attribute-discard-for-atomic-aggregate-and-aggregator')
@pytest.mark.parametrize(
    'code,attributes',
    [
        (CODE.ATOMIC_AGGREGATE, MANDATORY + MALFORMED_ATOMIC),
        (CODE.AGGREGATOR, MANDATORY + MALFORMED_AGGREGATOR),
    ],
)
def test_atomic_aggregate_and_aggregator_are_discarded_not_withdrawn(code: int, attributes: bytes) -> None:
    """Neither changes which route is chosen, so the route survives the malformation."""
    parsed = parse(update(attributes), session())

    assert code not in parsed.attributes, f'the malformed {Attribute.CODE.name(code)} was kept'
    assert announced(parsed) == ['10.0.0.0/24'], (
        f'a malformed {Attribute.CODE.name(code)} withdrew the route; RFC 7606 3 (f) says attribute discard'
    )


@pytest.mark.rfc('rfc7606#3f-attribute-discard-for-atomic-aggregate-and-aggregator', polarity='negative')
def test_atomic_aggregate_and_aggregator_are_kept_when_well_formed() -> None:
    attributes = MANDATORY + attribute(WELL_KNOWN_TRANSITIVE, CODE.ATOMIC_AGGREGATE, b'')
    attributes += attribute(OPTIONAL_TRANSITIVE, CODE.AGGREGATOR, bytes(8))
    parsed = parse(update(attributes), session(asn4=True))

    assert CODE.ATOMIC_AGGREGATE in parsed.attributes, 'a well formed ATOMIC_AGGREGATE was discarded'
    assert CODE.AGGREGATOR in parsed.attributes, 'a well formed AGGREGATOR was discarded'


# ------------------------------------------------------------------ 3 (g)


@pytest.mark.rfc('rfc7606#3g-duplicate-mp-nlri-notification')
@pytest.mark.parametrize(
    'name,repeated',
    [
        ('MP_REACH_NLRI', mp_reach_ipv6()),
        ('MP_UNREACH_NLRI', mp_unreach_ipv6()),
    ],
)
def test_a_repeated_mp_nlri_attribute_is_a_malformed_attribute_list(name: str, repeated: bytes) -> None:
    """These two are the exception to the discard-the-later-copies rule below."""
    with pytest.raises(Notify) as raised:
        parse(update(ORIGIN_IGP + EMPTY_AS_PATH + repeated + repeated, nlri=b''), session())

    assert (raised.value.code, raised.value.subcode) == (UPDATE_MESSAGE_ERROR, MALFORMED_ATTRIBUTE_LIST), (
        f'a repeated {name} gave {raised.value.code}/{raised.value.subcode}, not Malformed Attribute List'
    )


@pytest.mark.rfc('rfc7606#3g-duplicate-mp-nlri-notification', polarity='negative')
def test_a_single_mp_nlri_attribute_is_not_an_error() -> None:
    parsed = parse(update(ORIGIN_IGP + EMPTY_AS_PATH + mp_reach_ipv6(), nlri=b''), session())

    assert announced(parsed) == ['::/64'], 'one MP_REACH_NLRI was treated as a duplicate'


@pytest.mark.rfc('rfc7606#3g-duplicate-attribute-keeps-the-first')
def test_a_repeated_attribute_keeps_the_first_occurrence() -> None:
    """Which copy survives is the whole requirement: "other than the first one"."""
    first = attribute(WELL_KNOWN_TRANSITIVE, CODE.ORIGIN, bytes([0]))  # igp
    second = attribute(WELL_KNOWN_TRANSITIVE, CODE.ORIGIN, bytes([2]))  # incomplete
    parsed = parse(update(first + second + EMPTY_AS_PATH + NEXT_HOP), session())

    assert announced(parsed) == ['10.0.0.0/24'], 'a duplicate attribute stopped the UPDATE being processed'
    assert str(parsed.attributes[CODE.ORIGIN]) == 'igp', (
        'the second ORIGIN won; RFC 7606 3 (g) discards every occurrence but the first'
    )


@pytest.mark.rfc('rfc7606#3g-duplicate-attribute-keeps-the-first', polarity='negative')
def test_an_attribute_sent_once_is_the_one_we_report() -> None:
    """Otherwise a parser which always reported "igp" would pass the test above."""
    parsed = parse(
        update(attribute(WELL_KNOWN_TRANSITIVE, CODE.ORIGIN, bytes([2])) + EMPTY_AS_PATH + NEXT_HOP), session()
    )

    assert str(parsed.attributes[CODE.ORIGIN]) == 'incomplete'


# ------------------------------------------------------------------ 3 (h)


@pytest.mark.rfc('rfc7606#3h-strongest-action-wins')
def test_a_discard_and_a_withdraw_in_one_update_give_the_withdraw() -> None:
    """Treat-as-withdraw is the stronger of the two, so it decides."""
    parsed = parse(update(MANDATORY + MALFORMED_ATOMIC + MALFORMED_MED), session())

    assert announced(parsed) == [], 'the weaker approach won when both applied'
    assert withdrawn_routes(parsed) == ['10.0.0.0/24'], 'the stronger of the two approaches was not used'
    assert CODE.ATOMIC_AGGREGATE not in parsed.attributes, 'the discarded attribute came back'


@pytest.mark.rfc('rfc7606#3h-strongest-action-wins', polarity='negative')
def test_two_discards_in_one_update_stay_discards() -> None:
    """ "If the same approach is specified ... then the specified approach MUST be used"."""
    parsed = parse(update(MANDATORY + MALFORMED_ATOMIC + MALFORMED_AGGREGATOR), session())

    assert announced(parsed) == ['10.0.0.0/24'], 'two attribute-discard errors escalated to a withdrawal'
    assert CODE.ATOMIC_AGGREGATE not in parsed.attributes
    assert CODE.AGGREGATOR not in parsed.attributes


# ------------------------------------------------------------------ 3 (i) and 3 (j)


@pytest.mark.rfc('rfc7606#3i-withdrawn-routes-checked-like-nlri')
@pytest.mark.parametrize(
    'name,withdrawn',
    [
        ('a mask of 33', bytes([33, 10, 0, 0, 0])),
        ('a prefix shorter than its mask', bytes([24, 10, 0])),
    ],
)
def test_the_withdrawn_routes_field_is_checked_for_syntax(name: str, withdrawn: bytes) -> None:
    """Section 5.3's rules apply to the withdrawn field, not only to the NLRI field."""
    with pytest.raises(Notify) as raised:
        parse(update(MANDATORY, nlri=b'', withdrawn=withdrawn), session())

    assert (raised.value.code, raised.value.subcode) == (UPDATE_MESSAGE_ERROR, INVALID_NETWORK_FIELD), (
        f'{name} in the withdrawn routes field gave {raised.value.code}/{raised.value.subcode}'
    )


@pytest.mark.rfc('rfc7606#3i-withdrawn-routes-checked-like-nlri', polarity='negative')
def test_a_syntactically_correct_withdrawn_routes_field_is_accepted() -> None:
    parsed = parse(update(MANDATORY, nlri=b'', withdrawn=IPV4_PREFIX), session())

    assert withdrawn_routes(parsed) == ['10.0.0.0/24'], 'a well formed withdrawal was refused'


@pytest.mark.rfc('rfc7606#3j-session-reset-when-nlri-cannot-be-parsed')
def test_an_unparseable_nlri_field_resets_the_session_even_with_an_attribute_error() -> None:
    """Treat-as-withdraw needs the NLRI; when they cannot be read, the reset comes back."""
    payload = update(MANDATORY + MALFORMED_MED, nlri=bytes([33, 10, 0, 0, 0]))

    with pytest.raises(Notify) as raised:
        parse(payload, session())

    assert raised.value.code == UPDATE_MESSAGE_ERROR


@pytest.mark.rfc('rfc7606#3j-session-reset-when-nlri-cannot-be-parsed', polarity='negative')
def test_a_parseable_nlri_field_keeps_the_session_when_an_attribute_is_malformed() -> None:
    """The same malformed attribute, with NLRI we can read, must not cost the adjacency."""
    parsed = parse(update(MANDATORY + MALFORMED_MED), session())

    assert withdrawn_routes(parsed) == ['10.0.0.0/24'], 'the route was not withdrawn'
    assert announced(parsed) == []
