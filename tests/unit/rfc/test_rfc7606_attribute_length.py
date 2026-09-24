"""RFC 7606 section 4: when the attribute lengths and the Total Attribute Length disagree.

Two shapes of error, and one instruction about what to do afterwards.

The two shapes are an attribute whose own length runs past the end of the attribute
section, and a tail of the section too short to hold even an empty attribute header.  Both
are treat-as-withdraw, and both are easy to get wrong in the same direction: Python slicing
does not raise on an overrun, so a decoder which does not check ends up reading the
attribute from however many bytes happened to remain and accepting it as well formed.

The instruction is that the NLRI field is then located from the Total Attribute Length
rather than by walking the attributes.  That is what makes treat-as-withdraw possible at
all in this case: there is a route to withdraw only if we can still find it.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.update.attribute import Attribute

from rfc.rfc7606_wire import (
    EMPTY_AS_PATH,
    IPV4_PREFIX,
    MANDATORY,
    NEXT_HOP,
    OPTIONAL,
    OPTIONAL_TRANSITIVE,
    WELL_KNOWN_TRANSITIVE,
    announced,
    attribute,
    parse,
    session,
    update,
    withdrawn_routes,
)

CODE = Attribute.CODE

# An ORIGIN whose length byte claims forty bytes when four follow it.  Written by hand
# rather than through attribute(), because the whole point is that the length is a lie.
ORIGIN_CLAIMING_FORTY_BYTES = bytes([WELL_KNOWN_TRANSITIVE, CODE.ORIGIN, 40]) + bytes(4)

# Two bytes left over after three well formed attributes: a flag and a type code, and no
# room for the length byte which has to follow them.
TRUNCATED_ATTRIBUTE_HEADER = bytes([WELL_KNOWN_TRANSITIVE, CODE.ORIGIN])


@pytest.mark.rfc('rfc7606#4-attribute-length-conflict-treat-as-withdraw')
@pytest.mark.parametrize(
    'name,attributes',
    [
        ('an attribute length past the end of the section', ORIGIN_CLAIMING_FORTY_BYTES),
        ('a tail too short for an attribute header', MANDATORY + TRUNCATED_ATTRIBUTE_HEADER),
    ],
)
def test_a_length_which_disagrees_with_the_section_withdraws_the_route(name: str, attributes: bytes) -> None:
    parsed = parse(update(attributes), session())

    assert announced(parsed) == [], f'{name} left the route advertised'
    assert withdrawn_routes(parsed) == ['10.0.0.0/24'], f'{name} was not treated as withdraw'


@pytest.mark.rfc('rfc7606#4-attribute-length-conflict-treat-as-withdraw', polarity='negative')
def test_lengths_which_agree_with_the_section_leave_the_route_alone() -> None:
    """An implementation which withdrew every UPDATE would pass the test above."""
    parsed = parse(update(MANDATORY), session())

    assert announced(parsed) == ['10.0.0.0/24'], 'consistent attribute lengths were reported as an error'
    assert withdrawn_routes(parsed) == []


@pytest.mark.rfc('rfc7606#4-total-attribute-length-locates-nlri')
def test_the_nlri_is_found_from_the_total_attribute_length_not_from_the_attributes() -> None:
    """Walking the attributes here lands forty bytes past the end; the NLRI is still found.

    The prefix in the assertion is what proves it.  A decoder which trusted the attribute
    length would start reading NLRI from the wrong offset, and would either fail or report
    a different prefix, so 10.0.0.0/24 coming back is the evidence.
    """
    parsed = parse(update(ORIGIN_CLAIMING_FORTY_BYTES, nlri=IPV4_PREFIX), session())

    assert withdrawn_routes(parsed) == ['10.0.0.0/24'], (
        'the NLRI after an over-long attribute was not located from the Total Attribute Length'
    )


@pytest.mark.rfc('rfc7606#4-zero-length-is-a-syntax-error')
@pytest.mark.parametrize(
    'name,attributes',
    [
        ('MULTI_EXIT_DISC', MANDATORY + attribute(OPTIONAL, CODE.MED, b'')),
        ('COMMUNITY', MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.COMMUNITY, b'')),
        ('ORIGIN', attribute(WELL_KNOWN_TRANSITIVE, CODE.ORIGIN, b'') + EMPTY_AS_PATH + NEXT_HOP),
    ],
)
def test_a_zero_length_attribute_is_a_syntax_error(name: str, attributes: bytes) -> None:
    """None of these three is allowed to be empty, so an empty one is malformed."""
    parsed = parse(update(attributes), session())

    assert announced(parsed) == [], f'a zero length {name} left the route advertised'
    assert withdrawn_routes(parsed) == ['10.0.0.0/24'], f'a zero length {name} was accepted'


@pytest.mark.rfc('rfc7606#4-zero-length-is-a-syntax-error', polarity='negative')
@pytest.mark.parametrize(
    'name,code,attributes',
    [
        ('AS_PATH', CODE.AS_PATH, MANDATORY),
        (
            'ATOMIC_AGGREGATE',
            CODE.ATOMIC_AGGREGATE,
            MANDATORY + attribute(WELL_KNOWN_TRANSITIVE, CODE.ATOMIC_AGGREGATE, b''),
        ),
    ],
)
def test_the_two_attributes_which_may_be_empty_are_accepted_empty(name: str, code: int, attributes: bytes) -> None:
    """ "Only AS_PATH and ATOMIC_AGGREGATE may validly have an attribute length of zero"."""
    parsed = parse(update(attributes), session())

    assert announced(parsed) == ['10.0.0.0/24'], f'a zero length {name}, which is legal, withdrew the route'
    assert code in parsed.attributes, f'a zero length {name}, which is legal, was dropped'
