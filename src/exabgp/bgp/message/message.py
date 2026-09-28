"""message.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import TYPE_CHECKING, Any, ClassVar, Type, TypeVar, final

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated


_M = TypeVar('_M', bound='Message')


class _MessageCode(int):
    OPEN: ClassVar[int] = 0x01  # .          1
    UPDATE: ClassVar[int] = 0x02  # .        2
    NOTIFICATION: ClassVar[int] = 0x03  # .  3
    KEEPALIVE: ClassVar[int] = 0x04  # .     4
    ROUTE_REFRESH: ClassVar[int] = 0x05  # . 5
    OPERATIONAL: ClassVar[int] = 0x06  # .   6  # Not IANA assigned yet

    names: ClassVar[dict[int | None, str]] = {
        None: 'INVALID',
        OPEN: 'OPEN',
        UPDATE: 'UPDATE',
        NOTIFICATION: 'NOTIFICATION',
        KEEPALIVE: 'KEEPALIVE',
        ROUTE_REFRESH: 'ROUTE_REFRESH',
        OPERATIONAL: 'OPERATIONAL',
    }

    short_names: ClassVar[dict[int | None, str]] = {
        None: 'invalid',
        OPEN: 'open',
        UPDATE: 'update',
        NOTIFICATION: 'notification',
        KEEPALIVE: 'keepalive',
        ROUTE_REFRESH: 'refresh',
        OPERATIONAL: 'operational',
    }

    long_names: ClassVar[dict[int | None, str]] = {
        None: 'invalid',
        OPEN: 'open',
        UPDATE: 'update',
        NOTIFICATION: 'notification',
        KEEPALIVE: 'keepalive',
        ROUTE_REFRESH: 'route-refresh',
        OPERATIONAL: 'operational',
    }

    # to_short_names = dict((name,code) for (code,name) in short_names.items())

    SHORT: str
    NAME: str

    def __init__(self, value: int) -> None:
        self.SHORT = self.short()
        self.NAME = str(self)

    def __str__(self) -> str:
        return self.names.get(self, 'unknown message {}'.format(hex(self)))

    def __repr__(self) -> str:
        return str(self)

    def short(self) -> str:
        return self.short_names.get(self, '{}'.format(self))


# ================================================================== BGP Message
#

# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                                                               |
# +                                                               +
# |                                                               |
# +                                                               +
# |                           Marker                              |
# +                                                               +
# |                                                               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |          Length               |      Type     |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


class Message:
    """A BGP message: the body it was built from, and the framing every message shares.

    The contract (.claude/exabgp/BGP_MESSAGE_INTERFACE.md, enforced by
    tests/unit/bgp/message/test_message_contract.py):

    - ID is the type octet, TYPE is derived from it and never declared by a subclass
    - FIXED_SIZE is the part of the body every message of the type has, LENGTH_MIN is
      derived from it, LENGTH_MAX bounds the whole message, header included
    - a subclass says what its body is with pack_body(), and nothing else: the header,
      the framing and the length rules belong here
    - a message is its bytes: _packed is the body it was built from, every field is read
      from it, and two messages are equal when their type and their body are
    """

    MARKER: ClassVar[bytes] = bytes([0xFF] * 16)
    HEADER_LEN: ClassVar[int] = 19

    # RFC 4271 4.1: the largest message; RFC 8654 raises it for all but OPEN and KEEPALIVE
    STANDARD_MAX: ClassVar[int] = 4096
    EXTENDED_MAX: ClassVar[int] = 65535

    registered_message: ClassVar[dict[int, Type[Message]]] = {}

    ID: ClassVar[int]
    TYPE: ClassVar[bytes]

    _packed: Buffer

    # the octets of the body before its variable part, which every message of the type has
    FIXED_SIZE: ClassVar[int] = 0
    # the whole message, header included; the session's own maximum is checked apart
    LENGTH_MIN: ClassVar[int] = HEADER_LEN
    LENGTH_MAX: ClassVar[int] = EXTENDED_MAX

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # a class is defined once, at import, and must be refused under -O too
        for derived, source in (('TYPE', 'ID'), ('LENGTH_MIN', 'FIXED_SIZE')):
            if derived in vars(cls):
                raise TypeError(f'{cls.__qualname__}: {derived} is derived from {source}, not declared')
        if not 0 <= cls.ID <= 0xFF:
            raise TypeError(f'{cls.__qualname__}: the type of a message is one octet')
        cls.TYPE = bytes([cls.ID])
        cls.LENGTH_MIN = cls.HEADER_LEN + cls.FIXED_SIZE
        assert cls.HEADER_LEN <= cls.LENGTH_MIN <= cls.LENGTH_MAX <= cls.EXTENDED_MAX

    class CODE:
        OPEN: ClassVar[_MessageCode] = _MessageCode(_MessageCode.OPEN)
        UPDATE: ClassVar[_MessageCode] = _MessageCode(_MessageCode.UPDATE)
        NOTIFICATION: ClassVar[_MessageCode] = _MessageCode(_MessageCode.NOTIFICATION)
        KEEPALIVE: ClassVar[_MessageCode] = _MessageCode(_MessageCode.KEEPALIVE)
        ROUTE_REFRESH: ClassVar[_MessageCode] = _MessageCode(_MessageCode.ROUTE_REFRESH)
        OPERATIONAL: ClassVar[_MessageCode] = _MessageCode(_MessageCode.OPERATIONAL)

        MESSAGES: ClassVar[list[_MessageCode]] = [
            OPEN,
            UPDATE,
            NOTIFICATION,
            KEEPALIVE,
            ROUTE_REFRESH,
            OPERATIONAL,
        ]

        @staticmethod
        def name(message_id: int | None) -> str:
            if message_id is None:
                return _MessageCode.names.get(message_id, 'unknown message')
            return _MessageCode.names.get(message_id, 'unknown message {}'.format(hex(message_id)))

        @staticmethod
        def short(message_id: int | None) -> str:
            if message_id is None:
                return _MessageCode.short_names.get(message_id, 'unknown message')
            return _MessageCode.short_names.get(message_id, 'unknown message {}'.format(hex(message_id)))

        def __init__(self) -> None:
            raise RuntimeError('This class can not be instantiated')

    def __eq__(self, other: object) -> bool:
        # `other` can be anything a caller compares with, so only here is its class asked
        if not isinstance(other, Message):
            return NotImplemented
        return self.ID == other.ID and bytes(self._packed) == bytes(other._packed)

    def __hash__(self) -> int:
        return hash((self.ID, bytes(self._packed)))

    @classmethod
    def length_valid(cls, code: int, length: int) -> bool:
        """Whether `length`, header included, is one a message of type `code` can have.

        A type nobody registered is refused by its type (RFC 4271 6.1, Bad Message Type),
        so only the header bounds it here.
        """
        klass = cls.registered_message.get(code)
        if klass is None:
            return length >= cls.HEADER_LEN
        return klass.LENGTH_MIN <= length <= klass.LENGTH_MAX

    @staticmethod
    def string(code: int | None) -> str:
        return _MessageCode.long_names.get(code, 'unknown')

    @classmethod
    def frame(cls, code: int, body: Buffer) -> bytes:
        """The complete message: marker, length and type, then the body."""
        assert 0 <= code <= 0xFF, 'the type of a message is one octet'
        # what we build, never what a peer sent, but it must hold under -O: the length field
        # is two octets, and a larger body would go out with a length which lies about it
        if cls.HEADER_LEN + len(body) > cls.EXTENDED_MAX:
            raise RuntimeError(f'a message body of {len(body)} octets does not fit a BGP message')
        return cls.MARKER + pack('!H', cls.HEADER_LEN + len(body)) + bytes([code]) + bytes(body)

    def pack_body(self, negotiated: Negotiated) -> Buffer:
        """The body of the message, what follows the header on the wire."""
        raise NotImplementedError(f'{type(self).__qualname__} does not say what its body is')

    @final
    def pack_message(self, negotiated: Negotiated) -> bytes:
        return self.frame(self.ID, self.pack_body(negotiated))

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: Negotiated) -> Message:
        raise NotImplementedError('unpack_message not implemented in subclass')

    @classmethod
    def register(cls, klass: Type[_M]) -> Type[_M]:
        if klass.ID in cls.registered_message:
            raise RuntimeError('only one class can be registered per message')
        cls.registered_message[klass.ID] = klass
        return klass

    @classmethod
    def klass(cls, what: int) -> Type[Message]:
        if what in cls.registered_message:
            return cls.registered_message[what]
        from exabgp.bgp.message.notification import Notify

        # RFC 4271 6.1: an unrecognised Type field is Bad Message Type, the same answer
        # unpack gives below.  This was 2/4, Unsupported Optional Parameter, an OPEN error
        raise Notify(1, 3, f'type {what}', data=bytes([what]))

    @classmethod
    def unpack(cls, message: int, data: Buffer, negotiated: Negotiated) -> Message:
        """Unpack a BGP message from wire format.

        Args:
            message: BGP message type code
            data: Message body as Buffer (bytes, memoryview, etc. - PEP 688)
            negotiated: Negotiated capabilities for this session

        Returns:
            Parsed Message subclass instance
        """
        if message in cls.registered_message:
            return cls.klass(message).unpack_message(data, negotiated)
        # klass_unknown was declared here and bound by unknown.py, which nothing imports,
        # so this line raised AttributeError for every unregistered code.  The reactor's
        # catch-all laundered it into Notify(1, 0, 'can not decode update message of type
        # 252'), which names the wrong error and the wrong message.  RFC 4271 6.1: an
        # unrecognised Type field is Bad Message Type
        from exabgp.bgp.message.notification import Notify

        raise Notify(1, 3, f'type {message}', data=bytes([message]))
