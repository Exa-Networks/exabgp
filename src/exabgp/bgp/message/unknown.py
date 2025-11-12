"""unknown.py

Created by Thomas Mangin on 2013-07-20.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.message import Message

# ================================================================= UnknownMessage
#


class UnknownMessage(Message):
    # Make sure we have a value, which is not defined in any RFC !

    def __init__(self, code: int, data: bytes = b'') -> None:
        self.ID = code
        self.TYPE = bytes([code])
        self.data = data

    def message(self, negotiated: Optional[Negotiated] = None) -> bytes:
        return self._message(self.data)

    def __str__(self) -> str:
        return 'UNKNOWN'

    @classmethod
    def unpack_message(cls, data: bytes) -> UnknownMessage:  # pylint: disable=W0613
        raise RuntimeError('should not have been used')


UnknownMessage.klass_unknown = UnknownMessage
