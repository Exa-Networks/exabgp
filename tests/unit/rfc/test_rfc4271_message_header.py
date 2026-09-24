"""RFC 4271 sections 4.1 and 6.1: the nineteen octets in front of every BGP message.

Each test here puts bytes on one end of a socket pair and lets a real `Outgoing`
connection and a real `Protocol` read them, because the header is not parsed by any
message class: the marker, the Length field and the per-type minimum lengths are all
checked in `reactor/network/connection.py`, and the type is checked in
`reactor/protocol.py`.  A test calling a message decoder would skip every one of those.

Two of the requirements below were findings and are now regression tests: a Bad Message
Length used to be reported with an English sentence where the RFC asks for the two octets
of the Length field, and an unrecognised Type field used to be answered Unspecific rather
than Bad Message Type.  Both are answered in `reactor/protocol.py`, which is why they are
tested through a real connection here rather than against a decoder.
"""

from __future__ import annotations

import asyncio
import socket
from collections import defaultdict
from struct import pack
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message import KeepAlive, Message, Notification, Notify, Open
from exabgp.bgp.message.open import ASN, Capabilities, HoldTime, RouterID, Version
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.neighbor import Neighbor
from exabgp.protocol.family import AFI
from exabgp.reactor.network.outgoing import Outgoing
from exabgp.reactor.protocol import Protocol

MARKER = bytes([0xFF] * 16)

MESSAGE_HEADER_ERROR = 1
CONNECTION_NOT_SYNCHRONIZED = 1
BAD_MESSAGE_LENGTH = 2
BAD_MESSAGE_TYPE = 3

OPEN = 1
UPDATE = 2
NOTIFICATION = 3
KEEPALIVE = 4

# read_message indexes these three rather than using .get, so a Neighbor built outside the
# configuration parser has to carry them before it can be read from.
API_KEYS = ('receive-packets', 'receive-consolidate', 'receive-parsed')


def header(length: int, message_type: int) -> bytes:
    """A well formed header, for whatever the caller wants to be wrong about."""
    return MARKER + pack('!H', length) + bytes([message_type])


def _read(wire: bytes) -> Message:
    """Hand `wire` to a real connection and a real Protocol, and return what came back.

    The only stand-in is the Peer, which read_message uses for its statistics counter and
    for the API fan-out we switch off above.  Everything which looks at the bytes is the
    production code.
    """

    async def run() -> Message:
        neighbor = Neighbor()
        for key in API_KEYS:
            neighbor.api[key] = False
        peer = Mock()
        peer.neighbor = neighbor
        peer.stats = defaultdict(int)

        protocol = Protocol(peer)
        ours, theirs = socket.socketpair()
        ours.setblocking(False)
        connection = Outgoing(AFI.ipv4, 'peer', 'local')
        connection.io = ours
        protocol.connection = connection
        try:
            theirs.sendall(wire)
            return await protocol.read_message()
        finally:
            theirs.close()
            connection.close()

    return asyncio.run(run())


def refused(wire: bytes) -> Notification:
    """The NOTIFICATION a peer would be sent for `wire`, or a failure if it was accepted."""
    try:
        message = _read(wire)
    except Notification as notification:
        return notification
    pytest.fail(f'{wire.hex()} was accepted and decoded as {message}')


def accepted(wire: bytes) -> Message:
    """The message `wire` decoded to, or a failure if it was refused."""
    try:
        return _read(wire)
    except Notification as notification:
        pytest.fail(f'{wire.hex()} was refused with {notification.code}/{notification.subcode}: {notification}')


def our_messages() -> list[Message]:
    """One of each message we generate ourselves, packed the way we would send it."""
    return [
        KeepAlive.make_keepalive(),
        Notify(6, 2, 'administrative shutdown'),
        Open.make_open(Version(4), ASN(65000), HoldTime(180), RouterID('192.0.2.1'), Capabilities()),
    ]


# ----------------------------------------------------------------- 4.1 the marker we send


@pytest.mark.rfc('rfc4271#4.1-marker-all-ones')
def test_every_message_we_send_carries_the_all_ones_marker() -> None:
    """Not Message.MARKER read back, but the first sixteen octets of the packed message."""
    for message in our_messages():
        wire = bytes(message.pack_message(Negotiated.UNSET))
        assert wire[:16] == MARKER, f'{message.__class__.__name__} went out with marker {wire[:16].hex()}'


# ------------------------------------------------------------------ 4.1 the length field


@pytest.mark.rfc('rfc4271#4.1-length-between-19-and-4096')
def test_the_length_we_send_is_the_length_of_the_message() -> None:
    """At least 19, no more than 4096, and equal to what we actually wrote."""
    for message in our_messages():
        wire = bytes(message.pack_message(Negotiated.UNSET))
        length = int.from_bytes(wire[16:18], 'big')
        assert length == len(wire), f'{message.__class__.__name__} announced {length} and wrote {len(wire)}'
        assert 19 <= length <= 4096, f'{message.__class__.__name__} announced a length of {length}'


@pytest.mark.parametrize('length', [0, 1, 18, 4097, 65535], ids=lambda value: f'length {value}')
@pytest.mark.rfc('rfc4271#4.1-length-between-19-and-4096', polarity='negative')
def test_a_length_outside_the_bounds_is_refused(length: int) -> None:
    """The bound applied on receipt is 4096 until Extended Message is negotiated."""
    notification = refused(header(length, KEEPALIVE))

    assert notification.code == MESSAGE_HEADER_ERROR
    assert notification.subcode == BAD_MESSAGE_LENGTH


# --------------------------------------------------------------- 6.1 the error code used


@pytest.mark.parametrize(
    'wire',
    [
        bytes(16) + pack('!H', 19) + bytes([KEEPALIVE]),
        header(18, KEEPALIVE),
        header(4097, UPDATE),
        header(20, KEEPALIVE),
    ],
    ids=['bad marker', 'length below 19', 'length above 4096', 'keepalive not 19'],
)
@pytest.mark.rfc('rfc4271#6.1-errors-use-the-message-header-error-code')
def test_a_header_error_is_reported_as_a_message_header_error(wire: bytes) -> None:
    notification = refused(wire)

    assert notification.code == MESSAGE_HEADER_ERROR, (
        f'a header error was reported as error code {notification.code}: {notification}'
    )


@pytest.mark.rfc('rfc4271#6.1-errors-use-the-message-header-error-code', polarity='negative')
def test_a_well_formed_header_is_not_reported_as_an_error() -> None:
    """Without this the file passes with a reader which refuses everything it is given."""
    assert isinstance(accepted(header(19, KEEPALIVE)), KeepAlive)


# ------------------------------------------------------------------------ 6.1 the marker


@pytest.mark.parametrize(
    'marker',
    [bytes(16), bytes([0xFE]) + bytes([0xFF]) * 15, bytes([0xFF]) * 15 + bytes([0x00])],
    ids=['all zero', 'first octet wrong', 'last octet wrong'],
)
@pytest.mark.rfc('rfc4271#6.1-marker-connection-not-synchronized')
def test_a_marker_which_is_not_all_ones_is_a_synchronization_error(marker: bytes) -> None:
    """One wrong bit anywhere in the sixteen octets, not only a marker of zeros."""
    notification = refused(marker + pack('!H', 19) + bytes([KEEPALIVE]))

    assert notification.code == MESSAGE_HEADER_ERROR
    assert notification.subcode == CONNECTION_NOT_SYNCHRONIZED


@pytest.mark.rfc('rfc4271#6.1-marker-connection-not-synchronized', polarity='negative')
def test_the_expected_marker_is_accepted() -> None:
    assert isinstance(accepted(header(19, KEEPALIVE)), KeepAlive)


# ------------------------------------------------------------------- 6.1 the length field

# The five cases RFC 4271 6.1 lists, each with a length the sentence makes illegal.
TOO_SHORT_OR_TOO_LONG = [
    (18, KEEPALIVE, 'header below 19'),
    (4097, UPDATE, 'header above 4096'),
    (28, OPEN, 'open below 29'),
    (22, UPDATE, 'update below 23'),
    (20, KEEPALIVE, 'keepalive not 19'),
    (18, KEEPALIVE, 'keepalive below 19'),
    (20, NOTIFICATION, 'notification below 21'),
]


@pytest.mark.parametrize(
    'length,message_type',
    [(length, message_type) for length, message_type, _ in TOO_SHORT_OR_TOO_LONG],
    ids=[name for _, _, name in TOO_SHORT_OR_TOO_LONG],
)
@pytest.mark.rfc('rfc4271#6.1-bad-message-length')
def test_a_length_the_rfc_forbids_is_a_bad_message_length(length: int, message_type: int) -> None:
    notification = refused(header(length, message_type))

    assert notification.code == MESSAGE_HEADER_ERROR
    assert notification.subcode == BAD_MESSAGE_LENGTH


# The smallest length each message type is allowed to have.  A body of zeros will be
# refused by most of these decoders for its own reasons, which is not this test's
# business; what matters is that the refusal is not Bad Message Length.
SMALLEST_LEGAL = [
    (29, OPEN, 'open'),
    (23, UPDATE, 'update'),
    (21, NOTIFICATION, 'notification'),
    (19, KEEPALIVE, 'keepalive'),
]


@pytest.mark.parametrize(
    'length,message_type',
    [(length, message_type) for length, message_type, _ in SMALLEST_LEGAL],
    ids=[name for _, _, name in SMALLEST_LEGAL],
)
@pytest.mark.rfc('rfc4271#6.1-bad-message-length', polarity='negative')
def test_the_smallest_legal_length_is_not_a_bad_message_length(length: int, message_type: int) -> None:
    """The boundary is the assertion worth making: off by one either way fails one half."""
    wire = header(length, message_type) + bytes(length - 19)
    try:
        _read(wire)
    except Notification as notification:
        assert not (notification.code == MESSAGE_HEADER_ERROR and notification.subcode == BAD_MESSAGE_LENGTH), (
            f'a {length} octet message of type {message_type} was called a bad message length'
        )


@pytest.mark.rfc('rfc4271#6.1-bad-message-length-data-field')
def test_a_bad_message_length_carries_the_erroneous_length() -> None:
    notification = refused(header(18, KEEPALIVE))

    assert notification.data == pack('!H', 18)


def test_the_in_parser_length_checks_do_carry_the_erroneous_length() -> None:
    """Unmarked: the other path to the same answer, which must keep giving it.

    Open, KeepAlive and UpdateCollection.split each raise Notify(1, 2, pack('!H', length))
    when the body they are handed is too short.  They are reached for a body which arrived
    shorter than its header claimed; the header check above is reached when the Length
    field itself is wrong, and that is the commoner case and the one which had the bug.
    """
    for message_type, body in ((OPEN, bytes(5)), (KEEPALIVE, bytes(1)), (UPDATE, bytes(2))):
        with pytest.raises(Notify) as caught:
            Message.unpack(message_type, body, Negotiated.UNSET)
        assert (caught.value.code, caught.value.subcode) == (MESSAGE_HEADER_ERROR, BAD_MESSAGE_LENGTH)
        assert caught.value.data == pack('!H', 19 + len(body))


# --------------------------------------------------------------------- 6.1 the type field


@pytest.mark.parametrize('message_type', [0, 7, 8, 100, 255], ids=lambda value: f'type {value}')
@pytest.mark.rfc('rfc4271#6.1-bad-message-type')
def test_an_unrecognised_message_type_is_a_bad_message_type(message_type: int) -> None:
    notification = refused(header(19, message_type))

    assert notification.code == MESSAGE_HEADER_ERROR
    assert notification.subcode == BAD_MESSAGE_TYPE


@pytest.mark.parametrize(
    'length,message_type',
    [(length, message_type) for length, message_type, _ in SMALLEST_LEGAL],
    ids=[name for _, _, name in SMALLEST_LEGAL],
)
@pytest.mark.rfc('rfc4271#6.1-bad-message-type', polarity='negative')
def test_a_recognised_message_type_is_never_called_a_bad_type(length: int, message_type: int) -> None:
    """A refusal which called OPEN an unknown type would mean dispatch had stopped working."""
    wire = header(length, message_type) + bytes(length - 19)
    try:
        _read(wire)
    except Notification as notification:
        assert not (notification.code == MESSAGE_HEADER_ERROR and notification.subcode == BAD_MESSAGE_TYPE), (
            f'type {message_type} has a decoder but was refused as unrecognised'
        )


def test_the_decoder_itself_answers_bad_message_type() -> None:
    """Unmarked: the decoder's own answer, which the reactor gate above shadows.

    The gate in read_message refuses an unrecognised type before any decoder is reached,
    so this is the half a peer never sees.  It is kept because the two have to agree.
    """
    unused: Any = Negotiated.UNSET
    with pytest.raises(Notify) as caught:
        Message.unpack(7, b'', unused)
    assert (caught.value.code, caught.value.subcode) == (MESSAGE_HEADER_ERROR, BAD_MESSAGE_TYPE)
