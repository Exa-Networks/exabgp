"""An attribute length which overruns the attribute section was silently truncated.

`Attributes.parse` read the declared length out of the attribute header and then sliced
`data[:length]` without ever checking that many bytes were there.  Python slicing does not
raise on an overrun, so an attribute declaring more bytes than the section holds was handed
however many happened to remain, decoded from the short buffer, and kept on the route as
though the peer had sent a well formed attribute.  A COMMUNITY declaring twelve bytes with
four behind it arrived as the single community those four decoded to: a community set nobody
sent, published to every API client and used for policy.

RFC 7606 section 4 is explicit about this case: an Attribute Length which exceeds the
message is an error in the framing of the UPDATE, not in one attribute, so the whole UPDATE
takes the treat-as-withdraw approach.  Every inner TLV parser in the tree checks the
remaining length before slicing; this outermost one did not.

The same slice also crashed the parser.  With the EXTENDED_LENGTH flag set, three header
octets and a declared length of 256 leave nothing behind it, so `NextHop.unpack` was called
with an empty buffer.  It answers `NoNextHop`, which is not an attribute and has no `ID`,
and `Attributes.add` reads `attribute.ID` on the next line:

    AttributeError: '_NoNextHop' object has no attribute 'ID'

out of `attributes.py` add(), past every RFC 7606 flag, from four peer chosen octets.
`NextHop.unpack` cannot be the place to fix that, because `mprnlri.py` relies on the same
`NoNextHop` answer for an MP_REACH next hop of zero length.

Note the case which is NOT a defect and is pinned below: an attribute whose declared length
exactly consumes the rest of the section is self consistent framing.  The peer may have
meant to send two attributes, but what it sent says one, and a parser cannot tell the
difference.  Only an overrun past the end of the section is detectable, and only that is
what this file asks for.
"""

from __future__ import annotations

from struct import pack
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.attributes import Attributes

COMMUNITY = int(Attribute.CODE.COMMUNITY)
ORIGIN = int(Attribute.CODE.ORIGIN)
NEXT_HOP = int(Attribute.CODE.NEXT_HOP)
TREAT_AS_WITHDRAW = int(Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW)

OPTIONAL_TRANSITIVE = 0xC0
WELL_KNOWN_TRANSITIVE = 0x40
EXTENDED_LENGTH = 0x10

COMMUNITY_SIZE = 4
# the declared length of the truncated COMMUNITY: three communities are claimed
DECLARED_LENGTH = 3 * COMMUNITY_SIZE
# how many bytes are actually behind it, all of them short of the declaration
PRESENT_LENGTHS = [0, 1, 4, 8, 11]

ORIGIN_IGP = bytes([WELL_KNOWN_TRANSITIVE, ORIGIN, 1, 0])


@pytest.fixture(autouse=True)
def _logger() -> Any:
    """The parser logs every attribute it sees, and the logger is not set up under pytest."""
    from exabgp.logger.option import option

    logger, formater = option.logger, option.formater
    option.logger = Mock()
    option.formater = Mock(return_value='formatted message')
    yield
    option.logger, option.formater = logger, formater


@pytest.fixture(autouse=True)
def _no_parse_cache() -> Any:
    """Attributes memoises the last parse on the class, so one test would feed the next."""
    Attributes.cached = None
    Attributes.previous = ''
    yield
    Attributes.cached = None
    Attributes.previous = ''


def session() -> Any:
    negotiated = Mock()
    negotiated.asn4 = False
    negotiated.addpath = Mock()
    negotiated.addpath.receive = Mock(return_value=False)
    negotiated.addpath.send = Mock(return_value=False)
    negotiated.required = Mock(return_value=False)
    negotiated.families = []
    negotiated.nexthop = []
    negotiated.msg_size = 4096
    neighbour = Mock()
    neighbour.__getitem__ = Mock(return_value=False)
    negotiated.neighbor = neighbour
    return negotiated


def parsed(attributes: bytes) -> Attributes:
    """The attributes the reactor would see for that attribute section."""
    return Attributes.unpack(attributes, Direction.IN, session())


def truncated_community(present: int) -> bytes:
    """A COMMUNITY claiming DECLARED_LENGTH bytes with fewer bytes behind it."""
    return bytes([OPTIONAL_TRANSITIVE, COMMUNITY, DECLARED_LENGTH]) + bytes(present)


@pytest.mark.parametrize('present', PRESENT_LENGTHS, ids=[str(n) for n in PRESENT_LENGTHS])
def test_an_attribute_longer_than_the_section_is_treated_as_withdraw(present: int) -> None:
    """RFC 7606 section 4: the framing is wrong, so the UPDATE is withdrawn, not trimmed."""
    attributes = parsed(truncated_community(present))

    assert TREAT_AS_WITHDRAW in attributes, (
        f'a COMMUNITY declaring {DECLARED_LENGTH} bytes with {present} present '
        f'was accepted rather than treated as withdraw'
    )
    assert COMMUNITY not in attributes, 'the truncated attribute was kept as well as flagged'


def test_a_preceding_attribute_does_not_excuse_the_overrun() -> None:
    """The overrun is found wherever in the section it sits, not only as the first attribute."""
    attributes = parsed(ORIGIN_IGP + truncated_community(COMMUNITY_SIZE))

    assert TREAT_AS_WITHDRAW in attributes, 'an overrun after a valid attribute was accepted'


def test_an_extended_length_attribute_longer_than_the_section_is_treated_as_withdraw() -> None:
    """The two byte length header reaches the same slice and needs the same check."""
    overrunning = bytes([OPTIONAL_TRANSITIVE | EXTENDED_LENGTH, COMMUNITY]) + pack('!H', 0xFF) + bytes(COMMUNITY_SIZE)

    assert TREAT_AS_WITHDRAW in parsed(overrunning), 'an extended length overrun was accepted'


def test_an_overrunning_next_hop_does_not_crash_the_parser() -> None:
    """The four octets which reached NoNextHop, and add() reading .ID off it.

    EXTENDED_LENGTH with a declared length of 256 and nothing behind it.  The assertion is
    that parse answers at all: before the length check this raised AttributeError, which the
    reactor reports as an unknown failure and answers with a session reset.
    """
    overrunning = bytes([WELL_KNOWN_TRANSITIVE | EXTENDED_LENGTH, NEXT_HOP, 0x01, 0x00])

    attributes = parsed(overrunning)

    assert TREAT_AS_WITHDRAW in attributes
    assert NEXT_HOP not in attributes


def test_an_attribute_which_exactly_fills_the_section_still_parses() -> None:
    """The negative space: self consistent framing must survive the new check.

    Three communities declared and twelve bytes present is a peer saying one attribute.
    Rejecting this would pass every assertion above while breaking every real session.
    """
    attributes = parsed(truncated_community(DECLARED_LENGTH))

    assert TREAT_AS_WITHDRAW not in attributes, 'a well framed COMMUNITY was treated as withdraw'
    assert COMMUNITY in attributes, 'a well framed COMMUNITY was dropped'


def test_two_well_formed_attributes_still_parse() -> None:
    """The other half of the negative space: the ordinary two attribute case is untouched."""
    attributes = parsed(ORIGIN_IGP + truncated_community(DECLARED_LENGTH))

    assert TREAT_AS_WITHDRAW not in attributes, 'a well formed UPDATE was treated as withdraw'
    assert ORIGIN in attributes, 'ORIGIN was lost from a well formed UPDATE'
    assert COMMUNITY in attributes, 'COMMUNITY was lost from a well formed UPDATE'
