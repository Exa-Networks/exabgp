"""RFC 7606 section 2: the three outcomes, and the rule about which one may be used.

Section 2 names four approaches and orders them.  Three of them reach this code:

    session reset       a NOTIFICATION goes out and the adjacency is gone
    treat-as-withdraw   the session lives, and every route the UPDATE announced is withdrawn
    attribute discard   the session lives, the attribute is dropped, the routes stand

Conflating any two of them is the bug this RFC was written to stop, so the assertions below
separate them by what came out rather than by whether an exception was raised.  A test which
accepts "no traceback escaped" as success cannot tell a withdrawal from a reset, and the
sweep in tests/unit/test_attribute_error_handling.py says so in its own docstring.

The last requirement in this file is not about one message.  "Attribute discard MUST NOT be
used except in the case of an attribute that has no effect on route selection or
installation" constrains which attribute classes may carry the DISCARD flag at all, so the
test reads the real registry rather than sending bytes.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.update.attribute import Attribute

from rfc.rfc7606_wire import (
    EMPTY_AS_PATH,
    MANDATORY,
    OPTIONAL,
    ORIGIN_IGP,
    WELL_KNOWN_TRANSITIVE,
    announced,
    attribute,
    mp_reach_ipv6,
    parse,
    session,
    update,
    withdrawn_routes,
)

# RFC 7606 7.4: MULTI_EXIT_DISC is malformed at any length but 4.  MED is optional
# NON-transitive (RFC 4271 5.1.4), so the flag has to be OPTIONAL alone: setting the
# transitive bit as well would make the attribute malformed for a different reason, under
# section 3 (c), and the test would pass without the length ever being looked at.
MALFORMED_MED = attribute(OPTIONAL, Attribute.CODE.MED, bytes(3))
WELL_FORMED_MED = attribute(OPTIONAL, Attribute.CODE.MED, bytes(4))

# RFC 7606 7.6: ATOMIC_AGGREGATE is malformed at any length but 0, and is attribute discard.
MALFORMED_ATOMIC = attribute(WELL_KNOWN_TRANSITIVE, Attribute.CODE.ATOMIC_AGGREGATE, bytes(4))
WELL_FORMED_ATOMIC = attribute(WELL_KNOWN_TRANSITIVE, Attribute.CODE.ATOMIC_AGGREGATE, b'')

# Every attribute class in the tree which says "drop me and carry on".  The RFC allows the
# approach only where the attribute cannot change which route is chosen or installed, so
# each entry needs a specification of its own which prescribes it.
DISCARD_IS_PRESCRIBED_BY = {
    Attribute.CODE.ATOMIC_AGGREGATE: 'RFC 7606 7.6',
    Attribute.CODE.AGGREGATOR: 'RFC 7606 7.7',
    Attribute.CODE.AS4_AGGREGATOR: 'RFC 6793 6, as the four octet twin of AGGREGATOR',
    Attribute.CODE.BGP_LS: 'RFC 9552 5, which names attribute discard for the BGP-LS attribute',
    Attribute.CODE.BGP_PREFIX_SID: 'RFC 8669 5, see tests/unit/test_rfc8669_prefix_sid_discard.py',
}

# The attributes which do decide, or help decide, which route wins.  None of them may ever
# be discarded: RFC 7606 gives every one of them treat-as-withdraw instead.
FEEDS_ROUTE_SELECTION = (
    Attribute.CODE.ORIGIN,
    Attribute.CODE.AS_PATH,
    Attribute.CODE.NEXT_HOP,
    Attribute.CODE.MED,
    Attribute.CODE.LOCAL_PREF,
    Attribute.CODE.COMMUNITY,
    Attribute.CODE.EXTENDED_COMMUNITY,
    Attribute.CODE.IPV6_EXTENDED_COMMUNITY,
    Attribute.CODE.ORIGINATOR_ID,
    Attribute.CODE.CLUSTER_LIST,
)


def registered_classes() -> dict[int, type[Attribute]]:
    """One class per attribute code, from the registry the decoder itself reads."""
    return {code: klass for (code, _), klass in Attribute.registered_attributes.items()}


@pytest.mark.rfc('rfc7606#2-treat-as-withdraw-removes-contained-routes')
def test_treat_as_withdraw_withdraws_the_routes_carried_in_mp_reach() -> None:
    """ "All contained routes" means the MP_REACH ones too, not only the IPv4 NLRI field."""
    parsed = parse(update(ORIGIN_IGP + EMPTY_AS_PATH + MALFORMED_MED + mp_reach_ipv6(), nlri=b''), session())

    assert announced(parsed) == [], 'a malformed MULTI_EXIT_DISC left the MP_REACH route advertised'
    assert withdrawn_routes(parsed) == ['::/64'], (
        'RFC 7606 2 says every contained route is withdrawn, and the MP_REACH route was not'
    )


@pytest.mark.rfc('rfc7606#2-treat-as-withdraw-removes-contained-routes', polarity='negative')
def test_a_well_formed_update_does_not_have_its_mp_reach_routes_withdrawn() -> None:
    """Without this, an implementation which withdrew everything would pass the test above."""
    parsed = parse(update(ORIGIN_IGP + EMPTY_AS_PATH + WELL_FORMED_MED + mp_reach_ipv6(), nlri=b''), session())

    assert announced(parsed) == ['::/64'], 'a well formed UPDATE lost its MP_REACH route'
    assert withdrawn_routes(parsed) == [], 'a well formed UPDATE withdrew a route nobody asked to withdraw'


@pytest.mark.rfc('rfc7606#2-attribute-discard-continues-processing')
def test_attribute_discard_drops_the_attribute_and_keeps_the_rest_of_the_update() -> None:
    """The malformed attribute goes; the route, and every other attribute, stays."""
    parsed = parse(update(MANDATORY + MALFORMED_ATOMIC), session())

    assert Attribute.CODE.ATOMIC_AGGREGATE not in parsed.attributes, 'the malformed attribute was kept'
    assert announced(parsed) == ['10.0.0.0/24'], 'attribute discard withdrew the route'
    assert Attribute.CODE.ORIGIN in parsed.attributes, 'the UPDATE stopped being processed at the bad attribute'
    assert Attribute.CODE.NEXT_HOP in parsed.attributes, 'the UPDATE stopped being processed at the bad attribute'


@pytest.mark.rfc('rfc7606#2-attribute-discard-continues-processing', polarity='negative')
def test_a_well_formed_attribute_is_not_discarded() -> None:
    """An implementation which dropped ATOMIC_AGGREGATE always would pass the test above."""
    parsed = parse(update(MANDATORY + WELL_FORMED_ATOMIC), session())

    assert Attribute.CODE.ATOMIC_AGGREGATE in parsed.attributes, 'a well formed ATOMIC_AGGREGATE was discarded'
    assert announced(parsed) == ['10.0.0.0/24'], 'a well formed UPDATE lost its route'


@pytest.mark.rfc('rfc7606#2-attribute-discard-only-without-route-effect')
def test_every_attribute_we_discard_has_a_specification_which_says_to_discard_it() -> None:
    """The flag is the decision, so the registry is where the requirement is kept."""
    classes = registered_classes()
    assert len(classes) >= 23, 'the registry is short, so this sweep is measuring an empty set'

    discarding = {code for code, klass in classes.items() if klass.DISCARD}
    assert discarding, 'no attribute carries DISCARD, so this test proves nothing'

    for code in sorted(discarding):
        assert code in DISCARD_IS_PRESCRIBED_BY, (
            f'{Attribute.CODE.name(code)} carries DISCARD with no specification prescribing it; '
            f'RFC 7606 2 allows attribute discard only where the attribute cannot affect '
            f'route selection or installation'
        )


@pytest.mark.rfc('rfc7606#2-attribute-discard-only-without-route-effect', polarity='negative')
def test_no_attribute_which_decides_a_route_may_be_discarded() -> None:
    """The half with teeth: flipping DISCARD onto any of these has to fail here."""
    classes = registered_classes()

    for code in FEEDS_ROUTE_SELECTION:
        klass = classes.get(code)
        assert klass is not None, f'{Attribute.CODE.name(code)} is not registered, so this row checks nothing'
        assert not klass.DISCARD, (
            f'{Attribute.CODE.name(code)} carries DISCARD, but it affects route selection, '
            f'which RFC 7606 2 forbids; RFC 7606 7 gives it treat-as-withdraw'
        )
        assert klass.TREAT_AS_WITHDRAW, (
            f'{Attribute.CODE.name(code)} carries neither flag, so a Notify from its decoder '
            f'escapes AttributeCollection.parse and resets the session'
        )
