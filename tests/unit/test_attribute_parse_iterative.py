"""One UPDATE with a thousand small attributes exhausted the stack and reset the session.

`Attributes.parse` tail-called itself once per attribute, seven times over.  CPython does not
eliminate a tail call, so the recursion depth was the attribute COUNT, and 996 three octet
attributes reached the default limit of 1000.  That is a 3015 byte UPDATE, well inside the
4096 octet maximum, with no withdrawn routes and every attribute in it individually well
formed.  RFC 4271 4.3 bounds the attribute section by the message length alone, so a peer
sending many small attributes is doing nothing wrong.

`reactor/protocol.py` catches the `RecursionError` as an unspecified `Exception` and answers
`Notify(1, 0)`, "can not decode update message": the peer is told its message HEADER was
malformed, which is neither true nor actionable, and the session is reset.  Inside the reactor
the ceiling is lower still, because the protocol and loop frames are already on the stack when
this is entered, so the count which breaks a real session is smaller than the one here.

The counts below are deliberately close to the old crossover rather than absurd.  A test at
100,000 attributes would pass on a parser which merely raised the recursion limit, and a test
at 100 would have passed before the fix.
"""

from __future__ import annotations

import sys
from struct import pack
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Update
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.attributes import Attributes

# an unknown non-transitive attribute of zero length: three octets, ignored, and it drives the
# cheapest of the seven tail calls, so it is the one which reaches the highest count
UNKNOWN_NON_TRANSITIVE = bytes([0x80, 0xEF, 0x00])

# 996 was the crossover at a limit of 1000; the largest count here fills the attribute section
# of a maximum sized UPDATE
COUNTS = [900, 996, 997, 1000, 1350]

ORIGIN = int(Attribute.CODE.ORIGIN)
COMMUNITY = int(Attribute.CODE.COMMUNITY)
IPV4_PREFIX = bytes([24, 10, 0, 0])


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


def update_carrying(attributes: bytes, announced: bytes = IPV4_PREFIX) -> bytes:
    return pack('!H', 0) + pack('!H', len(attributes)) + attributes + announced


def test_the_counts_here_are_above_the_interpreter_recursion_limit() -> None:
    """A limit raised elsewhere in the suite would make every assertion below vacuous."""
    assert sys.getrecursionlimit() <= min(COUNTS) + 100, (
        f'the recursion limit is {sys.getrecursionlimit()}, so {min(COUNTS)} attributes '
        f'would not have crashed the recursive parser either'
    )


@pytest.mark.parametrize('count', COUNTS, ids=[str(n) for n in COUNTS])
def test_many_small_attributes_in_one_update_are_parsed(count: int) -> None:
    """A RecursionError here is answered to the peer as a malformed message header."""
    payload = update_carrying(UNKNOWN_NON_TRANSITIVE * count)

    assert len(payload) + 19 <= 4096, 'the UPDATE built here is larger than BGP allows'

    decoded = Update.unpack_message(payload, Direction.IN, session())

    assert decoded is not None


@pytest.mark.parametrize('count', COUNTS, ids=[str(n) for n in COUNTS])
def test_many_duplicate_attributes_in_one_update_are_parsed(count: int) -> None:
    """The duplicate branch is a different one of the seven tail calls."""
    origin = bytes([0x40, ORIGIN, 1, 0])
    payload = update_carrying(origin * count)

    decoded = Update.unpack_message(payload, Direction.IN, session())

    assert decoded is not None
    assert ORIGIN in decoded.attributes


@pytest.mark.parametrize('count', COUNTS, ids=[str(n) for n in COUNTS])
def test_many_unknown_transitive_attributes_in_one_update_are_parsed(count: int) -> None:
    """And so is the unknown-transitive branch, which builds a GenericAttribute each time."""
    payload = update_carrying(bytes([0xC0, 0xEE, 0x00]) * count)

    assert Update.unpack_message(payload, Direction.IN, session()) is not None


# --- the negative space: none of the per-attribute verdicts may have changed ---------------


def test_the_attributes_are_all_still_read_and_not_merely_skipped() -> None:
    """A loop which consumed the section without decoding it would pass every test above."""
    attributes = bytes([0x40, ORIGIN, 1, 0]) + bytes([0xC0, COMMUNITY, 4, 0, 0, 0, 1])

    decoded = Update.unpack_message(update_carrying(attributes), Direction.IN, session())

    assert ORIGIN in decoded.attributes
    assert COMMUNITY in decoded.attributes
    assert '0:1' in str(decoded.attributes)


def test_a_notify_still_stops_the_parse_where_it_did() -> None:
    """Two MP_REACH_NLRI is Notify(3, 1); the loop must not swallow a raise."""
    value = bytes([0, 1, 1, 0, 0])
    duplicate = (bytes([0x80, int(Attribute.CODE.MP_REACH_NLRI), len(value)]) + value) * 2

    with pytest.raises(Notify) as raised:
        Update.unpack_message(update_carrying(duplicate, announced=b''), Direction.IN, session())

    assert raised.value.code == 3


def test_a_truncated_attribute_header_is_still_treat_as_withdraw() -> None:
    """One of the three early returns, which became a break rather than a continue."""
    decoded = Update.unpack_message(update_carrying(bytes([0x40])), Direction.IN, session())

    assert int(Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW) in decoded.attributes
