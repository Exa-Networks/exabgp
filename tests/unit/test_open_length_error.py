"""An OPEN too short to read is a message length error, not an unspecific OPEN error.

RFC 4271 6.1: "if the Length field of an OPEN message is less than the minimum length of
the OPEN message, then the Error Subcode MUST be set to Bad Message Length."  That is a
Message Header Error, code 1 subcode 2.

ExaBGP sent 2/0, OPEN message error with an Unspecific subcode, which names nothing.  The
OPEN subcodes RFC 4271 6.2 defines cover an unsupported version, a bad peer AS, a bad BGP
identifier, an unsupported optional parameter and an unacceptable hold time; none of them
is "the message stopped before I could read it", which is why 6.1 handles it instead.

Session 5.0 found the divergence: their branch already answered 1/2, main answered 2/0, and
neither of us wanted to pick unilaterally on what a peer receives.
"""

from __future__ import annotations

from struct import pack, unpack

import pytest

from exabgp.bgp.message import Message
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open import Open
from exabgp.bgp.message.open.capability.negotiated import Negotiated

MESSAGE_HEADER_ERROR = 1
BAD_MESSAGE_LENGTH = 2
OPEN_MESSAGE_ERROR = 2
UNSUPPORTED_VERSION = 1

# up to and including 9, which is the byte that matters: HEADER_SIZE is what Open stores
# and MINIMUM_BODY_SIZE is what RFC 4271 4.2 requires on the wire, and a body of 9 sits
# between them.  A test which only ranges to HEADER_SIZE passes at either threshold, which
# is why the boundary is the assertion worth making
TOO_SHORT = list(range(Open.MINIMUM_BODY_SIZE))

# version 4, AS 65000, hold time 180, identifier 1.2.3.4
WELL_FORMED = bytes([4]) + pack('!H', 65000) + pack('!H', 180) + bytes([1, 2, 3, 4]) + bytes([0])


@pytest.mark.parametrize('length', TOO_SHORT, ids=[f'{n} bytes' for n in TOO_SHORT])
def test_an_open_too_short_to_read_is_a_bad_message_length(length: int) -> None:
    """Every length below the minimum, not only the empty one."""
    with pytest.raises(Notify) as caught:
        Message.unpack(int(Message.CODE.OPEN), bytes(length), Negotiated.UNSET)

    assert caught.value.code == MESSAGE_HEADER_ERROR, 'a short OPEN is a header error, RFC 4271 6.1'
    assert caught.value.subcode == BAD_MESSAGE_LENGTH


def test_the_boundary_is_the_rfc_minimum_and_not_what_the_class_stores() -> None:
    """Nine octets is an OPEN with no Optional Parameters Length at all, and it was accepted.

    HEADER_SIZE is 9 because that is what Open keeps in _packed, and __init__ requires
    exactly that.  The wire minimum is a different question: RFC 4271 4.2 makes the
    Optional Parameters Length octet part of the fixed portion and states "The minimum
    length of the OPEN message is 29 octets (including the message header)", so the body
    is 10.  The validation reused the wrong constant, and Capabilities.unpack cannot tell
    a missing octet from an octet saying zero, because both arrive as an empty slice.

    Session 5.0 traced it: the check said 9 on the day it was written and there is no
    regression to revert.
    """
    assert Open.MINIMUM_BODY_SIZE == Open.HEADER_SIZE + 1, 'the optional parameters length octet is mandatory'

    with pytest.raises(Notify):
        Message.unpack(int(Message.CODE.OPEN), bytes(Open.HEADER_SIZE), Negotiated.UNSET)

    # and one octet more, the smallest legal OPEN body, is read
    smallest = bytes([4]) + pack('!H', 65000) + pack('!H', 180) + bytes([1, 2, 3, 4]) + bytes([0])
    assert len(smallest) == Open.MINIMUM_BODY_SIZE
    assert Message.unpack(int(Message.CODE.OPEN), smallest, Negotiated.UNSET) is not None


def test_a_long_enough_open_with_a_bad_version_is_still_an_open_error() -> None:
    """The header error must not have swallowed the OPEN errors which belong in 6.2.

    A message long enough to read whose version is wrong is an OPEN message error with the
    Unsupported Version Number subcode, and moving the length case must not move this one.
    """
    wrong_version = bytes([3]) + WELL_FORMED[1:]

    with pytest.raises(Notify) as caught:
        Message.unpack(int(Message.CODE.OPEN), wrong_version, Negotiated.UNSET)

    assert caught.value.code == OPEN_MESSAGE_ERROR
    assert caught.value.subcode == UNSUPPORTED_VERSION


def test_a_well_formed_open_still_decodes() -> None:
    """The refusal must not have narrowed what a working session sends.

    Both tests above are satisfied by a decoder which refuses every OPEN, so one of them
    has to read one and check what it says.
    """
    decoded = Message.unpack(int(Message.CODE.OPEN), WELL_FORMED, Negotiated.UNSET)

    assert isinstance(decoded, Open)
    assert decoded.asn == 65000
    assert decoded.hold_time == 180
    assert str(decoded.router_id) == '1.2.3.4'


# RFC 4271 6.1 states two requirements and the subcode is only the first.  The second:
#
#     The Data field MUST contain the erroneous Length field.
#
# Every one of these sent a sentence describing the problem instead, so a peer reading
# those octets as the two byte Length the RFC promises got ASCII.  Session 5.0 found it,
# and found that Notify could not carry the octets at all: its constructor ended in
# bytes(data, 'ascii'), so text was the only thing that fitted.

BGP_HEADER_LENGTH = 19
LENGTH_FIELD_SIZE = 2

# message type, a body length below that type's minimum
SHORT_MESSAGES = [
    ('open', int(Message.CODE.OPEN), 4),
    ('open at the boundary', int(Message.CODE.OPEN), 9),
    ('update', int(Message.CODE.UPDATE), 2),
    ('keepalive with a payload', int(Message.CODE.KEEPALIVE), 5),
]


@pytest.mark.parametrize('name, code, body', SHORT_MESSAGES, ids=[row[0] for row in SHORT_MESSAGES])
def test_the_data_field_carries_the_erroneous_length(name: str, code: int, body: int) -> None:
    """Two octets holding the header Length, which is nineteen plus the body."""
    with pytest.raises(Notify) as caught:
        Message.unpack(code, bytes(body), Negotiated.UNSET)

    assert caught.value.code == MESSAGE_HEADER_ERROR
    assert caught.value.subcode == BAD_MESSAGE_LENGTH

    data = bytes(caught.value.data)
    assert len(data) == LENGTH_FIELD_SIZE, f'{name} sent {data!r} where the RFC asks for the Length field'
    assert unpack('!H', data)[0] == BGP_HEADER_LENGTH + body, f'{name} reported the wrong Length'
