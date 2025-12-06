"""scheduling.py

Internal message types for reactor scheduling control.
These are not BGP wire messages - they signal scheduling intent.

Created by Thomas Mangin on 2022-05-19.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from collections.abc import Buffer
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.message import Message


class Scheduling(IntEnum):
    """Reactor scheduling actions for internal message types"""

    MESSAGE = 0x00  # . Real BGP messages (not scheduling)
    NOW = 0x01  # .     Immediate action needed
    LATER = 0x02  # .   No data yet, check later
    CLOSE = 0x03  # .   Peer finished, remove from reactor

    def __str__(self) -> str:
        return self.__format__('s')

    def __format__(self, what: str) -> str:
        if what == 's':
            if self is Scheduling.MESSAGE:
                return 'message'
            if self is Scheduling.LATER:
                return 'later'
            if self is Scheduling.NOW:
                return 'now'
            if self is Scheduling.CLOSE:
                return 'close'
        return 'unknown'


class NOP(Message):
    """No operation - signals 'no data yet, check later'"""

    ID = Message.CODE.NOP
    TYPE = bytes([Message.CODE.NOP])
    SCHEDULING = Scheduling.LATER

    def pack_message(self, negotiated: Negotiated) -> bytes:
        raise RuntimeError('NOP messages can not be sent on the wire')

    def __str__(self) -> str:
        return 'NOP'

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: Negotiated) -> NOP:
        return _NOP


class AWAKE(Message):
    """Awake - signals 'immediate action needed'"""

    ID = Message.CODE.AWAKE
    TYPE = bytes([Message.CODE.AWAKE])
    SCHEDULING = Scheduling.NOW

    def pack_message(self, negotiated: Negotiated) -> bytes:
        raise RuntimeError('AWAKE messages can not be sent on the wire')

    def __str__(self) -> str:
        return 'AWAKE'

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: Negotiated) -> AWAKE:
        return _AWAKE


class DONE(Message):
    """Done - signals 'peer finished, remove from reactor'"""

    ID = Message.CODE.DONE
    TYPE = bytes([Message.CODE.DONE])
    SCHEDULING = Scheduling.CLOSE

    def pack_message(self, negotiated: Negotiated) -> bytes:
        raise RuntimeError('DONE messages can not be sent on the wire')

    def __str__(self) -> str:
        return 'DONE'

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: Negotiated) -> DONE:
        return _DONE


# Singletons for reactor scheduling
_NOP: NOP = NOP()
_AWAKE: AWAKE = AWAKE()
_DONE: DONE = DONE()
