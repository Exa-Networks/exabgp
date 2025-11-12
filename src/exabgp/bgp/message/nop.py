"""nop.py

Created by Thomas Mangin on 2009-11-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.bgp.message.message import Message

# ========================================================================= NOP
#


class NOP(Message):
    ID = Message.CODE.NOP
    TYPE = bytes([Message.CODE.NOP])

    def message(self, negotiated: Any = None) -> bytes:
        raise RuntimeError('NOP messages can not be sent on the wire')

    def __str__(self) -> str:
        return 'NOP'

    @classmethod
    def unpack_message(cls, data: bytes, direction: int, negotiated: Any) -> NOP:  # pylint: disable=W0613
        return NOP()


_NOP: NOP = NOP()
