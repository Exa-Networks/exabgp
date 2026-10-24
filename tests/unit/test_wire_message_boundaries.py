#!/usr/bin/env python3
# encoding: utf-8

"""What a peer can send before we have decided the message is well formed

Three places read a fixed number of bytes off a peer supplied buffer without
checking the bytes were there, so the failure was a raw Python exception out of
the message parser rather than a NOTIFICATION:

    Update.split                 computed `length = len(data)` and then never
                                 consulted it, unpacking the two mandatory 2 byte
                                 length fields of RFC 4271 4.3 regardless.  A one
                                 byte UPDATE body raised struct.error.

    Notification.unpack_message  read data[0] and data[1] with nothing checking
                                 the body carried them, so an empty NOTIFICATION
                                 raised IndexError.

    Message.unpack               fell through to klass_unknown, which is bound to
                                 Exception unless exabgp.bgp.message.unknown is
                                 imported and nothing imports it.  So it
                                 CONSTRUCTED an Exception and returned it as if it
                                 were a message.  Type 0 is in CODE.MESSAGES, so it
                                 passes the reactor's own check and got here from
                                 the wire.

None of the three was reachable by the fuzz suite, whose assertions were

    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt))

SystemExit and KeyboardInterrupt derive from BaseException, so `except Exception`
can never bind either and the assertion could not fail. Every one of these bugs
passed it.
"""

from struct import pack

from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Message
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notification, Notify
from exabgp.bgp.message.update import Update

# the registry is keyed by the int-like message code, while Notification.TYPE is
# b'\x03' and does not match it; the reactor passes the code, so tests do too
NOTIFICATION = 3


@pytest.fixture(autouse=True)
def mocked_logger():
    """The parsers log, and the logger is not initialised under pytest"""
    from exabgp.logger.option import option

    saved = option.logger
    option.logger = Mock()
    yield
    option.logger = saved


def negotiated():
    stub = Mock()
    stub.families = []
    stub.asn4 = True
    return stub


# a well formed, empty UPDATE: no withdrawn routes, no path attributes
EMPTY_UPDATE = pack('!HH', 0, 0)


HEADER_LEN = 19  # RFC 4271 4.1


def bad_message_length(caught, body_size):
    """RFC 4271 6.1 asks for a specific code, subcode AND data field

    "if the Length field of an OPEN message is less than the minimum length of
    the OPEN message ... then the Error Subcode MUST be set to Bad Message
    Length. The Data field MUST contain the erroneous Length field."

    The Length field is the one in the header, so it counts the 19 header octets
    the body arrives without.
    """
    assert (caught.code, caught.subcode) == (1, 2)
    assert caught.data == pack('!H', HEADER_LEN + body_size), 'the data must be the erroneous Length field'


class TestATruncatedUpdate:
    def test_the_one_byte_body_which_raised_struct_error(self) -> None:
        with pytest.raises(Notify) as caught:
            Update.unpack_message(bytes([0x4F]), Direction.IN, negotiated())
        bad_message_length(caught.value, 1)

    @pytest.mark.parametrize('size', [0, 1, 2, 3])
    def test_anything_too_short_for_the_two_length_fields(self, size) -> None:
        with pytest.raises(Notify) as caught:
            Update.unpack_message(bytes(size), Direction.IN, negotiated())
        # a header Length error, NOT 3/1 Malformed Attribute List: 6.3 is for
        # the lengths inside a message which is itself long enough
        bad_message_length(caught.value, size)

    def test_a_withdrawn_length_which_eats_the_attribute_length(self) -> None:
        # says 2 bytes of withdrawn routes and supplies them, leaving nothing for
        # the total path attribute length which must follow
        wire = pack('!H', 2) + bytes([0, 0])
        with pytest.raises(Notify) as caught:
            Update.unpack_message(wire, Direction.IN, negotiated())
        # the message is long enough, its own lengths are not consistent, which
        # RFC 4271 6.3 calls a Malformed Attribute List
        assert (caught.value.code, caught.value.subcode) == (3, 1)

    def test_the_empty_update_still_decodes(self) -> None:
        # the gate must not refuse the smallest well formed UPDATE there is
        assert Update.unpack_message(EMPTY_UPDATE, Direction.IN, negotiated()) is not None


class TestATruncatedNotification:
    """RFC 4271 6.5: close the connection, do NOT send a NOTIFICATION back

    Returning a Notification is what does that here. protocol.py raises the
    parsed object and the reactor resets in silence, where raising Notify would
    have us answer a malformed NOTIFICATION with one of our own.
    """

    @pytest.mark.parametrize('size', [0, 1])
    def test_it_closes_rather_than_raising_indexerror(self, size) -> None:
        result = Message.unpack(NOTIFICATION, bytes(size), Direction.IN, negotiated())
        assert isinstance(result, Notification)

    @pytest.mark.parametrize('size', [0, 1])
    def test_and_it_is_not_a_notify(self, size) -> None:
        # a Notify would make the reactor send a NOTIFICATION in reply, which
        # 6.5 forbids.  Notify subclasses Notification, so isinstance above
        # cannot tell them apart and this is the assertion which can
        result = Message.unpack(NOTIFICATION, bytes(size), Direction.IN, negotiated())
        assert not isinstance(result, Notify)

    def test_a_well_formed_notification_still_reads_its_code(self) -> None:
        result = Message.unpack(NOTIFICATION, bytes([6, 2]), Direction.IN, negotiated())
        assert (result.code, result.subcode) == (6, 2)


class TestAnUnknownMessageType:
    @pytest.mark.parametrize('msg_type', [0, 7, 100, 252, 255])
    def test_it_is_bad_message_type(self, msg_type) -> None:
        with pytest.raises(Notify) as caught:
            Message.unpack(msg_type, bytes([1, 2, 3]), Direction.IN, negotiated())
        # RFC 4271 6.1
        assert (caught.value.code, caught.value.subcode) == (1, 3)

    def test_it_no_longer_returns_something_which_is_not_a_message(self) -> None:
        # the defect: an Exception instance was constructed and RETURNED, so the
        # caller went on to read .TYPE off it
        try:
            result = Message.unpack(0, bytes([1, 2, 3]), Direction.IN, negotiated())
        except Notify:
            return
        pytest.fail(f'returned {type(result).__name__} instead of refusing')

    @pytest.mark.parametrize('msg_type', [1, 2, 3, 4])
    def test_a_registered_type_is_untouched(self, msg_type) -> None:
        # the gate must refuse only what is genuinely unregistered
        assert msg_type in Message.registered_message


class TestNothingRawEscapesTheMessageParser:
    """The property the dead fuzz assertion was reaching for

    Notify and Notification are answers. Anything else is a traceback in the
    reactor, on input a peer chose.
    """

    @pytest.mark.parametrize('msg_type', [1, 2, 3, 4, 5])
    @pytest.mark.parametrize('size', list(range(0, 12)))
    def test_over_every_short_body(self, msg_type, size) -> None:
        try:
            Message.unpack(msg_type, bytes(size), Direction.IN, negotiated())
        except (Notify, Notification):
            pass
        except Exception as exc:  # noqa: BLE001 - naming it is the assertion
            pytest.fail(f'type {msg_type} with {size} bytes raised {type(exc).__name__}: {exc}')


class TestATruncatedOpen:
    @pytest.mark.parametrize('size', [0, 1, 5, 9])
    def test_below_the_ten_byte_fixed_header(self, size) -> None:
        with pytest.raises(Notify) as caught:
            Message.unpack(1, bytes(size), Direction.IN, negotiated())
        bad_message_length(caught.value, size)

    def test_the_smallest_valid_open_is_accepted(self) -> None:
        # version 4, AS, hold time, identifier, no optional parameters
        body = bytes([4]) + pack('!HH', 65000, 180) + bytes([10, 0, 0, 1]) + bytes([0])
        assert Message.unpack(1, body, Direction.IN, negotiated()) is not None


class TestAKeepaliveWithAPayload:
    """RFC 4271 4.4: a KEEPALIVE is the header and nothing else

    The refusal read `Notify(text, hexstring(data))`: the text became the code
    and the hexstring became the subcode, neither was ever formatted, and
    message() would have raised on bytes([self.code, self.subcode]) rather than
    sending anything at all. A peer only had to attach one byte.
    """

    @pytest.mark.parametrize('size', [1, 2, 40])
    def test_it_is_bad_message_length(self, size) -> None:
        with pytest.raises(Notify) as caught:
            Message.unpack(4, bytes(size), Direction.IN, negotiated())
        bad_message_length(caught.value, size)

    @pytest.mark.parametrize('size', [1, 40])
    def test_and_the_refusal_can_actually_be_sent(self, size) -> None:
        # the assertion the old code fails: code and subcode must be integers,
        # because message() packs them as bytes
        with pytest.raises(Notify) as caught:
            Message.unpack(4, bytes(size), Direction.IN, negotiated())
        assert isinstance(caught.value.code, int)
        assert isinstance(caught.value.subcode, int)
        assert caught.value.message()

    def test_an_empty_keepalive_is_still_accepted(self) -> None:
        assert Message.unpack(4, b'', Direction.IN, negotiated()) is not None
