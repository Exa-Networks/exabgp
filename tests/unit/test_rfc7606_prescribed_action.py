"""RFC 7606 section 7 names an action per attribute, and this file pins each one.

tests/unit/test_attribute_error_handling.py already sweeps every registered attribute and
asserts that nothing leaves the parser as a raw Python exception.  It accepts a Notify as a
correct outcome, because for that question it is one: the session was closed deliberately
and the peer was told why.

That is the weaker question.  RFC 7606 exists precisely to stop a BGP speaker from resetting
a session over one badly encoded attribute, so for most attributes a Notify is the wrong
answer even though it is a well formed one.  A sweep which accepts it cannot tell the
difference between "we handled this" and "we dropped the adjacency".

So this file asserts the ACTION the RFC names, per attribute, per section:

    treat-as-withdraw   the UPDATE survives, and every route it announced is withdrawn
    attribute discard   the UPDATE survives, minus the attribute; the routes stand

Three rows here failed when the file was written.  Community (7.8), Extended Community
(7.14) and IPv6 Address Specific Extended Community (7.15) each carried neither flag, so a
Notify escaped AttributeCollection.parse and reset the session.  LargeCommunities already
had TREAT_AS_WITHDRAW, which is what made the gap visible: the tree disagreed with itself
about attributes the RFC treats identically.

What this file does NOT establish is that ExaBGP implements RFC 7606 completely.  It pins
the rows it lists and nothing else, and the list is hand written from the RFC.  A row absent
here is untested, not compliant.
"""

from __future__ import annotations

from struct import pack
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.protocol.family import AFI

TREAT_AS_WITHDRAW = 'treat-as-withdraw'
ATTRIBUTE_DISCARD = 'attribute discard'

OPTIONAL_TRANSITIVE = 0xC0
OPTIONAL = 0x80
WELL_KNOWN_TRANSITIVE = 0x40

# one real prefix, so the UPDATE announces a route rather than being an End-of-RIB.  The
# route is what treat-as-withdraw acts on, so without it the two actions look identical.
IPV4_PREFIX = bytes([24, 10, 0, 0])

# (section, attribute code, flag the peer sets, a length the attribute cannot have, action)
#
# The lengths are chosen to be malformed for that attribute and nothing subtler: COMMUNITY
# is a sequence of 4 byte values so 5 cannot parse, EXTENDED_COMMUNITY is 8 byte values so 9
# cannot, IPV6_EXTENDED_COMMUNITY is 20 byte values so 21 cannot.
PRESCRIBED: list[tuple[str, int, int, int, str]] = [
    ('7.1', Attribute.CODE.ORIGIN, WELL_KNOWN_TRANSITIVE, 2, TREAT_AS_WITHDRAW),
    # OPTIONAL alone, not OPTIONAL_TRANSITIVE: MULTI_EXIT_DISC is optional NON-transitive
    # (RFC 4271 5.1.4), so setting the transitive bit makes the attribute malformed under
    # RFC 7606 3 (c) for its FLAGS, and the row then passes without its length ever being
    # read.  Every other row here already uses the flag its own specification gives it.
    ('7.4', Attribute.CODE.MED, OPTIONAL, 3, TREAT_AS_WITHDRAW),
    ('7.6', Attribute.CODE.ATOMIC_AGGREGATE, WELL_KNOWN_TRANSITIVE, 4, ATTRIBUTE_DISCARD),
    ('7.7', Attribute.CODE.AGGREGATOR, OPTIONAL_TRANSITIVE, 7, ATTRIBUTE_DISCARD),
    ('7.8', Attribute.CODE.COMMUNITY, OPTIONAL_TRANSITIVE, 5, TREAT_AS_WITHDRAW),
    ('7.14', Attribute.CODE.EXTENDED_COMMUNITY, OPTIONAL_TRANSITIVE, 9, TREAT_AS_WITHDRAW),
    ('7.15', Attribute.CODE.IPV6_EXTENDED_COMMUNITY, OPTIONAL_TRANSITIVE, 21, TREAT_AS_WITHDRAW),
]

IDS = [f'{section}-{Attribute.CODE.name(code)}' for section, code, _, _, _ in PRESCRIBED]


def negotiated() -> Any:
    """The session state both the decode and the semantic transformation read."""
    session = Mock()
    session.asn4 = False
    session.addpath = Mock()
    session.addpath.receive = Mock(return_value=False)
    session.addpath.send = Mock(return_value=False)
    session.required = Mock(return_value=False)
    session.families = []
    session.nexthop = []
    session.msg_size = 4096
    session.direction = Action.ANNOUNCE

    neighbour = Mock()
    neighbour.__getitem__ = Mock(return_value={'aigp': False})
    neighbour.session = Mock()
    neighbour.session.local_address = Mock()
    neighbour.session.local_address.afi = AFI.ipv4
    session.neighbor = neighbour
    return session


def update_announcing_one_route(flag: int, code: int, length: int) -> bytes:
    """An UPDATE announcing IPV4_PREFIX, carrying the attribute the caller describes.

    A NEXT_HOP and an ORIGIN come along for the ride unless the attribute under test is one
    of them: an UPDATE missing a mandatory attribute is itself treat-as-withdraw, which
    would satisfy this file's assertion for the wrong reason.
    """
    attributes = bytes([flag, code, length]) + bytes(length)
    if code != Attribute.CODE.ORIGIN:
        attributes += bytes([WELL_KNOWN_TRANSITIVE, Attribute.CODE.ORIGIN, 1]) + bytes(1)
    if code != Attribute.CODE.NEXT_HOP:
        attributes += bytes([WELL_KNOWN_TRANSITIVE, Attribute.CODE.NEXT_HOP, 4]) + bytes([10, 0, 0, 1])
    if code != Attribute.CODE.AS_PATH:
        attributes += bytes([WELL_KNOWN_TRANSITIVE, Attribute.CODE.AS_PATH, 0])
    return pack('!H', 0) + pack('!H', len(attributes)) + attributes + IPV4_PREFIX


@pytest.mark.rfc(
    'rfc7606#7.1-origin-treat-as-withdraw',
    'rfc7606#7.4-med-treat-as-withdraw',
    'rfc7606#7.6-atomic-aggregate-attribute-discard',
    'rfc7606#7.7-aggregator-attribute-discard',
    'rfc7606#7.8-community-treat-as-withdraw',
    'rfc7606#7.14-extended-community-treat-as-withdraw',
    'rfc7606#7.15-ipv6-extended-community-treat-as-withdraw',
)
@pytest.mark.parametrize('section,code,flag,length,action', PRESCRIBED, ids=IDS)
def test_a_malformed_attribute_gets_the_action_the_rfc_names(
    section: str, code: int, flag: int, length: int, action: str
) -> None:
    """The session survives, and the routes go or stay according to the RFC."""
    session = negotiated()
    payload = update_announcing_one_route(flag, code, length)

    try:
        message = Update.unpack_message(payload, session)
        assert isinstance(message, Update), f'expected an UPDATE, got {type(message).__name__}'
        parsed = message.parse(session)
    except Notify as exc:
        pytest.fail(
            f'a {length} byte {Attribute.CODE.name(code)} resets the session '
            f'(Notify {exc.code}/{exc.subcode}), RFC 7606 {section} says {action}'
        )

    assert code not in parsed.attributes, (
        f'the malformed {Attribute.CODE.name(code)} was kept, RFC 7606 {section} says {action}'
    )

    # announces and withdraws, never nlris: that property is the union of the two, so it
    # holds the route either way and an assertion against it cannot tell them apart.
    announced = list(parsed.announces)
    withdrawn = list(parsed.withdraws)

    if action == TREAT_AS_WITHDRAW:
        assert not announced, (
            f'{Attribute.CODE.name(code)} still announced {len(announced)} route(s), '
            f'RFC 7606 {section} says treat-as-withdraw'
        )
        assert withdrawn, f'RFC 7606 {section} says treat-as-withdraw, but nothing was withdrawn'
    else:
        assert announced, (
            f'{Attribute.CODE.name(code)} withdrew the route, RFC 7606 {section} says '
            f'attribute discard, which leaves the route standing'
        )


def test_a_well_formed_update_is_not_caught_by_the_same_net() -> None:
    """Every assertion above is satisfied by a parser which drops the attribute always.

    So one of them has to prove the route survives when nothing is wrong with it, or this
    file would still pass against an implementation that withdrew every UPDATE it saw.
    """
    session = negotiated()
    attributes = bytes([WELL_KNOWN_TRANSITIVE, Attribute.CODE.ORIGIN, 1]) + bytes(1)
    attributes += bytes([WELL_KNOWN_TRANSITIVE, Attribute.CODE.NEXT_HOP, 4]) + bytes([10, 0, 0, 1])
    attributes += bytes([WELL_KNOWN_TRANSITIVE, Attribute.CODE.AS_PATH, 0])
    payload = pack('!H', 0) + pack('!H', len(attributes)) + attributes + IPV4_PREFIX

    message = Update.unpack_message(payload, session)
    assert isinstance(message, Update), f'expected an UPDATE, got {type(message).__name__}'
    parsed = message.parse(session)

    assert list(parsed.announces), 'a well formed UPDATE announced nothing, so the assertions above pin nothing'
    assert not list(parsed.withdraws), 'a well formed UPDATE withdrew a route'
