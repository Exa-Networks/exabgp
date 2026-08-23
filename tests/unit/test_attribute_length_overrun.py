"""An attribute length which overruns the attribute section was silently truncated.

AttributeCollection.parse read the declared length out of the attribute header and then
sliced `data[:length]` without ever checking that many bytes were there.  Python slicing
does not raise on an overrun, so an attribute declaring more bytes than the section holds
was handed however many happened to remain, decoded from the short buffer, and added to
the route as though the peer had sent a well formed attribute.

RFC 7606 section 4 is explicit about this case: an Attribute Length which exceeds the
message is an error in the message framing, not in one attribute, and the whole UPDATE
takes the "treat-as-withdraw" approach.  Every inner TLV parser in the tree checks the
remaining length before slicing; this outermost one did not.

Note the case which is *not* a defect and is pinned below: an attribute whose declared
length exactly consumes the rest of the section is self consistent framing.  The peer may
have meant to send two attributes, but what it sent says one, and a parser cannot tell the
difference.  Only an overrun past the end of the section is detectable, and only that is
what this file asks for.
"""

from __future__ import annotations

from struct import pack
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.attribute import Attribute

COMMUNITY = int(Attribute.CODE.COMMUNITY)
ORIGIN = int(Attribute.CODE.ORIGIN)
TREAT_AS_WITHDRAW = int(Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW)

OPTIONAL_TRANSITIVE = 0xC0
WELL_KNOWN_TRANSITIVE = 0x40

COMMUNITY_SIZE_BYTES = 4
# The declared length of the truncated COMMUNITY.  Three communities are claimed.
DECLARED_LENGTH_BYTES = 3 * COMMUNITY_SIZE_BYTES
# How many bytes are actually left for it, all of them short of the declaration.
PRESENT_LENGTHS_BYTES = [0, 1, 4, 8, 11]

ORIGIN_IGP = bytes([WELL_KNOWN_TRANSITIVE, ORIGIN, 1, 0])


def negotiated() -> Any:
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
    session.neighbor = {'aigp': False}
    return session


def update_carrying(attributes: bytes) -> bytes:
    """An UPDATE with no withdrawn routes, no NLRI, and the attribute section given."""
    return pack('!H', 0) + pack('!H', len(attributes)) + attributes


def parsed(attributes: bytes) -> Any:
    """The semantic attributes the reactor would see for that attribute section."""
    session = negotiated()
    return Update.unpack_message(update_carrying(attributes), session).parse(session).attributes


def truncated_community(present_length_bytes: int) -> bytes:
    """A COMMUNITY claiming DECLARED_LENGTH_BYTES with fewer bytes behind it."""
    return bytes([OPTIONAL_TRANSITIVE, COMMUNITY, DECLARED_LENGTH_BYTES]) + bytes(present_length_bytes)


@pytest.mark.parametrize('present_length_bytes', PRESENT_LENGTHS_BYTES, ids=[str(n) for n in PRESENT_LENGTHS_BYTES])
def test_an_attribute_longer_than_the_section_is_treated_as_withdraw(present_length_bytes: int) -> None:
    """RFC 7606 section 4: the framing is wrong, so the UPDATE is withdrawn, not trimmed.

    Silently accepting it is the defect.  The peer declared twelve bytes of communities
    and the route is installed carrying whatever shorter list the remaining bytes happened
    to decode to, which is a community set nobody sent.
    """
    attributes = parsed(truncated_community(present_length_bytes))

    assert TREAT_AS_WITHDRAW in attributes, (
        f'a COMMUNITY declaring {DECLARED_LENGTH_BYTES} bytes with {present_length_bytes} present '
        f'was accepted rather than treated as withdraw'
    )
    assert COMMUNITY not in attributes, 'the truncated attribute was kept as well as flagged'


def test_a_preceding_attribute_does_not_excuse_the_overrun() -> None:
    """The overrun is found wherever in the section it sits, not only as the first attribute."""
    attributes = parsed(ORIGIN_IGP + truncated_community(COMMUNITY_SIZE_BYTES))

    assert TREAT_AS_WITHDRAW in attributes, 'an overrun after a valid attribute was accepted'


def test_an_extended_length_attribute_longer_than_the_section_is_treated_as_withdraw() -> None:
    """The two byte length header reaches the same slice and needs the same check."""
    extended_length = 0xC0 | 0x10
    overrunning = bytes([extended_length, COMMUNITY]) + pack('!H', 0xFF) + bytes(COMMUNITY_SIZE_BYTES)

    assert TREAT_AS_WITHDRAW in parsed(overrunning), 'an extended length overrun was accepted'


def test_an_attribute_which_exactly_fills_the_section_still_parses() -> None:
    """The negative space: self consistent framing must survive the new check.

    Three communities declared and twelve bytes present is a peer saying one attribute.
    Rejecting this would pass every assertion above while breaking every real session.
    """
    attributes = parsed(truncated_community(DECLARED_LENGTH_BYTES))

    assert TREAT_AS_WITHDRAW not in attributes, 'a well framed COMMUNITY was treated as withdraw'
    assert COMMUNITY in attributes, 'a well framed COMMUNITY was dropped'


def test_two_well_formed_attributes_still_parse() -> None:
    """The other half of the negative space: the ordinary two attribute case is untouched."""
    attributes = parsed(ORIGIN_IGP + truncated_community(DECLARED_LENGTH_BYTES))

    assert TREAT_AS_WITHDRAW not in attributes, 'a well formed UPDATE was treated as withdraw'
    assert ORIGIN in attributes, 'ORIGIN was lost from a well formed UPDATE'
    assert COMMUNITY in attributes, 'COMMUNITY was lost from a well formed UPDATE'
