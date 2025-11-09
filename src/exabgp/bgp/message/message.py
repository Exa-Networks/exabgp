
"""message.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack


class _MessageCode(int):
    NOP = 0x00  # .           0 - internal
    OPEN = 0x01  # .          1
    UPDATE = 0x02  # .        2
    NOTIFICATION = 0x03  # .  3
    KEEPALIVE = 0x04  # .     4
    ROUTE_REFRESH = 0x05  # . 5
    OPERATIONAL = 0x06  # .   6  # Not IANA assigned yet

    names = {
        None: 'INVALID',
        NOP: 'NOP',
        OPEN: 'OPEN',
        UPDATE: 'UPDATE',
        NOTIFICATION: 'NOTIFICATION',
        KEEPALIVE: 'KEEPALIVE',
        ROUTE_REFRESH: 'ROUTE_REFRESH',
        OPERATIONAL: 'OPERATIONAL',
    }

    short_names = {
        None: 'invalid',
        NOP: 'nop',
        OPEN: 'open',
        UPDATE: 'update',
        NOTIFICATION: 'notification',
        KEEPALIVE: 'keepalive',
        ROUTE_REFRESH: 'refresh',
        OPERATIONAL: 'operational',
    }

    long_names = {
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

    def __init__(self, value):
        self.SHORT = self.short()
        self.NAME = str(self)

    def __str__(self):
        return self.names.get(self, 'unknown message %s' % hex(self))

    def __repr__(self):
        return str(self)

    def short(self):
        return self.short_names.get(self, '%s' % self)


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

    MARKER = bytes(
        [
            0xFF,
        ]
        * 16,
    )
    HEADER_LEN = 19

    registered_message = {}
    klass_unknown = Exception

    class CODE:
        NOP = _MessageCode(_MessageCode.NOP)
        OPEN = _MessageCode(_MessageCode.OPEN)
        UPDATE = _MessageCode(_MessageCode.UPDATE)
        NOTIFICATION = _MessageCode(_MessageCode.NOTIFICATION)
        KEEPALIVE = _MessageCode(_MessageCode.KEEPALIVE)
        ROUTE_REFRESH = _MessageCode(_MessageCode.ROUTE_REFRESH)
        OPERATIONAL = _MessageCode(_MessageCode.OPERATIONAL)

        MESSAGES = [NOP, OPEN, UPDATE, NOTIFICATION, KEEPALIVE, ROUTE_REFRESH, OPERATIONAL]

        @staticmethod
        def name(message_id):
            return _MessageCode.names.get(message_id, 'unknown message %s' % hex(message_id))

        @staticmethod
        def short(message_id):
            return _MessageCode.short_names.get(message_id, 'unknown message %s' % hex(message_id))

        # # Can raise KeyError
        # @staticmethod
        # def code (short):
        # 	return _MessageCode.names.get[short]

        def __init__(self):
            raise RuntimeError('This class can not be instantiated')

    Length = {
        CODE.OPEN: lambda _: _ >= 29,  # noqa
        CODE.UPDATE: lambda _: _ >= 23,  # noqa
        CODE.NOTIFICATION: lambda _: _ >= 21,  # noqa
        CODE.KEEPALIVE: lambda _: _ == 19,  # noqa
        CODE.ROUTE_REFRESH: lambda _: _ == 23,  # noqa
    }

    @staticmethod
    def string(code):
        return _MessageCode.long_names.get(code, 'unknown')

    def _message(self, message):
        message_len = pack('!H', 19 + len(message))
        return self.MARKER + message_len + self.TYPE + message

    def message(self, negotiated=None):
        raise NotImplementedError('message not implemented in subclasses')

    @classmethod
    def register(cls, klass):
        if klass.TYPE in cls.registered_message:
            raise RuntimeError('only one class can be registered per message')
        cls.registered_message[klass.ID] = klass
        return klass

    @classmethod
    def klass(cls, what):
        if what in cls.registered_message:
            return cls.registered_message[what]
        from exabgp.bgp.message.notification import Notify

        raise Notify(2, 4, f'can not handle message {what}')

    @classmethod
    def unpack(cls, message, data, direction, negotiated):
        if message in cls.registered_message:
            return cls.klass(message).unpack_message(data, direction, negotiated)
        return cls.klass_unknown(message, data, direction, negotiated)

    @classmethod
    def code(cls, name):
        for message in cls.CODE.MESSAGES:
            if name == str(message) or name == message.short():
                return message
        return cls.CODE.NOP
