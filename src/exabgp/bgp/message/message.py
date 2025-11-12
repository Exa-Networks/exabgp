"""message.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import Callable, ClassVar, Dict, List, Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated


class _MessageCode(int):
    NOP: ClassVar[int] = 0x00  # .           0 - internal
    OPEN: ClassVar[int] = 0x01  # .          1
    UPDATE: ClassVar[int] = 0x02  # .        2
    NOTIFICATION: ClassVar[int] = 0x03  # .  3
    KEEPALIVE: ClassVar[int] = 0x04  # .     4
    ROUTE_REFRESH: ClassVar[int] = 0x05  # . 5
    OPERATIONAL: ClassVar[int] = 0x06  # .   6  # Not IANA assigned yet

    names: ClassVar[Dict[Optional[int], str]] = {
        None: 'INVALID',
        NOP: 'NOP',
        OPEN: 'OPEN',
        UPDATE: 'UPDATE',
        NOTIFICATION: 'NOTIFICATION',
        KEEPALIVE: 'KEEPALIVE',
        ROUTE_REFRESH: 'ROUTE_REFRESH',
        OPERATIONAL: 'OPERATIONAL',
    }

    short_names: ClassVar[Dict[Optional[int], str]] = {
        None: 'invalid',
        NOP: 'nop',
        OPEN: 'open',
        UPDATE: 'update',
        NOTIFICATION: 'notification',
        KEEPALIVE: 'keepalive',
        ROUTE_REFRESH: 'refresh',
        OPERATIONAL: 'operational',
    }

    long_names: ClassVar[Dict[Optional[int], str]] = {
        None: 'invalid',
        NOP: 'nop',
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

    registered_message: ClassVar[Dict[int, Type[Message]]] = {}
    klass_unknown: ClassVar[Type[Exception]] = Exception

    # TYPE attribute set by subclasses
    TYPE: bytes
    ID: int

    class CODE:
        NOP: ClassVar[_MessageCode] = _MessageCode(_MessageCode.NOP)
        OPEN: ClassVar[_MessageCode] = _MessageCode(_MessageCode.OPEN)
        UPDATE: ClassVar[_MessageCode] = _MessageCode(_MessageCode.UPDATE)
        NOTIFICATION: ClassVar[_MessageCode] = _MessageCode(_MessageCode.NOTIFICATION)
        KEEPALIVE: ClassVar[_MessageCode] = _MessageCode(_MessageCode.KEEPALIVE)
        ROUTE_REFRESH: ClassVar[_MessageCode] = _MessageCode(_MessageCode.ROUTE_REFRESH)
        OPERATIONAL: ClassVar[_MessageCode] = _MessageCode(_MessageCode.OPERATIONAL)

        MESSAGES: ClassVar[List[_MessageCode]] = [
            NOP,
            OPEN,
            UPDATE,
            NOTIFICATION,
            KEEPALIVE,
            ROUTE_REFRESH,
            OPERATIONAL,
        ]

        @staticmethod
        def name(message_id: Optional[int]) -> str:
            if message_id is None:
                return _MessageCode.names.get(message_id, 'unknown message')
            return _MessageCode.names.get(message_id, 'unknown message {}'.format(hex(message_id)))

        @staticmethod
        def short(message_id: Optional[int]) -> str:
            if message_id is None:
                return _MessageCode.short_names.get(message_id, 'unknown message')
            return _MessageCode.short_names.get(message_id, 'unknown message {}'.format(hex(message_id)))

        # # Can raise KeyError
        # @staticmethod
        # def code (short):
        # 	return _MessageCode.names.get[short]

        def __init__(self) -> None:
            raise RuntimeError('This class can not be instantiated')

    Length: ClassVar[Dict[_MessageCode, Callable[[int], bool]]] = {
        CODE.OPEN: lambda _: _ >= 29,  # noqa
        CODE.UPDATE: lambda _: _ >= 23,  # noqa
        CODE.NOTIFICATION: lambda _: _ >= 21,  # noqa
        CODE.KEEPALIVE: lambda _: _ == 19,  # noqa
        CODE.ROUTE_REFRESH: lambda _: _ == 23,  # noqa
    }

    @staticmethod
    def string(code: Optional[int]) -> str:
        return _MessageCode.long_names.get(code, 'unknown')

    def _message(self, message: bytes) -> bytes:
        message_len: bytes = pack('!H', 19 + len(message))
        return self.MARKER + message_len + self.TYPE + message

    def message(self, negotiated: Optional[Negotiated] = None) -> bytes:
        raise NotImplementedError('message not implemented in subclasses')

    @classmethod
    def register(cls, klass: Type[Message]) -> Type[Message]:
        if klass.TYPE in cls.registered_message:
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
    def unpack(cls, message: int, data: bytes, direction: int, negotiated: Negotiated) -> Message:
        if message in cls.registered_message:
            return cls.klass(message).unpack_message(data, direction, negotiated)  # type: ignore[attr-defined,no-any-return]
        return cls.klass_unknown(message, data, direction, negotiated)  # type: ignore[return-value]

    @classmethod
    def code(cls, name: str) -> _MessageCode:
        for message in cls.CODE.MESSAGES:
            if name == str(message) or name == message.short():
                return message
        return cls.CODE.NOP
