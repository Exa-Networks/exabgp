"""RFC 7606 section 7 names an action per attribute, and this file pins each one.

RFC 7606 exists to stop a BGP speaker from resetting a session over one badly encoded
attribute.  A test which only asks "did the parser survive" cannot tell the difference
between "we handled this" and "we dropped the adjacency", because a Notify is a well
formed outcome for that weaker question.

So this file asserts the ACTION the RFC names, per attribute, per section:

    treat-as-withdraw   the UPDATE survives, and every route it announced is withdrawn
    attribute discard   the UPDATE survives, minus the attribute; the routes stand

In this branch `Attributes.parse` turns the decoder's Notify into a `TreatAsWithdraw` or
a `Discard` sentinel, and `reactor/protocol.py` acts on the sentinel when the message
reaches the reader.  The sentinel is therefore what the parser produces and what this
file reads: an attribute whose code is in neither `Attributes.TREAT_AS_WITHDRAW` nor
`Attributes.DISCARD` has its Notify escape instead, and the session goes down.

What this file does NOT establish is that ExaBGP implements RFC 7606 completely.  It
pins the rows it lists and nothing else, and the list is hand written from the RFC.  A
row absent here is untested, not compliant.

Section 7.1 is deliberately absent.  `Origin.unpack` reads `data[0]` and never looks at
the length, so a two byte ORIGIN is accepted rather than being handled either way.  That
is a real gap and a separate one: it is a missing check in a decoder, not a missing entry
in the table below, and pinning it here would mean shipping a red test.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.attributes import Attributes

TREAT_AS_WITHDRAW = 'treat-as-withdraw'
ATTRIBUTE_DISCARD = 'attribute discard'

OPTIONAL_TRANSITIVE = 0xC0
WELL_KNOWN_TRANSITIVE = 0x40

# (section, attribute code, flag the peer sets, a length the attribute cannot have, action)
#
# The lengths are malformed for that attribute and nothing subtler: COMMUNITY is a
# sequence of 4 byte values so 5 cannot parse, EXTENDED_COMMUNITY is 8 byte values so 9
# cannot, IPV6_EXTENDED_COMMUNITY is 20 byte values so 21 cannot.
PRESCRIBED: list[tuple[str, int, int, int, str]] = [
    ('7.4', Attribute.CODE.MED, OPTIONAL_TRANSITIVE, 3, TREAT_AS_WITHDRAW),
    ('7.6', Attribute.CODE.ATOMIC_AGGREGATE, WELL_KNOWN_TRANSITIVE, 4, ATTRIBUTE_DISCARD),
    ('7.7', Attribute.CODE.AGGREGATOR, OPTIONAL_TRANSITIVE, 7, ATTRIBUTE_DISCARD),
    ('7.8', Attribute.CODE.COMMUNITY, OPTIONAL_TRANSITIVE, 5, TREAT_AS_WITHDRAW),
    ('7.14', Attribute.CODE.EXTENDED_COMMUNITY, OPTIONAL_TRANSITIVE, 9, TREAT_AS_WITHDRAW),
    ('7.15', Attribute.CODE.IPV6_EXTENDED_COMMUNITY, OPTIONAL_TRANSITIVE, 21, TREAT_AS_WITHDRAW),
]

IDS = [f'{section}-{Attribute.CODE.names.get(code, code)}' for section, code, _, _, _ in PRESCRIBED]


@pytest.fixture(autouse=True)
def _logger() -> Any:
    """The parser logs every attribute it sees, and the logger is not set up under pytest."""
    from exabgp.logger.option import option

    logger, formater = option.logger, option.formater
    option.logger = Mock()
    option.formater = Mock(return_value='formatted message')
    yield
    option.logger, option.formater = logger, formater


def negotiated() -> Any:
    """The session state the decoders read."""
    session = Mock()
    session.asn4 = False
    session.families = []
    session.nexthop = []
    session.msg_size = 4096

    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    session.neighbor = neighbor
    return session


def one_attribute(flag: int, code: int, length: int) -> bytes:
    """The attribute the caller describes, with a value of the length it declares."""
    return bytes([flag, code, length]) + bytes(length)


@pytest.mark.parametrize('section,code,flag,length,action', PRESCRIBED, ids=IDS)
def test_a_malformed_attribute_gets_the_action_the_rfc_names(
    section: str, code: int, flag: int, length: int, action: str
) -> None:
    """The session survives, and the parser says which of the two answers applies."""
    name = Attribute.CODE.names.get(code, code)
    try:
        parsed = Attributes.unpack(one_attribute(flag, code, length), Direction.IN, negotiated())
    except Notify as exc:
        pytest.fail(
            f'a {length} byte {name} resets the session '
            f'(Notify {exc.code}/{exc.subcode}), RFC 7606 {section} says {action}'
        )

    assert code not in parsed, f'the malformed {name} was kept, RFC 7606 {section} says {action}'

    withdraw = Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW in parsed
    discard = Attribute.CODE.INTERNAL_DISCARD in parsed

    if action == TREAT_AS_WITHDRAW:
        assert withdraw, f'RFC 7606 {section} says treat-as-withdraw, the parser did not ask for one'
        assert not discard, f'RFC 7606 {section} says treat-as-withdraw, the parser asked for a discard'
    else:
        assert discard, f'RFC 7606 {section} says attribute discard, the parser did not ask for one'
        assert not withdraw, f'RFC 7606 {section} says attribute discard, the parser withdrew the route'


def test_a_well_formed_attribute_is_not_caught_by_the_same_net() -> None:
    """Every assertion above is satisfied by a parser which drops every attribute.

    So one of them has to prove a sound attribute survives, or this file would still pass
    against an implementation that withdrew every UPDATE it saw.
    """
    payload = one_attribute(WELL_KNOWN_TRANSITIVE, Attribute.CODE.ORIGIN, 1)
    parsed = Attributes.unpack(payload, Direction.IN, negotiated())

    assert Attribute.CODE.ORIGIN in parsed, 'a well formed ORIGIN was dropped, so the assertions above pin nothing'
    assert Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW not in parsed
    assert Attribute.CODE.INTERNAL_DISCARD not in parsed
