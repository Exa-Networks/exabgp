"""Three RFC 4271 answers a peer could not act on.

**4.3, the unused Attribute Flags bits.** "The lower-order four bits of the Attribute
Flags octet are unused.  They MUST be zero when sent and MUST be ignored when received."
We sent them zero.  We did not ignore them: the attribute registry is keyed on (type code,
flags) and only Extended Length was normalised away, so an ORIGIN arriving with flags 0x41
missed the lookup, was not recognised, and the route was withdrawn.  A peer which set a
reserved bit lost its routes.

**6.1, Bad Message Length.** "The Data field MUST contain the erroneous Length field."
`Connection.reader` builds `NotifyError(1, 2, '<type> has an invalid message length of
<n>')` and `reactor/protocol.py` turned that sentence into the Data field, so the peer
received ASCII where the RFC asks for two octets.  The three in-parser length checks
already sent the length; the header path, which is the one a peer actually reaches, did
not.

**6.2, an unrecognised OPEN Optional Parameter.** "If one of the Optional Parameters in
the OPEN message is not recognized, then the Error Subcode MUST be set to Unsupported
Optional Parameters."  We answered 2/0 Unspecific, which the next sentence of 6.2 reserves
for a parameter we do recognise and which is malformed, so a peer could not tell the two
apart.

Not here: an unrecognised message Type.  This branch already answers 1/3 Bad Message Type
at the gate in `read_message`.
"""

from __future__ import annotations

import socket
from collections import defaultdict
from struct import pack
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.neighbor import Neighbor
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notification, Notify
from exabgp.bgp.message.open.capability.capabilities import Capabilities
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.attributes import Attributes
from exabgp.protocol.family import AFI
from exabgp.reactor.network.outgoing import Outgoing
from exabgp.reactor.protocol import Protocol

MARKER = bytes([0xFF] * 16)

MESSAGE_HEADER_ERROR = 1
BAD_MESSAGE_LENGTH = 2

OPEN_MESSAGE_ERROR = 2
UNSPECIFIC = 0
UNSUPPORTED_OPTIONAL_PARAMETER = 4

KEEPALIVE = 4

WELL_KNOWN_TRANSITIVE = 0x40
OPTIONAL = 0x80

# read_message drives a generator over the connection; a handful of rounds is more than
# the one the header path needs and keeps a misbehaving reader from spinning the suite
MAX_READ_ROUNDS = 8


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


# ------------------------------------------------------ 4.3 the four unused flag bits


def one_attribute(flag: int, code: int, value: bytes) -> bytes:
    return bytes([flag, code, len(value)]) + value


@pytest.mark.parametrize('bits', [0x01, 0x02, 0x04, 0x08, 0x0F], ids=lambda value: f'bits {value:#04x}')
def test_the_four_unused_flag_bits_are_ignored(bits: int) -> None:
    """A peer which sets a reserved bit must still be understood, not have its route dropped."""
    parsed = Attributes.unpack(
        one_attribute(WELL_KNOWN_TRANSITIVE | bits, Attribute.CODE.ORIGIN, bytes(1)), Direction.IN, negotiated()
    )

    assert Attribute.CODE.ORIGIN in parsed, f'an ORIGIN with unused bits {bits:#04x} set was not recognised'
    assert Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW not in parsed, 'the route was withdrawn over a reserved bit'


@pytest.mark.parametrize('bits', [0x00, 0x01, 0x0F], ids=lambda value: f'bits {value:#04x}')
def test_a_genuine_flag_conflict_is_still_a_conflict(bits: int) -> None:
    """Optional, Transitive and Partial identify the attribute and are not normalised away.

    Ignoring the four unused bits must not turn into ignoring the four that mean something:
    a well-known ORIGIN sent with the Optional bit set is a flag conflict, and the registry
    lookup missing is how `Attributes.parse` detects one.
    """
    assert not Attribute.registered(
        Attribute.CODE.ORIGIN, OPTIONAL | bits
    ), 'an ORIGIN marked Optional was accepted as a registered attribute'


def test_the_registry_key_is_built_the_same_way_on_every_path() -> None:
    """register(), registered(), klass() and unpack() must agree, or a lookup misses.

    unpack() built its own key inline, so normalising in the first three and not the last
    would leave the decode path missing for exactly the attributes the others now find.
    """
    flag = WELL_KNOWN_TRANSITIVE | 0x0F

    assert Attribute.registered(Attribute.CODE.ORIGIN, flag)
    assert Attribute.klass(Attribute.CODE.ORIGIN, flag) is not None
    assert Attribute.unpack(Attribute.CODE.ORIGIN, flag, bytes(1), Direction.IN, negotiated()) is not None


# ---------------------------------------------------------- 6.1 Bad Message Length data


def header(length: int, message_type: int) -> bytes:
    """A well formed header, for whatever the caller wants to be wrong about."""
    return MARKER + pack('!H', length) + bytes([message_type])


def refused(wire: bytes) -> Notification:
    """The NOTIFICATION a peer would be sent for `wire`, read by a real Protocol.

    The header is not parsed by any message class: the marker and the Length field are
    checked in `reactor/network/connection.py` and answered in `reactor/protocol.py`, so a
    test calling a decoder would skip both.
    """
    ours, theirs = socket.socketpair()
    ours.setblocking(False)

    connection = Outgoing(AFI.ipv4, 'peer', 'local')
    connection.io = ours

    # Neighbor.api is filled in by the configuration parser rather than the class, and
    # read_message indexes these three rather than using .get
    neighbor = Neighbor()
    neighbor.api = {'receive-packets': False, 'receive-consolidate': False, 'receive-parsed': False}

    peer = Mock()
    peer.neighbor = neighbor
    peer.stats = defaultdict(int)

    protocol = Protocol(peer)
    protocol.connection = connection

    try:
        theirs.sendall(wire)
        reader = protocol.read_message()
        for _ in range(MAX_READ_ROUNDS):
            next(reader)
    except Notification as notification:
        return notification
    finally:
        theirs.close()
        connection.io = None
        ours.close()

    pytest.fail(f'{wire.hex()} was accepted')


def test_a_bad_message_length_carries_the_erroneous_length() -> None:
    """RFC 4271 6.1: the Data field MUST contain the Length field the peer got wrong."""
    notification = refused(header(18, KEEPALIVE))

    assert (notification.code, notification.subcode) == (MESSAGE_HEADER_ERROR, BAD_MESSAGE_LENGTH)
    assert notification.data == pack(
        '!H', 18
    ), f'the peer was sent {notification.data!r} where RFC 4271 6.1 asks for the two octets of the Length'


def test_a_header_error_which_is_not_a_bad_length_keeps_its_sentence() -> None:
    """Only (1, 2) carries the Length; everything else still explains itself in the log."""
    notification = refused(bytes(16) + pack('!H', 19) + bytes([KEEPALIVE]))

    assert (notification.code, notification.subcode) == (MESSAGE_HEADER_ERROR, 1)
    assert b'marker' in notification.data.lower(), notification.data


# ------------------------------------------- 6.2 an unrecognised OPEN Optional Parameter


def optional_parameters(block: bytes) -> bytes:
    return bytes([len(block)]) + block


def parameter(kind: int, value: bytes) -> bytes:
    return bytes([kind, len(value)]) + value


@pytest.mark.parametrize('kind', [0, 3, 99, 255], ids=lambda value: f'parameter type {value}')
def test_an_unrecognised_optional_parameter_is_unsupported(kind: int) -> None:
    with pytest.raises(Notify) as caught:
        Capabilities.unpack(optional_parameters(parameter(kind, b'')))

    assert (caught.value.code, caught.value.subcode) == (OPEN_MESSAGE_ERROR, UNSUPPORTED_OPTIONAL_PARAMETER)


def test_a_recognised_but_malformed_parameter_is_unspecific() -> None:
    """The pair only means something if the other half stays 2/0.

    A capabilities parameter (type 2) whose declared length runs past the block is one we
    do recognise and which is malformed, which is what the next sentence of 6.2 covers.
    """
    with pytest.raises(Notify) as caught:
        Capabilities.unpack(optional_parameters(bytes([2, 10]) + b'\x00'))

    assert (caught.value.code, caught.value.subcode) == (OPEN_MESSAGE_ERROR, UNSPECIFIC)
