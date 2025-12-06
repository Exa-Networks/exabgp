"""keepalive.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from collections.abc import Buffer
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.util import hexstring

from exabgp.bgp.message.message import Message
from exabgp.bgp.message.notification import Notify

# =================================================================== KeepAlive
#


@Message.register
class KeepAlive(Message):
    ID = Message.CODE.KEEPALIVE
    TYPE = bytes([Message.CODE.KEEPALIVE])

    def __init__(self, packed: Buffer = b'') -> None:
        if packed:
            # Convert to bytes only on error path for the message
            raise ValueError(f'KeepAlive must have empty payload, got {len(bytes(packed))} bytes')
        # Two-buffer pattern: bytearray owns data, memoryview provides zero-copy slicing
        # For KeepAlive this is always empty
        self._buffer = bytearray()
        self._packed = memoryview(self._buffer)

    @classmethod
    def make_keepalive(cls) -> 'KeepAlive':
        return cls(b'')

    def pack_message(self, negotiated: Negotiated) -> bytes:
        return self._message(self._packed)

    def __str__(self) -> str:
        return 'KEEPALIVE'

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: Negotiated) -> KeepAlive:  # pylint: disable=W0613
        # This can not happen at decode time as we check the length of the KEEPALIVE message
        # But could happen when calling the function programmatically
        if data:
            raise Notify(1, 2, 'Keepalive can not have any payload but contains %s' % hexstring(bytes(data)))
        return cls(data)
