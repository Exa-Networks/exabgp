"""RFC 7606 attribute discard was honoured for one exception type and not the other.

AttributeCollection.parse catches two things out of a decoder.  A Notify was checked
against both TREAT_AS_WITHDRAW and DISCARD; a ValueError or an IndexError was checked
against TREAT_AS_WITHDRAW only, and re-raised otherwise.  So an attribute whose decoder
signals a bad length by raising ValueError left Update.unpack_message as a raw ValueError,
where the reactor's catch-all turned RFC 7606 7.7 attribute discard into a session reset
with a misleading message.

AGGREGATOR is the one which reaches it today: it sets DISCARD, and Aggregator.from_packet
raises ValueError for any length but the negotiated one.
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

AGGREGATOR = int(Attribute.CODE.AGGREGATOR)
OPTIONAL_TRANSITIVE = 0xC0

# a two byte ASN session, so RFC 4271 says AGGREGATOR is six bytes
VALID_AGGREGATOR_LENGTH = 6
LENGTHS = [0, 1, 2, 5, 6, 7, 8, 9, 20, 255]


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


def update_carrying_aggregator(length: int) -> bytes:
    """An UPDATE whose only attribute is an AGGREGATOR of the length the peer chose."""
    attribute = bytes([OPTIONAL_TRANSITIVE, AGGREGATOR, length]) + bytes(length)
    return pack('!H', 0) + pack('!H', len(attribute)) + attribute


@pytest.mark.parametrize('length', LENGTHS, ids=[str(n) for n in LENGTHS])
def test_a_mis_sized_aggregator_is_discarded_rather_than_raised(length: int) -> None:
    """The peer's UPDATE survives, minus the attribute.  RFC 7606 7.7.

    A raw ValueError here is the defect: not because ValueError is untidy, but because it
    reaches the reactor as an unknown failure rather than as the attribute discard the RFC
    asks for, and the route the peer announced is lost with it.
    """
    session = negotiated()
    try:
        decoded = Update.unpack_message(update_carrying_aggregator(length), session)
        # the wire container defers the attributes, so the discard has to survive the
        # transformation to the semantic one as well: parse() is what the reactor calls
        decoded.parse(session)
    except Notify:
        pytest.fail(f'AGGREGATOR of {length} bytes resets the session, RFC 7606 7.7 says discard')

    attributes = decoded.parse(session).attributes
    if length != VALID_AGGREGATOR_LENGTH:
        assert AGGREGATOR not in attributes, f'a {length} byte AGGREGATOR was kept rather than discarded'


def test_a_well_sized_aggregator_still_arrives() -> None:
    """The discard must not have swallowed the working case.

    Every other assertion in this file is satisfied by a parse which drops AGGREGATOR
    unconditionally, so one of them has to check that a good one survives.
    """
    session = negotiated()
    decoded = Update.unpack_message(update_carrying_aggregator(VALID_AGGREGATOR_LENGTH), session)

    attributes = decoded.parse(session).attributes
    assert AGGREGATOR in attributes, 'a valid AGGREGATOR was discarded with the malformed ones'
