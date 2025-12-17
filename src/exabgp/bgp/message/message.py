"""message.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import TYPE_CHECKING, Callable, ClassVar, Type

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated


class _MessageCode(int):
    OPEN: ClassVar[int] = 0x01  # .          1
    UPDATE: ClassVar[int] = 0x02  # .        2
    NOTIFICATION: ClassVar[int] = 0x03  # .  3
    KEEPALIVE: ClassVar[int] = 0x04  # .     4
    ROUTE_REFRESH: ClassVar[int] = 0x05  # . 5
    OPERATIONAL: ClassVar[int] = 0x06  # .   6  # Not IANA assigned yet
    NOP: ClassVar[int] = 0xFC  # .           252 - internal - no data yet
    DONE: ClassVar[int] = 0xFD  # .          253 - internal - peer finished
    AWAKE: ClassVar[int] = 0xFE  # .         254 - internal - immediate action

    names: ClassVar[dict[int | None, str]] = {
        None: 'INVALID',
        NOP: 'NOP',
        AWAKE: 'AWAKE',
        DONE: 'DONE',
        OPEN: 'OPEN',
        UPDATE: 'UPDATE',
        NOTIFICATION: 'NOTIFICATION',
        KEEPALIVE: 'KEEPALIVE',
        ROUTE_REFRESH: 'ROUTE_REFRESH',
        OPERATIONAL: 'OPERATIONAL',
    }

    short_names: ClassVar[dict[int | None, str]] = {
        None: 'invalid',
        NOP: 'nop',
        AWAKE: 'awake',
        DONE: 'done',
        OPEN: 'open',
        UPDATE: 'update',
        NOTIFICATION: 'notification',
        KEEPALIVE: 'keepalive',
        ROUTE_REFRESH: 'refresh',
        OPERATIONAL: 'operational',
    }

    long_names: ClassVar[dict[int | None, str]] = {
        None: 'invalid',
        NOP: 'nop',
        AWAKE: 'awake',
        DONE: 'done',
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
    # we need to define TYPE inside __init__ of the subclasses
    # otherwise we can not dynamically create different UnknownMessage
    # TYPE = None

    MARKER: ClassVar[bytes] = bytes(
        [
            0xFF,
        ]
        * 16,
    )
    HEADER_LEN: ClassVar[int] = 19

    registered_message: ClassVar[dict[int, Type[Message]]] = {}
    klass_unknown: ClassVar[Callable[[int, Buffer, Negotiated], Message]]

    # TYPE attribute set by subclasses
    TYPE: ClassVar[bytes]
    ID: ClassVar[int]

    # Reactor scheduling - 0 (MESSAGE) for real BGP messages
    # Scheduling messages (NOP, AWAKE, DONE) set this to Scheduling.LATER/NOW/CLOSE
    SCHEDULING: int = 0  # Scheduling.MESSAGE

    class CODE:
        NOP: ClassVar[_MessageCode] = _MessageCode(_MessageCode.NOP)
        OPEN: ClassVar[_MessageCode] = _MessageCode(_MessageCode.OPEN)
        UPDATE: ClassVar[_MessageCode] = _MessageCode(_MessageCode.UPDATE)
        NOTIFICATION: ClassVar[_MessageCode] = _MessageCode(_MessageCode.NOTIFICATION)
        KEEPALIVE: ClassVar[_MessageCode] = _MessageCode(_MessageCode.KEEPALIVE)
        ROUTE_REFRESH: ClassVar[_MessageCode] = _MessageCode(_MessageCode.ROUTE_REFRESH)
        OPERATIONAL: ClassVar[_MessageCode] = _MessageCode(_MessageCode.OPERATIONAL)
        DONE: ClassVar[_MessageCode] = _MessageCode(_MessageCode.DONE)
        AWAKE: ClassVar[_MessageCode] = _MessageCode(_MessageCode.AWAKE)

        MESSAGES: ClassVar[list[_MessageCode]] = [
            NOP,
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

        # # Can raise KeyError
        # @staticmethod
        # def code (short):
        # 	return _MessageCode.names.get[short]

        def __init__(self) -> None:
            raise RuntimeError('This class can not be instantiated')

    Length: ClassVar[dict[int, Callable[[int], bool]]] = {
        CODE.OPEN: lambda _: _ >= 29,  # noqa
        CODE.UPDATE: lambda _: _ >= 23,  # noqa
        CODE.NOTIFICATION: lambda _: _ >= 21,  # noqa
        CODE.KEEPALIVE: lambda _: _ == 19,  # noqa
        CODE.ROUTE_REFRESH: lambda _: _ == 23,  # noqa
    }

    @staticmethod
    def string(code: int | None) -> str:
        return _MessageCode.long_names.get(code, 'unknown')

    def _message(self, message: Buffer) -> bytes:
        # Accept Buffer (bytes or memoryview), convert to bytes for output
        message_len: bytes = pack('!H', 19 + len(message))
        return self.MARKER + message_len + self.TYPE + bytes(message)

    def pack_message(self, negotiated: Negotiated) -> Buffer:
        raise NotImplementedError('message not implemented in subclasses')

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: Negotiated) -> Message:
        raise NotImplementedError('unpack_message not implemented in subclass')

    @classmethod
    def register(cls, klass: Type[Message]) -> Type[Message]:
        if klass.ID in cls.registered_message:
            raise RuntimeError('only one class can be registered per message')
        cls.registered_message[klass.ID] = klass
        return klass

    @classmethod
    def klass(cls, what: int) -> Type[Message]:
        if what in cls.registered_message:
            return cls.registered_message[what]
        from exabgp.bgp.message.notification import Notify

        raise Notify(2, 4, f'can not handle message {what}')

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
        return cls.klass_unknown(message, data, negotiated)

    @classmethod
    def code_from_name(cls, name: str) -> _MessageCode:
        for message in cls.CODE.MESSAGES:
            if name == str(message) or name == message.short():
                return message
        return cls.CODE.NOP
