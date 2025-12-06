"""unknown.py

Created by Thomas Mangin on 2013-07-20.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from collections.abc import Buffer
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.message import Message

# ================================================================= UnknownMessage
#


class UnknownMessage(Message):
    # Make sure we have a value, which is not defined in any RFC !

    def __init__(self, code: int, data: Buffer = b'', negotiated: Negotiated | None = None) -> None:
        self.ID = code
        self.TYPE = bytes([code])
        # Two-buffer pattern: bytearray owns data, memoryview provides zero-copy slicing
        self._buffer = bytearray(data)
        self.data = memoryview(self._buffer)

    def pack_message(self, negotiated: Negotiated) -> bytes:
        return self._message(self.data)

    def __str__(self) -> str:
        return 'UNKNOWN'

    @classmethod
    def unpack_message(cls, data: Buffer) -> UnknownMessage:  # pylint: disable=W0613
        raise RuntimeError('should not have been used')


UnknownMessage.klass_unknown = UnknownMessage
